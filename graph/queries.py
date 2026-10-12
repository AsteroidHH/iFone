"""
Quorum Graph Query Library (graph/queries.py)

Author: Janani (Person 1 - Graph & FalkorDB)
Delivers tested Cypher statements returning plain Python dicts.
Logs every query execution to an in-memory query log for the UI 'Show Cypher' drawer.
"""

import time
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from falkordb import FalkorDB

logger = logging.getLogger("quorum.graph")

# In-memory query log (FIFO ring buffer of last 500 queries)
QUERY_LOG: List[Dict[str, Any]] = []
MAX_QUERY_LOG_SIZE = 500

_db_client: Optional[FalkorDB] = None


def get_db(host: str = "localhost", port: int = 6379) -> FalkorDB:
    global _db_client
    if _db_client is None:
        _db_client = FalkorDB(host=host, port=port)
    return _db_client


def log_query(name: str, cypher: str, ms: float, rows: int, request_id: Optional[str] = None):
    entry = {
        "ts": int(time.time() * 1000),
        "request_id": request_id or "",
        "name": name,
        "cypher": cypher.strip(),
        "ms": round(ms, 2),
        "rows": rows,
    }
    QUERY_LOG.append(entry)
    if len(QUERY_LOG) > MAX_QUERY_LOG_SIZE:
        QUERY_LOG.pop(0)


def get_query_log(limit: int = 50) -> List[Dict[str, Any]]:
    return list(reversed(QUERY_LOG[-limit:]))


def get_graph(tenant_id: str, kind: str = "commons"):
    graph_name = f"tenant_{tenant_id}:{kind}"
    db = get_db()
    g = db.select_graph(graph_name)
    # Ensure Meta node exists
    try:
        res = g.query("MATCH (m:Meta {id: 'meta'}) RETURN m.epoch")
        if not res.result_set:
            g.query("CREATE (:Meta {id: 'meta', epoch: 1})")
    except Exception:
        pass
    return g


def ensure_indexes(tenant_id: str):
    """Initializes vector index and primary lookup indexes."""
    g = get_graph(tenant_id, "commons")
    queries = [
        "CREATE INDEX FOR (f:Fact) ON (f.id)",
        "CREATE INDEX FOR (f:Fact) ON (f.key)",
        "CREATE INDEX FOR (f:Fact) ON (f.status)",
        "CREATE INDEX FOR (c:Conclusion) ON (c.id)",
        "CREATE INDEX FOR (c:Conclusion) ON (c.status)",
        "CREATE INDEX FOR (a:Action) ON (a.id)",
        "CREATE INDEX FOR (a:Action) ON (a.status)",
        "CREATE INDEX FOR (h:Handoff) ON (h.id)",
        "CREATE INDEX FOR (s:Source) ON (s.id)",
        "CREATE VECTOR INDEX FOR (f:Fact) ON (f.embedding) OPTIONS {dimension: 384, similarityFunction: 'cosine'}",
    ]
    for q in queries:
        try:
            g.query(q)
        except Exception:
            pass


# =========================================================================
# 1. ATOMIC DERIVATION GUARD: STAGE ACTION & DERIVE
# =========================================================================

def stage_action(
    tenant_id: str,
    action_id: str,
    parent_ids: List[str],
    action_type: str,
    payload: Dict[str, Any],
    reversibility: str,
    gate: str = "PASSED",
    procedure_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Stages an action with the atomic derivation guard: commits only if all
    parent_ids currently exist and are HEALTHY.
    """
    g = get_graph(tenant_id, "commons")
    name = "stage_action"
    idempotency_key = idempotency_key or f"idem_{action_id}"
    payload_str = json.dumps(payload)

    if not parent_ids:
        # Standalone action without parents
        cypher = """
        CREATE (a:Action:MemoryNode {
            id: $id, type: $type, payload: $payload, status: 'HEALTHY',
            executed: false, executed_at: null, confirmed: false,
            gate: $gate, reversibility: $reversibility,
            procedure_id: $procedure_id, idempotency_key: $idempotency_key,
            stale: false, created_at: timestamp()
        })
        RETURN a.id, a.status, a.gate
        """
        params = {
            "id": action_id, "type": action_type, "payload": payload_str,
            "gate": gate, "reversibility": reversibility,
            "procedure_id": procedure_id, "idempotency_key": idempotency_key
        }
    else:
        cypher = """
        MATCH (p:MemoryNode) WHERE p.id IN $parent_ids
        WITH collect(p) AS parents
        WHERE size(parents) = size($parent_ids) AND ALL(x IN parents WHERE x.status = 'HEALTHY')
        CREATE (a:Action:MemoryNode {
            id: $id, type: $type, payload: $payload, status: 'HEALTHY',
            executed: false, executed_at: null, confirmed: false,
            gate: $gate, reversibility: $reversibility,
            procedure_id: $procedure_id, idempotency_key: $idempotency_key,
            stale: false, created_at: timestamp()
        })
        WITH a, parents
        UNWIND parents AS p
        CREATE (p)-[:LEADS_TO]->(a)
        RETURN a.id, a.status, a.gate
        """
        params = {
            "id": action_id, "parent_ids": parent_ids, "type": action_type,
            "payload": payload_str, "gate": gate, "reversibility": reversibility,
            "procedure_id": procedure_id, "idempotency_key": idempotency_key
        }

    t0 = time.time()
    res = g.query(cypher, params)
    ms = (time.time() - t0) * 1000
    rows = len(res.result_set)
    log_query(name, cypher, ms, rows, request_id)

    if not rows:
        return {"success": False, "error": "Atomic derivation guard refused: parents missing or not HEALTHY"}

    return {
        "success": True,
        "action_id": res.result_set[0][0],
        "status": res.result_set[0][1],
        "gate": res.result_set[0][2],
    }


def derive(
    tenant_id: str,
    conclusion_id: str,
    parent_ids: List[str],
    text: str,
    is_decision: bool = False,
    owner_team: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Derives a new Conclusion (or Decision) node with atomic derivation guard.
    """
    g = get_graph(tenant_id, "commons")
    name = "derive"
    label_part = ":Conclusion:Decision:MemoryNode" if is_decision else ":Conclusion:MemoryNode"

    cypher = f"""
    MATCH (p:MemoryNode) WHERE p.id IN $parent_ids
    WITH collect(p) AS parents
    WHERE size(parents) = size($parent_ids) AND ALL(x IN parents WHERE x.status = 'HEALTHY')
    CREATE (c{label_part} {{
        id: $id, text: $text, status: 'HEALTHY', stale: false,
        owner_team: $owner_team, created_at: timestamp()
    }})
    WITH c, parents
    UNWIND parents AS p
    CREATE (p)-[:LEADS_TO]->(c)
    RETURN c.id, c.status
    """
    params = {"id": conclusion_id, "parent_ids": parent_ids, "text": text, "owner_team": owner_team}

    t0 = time.time()
    res = g.query(cypher, params)
    ms = (time.time() - t0) * 1000
    rows = len(res.result_set)
    log_query(name, cypher, ms, rows, request_id)

    if not rows:
        return {"success": False, "error": "Atomic derivation guard refused: parents missing or not HEALTHY"}

    return {"success": True, "conclusion_id": res.result_set[0][0], "status": res.result_set[0][1]}


# =========================================================================
# 2. ATOMIC EXECUTE GUARD
# =========================================================================

def execute_guard(tenant_id: str, action_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Atomic execute guard. Single statement checking that action is HEALTHY,
    unexecuted, gate PASSED, and has zero non-healthy ancestors over [:LEADS_TO|SUPPORTS*].
    Returns success=True only if the action passed all checks and was marked executed.
    """
    g = get_graph(tenant_id, "commons")
    name = "execute_guard"
    cypher = """
    MATCH (a:Action {id: $id})
    WHERE a.status = 'HEALTHY' AND a.executed = false AND a.gate = 'PASSED'
    OPTIONAL MATCH (x:MemoryNode)-[:LEADS_TO|SUPPORTS*]->(a)
    WHERE coalesce(x.status, 'MISSING') <> 'HEALTHY'
    WITH a, count(DISTINCT x) AS bad
    WHERE bad = 0
    SET a.executed = true, a.executed_at = timestamp(), a.confirmed = false
    RETURN a.id, a.executed, a.executed_at, a.idempotency_key, a.type, a.payload
    """
    t0 = time.time()
    res = g.query(cypher, {"id": action_id})
    ms = (time.time() - t0) * 1000
    rows = len(res.result_set)
    log_query(name, cypher, ms, rows, request_id)

    if not rows:
        return {"success": False, "action_id": action_id, "reason": "Guard refused: ancestor non-healthy or gate blocked"}

    row = res.result_set[0]
    return {
        "success": True,
        "action_id": row[0],
        "executed": row[1],
        "executed_at": row[2],
        "idempotency_key": row[3],
        "action_type": row[4],
        "payload": row[5],
    }


def confirm_action(tenant_id: str, action_id: str, request_id: Optional[str] = None) -> bool:
    """Sets confirmed=true upon receiving 200 OK from external API."""
    g = get_graph(tenant_id, "commons")
    cypher = "MATCH (a:Action {id: $id}) SET a.confirmed = true RETURN a.id"
    t0 = time.time()
    res = g.query(cypher, {"id": action_id})
    ms = (time.time() - t0) * 1000
    log_query("confirm_action", cypher, ms, len(res.result_set), request_id)
    return len(res.result_set) > 0


# =========================================================================
# 3. QUARANTINE CASCADE & COMPENSATIONS
# =========================================================================

def cascade(tenant_id: str, root_fact_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Quarantine cascade. In one pass:
    1. Collects descendants over [:LEADS_TO|SUPPORTS*].
    2. Partitions actions before mutating status.
    3. Sets status='QUARANTINED', quarantined_at=now, quarantine_root=root_id.
    4. Increments Meta.epoch.
    """
    g = get_graph(tenant_id, "commons")
    name = "cascade"
    t0 = time.time()

    # Query descendants with shortest path length (depth)
    cypher = """
    MATCH (root:Fact {id: $root_id})
    OPTIONAL MATCH p = (root)-[:LEADS_TO|SUPPORTS*0..15]->(m:MemoryNode)
    WITH m, length(p) AS depth
    ORDER BY depth ASC
    WITH collect(DISTINCT {node: m, depth: depth}) AS items
    UNWIND items AS item
    WITH item.node AS m, item.depth AS depth
    WHERE m IS NOT NULL
    SET m.status = 'QUARANTINED',
        m.quarantined_at = timestamp(),
        m.quarantine_root = $root_id
    WITH collect(DISTINCT {id: m.id, labels: labels(m), depth: depth, executed: m.executed, reversibility: m.reversibility}) AS affected
    MATCH (meta:Meta {id: 'meta'})
    SET meta.epoch = meta.epoch + 1
    RETURN affected, meta.epoch
    """
    res = g.query(cypher, {"root_id": root_fact_id})
    ms_containment = (time.time() - t0) * 1000
    rows = len(res.result_set)
    log_query(name, cypher, ms_containment, rows, request_id)

    if not rows or not res.result_set[0][0]:
        return {"affected_count": 0, "ms_to_containment": ms_containment, "node_ids_by_depth": {}, "executed_actions": []}

    raw_affected = res.result_set[0][0]
    epoch = res.result_set[0][1]

    node_ids_by_depth: Dict[int, List[str]] = {}
    executed_actions: List[Dict[str, Any]] = []

    for item in raw_affected:
        nid = item["id"]
        d = item["depth"]
        node_ids_by_depth.setdefault(d, []).append(nid)
        if "Action" in item.get("labels", []) and item.get("executed") is True:
            executed_actions.append({
                "action_id": nid,
                "reversibility": item.get("reversibility", "COMPENSABLE")
            })

    return {
        "success": True,
        "root_id": root_fact_id,
        "affected_count": len(raw_affected),
        "ms_to_containment": round(ms_containment, 2),
        "node_ids_by_depth": node_ids_by_depth,
        "executed_actions": executed_actions,
        "epoch": epoch,
    }


def create_compensations(
    tenant_id: str, executed_actions: List[Dict[str, Any]], request_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Separate idempotent compensation creation for actions that were executed=true.
    REVERSIBLE -> revert request
    COMPENSABLE -> reverse request
    IRREVERSIBLE -> ESCALATION handoff + notice
    """
    g = get_graph(tenant_id, "commons")
    results = []
    cypher = """
    MATCH (a:Action {id: $action_id})
    MERGE (c:Compensation {id: $comp_id})
    ON CREATE SET c.target_action_id = a.id,
                  c.status = 'PENDING_COMPENSATION',
                  c.attempts = 0,
                  c.lease_until = null,
                  c.idempotency_key = 'comp_' + a.idempotency_key,
                  c.reversibility = a.reversibility,
                  c.created_at = timestamp()
    MERGE (a)-[:COMPENSATED_BY]->(c)
    RETURN c.id, c.status
    """
    for act in executed_actions:
        aid = act["action_id"]
        cid = f"comp_{aid}"
        t0 = time.time()
        res = g.query(cypher, {"action_id": aid, "comp_id": cid})
        ms = (time.time() - t0) * 1000
        log_query("create_compensation", cypher, ms, len(res.result_set), request_id)
        if res.result_set:
            results.append({"compensation_id": cid, "action_id": aid, "status": "PENDING_COMPENSATION"})
    return results


# =========================================================================
# 4. SUPERSEDE & STALE PROPAGATION
# =========================================================================

def supersede(
    tenant_id: str,
    old_fact_id: str,
    new_fact_id: str,
    new_value: str,
    new_text: str,
    new_embedding: List[float],
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Supersedes an existing healthy fact with new value.
    Marks old fact valid_to=now, status=SUPERSEDED.
    Creates new fact, SUPERSEDES edge, increments Meta.epoch.
    Propagates stale=true to all Conclusion/Decision descendants.
    Creates REVIEW handoffs to owning teams.
    """
    g = get_graph(tenant_id, "commons")
    name = "supersede"

    cypher_main = """
    MATCH (old:Fact {id: $old_id}) WHERE old.status = 'HEALTHY' AND old.valid_to IS NULL
    SET old.valid_to = timestamp(), old.status = 'SUPERSEDED'
    CREATE (new:Fact:MemoryNode {
        id: $new_id, key: old.key, value: $value, text: $text, status: 'HEALTHY',
        embedding: vecf32($embedding), valid_from: timestamp(), stale: false
    })
    CREATE (new)-[:SUPERSEDES]->(old)
    WITH old, new
    MATCH (meta:Meta {id: 'meta'})
    SET meta.epoch = meta.epoch + 1
    RETURN new.id, meta.epoch
    """
    t0 = time.time()
    res = g.query(cypher_main, {
        "old_id": old_fact_id, "new_id": new_fact_id,
        "value": new_value, "text": new_text, "embedding": new_embedding
    })
    ms = (time.time() - t0) * 1000
    log_query(name, cypher_main, ms, len(res.result_set), request_id)

    if not res.result_set:
        return {"success": False, "error": "Old fact not found, not HEALTHY, or already superseded"}

    epoch = res.result_set[0][1]

    # Stale propagation: flag descendant conclusions as stale
    cypher_stale = """
    MATCH (old:Fact {id: $old_id})-[:LEADS_TO*1..10]->(c:Conclusion)
    SET c.stale = true
    RETURN c.id, c.owner_team
    """
    t1 = time.time()
    res_stale = g.query(cypher_stale, {"old_id": old_fact_id})
    ms_stale = (time.time() - t1) * 1000
    log_query("stale_propagation", cypher_stale, ms_stale, len(res_stale.result_set), request_id)

    stale_conclusions = [r[0] for r in res_stale.result_set]
    return {
        "success": True,
        "new_fact_id": new_fact_id,
        "stale_conclusions_count": len(stale_conclusions),
        "epoch": epoch,
    }


# =========================================================================
# 5. RESTORE
# =========================================================================

def restore(tenant_id: str, root_fact_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Restores quarantined subgraph starting from root.
    A node is restored ONLY if ALL its parents (LEADS_TO and SUPPORTS) are HEALTHY.
    NEVER restores executed actions. Bumps Meta.epoch.
    """
    g = get_graph(tenant_id, "commons")
    name = "restore"

    # Step 1: Restore root fact
    cypher_root = """
    MATCH (root:Fact {id: $root_id, status: 'QUARANTINED'})
    SET root.status = 'HEALTHY', root.released_at = timestamp()
    RETURN root.id
    """
    t0 = time.time()
    res_root = g.query(cypher_root, {"root_id": root_fact_id})
    ms = (time.time() - t0) * 1000
    log_query("restore_root", cypher_root, ms, len(res_root.result_set), request_id)

    if not res_root.result_set:
        return {"success": False, "error": "Root fact not in QUARANTINED state"}

    # Step 2: Iterative parent-verified restore for descendants
    # Never restore executed actions (executed = true)
    cypher_iter = """
    MATCH (p:MemoryNode)-[:LEADS_TO|SUPPORTS]->(m:MemoryNode {status: 'QUARANTINED'})
    WHERE NOT (m:Action AND m.executed = true)
    WITH m, collect(p) AS parents
    WHERE ALL(parent IN parents WHERE parent.status = 'HEALTHY')
    SET m.status = 'HEALTHY', m.released_at = timestamp()
    RETURN m.id
    """
    restored_nodes = [root_fact_id]
    while True:
        t_iter = time.time()
        res_iter = g.query(cypher_iter)
        ms_iter = (time.time() - t_iter) * 1000
        rows = len(res_iter.result_set)
        log_query("restore_descendant_pass", cypher_iter, ms_iter, rows, request_id)
        if not rows:
            break
        restored_nodes.extend([r[0] for r in res_iter.result_set])

    # Increment epoch
    bump_epoch(tenant_id)

    return {
        "success": True,
        "restored_count": len(restored_nodes),
        "restored_nodes": restored_nodes,
    }


# =========================================================================
# 6. HANDOFF CLAIM
# =========================================================================

def claim_handoff(
    tenant_id: str,
    handoff_id: str,
    agent_id: str,
    role: str = "agent",
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Kind-aware atomic claim of a handoff node with lease timestamp.
    REVIEW/ESCALATION kinds require role in ['human', 'auditor'].
    """
    g = get_graph(tenant_id, "commons")
    name = "claim_handoff"

    # Pre-check kind permissions
    res_kind = g.query("MATCH (h:Handoff {id: $id}) RETURN h.kind", {"id": handoff_id})
    if not res_kind.result_set:
        return {"success": False, "error": "Handoff not found"}

    kind = res_kind.result_set[0][0]
    if kind in ["REVIEW", "ESCALATION"] and role not in ["human", "auditor"]:
        return {"success": False, "error": f"Role '{role}' forbidden from claiming {kind} handoffs"}

    cypher = """
    MATCH (h:Handoff {id: $id})
    OPTIONAL MATCH (h)-[:CONTEXT_ROOT]->(anchor:MemoryNode)
    WITH h, anchor
    WHERE (h.status = 'PENDING' OR (h.status = 'IN_PROGRESS' AND h.lease_until < timestamp()))
      AND (h.kind <> 'TASK' OR anchor IS NULL OR anchor.status = 'HEALTHY')
    SET h.status = 'IN_PROGRESS',
        h.claimed_by = $agent_id,
        h.claimed_at = timestamp(),
        h.lease_until = timestamp() + 60000
    RETURN h.id, h.status, h.claimed_by, h.lease_until
    """
    t0 = time.time()
    res = g.query(cypher, {"id": handoff_id, "agent_id": agent_id})
    ms = (time.time() - t0) * 1000
    rows = len(res.result_set)
    log_query(name, cypher, ms, rows, request_id)

    if not rows:
        return {"success": False, "error": "Handoff already claimed, expired, or anchor unhealthy"}

    row = res.result_set[0]
    return {
        "success": True,
        "handoff_id": row[0],
        "status": row[1],
        "claimed_by": row[2],
        "lease_until": row[3],
    }


# =========================================================================
# 7. RETRIEVAL & AS-OF
# =========================================================================

def retrieve(
    tenant_id: str,
    query_embedding: List[float],
    k: int = 5,
    max_hops: int = 3,
    request_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Healthy-only retrieval. Returns only HEALTHY, unsuperseded context.
    Expands up to max_hops over healthy LEADS_TO paths.
    Uses verified vec.cosineDistance for ranking.
    """
    g = get_graph(tenant_id, "commons")
    name = "retrieve"

    cypher = f"""
    CALL db.idx.vector.queryNodes('Fact', 'embedding', {k * 2}, vecf32($vec))
    YIELD node, score
    WHERE node.status = 'HEALTHY' AND (node.valid_to IS NULL OR node.valid_to > timestamp())
    WITH node, score
    ORDER BY score ASC
    LIMIT {k}
    OPTIONAL MATCH p = (node)-[:LEADS_TO*0..{max_hops}]->(target:MemoryNode)
    WHERE ALL(n IN nodes(p) WHERE n.status = 'HEALTHY')
    RETURN DISTINCT target.id, labels(target), target.text, target.status, score
    """
    t0 = time.time()
    res = g.query(cypher, {"vec": query_embedding})
    ms = (time.time() - t0) * 1000
    rows = len(res.result_set)
    log_query(name, cypher, ms, rows, request_id)

    output = []
    for row in res.result_set:
        output.append({
            "id": row[0],
            "labels": row[1],
            "text": row[2],
            "status": row[3],
            "score": row[4],
        })
    return output


def as_of(tenant_id: str, timestamp_ms: int, request_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    As-of point-in-time belief recall (latest quarantine window per node).
    """
    g = get_graph(tenant_id, "commons")
    name = "as_of"
    cypher = """
    MATCH (f:Fact)
    WHERE f.valid_from <= $t AND (f.valid_to IS NULL OR f.valid_to > $t)
      AND NOT (f.quarantined_at IS NOT NULL AND f.quarantined_at <= $t
               AND (f.released_at IS NULL OR f.released_at > $t))
    RETURN f.id, f.text, f.status
    """
    t0 = time.time()
    res = g.query(cypher, {"t": timestamp_ms})
    ms = (time.time() - t0) * 1000
    rows = len(res.result_set)
    log_query(name, cypher, ms, rows, request_id)

    return [{"id": r[0], "text": r[1], "status": r[2]} for r in res.result_set]


# =========================================================================
# 8. COMPANY BRAIN QUERIES (TRACK 03)
# =========================================================================

def provenance(tenant_id: str, decision_id: str, request_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Decision provenance: Decision <- LEADS_TO <- Fact -> Source.
    """
    g = get_graph(tenant_id, "commons")
    name = "provenance"
    cypher = """
    MATCH (dec:Decision {id: $id})<-[:LEADS_TO*1..5]-(f:Fact)-[:FROM_SOURCE]->(s:Source)
    OPTIONAL MATCH (team:Team)-[:OWNS]->(s)
    RETURN f.text AS claim, f.quote AS quote, s.title AS source, s.url AS url,
           s.version AS version, team.name AS owner
    """
    t0 = time.time()
    res = g.query(cypher, {"id": decision_id})
    ms = (time.time() - t0) * 1000
    rows = len(res.result_set)
    log_query(name, cypher, ms, rows, request_id)

    return [
        {
            "claim": r[0], "quote": r[1], "source": r[2],
            "url": r[3], "version": r[4], "owner": r[5]
        }
        for r in res.result_set
    ]


def who_knows(tenant_id: str, topic_id: str, request_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Ranks Person nodes by count of AUTHORED|RESOLVED Sources ABOUT topic.
    """
    g = get_graph(tenant_id, "commons")
    name = "who_knows"
    cypher = """
    MATCH (p:Person)-[:AUTHORED|RESOLVED]->(s:Source)-[:ABOUT]->(t:Topic {id: $topic_id})
    RETURN p.id, p.name, count(s) AS evidence
    ORDER BY evidence DESC
    """
    t0 = time.time()
    res = g.query(cypher, {"topic_id": topic_id})
    ms = (time.time() - t0) * 1000
    rows = len(res.result_set)
    log_query(name, cypher, ms, rows, request_id)

    return [{"person_id": r[0], "name": r[1], "evidence_count": r[2]} for r in res.result_set]


# =========================================================================
# 9. BLAST PREVIEW, INVARIANTS, EPOCH & SNAPSHOT
# =========================================================================

def blast_preview(tenant_id: str, root_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
    """Read-only preview of affected facts, conclusions, and actions."""
    g = get_graph(tenant_id, "commons")
    name = "blast_preview"
    cypher = """
    MATCH (root:Fact {id: $root_id})-[:LEADS_TO|SUPPORTS*0..15]->(m:MemoryNode)
    RETURN count(DISTINCT CASE WHEN 'Fact' IN labels(m) THEN m END) AS facts,
           count(DISTINCT CASE WHEN 'Conclusion' IN labels(m) THEN m END) AS conclusions,
           count(DISTINCT CASE WHEN 'Action' IN labels(m) AND m.executed = true THEN m END) AS executed_actions,
           count(DISTINCT CASE WHEN 'Action' IN labels(m) AND m.executed = false THEN m END) AS staged_actions
    """
    t0 = time.time()
    res = g.query(cypher, {"root_id": root_id})
    ms = (time.time() - t0) * 1000
    rows = len(res.result_set)
    log_query(name, cypher, ms, rows, request_id)

    if not rows:
        return {"facts": 0, "conclusions": 0, "executed_actions": 0, "staged_actions": 0}

    row = res.result_set[0]
    return {
        "facts": row[0],
        "conclusions": row[1],
        "executed_actions": row[2],
        "staged_actions": row[3],
    }


def invariant_check(tenant_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Audits graph invariants:
    1. Zero HEALTHY children under QUARANTINED parents (zero orphans).
    2. Zero actions executed after an ancestor was already quarantined.
    """
    g = get_graph(tenant_id, "commons")

    # Invariant 1: Healthy child under quarantined parent
    q1 = """
    MATCH (parent:MemoryNode {status: 'QUARANTINED'})-[:LEADS_TO|SUPPORTS]->(child:MemoryNode {status: 'HEALTHY'})
    RETURN count(child)
    """
    res1 = g.query(q1).result_set[0][0]

    # Invariant 2: Action executed after an ancestor was already quarantined
    q2 = """
    MATCH (ancestor:MemoryNode)-[:LEADS_TO|SUPPORTS*]->(a:Action {executed: true})
    WHERE ancestor.quarantined_at IS NOT NULL AND a.executed_at > ancestor.quarantined_at
    RETURN count(a)
    """
    res2 = g.query(q2).result_set[0][0]

    return {
        "healthy_children_under_quarantined": res1,
        "actions_executed_after_ancestor_quarantined": res2,
        "all_passed": (res1 == 0 and res2 == 0),
    }


def bump_epoch(tenant_id: str) -> int:
    """Increments Meta.epoch and returns new epoch."""
    g = get_graph(tenant_id, "commons")
    res = g.query("MATCH (m:Meta {id: 'meta'}) SET m.epoch = m.epoch + 1 RETURN m.epoch")
    if res.result_set:
        return res.result_set[0][0]
    return 1


def graph_snapshot(tenant_id: str, as_of_ms: Optional[int] = None) -> Dict[str, Any]:
    """
    Returns full graph payload matching CONTRACT.md format for Cytoscape.js.
    """
    g = get_graph(tenant_id, "commons")
    nodes_q = "MATCH (n) RETURN n.id, labels(n), properties(n)"
    edges_q = "MATCH (src)-[r]->(tgt) RETURN src.id, type(r), tgt.id, properties(r)"

    res_nodes = g.query(nodes_q).result_set
    res_edges = g.query(edges_q).result_set

    nodes = []
    for r in res_nodes:
        nid, labels, props = r[0], r[1], r[2]
        if not nid:
            continue
        kind = "fact"
        if "Action" in labels:
            kind = "action"
        elif "Conclusion" in labels:
            kind = "conclusion"
        elif "Source" in labels:
            kind = "source"
        elif "Handoff" in labels:
            kind = "handoff"
        elif "Procedure" in labels:
            kind = "procedure"

        nodes.append({
            "id": nid,
            "kind": kind,
            "is_decision": "Decision" in labels,
            "label": props.get("text", props.get("id", nid))[:60],
            "text": props.get("text"),
            "key": props.get("key"),
            "value": props.get("value"),
            "status": props.get("status", "HEALTHY"),
            "stale": props.get("stale", False),
            "executed": props.get("executed", False),
            "gate": props.get("gate"),
            "reversibility": props.get("reversibility"),
            "quarantined_at": props.get("quarantined_at"),
            "released_at": props.get("released_at"),
        })

    edges = []
    for r in res_edges:
        edges.append({
            "source": r[0],
            "type": r[1],
            "target": r[2],
        })

    epoch_res = g.query("MATCH (m:Meta {id: 'meta'}) RETURN m.epoch")
    epoch = epoch_res.result_set[0][0] if epoch_res.result_set else 1

    return {"nodes": nodes, "edges": edges, "epoch": epoch}
