"""Mock LLM for offline demo (no API key needed)."""
import asyncio
import random


# Different "personalities" per model — для демо різниці у відповідях
MOCK_RESPONSES = {
    "meta-llama/llama-3.1-8b-instruct": (
        "Sure! Let me explain. The basic idea is straightforward. "
        "You start by understanding the problem, then apply a known pattern. "
        "It's similar to how other systems work in this domain."
    ),
    "mistralai/mistral-nemo": (
        "Bonjour! Here's my take. We must analyse the request structurally. "
        "Step one: identify the core constraint. Step two: propose a clean solution. "
        "Voilà — this approach is both elegant and pragmatic."
    ),
    "google/gemma-3-4b-it": (
        "Quick answer: this is a common scenario. The key insight is that "
        "you should focus on what matters most. "
        "Here's the practical approach with concrete examples and clear next steps."
    ),
}


async def stream_mock(model_id: str, prompt: str):
    """Yield tokens one by one with realistic delays."""
    # Different speeds per model
    speed_per_model = {
        "meta-llama/llama-3.1-8b-instruct": 0.04,
        "mistralai/mistral-nemo": 0.035,
        "google/gemma-3-4b-it": 0.025,           # fastest
    }
    delay = speed_per_model.get(model_id, 0.04)

    text = MOCK_RESPONSES.get(model_id, "Mock response.")
    # Add prompt echo for realism
    if "rag" in prompt.lower():
        text = "RAG (Retrieval-Augmented Generation) combines retrieval with LLM generation. " + text
    elif "fastapi" in prompt.lower():
        text = "FastAPI is a modern Python web framework. " + text

    # Stream word by word (more realistic than char by char)
    words = text.split(" ")
    for i, word in enumerate(words):
        await asyncio.sleep(delay + random.uniform(-0.01, 0.02))
        yield word + (" " if i < len(words) - 1 else "")

    # Simulate some models occasionally being slow
    if random.random() < 0.1:
        await asyncio.sleep(0.5)


async def fail_random(model_id: str, fail_rate: float = 0.0):
    """Simulate model failure for chaos engineering demo."""
    if random.random() < fail_rate:
        await asyncio.sleep(0.3)
        raise RuntimeError(f"Mock failure for {model_id}")
