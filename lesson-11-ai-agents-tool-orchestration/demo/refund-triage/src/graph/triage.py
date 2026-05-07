"""LangGraph wiring — evaluator-optimizer loop + HITL interrupt before execute."""

from __future__ import annotations

import time

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.agents.evaluator import run_evaluator
from src.agents.resolver import run_resolver
from src.llm import LLMUsage
from src.schemas import TriageState
from src.tools.execute import issue_refund
from src.tools.lookup import get_fraud_signals, lookup_customer, lookup_order

MAX_RETRIES = 2
EVALUATOR_THRESHOLD = 0.75
AUTO_APPROVE_AMOUNT = 100
AUTO_APPROVE_RISK = 0.30


def _trace(state: TriageState, node: str, payload: dict, ms: int) -> list[dict]:
    entry = {"node": node, "ms": ms, "payload": payload, "ts": time.time()}
    return [*state.get("trace", []), entry]


def fetch_context(state: TriageState, *, usage: LLMUsage) -> dict:
    start = time.time()
    case = state["case"]
    context = {
        "customer": lookup_customer(case["customer_id"]),
        "order": lookup_order(case["order_id"]),
        "fraud": get_fraud_signals(case["customer_id"]),
    }
    ms = int((time.time() - start) * 1000)
    return {
        "context": context,
        "retries": 0,
        "trace": _trace(state, "fetch_context", context, ms),
    }


def resolver_node(state: TriageState, *, usage: LLMUsage, model: str | None) -> dict:
    start = time.time()
    decision = run_resolver(
        state["case"], state["context"], state.get("feedback"), usage, model=model
    )
    ms = int((time.time() - start) * 1000)
    payload = decision.model_dump()
    payload["_attempt"] = state.get("retries", 0) + 1
    return {
        "decision": decision.model_dump(),
        "trace": _trace(state, "resolver", payload, ms),
    }


def evaluator_node(state: TriageState, *, usage: LLMUsage, model: str | None) -> dict:
    start = time.time()
    evaluation = run_evaluator(
        state["case"], state["context"], state["decision"], usage, model=model
    )
    ms = int((time.time() - start) * 1000)
    return {
        "evaluation": evaluation.model_dump(),
        "trace": _trace(state, "evaluator", evaluation.model_dump(), ms),
    }


def route_after_evaluator(state: TriageState) -> str:
    """Three outcomes:
      - retry_resolver: evaluator failed, retries left
      - hitl_gate: needs human (escalate, max retries hit, or risky decision)
      - execute: passes auto-approve gate
    """
    evaluation = state["evaluation"]
    decision = state["decision"]
    retries = state.get("retries", 0)

    if evaluation["verdict"] == "escalate":
        return "hitl_gate"

    passed = (
        evaluation["score"] >= EVALUATOR_THRESHOLD
        and evaluation["policy_compliance"]
    )
    if not passed:
        if retries >= MAX_RETRIES:
            return "hitl_gate"
        return "retry_resolver"

    auto_ok = (
        decision["amount_usd"] < AUTO_APPROVE_AMOUNT
        and evaluation["risk_level"] < AUTO_APPROVE_RISK
        and decision["action"] != "deny"
    )
    return "execute" if auto_ok else "hitl_gate"


def retry_resolver_node(state: TriageState) -> dict:
    suggestions = state["evaluation"].get("suggestions", [])
    issues = state["evaluation"].get("issues", [])
    feedback_lines = []
    if issues:
        feedback_lines.append("Issues found:")
        feedback_lines.extend(f"- {i}" for i in issues)
    if suggestions:
        feedback_lines.append("Suggestions:")
        feedback_lines.extend(f"- {s}" for s in suggestions)
    feedback = "\n".join(feedback_lines) or "Improve the decision."
    return {
        "feedback": feedback,
        "retries": state.get("retries", 0) + 1,
        "trace": _trace(
            state,
            "retry",
            {"feedback": feedback, "attempt": state.get("retries", 0) + 1},
            0,
        ),
    }


def hitl_gate_node(state: TriageState) -> dict:
    decision = state["decision"]
    evaluation = state["evaluation"]
    payload = {
        "awaiting": "human_approval",
        "proposed_action": decision["action"],
        "amount_usd": decision["amount_usd"],
        "risk_level": evaluation["risk_level"],
        "evaluator_verdict": evaluation["verdict"],
        "issues": evaluation.get("issues", []),
    }
    return {"trace": _trace(state, "hitl_gate", payload, 0)}


def execute_node(state: TriageState) -> dict:
    case = state["case"]
    decision = state["decision"]
    review = state.get("human_review")

    action = decision["action"]
    amount = decision["amount_usd"]
    if review:
        if review["action"] == "reject":
            action = "deny"
            amount = 0
        elif review["action"] == "modify" and review.get("modified_amount_usd") is not None:
            amount = float(review["modified_amount_usd"])

    start = time.time()
    result = issue_refund(case["case_id"], amount, action)
    ms = int((time.time() - start) * 1000)

    final_status = (
        "auto_executed" if not review else f"human_{review['action']}_executed"
    )
    return {
        "refund_id": result["refund_id"],
        "final_status": final_status,
        "trace": _trace(state, "execute", result, ms),
    }


def build_graph(usage: LLMUsage, model: str | None = None):
    builder = StateGraph(TriageState)

    builder.add_node("fetch_context", lambda s: fetch_context(s, usage=usage))
    builder.add_node(
        "resolver", lambda s: resolver_node(s, usage=usage, model=model)
    )
    builder.add_node(
        "evaluator", lambda s: evaluator_node(s, usage=usage, model=model)
    )
    builder.add_node("retry_resolver", retry_resolver_node)
    builder.add_node("hitl_gate", hitl_gate_node)
    builder.add_node("execute", execute_node)

    builder.add_node("auto_execute", execute_node)

    builder.add_edge(START, "fetch_context")
    builder.add_edge("fetch_context", "resolver")
    builder.add_edge("resolver", "evaluator")

    builder.add_conditional_edges(
        "evaluator",
        route_after_evaluator,
        {
            "retry_resolver": "retry_resolver",
            "hitl_gate": "hitl_gate",
            "execute": "auto_execute",
        },
    )
    builder.add_edge("retry_resolver", "resolver")
    builder.add_edge("hitl_gate", "execute")
    builder.add_edge("auto_execute", END)
    builder.add_edge("execute", END)

    checkpointer = MemorySaver()
    return builder.compile(
        checkpointer=checkpointer, interrupt_before=["execute"]
    )
