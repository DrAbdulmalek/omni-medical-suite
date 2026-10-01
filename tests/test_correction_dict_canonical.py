"""Tests for the correction_dict.json canonicalization (branch ``gs/t4-canonical-corrections``).

Contract under test
-------------------
1. ``packages/config/correction_dict.json`` is the single canonical reference
   (97 learned corrections, md5 e6eb3df8..., byte-identical to the richest
   legacy runtime copy).
2. It is a strict superset of the 52-entry seed
   (``data/correction_dict_seed.json``) with zero value conflicts.
3. ``SpellCorrector`` default resolution in all four in-repo contexts
   (root ``packages/nlp`` and the omnifile / file_processor / handwriting
   bundles) points at the canonical file and loads its full converted
   content; legacy local copies remain as fallback.
4. The excluded standalone bundles (hf-space deployment artifact, apps demo
   variant) stay byte-identical to the canonical content (sync guard).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # allow running from any working directory
    sys.path.insert(0, str(REPO_ROOT))

CANONICAL_FILE = REPO_ROOT / "packages" / "config" / "correction_dict.json"
SEED_FILE = REPO_ROOT / "data" / "correction_dict_seed.json"

# Standalone deployment bundles intentionally excluded from loader
# redirection — guarded byte-identical instead.
EXCLUDED_RUNTIME_COPIES = [
    REPO_ROOT / "hf-space" / "packages" / "nlp" / "correction_dict.json",
    REPO_ROOT
    / "apps"
    / "handwriting-demo"
    / "variants"
    / "handwriting-ocr"
    / "modules"
    / "nlp"
    / "correction_dict.json",
]

# (label, spell_corrector.py path) for the four redirected contexts.
SPELL_CORRECTOR_CONTEXTS = [
    ("root-packages-nlp", REPO_ROOT / "packages" / "nlp" / "spell_corrector.py"),
    (
        "omnifile-bundle",
        REPO_ROOT / "packages" / "omnifile" / "modules" / "nlp" / "spell_corrector.py",
    ),
    (
        "file_processor-bundle",
        REPO_ROOT
        / "packages"
        / "file_processor"
        / "modules"
        / "nlp"
        / "spell_corrector.py",
    ),
    (
        "handwriting-bundle",
        REPO_ROOT / "packages" / "handwriting" / "modules" / "nlp" / "spell_corrector.py",
    ),
]


def _load_file_as_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _convert_like_loader(raw: dict) -> dict:
    """Mirror SpellCorrector._load_corrections conversion rules."""
    converted = {}
    for wrong, correct_or_dict in raw.items():
        if isinstance(correct_or_dict, dict):
            converted[wrong] = {k: int(v) for k, v in correct_or_dict.items()}
        else:
            converted[wrong] = {str(correct_or_dict): 1}
    return converted


class TestCanonicalReference:
    def test_canonical_exists_and_shape(self):
        assert CANONICAL_FILE.is_file(), f"missing canonical file: {CANONICAL_FILE}"
        raw = _load_json(CANONICAL_FILE)
        assert len(raw) == 97, "canonical content drifted from the 97-key reference"
        for value in raw.values():
            assert isinstance(value, (str, dict)), f"unexpected value type: {value!r}"

    def test_canonical_is_strict_superset_of_seed(self):
        seed = _load_json(SEED_FILE)
        canonical = _load_json(CANONICAL_FILE)
        assert len(seed) == 52
        assert set(seed) <= set(canonical), "seed keys missing from canonical"
        conflicts = {k for k in seed if canonical.get(k) != seed[k]}
        assert not conflicts, f"value conflicts on shared keys: {sorted(conflicts)}"
        assert len(canonical) - len(seed) == 45  # 45 runtime-only learned keys


class TestLoaderResolution:
    @pytest.mark.parametrize("label,spell_path", SPELL_CORRECTOR_CONTEXTS)
    def test_default_resolution_points_at_canonical(self, label, spell_path):
        canonical_raw = _load_json(CANONICAL_FILE)
        module = _load_file_as_module(spell_path, f"_spell_under_test_{label}")
        sys.modules.pop(f"_spell_under_test_{label}", None)

        corrector = module.SpellCorrector()  # default resolution path
        assert Path(corrector._correction_file) == CANONICAL_FILE, (
            f"{label}: default resolved to {corrector._correction_file}, "
            "expected the canonical reference"
        )
        assert len(corrector._learned_corrections) == 97
        assert corrector._learned_corrections == _convert_like_loader(canonical_raw)

    def test_explicit_correction_file_still_wins(self, tmp_path):
        module = _load_file_as_module(
            SPELL_CORRECTOR_CONTEXTS[0][1], "_spell_explicit_test"
        )
        sys.modules.pop("_spell_explicit_test", None)
        custom = tmp_path / "correction_dict_explicit.json"
        custom.write_text(json.dumps({"zzz": {"yyy": 3}}), encoding="utf-8")
        corrector = module.SpellCorrector(correction_file=str(custom))
        assert corrector._correction_file == str(custom)
        assert corrector._learned_corrections == {"zzz": {"yyy": 3}}


class TestExcludedBundlesSyncGuard:
    @pytest.mark.parametrize("copy_path", EXCLUDED_RUNTIME_COPIES)
    def test_excluded_copies_stay_byte_identical(self, copy_path):
        assert copy_path.is_file(), (
            f"excluded bundle copy missing: {copy_path} — update the guard path"
        )
        assert copy_path.read_bytes() == CANONICAL_FILE.read_bytes(), (
            f"{copy_path} drifted from the canonical content — sync it or "
            "update this guard consciously"
        )
