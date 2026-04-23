# 🧪 Embedding Failure Modes Lab

Інтерактивний навчальний застосунок, який показує 4 ключові **failure modes** embedding-систем у продакшні. Студент бачить проблему вживу, а потім — як її фіксити.

## 🎯 Мета

Після трьох вступних візуалізацій (`what-are-embeddings`, `similarity-search`, `multimodal-embeddings`) студенти знають «щасливий шлях». Ця лабораторна — про те, що ламається в продакшн RAG:

1. **Reranking** — bi-encoder повертає топ-10 за тематикою, але порядок часто неправильний. Cross-encoder rerank суттєво покращує якість.
2. **Negation Blindness** — `"I love this"` і `"I hate this"` мають майже однакові вектори.
3. **Silent Truncation** — документи довші за context window обрізаються мовчки, без warnings.
4. **Lost in the Middle** — LLM гірше витягує факти з середини контексту, ніж з країв.

## 🛠️ Технічний стек

- **Backend:** FastAPI + OpenAI (embeddings + gpt-4o-mini як NLI) + Cohere Rerank
- **Frontend:** Vanilla HTML + Chart.js (CDN)
- **Live API** — усі embed/rerank/LLM виклики йдуть на реальні API при запиті.

## 📦 Встановлення

```bash
cd embedding-failures-lab
pip install -r requirements.txt
cp .env.example .env
# Відредагуй .env — додай свої ключі:
#   OPENAI_API_KEY=sk-...
#   COHERE_API_KEY=...
```

### API ключі — де взяти

- **OpenAI:** https://platform.openai.com/api-keys (~$5 вистачить на сотні запитів)
- **Cohere Rerank:** https://dashboard.cohere.com/api-keys (безкоштовний tier — 1000 rerank-запитів/місяць)

## 🚀 Запуск

```bash
uvicorn app:app --reload --port 8001
```

Відкрий у браузері: **http://localhost:8001**

## 📚 Структура

```
embedding-failures-lab/
├── app.py                  # FastAPI — 7 endpoints для 4 демо
├── index.html              # SPA з 4 вкладками
├── requirements.txt
├── .env.example
├── README.md
└── data/
    ├── python_docs.json    # 30 чанків про Python web dev (demo 1)
    ├── medical_texts.json  # 5 пар + 20 тверджень про ліки (demo 2)
    ├── long_doc.txt        # ~15k-токенів документ з прихованим «BANANA-42» (demo 3)
    ├── qa_passages.json    # 13 passages, один з goldfish-фактом (demo 4)
    └── _generate_long_doc.py  # скрипт, який створив long_doc.txt
```

## 🧑‍🏫 Що студент має винести

### Demo 1: Reranking
> Bi-encoder бачить «тематичну схожість», cross-encoder читає query + document разом. Додавай reranker після vector search — це найдешевший спосіб +10-20 nDCG на RAG.

### Demo 2: Negation Blindness
> Embeddings моделюють *про що* текст, а не *що саме* він стверджує. Для медицини/права/безпеки — завжди додавай NLI-класифікатор або LLM-фільтр.

### Demo 3: Silent Truncation
> Embedders мовчки відкидають все за limit. Перевіряй `context_length` моделі та чанкуй самостійно. Без чанкування половина бази знань «не існує» для пошуку.

### Demo 4: Lost in the Middle
> Більше контексту ≠ краща відповідь. Менше top-K, найрелевантніший — першим або останнім (reorder). U-shape attention — реальна властивість трансформерів.

## 💰 Приблизна вартість

- Demo 1 (1 запит): ~$0.0003 embeddings + ~$0.002 Cohere rerank
- Demo 2 retrieve (1 запит): ~$0.001 embeddings + ~$0.001 gpt-4o-mini
- Demo 3 chunking (1 запит на 15k-doc): ~$0.005 embeddings
- Demo 4 run-all (5 LLM calls): ~$0.005 gpt-4o-mini

На всі демо одному студенту вистачить ~$0.10-0.20.

## 🐛 Відомі нюанси

- `all-MiniLM-L6-v2` у Demo 3 **симулюється** — ми рахуємо токени через `tiktoken` (cl100k) і обмежуємо до 512, щоб не тягнути важку HF-модель. Для цілі демо цього достатньо.
- Cohere `rerank-english-v3.0` очікує англійські query та docs — датасет Demo 1 спеціально англійський.
- NLI у Demo 2 реалізовано через `gpt-4o-mini` замість DeBERTa-NLI — дешевше та швидше, якість аналогічна для цього простого кейсу.

---

**Автор:** AI Engineering Course · Lesson 7 · Embeddings &amp; Semantic Systems
