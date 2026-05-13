"""Langfuse observability — optional tracing integration."""

import os
from contextlib import contextmanager
from typing import Any

from .config import LANGFUSE_ENABLED, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST

_langfuse = None


def get_langfuse():
    """Get Langfuse client (lazy init, returns None if not configured)."""
    global _langfuse
    if not LANGFUSE_ENABLED:
        return None
    if _langfuse is None:
        try:
            from langfuse import Langfuse
            _langfuse = Langfuse(
                public_key=LANGFUSE_PUBLIC_KEY,
                secret_key=LANGFUSE_SECRET_KEY,
                host=LANGFUSE_HOST,
            )
            print("🔭 Langfuse connected")
        except Exception as e:
            print(f"⚠️  Langfuse init failed: {e}")
            return None
    return _langfuse


class TraceContext:
    """Wrapper for Langfuse trace that gracefully degrades to no-op."""

    def __init__(self, name: str, metadata: dict | None = None):
        self.name = name
        self.trace = None
        self._current_span = None
        lf = get_langfuse()
        if lf:
            try:
                self.trace = lf.trace(name=name, metadata=metadata or {})
            except Exception:
                pass

    def span(self, name: str, **kwargs) -> "TraceContext":
        """Create a child span."""
        if self.trace:
            try:
                self._current_span = self.trace.span(name=name, **kwargs)
            except Exception:
                pass
        return self

    def end_span(self, **kwargs) -> None:
        """End the current span."""
        if self._current_span:
            try:
                self._current_span.end(**kwargs)
            except Exception:
                pass
            self._current_span = None

    def generation(self, name: str, **kwargs) -> Any:
        """Log a generation (LLM call)."""
        if self.trace:
            try:
                return self.trace.generation(name=name, **kwargs)
            except Exception:
                pass
        return None

    def update(self, **kwargs) -> None:
        """Update trace metadata."""
        if self.trace:
            try:
                self.trace.update(**kwargs)
            except Exception:
                pass


def create_trace(name: str, metadata: dict | None = None) -> TraceContext:
    """Create a new trace context. No-op if Langfuse not configured."""
    return TraceContext(name=name, metadata=metadata)


def flush() -> None:
    """Flush pending events to Langfuse."""
    lf = get_langfuse()
    if lf:
        try:
            lf.flush()
        except Exception:
            pass
