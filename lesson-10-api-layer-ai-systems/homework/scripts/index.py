"""Index document into FAISS vector store.

Usage: python -m scripts.index
"""

import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import tiktoken
from app.embedder import embed_batch
from app.vector_store import VectorStore

SOURCE_PATH = Path(__file__).parent.parent / "data" / "source.md"
CHUNK_SIZE = 500     # tokens
CHUNK_OVERLAP = 50   # tokens


def read_document(path: Path) -> str:
    """Read source document."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """Split text into overlapping chunks of ~chunk_size tokens.

    Strategy: split by paragraphs, then merge until reaching chunk_size.
    """
    enc = tiktoken.get_encoding("cl100k_base")

    # Split by double newlines (paragraphs/sections)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current_text = ""
    current_tokens = 0
    chunk_id = 0

    for para in paragraphs:
        para_tokens = len(enc.encode(para))

        # If adding this paragraph exceeds chunk size, save current chunk
        if current_tokens + para_tokens > chunk_size and current_text:
            chunks.append({
                "id": f"chunk_{chunk_id}",
                "text": current_text.strip(),
                "tokens": current_tokens,
            })
            chunk_id += 1

            # Overlap: keep the last ~overlap tokens worth of text
            if overlap > 0:
                words = current_text.split()
                overlap_words = []
                overlap_count = 0
                for w in reversed(words):
                    overlap_count += len(enc.encode(w))
                    if overlap_count >= overlap:
                        break
                    overlap_words.insert(0, w)
                current_text = " ".join(overlap_words) + "\n\n"
                current_tokens = len(enc.encode(current_text))
            else:
                current_text = ""
                current_tokens = 0

        current_text += para + "\n\n"
        current_tokens += para_tokens

    # Don't forget the last chunk
    if current_text.strip():
        chunks.append({
            "id": f"chunk_{chunk_id}",
            "text": current_text.strip(),
            "tokens": current_tokens,
        })

    return chunks


def main():
    print("=" * 60)
    print("📄 Document Indexer")
    print("=" * 60)

    # 1. Read document
    if not SOURCE_PATH.exists():
        print(f"❌ Source document not found: {SOURCE_PATH}")
        sys.exit(1)

    text = read_document(SOURCE_PATH)
    print(f"📖 Read {len(text)} characters from {SOURCE_PATH.name}")

    # 2. Split into chunks
    chunks = split_into_chunks(text)
    print(f"✂️  Split into {len(chunks)} chunks")
    for c in chunks[:3]:
        print(f"   {c['id']}: {c['tokens']} tokens — {c['text'][:80]}...")

    # 3. Embed chunks
    print(f"\n🧠 Embedding {len(chunks)} chunks...")
    texts = [c["text"] for c in chunks]
    embeddings = embed_batch(texts)
    print(f"✅ Embeddings shape: {embeddings.shape}")

    # 4. Build and save index
    store = VectorStore()
    store.build(embeddings, chunks)
    store.save()

    print(f"\n🎉 Done! Index saved with {len(chunks)} chunks.")
    print("   Run: uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
