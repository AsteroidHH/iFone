import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.auth import get_auth_context, AuthContext
from app.graph.queries import get_graph_store
from app.models.graph import GraphNode, ActionInfo, GraphEdge
from app.models.common import (
    NodeKind,
    Status,
    Reversibility,
    GateStatus,
    EdgeType,
    ErrorCode,
)
from app.services.gate import quorum_gate
from app.services.executor import action_executor

router = APIRouter()


class StageActionRequest(BaseModel):
    id: Optional[str] = None
    label: str
    action_type: str
    reversibility: Reversibility
    parent_ids: List[str]
    procedure_id: Optional[str] = None
    idempotency_key: Optional[str] = None


@router.get("/actions", response_model=List[GraphNode])
def list_actions(auth: AuthContext = Depends(get_auth_context)):
    store = get_graph_store(tenant=auth.tenant)
    actions = [n for n in store.nodes.values() if n.kind == NodeKind.ACTION]
    if not actions:
        # Fallback to fixtures if store is fresh
        from app.services.fixtures import get_fixture_graph
        graph = get_fixture_graph(tenant=auth.tenant)
        actions = [n for n in graph.nodes if n.kind == NodeKind.ACTION]
    return actions


@router.post("/actions/stage", response_model=GraphNode)
def stage_action(
    req: StageActionRequest,
    auth: AuthContext = Depends(get_auth_context),
):
    store = get_graph_store(tenant=auth.tenant)

    with store._lock:
        # 1. Atomic derivation check: all parents must exist and be HEALTHY
        parents = [store.nodes.get(pid) for pid in req.parent_ids if store.nodes.get(pid)]
        if len(parents) != len(req.parent_ids) or any(p.status != Status.HEALTHY for p in parents):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": ErrorCode.CONFLICT.value,
                        "message": "Atomic derivation guard failed: one or more parents do not exist or are not HEALTHY.",
                    }
                },
            )

        action_id = req.id or f"act_{uuid.uuid4().hex[:6]}"
        action_node = GraphNode(
            id=action_id,
            kind=NodeKind.ACTION,
            label=req.label[:60],
            status=Status.HEALTHY,
            stale=False,
            action=ActionInfo(
                type=req.action_type,
                reversibility=req.reversibility,
                executed=False,
                confirmed=False,
                gate=GateStatus.PASSED,  # Evaluated by gate below
                procedure_id=req.procedure_id,
            ),
        )
        if req.idempotency_key:
            action_node.action.idempotency_key = req.idempotency_key

        # Add node and causal edges
        store.add_node(action_node)
        for p in parents:
            store.add_edge(GraphEdge(
                id=f"e_{uuid.uuid4().hex[:6]}",
                source=p.id,
                target=action_node.id,
                type=EdgeType.LEADS_TO,
            ))

    # 2. Evaluate Quorum Gate
    gate_status, reason, handoff = quorum_gate.evaluate(store, action_node, tenant=auth.tenant)

    return action_node


@router.post("/actions/{action_id}/execute", response_model=GraphNode)
def execute_action_endpoint(
    action_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    store = get_graph_store(tenant=auth.tenant)
    return action_executor.execute(store, action_id, tenant=auth.tenant)


@router.post("/actions/{action_id}/approve-correction")
def approve_correction(
    action_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    store = get_graph_store(tenant=auth.tenant)
    action_node = store.nodes.get(action_id)
    if not action_node or not action_node.action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": ErrorCode.NOT_FOUND.value, "message": f"Action '{action_id}' not found."}},
        )

    notice = getattr(action_node.action, "correction_notice", None)
    if not notice:
        from app.services.saga import generate_correction_notice
        notice = generate_correction_notice(action_node, store, tenant=auth.tenant)

    notice["status"] = "DISPATCHED"
    action_node.action.correction_notice = notice
    action_node.correction_notice = notice

    from app.routes.handoffs import _handoff_store, _handoff_lock
    from app.models.common import HandoffStatus
    from app.services.event_bus import event_bus

    with _handoff_lock:
        for h in _handoff_store:
            if h.context_root_id == action_id or (h.correction_notice and h.correction_notice.get("target_action_id") == action_id):
                h.status = HandoffStatus.COMPLETED
                if h.correction_notice:
                    h.correction_notice["status"] = "DISPATCHED"
                event_bus.publish(auth.tenant, "handoff_updated", {"handoff": h.model_dump()})

    # Update alert memory node if present
    alert_node = store.nodes.get(f"alert_retraction_{action_id}")
    if alert_node:
        alert_node.label = f"✅ Retraction Dispatched for {action_id}"
        event_bus.publish(auth.tenant, "node_updated", {"node": alert_node.model_dump()})

    try:
        import graph.queries as falkor_queries
        falkor_queries.approve_correction(auth.tenant, action_id)
    except Exception:
        pass

    event_bus.publish(
        auth.tenant,
        "correction_dispatched",
        {"action_id": action_id, "status": "DISPATCHED", "notice": notice},
    )

    return {
        "status": "DISPATCHED",
        "action_id": action_id,
        "notice": notice,
    }

