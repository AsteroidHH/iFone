import time
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from app.auth import get_auth_context, AuthContext
from app.models.brain import (
    BrainAskRequest,
    BrainAskResponse,
    Citation,
    WhoKnowsItem,
    DecisionTraceItem,
)

router = APIRouter()


@router.post("/brain/ask", response_model=BrainAskResponse)
def ask_brain(
    request: BrainAskRequest,
    auth: AuthContext = Depends(get_auth_context),
):
    q = request.question.lower()
    now_ms = int(time.time() * 1000)

    if "refund" in q or "window" in q:
        return BrainAskResponse(
            refused=False,
            answer="According to Acme Refund Policy v3, customers are permitted to request refunds within 30 days of initial purchase.",
            citations=[
                Citation(
                    source_title="Refund policy",
                    url="https://acme.example/policy",
                    version="3",
                    quote="Refunds are allowed within 30 days.",
                    owner_team="Support Ops",
                    valid_from=now_ms - 86400000,
                    stale=False,
                )
            ],
        )

    # Untraceable answer refusal
    return BrainAskResponse(
        refused=True,
        reason="no sourced answer found",
        citations=[],
    )


@router.get("/who-knows", response_model=List[WhoKnowsItem])
def who_knows(
    topic: Optional[str] = Query(None),
    auth: AuthContext = Depends(get_auth_context),
):
    return [
        WhoKnowsItem(
            person="Sarah Chen",
            team="Support Ops",
            evidence_count=14,
            source_ids=["src_policy_v3", "doc_runbook_refunds"],
        ),
        WhoKnowsItem(
            person="Marcus Vance",
            team="Billing Tier 1",
            evidence_count=9,
            source_ids=["src_webhook_partner"],
        ),
    ]


@router.get("/decisions/{decision_id}/trace", response_model=List[DecisionTraceItem])
def trace_decision(
    decision_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    return [
        DecisionTraceItem(
            claim="Refund window is 30 days",
            quote="Refunds are allowed within 30 days.",
            source_title="Refund policy",
            url="https://acme.example/policy",
            version="3",
            owner="Support Ops",
        )
    ]
