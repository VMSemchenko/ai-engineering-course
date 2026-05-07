"""
Supply Chain Multi-Agent Demo — Streamlit UI.

Запуск:
  streamlit run app.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import streamlit as st  # noqa: E402

from data.fixtures import get_part, list_parts  # noqa: E402
from src.graph.baseline import run_baseline  # noqa: E402
from src.graph.crew import graph_mermaid, run_crew  # noqa: E402
from src.judge import judge_plans  # noqa: E402
from src.viz import render_flow  # noqa: E402

st.set_page_config(page_title="Supply Chain Multi-Agent Demo", layout="wide")

st.title("✈️ Aerospace Supply Chain — Multi-Agent Demo")
st.caption(
    "Demo для lesson 11. Multi-agent crew (LangGraph) vs single-agent baseline. "
    "OpenRouter + Gemini 2.0 Flash."
)

with st.expander("📋 Бізнес-контекст і навіщо це потрібно", expanded=True):
    col_a, col_b = st.columns([2, 1])

    with col_a:
        st.markdown(
            """
### Проблема
В **аерокосмічних компаніях** (Boeing, Airbus, Safran) procurement-команда
(відділ закупівель — фахівці що замовляють деталі у постачальників, домовляються
про ціни, контракти, terms і дбають щоб виробництво не зупинилось через брак комплектуючих)
щодня отримує сотні запитів типу _"скільки замовити деталі X на наступний квартал?"_

Щоб дати відповідь, фахівець має:
1. Прогнозувати **попит** (planning department)
2. Перевірити **запаси** на 5+ складах (inventory management)
3. З'ясувати **умови постачання** від supplier (procurement)
4. Синтезувати все у **procurement plan** з ризиками і термінами

Ціна помилки висока: один turbine blade коштує **$18 500**, lead time **90 днів**.
Замовиш мало — зупиниш виробництво літака. Замовиш багато — заморозиш капітал.

### Рішення — multi-agent crew
Кожен крок виконує **спеціалізований AI-агент** з власним tool-set.
Координація через **LangGraph**: router класифікує запит, workers виконуються
паралельно, synthesizer будує фінальний план.
"""
        )

    with col_b:
        st.markdown(
            """
### Реальні приклади (з індустрії)

🏦 **JPMorgan DeepX**
Multi-agent для investment recommendations
(macro + sector + company analysts)

📦 **DHL Routes**
Truck-як-агент → −15% fuel costs

🛒 **Ocado**
2,000+ robot agents у warehouse
→ +50% order fulfilment

📊 **Gartner**
75% великих компаній впровадять
MAS до 2026 року

💰 **BCG**
$53B market revenue з MAS
до 2030 ($5.7B → $53B)
"""
        )

    st.info(
        "💡 **Що показує демка:** crew з 5 агентів (router + 3 workers + synthesizer) "
        "vs один універсальний агент. Ми побачимо у яких сценаріях multi-agent виграє "
        "(складні з disruption / спеціалізацією) і де програє (прості stat-запити, де overhead не виправданий)."
    )

    st.markdown("### 🏗 Архітектура crew")
    render_flow(
        active_workers=["forecaster", "inventory", "delivery"],
        route_decision="full",
    )

    st.markdown(
        """
**3 паттерни Anthropic Building Effective Agents у одному графі:**

| Паттерн | Де у демці |
|---------|------------|
| **Routing** | router_agent класифікує запит → conditional edges пропускають непотрібних workers |
| **Parallelization (Sectioning)** | вибрані workers запускаються одночасно |
| **Orchestrator-Workers** | synthesizer агрегує висновки workers у фінальний plan |
"""
    )

QUERY_TYPES = {
    "Повний procurement plan": "Full procurement plan — потрібні всі дані",
    "Тільки прогноз попиту": "Що буде з попитом наступного кварталу?",
    "Тільки запаси і постачання": "Чи є достатньо запасів і коли треба замовляти?",
    "Тільки про disruption / постачальника": "Чи є проблеми з постачальником?",
}

with st.sidebar:
    st.header("Параметри запиту")
    part_id = st.selectbox("Деталь", list_parts(), index=0)
    quarter = st.text_input("Квартал", value="Q2-2026")
    query_label = st.selectbox("Тип запиту (для router)", list(QUERY_TYPES.keys()), index=0)
    query_type = QUERY_TYPES[query_label]

    st.markdown("---")
    st.subheader("Архітектура")
    arch = st.radio(
        "Що запустити",
        options=["Crew (multi-agent)", "Baseline (single agent)", "Обидві паралельно"],
        index=2,
    )

    with st.expander("ℹ️ У чому різниця?", expanded=False):
        st.markdown(
            """
**🤝 Crew (multi-agent)**
5 агентів зі спеціалізацією:
router → 3 workers паралельно → synthesizer.
Кожен має свій system prompt і набір tools.

- ✅ Спеціалізація → краща якість на складних задачах
- ✅ Routing економить compute на простих запитах
- ✅ Workers паралельні → менше wall time
- ❌ Більше токенів (context-passing)
- ❌ Більше latency для простих кейсів

**🤖 Baseline (single agent)**
Один агент з усіма 3 tools, послідовний tool-use loop.

- ✅ Менше токенів (один контекст)
- ✅ Дешевший на простих кейсах
- ✅ Простіший дебаг
- ❌ Tools викликаються послідовно
- ❌ Без спеціалізації — один промпт на все

**📊 Обидві паралельно**
Запускає обидві архітектури з однаковим запитом.
Знизу — таблиця порівняння cost / tokens / wall time.
Найкорисніший режим — видно тradeoff на цифрах.
"""
        )

    st.markdown("---")
    st.subheader("Структура crew")
    with st.expander("Граф LangGraph", expanded=False):
        st.code(graph_mermaid(), language="text")

    run_btn = st.button("▶ Запустити", type="primary", use_container_width=True)


def render_result(col, label: str, result: dict, elapsed: float) -> None:
    with col:
        st.subheader(label)
        usage = result["usage"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Cost", f"${usage.cost_usd:.5f}")
        c2.metric("Tokens", f"{usage.input_tokens + usage.output_tokens:,}")
        c3.metric("LLM calls", usage.calls)
        c4.metric("Wall time", f"{elapsed:.1f}s")

        if result["architecture"] == "crew" and result.get("route_decision"):
            st.success(f"Router decision: **{result['route_decision']}**")

            active = []
            if result.get("forecast"):
                active.append("forecaster")
            if result.get("inventory"):
                active.append("inventory")
            if result.get("delivery"):
                active.append("delivery")

            st.markdown("**Реальний флоу цього запуску:**")
            render_flow(
                active_workers=active,
                route_decision=result["route_decision"],
            )

        st.markdown("**Final plan:**")
        st.write(result["final_plan"])

        with st.expander("Деталі — intermediate results", expanded=False):
            if result["architecture"] == "crew":
                if result.get("forecast"):
                    st.markdown("**Forecaster:**")
                    st.write(result["forecast"]["answer"])
                    st.json(result["forecast"]["tool_calls"], expanded=False)
                else:
                    st.caption("Forecaster — пропущено router-ом")

                if result.get("inventory"):
                    st.markdown("**Inventory:**")
                    st.write(result["inventory"]["answer"])
                    st.json(result["inventory"]["tool_calls"], expanded=False)
                else:
                    st.caption("Inventory — пропущено router-ом")

                if result.get("delivery"):
                    st.markdown("**Delivery:**")
                    st.write(result["delivery"]["answer"])
                    st.json(result["delivery"]["tool_calls"], expanded=False)
                else:
                    st.caption("Delivery — пропущено router-ом")
            else:
                st.markdown("**Tool calls (sequential):**")
                st.json(result.get("tool_calls", []), expanded=False)

        with st.expander("Cost breakdown by agent", expanded=False):
            st.json(usage.by_agent)


if run_btn:
    st.markdown("---")

    if arch == "Crew (multi-agent)":
        with st.spinner("Запускаю multi-agent crew..."):
            t0 = time.time()
            crew_result = run_crew(part_id, quarter, query_type=query_type)
            elapsed = time.time() - t0
        render_result(st.container(), "Multi-agent crew (LangGraph)", crew_result, elapsed)

    elif arch == "Baseline (single agent)":
        with st.spinner("Запускаю single-agent baseline..."):
            t0 = time.time()
            baseline_result = run_baseline(part_id, quarter)
            elapsed = time.time() - t0
        render_result(st.container(), "Single-agent baseline", baseline_result, elapsed)

    else:
        col1, col2 = st.columns(2)
        with st.spinner("Запускаю обидві архітектури..."):
            t0 = time.time()
            crew_result = run_crew(part_id, quarter, query_type=query_type)
            crew_elapsed = time.time() - t0

            t0 = time.time()
            baseline_result = run_baseline(part_id, quarter)
            baseline_elapsed = time.time() - t0

        render_result(col1, "Multi-agent crew (LangGraph)", crew_result, crew_elapsed)
        render_result(col2, "Single-agent baseline", baseline_result, baseline_elapsed)

        st.markdown("---")
        st.subheader("Порівняння")
        crew_u = crew_result["usage"]
        base_u = baseline_result["usage"]
        comparison = {
            "Crew": {
                "cost_usd": round(crew_u.cost_usd, 5),
                "tokens": crew_u.input_tokens + crew_u.output_tokens,
                "llm_calls": crew_u.calls,
                "wall_time_s": round(crew_elapsed, 2),
            },
            "Baseline": {
                "cost_usd": round(base_u.cost_usd, 5),
                "tokens": base_u.input_tokens + base_u.output_tokens,
                "llm_calls": base_u.calls,
                "wall_time_s": round(baseline_elapsed, 2),
            },
            "Crew_vs_Baseline": {
                "cost_ratio": round(crew_u.cost_usd / max(base_u.cost_usd, 1e-9), 2),
                "tokens_ratio": round(
                    (crew_u.input_tokens + crew_u.output_tokens)
                    / max(base_u.input_tokens + base_u.output_tokens, 1),
                    2,
                ),
                "wall_time_ratio": round(crew_elapsed / max(baseline_elapsed, 0.001), 2),
            },
        }
        st.json(comparison)

        st.markdown("---")
        st.subheader("🧑‍⚖️ Quality assessment (LLM-as-judge)")
        st.caption(
            "Окремий LLM (не той що генерував плани) оцінює обидва за 4 критеріями (0-10): "
            "groundedness, structure, completeness, actionability."
        )

        with st.spinner("Judge оцінює якість планів..."):
            try:
                judge_result = judge_plans(
                    part_id=part_id,
                    facts=get_part(part_id),
                    plan_a=crew_result["final_plan"],
                    plan_b=baseline_result["final_plan"],
                    plan_a_label="Multi-agent crew",
                    plan_b_label="Single-agent baseline",
                )
            except Exception as exc:
                st.error(f"Judge не зміг оцінити: {exc}")
                judge_result = None

        if judge_result is not None:
            j_col1, j_col2, j_col3 = st.columns([1, 1, 1])

            crew_total = judge_result.plan_a_total
            base_total = judge_result.plan_b_total or 0
            delta = crew_total - base_total

            j_col1.metric(
                "Crew total",
                f"{crew_total}/40",
                delta=f"{delta:+d} vs baseline" if delta != 0 else "tie",
            )
            j_col2.metric(
                "Baseline total",
                f"{base_total}/40",
                delta=f"{-delta:+d} vs crew" if delta != 0 else "tie",
            )

            winner_emoji = {"a": "🏆 Crew", "b": "🏆 Baseline", "tie": "🤝 Tie"}
            j_col3.metric("Winner", winner_emoji.get(judge_result.winner, "—"))

            # Per-criterion breakdown з reasoning
            for key in ["groundedness", "structure", "completeness", "actionability"]:
                crew_val = judge_result.plan_a_scores.get(key, 0)
                base_val = (judge_result.plan_b_scores or {}).get(key, 0)
                crew_reason = judge_result.plan_a_reasons.get(key, "")
                base_reason = (judge_result.plan_b_reasons or {}).get(key, "")
                diff = crew_val - base_val
                arrow = "🟢" if diff > 0 else ("🔴" if diff < 0 else "⚪")
                winner_label = (
                    "Crew виграв" if diff > 0
                    else ("Baseline виграв" if diff < 0 else "tie")
                )

                with st.expander(
                    f"**{key}** — Crew **{crew_val}/10** vs Baseline **{base_val}/10**  {arrow}  ({winner_label})",
                    expanded=True,
                ):
                    rc1, rc2 = st.columns(2)
                    with rc1:
                        st.markdown(f"**🤝 Crew ({crew_val}/10)**")
                        st.caption(crew_reason or "—")
                    with rc2:
                        st.markdown(f"**🤖 Baseline ({base_val}/10)**")
                        st.caption(base_reason or "—")

            # Weaknesses summary
            if judge_result.baseline_weaknesses or judge_result.crew_weaknesses:
                w_col1, w_col2 = st.columns(2)
                with w_col1:
                    st.markdown("**🔻 Crew weaknesses**")
                    if judge_result.crew_weaknesses:
                        for w in judge_result.crew_weaknesses:
                            st.markdown(f"- {w}")
                    else:
                        st.caption("Не виявлено")
                with w_col2:
                    st.markdown("**🔻 Baseline weaknesses**")
                    if judge_result.baseline_weaknesses:
                        for w in judge_result.baseline_weaknesses:
                            st.markdown(f"- {w}")
                    else:
                        st.caption("Не виявлено")

            st.info(f"**Verdict:** {judge_result.verdict}")

            with st.expander("Raw judge response", expanded=False):
                st.code(judge_result.raw_response, language="json")

            # Cost-quality tradeoff insight
            crew_cost = crew_result["usage"].cost_usd
            base_cost = baseline_result["usage"].cost_usd
            if crew_cost > base_cost and crew_total <= base_total:
                st.warning(
                    f"⚠️ **Anti-pattern:** Crew коштував у {crew_cost / max(base_cost, 1e-9):.1f}× більше "
                    f"({crew_cost:.5f} vs {base_cost:.5f}), але якість **не вища** ({crew_total} vs {base_total}/40). "
                    "Multi-agent overhead не виправданий на цьому кейсі."
                )
            elif crew_total > base_total and crew_cost > base_cost:
                ratio = (crew_total - base_total) / max(crew_cost - base_cost, 1e-9) * 1000
                st.success(
                    f"✅ Crew виграв у якості (+{crew_total - base_total} балів) "
                    f"коштом +${crew_cost - base_cost:.5f}. "
                    f"Це {ratio:.0f} балів на $0.001 — сам вирішуй чи виправдано."
                )

        st.info(
            "Питання для обговорення на парі: чи виправдане multi-agent ускладнення "
            "для цієї задачі? Дивися cost_ratio, wall_time_ratio і quality scores. "
            "На простих кейсах (BOLT-X12) baseline зазвичай дешевший, швидший і не гірший за якістю. "
            "На складних (COMPOSITE-K9 з disruption) crew частіше виграє завдяки спеціалізації агентів."
        )
else:
    st.info(
        "Обери деталь і квартал у сайдбарі і натисни **Запустити**. "
        "Спробуй усі 3 деталі — у них різні патерни:\n\n"
        "- **TURBINE-A37** — high demand growth, low inventory → треба багато замовляти\n"
        "- **BOLT-X12** — overstock, demand стабільний → не замовляти\n"
        "- **COMPOSITE-K9** — supply chain disruption → замовляти раніше"
    )
