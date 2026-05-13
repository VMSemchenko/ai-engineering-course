"""Cost tracking — SQLite storage for request logs."""

import sqlite3
import uuid
from datetime import datetime, date
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.parent / "data" / "costs.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS cost_log (
    request_id     TEXT PRIMARY KEY,
    api_key        TEXT NOT NULL,
    model          TEXT NOT NULL,
    input_tokens   INTEGER NOT NULL DEFAULT 0,
    output_tokens  INTEGER NOT NULL DEFAULT 0,
    cost_usd       REAL NOT NULL DEFAULT 0.0,
    latency_ms     INTEGER NOT NULL DEFAULT 0,
    ttft_ms        INTEGER NOT NULL DEFAULT 0,
    cache_hit      BOOLEAN NOT NULL DEFAULT 0,
    fallback_used  BOOLEAN NOT NULL DEFAULT 0,
    output_filtered BOOLEAN NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL
);
"""


@contextmanager
def _get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_TABLE)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def log_request(
    api_key: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    latency_ms: int,
    ttft_ms: int,
    cache_hit: bool = False,
    fallback_used: bool = False,
    output_filtered: bool = False,
) -> str:
    """Log a request to the cost database. Returns request_id."""
    request_id = str(uuid.uuid4())
    with _get_db() as db:
        db.execute(
            """INSERT INTO cost_log
               (request_id, api_key, model, input_tokens, output_tokens,
                cost_usd, latency_ms, ttft_ms, cache_hit, fallback_used,
                output_filtered, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                request_id, api_key, model,
                input_tokens, output_tokens, cost_usd,
                latency_ms, ttft_ms,
                cache_hit, fallback_used, output_filtered,
                datetime.utcnow().isoformat(),
            ),
        )
    return request_id


def get_today_usage(api_key: str) -> dict:
    """Get aggregated usage for today for a given API key."""
    today = date.today().isoformat()
    with _get_db() as db:
        row = db.execute(
            """SELECT
                 COUNT(*) as requests,
                 COALESCE(SUM(input_tokens + output_tokens), 0) as tokens,
                 COALESCE(SUM(cost_usd), 0.0) as cost_usd
               FROM cost_log
               WHERE api_key = ? AND created_at >= ?""",
            (api_key, today),
        ).fetchone()
    return {
        "requests": row["requests"],
        "tokens": row["tokens"],
        "cost_usd": round(row["cost_usd"], 6),
    }


def get_breakdown(api_key: str) -> dict:
    """Get per-model breakdown with cache/fallback rates and latency stats."""
    today = date.today().isoformat()
    with _get_db() as db:
        # Per-model stats
        rows = db.execute(
            """SELECT
                 model,
                 COUNT(*) as requests,
                 COALESCE(SUM(input_tokens + output_tokens), 0) as tokens,
                 COALESCE(SUM(cost_usd), 0.0) as cost_usd,
                 COALESCE(AVG(latency_ms), 0) as avg_latency_ms
               FROM cost_log
               WHERE api_key = ? AND created_at >= ?
               GROUP BY model""",
            (api_key, today),
        ).fetchall()

        # Overall stats
        totals = db.execute(
            """SELECT
                 COUNT(*) as total,
                 COALESCE(SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END), 0) as cache_hits,
                 COALESCE(SUM(CASE WHEN fallback_used THEN 1 ELSE 0 END), 0) as fallbacks,
                 COALESCE(AVG(latency_ms), 0) as avg_latency_ms
               FROM cost_log
               WHERE api_key = ? AND created_at >= ?""",
            (api_key, today),
        ).fetchone()

        # P95 latency
        p95_row = db.execute(
            """SELECT latency_ms FROM cost_log
               WHERE api_key = ? AND created_at >= ?
               ORDER BY latency_ms ASC""",
            (api_key, today),
        ).fetchall()

    total = totals["total"]
    p95_latency = 0
    if p95_row:
        idx = int(len(p95_row) * 0.95)
        idx = min(idx, len(p95_row) - 1)
        p95_latency = p95_row[idx]["latency_ms"]

    return {
        "by_model": {
            row["model"]: {
                "requests": row["requests"],
                "tokens": row["tokens"],
                "cost_usd": round(row["cost_usd"], 6),
                "avg_latency_ms": round(row["avg_latency_ms"]),
            }
            for row in rows
        },
        "cache_hit_rate": round(totals["cache_hits"] / max(total, 1), 3),
        "fallback_rate": round(totals["fallbacks"] / max(total, 1), 3),
        "avg_latency_ms": round(totals["avg_latency_ms"]),
        "p95_latency_ms": p95_latency,
        "total_requests": total,
    }
