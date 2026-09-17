"""AHW-02C / AHW-02G — Arabic HTR adapter contract tests (test-first).

Wires the EXISTING, previously-unwired package ``packages/vision/htr``
(``ArabicHandwrittenHTR`` + ``FineTunedTrOCR``) behind the existing
``EngineAdapter`` abstraction — REUSE, no rebuild.

Critical rules encoded here:
    - ``microsoft/trocr-base-handwritten`` is a LATIN baseline:
      it must never be claimed as Arabic-handwriting proof (AHW-02C).
    - No model weights are downloaded at adapter construction time;
      model loading happens lazily inside ``run()`` only.
    - The interface accepts an explicit ``model_path`` so a true
      Arabic model can be plugged in later without code changes.
    - Unavailability is explicit (``EngineNotExecutableError``),
      never a silent fallback.
"""

import importlib.util

import pytest
from PIL import Image

from packages.core.engine_registry import EngineAdapter
from packages.core.router_executor import (
    EngineNotExecutableError,
    HandwritingHTRAdapter,
)

HAVE_TORCH_STACK = (
    importlib.util.find_spec("torch") is not None
    and importlib.util.find_spec("transformers") is not None
)

_TINY_IMAGE = Image.new("RGB", (32, 16), color=(255, 255, 255))


# ---------------------------------------------------------------------------
# Adapter contract (AHW-02C: implemented / importable / tested)
# ---------------------------------------------------------------------------
class TestAdapterContract:
    def test_is_engine_adapter(self):
        assert issubclass(HandwritingHTRAdapter, EngineAdapter)

    def test_declares_handwriting_capability_and_router_name(self):
        adapter = HandwritingHTRAdapter()
        assert adapter.name == "TrOCR"  # matches router vocabulary (Qwen→QARI→TrOCR)
        assert "handwriting" in adapter.supported_tasks
        assert adapter.estimated_ram_gb == 3.5  # mirrors registry RAM declaration

    def test_construction_downloads_nothing(self):
        """ transformers/torch are absent in this environment; if adapter
        construction tried to import them or load a model, this line would
        raise.  Construction must be dependency-free."""
        adapter = HandwritingHTRAdapter(model_path=None, device="cpu")
        assert adapter._model_path is None

    def test_availability_matches_torch_stack_only(self):
        """is_available() reflects importability of the runtime stack —
        it must NOT attempt any model download or network call."""
        adapter = HandwritingHTRAdapter()
        assert adapter.is_available() == HAVE_TORCH_STACK

    def test_healthcheck_is_lightweight(self):
        report = HandwritingHTRAdapter().healthcheck()
        assert set(report) >= {"ok", "error", "version", "details"}
        if not HAVE_TORCH_STACK:
            assert report["ok"] is False


# ---------------------------------------------------------------------------
# Failure paths — explicit, never silent
# ---------------------------------------------------------------------------
class TestFailurePaths:
    @pytest.mark.skipif(HAVE_TORCH_STACK, reason="torch stack present — no ImportError path")
    def test_run_without_torch_stack_raises_explicitly(self):
        with pytest.raises(EngineNotExecutableError):
            HandwritingHTRAdapter().run(_TINY_IMAGE, block_type="handwriting")

    def test_pipeline_crash_propagates_to_executor_layer(self):
        """If the HTR pipeline itself raises, the adapter must not swallow
        the error into a fake success — the executor records the failure."""
        adapter = HandwritingHTRAdapter()

        class ExplodingPipeline:
            def recognize(self, image):
                raise RuntimeError("model exploded")

        adapter._pipeline = ExplodingPipeline()
        with pytest.raises(RuntimeError, match="model exploded"):
            adapter.run(_TINY_IMAGE, block_type="handwriting")


# ---------------------------------------------------------------------------
# Mocked inference — offline success path with provenance
# ---------------------------------------------------------------------------
class TestMockedInference:
    @staticmethod
    def _fake_htr_result():
        from packages.vision.htr.arabic_htr import HTRResult, LineResult

        line = LineResult(text="ضغط الدم", confidence=0.91, y_start=0, y_end=20, words=[])
        return HTRResult(text="ضغط الدم", lines=[line], words=[], confidence=0.91)

    def test_mocked_success_maps_htrresult_to_ocrresult(self, monkeypatch):
        constructed = {}

        class FakePipeline:
            def __init__(self, model_path=None, device="cpu"):
                constructed["model_path"] = model_path
                constructed["device"] = device

            def recognize(self, image):
                return self._result

        fake = FakePipeline
        fake._result = self._fake_htr_result()
        monkeypatch.setattr(
            "packages.vision.htr.arabic_htr.ArabicHandwrittenHTR", fake
        )

        adapter = HandwritingHTRAdapter(model_path="/models/arabic-lora-v1", device="cpu")
        result = adapter.run(_TINY_IMAGE, block_type="handwriting", language="ar")

        assert result.success
        assert result.engine == "TrOCR"
        assert result.text == "ضغط الدم"
        assert result.confidence == pytest.approx(0.91)
        assert constructed == {"model_path": "/models/arabic-lora-v1", "device": "cpu"}
        # provenance distinguishes engine + script + model + normalization
        assert result.provenance["engine"] == "TrOCR"
        assert result.provenance["script_kind"] == "handwriting"
        assert result.provenance["language"] == "ar"
        assert result.provenance["model"] == "/models/arabic-lora-v1"
        assert result.provenance["normalization"]["dotted_recovery"] is True

    def test_default_model_is_recorded_as_latin_baseline(self, monkeypatch):
        """The default HF model id must be visible in provenance and must be
        flagged as a LATIN baseline — never as Arabic handwriting proof."""
        captured = {}

        class RecordingPipeline:
            def __init__(self, model_path=None, device="cpu"):
                captured["model_path"] = model_path

            def recognize(self, image):
                from packages.vision.htr.arabic_htr import HTRResult

                return HTRResult(text="", lines=[], words=[], confidence=0.0)

        monkeypatch.setattr(
            "packages.vision.htr.arabic_htr.ArabicHandwrittenHTR", RecordingPipeline
        )
        adapter = HandwritingHTRAdapter()
        result = adapter.run(_TINY_IMAGE, block_type="handwriting")

        assert captured["model_path"] is None  # default base model used
        assert "trocr-base-handwritten" in result.provenance["base_model"]
        assert "LATIN" in result.provenance["base_model_note"]
        assert not result.success  # empty text is not a silent success

    def test_empty_text_is_explicit_not_success(self, monkeypatch):
        class EmptyPipeline:
            def __init__(self, model_path=None, device="cpu"):
                pass

            def recognize(self, image):
                from packages.vision.htr.arabic_htr import HTRResult

                return HTRResult(text="", lines=[], words=[], confidence=0.0)

        monkeypatch.setattr(
            "packages.vision.htr.arabic_htr.ArabicHandwrittenHTR", EmptyPipeline
        )
        result = HandwritingHTRAdapter().run(_TINY_IMAGE, block_type="handwriting")
        assert not result.success
