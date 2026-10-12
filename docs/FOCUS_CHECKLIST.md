# Quorum Acceptance Focus Checklist

This checklist tracks every core focus item from `docs/QUORUM_BRIEF.md` for Track 02 and Track 03.
**Rule:** Status progresses from `not started` -> `built` -> `verified`. Never mark an item `verified` until it has been executed and proven by a real command or demo step.

---

## Track 02: Agent Memory and Coordination (~80% Effort)

| Focus | Description | Feature Implementation | Status | Verification Command / Demo Step |
|---|---|---|---|---|
| **T02-1: Episodic, Semantic & Procedural Memory** | Multi-type memory in graph: Episodic (`Message` nodes + `Fact.source_ref`, `Fact.quote`), Semantic (`Fact`, `Conclusion`), Procedural (`Procedure` with ordered `steps[]`, `uses/successes/failures`). | `graph/queries.py`, schema definitions, procedure scoring | `not started` | Demo: Procedure selection changing between two runs based on success/failure score updates. |
| **T02-2: Persistent Conversation History** | Multi-session recall: `Session -> Message` (NEXT-linked) in private raw graphs; session summary on close. Restarted agents resume via 2-query flow (raw graph then commons). | Private raw graph `tenant_<id>:agent_<n>:raw`, session summarizer, resume queries | `not started` | Demo: Agent restart beat showing persistent recall and attribution ("where each belief came from"). |
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
| **T03-4: Keeping Knowledge Current** | Living knowledge: `SUPERSEDES` by fact key, stale propagation (`stale=true` on conclusions/decisions), REVIEW handoffs to owning teams. | `supersede` query in `graph/queries.py`, stale propagation engine | `not started` | Demo Step 4: Policy change (30 -> 45 days) flags downstream decisions stale and queues review handoffs. |
| **T03-5: Answers with Clear Sources** | Grounded answers: every answer carries citations, owning team, and freshness. Untraceable answers are strictly refused. | `/api/brain/ask` endpoint with citation verification and refusal guard | `not started` | API & UI test: Valid query returns cited answer with owner team; ungrounded query triggers refusal response. |

---

## Frontend evidence (Hamza)

Status is one of: not started, built, verified. A focus is only "verified" after it was run and looked at.
Frontend rows say which data mode they were checked in. Mock mode is the in-browser scripted backend and proves the UI, not the system.

### Track 02: Agent memory and coordination

| # | Focus | Where it shows in the UI | Status | How to check |
|---|---|---|---|---|
| 1 | Episodic, semantic, procedural memory | Memory view: procedure ranking with "seeded" and "learned in this run" labels | built; verified in mock only | `docs/screens/10-memory.png`; live check waits on the backend |
| 2 | Persistent history, resume | Memory view: "What this agent remembers" with source and quote per belief | built; verified in mock only | `docs/screens/10-memory.png` |
| 3 | Shared state and handoffs | Actions and handoffs tab: claim race, lease ring, review queue | built; verified in mock only | `npm run qa` then `docs/screens/07-ledger.png` |
| 4 | High-concurrency reads and writes | Benchmark view reads `/bench/results` and shows `generated_at` and run parameters | built; numbers are a mock fixture | `docs/screens/13-benchmark.png`; real numbers come from `make proof` |
| 5 | Per-tenant memory | Tenants view: denied read; header tenant switch | built; verified in mock only | `docs/screens/12-tenants.png` |
| + | Memory over time (supersede, as-of, quarantine, restore) | Timeline slider, "Viewing the past" frame, belief diff, Restore step | built; verified in mock only | `docs/screens/08-past.png` |

### Track 03: Company brain

| # | Focus | Where it shows in the UI | Status | How to check |
|---|---|---|---|---|
| 1 | Docs, tickets, chats in one graph | Source nodes (folded boxes) in the graph, origin in Inspector path | built; verified in mock only | `docs/screens/05-contained.png` |
| 2 | Who owns, who knows | Brain view: who-knows leaderboard; owner team in Inspector | built; verified in mock only | `docs/screens/11-brain.png` |
| 3 | Trace decisions to source | Brain view: decision trace with quote, version, owner | built; verified in mock only | `docs/screens/11-brain.png` |
| 4 | Knowledge stays current | Replace policy: "Out of date" rings, review handoff to the owning team | built; verified in mock only | `docs/screens/09-supersede.png` |
| 5 | Cited answers, refusals | Brain view: citations with freshness, refusal state | built; verified in mock only | `docs/screens/11-brain.png` |

### Visible moments (the 90-second demo)

| Moment | Status | Evidence |
|---|---|---|
| Poison arrives and agents act (Ran, Held for review) | built; verified in mock only | `03-agents-acted.png`, `npm run qa` |
| Quarantine wave by hop depth, containment report | built; verified in mock only | `04-wave.png`, `05-contained.png` |
| Prompt diff with removed lines struck through | built; verified in mock only | `06-prompt-diff.png` |
| Execute guard refusal in History | built; verified in mock only | History entry "Refused by the execute guard" |
| As-of slider and belief diff | built; verified in mock only | `08-past.png`, `npm run qa` |
| Claim race | built; verified in mock only | `07-ledger.png` |
| Denied read | built; verified in mock only | `12-tenants.png` |
| Supersede and stale | built; verified in mock only | `09-supersede.png` |
| Autopilot, one take | built; verified in mock only | `npm run qa` (runs the full sequence) |
| Three live Replay runs in a row | not started | needs the backend |
| `npm run contract:check` against the live backend | not started | needs the backend and an OpenAPI snapshot |

