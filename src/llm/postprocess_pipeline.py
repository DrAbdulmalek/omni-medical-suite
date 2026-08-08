"""
Unified OCR Post-Processing Pipeline
=====================================
Chains rule-based corrections (RTL fix, Arabic normalization) with optional
LLM-powered refinement (Gemini, Jais, or Ollama) and medical field extraction.

All heavy dependencies (torch, google-generativeai, requests) are imported
lazily so the module can be loaded in any environment.

Usage::

    from src.llm.postprocess_pipeline import PostProcessPipeline, PostProcessResult

    pipe = PostProcessPipeline()          # auto-detects best available backend
    result: PostProcessResult = pipe.process(raw_ocr_text)
    print(result.final_text)
    print(result.fields)                  # dict or None
"""

from __future__ import annotations

import logging
import os
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

__all__ = ["PostProcessPipeline", "PostProcessResult"]

# ── Valid backend names ──────────────────────────────────────────────────────
BackendName = Literal["auto", "gemini", "jais", "ollama", "none"]


# ── Result dataclass ─────────────────────────────────────────────────────────
@dataclass(slots=True)
class PostProcessResult:
    """Holds the output of :meth:`PostProcessPipeline.process`."""

    original: str
    rtl_fixed: str
    normalized: str
    llm_corrected: str
    final_text: str
    fields: dict[str, Any] | None
    entities: dict[str, Any] | None
    backend_used: str
    steps_applied: list[str] = field(default_factory=list)


# ── Availability probes ──────────────────────────────────────────────────────

def _probe_gemini() -> bool:
    """Check that ``GEMINI_API_KEY`` is set *and* ``google.generativeai`` is importable."""
    if not os.environ.get("GEMINI_API_KEY"):
        logger.debug("Gemini probe: GEMINI_API_KEY not set")
        return False
    try:
        import google.generativeai  # noqa: F401
        logger.debug("Gemini probe: available")
        return True
    except ImportError:
        logger.debug("Gemini probe: google-generativeai not installed")
        return False


def _probe_jais() -> bool:
    """Check that ``transformers`` *and* ``torch`` are importable."""
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        logger.debug("Jais probe: available")
        return True
    except ImportError:
        logger.debug("Jais probe: torch/transformers not installed")
        return False


def _probe_ollama(host: str = "http://localhost:11434") -> bool:
    """Check that the Ollama server is reachable."""
    try:
        req = urllib.request.Request(f"{host}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                logger.debug("Ollama probe: server reachable at %s", host)
                return True
    except Exception:
        logger.debug("Ollama probe: server not reachable at %s", host)
    return False


# ── Pipeline ─────────────────────────────────────────────────────────────────

class PostProcessPipeline:
    """Unified post-OCR processing pipeline.

    Chains four optional stages:

    1. **RTL fix** — :class:`src.ocr.rtl_utils.ArabicRTLFixer`
    2. **Strong normalization** — :func:`src.ocr.normalization.arabic_strong_normalize`
    3. **LLM correction** — Gemini / Jais / Ollama (selected at init)
    4. **Field extraction** — :class:`src.ocr.field_extractor.ArabicMedicalFieldExtractor`

    Parameters
    ----------
    backend:
        ``"auto"`` (default) probes Gemini → Ollama → Jais → ``"none"``.
        Explicit names skip probing and disable the pipeline gracefully
        if the dependency is missing.
    ollama_host:
        Base URL of the local Ollama server (used only when backend is
        ``"ollama"`` or ``"auto"``).
    """

    def __init__(
        self,
        backend: BackendName = "auto",
        ollama_host: str = "http://localhost:11434",
    ) -> None:
        self._ollama_host = ollama_host
        self._backend: str = self._resolve_backend(backend)
        logger.info("PostProcessPipeline initialised with backend=%r", self._backend)

    # ── backend resolution ───────────────────────────────────────────────

    @staticmethod
    def _resolve_backend(backend: BackendName) -> str:
        if backend == "none":
            return "none"
        if backend == "gemini":
            return "gemini" if _probe_gemini() else "none"
        if backend == "jais":
            return "jais" if _probe_jais() else "none"
        if backend == "ollama":
            return "ollama" if _probe_ollama() else "none"
        # "auto" — ordered fallback
        for name in ("gemini", "ollama", "jais"):
            probe = {"gemini": _probe_gemini, "ollama": _probe_ollama, "jais": _probe_jais}[name]
            if probe():
                return name
        return "none"

    @property
    def backend(self) -> str:
        """The backend that was selected after probing."""
        return self._backend

    # ── Lazy component factories (thread-safe, no shared mutable state) ──

    @staticmethod
    def _get_rtl_fixer():
        from src.ocr.rtl_utils import ArabicRTLFixer
        return ArabicRTLFixer()

    @staticmethod
    def _get_normalizer():
        from src.ocr.normalization import arabic_strong_normalize
        return arabic_strong_normalize

    @staticmethod
    def _get_field_extractor():
        from src.ocr.field_extractor import ArabicMedicalFieldExtractor
        return ArabicMedicalFieldExtractor()

    def _get_llm_refiner(self, block_type: str = "text"):
        """Return a callable ``(text: str) -> tuple[str, dict | None]``.

        The callable returns ``(corrected_text, entities_or_none)``.
        Entities are only provided by the Jais backend.
        """
        if self._backend == "gemini":
            return self._make_gemini_call(block_type)
        if self._backend == "jais":
            return self._make_jais_call()
        if self._backend == "ollama":
            return self._make_ollama_call()
        # "none"
        return None

    # ── LLM backend callables ────────────────────────────────────────────

    def _make_gemini_call(self, block_type: str):
        from packages.ai.gemini_refiner import GeminiRefiner

        refiner = GeminiRefiner()

        def _call(text: str) -> tuple[str, dict | None]:
            try:
                corrected = refiner.refine_block(text, block_type=block_type)
                return corrected, None
            except Exception as exc:
                logger.warning("Gemini refinement failed: %s — returning original", exc)
                return text, None

        return _call

    def _make_jais_call(self):
        from src.llm.proofreader import MedicalProofreader

        proofreader = MedicalProofreader()

        def _call(text: str) -> tuple[str, dict | None]:
            try:
                result = proofreader.proofread(text)
                return result.get("corrected", text), result.get("entities")
            except Exception as exc:
                logger.warning("Jais proofreading failed: %s — returning original", exc)
                return text, None

        return _call

    def _make_ollama_call(self):
        from src.llm.ollama_proofreader import OllamaProofreader

        proofreader = OllamaProofreader(host=self._ollama_host)

        def _call(text: str) -> tuple[str, dict | None]:
            try:
                result = proofreader.proofread(text)
                return result.get("corrected_text", text), None
            except Exception as exc:
                logger.warning("Ollama proofreading failed: %s — returning original", exc)
                return text, None

        return _call

    # ── Main entry point ─────────────────────────────────────────────────

    def process(
        self,
        text: str,
        *,
        block_type: str = "text",
        apply_rtl: bool = True,
        apply_normalization: bool = True,
        apply_llm: bool = True,
        extract_fields: bool = True,
    ) -> PostProcessResult:
        """Run the full post-processing pipeline on a single text.

        Parameters
        ----------
        text:
            Raw OCR text.
        block_type:
            Hint for the LLM refiner (``"text"``, ``"heading"``,
            ``"table"``, etc.).
        apply_rtl:
            Whether to apply the Arabic RTL fix.
        apply_normalization:
            Whether to apply strong Arabic normalization.
        apply_llm:
            Whether to apply LLM-based correction (requires a non-"none"
            backend).
        extract_fields:
            Whether to run medical field extraction on the final text.

        Returns
        -------
        PostProcessResult
        """
        steps: list[str] = []
        current = text or ""
        original = current

        # Step 1 — RTL fix
        rtl_fixed = current
        if apply_rtl:
            try:
                fixer = self._get_rtl_fixer()
                rtl_fixed = fixer.fix_text(current)
                steps.append("rtl_fix")
                logger.debug("Step [rtl_fix] applied")
            except Exception as exc:
                logger.warning("RTL fix failed: %s — skipping", exc)
                rtl_fixed = current
        else:
            logger.debug("Step [rtl_fix] skipped (disabled)")

        # Step 2 — Strong normalization
        normalized = rtl_fixed
        if apply_normalization:
            try:
                norm_fn = self._get_normalizer()
                normalized = norm_fn(rtl_fixed)
                steps.append("normalization")
                logger.debug("Step [normalization] applied")
            except Exception as exc:
                logger.warning("Normalization failed: %s — skipping", exc)
                normalized = rtl_fixed
        else:
            logger.debug("Step [normalization] skipped (disabled)")

        # Step 3 — LLM correction
        llm_corrected = normalized
        entities: dict[str, Any] | None = None
        if apply_llm and self._backend != "none":
            try:
                llm_fn = self._get_llm_refiner(block_type)
                if llm_fn is not None:
                    llm_corrected, entities = llm_fn(normalized)
                    steps.append(f"llm_{self._backend}")
                    logger.debug("Step [llm_%s] applied", self._backend)
                else:
                    logger.debug("Step [llm] skipped — no refiner available")
            except Exception as exc:
                logger.warning("LLM correction failed: %s — skipping", exc)
                llm_corrected = normalized
        else:
            logger.debug(
                "Step [llm] skipped (apply_llm=%s, backend=%r)",
                apply_llm,
                self._backend,
            )

        # Step 4 — Field extraction
        fields: dict[str, Any] | None = None
        final_text = llm_corrected
        if extract_fields:
            try:
                extractor = self._get_field_extractor()
                extracted = extractor.extract_fields(final_text)
                fields = extracted.to_dict()
                steps.append("field_extraction")
                logger.debug("Step [field_extraction] applied")
            except Exception as exc:
                logger.warning("Field extraction failed: %s — skipping", exc)
        else:
            logger.debug("Step [field_extraction] skipped (disabled)")

        return PostProcessResult(
            original=original,
            rtl_fixed=rtl_fixed,
            normalized=normalized,
            llm_corrected=llm_corrected,
            final_text=final_text,
            fields=fields,
            entities=entities,
            backend_used=self._backend,
            steps_applied=steps,
        )

    # ── Batch convenience ────────────────────────────────────────────────

    def process_batch(
        self,
        texts: list[str],
        **kwargs: Any,
    ) -> list[PostProcessResult]:
        """Process multiple texts through the pipeline.

        Parameters
        ----------
        texts:
            List of raw OCR strings.
        **kwargs:
            Forwarded verbatim to :meth:`process` (e.g. ``block_type``,
            ``apply_rtl``, etc.).

        Returns
        -------
        list[PostProcessResult]
            One result per input text, in the same order.
        """
        logger.info("process_batch: %d text(s) with backend=%r", len(texts), self._backend)
        results: list[PostProcessResult] = []
        for idx, t in enumerate(texts):
            logger.debug("process_batch [%d/%d]", idx + 1, len(texts))
            results.append(self.process(t, **kwargs))
        logger.info(
            "process_batch complete: %d result(s), steps in last item: %s",
            len(results),
            results[-1].steps_applied if results else [],
        )
        return results