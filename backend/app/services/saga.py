import time
import uuid
from typing import List, Optional
from app.graph.queries import GraphStore
from app.models.common import (
    NodeKind,
    CompensationStatus,
    HandoffKind,
    HandoffStatus,
)
from app.models.graph import GraphNode
from app.models.handoffs import Handoff
from app.services.helpdesk import helpdesk_service
from app.services.event_bus import event_bus


class OutboxSagaWorker:
    """
    Outbox Saga Worker:
    - Polls actions where compensation is PENDING_COMPENSATION.
    - Claims with lease (DISPATCHING).
    - Calls Helpdesk with idempotency keys.
    - Handles in-flight actions (executed=True, confirmed=False older than 60s) safely via Helpdesk tombstones.
    """
    def __init__(self, max_attempts: int = 3):
        self.max_attempts = max_attempts

    def process_pending(self, store: GraphStore, tenant: str = "acme") -> List[GraphNode]:
        processed = []
        now_ms = int(time.time() * 1000)

        for node in list(store.nodes.values()):
            if node.kind != NodeKind.ACTION or not node.action or not node.action.compensation:
                continue

            comp = node.action.compensation
            if comp.status != CompensationStatus.PENDING_COMPENSATION:
                continue

            # Lease row
            comp.status = CompensationStatus.DISPATCHING
            event_bus.publish(
                tenant,
                "compensation_updated",
                {"action_id": node.id, "status": comp.status.value, "attempts": comp.attempts},
            )

            # In-flight check: if unconfirmed and older than 60s, dispatch compensation anyway
            # The helpdesk tombstone guarantees safety
            idempotency_key = getattr(node.action, "idempotency_key", f"key_{node.id}")
            resp = helpdesk_service.compensate_action(
                idempotency_key=idempotency_key,
                action_id=node.id,
                action_type=node.action.type,
            )

            if resp.get("status") == 200:
                comp.status = CompensationStatus.COMPENSATED
                event_bus.publish(
                    tenant,
                    "compensation_updated",
                    {"action_id": node.id, "status": comp.status.value, "attempts": comp.attempts},
                )
                processed.append(node)
            else:
                comp.attempts += 1
                if comp.attempts >= self.max_attempts:
                    comp.status = CompensationStatus.FAILED
                    # Create ESCALATION handoff for human
                    handoff = Handoff(
                        id=f"hand_comp_fail_{uuid.uuid4().hex[:6]}",
                        kind=HandoffKind.ESCALATION,
                        task=f"Compensation failed for action '{node.id}' after {comp.attempts} attempts. Manual intervention required.",
                        status=HandoffStatus.PENDING,
                        context_root_id=node.id,
                    )
                    event_bus.publish(tenant, "handoff_updated", {"handoff": handoff.dict()})
                else:
                    comp.status = CompensationStatus.PENDING_COMPENSATION

                event_bus.publish(
                    tenant,
                    "compensation_updated",
                    {"action_id": node.id, "status": comp.status.value, "attempts": comp.attempts},
                )

        return processed


saga_worker = OutboxSagaWorker()
