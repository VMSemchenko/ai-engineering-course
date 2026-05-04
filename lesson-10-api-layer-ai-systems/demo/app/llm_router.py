"""LLM router: streams from real OpenRouter or mock."""
import asyncio
import time
from typing import AsyncIterator

from openai import AsyncOpenAI

from .config import OPENROUTER_API_KEY, USE_MOCK
from .mock_llm import stream_mock, fail_random


_client: AsyncOpenAI | None = None
# Per-model fail_rate for chaos demo (0.0 = healthy, 1.0 = always fails)
fail_rates: dict[str, float] = {}


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
    return _client


async def stream_from_model(
    model_id: str,
    prompt: str,
    semaphore: asyncio.Semaphore,
) -> AsyncIterator[dict]:
    """
    Stream tokens from a single model.
    Yields dicts: {"type": "token", "content": str}, {"type": "done", "stats": {...}},
                  {"type": "error", "message": str}
    """
    async with semaphore:
        start = time.monotonic()
        first_token_time: float | None = None
        token_count = 0
        full_text = ""

        try:
            # Chaos engineering: simulate provider failure
            await fail_random(model_id, fail_rates.get(model_id, 0.0))

            if USE_MOCK:
                async for chunk in stream_mock(model_id, prompt):
                    if first_token_time is None:
                        first_token_time = time.monotonic()
                    token_count += 1
                    full_text += chunk
                    yield {"type": "token", "content": chunk}
            else:
                client = get_client()
                stream = await client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                    max_tokens=300,
                    temperature=0.7,
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        if first_token_time is None:
                            first_token_time = time.monotonic()
                        token_count += 1
                        full_text += delta
                        yield {"type": "token", "content": delta}

            total_time = time.monotonic() - start
            ttft = (first_token_time - start) if first_token_time else total_time
            yield {
                "type": "done",
                "stats": {
                    "total_ms": round(total_time * 1000),
                    "ttft_ms": round(ttft * 1000),
                    "tokens": token_count,
                    "tokens_per_sec": round(token_count / max(total_time, 0.001), 1),
                },
            }

        except Exception as e:
            yield {"type": "error", "message": str(e), "after_ms": round((time.monotonic() - start) * 1000)}
