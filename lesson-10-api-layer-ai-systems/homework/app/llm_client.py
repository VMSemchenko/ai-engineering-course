"""LLM client — OpenRouter with multi-model fallback and circuit breaker."""

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import AsyncIterator

from openai import AsyncOpenAI, APIStatusError

from .config import OPENROUTER_API_KEY, USE_MOCK, SYSTEM_PROMPT


# ── Circuit Breaker ──────────────────────────────────────────

@dataclass
class CircuitState:
    """Per-model circuit breaker state."""
    failures: list[float] = field(default_factory=list)
    open_until: float = 0.0

    FAILURE_THRESHOLD = 5
    WINDOW_SECONDS = 60
    COOLDOWN_SECONDS = 60

    def record_failure(self) -> None:
        now = time.monotonic()
        self.failures.append(now)
        # Clean old failures
        self.failures = [t for t in self.failures if now - t < self.WINDOW_SECONDS]
        if len(self.failures) >= self.FAILURE_THRESHOLD:
            self.open_until = now + self.COOLDOWN_SECONDS

    def is_open(self) -> bool:
        return time.monotonic() < self.open_until

    def record_success(self) -> None:
        self.failures.clear()
        self.open_until = 0.0


_circuits: dict[str, CircuitState] = {}


def _get_circuit(model: str) -> CircuitState:
    if model not in _circuits:
        _circuits[model] = CircuitState()
    return _circuits[model]


# ── Client ───────────────────────────────────────────────────

_client: AsyncOpenAI | None = None

# Retryable HTTP status codes
RETRYABLE_CODES = {429, 500, 502, 503, 504}
NON_RETRYABLE_CODES = {400, 401, 403, 422}
LLM_TIMEOUT = 15  # seconds


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
    return _client


@dataclass
class StreamResult:
    """Accumulated result from a streaming LLM call."""
    model_used: str = ""
    fallback_used: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    full_text: str = ""
    ttft_ms: int = 0
    total_ms: int = 0


# ── Mock streaming ───────────────────────────────────────────

async def _stream_mock(prompt: str) -> AsyncIterator[str]:
    """Mock streaming for testing without API key."""
    mock_response = (
        "Based on the provided context from The Twelve-Factor App methodology, "
        "here is the answer to your question. The twelve-factor app is a methodology "
        "for building software-as-a-service apps that use declarative formats for setup "
        "automation, have a clean contract with the underlying operating system, are "
        "suitable for deployment on modern cloud platforms, minimize divergence between "
        "development and production, and can scale up without significant changes. "
        "This methodology was developed based on experience with hundreds of apps "
        "on the Heroku platform."
    )
    words = mock_response.split(" ")
    for i, word in enumerate(words):
        await asyncio.sleep(0.03)
        yield word + (" " if i < len(words) - 1 else "")


async def stream_with_fallback(
    models: list[str],
    query: str,
    context_chunks: list[dict],
) -> tuple[AsyncIterator[str], StreamResult]:
    """Stream LLM response with fallback chain.

    Returns (token_iterator, result_tracker).
    The caller should iterate the token_iterator and read final stats from result_tracker.
    """
    result = StreamResult()

    # Build the prompt
    context_text = "\n\n---\n\n".join(
        f"[Chunk {c['id']}]: {c['text']}" for c in context_chunks
    )
    full_prompt = SYSTEM_PROMPT.format(context=context_text, query=query)

    # Estimate input tokens (~4 chars per token)
    result.input_tokens = max(1, len(full_prompt) // 4)

    if USE_MOCK:
        result.model_used = "mock/local"

        async def mock_gen():
            start = time.monotonic()
            first_token = True
            async for token in _stream_mock(full_prompt):
                if first_token:
                    result.ttft_ms = round((time.monotonic() - start) * 1000)
                    first_token = False
                result.full_text += token
                result.output_tokens += 1
                yield token
            result.total_ms = round((time.monotonic() - start) * 1000)

        return mock_gen(), result

    # Real LLM call with fallback chain
    last_error: Exception | None = None

    for i, model in enumerate(models):
        circuit = _get_circuit(model)

        # Skip if circuit breaker is open
        if circuit.is_open():
            continue

        result.model_used = model
        result.fallback_used = i > 0

        try:
            client = get_client()
            start = time.monotonic()

            stream = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": full_prompt.split("<user_query>")[0]},
                        {"role": "user", "content": query},
                    ],
                    stream=True,
                    max_tokens=500,
                    temperature=0.3,
                ),
                timeout=LLM_TIMEOUT,
            )

            async def real_gen(stream=stream, start=start, model=model, circuit=circuit):
                first_token = True
                try:
                    async for chunk in stream:
                        delta = chunk.choices[0].delta.content if chunk.choices else None
                        if delta:
                            if first_token:
                                result.ttft_ms = round((time.monotonic() - start) * 1000)
                                first_token = False
                            result.full_text += delta
                            result.output_tokens += 1
                            yield delta
                    result.total_ms = round((time.monotonic() - start) * 1000)
                    circuit.record_success()
                except Exception:
                    result.total_ms = round((time.monotonic() - start) * 1000)
                    circuit.record_failure()
                    raise

            return real_gen(), result

        except asyncio.TimeoutError:
            circuit.record_failure()
            last_error = TimeoutError(f"Timeout after {LLM_TIMEOUT}s for {model}")
            continue
        except APIStatusError as e:
            if e.status_code in NON_RETRYABLE_CODES:
                raise  # Don't fallback on client errors
            circuit.record_failure()
            last_error = e
            continue
        except Exception as e:
            circuit.record_failure()
            last_error = e
            continue

    # All models failed
    raise RuntimeError(
        f"All models in fallback chain failed. Last error: {last_error}"
    )
