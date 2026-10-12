import sys
import os
import asyncio

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from mcp.server.mcpserver import MCPServer
from app.services import mcp_tools

mcp_server = MCPServer("quorum")

# Register tools directly on the server instance
mcp_server.tool()(mcp_tools.remember_fact)
mcp_server.tool()(mcp_tools.derive)
mcp_server.tool()(mcp_tools.retrieve_context)
mcp_server.tool()(mcp_tools.stage_action)
mcp_server.tool()(mcp_tools.execute_action)
mcp_server.tool()(mcp_tools.claim_handoff)
mcp_server.tool()(mcp_tools.quarantine)
mcp_server.tool()(mcp_tools.explain_blast_radius)
mcp_server.tool()(mcp_tools.review_handoff)


def main():
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Quorum Standalone MCP Server")
    parser.add_argument("--stdio", action="store_true", help="Run in stdio mode")
    parser.add_argument("--port", type=int, default=8001, help="Port for streamable HTTP transport (default: 8001)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host for streamable HTTP transport")
    args = parser.parse_args()

    if args.stdio:
        asyncio.run(mcp_server.run_stdio_async())
    else:
        app = mcp_server.streamable_http_app()
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
