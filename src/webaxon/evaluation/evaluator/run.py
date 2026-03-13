"""Main evaluator entry point — migrated and refactored.

Changes from original:
- Flattened src/ nesting; all imports are relative.
- Replaced multiprocessing.Process + Manager() with parallel_process_by_pool + ThreadPool.
- auto_eval() and parallel_eval() accept engine/engine_factory instead of args for model creation.
- Removed _create_model_engine() and argparse __main__ block (invoked from scoring.py).
"""

import os
import re
import json
import copy
import asyncio
import threading
from typing import Callable, Optional

from multiprocessing.pool import ThreadPool

from .methods.agenttrek_eval import *
from .methods.automomous_eval import *
from .methods.webjudge_general_eval import *
from .methods.webjudge_online_mind2web import *
from .methods.webvoyager_eval import *
from .utils import extract_predication
from .clean_html import process_element_tag, SALIENT_ATTRIBUTES

# Image extensions for filtering trajectory files
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _load_screenshot_paths(trajectory_dir):
    paths = []
    for fname in os.listdir(trajectory_dir):
        fpath = os.path.join(trajectory_dir, fname)
        if not os.path.isfile(fpath):
            continue
        _, ext = os.path.splitext(fname)
        if ext.lower() not in _IMAGE_EXTS:
            continue
        # Skip post-action screenshots (redundant with next step's pre-screenshot)
        if "_post_" in fname:
            continue
        paths.append(fpath)
    # Sort by leading number, matching the official repo's sort key
    paths.sort(key=lambda x: int(re.findall(r'\d+', os.path.basename(x))[0]))
    return paths


def _load_snapshot_texts(trajectory_dir):
    """Load *_snapshot_text.txt files (DOM content the agent used). Sorted by index."""
    texts = []
    for fname in sorted(os.listdir(trajectory_dir)):
        if not fname.endswith("_snapshot_text.txt"):
            continue
        fpath = os.path.join(trajectory_dir, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            texts.append((fpath, open(fpath, encoding="utf-8", errors="replace").read()))
        except Exception:
            pass
    # Sort by leading number (1_, 2_, ...)
    texts.sort(key=lambda x: int(re.findall(r'\d+', os.path.basename(x[0]))[0]))
    return texts


# Action types that are NOT factual browser actions — exclude from eval history.
_NON_FACTUAL_PREFIXES = (
    "DONE ",
    "WAIT ",
    "DISMISS_OVERLAYS",
)

# Regex to detect raw HTML tags in action strings
_HTML_TAG_RE = re.compile(r"<[a-zA-Z][^>]*>")


def _clean_action_history(action_history):
    if not action_history:
        return action_history

    cleaned = []
    for action in action_history:
        action_str = str(action).strip()

        # 1. Skip non-factual actions
        if any(action_str.startswith(prefix) for prefix in _NON_FACTUAL_PREFIXES):
            continue

        # 2. Clean any raw HTML tags in the action string
        if _HTML_TAG_RE.search(action_str):
            action_str = process_element_tag(action_str, SALIENT_ATTRIBUTES)

        cleaned.append(action_str)

    return cleaned


def auto_eval(task_dir, engine, mode, score_threshold, output_path, trajectories_dir):
    """Evaluate a single task directory.

    Args:
        task_dir: Task directory name (task_id).
        engine: An EvalLLMEngine instance with .generate(messages) -> List[str].
        mode: Evaluation mode string.
        score_threshold: Score threshold for image filtering.
        output_path: Directory to write results.
        trajectories_dir: Parent directory containing task_dir subdirectories.
    """
    task_id = task_dir

    # Check if already done
    output_json_path = os.path.join(
        output_path, f"{mode}_score_threshold_{score_threshold}_auto_eval_results.json"
    )
    already_ids = []
    if os.path.exists(output_json_path):
        with open(output_json_path, "r") as f:
            already_data = f.read()
        already_tasks = already_data.splitlines()
        for item in already_tasks:
            if not item.strip():
                continue
            item = json.loads(item)
            already_ids.append(item["task_id"])

    if task_id in already_ids:
        return None

    trajectory_images_path = os.path.join(trajectories_dir, task_id, "trajectory")
    thoughts = None
    action_history = None
    final_result_response = None
    input_image_paths = None
    task_description = None

    # Load results
    with open(os.path.join(trajectories_dir, task_id, "result.json")) as f:
        result = json.load(f)
        output_results = copy.deepcopy(result)
        task_description = result["task"]
        if "action_history" in result:
            action_history = result["action_history"]
        if "thoughts" in result:
            thoughts = result["thoughts"]
        if "final_result_response" in result:
            final_result_response = result["final_result_response"]
        if "input_image_paths" in result:
            input_image_paths = result["input_image_paths"]

    # Clean action history: remove DONE/WAIT/DISMISS_OVERLAYS + strip raw HTML
    clean_actions = _clean_action_history(action_history)

    # Load screenshots: only images, no post-action shots, sorted by step number
    screenshot_paths = _load_screenshot_paths(trajectory_images_path)
    snapshot_texts = _load_snapshot_texts(trajectory_images_path)

    print(f"Start evaluation for {task_description}")
    print(f"  action_history: {len(action_history or [])} raw → {len(clean_actions or [])} after cleaning")
    print(f"  screenshots: {len(screenshot_paths)} images")
    if snapshot_texts:
        print(f"  snapshot_texts: {len(snapshot_texts)} files (DOM content agent used)")

    # Do the auto-eval
    if mode == "Autonomous_eval":
        messages, text, system_msg = Autonomous_eval(task_description, clean_actions, screenshot_paths[-1])

    elif mode == "AgentTrek_eval":
        messages, text, system_msg = AgentTrek_eval(task_description, clean_actions, thoughts, screenshot_paths[-1])

    elif mode == "WebVoyager_eval":
        messages, text, system_msg = WebVoyager_eval(task_description, screenshot_paths, final_result_response)

    elif mode == "WebJudge_Online_Mind2Web_eval":
        messages, text, system_msg, record, key_points = asyncio.run(WebJudge_Online_Mind2Web_eval(
            task_description, clean_actions, screenshot_paths, engine, score_threshold,
            snapshot_texts=snapshot_texts,
        ))
        output_results["image_judge_record"] = record
        output_results["key_points"] = key_points

    elif mode == "WebJudge_general_eval":
        messages, text, system_msg, record, key_points = asyncio.run(WebJudge_general_eval(
            task_description, input_image_paths, thoughts, clean_actions, screenshot_paths, engine, score_threshold
        ))
        output_results["image_judge_record"] = record
        output_results["key_points"] = key_points

    else:
        raise ValueError(f"Unknown mode: {mode}")

    # Final judgment
    response = engine.generate(messages)[0]
    predicted_label = extract_predication(response, mode)

    # Store evaluation details
    evaluation_results = {"response": response, "predicted_label": predicted_label}
    output_results["task_id"] = task_id
    output_results["input_text"] = text
    output_results["system_msg"] = system_msg
    output_results["evaluation_details"] = evaluation_results
    output_results["predicted_label"] = predicted_label

    print(f"Finish evaluation for {task_description}")
    print("=" * 20)
    os.makedirs(output_path, exist_ok=True)
    with open(output_json_path, "a+") as f_out:
        f_out.write(json.dumps(output_results) + "\n")

    return predicted_label


def parallel_eval(
    trajectories_dir: str,
    engine_factory: Callable,
    mode: str = "WebJudge_Online_Mind2Web_eval",
    score_threshold: int = 3,
    num_worker: int = 1,
    output_path: Optional[str] = None,
    debug: bool = False,
):
    """Evaluate tasks in parallel using threads (I/O-bound LLM API calls).

    Args:
        trajectories_dir: Directory containing task subdirectories.
        engine_factory: Zero-arg callable that creates a fresh EvalLLMEngine instance.
            Each thread calls engine_factory() for isolation. Can be any callable
            (lambda, closure, partial) — no pickling constraints with threading.
        mode: Evaluation mode string.
        score_threshold: Score threshold for image filtering.
        num_worker: Number of parallel workers.
        output_path: Directory to write results. Defaults to trajectories_dir + "_eval".
        debug: If True, run single-threaded for debugging.
    """
    from rich_python_utils.mp_utils.parallel_process import parallel_process_by_pool

    if output_path is None:
        output_path = trajectories_dir.rstrip("/") + "_eval"

    task_dirs = [
        d for d in sorted(os.listdir(trajectories_dir))
        if os.path.isdir(os.path.join(trajectories_dir, d))
    ]
    print(f"Evaluating {len(task_dirs)} tasks in total.")
    if not task_dirs:
        print("No tasks found. Exiting.")
        return

    def worker(pid, chunk, engine_factory, mode, score_threshold, output_path, trajectories_dir):
        engine = engine_factory()
        results = []
        for task_dir in chunk:
            label = auto_eval(task_dir, engine, mode, score_threshold, output_path, trajectories_dir)
            if label is not None:
                results.append(label)
        return results

    if debug or num_worker <= 1:
        # Single-threaded mode
        engine = engine_factory()
        labels = []
        for task_dir in task_dirs:
            label = auto_eval(task_dir, engine, mode, score_threshold, output_path, trajectories_dir)
            if label is not None:
                labels.append(label)
    else:
        all_results = parallel_process_by_pool(
            num_p=num_worker,
            data_iter=task_dirs,
            target=worker,
            args=(engine_factory, mode, score_threshold, output_path, trajectories_dir),
            pool_object=ThreadPool,
        )
        # Flatten results from all workers
        labels = []
        if isinstance(all_results, list):
            for chunk_result in all_results:
                if isinstance(chunk_result, list):
                    labels.extend(chunk_result)
                elif chunk_result is not None:
                    labels.append(chunk_result)
        elif all_results is not None:
            labels = all_results if isinstance(all_results, list) else [all_results]

    success_num = sum(labels) if labels else 0
    total = len(task_dirs)
    accuracy = (success_num / total) * 100 if total > 0 else 0.0

    print("\n" + "=" * 60)
    print(f"  EVALUATION COMPLETE")
    print(f"  FINAL ACCURACY: {accuracy:.2f}%")
    print(f"  Successes: {success_num} / {total}")
    print("=" * 60 + "\n")
