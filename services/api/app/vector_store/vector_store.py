#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vector_store.py
Persistent vector store for medical document embeddings using Qdrant.
Supports multi-tenant isolation and hybrid search.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance, VectorParams, PointStruct,
        Filter, FieldCondition, MatchValue,
    )
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


@dataclass
class SearchResult:
    """A single vector search result."""
    doc_id: str
    score: float
    text: str
    metadata: Dict[str, Any]


class MedicalVectorStore:
    """
    Persistent vector store for medical document embeddings.
    
    Features:
    - Persistent storage via Qdrant (with in-memory fallback)
    - Multi-tenant data isolation
    - Semantic similarity search
    - Metadata filtering
    """
    
    DEFAULT_COLLECTION = "medical_documents"
    EMBEDDING_DIM = 384  # paraphrase-multilingual-MiniLM-L12-v2
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection: str = DEFAULT_COLLECTION,
        api_key: Optional[str] = None,
    ):
        self.collection = collection
        self.connected = False
        self._mock_storage: List[Dict] = []
        
        if QDRANT_AVAILABLE:
            try:
                kwargs = {"host": host, "port": port, "timeout": 5}
                if api_key:
                    kwargs["api_key"] = api_key
                self.client = QdrantClient(**kwargs)
                self._ensure_collection()
                self.connected = True
            except Exception:
                self.connected = False
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=self.EMBEDDING_DIM,
                    distance=Distance.COSINE,
                ),
            )

    def store(
        self,
        doc_id: str,
        text: str,
        embedding: List[float],
        metadata: Optional[Dict] = None,
        tenant_id: str = "default",
    ) -> bool:
        """
        Store a document embedding with metadata.
        
        Args:
            doc_id: Unique document identifier
            text: Original text content
            embedding: Vector embedding
            metadata: Additional metadata dict
            tenant_id: Tenant identifier for data isolation
            
        Returns:
            True if stored successfully
        """
        payload = {**(metadata or {}), "text": text, "tenant_id": tenant_id}
        
        if self.connected:
            self.client.upsert(
                collection_name=self.collection,
                points=[PointStruct(
                    id=doc_id,
                    vector=embedding,
                    payload=payload,
                )],
            )
        else:
            self._mock_storage.append({
                "id": doc_id,
                "text": text,
                "vector": embedding,
                "payload": payload,
            })
        return True

    def search(
        self,
        query_embedding: List[float],
        tenant_id: str = "default",
        limit: int = 5,
        score_threshold: float = 0.0,
    ) -> List[SearchResult]:
        """
        Search for similar documents.
        
        Args:
            query_embedding: Query vector
            tenant_id: Tenant filter
            limit: Max results
            score_threshold: Minimum similarity score
            
        Returns:
            List of SearchResult sorted by score descending
        """
        if self.connected:
            raw_results = self.client.search(
                collection_name=self.collection,
                query_vector=query_embedding,
                query_filter=Filter(must=[
                    FieldCondition(
                        key="tenant_id",
                        match=MatchValue(value=tenant_id),
                    )
                ]),
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
            )
            return [
                SearchResult(
                    doc_id=str(r.id),
                    score=r.score,
                    text=r.payload.get("text", ""),
                    metadata={k: v for k, v in r.payload.items() if k != "text"},
                )
                for r in raw_results
            ]
        
        # Fallback: in-memory cosine similarity
        results = []
        for item in self._mock_storage:
            if item["payload"].get("tenant_id") == tenant_id:
                sim = cosine_similarity(
                    [query_embedding], [item["vector"]]
                )[0][0]
                if sim >= score_threshold:
                    results.append(SearchResult(
                        doc_id=item["id"],
                        score=float(sim),
                        text=item["payload"].get("text", ""),
                        metadata={k: v for k, v in item["payload"].items() if k != "text"},
                    ))
        
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def delete(self, doc_id: str) -> bool:
        """Delete a document by ID."""
        if self.connected:
            self.client.delete(
                collection_name=self.collection,
                points_selector=[doc_id],
            )
            return True
        self._mock_storage = [s for s in self._mock_storage if s["id"] != doc_id]
        return True

    def count(self, tenant_id: Optional[str] = None) -> int:
        """Count stored documents, optionally filtered by tenant."""
        if self.connected:
            if tenant_id:
                result = self.client.count(
                    collection_name=self.collection,
                    count_filter=Filter(must=[
                        FieldCondition(
                            key="tenant_id",
                            match=MatchValue(value=tenant_id),
                        )
                    ]),
                )
                return result.count
            return self.client.count(collection_name=self.collection).count
        if tenant_id:
            return sum(
                1 for s in self._mock_storage
                if s["payload"].get("tenant_id") == tenant_id
            )
        return len(self._mock_storage)
