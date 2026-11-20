from packages.core.engine_router import EngineRouter


class TestAdvancedEngineRouter:
    def test_handwriting_prefers_qwen(self):
        router = EngineRouter(profile="high", max_engines=2, available_ram_gb=16.0)
        engines, reasons = router.select(block_type="handwriting", language="ar")
        assert engines[0] == "Arabic-handwritten-OCR (Qwen)"
        assert any("handwriting" in reason for reason in reasons)

    def test_diacritics_prefers_qari(self):
        router = EngineRouter(profile="high", max_engines=2, available_ram_gb=16.0)
        engines, _ = router.select(language="ar", has_diacritics=True)
        assert "QARI" in engines

    def test_structured_output_can_route_to_nougat(self):
        router = EngineRouter(profile="high", max_engines=3, available_ram_gb=16.0)
        engines, _ = router.select(language="ar", block_type="form", prefer_structured_output=True)
        assert "Nougat" in engines
