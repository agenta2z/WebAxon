"""Property-based tests for dataset download and URL normalization.

**Validates: Requirements 6.1**

Tests:
- URL normalization is idempotent (Property 2)
- Download produces load_tasks()-compatible JSONL with mocked HuggingFace (Property 1)
- Token resolution priority: param → HF_TOKEN → HUGGINGFACE_TOKEN
- FileExistsError when overwrite=False and processed file exists
"""

from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from webaxon.evaluation.datasets import (
    _normalize_start_url,
    _resolve_hf_token,
    download_dataset,
)
from webaxon.evaluation.tasks import load_tasks


# ── Mock setup for 'datasets' library ────────────────────────────────────────

def _make_mock_dataset(rows: List[Dict[str, Any]]) -> MagicMock:
    """Create a mock HuggingFace Dataset object from a list of row dicts."""
    mock_ds = MagicMock()
    mock_ds.__iter__ = lambda self: iter(rows)
    mock_ds._fingerprint = "test_fingerprint"
    mock_ds.features = {
        "task_id": "Value(dtype='string')",
        "website": "Value(dtype='string')",
        "confirmed_task": "Value(dtype='string')",
        "reference_length": "Value(dtype='int64')",
        "level": "Value(dtype='string')",
    }
    return mock_ds


def _install_datasets_mock(rows: List[Dict[str, Any]]):
    """Install a fake 'datasets' module in sys.modules that returns the given rows.

    Returns the mock module so callers can inspect it.
    The local import inside download_dataset() will pick up this fake module.
    """
    mock_ds = _make_mock_dataset(rows)
    fake_mod = types.ModuleType("datasets")
    fake_mod.load_dataset = MagicMock(return_value=mock_ds)  # type: ignore[attr-defined]
    fake_mod.__version__ = "2.0.0"  # type: ignore[attr-defined]
    return fake_mod


# ── Strategies ────────────────────────────────────────────────────────────────

# URLs with explicit scheme
_scheme_url = st.from_regex(r"https?://[a-z]{1,10}\.[a-z]{2,4}(/[a-z0-9]*)?", fullmatch=True)

# URLs without scheme (bare domains)
_bare_url = st.from_regex(r"[a-z]{1,10}\.[a-z]{2,4}(/[a-z0-9]*)?", fullmatch=True)

# Any URL-like string (with or without scheme)
_any_url = st.one_of(_scheme_url, _bare_url)

# Non-empty printable text for task fields
_task_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"), blacklist_characters="\x00"),
    min_size=1,
    max_size=60,
).filter(lambda s: s.strip())

# Strategy for a single HuggingFace dataset row
@st.composite
def hf_row_strategy(draw):
    """Generate a synthetic HuggingFace dataset row."""
    task_id = draw(st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=1,
        max_size=20,
    ))
    website = draw(_any_url)
    confirmed_task = draw(_task_text)
    reference_length = draw(st.integers(min_value=0, max_value=100))
    level = draw(st.sampled_from(["easy", "medium", "hard"]))
    return {
        "task_id": task_id,
        "website": website,
        "confirmed_task": confirmed_task,
        "reference_length": reference_length,
        "level": level,
    }


# ── Property: URL normalization is idempotent ─────────────────────────────────


class TestUrlNormalizationIdempotent:
    """Property 2: _normalize_start_url applied twice equals applied once."""

    @given(url=_any_url)
    @settings(max_examples=100)
    def test_idempotent_any_url(self, url: str):
        once = _normalize_start_url(url)
        twice = _normalize_start_url(once)
        assert twice == once, f"Not idempotent: '{url}' → '{once}' → '{twice}'"

    @given(url=_scheme_url)
    @settings(max_examples=100)
    def test_idempotent_scheme_url(self, url: str):
        once = _normalize_start_url(url)
        twice = _normalize_start_url(once)
        assert twice == once

    @given(url=_bare_url)
    @settings(max_examples=100)
    def test_bare_url_gets_https_prefix(self, url: str):
        result = _normalize_start_url(url)
        assert result.startswith("https://")

    def test_empty_string_returns_empty(self):
        assert _normalize_start_url("") == ""

    def test_whitespace_only_returns_empty(self):
        assert _normalize_start_url("   ") == ""

    def test_http_preserved(self):
        assert _normalize_start_url("http://example.com") == "http://example.com"

    def test_https_preserved(self):
        assert _normalize_start_url("https://example.com") == "https://example.com"


# ── Property: Download produces load_tasks()-compatible JSONL ─────────────────


class TestDownloadProducesCompatibleJsonl:
    """Property 1: download_dataset() output parses via load_tasks()."""

    @given(rows=st.lists(hf_row_strategy(), min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_download_output_parseable_by_load_tasks(self, rows, tmp_path_factory):
        tmp_path = tmp_path_factory.mktemp("ds")
        fake_mod = _install_datasets_mock(rows)
        saved = sys.modules.get("datasets")
        sys.modules["datasets"] = fake_mod
        try:
            result = download_dataset(tmp_path, hf_token="fake_token", overwrite=True)
        finally:
            if saved is None:
                sys.modules.pop("datasets", None)
            else:
                sys.modules["datasets"] = saved

        processed_path = tmp_path / "processed" / "tasks.jsonl"
        assert processed_path.exists()

        # load_tasks must parse the output without error
        tasks = load_tasks(processed_path)

        # Every loaded task must have required fields
        for t in tasks:
            assert t.task_id
            assert t.task
            assert t.start_url
            assert isinstance(t.reference_length, int)
            assert t.reference_length >= 0

        # Processed count matches loaded tasks
        assert result["processed"] == len(tasks)
        assert result["raw"] == len(rows)
        assert result["processed"] + result["skipped"] == result["raw"]

    @given(rows=st.lists(hf_row_strategy(), min_size=1, max_size=5))
    @settings(max_examples=100)
    def test_download_writes_metadata(self, rows, tmp_path_factory):
        tmp_path = tmp_path_factory.mktemp("ds")
        fake_mod = _install_datasets_mock(rows)
        saved = sys.modules.get("datasets")
        sys.modules["datasets"] = fake_mod
        try:
            download_dataset(tmp_path, hf_token="fake_token", overwrite=True)
        finally:
            if saved is None:
                sys.modules.pop("datasets", None)
            else:
                sys.modules["datasets"] = saved

        metadata_path = tmp_path / "metadata" / "source.json"
        assert metadata_path.exists()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert metadata["dataset"] == "osunlp/Online-Mind2Web"
        assert "downloaded_at" in metadata
        assert "num_rows_raw" in metadata

    @given(rows=st.lists(hf_row_strategy(), min_size=1, max_size=5))
    @settings(max_examples=100)
    def test_download_urls_are_normalized_in_jsonl(self, rows, tmp_path_factory):
        """The start_url field in the JSONL output is always normalized (has scheme).

        Note: load_tasks() prefers the 'website' field over 'start_url',
        so we check the raw JSONL to verify normalization.
        """
        tmp_path = tmp_path_factory.mktemp("ds")
        fake_mod = _install_datasets_mock(rows)
        saved = sys.modules.get("datasets")
        sys.modules["datasets"] = fake_mod
        try:
            download_dataset(tmp_path, hf_token="fake_token", overwrite=True)
        finally:
            if saved is None:
                sys.modules.pop("datasets", None)
            else:
                sys.modules["datasets"] = saved

        processed_path = tmp_path / "processed" / "tasks.jsonl"
        with open(processed_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                start_url = obj["start_url"]
                assert start_url.startswith("http://") or start_url.startswith("https://")


# ── Token resolution ──────────────────────────────────────────────────────────


class TestTokenResolution:
    """Token resolution: param → HF_TOKEN → HUGGINGFACE_TOKEN."""

    def test_explicit_token_takes_priority(self):
        with patch.dict(os.environ, {"HF_TOKEN": "env_token", "HUGGINGFACE_TOKEN": "hf_token"}):
            assert _resolve_hf_token("explicit") == "explicit"

    def test_hf_token_env_fallback(self):
        with patch.dict(os.environ, {"HF_TOKEN": "env_token"}, clear=False):
            # Remove HUGGINGFACE_TOKEN if present
            env = os.environ.copy()
            env.pop("HUGGINGFACE_TOKEN", None)
            with patch.dict(os.environ, env, clear=True):
                with patch.dict(os.environ, {"HF_TOKEN": "env_token"}):
                    assert _resolve_hf_token(None) == "env_token"

    def test_huggingface_token_env_fallback(self):
        env_clean = {k: v for k, v in os.environ.items() if k != "HF_TOKEN"}
        with patch.dict(os.environ, {**env_clean, "HUGGINGFACE_TOKEN": "hf2"}, clear=True):
            assert _resolve_hf_token(None) == "hf2"

    def test_no_token_returns_none(self):
        env_clean = {k: v for k, v in os.environ.items()
                     if k not in ("HF_TOKEN", "HUGGINGFACE_TOKEN")}
        with patch.dict(os.environ, env_clean, clear=True):
            assert _resolve_hf_token(None) is None

    @given(token=st.text(min_size=1).filter(lambda s: s.strip()))
    @settings(max_examples=100)
    def test_explicit_token_always_returned(self, token: str):
        result = _resolve_hf_token(token)
        assert result == token


# ── FileExistsError when overwrite=False ──────────────────────────────────────


class TestFileExistsError:
    """FileExistsError raised when overwrite=False and processed file exists."""

    def test_raises_when_file_exists_no_overwrite(self, tmp_path: Path):
        processed_dir = tmp_path / "processed"
        processed_dir.mkdir(parents=True)
        (processed_dir / "tasks.jsonl").write_text("{}", encoding="utf-8")

        fake_mod = _install_datasets_mock([])
        saved = sys.modules.get("datasets")
        sys.modules["datasets"] = fake_mod
        try:
            with pytest.raises(FileExistsError):
                download_dataset(tmp_path, hf_token="fake", overwrite=False)
        finally:
            if saved is None:
                sys.modules.pop("datasets", None)
            else:
                sys.modules["datasets"] = saved

    @given(rows=st.lists(hf_row_strategy(), min_size=1, max_size=3))
    @settings(max_examples=100)
    def test_overwrite_true_succeeds_when_file_exists(self, rows, tmp_path_factory):
        tmp_path = tmp_path_factory.mktemp("ds")
        processed_dir = tmp_path / "processed"
        processed_dir.mkdir(parents=True)
        (processed_dir / "tasks.jsonl").write_text("{}", encoding="utf-8")

        fake_mod = _install_datasets_mock(rows)
        saved = sys.modules.get("datasets")
        sys.modules["datasets"] = fake_mod
        try:
            result = download_dataset(tmp_path, hf_token="fake", overwrite=True)
        finally:
            if saved is None:
                sys.modules.pop("datasets", None)
            else:
                sys.modules["datasets"] = saved

        assert result["raw"] == len(rows)

    def test_no_token_raises_runtime_error(self, tmp_path: Path):
        env_clean = {k: v for k, v in os.environ.items()
                     if k not in ("HF_TOKEN", "HUGGINGFACE_TOKEN")}
        fake_mod = _install_datasets_mock([])
        saved = sys.modules.get("datasets")
        sys.modules["datasets"] = fake_mod
        try:
            with patch.dict(os.environ, env_clean, clear=True):
                with pytest.raises(RuntimeError, match="token required"):
                    download_dataset(tmp_path, hf_token=None, overwrite=True)
        finally:
            if saved is None:
                sys.modules.pop("datasets", None)
            else:
                sys.modules["datasets"] = saved
