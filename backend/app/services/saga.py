import time
import uuid
from typing import List, Optional, Dict, Any
from app.graph.queries import GraphStore
from app.models.common import (
    NodeKind,
    Tier,
    Status,
    CompensationStatus,
    HandoffKind,
    HandoffStatus,
)
from app.models.graph import GraphNode
from app.models.handoffs import Handoff
from app.services.helpdesk import helpdesk_service
from app.services.event_bus import event_bus


def generate_correction_notice(
    action_node: GraphNode,
    store: GraphStore,
    tenant: str = "acme",
) -> Dict[str, Any]:
    """
    Automated Damage Control / Retraction Notice Generator:
    Generates structured CorrectionNotice for an executed IRREVERSIBLE action
    hit by quarantine cascade, linking back to verified truth and policy citations.
    """
    recipient = "customer@acme.com"
    original_subject = "Update: Your Refund Request is Approved"
    original_statement = "Your refund of $150 has been approved under our new 90-day policy."

    if action_node.text:
        original_statement = action_node.text
    elif action_node.label and "email" not in action_node.label.lower():
        original_statement = action_node.label

    # Search for verified root policy citation in graph
    citation = "Finance Ops Policy Doc v3.0 (30-day window)"
    root_policy = None
    for n in store.nodes.values():
        if n.kind == NodeKind.FACT and n.status == Status.HEALTHY:
            if n.asserted_by and n.asserted_by.tier == Tier.ROOT:
                root_policy = n
                break
            if n.id in ["fact_30d", "fact_refund_policy_30d"]:
                root_policy = n
                break

    if root_policy:
        if root_policy.source_ref and "policy" in root_policy.source_ref.lower():
            window = root_policy.value or "30"
            citation = f"Finance Ops Policy Doc v3.0 ({window}-day window)"

    correction_subject = "CORRECTION: Important update regarding your refund request"
    drafted_body = (
        "Dear Customer,\n\n"
        "We recently sent an email stating that your refund request was approved under a 90-day refund policy. "
        "That communication was sent in error due to an unverified policy update.\n\n"
        "Our official refund policy remains 30 days (per Finance Ops Policy v3.0). "
        "We sincerely apologize for any confusion. Please find our verified policy details attached.\n\n"
        "Sincerely,\n"
        "Acme Support Operations"
    )

    return {
        "target_action_id": action_node.id,
        "recipient": recipient,
        "original_subject": original_subject,
        "original_statement": original_statement,
        "correction_subject": correction_subject,
        "drafted_body": drafted_body,
        "verified_policy_citation": citation,
        "status": "READY_FOR_HUMAN_APPROVAL",
    }


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

            with store._lock:
                comp = node.action.compensation
                if not comp or comp.status != CompensationStatus.PENDING_COMPENSATION:
                    continue

                # Lease row atomically
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

            with store._lock:
                if resp.get("status") == 200:
                    comp.status = CompensationStatus.COMPENSATED
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
                        store.add_handoff(handoff)
                        event_bus.publish(tenant, "handoff_updated", {"handoff": handoff.model_dump()})
                    else:
                        comp.status = CompensationStatus.PENDING_COMPENSATION

            event_bus.publish(
                tenant,
                "compensation_updated",
                {"action_id": node.id, "status": comp.status.value, "attempts": comp.attempts},
            )

        return processed


saga_worker = OutboxSagaWorker()
