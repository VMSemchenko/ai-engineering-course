# Lesson 10 — Production-Ready RAG API

A Q&A bot over **The Twelve-Factor App** document, wrapped in a production API with all key layers from the lecture.

## Architecture

```
POST /chat/stream
  │
  ├─ 1. Auth (X-API-Key → tier resolution)
  ├─ 2. Security (prompt injection detection)
  ├─ 3. Rate Limit (token bucket pre-check)
  ├─ 4. Embed Query (sentence-transformers, single call)
  ├─ 5. Cache Check (Qdrant semantic cache, threshold > 0.92)
  │     ├─ HIT → stream cached response
  │     └─ MISS ↓
  ├─ 6. Vector Search (FAISS, top-k=3)
  ├─ 7. LLM Call (OpenRouter + fallback chain + circuit breaker)
  ├─ 8. SSE Streaming (token by token)
  ├─ 9. Cost Tracking (SQLite)
  └─ 10. Cache Store (save for future hits)
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11 · FastAPI · Uvicorn |
| LLM | OpenRouter (200+ models via single API key) |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`, local) |
| Vector DB | FAISS (in-memory, persisted to disk) |
| Semantic Cache | Qdrant (in-memory local mode) |
| Rate Limiting | In-memory token bucket |
| Cost Tracking | SQLite |
| Observability | Langfuse (optional) |
| Deploy | Docker |

## Quick Start

### 1. Install dependencies

```bash
cd lesson-10-api-layer-ai-systems/homework
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — add your OPENROUTER_API_KEY
# Or set USE_MOCK=true for testing without API key
```

### 3. Build the index

```bash
python -m scripts.index
```

### 4. Run the server

```bash
uvicorn app.main:app --reload
```

### 5. Test

```bash
# Streaming RAG query
curl -N -X POST http://localhost:8000/chat/stream \
  -H "X-API-Key: demo-key-free" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the twelve-factor app?"}'

# Health check
curl http://localhost:8000/health

# Usage stats
curl -H "X-API-Key: demo-key-free" http://localhost:8000/usage/today
curl -H "X-API-Key: demo-key-free" http://localhost:8000/usage/breakdown
```

## API Keys

| Key | Tier | Token Limit | Models |
|-----|------|------------|--------|
| `demo-key-free` | demo-free | 5,000/min | Llama 3.1 8B (free), Gemini Flash 1.5 8B, Llama 3.2 3B (free) |
| `demo-key-pro` | demo-pro | 20,000/min | Mistral Nemo, Llama 3.1 8B, Gemma 3 4B |
| `demo-key-enterprise` | demo-enterprise | 100,000/min | GPT-4o-mini, Mistral Nemo, Llama 3.1 8B |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat/stream` | RAG Q&A with SSE streaming |
| `GET` | `/usage/today` | Today's cost summary |
| `GET` | `/usage/breakdown` | Per-model breakdown |
| `GET` | `/health` | Liveness probe |
| `POST` | `/index/rebuild` | Re-index document |

## Features Implemented

- [x] **§1 RAG Base Layer** — FAISS + sentence-transformers, no LangChain abstractions
- [x] **§2 SSE Streaming** — token-by-token with disconnect handling
- [x] **§3 Auth** — 3 API keys with tier metadata
- [x] **§4 Token Rate Limiting** — token bucket with actual usage tracking
- [x] **§5 Semantic Cache** — Qdrant local mode, threshold 0.92, TTL 1h
- [x] **§6 Cost Tracking** — SQLite with per-request logging
- [x] **§7 Multi-Provider Fallback** — 3-model chain with circuit breaker
- [x] **§8 Prompt Injection Defense** — input patterns + output filtering
- [x] **§9 Async/Concurrency** — Semaphore(20) + disconnect handling
- [x] **§10 Observability** — Langfuse integration (optional)
- [x] **§11 Deployment** — Dockerfile + docker-compose

## Docker

```bash
docker compose up --build
```

## Environment Variables

```
OPENROUTER_API_KEY     — OpenRouter API key (required for real LLM)
USE_MOCK               — "true" to use mock LLM (default: false)
LANGFUSE_PUBLIC_KEY    — Langfuse public key (optional)
LANGFUSE_SECRET_KEY    — Langfuse secret key (optional)
LANGFUSE_HOST          — Langfuse host (default: https://cloud.langfuse.com)
CONCURRENCY_LIMIT      — Max concurrent LLM calls (default: 20)
```
