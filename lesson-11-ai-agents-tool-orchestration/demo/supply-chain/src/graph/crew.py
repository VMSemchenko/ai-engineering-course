"""
LangGraph crew з трьома паттернами:
  - Routing            — router_agent класифікує запит, conditional edges пропускають
                          непотрібних workers
  - Parallelization    — workers що залишились після routing виконуються паралельно
  - Orchestrator-Workers — synthesizer (orchestrator) агрегує висновки workers у фінальний plan

Граф (з усіма потенційними ребрами; conditional edges активуються залежно від рішення router):

    START ──► router ──┬──► forecaster ──┐
                       ├──► inventory   ──┼──► synthesizer ──► END
                       └──► delivery    ──┘

Routing decisions:
  - "full"          → forecaster + inventory + delivery
  - "stock_only"    → inventory + delivery
  - "demand_only"   → forecaster
  - "delivery_only" → delivery
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from src.agents.workers import (
    delivery_agent,
    forecaster_agent,
    inventory_agent,
    router_agent,
    synthesizer_agent,
)
from src.llm import LLMUsage


class SupplyChainState(TypedDict, total=False):
    part_id: str
    quarter: str
    query_type: str
    route_decision: str
    forecast: dict
    inventory: dict
    delivery: dict
    final_plan: str
    usage: LLMUsage


def router_node(state: SupplyChainState) -> dict:
    """Routing pattern — обирає шлях для подальшого виконання."""
    result = router_agent(
        state.get("query_type", "full procurement plan"),
        state["part_id"],
        state["usage"],
    )
    return {"route_decision": result["decision"]}


def route_after_router(state: SupplyChainState) -> list[str]:
    """Conditional edge — повертає список наступних nodes."""
    decision = state.get("route_decision", "full")
    routes = {
        "full": ["forecaster", "inventory", "delivery"],
        "stock_only": ["inventory", "delivery"],
        "demand_only": ["forecaster"],
        "delivery_only": ["delivery"],
    }
    return routes.get(decision, ["forecaster", "inventory", "delivery"])


def forecaster_node(state: SupplyChainState) -> dict:
    result = forecaster_agent(state["part_id"], state["quarter"], state["usage"])
    return {"forecast": result}


def inventory_node(state: SupplyChainState) -> dict:
    result = inventory_agent(state["part_id"], state["usage"])
    return {"inventory": result}


def delivery_node(state: SupplyChainState) -> dict:
    result = delivery_agent(state["part_id"], state["usage"])
    return {"delivery": result}


def synthesizer_node(state: SupplyChainState) -> dict:
    plan = synthesizer_agent(
        state["part_id"],
        state["quarter"],
        state.get("forecast"),
        state.get("inventory"),
        state.get("delivery"),
        state["usage"],
    )
    return {"final_plan": plan}


def build_graph():
    graph = StateGraph(SupplyChainState)
    graph.add_node("router", router_node)
    graph.add_node("forecaster", forecaster_node)
    graph.add_node("inventory", inventory_node)
    graph.add_node("delivery", delivery_node)
    graph.add_node("synthesizer", synthesizer_node)

    # Routing pattern: router class запит, conditional edge обирає workers
    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        route_after_router,
        ["forecaster", "inventory", "delivery"],
    )

    # Parallelization: вибрані workers виконуються паралельно
    # Fan-in: всі шляхи сходяться у synthesizer (LangGraph чекає тільки тих що запустилися)
    graph.add_edge("forecaster", "synthesizer")
    graph.add_edge("inventory", "synthesizer")
    graph.add_edge("delivery", "synthesizer")
    graph.add_edge("synthesizer", END)

    return graph.compile()


def run_crew(part_id: str, quarter: str, query_type: str = "full procurement plan") -> dict:
    """Запуск multi-agent crew. Повертає final_plan + intermediate results + usage + route_decision."""
    app = build_graph()
    usage = LLMUsage()
    final_state = app.invoke({
        "part_id": part_id,
        "quarter": quarter,
        "query_type": query_type,
        "usage": usage,
    })
    return {
        "architecture": "crew",
        "final_plan": final_state["final_plan"],
        "route_decision": final_state.get("route_decision", "unknown"),
        "forecast": final_state.get("forecast"),
        "inventory": final_state.get("inventory"),
        "delivery": final_state.get("delivery"),
        "usage": usage,
    }


def graph_mermaid() -> str:
    """Mermaid-діаграма графа для UI."""
    return build_graph().get_graph().draw_mermaid()
