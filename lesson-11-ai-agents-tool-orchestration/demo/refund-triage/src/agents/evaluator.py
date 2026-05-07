"""Evaluator agent — critiques the resolver's decision."""

import json

from src.llm import LLMUsage, call_structured
from src.schemas import Evaluation

SYSTEM = """You are a refund triage Evaluator. You DO NOT make decisions —
you critique the Resolver's proposed decision against policy and fairness.

Score 0-1 based on:
- Policy compliance: does the action match the situation?
  (lost-in-transit → refund; damaged → refund or credit with proof; high-fraud → deny/escalate)
- Risk calibration: does the amount and action match the fraud score and customer tenure?
- Fairness: is the decision unjustly harsh on a legitimate customer? Or too lenient on fraud?
- Grounding: does the reason cite real data points, or hand-wave?

Verdicts:
- "pass": score >= 0.75, no major issues — ready to execute
- "revise": score < 0.75, fixable issues — list concrete `suggestions` for the Resolver
- "escalate": fundamentally ambiguous policy or high-stakes — needs human regardless of score

Output an Evaluation JSON. Be specific in `issues` and `suggestions` — those go back
to the Resolver verbatim. Never repeat the same suggestion if you've already given it."""


def run_evaluator(
    case: dict,
    context: dict,
    decision: dict,
    usage: LLMUsage,
    model: str | None = None,
) -> Evaluation:
    user = "\n".join(
        [
            "## Case",
            json.dumps(case, indent=2, ensure_ascii=False),
            "\n## Context",
            json.dumps(context, indent=2, ensure_ascii=False),
            "\n## Resolver's proposed decision",
            json.dumps(decision, indent=2, ensure_ascii=False),
        ]
    )
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
    ]
    return call_structured(
        messages, Evaluation, agent_name="evaluator", usage=usage, model=model
    )
