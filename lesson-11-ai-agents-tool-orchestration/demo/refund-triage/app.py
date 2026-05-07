"""Refund Triage Agent — Streamlit UI.

Layout: sidebar (case + controls) · main (live trace) · right (case JSON + HITL).
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

load_dotenv(os.path.join(ROOT, ".env"))

import streamlit as st  # noqa: E402

from data.fixtures import CASES, get_case  # noqa: E402
from src.graph.triage import (  # noqa: E402
    AUTO_APPROVE_AMOUNT,
    AUTO_APPROVE_RISK,
    EVALUATOR_THRESHOLD,
    MAX_RETRIES,
    build_graph,
)
from src.llm import DEFAULT_MODEL, LLMUsage  # noqa: E402
from src.viz import graph_for_case  # noqa: E402

st.set_page_config(
    page_title="Refund Triage Agent",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----- session init -----
if "thread_id" not in st.session_state:
    st.session_state.thread_id = uuid.uuid4().hex
if "usage" not in st.session_state:
    st.session_state.usage = LLMUsage()
if "graph" not in st.session_state:
    st.session_state.graph = build_graph(st.session_state.usage)
if "trace" not in st.session_state:
    st.session_state.trace = []
if "current_state" not in st.session_state:
    st.session_state.current_state = None
if "interrupted" not in st.session_state:
    st.session_state.interrupted = False
if "completed" not in st.session_state:
    st.session_state.completed = False
if "pending_input" not in st.session_state:
    st.session_state.pending_input = None


def reset_session() -> None:
    st.session_state.thread_id = uuid.uuid4().hex
    st.session_state.usage = LLMUsage()
    st.session_state.graph = build_graph(st.session_state.usage)
    st.session_state.trace = []
    st.session_state.current_state = None
    st.session_state.interrupted = False
    st.session_state.completed = False
    st.session_state.pending_input = None


# ----- sidebar -----
with st.sidebar:
    st.markdown("### 🛡️ Refund Triage Agent")
    st.caption("Lesson 11 · evaluator-optimizer + HITL")

    st.markdown("#### Case")
    case_labels = {c["case_id"]: c["label"] for c in CASES}
    case_id = st.radio(
        "Pick a refund case",
        list(case_labels.keys()),
        format_func=lambda cid: case_labels[cid],
        label_visibility="collapsed",
    )

    st.markdown("#### Settings")
    st.caption(f"Model: `{DEFAULT_MODEL}`")
    st.caption(
        f"Evaluator pass threshold: ≥ {EVALUATOR_THRESHOLD} · "
        f"Auto-approve: < ${AUTO_APPROVE_AMOUNT} & risk < {AUTO_APPROVE_RISK} · "
        f"Max retries: {MAX_RETRIES}"
    )

    col_a, col_b = st.columns(2)
    run_clicked = col_a.button("▶ Run case", type="primary", use_container_width=True)
    reset_clicked = col_b.button("↺ Reset", use_container_width=True)

    show_graph = st.checkbox("Show LangGraph diagram", value=True)
    if show_graph:
        st.markdown("##### Graph")
        st.code(
            "START → fetch_context → resolver → evaluator\n"
            "                            │\n"
            "       ┌─ retry ────────────┤\n"
            "       │                    ├─ execute (auto)\n"
            "       └────────────────────┴─ hitl_gate ⏸ → execute\n"
            "                                              │\n"
            "                                              ▼\n"
            "                                             END",
            language="text",
        )

if reset_clicked:
    reset_session()
    st.rerun()


# ----- helpers -----
NODE_LABELS = {
    "fetch_context": "📥 fetch_context",
    "resolver": "🧠 resolver",
    "evaluator": "🔍 evaluator",
    "retry": "↻ retry",
    "hitl_gate": "⏸ hitl_gate",
    "execute": "💸 execute",
}


def render_trace_entry(entry: dict) -> None:
    label = NODE_LABELS.get(entry["node"], entry["node"])
    suffix = f" · {entry['ms']}ms" if entry.get("ms") else ""
    with st.expander(f"{label}{suffix}", expanded=True):
        st.json(entry["payload"])


def render_trace(trace: list[dict]) -> None:
    if not trace:
        st.info("Press ▶ Run case to start.")
        return
    for entry in trace:
        render_trace_entry(entry)


# ----- header / project description -----
st.markdown("# 🛡️ Refund Triage Agent")

with st.expander("📖 Про проект — бізнес-контекст і архітектура", expanded=True):
    st.markdown(
        """
### Проблема
E-commerce компанія отримує **200+ refund requests на день**. Два крайні підходи провалюються:
- **100% manual review** — support 12+ годин розглядає кейси, CSAT падає, дорого
- **100% auto-approve** — швидко, але **$50K/місяць fraud losses**, abuse pattern

**Потрібен agent який сам сортує**: дрібні валідні case-и approve автоматично за секунди,
ризикові і великі — ескалює до людини з готовою аналітикою.

### Як це працює — два agentic patterns

**1. Evaluator-Optimizer loop** (replaces single-prompt agent)
- **Resolver** агент читає case + customer history + fraud signals → пропонує рішення
  (`approve_refund` / `approve_credit` / `deny` / `request_info`)
- **Evaluator** агент критикує це рішення по 4 осях: policy compliance, risk calibration,
  fairness до клієнта, grounding у фактах → видає score 0-1 + concrete suggestions
- Якщо `score < 0.75` → resolver переписує рішення з фідбеком (max 2 retries)
- Працює **краще ніж "1 промпт із усім"** бо два агенти з різними ролями ловлять помилки
  один одного: resolver схильний бути занадто м'яким, evaluator — занадто строгим, у
  парі дають калібровану відповідь

**2. Human-in-the-Loop через LangGraph interrupt**
- Граф **зупиняється перед `execute`** якщо `amount > $100` АБО `risk > 0.3` АБО
  evaluator сказав `verdict=escalate`
- LangGraph state checkpointed — людина бачить у UI пропозицію + критику + ризик-факти,
  вирішує: approve as-is / modify amount / reject
- Граф **продовжується** з рішенням людини — не нова сесія, той самий thread

### Технічний стек
- **LangGraph** — state machine з conditional edges і `interrupt_before=["execute"]`
- **Pydantic** — typed structured output (Decision, Evaluation), schema repair fallback
  на випадок якщо слабка модель верне JSON Schema замість instance
- **OpenRouter** — provider-agnostic LLM access; default `gemini-2.0-flash` ($0.10/M),
  swap-able на `llama-3.1-8b` ($0.020/M) для side-by-side якості
- **Streamlit** — live trace, HITL approval panel з resume через `graph.update_state()`
- **MemorySaver** checkpointer — interrupt/resume у межах сесії

### Cost & latency
~$0.0002 за case на gemini-flash, ~3-15с end-to-end. Один прогон 4 кейсів — $0.0008.
        """
    )

with st.expander("📋 Refund cases — детальний опис що демонструє кожен", expanded=False):
    st.markdown(
        """
### RF-001 · Lost package · $45 — happy path

**Customer C-1001:** John Doe, 3.4 роки tenure, 47 ордерів, 2 refunds, $2,840 LTV. Fraud score 0.05, no flags.
**Order O-9001:** Wireless mouse, $45, shipped 14 днів тому, carrier marked "lost in transit".
**Reason:** "Package marked as lost by carrier 14 days ago. Never received."

**Очікувана поведінка:**
1. Resolver → `approve_refund $45` (carrier confirmation + clean customer = clear case)
2. Evaluator → `score 1.0, risk 0.05, verdict=pass` (зразкова валідна заявка)
3. Auto-approve gate: amount $45 < $100 ✓, risk 0.05 < 0.3 ✓, action ≠ deny ✓
4. **Auto-execute, no HITL** — refund issued за ~3 секунди

**Урок:** показує що дрібні очевидні case-и не повинні турбувати людину.

---

### RF-002 · Damaged item · $320 — possible retry loop → HITL

**Customer C-1002:** Maria Schmidt, 0.2 роки tenure (1 ордер), 0 refunds. Fraud 0.20, flag: `new_account`.
**Order O-9002:** Ceramic vase set, $320, delivered 5 днів тому.
**Reason:** "Vase arrived broken. No photo provided initially. New customer."

**Очікувана поведінка:**
1. Resolver спочатку може запропонувати `request_info` (попросити фото) або `approve_credit` обережно
2. Evaluator може **завалити** перше рішення з issues: "new customer + no photo asked = unfair denial"
   → suggestions: "ask for photo before deny" або "approve credit з низьким risk"
3. Resolver переписує з фідбеком → `approve_credit $320` або `request_info`
4. Amount $320 > $100 → **HITL pause**, людина дивиться trade-off:
   policy суворіша до новачків vs CSAT для legitimate damage claim

**Урок:** evaluator-loop ловить "ноль-toleranceдо новачків" = unfair pattern. HITL для borderline-сум.

---

### RF-003 · "Not as described" · $1,200 — direct HITL (high fraud)

**Customer C-1003:** Alex Petrov, 0.1 року tenure, 6 ордерів, **5 refunds** (83% refund rate),
$1,200 LTV. Fraud score **0.78** з 4 flags: `new_account_under_60d`, `5_refunds_in_30d`,
`high_value_disputes`, `ip_geolocation_mismatch`.
**Order O-9003:** Designer handbag, $1,200, delivered 8 днів тому.
**Reason:** "Customer claims handbag is not as described. High refund history."

**Очікувана поведінка:**
1. Resolver має fraud signals → `deny $0` з reason що цитує fraud score 0.78 і pattern
   "5 refunds в 6 ордерах від new account"
2. Evaluator → `risk_level 0.90, score 0.85-0.95, verdict=pass` (deny відповідає policy)
3. **HITL pause** — навіть валідний deny на $1,200 не виконується автоматично
4. Людина у UI бачить: пропозиція deny + всі fraud flags + customer history → confirms reject

**Урок:** high-stakes рішення (особливо `deny` на велику суму) завжди потребують людського
підпису — навіть якщо AI правий, юридично і репутаційно це має бути людина.

---

### RF-004 · Subscription dispute · $89 — edge case з policy ambiguity

**Customer C-1004:** Sara Lee, 2.1 роки tenure, 18 ордерів, 1 refund. Fraud 0.35, flags:
`expired_card_on_file`, **`policy_unclear`** (annual auto-renewal disputes — gray area).
**Order O-9004:** Streaming subscription (annual), $89, charged 32 днів тому, digital.
**Reason:** "Customer disputes annual renewal charge. Card on file expired."

**Очікувана поведінка:**
1. Resolver → можливо `approve_credit $89` (хороша tenure + амбівалентна policy)
2. Evaluator може `verdict=escalate` напряму через `policy_unclear` flag — або loop-ити
   через "policy unclear" як issue, до `max_retries=2`
3. Forced HITL — приклад де evaluator-loop не сходиться (policy сама по собі неоднозначна)

**Урок:** не всі problems вирішує "більше промптів" — деякі потребують policy update від
людини. Max retries + escalate verdict рятують від нескінченного loop-а.
        """
    )

st.markdown(f"### Expected execution path for **{case_id}**")
st.caption(
    "Підсвічений шлях — куди граф піде на цьому кейсі. "
    "🟢 active edge · 🔵 always-on prefix · 🟠 retry branch · 🔴 HITL branch · сірі — alternate paths."
)
graph_col, _ = st.columns([0.33, 0.67])
with graph_col:
    st.graphviz_chart(graph_for_case(case_id), use_container_width=True)

st.markdown("---")

# ----- main layout -----
left, right = st.columns([0.62, 0.38])

with left:
    st.markdown("## Agent Trace")
    trace_container = st.container()

with right:
    st.markdown("## Case")
    case_data = get_case(case_id)
    st.json(case_data)

    st.markdown("## HITL Panel")
    hitl_container = st.container()


# ----- run logic -----
def run_until_pause_or_end(graph, config: dict) -> dict:
    """Step the graph until interrupt or completion. Returns final state snapshot."""
    last_state = None
    for chunk in graph.stream(
        st.session_state.pending_input or None,
        config=config,
        stream_mode="values",
    ):
        last_state = chunk
        new_trace = chunk.get("trace", [])
        if len(new_trace) > len(st.session_state.trace):
            st.session_state.trace = new_trace
    st.session_state.pending_input = None
    return last_state or graph.get_state(config).values


if run_clicked and not st.session_state.interrupted:
    reset_session()
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    st.session_state.pending_input = {"case": case_data, "trace": []}
    with st.spinner("Running…"):
        run_until_pause_or_end(st.session_state.graph, config)
    snapshot = st.session_state.graph.get_state(config)
    st.session_state.current_state = snapshot
    st.session_state.interrupted = bool(snapshot.next) and "execute" in snapshot.next
    st.session_state.completed = not snapshot.next
    st.rerun()


# ----- render trace -----
with trace_container:
    render_trace(st.session_state.trace)
    if st.session_state.completed:
        last = st.session_state.trace[-1] if st.session_state.trace else {}
        st.success(
            f"✓ Completed · final_status: "
            f"{last.get('payload', {}).get('status', '?')} · "
            f"refund_id: {last.get('payload', {}).get('refund_id', '?')}"
        )
    elif st.session_state.interrupted:
        st.warning("⏸ Paused — awaiting human approval (see right panel)")


# ----- HITL panel -----
with hitl_container:
    if st.session_state.interrupted and st.session_state.current_state is not None:
        snap_values = st.session_state.current_state.values
        decision = snap_values.get("decision", {})
        evaluation = snap_values.get("evaluation", {})

        st.error(f"**Proposed:** `{decision.get('action')}` · ${decision.get('amount_usd', 0):.2f}")
        st.caption(decision.get("reason", ""))
        st.markdown(
            f"**Evaluator score:** {evaluation.get('score', 0):.2f} · "
            f"**Risk:** {evaluation.get('risk_level', 0):.2f} · "
            f"**Verdict:** `{evaluation.get('verdict', '?')}`"
        )
        if evaluation.get("issues"):
            st.markdown("**Flagged issues:**")
            for i in evaluation["issues"]:
                st.markdown(f"- {i}")

        action_choice = st.radio(
            "Your decision",
            ["approve_as_is", "modify", "reject"],
            format_func=lambda x: {
                "approve_as_is": "✓ Approve as-is",
                "modify": "✎ Modify amount",
                "reject": "✗ Reject (deny refund)",
            }[x],
        )
        modified_amount = None
        if action_choice == "modify":
            modified_amount = st.number_input(
                "Modified amount (USD)",
                min_value=0.0,
                value=float(decision.get("amount_usd", 0)),
                step=10.0,
            )
        notes = st.text_area("Reviewer notes", value="", height=70)

        if st.button("Submit decision", type="primary", use_container_width=True):
            review = {
                "action": action_choice,
                "modified_amount_usd": modified_amount,
                "reviewer_notes": notes,
            }
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            st.session_state.graph.update_state(config, {"human_review": review})
            st.session_state.pending_input = None
            with st.spinner("Resuming graph…"):
                for chunk in st.session_state.graph.stream(
                    None, config=config, stream_mode="values"
                ):
                    new_trace = chunk.get("trace", [])
                    if len(new_trace) > len(st.session_state.trace):
                        st.session_state.trace = new_trace
            snapshot = st.session_state.graph.get_state(config)
            st.session_state.current_state = snapshot
            st.session_state.interrupted = False
            st.session_state.completed = not snapshot.next
            st.rerun()
    else:
        st.info("No approval pending.")


# ----- footer metrics -----
usage = st.session_state.usage
st.markdown("---")
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Latency", f"{usage.duration_ms / 1000:.1f}s")
m2.metric("Tokens", f"{usage.input_tokens + usage.output_tokens:,}")
m3.metric("Cost", f"${usage.cost_usd:.4f}")
retries_count = sum(1 for e in st.session_state.trace if e["node"] == "retry")
m4.metric("Retries", str(retries_count))
hitl_hit = any(e["node"] == "hitl_gate" for e in st.session_state.trace)
m5.metric("HITL", "✅" if hitl_hit else "❌")
