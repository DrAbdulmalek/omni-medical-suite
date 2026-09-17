"""AHW-02B/C/F — Router execution bridge (controlled handwriting OCR).

The PROVEN gap (AHW-01 §C/§D): ``EngineRouter.select()`` returns engine
NAMES only, and the only production caller formats them into a
recommendation string — no engine is ever executed.  This module adds the
smallest possible execution bridge WITHOUT new frameworks:

    caller → EngineRouter.select() → RouterExecutor.execute()
           → ExecutableEngineAdapter.run() → existing OCRResult

Design decisions (AHW-02B contract answers):
    - The router contract STAYS ``(engine names, reasons)`` — a selection
      contract.  Execution is a separate, composable step.
    - Adapters are the existing ``EngineAdapter`` abstraction, extended by
      ``ExecutableEngineAdapter`` with a single ``run()`` method.
    - Results are the existing ``packages.omni_ocr.OCRResult``, extended
      with one optional ``provenance`` field (AHW-02D, minimal change).
    - Fallback is NEVER silent (AHW-02 §10): only engines returned by
      ``select()`` are attempted, in the router's own order; every
      skip / failure / success is recorded in ``provenance["attempts"]``.
    - The router itself is NOT taught about translation, TM, medical KB,
      Telegram or cloud AI — OCR/HTR execution only (AHW-02 §3/§11).
"""

from __future__ import annotations

import importlib.util
import logging
import os
import time
from abc import ABC
from typing import Any, Dict, List, Optional, Sequence

from packages.core.engine_registry import EngineAdapter
from packages.core.engine_router import EngineRouter
from packages.omni_ocr.adapter import OCRResult

logger = logging.getLogger(__name__)

__all__ = [
    "EngineNotExecutableError",
    "ExecutableEngineAdapter",
    "HandwritingHTRAdapter",
    "OLMoCRAdapter",
    "RouterExecutor",
    "build_default_executor",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class EngineNotExecutableError(RuntimeError):
    """Raised when an adapter cannot execute in this environment/contract.

    This is an EXPLICIT unavailability signal — it must never be converted
    into a silent fallback to a different engine.
    """


# ---------------------------------------------------------------------------
# Execution-capable adapter base
# ---------------------------------------------------------------------------
class ExecutableEngineAdapter(EngineAdapter, ABC):
    """Existing ``EngineAdapter`` + one execution method.

    Subclasses keep the registry contract (``is_available``/``healthcheck``)
    and add ``run()`` returning the standard ``OCRResult``.
    """

    def run(
        self,
        image: Any,
        *,
        language: str = "ar",
        block_type: str = "paragraph",
    ) -> OCRResult:
        """Execute OCR/HTR on ``image``.  Raise on unavailability/failure —
        the executor records the failure explicitly."""
        raise NotImplementedError(
            f"adapter {self.name!r} declares no execution implementation"
        )


# ---------------------------------------------------------------------------
# AHW-02C — Arabic handwriting HTR (wires the EXISTING packages/vision/htr)
# ---------------------------------------------------------------------------
_TROCR_LATIN_BASE_MODEL = "microsoft/trocr-base-handwritten"


class HandwritingHTRAdapter(ExecutableEngineAdapter):
    """Adapter binding the existing ``ArabicHandwrittenHTR`` pipeline to the
    router's ``TrOCR`` engine name (Qwen → QARI → TrOCR chain).

    REUSE note: the HTR pipeline (line/word segmentation, dotted recovery,
    ``FineTunedTrOCR``) already exists in ``packages/vision/htr`` — this
    adapter only makes it reachable from the router.  No engine logic is
    rebuilt here.

    Model policy (AHW-02C critical rule):
        - default base model ``microsoft/trocr-base-handwritten`` is a
          LATIN-script baseline; its Arabic-handwriting capability is
          UNPROVEN and recorded as such in provenance;
        - no model weights are loaded or downloaded at construction time —
          model loading happens lazily inside ``run()``;
        - pass ``model_path`` to plug a true Arabic model in later without
          code changes.
    """

    name = "TrOCR"
    estimated_ram_gb = 3.5  # mirrors the registry's TrOCR declaration
    supported_tasks = ["handwriting", "printed", "latin", "arabic"]

    def __init__(self, model_path: Optional[str] = None, device: str = "cpu") -> None:
        self._model_path = model_path
        self._device = device
        self._pipeline: Optional[Any] = None

    # -- registry contract --------------------------------------------------
    def is_available(self) -> bool:
        return (
            importlib.util.find_spec("torch") is not None
            and importlib.util.find_spec("transformers") is not None
        )

    def healthcheck(self) -> Dict[str, Any]:
        if not self.is_available():
            return {
                "ok": False,
                "error": "torch/transformers not importable (no model load attempted)",
                "version": None,
                "details": {"device": self._device},
            }
        try:
            import torch  # noqa: WPS433 (runtime check only)

            return {
                "ok": True,
                "error": None,
                "version": f"torch {torch.__version__}",
                "details": {"device": self._device, "cuda": bool(torch.cuda.is_available())},
            }
        except Exception as exc:  # pragma: no cover - depends on env
            return {"ok": False, "error": str(exc), "version": None, "details": {}}

    # -- execution ----------------------------------------------------------
    def _get_pipeline(self) -> Any:
        """Lazily construct the HTR pipeline (first ``run()`` call only)."""
        if self._pipeline is None:
            from packages.vision.htr.arabic_htr import ArabicHandwrittenHTR

            self._pipeline = ArabicHandwrittenHTR(
                model_path=self._model_path, device=self._device
            )
        return self._pipeline

    def run(
        self,
        image: Any,
        *,
        language: str = "ar",
        block_type: str = "handwriting",
    ) -> OCRResult:
        started = time.perf_counter()
        try:
            pipeline = self._get_pipeline()
        except Exception as exc:
            raise EngineNotExecutableError(
                f"TrOCR HTR pipeline unavailable: {type(exc).__name__}: {exc}"
            ) from exc

        htr = pipeline.recognize(image)
        elapsed = time.perf_counter() - started
        text = (htr.text or "").strip()

        return OCRResult(
            text=text,
            confidence=float(htr.confidence or 0.0),
            engine=self.name,
            word_count=len(htr.words),
            words=[
                {"text": w.text, "confidence": w.confidence}
                for w in htr.words
            ],
            raw_result={"lines": len(htr.lines), "device": self._device},
            error="" if text else "HTR produced no text",
            provenance={
                "engine": self.name,
                "script_kind": "handwriting" if block_type == "handwriting" else "printed",
                "language": language,
                "model": self._model_path,
                "base_model": _TROCR_LATIN_BASE_MODEL,
                "base_model_note": (
                    "LATIN-script pretrained baseline — Arabic handwriting "
                    "capability UNPROVEN (no benchmark; AHW-02 §12)"
                ),
                "normalization": {"state": "raw-engine-output", "dotted_recovery": True},
                "processing_time": round(elapsed, 3),
            },
        )


# ---------------------------------------------------------------------------
# AHW-02F — OLMoCR optional adapter (absent from main; optional dependency)
# ---------------------------------------------------------------------------
class OLMoCRAdapter(ExecutableEngineAdapter):
    """Optional OLMoCR adapter behind the existing adapter contract.

    OLMoCR is ABSENT from ``main`` (AHW-01 §EV-1, PROVEN).  This adapter:
        - keeps the repository fully functional WITHOUT olmocr installed
          (``is_available() = False`` → explicit skip, never a crash);
        - is NOT added to any router profile (no silent integration);
        - probes a small documented entrypoint contract at run time and
          fails EXPLICITLY when the upstream package changes shape
          (the upstream API is not pinned on main — see AHW-02 report §G);
        - never downloads models, never calls the network in tests.
    """

    name = "OLMoCR"
    estimated_ram_gb = 4.5
    supported_tasks = ["printed", "structured", "document"]

    # -- registry contract --------------------------------------------------
    def is_available(self) -> bool:
        try:
            return importlib.util.find_spec("olmocr") is not None
        except (ImportError, ValueError):
            # defensive: namespace packages / broken installs must read as
            # "unavailable", never crash the availability probe
            return False

    def healthcheck(self) -> Dict[str, Any]:
        if not self.is_available():
            return {
                "ok": False,
                "error": "olmocr package not installed (optional dependency)",
                "version": None,
                "details": {},
            }
        try:
            import olmocr  # noqa: WPS433

            return {
                "ok": True,
                "error": None,
                "version": getattr(olmocr, "__version__", "unknown"),
                "details": {},
            }
        except Exception as exc:  # pragma: no cover - depends on env
            return {"ok": False, "error": str(exc), "version": None, "details": {}}

    # -- execution ----------------------------------------------------------
    @staticmethod
    def _resolve_entrypoint(module: Any) -> tuple[str, Any]:
        for attr in ("process_document", "process_pdf", "pipeline"):
            candidate = getattr(module, attr, None)
            if callable(candidate):
                return attr, candidate
        raise EngineNotExecutableError(
            "olmocr module exposes no known entrypoint "
            "(upstream API not pinned on main — AHW-02 §G)"
        )

    def run(
        self,
        image: Any,
        *,
        language: str = "ar",
        block_type: str = "paragraph",
    ) -> OCRResult:
        started = time.perf_counter()
        if not self.is_available():
            raise EngineNotExecutableError(
                "olmocr not installed — OLMoCR is an optional dependency (AHW-02 §7)"
            )
        try:
            import olmocr  # noqa: WPS433
        except Exception as exc:
            raise EngineNotExecutableError(f"olmocr import failed: {exc}") from exc

        _attr, entrypoint = self._resolve_entrypoint(olmocr)
        payload = entrypoint(image)

        if isinstance(payload, dict):
            text = str(payload.get("markdown") or payload.get("text") or "")
        elif isinstance(payload, str):
            text = payload
        else:
            text = ""

        text = text.strip()
        return OCRResult(
            text=text,
            confidence=0.0,  # upstream exposes no calibrated confidence
            engine=self.name,
            word_count=len(text.split()),
            words=[],
            raw_result=None,
            error="" if text else "OLMoCR produced no text",
            provenance={
                "engine": self.name,
                "script_kind": "handwriting" if block_type == "handwriting" else "printed",
                "language": language,
                "confidence_available": False,
                "upstream_status": "not-pinned-on-main",
                "normalization": {"state": "raw-engine-output"},
                "processing_time": round(time.perf_counter() - started, 3),
            },
        )


# ---------------------------------------------------------------------------
# AHW-02B — the executor (router selection → actual adapter execution)
# ---------------------------------------------------------------------------
class RouterExecutor:
    """Execute the router's selection through executable adapters.

    Fallback semantics (AHW-02 §10 — NO SILENT FALLBACK):
        - ONLY engines returned by ``EngineRouter.select()`` are attempted,
          in the router's own order;
        - skipping (no adapter / unavailable) and failures are recorded in
          ``provenance["attempts"]``;
        - ``fallback_used`` is True iff an engine was actually EXECUTED
          before the successful one (designed, logged, provenance-visible);
        - if nothing succeeds, an explicit error OCRResult is returned —
          no engine outside the selection is ever conjured.
    """

    def __init__(
        self,
        router: EngineRouter,
        adapters: Sequence[ExecutableEngineAdapter] = (),
    ) -> None:
        self._router = router
        self._adapters: Dict[str, ExecutableEngineAdapter] = {}
        for adapter in adapters:
            self._adapters[adapter.name] = adapter

    # -- public API ---------------------------------------------------------
    def execute(
        self,
        image: Any,
        *,
        language: str = "ar",
        block_type: str = "paragraph",
        image_quality: float = 0.80,
        has_diacritics: bool = False,
        document_type: str = "generic",
        prefer_structured_output: bool = False,
    ) -> OCRResult:
        selection, reasons = self._router.select(
            language=language,
            block_type=block_type,
            image_quality=image_quality,
            has_diacritics=has_diacritics,
            prefer_structured_output=prefer_structured_output,
            document_type=document_type,
        )
        attempts: List[Dict[str, Any]] = []
        executed_count = 0

        for engine_name in selection:
            adapter = self._adapters.get(engine_name)
            if adapter is None:
                attempts.append(
                    {"engine": engine_name, "status": "skipped", "reason": "no_executable_adapter"}
                )
                logger.info("Executor: %s skipped — no executable adapter registered", engine_name)
                continue
            if not adapter.is_available():
                attempts.append(
                    {"engine": engine_name, "status": "skipped", "reason": "unavailable"}
                )
                logger.info("Executor: %s skipped — unavailable in this environment", engine_name)
                continue

            started = time.perf_counter()
            try:
                result = adapter.run(image, language=language, block_type=block_type)
            except Exception as exc:
                executed_count += 1
                attempts.append(
                    {
                        "engine": engine_name,
                        "status": "failed",
                        "reason": f"{type(exc).__name__}: {exc}",
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    }
                )
                logger.warning("Executor: %s execution failed: %s", engine_name, exc)
                continue

            executed_count += 1
            attempts.append(
                {
                    "engine": engine_name,
                    "status": "executed",
                    "reason": "" if result.success else "no text produced",
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    "confidence": result.confidence,
                }
            )

            if result.success:
                result.provenance = {
                    **self._base_provenance(selection, reasons, attempts, language, block_type),
                    "fallback_used": executed_count > 1,
                    **(result.provenance or {}),
                }
                # AHW-02D: the engine dimension is authoritative from the
                # result itself, never from merge defaults
                result.provenance["engine"] = result.engine
                logger.info(
                    "Executor: %s succeeded (fallback_used=%s)",
                    engine_name,
                    result.provenance["fallback_used"],
                )
                return result

        summary = "; ".join(
            f"{a['engine']}:{a['status']}" + (f"({a['reason']})" if a.get("reason") else "")
            for a in attempts
        )
        return OCRResult(
            text="",
            confidence=0.0,
            engine="router-executor",
            word_count=0,
            words=[],
            raw_result=None,
            error=f"no selected engine produced text — attempts: {summary}",
            provenance={
                **self._base_provenance(selection, reasons, attempts, language, block_type),
                "fallback_used": False,
                "engine": "router-executor",
                "error_state": "no-engine-produced-text",
            },
        )

    # -- helpers ------------------------------------------------------------
    def _base_provenance(
        self,
        selection: List[str],
        reasons: List[str],
        attempts: List[Dict[str, Any]],
        language: str,
        block_type: str,
    ) -> Dict[str, Any]:
        return {
            "engine": "router-executor",
            "profile": self._router.profile,
            "language": language,
            "block_type": block_type,
            "script_kind": "handwriting" if block_type == "handwriting" else "printed",
            "selection": selection,
            "reasons": reasons,
            "attempts": attempts,
            "normalization": {"state": "raw-engine-output"},
        }


def build_default_executor(
    profile: Optional[str] = None,
    use_gpu: bool = False,
    max_engines: int = 2,
    registry: Optional[Any] = None,
) -> RouterExecutor:
    """Factory: default router + the two adapters PROVEN implementable now.

    Registered adapters: ``HandwritingHTRAdapter`` (existing HTR package)
    and ``OLMoCRAdapter`` (optional).  No cloud engine is ever registered.
    """
    router = EngineRouter(
        profile=profile or os.getenv("ENGINE_PROFILE", "balanced"),
        use_gpu=use_gpu,
        max_engines=max_engines,
        registry=registry,
    )
    return RouterExecutor(
        router=router,
        adapters=[HandwritingHTRAdapter(), OLMoCRAdapter()],
    )
