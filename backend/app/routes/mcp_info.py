from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import AuthContext, get_auth_context
from app.graph.queries import get_graph_store
from pydantic import BaseModel, Field

from app.config import settings
from app.services import context_pack as cp, embeddings, mcp_catalog, mcp_tools
from app.services import workspace as ws

router = APIRouter()


def visible_calls(store, auth: AuthContext) -> List[Dict[str, Any]]:
    """Unscoped callers (demo and service tokens) see every call. A member sees calls by their own team and linked teams."""
    viewer = ws.viewer_for(store, auth.member_id)
    with store._lock:
        calls = list(store.calls)
        members = {m["id"]: m for m in store.workspace["members"]}
    if not viewer.scoped:
        return calls
    allowed = {viewer.team_id} | set(viewer.linked_teams)
    out = []
    for c in calls:
        m = members.get(c.get("member_id") or "")
        if m is None or m["team_id"] in allowed:
            out.append(c)
    return out


def stats_for(calls: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Savings are counted only on calls that report a baseline (the read tools). Per call it can be negative; it is not clipped."""
    measured = [c for c in calls if c.get("baseline", 0) > 0 and c.get("ok", True)]
    tokens = sum(c["tokens"] for c in measured)
    baseline = sum(c["baseline"] for c in measured)

    def agg(key: str) -> List[Dict[str, Any]]:
        d: Dict[str, Dict[str, Any]] = {}
        for c in measured:
            k = c.get(key) or "unknown"
            r = d.setdefault(k, {"name": k, "calls": 0, "tokens": 0, "baseline": 0})
            r["calls"] += 1
            r["tokens"] += c["tokens"]
            r["baseline"] += c["baseline"]
        return sorted(({**r, "saved": r["baseline"] - r["tokens"]} for r in d.values()), key=lambda r: -r["saved"])

    return {
        "calls": len(calls),
        "measured_calls": len(measured),
        "tokens": tokens,
        "baseline": baseline,
        "saved": baseline - tokens,
        "saved_pct": round((baseline - tokens) / baseline * 100, 1) if baseline else 0.0,
        "by_tool": agg("tool"),
        "by_agent": agg("agent_id"),
        "method": "tokens are estimates (about 4.5 characters per token); baseline is a typical top-8 retriever's full-JSON answer to the same call",
    }


@router.get("/mcp/activity")
def mcp_activity(
    limit: int = Query(100, ge=1, le=500),
    member_id: Optional[str] = Query(None),
    auth: AuthContext = Depends(get_auth_context),
):
    """Every MCP tool call, newest first: who, what, tokens used and the baseline. The Connect page's feed and chats."""
    store = get_graph_store(auth.tenant)
    calls = visible_calls(store, auth)
    if member_id:
        calls = [c for c in calls if c.get("member_id") == member_id]
    return list(reversed(calls[-limit:]))


@router.get("/token-stats")
def token_stats(auth: AuthContext = Depends(get_auth_context)):
    store = get_graph_store(auth.tenant)
    return stats_for(visible_calls(store, auth))


@router.get("/context/preview")
def context_preview(
    query: str = Query("refund window", max_length=200),
    budget: int = Query(400, ge=60, le=4000),
    auth: AuthContext = Depends(get_auth_context),
):
    """What an agent with this token would be handed for `query`, and what it costs against the usual alternatives."""
    store = get_graph_store(auth.tenant)
    return cp.compare(store, query, budget, ws.viewer_for(store, auth.member_id))


@router.get("/mcp/catalog")
def mcp_catalog_route(auth: AuthContext = Depends(get_auth_context)):
    """The tools this hub serves, read from the code, plus how to reach it."""
    return {
        "tools": mcp_catalog.catalog(),
        "public_url": settings.PUBLIC_URL or None,
        "header_required": settings.mcp_header_required(),
        "rate_limit_per_min": {"tools": settings.RATE_LIMIT_TOOLS_PER_MIN, "http": settings.RATE_LIMIT_HTTP_PER_MIN},
        "embedding_provider": embeddings.provider_name(),
    }


class ObserveIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=60000)
    source: str = Field("transcript", max_length=40)
    dry_run: bool = False
    scope: str = "commons"


@router.post("/observe")
def observe_route(body: ObserveIn, auth: AuthContext = Depends(get_auth_context)):
    """Passive capture: send a chat transcript or tool output; durable facts in it are stored with their source sentence."""
    if auth.role == "auditor":
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN_ROLE", "message": "Auditors do not write facts."}})
    info = {"tenant": auth.tenant, "role": auth.role, "agent_id": auth.agent_id, "member_id": auth.member_id, "team_id": auth.team_id}
    return mcp_tools.observe_text(info, body.text, body.source, body.dry_run, body.scope)


@router.get("/context/semantic-check")
def semantic_check(query: str = Query("how long can shoppers get their money back", max_length=200), k: int = Query(5, ge=1, le=20), auth: AuthContext = Depends(get_auth_context)):
    """Ask FalkorDB's own vector index for the nearest nodes and compare with the API process's ranking."""
    from app import db

    store = get_graph_store(auth.tenant)
    viewer = ws.viewer_for(store, auth.member_id)
    with store._lock:
        nodes = [n for n in store.nodes.values() if viewer.can_see(n)]
    cand = [n for n in nodes if n.kind.value in ("fact", "conclusion") and n.status.value == "HEALTHY" and not n.stale]
    ranked = cp.rank(cand, query, cp.idf_weights(cand))[:k]
    out = {"query": query, "provider": embeddings.provider_name(), "api_top": [{"id": n.id, "score": round(s, 3), "cosine": round(c, 3)} for n, s, c in ranked if s > 0], "falkordb_top": None, "agrees": None}
    if store.persister is not None and embeddings.provider_name() == "local":
        qv = embeddings.as_list(embeddings.query_vector(query))
        try:
            res = db.graph_for(auth.tenant).query(
                "CALL db.idx.vector.queryNodes('QNode', 'embedding', $k, vecf32($q)) YIELD node, score RETURN node.id, score ORDER BY score",
                {"k": max(k * 4, 20), "q": qv},
            ).result_set
            allowed = {n.id for n in cand}
            fal = [{"id": r[0], "distance": round(float(r[1]), 3)} for r in res if r[0] in allowed][:k]
            out["falkordb_top"] = fal
            out["agrees"] = bool(fal) and bool(out["api_top"]) and fal[0]["id"] in [a["id"] for a in out["api_top"][:3]]
        except Exception as e:
            out["falkordb_error"] = f"{type(e).__name__}: {e}"[:200]
    return out


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
