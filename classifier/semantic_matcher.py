"""
AI Fuel Engine - Semantic Matcher Module

Semantic classification using vector similarity — Layer 2 of the
hierarchical classifier.  Encodes input text with a multilingual
sentence-transformer model and compares it against a reference index
of category embeddings stored in Qdrant (preferred) or a local
FAISS-based in-memory index.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Lazy-import guards ─────────────────────────────────────────────────
_sentence_transformers_available = False
try:
    import numpy as np
    _sentence_transformers_available = True
except ImportError:
    np = None  # type: ignore[assignment]

try:
    from sentence_transformers import SentenceTransformer
    _sentence_transformers_available = True
except ImportError:
    SentenceTransformer = None  # type: ignore[assignment,misc]


class SemanticMatcher:
    """Semantic classification using vector similarity — Layer 2.

    Encodes input text using a multilingual sentence-transformer model
    and searches a reference embedding index for the closest matching
    category.  Supports both **Qdrant** (cloud/self-hosted) and a
    **local FAISS-like** index as the vector backend.

    The local index is built lazily on first use from the taxonomy so
    that the matcher can be instantiated quickly without heavy model
    downloads.

    Args:
        model_name: Name of the ``sentence-transformers`` model to load.
            Defaults to ``paraphrase-multilingual-mpnet-base-v2`` which
            supports 50+ languages including Arabic.
        qdrant_url: URL of a running Qdrant instance.  When ``None``,
            a local in-memory index is used instead.
        collection_name: Qdrant collection name (only used when
            ``qdrant_url`` is provided).
        taxonomy_path: Path to the medical taxonomy JSON.  When ``None``,
            the built-in path inside the classifier package is used.
    """

    _DEFAULT_MODEL = "paraphrase-multilingual-mpnet-base-v2"
    _DEFAULT_TAXONOMY_PATH = os.path.join(
        os.path.dirname(__file__), "medical_taxonomy.json"
    )

    def __init__(
        self,
        model_name: Optional[str] = None,
        qdrant_url: Optional[str] = None,
        collection_name: Optional[str] = None,
        taxonomy_path: Optional[str] = None,
    ) -> None:
        self.model_name: str = model_name or self._DEFAULT_MODEL
        self.qdrant_url: Optional[str] = qdrant_url
        self.collection_name: str = collection_name or "ai_fuel_categories"
        self.taxonomy_path: str = taxonomy_path or self._DEFAULT_TAXONOMY_PATH

        # ── Lazy-loaded state ──────────────────────────────────────────
        self._model: Any = None
        self._qdrant_client: Any = None
        self._local_index: Optional[_LocalVectorIndex] = None
        self._index_built: bool = False

        # Track whether optional dependencies are available
        self._available = _sentence_transformers_available

    # ── Lazy initialisation ────────────────────────────────────────────

    def _ensure_model(self) -> None:
        """Load the sentence-transformer model on first use."""
        if self._model is not None:
            return

        if not _sentence_transformers_available:
            raise RuntimeError(
                "sentence-transformers is required for SemanticMatcher. "
                "Install it with: pip install sentence-transformers"
            )

        logger.info("Loading sentence-transformer model: %s", self.model_name)
        self._model = SentenceTransformer(self.model_name)
        logger.info("Model loaded successfully")

    def _ensure_index(self) -> None:
        """Build the reference embedding index on first use."""
        if self._index_built:
            return

        self._ensure_model()
        taxonomy = self._load_taxonomy()

        if self.qdrant_url is not None:
            self._build_qdrant_index(taxonomy)
        else:
            self._build_local_index(taxonomy)

        self._index_built = True
        logger.info("Reference index built with %d categories", len(taxonomy))

    # ── Taxonomy loading ──────────────────────────────────────────────

    def _load_taxonomy(self) -> List[Dict]:
        """Load categories from the taxonomy JSON file."""
        path = self.taxonomy_path
        if not os.path.exists(path):
            logger.warning("Taxonomy file not found at %s — using empty taxonomy", path)
            return []

        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("categories", [])

    # ── Index builders ────────────────────────────────────────────────

    def _build_reference_descriptions(
        self, taxonomy: List[Dict]
    ) -> List[Tuple[str, str, str]]:
        """Build rich text descriptions for each category.

        Combines the English and Arabic name, description, and keywords
        into a single string per category for embedding.

        Returns:
            List of ``(category_id, category_name, description_text)``.
        """
        descriptions: List[Tuple[str, str, str]] = []
        for cat in taxonomy:
            cat_id = cat["id"]
            name_en = cat.get("name_en", cat_id)
            name_ar = cat.get("name_ar", "")
            desc_en = cat.get("description_en", "")
            desc_ar = cat.get("description_ar", "")
            kw_en = " ".join(cat.get("keywords_en", [])[:10])
            kw_ar = " ".join(cat.get("keywords_ar", [])[:10])

            # Combine all information for a rich embedding
            combined = f"{name_en}. {desc_en}. Keywords: {kw_en}"
            if name_ar:
                combined += f" | {name_ar}. {desc_ar}. الكلمات المفتاحية: {kw_ar}"

            descriptions.append((cat_id, name_en, combined))

        return descriptions

    def _build_local_index(self, taxonomy: List[Dict]) -> None:
        """Build a local in-memory vector index from taxonomy."""
        descriptions = self._build_reference_descriptions(taxonomy)
        if not descriptions:
            logger.warning("No taxonomy categories to index")
            return

        # Encode all descriptions
        cat_ids = [d[0] for d in descriptions]
        cat_names = [d[1] for d in descriptions]
        texts = [d[2] for d in descriptions]

        embeddings = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)

        self._local_index = _LocalVectorIndex(
            category_ids=cat_ids,
            category_names=cat_names,
            embeddings=embeddings,
        )
        logger.info(
            "Local vector index built with %d categories (dim=%d)",
            len(cat_ids),
            embeddings.shape[1] if hasattr(embeddings, "shape") else 0,
        )

    def _build_qdrant_index(self, taxonomy: List[Dict]) -> None:
        """Build a Qdrant collection with category reference embeddings."""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams, PointStruct
        except ImportError:
            raise RuntimeError(
                "qdrant-client is required for Qdrant backend. "
                "Install it with: pip install qdrant-client"
            )

        descriptions = self._build_reference_descriptions(taxonomy)
        if not descriptions:
            logger.warning("No taxonomy categories to index in Qdrant")
            return

        self._qdrant_client = QdrantClient(url=self.qdrant_url)

        # Recreate collection
        self._qdrant_client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self._model.get_sentence_embedding_dimension(),
                distance=Distance.COSINE,
            ),
        )

        # Encode and upload
        texts = [d[2] for d in descriptions]
        embeddings = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)

        points = [
            PointStruct(
                id=idx,
                vector=emb.tolist(),
                payload={
                    "category_id": d[0],
                    "category_name": d[1],
                    "description": d[2],
                },
            )
            for idx, (d, emb) in enumerate(zip(descriptions, embeddings))
        ]

        self._qdrant_client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        logger.info(
            "Qdrant collection '%s' created with %d vectors",
            self.collection_name,
            len(points),
        )

    # ── Classification ───────────────────────────────────────────────

    def classify(
        self,
        text: str,
        chunk_id: str = "unknown",
        threshold: float = 0.85,
    ) -> Optional["ClassificationResult"]:
        """Classify text using semantic similarity.

        Args:
            text: The text to classify.
            chunk_id: Identifier for the text chunk.
            threshold: Minimum similarity score to accept a match.

        Returns:
            A :class:`ClassificationResult` if the best match exceeds
            ``threshold``, otherwise ``None``.
        """
        if not self._available:
            logger.warning(
                "SemanticMatcher dependencies not available — skipping classification"
            )
            return None

        start = time.perf_counter()
        self._ensure_index()

        if self._model is None:
            return None

        # Encode input text
        query_embedding = self._model.encode(
            [text], convert_to_numpy=True, normalize_embeddings=True
        )[0]

        # Search the appropriate index
        if self.qdrant_url is not None and self._qdrant_client is not None:
            top_results = self._search_qdrant(query_embedding, top_k=5)
        elif self._local_index is not None:
            top_results = self._local_index.search(query_embedding, top_k=5)
        else:
            return None

        if not top_results:
            return None

        best_cat_id, best_name, best_score = top_results[0]
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        if best_score < threshold:
            logger.debug(
                "Semantic score %.3f < threshold %.3f for chunk %s",
                best_score,
                threshold,
                chunk_id,
            )
            return None

        from core.schemas import ClassificationMethod, ClassificationResult

        alternatives = [
            {"category": cat_id, "confidence": score}
            for cat_id, name, score in top_results[1:]
        ]

        result = ClassificationResult(
            chunk_id=chunk_id,
            category=best_cat_id,
            subcategory=best_name,
            confidence=round(best_score, 4),
            method=ClassificationMethod.SEMANTIC,
            alternatives=alternatives,
            processing_time_ms=round(elapsed_ms, 2),
        )

        logger.info(
            "Semantic classification: chunk=%s category=%s confidence=%.3f (%.1fms)",
            chunk_id,
            best_cat_id,
            best_score,
            elapsed_ms,
        )
        return result

    # ── Search helpers ───────────────────────────────────────────────

    def _search_qdrant(
        self, query: Any, top_k: int = 5
    ) -> List[Tuple[str, str, float]]:
        """Search Qdrant for the closest category."""
        hits = self._qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query.tolist(),
            limit=top_k,
        )
        return [
            (
                hit.payload["category_id"],
                hit.payload["category_name"],
                hit.score,
            )
            for hit in hits
        ]

    # ── Training / augmentation ───────────────────────────────────────

    def add_training_examples(
        self, texts: List[str], categories: List[str]
    ) -> None:
        """Add training examples to the reference index for better matching.

        This re-encodes the provided texts with their known categories and
        appends them to the local index (or updates Qdrant).

        Args:
            texts: List of example texts.
            categories: Parallel list of category IDs (same length as *texts*).

        Raises:
            ValueError: If *texts* and *categories* have different lengths.
        """
        if len(texts) != len(categories):
            raise ValueError(
                f"texts ({len(texts)}) and categories ({len(categories)}) must have same length"
            )

        self._ensure_index()

        embeddings = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)

        if self._local_index is not None:
            for text, cat_id, emb in zip(texts, categories, embeddings):
                self._local_index.add_embedding(cat_id, cat_id, emb)
            logger.info("Added %d training examples to local index", len(texts))
        elif self._qdrant_client is not None:
            from qdrant_client.models import PointStruct

            # Find current max ID in Qdrant
            points = self._qdrant_client.scroll(
                collection_name=self.collection_name, limit=1
            )
            offset = points[0][0] if points[0] else 0

            new_points = []
            for i, (text, cat_id, emb) in enumerate(zip(texts, categories, embeddings)):
                # Re-encode full text for richer embedding
                combined = text
                new_points.append(
                    PointStruct(
                        id=offset + i + 1,
                        vector=emb.tolist(),
                        payload={
                            "category_id": cat_id,
                            "category_name": cat_id,
                            "description": combined,
                            "is_training_example": True,
                        },
                    )
                )
            self._qdrant_client.upsert(
                collection_name=self.collection_name,
                points=new_points,
            )
            logger.info("Added %d training examples to Qdrant", len(texts))


class _LocalVectorIndex:
    """Minimal in-memory vector index for category embeddings.

    Stores embeddings as a NumPy array and uses cosine similarity
    for nearest-neighbour search.  Designed for small-to-medium
    reference sets (dozens to low hundreds of entries).

    Args:
        category_ids: Ordered list of category IDs matching embeddings.
        category_names: Ordered list of category display names.
        embeddings: 2-D NumPy array of shape ``(n, dim)``.
    """

    def __init__(
        self,
        category_ids: List[str],
        category_names: List[str],
        embeddings: Any,
    ) -> None:
        self.category_ids: List[str] = list(category_ids)
        self.category_names: List[str] = list(category_names)

        if np is not None:
            self.embeddings = np.array(embeddings, dtype=np.float32)
        else:
            self.embeddings = embeddings
            raise RuntimeError("NumPy is required for the local vector index")

        # Pre-compute norms for cosine similarity
        self._norms: Any = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        self._norms = np.maximum(self._norms, 1e-10)  # avoid division by zero
        self._normalized: Any = self.embeddings / self._norms

    def search(
        self, query: Any, top_k: int = 5
    ) -> List[Tuple[str, str, float]]:
        """Find the top-k closest categories by cosine similarity.

        Args:
            query: 1-D embedding vector.
            top_k: Number of results to return.

        Returns:
            List of ``(category_id, category_name, cosine_similarity)``.
        """
        query = np.asarray(query, dtype=np.float32)
        query_norm = np.linalg.norm(query)
        if query_norm < 1e-10:
            return []
        query_normalized = query / query_norm

        # Compute cosine similarities
        scores = self._normalized @ query_normalized

        # Get top-k indices
        top_indices = np.argsort(scores)[-top_k:][::-1]

        results: List[Tuple[str, str, float]] = []
        for idx in top_indices:
            score = float(scores[idx])
            if score > 0:  # only return positive similarities
                results.append((
                    self.category_ids[idx],
                    self.category_names[idx],
                    score,
                ))

        return results

    def add_embedding(
        self, cat_id: str, cat_name: str, embedding: Any
    ) -> None:
        """Add a new embedding to the index.

        Args:
            cat_id: Category ID.
            cat_name: Category display name.
            embedding: 1-D embedding vector.
        """
        emb = np.asarray(embedding, dtype=np.float32).reshape(1, -1)
        self.embeddings = np.vstack([self.embeddings, emb])
        norm = np.linalg.norm(emb)
        self._norms = np.vstack([self._norms, np.maximum(norm, 1e-10)])
        self._normalized = np.vstack([
            self._normalized,
            emb / max(norm, 1e-10),
        ])
        self.category_ids.append(cat_id)
        self.category_names.append(cat_name)
