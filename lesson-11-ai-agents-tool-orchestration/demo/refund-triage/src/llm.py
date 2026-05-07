"""LLM client through OpenRouter with structured-output helper."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

from openai import OpenAI
from pydantic import BaseModel, ValidationError

DEFAULT_MODEL = os.getenv("MODEL", "google/gemini-2.0-flash-001")


def get_client() -> OpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Скопіюй .env.example у .env і додай ключ "
            "(https://openrouter.ai/keys)."
        )
    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://github.com/andbilous/ai-engineering-course",
            "X-Title": "Refund Triage Demo",
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
    "google/gemini-2.0-flash-001": (0.10, 0.40),
    "meta-llama/llama-3.1-8b-instruct": (0.020, 0.050),
    "mistralai/mistral-nemo": (0.020, 0.030),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "anthropic/claude-haiku-4.5": (1.0, 5.0),
    "deepseek/deepseek-chat": (0.27, 1.10),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    in_price, out_price = PRICING_USD_PER_M.get(model, (0.5, 1.5))
    return (input_tokens * in_price + output_tokens * out_price) / 1_000_000


def call_structured(
    messages: list[dict],
    schema: type[BaseModel],
    *,
    agent_name: str,
    usage: LLMUsage,
    model: str | None = None,
    temperature: float = 0.2,
) -> BaseModel:
    """Call LLM, parse JSON response into the given Pydantic schema.

    Uses response_format={"type": "json_object"} which is broadly supported
    on OpenRouter. Schema is described in the system prompt.
    """
    model = model or DEFAULT_MODEL
    client = get_client()
    start = time.time()

    schema_hint = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    messages = [
        *messages,
        {
            "role": "system",
            "content": (
                f"Return ONLY a JSON object that matches this JSON Schema:\n{schema_hint}"
            ),
        },
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    duration_ms = int((time.time() - start) * 1000)

    in_t = response.usage.prompt_tokens if response.usage else 0
    out_t = response.usage.completion_tokens if response.usage else 0
    cost = estimate_cost(model, in_t, out_t)
    usage.add(agent_name, in_t, out_t, cost, duration_ms)

    raw = response.choices[0].message.content or "{}"
    try:
        return schema.model_validate_json(raw)
    except ValidationError as e:
        # Weak models sometimes return the JSON Schema instead of an instance.
        # One repair attempt with the validation error fed back.
        repair_messages = [
            *messages,
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": (
                    f"Your previous response failed schema validation:\n{e}\n\n"
                    "Return ONLY a JSON object with concrete VALUES that match "
                    "the schema (not the schema itself, not a description)."
                ),
            },
        ]
        response = client.chat.completions.create(
            model=model,
            messages=repair_messages,
            temperature=0,
            response_format={"type": "json_object"},
        )
        in_t2 = response.usage.prompt_tokens if response.usage else 0
        out_t2 = response.usage.completion_tokens if response.usage else 0
        usage.add(
            f"{agent_name}:repair",
            in_t2,
            out_t2,
            estimate_cost(model, in_t2, out_t2),
            0,
        )
        raw = response.choices[0].message.content or "{}"
        return schema.model_validate_json(raw)
