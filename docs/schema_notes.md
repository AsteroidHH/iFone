# Quorum Schema & Mechanics Notes

## 1. Graph Namespaces & Tenant Isolation
- **Commons:** `tenant_<id>:commons` (Derived knowledge: Fact, Conclusion, Action, Handoff, Procedure, Meta). Invalidation cascades happen entirely within here.
- **Raw:** `tenant_<id>:agent_<n>:raw` (Private Session, Message).
- *Isolation enforced via Redis ACL user limited to `~tenant_<id>:*`, mapped by gateway via authenticated token.*

## 2. Core Nodes & Properties
*All reasoning nodes in `commons` carry `:MemoryNode`.*

- **`Meta`**: `(tenant_id, epoch [int])` - Epoch increments on every quarantine, restore, AND supersede.
- **`Source`**: `(id, kind, title, url, version, origin)` - `origin` is set ONLY by ingest gateway.
- **`Fact`**: `(id, key, value, text, status [HEALTHY|SUPERSEDED|QUARANTINED], embedding, valid_from, valid_to, stale, quarantined_at, released_at, quarantine_root, source_ref, quote)`
- **`Conclusion`**: `(id, text, status, stale, quarantine fields)` + optional `:Decision` label with `owner_team`.
- **`Action`**: `(id, type, payload, status, executed, confirmed, gate [PASSED|BLOCKED], reversibility [REVERSIBLE|COMPENSABLE|IRREVERSIBLE], procedure_id, run_id, idempotency_key, quarantine fields)`
- **`Compensation`**: `(id, target_action_id, status [PENDING_COMPENSATION|DISPATCHING|COMPENSATED|FAILED], attempts, lease_until, idempotency_key)`
- **`Handoff`**: `(id, kind [TASK|REVIEW|ESCALATION], task, assigned_to, status, claimed_by, claimed_at, lease_until)`
- **`Agent`**: `(id, name, role, tier [root|established|new], tier_weight [10|3|0.5])`
- **`Procedure`**: `(id, task_type, steps [array], uses, successes, failures)`
- **`Session` / `Message`** (Raw): `Session(id, created_at, summary)`, `Message(id, text, ts)`.

## 3. Edges
- `ASSERTS`, `SUPERSEDES`, `CONTRADICTS`, `LEADS_TO` (DAG), `SUPPORTS` (created when gate passes), `CONTEXT_ROOT`, `FROM_SOURCE`, `OWNS`, `MEMBER_OF`, `AUTHORED|RESOLVED`, `ABOUT`, `OWNED_BY`, `COMPENSATED_BY`.

## 4. The Three Defense Layers

### Defense 1: Quorum Gate (stage_action)
- Reversible/compensable actions automatically get `gate=PASSED`.
- **IRREVERSIBLE** actions pass ONLY IF:
  1. No ancestor is `stale`.
  2. EVERY leaf fact (ancestor Fact with no incoming `LEADS_TO`) is asserted by a `root-tier` agent OR is corroborated: Another `HEALTHY` Fact with the same `key` and `value` from a Source with a DIFFERENT `origin`, with at least one asserted by `established` or higher.
- If passed: Creates `(corroborator)-[:SUPPORTS]->(action)`.
- If failed: `gate=BLOCKED`, creates a `REVIEW` Handoff. 

*Draft Leaf Fetch Query:*
```cypher
MATCH (leaf:Fact)-[:LEADS_TO*]->(a:Action {id:$id}) WHERE NOT (()-[:LEADS_TO]->(leaf)) RETURN DISTINCT leaf
```

### Defense 2: Atomic Execute Guard (execute_action)
A single check-and-set prevents race conditions:
```cypher
MATCH (a:Action {id:$id}) WHERE a.status='HEALTHY' AND a.executed=false AND a.gate='PASSED'
OPTIONAL MATCH (x:MemoryNode)-[:LEADS_TO|SUPPORTS*]->(a) WHERE coalesce(x.status,'MISSING') <> 'HEALTHY'
WITH a, count(DISTINCT x) AS bad WHERE bad = 0
SET a.executed = true, a.confirmed = false
RETURN a.id
```

### Defense 3: Quarantine Cascade (The Red Wave)
- Follows unbounded `[:LEADS_TO|SUPPORTS*]`. Sets `status='QUARANTINED'` and `quarantined_at`.
- **Context Epoch Increment**: Atomically increments `Meta.epoch`. MCP responses return this epoch; agents with stale epochs must rebuild context.
- Compensations created iteratively *after* cascade via `MERGE`.

## 5. Trust, Tombstones, and Token Roles
- **Trust Rule**: Root > Corroborated > Tier (ties -> REVIEW). Root never auto-quarantines.
- **Tombstones (In-Flight Protection)**: A compensation request for an unknown/unconfirmed idempotency key records a TOMBSTONE. Later execute requests with a tombstoned key get 409 Rejected. The worker retries compensations (idempotent) until the action is confirmed or tombstoned.
- **Token Roles**: Agent tokens can ONLY claim/complete `kind=TASK`. `REVIEW` and `ESCALATION` claims (and approving blocked gates) require a Human or Auditor token.
- **Procedure Scoring**: Rank = `(successes+1)/(successes+failures+2)`. Real distill step creates a `Procedure` from an unrecorded run. Failures trigger instantly if an action is quarantined. Success requires the Auditor to call `verify_run` post-audit window with 0 quarantined actions.
