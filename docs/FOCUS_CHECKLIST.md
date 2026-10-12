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
