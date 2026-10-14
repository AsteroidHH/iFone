"""Auditor tools: quarantine, restore, explain_blast_radius."""
from typing import Any, Dict

from app.graph.queries import get_graph_store
from app.services import roles
from app.services.auditor import auditor_service
from app.services.mcp_guard import AuthError, _get_auth, effective_token, emit as _emit, guarded, viewer_of as _viewer  # noqa: F401


def quarantine(root_id: str, token: str = "", reason: str = "Manual auditor quarantine") -> Dict[str, Any]:
    """Auditor-only tool: Quarantines root fact and cascades down causal descendants."""
    auth = _get_auth(token)
    if auth["role"] not in ["auditor", "human"]:
        return {"error": roles.refusal(auth.get("agent_id") or "This token", auth["role"], "quarantine facts", "auditor", "human"), "success": False}

    store = get_graph_store(auth["tenant"])
    affected = auditor_service.quarantine(store, root_id, reason=reason, tenant=auth["tenant"])
    return {
        "epoch": store.epoch,
        "root_id": root_id,
        "affected_count": len(affected),
        "affected_nodes": affected,
        "success": True,
    }


def restore(root_id: str, token: str = "") -> Dict[str, Any]:
    """Auditor-only tool: Restores root fact and valid descendants if all parents are healthy."""
    auth = _get_auth(token)
    if auth["role"] not in ["auditor", "human"]:
        return {"error": roles.refusal(auth.get("agent_id") or "This token", auth["role"], "restore facts", "auditor", "human"), "success": False}

    store = get_graph_store(auth["tenant"])
    restored_ids = auditor_service.restore(store, root_id, tenant=auth["tenant"])
    return {
        "epoch": store.epoch,
        "root_id": root_id,
        "restored_count": len(restored_ids),
        "restored_nodes": restored_ids,
        "success": True,
    }


def explain_blast_radius(root_id: str, token: str = "") -> Dict[str, Any]:
    """Auditor tool: Dry-run blast radius calculation."""
    auth = _get_auth(token)
    store = get_graph_store(auth["tenant"])
    with store._lock:
        descendants = store.get_descendants(root_id, edge_types=["LEADS_TO", "SUPPORTS"])
    return {
        "epoch": store.epoch,
        "root_id": root_id,
        "predicted_impact_count": len(descendants),
        "predicted_impact_nodes": [d.id for d in descendants],
    }
