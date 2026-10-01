"""Tests for the arabic_rtl canonicalization (branch ``gs/t3-canonical-arabic-rtl``).

Contract under test
-------------------
1. ``packages/omnifile/modules/nlp/arabic_rtl.py`` is the single canonical
   implementation (the five former byte-identical copies were consolidated).
2. Root-context code imports it warning-free via
   ``packages.arabic_rtl_canonical`` (must survive CI's ``-W error`` gate).
3. The three deprecated shims re-export the canonical objects, emit exactly
   one ``DeprecationWarning`` per import, and share the SAME module instance.
4. The ``hf-space`` deployment copy stays byte-identical to the canonical
   module (sync guard for the standalone deployment artifact, intentionally
   excluded from the shim conversion).
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # allow running from any working directory
    sys.path.insert(0, str(REPO_ROOT))

CANONICAL_FILE = REPO_ROOT / "packages" / "omnifile" / "modules" / "nlp" / "arabic_rtl.py"
CANONICAL_SYSMODULE_NAME = "packages.omnifile.modules.nlp.arabic_rtl"

SHIM_FILES = [
    REPO_ROOT / "packages" / "nlp" / "arabic_rtl.py",
    REPO_ROOT / "packages" / "file_processor" / "modules" / "nlp" / "arabic_rtl.py",
    REPO_ROOT / "packages" / "handwriting" / "modules" / "nlp" / "arabic_rtl.py",
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


@pytest.fixture()
def canonical_module():
    from packages.arabic_rtl_canonical import load_canonical_arabic_rtl

    return load_canonical_arabic_rtl()


class TestCanonicalModule:
    def test_canonical_file_exists(self):
        assert CANONICAL_FILE.is_file(), f"canonical module missing: {CANONICAL_FILE}"

    def test_accessor_loads_canonical(self, canonical_module):
        assert canonical_module.__name__ == CANONICAL_SYSMODULE_NAME
        for attr in (
            "RTLFixer",
            "is_rtl_text",
            "get_text_direction",
            "ARABIC_NORMALIZATION_MAP",
        ):
            assert hasattr(canonical_module, attr), f"canonical missing {attr}"

    def test_single_module_instance_cached(self, canonical_module):
        assert sys.modules[CANONICAL_SYSMODULE_NAME] is canonical_module

    def test_canonical_semantics_smoke(self, canonical_module):
        assert canonical_module.is_rtl_text("مرحبا بالعالم") is True
        assert canonical_module.get_text_direction("مرحبا") == "rtl"
        assert canonical_module.get_text_direction("hello world") == "ltr"


class TestRootImportsStayWarningFree:
    def test_root_imports_survive_werror(self):
        """The -W error CI gate (ocr-core-gate.yml) must keep passing."""
        code = (
            "import packages.arabic_rtl_canonical as c; "
            "import packages.vision.text_reconstructor as tr; "
            "assert tr.ARABIC_NORMALIZATION_MAP is c.ARABIC_NORMALIZATION_MAP; "
            "print('OK')"
        )
        proc = subprocess.run(
            [sys.executable, "-W", "error", "-c", code],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert proc.returncode == 0, f"stderr:\n{proc.stderr}"
        assert "OK" in proc.stdout


class TestDeprecatedShims:
    def test_all_shims_warn_once_and_share_canonical_identity(self, canonical_module):
        for index, shim_path in enumerate(SHIM_FILES):
            name = f"_arabic_rtl_shim_under_test_{index}"
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                module = _load_file_as_module(shim_path, name)
            sys.modules.pop(name, None)
            deprecations = [
                w for w in caught if issubclass(w.category, DeprecationWarning)
            ]
            assert len(deprecations) == 1, (
                f"{shim_path}: expected exactly one DeprecationWarning, "
                f"got {len(deprecations)}"
            )
            assert "canonical" in str(deprecations[0].message).lower()
            assert module.RTLFixer is canonical_module.RTLFixer, (
                f"{shim_path}: RTLFixer identity mismatch — shim must re-export "
                "the canonical object, not a copy"
            )
            assert module.is_rtl_text is canonical_module.is_rtl_text
            assert module.ARABIC_NORMALIZATION_MAP is (
                canonical_module.ARABIC_NORMALIZATION_MAP
            )

    def test_shim_functions_are_functional(self, canonical_module):
        module = _load_file_as_module(SHIM_FILES[0], "_arabic_rtl_shim_smoke")
        sys.modules.pop("_arabic_rtl_shim_smoke", None)
        assert module.get_text_direction("مرحبا") == "rtl"
        assert module.is_rtl_text("hello") is False

    @pytest.mark.parametrize("bundle", ["file_processor", "handwriting"])
    def test_bundle_namespace_shim(self, bundle, canonical_module):
        """``modules.nlp.arabic_rtl`` keeps working with a bundle on sys.path."""
        bundle_root = REPO_ROOT / "packages" / bundle
        path_added = str(bundle_root) not in sys.path
        if path_added:
            sys.path.insert(0, str(bundle_root))
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try:
                    module = importlib.import_module("modules.nlp.arabic_rtl")
                except ImportError:
                    pytest.skip(
                        f"{bundle}: nlp package dependencies unavailable "
                        "in this environment"
                    )
            assert any(
                issubclass(w.category, DeprecationWarning) for w in caught
            ), f"{bundle}: namespace import should carry the deprecation warning"
            assert module.RTLFixer is canonical_module.RTLFixer
        finally:
            if path_added and str(bundle_root) in sys.path:
                sys.path.remove(str(bundle_root))
            stale = [k for k in sys.modules if k == "modules" or k.startswith("modules.")]
            for key in stale:
                sys.modules.pop(key, None)

    def test_root_namespace_shim_via_packages_nlp(self, canonical_module):
        """Real import path ``packages.nlp.arabic_rtl`` warns and re-exports."""
        try:
            import packages.nlp  # noqa: F401 - verify the package imports
        except ImportError:
            pytest.skip("packages.nlp dependencies unavailable in this environment")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            module = importlib.import_module("packages.nlp.arabic_rtl")
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)
        assert module.RTLFixer is canonical_module.RTLFixer


class TestHFSpaceSyncGuard:
    def test_hf_space_deployment_copy_in_sync(self):
        """hf-space is a standalone deployment artifact — kept as a full copy.

        This guard fails when the canonical module changes without syncing
        ``hf-space/``, which is the only accepted way to change that copy.
        """
        hf_copy = REPO_ROOT / "hf-space" / "packages" / "nlp" / "arabic_rtl.py"
        assert hf_copy.is_file(), "hf-space deployment copy missing — update guard"
        assert hf_copy.read_bytes() == CANONICAL_FILE.read_bytes(), (
            "hf-space arabic_rtl.py drifted from the canonical module — "
            "sync the deployment copy or update this guard consciously"
        )
