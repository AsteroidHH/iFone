# Token saving: what Quorum does, and what was measured

## What an agent gets

Quorum keeps one organized memory and gives an agent the smallest slice that answers its question. All of this runs in the backend (`backend/app/services/context_pack.py`) and is exposed as MCP tools:

| Tool | What it returns | Why it is cheap |
| --- | --- | --- |
| `retrieve_context(query, format="compact", budget_tokens)` | One line per node: `F3|label|text|<S1` with short ids and the sources that prove it | Healthy, in-scope nodes only; ranked by rarity-weighted word coverage; ancestors for provenance; duplicates removed; trimmed to the budget |
| `get_map()` | Areas, hubs and how to ask, a few hundred tokens | Orientation without loading the graph |
| `get_node(id)` | One node with its parents and children, by short id (`F3`) or full id | A few lines instead of a document |
| `find_path(from_id, to_id)` | The shortest causal chain | Provenance without the subgraph |
| `delta()` | What stopped being true since this agent's last read, plus new matches | Refresh without re-reading |

`retrieve_context` still returns the full JSON by default (`format="full"`), so existing callers are unchanged. Every response carries `tokens` (its size) and `tokens_baseline` (what a typical top-8 retriever returns for the same call: the best keyword matches as full JSON, healthy or not). Both come from one estimator, about 4.5 characters per token for words and one per symbol, within roughly 15% of a real tokenizer, with identical results in Python and TypeScript (a shared fixture test enforces it).

Quorum also never hands an agent a quarantined, superseded or stale fact, and never one outside the agent's team scope. That is correctness, not saving, but a plain retriever cannot do it at all.

Every call is recorded (who, tool, tokens, baseline). `GET /api/token-stats` sums the read calls; the header counter, the Context page and each member's "tokens saved" come from it. Per call the saving can be negative, and it is not clipped.

## What was measured with a real AI

`frontend/scripts/token_bench.mjs` runs fresh Claude Code sessions against the live stack. The same five questions are answered from the same 160-fact memory, three ways:

- **plain**: `retrieve_context(query, k=8)` in the full format, what a typical top-8 memory returns.
- **compact**: `retrieve_context(query, format="compact", budget_tokens=400)`.
- **mapped**: `get_map` once, then the compact calls.

Two memories: short facts (one or two sentences) and real-sized documents (about 120 words each). Two runs per arm, medians. Every arm answered 5/5 correctly. Raw results are in `bench/token_bench_short.json` and `bench/token_bench_long.json`.

| Memory | Tool-result tokens per run (plain → compact) | Whole session, input tokens | Session cost |
| --- | --- | --- | --- |
| Short facts | 4,618 → 2,353 (49% fewer) | 160,809 → 159,362 (1% fewer) | $0.193 → $0.187 (3% less) |
| Real-sized documents | 10,811 → 2,347 (78% fewer) | 166,875 → 159,248 (5% fewer) | $0.229 → $0.186 (19% less) |

How to read it:

- **Tool results shrink a lot**, and the more text each fact carries the more they shrink, because compact lines are bounded by the budget while full results grow with the documents.
- **Whole sessions move less**, because Claude Code sends its own fixed prompt (about 37,000 tokens even for the word "ok") on every turn, and Quorum cannot change that. The saving shows in cost most, because tool results stay in the context for the turns that follow.
- **Turns matter more than lines.** Adding `get_map` added a turn and made the five-question session use 33% more input tokens (28% on the long memory). A turn costs far more than the map saves in a short session. The shipped agent rules therefore tell agents to call `get_map` only when they do not know where to look.
- Savings grow with the size of the memory and the length of the session. A five-question session on a 160-fact memory is a small case.

Reproduce: `cd frontend && node scripts/token_bench.mjs http://127.0.0.1:8000 2 long` (costs a few dollars of Claude usage; use `short` for the other memory).
