import time
from fastapi import APIRouter, Depends
from app.auth import get_auth_context, AuthContext
from app.models.scenario import BlastPreviewResponse, BlastReportResponse, BlastActionsBreakdown

router = APIRouter()


@router.get("/blast/{node_id}/preview", response_model=BlastPreviewResponse)
def blast_preview(node_id: str, auth: AuthContext = Depends(get_auth_context)):
    return BlastPreviewResponse(
        root_id=node_id,
        node_ids=[node_id, "conc_eligible_1042", "act_refund_2", "act_email_cust"],
        facts=1,
        conclusions=1,
        actions=BlastActionsBreakdown(
            staged=1,
            executed_reversible=0,
            executed_compensable=1,
            executed_irreversible=0,
        ),
    )


@router.get("/blast/{node_id}/report", response_model=BlastReportResponse)
def blast_report(node_id: str, auth: AuthContext = Depends(get_auth_context)):
    now_ms = int(time.time() * 1000)
    return BlastReportResponse(
        root_id=node_id,
        quarantined_at=now_ms - 120000,
        ms_to_containment=42,
        facts=1,
        conclusions=1,
        actions_cancelled=1,
        actions_compensated=1,
        actions_escalated=0,
        node_ids_by_depth=[
            [node_id],
            ["conc_eligible_1042"],
            ["act_refund_2", "act_email_cust"],
        ],
    )
