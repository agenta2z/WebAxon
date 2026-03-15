"""Evaluator utilities — rewritten to use generic EvalLLMEngine protocol.

Removed: AIGatewayEngine, OpenaiEngine (vendor-specific engines).
Added: EvalLLMEngine protocol, InferencerEngine adapter.
Retained: extract_predication(), encode_image().
"""

import base64
import io
from typing import Dict, List, Protocol, runtime_checkable

from PIL import Image


@runtime_checkable
class EvalLLMEngine(Protocol):
    """Minimal protocol for LLM engines used by the evaluator.
    Any object with .generate(messages) -> List[str] works.
    This keeps the evaluator decoupled from any specific LLM SDK."""

    def generate(self, messages: List[Dict], **kwargs) -> List[str]: ...


class InferencerEngine:
    """Wraps an InferencerBase to conform to EvalLLMEngine protocol.

    Handles OpenAI-format message lists (including ``role: "system"`` and
    multimodal ``image_url`` content).  For Claude-based inferencers, system
    messages are extracted from the list and passed via the ``system`` kwarg
    (Claude's Messages API requires this).
    """

    def __init__(self, inferencer):
        self._inferencer = inferencer
        # Detect Claude-based inferencers to auto-extract system messages.
        cls_name = type(inferencer).__name__
        self._is_claude = "claude" in cls_name.lower()

    def generate(self, messages: List[Dict], **kwargs) -> List[str]:
        if self._is_claude:
            messages, kwargs = self._adapt_for_claude(messages, kwargs)
        result = self._inferencer(messages, **kwargs)
        return [result] if isinstance(result, str) else result

    @staticmethod
    def _adapt_for_claude(
        messages: List[Dict], kwargs: dict
    ) -> tuple:
        """Adapt OpenAI-format messages to Claude's Messages API format.

        Two transformations:
        1. Extract ``role: "system"`` messages into the ``system`` kwarg.
        2. Convert ``image_url`` content blocks to Claude's ``image`` format.
        """
        import re

        system_parts = []
        adapted = []
        for msg in messages:
            if msg.get("role") == "system":
                content = msg.get("content", "")
                if isinstance(content, str):
                    system_parts.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            system_parts.append(block["text"])
                        elif isinstance(block, str):
                            system_parts.append(block)
            else:
                # Convert image_url blocks in content
                content = msg.get("content")
                if isinstance(content, list):
                    new_content = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "image_url":
                            new_content.append(
                                InferencerEngine._convert_image_block(block)
                            )
                        else:
                            new_content.append(block)
                    adapted.append({**msg, "content": new_content})
                else:
                    adapted.append(msg)

        if system_parts:
            kwargs = {**kwargs, "system": "\n\n".join(system_parts)}

        return adapted, kwargs

    @staticmethod
    def _convert_image_block(block: Dict) -> Dict:
        """Convert OpenAI ``image_url`` block to Claude ``image`` block.

        OpenAI format::

            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}

        Claude format::

            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "..."}}
        """
        url = block.get("image_url", {}).get("url", "")
        # Parse data URI: data:<media_type>;base64,<data>
        match = __import__("re").match(
            r"data:(image/[^;]+);base64,(.*)", url, flags=__import__("re").DOTALL
        )
        if match:
            media_type = match.group(1)
            data = match.group(2)
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": data,
                },
            }
        # If not a data URI, return as-is (will likely fail, but let the API report it)
        return block


def encode_image(image, max_dimension=7680):
    """Encode a PIL Image to base64 JPEG string.

    Resizes if any dimension exceeds max_dimension (Claude API limit is 8000px).
    """
    # JPEG only supports RGB, L (grayscale), and CMYK.
    # Convert any incompatible mode (RGBA, LA, P, PA, etc.) to RGB.
    if image.mode not in ("RGB", "L", "CMYK"):
        image = image.convert("RGB")
    # Resize if either dimension exceeds the limit
    w, h = image.size
    if w > max_dimension or h > max_dimension:
        scale = max_dimension / max(w, h)
        image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def _extract_status_label(response):
    lower = response.lower()

    # --- Primary: explicit 'Status:' line ---
    if "status:" in lower:
        after_status = lower.split("status:")[-1]
        # The text after "Status:" should contain "success" or "failure"
        if "success" in after_status:
            return 1
        return 0

    # --- Fallback: response was truncated / missing Status line ---
    # Look for the LAST occurrence of 'success' or 'failure' in the body.
    last_success = lower.rfind("success")
    last_failure = lower.rfind("fail")  # matches 'failure', 'failed', 'fails' too
    if last_success == -1 and last_failure == -1:
        # No verdict at all — conservatively treat as failure
        print(
            f"WARNING: No 'Status:' line AND no success/failure keyword in response ({len(response)} chars)"
        )
        return 0
    if last_success > last_failure:
        print(f"WARNING: No 'Status:' line — inferred SUCCESS from response text")
        return 1
    else:
        print(f"WARNING: No 'Status:' line — inferred FAILURE from response text")
        return 0


def extract_predication(response, mode):
    if mode == "WebVoyager_eval":
        if "FAILURE" in response:
            return 0
        else:
            return 1
    elif mode in (
        "Autonomous_eval",
        "AgentTrek_eval",
        "WebJudge_Online_Mind2Web_eval",
        "WebJudge_general_eval",
    ):
        return _extract_status_label(response)
    else:
        raise ValueError(f"Unknown mode: {mode}")
