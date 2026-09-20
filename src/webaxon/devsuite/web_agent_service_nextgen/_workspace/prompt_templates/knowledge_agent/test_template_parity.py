"""Parity test: verify .hbs templates produce identical output to Python prompt constants.

Usage:
    python test_template_parity.py

This script renders each .hbs template with sample feed variables using
handlebars format_template(), then renders the corresponding Python prompt
constant with .format() using the same variables, and asserts they match.

For structuring/classification templates, domain_taxonomy is dynamically
generated via format_taxonomy_for_prompt() and injected as a feed variable
to both renderers. Truncation (1000/500/300 chars) is a consumer concern
and is NOT tested here — full sample content is passed.

Format spec handling: Python templates use :.3f for some float variables
(similarity, avg_similarity). Handlebars has no format specs, so the .hbs
templates receive pre-formatted strings. The parity test passes floats to
Python .format() and pre-formatted strings to Handlebars, then compares.
"""

import sys
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

# Adjust paths so we can import from both projects
SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR

# Attempt imports; provide clear error messages if missing
try:
    from rich_python_utils.string_utils.formatting.handlebars_format import (
        format_template as handlebars_format,
    )
except ImportError:
    print("ERROR: Cannot import handlebars_format from rich_python_utils.")
    print("Ensure rich_python_utils is installed or on PYTHONPATH.")
    sys.exit(1)

try:
    from agent_foundation.knowledge.ingestion.prompts.structuring_prompt import (
        STRUCTURING_PROMPT_TEMPLATE,
        PIECES_ONLY_PROMPT_TEMPLATE,
        CLASSIFICATION_PROMPT_TEMPLATE,
    )
    from agent_foundation.knowledge.ingestion.prompts.dedup_llm_judge import (
        DEDUP_LLM_JUDGE_PROMPT,
    )
    from agent_foundation.knowledge.ingestion.prompts.merge_execution import (
        MERGE_EXECUTION_PROMPT,
    )
    from agent_foundation.knowledge.ingestion.prompts.update_prompt import (
        UPDATE_INTENT_PROMPT,
    )
    from agent_foundation.knowledge.ingestion.prompts.validation import (
        VALIDATION_PROMPT,
    )
    from agent_foundation.knowledge.ingestion.prompts.skill_synthesis import (
        SKILL_SYNTHESIS_PROMPT,
    )
    from agent_foundation.knowledge.ingestion.taxonomy import (
        format_taxonomy_for_prompt,
    )
except ImportError:
    print("ERROR: Cannot import from agent_foundation.")
    print("Ensure AgentFoundation is installed or on PYTHONPATH.")
    sys.exit(1)


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace for comparison: strip trailing whitespace per line, normalize line endings."""
    lines = text.strip().splitlines()
    return "\n".join(line.rstrip() for line in lines)


def read_hbs(relative_path: str) -> str:
    """Read a .hbs template file."""
    path = TEMPLATE_DIR / relative_path
    return path.read_text(encoding="utf-8")


def strip_hbs_comment(template: str) -> str:
    """Strip the leading {{!-- ... --}} comment block from an .hbs template."""
    return re.sub(r"^\s*\{\{!--.*?--\}\}\s*", "", template, count=1, flags=re.DOTALL)


# ---------------------------------------------------------------------------
# Sample feed variables for each template
# ---------------------------------------------------------------------------

# Dynamic taxonomy — generated at runtime, same for both renderers
DOMAIN_TAXONOMY = format_taxonomy_for_prompt()

# For the inline prompt in agentic_retriever.py, we need the raw template
# (it's a local variable, not a module-level constant)
QUERY_DECOMPOSITION_PYTHON_TEMPLATE = """You are a query decomposition assistant.

Given a user query, decompose it into 1-3 sub-queries that together cover
the full information need. Each sub-query should target a specific aspect.

{domains_section}
User query: {query}

Return a JSON array of objects with keys:
- "query": the sub-query string
- "domain": the target domain (or null for general)
- "weight": importance weight (0.5-1.5)

Example:
[
  {{"query": "flash attention memory optimization", "domain": "model_optimization", "weight": 1.0}},
  {{"query": "flash attention H100 performance", "domain": "training_efficiency", "weight": 0.8}}
]

Return only the JSON array, no explanation.
"""


# Each entry: (name, hbs_path, python_template, feed_dict, py_feed_override)
# py_feed_override: optional dict of overrides for the Python .format() call.
# Used when Python templates have format specs (e.g., :.3f) that need native
# types (float) while Handlebars receives pre-formatted strings.
TEST_CASES: list[Tuple[str, str, str, Dict, Optional[Dict]]] = [
    (
        "Structuring",
        "main/Structuring.hbs",
        STRUCTURING_PROMPT_TEMPLATE,
        {
            "domain_taxonomy": DOMAIN_TAXONOMY,
            "context": "Header: Machine Learning > Optimization",
            "user_input": "Flash attention reduces memory from O(n^2) to O(n) by tiling.",
        },
        None,
    ),
    (
        "Structuring.PiecesOnly",
        "main/Structuring.PiecesOnly.hbs",
        PIECES_ONLY_PROMPT_TEMPLATE,
        {
            "domain_taxonomy": DOMAIN_TAXONOMY,
            "user_input": "LoRA fine-tuning enables efficient adaptation of large models.",
        },
        None,
    ),
    (
        "Classification",
        "main/Classification.hbs",
        CLASSIFICATION_PROMPT_TEMPLATE,
        {
            "domain_taxonomy": DOMAIN_TAXONOMY,
            "content": "Use gradient checkpointing to reduce peak memory usage during training.",
            "tags": "gradient_checkpointing, memory",
            "info_type": "instructions",
            "knowledge_type": "instruction",
        },
        None,
    ),
    (
        # WARNING: This test uses a hardcoded copy of the inline template from
        # agentic_retriever.py:create_llm_decomposer(). If the original is edited,
        # this copy will become stale and the test will give false confidence.
        # The skip_sync=True in sync_templates.py reflects this is manual-only.
        "QueryDecomposition",
        "main/QueryDecomposition.hbs",
        QUERY_DECOMPOSITION_PYTHON_TEMPLATE,
        {
            "domains_section": "Available domains: model_optimization, training_efficiency\n\n",
            "query": "How does flash attention improve H100 performance?",
        },
        None,
    ),
    (
        # Python uses {similarity:.3f} — pass float to Python, pre-formatted string to HBS
        "DedupJudge",
        "judgment/DedupJudge.hbs",
        DEDUP_LLM_JUDGE_PROMPT,
        {
            "similarity": f"{0.912:.3f}",  # Pre-formatted for Handlebars
            "existing_content": "Flash attention uses tiling to reduce memory from quadratic to linear.",
            "existing_domain": "model_optimization",
            "existing_tags": "flash_attention, memory",
            "existing_created_at": "2024-01-15T10:00:00",
            "new_content": "FlashAttention tiles Q, K, V matrices to achieve O(n) memory complexity.",
            "new_domain": "model_optimization",
            "new_tags": "flash_attention, tiling",
        },
        {"similarity": 0.912},  # Float for Python's :.3f
    ),
    (
        "MergeExecution",
        "judgment/MergeExecution.hbs",
        MERGE_EXECUTION_PROMPT,
        {
            "piece_a_content": "Use gradient accumulation to simulate larger batch sizes on limited GPU memory.",
            "piece_a_domain": "training_efficiency",
            "piece_a_tags": "gradient_accumulation, batch_size",
            "piece_b_content": "Gradient accumulation steps of 4-8 work well for most transformer training.",
            "piece_b_domain": "training_efficiency",
            "piece_b_tags": "gradient_accumulation, transformers",
        },
        None,
    ),
    (
        "UpdateIntent",
        "judgment/UpdateIntent.hbs",
        UPDATE_INTENT_PROMPT,
        {
            "existing_id": "flash-attn-memory-optimization",
            "existing_content": "Flash Attention v1 uses tiling for O(n) memory.",
            "existing_length": "52",
            "existing_domain": "model_optimization",
            "existing_tags": "flash_attention, memory",
            "existing_updated_at": "2024-01-15T10:00:00",
            "new_content": "Flash Attention v2 adds backward pass optimization and multi-query support.",
            "new_length": "73",
            "update_instruction": "User says: Update with Flash Attention v2 improvements.",
        },
        None,
    ),
    (
        "Validation",
        "judgment/Validation.hbs",
        VALIDATION_PROMPT,
        {
            "content": "LoRA reduces trainable parameters by 10000x while maintaining 95% of full fine-tuning performance.",
            "domain": "model_optimization",
            "source": "arxiv:2106.09685",
            "created_at": "2024-03-01T12:00:00",
            "checks_to_perform": "correctness, authenticity, consistency",
        },
        None,
    ),
    (
        # Python uses {avg_similarity:.3f} — pass float to Python, pre-formatted string to HBS
        "SkillSynthesis",
        "judgment/SkillSynthesis.hbs",
        SKILL_SYNTHESIS_PROMPT,
        {
            "pieces_formatted": (
                "Piece 1 (procedure):\nStep 1: Choose rank r=4-16 for LoRA adapters\n\n"
                "Piece 2 (procedure):\nStep 2: Initialize A with random Gaussian, B with zeros\n\n"
                "Piece 3 (procedure):\nStep 3: Train only LoRA parameters while freezing base model"
            ),
            "num_pieces": "3",
            "avg_similarity": f"{0.890:.3f}",  # Pre-formatted for Handlebars
            "common_tags": "lora, fine_tuning, parameter_efficient",
            "domains": "model_optimization",
        },
        {"avg_similarity": 0.890},  # Float for Python's :.3f
    ),
]


def run_parity_tests() -> bool:
    """Run all parity tests. Returns True if all pass."""
    passed = 0
    failed = 0

    for name, hbs_path, python_template, feed, py_feed_override in TEST_CASES:
        print(f"Testing {name}...", end=" ")

        # 1. Render .hbs template (uses feed as-is — pre-formatted strings)
        hbs_raw = read_hbs(hbs_path)
        hbs_content = strip_hbs_comment(hbs_raw)
        try:
            hbs_rendered = handlebars_format(hbs_content, feed=feed)
        except Exception as e:
            print(f"FAIL (hbs render error: {e})")
            failed += 1
            continue

        # 2. Render Python .format() template
        # Apply py_feed_override for variables with format specs (e.g., :.3f needs float)
        py_feed = {**feed, **(py_feed_override or {})}
        try:
            py_rendered = python_template.format(**py_feed)
        except Exception as e:
            print(f"FAIL (python format error: {e})")
            failed += 1
            continue

        # 3. Compare (normalize whitespace)
        hbs_norm = normalize_whitespace(hbs_rendered)
        py_norm = normalize_whitespace(py_rendered)

        if hbs_norm == py_norm:
            print("PASS")
            passed += 1
        else:
            print("FAIL (output mismatch)")
            failed += 1
            # Show first difference for debugging
            hbs_lines = hbs_norm.splitlines()
            py_lines = py_norm.splitlines()
            for i, (h, p) in enumerate(zip(hbs_lines, py_lines)):
                if h != p:
                    print(f"  First diff at line {i + 1}:")
                    print(f"    HBS: {h[:120]!r}")
                    print(f"     PY: {p[:120]!r}")
                    break
            else:
                if len(hbs_lines) != len(py_lines):
                    print(f"  Line count differs: hbs={len(hbs_lines)}, py={len(py_lines)}")

    print(f"\nResults: {passed} passed, {failed} failed, {passed + failed} total")
    return failed == 0


if __name__ == "__main__":
    success = run_parity_tests()
    sys.exit(0 if success else 1)
