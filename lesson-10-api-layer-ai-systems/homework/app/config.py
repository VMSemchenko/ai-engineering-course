"""Application configuration — settings, tiers, model chains."""

import os
from dotenv import load_dotenv

load_dotenv()

# ── OpenRouter ──────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
USE_MOCK = os.getenv("USE_MOCK", "false").lower() == "true" or not OPENROUTER_API_KEY

# ── Langfuse (optional) ────────────────────────────────────
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
LANGFUSE_ENABLED = bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)

# ── Concurrency ─────────────────────────────────────────────
CONCURRENCY_LIMIT = int(os.getenv("CONCURRENCY_LIMIT", "20"))

# ── Embedding model ─────────────────────────────────────────
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# ── RAG settings ─────────────────────────────────────────────
CHUNK_SIZE_TOKENS = 500
CHUNK_OVERLAP_TOKENS = 50
RAG_TOP_K = 3

# ── Semantic cache ───────────────────────────────────────────
CACHE_SIMILARITY_THRESHOLD = 0.92
CACHE_TTL_SECONDS = 3600  # 1 hour

# ── API key tiers ────────────────────────────────────────────
# Each tier: token_limit (per minute), list of models (fallback chain)
TIERS = {
    "demo-free": {
        "token_limit": 5_000,
        "models": [
            "meta-llama/llama-3.1-8b-instruct:free",
            "google/gemini-flash-1.5-8b",
            "meta-llama/llama-3.2-3b-instruct:free",
        ],
    },
    "demo-pro": {
        "token_limit": 20_000,
        "models": [
            "mistralai/mistral-nemo",
            "meta-llama/llama-3.1-8b-instruct",
            "google/gemma-3-4b-it",
        ],
    },
    "demo-enterprise": {
        "token_limit": 100_000,
        "models": [
            "openai/gpt-4o-mini",
            "mistralai/mistral-nemo",
            "meta-llama/llama-3.1-8b-instruct",
        ],
    },
}

# ── API keys → tier mapping ──────────────────────────────────
API_KEYS = {
    "demo-key-free": "demo-free",
    "demo-key-pro": "demo-pro",
    "demo-key-enterprise": "demo-enterprise",
}

# ── System prompt ────────────────────────────────────────────
SYSTEM_PROMPT = """You are a helpful Q&A assistant. You answer questions based ONLY on the provided context.
If the context does not contain enough information to answer, say so honestly.
Always cite which parts of the context you used. Be concise and precise.

<context>
{context}
</context>

Answer the following user question based on the context above.
<user_query>
{query}
</user_query>"""
