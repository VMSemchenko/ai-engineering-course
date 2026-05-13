"""Semantic cache using Qdrant local mode."""

import time
import uuid
from dataclasses import dataclass

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
    Filter,
    FieldCondition,
    Range,
)

from .config import EMBEDDING_DIM, CACHE_SIMILARITY_THRESHOLD, CACHE_TTL_SECONDS

CACHE_COLLECTION = "cache_collection"


@dataclass
class CachedResponse:
    query: str
    response: str
    model: str
    score: float
    timestamp: float


class SemanticCache:
    """Qdrant-based semantic cache for LLM responses."""

    def __init__(self):
        # In-memory Qdrant — no Docker needed
        self.client = QdrantClient(":memory:")
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create cache collection if it doesn't exist."""
        collections = [c.name for c in self.client.get_collections().collections]
        if CACHE_COLLECTION not in collections:
            self.client.create_collection(
                collection_name=CACHE_COLLECTION,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIM,
                    distance=Distance.COSINE,
                ),
            )

    def check(self, embedding: np.ndarray) -> CachedResponse | None:
        """Check cache for a semantically similar query.

        Returns CachedResponse if similarity > threshold and not expired.
        """
        now = time.time()

        results = self.client.search(
            collection_name=CACHE_COLLECTION,
            query_vector=embedding.tolist(),
            limit=1,
            score_threshold=CACHE_SIMILARITY_THRESHOLD,
        )

        if not results:
            return None

        hit = results[0]
        payload = hit.payload

        # Check TTL
        expire_at = payload.get("expire_at", 0)
        if now > expire_at:
            # Expired — delete and return None
            self.client.delete(
                collection_name=CACHE_COLLECTION,
                points_selector=[hit.id],
            )
            return None

        return CachedResponse(
            query=payload["query"],
            response=payload["response"],
            model=payload["model"],
            score=hit.score,
            timestamp=payload["timestamp"],
        )

    def store(
        self,
        embedding: np.ndarray,
        query: str,
        response: str,
        model: str,
    ) -> None:
        """Store a new cache entry."""
        now = time.time()
        point_id = str(uuid.uuid4())

        self.client.upsert(
            collection_name=CACHE_COLLECTION,
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding.tolist(),
                    payload={
                        "query": query,
                        "response": response,
                        "model": model,
                        "timestamp": now,
                        "expire_at": now + CACHE_TTL_SECONDS,
                    },
                )
            ],
        )

    @property
    def size(self) -> int:
        """Number of entries in cache."""
        info = self.client.get_collection(CACHE_COLLECTION)
        return info.points_count


# Singleton
_cache: SemanticCache | None = None


def get_cache() -> SemanticCache:
    global _cache
    if _cache is None:
        _cache = SemanticCache()
    return _cache
