"""Pydantic models for structured agent output and LangGraph state."""

from typing import Literal, Optional, TypedDict
from pydantic import BaseModel, Field


class Decision(BaseModel):
    """Resolver agent output — proposed refund decision."""

    action: Literal["approve_refund", "approve_credit", "deny", "request_info"]
    amount_usd: float = Field(ge=0)
    reason: str = Field(description="1-2 sentence justification grounded in the data.")
    confidence: float = Field(ge=0, le=1)


class Evaluation(BaseModel):
    """Evaluator agent output — critique of resolver's decision."""

    score: float = Field(ge=0, le=1, description="Overall quality score.")
    policy_compliance: bool
    risk_level: float = Field(ge=0, le=1)
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(
        default_factory=list,
        description="Concrete fixes for resolver if score < threshold.",
    )
    verdict: Literal["pass", "revise", "escalate"]


class HumanReview(BaseModel):
    """Output from the HITL approval panel."""

    action: Literal["approve_as_is", "modify", "reject"]
    modified_amount_usd: Optional[float] = None
    reviewer_notes: str = ""


class TriageState(TypedDict, total=False):
    """LangGraph state — flows through every node."""

    case: dict
    context: dict
    decision: dict
    evaluation: dict
    human_review: Optional[dict]
    retries: int
    feedback: Optional[str]
    final_status: Optional[str]
    refund_id: Optional[str]
    trace: list[dict]
