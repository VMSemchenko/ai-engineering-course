import json
import matplotlib.pyplot as plt

def main():
    with open("results.json", "r") as f:
        results = json.load(f)
        
    sizes = sorted([int(s) for s in results.keys()])
    sizes_str = [f"{s//1000}K" if s >= 1000 else str(s) for s in sizes]
    
    flat_p95 = [results[str(s)]["flat_p95_ms"] for s in sizes]
    hnsw_p95 = [results[str(s)]["hnsw_p95_ms"] for s in sizes]
    
    flat_recall1 = [results[str(s)]["flat_metrics"]["recall@1"] for s in sizes]
    hybrid_recall1 = [results[str(s)]["hybrid_metrics"]["recall@1"] for s in sizes]
    flat_recall10 = [results[str(s)]["flat_metrics"]["recall@10"] for s in sizes]
    hybrid_recall10 = [results[str(s)]["hybrid_metrics"]["recall@10"] for s in sizes]
    
    # Chart 1: Latency
    plt.figure(figsize=(10, 6))
    plt.plot(sizes_str, flat_p95, marker='o', linewidth=2, label='Flat Index (Brute Force)')
    plt.plot(sizes_str, hnsw_p95, marker='s', linewidth=2, label='HNSW Index')
    plt.title("Scaling vs Latency (p95)", fontsize=14)
    plt.xlabel("Corpus Size", fontsize=12)
    plt.ylabel("Latency p95 (ms)", fontsize=12)
    plt.legend(fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig("latency_scaling.png", dpi=300)
    plt.close()
    
    # Chart 2: Recall@1 vs Recall@10
    plt.figure(figsize=(10, 6))
    plt.plot(sizes_str, flat_recall1, marker='o', color='blue', linewidth=2, label='Dense Recall@1')
    plt.plot(sizes_str, flat_recall10, marker='o', color='lightblue', linestyle='--', linewidth=2, label='Dense Recall@10')
    plt.plot(sizes_str, hybrid_recall1, marker='s', color='green', linewidth=2, label='Hybrid Recall@1')
    plt.plot(sizes_str, hybrid_recall10, marker='s', color='lightgreen', linestyle='--', linewidth=2, label='Hybrid Recall@10')
    
    plt.title("Scaling vs Recall", fontsize=14)
    plt.xlabel("Corpus Size", fontsize=12)
    plt.ylabel("Recall Score", fontsize=12)
    plt.legend(fontsize=10)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig("recall_scaling.png", dpi=300)
    plt.close()
    
    print("Saved charts to latency_scaling.png and recall_scaling.png")

if __name__ == "__main__":
    main()
