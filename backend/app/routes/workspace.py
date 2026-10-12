from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import AuthContext, get_auth_context, require_role
from app.graph.queries import get_graph_store
from app.services import workspace as ws
from app.services.event_bus import event_bus

router = APIRouter()


def _fail(e: ws.WorkspaceError) -> HTTPException:
    return HTTPException(status_code=e.status, detail={"error": {"code": e.code, "message": e.message}})


def _done(auth: AuthContext, store, extra: Optional[dict] = None) -> dict:
    out = ws.public_view(store)
    event_bus.publish(auth.tenant, "workspace_changed", {})
    if extra:
        out.update(extra)
    return out


class WorkspacePatch(BaseModel):
    org: Optional[str] = None
    plan: Optional[str] = None
    hub: Optional[str] = None


class TeamIn(BaseModel):
    name: str
    seats: int = 5


class SeatsIn(BaseModel):
    seats: int


class MemberIn(BaseModel):
    name: str
    role: str = "agent"
    team_id: str
    client: str = "custom"
    device: str = ""


class LinkIn(BaseModel):
    a: str
    b: str
    scope: str = "team"


class PausedIn(BaseModel):
    paused: bool


@router.get("/workspace")
def get_workspace(auth: AuthContext = Depends(get_auth_context)):
    return ws.public_view(get_graph_store(auth.tenant))


@router.put("/workspace")
def patch_workspace(body: WorkspacePatch, auth: AuthContext = Depends(require_role(["human"]))):
    store = get_graph_store(auth.tenant)
    try:
        if body.org is not None:
            ws.rename(store, body.org)
        if body.plan is not None:
            ws.set_plan(store, body.plan)
        if body.hub is not None:
            ws.set_hub(store, body.hub)
    except ws.WorkspaceError as e:
        raise _fail(e)
    return _done(auth, store)


@router.post("/workspace/teams")
def add_team(body: TeamIn, auth: AuthContext = Depends(require_role(["human"]))):
    store = get_graph_store(auth.tenant)
    try:
        ws.add_team(store, body.name, body.seats)
    except ws.WorkspaceError as e:
        raise _fail(e)
    return _done(auth, store)


@router.patch("/workspace/teams/{team_id}")
def set_seats(team_id: str, body: SeatsIn, auth: AuthContext = Depends(require_role(["human"]))):
    store = get_graph_store(auth.tenant)
    try:
        ws.set_seats(store, team_id, body.seats)
    except ws.WorkspaceError as e:
        raise _fail(e)
    return _done(auth, store)


@router.delete("/workspace/teams/{team_id}")
def remove_team(team_id: str, auth: AuthContext = Depends(require_role(["human"]))):
    store = get_graph_store(auth.tenant)
    try:
        ws.remove_team(store, team_id)
    except ws.WorkspaceError as e:
        raise _fail(e)
    return _done(auth, store)


@router.post("/workspace/members")
def add_member(body: MemberIn, auth: AuthContext = Depends(require_role(["human"]))):
    """Creates a member and returns their token. It is shown once and only its hash is kept."""
    store = get_graph_store(auth.tenant)
    try:
        member, token = ws.add_member(store, body.name, body.role, body.team_id, body.client, body.device)
    except ws.WorkspaceError as e:
        raise _fail(e)
    return _done(auth, store, {"issued": {"member": member, "token": token}})


@router.post("/workspace/members/{member_id}/rotate")
def rotate(member_id: str, auth: AuthContext = Depends(require_role(["human"]))):
    store = get_graph_store(auth.tenant)
    try:
        member, token = ws.rotate_token(store, member_id)
    except ws.WorkspaceError as e:
        raise _fail(e)
    return _done(auth, store, {"issued": {"member": member, "token": token}})


@router.delete("/workspace/members/{member_id}")
def remove_member(member_id: str, auth: AuthContext = Depends(require_role(["human"]))):
    store = get_graph_store(auth.tenant)
    try:
        ws.remove_member(store, member_id)
    except ws.WorkspaceError as e:
        raise _fail(e)
    return _done(auth, store)


@router.post("/workspace/links")
def add_link(body: LinkIn, auth: AuthContext = Depends(require_role(["human"]))):
    store = get_graph_store(auth.tenant)
    try:
        ws.link(store, body.a, body.b, body.scope)
    except ws.WorkspaceError as e:
        raise _fail(e)
    return _done(auth, store)


@router.patch("/workspace/links/{link_id}")
def pause_link(link_id: str, body: PausedIn, auth: AuthContext = Depends(require_role(["human"]))):
    store = get_graph_store(auth.tenant)
    try:
        ws.set_link_paused(store, link_id, body.paused)
    except ws.WorkspaceError as e:
        raise _fail(e)
    return _done(auth, store)


@router.delete("/workspace/links/{link_id}")
def remove_link(link_id: str, auth: AuthContext = Depends(require_role(["human"]))):
    store = get_graph_store(auth.tenant)
    try:
        ws.unlink(store, link_id)
    except ws.WorkspaceError as e:
        raise _fail(e)
    return _done(auth, store)
