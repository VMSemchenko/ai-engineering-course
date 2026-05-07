"""Write-only tool — gated behind HITL for high-value/high-risk cases."""

import time
import uuid


def issue_refund(case_id: str, amount_usd: float, action: str) -> dict:
    """Mocked payment gateway call. Returns refund_id and status."""
    time.sleep(0.3)
    return {
        "refund_id": f"{case_id}-{uuid.uuid4().hex[:6].upper()}",
        "status": "ISSUED" if action != "deny" else "NO_REFUND",
        "action": action,
        "amount_usd": amount_usd if action != "deny" else 0,
    }
