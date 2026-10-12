import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, status
from app.auth import get_auth_context, AuthContext, require_role
from app.models.scenario import ScenarioResponse
from app.models.common import ErrorCode, Status
from app.services.event_bus import event_bus

from app.services.scenario_orchestrator import scenario_orchestrator

router = APIRouter()

ScenarioStep = Literal["inject_poison", "run_agents", "audit", "supersede", "restore", "reset"]


@router.post("/scenario/{step}", response_model=ScenarioResponse)
async def run_scenario_step(
    step: ScenarioStep,
    auth: AuthContext = Depends(require_role(["auditor", "human"])),
):
    run_id = f"run_{uuid.uuid4().hex[:8]}"

    # Broadcast step start
    event_bus.publish(
        auth.tenant,
        "scenario_progress",
        {"run_id": run_id, "step": step, "state": "started"},
    )

    try:
        scenario_orchestrator.execute_step(step, tenant=auth.tenant, request_id=run_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": ErrorCode.VALIDATION.value, "message": str(e)}},
        )

    # Broadcast step completion
    event_bus.publish(
        auth.tenant,
        "scenario_progress",
        {"run_id": run_id, "step": step, "state": "finished", "detail": f"Step '{step}' executed successfully."},
    )

    return ScenarioResponse(run_id=run_id, accepted=True)

