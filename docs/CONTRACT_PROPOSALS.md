# Contract proposals from the console

These are additions the new console pages (Context, Connect, Team) would like from the backend. **None of them are in `docs/CONTRACT.md` yet** and the backend does not implement them. Until the three of us agree, the console builds each feature in the browser and labels it. Nothing here changes an existing endpoint.

## 1. Token-saving MCP tools

The packer in `frontend/src/context/packer.ts` is the reference behavior. It is pure TypeScript with tests (`packer.test.ts`) and can be ported to the backend as is.

| Tool | Arguments | Returns | Why |
| --- | --- | --- | --- |
| `get_map` | `token` | the `quorum_map.md` text | An agent reads where things live once per session, then fetches single nodes. |
| `get_node` | `id`, `token` | one node, its parents, short ids | A few lines instead of a document. |
| `delta` | `epoch`, `token` | nodes added and removed since `epoch` | Refresh after an epoch change without re-reading. |
| `find_path` | `from`, `to`, `token` | shortest chain of ids | Provenance without the whole subgraph. |
| `retrieve_context` (extend) | add `budget_tokens` | same shape, trimmed to the budget, plus `tokens` | Today it returns up to `k` full facts. |

`retrieve_context` should also return ancestors of each fact (ids only) so the agent can cite where an answer came from.

### Response fields worth adding to every tool

```json
{ "epoch": 7, "tokens": 391, "tokens_baseline": 1209 }
```

`tokens_baseline` is the size of a typical top-8 retrieval for the same query. The Context page and the header counter use it.

### Method (so the numbers are checkable)

1. Drop anything not `HEALTHY` or marked `stale`.
2. Rank the rest by keyword overlap with the query (fact and conclusion nodes get a small boost).
3. Add the ancestors of the top matches, up to `depth * 3` each, so every answer carries its provenance.
4. One line per node: `F3|label|text|<parents`, short ids, duplicates removed.
5. Trim from the bottom until the output fits the budget.

Token counts in the console are an estimate (about 4.5 characters per token for words, one token per symbol), within roughly 15% of a real tokenizer. Replace `estimateTokens` with the model's tokenizer when the backend has one.

## 2. Workspace service (teams, members, links)

Used by the Team page. Today the workspace is stored in the browser (`localStorage`, key `quorum:workspace:v1`).

```
GET    /api/workspace                    -> { org, plan, hub, teams[], members[], links[] }
PUT    /api/workspace                    -> rename org, change plan, set hub
POST   /api/workspace/teams              { name, seats }
PATCH  /api/workspace/teams/{id}         { seats }
DELETE /api/workspace/teams/{id}
POST   /api/workspace/members            { name, role, team_id, client, device } -> member with a new token (shown once)
POST   /api/workspace/members/{id}/rotate
DELETE /api/workspace/members/{id}
POST   /api/workspace/links              { a, b, scope: "team" | "commons" }
PATCH  /api/workspace/links/{id}         { paused }
DELETE /api/workspace/links/{id}
```

Rules the UI already enforces and the server must too: seat limits per plan and per team, unique team names, no link between a member and themselves, no duplicate links, tokens are never returned after creation except through `rotate`.

Linked members receive each other's changes as `delta` responses scoped by the link (`team` shares only that team's nodes, `commons` shares everything in the tenant graph). Links never copy graph data between tenants.

## 3. Presence and activity

Used by the Connect page.

```
GET /api/mcp/status   -> { state: "up" | "down", latency_ms, tools: [names], version }
GET /api/activity     -> SSE of { ts, member_id, tool, summary, tokens, tokens_baseline, epoch }
GET /api/sessions/{member_id}  -> recent turns [{ from, text, tokens? }]
```

In live mode the console already probes the real MCP endpoint (`POST /mcp/` with an `initialize` request, proxied by Vite from `QUORUM_MCP`, default `http://127.0.0.1:8001`). Presence, the activity feed and chats are simulated in the browser until these endpoints exist, and the page says so.

## 4. What the console never does

It never writes to a user's machine. The Connect page prints commands and config files for the user to paste.
