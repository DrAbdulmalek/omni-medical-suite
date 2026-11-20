"""LFS: golden_set text artifacts must fail loudly as pointers, not as bad JSON.

`.gitattributes` tracks `*.jsonl` with no size threshold, so a plain clone
without `git lfs pull` yields a 129-byte pointer where `ground_truth.jsonl`
should be. Before the guard this surfaced as
`json.decoder.JSONDecodeError: Expecting value: line 1 column 1` and failed four
tests in `test_golden_harness.py` with a misleading cause.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from packages.evaluation import golden_harness as gh

_POINTER = (
    b"version https://git-lfs.github.com/spec/v1\n"
    b"oid sha256:" + b"0" * 64 + b"\nsize 9460\n"
)


def test_rejects_lfs_pointer(tmp_path: Path) -> None:
    p = tmp_path / "ground_truth.jsonl"
    p.write_bytes(_POINTER)
    with pytest.raises(RuntimeError, match=r"Git LFS pointer"):
        gh._reject_lfs_pointer(p)


def test_error_message_names_the_fix(tmp_path: Path) -> None:
    """The message must tell the operator what to run, not just that it failed."""
    p = tmp_path / "x.jsonl"
    p.write_bytes(_POINTER)
    with pytest.raises(RuntimeError) as exc:
        gh._reject_lfs_pointer(p)
    assert "git lfs pull" in str(exc.value)
    assert p.name in str(exc.value)


def test_accepts_real_content(tmp_path: Path) -> None:
    p = tmp_path / "ground_truth.jsonl"
    p.write_text('{"id": "a", "text": "نص"}\n', encoding="utf-8")
    gh._reject_lfs_pointer(p)          # must not raise


def test_missing_file_still_raises_filenotfound(tmp_path: Path) -> None:
    """The guard must not mask a genuinely absent file as an LFS problem."""
    with pytest.raises(FileNotFoundError):
        gh._reject_lfs_pointer(tmp_path / "does-not-exist.jsonl")


def test_gitattributes_exempts_golden_set_text() -> None:
    """The small text artifacts must be readable from a plain clone."""
    attrs = Path(gh.__file__).parents[2] / ".gitattributes"
    if not attrs.exists():
        pytest.skip(".gitattributes not in this checkout")
    text = attrs.read_text(encoding="utf-8")
    assert "packages/evaluation/golden_set/*.jsonl" in text, \
        "golden_set/*.jsonl still LFS-tracked — gate not reproducible from a plain clone"
