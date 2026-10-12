import time
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from app.models.common import Status, NodeKind, EdgeType, Tier, Reversibility, GateStatus, CompensationStatus
from app.models.graph import GraphNode, GraphEdge, GraphResponse


class CypherLogEntry(BaseModel):
    ts: int
    request_id: Optional[str] = None
    name: str
    cypher: str
    ms: float
    rows: int


class GraphStore:
    """
    In-memory graph store implementing the interface contract expected from Person 1 (graph/queries.py).
    Can be swapped or wired to live FalkorDB queries.
    """
    def __init__(self, tenant: str = "acme"):
        self.tenant = tenant
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self.epoch: int = 1
        self.query_log: List[CypherLogEntry] = []

    def log_query(self, name: str, cypher: str, ms: float, rows: int, request_id: Optional[str] = None):
        entry = CypherLogEntry(
            ts=int(time.time() * 1000),
            request_id=request_id,
            name=name,
            cypher=cypher,
            ms=ms,
            rows=rows,
        )
        self.query_log.append(entry)
        if len(self.query_log) > 200:
            self.query_log.pop(0)

    def bump_epoch(self, request_id: Optional[str] = None) -> int:
        start = time.time()
        self.epoch += 1
        self.log_query("bump_epoch", "MATCH (m:Meta) SET m.epoch = m.epoch + 1 RETURN m.epoch", (time.time() - start) * 1000, 1, request_id)
        return self.epoch

    def add_node(self, node: GraphNode, request_id: Optional[str] = None):
        start = time.time()
        self.nodes[node.id] = node
        self.log_query("add_node", f"CREATE (n:{node.kind.value.capitalize()} {{id:'{node.id}'}})", (time.time() - start) * 1000, 1, request_id)

    def add_edge(self, edge: GraphEdge, request_id: Optional[str] = None):
        start = time.time()
        self.edges.append(edge)
        self.log_query("add_edge", f"MATCH (a), (b) CREATE (a)-[:{edge.type.value}]->(b)", (time.time() - start) * 1000, 1, request_id)

    def get_ancestors(self, node_id: str, edge_types: List[str] = ["LEADS_TO", "SUPPORTS"]) -> List[GraphNode]:
        """Traverses backwards from node_id along incoming edges of given types."""
        visited = set()
        queue = [node_id]
        ancestors = []

        while queue:
            curr = queue.pop(0)
            incoming = [e for e in self.edges if e.target == curr and e.type.value in edge_types]
            for edge in incoming:
                parent_id = edge.source
                if parent_id not in visited and parent_id != node_id:
                    visited.add(parent_id)
                    parent = self.nodes.get(parent_id)
                    if parent:
                        ancestors.append(parent)
                        queue.append(parent_id)

        return ancestors

    def get_leaf_facts(self, node_id: str) -> List[GraphNode]:
        """Finds all leaf ancestor Facts (ancestor Facts that have no incoming LEADS_TO edges)."""
        start = time.time()
        ancestors = self.get_ancestors(node_id, edge_types=["LEADS_TO"])
        facts = [n for n in ancestors if n.kind == NodeKind.FACT]

        leaf_facts = []
        for fact in facts:
            has_incoming_leads_to = any(e for e in self.edges if e.target == fact.id and e.type == EdgeType.LEADS_TO)
            if not has_incoming_leads_to:
                leaf_facts.append(fact)

        self.log_query(
            "get_leaf_facts",
            "MATCH (leaf:Fact)-[:LEADS_TO*]->(a:Action {id:$id}) WHERE NOT (()-[:LEADS_TO]->(leaf)) RETURN DISTINCT leaf",
            (time.time() - start) * 1000,
            len(leaf_facts),
        )
        return leaf_facts

    def execute_guard(self, action_id: str, request_id: Optional[str] = None) -> bool:
        """
        Atomic execute guard statement:
        Ensures action is HEALTHY, executed=false, gate=PASSED, and 0 ancestors/supporters are non-healthy.
        """
        start = time.time()
        cypher = (
            "MATCH (a:Action {id:$id}) WHERE a.status='HEALTHY' AND a.executed=false AND a.gate='PASSED' "
            "OPTIONAL MATCH (x:MemoryNode)-[:LEADS_TO|SUPPORTS*]->(a) WHERE coalesce(x.status,'MISSING') <> 'HEALTHY' "
            "WITH a, count(DISTINCT x) AS bad WHERE bad = 0 "
            "SET a.executed = true, a.executed_at = timestamp(), a.confirmed = false RETURN a.id"
        )
        action = self.nodes.get(action_id)
        if not action or action.kind != NodeKind.ACTION:
            self.log_query("execute_guard", cypher, (time.time() - start) * 1000, 0, request_id)
            return False

        if action.status != Status.HEALTHY or not action.action:
            self.log_query("execute_guard", cypher, (time.time() - start) * 1000, 0, request_id)
            return False

        if action.action.executed or action.action.gate != GateStatus.PASSED:
            self.log_query("execute_guard", cypher, (time.time() - start) * 1000, 0, request_id)
            return False

        ancestors = self.get_ancestors(action_id, edge_types=["LEADS_TO", "SUPPORTS"])
        bad_ancestors = [x for x in ancestors if x.status != Status.HEALTHY]

        if bad_ancestors:
            self.log_query("execute_guard", cypher, (time.time() - start) * 1000, 0, request_id)
            return False

        # Atomic check-and-set succeeds
        action.action.executed = True
        action.action.confirmed = False
        self.log_query("execute_guard", cypher, (time.time() - start) * 1000, 1, request_id)
        return True

    def cascade_quarantine(self, root_id: str, request_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Quarantine cascade over LEADS_TO|SUPPORTS*.
        Returns list of {id, status, depth, root_id}.
        """
        start = time.time()
        cypher = (
            "MATCH (root:Fact {id:$root_id}) "
            "OPTIONAL MATCH (root)-[:LEADS_TO|SUPPORTS*]->(descendant) "
            "SET descendant.status='QUARANTINED', descendant.quarantined_at=timestamp(), descendant.quarantine_root=$root_id "
            "RETURN descendant, depth"
        )

        root = self.nodes.get(root_id)
        if not root:
            return []

        now_ms = int(time.time() * 1000)
        root.status = Status.QUARANTINED
        root.quarantined_at = now_ms
        root.quarantine_root = root_id
        root.depth = 0

        affected = [{"id": root.id, "status": Status.QUARANTINED, "depth": 0, "root_id": root_id}]

        # BFS for descendants to compute exact hop depth
        queue = [(root_id, 0)]
        visited = {root_id}

        while queue:
            curr_id, curr_depth = queue.pop(0)
            outgoing = [e for e in self.edges if e.source == curr_id and e.type.value in ["LEADS_TO", "SUPPORTS"]]
            for edge in outgoing:
                child_id = edge.target
                if child_id not in visited:
                    visited.add(child_id)
                    child = self.nodes.get(child_id)
                    if child:
                        child.status = Status.QUARANTINED
                        child.quarantined_at = now_ms
                        child.quarantine_root = root_id
                        child.depth = curr_depth + 1
                        affected.append({
                            "id": child.id,
                            "status": Status.QUARANTINED,
                            "depth": curr_depth + 1,
                            "root_id": root_id,
                        })
                        queue.append((child_id, curr_depth + 1))

        self.bump_epoch(request_id)
        self.log_query("cascade_quarantine", cypher, (time.time() - start) * 1000, len(affected), request_id)
        return affected


# Global store instance per tenant
_stores: Dict[str, GraphStore] = {}

def get_graph_store(tenant: str = "acme") -> GraphStore:
    if tenant not in _stores:
        _stores[tenant] = GraphStore(tenant)
    return _stores[tenant]
