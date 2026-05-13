import os
import time
import json
import psutil
import numpy as np
import faiss
from pathlib import Path
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

from template.data_loader import load_cache, build_subset
from template.metrics import evaluate

os.environ["TOKENIZERS_PARALLELISM"] = "false"

def get_ram_mb():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

def build_flat_index(embeddings):
    d = embeddings.shape[1]
    index = faiss.IndexFlatIP(d)
    index.add(embeddings)
    return index

def build_hnsw_index(embeddings, m=32, ef_construction=64):
    d = embeddings.shape[1]
    index = faiss.IndexHNSWFlat(d, m)
    index.hnsw.efConstruction = ef_construction
    index.add(embeddings)
    return index

def hybrid_rrf(dense_ranks, sparse_ranks, k=60):
    scores = {}
    for rank, doc_id in enumerate(dense_ranks):
        scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
    for rank, doc_id in enumerate(sparse_ranks):
        scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
    
    sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [d[0] for d in sorted_docs]

def main():
    CACHE_PATH = Path("template/cache/corpus.json")
    if not CACHE_PATH.exists():
        print("Please run data_loader.py first to cache the corpus.")
        return

    pool, eval_set = load_cache(CACHE_PATH)
    
    print("Loading embedding model...")
    # Use MPS on Apple Silicon, CUDA on Nvidia, or CPU
    import torch
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = SentenceTransformer("BAAI/bge-small-en-v1.5", device=device)
    
    # Pre-compute embeddings for the entire pool to save time across runs
    print(f"Generating embeddings for {len(pool)} docs...")
    # Cache to disk as numpy array
    EMBEDDINGS_CACHE = Path("template/cache/embeddings.npy")
    if EMBEDDINGS_CACHE.exists():
        all_embeddings = np.load(EMBEDDINGS_CACHE)
        print("Loaded embeddings from cache.")
    else:
        docs = [d["text"] for d in pool]
        batch_size = 512
        all_embeddings = []
        print("Encoding in chunks to avoid tokenization memory spikes...")
        for i in tqdm(range(0, len(docs), batch_size), desc="Encoding batches"):
            batch = docs[i:i+batch_size]
            emb = model.encode(batch, show_progress_bar=False, normalize_embeddings=True)
            all_embeddings.append(emb)
        all_embeddings = np.vstack(all_embeddings)
        EMBEDDINGS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        np.save(EMBEDDINGS_CACHE, all_embeddings)
    
    doc_id_to_idx = {d["id"]: i for i, d in enumerate(pool)}
    
    # Query embeddings
    print("Generating query embeddings...")
    queries = [e["query"] for e in eval_set]
    query_embeddings = model.encode(queries, normalize_embeddings=True)
    
    sizes = [1000, 10000, 100000, 300000]
    results = {}
    
    for size in sizes:
        print(f"\n--- Running evaluation for size {size} ---")
        subset = build_subset(pool, eval_set, size=size, seed=42)
        subset_ids = [d["id"] for d in subset]
        subset_texts = [d["text"] for d in subset]
        
        # Get subset embeddings
        subset_indices = [doc_id_to_idx[did] for did in subset_ids]
        subset_embeddings = all_embeddings[subset_indices]
        
        size_results = {}
        
        # 1. Baseline: FAISS Flat
        print("Building Flat Index...")
        ram_before = get_ram_mb()
        flat_index = build_flat_index(subset_embeddings)
        ram_after = get_ram_mb()
        size_results["flat_ram_mb"] = ram_after - ram_before
        
        print("Searching Flat Index...")
        latencies = []
        retrieved_flat = []
        for q_emb in query_embeddings:
            t0 = time.time()
            distances, indices = flat_index.search(np.array([q_emb]), 10)
            t1 = time.time()
            latencies.append(t1 - t0)
            retrieved_flat.append([subset_ids[i] for i in indices[0]])
            
        size_results["flat_p50_ms"] = np.percentile(latencies, 50) * 1000
        size_results["flat_p95_ms"] = np.percentile(latencies, 95) * 1000
        size_results["flat_metrics"] = evaluate(eval_set, retrieved_flat)
        
        # 2. Fix 1: FAISS HNSW
        print("Building HNSW Index...")
        ram_before = get_ram_mb()
        hnsw_index = build_hnsw_index(subset_embeddings)
        ram_after = get_ram_mb()
        size_results["hnsw_ram_mb"] = ram_after - ram_before
        
        print("Searching HNSW Index...")
        latencies = []
        retrieved_hnsw = []
        hnsw_index.hnsw.efSearch = 64
        for q_emb in query_embeddings:
            t0 = time.time()
            distances, indices = hnsw_index.search(np.array([q_emb]), 10)
            t1 = time.time()
            latencies.append(t1 - t0)
            retrieved_hnsw.append([subset_ids[i] for i in indices[0]])
            
        size_results["hnsw_p50_ms"] = np.percentile(latencies, 50) * 1000
        size_results["hnsw_p95_ms"] = np.percentile(latencies, 95) * 1000
        size_results["hnsw_metrics"] = evaluate(eval_set, retrieved_hnsw)
        
        # 3. Fix 2: Hybrid (BM25 + Flat)
        print("Building BM25 Index...")
        # Simple tokenization by split() for speed. 
        # In a real system, you'd use a better tokenizer and lowercasing, 
        # but let's stick to this as basic baseline.
        tokenized_corpus = [doc.lower().split() for doc in subset_texts]
        bm25 = BM25Okapi(tokenized_corpus)
        
        print("Searching Hybrid...")
        latencies = []
        retrieved_hybrid = []
        for i, q in enumerate(queries):
            t0 = time.time()
            tokenized_query = q.lower().split()
            # BM25 retrieve top 60
            bm25_scores = bm25.get_scores(tokenized_query)
            top_sparse_idx = np.argsort(bm25_scores)[::-1][:60]
            sparse_ranks = [subset_ids[idx] for idx in top_sparse_idx]
            
            # Dense retrieve top 60
            distances, indices = flat_index.search(np.array([query_embeddings[i]]), 60)
            dense_ranks = [subset_ids[idx] for idx in indices[0]]
            
            # Hybrid RRF
            fused = hybrid_rrf(dense_ranks, sparse_ranks, k=60)
            t1 = time.time()
            latencies.append(t1 - t0)
            retrieved_hybrid.append(fused[:10])
            
        size_results["hybrid_p50_ms"] = np.percentile(latencies, 50) * 1000
        size_results["hybrid_p95_ms"] = np.percentile(latencies, 95) * 1000
        size_results["hybrid_metrics"] = evaluate(eval_set, retrieved_hybrid)
        
        results[str(size)] = size_results
        
        print(f"Results for size {size}:")
        print(f"  Flat:   Recall@1={size_results['flat_metrics']['recall@1']:.3f}, p95={size_results['flat_p95_ms']:.2f}ms")
        print(f"  HNSW:   Recall@1={size_results['hnsw_metrics']['recall@1']:.3f}, p95={size_results['hnsw_p95_ms']:.2f}ms")
        print(f"  Hybrid: Recall@1={size_results['hybrid_metrics']['recall@1']:.3f}, p95={size_results['hybrid_p95_ms']:.2f}ms")
        
    with open("results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Saved results to results.json")

if __name__ == "__main__":
    main()
