"""Result fusion and analysis endpoints for OmniMedicalSuite.

Provides endpoints for semantic deduplication, OCR result merging,
knowledge graph extraction, text similarity computation, and full
document analysis combining all components.

Endpoints
---------
POST /fusion/deduplicate    Semantic deduplication of text chunks
POST /fusion/merge          Merge results from multiple OCR runs
POST /fusion/knowledge-graph Extract knowledge graph from text
GET  /fusion/similarity     Calculate similarity between two texts
POST /fusion/analyze        Full document analysis pipeline
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import tempfile
import time
from collections import Counter
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

__all__ = ["router"]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fusion", tags=["fusion"])


# ===================================================================
# Pydantic models – requests
# ===================================================================

class DeduplicateRequest(BaseModel):
    """Request body for semantic deduplication."""

    chunks: list[str] = Field(
        ...,
        description="List of text chunks to deduplicate.",
        min_length=1,
    )
    similarity_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity for clustering.",
    )


class OCRResultItem(BaseModel):
    """A single OCR engine result for merging."""

    engine_name: str
    text: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class MergeRequest(BaseModel):
    """Request body for merging multiple OCR results."""

    results: list[OCRResultItem] = Field(
        ...,
        description="List of OCR results to merge.",
        min_length=1,
    )
    fusion_method: str = Field(
        default="weighted_vote",
        description="Fusion strategy (weighted_vote, character_level, best_confidence, smart_fallback).",
    )


class KnowledgeGraphRequest(BaseModel):
    """Request body for knowledge graph extraction."""

    text: str = Field(
        ...,
        description="Text to extract entities and relations from.",
        min_length=1,
    )
    language: str = Field(
        default="eng+ara",
        description="Language hint for entity pattern selection.",
    )


class SimilarityQuery(BaseModel):
    """Query parameters for text similarity (used as query params)."""

    text_a: str = Field(..., description="First text passage.")
    text_b: str = Field(..., description="Second text passage.")


class AnalyzeRequest(BaseModel):
    """Request body for full document analysis."""

    text: str | None = Field(
        default=None,
        description="Raw text to analyse. If None, a file must be uploaded.",
    )
    language: str = Field(
        default="eng+ara",
        description="Language hint for OCR processing.",
    )
    include_summary: bool = Field(
        default=True,
        description="Whether to include an LLM-generated summary.",
    )


# ===================================================================
# Pydantic models – responses
# ===================================================================

class ClusterMember(BaseModel):
    """A single chunk within a deduplication cluster."""

    index: int
    text: str


class DeduplicateCluster(BaseModel):
    """A semantic cluster from deduplication."""

    cluster_id: str
    members: list[ClusterMember]
    representative_text: str
    similarity_score: float = 0.0


class DeduplicateResponse(BaseModel):
    """Response from semantic deduplication."""

    clusters: list[DeduplicateCluster]
    total_chunks: int = 0
    unique_chunks: int = 0
    deduplication_ratio: float = 0.0


class MergeResponse(BaseModel):
    """Response from merging OCR results."""

    final_text: str
    fusion_method: str
    source_engines: list[str] = Field(default_factory=list)
    confidence_scores: dict[str, float] = Field(default_factory=dict)
    word_count: int = 0


class EntityResponse(BaseModel):
    """A single medical entity."""

    entity_type: str
    text: str
    confidence: float = 1.0
    position: tuple[int, int] = (0, 0)


class RelationResponse(BaseModel):
    """A single relation between entities."""

    subject: str
    predicate: str
    object: str
    confidence: float = 0.8


class KnowledgeGraphResponse(BaseModel):
    """Extracted knowledge graph."""

    entities: list[EntityResponse]
    relations: list[RelationResponse]
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimilarityResponse(BaseModel):
    """Similarity score between two texts."""

    text_a: str
    text_b: str
    similarity_score: float = 0.0
    method: str = "cosine"


class AnalyzeResponse(BaseModel):
    """Full document analysis result."""

    text: str = ""
    word_count: int = 0
    deduplication: DeduplicateResponse | None = None
    knowledge_graph: KnowledgeGraphResponse | None = None
    summary: str | None = None
    processing_time_ms: float = 0.0


# ===================================================================
# Helper: get deduplication engine
# ===================================================================

async def _get_dedup_engine(threshold: float = 0.85):
    """Return an initialised SemanticDeduplicationEngine."""
    from ...vision.ocr_fusion_system import SemanticDeduplicationEngine

    engine = SemanticDeduplicationEngine(similarity_threshold=threshold)
    await engine.initialize()
    return engine


# ===================================================================
# Helper: cosine similarity (numpy-free fallback)
# ===================================================================

def _cosine_similarity(text_a: str, text_b: str) -> float:
    """Compute a basic cosine similarity between two texts using word frequency vectors.

    Falls back to a Jaccard-like metric when texts are very short.
    """
    words_a = Counter(text_a.lower().split())
    words_b = Counter(text_b.lower().split())
    all_words = set(words_a) | set(words_b)

    if not all_words:
        return 1.0

    dot_product = sum(words_a[w] * words_b[w] for w in all_words)
    norm_a = math.sqrt(sum(v ** 2 for v in words_a.values()))
    norm_b = math.sqrt(sum(v ** 2 for v in words_b.values()))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


# ===================================================================
# Helper: merge OCR results using fusion engine
# ===================================================================

def _merge_results(
    items: list[OCRResultItem],
    method: str,
) -> tuple[str, dict[str, float], list[str]]:
    """Merge a list of OCR results using a specified fusion strategy.

    Returns (merged_text, confidence_scores, source_engine_names).
    """
    if not items:
        return "", {}, []

    source_engines = [r.engine_name for r in items]
    confidence_scores = {r.engine_name: r.confidence for r in items}

    if len(items) == 1:
        return items[0].text, confidence_scores, source_engines

    if method == "best_confidence":
        best = max(items, key=lambda r: r.confidence)
        return best.text, confidence_scores, source_engines

    if method == "character_level":
        texts = [r.text for r in items]
        weights = [r.confidence ** 1.5 for r in items]
        max_len = max(len(t) for t in texts) if texts else 0
        padded = [t.ljust(max_len, "\x00") for t in texts]

        from collections import defaultdict
        result_chars: list[str] = []
        for i in range(max_len):
            char_count: dict[str, float] = defaultdict(float)
            for t, w in zip(padded, weights):
                ch = t[i]
                char_count[ch] += w
            best_char = max(char_count, key=char_count.get)
            if best_char != "\x00":
                result_chars.append(best_char)
        return "".join(result_chars), confidence_scores, source_engines

    if method == "smart_fallback":
        sorted_items = sorted(items, key=lambda r: r.confidence, reverse=True)
        if len(sorted_items) > 1 and (sorted_items[0].confidence - sorted_items[1].confidence) >= 0.15:
            return sorted_items[0].text, confidence_scores, source_engines

    # Default: weighted_vote
    word_weights: dict[str, tuple[str, float]] = {}
    for item in items:
        weight = item.confidence ** 1.5
        for word in item.text.split():
            norm = word.lower().strip(".,;:!?()-\"'")
            if not norm:
                continue
            if norm not in word_weights or weight > word_weights[norm][1]:
                word_weights[norm] = (word, weight)

    merged = " ".join(w[0] for w in word_weights.values())
    return merged, confidence_scores, source_engines


# ===================================================================
# Endpoints
# ===================================================================

@router.post("/deduplicate", response_model=DeduplicateResponse, summary="Semantic deduplication of text chunks")
async def deduplicate_chunks(body: DeduplicateRequest) -> DeduplicateResponse:
    """Run semantic deduplication on a list of text chunks.

    Uses embedding-based similarity to cluster duplicate or near-duplicate
    chunks, returning representative texts for each cluster.

    Raises
    ------
    500
        If the deduplication engine fails to initialise.
    """
    from ...vision.ocr_fusion_system import SemanticDeduplicationEngine, DocumentChunk

    try:
        engine = await _get_dedup_engine(body.similarity_threshold)
    except Exception as exc:
        logger.error("Dedup engine init failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialise deduplication engine: {exc}",
        ) from exc

    # Convert plain strings to DocumentChunk objects
    chunks = [
        DocumentChunk(text=text, chunk_index=idx)
        for idx, text in enumerate(body.chunks)
    ]

    t0 = time.perf_counter()
    try:
        clusters = await engine.deduplicate(chunks)
    except Exception as exc:
        logger.error("Deduplication failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Deduplication failed: {exc}",
        ) from exc
    elapsed = (time.perf_counter() - t0) * 1000

    response_clusters: list[DeduplicateCluster] = []
    for cluster in clusters:
        members = [
            ClusterMember(
                index=c.chunk_index,
                text=c.text,
            )
            for c in cluster.chunks
        ]
        response_clusters.append(
            DeduplicateCluster(
                cluster_id=cluster.cluster_id,
                members=members,
                representative_text=cluster.representative_text,
                similarity_score=cluster.similarity_score,
            )
        )

    total = len(body.chunks)
    unique = len(response_clusters)
    ratio = round((1.0 - unique / total) * 100, 1) if total > 0 else 0.0

    return DeduplicateResponse(
        clusters=response_clusters,
        total_chunks=total,
        unique_chunks=unique,
        deduplication_ratio=ratio,
    )


@router.post("/merge", response_model=MergeResponse, summary="Merge results from multiple OCR runs")
async def merge_ocr_results(body: MergeRequest) -> MergeResponse:
    """Merge text outputs from multiple OCR engines using a fusion strategy.

    Supports weighted_vote, character_level, best_confidence, and
    smart_fallback fusion methods.

    Raises
    ------
    400
        If the fusion method is invalid.
    """
    valid_methods = {"weighted_vote", "character_level", "best_confidence", "smart_fallback"}
    if body.fusion_method not in valid_methods:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid fusion method '{body.fusion_method}'. Valid: {sorted(valid_methods)}",
        )

    merged_text, confidence_scores, source_engines = _merge_results(
        body.results,
        body.fusion_method,
    )

    return MergeResponse(
        final_text=merged_text,
        fusion_method=body.fusion_method,
        source_engines=source_engines,
        confidence_scores=confidence_scores,
        word_count=len(merged_text.split()),
    )


@router.post("/knowledge-graph", response_model=KnowledgeGraphResponse, summary="Extract knowledge graph from text")
async def extract_knowledge_graph(body: KnowledgeGraphRequest) -> KnowledgeGraphResponse:
    """Extract medical entities and relations from text.

    Identifies diagnoses, medications, procedures, anatomy, dates, and
    lab values using regex-based pattern matching for both English and Arabic.

    Raises
    ------
    500
        If knowledge graph extraction fails.
    """
    from ...vision.ocr_fusion_system import MedicalKnowledgeGraph

    try:
        kg_engine = MedicalKnowledgeGraph()
        kg = await kg_engine.build(body.text)
    except Exception as exc:
        logger.error("Knowledge graph extraction failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Knowledge graph extraction failed: {exc}",
        ) from exc

    entities = [
        EntityResponse(
            entity_type=e.entity_type.value,
            text=e.text,
            confidence=e.confidence,
            position=e.position,
        )
        for e in kg.entities
    ]
    relations = [
        RelationResponse(
            subject=r.subject,
            predicate=r.predicate,
            object=r.object,
            confidence=r.confidence,
        )
        for r in kg.relations
    ]

    return KnowledgeGraphResponse(
        entities=entities,
        relations=relations,
        metadata=kg.metadata,
    )


@router.get("/similarity", response_model=SimilarityResponse, summary="Calculate similarity between two texts")
async def calculate_similarity(
    text_a: str,
    text_b: str,
) -> SimilarityResponse:
    """Compute cosine similarity between two text passages.

    Uses word-frequency-based cosine similarity. Returns a score between
    0.0 (completely dissimilar) and 1.0 (identical).
    """
    score = _cosine_similarity(text_a, text_b)

    return SimilarityResponse(
        text_a=text_a,
        text_b=text_b,
        similarity_score=round(score, 4),
        method="cosine",
    )


@router.post("/analyze", response_model=AnalyzeResponse, summary="Full document analysis pipeline")
async def analyze_document(
    body: AnalyzeRequest | None = None,
    file: UploadFile | None = File(default=None),
) -> AnalyzeResponse:
    """Run a full analysis pipeline on text or an uploaded file.

    The pipeline includes:
    1. OCR extraction (if a file is provided)
    2. Semantic deduplication of chunks
    3. Knowledge graph extraction
    4. Optional LLM summary generation

    Provide either ``text`` in the request body or upload a ``file``.

    Raises
    ------
    400
        If neither text nor file is provided.
    500
        If analysis processing fails.
    """
    if body is None:
        body = AnalyzeRequest()

    # Obtain text from file or request body
    extracted_text = body.text or ""

    if file and not extracted_text:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        suffix = os.path.splitext(file.filename or ".png")[1] or ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            from ...core.config import get_settings
            from ...vision.ocr_fusion_system import OCRFusionEngine

            settings = get_settings()
            engine = OCRFusionEngine(settings)
            engine.discover_and_register_all()
            result = await engine.process(tmp_path, lang=body.language)
            extracted_text = result.final_text
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"OCR processing failed: {exc}",
            ) from exc
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    if not extracted_text.strip():
        raise HTTPException(
            status_code=400,
            detail="No text available for analysis. Provide text or a valid document file.",
        )

    t_start = time.perf_counter()
    word_count = len(extracted_text.split())

    # Step 1: Semantic deduplication
    dedup_response: DeduplicateResponse | None = None
    try:
        dedup_body = DeduplicateRequest(chunks=[extracted_text])
        dedup_response = await deduplicate_chunks(dedup_body)
    except Exception as exc:
        logger.warning("Deduplication step failed during analysis: %s", exc)

    # Step 2: Knowledge graph extraction
    kg_response: KnowledgeGraphResponse | None = None
    try:
        kg_body = KnowledgeGraphRequest(text=extracted_text, language=body.language)
        kg_response = await extract_knowledge_graph(kg_body)
    except Exception as exc:
        logger.warning("Knowledge graph step failed during analysis: %s", exc)

    # Step 3: LLM summary (optional)
    summary: str | None = None
    if body.include_summary:
        try:
            from ...ai.llm_router import LLMRouter
            from ...core.config import get_settings

            settings = get_settings()
            llm = LLMRouter(settings)
            summary = await llm.route_with_fallback(
                extracted_text[:4000],
                "summarize",
            )
        except Exception as exc:
            logger.warning("LLM summary failed: %s", exc)

    total_ms = (time.perf_counter() - t_start) * 1000

    return AnalyzeResponse(
        text=extracted_text,
        word_count=word_count,
        deduplication=dedup_response,
        knowledge_graph=kg_response,
        summary=summary,
        processing_time_ms=round(total_ms, 2),
    )
