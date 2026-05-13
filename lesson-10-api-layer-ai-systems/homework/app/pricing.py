"""Model pricing — single source of truth for cost calculation.

Prices in USD per 1M tokens, sourced from OpenRouter.
"""

PRICING: dict[str, dict[str, float]] = {
    # ── Free models ──────────────────────────────────────────
    "meta-llama/llama-3.1-8b-instruct:free": {
        "input": 0.0,
        "output": 0.0,
    },
    "meta-llama/llama-3.2-3b-instruct:free": {
        "input": 0.0,
        "output": 0.0,
    },
    # ── Paid models ──────────────────────────────────────────
    "meta-llama/llama-3.1-8b-instruct": {
        "input": 0.02,
        "output": 0.05,
    },
    "mistralai/mistral-nemo": {
        "input": 0.02,
        "output": 0.03,
    },
    "google/gemma-3-4b-it": {
        "input": 0.04,
        "output": 0.08,
    },
    "google/gemini-flash-1.5-8b": {
        "input": 0.0375,
        "output": 0.15,
    },
    "openai/gpt-4o-mini": {
        "input": 0.15,
        "output": 0.60,
    },
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD for a given model and token counts."""
    prices = PRICING.get(model, {"input": 0.0, "output": 0.0})
    cost = (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000
    return round(cost, 8)
