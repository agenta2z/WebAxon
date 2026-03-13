"""Download and preprocess Online-Mind2Web from HuggingFace.

Migrated from ``_dev/external/evaluation_framework/src/datasets/online_mind2web.py``.
Outputs JSONL compatible with :func:`webaxon.evaluation.tasks.load_tasks`.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


def _resolve_hf_token(explicit_token: Optional[str]) -> Optional[str]:
    """Resolve HuggingFace token: parameter → ``HF_TOKEN`` env → ``HUGGINGFACE_TOKEN`` env."""
    if explicit_token:
        return explicit_token
    return os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")


def _normalize_start_url(website: str) -> str:
    """Prepend ``https://`` when no scheme is present."""
    website = (website or "").strip()
    if not website:
        return ""
    if website.startswith("http://") or website.startswith("https://"):
        return website
    return f"https://{website}"


def download_dataset(
    out_root: Path,
    split: str = "test",
    hf_token: Optional[str] = None,
    overwrite: bool = False,
) -> Dict[str, int]:
    """Download Online-Mind2Web from HuggingFace and write preprocessed JSONL.

    Parameters
    ----------
    out_root:
        Root output directory.  Creates ``raw/``, ``processed/``, and
        ``metadata/`` subdirectories.
    split:
        HuggingFace dataset split (default ``"test"``).
    hf_token:
        Explicit HuggingFace token.  Falls back to ``HF_TOKEN`` /
        ``HUGGINGFACE_TOKEN`` environment variables.
    overwrite:
        When *False* and the processed file already exists, raise
        :class:`FileExistsError`.

    Returns
    -------
    dict
        Counts: ``{"raw": int, "processed": int, "skipped": int}``.
    """
    try:
        from datasets import load_dataset as hf_load_dataset  # type: ignore[import-untyped]
        import datasets as datasets_pkg  # type: ignore[import-untyped]
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Missing 'datasets' dependency. Install with: pip install datasets"
        ) from exc

    out_root = Path(out_root)
    raw_dir = out_root / "raw"
    processed_dir = out_root / "processed"
    metadata_dir = out_root / "metadata"

    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    raw_path = raw_dir / f"{split}.jsonl"
    processed_path = processed_dir / "tasks.jsonl"
    metadata_path = metadata_dir / "source.json"

    if not overwrite and processed_path.exists():
        raise FileExistsError(f"Processed file already exists: {processed_path}")

    token = _resolve_hf_token(hf_token)
    if not token:
        raise RuntimeError(
            "Hugging Face token required. Set HF_TOKEN (or pass --hf_token)."
        )

    dataset = hf_load_dataset("osunlp/Online-Mind2Web", split=split, token=token)

    raw_count = 0
    processed_count = 0
    skipped = 0

    with raw_path.open("w", encoding="utf-8") as raw_f, \
         processed_path.open("w", encoding="utf-8") as proc_f:
        for row in dataset:
            raw_f.write(json.dumps(row, ensure_ascii=False) + "\n")
            raw_count += 1

            task_id = str(row.get("task_id", "")).strip()
            website = str(row.get("website", "")).strip()
            task_desc = str(row.get("confirmed_task", "")).strip()
            ref_len = row.get("reference_length", 0)
            try:
                reference_length = int(ref_len)
            except (TypeError, ValueError):
                reference_length = 0

            start_url = _normalize_start_url(website)

            if not task_id or not task_desc or not start_url:
                skipped += 1
                continue

            level = str(row.get("level", "")).strip().lower()

            proc_f.write(
                json.dumps(
                    {
                        "task_id": task_id,
                        "website": website,
                        "task": task_desc,
                        "reference_length": reference_length,
                        "start_url": start_url,
                        "split": split,
                        "level": level,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            processed_count += 1

    # ── metadata ──────────────────────────────────────────────────────
    metadata = {
        "dataset": "osunlp/Online-Mind2Web",
        "split": split,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "num_rows_raw": raw_count,
        "num_rows_processed": processed_count,
        "num_rows_skipped": skipped,
        "fingerprint": getattr(dataset, "_fingerprint", None),
        "features": {k: str(v) for k, v in dataset.features.items()},
        "datasets_version": getattr(datasets_pkg, "__version__", "unknown"),
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "raw": raw_count,
        "processed": processed_count,
        "skipped": skipped,
    }
