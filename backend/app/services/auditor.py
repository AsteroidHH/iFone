import time
import uuid
from typing import List, Dict, Any, Optional
from app.graph.queries import GraphStore
from app.models.common import (
    NodeKind,
    Tier,
    Status,
    Reversibility,
    CompensationStatus,
    HandoffKind,
    HandoffStatus,
)
from app.models.graph import GraphNode, CompensationInfo
from app.models.handoffs import Handoff
from app.services.event_bus import event_bus


class AuditorService:
    """
    Deterministic Auditor Service (NOT an LLM):
    1. Contradiction detection & trust rule evaluation (root > corroborated > tier).
    2. Supersede authority verification.
    3. Triggers cascade quarantine, sets depths, bumps Meta.epoch, and enqueues compensations.
    4. Triggers restore, checks all parents healthy, bumps Meta.epoch.
    """
    def check_contradiction(
        self,
        store: GraphStore,
        new_fact: GraphNode,
        tenant: str = "acme",
        request_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if not new_fact.key or not new_fact.value:
            return None

        # Find existing healthy facts with same key
        conflicting_facts = [
            f for f in store.nodes.values()
            if f.kind == NodeKind.FACT and f.status == Status.HEALTHY and f.id != new_fact.id and f.key == new_fact.key and f.value != new_fact.value
        ]

        if not conflicting_facts:
            return None

        old_fact = conflicting_facts[0]

        # Trust evaluation
        old_tier = old_fact.asserted_by.tier if old_fact.asserted_by else Tier.NEW
        new_tier = new_fact.asserted_by.tier if new_fact.asserted_by else Tier.NEW

        # Rule 1: Contradicting a root fact auto-quarantines the CHALLENGER
        if old_tier == Tier.ROOT:
            self.quarantine(store, new_fact.id, reason="Contradicts root-tier policy fact", tenant=tenant, request_id=request_id)
            return {"verdict": "CHALLENGER_QUARANTINED", "quarantined_id": new_fact.id}

        if new_tier == Tier.ROOT:
            self.quarantine(store, old_fact.id, reason="Contradicted by root-tier assertion", tenant=tenant, request_id=request_id)
            return {"verdict": "OLD_FACT_QUARANTINED", "quarantined_id": old_fact.id}

        # Rule 2: Compare tier weights
        tier_weights = {Tier.ROOT: 10.0, Tier.ESTABLISHED: 3.0, Tier.NEW: 0.5}
        old_weight = tier_weights.get(old_tier, 0.5)
        new_weight = tier_weights.get(new_tier, 0.5)

        if new_weight >= 3 * old_weight:
            self.quarantine(store, old_fact.id, reason="Weaker assertion superseded by higher tier", tenant=tenant, request_id=request_id)
            return {"verdict": "OLD_FACT_QUARANTINED", "quarantined_id": old_fact.id}
        elif old_weight >= 3 * new_weight:
            self.quarantine(store, new_fact.id, reason="Weaker assertion rejected by established fact", tenant=tenant, request_id=request_id)
            return {"verdict": "CHALLENGER_QUARANTINED", "quarantined_id": new_fact.id}
        else:
            # Closer call -> REVIEW handoff for human
            handoff = Handoff(
                id=f"hand_review_{uuid.uuid4().hex[:6]}",
                kind=HandoffKind.REVIEW,
                task=f"Auditor: Contradiction between '{new_fact.id}' and '{old_fact.id}' for key '{new_fact.key}' requires human tie-break.",
                status=HandoffStatus.PENDING,
                context_root_id=new_fact.id,
            )
            event_bus.publish(
                tenant,
                "handoff_updated",
                {"handoff": handoff.dict()},
                request_id=request_id,
            )
            return {"verdict": "REVIEW_HANDOFF", "handoff_id": handoff.id}

    def verify_supersede_authority(self, old_fact: GraphNode, new_fact: GraphNode) -> bool:
        """
        Supersede authority: a Fact may supersede another only if asserted by a root-tier agent,
        or it is a newer version from the same Source.origin as the old fact.
        """
        if new_fact.asserted_by and new_fact.asserted_by.tier == Tier.ROOT:
            return True

        if old_fact.origin and new_fact.origin and old_fact.origin == new_fact.origin:
            return True

        return False

    def quarantine(
        self,
        store: GraphStore,
        root_id: str,
        reason: str = "Invalidated",
        tenant: str = "acme",
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        # 1. Run cascade
        affected = store.cascade_quarantine(root_id, request_id=request_id)

        # 2. Emit status_changed events in order of depth so UI can animate wave
        for node_info in affected:
            event_bus.publish(
                tenant,
                "status_changed",
                {
                    "id": node_info["id"],
                    "status": Status.QUARANTINED.value,
                    "depth": node_info["depth"],
                    "root_id": root_id,
                },
                request_id=request_id,
            )

        # 3. Emit epoch_changed
        event_bus.publish(
            tenant,
            "epoch_changed",
            {"epoch": store.epoch, "reason": "quarantine"},
            request_id=request_id,
        )

        # 4. Enqueue compensations for executed actions
        for node_info in affected:
            node = store.nodes.get(node_info["id"])
            if node and node.kind == NodeKind.ACTION and node.action and node.action.executed:
                if node.action.reversibility == Reversibility.IRREVERSIBLE:
                    # Escalation handoff for human
                    handoff = Handoff(
                        id=f"hand_escl_{uuid.uuid4().hex[:6]}",
                        kind=HandoffKind.ESCALATION,
                        task=f"Irreversible action '{node.id}' quarantined! Draft customer correction notice.",
                        status=HandoffStatus.PENDING,
                        context_root_id=node.id,
                    )
                    event_bus.publish(tenant, "handoff_updated", {"handoff": handoff.dict()}, request_id=request_id)
                else:
                    # Enqueue compensation
                    node.action.compensation = CompensationInfo(
                        status=CompensationStatus.PENDING_COMPENSATION,
                        attempts=0,
                    )
                    event_bus.publish(
                        tenant,
                        "compensation_updated",
                        {"action_id": node.id, "status": CompensationStatus.PENDING_COMPENSATION.value, "attempts": 0},
                        request_id=request_id,
                    )

        return affected

    def restore(
        self,
        store: GraphStore,
        root_id: str,
        tenant: str = "acme",
        request_id: Optional[str] = None,
    ) -> List[str]:
        restored_ids = store.restore_node(root_id, request_id=request_id)

        for rid in restored_ids:
            event_bus.publish(
                tenant,
                "status_changed",
                {"id": rid, "status": Status.HEALTHY.value},
                request_id=request_id,
            )

        if restored_ids:
            event_bus.publish(
                tenant,
                "epoch_changed",
                {"epoch": store.epoch, "reason": "restore"},
                request_id=request_id,
            )

        return restored_ids


auditor_service = AuditorService()
