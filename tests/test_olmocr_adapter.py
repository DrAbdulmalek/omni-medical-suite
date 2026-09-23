"""Contract tests for the OLMoCR engine adapter (isolated-env contract).

These tests run in the MAIN runtime where ``olmocr`` is deliberately NOT
installed.  They prove the fail-closed registry contract: OLMoCR is
advertised, probeable, and NEVER available outside its isolated env
(R19: benchmark-first, isolated env, GPU >= 12GB).
"""

import pytest


class TestOLMoCRAdapterContract:
    """Adapter class-level contract (pins, metadata, fail-closed)."""

    def _adapter(self):
        from packages.core.engine_registry import _OLMoCRAdapter

        return _OLMoCRAdapter()

    def test_adapter_metadata(self):
        adapter = self._adapter()
        assert adapter.name == "OLMoCR"
        assert adapter.estimated_ram_gb >= 12.0
        assert "printed" in adapter.supported_tasks

    def test_pin_constants_match_pypi_metadata(self):
        """Pins verified against PyPI metadata on 2026-09-23."""
        adapter = self._adapter()
        assert adapter.OLMOCR_VERSION == "0.4.27"
        assert adapter.TRANSFORMERS_PIN == "4.57.3"
        assert adapter.VLLM_PIN == "0.11.2"
        assert adapter.TORCH_PIN == ">=2.7.0"
        assert adapter.MODEL_ID == "allenai/olmOCR-2-7B-1025-FP8"
        assert adapter.MIN_VRAM_GB == 12

    def test_fail_closed_without_isolated_marker(self, monkeypatch):
        monkeypatch.delenv("OMNI_OLMOCR_ISOLATED_ENV", raising=False)
        adapter = self._adapter()
        assert adapter.is_available() is False

    def test_fail_closed_marker_without_package(self, monkeypatch):
        monkeypatch.setenv("OMNI_OLMOCR_ISOLATED_ENV", "1")
        if _olmocr_really_installed():  # pragma: no cover - isolated env
            pytest.skip("olmocr importable in this env")
        adapter = self._adapter()
        assert adapter.is_available() is False

    def test_healthcheck_never_loads_weights_and_never_crashes(self, monkeypatch):
        monkeypatch.delenv("OMNI_OLMOCR_ISOLATED_ENV", raising=False)
        adapter = self._adapter()
        report = adapter.healthcheck()
        assert report["ok"] is False  # not importable in main env
        assert report["version"] is None
        assert "error" in report and report["error"]
        assert report["details"]["isolated_env"] is True

    def test_healthcheck_pin_violation_detected(self, monkeypatch):
        """Inside an isolated env with a WRONG transformers pin -> not ok."""
        monkeypatch.setenv("OMNI_OLMOCR_ISOLATED_ENV", "1")
        adapter = self._adapter()

        import sys
        import types

        if "transformers" in sys.modules:
            pytest.skip("real transformers already imported; stub N/A")

        fake_tf = types.ModuleType("transformers")
        fake_tf.__version__ = "9.9.9"  # deliberately wrong pin
        fake_olm = types.ModuleType("olmocr")
        fake_olm.__version__ = adapter.OLMOCR_VERSION
        monkeypatch.setitem(sys.modules, "transformers", fake_tf)
        monkeypatch.setitem(sys.modules, "olmocr", fake_olm)

        report = adapter.healthcheck()
        assert report["ok"] is False
        assert "pinned" in report["error"]
        assert report["details"]["transformers_pin_ok"] is False

    def test_healthcheck_ok_with_correct_pins(self, monkeypatch):
        """Isolated env + correct pins -> ok True (no weights touched)."""
        adapter = self._adapter()

        import sys
        import types

        if "transformers" in sys.modules:
            pytest.skip("real transformers already imported; stub N/A")

        fake_tf = types.ModuleType("transformers")
        fake_tf.__version__ = adapter.TRANSFORMERS_PIN
        fake_olm = types.ModuleType("olmocr")
        fake_olm.__version__ = adapter.OLMOCR_VERSION
        monkeypatch.setitem(sys.modules, "transformers", fake_tf)
        monkeypatch.setitem(sys.modules, "olmocr", fake_olm)

        report = adapter.healthcheck()
        assert report["ok"] is True
        assert report["details"]["transformers_pin_ok"] is True
        assert report["details"]["model_id"] == adapter.MODEL_ID


class TestRegistryIntegration:
    """OLMoCR must be discoverable yet never available in main env."""

    def test_registered_in_default_adapters(self):
        from packages.core.engine_registry import EngineRegistry

        names = [cls().name for cls in EngineRegistry.DEFAULT_ADAPTERS]
        assert "OLMoCR" in names
        assert len(names) == 8  # 7 pre-existing + OLMoCR (additive)

    def test_discover_reports_olmocr_unavailable_in_main_env(self, monkeypatch):
        monkeypatch.delenv("OMNI_OLMOCR_ISOLATED_ENV", raising=False)
        if _olmocr_really_installed():  # pragma: no cover - isolated env
            pytest.skip("olmocr importable in this env")
        from packages.core.engine_registry import EngineRegistry

        registry = EngineRegistry()
        registry.discover()
        report = registry.health_report()
        assert "OLMoCR" in report
        assert report["OLMoCR"]["available"] is False

    def test_available_engines_never_include_olmocr_outside_isolated_env(
        self, monkeypatch
    ):
        monkeypatch.delenv("OMNI_OLMOCR_ISOLATED_ENV", raising=False)
        if _olmocr_really_installed():  # pragma: no cover
            pytest.skip("olmocr importable in this env")
        from packages.core.engine_registry import EngineRegistry

        registry = EngineRegistry()
        registry.discover()
        assert "OLMoCR" not in registry.available_engine_names()


def _olmocr_really_installed() -> bool:
    try:
        import olmocr  # noqa: F401

        return True
    except Exception:
        return False
