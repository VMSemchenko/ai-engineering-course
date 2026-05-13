"""
Production-Ready RAG API — Lesson 10 Homework.

Endpoints:
  POST /chat/stream      — RAG Q&A with SSE streaming
  GET  /usage/today      — today's cost summary
  GET  /usage/breakdown  — per-model breakdown
  GET  /health           — liveness probe
  POST /index/rebuild    — re-index document
"""

import asyncio
import json
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from . import auth, rate_limiter, security, embedder, cost_tracker, observability
from .config import CONCURRENCY_LIMIT, USE_MOCK, RAG_TOP_K
from .llm_client import stream_with_fallback
from .pricing import calculate_cost
from .semantic_cache import get_cache
from .vector_store import get_store, reload_store

# ── Global state ─────────────────────────────────────────────
semaphore: asyncio.Semaphore | None = None
active_streams = 0
aborted_streams = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    global semaphore
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    print(f"🚀 RAG API started | mock={USE_MOCK} | concurrency={CONCURRENCY_LIMIT}")
    # Pre-load embedding model and FAISS index
    embedder.get_model()
    get_store()
    get_cache()
    yield
    observability.flush()


app = FastAPI(
    title="RAG Q&A API",
    description="Production-ready RAG API with streaming, cache, rate limiting, and fallback",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Request models ───────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


# ── Endpoints ────────────────────────────────────────────────

@app.get("/health")
async def health():
    store = get_store()
    cache = get_cache()
    return {
        "status": "ok",
        "active_streams": active_streams,
        "aborted_streams": aborted_streams,
        "concurrency_used": CONCURRENCY_LIMIT - semaphore._value if semaphore else 0,
        "concurrency_limit": CONCURRENCY_LIMIT,
        "index_size": store.index.ntotal if store.index else 0,
        "cache_size": cache.size,
        "mock_mode": USE_MOCK,
    }


@app.get("/usage/today")
async def usage_today(request: Request):
    tier_info = auth.authenticate(request)
    return cost_tracker.get_today_usage(tier_info["api_key"])


@app.get("/usage/breakdown")
async def usage_breakdown(request: Request):
    tier_info = auth.authenticate(request)
    return cost_tracker.get_breakdown(tier_info["api_key"])


@app.post("/index/rebuild")
async def index_rebuild(request: Request):
    auth.authenticate(request)  # require auth
    # Lazy import to avoid circular deps
    import subprocess, sys
    subprocess.Popen(
        [sys.executable, "-m", "scripts.index"],
        cwd=str(__import__("pathlib").Path(__file__).parent.parent),
    )
    return {"status": "rebuilding", "message": "Index rebuild started in background"}


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    global active_streams, aborted_streams

    # ── 1. Auth ──────────────────────────────────────────────
    tier_info = auth.authenticate(request)

    # ── 2. Security check ────────────────────────────────────
    security.check_input(req.message)

    # ── 3. Rate limit pre-check ──────────────────────────────
    rate_limiter.check_rate_limit(
        tier_info["api_key"],
        tier_info["token_limit"],
    )

    # ── Start trace ──────────────────────────────────────────
    trace = observability.create_trace(
        name="chat_stream",
        metadata={
            "api_key": tier_info["api_key"],
            "tier": tier_info["tier_name"],
        },
    )

    # ── 4. Embed query (single call for both cache + RAG) ────
    trace.span(name="embed_query")
    query_embedding = embedder.embed(req.message)
    trace.end_span()

    # ── 5. Cache check ───────────────────────────────────────
    trace.span(name="cache_check")
    cache = get_cache()
    cached = cache.check(query_embedding)
    trace.end_span()

    if cached:
        # Cache HIT — stream cached response token by token
        active_streams += 1
        rate_limiter.refund_tokens(
            tier_info["api_key"],
            tier_info["token_limit"],
        )

        async def stream_cached():
            global active_streams
            try:
                start = time.monotonic()
                words = cached.response.split(" ")
                for i, word in enumerate(words):
                    if await request.is_disconnected():
                        break
                    token = word + (" " if i < len(words) - 1 else "")
                    event = {"type": "token", "content": token}
                    yield f"data: {json.dumps(event)}\n\n"
                    await asyncio.sleep(0.005)  # Fast but visible streaming

                done_event = {
                    "type": "done",
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                    "cost_usd": 0.0,
                    "cache_hit": True,
                    "cache_score": round(cached.score, 4),
                    "model": cached.model,
                    "sources": [],
                    "latency_ms": round((time.monotonic() - start) * 1000),
                }
                yield f"data: {json.dumps(done_event)}\n\n"

                # Log as cache hit
                cost_tracker.log_request(
                    api_key=tier_info["api_key"],
                    model=cached.model,
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=0.0,
                    latency_ms=round((time.monotonic() - start) * 1000),
                    ttft_ms=5,
                    cache_hit=True,
                )
                trace.update(
                    metadata={"cache_hit": True, "cache_score": cached.score}
                )
            finally:
                active_streams -= 1

        return StreamingResponse(stream_cached(), media_type="text/event-stream")

    # ── 6. Vector search (RAG retrieval) ─────────────────────
    trace.span(name="vector_search")
    store = get_store()
    chunks = store.search(query_embedding, top_k=RAG_TOP_K)
    source_ids = [c["id"] for c in chunks]
    trace.end_span()

    # ── 7. LLM call with fallback ────────────────────────────
    active_streams += 1

    async def stream_llm():
        global active_streams, aborted_streams
        request_start = time.monotonic()
        disconnected = False

        try:
            trace.span(name="llm_call")
            async with semaphore:
                token_gen, result = await stream_with_fallback(
                    models=tier_info["models"],
                    query=req.message,
                    context_chunks=chunks,
                )

                async for token in token_gen:
                    if await request.is_disconnected():
                        disconnected = True
                        break
                    event = {"type": "token", "content": token}
                    yield f"data: {json.dumps(event)}\n\n"

            trace.end_span()

            if disconnected:
                aborted_streams += 1
                rate_limiter.refund_tokens(
                    tier_info["api_key"],
                    tier_info["token_limit"],
                )
                return

            # ── 8. Post-processing ───────────────────────────
            # Output filtering
            output_filtered = security.check_output(result.full_text)

            # Calculate cost
            cost = calculate_cost(
                result.model_used,
                result.input_tokens,
                result.output_tokens,
            )

            # Consume actual tokens in rate limiter
            total_tokens = result.input_tokens + result.output_tokens
            rate_limiter.consume_tokens(
                tier_info["api_key"],
                tier_info["token_limit"],
                total_tokens,
            )

            total_ms = round((time.monotonic() - request_start) * 1000)

            # Done event
            done_event = {
                "type": "done",
                "usage": {
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                },
                "cost_usd": cost,
                "cache_hit": False,
                "model": result.model_used,
                "fallback_used": result.fallback_used,
                "sources": source_ids,
                "latency_ms": total_ms,
                "ttft_ms": result.ttft_ms,
            }
            yield f"data: {json.dumps(done_event)}\n\n"

            # ── 9. Log cost ──────────────────────────────────
            cost_tracker.log_request(
                api_key=tier_info["api_key"],
                model=result.model_used,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost_usd=cost,
                latency_ms=total_ms,
                ttft_ms=result.ttft_ms,
                cache_hit=False,
                fallback_used=result.fallback_used,
                output_filtered=output_filtered,
            )

            # ── 10. Store in cache ───────────────────────────
            cache.store(
                embedding=query_embedding,
                query=req.message,
                response=result.full_text,
                model=result.model_used,
            )

            # ── Update trace ─────────────────────────────────
            trace.update(
                metadata={
                    "model": result.model_used,
                    "fallback_used": result.fallback_used,
                    "cache_hit": False,
                    "cost_usd": cost,
                    "output_filtered": output_filtered,
                }
            )
            gen = trace.generation(
                name="llm_completion",
                model=result.model_used,
                input=req.message,
                output=result.full_text,
                usage={
                    "input": result.input_tokens,
                    "output": result.output_tokens,
                },
            )

        except Exception as e:
            error_event = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error_event)}\n\n"
        finally:
            active_streams -= 1

    return StreamingResponse(stream_llm(), media_type="text/event-stream")
