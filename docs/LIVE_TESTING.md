# Testing the console against the live backend

`npm run qa` drives the console on sample data. `npm run qa:live` drives it against the real FastAPI backend, the real event stream and the real MCP server, with an outside MCP client acting as an agent.

## What the live run checks (31 checks)

- Live mode is really live: no sample chip, event stream connected, nothing simulated in the header.
- The Connect page shows a real MCP handshake, not a simulated one.
- An outside agent speaks MCP over HTTP: lists the ten tools, writes a fact, reads it back with `retrieve_context`, is refused when it tries `quarantine` with an agent token, succeeds with an auditor token, and no longer retrieves the quarantined fact. The console shows the fact and its quarantine without a reload.
- The 90-second story (inject, run agents, audit, replace policy) runs with the real agents, in order, without getting stuck.
- Insights, Prompt diff, Actions and handoffs, Memory, Company brain, Tenants, Benchmark, Context and Team render real data.
- The dev console shows no schema-validation failures and no request failed.

## Run it

1. FalkorDB (needed for the graph tests and the benchmark, not for the API itself, see Notes):

   ```bash
   docker compose up -d falkordb
   ```

2. The backend with MCP embedded, so agents and the console share one graph and one event stream:

   ```bash
   pip install -r backend/requirements.txt
   QUORUM_EMBED_MCP=1 python -m uvicorn app.main:app --app-dir backend --port 8000
   ```

3. The console in live mode, with demo tokens (never commit this file):

   ```bash
   cd frontend
   VITE_API_MODE=live npx vite build --outDir dist-live --emptyOutDir
   echo '{"tokens":{"acme":{"human":"token_human","auditor":"token_auditor","agent":"token_agent_scout"},"globex":{"human":"token_globex_human","auditor":"token_globex_auditor","agent":"token_globex_agent"}},"tenants":["acme","globex"]}' > dist-live/config.json
   QUORUM_MCP=http://127.0.0.1:8000 npx vite preview --outDir dist-live --port 5174 --strictPort
   ```

4. In another terminal:

   ```bash
   cd frontend && npm run qa:live
   ```

## What this run found and fixed

| Where | Problem | Fix |
| --- | --- | --- |
| Console, schemas | The backend sends explicit `null` for optional fields; the console rejected the whole graph ("Couldn't load GET graph"). | Optional fields accept `null` (`schemas.ts`), with a regression test. |
| Backend, `GET /graph` | `seq` was the query-log length, not the event bus sequence, so the console re-synced forever ("Out of sync"). | `seq` now comes from the event bus; test added. |
| Console, events | One event type the console does not know (`correction_notice_created`) was dropped, leaving a hole in the sequence, which stalled the stream. | Unknown events keep their place in the sequence and change nothing. |
| Backend, `GET /events` | Response headers were not sent until the first event, so the connection looked stuck at "connecting". | The stream sends a heartbeat immediately. |
| Console, startup | A handoffs request fired before the session token existed (401 on every load). | The query waits for the session. |
| Backend, MCP | The standalone MCP server has its own in-memory graph, so agent writes never reached the console. MCP writes also published no events. | `QUORUM_EMBED_MCP=1` serves MCP from the API process (`app/mcp_embed.py`), and `remember_fact`, `derive` and `stage_action` now publish `node_added` and `edge_added`. |
| Backend, requirements | `mcp` was missing, so the MCP container could not start. | `mcp>=2.0.0,<3` added. |
| Bench | Against FalkorDB the handoff race never created its handoff nodes, so it reported 0 winners. | The harness seeds them; the race is 100/100. |

## Notes

- The API server runs on the in-memory `GraphStore` (`backend/app/graph/queries.py`). FalkorDB is used by `graph/queries.py` in the graph tests and the benchmark. The API is not yet wired to it.
- The Tenants page text comes from a canned response in `backend/app/routes/system.py`, not from a real Redis ACL denial.
- Throughput depends on the machine and the engine. On one Windows laptop against FalkorDB: 477 ops/s, p99 133 ms, 100/100 claim winners, 0 leakage. Recorded runs elsewhere in the repo show different numbers. Publish one `make proof` run from the demo machine.
- `docker compose build backend` failed here at `apt-get update` (the Docker engine had no network during the build). Running the services directly with Python worked.
