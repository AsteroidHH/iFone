from typing import List
from fastapi import APIRouter, Depends
from app.auth import get_auth_context, AuthContext
from app.models.graph import GraphNode
from app.models.common import NodeKind
from app.services.fixtures import get_fixture_graph

router = APIRouter()


@router.get("/actions", response_model=List[GraphNode])
def list_actions(auth: AuthContext = Depends(get_auth_context)):
    graph = get_fixture_graph(tenant=auth.tenant)
    return [n for n in graph.nodes if n.kind == NodeKind.ACTION]
