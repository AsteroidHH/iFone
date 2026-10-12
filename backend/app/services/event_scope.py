"""Which live events a scoped viewer may receive. Unscoped callers (demo and service tokens) get everything."""
from typing import Any, Dict

from app.services.context_pack import Viewer


def _visible_node_id(store, viewer: Viewer, node_id: str) -> bool:
    n = store.nodes.get(node_id)
    return n is None or viewer.can_see(n)


def event_visible(store, viewer: Viewer, ev) -> bool:
    if not viewer.scoped:
        return True
    t, d = ev.type, (ev.data or {})
    if t in ("node_added", "node_updated"):
        node: Dict[str, Any] = d.get("node") or {}
        st = node.get("scope_team")
        return not st or st == viewer.team_id or st in viewer.linked_teams
    if t == "edge_added":
        e = d.get("edge") or {}
        return _visible_node_id(store, viewer, e.get("source", "")) and _visible_node_id(store, viewer, e.get("target", ""))
    if t == "status_changed":
        return _visible_node_id(store, viewer, d.get("id", ""))
    if t == "mcp_call":
        mid = (d.get("call") or {}).get("member_id")
        if not mid:
            return True
        member = next((m for m in store.workspace["members"] if m["id"] == mid), None)
        return member is None or member["team_id"] in ({viewer.team_id} | set(viewer.linked_teams))
    return True
