"""Post-hoc trajectory extraction from session logs and screenshots.

Reads WebAxon session logs (JSONL + .parts/) after an agent run completes
and combines them with screenshots saved to trajectory_dir by the WebDriver
trajectory capture hooks.
"""

from __future__ import annotations

import json
import logging
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Canonical action types from AgentFoundation schema/constants.py
_ACTION_FORMAT_MAP = {
    "visit_url": lambda e: f"NAVIGATE {_get_arg(e, 'url', e.get('target', ''))}",
    "click": lambda e: f"CLICK [target={e.get('target', '?')}]",
    "input_text": lambda e: f"INPUT [target={e.get('target', '?')}]: {_get_arg(e, 'text', '')[:60]}",
    "input_and_submit": lambda e: f"INPUT_SUBMIT [target={e.get('target', '?')}]: {_get_arg(e, 'text', '')[:60]}",
    "append_text": lambda e: f"APPEND [target={e.get('target', '?')}]: {_get_arg(e, 'text', '')[:60]}",
    "scroll": lambda e: f"SCROLL {_get_arg(e, 'direction', 'down')}",
    "scroll_up_to_element": lambda e: f"SCROLL_TO [target={e.get('target', '?')}]",
    "wait": lambda _: "WAIT",
    "no_op": lambda _: "NO_OP",
    "search": lambda e: f"SEARCH {e.get('target', '')}",
}


def _get_arg(entry: Dict, key: str, default: str = "") -> str:
    """Safely extract a value from the args dict."""
    args = entry.get("args") or {}
    return str(args.get(key, default))


@dataclass(frozen=True)
class TrajectoryResult:
    """Extracted trajectory data from a completed agent run."""

    screenshots: List[Path] = field(default_factory=list)
    action_history: List[str] = field(default_factory=list)
    action_history_readable: List[str] = field(default_factory=list)
    thoughts: List[str] = field(default_factory=list)
    raw_generations: List[str] = field(default_factory=list)
    answer: str = ""
    confidence: float = 0.0


def capture(
    session_dir: str,
    trajectory_dir: Path,
) -> TrajectoryResult:
    """Read session logs + screenshots and build a TrajectoryResult.

    Parameters
    ----------
    session_dir:
        Path to the SessionLogger session directory (contains JSONL + .parts/).
        May be empty string if the run failed before creating a session.
    trajectory_dir:
        Directory where WebDriver saved per-step screenshots.
    """
    thoughts: List[str] = []
    raw_generations: List[str] = []
    action_history: List[str] = []
    action_history_readable: List[str] = []
    answer = ""

    # Parse session logs if available
    if session_dir and Path(session_dir).is_dir():
        try:
            thoughts, raw_generations, action_history, action_history_readable, answer = (
                _parse_session_logs(session_dir)
            )
        except Exception as exc:
            logger.warning("Session log parsing failed: %s", exc, exc_info=True)

    # Collect screenshots from trajectory_dir
    screenshots = _collect_screenshots(trajectory_dir)

    # Compute confidence heuristic from answer
    confidence = _compute_confidence(answer)

    return TrajectoryResult(
        screenshots=screenshots,
        action_history=action_history,
        action_history_readable=action_history_readable,
        thoughts=thoughts,
        raw_generations=raw_generations,
        answer=answer or "Task not completed — no agent response.",
        confidence=confidence,
    )


def _parse_session_logs(
    session_dir: str,
) -> tuple[List[str], List[str], List[str], List[str], str]:
    """Parse session JSONL logs into trajectory components.

    Returns (thoughts, raw_generations, action_history, action_history_readable, answer).
    """
    from rich_python_utils.service_utils.session_management.session_logger import (
        SessionLogReader,
    )

    thoughts: List[str] = []
    raw_generations: List[str] = []
    action_history: List[str] = []
    action_history_readable: List[str] = []
    answer = ""

    reader = SessionLogReader(session_dir, resolve_parts=True)

    for entry in reader:
        if not isinstance(entry, dict):
            continue

        log_type = entry.get("type", "")
        item = entry.get("item")
        if item is None:
            continue

        if log_type == "ReasonerResponse":
            # Raw LLM output
            raw_text = str(item) if not isinstance(item, str) else item
            raw_generations.append(raw_text)

        elif log_type == "AgentResponse":
            # Extract thoughts from AgentResponse
            _extract_agent_response(item, thoughts)
            # The last AgentResponse's instant_response is the answer
            instant_resp = _safe_getattr(item, "instant_response", "")
            if instant_resp:
                answer = instant_resp

        elif log_type == "AgentActionResults":
            # Extract action history from WebDriverActionResult(s)
            _extract_action_results(item, action_history, action_history_readable)

    return thoughts, raw_generations, action_history, action_history_readable, answer


def _extract_agent_response(
    item: Any,
    thoughts: List[str],
) -> None:
    """Extract reasoning/thoughts from an AgentResponse log item."""
    # AgentResponse has .next_actions: list[list[AgentAction]]
    next_actions = _safe_getattr(item, "next_actions", None)
    if next_actions:
        for action_group in next_actions:
            if not isinstance(action_group, (list, tuple)):
                continue
            for action in action_group:
                reasoning = _safe_getattr(action, "reasoning", "")
                if reasoning:
                    thoughts.append(reasoning)


def _extract_action_results(
    item: Any,
    action_history: List[str],
    action_history_readable: List[str],
) -> None:
    """Extract action history from AgentActionResults log items.

    The item is typically a list of WebDriverActionResult or similar objects,
    but it may also be a single item or a nested structure.
    """
    items = item if isinstance(item, (list, tuple)) else [item]

    for result_item in items:
        # Try to extract action type and target from the result
        # WebDriverActionResult has: source (url), action_skipped, skip_reason
        # But the ACTION details come from the preceding AgentResponse.next_actions
        # For now, capture what we can from the result
        source = _safe_getattr(result_item, "source", "")
        skipped = _safe_getattr(result_item, "action_skipped", False)

        entry = {
            "source": source,
            "action_skipped": skipped,
        }
        if skipped:
            skip_reason = _safe_getattr(result_item, "skip_reason", "")
            entry["skip_reason"] = skip_reason

        action_history.append(json.dumps(entry, ensure_ascii=False))

        if skipped:
            action_history_readable.append(f"SKIPPED: {entry.get('skip_reason', '')}")
        elif source:
            action_history_readable.append(f"ACTION on {source[:80]}")
        else:
            action_history_readable.append("ACTION")


def format_action_readable(action_entry: Dict[str, Any]) -> str:
    """Map a WebAxon canonical action type to evaluation framework format.

    Uses AgentAction fields: ``.type`` (NOT ``.action_type``), ``.target``, ``.args``.
    """
    action_type = action_entry.get("type", "unknown")
    formatter = _ACTION_FORMAT_MAP.get(action_type)
    if formatter:
        return formatter(action_entry)
    return f"{action_type.upper()} {str(action_entry)[:80]}"


def _collect_screenshots(trajectory_dir: Path) -> List[Path]:
    """Collect and sort screenshots from trajectory_dir."""
    if not trajectory_dir.is_dir():
        return []

    screenshots = sorted(
        trajectory_dir.glob("*_screenshot.png"),
        key=lambda p: _extract_step_number(p.name),
    )

    # Write placeholders for gaps if needed
    if screenshots:
        max_step = _extract_step_number(screenshots[-1].name)
        for i in range(max_step + 1):
            expected = trajectory_dir / f"{i}_screenshot.png"
            if not expected.exists():
                _write_placeholder_png(expected)
                screenshots.append(expected)
        screenshots.sort(key=lambda p: _extract_step_number(p.name))

    return screenshots


def _extract_step_number(filename: str) -> int:
    """Extract the numeric step prefix from a screenshot filename."""
    try:
        return int(filename.split("_")[0])
    except (ValueError, IndexError):
        return -1


def _compute_confidence(answer: str) -> float:
    """Heuristic confidence from answer text."""
    if not answer:
        return 0.0
    lower = answer.lower()
    if any(p in lower for p in ["task complete", "successfully", "done", "finished", "completed"]):
        return 0.8
    if any(p in lower for p in ["error", "failed", "unable", "could not"]):
        return 0.2
    return 0.5


def _write_placeholder_png(path: Path) -> None:
    """Write a minimal 1x1 white PNG file."""
    # Minimal valid PNG: 1x1 white pixel
    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw_data = zlib.compress(b"\x00\xff\xff\xff")
    idat = _chunk(b"IDAT", raw_data)
    iend = _chunk(b"IEND", b"")

    path.write_bytes(sig + ihdr + idat + iend)


def _safe_getattr(obj: Any, name: str, default: Any = None) -> Any:
    """Safely get attribute from an object (may be dict or dataclass)."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)
