"""
3 worker-агенти. Кожен має одну спеціалізацію + один tool.
"""
from __future__ import annotations

import json

from src.llm import LLMUsage, call_llm
from src.tools import (
    TOOL_SCHEMAS,
    check_inventory,
    forecast_demand,
    optimize_delivery,
)

TOOL_REGISTRY = {
    "forecast_demand": forecast_demand,
    "check_inventory": check_inventory,
    "optimize_delivery": optimize_delivery,
}


def _execute_tool_calls(tool_calls) -> list[dict]:
    results = []
    for tc in tool_calls:
        fn_name = tc.function.name
        args = json.loads(tc.function.arguments)
        fn = TOOL_REGISTRY[fn_name]
        try:
            result = fn(**args)
        except Exception as e:
            result = {"error": str(e)}
        results.append({
            "tool_call_id": tc.id,
            "role": "tool",
            "name": fn_name,
            "content": json.dumps(result, ensure_ascii=False),
        })
    return results


def _run_agent(
    *,
    agent_name: str,
    system_prompt: str,
    user_prompt: str,
    tool_names: list[str],
    usage: LLMUsage,
    max_iterations: int = 3,
) -> dict:
    """Простий tool-use loop для одного агента з визначеним набором tools."""
    tools = [t for t in TOOL_SCHEMAS if t["function"]["name"] in tool_names]
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    tool_calls_log: list[dict] = []

    for _ in range(max_iterations):
        response = call_llm(
            messages,
            agent_name=agent_name,
            usage=usage,
            tools=tools,
            temperature=0.1,
        )
        msg = response.choices[0].message
        if msg.tool_calls:
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })
            tool_results = _execute_tool_calls(msg.tool_calls)
            for tc, tr in zip(msg.tool_calls, tool_results):
                tool_calls_log.append({
                    "tool": tc.function.name,
                    "args": json.loads(tc.function.arguments),
                    "result": json.loads(tr["content"]),
                })
            messages.extend(tool_results)
            continue

        return {
            "agent": agent_name,
            "answer": msg.content or "",
            "tool_calls": tool_calls_log,
        }

    return {
        "agent": agent_name,
        "answer": "[max iterations reached]",
        "tool_calls": tool_calls_log,
    }


def router_agent(query_type: str, part_id: str, usage: LLMUsage) -> dict:
    """
    Routing pattern — класифікує запит і вирішує яких workers викликати.

    Можливі route-и (LLM повертає JSON):
      - "full"          → всі 3 workers (стандартний procurement plan)
      - "stock_only"    → тільки inventory + delivery (питання типу "чи є запаси")
      - "demand_only"   → тільки forecaster (питання про прогноз)
      - "delivery_only" → тільки delivery (питання про supplier / disruption)
    """
    system = (
        "Ти Routing Coordinator у supply chain crew. На вхід отримуєш тип запиту "
        "користувача. Твоя задача — вирішити яких саме workers потрібно залучити, "
        "щоб не витрачати compute на зайве.\n\n"
        "Доступні route-опції:\n"
        "  - 'full' — повний procurement plan (forecaster + inventory + delivery)\n"
        "  - 'stock_only' — питання про поточні запаси і умови постачання (inventory + delivery)\n"
        "  - 'demand_only' — питання тільки про прогноз попиту (forecaster)\n"
        "  - 'delivery_only' — питання про постачальника і disruption (delivery)\n\n"
        "Поверни ТІЛЬКИ один з цих рядків, без пояснень, без лапок, без markdown."
    )
    user = f"Деталь: {part_id}. Тип запиту користувача: {query_type}."

    response = call_llm(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        agent_name="router",
        usage=usage,
        temperature=0.0,
    )
    raw = (response.choices[0].message.content or "").strip().lower()
    valid = {"full", "stock_only", "demand_only", "delivery_only"}
    decision = raw if raw in valid else "full"
    return {
        "agent": "router",
        "decision": decision,
        "raw_output": raw,
    }


def forecaster_agent(part_id: str, quarter: str, usage: LLMUsage) -> dict:
    system = (
        "Ти Demand Forecasting Analyst у аерокосмічній компанії. "
        "Викликаєш forecast_demand і повертаєш короткий висновок: "
        "очікуваний попит (low/expected/high), trend, ключові drivers. "
        "Якщо у відповіді tool є regulatory_alert — ОБОВ'ЯЗКОВО згадай його окремо як критичний фактор "
        "що впливає на timing і обсяг замовлення. "
        "2-5 речень, конкретні числа."
    )
    user = f"Дай прогноз попиту на {part_id} у {quarter}."
    return _run_agent(
        agent_name="forecaster",
        system_prompt=system,
        user_prompt=user,
        tool_names=["forecast_demand"],
        usage=usage,
    )


def inventory_agent(part_id: str, usage: LLMUsage) -> dict:
    system = (
        "Ти Inventory Manager. Викликаєш check_inventory і повертаєш стислий стан: "
        "поточні запаси, чи покривають safety stock, розподіл по складах. "
        "Якщо у відповіді tool є imbalance_alert — ОБОВ'ЯЗКОВО згадай його (overstock/deficit "
        "по конкретних складах + рекомендація transfer). "
        "2-5 речень з числами."
    )
    user = f"Покажи стан запасів {part_id}."
    return _run_agent(
        agent_name="inventory",
        system_prompt=system,
        user_prompt=user,
        tool_names=["check_inventory"],
        usage=usage,
    )


def delivery_agent(part_id: str, usage: LLMUsage) -> dict:
    system = (
        "Ти Procurement Specialist. Викликаєш optimize_delivery і повертаєш стислий висновок: "
        "supplier, lead time (з трендом), MOQ, надійність. "
        "ОБОВ'ЯЗКОВО згадуєш: disruption_alert (з конкретними числами P50/P90 lead time) "
        "та alternative_supplier (якщо є — порівняти з основним по lead time, ціні, ризику). "
        "2-6 речень."
    )
    user = f"Опиши умови постачання {part_id}."
    return _run_agent(
        agent_name="delivery",
        system_prompt=system,
        user_prompt=user,
        tool_names=["optimize_delivery"],
        usage=usage,
    )


def synthesizer_agent(
    part_id: str,
    quarter: str,
    forecast_result: dict | None,
    inventory_result: dict | None,
    delivery_result: dict | None,
    usage: LLMUsage,
) -> str:
    system = (
        "Ти Supply Chain Director. Отримуєш висновки від спеціалістів "
        "(Forecaster, Inventory Manager, Procurement) — деякі можуть бути недоступні. "
        "Твоя задача — синтезувати фінальну відповідь:\n"
        "1) ВСІ alert-и (regulatory, disruption, imbalance) врахувати у плані ЯВНО з числами\n"
        "2) Чітка формула розрахунку order quantity (показати: demand - inventory + safety_stock_gap)\n"
        "3) Конкретна дата розміщення замовлення (з урахуванням lead time + регуляторного cutoff)\n"
        "4) Якщо є alternative_supplier — обґрунтоване рішення основного vs alternative\n"
        "5) Якщо думки спеціалістів конфліктують — явно зазначити\n"
        "6) Якщо доступна тільки частина даних — відповідай на основі того що є, не вигадуй\n"
        "До 12 речень. Структуруй з нумерованим списком якщо багато факторів."
    )
    sections = [f"Деталь: {part_id}, квартал: {quarter}."]
    if forecast_result:
        sections.append(f"Forecaster: {forecast_result['answer']}")
    if inventory_result:
        sections.append(f"Inventory: {inventory_result['answer']}")
    if delivery_result:
        sections.append(f"Delivery: {delivery_result['answer']}")
    sections.append("Сформулюй відповідь.")
    user = "\n\n".join(sections)
    response = call_llm(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        agent_name="synthesizer",
        usage=usage,
        temperature=0.2,
    )
    return response.choices[0].message.content or ""
