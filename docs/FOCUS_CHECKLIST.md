# Quorum Acceptance Focus Checklist

This checklist tracks every core focus item from `docs/QUORUM_BRIEF.md` for Track 02 and Track 03.
**Rule:** Status progresses from `not started` -> `built` -> `verified`. Never mark an item `verified` until it has been executed and proven by a real command or demo step.

---

## Track 02: Agent Memory and Coordination (~80% Effort)

| Focus | Description | Feature Implementation | Status | Verification Command / Demo Step |
|---|---|---|---|---|
| **T02-1: Episodic, Semantic & Procedural Memory** | Multi-type memory in graph: Episodic (`Message` nodes + `Fact.source_ref`, `Fact.quote`), Semantic (`Fact`, `Conclusion`), Procedural (`Procedure` with ordered `steps[]`, `uses/successes/failures`). | `graph/queries.py`, schema definitions, procedure scoring | `not started` | Demo: Procedure selection changing between two runs based on success/failure score updates. |
| **T02-2: Persistent Conversation History** | Multi-session recall: `Session -> Message` (NEXT-linked) in private raw graphs; session summary on close. Restarted agents resume via 2-query flow (raw graph then commons). | Private raw graph `tenant_<id>:agent_<n>:raw`, session summarizer, resume queries | `not started` | Demo: Agent restart beat showing persistent recall and attribution ("where each belief came from"). |
| **T02-3: Shared State and Handoffs** | Atomic handoffs: `Handoff` nodes with atomic claim, lease, timeout recovery, `CONTEXT_ROOT` anchor. Exactly one winner under concurrent claims. | `claim_handoff` query in `graph/queries.py`, Handoff lease manager | `not started` | Demo: Two agents visibly race for a claim; `make proof` (100 handoffs x 30 claimers = exactly 1 winner each). |
| **T02-4: High-Concurrency Reads/Writes** | High-throughput multi-agent execution with zero orphan invariants under heavy concurrent load. | FalkorDB connection pool, atomic guards, `bench/run.py` | `not started` | `make proof` / `python bench/run.py` prints real throughput, p50/p95/p99 latencies, and 0 orphan violations. |
| **T02-5: Per-Tenant Memory & Updates Over Time** | Strict tenant isolation via Redis ACL (`~tenant_<id>:*`); memory updates over time (SUPERSEDES, as-of recall, quarantine, restore). | Redis ACL config, tenant token gateway, as-of time-travel query | `not started` | Demo & test: Live denied-read test with `globex` tenant; `pytest tests/test_tenant_isolation.py`. |

---

## Track 03: Company Brain (~20% Effort)

| Focus | Description | Feature Implementation | Status | Verification Command / Demo Step |
|---|---|---|---|---|
| **T03-1: Docs, Tickets & Chats in One Graph** | Unified enterprise knowledge: `Source` (DOC, TICKET, CHAT) -> `Fact` in commons graph from synthetic seed corpus (~25 items, 12 people, 4 teams, 3 projects, 3 systems). | Seed script `scripts/seed.py`, `Source` & `Fact` graph model | `not started` | Brain view: Visualizing documents, tickets, and Slack chats co-located in the same graph. |
| **T03-2: Who Owns What, Who Knows What** | Ownership & expertise topology: `Team-[:OWNS]->Source`, `Person-[:AUTHORED\|RESOLVED]->Source-[:ABOUT]->Topic`. "Knows" = evidence count. | `who_knows` query in `graph/queries.py`, Topic expertise ranking | `not started` | Query / UI: Leaderboard of topic experts ranked by authored/resolved evidence count. |
| **T03-3: Tracing Decisions to Source** | Full causal audit trail: `Decision <- LEADS_TO <- Fact -> Source` returning quote, URL, version, and owner team. | `provenance` query in `graph/queries.py` | `not started` | UI Decision trace drawer: Single-click provenance inspection from any decision back to source quote and URL. |
| **T03-4: Keeping Knowledge Current** | Living knowledge: `SUPERSEDES` by fact key, stale propagation (`stale=true` on conclusions/decisions), REVIEW handoffs to owning teams. | `supersede` query in `graph/queries.py`, stale propagation engine | `not started` | Demo Step 4: Policy change (30 -> 45 days) flags downstream decisions stale and queues review handoffs. |
| **T03-5: Answers with Clear Sources** | Grounded answers: every answer carries citations, owning team, and freshness. Untraceable answers are strictly refused. | `/api/brain/ask` endpoint with citation verification and refusal guard | `not started` | API & UI test: Valid query returns cited answer with owner team; ungrounded query triggers refusal response. |
