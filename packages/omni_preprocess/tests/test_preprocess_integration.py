"""اختبارات PreprocessRouter — منطق القرار نقّي (بلا خادم) + حي يُتخطى."""
import pytest


def test_router_rejects_unsupported_format():
    from omni_preprocess.routing.preprocess_router import PreprocessRouter
    r = PreprocessRouter()
    d = r.should_preprocess("notes.txt")
    assert d["preprocess"] is False


def test_router_accepts_scans():
    from omni_preprocess.routing.preprocess_router import PreprocessRouter
    r = PreprocessRouter()
    for p in ("scan.pdf", "page.png", "page.JPG", "page.tiff"):
        assert r.should_preprocess(p)["preprocess"] is True


def test_router_poor_quality_reason():
    from omni_preprocess.routing.preprocess_router import PreprocessRouter
    r = PreprocessRouter()
    d = r.should_preprocess("scan.pdf", quality="poor")
    assert d["preprocess"] is True
    assert "deskew" in d["operations"] and "clean" in d["operations"]


def test_live_full_pipeline(live_client, tmp_path):
    """preprocess كامل ضد خادم حي — يُتخطى تلقائيًا في CI العادي."""
    if live_client is None:
        pytest.skip("Stirling PDF server not running")
    from .conftest import FIXTURE
    if not FIXTURE.exists():
        pytest.skip(f"fixture missing: {FIXTURE}")
    from omni_preprocess.routing.preprocess_router import PreprocessRouter
    router = PreprocessRouter()
    out = tmp_path / "preprocessed.pdf"
    result = router.preprocess(input_path=str(FIXTURE), output_path=str(out))
    assert result["success"]
