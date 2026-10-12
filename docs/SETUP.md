# Setting up Quorum

Quorum stores every belief, handoff and action in **FalkorDB**. It does not run without it: if FalkorDB is missing or misconfigured, the API answers `503 FALKORDB_UNAVAILABLE`, the MCP server refuses tool calls, and the console shows a locked setup screen instead of the product. There is no sample-data fallback in a normal build.

## 1. Start everything (Docker)

```bash
docker compose up -d
python scripts/doctor.py
```

Open `http://localhost:5173`. The console opens by itself once FalkorDB is ready.

`doctor.py` checks Python packages, Docker, FalkorDB (including that the graph module is loaded), the backend and the MCP endpoint, and prints the exact command that fixes anything missing.

## 2. Start it without Docker for the app (FalkorDB still in Docker)

```bash
docker compose up -d falkordb
pip install -r backend/requirements.txt
QUORUM_EMBED_MCP=1 python -m uvicorn app.main:app --app-dir backend --port 8000
cd frontend && npm ci && npm run build && npx vite preview --port 5173
python scripts/doctor.py
```

On Windows PowerShell set the variable first: `$env:QUORUM_EMBED_MCP = "1"`.

## 3. Connect an AI

Open the **Connect** page in the console for paste-ready setup for Claude Code, Claude Desktop, Cursor, VS Code, Windsurf, Antigravity and any MCP client. For Claude Code:

```bash
claude mcp add --transport http quorum http://localhost:8000/mcp
```

Every tool takes your token as the `token` argument. Give the agent its rules from the Connect page so it passes the right one.

## 4. Teams, members and tokens

Open **Team** in the console (you need a `human` token). Add a team, then add a member to it: you get that person's token **once** (`qrm_<tenant>_<secret>`); only its hash is stored, and rotating or removing the member invalidates it. They paste it into their AI's rules (the Connect page generates the text) and connect their own laptop to the same backend URL.

- Plans set the seat and team limits; teams set their own seats. The server enforces both.
- A fact saved with `scope="team"` is private to that team. **Link** two members and each sees the other's team facts, from any laptop and any AI; pause or unlink and access ends at once.
- Presence, call counts and "tokens saved" per member come from their real MCP calls.

## What happens when FalkorDB goes away

| Moment | What you see |
| --- | --- |
| FalkorDB not running at start | The console shows "FalkorDB is not set up, so Quorum is locked" with the steps. The backend still starts so it can say so. |
| FalkorDB stops while you work | Within a few seconds every API call returns 503, the event stream ends, and the console is replaced by the same screen. Writes made in that moment are held and saved when it returns. |
| FalkorDB comes back | The console reopens by itself and reloads from the database. Nothing is lost. |
| Backend not running | The console says the backend is not running and shows the command to start it. |

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `QUORUM_FALKORDB_URL` | `redis://localhost:6379` | Where FalkorDB is. `FALKORDB_HOST` and `FALKORDB_PORT` are also read. |
| `QUORUM_EMBED_MCP` | off | Serve MCP from the API process at `/mcp` so agents and the console share one graph. Needs `mcp>=2`. |
| `QUORUM_ENV` | `development` | `production` turns off the built-in demo tokens and ad-hoc tokens. |
| `QUORUM_TOKENS_JSON` | empty | `{"<token>": {"tenant": "acme", "role": "agent", "agent_id": "scout"}}`. With member tokens issued from the Team page, the only tokens accepted in production. |
| `QUORUM_ALLOW_DYNAMIC_TOKENS` | on outside production | Accept ad-hoc `token_<tenant>_<role>` tokens. Anyone can forge these, so keep it off in production. |
| `QUORUM_CORS_ORIGINS` | localhost only | Comma separated origins allowed to call the API from a browser. |
| `QUORUM_PERSISTENCE` | `falkordb` | `memory` exists for unit tests only and shows a warning banner. Never use it for real work. |

## Production checklist

1. `QUORUM_ENV=production`, and `QUORUM_TOKENS_JSON` with real tokens. Replace `frontend/public/config.json` at deploy time with a file holding the same tokens for the console.
2. FalkorDB with a volume and a password in `QUORUM_FALKORDB_URL` (`redis://:password@host:6379`). Do not expose port 6379.
3. One backend process. Atomic guards run in the process under locks, so do not run several API workers against one FalkorDB.
4. Put HTTPS in front of the console and the API, and set `QUORUM_CORS_ORIGINS` to the console's origin.
5. `python scripts/doctor.py` and `GET /api/health` should both report ready.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| "Database not ready" screen | `docker compose up -d falkordb`, then `python scripts/doctor.py` |
| "Redis is running but the FalkorDB graph module is not loaded" | You started plain Redis. Use the `falkordb/falkordb` image. |
| "Backend not running" screen | Start the backend (step 2), or `docker compose up -d backend`. |
| Console loads but every call is 401 | The tokens in `frontend/public/config.json` do not match the backend's tokens (see `QUORUM_TOKENS_JSON`). |
| Agent writes do not show in the console | The MCP server is a separate process. Use `QUORUM_EMBED_MCP=1` instead of the standalone server. |
| `docker compose build` fails at `pip install` | The Docker engine has no network. Check Docker Desktop's proxy and DNS settings. |
