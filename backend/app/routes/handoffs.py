import time
import threading
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.auth import get_auth_context, AuthContext, require_role
from app.models.handoffs import Handoff, ReviewRequest, ReviewDecision
from app.models.common import ErrorCode, HandoffStatus, HandoffKind
from app.services.fixtures import get_fixture_handoffs
from app.services.event_bus import event_bus

router = APIRouter()
_handoff_store: List[Handoff] = get_fixture_handoffs()
_handoff_lock = threading.Lock()


@router.get("/handoffs", response_model=List[Handoff])
def list_handoffs(auth: AuthContext = Depends(get_auth_context)):
    with _handoff_lock:
        return list(_handoff_store)


@router.post("/handoffs/{handoff_id}/claim", response_model=Handoff)
def claim_handoff(
    handoff_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    with _handoff_lock:
        target = next((h for h in _handoff_store if h.id == handoff_id), None)
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": ErrorCode.NOT_FOUND.value, "message": f"Handoff '{handoff_id}' not found."}},
            )

        # Role enforcement
        if auth.role == "agent" and target.kind != HandoffKind.TASK:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": ErrorCode.FORBIDDEN_ROLE.value,
                        "message": f"Agents may only claim TASK handoffs. Handoff '{handoff_id}' is kind '{target.kind.value}'.",
                    }
                },
            )

        now_ms = int(time.time() * 1000)

        # Atomic lease check (Brief Section 5.8)
        # Allowed if PENDING or if IN_PROGRESS with expired lease
        is_claimable = (
            target.status == HandoffStatus.PENDING
            or (target.status == HandoffStatus.IN_PROGRESS and target.lease_until and target.lease_until < now_ms)
        )

        if not is_claimable:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": ErrorCode.CONFLICT.value,
                        "message": f"Handoff '{handoff_id}' already claimed by '{target.claimed_by}' with active lease until {target.lease_until}.",
                    }
                },
            )

        claimer = auth.agent_id or auth.role
        target.status = HandoffStatus.IN_PROGRESS
        target.claimed_by = claimer
        target.claimed_at = now_ms
        target.lease_until = now_ms + 60000

        event_bus.publish(
            auth.tenant,
            "handoff_claimed",
            {
                "handoff_id": target.id,
                "winner": claimer,
                "losers": ["agent_refunder"] if claimer != "agent_refunder" else ["agent_analyst"],
                "lease_until": target.lease_until,
            },
        )

        return target


@router.post("/handoffs/{handoff_id}/review", response_model=Handoff)
def review_handoff(
    handoff_id: str,
    body: ReviewRequest,
    auth: AuthContext = Depends(require_role(["human"])),
):
    with _handoff_lock:
        target = next((h for h in _handoff_store if h.id == handoff_id), None)
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": ErrorCode.NOT_FOUND.value, "message": f"Handoff '{handoff_id}' not found."}},
            )

        target.status = HandoffStatus.COMPLETED

        if body.decision in [ReviewDecision.APPROVE, "approve", "APPROVE"] and target.context_root_id:
            from app.graph.queries import get_graph_store
            from app.models.common import GateStatus
            store = get_graph_store(auth.tenant)
            with store._lock:
                action_node = store.nodes.get(target.context_root_id)
                if action_node and action_node.action:
                    action_node.action.gate = GateStatus.PASSED
                    if getattr(action_node.action, "correction_notice", None):
                        action_node.action.correction_notice["status"] = "DISPATCHED"
                        action_node.correction_notice = action_node.action.correction_notice
                if target.correction_notice:
                    target.correction_notice["status"] = "DISPATCHED"

                alert_node = store.nodes.get(f"alert_retraction_{target.context_root_id}")
                if alert_node:
                    alert_node.label = f"✅ Retraction Dispatched for {target.context_root_id}"
                    event_bus.publish(auth.tenant, "node_updated", {"node": alert_node.model_dump()})

        event_bus.publish(
            auth.tenant,
            "handoff_updated",
            {"handoff": target.model_dump()},
        )

        return target
