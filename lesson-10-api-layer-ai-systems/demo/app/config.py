import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
USE_MOCK = os.getenv("USE_MOCK", "true").lower() == "true" or not OPENROUTER_API_KEY

# Three cheap models battling each other.
# Prices verified on OpenRouter — найдешевші моделі від трьох різних провайдерів.
MODELS = [
    {
        "id": "meta-llama/llama-3.1-8b-instruct",
        "label": "Llama 3.1 8B",
        "provider": "Meta",
        "color": "#0084ff",
        "price_in": 0.02,     # $/1M input tokens
        "price_out": 0.05,
    },
    {
        "id": "mistralai/mistral-nemo",
        "label": "Mistral Nemo 12B",
        "provider": "Mistral",
        "color": "#ff7000",
        "price_in": 0.02,
        "price_out": 0.03,    # найдешевший output на OpenRouter
    },
    {
        "id": "google/gemma-3-4b-it",
        "label": "Gemma 3 4B",
        "provider": "Google",
        "color": "#4285f4",
        "price_in": 0.04,
        "price_out": 0.08,
    },
]

# Concurrency limit — max 6 simultaneous LLM calls (3 models x 2 concurrent users)
CONCURRENCY_LIMIT = 6
