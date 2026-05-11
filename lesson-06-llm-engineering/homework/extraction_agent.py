"""
Extraction Agent — витягує структуровані дані зі зустрічей
Порівнює self-hosted (Ollama/Mistral) vs cloud (Z.ai/GLM) LLM
"""

import openai
import requests
import json
import sys
import os
import time
import csv
from dotenv import load_dotenv
from pathlib import Path

# ── CONFIG ──
load_dotenv()

ZAI_API_KEY = os.getenv("ZAI_API_KEY", "")
ZAI_BASE_URL = os.getenv("ZAI_BASE_URL", "https://api.z.ai/api/paas/v4")
ZAI_MODEL = os.getenv("ZAI_MODEL", "glm-4.5")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
OLLAMA_BASE_URL = "http://localhost:11434"

# Каталоги
BASE_DIR = Path(__file__).parent
RESULTS_DIR = BASE_DIR / "results"
SAMPLES_DIR = BASE_DIR / "samples"

RESULTS_DIR.mkdir(exist_ok=True)


# ── SYSTEM PROMPT ──
SYSTEM_PROMPT = """You are a meeting transcription parser. Your job is to extract structured information from meeting transcripts written in Ukrainian.

Extract:
1. summary - one sentence summary of the meeting (in Ukrainian)
2. tasks - array of tasks with owner, task description, and deadline
3. decisions - array of decisions that were made

Return ONLY valid JSON, no markdown, no extra text, no code blocks. The response must be parseable by json.loads().

Expected format:
{
  "summary": "...",
  "tasks": [
    {"owner": "...", "task": "...", "deadline": "..."}
  ],
  "decisions": ["..."]
}"""


# ── OLLAMA (self-hosted) ──
def call_ollama(prompt: str) -> str:
    """Викликає локальну модель через Ollama API"""
    response = requests.post(
        f'{OLLAMA_BASE_URL}/api/chat',
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {
                "temperature": 0.3
            }
        },
        timeout=300
    )
    response.raise_for_status()
    return response.json()['message']['content']


# ── Z.AI (cloud) ──
def call_zai(prompt: str) -> str:
    """Викликає GLM модель через Z.ai OpenAI-сумісний API"""
    if not ZAI_API_KEY:
        raise ValueError("ZAI_API_KEY не встановлений у .env")

    client = openai.OpenAI(
        api_key=ZAI_API_KEY,
        base_url=ZAI_BASE_URL
    )
    response = client.chat.completions.create(
        model=ZAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content


# ── JSON EXTRACTION ──
def extract_json_from_response(text: str) -> dict | None:
    """Спробувати витягти JSON з відповіді моделі (може бути обгорнутий у ```json)"""
    # Спроба 1: прямий парсинг
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Спроба 2: витягти з markdown code block
    import re
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Спроба 3: знайти перший { ... } блок
    brace_match = re.search(r'\{.*\}', text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


# ── EXTRACTION LOGIC ──
def extract_meeting_data(text: str, provider: str = "ollama") -> dict:
    """
    Витягує структурований JSON з неструктурованого тексту зустрічі.

    Args:
        text: Транскрипт / протокол зустрічі
        provider: "ollama" або "zai"

    Returns:
        dict: {"result": parsed_json, "raw": raw_text, "latency": seconds,
               "json_valid": bool, "tokens_estimate": int}
    """

    user_prompt = f"""Прочитай цей текст зустрічі та витягни структуровану інформацію.

Текст зустрічі:
{text}

Поверни ТІЛЬКИ JSON, нічого більше."""

    # Вимірюємо latency
    start = time.time()

    if provider == "ollama":
        raw_response = call_ollama(user_prompt)
    elif provider == "zai":
        raw_response = call_zai(user_prompt)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    latency = time.time() - start

    # Парсимо JSON
    parsed = extract_json_from_response(raw_response)

    # Оцінка токенів (приблизна: слова × 1.3)
    input_words = len(user_prompt.split())
    output_words = len(raw_response.split())
    tokens_input = int(input_words * 1.3)
    tokens_output = int(output_words * 1.3)
    tokens_total = tokens_input + tokens_output

    return {
        "result": parsed,
        "raw": raw_response,
        "latency": round(latency, 2),
        "json_valid": parsed is not None,
        "tokens_input": tokens_input,
        "tokens_output": tokens_output,
        "tokens_total": tokens_total,
        "provider": provider,
        "model": OLLAMA_MODEL if provider == "ollama" else ZAI_MODEL
    }


# ── COST CALCULATION ──
def calculate_cost(tokens: int, provider: str) -> float:
    """Розраховує вартість запиту"""
    if provider == "ollama":
        return 0.0  # self-hosted = безкоштовно
    else:
        # Z.ai pricing (приблизно): ~$0.001 per 1K tokens
        return round(tokens / 1_000_000 * 1.0, 6)


# ── MAIN RUNNER ──
def run_evaluation():
    """Запускає агента на всіх датасетах та зберігає результати"""

    datasets = {
        "simple": SAMPLES_DIR / "simple_meeting.txt",
        "chaotic": SAMPLES_DIR / "chaotic_standup.txt",
        "technical": SAMPLES_DIR / "technical_sync.txt",
    }

    providers = ["ollama", "zai"]
    eval_rows = []

    print("=" * 70)
    print("🔬 EXTRACTION AGENT — EVALUATION RUN")
    print("=" * 70)

    for dataset_name, filepath in datasets.items():
        if not filepath.exists():
            print(f"⚠️  Файл {filepath} не знайдено, пропускаємо")
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()

        print(f"\n{'─' * 70}")
        print(f"📄 Dataset: {dataset_name} ({len(text)} chars)")
        print(f"{'─' * 70}")

        for provider in providers:
            print(f"\n  {'🤖' if provider == 'ollama' else '☁️'}  Provider: {provider.upper()} "
                  f"({OLLAMA_MODEL if provider == 'ollama' else ZAI_MODEL})")

            try:
                result = extract_meeting_data(text, provider=provider)

                # Зберігаємо результат у JSON
                result_filename = f"{dataset_name}_{provider}.json"
                result_path = RESULTS_DIR / result_filename
                with open(result_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        "provider": provider,
                        "model": result["model"],
                        "dataset": dataset_name,
                        "json_valid": result["json_valid"],
                        "latency_sec": result["latency"],
                        "tokens_total": result["tokens_total"],
                        "parsed_result": result["result"],
                        "raw_response": result["raw"]
                    }, f, indent=2, ensure_ascii=False)

                # Виводимо результат
                json_status = "✅" if result["json_valid"] else "❌"
                tasks_count = len(result["result"].get("tasks", [])) if result["result"] else 0
                cost = calculate_cost(result["tokens_total"], provider)

                print(f"     JSON valid: {json_status}")
                print(f"     Tasks found: {tasks_count}")
                print(f"     Latency: {result['latency']}s")
                print(f"     Tokens: {result['tokens_total']} "
                      f"(in:{result['tokens_input']} + out:{result['tokens_output']})")
                print(f"     Cost: ${cost}")
                print(f"     Saved: {result_path.name}")

                if result["result"]:
                    print(f"\n     📋 Parsed JSON:")
                    print(json.dumps(result["result"], indent=6, ensure_ascii=False))

                # Додаємо рядок до eval таблиці
                eval_rows.append({
                    "dataset": dataset_name,
                    "provider": f"{provider} ({result['model']})",
                    "json_valid": json_status,
                    "tasks_found": tasks_count,
                    "hallucinations": "— (manual check)",
                    "tokens_input": result["tokens_input"],
                    "tokens_output": result["tokens_output"],
                    "tokens_total": result["tokens_total"],
                    "cost": f"${cost}",
                    "latency": f"{result['latency']}s"
                })

            except Exception as e:
                print(f"     ❌ Error: {e}")
                eval_rows.append({
                    "dataset": dataset_name,
                    "provider": provider,
                    "json_valid": "❌ ERROR",
                    "tasks_found": 0,
                    "hallucinations": "—",
                    "tokens_input": 0,
                    "tokens_output": 0,
                    "tokens_total": 0,
                    "cost": "$0",
                    "latency": "—"
                })

    # ── Зберігаємо eval_results.csv ──
    csv_path = BASE_DIR / "eval_results.csv"
    if eval_rows:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=eval_rows[0].keys())
            writer.writeheader()
            writer.writerows(eval_rows)
        print(f"\n{'=' * 70}")
        print(f"📊 Evaluation matrix saved to: {csv_path}")

    # ── Виводимо таблицю ──
    print(f"\n{'=' * 70}")
    print("📊 EVALUATION MATRIX")
    print(f"{'=' * 70}")
    header = f"{'Dataset':<12} | {'Provider':<25} | {'JSON':^6} | {'Tasks':^6} | "
    header += f"{'Tokens':^8} | {'Cost':^10} | {'Latency':^8}"
    print(header)
    print("-" * len(header))
    for row in eval_rows:
        line = f"{row['dataset']:<12} | {row['provider']:<25} | {row['json_valid']:^6} | "
        line += f"{row['tasks_found']:^6} | {row['tokens_total']:^8} | "
        line += f"{row['cost']:^10} | {row['latency']:^8}"
        print(line)

    print(f"\n✅ Усі результати збережено у {RESULTS_DIR}/")
    print(f"✅ Evaluation matrix: {csv_path}")


# ── SINGLE FILE MODE ──
def run_single(filepath: str, provider: str = "ollama"):
    """Запускає агента на одному файлі"""
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    print(f"{'🤖' if provider == 'ollama' else '☁️'}  Testing {provider.upper()} "
          f"({OLLAMA_MODEL if provider == 'ollama' else ZAI_MODEL})...")
    print(f"📄 Input: {filepath} ({len(text)} chars)\n")

    result = extract_meeting_data(text, provider=provider)

    json_status = "✅ Valid" if result["json_valid"] else "❌ Invalid"
    print(f"JSON: {json_status} | Latency: {result['latency']}s | "
          f"Tokens: {result['tokens_total']}")

    if result["result"]:
        print(f"\n{json.dumps(result['result'], indent=2, ensure_ascii=False)}")
    else:
        print(f"\n❌ Raw response (first 500 chars):\n{result['raw'][:500]}")


# ── MAIN ──
if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Режим одного файлу: python extraction_agent.py <file> [provider]
        input_file = sys.argv[1]

        if input_file == "--all":
            # Запустити повну оцінку
            run_evaluation()
        else:
            provider = sys.argv[2] if len(sys.argv) > 2 else "ollama"
            run_single(input_file, provider)
    else:
        # Без аргументів — запускаємо повну оцінку
        run_evaluation()
