"""
AI Fuel Engine - RAG Exporter

Exports classified chunks in RAG-ready format with optional pre-computed
embeddings.  Produces a directory containing:

- ``texts.jsonl`` – one JSON record per chunk (text + metadata).
- ``embeddings.npy`` – numpy array of dense embeddings (optional).
- ``metadata.json`` – dataset-level metadata (counts, dimensions, etc.).

Also supports direct preparation of Qdrant-compatible batch payloads.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.schemas import ClassifiedChunk

logger = logging.getLogger(__name__)

# Lazy-load detection
_np_available = False
_sentence_transformers_available = False

try:
    import numpy as _np  # type: ignore[import-untyped]

    _np_available = True
except ImportError:  # pragma: no cover
    _np = None  # type: ignore[assignment]

try:
    from sentence_transformers import SentenceTransformer as _ST  # type: ignore[import-untyped]

    _sentence_transformers_available = True
except ImportError:  # pragma: no cover
    _ST = None  # type: ignore[assignment]


class RAGExporter:
    """Export in RAG-ready format with embeddings.

    Generates a self-contained corpus directory that can be directly
    consumed by vector databases, embedding search engines, or custom
    RAG pipelines.

    Args:
        model_name: Name of the sentence-transformers model used to
            produce embeddings.  Set to ``None`` to disable embedding
            generation (text-only export).
    """

    def __init__(self, model_name: Optional[str] = None) -> None:
        """Initialise the RAG exporter.

        Args:
            model_name: Optional model name for embedding generation.
                Defaults to ``None`` (embeddings disabled).
        """
        self.model_name = model_name
        self.model = None
        self._model_loaded = False
        self._exports_completed = int = 0

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _ensure_model(self) -> bool:
        """Lazily load the embedding model.

        Returns:
            ``True`` if a model is available, ``False`` otherwise.
        """
        if self._model_loaded:
            return self.model is not None

        self._model_loaded = True

        if self.model_name is None:
            logger.info("No model name specified; embeddings will be skipped.")
            return False

        if not _sentence_transformers_available:
            logger.warning(
                "sentence-transformers not installed; embeddings disabled. "
                "Install with: pip install sentence-transformers"
            )
            return False

        if not _np_available:
            logger.warning(
                "numpy not installed; embeddings disabled. "
                "Install with: pip install numpy"
            )
            return False

        try:
            logger.info("Loading embedding model: %s", self.model_name)
            self.model = _ST(self.model_name)
            logger.info("Embedding model loaded.")
            return True

        except Exception as exc:  # pragma: no cover
            logger.error("Failed to load model '%s': %s", self.model_name, exc)
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export(
        self,
        chunks: List[ClassifiedChunk],
        output_dir: str,
        include_embeddings: bool = True,
    ) -> Dict[str, Any]:
        """Export RAG-ready dataset to a directory.

        Produces:
        - ``texts.jsonl`` – text + metadata per chunk.
        - ``embeddings.npy`` – numpy array of embeddings (if enabled).
        - ``metadata.json`` – dataset-level information.

        Args:
            chunks: List of :class:`ClassifiedChunk` objects.
            output_dir: Directory path for the output files.
            include_embeddings: Whether to compute and save embeddings.
                Requires a model name to be set.

        Returns:
            Dictionary with ``output_dir``, ``chunk_count``,
            ``embedding_dim`` (if computed), and file paths.

        Raises:
            ValueError: If *chunks* is empty.
        """
        if not chunks:
            raise ValueError("No chunks to export.")

        output_dir = os.path.abspath(output_dir)
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # ── Export texts.jsonl ──────────────────────────────────────
        texts_path = os.path.join(output_dir, "texts.jsonl")
        records: List[Dict[str, Any]] = []

        with open(texts_path, "w", encoding="utf-8") as fh:
            for classified in chunks:
                record = {
                    "chunk_id": classified.chunk.id,
                    "text": classified.chunk.text,
                    "category": classified.classification.category,
                    "subcategory": classified.classification.subcategory or "",
                    "confidence": classified.classification.confidence,
                    "source_file": classified.chunk.source_file or "",
                    "language": classified.chunk.language.value,
                }
                records.append(record)
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")

        logger.info("Exported %d texts to %s", len(records), texts_path)

        # ── Export embeddings.npy (optional) ─────────────────────────
        embeddings_path = None
        embedding_dim = 0

        if include_embeddings and self._ensure_model():
            embeddings = self._compute_embeddings(chunks)

            if embeddings is not None and _np is not None:
                embeddings_path = os.path.join(output_dir, "embeddings.npy")
                _np.save(embeddings_path, embeddings)  # type: ignore[union-attr]
                embedding_dim = embeddings.shape[1]
                logger.info(
                    "Saved %d embeddings (%d-dim) to %s",
                    len(embeddings),
                    embedding_dim,
                    embeddings_path,
                )

        # ── Export metadata.json ──────────────────────────────────────
        metadata_path = os.path.join(output_dir, "metadata.json")
        metadata = {
            "chunk_count": len(chunks),
            "embedding_dim": embedding_dim,
            "model_name": self.model_name,
            "created_at": time.time(),
            "files": {
                "texts": "texts.jsonl",
                "embeddings": "embeddings.npy" if embeddings_path else None,
                "metadata": "metadata.json",
            },
            "category_distribution": self._compute_category_dist(chunks),
        }

        with open(metadata_path, "w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2, ensure_ascii=False)

        self._exports_completed += 1

        return {
            "output_dir": output_dir,
            "chunk_count": len(chunks),
            "embedding_dim": embedding_dim,
            "files": {
                "texts": texts_path,
                "embeddings": embeddings_path,
                "metadata": metadata_path,
            },
        }

    def export_for_qdrant(
        self,
        chunks: List[ClassifiedChunk],
        collection_name: str = "ai_fuel_corpus",
        batch_size: int = 100,
    ) -> Dict[str, Any]:
        """Prepare data for direct upload to Qdrant.

        Generates Qdrant-compatible point payloads (id, vector, payload)
        that can be batch-uploaded using the Qdrant client.

        Args:
            chunks: List of :class:`ClassifiedChunk` objects.
            collection_name: Target Qdrant collection name.
            batch_size: Number of points per batch.

        Returns:
            Dictionary with:
            - ``collection_name`` – the collection name.
            - ``total_points`` – total number of points generated.
            - ``batches`` – list of batch payloads.
            - ``embedding_dim`` – dimension of embedding vectors.
        """
        if not chunks:
            return {
                "collection_name": collection_name,
                "total_points": 0,
                "batches": [],
                "embedding_dim": 0,
            }

        if not self._ensure_model():
            logger.warning(
                "No embedding model available; generating text-only Qdrant payloads."
            )
            embeddings = None
            embedding_dim = 0
        else:
            embeddings = self._compute_embeddings(chunks)
            embedding_dim = embeddings.shape[1] if embeddings is not None else 0  # type: ignore[union-attr]

        batches: List[List[Dict[str, Any]]] = []
        current_batch: List[Dict[str, Any]] = []

        for idx, classified in enumerate(chunks):
            point: Dict[str, Any] = {
                "id": classified.chunk.id,
                "payload": {
                    "text": classified.chunk.text,
                    "category": classified.classification.category,
                    "subcategory": classified.classification.subcategory or "",
                    "confidence": classified.classification.confidence,
                    "source_file": classified.chunk.source_file or "",
                    "language": classified.chunk.language.value,
                },
            }

            if embeddings is not None:
                point["vector"] = embeddings[idx].tolist()  # type: ignore[index,union-attr]

            current_batch.append(point)

            if len(current_batch) >= batch_size:
                batches.append(current_batch)
                current_batch = []

        if current_batch:
            batches.append(current_batch)

        result = {
            "collection_name": collection_name,
            "total_points": len(chunks),
            "batches": batches,
            "embedding_dim": embedding_dim,
        }

        logger.info(
            "Prepared %d Qdrant points in %d batches (collection=%s).",
            len(chunks),
            len(batches),
            collection_name,
        )
        return result

    def get_stats(self) -> Dict:
        """Return exporter statistics.

        Returns:
            Dictionary with ``exports_completed`` and model info.
        """
        return {
            "exports_completed": self._exports_completed,
            "model_name": self.model_name,
            "model_loaded": self.model is not None,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_embeddings(
        self, chunks: List[ClassifiedChunk]
    ) -> Optional[Any]:
        """Compute dense embeddings for all chunk texts.

        Returns:
            A numpy array of shape ``(N, dim)`` or ``None`` on failure.
        """
        if self.model is None or _np is None:
            return None

        try:
            texts = [c.chunk.text for c in chunks]
            logger.info(
                "Computing embeddings for %d texts...", len(texts)
            )
            start = time.time()
            embeddings = self.model.encode(
                texts, normalize_embeddings=True, show_progress_bar=False
            )
            elapsed = time.time() - start
            logger.info(
                "Embeddings computed in %.2fs (shape=%s).",
                elapsed,
                embeddings.shape,
            )
            return embeddings

        except Exception as exc:  # pragma: no cover
            logger.error("Failed to compute embeddings: %s", exc)
            return None

    @staticmethod
    def _compute_category_dist(chunks: List[ClassifiedChunk]) -> Dict[str, int]:
        """Count chunks per category."""
        dist: Dict[str, int] = {}
        for c in chunks:
            cat = c.classification.category
            dist[cat] = dist.get(cat, 0) + 1
        return dist

    def __repr__(self) -> str:
        return (
            f"RAGExporter(model={self.model_name!r}, "
            f"exports={self._exports_completed})"
        )
