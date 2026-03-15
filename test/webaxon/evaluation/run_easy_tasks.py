"""Run all easy tasks from the Online-Mind2Web dataset sequentially.

Stops on first agent crash (not eval failure). Prints progress and summary.

Usage::

    cd WebAxon
    PYTHONPATH="src;../RichPythonUtils/src;../AgentFoundation/src" python test/webaxon/evaluation/run_easy_tasks.py [--output-dir OUTPUT] [--skip N] [--max-tasks N]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Path setup
_SCRIPT_DIR = Path(__file__).resolve().parent
_WEBAXON_ROOT = _SCRIPT_DIR.parents[2]
_SRC = _WEBAXON_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_PROJECTS = _WEBAXON_ROOT.parent
for dep in ["RichPythonUtils/src", "AgentFoundation/src"]:
    p = _PROJECTS / dep
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("easy_runner")


def main():
    parser = argparse.ArgumentParser(description="Run easy tasks")
    parser.add_argument(
        "--output-dir",
        default=str(_WEBAXON_ROOT / "_easy_runs"),
        help="Output directory for results",
    )
    parser.add_argument("--skip", type=int, default=0, help="Skip first N easy tasks")
    parser.add_argument("--max-tasks", type=int, default=0, help="Max tasks to run (0=all)")
    parser.add_argument("--agent-timeout", type=int, default=300, help="Agent timeout in seconds")
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    parser.add_argument(
        "--template-version",
        default="",
        help="Template version (e.g. 'end_customers'). Empty=default templates.",
    )
    args = parser.parse_args()

    # Load easy tasks
    tasks_path = _WEBAXON_ROOT / "data" / "online_mind2web" / "processed" / "tasks.jsonl"
    from webaxon.evaluation.tasks import EvaluationTask, load_tasks

    all_tasks = load_tasks(tasks_path)
    easy_tasks = [t for t in all_tasks if t.level == "easy"]
    logger.info("Loaded %d easy tasks (of %d total)", len(easy_tasks), len(all_tasks))

    # Apply skip/limit
    easy_tasks = easy_tasks[args.skip:]
    if args.max_tasks > 0:
        easy_tasks = easy_tasks[:args.max_tasks]
    logger.info("Running %d tasks (skip=%d, max=%d)", len(easy_tasks), args.skip, args.max_tasks)

    # Workspace
    workspace = (
        _WEBAXON_ROOT / "src" / "webaxon" / "devsuite"
        / "web_agent_service_nextgen" / "_workspace"
    )
    if not workspace.is_dir():
        logger.error("Workspace not found: %s", workspace)
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build adapter
    from webaxon.evaluation.adapters.webaxon_adapter import WebAxonAdapter
    from webaxon.evaluation.config import EvaluationConfig
    from webaxon.evaluation.runner import EvaluationRunner

    adapter = WebAxonAdapter(
        testcase_root=workspace,
        agent_type="DefaultAgent",
        template_version=args.template_version,
        headless=args.headless,
        agent_timeout=args.agent_timeout,
    )

    config = EvaluationConfig(
        adapter_name="webaxon",
        max_steps=30,
        agent_timeout=args.agent_timeout,
        output_dir=output_dir,
    )

    runner = EvaluationRunner(adapter=adapter, config=config)

    # Run
    results = []
    start_all = time.time()

    for i, task in enumerate(easy_tasks, 1):
        # Check if already completed
        result_path = output_dir / task.task_id / "result.json"
        if result_path.exists():
            logger.info("[%d/%d] SKIP (already done): %s", i, len(easy_tasks), task.task_id[:16])
            try:
                existing = json.loads(result_path.read_text(encoding="utf-8"))
                results.append(existing)
            except Exception:
                pass
            continue

        logger.info(
            "[%d/%d] RUNNING: %s | %s | ref_len=%d",
            i, len(easy_tasks), task.task_id[:16], task.task[:60], task.reference_length,
        )

        task_start = time.time()
        try:
            result_dict = runner.run_task(task)
            duration = time.time() - task_start
            error = result_dict.get("error")
            answer = result_dict.get("final_result_response", "")[:100]

            if error:
                logger.error(
                    "[%d/%d] AGENT CRASH after %.1fs: %s — %s",
                    i, len(easy_tasks), duration, task.task_id[:16], error[:200],
                )
                # Stop on crash
                logger.error("Stopping on first crash. Task: %s", task.task_id)
                results.append(result_dict)
                break
            else:
                logger.info(
                    "[%d/%d] DONE in %.1fs | steps=%d | screenshots=%d | answer=%s",
                    i, len(easy_tasks), duration,
                    result_dict.get("num_steps", 0),
                    result_dict.get("num_screenshots", 0),
                    answer,
                )
                results.append(result_dict)

        except Exception as exc:
            duration = time.time() - task_start
            logger.error(
                "[%d/%d] EXCEPTION after %.1fs: %s — %s",
                i, len(easy_tasks), duration, task.task_id[:16], exc,
            )
            logger.error("Stopping on first exception. Task: %s", task.task_id)
            break
        finally:
            try:
                adapter.cleanup()
            except Exception:
                pass

    total_time = time.time() - start_all

    # Summary
    print("\n" + "=" * 60)
    print(f"  EASY TASKS SUMMARY")
    print(f"  Completed: {len(results)} / {len(easy_tasks)}")
    print(f"  Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
    crashes = sum(1 for r in results if r.get("error"))
    print(f"  Crashes: {crashes}")
    no_answer = sum(1 for r in results if not r.get("final_result_response") or r.get("final_result_response", "").startswith("Task not completed"))
    print(f"  No answer: {no_answer}")
    with_answer = len(results) - crashes - no_answer
    print(f"  With answer: {with_answer}")
    print(f"  Output: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
