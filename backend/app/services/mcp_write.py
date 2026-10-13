"""Write tools: remember_fact, observe, derive, stage_action, execute_action, claim_handoff, review_handoff."""
import time
import uuid
from typing import Any, Dict, List, Optional

from app.config import settings
from app.graph.queries import get_graph_store
from app.models.common import EdgeType, GateStatus, HandoffKind, HandoffStatus, NodeKind, Reversibility, Status, Tier
from app.models.graph import ActionInfo, AssertedBy, GraphEdge, GraphNode
from app.services import observer
from app.services.auditor import auditor_service
from app.services.executor import action_executor
from app.services.gate import quorum_gate
from app.services.mcp_guard import AuthError, _get_auth, effective_token, emit as _emit, guarded, viewer_of as _viewer  # noqa: F401


def remember_fact(
    key: str,
    value: str,
    text: str,
    token: str = "",
    id: Optional[str] = None,
    quote: Optional[str] = None,
    origin: Optional[str] = None,
    scope: str = "commons",
) -> Dict[str, Any]:
    """Stores a Fact. scope="commons" (default) is readable by everyone in the tenant; scope="team" only by your team and teams linked to it."""
    auth = _get_auth(token)
    store = get_graph_store(auth["tenant"])
    fact_id = id or f"fact_{uuid.uuid4().hex[:6]}"

    tier_val = Tier.ROOT if "root" in auth.get("agent_id", "") else Tier.NEW
    scope_team = None
    if scope == "team":
        if not auth.get("team_id"):
            return {"error": "scope=team needs a member token that belongs to a team.", "success": False}
        scope_team = auth["team_id"]
    elif scope != "commons":
        return {"error": "scope must be commons or team.", "success": False}

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
        scope_team=scope_team,
        asserted_by=AssertedBy(
            id=auth.get("agent_id", "agent_scout"),
            name=auth.get("agent_id", "Agent"),
            tier=tier_val,
        ),
    )
    store.add_node(fact)
    _emit(auth["tenant"], nodes=[fact])

    # Check contradiction with Auditor
    verdict = auditor_service.check_contradiction(store, fact, tenant=auth["tenant"])

    return {
        "epoch": store.epoch,
        "fact_id": fact.id,
        "status": fact.status.value,
        "verdict": verdict,
    }


def observe_text(auth: Dict[str, Any], text: str, source: str = "chat", dry_run: bool = False, scope: str = "commons") -> Dict[str, Any]:
    """Pull durable facts out of text the agent already produced and store them with their source sentence."""
    store = get_graph_store(auth["tenant"])
    if scope == "team" and not auth.get("team_id"):
        return {"error": "scope=team needs a member token that belongs to a team.", "success": False}
    if scope not in ("commons", "team"):
        return {"error": "scope must be commons or team.", "success": False}
    cands = observer.candidates(text, settings.OBSERVER_MAX_FACTS)
    with store._lock:
        known = {observer.fingerprint(n.quote or n.text or ""): n.id for n in store.nodes.values() if n.kind == NodeKind.FACT and (n.quote or n.text)}
        known.update({observer.fingerprint(n.text or ""): n.id for n in store.nodes.values() if n.kind == NodeKind.FACT and n.text})
    stored, duplicates, verdicts = [], [], []
    for c in cands:
        if c["fingerprint"] in known:
            duplicates.append({"text": c["text"], "existing_id": known[c["fingerprint"]]})
            continue
        item = {"text": c["text"], "key": c["key"], "value": c["value"], "confidence": c["confidence"], "signals": c["signals"]}
        if dry_run:
            stored.append({**item, "id": None})
            continue
        fact = GraphNode(
            id=f"obs_{c['fingerprint'][:8]}",
            kind=NodeKind.FACT,
            label=c["text"][:60],
            status=Status.HEALTHY,
            stale=False,
            key=c["key"],
            value=c["value"],
            text=c["text"],
            quote=c["text"],
            origin=f"observer:{source}"[:60],
            scope_team=auth["team_id"] if scope == "team" else None,
            asserted_by=AssertedBy(id=auth.get("agent_id", "agent"), name=auth.get("agent_id", "Agent"), tier=Tier.NEW),
        )
        store.add_node(fact)
        _emit(auth["tenant"], nodes=[fact])
        v = auditor_service.check_contradiction(store, fact, tenant=auth["tenant"])
        if v:
            verdicts.append({"fact_id": fact.id, **v})
        stored.append({**item, "id": fact.id})
    return {
        "epoch": store.epoch,
        "dry_run": dry_run,
        "candidates": len(cands),
        "stored": len(stored) if not dry_run else 0,
        "facts": stored,
        "duplicates": duplicates,
        "conflicts": verdicts,
        "success": True,
    }


def observe(text: str, token: str = "", source: str = "chat", dry_run: bool = False, scope: str = "commons") -> Dict[str, Any]:
    """
    Reads text you already produced (a reply, a tool result, a ticket thread) and saves the facts in it: numbers with
    units, policies, limits, dates. Each keeps its source sentence. Duplicates are skipped and a conflicting number opens a
    review. Use dry_run=true to preview. You can skip remember_fact for ordinary facts and call this once at the end.
    """
    return observe_text(_get_auth(token), text, source, dry_run, scope)


def derive(
    text: str,
    parent_ids: List[str],
    token: str = "",
    id: Optional[str] = None,
    is_decision: bool = False,
    owner_team: Optional[str] = None,
) -> Dict[str, Any]:
    """Derives a new Conclusion or Decision node. Requires all parents to exist and be HEALTHY."""
    auth = _get_auth(token)
    store = get_graph_store(auth["tenant"])

    viewer = _viewer(auth, store)

    # Atomic derivation check
    with store._lock:
        parents = [store.nodes.get(pid) for pid in parent_ids if store.nodes.get(pid) and viewer.can_see(store.nodes.get(pid))]
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
            scope_team=next((p.scope_team for p in parents if p.scope_team), None),
        )
        store.add_node(conc)

        new_edges = []
        for p in parents:
            edge = GraphEdge(
                id=f"e_{uuid.uuid4().hex[:6]}",
                source=p.id,
                target=conc.id,
                type=EdgeType.LEADS_TO,
            )
            store.add_edge(edge)
            new_edges.append(edge)
        _emit(auth["tenant"], nodes=[conc], edges=new_edges)

        return {
            "epoch": store.epoch,
            "conclusion_id": conc.id,
            "status": conc.status.value,
            "success": True,
        }


def stage_action(
    label: str,
    action_type: str,
    reversibility: str,
    parent_ids: List[str],
    token: str = "",
    id: Optional[str] = None,
    procedure_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Stages an action node and passes through the Quorum Gate."""
    auth = _get_auth(token)
    store = get_graph_store(auth["tenant"])

    rev_enum = getattr(Reversibility, reversibility.upper(), Reversibility.COMPENSABLE)

    viewer = _viewer(auth, store)

    # 1. Atomic derivation check
    with store._lock:
        parents = [store.nodes.get(pid) for pid in parent_ids if store.nodes.get(pid) and viewer.can_see(store.nodes.get(pid))]
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
            scope_team=next((p.scope_team for p in parents if p.scope_team), None),
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

        new_edges = []
        for p in parents:
            edge = GraphEdge(
                id=f"e_{uuid.uuid4().hex[:6]}",
                source=p.id,
                target=action_node.id,
                type=EdgeType.LEADS_TO,
            )
            store.add_edge(edge)
            new_edges.append(edge)
        _emit(auth["tenant"], nodes=[action_node], edges=new_edges)

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


def execute_action(id: str, token: str = "") -> Dict[str, Any]:
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


def claim_handoff(id: str, token: str = "") -> Dict[str, Any]:
    """Claims a handoff task with atomic lease. Agent tokens restricted to kind=TASK."""
    auth = _get_auth(token)
    store = get_graph_store(auth["tenant"])

    with store.handoff_lock:
        target = next((h for h in store.handoffs if h.id == id), None)
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

def review_handoff(id: str, decision: str, token: str = "", note: Optional[str] = None) -> Dict[str, Any]:
    """Human-only tool: Approves or rejects a gate-blocked review handoff."""
    auth = _get_auth(token)
    if auth["role"] != "human":
        return {"error": "Only human reviewers may complete REVIEW handoffs.", "success": False}

    store = get_graph_store(auth["tenant"])
    with store.handoff_lock:
        target = next((h for h in store.handoffs if h.id == id), None)
        if not target:
            return {"error": f"Handoff '{id}' not found.", "success": False}

        target.status = HandoffStatus.COMPLETED
        store = get_graph_store(auth["tenant"])

        if decision.lower() == "approve" and target.context_root_id:
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

        return {
            "epoch": store.epoch,
            "handoff_id": id,
            "decision": decision,
            "status": target.status.value,
            "success": True,
        }
