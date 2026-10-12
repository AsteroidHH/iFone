---
name: quorum-mcp
description: >-
  Use Quorum MCP tools to query causal graph memory, store facts and conclusions,
  stage and execute gated actions, orchestrate handoff tasks, calculate blast radius,
  quarantine faulty premises, and review handoffs.
---

# Quorum Agent Memory & Safety Gateway

Quorum provides a multi-agent causal memory commons and safety execution gateway.

## Available Tools

1. `retrieve_context(token: str, key_filter: Optional[str] = None)`
   - Retrieves active, healthy, unsuperseded facts and conclusions.
   - Always run before deriving new conclusions or staging actions.

2. `remember_fact(key: str, value: str, text: str, token: str, id: Optional[str] = None, quote: Optional[str] = None, origin: Optional[str] = None)`
   - Stores an episodic or semantic fact node into the graph.

3. `derive(key: str, value: str, text: str, caused_by: List[str], token: str, kind: str = "conclusion", id: Optional[str] = None)`
   - Derives a conclusion or decision node causally anchored to parent node IDs in `caused_by`.

4. `stage_action(action_type: str, params: Dict[str, Any], token: str, caused_by: List[str], tier: int = 1, reversibility: str = "reversible", dry_run: bool = False)`
   - Proposes an action through the Quorum safety gate. Checks for quarantined premises and policy constraints.

5. `execute_action(action_id: str, token: str)`
   - Atomically executes an approved staged action against integrated tools/APIs.

6. `claim_handoff(agent_id: str, token: str, handoff_id: Optional[str] = None, capability: Optional[str] = None, lease_seconds: int = 300)`
   - Claims an unassigned task from the handoff queue with a lease.

7. `explain_blast_radius(root_id: str, token: str)`
   - Dry-run analysis calculating the downstream impact if `root_id` were quarantined.

8. `quarantine(root_id: str, token: str, reason: str = "")`
   - Auditor tool: Quarantines a faulty node and cascades quarantine down its causal tree.

9. `restore(root_id: str, token: str)`
   - Auditor tool: Restores a previously quarantined root node and its valid downstream nodes.

10. `review_handoff(handoff_id: str, approved: bool, token: str, reason: str = "")`
    - Human tool: Approves or rejects a gated or quarantined handoff task.
