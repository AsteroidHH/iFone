# Quorum Focus Checklist & Proof Pack Guidelines

*All features must be verified via `make proof`. Do not mark as `[BUILT]` or `[VERIFIED]` until dynamic tests and `docs/PROOF.md` generation confirm execution.*

## Track 02: Agent Memory and Coordination (~80%)

- [ ] **Episodic, Semantic, Procedural Memory**
  - *Verification*: `bench/run.py` & Demo step showing Procedure rank drops post-quarantine and switching to a new procedure.
- [ ] **Persistent Conversation History**
  - *Verification*: Restart agents in demo; prove kill-and-resume 2-query flow and summary generation.
- [ ] **Shared State & Handoffs**
  - *Verification*: Two agents visibly race for a claim in the demo; 100 handoffs x 30 claimers load test asserts exactly 1 winner. Lease-expiry beat with killed claimer takeover.
- [ ] **High-Concurrency Reads/Writes**
  - *Verification*: `bench/run.py` reporting throughput (p50/p95/p99) single/multi-tenant (RO_QUERY) and proving zero-orphans invariant.
- [ ] **Per-Tenant Memory Isolation**
  - *Verification*: Passing `tests/test_tenant_isolation.py`, live denied-read demo, and GRAPH.LIST leak check.

## Track 03: Company Brain (~20%)

- [ ] **Docs, Tickets, Chats in One Graph**
  - *Verification*: `make seed` outputs correct counts mapping 3 Source types into commons graph.
- [ ] **Who Owns What, Who Knows What**
  - *Verification*: Execution of `Team-[:OWNS]->` and `Person-[:AUTHORED|RESOLVED]->Source` Cypher queries. UI Panel display.
- [ ] **Tracing Decisions to Source**
  - *Verification*: Execution of `Decision <- LEADS_TO <- Fact -> Source` returning quote, url, version, owner.
- [ ] **Keeping Knowledge Current**
  - *Verification*: `SUPERSEDES` query execution; dependents flagged `stale`; `REVIEW` handoff created; Epoch incremented.
- [ ] **Answers with Clear Sources**
  - *Verification*: `tests/test_answers.py` runs a 15-question eval (12 expected, 3 refusal) printing precision/recall and refusal accuracy.

## Benchmarks & Invariants (`make proof`)

- [ ] **Poison Benchmark (No LLM, Direct Retrieval)**
  - *Verification*: Measures leaked context rate, wrongly quarantined nodes, and time-to-containment against flat vector TTL baseline and no-cascade baseline.
- [ ] **Atomic Execute Guard & Tombstone Race**
  - *Verification*: Hammer test with concurrent quarantines asserting no executed action has a non-healthy ancestor/supporter. Tombstone race test passes with 409 rejection.
- [ ] **Quorum Gate**
  - *Verification*: Gate blocks irreversible actions backed by uncorroborated leaves, stale ancestors, or if a corroborator is later quarantined.
- [ ] **Token Role Enforcement**
  - *Verification*: Agent tokens cannot claim or complete `REVIEW` or `ESCALATION` handoffs.

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

