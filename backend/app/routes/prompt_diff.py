from typing import Optional
from fastapi import APIRouter, Depends, Query
from app.auth import get_auth_context, AuthContext
from app.models.agents import PromptDiffResponse, PromptDiffNode
from app.models.common import Status

router = APIRouter()


@router.get("/prompt-diff", response_model=PromptDiffResponse)
def get_prompt_diff(
    agent: Optional[str] = Query(None),
    auth: AuthContext = Depends(get_auth_context),
):
    return PromptDiffResponse(
        epoch_before=13,
        epoch_after=14,
        before=[
            PromptDiffNode(node_id="fact_30d", text="Refund window is 30 days.", status=Status.HEALTHY),
            PromptDiffNode(node_id="fact_90d", text="Refund window is 90 days.", status=Status.HEALTHY),
            PromptDiffNode(node_id="conc_eligible_1042", text="Order 1042 eligible for refund (45d).", status=Status.HEALTHY),
        ],
        after=[
            PromptDiffNode(node_id="fact_30d", text="Refund window is 30 days.", status=Status.HEALTHY),
        ],
        removed_ids=["fact_90d", "conc_eligible_1042"],
    )
