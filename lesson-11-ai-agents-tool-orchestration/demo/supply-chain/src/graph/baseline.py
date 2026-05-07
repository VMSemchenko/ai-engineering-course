"""
Single-agent baseline. Один агент, всі 3 tools — simple tool_use loop.
Для порівняння cost/latency vs LangGraph crew.
"""
from __future__ import annotations

import json

from src.agents.workers import TOOL_REGISTRY
from src.llm import LLMUsage, call_llm
from src.tools import TOOL_SCHEMAS


def run_baseline(part_id: str, quarter: str) -> dict:
    usage = LLMUsage()
    system = (
        "Ти Supply Chain Director у аерокосмічній компанії. Маєш доступ до tools "
        "(forecast_demand, check_inventory, optimize_delivery). Користуйся ними щоб "
        "побудувати procurement plan: чи замовляти, скільки, коли, які ризики. "
        "Чіткий план з числами, до 8 речень."
    )
    user = f"Побудуй procurement plan для {part_id} на {quarter}."

    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    tool_calls_log: list[dict] = []

    for _ in range(8):
        response = call_llm(
            messages,
            agent_name="single_agent",
            usage=usage,
            tools=TOOL_SCHEMAS,
            temperature=0.2,
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
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)
                fn = TOOL_REGISTRY[tc.function.name]
                try:
                    result = fn(**args)
                except Exception as e:
                    result = {"error": str(e)}
                tool_calls_log.append({
                    "tool": tc.function.name,
                    "args": args,
                    "result": result,
                })
                messages.append({
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "name": tc.function.name,
                    "content": json.dumps(result, ensure_ascii=False),
                })
            continue

        return {
            "architecture": "baseline",
            "final_plan": msg.content or "",
            "tool_calls": tool_calls_log,
            "usage": usage,
        }

    return {
        "architecture": "baseline",
        "final_plan": "[max iterations reached]",
        "tool_calls": tool_calls_log,
        "usage": usage,
    }
