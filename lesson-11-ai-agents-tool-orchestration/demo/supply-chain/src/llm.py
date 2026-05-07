"""
LLM-клієнт через OpenRouter.

Дешева модель (~$0.075 / $0.30 за M tokens у листопаді 2025) —
google/gemini-2.0-flash-001. Швидкий, недорогий, добре справляється з tool calling.
Можна замінити на анших дешевих:
  - openai/gpt-4o-mini  (~$0.15 / $0.60)
  - anthropic/claude-haiku-4.5 (~$1 / $5)
  - google/gemini-2.5-flash  (~$0.30 / $2.50)
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from openai import OpenAI

DEFAULT_MODEL = os.getenv("MODEL", "google/gemini-2.0-flash-001")


def get_client() -> OpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Скопіюй .env.example у .env і додай ключ "
            "(отримати на https://openrouter.ai/keys)."
        )
    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://github.com/andbilous/ai-engineering-course",
            "X-Title": "Supply Chain Multi-Agent Demo",
        },
    )


@dataclass
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    calls: int = 0
    by_agent: dict[str, dict] = field(default_factory=dict)

    def add(self, agent: str, input_t: int, output_t: int, cost: float, ms: int) -> None:
        self.input_tokens += input_t
        self.output_tokens += output_t
        self.cost_usd += cost
        self.duration_ms += ms
        self.calls += 1
        bucket = self.by_agent.setdefault(
            agent, {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0}
        )
        bucket["input_tokens"] += input_t
        bucket["output_tokens"] += output_t
        bucket["cost_usd"] += cost
        bucket["calls"] += 1


PRICING_USD_PER_M = {
    "google/gemini-2.0-flash-001": (0.075, 0.30),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "anthropic/claude-haiku-4.5": (1.0, 5.0),
    "google/gemini-2.5-flash": (0.30, 2.50),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    in_price, out_price = PRICING_USD_PER_M.get(model, (0.5, 1.5))
    return (input_tokens * in_price + output_tokens * out_price) / 1_000_000


def call_llm(
    messages: list[dict],
    *,
    agent_name: str,
    usage: LLMUsage,
    tools: list[dict] | None = None,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
):
    client = get_client()
    start = time.time()
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    response = client.chat.completions.create(**kwargs)
    duration_ms = int((time.time() - start) * 1000)

    in_t = response.usage.prompt_tokens if response.usage else 0
    out_t = response.usage.completion_tokens if response.usage else 0
    cost = estimate_cost(model, in_t, out_t)
    usage.add(agent_name, in_t, out_t, cost, duration_ms)

    return response
