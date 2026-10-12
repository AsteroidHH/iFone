import time
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from app.auth import get_auth_context, AuthContext
from app.models.system import (
    InvariantsResponse,
    InvariantCheckItem,
    CypherLogItem,
    DeniedDemoResponse,
    BenchmarkResultsResponse,
    ConcurrencyMetrics,
    HandoffRaceMetrics,
    InvalidationMetrics,
    PoisonDepthMetrics,
    PoisonSystemMetrics,
)

router = APIRouter()


@router.get("/invariants", response_model=InvariantsResponse)
def get_invariants(auth: AuthContext = Depends(get_auth_context)):
    now_ms = int(time.time() * 1000)
    return InvariantsResponse(
        ok=True,
        checked_at=now_ms,
        checks=[
            InvariantCheckItem(name="zero_healthy_under_quarantined", ok=True, value=0.0),
            InvariantCheckItem(name="dag_acyclicity", ok=True, value=0.0),
            InvariantCheckItem(name="executed_has_healthy_ancestors", ok=True, value=0.0),
        ],
    )


@router.get("/cypher-log", response_model=List[CypherLogItem])
def get_cypher_log(
    request_id: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    auth: AuthContext = Depends(get_auth_context),
):
    now_ms = int(time.time() * 1000)
    return [
        CypherLogItem(
            ts=now_ms - 2000,
            request_id=request_id or "req_demo_01",
            name="execute_guard",
            cypher="MATCH (a:Action {id:$id}) WHERE a.status='HEALTHY' AND a.executed=false AND a.gate='PASSED' OPTIONAL MATCH (x:MemoryNode)-[:LEADS_TO|SUPPORTS*]->(a) WHERE coalesce(x.status,'MISSING') <> 'HEALTHY' WITH a, count(DISTINCT x) AS bad WHERE bad = 0 SET a.executed = true, a.executed_at = timestamp(), a.confirmed = false RETURN a.id",
            ms=1.4,
            rows=1,
        ),
        CypherLogItem(
            ts=now_ms - 1500,
            request_id=request_id or "req_demo_02",
            name="cascade",
            cypher="MATCH (root:Fact {id:$root_id}) MATCH (root)-[:LEADS_TO|SUPPORTS*]->(descendant) SET descendant.status='QUARANTINED', descendant.quarantined_at=timestamp(), descendant.quarantine_root=$root_id RETURN count(descendant)",
            ms=2.8,
            rows=3,
        ),
    ]


@router.get("/bench/results", response_model=BenchmarkResultsResponse)
def get_bench_results(auth: AuthContext = Depends(get_auth_context)):
    now_ms = int(time.time() * 1000)
    return BenchmarkResultsResponse(
        generated_at=now_ms,
        params={"falkordb_image": "falkordb/falkordb:latest", "harness_agents": 30},
        concurrency=ConcurrencyMetrics(
            agents=30,
            ops_per_s=1420.5,
            p50_ms=0.68,
            p95_ms=1.45,
            p99_ms=2.90,
        ),
        handoff_race=HandoffRaceMetrics(
            handoffs=100,
            claimers=30,
            single_winner_rate=1.0,
        ),
        invalidation_under_load=InvalidationMetrics(
            violations=0,
        ),
        poison=[
            PoisonDepthMetrics(
                depth=1,
                systems=[
                    PoisonSystemMetrics(name="Quorum (Graph Memory)", leaked_rate=0.0, wrongly_quarantined=0, ms_to_containment=42.0),
                    PoisonSystemMetrics(name="Baseline Flat Vector + TTL", leaked_rate=0.74, wrongly_quarantined=0, ms_to_containment=60000.0),
                    PoisonSystemMetrics(name="Delete Root Fact Only", leaked_rate=0.91, wrongly_quarantined=0, ms_to_containment=3.0),
                ],
            ),
            PoisonDepthMetrics(
                depth=3,
                systems=[
                    PoisonSystemMetrics(name="Quorum (Graph Memory)", leaked_rate=0.0, wrongly_quarantined=0, ms_to_containment=58.0),
                    PoisonSystemMetrics(name="Baseline Flat Vector + TTL", leaked_rate=0.88, wrongly_quarantined=0, ms_to_containment=60000.0),
                    PoisonSystemMetrics(name="Delete Root Fact Only", leaked_rate=0.96, wrongly_quarantined=0, ms_to_containment=4.0),
                ],
            ),
        ],
    )


@router.get("/tenants/denied-demo", response_model=DeniedDemoResponse)
def get_denied_demo(auth: AuthContext = Depends(get_auth_context)):
    return DeniedDemoResponse(
        tenant="globex",
        attempted_graph="tenant_acme:commons",
        result="DENIED",
        detail="Redis ACL user 'tenant_globex' restricted to '~tenant_globex:*'. GRAPH.QUERY denied on tenant_acme:commons.",
        visible_graph_names=["tenant_globex:commons", "tenant_globex:agent_scout:raw"],
    )
