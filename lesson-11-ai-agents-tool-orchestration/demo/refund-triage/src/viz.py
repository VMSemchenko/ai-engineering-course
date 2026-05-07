"""Graphviz diagrams — per-case expected execution paths."""

# Color palette aligned with lecture HTML
NODE_BG = "#13131a"
ACTIVE = "#7df9ff"
RETRY = "#ffa657"
HITL = "#f97583"
AUTO = "#85e89d"
DIM = "#3a3a4a"
TEXT = "#ffffff"


def _base_graph() -> list[str]:
    return [
        "digraph G {",
        "  rankdir=TB;",
        "  bgcolor=\"#0a0a12\";",
        "  fontname=\"Helvetica\";",
        f"  node [shape=box, style=\"rounded,filled\", fontcolor=\"{TEXT}\", "
        f"fontname=\"Helvetica\", fontsize=11, color=\"{DIM}\"];",
        f"  edge [color=\"{DIM}\", fontcolor=\"#8a8a9a\", fontname=\"Helvetica\", fontsize=9];",
    ]


def _node(name: str, label: str, color: str = DIM, fillcolor: str = NODE_BG) -> str:
    return (
        f'  {name} [label="{label}", color="{color}", fillcolor="{fillcolor}", '
        f'penwidth=2];'
    )


def _edge(src: str, dst: str, label: str = "", color: str = DIM, style: str = "solid") -> str:
    lbl = f', label="{label}"' if label else ""
    return f'  {src} -> {dst} [color="{color}", style="{style}"{lbl}];'


def _legend(active_paths: list[str]) -> str:
    parts = "  ".join(f'<font color="{ACTIVE}">{p}</font>' for p in active_paths)
    return parts


def graph_for_case(case_id: str) -> str:
    """Return DOT source highlighting the path this case takes."""
    lines = _base_graph()

    # Decide highlight per case
    paths = {
        "RF-001": {
            "label_top": "RF-001 · Happy path · auto-approve",
            "color_resolve_eval": AUTO,
            "show_retry": False,
            "highlight": "auto_execute",
            "subtitle": "score 1.0 · risk 0.05 · amount $45 → auto",
        },
        "RF-002": {
            "label_top": "RF-002 · Possible retry → HITL",
            "color_resolve_eval": RETRY,
            "show_retry": True,
            "highlight": "hitl",
            "subtitle": "evaluator може попросити фото · amount $320 > $100",
        },
        "RF-003": {
            "label_top": "RF-003 · High fraud → HITL",
            "color_resolve_eval": HITL,
            "show_retry": False,
            "highlight": "hitl",
            "subtitle": "fraud 0.78 · risk 0.90 · forced HITL pause",
        },
        "RF-004": {
            "label_top": "RF-004 · Policy unclear → forced HITL",
            "color_resolve_eval": RETRY,
            "show_retry": True,
            "highlight": "hitl",
            "subtitle": "evaluator може loop-ити до max_retries → HITL",
        },
    }
    p = paths.get(case_id, paths["RF-001"])

    lines.append(
        f'  labelloc="t"; label="{p["label_top"]}\\n{p["subtitle"]}"; '
        f'fontcolor="{TEXT}"; fontsize=12;'
    )

    # Nodes
    lines.append(_node("start", "START", color=DIM))
    lines.append(_node("fetch", "📥 fetch_context\\n(lookup customer/order/fraud)", color=ACTIVE))
    lines.append(_node("resolver", "🧠 resolver\\n(propose decision)", color=p["color_resolve_eval"]))
    lines.append(_node("evaluator", "🔍 evaluator\\n(score · risk · verdict)", color=p["color_resolve_eval"]))

    if p["show_retry"]:
        lines.append(_node("retry", "↻ retry_resolver\\n(feedback to resolver)", color=RETRY))
    else:
        lines.append(_node("retry", "↻ retry_resolver", color=DIM, fillcolor="#0d0d14"))

    auto_color = ACTIVE if p["highlight"] == "auto_execute" else DIM
    auto_fill = NODE_BG if p["highlight"] == "auto_execute" else "#0d0d14"
    hitl_color = ACTIVE if p["highlight"] == "hitl" else DIM
    hitl_fill = NODE_BG if p["highlight"] == "hitl" else "#0d0d14"

    lines.append(_node("auto", "💸 auto_execute\\n(no HITL)", color=auto_color, fillcolor=auto_fill))
    lines.append(_node("hitl", "⏸ hitl_gate\\n(human approval)", color=hitl_color, fillcolor=hitl_fill))
    lines.append(_node("execute", "💸 execute\\n(after human review)", color=hitl_color, fillcolor=hitl_fill))
    lines.append(_node("end", "END", color=DIM))

    # Edges — highlight active path
    is_auto = p["highlight"] == "auto_execute"
    is_hitl = p["highlight"] == "hitl"
    show_retry = p["show_retry"]

    lines.append(_edge("start", "fetch", color=ACTIVE))
    lines.append(_edge("fetch", "resolver", color=ACTIVE))
    lines.append(_edge("resolver", "evaluator", color=ACTIVE))

    if show_retry:
        lines.append(_edge("evaluator", "retry", "score < 0.75", color=RETRY))
        lines.append(_edge("retry", "resolver", color=RETRY, style="dashed"))
    else:
        lines.append(_edge("evaluator", "retry", "score < 0.75", color=DIM))
        lines.append(_edge("retry", "resolver", color=DIM, style="dashed"))

    lines.append(_edge("evaluator", "auto", "score≥0.75 ∧ amt<$100 ∧ risk<0.3", color=ACTIVE if is_auto else DIM))
    lines.append(_edge("evaluator", "hitl", "needs human", color=ACTIVE if is_hitl else DIM))
    lines.append(_edge("hitl", "execute", "after approve/reject", color=ACTIVE if is_hitl else DIM))

    lines.append(_edge("auto", "end", color=ACTIVE if is_auto else DIM))
    lines.append(_edge("execute", "end", color=ACTIVE if is_hitl else DIM))

    lines.append("}")
    return "\n".join(lines)
