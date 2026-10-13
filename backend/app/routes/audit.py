from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from app.auth import AuthContext, get_auth_context
from app.graph.queries import get_graph_store
from app.routes.mcp_info import visible_calls

router = APIRouter()


_VERBS = {
    "retrieve_context": ("looked up", "read"),
    "get_map": ("read the memory map", "read"),
    "get_node": ("opened", "read"),
    "find_path": ("traced how", "read"),
    "delta": ("checked what changed", "read"),
    "remember_fact": ("recorded a fact", "write"),
    "observe": ("captured facts from text", "write"),
    "derive": ("recorded a conclusion", "write"),
    "stage_action": ("proposed an action", "write"),
    "execute_action": ("executed an action", "write"),
    "claim_handoff": ("claimed a task", "write"),
    "quarantine": ("quarantined", "alert"),
    "restore": ("restored", "alert"),
    "explain_blast_radius": ("previewed the impact of quarantining", "read"),
    "review_handoff": ("reviewed a handoff", "alert"),
}


_INFINITIVE = {
    "looked up": "look up",
    "read the memory map": "read the memory map",
    "opened": "open",
    "traced how": "trace how",
    "checked what changed": "check what changed",
    "recorded a fact": "record a fact",
    "captured facts from text": "capture facts from text",
    "recorded a conclusion": "record a conclusion",
    "proposed an action": "propose an action",
    "executed an action": "execute an action",
    "claimed a task": "claim a task",
    "quarantined": "quarantine",
    "restored": "restore",
    "previewed the impact of quarantining": "preview the impact of quarantining",
    "reviewed a handoff": "review a handoff",
}
_QUOTED = ("retrieve_context", "remember_fact", "stage_action", "get_node", "observe")


def _sentence(c: Dict[str, Any]) -> Dict[str, Any]:
    verb, sev = _VERBS.get(c["tool"], (c["tool"], "read"))
    subj = c.get("summary") or ""
    if not c.get("ok", True):
        why = c.get("error") or "an error"
        return {"text": f"tried to {_INFINITIVE.get(verb, verb)}{(' ' + subj) if subj else ''} and was refused: {why}", "severity": "failed"}
    if subj and c["tool"] in _QUOTED:
        return {"text": f"{verb} “{subj}”", "severity": sev}
    return {"text": f"{verb} {subj}".strip(), "severity": sev}


@router.get("/audit")
def audit(
    limit: int = Query(200, ge=1, le=2000),
    since: Optional[int] = Query(None, description="only events after this unix-ms timestamp"),
    agent: Optional[str] = Query(None),
    severity: Optional[str] = Query(None, pattern="^(read|write|alert|failed)$"),
    format: str = Query("json", pattern="^(json|csv)$"),
    auth: AuthContext = Depends(get_auth_context),
):
    """A plain-language record of what every agent did: who, what, when, what it cost. Newest first."""
    import csv
    import io

    from fastapi.responses import Response

    store = get_graph_store(auth.tenant)
    with store._lock:
        members = {m["id"]: m for m in store.workspace["members"]}
        teams = {t["id"]: t["name"] for t in store.workspace["teams"]}
    events = []
    for c in reversed(visible_calls(store, auth)):
        if since and c["ts"] <= since:
            break
        m = members.get(c.get("member_id") or "")
        s = _sentence(c)
        if agent and agent not in (c.get("agent_id"), (m or {}).get("name")):
            continue
        if severity and s["severity"] != severity:
            continue
        events.append(
            {
                "id": c["id"],
                "ts": c["ts"],
                "who": (m or {}).get("name") or c.get("agent_id") or "unknown",
                "team": teams.get((m or {}).get("team_id") or "", None),
                "client": (m or {}).get("client"),
                "tool": c["tool"],
                "text": s["text"],
                "severity": s["severity"],
                "ok": bool(c.get("ok", True)),
                "tokens": c.get("tokens", 0),
                "saved": max(0, c.get("baseline", 0) - c.get("tokens", 0)) if c.get("baseline", 0) > 0 else 0,
            }
        )
        if len(events) >= limit:
            break
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["time_utc", "who", "team", "client", "tool", "what", "severity", "ok", "tokens", "tokens_saved"])
        import datetime as _dt

        for e in events:
            # a leading = + - @ would make a spreadsheet run the cell as a formula
            cell = lambda v: ("'" + v) if isinstance(v, str) and v[:1] in "=+-@" else v  # noqa: E731
            w.writerow([_dt.datetime.fromtimestamp(e["ts"] / 1000, _dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), cell(e["who"]), cell(e["team"] or ""), e["client"] or "", e["tool"], cell(e["text"]), e["severity"], e["ok"], e["tokens"], e["saved"]])
        return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="quorum-audit.csv"'})
    by_sev: Dict[str, int] = {}
    agents = set()
    for e in events:
        by_sev[e["severity"]] = by_sev.get(e["severity"], 0) + 1
        agents.add(e["who"])
    return {
        "events": events,
        "summary": {"events": len(events), "agents": len(agents), "by_severity": by_sev, "tokens": sum(e["tokens"] for e in events), "tokens_saved": sum(e["saved"] for e in events)},
        "retention": f"the last {store.MAX_CALLS} tool calls",
    }

