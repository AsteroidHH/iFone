import time
import uuid
from typing import Optional, List, Dict, Any
from app.graph.queries import get_graph_store
from app.models.common import (
    Status,
    NodeKind,
    EdgeType,
    Tier,
    Reversibility,
    GateStatus,
    HandoffKind,
    HandoffStatus,
)
from app.models.graph import GraphNode, GraphEdge, ActionInfo, AssertedBy
from app.models.handoffs import Handoff
from app.services.gate import quorum_gate
from app.services.executor import action_executor
from app.services.auditor import auditor_service
from app.config import settings


def _get_auth(token: str) -> Dict[str, Any]:
    if token in settings.DEMO_TOKENS:
        return settings.DEMO_TOKENS[token]
    parts = token.split("_")
    if len(parts) >= 3 and parts[0] == "token":
        return {"tenant": parts[1], "role": parts[2], "agent_id": f"{parts[2]}_{parts[1]}"}
    if len(parts) >= 2 and parts[0] == "token":
        return {"tenant": settings.DEFAULT_TENANT, "role": parts[1], "agent_id": f"{parts[1]}_demo"}
    return {"tenant": settings.DEFAULT_TENANT, "role": "agent", "agent_id": "agent_demo"}


def remember_fact(
    key: str,
    value: str,
    text: str,
    token: str,
    id: Optional[str] = None,
    quote: Optional[str] = None,
    origin: Optional[str] = None,
) -> Dict[str, Any]:
    """Stores an episodic/semantic Fact node into the commons causal graph."""
    auth = _get_auth(token)
    store = get_graph_store(auth["tenant"])
    fact_id = id or f"fact_{uuid.uuid4().hex[:6]}"

    tier_val = Tier.ROOT if "root" in auth.get("agent_id", "") else Tier.NEW

    fact = GraphNode(
        id=fact_id,
        kind=NodeKind.FACT,
        label=text[:60],
        status=Status.HEALTHY,
        stale=False,
        key=key,
        value=value,
        text=text,
        quote=quote,
        origin=origin or f"agent:{auth.get('agent_id', 'unknown')}",
        asserted_by=AssertedBy(
            id=auth.get("agent_id", "agent_scout"),
            name=auth.get("agent_id", "Agent"),
            tier=tier_val,
        ),
    )
    store.add_node(fact)

    # Check contradiction with Auditor
    verdict = auditor_service.check_contradiction(store, fact, tenant=auth["tenant"])

    return {
        "epoch": store.epoch,
        "fact_id": fact.id,
        "status": fact.status.value,
        "verdict": verdict,
    }


def derive(
    text: str,
    parent_ids: List[str],
    token: str,
    id: Optional[str] = None,
    is_decision: bool = False,
    owner_team: Optional[str] = None,
) -> Dict[str, Any]:
    """Derives a new Conclusion or Decision node. Requires all parents to exist and be HEALTHY."""
    auth = _get_auth(token)
    store = get_graph_store(auth["tenant"])

    # Atomic derivation check
    parents = [store.nodes.get(pid) for pid in parent_ids if store.nodes.get(pid)]
    if len(parents) != len(parent_ids) or any(p.status != Status.HEALTHY for p in parents):
        return {
            "epoch": store.epoch,
            "error": "Atomic derivation check failed: one or more parents do not exist or are not HEALTHY.",
            "success": False,
        }

    conc_id = id or f"conc_{uuid.uuid4().hex[:6]}"
    conc = GraphNode(
        id=conc_id,
        kind=NodeKind.CONCLUSION,
        is_decision=is_decision,
        label=text[:60],
        status=Status.HEALTHY,
        stale=False,
        text=text,
        owner_team=owner_team,
    )
    store.add_node(conc)

    for p in parents:
        store.add_edge(GraphEdge(
            id=f"e_{uuid.uuid4().hex[:6]}",
            source=p.id,
            target=conc.id,
            type=EdgeType.LEADS_TO,
        ))

    return {
        "epoch": store.epoch,
        "conclusion_id": conc.id,
        "status": conc.status.value,
        "success": True,
    }


def retrieve_context(query: str, token: str, k: int = 5) -> Dict[str, Any]:
    """Retrieves healthy, unsuperseded context from the causal graph."""
    auth = _get_auth(token)
    store = get_graph_store(auth["tenant"])

    # Healthy-only context
    healthy_facts = [
        n for n in store.nodes.values()
        if n.kind == NodeKind.FACT and n.status == Status.HEALTHY and not n.stale
    ]

    matched = []
    q_lower = query.lower()
    for f in healthy_facts:
        if any(w in (f.text or "").lower() or w in (f.key or "").lower() for w in q_lower.split()):
            matched.append({
                "id": f.id,
                "key": f.key,
                "value": f.value,
                "text": f.text,
                "quote": f.quote,
                "asserted_by": f.asserted_by.model_dump() if f.asserted_by else None,
            })

    return {
        "epoch": store.epoch,
        "count": len(matched),
        "context": matched[:k],
    }


def stage_action(
    label: str,
    action_type: str,
    reversibility: str,
    parent_ids: List[str],
    token: str,
    id: Optional[str] = None,
    procedure_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Stages an action node and passes through the Quorum Gate."""
    auth = _get_auth(token)
    store = get_graph_store(auth["tenant"])

    rev_enum = getattr(Reversibility, reversibility.upper(), Reversibility.COMPENSABLE)

    # 1. Atomic derivation check
    parents = [store.nodes.get(pid) for pid in parent_ids if store.nodes.get(pid)]
    if len(parents) != len(parent_ids) or any(p.status != Status.HEALTHY for p in parents):
        return {
            "epoch": store.epoch,
            "error": "Atomic derivation check failed: one or more parents do not exist or are not HEALTHY.",
            "success": False,
        }

    act_id = id or f"act_{uuid.uuid4().hex[:6]}"
    action_node = GraphNode(
        id=act_id,
        kind=NodeKind.ACTION,
        label=label[:60],
        status=Status.HEALTHY,
        stale=False,
        action=ActionInfo(
            type=action_type,
            reversibility=rev_enum,
            executed=False,
            confirmed=False,
            gate=GateStatus.PASSED,
            procedure_id=procedure_id,
            idempotency_key=idempotency_key,
        ),
    )
    store.add_node(action_node)

    for p in parents:
        store.add_edge(GraphEdge(
            id=f"e_{uuid.uuid4().hex[:6]}",
            source=p.id,
            target=action_node.id,
            type=EdgeType.LEADS_TO,
        ))

    # 2. Evaluate Quorum Gate
    gate_status, reason, handoff = quorum_gate.evaluate(store, action_node, tenant=auth["tenant"])

    return {
        "epoch": store.epoch,
        "action_id": action_node.id,
        "gate": action_node.action.gate.value,
        "status": action_node.status.value,
        "blocked_reason": reason,
        "handoff_id": handoff.id if handoff else None,
        "success": True,
    }


def execute_action(id: str, token: str) -> Dict[str, Any]:
    """Runs atomic execute guard and dispatches to external Helpdesk."""
    auth = _get_auth(token)
    store = get_graph_store(auth["tenant"])

    try:
        executed_node = action_executor.execute(store, id, tenant=auth["tenant"])
        return {
            "epoch": store.epoch,
            "action_id": executed_node.id,
            "executed": executed_node.action.executed,
            "confirmed": executed_node.action.confirmed,
            "success": True,
        }
    except Exception as e:
        return {
            "epoch": store.epoch,
            "action_id": id,
            "error": str(e),
            "success": False,
        }


def claim_handoff(id: str, token: str) -> Dict[str, Any]:
    """Claims a handoff task with atomic lease. Agent tokens restricted to kind=TASK."""
    auth = _get_auth(token)
    store = get_graph_store(auth["tenant"])

    from app.routes.handoffs import _handoff_store, _handoff_lock

    with _handoff_lock:
        target = next((h for h in _handoff_store if h.id == id), None)
        if not target:
            return {"epoch": store.epoch, "error": f"Handoff '{id}' not found", "success": False}

        if auth["role"] == "agent" and target.kind != HandoffKind.TASK:
            return {
                "epoch": store.epoch,
                "error": f"Agent tokens are forbidden from claiming '{target.kind.value}' handoffs.",
                "success": False,
            }

        now_ms = int(time.time() * 1000)
        is_claimable = (
            target.status == HandoffStatus.PENDING
            or (target.status == HandoffStatus.IN_PROGRESS and target.lease_until and target.lease_until < now_ms)
        )
        if not is_claimable:
            return {
                "epoch": store.epoch,
                "error": f"Handoff '{id}' already claimed by '{target.claimed_by}' with active lease until {target.lease_until}.",
                "success": False,
            }

        target.status = HandoffStatus.IN_PROGRESS
        target.claimed_by = auth.get("agent_id", "agent")
        target.claimed_at = now_ms
        target.lease_until = now_ms + 60000
        return {"epoch": store.epoch, "handoff_id": id, "status": target.status.value, "success": True}


def quarantine(root_id: str, token: str, reason: str = "Manual auditor quarantine") -> Dict[str, Any]:
    """Auditor-only tool: Quarantines root fact and cascades down causal descendants."""
    auth = _get_auth(token)
    if auth["role"] not in ["auditor", "human"]:
        return {"error": "Role forbidden. Requires auditor or human role.", "success": False}

    store = get_graph_store(auth["tenant"])
    affected = auditor_service.quarantine(store, root_id, reason=reason, tenant=auth["tenant"])
    return {
        "epoch": store.epoch,
        "root_id": root_id,
        "affected_count": len(affected),
        "affected_nodes": affected,
        "success": True,
    }


def restore(root_id: str, token: str) -> Dict[str, Any]:
    """Auditor-only tool: Restores root fact and valid descendants if all parents are healthy."""
    auth = _get_auth(token)
    if auth["role"] not in ["auditor", "human"]:
        return {"error": "Role forbidden. Requires auditor or human role.", "success": False}

    store = get_graph_store(auth["tenant"])
    restored_ids = auditor_service.restore(store, root_id, tenant=auth["tenant"])
    return {
        "epoch": store.epoch,
        "root_id": root_id,
        "restored_count": len(restored_ids),
        "restored_nodes": restored_ids,
        "success": True,
    }


def explain_blast_radius(root_id: str, token: str) -> Dict[str, Any]:
    """Auditor tool: Dry-run blast radius calculation."""
    auth = _get_auth(token)
    store = get_graph_store(auth["tenant"])
    descendants = [n.id for n in store.nodes.values() if n.id != root_id]
    return {
        "epoch": store.epoch,
        "root_id": root_id,
        "predicted_impact_count": len(descendants),
    }


def review_handoff(id: str, decision: str, token: str, note: Optional[str] = None) -> Dict[str, Any]:
    """Human-only tool: Approves or rejects a gate-blocked review handoff."""
    auth = _get_auth(token)
    if auth["role"] != "human":
        return {"error": "Only human reviewers may complete REVIEW handoffs.", "success": False}

    from app.routes.handoffs import _handoff_store
    target = next((h for h in _handoff_store if h.id == id), None)
    if not target:
        return {"error": f"Handoff '{id}' not found.", "success": False}

    target.status = HandoffStatus.COMPLETED
    store = get_graph_store(auth["tenant"])

    if decision.lower() == "approve" and target.context_root_id:
        action_node = store.nodes.get(target.context_root_id)
        if action_node and action_node.action:
            action_node.action.gate = GateStatus.PASSED

    return {
        "epoch": store.epoch,
        "handoff_id": id,
        "decision": decision,
        "status": target.status.value,
        "success": True,
    }
