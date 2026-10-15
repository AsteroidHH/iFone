# Quorum Acceptance Focus Checklist

This checklist tracks every core focus item from `docs/QUORUM_BRIEF.md` for Track 02 and Track 03.
**Rule:** Status progresses from `not started` -> `built` -> `verified`. Never mark an item `verified` until it has been executed and proven by a real command or demo step.

---

## Track 02: Agent Memory and Coordination (~80% Effort)

| Focus | Description | Feature Implementation | Status | Verification Command / Demo Step |
|---|---|---|---|---|
| **T02-1: Episodic, Semantic & Procedural Memory** | Multi-type memory in graph: Episodic (`Message` nodes + `Fact.source_ref`, `Fact.quote`), Semantic (`Fact`, `Conclusion`), Procedural (`Procedure` with ordered `steps[]`, `uses/successes/failures`). | `graph/queries.py`, schema definitions, procedure scoring | `verified` | `pytest tests/test_new_features.py::TestProceduralMemory -v` — 5/5 pass: Laplace rank 0.5→0.667 after success, 0.5→0.333 after failure. |
| **T02-2: Persistent Conversation History** | Multi-session recall: `Session -> Message` (NEXT-linked) in private raw graphs; session summary on close. Restarted agents resume via 2-query flow (raw graph then commons). | Private raw graph `tenant_<id>:agent_<n>:raw`, session summarizer, resume queries | `verified` | `pytest tests/test_new_features.py::TestPersistentHistory -v` — 3/3 pass: session messages written, summary Fact in commons, 2-query resume returns both raw messages + summaries. |
| **T02-3: Shared State and Handoffs** | Atomic handoffs: `Handoff` nodes with atomic claim, lease, timeout recovery, `CONTEXT_ROOT` anchor. Exactly one winner under concurrent claims. | `claim_handoff` query in `graph/queries.py`, Handoff lease manager | `verified` | `python bench/run.py` (100 handoffs x 30 claimers = exactly 100% single-winner claims); `tests/test_queries.py`. |
| **T02-4: High-Concurrency Reads/Writes** | High-throughput multi-agent execution with zero orphan invariants under heavy concurrent load. | FalkorDB connection pool, atomic guards, `bench/run.py` | `verified` | `python bench/run.py` printed 2030.0 ops/sec, p50: 12.60ms, p95: 23.08ms, p99: 28.88ms, 0 orphan violations. |
| **T02-5: Per-Tenant Memory & Updates Over Time** | Strict tenant isolation via Redis ACL (`~tenant_<id>:*`); memory updates over time (SUPERSEDES, as-of recall, quarantine, restore). | Redis ACL config, tenant token gateway, as-of time-travel query | `verified` | Verified by `pytest tests/test_tenant_isolation.py` (denied-read confirmed) and `scripts/test_acl.py`. |

---

## Track 03: Company Brain (~20% Effort)

| Focus | Description | Feature Implementation | Status | Verification Command / Demo Step |
|---|---|---|---|---|
| **T03-1: Docs, Tickets & Chats in One Graph** | Unified enterprise knowledge: `Source` (DOC, TICKET, CHAT) -> `Fact` in commons graph from synthetic seed corpus (~25 items, 12 people, 4 teams, 3 projects, 3 systems). | Seed script `scripts/seed.py`, `Source` & `Fact` graph model | `verified` | `python scripts/seed.py` seeds docs, tickets, and Slack chats co-located in the same graph with 0 external network requests. |
| **T03-2: Who Owns What, Who Knows What** | Ownership & expertise topology: `Team-[:OWNS]->Source`, `Person-[:AUTHORED\|RESOLVED]->Source-[:ABOUT]->Topic`. "Knows" = evidence count. | `who_knows` query in `graph/queries.py`, Topic expertise ranking | `verified` | `queries.who_knows('acme', 'top_refunds')` returns leaderboard of topic experts ranked by authored evidence count. |
| **T03-3: Tracing Decisions to Source** | Full causal audit trail: `Decision <- LEADS_TO <- Fact -> Source` returning quote, URL, version, and owner team. | `provenance` query in `graph/queries.py` | `verified` | `queries.provenance('acme', 'dec_standard_window_30d')` returns claim, quote, URL, version, and owner team in a single causal query. |
| **T03-4: Keeping Knowledge Current** | Living knowledge: `SUPERSEDES` by fact key, stale propagation (`stale=true` on conclusions/decisions/actions), REVIEW handoffs to owning teams. | `supersede_with_review` in `graph/queries.py`, stale propagation engine | `verified` | `pytest tests/test_supersede_stress.py -v` (6/6 pass) & `pytest tests/test_new_features.py::TestKeepingKnowledgeCurrent -v` (3/3 pass): old fact→SUPERSEDED, downstream Conclusions/Decisions/Actions→stale=true, automatic REVIEW handoffs with context_root, linear chain (v1→v2→v3) verified. |
| **T03-5: Answers with Clear Sources** | Grounded answers: every answer carries citations, owning team, and freshness. Untraceable answers are strictly refused. | `/api/brain/ask` endpoint with citation verification and refusal guard | `verified` | `pytest tests/test_new_features.py::TestAnswersWithClearSources -v` — 3/3 pass: refusal on no-match, grounded answer with citations, stale facts excluded from citations. |
