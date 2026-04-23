"""
Генерує довгий документ ~15000 токенів для demo 3 (Silent Truncation).
Запустити один раз — створить data/long_doc.txt.
Секретний факт вставляється приблизно на позиції 10000 токенів.
"""
import os

SECRET = "The secret password is BANANA-42."

PARAGRAPHS = [
    "The history of software engineering traces back to the mid-twentieth century when computers began transitioning from experimental machines to practical business tools. Early programmers wrote instructions in assembly language, directly manipulating machine registers and memory addresses. The introduction of high-level languages such as FORTRAN and COBOL allowed engineers to express complex algorithms in forms closer to human language, dramatically increasing productivity.",
    "Distributed systems introduce challenges absent from single-machine software: partial failures, network partitions, and clock skew. Engineers working on these systems must reason about consistency models, from strong linearizability to eventual consistency, each with its own trade-offs in performance and correctness. CAP theorem formalizes the inherent tension between consistency, availability, and partition tolerance.",
    "Database design principles have evolved from normalized relational schemas toward schema-on-read approaches in data lakes. Relational databases enforce strict consistency through ACID transactions, while NoSQL databases sacrifice some guarantees for horizontal scalability. Choosing between them depends on workload characteristics, query patterns, and consistency requirements.",
    "Microservices architecture decomposes applications into small, independently deployable services communicating over networks. Each service owns its data and exposes a well-defined API. While this approach improves team autonomy and deployment flexibility, it introduces complexity in testing, observability, and distributed debugging that monoliths avoid.",
    "Container orchestration platforms like Kubernetes have become the standard for deploying cloud-native applications. Kubernetes abstracts infrastructure concerns, scheduling containers across clusters, handling service discovery, and managing rollouts. Its declarative API lets engineers describe desired state and the system reconciles reality with that specification.",
    "Observability encompasses three pillars: logs, metrics, and traces. Modern distributed systems require all three to diagnose issues effectively. Structured logging provides searchable event records, time-series metrics reveal trends and anomalies, and distributed tracing reconstructs request flows across service boundaries.",
    "Security in modern applications follows defense-in-depth principles. Input validation prevents injection attacks, authentication verifies identity, authorization enforces access policies, encryption protects data in transit and at rest, and audit logging provides forensic trails. No single control is sufficient; layers compensate for one another's weaknesses.",
    "Performance optimization is a discipline of measurement before change. Profilers reveal hotspots, benchmarks quantify improvements, and production monitoring confirms real-world impact. Common patterns include caching frequently accessed data, batching expensive operations, and parallelizing independent work across CPU cores.",
    "Version control systems like Git have transformed collaborative software development. The distributed model enables offline work, lightweight branching encourages experimentation, and merge algorithms handle most concurrent changes automatically. Pull request workflows add structure for code review and continuous integration.",
    "Testing strategies balance confidence against maintenance cost. Unit tests verify small pieces in isolation with mocks substituting for dependencies. Integration tests exercise component boundaries with real collaborators. End-to-end tests validate user-facing flows but run slowly and become brittle. The testing pyramid prescribes many fast tests and few slow ones.",
    "Continuous integration automates the build-test cycle on every commit, catching regressions quickly. Continuous delivery extends this to automated deployment, keeping the main branch always releasable. Feature flags decouple deployment from release, letting engineers ship code dormant until activated.",
    "Cloud providers offer a spectrum of abstraction levels. Infrastructure-as-a-Service gives raw virtual machines. Platform-as-a-Service hides machines behind managed runtimes. Function-as-a-Service executes code in response to events without any persistent server. Serverless computing maximizes operational simplicity but introduces cold-start latency and vendor lock-in.",
    "Machine learning systems differ from traditional software in that behavior depends on data, not only code. Training pipelines ingest examples, optimize model parameters, and produce artifacts that serve predictions. MLOps practices adapt DevOps principles to these pipelines, addressing data versioning, model monitoring, and drift detection.",
    "Networking fundamentals underpin all distributed computing. TCP provides reliable ordered delivery over unreliable IP networks through retransmission and windowing. DNS translates human-readable names into addresses. HTTP semantics have evolved from text-based request-response to binary multiplexed streams in HTTP/2 and HTTP/3.",
    "Concurrency primitives vary across languages and runtimes. Threads share memory and require locks to avoid races. Actors encapsulate state and communicate by message passing. Async/await syntax makes nonblocking I/O readable. Channels synchronize producers and consumers in concurrent pipelines. Each model suits different problem shapes.",
    "Functional programming emphasizes pure functions, immutable data, and composition. Languages like Haskell enforce purity at the type level, while multi-paradigm languages adopt functional techniques selectively. Benefits include easier reasoning about state and natural parallelism; costs include performance overhead from immutability and learning curve.",
    "API design shapes how services are consumed and evolved. REST relies on HTTP verbs and resource URLs. GraphQL lets clients specify response shape. gRPC uses Protocol Buffers over HTTP/2 for efficient binary communication. Versioning strategies range from URL paths to content negotiation to semantic versioning with deprecation policies.",
    "Data pipelines transform raw inputs into analytical datasets. Batch pipelines process bounded datasets at regular intervals. Streaming pipelines handle unbounded event streams with low latency. Lambda architecture combines both for different use cases; Kappa architecture treats streaming as the primary model.",
    "Caching accelerates systems by trading memory for latency. Cache invalidation is famously hard: TTL-based expiration is simple but imprecise, event-driven invalidation is precise but complex, and read-through caches hide complexity from callers. Write-through, write-behind, and write-around patterns differ in consistency and performance trade-offs.",
    "Search systems index documents for fast retrieval. Inverted indexes map terms to document lists, enabling millisecond queries across billions of documents. Modern search systems combine lexical matching with semantic similarity via vector embeddings, producing hybrid results superior to either alone.",
]


def main():
    target_tokens = 15000  # approximate
    # Rough approximation: 1 token ~= 0.75 words for English
    target_words = int(target_tokens * 0.75)

    words_per_paragraph = sum(len(p.split()) for p in PARAGRAPHS) / len(PARAGRAPHS)
    repeats_needed = int(target_words / words_per_paragraph) + 5

    out_lines = []
    for i in range(repeats_needed):
        p = PARAGRAPHS[i % len(PARAGRAPHS)]
        out_lines.append(f"Section {i + 1}. {p}")

    text = "\n\n".join(out_lines)

    # Insert secret at ~position 10000 tokens (~7500 words)
    words = text.split()
    insert_idx = 7500
    words.insert(insert_idx, SECRET)
    text = " ".join(words)

    out_path = os.path.join(os.path.dirname(__file__), "long_doc.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"Wrote {out_path}")
    print(f"Approx words: {len(text.split())}")
    print(f"Approx tokens: ~{int(len(text.split()) / 0.75)}")


if __name__ == "__main__":
    main()
