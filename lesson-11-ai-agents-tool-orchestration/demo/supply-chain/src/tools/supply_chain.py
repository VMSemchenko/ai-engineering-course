"""
Mock-tools для supply chain demo. Повертають hardcoded fixtures —
у реальній системі це були б виклики до ERP, демпланінг-системи, WMS.
"""
from __future__ import annotations

from data.fixtures import get_part


def forecast_demand(part_id: str, quarter: str) -> dict:
    """Прогнозує попит на деталь у вказаному кварталі."""
    part = get_part(part_id)
    result = {
        "part_id": part_id,
        "description": part["description"],
        "quarter": quarter,
        "history": part["demand_history"],
        "forecast": part["demand_forecast_q2_2026"],
        "drivers": part["demand_drivers"],
    }
    if "regulatory_alert" in part:
        result["regulatory_alert"] = part["regulatory_alert"]
    return result


def check_inventory(part_id: str) -> dict:
    """Перевіряє поточні запаси по складах."""
    part = get_part(part_id)
    total = part["current_inventory"]
    target = part["safety_stock_target"]
    result = {
        "part_id": part_id,
        "total_inventory": total,
        "by_location": part["warehouse_locations"],
        "safety_stock_target": target,
        "deficit_vs_target": max(0, target - total),
        "surplus_vs_target": max(0, total - target),
        "unit_cost_usd": part["unit_cost_usd"],
    }
    if "warehouse_imbalance_note" in part:
        result["imbalance_alert"] = part["warehouse_imbalance_note"]
    return result


def optimize_delivery(part_id: str) -> dict:
    """Аналізує можливості постачання — supplier, lead time, MOQ, надійність."""
    part = get_part(part_id)
    result = {
        "part_id": part_id,
        "supplier": part["supplier"],
        "lead_time_days": part["lead_time_days"],
        "lead_time_trend": part["lead_time_trend"],
        "delivery_reliability_pct": part["delivery_reliability_pct"],
        "minimum_order_quantity": part["moq"],
    }
    if "lead_time_disruption_note" in part:
        result["disruption_alert"] = part["lead_time_disruption_note"]
    if "secondary_supplier" in part:
        result["alternative_supplier"] = part["secondary_supplier"]
    return result


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "forecast_demand",
            "description": (
                "Повертає історичний попит та прогноз на наступний квартал "
                "для аерокосмічної деталі, плюс drivers попиту."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "part_id": {"type": "string", "description": "ID деталі (наприклад TURBINE-A37, BOLT-X12, COMPOSITE-K9, AVIONICS-R88)"},
                    "quarter": {"type": "string", "description": "Квартал, наприклад 'Q2-2026'"},
                },
                "required": ["part_id", "quarter"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_inventory",
            "description": "Повертає поточні запаси деталі по складах і порівняння з safety stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "part_id": {"type": "string"},
                },
                "required": ["part_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "optimize_delivery",
            "description": (
                "Повертає інформацію про supplier, lead time, MOQ і надійність постачання. "
                "Може містити disruption_alert якщо є проблеми з постачанням."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "part_id": {"type": "string"},
                },
                "required": ["part_id"],
            },
        },
    },
]
