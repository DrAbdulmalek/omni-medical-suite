"""اختبارات StirlingPDFClient — وحدة (mock) + حي (يُتخطى بلا خادم)."""
import pytest


# ----------------------------------------------------------------- وحدة ----
def test_config_defaults():
    from omni_preprocess.config.stirling_config import StirlingConfig
    cfg = StirlingConfig()
    assert cfg.enabled is False          # معطّل افتراضيًا — لا مفاجآت
    assert cfg.default_languages == ["ara", "eng"]
    assert cfg.base_url.endswith("8080")


def test_config_from_env(monkeypatch):
    from omni_preprocess.config.stirling_config import StirlingConfig
    monkeypatch.setenv("OMNI_STIRLING_ENABLED", "true")
    monkeypatch.setenv("OMNI_STIRLING_URL", "http://stirling:9999")
    monkeypatch.setenv("OMNI_STIRLING_LANGS", "ara,eng,fra")
    cfg = StirlingConfig.from_env()
    assert cfg.enabled is True
    assert cfg.base_url == "http://stirling:9999"
    assert cfg.default_languages == ["ara", "eng", "fra"]


def test_contract_shape():
    from omni_preprocess.contract.preprocessing_result import (
        PreprocessingResult, PreprocessOperation,
    )
    r = PreprocessingResult(output_path="/tmp/o.pdf",
                            operation=PreprocessOperation.DESKEW,
                            success=True, processing_time_ms=12.5)
    assert r.errors == [] and r.warnings == []


def test_is_available_false_when_no_server():
    """بلا خادم → False (لا استثناء) — أساس التخطي الآمن."""
    from omni_preprocess.backends.stirling_client import StirlingPDFClient
    c = StirlingPDFClient(base_url="http://127.0.0.1:1")  # منفذ ميت
    assert c.is_available() is False


def test_ocr_preprocess_payload_shape(monkeypatch):
    """يتحقق من شكل الطلب دون خادم (mock على مستوى httpx)."""
    from omni_preprocess.backends import stirling_client as sc

    captured = {}

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "application/pdf"}
        content = b"%PDF-1.4 fake"

        def raise_for_status(self):
            pass

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["data"] = kwargs.get("data")
        return FakeResponse()

    client = sc.StirlingPDFClient(base_url="http://localhost:8080")
    monkeypatch.setattr(client.client, "post", fake_post)

    import tempfile, os
    fd, tmp_in = tempfile.mkstemp(suffix=".pdf"); os.close(fd)
    fd, tmp_out = tempfile.mkstemp(suffix=".pdf"); os.close(fd)
    try:
        result = client.ocr_preprocess(tmp_in, tmp_out, languages=["ara", "eng"])
        assert result.success is True
        assert captured["url"].endswith("/api/v1/misc/ocr-pdf")
        assert captured["data"]["ocrType"] == "skip-text"
        assert captured["data"]["deskew"] == "true"
    finally:
        os.unlink(tmp_in); os.unlink(tmp_out)


# ------------------------------------------------------------------ حي ----
def test_live_availability_and_ocr(live_client, tmp_path):
    """يتطلب خادم Stirling حي + fixture — وإلا يُتخطى."""
    if live_client is None:
        pytest.skip("Stirling PDF server not running")
    from .conftest import FIXTURE
    if not FIXTURE.exists():
        pytest.skip(f"fixture missing: {FIXTURE}")
    out = tmp_path / "output.pdf"
    result = live_client.ocr_preprocess(str(FIXTURE), str(out),
                                        languages=["ara", "eng"])
    assert result.success
    assert result.processing_time_ms > 0
