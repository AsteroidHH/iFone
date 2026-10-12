"""
Write-through persistence of a tenant's graph into FalkorDB.

FalkorDB is the system of record. Each tenant has a graph named quorum:<tenant> holding:
  (:QNode:<Kind> {id, kind, label, status, stale, depth, valid_from, json})   the beliefs
  (a)-[:LEADS_TO|SUPPORTS|CONTRADICTS|SUPERSEDES|FROM_SOURCE {id}]->(b)       the causal links
  (:QHandoff {id, kind, status, json})                                        handoffs
  (:QMeta {id:'meta', epoch})                                                 the context epoch

Hot-path logic (cascade, guards, gate) still runs in the API process under locks, then `sync()` writes every change
that happened since the last sync. `load()` rebuilds the in-memory view from FalkorDB when a tenant is first used,
so a restart loses nothing. The Cypher shown in the console is the Cypher that actually ran.
"""
import hashlib
import re
import time
from typing import Any, Dict, List, Optional

from app import db
from app.models.graph import GraphEdge, GraphNode
from app.models.handoffs import Handoff

_SAFE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _label(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_]", "", s or "")
    return s if _SAFE.match(s) else "Other"


def _h(js: str) -> str:
    return hashlib.blake2b(js.encode("utf8"), digest_size=12).hexdigest()


class Persister:
    def __init__(self, store):
        self.store = store
        self.nodes: Dict[str, str] = {}
        self.edges: Dict[str, str] = {}
        self.handoffs: Dict[str, str] = {}
        self.epoch: Optional[int] = None

    @property
    def graph(self):
        return db.graph_for(self.store.tenant)

    def _q(self, name: str, cypher: str, params: Dict[str, Any], request_id: Optional[str] = None):
        t0 = time.time()
        res = self.graph.query(cypher, params)
        rows = len(res.result_set) if res.result_set else 0
        written = (res.nodes_created or 0) + (res.properties_set or 0) + (res.relationships_created or 0) + (res.nodes_deleted or 0)
        self.store.log_query(name, cypher.strip().replace("\n", " "), (time.time() - t0) * 1000, rows or written, request_id)
        return res

    def ensure_schema(self) -> None:
        g = self.graph
        for stmt in (
            "CREATE INDEX FOR (n:QNode) ON (n.id)",
            "CREATE INDEX FOR (n:QNode) ON (n.status)",
            "CREATE INDEX FOR (h:QHandoff) ON (h.id)",
            "CREATE INDEX FOR (m:QMeta) ON (m.id)",
        ):
            try:
                g.query(stmt)
            except Exception:
                pass  # already exists

    # ---------- load ----------
    def load(self) -> bool:
        """Rebuild the store from FalkorDB. Returns True if the tenant already had data."""
        self.ensure_schema()
        store = self.store
        nodes = self.graph.query("MATCH (n:QNode) RETURN n.json").result_set
        edges = self.graph.query("MATCH (:QNode)-[r]->(:QNode) WHERE r.id IS NOT NULL RETURN r.json").result_set
        hands = self.graph.query("MATCH (h:QHandoff) RETURN h.json").result_set
        meta = self.graph.query("MATCH (m:QMeta {id:'meta'}) RETURN m.epoch").result_set
        with store._lock:
            store.nodes.clear()
            store.edges.clear()
            store.handoffs.clear()
            for (js,) in nodes:
                n = GraphNode.model_validate_json(js)
                store.nodes[n.id] = n
                self.nodes[n.id] = _h(js)
            for (js,) in edges:
                e = GraphEdge.model_validate_json(js)
                store.edges.append(e)
                self.edges[e.id] = _h(js)
            for (js,) in hands:
                h = Handoff.model_validate_json(js)
                store.handoffs.append(h)
                self.handoffs[h.id] = _h(js)
            if meta and meta[0][0] is not None:
                store.epoch = int(meta[0][0])
                self.epoch = store.epoch
        return bool(nodes or edges or hands or meta)

    # ---------- sync ----------
    def sync(self, request_id: Optional[str] = None) -> int:
        """Writes everything that changed since the last sync. Returns the number of statements run."""
        store = self.store
        with store._lock:
            cur_nodes = {n.id: n.model_dump_json() for n in store.nodes.values()}
            cur_edges = {e.id: e.model_dump_json() for e in store.edges}
            cur_hands = {h.id: h.model_dump_json() for h in store.handoffs}
            epoch = store.epoch
            nodes_by_id = dict(store.nodes)
            edges_by_id = {e.id: e for e in store.edges}

        up_nodes = [i for i, js in cur_nodes.items() if self.nodes.get(i) != _h(js)]
        del_nodes = [i for i in self.nodes if i not in cur_nodes]
        up_edges = [i for i, js in cur_edges.items() if self.edges.get(i) != _h(js)]
        del_edges = [i for i in self.edges if i not in cur_edges]
        up_hands = [i for i, js in cur_hands.items() if self.handoffs.get(i) != _h(js)]
        del_hands = [i for i in self.handoffs if i not in cur_hands]
        epoch_changed = self.epoch != epoch
        if not (up_nodes or del_nodes or up_edges or del_edges or up_hands or del_hands or epoch_changed):
            return 0

        n_stmts = 0
        # Removed things first so a reset does not leave orphans behind.
        if del_edges:
            self._q("delete_edges", "UNWIND $ids AS id MATCH ()-[r {id:id}]->() DELETE r", {"ids": del_edges}, request_id)
            n_stmts += 1
        if del_nodes:
            self._q("delete_nodes", "UNWIND $ids AS id MATCH (n:QNode {id:id}) DETACH DELETE n", {"ids": del_nodes}, request_id)
            n_stmts += 1
        if del_hands:
            self._q("delete_handoffs", "UNWIND $ids AS id MATCH (h:QHandoff {id:id}) DELETE h", {"ids": del_hands}, request_id)
            n_stmts += 1

        by_kind: Dict[str, List[Dict[str, Any]]] = {}
        for i in up_nodes:
            n = nodes_by_id[i]
            by_kind.setdefault(_label(n.kind.value.capitalize()), []).append(
                {
                    "id": n.id,
                    "kind": n.kind.value,
                    "label": n.label,
                    "status": n.status.value,
                    "stale": bool(n.stale),
                    "depth": n.depth,
                    "valid_from": n.valid_from,
                    "json": cur_nodes[i],
                }
            )
        for kind, rows in by_kind.items():
            self._q(
                f"upsert_{kind.lower()}",
                f"UNWIND $rows AS row MERGE (n:QNode {{id: row.id}}) SET n:{kind}, n.kind = row.kind, n.label = row.label, "
                "n.status = row.status, n.stale = row.stale, n.depth = row.depth, n.valid_from = row.valid_from, n.json = row.json",
                {"rows": rows},
                request_id,
            )
            n_stmts += 1

        by_type: Dict[str, List[Dict[str, Any]]] = {}
        for i in up_edges:
            e = edges_by_id[i]
            by_type.setdefault(_label(e.type.value), []).append({"id": e.id, "s": e.source, "t": e.target, "json": cur_edges[i]})
        for typ, rows in by_type.items():
            self._q(
                f"upsert_{typ.lower()}_link",
                f"UNWIND $rows AS row MATCH (a:QNode {{id: row.s}}), (b:QNode {{id: row.t}}) "
                f"MERGE (a)-[r:{typ} {{id: row.id}}]->(b) SET r.json = row.json",
                {"rows": rows},
                request_id,
            )
            n_stmts += 1

        if up_hands:
            hs = {h.id: h for h in store.handoffs}
            rows = [{"id": i, "kind": hs[i].kind.value, "status": hs[i].status.value, "json": cur_hands[i]} for i in up_hands if i in hs]
            self._q(
                "upsert_handoffs",
                "UNWIND $rows AS row MERGE (h:QHandoff {id: row.id}) SET h.kind = row.kind, h.status = row.status, h.json = row.json",
                {"rows": rows},
                request_id,
            )
            n_stmts += 1

        if epoch_changed:
            self._q("save_epoch", "MERGE (m:QMeta {id:'meta'}) SET m.epoch = $e", {"e": epoch}, request_id)
            n_stmts += 1

        # Only now remember what is persisted, so a failed write is retried on the next sync.
        self.nodes = {i: _h(js) for i, js in cur_nodes.items()}
        self.edges = {i: _h(js) for i, js in cur_edges.items()}
        self.handoffs = {i: _h(js) for i, js in cur_hands.items()}
        self.epoch = epoch
        return n_stmts

    def wipe(self) -> None:
        """Delete this tenant's API graph entirely (used by tests and tenant reset)."""
        try:
            self.graph.delete()
        except Exception:
            pass
        self.nodes, self.edges, self.handoffs, self.epoch = {}, {}, {}, None
