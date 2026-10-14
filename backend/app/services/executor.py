import time
from typing import Optional
from fastapi import HTTPException, status
from app.graph.queries import GraphStore
from app.models.common import ErrorCode
from app.models.graph import GraphNode
from app.services.helpdesk import helpdesk_service
from app.services.event_bus import event_bus


class ActionExecutorService:
    """
    Handles action execution with the atomic execute guard.
    - Runs execute_guard (check-and-set).
    - If 0 rows return, NEVER calls the external API and returns 409 GUARD_REFUSED.
    - If guard succeeds, dispatches to helpdesk and sets confirmed=True on 200.
    """
    def execute(
        self,
        store: GraphStore,
        action_id: str,
        tenant: str = "acme",
        request_id: Optional[str] = None,
    ) -> GraphNode:
        action = store.nodes.get(action_id)
        if not action or not action.action:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": ErrorCode.NOT_FOUND.value, "message": f"Action '{action_id}' not found."}},
            )

        # 1. Atomic execute guard check-and-set
        guard_passed = store.execute_guard(action_id, request_id=request_id)
        if not guard_passed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": ErrorCode.GUARD_REFUSED.value,
                        "message": f"Execute guard refused action '{action_id}': one or more ancestors or supporters are not healthy, or gate was blocked.",
                    }
                },
            )

        # 2. Call external API (Helpdesk) with idempotency key
        idempotency_key = getattr(action.action, "idempotency_key", None) or f"key_{action_id}"
        resp = helpdesk_service.execute_action(
            idempotency_key=idempotency_key,
            action_type=action.action.type,
            payload={},
        )

        if resp.get("status") == 200:
            action.action.confirmed = True
            action.action.executed_at = int(time.time() * 1000)
            event_bus.publish(
                tenant,
                "action_executed",
                {"action_id": action.id, "confirmed": True},
                request_id=request_id,
            )
            return action
        elif resp.get("status") == 409:
            # Action was tombstoned!
            action.action.confirmed = False
            event_bus.publish(
                tenant,
                "action_executed",
                {"action_id": action.id, "confirmed": False},
                request_id=request_id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": ErrorCode.CONFLICT.value, "message": resp.get("message")}},
            )
        else:
            action.action.confirmed = False
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": {"code": ErrorCode.INTERNAL.value, "message": "Failed calling external service."}},
            )


action_executor = ActionExecutorService()
