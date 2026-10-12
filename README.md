# Quorum

Git revert for agent beliefs. Agents share memory in a causal graph (FalkorDB). When a belief turns out to be wrong, Quorum quarantines that fact and everything built on it, queues compensations for real-world effects, and no later retrieval can return it.

Built for Graph Hacks: Context for AI Agents (WeMakeDevs x FalkorDB). Tracks: 02 Agent Memory and Coordination (about 80% of effort), 03 Company Brain (about 20%). All data is synthetic.

Status of this branch: the frontend console is built and runs in mock mode. The backend, graph and agents are owned by the other two team members and are not in this branch yet.

## Run the console

```bash
cd frontend
npm install
npm run dev        # http://127.0.0.1:5173
```

See [frontend/README.md](frontend/README.md) for modes, scripts and layout.

## Track 02: agent memory and coordination

| Focus | Feature | Where to verify |
|---|---|---|
| Episodic, semantic, procedural memory | Procedure ranking that changes after a bad run; beliefs with quote and source | Memory view; [FOCUS_CHECKLIST](docs/FOCUS_CHECKLIST.md) |
| Persistent history | "What this agent remembers", resumed from private history | Memory view, "Show what it remembers" |
| Shared state and handoffs | Claim race, lease countdown, human review queue | Console, "Actions and handoffs" tab |
| High concurrency | Latency percentiles and handoff race from `make proof` | Benchmark view (mock fixture until the backend lands) |
| Per-tenant memory | Denied cross-tenant read | Tenants view; header tenant switch |

## Track 03: company brain

| Focus | Feature | Where to verify |
|---|---|---|
| Docs, tickets, chats in one graph | Source nodes feed facts; origin shown in the Inspector | Console graph |
| Who owns, who knows | Who-knows leaderboard, owner team on decisions | Brain view |
| Trace decisions to source | Decision trace with quote, version, owner | Brain view |
| Knowledge stays current | Replace policy marks dependents "Out of date" and queues a review | Console, "Replace policy" |
| Cited answers | Ask box with citations, freshness and refusals | Brain view |

## Docs

| File | Purpose |
|---|---|
| [docs/QUORUM_BRIEF.md](docs/QUORUM_BRIEF.md) | Source of truth for idea and build |
| [docs/TEAM_PLAN.md](docs/TEAM_PLAN.md) | Who builds what |
| [docs/CONTRACT.md](docs/CONTRACT.md) | REST and SSE contract (0.1.0 draft, unsigned) |
| [docs/FRONTEND_DESIGN.md](docs/FRONTEND_DESIGN.md) | Frontend design plan |
| [docs/FOCUS_CHECKLIST.md](docs/FOCUS_CHECKLIST.md) | Focus status and evidence |
| [docs/screens/](docs/screens/) | One screenshot per demo beat |

## Honest limits

- Compensation is not undo. Irreversible actions are flagged and handed to a person.
- An agent whose context window already holds a fact keeps it until it rebuilds; agents refresh when the epoch changes.
- The claim is "no later retrieval returns quarantined content", not "it never reached the model". In the demo, Refunder executes two refunds before detection.
- As-of queries see only the latest quarantine window per node.
- Seeded procedure scores are labelled "seeded".
- Benchmark numbers are whatever the run prints. Until then the console shows a labelled mock fixture.

## AI use

The frontend was built with the help of Claude Code (an AI coding assistant), reviewed and committed by Hamza. Add the other members' disclosures here.
