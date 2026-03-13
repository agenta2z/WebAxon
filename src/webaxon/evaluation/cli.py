"""CLI entry point for the WebAxon evaluation framework.

Usage::

    # Single demo task
    python -m webaxon.evaluation.cli --demo \\
        --task "Search for Python tutorials" \\
        --start_url "https://google.com"

    # Run Online-Mind2Web dataset
    python -m webaxon.evaluation.cli \\
        --tasks tasks.jsonl --limit 5 --level easy --output runs/

    # With custom workspace
    python -m webaxon.evaluation.cli \\
        --adapter webaxon --tasks tasks.jsonl \\
        --workspace path/to/workspace
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_DEFAULT_TASKS_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "online_mind2web"
    / "processed"
    / "tasks.jsonl"
)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="WebAxon Evaluation Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Adapter
    parser.add_argument(
        "--adapter",
        default="webaxon",
        help="Adapter name (default: webaxon)",
    )

    # Task source (mutually exclusive)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--demo",
        action="store_true",
        help="Run a single demo task (requires --task and --start_url)",
    )
    group.add_argument(
        "--tasks",
        type=Path,
        default=_DEFAULT_TASKS_PATH,
        help=f"Path to JSONL task file (default: {_DEFAULT_TASKS_PATH})",
    )
    group.add_argument(
        "--download",
        action="store_true",
        help="Download Online-Mind2Web dataset from HuggingFace",
    )
    group.add_argument(
        "--eval",
        action="store_true",
        help="Run evaluation scoring on completed runs",
    )

    # Demo task options
    parser.add_argument("--task", help="Task description (for --demo mode)")
    parser.add_argument("--start_url", help="Start URL (for --demo mode)")

    # Download options
    parser.add_argument("--hf_token", help="HuggingFace token (for --download mode)")
    parser.add_argument("--split", default="test", help="Dataset split (default: test)")
    parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing files"
    )

    # Eval options
    parser.add_argument(
        "--runs_dir", type=Path, help="Path to runs directory (for --eval mode)"
    )
    parser.add_argument(
        "--inferencer",
        choices=["openai", "claude"],
        default="openai",
        help="Inferencer backend (default: openai)",
    )
    parser.add_argument("--model", help="Model ID for the inferencer")
    parser.add_argument(
        "--mode",
        default="WebJudge_Online_Mind2Web_eval",
        help="Evaluation mode (default: WebJudge_Online_Mind2Web_eval)",
    )
    parser.add_argument(
        "--score_threshold", type=int, default=3, help="Score threshold (default: 3)"
    )
    parser.add_argument(
        "--num_worker", type=int, default=1, help="Number of worker threads (default: 1)"
    )

    # Dataset options
    parser.add_argument("--limit", type=int, help="Max number of tasks to run")
    parser.add_argument("--offset", type=int, default=0, help="Skip first N tasks")
    parser.add_argument("--level", help="Filter tasks by difficulty level")

    # Config
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("runs"),
        help="Output directory (default: runs/)",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        help="WebAxon workspace (testcase_root). Defaults to devsuite/_workspace.",
    )
    parser.add_argument("--max_steps", type=int, default=50, help="Max agent steps per task")
    parser.add_argument("--timeout", type=int, default=300, help="Agent timeout in seconds")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--chrome_version", type=int, help="Chrome version override")
    parser.add_argument("--agent_type", default="DefaultAgent", help="Agent type")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args(argv)

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # ── Download mode (no adapter/runner needed) ──────────────────────
    if args.download:
        from webaxon.evaluation.datasets import download_dataset

        counts = download_dataset(
            out_root=args.output,
            split=args.split,
            hf_token=args.hf_token,
            overwrite=args.overwrite,
        )
        print(f"Download complete → {args.output}")
        print(f"  Raw rows:       {counts['raw']}")
        print(f"  Processed rows: {counts['processed']}")
        print(f"  Skipped:        {counts['skipped']}")
        return

    # ── Eval mode (no adapter/runner needed) ──────────────────────────
    if args.eval:
        if not args.runs_dir:
            parser.error("--eval requires --runs_dir")
        if not args.model:
            parser.error("--eval requires --model")

        from webaxon.evaluation.evaluator.utils import InferencerEngine
        from webaxon.evaluation.scoring import run_eval

        if args.inferencer == "claude":
            from agent_foundation.common.inferencers.api_inferencers.claude_api_inferencer import ClaudeApiInferencer
            engine_factory = lambda: InferencerEngine(ClaudeApiInferencer(model_id=args.model))
        else:
            from agent_foundation.common.inferencers.api_inferencers.openai_api_inferencer import OpenaiApiInferencer
            engine_factory = lambda: InferencerEngine(OpenaiApiInferencer(model_id=args.model))

        run_eval(
            runs_dir=args.runs_dir,
            engine_factory=engine_factory,
            mode=args.mode,
            score_threshold=args.score_threshold,
            num_worker=args.num_worker,
        )
        return

    # Resolve workspace
    workspace = args.workspace
    if workspace is None:
        # Default: look for devsuite/_workspace relative to this file
        workspace = (
            Path(__file__).resolve().parent.parent
            / "devsuite"
            / "web_agent_service_nextgen"
            / "_workspace"
        )
        if not workspace.is_dir():
            print(f"Error: Default workspace not found at {workspace}")
            print("Use --workspace to specify the testcase_root directory.")
            sys.exit(1)

    # Build adapter
    from webaxon.evaluation.adapters import get_adapter

    adapter = get_adapter(
        args.adapter,
        testcase_root=workspace,
        agent_type=args.agent_type,
        chrome_version=args.chrome_version,
        headless=args.headless,
        agent_timeout=args.timeout,
    )

    # Build config
    from webaxon.evaluation.config import EvaluationConfig

    config = EvaluationConfig(
        adapter_name=args.adapter,
        max_steps=args.max_steps,
        agent_timeout=args.timeout,
        output_dir=args.output,
    )

    # Build runner
    from webaxon.evaluation.runner import EvaluationRunner

    runner = EvaluationRunner(adapter=adapter, config=config)

    if args.demo:
        # Demo mode: single task
        if not args.task or not args.start_url:
            parser.error("--demo requires --task and --start_url")

        from webaxon.evaluation.tasks import EvaluationTask

        task = EvaluationTask(
            task_id="demo_001",
            task=args.task,
            start_url=args.start_url,
        )
        result = runner.run_task(task)
        print("\n=== Demo Result ===")
        print(f"Answer: {result.get('final_result_response', 'N/A')}")
        print(f"Confidence: {result.get('confidence', 0.0)}")
        print(f"Steps: {result.get('num_steps', 0)}")
        print(f"Duration: {result.get('duration_seconds', 0.0)}s")
        print(f"Output: {args.output / 'demo_001'}")

    elif args.tasks:
        # Dataset mode
        from webaxon.evaluation.tasks import load_tasks

        tasks = load_tasks(
            args.tasks,
            level=args.level,
            limit=args.limit,
            offset=args.offset,
        )

        if not tasks:
            print("No tasks loaded. Check filters and file path.")
            sys.exit(1)

        print(f"Loaded {len(tasks)} tasks. Starting evaluation...")
        answers_path = runner.run_dataset(tasks)
        print(f"\nDone. Answers: {answers_path}")


if __name__ == "__main__":
    main()
