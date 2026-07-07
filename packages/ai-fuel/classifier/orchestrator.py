"""
AI Fuel Engine - Classification Orchestrator Module

Orchestrates the 3-layer hierarchical classification pipeline:

    1. **Keyword Router** (fast, <1ms) — inverted-index keyword matching.
    2. **Semantic Matcher** (medium, ~50ms) — vector-similarity search.
    3. **LLM Classifier** (slow, ~2s) — large-language-model analysis.

The orchestrator tries each layer in order and returns the first result
that meets the confidence threshold.  Only uncertain texts cascade
down to more expensive layers, keeping overall throughput high.

Batch classification is optimised by processing all texts through the
keyword layer first and only forwarding low-confidence items to
downstream classifiers.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from core.config import AIFuelConfig
from core.schemas import ClassificationMethod, ClassificationResult

logger = logging.getLogger(__name__)


class ClassificationOrchestrator:
    """Orchestrates 3-layer hierarchical classification.

    Manages the lifecycle of :class:`KeywordRouter`, :class:`SemanticMatcher`,
    and :class:`LLMClassifier` instances, routing text chunks through the
    hierarchy based on confidence thresholds.

    Usage::

        orchestrator = ClassificationOrchestrator()
        result = orchestrator.classify("Patient presents with acute MI...")
        print(result.category, result.confidence, result.method)

    Args:
        config: An :class:`AIFuelConfig` instance.  When ``None`` the
            default configuration is used.
        keyword_threshold: Minimum confidence for keyword classification
            (default ``0.85``).
        semantic_threshold: Minimum confidence for semantic classification
            (default ``0.85``).
        taxonomy_path: Path to the medical taxonomy JSON.
        enable_semantic: Whether to enable Layer 2 (semantic matching).
        enable_llm: Whether to enable Layer 3 (LLM classification).
        llm_provider: LLM provider to use (``"gemini"``, ``"openai"``,
            ``"local"``).
        llm_api_key: API key for the chosen LLM provider.
    """

    def __init__(
        self,
        config: Optional[AIFuelConfig] = None,
        keyword_threshold: float = 0.85,
        semantic_threshold: float = 0.85,
        taxonomy_path: Optional[str] = None,
        enable_semantic: bool = True,
        enable_llm: bool = True,
        llm_provider: str = "gemini",
        llm_api_key: Optional[str] = None,
    ) -> None:
        self.config = config or AIFuelConfig()

        # Override thresholds if explicitly provided
        self.keyword_threshold: float = (
            keyword_threshold
            if keyword_threshold != 0.85
            else self.config.keyword_confidence_threshold
        )
        self.semantic_threshold: float = (
            semantic_threshold
            if semantic_threshold != 0.85
            else self.config.semantic_confidence_threshold
        )
        self.taxonomy_path: Optional[str] = taxonomy_path
        self.enable_semantic: bool = enable_semantic
        self.enable_llm: bool = enable_llm

        # ── Layer instances ───────────────────────────────────────────
        self.keyword_router = self._init_keyword_router()

        # Semantic and LLM are lazily initialised
        self._semantic_matcher: Optional[Any] = None
        self._llm_classifier: Optional[Any] = None
        self._semantic_initialised: bool = False
        self._llm_initialised: bool = False
        self._llm_provider: str = llm_provider
        self._llm_api_key: Optional[str] = llm_api_key

        # ── Statistics ────────────────────────────────────────────────
        self._stats: Dict[str, int] = defaultdict(int)
        self._total_processing_time_ms: float = 0.0
        self._total_classified: int = 0

        logger.info(
            "ClassificationOrchestrator initialised: "
            "keyword_threshold=%.2f semantic_threshold=%.2f "
            "semantic=%s llm=%s",
            self.keyword_threshold,
            self.semantic_threshold,
            self.enable_semantic,
            self.enable_llm,
        )

    # ── Initialisation helpers ────────────────────────────────────────

    def _init_keyword_router(self) -> "KeywordRouter":
        """Create the KeywordRouter instance."""
        from classifier.keyword_router import KeywordRouter

        return KeywordRouter(
            taxonomy_path=self.taxonomy_path,
            threshold=self.keyword_threshold,
        )

    def _init_semantic_matcher(self) -> Optional["SemanticMatcher"]:
        """Lazily create the SemanticMatcher instance."""
        if self._semantic_initialised:
            return self._semantic_matcher

        if not self.enable_semantic:
            logger.info("Semantic matching is disabled")
            self._semantic_initialised = True
            return None

        try:
            from classifier.semantic_matcher import SemanticMatcher

            self._semantic_matcher = SemanticMatcher(
                model_name=self.config.semantic_model_name,
                taxonomy_path=self.taxonomy_path,
            )
            logger.info("SemanticMatcher initialised successfully")
        except Exception as exc:
            logger.warning(
                "Failed to initialise SemanticMatcher (semantic layer disabled): %s",
                exc,
            )
            self._semantic_matcher = None

        self._semantic_initialised = True
        return self._semantic_matcher

    def _init_llm_classifier(self) -> Optional["LLMClassifier"]:
        """Lazily create the LLMClassifier instance."""
        if self._llm_initialised:
            return self._llm_classifier

        if not self.enable_llm:
            logger.info("LLM classification is disabled")
            self._llm_initialised = True
            return None

        try:
            from classifier.llm_classifier import LLMClassifier

            self._llm_classifier = LLMClassifier(
                provider=self._llm_provider,
                api_key=self._llm_api_key,
                taxonomy_path=self.taxonomy_path,
            )
            logger.info("LLMClassifier initialised successfully")
        except Exception as exc:
            logger.warning(
                "Failed to initialise LLMClassifier (LLM layer disabled): %s",
                exc,
            )
            self._llm_classifier = None

        self._llm_initialised = True
        return self._llm_classifier

    # ── Single classification ─────────────────────────────────────────

    def classify(
        self,
        text: str,
        chunk_id: str = "unknown",
    ) -> ClassificationResult:
        """Run hierarchical classification on a single text.

        Execution order:
            1. **Keyword Router** — if confidence ≥ ``keyword_threshold``,
               return immediately.
            2. **Semantic Matcher** — if confidence ≥ ``semantic_threshold``,
               return.
            3. **LLM Classifier** — always returns a result (may have
               low confidence).

        Args:
            text: The text to classify.
            chunk_id: Identifier for the text chunk.

        Returns:
            A :class:`ClassificationResult` from whichever layer
            produced the first acceptable result.
        """
        start = time.perf_counter()

        # ── Layer 1: Keyword ─────────────────────────────────────────
        keyword_result = self.keyword_router.classify(text, chunk_id=chunk_id)
        if keyword_result is not None:
            self._stats["keyword"] += 1
            self._record_stats(start)
            return keyword_result

        # ── Layer 2: Semantic ────────────────────────────────────────
        matcher = self._init_semantic_matcher()
        if matcher is not None:
            try:
                semantic_result = matcher.classify(
                    text, chunk_id=chunk_id, threshold=self.semantic_threshold
                )
                if semantic_result is not None:
                    self._stats["semantic"] += 1
                    self._record_stats(start)
                    return semantic_result
            except Exception as exc:
                logger.warning(
                    "Semantic classification error for chunk %s: %s",
                    chunk_id,
                    exc,
                )

        # ── Layer 3: LLM ────────────────────────────────────────────
        classifier = self._init_llm_classifier()
        if classifier is not None:
            try:
                llm_result = classifier.classify(text, chunk_id=chunk_id)
                self._stats["llm"] += 1
                self._record_stats(start)
                return llm_result
            except Exception as exc:
                logger.error(
                    "LLM classification error for chunk %s: %s",
                    chunk_id,
                    exc,
                )

        # ── Fallback ──────────────────────────────────────────────────
        self._stats["fallback"] += 1
        self._record_stats(start)

        logger.warning("All classification layers failed for chunk %s", chunk_id)
        return ClassificationResult(
            chunk_id=chunk_id,
            category="unclassified",
            subcategory=None,
            confidence=0.0,
            method=ClassificationMethod.KEYWORD,  # best-effort marker
            alternatives=[],
            processing_time_ms=(time.perf_counter() - start) * 1000.0,
        )

    # ── Batch classification ──────────────────────────────────────────

    def classify_batch(
        self,
        texts: List[str],
        chunk_ids: Optional[List[str]] = None,
    ) -> List[ClassificationResult]:
        """Classify multiple texts efficiently.

        Optimisation strategy:
            1. Run **all** texts through the keyword router (very fast).
            2. Collect only the uncertain results.
            3. Run uncertain texts through semantic matcher (if enabled).
            4. Run remaining uncertain texts through LLM (if enabled).

        This avoids expensive semantic/LLM calls for the majority of
        texts that are keyword-classifiable.

        Args:
            texts: List of texts to classify.
            chunk_ids: Optional parallel list of chunk IDs.  When ``None``,
                auto-generated IDs of the form ``"batch-0"``, ``"batch-1"``,
                etc. are used.

        Returns:
            Parallel list of :class:`ClassificationResult` objects.
        """
        if not texts:
            return []

        # Generate chunk IDs if not provided
        if chunk_ids is None:
            chunk_ids = [f"batch-{i}" for i in range(len(texts))]
        elif len(chunk_ids) != len(texts):
            raise ValueError(
                f"chunk_ids length ({len(chunk_ids)}) must match "
                f"texts length ({len(texts)})"
            )

        n = len(texts)
        results: List[Optional[ClassificationResult]] = [None] * n
        uncertain_indices: List[int] = []

        # ── Layer 1: Keyword (batch) ──────────────────────────────────
        logger.info("Batch keyword classification: %d texts", n)
        for i, (text, cid) in enumerate(zip(texts, chunk_ids)):
            kw_result = self.keyword_router.classify(text, chunk_id=cid)
            if kw_result is not None:
                results[i] = kw_result
                self._stats["keyword"] += 1
            else:
                uncertain_indices.append(i)

        keyword_hit_rate = (n - len(uncertain_indices)) / n * 100
        logger.info(
            "Keyword layer: %d/%d classified (%.1f%%), %d uncertain",
            n - len(uncertain_indices),
            n,
            keyword_hit_rate,
            len(uncertain_indices),
        )

        if not uncertain_indices:
            self._total_classified += n
            return [r for r in results if r is not None]  # type: ignore[return-value]

        # ── Layer 2: Semantic (uncertain only) ─────────────────────────
        matcher = self._init_semantic_matcher()
        still_uncertain: List[int] = []

        if matcher is not None:
            logger.info("Semantic classification: %d uncertain texts", len(uncertain_indices))
            for idx in uncertain_indices:
                try:
                    sem_result = matcher.classify(
                        texts[idx],
                        chunk_id=chunk_ids[idx],
                        threshold=self.semantic_threshold,
                    )
                    if sem_result is not None:
                        results[idx] = sem_result
                        self._stats["semantic"] += 1
                    else:
                        still_uncertain.append(idx)
                except Exception as exc:
                    logger.warning(
                        "Semantic error for chunk %s: %s",
                        chunk_ids[idx],
                        exc,
                    )
                    still_uncertain.append(idx)

            semantic_hit_rate = (
                (len(uncertain_indices) - len(still_uncertain))
                / len(uncertain_indices) * 100
            ) if uncertain_indices else 100
            logger.info(
                "Semantic layer: classified %d/%d uncertain (%.1f%%), %d remaining",
                len(uncertain_indices) - len(still_uncertain),
                len(uncertain_indices),
                semantic_hit_rate,
                len(still_uncertain),
            )
        else:
            still_uncertain = list(uncertain_indices)

        if not still_uncertain:
            self._total_classified += n
            return [r for r in results if r is not None]  # type: ignore[return-value]

        # ── Layer 3: LLM (remaining uncertain) ──────────────────────
        classifier = self._init_llm_classifier()
        llm_uncertain: List[int] = []

        if classifier is not None:
            logger.info("LLM classification: %d remaining texts", len(still_uncertain))
            for idx in still_uncertain:
                try:
                    llm_result = classifier.classify(
                        texts[idx], chunk_id=chunk_ids[idx]
                    )
                    results[idx] = llm_result
                    self._stats["llm"] += 1
                except Exception as exc:
                    logger.error(
                        "LLM error for chunk %s: %s",
                        chunk_ids[idx],
                        exc,
                    )
                    llm_uncertain.append(idx)
        else:
            llm_uncertain = list(still_uncertain)

        # ── Fallback for truly unclassified ──────────────────────────
        for idx in llm_uncertain:
            self._stats["fallback"] += 1
            results[idx] = ClassificationResult(
                chunk_id=chunk_ids[idx],
                category="unclassified",
                subcategory=None,
                confidence=0.0,
                method=ClassificationMethod.KEYWORD,
                alternatives=[],
                processing_time_ms=0.0,
            )

        self._total_classified += n
        final = [r for r in results if r is not None]
        logger.info(
            "Batch classification complete: %d/%d classified successfully",
            n - len(llm_uncertain),
            n,
        )
        return final

    # ── Statistics ────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Get classification statistics per method.

        Returns:
            Dictionary with counts per method, percentages, and timing info.
        """
        total = max(sum(self._stats.values()), 1)

        return {
            "total_classified": self._total_classified,
            "by_method": {
                "keyword": {
                    "count": self._stats.get("keyword", 0),
                    "percentage": self._stats.get("keyword", 0) / total * 100,
                },
                "semantic": {
                    "count": self._stats.get("semantic", 0),
                    "percentage": self._stats.get("semantic", 0) / total * 100,
                },
                "llm": {
                    "count": self._stats.get("llm", 0),
                    "percentage": self._stats.get("llm", 0) / total * 100,
                },
                "fallback": {
                    "count": self._stats.get("fallback", 0),
                    "percentage": self._stats.get("fallback", 0) / total * 100,
                },
            },
            "avg_processing_time_ms": (
                self._total_processing_time_ms / self._total_classified
                if self._total_classified > 0
                else 0.0
            ),
            "keyword_threshold": self.keyword_threshold,
            "semantic_threshold": self.semantic_threshold,
            "semantic_enabled": self.enable_semantic,
            "llm_enabled": self.enable_llm,
        }

    def reset_stats(self) -> None:
        """Reset all classification statistics."""
        self._stats = defaultdict(int)
        self._total_processing_time_ms = 0.0
        self._total_classified = 0
        logger.info("Classification statistics reset")

    # ── Private helpers ──────────────────────────────────────────────

    def _record_stats(self, start_time: float) -> None:
        """Record timing statistics for a single classification."""
        elapsed = (time.perf_counter() - start_time) * 1000.0
        self._total_processing_time_ms += elapsed
        self._total_classified += 1
