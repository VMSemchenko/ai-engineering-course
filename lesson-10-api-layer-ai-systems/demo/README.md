# Multi-LLM Chat Battle · Lesson 10 Demo

Інтерактивна демо-аппка, що показує **API layer патерни** на live прикладі: 3 LLM моделі стрімлять відповіді **паралельно** в 3 колонках, з real-time порівнянням latency, tokens/sec, cost.

## Що демонструє

- **SSE Streaming** — токени з 3 моделей друкуються паралельно в 3 колонках
- **Concurrency control** — `asyncio.Semaphore(6)` обмежує одночасні LLM-виклики (видно в badge `concurrency: X/6`)
- **Cost tracking** — кожен запит логується, показує per-model і загальний cost у real-time
- **Disconnect handling** — counter `aborted_streams` інкрементується при перериванні
- **Chaos engineering** — кнопка "kill 50%" на кожній моделі імітує fail для демо resilience
- **Winner highlight** — найшвидша модель отримує 🏆 (gold border) після завершення

## Стек

- **Backend:** FastAPI + SSE streaming
- **LLM:** OpenRouter (3 найдешевші моделі: Llama 3.1 8B, Mistral Nemo, Gemma 3 4B)
- **Frontend:** Vanilla JS + темна тема
- **Mock mode:** працює без API ключа (для лекції без інтернету)

## Quick start

```bash
cd demo
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 1) Mock mode (без OpenRouter ключа, фейкові відповіді):
.venv/bin/uvicorn app.main:app --port 8765

# 2) Real mode (з реальним OpenRouter):
cp .env.example .env
# додай свій OPENROUTER_API_KEY у .env
# встанови USE_MOCK=false
.venv/bin/uvicorn app.main:app --port 8765
```

Відкрий [http://localhost:8765](http://localhost:8765)

## API endpoints

- `GET /` — frontend HTML
- `GET /api/models` — list of configured models + current mode
- `GET /api/health` — `{active_streams, aborted_streams, concurrency_used, ...}`
- `GET /api/usage` — aggregated cost stats per model + recent requests
- `POST /api/battle` — SSE endpoint: `{message: str}` → stream tokens from all 3 models
- `POST /api/chaos` — set `fail_rate` per model для chaos engineering demo

## Як використати на лекції

1. Введи питання → 3 колонки одночасно стрімлять
2. Покажи різницю в швидкості (TTFT, tokens/sec)
3. Натисни "kill 50%" на одній колонці → ця модель починає періодично фейлити
4. Через 5 запитів — bottom summary показує total cost і breakdown

## Файли

```
demo/
├── README.md               # цей файл
├── requirements.txt        # FastAPI + OpenAI SDK
├── .env.example            # template для секретів
├── app/
│   ├── config.py           # 3 моделі + concurrency limit
│   ├── llm_router.py       # async streaming router (real / mock)
│   ├── mock_llm.py         # fake responses для offline demo
│   └── main.py             # FastAPI з SSE endpoint
└── static/
    └── index.html          # 3-колонковий battle UI
```
