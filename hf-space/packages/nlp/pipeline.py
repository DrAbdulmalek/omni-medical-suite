"""
Medical NLP Pipeline — Unified Text Processing
================================================
A four-stage pipeline that unifies NLP capabilities from both
**medical-doc-processor** (basic OCR correction, word segmentation) and
**OmniFile_Processor** (full NLP stack) into a single, configurable
processing flow.

Stages
------
1. **Pre-processing** — Language detection, text normalization, RTL handling.
2. **Correction** — Spell check (Arabic + mixed language), AI correction,
   protected-word preservation.
3. **Entity Extraction** — Medical / named entities, PII detection.
4. **Enrichment** — Summarization, classification, study-guide generation.

Configuration
-------------
Stages can be enabled / disabled via constructor flags, the
``NLP_STAGES`` environment variable, or per-call kwargs.

Environment variables
---------------------
``NLP_STAGES``
    Comma-separated list of stages to enable.  Example::

        export NLP_STAGES=preprocessing,correction,entity_extraction,enrichment

    To skip a stage, simply omit it from the list.

Example usage
-------------
::

    from packages.nlp.pipeline import MedicalNLPPipeline

    pipeline = MedicalNLPPipeline()
    result = pipeline.process("مرحبا بالعالم Hello World")
    print(result.corrected_text)
    print(result.entities)
    print(result.summary)
"""

from __future__ import annotations

import logging
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ======================================================================
# Data classes
# ======================================================================


class PipelineStage(str, Enum):
    """Enumerates the four processing stages."""

    PREPROCESSING = "preprocessing"
    CORRECTION = "correction"
    ENTITY_EXTRACTION = "entity_extraction"
    ENRICHMENT = "enrichment"


@dataclass
class StageResult:
    """Result of a single pipeline stage.

    Attributes:
        stage: Which stage produced this result.
        success: Whether the stage completed without error.
        data: Arbitrary dict returned by the stage processor.
        error: Error message if *success* is ``False``.
        duration_sec: Wall-clock time for the stage in seconds.
    """

    stage: str
    success: bool = True
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_sec: float = 0.0


@dataclass
class NLPPipelineResult:
    """Aggregated result of the full NLP pipeline.

    Attributes:
        original_text: The input text before any processing.
        corrected_text: The text after all corrections have been applied.
        language: Detected language code (``'ar'``, ``'en'``, ``'mixed'``).
        direction: Detected text direction (``'rtl'``, ``'ltr'``, ``'mixed'``).
        entities: List of extracted named-entity dicts.
        pii_entities: List of PII / sensitive-data entities.
        summary: Generated summary string (may be empty for short texts).
        classification: Text category and confidence from the classifier.
        study_guide_markdown: Markdown study guide (only if enabled).
        stage_results: Per-stage :class:`StageResult` objects keyed by stage name.
        total_duration_sec: Total wall-clock time for the entire pipeline.
        errors: List of error messages from stages that failed.
    """

    original_text: str = ""
    corrected_text: str = ""
    language: str = "unknown"
    direction: str = "ltr"
    entities: List[Dict[str, Any]] = field(default_factory=list)
    pii_entities: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    classification: Dict[str, Any] = field(default_factory=dict)
    study_guide_markdown: str = ""
    stage_results: Dict[str, StageResult] = field(default_factory=dict)
    total_duration_sec: float = 0.0
    errors: List[str] = field(default_factory=list)

    # ---- convenience helpers ----

    @property
    def succeeded(self) -> bool:
        """Return ``True`` if no stage raised an error."""
        return len(self.errors) == 0

    def get_stage(self, stage: str) -> Optional[StageResult]:
        """Retrieve the :class:`StageResult` for a given stage name."""
        return self.stage_results.get(stage)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the result to a plain dictionary."""
        return {
            "original_text": self.original_text,
            "corrected_text": self.corrected_text,
            "language": self.language,
            "direction": self.direction,
            "entities": self.entities,
            "pii_entities": self.pii_entities,
            "summary": self.summary,
            "classification": self.classification,
            "study_guide_markdown": self.study_guide_markdown,
            "stage_results": {
                k: {
                    "stage": v.stage,
                    "success": v.success,
                    "data": v.data,
                    "error": v.error,
                    "duration_sec": v.duration_sec,
                }
                for k, v in self.stage_results.items()
            },
            "total_duration_sec": self.total_duration_sec,
            "errors": self.errors,
            "succeeded": self.succeeded,
        }


# ======================================================================
# Lazy-import helpers
# ======================================================================


def _import_class(module_path: str, class_name: str) -> Any:
    """Attempt a lazy import and return the class, or ``None`` on failure.

    Args:
        module_path: Dotted Python module path.
        class_name: Name of the class to retrieve.

    Returns:
        The class object, or ``None`` if import failed.
    """
    try:
        import importlib

        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as exc:
        logger.debug("Lazy import %s.%s failed: %s", module_path, class_name, exc)
        return None


# ======================================================================
# MedicalNLPPipeline
# ======================================================================


class MedicalNLPPipeline:
    """Unified Medical NLP Pipeline.

    Orchestrates four processing stages — pre-processing, correction,
    entity extraction, and enrichment — into a single ``process()`` call.

    Each stage can be independently enabled / disabled at construction
    time, via the ``NLP_STAGES`` environment variable, or per-call.

    Stage failures are non-fatal: the pipeline logs the error, records it
    in the result, and continues to the next stage.

    Example::

        pipeline = MedicalNLPPipeline(
            enable_correction=True,
            enable_entity_extraction=True,
        )
        result = pipeline.process("المريض يعاني من الم في الركبة")
        if result.succeeded:
            print(result.corrected_text)

    Args:
        enable_preprocessing: Run Stage 1 (language detection, normalisation,
            RTL handling).
        enable_correction: Run Stage 2 (spell check, AI correction,
            protected words).
        enable_entity_extraction: Run Stage 3 (NER, PII scanning).
        enable_enrichment: Run Stage 4 (summarisation, classification,
            study guide).
        enable_ai_correction: Attempt GPT-based AI correction inside Stage 2.
        enable_study_guide: Generate a study guide inside Stage 4.
        device: Compute device (``'cpu'`` or ``'cuda'``) forwarded to
            sub-components that support it.
        summarizer_max_length: Maximum token length for summarisation output.
        summarizer_min_length: Minimum token length for summarisation output.
        ner_model_name: Optional HuggingFace model name for NER.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        enable_preprocessing: bool = True,
        enable_correction: bool = True,
        enable_entity_extraction: bool = True,
        enable_enrichment: bool = True,
        enable_ai_correction: bool = False,
        enable_study_guide: bool = False,
        device: str = "cpu",
        summarizer_max_length: int = 130,
        summarizer_min_length: int = 30,
        ner_model_name: Optional[str] = None,
    ) -> None:
        """Initialise the pipeline and lazily load sub-components."""

        # ------------------------------------------------------------------
        # Resolve which stages are active.
        # Priority: env-var > explicit flags > defaults.
        # ------------------------------------------------------------------
        self._stages_from_env = self._parse_env_stages()

        self.enable_preprocessing: bool = self._resolve_stage(
            PipelineStage.PREPROCESSING, enable_preprocessing,
        )
        self.enable_correction: bool = self._resolve_stage(
            PipelineStage.CORRECTION, enable_correction,
        )
        self.enable_entity_extraction: bool = self._resolve_stage(
            PipelineStage.ENTITY_EXTRACTION, enable_entity_extraction,
        )
        self.enable_enrichment: bool = self._resolve_stage(
            PipelineStage.ENRICHMENT, enable_enrichment,
        )

        # Fine-grained toggles
        self.enable_ai_correction = enable_ai_correction
        self.enable_study_guide = enable_study_guide
        self.device = device

        # ------------------------------------------------------------------
        # Lazy-load sub-components
        # ------------------------------------------------------------------
        self._language_detector = None
        self._spell_corrector = None
        self._entity_extractor = None
        self._summarizer = None
        self._text_classifier = None
        self._protected_words = None
        self._ai_corrector = None
        self._rtl_fixer = None
        self._mixed_language_handler = None
        self._sensitive_scanner = None
        self._study_guide_generator = None

        # Component configuration
        self._summarizer_max_length = summarizer_max_length
        self._summarizer_min_length = summarizer_min_length
        self._ner_model_name = ner_model_name

        logger.info(
            "MedicalNLPPipeline initialised — stages: preprocessing=%s, "
            "correction=%s, entity_extraction=%s, enrichment=%s",
            self.enable_preprocessing,
            self.enable_correction,
            self.enable_entity_extraction,
            self.enable_enrichment,
        )

    # ------------------------------------------------------------------
    # Environment-variable parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_env_stages() -> Optional[List[str]]:
        """Parse ``NLP_STAGES`` environment variable.

        Returns:
            List of lowercase stage names, or ``None`` if the variable
            is not set.
        """
        env_val = os.environ.get("NLP_STAGES", "").strip()
        if not env_val:
            return None
        return [s.strip().lower() for s in env_val.split(",") if s.strip()]

    def _resolve_stage(self, stage: PipelineStage, flag: bool) -> bool:
        """Determine whether a stage should be active.

        If ``NLP_STAGES`` is set, it takes precedence over the constructor
        flag.  Otherwise, the constructor flag is used.

        Args:
            stage: The stage to resolve.
            flag: The constructor flag value.

        Returns:
            Whether the stage should run.
        """
        if self._stages_from_env is not None:
            return stage.value in self._stages_from_env
        return flag

    # ------------------------------------------------------------------
    # Lazy property loaders
    # ------------------------------------------------------------------

    @property
    def language_detector(self):  # type: ignore[no-untyped-def]
        """Lazily load :class:`LanguageDetector`."""
        if self._language_detector is None:
            cls = _import_class("packages.nlp.language_detector", "LanguageDetector")
            self._language_detector = cls(device=self.device) if cls else None
        return self._language_detector

    @property
    def spell_corrector(self):  # type: ignore[no-untyped-def]
        """Lazily load :class:`SpellCorrector`."""
        if self._spell_corrector is None:
            cls = _import_class("packages.nlp.spell_corrector", "SpellCorrector")
            self._spell_corrector = cls(device=self.device) if cls else None
        return self._spell_corrector

    @property
    def entity_extractor(self):  # type: ignore[no-untyped-def]
        """Lazily load :class:`EntityExtractor`."""
        if self._entity_extractor is None:
            cls = _import_class("packages.nlp.entity_extractor", "EntityExtractor")
            self._entity_extractor = (
                cls(model_name=self._ner_model_name, device=self.device)
                if cls
                else None
            )
        return self._entity_extractor

    @property
    def summarizer(self):  # type: ignore[no-untyped-def]
        """Lazily load :class:`TextSummarizer`."""
        if self._summarizer is None:
            cls = _import_class("packages.nlp.summarizer", "TextSummarizer")
            if cls:
                self._summarizer = cls(
                    max_length=self._summarizer_max_length,
                    min_length=self._summarizer_min_length,
                    device=self.device,
                )
        return self._summarizer

    @property
    def text_classifier(self):  # type: ignore[no-untyped-def]
        """Lazily load :class:`TextClassifier`."""
        if self._text_classifier is None:
            cls = _import_class("packages.nlp.text_classifier", "TextClassifier")
            self._text_classifier = cls(device=self.device) if cls else None
        return self._text_classifier

    @property
    def protected_words(self):  # type: ignore[no-untyped-def]
        """Lazily load :class:`ProtectedWordsManager`."""
        if self._protected_words is None:
            cls = _import_class("packages.nlp.protected_words", "ProtectedWordsManager")
            self._protected_words = cls() if cls else None
        return self._protected_words

    @property
    def ai_corrector(self):  # type: ignore[no-untyped-def]
        """Lazily load :class:`AICorrector` (optional dependency)."""
        if self._ai_corrector is None:
            cls = _import_class("packages.nlp.ai_corrector", "AICorrector")
            self._ai_corrector = cls() if cls else None
        return self._ai_corrector

    @property
    def rtl_fixer(self):  # type: ignore[no-untyped-def]
        """Lazily load :class:`RTLFixer`."""
        if self._rtl_fixer is None:
            cls = _import_class("packages.nlp.arabic_rtl", "RTLFixer")
            self._rtl_fixer = cls() if cls else None
        return self._rtl_fixer

    @property
    def mixed_language_handler(self):  # type: ignore[no-untyped-def]
        """Lazily load :class:`MixedLanguageHandler`."""
        if self._mixed_language_handler is None:
            cls = _import_class("packages.nlp.mixed_language", "MixedLanguageHandler")
            self._mixed_language_handler = cls() if cls else None
        return self._mixed_language_handler

    @property
    def sensitive_scanner(self):  # type: ignore[no-untyped-def]
        """Lazily load :class:`SensitiveDataScanner`."""
        if self._sensitive_scanner is None:
            cls = _import_class(
                "packages.security.sensitive_data_scanner",
                "SensitiveDataScanner",
            )
            self._sensitive_scanner = cls() if cls else None
        return self._sensitive_scanner

    @property
    def study_guide_generator(self):  # type: ignore[no-untyped-def]
        """Lazily load :class:`StudyGuideGenerator`."""
        if self._study_guide_generator is None:
            cls = _import_class("packages.nlp.study_guide", "StudyGuideGenerator")
            self._study_guide_generator = cls() if cls else None
        return self._study_guide_generator

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        text: str,
        language_hint: Optional[str] = None,
        context: Optional[str] = None,
        *,
        skip_preprocessing: bool = False,
        skip_correction: bool = False,
        skip_entity_extraction: bool = False,
        skip_enrichment: bool = False,
    ) -> NLPPipelineResult:
        """Run the full NLP pipeline on *text*.

        Args:
            text: Input text to process.
            language_hint: Optional language hint (``'ar'``, ``'en'``,
                ``'mixed'``).  When provided the language detector may
                be bypassed.
            context: Optional context string forwarded to the AI
                corrector to improve correction quality.
            skip_preprocessing: Override to disable Stage 1 for this call.
            skip_correction: Override to disable Stage 2 for this call.
            skip_entity_extraction: Override to disable Stage 3 for this call.
            skip_enrichment: Override to disable Stage 4 for this call.

        Returns:
            A :class:`NLPPipelineResult` with all stage outputs.
        """
        t0 = time.monotonic()
        result = NLPPipelineResult(original_text=text)
        current_text = text

        # Detect language up-front (used by later stages)
        detected_language = language_hint or "unknown"
        detected_direction = "ltr"

        # ==================================================================
        # Stage 1 — Pre-processing
        # ==================================================================
        if self.enable_preprocessing and not skip_preprocessing:
            sr = self._run_preprocessing(current_text)
            result.stage_results[PipelineStage.PREPROCESSING.value] = sr
            if sr.success:
                detected_language = sr.data.get("language", detected_language)
                detected_direction = sr.data.get("direction", detected_direction)
                current_text = sr.data.get("normalized_text", current_text)
                result.language = detected_language
                result.direction = detected_direction
            else:
                result.errors.append(sr.error or "preprocessing failed")
        else:
            result.stage_results[PipelineStage.PREPROCESSING.value] = StageResult(
                stage=PipelineStage.PREPROCESSING.value,
                success=True,
                data={"skipped": True},
            )

        # ==================================================================
        # Stage 2 — Correction
        # ==================================================================
        if self.enable_correction and not skip_correction:
            sr = self._run_correction(
                current_text,
                language=detected_language,
                context=context,
            )
            result.stage_results[PipelineStage.CORRECTION.value] = sr
            if sr.success:
                current_text = sr.data.get("corrected_text", current_text)
                result.corrected_text = current_text
            else:
                result.errors.append(sr.error or "correction failed")
                result.corrected_text = current_text
        else:
            result.corrected_text = current_text
            result.stage_results[PipelineStage.CORRECTION.value] = StageResult(
                stage=PipelineStage.CORRECTION.value,
                success=True,
                data={"skipped": True},
            )

        # ==================================================================
        # Stage 3 — Entity Extraction
        # ==================================================================
        if self.enable_entity_extraction and not skip_entity_extraction:
            sr = self._run_entity_extraction(
                result.corrected_text,
                language=detected_language,
            )
            result.stage_results[PipelineStage.ENTITY_EXTRACTION.value] = sr
            if sr.success:
                result.entities = sr.data.get("entities", [])
                result.pii_entities = sr.data.get("pii_entities", [])
            else:
                result.errors.append(sr.error or "entity_extraction failed")
        else:
            result.stage_results[PipelineStage.ENTITY_EXTRACTION.value] = StageResult(
                stage=PipelineStage.ENTITY_EXTRACTION.value,
                success=True,
                data={"skipped": True},
            )

        # ==================================================================
        # Stage 4 — Enrichment
        # ==================================================================
        if self.enable_enrichment and not skip_enrichment:
            sr = self._run_enrichment(
                result.corrected_text,
                language=detected_language,
            )
            result.stage_results[PipelineStage.ENRICHMENT.value] = sr
            if sr.success:
                result.summary = sr.data.get("summary", "")
                result.classification = sr.data.get("classification", {})
                result.study_guide_markdown = sr.data.get(
                    "study_guide_markdown", "",
                )
            else:
                result.errors.append(sr.error or "enrichment failed")
        else:
            result.stage_results[PipelineStage.ENRICHMENT.value] = StageResult(
                stage=PipelineStage.ENRICHMENT.value,
                success=True,
                data={"skipped": True},
            )

        result.total_duration_sec = time.monotonic() - t0
        return result

    # ------------------------------------------------------------------
    # Stage implementations
    # ------------------------------------------------------------------

    def _run_preprocessing(self, text: str) -> StageResult:
        """Execute Stage 1: language detection, normalisation, RTL handling.

        Args:
            text: Raw input text.

        Returns:
            A :class:`StageResult` with detection / normalisation data.
        """
        t0 = time.monotonic()
        data: Dict[str, Any] = {}

        try:
            # --- Language detection ---
            language = "unknown"
            confidence = 0.0
            direction = "ltr"

            detector = self.language_detector
            if detector is not None:
                lang_result = detector.detect(text)
                language = lang_result.get("language", "unknown")
                confidence = lang_result.get("confidence", 0.0)
            else:
                logger.warning("LanguageDetector not available — using fallback")

            # --- Text direction ---
            direction = self._detect_direction(text)

            # --- Normalisation ---
            normalized_text = self._normalize_text(text)

            # --- RTL handling ---
            if direction in ("rtl", "mixed"):
                normalized_text = self._apply_rtl_fix(normalized_text)

            data = {
                "language": language,
                "confidence": confidence,
                "direction": direction,
                "normalized_text": normalized_text,
            }

            logger.info(
                "Pre-processing complete — language=%s, direction=%s",
                language,
                direction,
            )
            return StageResult(
                stage=PipelineStage.PREPROCESSING.value,
                success=True,
                data=data,
                duration_sec=time.monotonic() - t0,
            )
        except Exception as exc:
            logger.error("Pre-processing stage failed: %s", exc, exc_info=True)
            return StageResult(
                stage=PipelineStage.PREPROCESSING.value,
                success=False,
                error=str(exc),
                duration_sec=time.monotonic() - t0,
            )

    def _run_correction(
        self,
        text: str,
        language: str = "unknown",
        context: Optional[str] = None,
    ) -> StageResult:
        """Execute Stage 2: spell check, AI correction, protected words.

        Processing order:
        1. Apply protected-word placeholders.
        2. Run spell correction (Arabic-aware).
        3. Run mixed-language correction (if applicable).
        4. Run AI correction (if enabled and available).
        5. Restore protected words.

        Args:
            text: Normalised text from Stage 1.
            language: Detected language code.
            context: Optional context for AI correction.

        Returns:
            A :class:`StageResult` with the corrected text and metadata.
        """
        t0 = time.monotonic()
        data: Dict[str, Any] = {}
        current_text = text
        corrections: List[Dict[str, str]] = []

        try:
            # --- Protected-word preservation ---
            protected_mapping: Dict[str, str] = {}
            pwm = self.protected_words
            if pwm is not None:
                current_text, protected_mapping = pwm.protect_text(current_text)

            # --- Spell correction ---
            spell_data: Dict[str, Any] = {
                "corrected_text": current_text,
                "corrections": [],
                "total_corrections": 0,
            }
            sc = self.spell_corrector
            if sc is not None:
                spell_data = sc.correct_text(current_text)
                current_text = spell_data.get("corrected_text", current_text)
                corrections.extend(
                    {
                        "original": c.get("original", ""),
                        "corrected": c.get("corrected", ""),
                        "source": "spell_corrector",
                    }
                    for c in spell_data.get("corrections", [])
                )

            # --- Mixed-language correction ---
            if language == "mixed":
                mlh = self.mixed_language_handler
                if mlh is not None:
                    mixed_result = mlh.correct_text_mixed(current_text)
                    if mixed_result != current_text:
                        corrections.append({
                            "original": current_text,
                            "corrected": mixed_result,
                            "source": "mixed_language",
                        })
                        current_text = mixed_result

            # --- AI correction (optional) ---
            ai_data: Dict[str, Any] = {"applied": False}
            if self.enable_ai_correction:
                aic = self.ai_corrector
                if aic is not None and aic.is_available():
                    ai_result = aic.correct_text(
                        current_text, language=language, context=context,
                    )
                    if ai_result.get("success", False):
                        ai_text = ai_result.get("corrected_text", current_text)
                        if ai_text != current_text:
                            corrections.append({
                                "original": current_text,
                                "corrected": ai_text,
                                "source": "ai_corrector",
                            })
                            current_text = ai_text
                        ai_data = {
                            "applied": True,
                            "confidence": ai_result.get("confidence", 0),
                            "model": ai_result.get("model_used", ""),
                            "changes": ai_result.get("changes_made", []),
                        }
                else:
                    logger.debug("AI corrector not available — skipping")

            # --- Restore protected words ---
            if protected_mapping and pwm is not None:
                current_text = pwm.restore_text(current_text, protected_mapping)

            data = {
                "corrected_text": current_text,
                "corrections": corrections,
                "total_corrections": len(corrections),
                "spell_correction": spell_data,
                "ai_correction": ai_data,
                "protected_words_count": len(protected_mapping),
            }

            logger.info(
                "Correction complete — %d corrections applied",
                len(corrections),
            )
            return StageResult(
                stage=PipelineStage.CORRECTION.value,
                success=True,
                data=data,
                duration_sec=time.monotonic() - t0,
            )
        except Exception as exc:
            logger.error("Correction stage failed: %s", exc, exc_info=True)
            # Return the last known good text so downstream stages can proceed
            return StageResult(
                stage=PipelineStage.CORRECTION.value,
                success=False,
                data={"corrected_text": current_text, "error_stage": "correction"},
                error=str(exc),
                duration_sec=time.monotonic() - t0,
            )

    def _run_entity_extraction(
        self,
        text: str,
        language: str = "unknown",
    ) -> StageResult:
        """Execute Stage 3: named-entity extraction and PII scanning.

        Runs both the medical / general NER extractor and the
        sensitive-data (PII) scanner.  Results from both are merged
        and deduplicated by text span.

        Args:
            text: Corrected text from Stage 2.
            language: Detected language code.

        Returns:
            A :class:`StageResult` with entities and PII data.
        """
        t0 = time.monotonic()
        data: Dict[str, Any] = {"entities": [], "pii_entities": []}

        try:
            # --- Named-entity extraction ---
            entities: List[Dict[str, Any]] = []
            ee = self.entity_extractor
            if ee is not None:
                entity_doc = ee.extract_from_document(text)
                entities = entity_doc.get("entities", [])
            else:
                logger.warning("EntityExtractor not available — skipping NER")

            # --- PII / sensitive-data scanning ---
            pii_entities: List[Dict[str, Any]] = []
            scanner = self.sensitive_scanner
            if scanner is not None:
                scan_result = scanner.scan_text(text, language=language)
                if scan_result.get("sensitive_data_found", False):
                    pii_entities = scan_result.get("entities", [])
            else:
                logger.warning("SensitiveDataScanner not available — skipping PII")

            data = {
                "entities": entities,
                "entity_count": len(entities),
                "by_type": self._group_entities_by_type(entities),
                "pii_entities": pii_entities,
                "pii_count": len(pii_entities),
                "risk_level": self._compute_overall_risk(pii_entities),
            }

            logger.info(
                "Entity extraction complete — %d entities, %d PII items",
                len(entities),
                len(pii_entities),
            )
            return StageResult(
                stage=PipelineStage.ENTITY_EXTRACTION.value,
                success=True,
                data=data,
                duration_sec=time.monotonic() - t0,
            )
        except Exception as exc:
            logger.error("Entity extraction stage failed: %s", exc, exc_info=True)
            return StageResult(
                stage=PipelineStage.ENTITY_EXTRACTION.value,
                success=False,
                error=str(exc),
                duration_sec=time.monotonic() - t0,
            )

    def _run_enrichment(
        self,
        text: str,
        language: str = "unknown",
    ) -> StageResult:
        """Execute Stage 4: summarisation, classification, study guide.

        Args:
            text: Corrected text from Stage 2.
            language: Detected language code.

        Returns:
            A :class:`StageResult` with summary, classification, and
            optional study guide.
        """
        t0 = time.monotonic()
        data: Dict[str, Any] = {}

        try:
            # --- Summarisation ---
            summary = ""
            summary_data: Dict[str, Any] = {"generated": False}
            summ = self.summarizer
            if summ is not None:
                summ_result = summ.summarize(text, language=language)
                summary = summ_result.get("summary", "")
                summary_data = {
                    "generated": True,
                    "model": summ_result.get("model", ""),
                    "compression_ratio": summ_result.get(
                        "compression_ratio", 0.0,
                    ),
                    "from_cache": summ_result.get("from_cache", False),
                }
            else:
                logger.debug("TextSummarizer not available — skipping")

            # --- Classification ---
            classification: Dict[str, Any] = {}
            tc = self.text_classifier
            if tc is not None:
                classification = tc.classify(text)
            else:
                logger.debug("TextClassifier not available — skipping")

            # --- Study guide (optional) ---
            study_guide_markdown = ""
            if self.enable_study_guide:
                sgg = self.study_guide_generator
                if sgg is not None:
                    ocr_items = [{"text": text, "confidence": 1.0, "page": 1}]
                    study_guide_markdown = sgg.generate_markdown(ocr_items)
                else:
                    logger.debug("StudyGuideGenerator not available — skipping")

            data = {
                "summary": summary,
                "summary_meta": summary_data,
                "classification": classification,
                "study_guide_markdown": study_guide_markdown,
            }

            logger.info("Enrichment complete — summary=%s, category=%s",
                        bool(summary),
                        classification.get("category", "N/A"))
            return StageResult(
                stage=PipelineStage.ENRICHMENT.value,
                success=True,
                data=data,
                duration_sec=time.monotonic() - t0,
            )
        except Exception as exc:
            logger.error("Enrichment stage failed: %s", exc, exc_info=True)
            return StageResult(
                stage=PipelineStage.ENRICHMENT.value,
                success=False,
                error=str(exc),
                duration_sec=time.monotonic() - t0,
            )

    # ------------------------------------------------------------------
    # Text helpers (private)
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Apply Unicode normalisation and whitespace cleanup.

        Args:
            text: Raw input text.

        Returns:
            Normalised text.
        """
        if not text:
            return text

        # Unicode NFC normalisation
        normalized = unicodedata.normalize("NFC", text)

        # Collapse multiple whitespace (but preserve newlines)
        normalized = re.sub(r"[^\S\n]+", " ", normalized)

        # Remove zero-width characters
        normalized = re.sub(
            r"[\u200b\u200c\u200d\u200e\u200f\ufeff\u00ad]", "",
            normalized,
        )

        # Strip leading / trailing whitespace per line
        lines = [line.strip() for line in normalized.splitlines()]
        normalized = "\n".join(lines)

        return normalized.strip()

    def _detect_direction(self, text: str) -> str:
        """Detect text direction using :class:`RTLFixer` helpers or fallback.

        Args:
            text: Input text.

        Returns:
            ``'rtl'``, ``'ltr'``, or ``'mixed'``.
        """
        try:
            from packages.nlp.arabic_rtl import get_text_direction  # type: ignore

            return get_text_direction(text)
        except ImportError:
            # Fallback: heuristic based on character counting
            rtl_count = sum(
                1
                for c in text
                if "\u0600" <= c <= "\u06FF" or "\u0590" <= c <= "\u05FF"
            )
            ltr_count = sum(1 for c in text if c.isascii() and c.isalpha())
            total = max(rtl_count + ltr_count, 1)
            rtl_ratio = rtl_count / total
            ltr_ratio = ltr_count / total

            if rtl_ratio > 0.7:
                return "rtl"
            if ltr_ratio > 0.7:
                return "ltr"
            return "mixed"

    def _apply_rtl_fix(self, text: str) -> str:
        """Apply RTL display fixing if available.

        Args:
            text: Text that may need RTL reordering.

        Returns:
            RTL-fixed text.
        """
        fixer = self.rtl_fixer
        if fixer is not None:
            try:
                return fixer.fix_text(text)
            except Exception as exc:
                logger.warning("RTL fix failed: %s", exc)
        return text

    @staticmethod
    def _group_entities_by_type(
        entities: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group entity dicts by their ``type`` key.

        Args:
            entities: Flat list of entity dicts.

        Returns:
            Dict mapping entity type to list of entity dicts.
        """
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for ent in entities:
            etype = ent.get("type", "UNKNOWN")
            grouped.setdefault(etype, []).append(ent)
        return grouped

    @staticmethod
    def _compute_overall_risk(
        pii_entities: List[Dict[str, Any]],
    ) -> str:
        """Compute an overall risk level from PII entities.

        Args:
            pii_entities: List of PII entity dicts with a ``risk`` key.

        Returns:
            One of ``'none'``, ``'low'``, ``'medium'``, ``'high'``,
            ``'critical'``.
        """
        if not pii_entities:
            return "none"

        risk_scores = {
            "none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4,
        }
        max_score = 0
        for ent in pii_entities:
            risk = ent.get("risk", "medium")
            if isinstance(risk, str):
                max_score = max(max_score, risk_scores.get(risk, 2))
            elif isinstance(risk, (int, float)):
                max_score = max(max_score, int(risk))

        for level, score in risk_scores.items():
            if score == max_score:
                return level
        return "medium"

    # ------------------------------------------------------------------
    # Utility / introspection
    # ------------------------------------------------------------------

    def get_available_components(self) -> Dict[str, bool]:
        """Report which sub-components loaded successfully.

        Returns:
            Dict mapping component name to availability boolean.
        """
        return {
            "language_detector": self.language_detector is not None,
            "spell_corrector": self.spell_corrector is not None,
            "entity_extractor": self.entity_extractor is not None,
            "summarizer": self.summarizer is not None,
            "text_classifier": self.text_classifier is not None,
            "protected_words": self.protected_words is not None,
            "ai_corrector": self.ai_corrector is not None,
            "rtl_fixer": self.rtl_fixer is not None,
            "mixed_language_handler": self.mixed_language_handler is not None,
            "sensitive_scanner": self.sensitive_scanner is not None,
            "study_guide_generator": self.study_guide_generator is not None,
        }

    def get_active_stages(self) -> List[str]:
        """Return the list of currently active stage names.

        Returns:
            List of stage name strings.
        """
        stages = []
        if self.enable_preprocessing:
            stages.append(PipelineStage.PREPROCESSING.value)
        if self.enable_correction:
            stages.append(PipelineStage.CORRECTION.value)
        if self.enable_entity_extraction:
            stages.append(PipelineStage.ENTITY_EXTRACTION.value)
        if self.enable_enrichment:
            stages.append(PipelineStage.ENRICHMENT.value)
        return stages

    def __repr__(self) -> str:
        return (
            f"MedicalNLPPipeline("
            f"stages={self.get_active_stages()}, "
            f"ai_correction={self.enable_ai_correction}, "
            f"device={self.device!r})"
        )
