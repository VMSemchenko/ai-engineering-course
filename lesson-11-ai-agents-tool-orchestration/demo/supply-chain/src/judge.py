"""
LLM-as-judge для оцінки якості procurement plans.

Оцінює план за 4 критеріями (0-10 балів кожен):
  - groundedness  — чи числа з реальних даних
  - structure     — чи легко прочитати і знайти ключові цифри
  - completeness  — чи покриває обсяг, терміни, ризики
  - actionability — чи можна одразу діяти за планом

Повертає {scores, total, comparison_winner} коли подається 2 плани.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from src.llm import LLMUsage, call_llm


JUDGE_SYSTEM = """Ти неупереджений Supply Chain Director, який оцінює якість procurement plans.

Тобі дають фактичні дані про деталь і 1-2 кандидатних плани. Ти оцінюєш кожен план за 4 критеріями (0-10 балів):

1. groundedness — числа і факти у плані відповідають фактичним даним. Hallucinations і помилки у математиці штрафуються.
2. structure — план легко читати, цифри легко знайти, без води.
3. completeness — план відповідає на питання: скільки замовляти, коли, які ризики, чому саме стільки.
4. actionability — на основі плану можна одразу діяти (є конкретне число замовлення, дата, supplier, формула обґрунтована).

ВАЖЛИВО:
- Перевіряй математику: order quantity має бути обґрунтованим (наприклад demand - inventory + safety_buffer).
- Якщо план каже одне число без обґрунтування — це низький бал на actionability.
- Якщо план дає неправильну формулу — низький бал на groundedness.
- Не упереджуйся за обсяг тексту — короткий і чіткий план може бути кращим за довгий і розмитий.

Поверни ТІЛЬКИ JSON у форматі (без markdown, без пояснень навколо). Для кожного критерію — БАЛ і КОНКРЕТНА ПРИЧИНА (1-2 речення, посилайся на цифри з планів):
{
  "plan_a": {
    "groundedness": {"score": int, "reason": "..."},
    "structure":    {"score": int, "reason": "..."},
    "completeness": {"score": int, "reason": "..."},
    "actionability":{"score": int, "reason": "..."}
  },
  "plan_b": {
    "groundedness": {"score": int, "reason": "..."},
    "structure":    {"score": int, "reason": "..."},
    "completeness": {"score": int, "reason": "..."},
    "actionability":{"score": int, "reason": "..."}
  },
  "plan_a_total": int,
  "plan_b_total": int,
  "winner": "a" | "b" | "tie",
  "verdict": "1-2 речення про головну різницю",
  "baseline_weaknesses": ["короткий пункт", "..."],
  "crew_weaknesses": ["короткий пункт", "..."]
}

Якщо подано тільки plan_a — поверни plan_a, plan_a_total, winner: "a", verdict, і опусти plan_b/plan_b_total/weaknesses-блоки баз.

reason-поля МАЮТЬ містити ЦИФРИ з планів і пояснювати ЧОМУ саме такий бал. Не пиши "good" чи "bad" — пиши що саме у плані добре чи погано.
"""


@dataclass
class JudgeResult:
    plan_a_scores: dict        # {criterion: int}
    plan_b_scores: dict | None
    plan_a_reasons: dict       # {criterion: str}
    plan_b_reasons: dict | None
    plan_a_total: int
    plan_b_total: int | None
    winner: str
    verdict: str
    baseline_weaknesses: list[str]
    crew_weaknesses: list[str]
    raw_response: str


def _facts_text(part_id: str, facts: dict) -> str:
    """Форматує факти про деталь у текст для judge."""
    base = (
        f"Part: {part_id}\n"
        f"Description: {facts.get('description')}\n"
        f"Demand history: {facts.get('demand_history')}\n"
        f"Demand forecast Q2-2026: {facts.get('demand_forecast_q2_2026')}\n"
        f"Drivers: {facts.get('demand_drivers')}\n"
        f"Current inventory: {facts.get('current_inventory')} units\n"
        f"Warehouse split: {facts.get('warehouse_locations')}\n"
        f"Safety stock target: {facts.get('safety_stock_target')}\n"
        f"Supplier: {facts.get('supplier')}\n"
        f"Lead time: {facts.get('lead_time_days')} days "
        f"({facts.get('lead_time_trend')})\n"
        f"Reliability: {facts.get('delivery_reliability_pct')}%\n"
        f"MOQ: {facts.get('moq')}\n"
        f"Unit cost: ${facts.get('unit_cost_usd')}\n"
    )
    extras = []
    if "lead_time_disruption_note" in facts:
        extras.append(f"Disruption alert: {facts['lead_time_disruption_note']}")
    if "warehouse_imbalance_note" in facts:
        extras.append(f"Inventory imbalance: {facts['warehouse_imbalance_note']}")
    if "regulatory_alert" in facts:
        extras.append(f"Regulatory alert: {facts['regulatory_alert']}")
    if "secondary_supplier" in facts:
        extras.append(f"Alternative supplier: {facts['secondary_supplier']}")
    return base + ("\n".join(extras) + "\n" if extras else "")


def _parse_json(raw: str) -> dict:
    """Витягує JSON з відповіді LLM (інколи у markdown wrapper-ах)."""
    raw = raw.strip()
    # Зрізаємо markdown ```json ... ```
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON in judge response: {raw[:200]}")
    return json.loads(match.group(0))


def judge_plans(
    part_id: str,
    facts: dict,
    plan_a: str,
    plan_b: str | None = None,
    *,
    plan_a_label: str = "Plan A",
    plan_b_label: str = "Plan B",
    usage: LLMUsage | None = None,
    model: str | None = None,
) -> JudgeResult:
    """
    Оцінює один план (plan_b=None) або порівнює два.

    Використовує окрему дешеву модель — не ту що генерувала плани (avoid bias).
    """
    if usage is None:
        usage = LLMUsage()

    facts_block = _facts_text(part_id, facts)

    user_parts = [
        f"# Фактичні дані\n\n{facts_block}",
        f"\n# {plan_a_label} (plan_a)\n\n{plan_a}",
    ]
    if plan_b is not None:
        user_parts.append(f"\n# {plan_b_label} (plan_b)\n\n{plan_b}")

    user_parts.append("\nОціни і поверни JSON.")
    user_msg = "\n".join(user_parts)

    response = call_llm(
        [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        agent_name="judge",
        usage=usage,
        temperature=0.0,
        model=model or "google/gemini-2.0-flash-001",
    )
    raw = response.choices[0].message.content or ""
    parsed = _parse_json(raw)

    def _split(plan_block: dict | None) -> tuple[dict, dict]:
        """Розщеплює {criterion: {score, reason}} на 2 dict-и."""
        if not plan_block:
            return {}, {}
        scores = {k: v.get("score", 0) for k, v in plan_block.items() if isinstance(v, dict)}
        reasons = {k: v.get("reason", "") for k, v in plan_block.items() if isinstance(v, dict)}
        return scores, reasons

    a_scores, a_reasons = _split(parsed.get("plan_a"))
    b_scores, b_reasons = _split(parsed.get("plan_b"))

    return JudgeResult(
        plan_a_scores=a_scores,
        plan_b_scores=b_scores if b_scores else None,
        plan_a_reasons=a_reasons,
        plan_b_reasons=b_reasons if b_reasons else None,
        plan_a_total=parsed.get("plan_a_total", 0),
        plan_b_total=parsed.get("plan_b_total"),
        winner=parsed.get("winner", "tie"),
        verdict=parsed.get("verdict", ""),
        baseline_weaknesses=parsed.get("baseline_weaknesses", []),
        crew_weaknesses=parsed.get("crew_weaknesses", []),
        raw_response=raw,
    )
