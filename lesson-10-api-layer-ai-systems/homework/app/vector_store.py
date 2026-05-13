"""FAISS vector store for RAG chunks."""

import json
import os
from pathlib import Path

import faiss
import numpy as np

from .config import EMBEDDING_DIM

INDEX_DIR = Path(__file__).parent.parent / "data" / "faiss_index"


class VectorStore:
    """FAISS-based vector store with metadata sidecar."""

    def __init__(self):
        self.index: faiss.IndexFlatIP | None = None
        self.chunks: list[dict] = []

    def build(self, embeddings: np.ndarray, chunks: list[dict]) -> None:
        """Build index from embeddings and chunk metadata."""
        self.index = faiss.IndexFlatIP(EMBEDDING_DIM)
        # faiss.normalize_L2(embeddings)  # already normalized in embedder
        self.index.add(embeddings)
        self.chunks = chunks
        print(f"📊 FAISS index built: {self.index.ntotal} vectors")

    def search(self, query_embedding: np.ndarray, top_k: int = 3) -> list[dict]:
        """Search for top-k similar chunks."""
        if self.index is None or self.index.ntotal == 0:
            return []

        query = query_embedding.reshape(1, -1)
        scores, indices = self.index.search(query, min(top_k, self.index.ntotal))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            chunk = self.chunks[idx].copy()
            chunk["score"] = float(score)
            results.append(chunk)
        return results

    def save(self, directory: Path | None = None) -> None:
        """Save index and metadata to disk."""
        save_dir = directory or INDEX_DIR
        save_dir.mkdir(parents=True, exist_ok=True)

        if self.index is not None:
            faiss.write_index(self.index, str(save_dir / "index.faiss"))
        with open(save_dir / "chunks.json", "w") as f:
            json.dump(self.chunks, f, ensure_ascii=False, indent=2)
        print(f"💾 Index saved to {save_dir}")

    def load(self, directory: Path | None = None) -> bool:
        """Load index and metadata from disk. Returns True if successful."""
        load_dir = directory or INDEX_DIR
        index_path = load_dir / "index.faiss"
        meta_path = load_dir / "chunks.json"

        if not index_path.exists() or not meta_path.exists():
            return False

        self.index = faiss.read_index(str(index_path))
        with open(meta_path) as f:
            self.chunks = json.load(f)
        print(f"📦 Index loaded: {self.index.ntotal} vectors, {len(self.chunks)} chunks")
        return True


# Singleton
_store: VectorStore | None = None


def get_store() -> VectorStore:
    """Get or create the vector store singleton."""
    global _store
    if _store is None:
        _store = VectorStore()
        if not _store.load():
            print("⚠️  No FAISS index found. Run `python -m scripts.index` first.")
    return _store


def reload_store() -> VectorStore:
    """Force reload the vector store from disk."""
    global _store
    _store = VectorStore()
    _store.load()
    return _store
