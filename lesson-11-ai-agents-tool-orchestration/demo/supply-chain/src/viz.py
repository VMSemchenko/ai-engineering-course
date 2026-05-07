"""
Візуалізація флоу агентів через native Streamlit-компоненти —
картки зі стрілками, без SVG/HTML-анімації.
"""
from __future__ import annotations

import streamlit as st


AGENT_INFO: dict[str, dict] = {
    "user": {
        "emoji": "👤", "name": "User", "sub": "input query", "color": "#475569",
        "task": "Надає запит у природній мові: яка деталь, який квартал, який тип аналізу потрібен.",
        "tools": [],
    },
    "router": {
        "emoji": "🧭", "name": "Router", "sub": "classifier", "color": "#0ea5e9",
        "task": "Класифікує тип запиту та вирішує, яких саме workers залучити, щоб не платити за зайві LLM-виклики.",
        "tools": ["LLM classifier (Gemini Flash)"],
    },
    "forecaster": {
        "emoji": "📈", "name": "Forecaster", "sub": "demand analyst", "color": "#f59e0b",
        "task": "Прогнозує попит на деталь у вказаному кварталі: low/expected/high, тренд, drivers.",
        "tools": ["forecast_demand(part_id, quarter)"],
    },
    "inventory": {
        "emoji": "📦", "name": "Inventory", "sub": "stock manager", "color": "#10b981",
        "task": "Перевіряє поточні запаси по складах, порівнює з safety stock, рахує дефіцит/профіцит.",
        "tools": ["check_inventory(part_id)"],
    },
    "delivery": {
        "emoji": "🚚", "name": "Delivery", "sub": "procurement spec", "color": "#ec4899",
        "task": "Аналізує supplier: lead time, MOQ, надійність. Обовʼязково підіймає disruption_alert якщо є.",
        "tools": ["optimize_delivery(part_id)"],
    },
    "synthesizer": {
        "emoji": "🧩", "name": "Synthesizer", "sub": "orchestrator", "color": "#8b5cf6",
        "task": "Збирає висновки workers і будує фінальний procurement plan з числами, термінами, ризиками.",
        "tools": [],
    },
    "result": {
        "emoji": "📋", "name": "Plan", "sub": "final output", "color": "#475569",
        "task": "Структурований procurement plan: чи замовляти, скільки, коли, які ризики враховувати.",
        "tools": [],
    },
}


def _tooltip_html(agent_id: str) -> str:
    """HTML-вміст для custom CSS-tooltip."""
    info = AGENT_INFO[agent_id]
    tools_html = ""
    if info["tools"]:
        items = "".join(f"<li>{tool}</li>" for tool in info["tools"])
        tools_html = f'<div class="tt-tools-label">Tools:</div><ul class="tt-tools">{items}</ul>'
    else:
        tools_html = '<div class="tt-tools-label">Tools: немає (тільки LLM)</div>'

    return (
        f'<div class="tt-title">{info["emoji"]} {info["name"]} <span class="tt-sub">({info["sub"]})</span></div>'
        f'<div class="tt-task">{info["task"]}</div>'
        f'{tools_html}'
    )


def _agent_card(agent_id: str, active: bool = True, badge: str | None = None) -> str:
    """HTML картка агента (через markdown unsafe_allow_html)."""
    info = AGENT_INFO[agent_id]
    if active:
        bg = info["color"]
        text_color = "#ffffff"
        opacity = "1"
        border = f"2px solid {info['color']}"
    else:
        bg = "#1e293b"
        text_color = "#64748b"
        opacity = "0.5"
        border = "2px dashed #475569"

    badge_html = ""
    if badge:
        badge_html = (
            f'<div style="position:absolute;top:-8px;right:-8px;background:#fbbf24;'
            f'color:#0f172a;font-size:11px;font-weight:700;padding:2px 8px;border-radius:10px;">{badge}</div>'
        )

    tooltip_inner = _tooltip_html(agent_id)

    return (
        f'<div class="agent-tt-wrap" '
        f'style="position:relative;background:{bg};color:{text_color};border:{border};'
        f'border-radius:10px;padding:14px 8px;text-align:center;opacity:{opacity};'
        f'min-height:90px;display:flex;flex-direction:column;justify-content:center;'
        f'cursor:help;">'
        f'{badge_html}'
        f'<div style="font-size:28px;line-height:1;">{info["emoji"]}</div>'
        f'<div style="font-weight:600;font-size:13px;margin-top:4px;">{info["name"]}</div>'
        f'<div style="font-size:10px;opacity:0.85;">{info["sub"]}</div>'
        f'<div class="agent-tt-popup">{tooltip_inner}</div>'
        f'</div>'
    )


def _arrow(active: bool = True, label: str | None = None) -> str:
    """Стрілка між картками."""
    color = "#38bdf8" if active else "#475569"
    arrow_char = "➔" if active else "⤍"
    label_html = (
        f'<div style="font-size:10px;color:{color};margin-bottom:2px;">{label}</div>'
        if label else ""
    )
    return (
        f'<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;'
        f'min-height:90px;">'
        f'{label_html}'
        f'<div style="font-size:28px;color:{color};line-height:1;">{arrow_char}</div>'
        f'</div>'
    )


def render_flow(
    active_workers: list[str] | None = None,
    route_decision: str | None = None,
) -> None:
    """
    Малює статичну діаграму флоу. Активні nodes/edges підсвічені,
    пропущені router-ом — затемнені і пунктирні.

    Layout:
        User → Router → [Forecaster] → Synthesizer → Plan
                     ↘ [Inventory]   ↗
                     ↘ [Delivery]    ↗
    """
    if active_workers is None:
        active_workers = ["forecaster", "inventory", "delivery"]

    decision_badge = f"decision: {route_decision}" if route_decision else None

    # CSS для custom tooltips — instant, читабельний, без залежностей
    st.markdown(
        """
<style>
.agent-tt-wrap .agent-tt-popup {
  visibility: hidden;
  opacity: 0;
  position: absolute;
  bottom: calc(100% + 10px);
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  width: 260px;
  background: #0f172a;
  color: #e2e8f0;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 12px;
  text-align: left;
  font-size: 12px;
  line-height: 1.45;
  box-shadow: 0 8px 24px rgba(0,0,0,0.5);
  pointer-events: none;
  transition: opacity 0.15s ease;
  white-space: normal;
}
.agent-tt-wrap:hover .agent-tt-popup {
  visibility: visible;
  opacity: 1;
}
.agent-tt-wrap .agent-tt-popup::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 6px solid transparent;
  border-top-color: #0f172a;
}
.agent-tt-popup .tt-title {
  font-weight: 700;
  color: #f8fafc;
  font-size: 13px;
  margin-bottom: 6px;
}
.agent-tt-popup .tt-sub {
  font-weight: 400;
  color: #94a3b8;
  font-size: 11px;
}
.agent-tt-popup .tt-task {
  color: #cbd5e1;
  margin-bottom: 8px;
}
.agent-tt-popup .tt-tools-label {
  color: #fbbf24;
  font-weight: 600;
  font-size: 11px;
  margin-bottom: 4px;
}
.agent-tt-popup .tt-tools {
  margin: 0;
  padding-left: 16px;
  color: #cbd5e1;
}
.agent-tt-popup .tt-tools li {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  margin: 2px 0;
}
</style>
""",
        unsafe_allow_html=True,
    )

    # Row 1: User → Router → 3 workers (3 окремі рядки) → Synthesizer → Plan
    # Робимо 7 колонок: user, arrow, router, arrow, workers-stack, arrow, synth, arrow, plan
    # Спрощуємо: трирядкова сітка з вирівнюванням на середній ряд

    # Колонки: User | → | Router | → | (три worker-картки в стек) | → | Synthesizer | → | Plan
    cols = st.columns([1.2, 0.5, 1.2, 0.5, 1.4, 0.5, 1.4, 0.5, 1.2])

    # User
    with cols[0]:
        st.markdown('<div style="height:30px"></div>', unsafe_allow_html=True)
        st.markdown(_agent_card("user", active=True), unsafe_allow_html=True)
        st.markdown('<div style="height:30px"></div>', unsafe_allow_html=True)

    # →
    with cols[1]:
        st.markdown('<div style="height:30px"></div>', unsafe_allow_html=True)
        st.markdown(_arrow(active=True), unsafe_allow_html=True)
        st.markdown('<div style="height:30px"></div>', unsafe_allow_html=True)

    # Router (з badge decision)
    with cols[2]:
        st.markdown('<div style="height:30px"></div>', unsafe_allow_html=True)
        st.markdown(_agent_card("router", active=True, badge=decision_badge), unsafe_allow_html=True)
        st.markdown('<div style="height:30px"></div>', unsafe_allow_html=True)

    # → → → (трирядкова стрілка для fan-out)
    with cols[3]:
        for w in ["forecaster", "inventory", "delivery"]:
            is_active = w in active_workers
            label = "✓" if is_active else "skip"
            st.markdown(_arrow(active=is_active, label=label), unsafe_allow_html=True)

    # Workers stack (3 картки)
    with cols[4]:
        for w in ["forecaster", "inventory", "delivery"]:
            is_active = w in active_workers
            st.markdown(_agent_card(w, active=is_active), unsafe_allow_html=True)

    # ← ← ← (три стрілки до synthesizer)
    with cols[5]:
        for w in ["forecaster", "inventory", "delivery"]:
            is_active = w in active_workers
            st.markdown(_arrow(active=is_active), unsafe_allow_html=True)

    # Synthesizer
    with cols[6]:
        st.markdown('<div style="height:30px"></div>', unsafe_allow_html=True)
        st.markdown(_agent_card("synthesizer", active=True), unsafe_allow_html=True)
        st.markdown('<div style="height:30px"></div>', unsafe_allow_html=True)

    # →
    with cols[7]:
        st.markdown('<div style="height:30px"></div>', unsafe_allow_html=True)
        st.markdown(_arrow(active=True), unsafe_allow_html=True)
        st.markdown('<div style="height:30px"></div>', unsafe_allow_html=True)

    # Plan
    with cols[8]:
        st.markdown('<div style="height:30px"></div>', unsafe_allow_html=True)
        st.markdown(_agent_card("result", active=True), unsafe_allow_html=True)
        st.markdown('<div style="height:30px"></div>', unsafe_allow_html=True)

    # Caption
    st.caption(
        "Підсвічені картки — активні агенти. Пунктирні (затемнені) — пропущені router-ом. "
        "Стрілки з ✓ — дані передались, з 'skip' — workers не запускались."
    )
