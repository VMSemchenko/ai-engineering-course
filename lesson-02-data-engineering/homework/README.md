# Lesson 2: Data Engineering for AI — Homework

## Що потрібно зробити

Ви маєте готовий ingestion pipeline, який парсить документи (PDF, DOCX, HTML, XLSX), розбиває на чанки та зберігає з версіонуванням. Ваше завдання — запустити його, зрозуміти як він працює, та пройти всі кроки нижче.

---

## Крок 1: Налаштування середовища

```bash
cd homework/

python -m venv .venv
source .venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
```

---

## Крок 2: Згенерувати тестові документи

```bash
python src/generate_samples.py
```

Це створить файли у папці `samples/` — PDF, DOCX, HTML для тестування.

---

## Крок 3: Запустити pipeline у звичайному режимі

```bash
python src/main.py
```

Подивіться на вивід — скільки документів оброблено, скільки чанків створено. Результати зберігаються у `data/processed/`.

---

## Крок 4: Запустити pipeline у resilient режимі

Спочатку згенеруйте "погані" документи:

```bash
python src/generate_bad_samples.py
```

Потім запустіть pipeline з валідацією та quarantine:

```bash
python src/main.py --input samples/enterprise_challenges --resilient
```

Перевірте що потрапило у карантин:

```bash
ls data/quarantine/
```

---

## Крок 5: Streaming режим (file watcher)

```bash
python src/main.py --watch
```

Pipeline буде слідкувати за папкою `samples/` — спробуйте скопіювати туди новий файл і побачити як він автоматично обробляється.

---

## Крок 6: Запустити тести

```bash
pytest tests/ -v
```

Всі тести повинні проходити.

---

## Крок 7: Вивчити код

Пройдіться по основних файлах та зрозумійте як працює кожен компонент:

| Файл | Що робить |
|---|---|
| `src/main.py` | Точка входу, запуск pipeline |
| `src/parsers/router.py` | Роутер — визначає тип файлу та парсить через `unstructured` |
| `src/parsers/base.py` | Модель даних `ParsedDocument` |
| `src/ingestion/pipeline.py` | Головний pipeline — з'єднує парсинг, чанкінг, версіонування |
| `src/ingestion/chunker.py` | Розбиття тексту на чанки (fixed size / sentence) |
| `src/ingestion/resilience.py` | Валідація файлів, retry, quarantine для поганих файлів |
| `src/streaming/watcher.py` | File watcher — слідкує за новими файлами |
| `src/streaming/queue.py` | Async черга документів |
| `src/streaming/batcher.py` | Батчинг — групує документи для обробки |
| `src/versioning/version_store.py` | Версіонування — зберігає snapshot кожного прогону |
| `configs/pipeline.yaml` | Конфігурація pipeline |

---

## Крок 8: Прочитати CHALLENGES.md

```bash
cat CHALLENGES.md
```

Тут описані 12 реальних enterprise-проблем з документами (corrupted files, wrong encoding, password-protected PDFs тощо) та як pipeline їх вирішує.

---

## Структура проєкту

```
homework/
├── src/
│   ├── main.py                  — Точка входу
│   ├── generate_samples.py      — Генерація тестових документів
│   ├── generate_bad_samples.py  — Генерація "поганих" документів
│   ├── parsers/
│   │   ├── base.py              — ParsedDocument dataclass
│   │   └── router.py            — ParserRouter (unstructured)
│   ├── ingestion/
│   │   ├── pipeline.py          — IngestionPipeline
│   │   ├── chunker.py           — Chunker
│   │   └── resilience.py        — FileValidator, ResilientParser, DeadLetterQueue
│   ├── streaming/
│   │   ├── watcher.py           — FileWatcher
│   │   ├── queue.py             — DocumentQueue
│   │   └── batcher.py           — Batcher
│   └── versioning/
│       └── version_store.py     — VersionStore
├── configs/
│   └── pipeline.yaml
├── samples/                     — Тестові документи (генеруються)
├── data/
│   ├── processed/               — Результати обробки
│   ├── quarantine/              — Файли що не пройшли валідацію
│   └── versions/                — Версії snapshots
├── tests/                       — Тести
├── requirements.txt
├── CHALLENGES.md
└── README.md                    — Цей файл
```
