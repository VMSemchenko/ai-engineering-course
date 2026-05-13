"""Prompt injection detection and output filtering."""

import re
import logging
from pathlib import Path
from fastapi import HTTPException

# Set up loggers for suspicious activity
_logs_dir = Path(__file__).parent.parent / "logs"
_logs_dir.mkdir(exist_ok=True)

_request_logger = logging.getLogger("security.requests")
_response_logger = logging.getLogger("security.responses")

_req_handler = logging.FileHandler(_logs_dir / "suspicious_requests.log")
_req_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
_request_logger.addHandler(_req_handler)
_request_logger.setLevel(logging.WARNING)

_resp_handler = logging.FileHandler(_logs_dir / "suspicious_responses.log")
_resp_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
_response_logger.addHandler(_resp_handler)
_response_logger.setLevel(logging.WARNING)

# ── Input patterns ───────────────────────────────────────────
MAX_INPUT_LENGTH = 4000

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+the\s+above",
    r"system\s*:",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"</s>",
    r"you\s+are\s+now",
    r"forget\s+(all\s+)?(your\s+)?instructions",
    r"reveal\s+(your\s+)?(system\s+)?prompt",
    r"print\s+(your\s+)?(system\s+)?prompt",
    r"show\s+(me\s+)?(your\s+)?(system\s+)?prompt",
    r"act\s+as\s+if\s+you\s+have\s+no\s+restrictions",
    r"disregard\s+(all\s+)?prior",
    r"\[INST\]",
    r"\[/INST\]",
]

_compiled_patterns = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

# ── System prompt fragments to watch for in output ──────────
SYSTEM_FRAGMENTS = [
    "you are a helpful q&a assistant",
    "<context>",
    "</context>",
    "<user_query>",
    "</user_query>",
    "answer the following user question based on the context above",
]


def check_input(text: str) -> None:
    """Validate user input for length and injection patterns.

    Raises HTTPException 400 if suspicious.
    """
    if len(text) > MAX_INPUT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Input too long: {len(text)} chars (max {MAX_INPUT_LENGTH})",
        )

    for pattern in _compiled_patterns:
        if pattern.search(text):
            _request_logger.warning(
                "Injection attempt detected | pattern=%s | input=%s",
                pattern.pattern,
                text[:200],
            )
            raise HTTPException(
                status_code=400,
                detail="Suspicious input detected — request blocked",
            )


def check_output(text: str) -> bool:
    """Check LLM output for system prompt leakage.

    Returns True if suspicious fragments found (output_filtered=true).
    """
    text_lower = text.lower()
    for fragment in SYSTEM_FRAGMENTS:
        if fragment in text_lower:
            _response_logger.warning(
                "System prompt fragment in output | fragment=%s | output=%s",
                fragment,
                text[:300],
            )
            return True
    return False
