import contextvars
import json
import os
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
from app.auth import resolve_token
from app.services.event_bus import event_bus
from app.services import context_pack as cp, observer, workspace
from app.services.context_pack import estimate_tokens


def _emit(tenant: str, nodes: List[GraphNode] = (), edges: List[GraphEdge] = ()) -> None:
    """Tell connected consoles about what an agent just wrote, so MCP writes show up live like scenario writes do."""
    for n in nodes:
        event_bus.publish(tenant, "node_added", {"node": n.model_dump()})
    for e in edges:
        event_bus.publish(tenant, "edge_added", {"edge": e.model_dump()})


class AuthError(Exception):
    pass


class RateLimited(Exception):
    def __init__(self, retry_after: float):
        self.retry_after = retry_after


# The token the connection proved with its Authorization header. Set per call by `guarded`; a header token wins over
# a token passed as a tool argument, and the argument stays supported for clients that cannot send headers.
_header_token: contextvars.ContextVar[str] = contextvars.ContextVar("quorum_header_token", default="")


def effective_token(arg: Any = "") -> str:
    """Header token, else the token argument, else QUORUM_MCP_TOKEN (set on a stdio server so the model never sees it)."""
    return _header_token.get() or (arg if isinstance(arg, str) else "") or os.getenv("QUORUM_MCP_TOKEN", "")


def _get_auth(token: str = "") -> Dict[str, Any]:
    info = resolve_token(effective_token(token))
    if not info:
        raise AuthError("Missing or invalid token. Send Authorization: Bearer <token> on the connection, or pass token.")
    return info


def _summary(tool: str, bound: Dict[str, Any]) -> str:
    for key in ("query", "id", "ref", "root_id", "key", "text", "label", "from_id"):
        v = bound.get(key)
        if isinstance(v, str) and v:
            if tool == "find_path":
                return f"{bound.get('from_id')} to {bound.get('to_id')}"
            return v if len(v) <= 70 else v[:69] + "…"
    return ""


def _record(tool: str, bound: Dict[str, Any], out: Any, ms: float) -> None:
    """Every tool call becomes a row: who, what, how many tokens it cost, and what a typical retriever would have sent."""
    info = resolve_token(effective_token(bound.get("token")))
    if not info:
        return
    store = get_graph_store(info["tenant"])
    ok = not (isinstance(out, dict) and out.get("success") is False)
    tokens = out.get("tokens") if isinstance(out, dict) and isinstance(out.get("tokens"), int) else estimate_tokens(json.dumps(out, default=str))
    baseline = out.get("tokens_baseline", 0) if isinstance(out, dict) and isinstance(out.get("tokens_baseline"), int) else 0
    rec = store.record_call(
        {
            "tool": tool,
            "agent_id": info.get("agent_id"),
            "member_id": info.get("member_id"),
            "role": info["role"],
            "summary": _summary(tool, bound),
            "tokens": tokens,
            "baseline": baseline,
            "ms": round(ms, 1),
            "ok": ok,
            "error": (out.get("error") if isinstance(out, dict) and not ok else None),
        }
    )
    event_bus.publish(info["tenant"], "mcp_call", {"call": rec})


def _header_from(ctx) -> str:
    """The bearer token on the HTTP request that carries this tool call (streamable HTTP only)."""
    try:
        req = ctx.request_context.request
        h = req.headers
    except Exception:
        return ""
    auth = h.get("authorization") or ""
    if auth[:7].lower() == "bearer ":
        return auth[7:].strip()
    return (h.get("x-quorum-token") or "").strip()


def guarded(fn):
    """
    Wraps an MCP tool: refuses to run without FalkorDB, reads the Authorization header, rate limits per token, turns a
    bad token into a clear error, records the call, and persists the tool's writes before returning. The tool's
    signature is preserved (plus an injected `ctx`) so MCP can still describe it.
    """
    import functools
    import inspect

    from mcp.server.mcpserver import Context

    sig = inspect.signature(fn)
    ctx_param = inspect.Parameter("ctx", inspect.Parameter.KEYWORD_ONLY, default=None, annotation=Context)

    @functools.wraps(fn)
    def wrapper(*args, ctx=None, **kwargs):
        from app import db
        from app.db import FalkorUnavailable
        from app.graph.queries import sync_all
        from app.ratelimit import tool_limiter

        reset = _header_token.set(_header_from(ctx) if ctx is not None else "")
        try:
            if settings.PERSISTENCE == "falkordb":
                db.require_db()
                if os.getenv("QUORUM_STANDALONE_MCP") == "1":
                    # A separate MCP process shares FalkorDB, not memory: start every call from the stored state.
                    from app.graph.queries import forget_stores

                    forget_stores()
            bound_args = dict(sig.bind(*args, **kwargs).arguments)
            who = effective_token(bound_args.get("token")) or "anonymous"
            ok, wait = tool_limiter.allow(who)
            if not ok:
                return {"error": f"Rate limit reached. Retry in {wait:.1f}s.", "success": False, "rate_limited": True, "retry_after": round(wait, 1)}
            t0 = time.time()
            out = fn(*args, **kwargs)
            try:
                _record(fn.__name__, bound_args, out, (time.time() - t0) * 1000)
            except AuthError:
                pass
            if settings.PERSISTENCE == "falkordb":
                sync_all()
            return out
        except AuthError as e:
            return {"error": str(e), "success": False}
        except FalkorUnavailable as e:
            raise RuntimeError(f"FALKORDB_UNAVAILABLE: {e.reason}. Start FalkorDB (docker compose up -d falkordb) and retry.")
        finally:
            _header_token.reset(reset)

    wrapper.__signature__ = sig.replace(parameters=[*sig.parameters.values(), ctx_param])
    wrapper.__annotations__ = {**getattr(fn, "__annotations__", {}), "ctx": Context}
    return wrapper


def _viewer(auth: Dict[str, Any], store):
    return workspace.viewer_for(store, auth.get("member_id"))


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


def _agent_key(auth: Dict[str, Any]) -> str:
    return auth.get("member_id") or auth.get("agent_id") or "agent"


def _remember_delivery(store, auth: Dict[str, Any], ids: List[str], query: Optional[str] = None) -> None:
    with store._lock:
        st = store.agent_state.setdefault(_agent_key(auth), {"ids": set(), "query": "", "epoch": store.epoch})
        st["ids"].update(ids)
        st["epoch"] = store.epoch
        if query is not None:
            st["query"] = query


def retrieve_context(
    query: str,
    token: str = "",
    k: int = 5,
    format: str = "full",
    budget_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Healthy, unsuperseded, in-scope context for a question, best match first.
    format="full" returns the matching facts as JSON (the default, for existing callers).
    format="compact" returns one line per node with short ids and the ancestors that prove each one, within
    budget_tokens (default 400). It costs a fraction of the tokens: prefer it, and cite the ids it gives you.
    Every response carries `tokens` (its size) and `tokens_baseline` (what a typical top-8 retriever would have sent).
    """
    auth = _get_auth(token)
    store = get_graph_store(auth["tenant"])
    viewer = _viewer(auth, store)

    if format == "compact":
        p = cp.pack(store, query, budget=max(60, int(budget_tokens or 400)), viewer=viewer)
        _remember_delivery(store, auth, p["ids"], query)
        out = {
            "epoch": store.epoch,
            "format": "compact",
            "count": len(p["ids"]),
            "matched": p["matched"],
            "truncated": p["truncated"],
            "packed": p["text"],
            "ids": p["short_ids"],
        }
        out["tokens"] = estimate_tokens(json.dumps(out))
        out["tokens_baseline"] = p["tokens_baseline"]
        return out

    with store._lock:
        nodes = [n for n in store.nodes.values() if viewer.can_see(n)]
    qw = set(cp._words(query))
    candidates = [n for n in nodes if n.kind == NodeKind.FACT and n.status == Status.HEALTHY and not n.stale]
    idf = cp.idf_weights(candidates)
    ranked = [(n, sc) for n, sc, _ in cp.rank(candidates, query, idf)]
    matched = [
        {
            "id": f.id,
            "key": f.key,
            "value": f.value,
            "text": f.text,
            "quote": f.quote,
            "asserted_by": f.asserted_by.model_dump() if f.asserted_by else None,
        }
        for f, score in ranked
        if score > 0
    ]
    out = {"epoch": store.epoch, "count": len(matched), "context": matched[: max(1, k)]}
    _remember_delivery(store, auth, [m["id"] for m in out["context"]], query)
    out["tokens"] = estimate_tokens(json.dumps(out))
    out["tokens_baseline"] = cp.baseline_tokens(nodes, query)
    return out


def get_map(token: str = "") -> Dict[str, Any]:
    """A small index of the shared memory: areas, hubs and how to ask. Read it once per session instead of loading the graph."""
    auth = _get_auth(token)
    store = get_graph_store(auth["tenant"])
    m = cp.build_map(store, _viewer(auth, store))
    return {"epoch": m["epoch"], "map": m["text"], "tokens": m["tokens"], "tokens_baseline": m["tokens_baseline"]}


def get_node(id: str, token: str = "") -> Dict[str, Any]:
    """One node, its parents and its children, by short id (F3, C2) or full id. A few lines instead of a document."""
    auth = _get_auth(token)
    store = get_graph_store(auth["tenant"])
    v = cp.node_view(store, id, _viewer(auth, store))
    if v.get("success"):
        _remember_delivery(store, auth, [v["id"]])
    return v


def find_path(from_id: str, to_id: str, token: str = "") -> Dict[str, Any]:
    """The shortest causal chain between two nodes: provenance without the whole subgraph."""
    auth = _get_auth(token)
    store = get_graph_store(auth["tenant"])
    return cp.find_path(store, from_id, to_id, _viewer(auth, store))


def delta(token: str = "") -> Dict[str, Any]:
    """
    What changed since you last read: facts you were given that are no longer valid (drop them), and new matches for
    your last question. Call it when the epoch in any response changes, instead of re-reading everything.
    """
    auth = _get_auth(token)
    store = get_graph_store(auth["tenant"])
    viewer = _viewer(auth, store)
    with store._lock:
        st = store.agent_state.get(_agent_key(auth))
        delivered = set(st["ids"]) if st else set()
        last_query = st["query"] if st else ""
    if not st:
        text = "nothing read yet: call retrieve_context first"
        return {"epoch": store.epoch, "text": text, "invalidated": [], "tokens": estimate_tokens(text), "tokens_baseline": 0}
    with store._lock:
        nodes = {n.id: n for n in store.nodes.values()}
    ids = cp.short_ids(nodes.values())
    gone: List[str] = []
    for i in sorted(delivered):
        n = nodes.get(i)
        if n is None or not viewer.can_see(n) or n.status != Status.HEALTHY or n.stale:
            why = "removed" if n is None else (n.status.value.lower() if n.status != Status.HEALTHY else "stale")
            gone.append(f"✗ {ids.get(i, i)} no longer valid ({why})")
    still = {i for i in delivered if i in nodes and nodes[i].status == Status.HEALTHY and not nodes[i].stale and viewer.can_see(nodes[i])}
    p = cp.pack(store, last_query, budget=300, viewer=viewer, have_ids=still)
    body = [f"# delta · epoch {store.epoch}"] + gone + ([l for l in p["text"].split("\n")[1:]] if p["ids"] else [])
    if len(body) == 1:
        body.append("no changes")
    text = "\n".join(body)
    _remember_delivery(store, auth, p["ids"])
    with store._lock:
        store.agent_state[_agent_key(auth)]["ids"] = still | set(p["ids"])
    return {
        "epoch": store.epoch,
        "text": text,
        "invalidated": [g.split(" ")[1] for g in gone],
        "new": p["short_ids"],
        "tokens": estimate_tokens(text),
        "tokens_baseline": p["tokens_baseline"],
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


def quarantine(root_id: str, token: str = "", reason: str = "Manual auditor quarantine") -> Dict[str, Any]:
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


def restore(root_id: str, token: str = "") -> Dict[str, Any]:
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
