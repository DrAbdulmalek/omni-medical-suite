"""AHW-02B / AHW-02G — Router execution bridge contract tests (test-first).

Proves the smallest possible repair required by AHW-02B:
    router selection  ->  actual adapter execution
while preserving:
    - existing EngineRouter.select() contract  (list[str], list[str])
    - existing EngineAdapter registry abstraction
    - existing OCRResult result contract
    - explicit (non-silent) fallback behaviour with full provenance

Rule under test (AHW-02 §10 NO SILENT FALLBACK):
    Only engines returned by EngineRouter.select() are attempted, in the
    router's own order.  Every skip/failure is recorded in provenance.
    No engine outside the selection is ever executed.
"""

import pytest

from packages.core.engine_registry import EngineAdapter
from packages.core.engine_router import EngineRouter
from packages.core.router_executor import (
    EngineNotExecutableError,
    ExecutableEngineAdapter,
    RouterExecutor,
    build_default_executor,
)
from packages.omni_ocr.adapter import OCRResult


# ---------------------------------------------------------------------------
# Fake adapters bound to REAL router engine names
# ---------------------------------------------------------------------------
class FakeHandwritingAdapter(ExecutableEngineAdapter):
    """Configurable fake bound to one of the router's handwriting engines."""

    # class-level concrete implementations of the EngineAdapter ABC contract
    name = "FakeEngine"
    estimated_ram_gb = 1.0
    supported_tasks = ["handwriting", "printed"]

    def __init__(
        self,
        name: str,
        *,
        available: bool = True,
        text: str = "نص مزيف",
        fail: bool = False,
        ram: float = 1.0,
    ) -> None:
        self._name = name
        self._available = available
        self._text = text
        self._fail = fail
        self.estimated_ram_gb = ram
        self.calls: int = 0

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return self._available

    def healthcheck(self):
        return {"ok": True, "error": None, "version": "fake", "details": {}}

    def run(self, image, *, language: str = "ar", block_type: str = "paragraph") -> OCRResult:
        self.calls += 1
        if self._fail:
            raise RuntimeError(f"fake engine {self._name} failed")
        return OCRResult(
            text=self._text,
            confidence=0.90,
            engine=self._name,
            provenance={"fake": True, "script_kind": "handwriting" if block_type == "handwriting" else "printed"},
        )


def _make_executor(adapter_list, router_kwargs=None) -> RouterExecutor:
    # Router parameters chosen explicitly and documented: with the DEFAULTS
    # (max_engines=2, RAM=8GB) the real router's handwriting selection is
    # [Qwen, EasyOCR] — QARI is RAM-filtered (5.5+4.5>8) and EasyOCR is
    # appended by the arabic-language branch.  max_engines=3 + RAM=14GB
    # (5.5+4.5+3.5=13.5) yields the full declared chain [Qwen, QARI, TrOCR],
    # which is the behaviour under test here.
    kwargs = {"max_engines": 3, "available_ram_gb": 14.0}
    kwargs.update(router_kwargs or {})
    return RouterExecutor(router=EngineRouter(**kwargs), adapters=adapter_list)


# ---------------------------------------------------------------------------
# Contract of the bridge itself
# ---------------------------------------------------------------------------
class TestExecutableAdapterContract:
    def test_extends_existing_engine_adapter(self):
        assert issubclass(ExecutableEngineAdapter, EngineAdapter)

    def test_base_run_is_not_executable(self):
        class NoRunAdapter(ExecutableEngineAdapter):
            name = "NoRun"
            estimated_ram_gb = 1.0
            supported_tasks = ["printed"]

            def is_available(self):
                return True

            def healthcheck(self):
                return {"ok": True, "error": None, "version": None, "details": {}}

        with pytest.raises(NotImplementedError):
            NoRunAdapter().run(object())

    def test_engine_not_executable_error_exists(self):
        assert issubclass(EngineNotExecutableError, RuntimeError)


# ---------------------------------------------------------------------------
# Selection -> execution, per block type
# ---------------------------------------------------------------------------
class TestRouterExecution:
    def test_handwriting_selection_executes_first_available_engine(self):
        """Qwen unavailable -> QARI unavailable -> TrOCR executes (router order)."""
        qwen = FakeHandwritingAdapter("Arabic-handwritten-OCR (Qwen)", available=False)
        qari = FakeHandwritingAdapter("QARI", available=False)
        trocr = FakeHandwritingAdapter("TrOCR", text="نتيجة TrOCR")
        executor = _make_executor([qwen, qari, trocr])

        result = executor.execute(image=object(), block_type="handwriting")

        assert result.success
        assert result.engine == "TrOCR"
        assert result.text == "نتيجة TrOCR"
        assert trocr.calls == 1
        assert qwen.calls == 0 and qari.calls == 0

    def test_execution_uses_real_router_selection(self):
        """Selection must come from EngineRouter.select() itself."""
        executor = _make_executor([FakeHandwritingAdapter("TrOCR")])
        selection, _ = executor._router.select(block_type="handwriting")
        result = executor.execute(image=object(), block_type="handwriting")
        assert result.engine == selection[-1]  # first two skipped, last executed

    def test_printed_selection_executes(self):
        easy = FakeHandwritingAdapter("EasyOCR", text="printed output")
        executor = _make_executor([easy])
        result = executor.execute(image=object(), block_type="paragraph", language="ar")
        assert result.success
        assert result.engine == "EasyOCR"
        assert easy.calls == 1

    def test_unknown_block_type_does_not_raise(self):
        """Unknown block type → router default fallback path, still executed."""
        easy = FakeHandwritingAdapter("EasyOCR", text="fallback output")
        executor = _make_executor([easy])
        result = executor.execute(image=object(), block_type="definitely_not_a_block")
        assert result.success
        assert result.engine == "EasyOCR"


# ---------------------------------------------------------------------------
# NO SILENT FALLBACK (AHW-02 §10)
# ---------------------------------------------------------------------------
class TestNoSilentFallback:
    def test_unselected_engines_are_never_attempted(self):
        """Tesseract adapter is registered but never selected for handwriting
        (default image quality) — it must NOT be executed, even silently."""
        trocr = FakeHandwritingAdapter("TrOCR", text="ok")
        tesseract = FakeHandwritingAdapter("Tesseract", text="silent fallback?")
        executor = _make_executor([trocr, tesseract])

        result = executor.execute(image=object(), block_type="handwriting")

        assert result.success
        assert result.engine == "TrOCR"
        assert tesseract.calls == 0
        attempted = [a["engine"] for a in result.provenance["attempts"] if a["status"] == "executed"]
        assert "Tesseract" not in attempted

    def test_all_selected_fail_explicit_error_no_hidden_retry(self):
        qwen = FakeHandwritingAdapter("Arabic-handwritten-OCR (Qwen)", fail=True)
        qari = FakeHandwritingAdapter("QARI", fail=True)
        trocr = FakeHandwritingAdapter("TrOCR", fail=True)
        executor = _make_executor([qwen, qari, trocr])

        result = executor.execute(image=object(), block_type="handwriting")

        assert not result.success
        assert result.text == ""
        assert result.error  # explicit error state
        statuses = {a["engine"]: a["status"] for a in result.provenance["attempts"]}
        assert statuses == {
            "Arabic-handwritten-OCR (Qwen)": "failed",
            "QARI": "failed",
            "TrOCR": "failed",
        }

    def test_missing_adapter_recorded_not_crash(self):
        """Engines selected by the router but with no registered adapter are
        recorded as skipped with an explicit reason."""
        trocr = FakeHandwritingAdapter("TrOCR", text="ok")
        executor = _make_executor([trocr])
        result = executor.execute(image=object(), block_type="handwriting")
        assert result.success
        skipped = {a["engine"]: a for a in result.provenance["attempts"] if a["status"] == "skipped"}
        assert "Arabic-handwritten-OCR (Qwen)" in skipped
        assert "QARI" in skipped
        assert "no_executable_adapter" in skipped["Arabic-handwritten-OCR (Qwen)"]["reason"]

    def test_unavailable_adapter_recorded(self):
        qari = FakeHandwritingAdapter("QARI", available=False)
        trocr = FakeHandwritingAdapter("TrOCR", text="ok")
        executor = _make_executor([qari, trocr])
        result = executor.execute(image=object(), block_type="handwriting")
        assert result.success
        skipped = {a["engine"]: a for a in result.provenance["attempts"] if a["status"] == "skipped"}
        assert skipped["QARI"]["reason"] == "unavailable"

    def test_fallback_flag_visible_when_first_engine_fails(self):
        """Explicit fallback: Qwen fails at runtime -> TrOCR executed. This
        fallback is designed, declared and provenance-visible."""
        qwen = FakeHandwritingAdapter("Arabic-handwritten-OCR (Qwen)", fail=True)
        qari = FakeHandwritingAdapter("QARI", available=False)
        trocr = FakeHandwritingAdapter("TrOCR", text="rescued")
        executor = _make_executor([qwen, qari, trocr])

        result = executor.execute(image=object(), block_type="handwriting")

        assert result.success and result.engine == "TrOCR"
        assert result.provenance["fallback_used"] is True
        assert result.provenance["attempts"][0]["status"] == "failed"


# ---------------------------------------------------------------------------
# AHW-02D — result + provenance contract
# ---------------------------------------------------------------------------
class TestResultContract:
    def test_result_is_standard_ocrresult_with_provenance(self):
        executor = _make_executor([FakeHandwritingAdapter("TrOCR", text="x")])
        result = executor.execute(image=object(), block_type="handwriting", language="ar")
        assert isinstance(result, OCRResult)
        assert hasattr(result, "provenance")
        assert "provenance" in result.to_dict()

    def test_provenance_distinguishes_required_dimensions(self):
        """AHW-02D: engine / profile / language / script / fallback /
        normalization / error state must be distinguishable."""
        executor = _make_executor([FakeHandwritingAdapter("TrOCR", text="x")])
        result = executor.execute(image=object(), block_type="handwriting", language="ar")
        prov = result.provenance
        assert prov["engine"] == "TrOCR"
        assert prov["profile"] == "balanced"
        assert prov["language"] == "ar"
        assert prov["block_type"] == "handwriting"
        assert prov["script_kind"] == "handwriting"
        assert prov["fallback_used"] is False
        assert prov["selection"] and prov["reasons"]
        assert prov["normalization"]["state"] == "raw-engine-output"
        assert result.error == ""

    def test_printed_script_kind_recorded(self):
        executor = _make_executor([FakeHandwritingAdapter("EasyOCR", text="x")])
        result = executor.execute(image=object(), block_type="paragraph", language="ar")
        assert result.provenance["script_kind"] == "printed"


# ---------------------------------------------------------------------------
# Default factory (OLMoCR adapter stays optional — see test_olmocr_adapter)
# ---------------------------------------------------------------------------
class TestDefaultExecutorFactory:
    def test_build_default_executor_registers_trocr_and_olmocr(self):
        executor = build_default_executor()
        assert isinstance(executor, RouterExecutor)
        assert isinstance(executor._router, EngineRouter)
        assert set(executor._adapters.keys()) == {"TrOCR", "OLMoCR"}

    def test_default_executor_attempts_only_selected_engines(self):
        executor = build_default_executor()
        result = executor.execute(image=object(), block_type="handwriting")
        # In this CPU-only environment every real adapter is unavailable —
        # execution must fail EXPLICITLY, never silently, never via cloud.
        assert not result.success
        assert result.error
        attempted = [a["engine"] for a in result.provenance["attempts"]]
        # every selected engine got exactly one attempt record, in order
        assert attempted == result.provenance["selection"]
        # and no cloud engine can ever appear in the handwriting path
        assert {"mistral", "MISTRAL", "MistralOCR"}.isdisjoint(attempted)
