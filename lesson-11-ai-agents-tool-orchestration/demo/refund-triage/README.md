# Refund Triage Agent — Evaluator-Optimizer + HITL

Live-демо для lesson 11. E-commerce кейс — refund triage agent що автоматично approve дрібні валідні case-и, ескалує підозрілі до людини, і має evaluator-критика який може повернути рішення на доробку.

## Як запустити

```bash
cd lesson-11-ai-agents-tool-orchestration/demo/refund-triage
make install                       # створює .venv, ставить deps, копіює .env
# додати OPENROUTER_API_KEY у .env (https://openrouter.ai/keys)
make demo                          # відкриває Streamlit на http://localhost:8501
```

Модель за замовчуванням — `google/gemini-2.0-flash-001` через OpenRouter. Один прогон case ~$0.002-0.005.

## Що показує

**3 agentic patterns** в одній демці:

- **Evaluator-Optimizer loop** — Resolver пропонує decision → Evaluator оцінює (score, risk, policy compliance) → якщо score < threshold → loop назад з фідбеком (max 2 retries)
- **Human-in-the-Loop через LangGraph interrupt** — pause перед auto-execute якщо amount > $500 або risk > 0.6, чекати approval/rejection через UI, resume з результатом
- **Tool Authorization tiers** — read-only tools (lookup_*) дозволені завжди; write tools (issue_refund) проходять через HITL gate

## Архітектура

```
START
  │
  ▼
[fetch_context]   ── lookup_customer + lookup_order + fraud_signals
  │
  ▼
[resolver]        ── propose decision (approve/credit/deny + amount + reason)
  │
  ▼
[evaluator]       ── score 0-1: policy compliance, risk, fairness
  │
  ▼
{score >= 0.7?} ──No──► [resolver] (з фідбеком, до 2 retries)
  │ Yes
  ▼
{auto_approve?} ──No──► [hitl_gate] ⏸ interrupt → human → resume
  │ Yes (amount<$100, risk<0.3)
  ▼
[execute]         ── issue_refund tool call (mocked)
  │
  ▼
END
```

## 4 сценарії

| Case | Сума | Customer | Що демонструє |
|------|------|----------|---------------|
| `RF-001` Lost package | $45 | 3 роки, чиста | Happy path — auto-approve, evaluator passes одразу |
| `RF-002` Damaged item | $320 | новий | Evaluator валить перше рішення (unfair) → retry → approve credit |
| `RF-003` "Not as described" | $1,200 | new + 5 refunds/міс | High risk → HITL pause → human вирішує |
| `RF-004` Subscription dispute | $89 | стара карта | Edge case — 2 retries, forced HITL |

## План на парі (30-35 хв)

```
[0-5]   Контекст: e-commerce refunds, tradeoff auto-approve vs full-manual.

[5-10]  Архітектура: показати граф, пояснити evaluator-optimizer і HITL gate.

[10-16] Live RF-001 (lost package). Happy path, ~3с end-to-end.

[16-22] Live RF-002 (damaged). Evaluator валить → retry з фідбеком → approve.
        Показати: 2 calls resolver, 2 calls evaluator, diff у trace.

[22-28] Live RF-003 (fraud). HITL pause. Approval UI у sidebar.
        Натиснути "Reject" → graph resume з deny. Показати checkpoint.

[28-32] Live RF-004 (edge). Loop-ить 2 рази → forced HITL.
        Урок: ставити max_retries.

[32-35] Метрики: cost per case, % auto-approved, % retries, % HITL.
        Trade-off: вищий threshold = безпечніше але більше HITL.
```

## Структура

```
demo/refund-triage/
├── Makefile, requirements.txt, .env.example
├── app.py                      # Streamlit UI
├── data/fixtures.py            # 4 cases + customer/order DBs
└── src/
    ├── llm.py                  # OpenRouter client
    ├── schemas.py              # Pydantic models
    ├── tools/                  # lookup_*, issue_refund
    ├── agents/                 # resolver, evaluator
    └── graph/triage.py         # LangGraph з interrupt_before=["execute"]
```
