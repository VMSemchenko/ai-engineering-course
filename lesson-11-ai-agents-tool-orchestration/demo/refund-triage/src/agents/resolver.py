"""Resolver agent — proposes a refund decision based on context."""

import json

from src.llm import LLMUsage, call_structured
from src.schemas import Decision

SYSTEM = """You are a refund triage Resolver for an e-commerce platform.

Policy:
- approve_refund: full refund to original payment method (lost/damaged/never delivered)
- approve_credit: store credit (when refund is justified but fraud signals are mild,
  or item was used; new/low-tenure customers default to credit when in doubt)
- deny: no refund (clear policy violation, fraud signals high, abuse pattern)
- request_info: need photos/receipts before deciding (use sparingly — only if data is missing)

Be fair: balance customer empathy with fraud risk. Ground every decision in the data
(tenure, fraud score, carrier status). Never invent facts.

Output a Decision JSON. Keep `reason` to 1-2 sentences citing concrete data points."""


def run_resolver(
    case: dict,
    context: dict,
    feedback: str | None,
    usage: LLMUsage,
    model: str | None = None,
) -> Decision:
    user_parts = [
        "## Refund case",
        json.dumps(case, indent=2, ensure_ascii=False),
        "\n## Context (from tools)",
        json.dumps(context, indent=2, ensure_ascii=False),
    ]
    if feedback:
        user_parts.extend(
            [
                "\n## Evaluator feedback on your previous decision",
                feedback,
                "\nRevise your decision addressing every issue above.",
            ]
        )

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "\n".join(user_parts)},
    ]
    return call_structured(
        messages, Decision, agent_name="resolver", usage=usage, model=model
    )
