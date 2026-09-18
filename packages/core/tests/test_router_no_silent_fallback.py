"""TASK 004 - no-silent-fallback gate for EngineRouter.select()."""
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

captured: list[dict] = []


@pytest.fixture()
def _stub_decision_log(monkeypatch):
    """Guarantee a capturable log_decision regardless of app.core contents."""
    captured.clear()
    app_mod = types.ModuleType("app")
    core_mod = types.ModuleType("app.core")
    dl_mod = types.ModuleType("app.core.decision_log")
    dl_mod.log_decision = lambda **kw: captured.append(kw)  # type: ignore[attr-defined]
    app_mod.core = core_mod
    monkeypatch.setitem(sys.modules, "app", app_mod)
    monkeypatch.setitem(sys.modules, "app.core", core_mod)
    monkeypatch.setitem(sys.modules, "app.core.decision_log", dl_mod)
    yield


@pytest.mark.usefixtures("_stub_decision_log")
class TestNoSilentFallback:
    def test_normal_path_has_no_fallback(self):
        from packages.core.engine_router import EngineRouter

        router = EngineRouter(profile="balanced", available_ram_gb=16.0)
        result = router.select_with_provenance(
            image_quality=0.9, language="ar", block_type="paragraph"
        )
        assert result["engines"], "expected at least one engine"
        assert result["fallback_status"] == "none"

    def test_default_fallback_is_explicit(self):
        from packages.core.engine_router import EngineRouter

        router = EngineRouter(profile="balanced", available_ram_gb=16.0)
        result = router.select_with_provenance(
            image_quality=0.95,
            language="fr",  # not ar/mixed/en/de -> no rule fires
            block_type="paragraph",
            document_type="generic",
        )
        assert result["fallback_status"] == "explicit"
        assert "default fallback" in result["fallback_reason"]
        assert result["engines"], "fallback must still produce engines"

    def test_fallback_recorded_in_decision_log(self):
        from packages.core.engine_router import EngineRouter

        router = EngineRouter(profile="balanced", available_ram_gb=16.0)
        router.select_with_provenance(image_quality=0.95, language="fr")
        assert captured, "decision log must be written"
        entry = captured[-1]
        assert "fallback_status" in entry["inputs"]
        assert entry["inputs"]["fallback_status"] == "explicit"

    def test_select_signature_backward_compatible(self):
        from packages.core.engine_router import EngineRouter

        router = EngineRouter(profile="balanced", available_ram_gb=16.0)
        out = router.select(image_quality=0.9, language="ar")
        assert isinstance(out, tuple) and len(out) == 2
