"""AHW-02F / AHW-02G — OLMoCR optional adapter tests (test-first).

OLMoCR is ABSENT from ``main`` (AHW-01 §EV-1, PROVEN).  Therefore:
    - the repository must work with olmocr NOT installed;
    - the adapter must report ``is_available() = False``;
    - the adapter must never be selected implicitly (it is not in any
      router profile);
    - success/failure paths are tested with a mocked module only —
      no model download, no network, no CI dependency.
"""

import importlib.machinery
import importlib.util
import sys

import pytest

from packages.core.engine_registry import EngineAdapter, EngineRegistry
from packages.core.router_executor import (
    EngineNotExecutableError,
    OLMoCRAdapter,
)
from packages.omni_ocr.adapter import OCRResult

OLMOCR_INSTALLED = importlib.util.find_spec("olmocr") is not None


# ---------------------------------------------------------------------------
# Optional dependency — repository works without it
# ---------------------------------------------------------------------------
class TestOptionalDependency:
    def test_adapter_modules_importable_without_olmocr(self):
        import packages.core.engine_registry  # noqa: F401
        import packages.core.router_executor  # noqa: F401
        import packages.omni_ocr.adapter  # noqa: F401

    def test_is_available_false_when_not_installed(self):
        if OLMOCR_INSTALLED:
            pytest.skip("olmocr is installed in this environment")
        assert OLMoCRAdapter().is_available() is False

    def test_adapter_is_engine_adapter(self):
        assert issubclass(OLMoCRAdapter, EngineAdapter)

    def test_olmocr_not_in_any_router_profile(self):
        """No silent integration: the router must never auto-select OLMoCR."""
        from packages.core.engine_router import PROFILE_ENGINES

        for profile, engines in PROFILE_ENGINES.items():
            assert "OLMoCR" not in engines, f"OLMoCR leaked into profile {profile}"

    def test_registry_discover_does_not_require_olmocr(self):
        """Registering the adapter into a registry instance must not import
        olmocr; DEFAULT_ADAPTERS remain untouched (no hard dependency)."""
        registry = EngineRegistry(adapters=[OLMoCRAdapter()])
        assert "OLMoCR" in registry._adapters


# ---------------------------------------------------------------------------
# Failure paths (explicit)
# ---------------------------------------------------------------------------
class TestFailurePaths:
    def test_run_without_dependency_raises_engine_not_executable(self):
        if OLMOCR_INSTALLED:
            pytest.skip("olmocr is installed in this environment")
        with pytest.raises(EngineNotExecutableError, match="olmocr"):
            OLMoCRAdapter().run("document.pdf", block_type="paragraph")

    def test_missing_entrypoint_raises_when_module_is_broken(self, monkeypatch):
        """A module without a usable entrypoint must fail explicitly."""
        import types

        fake = types.ModuleType("olmocr")  # no process_document / pipeline
        fake.__spec__ = importlib.machinery.ModuleSpec("olmocr", None)
        monkeypatch.setitem(sys.modules, "olmocr", fake)
        with pytest.raises(EngineNotExecutableError, match="entrypoint"):
            OLMoCRAdapter().run("document.pdf", block_type="paragraph")


# ---------------------------------------------------------------------------
# Mocked success / mocked failure (offline)
# ---------------------------------------------------------------------------
class TestMockedExecution:
    def _install_fake_olmocr(self, monkeypatch, *, raise_error=None, markdown="نص تجريبي"):
        import types

        fake = types.ModuleType("olmocr")

        def process_document(file_path, **kwargs):
            if raise_error is not None:
                raise raise_error
            return {"markdown": markdown, "pages": 1}

        fake.process_document = process_document
        fake.__version__ = "0.0.0-fake"
        fake.__spec__ = importlib.machinery.ModuleSpec("olmocr", None)
        monkeypatch.setitem(sys.modules, "olmocr", fake)
        return fake

    def test_mocked_success_produces_ocrresult_with_provenance(self, monkeypatch):
        self._install_fake_olmocr(monkeypatch)
        adapter = OLMoCRAdapter()
        assert adapter.is_available() is True

        result = adapter.run("document.pdf", block_type="paragraph", language="ar")

        assert isinstance(result, OCRResult)
        assert result.success
        assert result.engine == "OLMoCR"
        assert result.text == "نص تجريبي"
        assert result.provenance["engine"] == "OLMoCR"
        assert result.provenance["script_kind"] == "printed"
        assert result.provenance["upstream_status"] == "not-pinned-on-main"

    def test_mocked_failure_is_explicit(self, monkeypatch):
        self._install_fake_olmocr(monkeypatch, raise_error=ValueError("upstream boom"))
        with pytest.raises(ValueError, match="upstream boom"):
            OLMoCRAdapter().run("document.pdf", block_type="paragraph")

    def test_healthcheck_reflects_fake_module(self, monkeypatch):
        self._install_fake_olmocr(monkeypatch)
        report = OLMoCRAdapter().healthcheck()
        assert report["ok"] is True
        assert report["version"] == "0.0.0-fake"
