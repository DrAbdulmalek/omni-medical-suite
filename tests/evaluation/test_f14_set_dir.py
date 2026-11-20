"""F-14: golden_harness must accept an alternate dataset dir.

SET_DIR was hard-coded, so measuring real channel pages required overwriting
``golden_set/`` — the synthetic set that is the CI regression gate. This adds
``set_dataset_dir()`` + ``--set-dir`` so ``golden_set_real/`` can coexist.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.evaluation import golden_harness as gh


@pytest.fixture()
def _restore_paths():
    """SET_DIR and friends are module globals — always put them back."""
    saved = (gh.SET_DIR, gh.GT_PATH, gh.MANIFEST_PATH, gh.LOCK_PATH)
    yield
    gh.SET_DIR, gh.GT_PATH, gh.MANIFEST_PATH, gh.LOCK_PATH = saved


def test_set_dataset_dir_exists():
    assert callable(getattr(gh, "set_dataset_dir", None)), "F-14: set_dataset_dir missing"


def test_set_dataset_dir_rebinds_all_paths(tmp_path: Path, _restore_paths):
    (tmp_path / "manifest.json").write_text("[]", encoding="utf-8")
    gh.set_dataset_dir(tmp_path)
    assert gh.SET_DIR == tmp_path.resolve()
    assert gh.MANIFEST_PATH == tmp_path / "manifest.json"
    assert gh.GT_PATH == tmp_path / "ground_truth.jsonl"
    assert gh.LOCK_PATH == tmp_path / "engines.lock.json"


def test_set_dataset_dir_rejects_dir_without_manifest(tmp_path: Path, _restore_paths):
    """Fail loudly — never silently measure against an empty/wrong set."""
    with pytest.raises(FileNotFoundError, match="manifest.json"):
        gh.set_dataset_dir(tmp_path)


def test_default_set_dir_unchanged(_restore_paths):
    """No --set-dir ⇒ behaviour identical to before F-14 (CI gate intact)."""
    assert gh.SET_DIR == Path(gh.__file__).parent / "golden_set"
    assert gh.MANIFEST_PATH.name == "manifest.json"


def test_cli_exposes_set_dir():
    import argparse

    ap = argparse.ArgumentParser()
    src = Path(gh.__file__).read_text(encoding="utf-8")
    assert '"--set-dir"' in src, "F-14: --set-dir not in the CLI"
    # --out must no longer bake in the old SET_DIR at parse time
    assert 'ap.add_argument("--out", default=None' in src, \
        "F-14: --out must default to None so it resolves after set_dataset_dir"


def test_real_set_does_not_clobber_ci_set(tmp_path: Path, _restore_paths):
    """The point of F-14: a real-page set must not touch golden_set/."""
    (tmp_path / "manifest.json").write_text(
        json.dumps([{"id": "x", "category": "c", "file": "x.png", "sha256": "0" * 64}]),
        encoding="utf-8")
    ci_manifest = gh.SET_DIR / "manifest.json"
    before = ci_manifest.read_bytes() if ci_manifest.exists() else None
    gh.set_dataset_dir(tmp_path)
    assert gh.MANIFEST_PATH != ci_manifest
    if before is not None:
        assert ci_manifest.read_bytes() == before, "CI golden_set was modified"
