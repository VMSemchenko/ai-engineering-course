"""Token-based rate limiting — in-memory token bucket per API key."""

import time
from dataclasses import dataclass, field

from fastapi import HTTPException


@dataclass
class TokenBucket:
    """Token bucket for a single API key."""
    capacity: int
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.monotonic)

    def __post_init__(self):
        self.tokens = float(self.capacity)

    @property
    def refill_rate(self) -> float:
        """Tokens per second — full refill in 60 seconds."""
        return self.capacity / 60.0

    def refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def try_consume(self, amount: int) -> tuple[bool, int]:
        """Try to consume tokens. Returns (allowed, retry_after_seconds)."""
        self.refill()
        if self.tokens >= amount:
            self.tokens -= amount
            return True, 0
        deficit = amount - self.tokens
        retry_after = int(deficit / self.refill_rate) + 1
        return False, retry_after


# Global bucket store
_buckets: dict[str, TokenBucket] = {}


def get_bucket(api_key: str, capacity: int) -> TokenBucket:
    """Get or create a token bucket for the given API key."""
    if api_key not in _buckets:
        _buckets[api_key] = TokenBucket(capacity=capacity)
    bucket = _buckets[api_key]
    # Update capacity if tier changed
    if bucket.capacity != capacity:
        bucket.capacity = capacity
    return bucket


def check_rate_limit(api_key: str, token_limit: int, estimated_tokens: int = 500) -> None:
    """Check rate limit before processing. Raises 429 if exceeded.

    Uses an estimated token count as a pre-check.
    Actual tokens are consumed after the LLM responds.
    """
    bucket = get_bucket(api_key, token_limit)
    allowed, retry_after = bucket.try_consume(estimated_tokens)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too Many Requests — token rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )


def consume_tokens(api_key: str, token_limit: int, actual_tokens: int) -> None:
    """Consume actual tokens after LLM response.

    The pre-check already consumed an estimate; this adjusts the difference.
    """
    bucket = get_bucket(api_key, token_limit)
    # We already consumed ~500 estimated tokens in the pre-check.
    # Now adjust for the real usage.
    adjustment = actual_tokens - 500  # positive = consumed more than estimated
    if adjustment > 0:
        bucket.tokens = max(0, bucket.tokens - adjustment)
    elif adjustment < 0:
        # Give back the over-estimated tokens
        bucket.tokens = min(bucket.capacity, bucket.tokens - adjustment)


def refund_tokens(api_key: str, token_limit: int, amount: int = 500) -> None:
    """Refund pre-consumed tokens (e.g., on disconnect or cache hit)."""
    bucket = get_bucket(api_key, token_limit)
    bucket.tokens = min(bucket.capacity, bucket.tokens + amount)
