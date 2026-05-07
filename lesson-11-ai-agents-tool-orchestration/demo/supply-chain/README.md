# Aerospace Supply Chain — Multi-Agent Demo

Live-demo для lesson 11. Реальний бізнес-кейс — procurement plan для аерокосмічної компанії, з multi-agent crew і single-agent baseline для side-by-side порівняння.

## Як запустити

```bash
cd lesson-11-ai-agents-tool-orchestration/demo/supply-chain
make install                       # створює .venv, ставить deps, копіює .env
# додати OPENROUTER_API_KEY у .env (https://openrouter.ai/keys)
make demo                          # відкриває Streamlit на http://localhost:8501
```

Модель за замовчуванням — `google/gemini-2.0-flash-001` через OpenRouter (~$0.075/$0.30 за M токенів). Один прогон обох архітектур коштує $0.001-0.003.

## Що показує

Crew з router-ом + 3 worker-агенти + synthesizer координуються через LangGraph:

```
START ──► router ──┬──► forecaster ──┐
                   ├──► inventory   ──┼──► synthesizer ──► END
                   └──► delivery    ──┘
```

**3 паттерни Anthropic Building Effective Agents** у одній демці:

- **Routing** — router_agent класифікує тип запиту і через conditional edges пропускає непотрібних workers (наприклад "тільки прогноз попиту" → запускає лише forecaster, не платимо за решту)
- **Parallelization (Sectioning)** — workers що пройшли router виконуються одночасно, не послідовно
- **Orchestrator-Workers** — synthesizer агрегує висновки від workers у фінальний procurement plan

Поряд — single-agent baseline (один агент, всі 3 tools, sequential tool calls) для порівняння cost / latency / якості плану.

## Сценарії для демонстрації

3 part-IDs з різними патернами — кожен показує свій insight:

| Part | Що демонструє |
|------|---------------|
| `TURBINE-A37` | High demand growth + low inventory → агенти узгоджено пропонують замовляти |
| `BOLT-X12` | Overstock + stable demand → агенти кажуть "не замовляти" |
| `COMPOSITE-K9` | Supply chain disruption (lead time зріс зі 120 до 165 днів) → треба замовляти раніше попри помірний попит |

## План демки на парі (35-40 хв)

```
[0-5]   Контекст: aerospace procurement. Дано — частина TURBINE-A37, треба
        план на Q2-2026. Замовляти чи ні? Скільки? Коли?

[5-12]  Архітектура: orchestrator + 3 workers (forecast, inventory, delivery).
        Показати LangGraph mermaid-граф у sidebar.

[12-22] Live: запустити TURBINE-A37 (обидві архітектури паралельно).
        Розглянути final plan, intermediate results кожного агента.

[22-28] Запустити BOLT-X12 — обидва агенти кажуть "не замовляти".
        Показати: на простих кейсах baseline 2-3× дешевший і швидший.

[28-35] Запустити COMPOSITE-K9 — підсвітити disruption_alert.
        Crew синтезатор краще піднімає тривогу через спеціалізацію агентів,
        baseline іноді її пропускає.

[35-40] Висновки:
        - Multi-agent — інструмент для складних кейсів зі спеціалізацією
        - Для простих stat-запитів — overhead не виправданий
        - LangGraph дає паралелізм автоматично + native tracing
```

## Структура

```
demo/supply-chain/
├── app.py                      # Streamlit UI з side-by-side порівнянням
├── data/fixtures.py            # 3 part-IDs з реалістичними patterns
├── src/
│   ├── llm.py                  # OpenRouter client + cost estimation
│   ├── tools/supply_chain.py   # 3 mock tools + JSON schemas
│   ├── agents/workers.py       # forecaster, inventory, delivery, synthesizer
│   └── graph/
│       ├── crew.py             # LangGraph crew з паралельним fan-out
│       └── baseline.py         # Single-agent з усіма tools
├── requirements.txt
├── Makefile
└── .env.example
```

## Що міняти live на парі

Якщо хочеш кодити безпосередньо на демці — найпростіші місця:

1. **`src/agents/workers.py:forecaster_agent`** — змінити system prompt, показати як змінюється output
2. **`data/fixtures.py`** — додати 4-й part-ID з якимсь специфічним patterns
3. **`src/graph/crew.py`** — закоментувати один з паралельних edges і подивитись як LangGraph переходить у sequential mode
4. **`src/llm.py:DEFAULT_MODEL`** — переключити модель на `claude-haiku-4-5` і порівняти якість плану vs Gemini Flash
