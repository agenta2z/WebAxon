"""Run scoring, sanitization, and evaluator invocation.

Migrated from ``_dev/external/evaluation_framework/evaluators/online_mind2web/run_eval.py``.

Key changes from the original:
- ``run_eval()`` calls ``evaluator.run.parallel_eval()`` directly (no subprocess).
- ``run_eval()`` accepts an ``engine_factory`` callable instead of raw CLI args.
- ``sanitize_runs()`` also copies ``*_snapshot_text.txt`` DOM content files.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Callable, List, Optional

from .evaluator.utils import EvalLLMEngine

# ---------------------------------------------------------------------------
# Image extensions recognised in trajectory directories
# ---------------------------------------------------------------------------
_IMAGE_EXTS = {".png", ".jpg", ".jpeg"}

# ---------------------------------------------------------------------------
# Infrastructure-failure patterns
# ---------------------------------------------------------------------------
_SKIP_PATTERNS: List[str] = [
    # Legacy patterns for backward compat with runs generated via AI Gateway
    "Adapter act error: AI Gateway",
    "AIGatewayRequestError",
    # Browser / network errors (infrastructure failures, not agent failures)
    "net::ERR_",
    "Reset error: Navigation failed",
    "Navigation failed",
    "net::ERR_HTTP2_PROTOCOL_ERROR",
    "net::ERR_CONNECTION_RESET",
    "net::ERR_CONNECTION_REFUSED",
    "net::ERR_NAME_NOT_RESOLVED",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_infra_failure(result_path: Path) -> bool:
    """Return *True* if ``result.json`` indicates an infrastructure failure."""
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception:
        return False

    final = data.get("final_result_response", "")
    thoughts = data.get("thoughts", [])

    # Check final_result_response
    for pat in _SKIP_PATTERNS:
        if pat in final:
            return True

    # Also check last thought (sometimes the error only appears there)
    if thoughts:
        last = thoughts[-1] if isinstance(thoughts[-1], str) else ""
        for pat in _SKIP_PATTERNS:
            if pat in last:
                return True

    return False


# ---------------------------------------------------------------------------
# sanitize_runs
# ---------------------------------------------------------------------------

def sanitize_runs(
    runs_dir: Path,
    sanitized_dir: Path,
    overwrite: bool = False,
) -> List[str]:
    """Filter infrastructure failures and copy valid runs to *sanitized_dir*.

    For each task directory under *runs_dir* that contains ``result.json`` and
    a ``trajectory/`` sub-directory:

    * Skip the task if ``_is_infra_failure()`` is *True*.
    * Otherwise copy ``result.json``, trajectory screenshots (excluding
      ``_post_`` screenshots), and ``*_snapshot_text.txt`` DOM content files
      (when present) into the corresponding location under *sanitized_dir*.

    Returns the list of excluded (skipped) task IDs.
    """
    if sanitized_dir.exists():
        if not overwrite:
            raise FileExistsError(f"Sanitized dir exists: {sanitized_dir}")
        shutil.rmtree(sanitized_dir)
    sanitized_dir.mkdir(parents=True, exist_ok=True)

    skipped: List[str] = []

    for task_dir in sorted(runs_dir.iterdir()):
        if not task_dir.is_dir():
            continue

        result_path = task_dir / "result.json"
        traj_dir = task_dir / "trajectory"
        if not result_path.exists() or not traj_dir.exists():
            continue

        # Skip tasks that failed due to infrastructure errors
        if _is_infra_failure(result_path):
            skipped.append(task_dir.name)
            continue

        dest_task_dir = sanitized_dir / task_dir.name
        dest_traj_dir = dest_task_dir / "trajectory"
        dest_traj_dir.mkdir(parents=True, exist_ok=True)

        # Copy result.json
        shutil.copy2(result_path, dest_task_dir / "result.json")

        # Copy trajectory contents
        for item in traj_dir.iterdir():
            if not item.is_file():
                continue

            # Copy screenshots (skip post-action duplicates)
            if item.suffix.lower() in _IMAGE_EXTS:
                if "_post_" in item.name:
                    continue
                shutil.copy2(item, dest_traj_dir / item.name)

            # Copy snapshot DOM text files
            elif item.name.endswith("_snapshot_text.txt"):
                shutil.copy2(item, dest_traj_dir / item.name)

    if skipped:
        print(
            f"⚠️  Excluded {len(skipped)} task(s) due to infrastructure errors "
            f"(gateway / network / browser):"
        )
        for tid in skipped:
            print(f"   - {tid}")

    return skipped


# ---------------------------------------------------------------------------
# write_retry_tasks
# ---------------------------------------------------------------------------

def write_retry_tasks(
    excluded_ids: List[str],
    tasks_jsonl: Path,
    output_path: Path,
) -> int:
    """Write a JSONL file containing only the tasks whose IDs are in *excluded_ids*.

    This is useful for re-running tasks that were excluded during sanitization.
    Returns the number of tasks written.
    """
    id_set = set(excluded_ids)
    written = 0
    with tasks_jsonl.open("r", encoding="utf-8") as fin, \
         output_path.open("w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("task_id", "").strip() in id_set:
                fout.write(line)
                written += 1
    return written


# ---------------------------------------------------------------------------
# run_eval  —  orchestrate sanitization + evaluator invocation
# ---------------------------------------------------------------------------

def run_eval(
    runs_dir: Path,
    engine_factory: Callable[[], EvalLLMEngine],
    mode: str = "WebJudge_Online_Mind2Web_eval",
    score_threshold: int = 3,
    num_worker: int = 1,
    output_path: Optional[Path] = None,
) -> None:
    """Orchestrate sanitization and evaluator invocation as direct Python calls.

    *engine_factory* is a zero-arg callable that creates a fresh
    :class:`EvalLLMEngine` instance.  Each worker thread calls
    ``engine_factory()`` for isolation — any callable works (lambda, closure,
    ``functools.partial``, class) since threading has no pickling constraints.

    Calls :func:`evaluator.run.parallel_eval` directly — no subprocess.
    """
    if engine_factory is None:
        raise ValueError(
            "engine_factory is required. Pass a zero-arg callable that returns "
            "an EvalLLMEngine instance."
        )

    if not runs_dir.exists():
        raise FileNotFoundError(f"runs_dir not found: {runs_dir}")

    # 1. Sanitize runs
    sanitized_dir = runs_dir.parent / f"{runs_dir.name}_sanitized"
    excluded = sanitize_runs(runs_dir, sanitized_dir, overwrite=True)

    if excluded:
        print(f"\n📋 {len(excluded)} task(s) excluded from evaluation.")

    # 2. Resolve output path
    resolved_output = (
        str(output_path) if output_path is not None
        else str(runs_dir.parent / f"{runs_dir.name}_eval")
    )

    # 3. Call evaluator directly (no subprocess)
    from .evaluator.run import parallel_eval

    parallel_eval(
        trajectories_dir=str(sanitized_dir),
        engine_factory=engine_factory,
        mode=mode,
        score_threshold=score_threshold,
        num_worker=num_worker,
        output_path=resolved_output,
    )
