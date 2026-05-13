"""Embedding wrapper — sentence-transformers all-MiniLM-L6-v2."""

import numpy as np
from sentence_transformers import SentenceTransformer

from .config import EMBEDDING_MODEL

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Load embedding model (singleton)."""
    global _model
    if _model is None:
        print(f"📦 Loading embedding model: {EMBEDDING_MODEL}")
        _model = SentenceTransformer(EMBEDDING_MODEL)
        print("✅ Embedding model loaded")
    return _model


def embed(text: str) -> np.ndarray:
    """Embed a single text. Returns normalized 384-dim vector."""
    model = get_model()
    vec = model.encode(text, normalize_embeddings=True)
    return np.array(vec, dtype=np.float32)


def embed_batch(texts: list[str]) -> np.ndarray:
    """Embed a batch of texts. Returns (N, 384) normalized matrix."""
    model = get_model()
    vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    return np.array(vecs, dtype=np.float32)
