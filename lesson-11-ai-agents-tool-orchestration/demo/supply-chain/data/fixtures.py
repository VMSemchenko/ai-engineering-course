"""
Mock-fixtures для аерокосмічного supply chain demo.

3 типові сценарії з різними патернами:
- TURBINE-A37  — high demand growth, low inventory → треба замовляти багато
- BOLT-X12     — overstocked, demand стабільний → не треба замовляти взагалі
- COMPOSITE-K9 — supply chain disruption (lead time виріс) → треба замовляти раніше

Fixtures навмисно створені так щоб 3 агенти давали часом конфліктні signals
— це wow-moment на демці, коли synthesizer мусить розрулити.
"""
from __future__ import annotations

PARTS: dict[str, dict] = {
    "TURBINE-A37": {
        "description": "High-pressure turbine blade, Boeing 787 engines",
        "demand_history": {
            "Q1-2025": 240, "Q2-2025": 280, "Q3-2025": 310,
            "Q4-2025": 360, "Q1-2026": 410,
        },
        "demand_forecast_q2_2026": {"low": 440, "expected": 480, "high": 530},
        "demand_drivers": [
            "Boeing 787 production ramp-up announced for 2026",
            "Two Asian airlines placed bulk orders in Q1 2026",
            "5-year service interval triggers replacement wave",
        ],
        "current_inventory": 95,
        "warehouse_locations": {"Toulouse": 60, "Seattle": 25, "Singapore": 10},
        "safety_stock_target": 120,
        "supplier": "Safran Aerospace",
        "lead_time_days": 90,
        "lead_time_trend": "stable",
        "delivery_reliability_pct": 92,
        "moq": 50,
        "unit_cost_usd": 18500,
    },
    "BOLT-X12": {
        "description": "Titanium fastener, Airbus A320 fuselage",
        "demand_history": {
            "Q1-2025": 12000, "Q2-2025": 11800, "Q3-2025": 12100,
            "Q4-2025": 11900, "Q1-2026": 12000,
        },
        "demand_forecast_q2_2026": {"low": 11500, "expected": 12000, "high": 12500},
        "demand_drivers": [
            "Stable A320 production rate",
            "No major fleet expansions announced",
        ],
        "current_inventory": 38000,
        "warehouse_locations": {"Hamburg": 22000, "Mobile": 11000, "Tianjin": 5000},
        "safety_stock_target": 18000,
        "supplier": "Precision Castparts (Berkshire Hathaway)",
        "lead_time_days": 30,
        "lead_time_trend": "stable",
        "delivery_reliability_pct": 98,
        "moq": 5000,
        "unit_cost_usd": 12,
    },
    "AVIONICS-R88": {
        "description": "Flight Management System computer module, Boeing 737 MAX cockpit",
        "demand_history": {
            "Q1-2025": 45, "Q2-2025": 60, "Q3-2025": 95,
            "Q4-2025": 140, "Q1-2026": 220,
        },
        "demand_forecast_q2_2026": {"low": 280, "expected": 340, "high": 420},
        "demand_drivers": [
            "Accelerating ramp-up: Boeing 737 MAX повертається у виробництво у 5 нових країнах",
            "Один великий замовник (American Airlines) розмістив contingent order на 80 одиниць",
            "Industry-wide retrofit campaign — старі літаки оновлюють FMS до new-spec",
            "Експонентний тренд: за 5 кварталів попит виріс у 5 разів",
        ],
        "current_inventory": 78,
        "warehouse_locations": {"Toulouse": 8, "Seattle": 65, "Singapore": 5},
        "warehouse_imbalance_note": (
            "Критичний дисбаланс: Seattle overstocked (65 при потребі ~25), "
            "Toulouse в дефіциті (8 при потребі 35). Потрібен intra-company transfer "
            "плюс додаткове замовлення. Transfer cost ~$150/одиницю + 14 днів."
        ),
        "safety_stock_target": 100,
        "supplier": "Honeywell Aerospace (Phoenix, AZ)",
        "secondary_supplier": "Thales Group (Toulouse) — щойно сертифікований у березні 2026",
        "lead_time_days": 130,
        "lead_time_trend": "volatile",
        "lead_time_disruption_note": (
            "Honeywell має labor dispute у Phoenix plant — lead time коливається "
            "від 95 до 165 днів. Forecast на Q2-2026: median 130, P90 = 160 днів. "
            "Thales (alternative): 110 днів стабільно, але ціна на 12% вища і "
            "перші 50 одиниць через qualification testing — ще +30 днів."
        ),
        "regulatory_alert": (
            "ВАЖЛИВО: FAA Airworthiness Directive AD 2026-03-15 вимагає всі замовлення "
            "розміщені до 2026-08-01 (cutoff date). Після цієї дати потрібна нова "
            "specifikatsiya R88-v2 (incompatible з поточними aircraft). Це означає: "
            "якщо замовлення на >250 одиниць не розміщене до 1 серпня 2026, "
            "решту попиту неможливо задовольнити поточною версією."
        ),
        "delivery_reliability_pct": 71,
        "moq": 25,
        "unit_cost_usd": 87000,
    },
    "COMPOSITE-K9": {
        "description": "Carbon-fiber composite panel, Airbus A350 wing",
        "demand_history": {
            "Q1-2025": 80, "Q2-2025": 95, "Q3-2025": 100,
            "Q4-2025": 105, "Q1-2026": 110,
        },
        "demand_forecast_q2_2026": {"low": 105, "expected": 115, "high": 130},
        "demand_drivers": [
            "Steady A350 production growth (+5% YoY)",
            "New variant A350-1000ULR entering production Q3 2026",
        ],
        "current_inventory": 60,
        "warehouse_locations": {"Toulouse": 40, "Hamburg": 15, "Tianjin": 5},
        "safety_stock_target": 50,
        "supplier": "Hexcel Corporation (Salt Lake City)",
        "lead_time_days": 165,  # розширено зі 120 через disruption
        "lead_time_trend": "deteriorating",
        "lead_time_disruption_note": (
            "Lead time виріс зі 120 до 165 днів через нестачу сирого carbon fiber "
            "(Hexcel оголосив про supply constraints у Q1 2026). Прогноз — повернення "
            "до норми не раніше Q4 2026."
        ),
        "delivery_reliability_pct": 76,
        "moq": 20,
        "unit_cost_usd": 42000,
    },
}


def get_part(part_id: str) -> dict:
    if part_id not in PARTS:
        raise ValueError(
            f"Unknown part {part_id!r}. Available: {list(PARTS.keys())}"
        )
    return PARTS[part_id]


def list_parts() -> list[str]:
    return list(PARTS.keys())
