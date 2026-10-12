import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, status
from app.auth import get_auth_context, AuthContext, require_role
from app.models.scenario import ScenarioResponse
from app.models.common import ErrorCode, Status
from app.services.event_bus import event_bus

router = APIRouter()

ScenarioStep = Literal["inject_poison", "run_agents", "audit", "supersede", "restore", "reset"]


@router.post("/scenario/{step}", response_model=ScenarioResponse)
async def run_scenario_step(
    step: ScenarioStep,
    auth: AuthContext = Depends(require_role(["auditor", "human"])),
):
    run_id = f"run_{uuid.uuid4().hex[:8]}"

    # Broadcast progress
    event_bus.publish(
        auth.tenant,
        "scenario_progress",
        {"run_id": run_id, "step": step, "state": "started"},
    )

    if step == "inject_poison":
        event_bus.publish(
            auth.tenant,
            "node_added",
            {
                "node": {
                    "id": "fact_90d",
                    "kind": "fact",
                    "label": "Refund window is 90 days",
                    "status": "HEALTHY",
                    "stale": False,
                    "key": "refund_window_days",
                    "value": "90",
                    "origin": "webhook:partner-feed",
                }
            },
        )
    elif step == "run_agents":
        event_bus.publish(
            auth.tenant,
            "gate_blocked",
            {
                "action_id": "act_email_cust",
                "handoff_id": "hand_email_gate",
                "reason": "Irreversible action resting on uncorroborated leaf fact_90d",
            },
        )
    elif step == "audit":
        # Simulate cascade wave with depth
        event_bus.publish(auth.tenant, "status_changed", {"id": "fact_90d", "status": "QUARANTINED", "depth": 0, "root_id": "fact_90d"})
        event_bus.publish(auth.tenant, "status_changed", {"id": "conc_eligible_1042", "status": "QUARANTINED", "depth": 1, "root_id": "fact_90d"})
        event_bus.publish(auth.tenant, "status_changed", {"id": "act_refund_2", "status": "QUARANTINED", "depth": 2, "root_id": "fact_90d"})
        buf = event_bus.get_tenant_buffer(auth.tenant)
        buf.current_epoch += 1
        event_bus.publish(auth.tenant, "epoch_changed", {"epoch": buf.current_epoch, "reason": "quarantine"})
        event_bus.publish(auth.tenant, "compensation_updated", {"action_id": "act_refund_2", "status": "COMPENSATED", "attempts": 1})
    elif step == "supersede":
        event_bus.publish(auth.tenant, "status_changed", {"id": "fact_30d", "status": "SUPERSEDED"})
        event_bus.publish(auth.tenant, "status_changed", {"id": "conc_eligible_1042", "status": "HEALTHY", "stale": True})
        buf = event_bus.get_tenant_buffer(auth.tenant)
        buf.current_epoch += 1
        event_bus.publish(auth.tenant, "epoch_changed", {"epoch": buf.current_epoch, "reason": "supersede"})

    event_bus.publish(
        auth.tenant,
        "scenario_progress",
        {"run_id": run_id, "step": step, "state": "finished", "detail": f"Step '{step}' completed successfully."},
    )

    return ScenarioResponse(run_id=run_id, accepted=True)
