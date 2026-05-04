"""
Multi-LLM Chat Battle — demo для Lesson 10 (API Layer for AI Systems).

Демонструє:
- Streaming SSE (паралельно з 3 моделей)
- Concurrency control (asyncio.Semaphore)
- Cost tracking per model
- Cancellation на disconnect
- Chaos engineering (kill provider toggle)
- Cost comparison real-time
"""
import asyncio
import json
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import llm_router
from .config import MODELS, CONCURRENCY_LIMIT, USE_MOCK


# Global state for demo
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
active_streams = 0
aborted_streams = 0
cost_log: list[dict] = []  # in-memory cost tracking


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 Demo started · MOCK_MODE={USE_MOCK} · concurrency_limit={CONCURRENCY_LIMIT}")
    yield


app = FastAPI(title="Multi-LLM Chat Battle", lifespan=lifespan)


# ====================== API Models ======================

class BattleRequest(BaseModel):
    message: str


class ChaosRequest(BaseModel):
    model_id: str
    fail_rate: float  # 0.0 = healthy, 1.0 = always fails


# ====================== Endpoints ======================

@app.get("/")
async def index():
    return FileResponse(Path(__file__).parent.parent / "static" / "index.html")


@app.get("/api/models")
async def list_models():
    return {
        "models": MODELS,
        "mock_mode": USE_MOCK,
        "concurrency_limit": CONCURRENCY_LIMIT,
    }


@app.get("/api/health")
async def health():
    return {
        "active_streams": active_streams,
        "aborted_streams": aborted_streams,
        "concurrency_used": CONCURRENCY_LIMIT - semaphore._value,
        "concurrency_limit": CONCURRENCY_LIMIT,
        "mock_mode": USE_MOCK,
    }


@app.get("/api/usage")
async def usage():
    """Aggregate cost stats per model."""
    by_model = defaultdict(lambda: {"requests": 0, "tokens": 0, "cost_usd": 0.0, "errors": 0})
    for entry in cost_log:
        m = by_model[entry["model"]]
        m["requests"] += 1
        if entry.get("error"):
            m["errors"] += 1
        else:
            m["tokens"] += entry.get("tokens", 0)
            m["cost_usd"] += entry.get("cost_usd", 0.0)

    total = {
        "requests": len(cost_log),
        "cost_usd": round(sum(e.get("cost_usd", 0.0) for e in cost_log), 6),
        "tokens": sum(e.get("tokens", 0) for e in cost_log),
        "errors": sum(1 for e in cost_log if e.get("error")),
    }
    return {"by_model": dict(by_model), "total": total, "recent": cost_log[-20:]}


@app.post("/api/chaos")
async def set_chaos(req: ChaosRequest):
    """Toggle failure rate per model — для демо fallback / resilience."""
    llm_router.fail_rates[req.model_id] = req.fail_rate
    return {"ok": True, "fail_rates": llm_router.fail_rates}


@app.post("/api/battle")
async def battle(req: BattleRequest, request: Request):
    """
    SSE endpoint: стрімить токени паралельно з усіх моделей.
    Кожен event має поле `model_id` щоб frontend знав куди писати.
    """
    global active_streams, aborted_streams
    active_streams += 1
    request_start = time.monotonic()

    async def event_stream():
        global active_streams, aborted_streams

        # Send initial event
        yield f"data: {json.dumps({'type': 'start', 'models': [m['id'] for m in MODELS]})}\n\n"

        # Build async generators for each model
        gens = {m["id"]: llm_router.stream_from_model(m["id"], req.message, semaphore) for m in MODELS}
        # Per-model accumulators
        text_buffers = {m["id"]: "" for m in MODELS}
        completed = set()
        disconnected = False

        # Pull from all generators concurrently
        async def pump(model_id: str):
            try:
                async for event in gens[model_id]:
                    yield model_id, event
            except asyncio.CancelledError:
                yield model_id, {"type": "error", "message": "cancelled"}

        # Merge using a queue
        queue: asyncio.Queue = asyncio.Queue()

        async def runner(model_id: str):
            async for event in gens[model_id]:
                await queue.put((model_id, event))
            await queue.put((model_id, None))  # sentinel

        tasks = [asyncio.create_task(runner(m["id"])) for m in MODELS]

        try:
            done_count = 0
            while done_count < len(MODELS):
                if await request.is_disconnected():
                    disconnected = True
                    break

                try:
                    model_id, event = await asyncio.wait_for(queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue

                if event is None:
                    done_count += 1
                    continue

                # Annotate with model_id
                event["model_id"] = model_id

                # Track full text
                if event["type"] == "token":
                    text_buffers[model_id] += event["content"]

                # Cost tracking on done
                if event["type"] == "done":
                    model_cfg = next(m for m in MODELS if m["id"] == model_id)
                    tokens = event["stats"]["tokens"]
                    # Approx: assume 1 char ≈ 0.25 tokens for input cost
                    input_tokens = max(1, len(req.message) // 4)
                    cost = (input_tokens * model_cfg["price_in"] + tokens * model_cfg["price_out"]) / 1_000_000
                    event["stats"]["cost_usd"] = round(cost, 6)
                    cost_log.append({
                        "model": model_id,
                        "tokens": tokens,
                        "cost_usd": cost,
                        "ttft_ms": event["stats"]["ttft_ms"],
                        "total_ms": event["stats"]["total_ms"],
                    })
                    completed.add(model_id)

                if event["type"] == "error":
                    cost_log.append({
                        "model": model_id,
                        "error": event["message"],
                        "tokens": 0,
                        "cost_usd": 0.0,
                    })
                    completed.add(model_id)

                yield f"data: {json.dumps(event)}\n\n"

            yield f"data: {json.dumps({'type': 'all_done', 'total_ms': round((time.monotonic() - request_start) * 1000)})}\n\n"

        finally:
            for t in tasks:
                if not t.done():
                    t.cancel()
            active_streams -= 1
            if disconnected:
                aborted_streams += 1

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# Mount static AFTER routes
app.mount("/static", StaticFiles(directory=Path(__file__).parent.parent / "static"), name="static")
