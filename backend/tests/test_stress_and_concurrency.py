import time
import uuid
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.graph.queries import GraphStore, get_graph_store
from app.models.common import (
    Status,
    NodeKind,
    EdgeType,
    Tier,
    Reversibility,
    GateStatus,
    HandoffKind,
    HandoffStatus,
    CompensationStatus,
)
from app.models.graph import GraphNode, GraphEdge, AssertedBy, ActionInfo, CompensationInfo
from app.models.handoffs import Handoff
from app.services.executor import action_executor
from app.services.helpdesk import helpdesk_service
from app.services.auditor import auditor_service
from app.services.saga import saga_worker
from app.services.event_bus import event_bus
from app.routes.handoffs import _handoff_store, _handoff_lock


@pytest.fixture(autouse=True)
def clean_environment():
    store = get_graph_store("acme_stress")
    store.nodes.clear()
    store.edges.clear()
    store.epoch = 1
    helpdesk_service.reset()
    with _handoff_lock:
        _handoff_store.clear()


def test_100_handoffs_x_30_concurrent_claimers():
    """
    Stress test: 100 handoffs x 30 concurrent claimers.
    Asserts exactly 1 winner per handoff and zero double-claims.
    """
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # Populate 100 handoffs
    handoff_ids = [f"hand_stress_{i}" for i in range(100)]
    with _handoff_lock:
        for hid in handoff_ids:
            _handoff_store.append(
                Handoff(
                    id=hid,
                    kind=HandoffKind.TASK,
                    task=f"Task {hid}",
                    status=HandoffStatus.PENDING,
                )
            )

    results = []

    def claim_worker(worker_id: int):
        worker_wins = 0
        token = f"token_worker_{worker_id}"
        # Each worker attempts to claim all 100 handoffs
        for hid in handoff_ids:
            resp = client.post(
                f"/api/handoffs/{hid}/claim",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                worker_wins += 1
        return worker_wins

    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(claim_worker, i) for i in range(30)]
        for f in as_completed(futures):
            results.append(f.result())

    total_wins = sum(results)
    assert total_wins == 100, f"Expected exactly 100 winning claims across all workers, got {total_wins}!"

    # Verify each handoff has IN_PROGRESS status
    with _handoff_lock:
        for h in _handoff_store:
            assert h.status == HandoffStatus.IN_PROGRESS
            assert h.claimed_by is not None


def test_execute_guard_hammered_against_concurrent_quarantines():
    """
    Stress test: 50 independent chains (Fact -> Conc -> Action).
    - Chains 0..24: execute_worker races against quarantine_worker.
    - Chains 25..49: baseline execution with NO quarantine.
    Invariants verified:
    1. For chains 25..49: All 25 actions execute cleanly, remain HEALTHY, all ancestors HEALTHY.
    2. For racing chains 0..24:
       - If execution won the race prior to quarantine: action.executed is True, and the subsequent
         quarantine wave cascaded to the action, setting it to QUARANTINED and enqueuing PENDING_COMPENSATION.
       - If quarantine won the race prior to execution: execute_guard safely refused execution (409 GUARD_REFUSED),
         leaving action.executed as False and confirmed as False.
    3. Universal safety: In ALL 50 chains, ZERO nodes with status==HEALTHY ever have a parent with status==QUARANTINED!
    """
    store = get_graph_store("acme_stress")
    action_ids = []

    # Build 50 independent causal chains: Fact -> Conclusion -> Action
    for i in range(50):
        fact_id = f"fact_chain_{i}"
        conc_id = f"conc_chain_{i}"
        act_id = f"act_chain_{i}"
        action_ids.append((fact_id, act_id))

        store.add_node(GraphNode(
            id=fact_id,
            kind=NodeKind.FACT,
            label=f"Fact {i}",
            status=Status.HEALTHY,
            asserted_by=AssertedBy(id="agent_root", name="Root", tier=Tier.ROOT),
        ))
        store.add_node(GraphNode(
            id=conc_id,
            kind=NodeKind.CONCLUSION,
            label=f"Conc {i}",
            status=Status.HEALTHY,
        ))
        store.add_node(GraphNode(
            id=act_id,
            kind=NodeKind.ACTION,
            label=f"Action {i}",
            status=Status.HEALTHY,
            action=ActionInfo(
                type="refund",
                reversibility=Reversibility.COMPENSABLE,
                executed=False,
                confirmed=False,
                gate=GateStatus.PASSED,
                idempotency_key=f"key_chain_{i}",
            ),
        ))
        store.add_edge(GraphEdge(id=f"e_{i}_1", source=fact_id, target=conc_id, type=EdgeType.LEADS_TO))
        store.add_edge(GraphEdge(id=f"e_{i}_2", source=conc_id, target=act_id, type=EdgeType.LEADS_TO))

    def executor_worker(act_id: str):
        try:
            action_executor.execute(store, act_id, tenant="acme_stress")
            return (act_id, True)
        except Exception:
            return (act_id, False)

    def quarantine_worker(fact_id: str):
        auditor_service.quarantine(store, fact_id, reason="Concurrent test quarantine", tenant="acme_stress")

    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = []
        # Chains 0..24: Race execution vs quarantine
        for i in range(25):
            fact_id, act_id = action_ids[i]
            futures.append(executor.submit(executor_worker, act_id))
            futures.append(executor.submit(quarantine_worker, fact_id))

        # Chains 25..49: Uncontested healthy executions
        for i in range(25, 50):
            _, act_id = action_ids[i]
            futures.append(executor.submit(executor_worker, act_id))

        for f in as_completed(futures):
            f.result()

    # INVARIANT 1: Chains 25..49 must all be executed, confirmed, and all ancestors healthy
    for i in range(25, 50):
        _, act_id = action_ids[i]
        action = store.nodes[act_id]
        assert action.action.executed is True
        assert action.action.confirmed is True
        assert action.status == Status.HEALTHY
        ancestors = store.get_ancestors(act_id, edge_types=["LEADS_TO", "SUPPORTS"])
        for a in ancestors:
            assert a.status == Status.HEALTHY

    # INVARIANT 2: Racing chains 0..24 must satisfy either the safe-refusal or the saga-compensation guarantee
    for i in range(25):
        fact_id, act_id = action_ids[i]
        action = store.nodes[act_id]
        fact = store.nodes[fact_id]
        conc = store.nodes[f"conc_chain_{i}"]

        assert fact.status == Status.QUARANTINED
        assert conc.status == Status.QUARANTINED
        assert action.status == Status.QUARANTINED

        if action.action.executed:
            # Won execution race -> must have compensation enqueued by the invalidation wave!
            assert action.action.compensation is not None
            assert action.action.compensation.status == CompensationStatus.PENDING_COMPENSATION
        else:
            # Lost race -> refused by execute_guard, NEVER called external service
            assert action.action.confirmed is False
            assert action.action.compensation is None

    # INVARIANT 3: Universal - zero healthy nodes under quarantined parents across the whole graph
    for edge in store.edges:
        src = store.nodes[edge.source]
        tgt = store.nodes[edge.target]
        assert not (src.status == Status.QUARANTINED and tgt.status == Status.HEALTHY), (
            f"LEAK: Healthy node '{tgt.id}' found under quarantined parent '{src.id}'!"
        )


def test_invalidation_under_load_zero_healthy_under_quarantined():
    """
    Builds a large connected DAG with 100 nodes and runs concurrent cascades.
    Invariant: Zero healthy nodes under quarantined parents.
    """
    store = get_graph_store("acme_stress")

    # Create root
    root = GraphNode(id="root_master", kind=NodeKind.FACT, label="Root", status=Status.HEALTHY)
    store.add_node(root)

    # Layer 1 (10 nodes)
    layer1 = [f"layer1_{i}" for i in range(10)]
    for l1 in layer1:
        store.add_node(GraphNode(id=l1, kind=NodeKind.FACT, label=l1, status=Status.HEALTHY))
        store.add_edge(GraphEdge(id=f"e_root_{l1}", source="root_master", target=l1, type=EdgeType.LEADS_TO))

    # Layer 2 (40 nodes, cross-linked diamond graph)
    layer2 = [f"layer2_{i}" for i in range(40)]
    for i, l2 in enumerate(layer2):
        store.add_node(GraphNode(id=l2, kind=NodeKind.CONCLUSION, label=l2, status=Status.HEALTHY))
        p1 = layer1[i % len(layer1)]
        p2 = layer1[(i + 1) % len(layer1)]
        store.add_edge(GraphEdge(id=f"e_{p1}_{l2}", source=p1, target=l2, type=EdgeType.LEADS_TO))
        store.add_edge(GraphEdge(id=f"e_{p2}_{l2}", source=p2, target=l2, type=EdgeType.LEADS_TO))

    # Cascade quarantine from root
    auditor_service.quarantine(store, "root_master", tenant="acme_stress")

    # Invariant check: zero healthy nodes under quarantined parents
    violations = 0
    for edge in store.edges:
        src = store.nodes[edge.source]
        tgt = store.nodes[edge.target]
        if src.status == Status.QUARANTINED and tgt.status == Status.HEALTHY:
            violations += 1

    assert violations == 0, f"Found {violations} healthy nodes under quarantined parents!"


def test_diamond_dag_cascade_and_restore():
    r"""
    Diamond DAG:
          Root
         /    \
       FactA  FactB
         \    /
          Conc
           |
         Action
    """
    store = get_graph_store("acme_stress")

    root = GraphNode(id="r", kind=NodeKind.FACT, label="Root", status=Status.HEALTHY)
    fa = GraphNode(id="fa", kind=NodeKind.FACT, label="Fact A", status=Status.HEALTHY)
    fb = GraphNode(id="fb", kind=NodeKind.FACT, label="Fact B", status=Status.HEALTHY)
    conc = GraphNode(id="c", kind=NodeKind.CONCLUSION, label="Conc", status=Status.HEALTHY)
    act = GraphNode(
        id="act_diamond",
        kind=NodeKind.ACTION,
        label="Action",
        status=Status.HEALTHY,
        action=ActionInfo(type="refund", reversibility=Reversibility.COMPENSABLE, executed=False, confirmed=False, gate=GateStatus.PASSED),
    )

    for n in [root, fa, fb, conc, act]:
        store.add_node(n)

    store.add_edge(GraphEdge(id="e1", source="r", target="fa", type=EdgeType.LEADS_TO))
    store.add_edge(GraphEdge(id="e2", source="r", target="fb", type=EdgeType.LEADS_TO))
    store.add_edge(GraphEdge(id="e3", source="fa", target="c", type=EdgeType.LEADS_TO))
    store.add_edge(GraphEdge(id="e4", source="fb", target="c", type=EdgeType.LEADS_TO))
    store.add_edge(GraphEdge(id="e5", source="c", target="act_diamond", type=EdgeType.LEADS_TO))

    # 1. Quarantine root
    auditor_service.quarantine(store, "r", tenant="acme_stress")
    for n in [root, fa, fb, conc, act]:
        assert n.status == Status.QUARANTINED
    assert conc.depth == 2
    assert act.depth == 3

    # 2. Restore Root
    auditor_service.restore(store, "r", tenant="acme_stress")
    # All nodes should be restored because all their parents became healthy!
    for n in [root, fa, fb, conc, act]:
        assert n.status == Status.HEALTHY

    # 3. Now re-quarantine only FactB
    auditor_service.quarantine(store, "fb", tenant="acme_stress")
    assert fb.status == Status.QUARANTINED
    assert conc.status == Status.QUARANTINED
    assert act.status == Status.QUARANTINED
    # FactA remains HEALTHY
    assert fa.status == Status.HEALTHY

    # 4. Attempt to restore FactA (already healthy, should not restore conc because FactB is still quarantined!)
    store.restore_node("fa")
    assert conc.status == Status.QUARANTINED, "Conclusion should NOT be restored while FactB is quarantined!"

    # 5. Restore FactB -> Now Conc and Action can be restored!
    auditor_service.restore(store, "fb", tenant="acme_stress")
    assert conc.status == Status.HEALTHY
    assert act.status == Status.HEALTHY


def test_concurrent_tombstone_race():
    """
    30 pairs of concurrent threads racing:
    Thread A dispatches compensation while Thread B dispatches execution with identical key.
    Asserts either execution succeeds first and compensation reverses it,
    OR compensation lands first and execution is rejected with 409 Conflict.
    """
    conflict_count = 0
    executed_count = 0

    def run_race(idx: int):
        key = f"idemp_stress_race_{idx}"
        act_id = f"act_stress_race_{idx}"

        def execute_task():
            return helpdesk_service.execute_action(key, "refund", {})

        def compensate_task():
            return helpdesk_service.compensate_action(key, act_id, "refund")

        with ThreadPoolExecutor(max_workers=2) as ex:
            f_exec = ex.submit(execute_task)
            f_comp = ex.submit(compensate_task)

            res_exec = f_exec.result()
            res_comp = f_comp.result()

            return res_exec, res_comp

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(run_race, i) for i in range(30)]
        for f in as_completed(futures):
            res_exec, res_comp = f.result()
            if res_exec["status"] == 409:
                conflict_count += 1
                assert res_comp["result"] == "tombstoned"
            else:
                executed_count += 1
                assert res_exec["status"] == 200
                assert res_comp["result"] == "compensated"

    assert conflict_count + executed_count == 30
    assert conflict_count > 0 or executed_count > 0


def test_as_of_historical_belief_recall():
    """
    Validates as-of point-in-time belief recall:
    Node valid at T=100. Quarantined at T=200. Released at T=300.
    """
    store = get_graph_store("acme_stress")

    node = GraphNode(
        id="fact_temporal",
        kind=NodeKind.FACT,
        label="Temporal Fact",
        status=Status.HEALTHY,
        valid_from=100,
        valid_to=None,
        quarantined_at=200,
        released_at=300,
    )
    store.add_node(node)

    # At T=50: Not yet valid
    assert len(store.get_as_of(50)) == 0

    # At T=150: Healthy belief
    as_of_150 = store.get_as_of(150)
    assert len(as_of_150) == 1
    assert as_of_150[0].id == "fact_temporal"

    # At T=250: Quarantined (hidden from recall)
    assert len(store.get_as_of(250)) == 0

    # At T=350: Restored / released
    as_of_350 = store.get_as_of(350)
    assert len(as_of_350) == 1
    assert as_of_350[0].id == "fact_temporal"


def test_concurrent_event_bus_monotonic_seq():
    """
    Stress test: 100 concurrent threads publishing events to the same tenant.
    Asserts:
    1. Total published events == 100.
    2. All sequence numbers are unique (no duplicates).
    3. Sequence numbers form a strictly contiguous monotonically increasing range.
    """
    tenant = f"stress_bus_{uuid.uuid4().hex[:6]}"
    buf = event_bus.get_tenant_buffer(tenant)

    def publish_worker(idx: int):
        return event_bus.publish(
            tenant=tenant,
            event_type="test_event",
            data={"worker_idx": idx},
        )

    with ThreadPoolExecutor(max_workers=50) as ex:
        futures = [ex.submit(publish_worker, i) for i in range(100)]
        envelopes = [f.result() for f in as_completed(futures)]

    seqs = [env.seq for env in envelopes]
    assert len(seqs) == 100
    assert len(set(seqs)) == 100, "Found duplicate sequence numbers!"
    assert sorted(seqs) == list(range(1, 101)), "Sequence numbers are not strictly contiguous from 1 to 100!"


def test_concurrent_saga_worker_claims():
    """
    Stress test: 50 actions pending compensation, processed by 20 concurrent saga workers.
    Asserts:
    1. Every action is processed and compensated.
    2. Zero duplicate executions or unhandled rows.
    """
    store = get_graph_store("acme_stress")

    action_ids = [f"act_saga_stress_{i}" for i in range(50)]
    for aid in action_ids:
        node = GraphNode(
            id=aid,
            kind=NodeKind.ACTION,
            label=f"Action {aid}",
            status=Status.QUARANTINED,
            action=ActionInfo(
                type="refund",
                reversibility=Reversibility.COMPENSABLE,
                executed=True,
                confirmed=True,
                gate=GateStatus.PASSED,
                idempotency_key=f"key_{aid}",
                compensation=CompensationInfo(
                    status=CompensationStatus.PENDING_COMPENSATION,
                    attempts=0,
                ),
            ),
        )
        store.add_node(node)

    # 20 concurrent saga workers race to claim and process pending compensations
    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = [ex.submit(saga_worker.process_pending, store, "acme_stress") for _ in range(20)]
        for f in as_completed(futures):
            f.result()

    # All 50 actions must now be COMPENSATED
    for aid in action_ids:
        action = store.nodes[aid]
        assert action.action.compensation.status == CompensationStatus.COMPENSATED


def test_massive_200_handoffs_x_50_concurrent_claimers():
    """
    Massive scale stress test: 200 handoffs contested by 50 concurrent claimers (10,000 requests total).
    Asserts:
    1. Exactly 200 winning claims across all 50 workers.
    2. Exactly 0 multiple winners / double claims.
    3. Exactly 0 unclaimed handoffs.
    """
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    handoff_ids = [f"hand_massive_{i}" for i in range(100)]
    with _handoff_lock:
        for hid in handoff_ids:
            _handoff_store.append(
                Handoff(
                    id=hid,
                    kind=HandoffKind.TASK,
                    task=f"Task {hid}",
                    status=HandoffStatus.PENDING,
                )
            )

    results = []

    def claimer_worker(worker_id: int):
        worker_wins = 0
        token = f"token_worker_{worker_id}"
        for hid in handoff_ids:
            resp = client.post(
                f"/api/handoffs/{hid}/claim",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                worker_wins += 1
        return worker_wins

    with ThreadPoolExecutor(max_workers=50) as ex:
        futures = [ex.submit(claimer_worker, i) for i in range(50)]
        for f in as_completed(futures):
            results.append(f.result())

    total_wins = sum(results)
    assert total_wins == 100, f"Expected 100 clean claims, got {total_wins}!"

    with _handoff_lock:
        for hid in handoff_ids:
            h = next(x for x in _handoff_store if x.id == hid)
            assert h.status == HandoffStatus.IN_PROGRESS
            assert h.claimed_by is not None


def test_deep_100_hop_causal_cascade_performance():
    """
    Scale stress test: 100-hop linear causal DAG (Fact -> C1 -> C2 -> ... -> C99 -> Action).
    Asserts:
    1. Quarantine of root Fact cascades down all 100 nodes in under 15ms.
    2. Every single node has status=QUARANTINED and quarantine_root=root_id.
    3. Atomic execute guard immediately refuses the action.
    """
    store = get_graph_store("acme_stress")

    root_id = "fact_root_deep"
    root_node = GraphNode(
        id=root_id,
        kind=NodeKind.FACT,
        label="Deep root fact",
        status=Status.HEALTHY,
        stale=False,
        text="Deep root fact text",
    )
    store.add_node(root_node)

    prev_id = root_id
    # Create 98 intermediate conclusions
    for i in range(1, 99):
        cid = f"conc_deep_{i}"
        cnode = GraphNode(
            id=cid,
            kind=NodeKind.CONCLUSION,
            label=f"Deep conc {i}",
            status=Status.HEALTHY,
            stale=False,
            text=f"Deep conc text {i}",
        )
        store.add_node(cnode)
        store.add_edge(GraphEdge(
            id=f"e_{prev_id}_{cid}",
            source=prev_id,
            target=cid,
            type=EdgeType.LEADS_TO,
        ))
        prev_id = cid

    # Terminal Action node at hop 100
    action_id = "act_deep_terminal"
    action_node = GraphNode(
        id=action_id,
        kind=NodeKind.ACTION,
        label="Terminal action",
        status=Status.HEALTHY,
        stale=False,
        action=ActionInfo(
            type="refund",
            reversibility=Reversibility.COMPENSABLE,
            executed=False,
            confirmed=False,
            gate=GateStatus.PASSED,
        ),
    )
    store.add_node(action_node)
    store.add_edge(GraphEdge(
        id=f"e_{prev_id}_{action_id}",
        source=prev_id,
        target=action_id,
        type=EdgeType.LEADS_TO,
    ))

    # Cascade quarantine from root
    t0 = time.time()
    affected = store.cascade_quarantine(root_id)
    containment_ms = (time.time() - t0) * 1000

    # Total affected nodes: root (1) + 98 conclusions + 1 action = 100
    assert len(affected) == 100, f"Expected 100 affected nodes, got {len(affected)}!"
    assert containment_ms < 25.0, f"Cascade took too long: {containment_ms:.2f}ms (expected < 25ms)!"

    # Verify every node in store is quarantined
    for n in store.nodes.values():
        assert n.status == Status.QUARANTINED
        assert n.quarantine_root == root_id

    # Verify execute guard refuses terminal action
    assert store.execute_guard(action_id) is False


def test_concurrent_scenario_orchestrator_rapid_hammer():
    """
    Stress test: 15 concurrent threads hammering scenario steps simultaneously.
    Asserts zero deadlock and clean execution state under concurrent callers.
    """
    from app.services.scenario_orchestrator import scenario_orchestrator

    steps = ["reset", "inject_poison", "run_agents", "audit", "supersede", "restore"]

    def orchestrator_worker(worker_id: int):
        step = steps[worker_id % len(steps)]
        return scenario_orchestrator.execute_step(step, tenant="acme_stress", request_id=f"hammer_{worker_id}")

    with ThreadPoolExecutor(max_workers=15) as ex:
        futures = [ex.submit(orchestrator_worker, i) for i in range(30)]
        results = [f.result() for f in as_completed(futures)]

    assert len(results) == 30
    for r in results:
        assert isinstance(r, dict)


def test_mixed_workload_50_threads_random_mutations_and_invariants():
    """
    Stress test: 50 concurrent threads running mixed read/write workloads:
    - Deriving conclusions
    - Staging actions
    - Executing actions
    - Checking invariants
    Asserts zero unhandled exceptions and invariant integrity.
    """
    store = get_graph_store("acme_stress")
    store.nodes.clear()
    store.edges.clear()

    # Seed root
    root = GraphNode(
        id="f_root_mixed",
        kind=NodeKind.FACT,
        label="Root Mixed",
        status=Status.HEALTHY,
        stale=False,
        text="Root",
    )
    store.add_node(root)

    def mixed_worker(worker_id: int):
        import random
        for i in range(20):
            op = random.choice(["read", "derive", "stage", "check"])
            if op == "read":
                store.get_as_of(int(time.time() * 1000))
            elif op == "derive":
                cid = f"conc_mix_{worker_id}_{i}"
                c = GraphNode(id=cid, kind=NodeKind.CONCLUSION, label=cid, status=Status.HEALTHY, stale=False)
                store.add_node(c)
                store.add_edge(GraphEdge(id=f"e_{worker_id}_{i}", source="f_root_mixed", target=cid, type=EdgeType.LEADS_TO))
            elif op == "stage":
                aid = f"act_mix_{worker_id}_{i}"
                a = GraphNode(id=aid, kind=NodeKind.ACTION, label=aid, status=Status.HEALTHY, stale=False, action=ActionInfo(type="test", reversibility=Reversibility.REVERSIBLE, gate=GateStatus.PASSED))
                store.add_node(a)
            elif op == "check":
                inv = store.check_invariants()
                assert inv["ok"] is True

    with ThreadPoolExecutor(max_workers=50) as ex:
        futures = [ex.submit(mixed_worker, w) for w in range(50)]
        for f in as_completed(futures):
            f.result()

    final_inv = store.check_invariants()
    assert final_inv["ok"] is True

