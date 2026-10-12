# Quorum Standalone MCP Server

This is the standalone, compact distribution of the **Quorum Agent Memory & Safety Gateway** MCP server.

It provides causal graph memory, prompt diffing, blast radius analysis, and atomic execution safety gates for autonomous agents.

## 🚀 Quick Start (3 Steps)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the MCP Server
You can run it in **stdio mode** (for local CLI/IDE clients) or **HTTP/SSE mode**:

* **Stdio Mode (Claude Desktop / Cursor / Antigravity):**
  ```bash
  python server.py --stdio
  ```

* **HTTP / SSE Mode (Network / Remote Access):**
  ```bash
  python server.py --host 0.0.0.0 --port 8001
  ```
  Connect your client to `http://localhost:8001/sse`.

### 3. Add to Your MCP Client Configuration

In your client's config file (`claude_desktop_config.json`, `mcp_config.json`, etc.):

```json
{
  "mcpServers": {
    "quorum": {
      "command": "python",
      "args": [
        "path/to/quorum-mcp-standalone/server.py",
        "--stdio"
      ]
    }
  }
}
```

## 🛠 Available Tools
1. `remember_fact`: Store an episodic/semantic belief node.
2. `derive`: Anchor a derived decision/plan to parent facts.
3. `retrieve_context`: Query active, healthy, unsuperseded beliefs.
4. `stage_action`: Propose an action through the Quorum Gate.
5. `execute_action`: Atomic Cypher check-and-set execute guard.
6. `explain_blast_radius`: Dry-run calculation of downstream impact.
7. `quarantine`: Invalidate a faulty belief and cascade the Quarantine Red Wave.
8. `restore`: Restore a quarantined root and valid descendants.
9. `claim_handoff`: Claim multi-agent handoff tasks.
10. `review_handoff`: Human/auditor approval gate.
