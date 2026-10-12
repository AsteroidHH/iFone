from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.auth import get_auth_context, AuthContext
from app.models.graph import GraphResponse, NodeDetailResponse, StatusHistoryEntry
from app.models.common import ErrorCode, Status
from app.services.fixtures import get_fixture_graph

router = APIRouter()


@router.get("/graph", response_model=GraphResponse)
def get_graph(as_of: Optional[int] = None, auth: AuthContext = Depends(get_auth_context)):
    return get_fixture_graph(tenant=auth.tenant, as_of=as_of)


@router.get("/node/{node_id}", response_model=NodeDetailResponse)
def get_node(node_id: str, auth: AuthContext = Depends(get_auth_context)):
    graph = get_fixture_graph(tenant=auth.tenant)
    target = next((n for n in graph.nodes if n.id == node_id), None)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": ErrorCode.NOT_FOUND.value,
                    "message": f"Node with id '{node_id}' not found.",
                }
            },
        )

    # Compute provenance path to root
    path = [target]
    curr_id = node_id
    while True:
        parent_edge = next((e for e in graph.edges if e.target == curr_id and e.type in ["LEADS_TO", "FROM_SOURCE"]), None)
        if not parent_edge:
            break
        parent_node = next((n for n in graph.nodes if n.id == parent_edge.source), None)
        if not parent_node:
            break
        path.insert(0, parent_node)
        curr_id = parent_node.id

    # Descendants count
    descendant_count = sum(1 for e in graph.edges if e.source == node_id)

    status_history = [
        StatusHistoryEntry(
            ts=target.valid_from or graph.generated_at,
            status=Status.HEALTHY,
            reason="Node created from source",
        )
    ]
    if target.status == Status.QUARANTINED:
        status_history.append(
            StatusHistoryEntry(
                ts=target.quarantined_at or graph.generated_at,
                status=Status.QUARANTINED,
                reason="Cascade invalidation from root fact_90d",
            )
        )

    return NodeDetailResponse(
        node=target,
        path=path,
        descendant_count=descendant_count,
        status_history=status_history,
    )
