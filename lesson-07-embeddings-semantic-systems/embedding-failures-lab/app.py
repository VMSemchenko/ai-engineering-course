"""
Embedding Failure Modes Lab — FastAPI backend.

Демонструє 4 failure modes embedding-систем:
  1. Reranking (bi-encoder vs cross-encoder)
  2. Negation Blindness
  3. Silent Truncation
  4. Lost in the Middle

Запуск: uvicorn app:app --reload --port 8001
"""

import json
import os
from typing import Optional

import numpy as np
import tiktoken
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="Embedding Failure Modes Lab")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")

HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "data")

app.mount("/static", StaticFiles(directory=HERE), name="static")


# ─── Data loading ─────────────────────────────────────────────────────────────

with open(os.path.join(DATA_DIR, "python_docs.json"), "r", encoding="utf-8") as f:
    PYTHON_DOCS = json.load(f)

with open(os.path.join(DATA_DIR, "medical_texts.json"), "r", encoding="utf-8") as f:
    MEDICAL = json.load(f)

with open(os.path.join(DATA_DIR, "qa_passages.json"), "r", encoding="utf-8") as f:
    QA = json.load(f)

with open(os.path.join(DATA_DIR, "domain_mismatch.json"), "r", encoding="utf-8") as f:
    DOMAIN_DATA = json.load(f)

with open(os.path.join(DATA_DIR, "long_doc.txt"), "r", encoding="utf-8") as f:
    LONG_DOC = f.read()


# ─── Helpers ──────────────────────────────────────────────────────────────────

MODEL_LIMITS = {
    "text-embedding-3-small": 8191,
    "text-embedding-ada-002": 8191,
    "all-MiniLM-L6-v2": 512,  # simulated limit; we use tiktoken for approximation
}


def get_openai_client(api_key: Optional[str] = None) -> AsyncOpenAI:
    key = api_key or OPENAI_API_KEY
    if not key:
        raise HTTPException(
            status_code=400,
            detail="OPENAI_API_KEY не встановлений. Додай у .env або передай X-OpenAI-Key header.",
        )
    return AsyncOpenAI(api_key=key)


def get_cohere_key(api_key: Optional[str] = None) -> str:
    key = api_key or COHERE_API_KEY
    if not key:
        raise HTTPException(
            status_code=400,
            detail="COHERE_API_KEY не встановлений. Додай у .env або передай X-Cohere-Key header.",
        )
    return key


def count_tokens(text: str, model: str = "text-embedding-3-small") -> int:
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


async def embed_batch(client: AsyncOpenAI, texts: list[str], model: str = "text-embedding-3-small") -> np.ndarray:
    resp = await client.embeddings.create(model=model, input=texts)
    return np.array([d.embedding for d in resp.data])


# ─── Root / static ────────────────────────────────────────────────────────────


@app.get("/")
async def root():
    return FileResponse(os.path.join(HERE, "index.html"))


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "openai_key_present": bool(OPENAI_API_KEY),
        "cohere_key_present": bool(COHERE_API_KEY),
    }


# ─── Demo 1: Reranking ────────────────────────────────────────────────────────


class Demo1Request(BaseModel):
    query: str


@app.post("/api/demo1/search")
async def demo1_search(
    req: Demo1Request,
    x_openai_key: Optional[str] = Header(None),
    x_cohere_key: Optional[str] = Header(None),
):
    """Vector search (OpenAI embeddings) vs Vector + Cohere Rerank."""
    client = get_openai_client(x_openai_key)
    cohere_key = get_cohere_key(x_cohere_key)

    texts = [d["text"] for d in PYTHON_DOCS]

    # Embed query and all docs (docs could be cached but keeping it simple & live)
    doc_embeds = await embed_batch(client, texts)
    query_embed = (await embed_batch(client, [req.query]))[0]

    # Cosine similarity and top-10
    sims = np.array([cosine(query_embed, e) for e in doc_embeds])
    top10_idx = np.argsort(-sims)[:10].tolist()

    vector_results = [
        {
            "id": PYTHON_DOCS[i]["id"],
            "text": PYTHON_DOCS[i]["text"],
            "score": float(sims[i]),
            "rank": rank + 1,
        }
        for rank, i in enumerate(top10_idx)
    ]

    # Rerank via Cohere
    import cohere  # local import to defer

    co = cohere.ClientV2(api_key=cohere_key)
    candidate_texts = [PYTHON_DOCS[i]["text"] for i in top10_idx]
    try:
        rerank_resp = co.rerank(
            model="rerank-english-v3.0",
            query=req.query,
            documents=candidate_texts,
            top_n=10,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cohere rerank помилка: {e}")

    # Build reranked list with original doc IDs
    rerank_results = []
    for new_rank, r in enumerate(rerank_resp.results):
        orig_pos = r.index  # index into candidate_texts (== top10_idx order)
        doc_idx = top10_idx[orig_pos]
        old_rank = orig_pos + 1
        new_rank_1 = new_rank + 1
        rerank_results.append(
            {
                "id": PYTHON_DOCS[doc_idx]["id"],
                "text": PYTHON_DOCS[doc_idx]["text"],
                "score": float(r.relevance_score),
                "rank": new_rank_1,
                "delta": old_rank - new_rank_1,  # positive = moved up
            }
        )

    return {"vector_results": vector_results, "rerank_results": rerank_results}


# ─── Demo 2: Negation ─────────────────────────────────────────────────────────


class Demo2SimRequest(BaseModel):
    text_a: str
    text_b: str


@app.post("/api/demo2/similarity")
async def demo2_similarity(req: Demo2SimRequest, x_openai_key: Optional[str] = Header(None)):
    client = get_openai_client(x_openai_key)
    embeds = await embed_batch(client, [req.text_a, req.text_b])
    return {"cosine": cosine(embeds[0], embeds[1])}


class Demo2RetrieveRequest(BaseModel):
    query: str = "drugs NOT safe for pregnant patients"


@app.post("/api/demo2/retrieve")
async def demo2_retrieve(req: Demo2RetrieveRequest, x_openai_key: Optional[str] = Header(None)):
    """Naive vector search (returns mix of safe/unsafe) vs NLI-filtered via GPT-4o-mini."""
    client = get_openai_client(x_openai_key)

    statements = MEDICAL["statements"]
    texts = [s["text"] for s in statements]

    doc_embeds = await embed_batch(client, texts)
    query_embed = (await embed_batch(client, [req.query]))[0]

    sims = [cosine(query_embed, e) for e in doc_embeds]
    top_indices = np.argsort(-np.array(sims))[:10].tolist()

    naive = [
        {
            "id": statements[i]["id"],
            "text": statements[i]["text"],
            "label": statements[i]["label"],
            "score": float(sims[i]),
        }
        for i in top_indices
    ]

    # NLI-filter: ask gpt-4o-mini to classify each candidate as NOT_SAFE vs SAFE
    # relative to the user's query intent ("drugs NOT safe").
    candidate_texts = [s["text"] for s in naive]
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(candidate_texts))
    system = (
        "You are a strict medical-text classifier. Given a list of statements about drugs, "
        "for EACH statement decide whether it asserts the drug is NOT SAFE during pregnancy. "
        "Return ONLY JSON in the form {\"verdicts\":[true,false,...]} in the exact order given."
    )
    user = f"Statements:\n{numbered}\n\nReturn verdicts as JSON."
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        verdicts = json.loads(resp.choices[0].message.content).get("verdicts", [])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"NLI classifier помилка: {e}")

    nli_filtered = [naive[i] for i, v in enumerate(verdicts) if v]

    return {"naive": naive, "nli_filtered": nli_filtered}


@app.post("/api/demo2/pca")
async def demo2_pca(x_openai_key: Optional[str] = Header(None)):
    """PCA to 2D of the 5 preset pairs so students see love/hate sit next to each other."""
    client = get_openai_client(x_openai_key)
    pairs = MEDICAL["pairs"]
    texts = []
    meta = []
    for p in pairs:
        texts.append(p["a"])
        meta.append({"label": p["a"], "pair_id": p["id"], "side": "a"})
        texts.append(p["b"])
        meta.append({"label": p["b"], "pair_id": p["id"], "side": "b"})

    embeds = await embed_batch(client, texts)

    # PCA via SVD
    X = embeds - embeds.mean(axis=0, keepdims=True)
    U, S, Vt = np.linalg.svd(X, full_matrices=False)
    coords_2d = U[:, :2] * S[:2]

    points = [
        {
            "label": m["label"],
            "pair_id": m["pair_id"],
            "side": m["side"],
            "x": float(coords_2d[i, 0]),
            "y": float(coords_2d[i, 1]),
        }
        for i, m in enumerate(meta)
    ]
    return {"points": points}


# ─── Demo 3: Silent Truncation ────────────────────────────────────────────────


class Demo3TokensRequest(BaseModel):
    text: str
    model: str = "text-embedding-3-small"


@app.post("/api/demo3/tokens")
async def demo3_tokens(req: Demo3TokensRequest):
    limit = MODEL_LIMITS.get(req.model, 8191)
    total = count_tokens(req.text, model="text-embedding-3-small")  # all use cl100k for counting
    used = min(total, limit)
    lost = max(0, total - limit)
    return {
        "total_tokens": total,
        "model_limit": limit,
        "used": used,
        "lost": lost,
        "truncated": lost > 0,
        "model": req.model,
    }


class Demo3SearchRequest(BaseModel):
    query: str = "What is the secret password?"
    use_chunking: bool = True
    chunk_size_tokens: int = 400
    model: str = "all-MiniLM-L6-v2"  # the "bad" one with 512-token limit


@app.post("/api/demo3/search")
async def demo3_search(req: Demo3SearchRequest, x_openai_key: Optional[str] = Header(None)):
    """
    'Find the secret' demo:
      - without chunking: embed the entire document truncated to model_limit tokens
                          (simulating the silent truncation), query → best match fails
      - with chunking: split doc into chunks of chunk_size tokens, embed each,
                       find best match — succeeds
    """
    client = get_openai_client(x_openai_key)
    limit = MODEL_LIMITS.get(req.model, 8191)

    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(LONG_DOC)
    total_tokens = len(tokens)

    query_embed = (await embed_batch(client, [req.query]))[0]

    if not req.use_chunking:
        # Simulate truncation: keep only first `limit` tokens
        truncated_text = enc.decode(tokens[:limit])
        doc_embed = (await embed_batch(client, [truncated_text]))[0]
        score = cosine(query_embed, doc_embed)
        contains_secret = "BANANA-42" in truncated_text
        return {
            "mode": "no_chunking",
            "total_tokens": total_tokens,
            "used_tokens": min(total_tokens, limit),
            "lost_tokens": max(0, total_tokens - limit),
            "best_score": float(score),
            "found_secret": contains_secret,
            "best_chunk": truncated_text[:400] + ("…" if len(truncated_text) > 400 else ""),
            "explanation": "Документ обрізався до перших {} токенів. Секрет знаходиться далі і був втрачений.".format(limit)
            if not contains_secret
            else "Випадково секрет був у перших токенах.",
        }

    # With chunking — split into chunks, embed in batches
    chunk_size = req.chunk_size_tokens
    chunks = []
    for i in range(0, total_tokens, chunk_size):
        chunk_tokens = tokens[i : i + chunk_size]
        chunks.append(enc.decode(chunk_tokens))

    # Embed in batches of 50
    chunk_embeds = []
    for i in range(0, len(chunks), 50):
        batch = chunks[i : i + 50]
        resp = await client.embeddings.create(model="text-embedding-3-small", input=batch)
        chunk_embeds.extend([np.array(d.embedding) for d in resp.data])

    scores = [cosine(query_embed, e) for e in chunk_embeds]
    best_idx = int(np.argmax(scores))
    best_chunk_text = chunks[best_idx]
    contains_secret = "BANANA-42" in best_chunk_text

    return {
        "mode": "chunking",
        "total_tokens": total_tokens,
        "num_chunks": len(chunks),
        "chunk_size": chunk_size,
        "best_score": float(scores[best_idx]),
        "best_chunk_index": best_idx,
        "found_secret": contains_secret,
        "best_chunk": best_chunk_text[:500] + ("…" if len(best_chunk_text) > 500 else ""),
        "explanation": "Знайшли чанк із секретом серед {} чанків.".format(len(chunks))
        if contains_secret
        else "Найрелевантніший чанк не містить секрет — перевір chunk_size.",
    }


# ─── Demo 4: Lost in the Middle ───────────────────────────────────────────────


class Demo4Request(BaseModel):
    position: int  # 1-based rank of where goldfish fact goes (1..total_chunks)
    total_chunks: int = 10
    run_all: bool = False


def build_prompt(position: int, total_chunks: int) -> str:
    gold = QA["goldfish_fact"]
    distractors = QA["distractors"]
    if total_chunks - 1 > len(distractors):
        # Repeat distractors if needed for slider up to 20
        distractors = (distractors * ((total_chunks // len(distractors)) + 2))[: total_chunks - 1]
    else:
        distractors = distractors[: total_chunks - 1]

    chunks = distractors.copy()
    # Insert goldfish at 1-based position
    insert_idx = max(0, min(position - 1, total_chunks - 1))
    chunks.insert(insert_idx, gold)
    chunks = chunks[:total_chunks]  # safety

    numbered = "\n\n".join(f"[Passage {i + 1}] {c}" for i, c in enumerate(chunks))
    return (
        f"You are given {total_chunks} passages. Answer the question using ONLY the passages.\n\n"
        f"{numbered}\n\n"
        f"Question: {QA['query']}\n"
        f"Short answer:"
    )


def is_correct(answer: str) -> bool:
    a = answer.lower()
    return "month" in a and "second" not in a


async def run_single(client: AsyncOpenAI, position: int, total_chunks: int) -> dict:
    prompt = build_prompt(position, total_chunks)
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=80,
    )
    answer = resp.choices[0].message.content.strip()
    return {
        "position": position,
        "total_chunks": total_chunks,
        "answer": answer,
        "correct": is_correct(answer),
    }


@app.post("/api/demo4/run")
async def demo4_run(req: Demo4Request, x_openai_key: Optional[str] = Header(None)):
    client = get_openai_client(x_openai_key)

    if not req.run_all:
        result = await run_single(client, req.position, req.total_chunks)
        return result

    # Run all positions: 1, 3, 5, 8, 10 (or scaled to total_chunks)
    positions = [1, max(1, req.total_chunks // 4), max(1, req.total_chunks // 2),
                 max(1, (3 * req.total_chunks) // 4), req.total_chunks]
    positions = sorted(set(positions))

    results = []
    for pos in positions:
        results.append(await run_single(client, pos, req.total_chunks))
    return {"results": results, "total_chunks": req.total_chunks}


# ─── Demo 5: Domain Mismatch ──────────────────────────────────────────────────


ALLOWED_EMBED_MODELS = {
    "text-embedding-3-small",
    "text-embedding-3-large",
    "text-embedding-ada-002",
}


class Demo5SearchRequest(BaseModel):
    query: str
    model: str = "text-embedding-3-small"


@app.post("/api/demo5/search")
async def demo5_search(req: Demo5SearchRequest, x_openai_key: Optional[str] = Header(None)):
    """
    Retrieve top matches across 18 mixed-domain chunks (code/legal/general)
    using a general-purpose embedder. Show which domain each hit came from —
    often the embedder groups by surface domain lexicon rather than by semantics.
    """
    if req.model not in ALLOWED_EMBED_MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown model: {req.model}")
    client = get_openai_client(x_openai_key)

    chunks = DOMAIN_DATA["chunks"]
    texts = [c["text"] for c in chunks]

    doc_embeds = await embed_batch(client, texts, model=req.model)
    query_embed = (await embed_batch(client, [req.query], model=req.model))[0]

    sims = [cosine(query_embed, e) for e in doc_embeds]
    ranked = sorted(
        [
            {
                "id": chunks[i]["id"],
                "text": chunks[i]["text"],
                "domain": chunks[i]["domain"],
                "topic": chunks[i]["topic"],
                "score": float(sims[i]),
            }
            for i in range(len(chunks))
        ],
        key=lambda x: -x["score"],
    )
    return {"results": ranked[:10], "total": len(chunks), "model": req.model}


class Demo5PcaRequest(BaseModel):
    model: str = "text-embedding-3-small"


@app.post("/api/demo5/pca")
async def demo5_pca(req: Demo5PcaRequest, x_openai_key: Optional[str] = Header(None)):
    """2D projection of all 18 chunks so students can see domain clusters."""
    if req.model not in ALLOWED_EMBED_MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown model: {req.model}")
    client = get_openai_client(x_openai_key)

    chunks = DOMAIN_DATA["chunks"]
    texts = [c["text"] for c in chunks]
    embeds = await embed_batch(client, texts, model=req.model)

    X = embeds - embeds.mean(axis=0, keepdims=True)
    U, S, Vt = np.linalg.svd(X, full_matrices=False)
    coords_2d = U[:, :2] * S[:2]

    points = [
        {
            "id": chunks[i]["id"],
            "label": chunks[i]["text"][:60] + ("…" if len(chunks[i]["text"]) > 60 else ""),
            "domain": chunks[i]["domain"],
            "topic": chunks[i]["topic"],
            "x": float(coords_2d[i, 0]),
            "y": float(coords_2d[i, 1]),
        }
        for i in range(len(chunks))
    ]
    return {"points": points, "model": req.model}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
