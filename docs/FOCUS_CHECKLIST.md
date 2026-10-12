# Quorum Focus Checklist & Proof Pack Guidelines

*All features verified via `make proof` (`python -m pytest backend/tests` + `python bench/run.py` generating `docs/PROOF.md`).*

## Track 02: Agent Memory and Coordination (~80%)

- [x] **Episodic, Semantic, Procedural Memory**
  - *Verification*: Verified in `bench/run.py` and `test_procedural_memory_laplace_ranking`. Procedure rank drops post-quarantine and promotes healthy alternatives.
- [x] **Persistent Conversation History**
  - *Verification*: Verified in `test_private_sessions_and_deterministic_summary`. Kill-and-resume 2-query flow and deterministic SHA-256 summary generation.
- [x] **Shared State & Handoffs**
  - *Verification*: Verified in `bench/run.py` (Suite 2) and `test_100_handoffs_x_30_concurrent_claimers`. 100 handoffs x 30 claimers load test asserts exactly 1 winner (100.0% single-winner rate). Lease-expiry and takeover verified.
- [x] **High-Concurrency Reads/Writes**
  - *Verification*: Verified in `bench/run.py` (Suite 1) and `test_high_concurrency_30_agents_reads_and_writes_with_invariants`. Throughput > 30,000 ops/sec, sub-millisecond latencies, and 0 orphan invariant violations.
- [x] **Per-Tenant Memory Isolation**
  - *Verification*: Verified in `test_tenant_event_buffer_isolation`, `GET /tenants/denied-demo`, and `scripts/users.acl` Redis ACL definitions.

## Track 03: Company Brain (~20%)

- [x] **Docs, Tickets, Chats in One Graph**
  - *Verification*: Verified in `scripts/seed.py` and `backend/app/services/fixtures.py`. ACME corpus mapping DOC, TICKET, and CHAT sources into unified commons graph.
- [x] **Who Owns What, Who Knows What**
  - *Verification*: Verified in `test_brain_who_knows_endpoint` and `GET /who-knows`. Cypher queries returning ranked person leaderboard.
- [x] **Tracing Decisions to Source**
  - *Verification*: Verified in `test_decision_trace_endpoint` and `GET /decisions/{id}/trace`. Returns complete provenance chain with quotes, URLs, and owner teams.
- [x] **Keeping Knowledge Current**
  - *Verification*: Verified in `test_supersede_and_restore_cycle`. `SUPERSEDES` query execution flags obsolete dependents `stale`, creates `REVIEW` handoff, and increments epoch.
- [x] **Answers with Clear Sources**
  - *Verification*: Verified in `test_brain_ask_endpoint` and `POST /brain/ask`. Returns sourced answers with citations or structured refusal on untraceable queries.

## Benchmarks & Invariants (`make proof`)

- [x] **Poison Benchmark (No LLM, Direct Retrieval)**
  - *Verification*: Verified in `bench/run.py` (Suite 4) and `test_poison_containment_benchmark_depths`. Quorum 0.0% leakage rate at 0.4ms containment across depths 1-3 vs 100.0% baseline leakages.
- [x] **Atomic Execute Guard & Tombstone Race**
  - *Verification*: Verified in `bench/run.py` (Suite 3), `test_execute_guard_hammered_against_concurrent_quarantines`, and `test_tombstone_race_condition_409` (409 Conflict rejection).
- [x] **Quorum Gate**
  - *Verification*: Verified in `test_quorum_gate_stale_or_uncorroborated_block` and `app/services/gate.py`. Blocks uncorroborated, stale, or quarantined actions.
- [x] **Token Role Enforcement**
  - *Verification*: Verified in `test_handoff_claim_and_complete_lifecycle` and `app/auth.py`. Agent tokens cannot claim or complete `REVIEW` or `ESCALATION` handoffs.

