/**
 * Everything the UI knows about Quorum's MCP server. The tool list mirrors mcp/server.py and
 * backend/app/services/mcp_tools.py; if a tool is added there, add it here and the Connect page picks it up.
 */
export interface McpTool {
  name: string;
  summary: string;
  args: string;
  who: 'agent' | 'auditor' | 'human' | 'any';
  writes: boolean;
  saves: string;
  /** not in the backend yet; documented in docs/CONTRACT_PROPOSALS.md */
  proposed?: boolean;
}

export const MCP_TOOLS: McpTool[] = [
  { name: 'retrieve_context', summary: 'Healthy, unsuperseded facts for a query', args: 'query, token, k=5', who: 'any', writes: false, saves: 'Returns a small slice, never the whole graph' },
  { name: 'remember_fact', summary: 'Store a fact with its source', args: 'key, value, text, token, id?, quote?, origin?', who: 'agent', writes: true, saves: 'Store once, reference by id everywhere' },
  { name: 'derive', summary: 'Record a conclusion or decision from parent facts', args: 'text, parent_ids[], token, is_decision?', who: 'agent', writes: true, saves: 'Conclusions are linked, not re-explained' },
  { name: 'stage_action', summary: 'Stage an action; the quorum gate decides', args: 'label, action_type, reversibility, parent_ids[], token', who: 'agent', writes: true, saves: 'One call replaces a long approval thread' },
  { name: 'execute_action', summary: 'Run a staged action under the atomic guard', args: 'id, token', who: 'agent', writes: true, saves: 'No retries from stale context' },
  { name: 'claim_handoff', summary: 'Claim a task with an atomic lease', args: 'id, token', who: 'agent', writes: true, saves: 'Two agents never do the same work' },
  { name: 'quarantine', summary: 'Quarantine a fact and everything built on it', args: 'root_id, token, reason', who: 'auditor', writes: true, saves: 'Bad context is removed, not re-read' },
  { name: 'restore', summary: 'Restore a quarantined fact and valid descendants', args: 'root_id, token', who: 'auditor', writes: true, saves: 'Undo without re-ingesting' },
  { name: 'explain_blast_radius', summary: 'Dry run: what a quarantine would touch', args: 'root_id, token', who: 'auditor', writes: false, saves: 'Ids only, no node bodies' },
  { name: 'review_handoff', summary: 'Approve or reject a gate-blocked review', args: 'id, decision, token, note?', who: 'human', writes: true, saves: 'Humans decide once, agents read the verdict' },
  { name: 'get_map', summary: 'The compact quorum_map: where everything lives', args: 'token', who: 'any', writes: false, saves: 'Read once, then fetch single nodes by id', proposed: true },
  { name: 'get_node', summary: 'One node with its parents, by short id', args: 'id, token', who: 'any', writes: false, saves: 'A few lines instead of a document', proposed: true },
  { name: 'delta', summary: 'Only what changed since your epoch', args: 'epoch, token', who: 'any', writes: false, saves: 'Refresh without re-reading', proposed: true },
  { name: 'find_path', summary: 'Shortest chain between two nodes', args: 'from, to, token', who: 'any', writes: false, saves: 'Provenance without the whole subgraph', proposed: true },
];

export const WHO_LABEL: Record<McpTool['who'], string> = { agent: 'Agent token', auditor: 'Auditor token', human: 'Human token', any: 'Any token' };

export type ClientId = 'claude-code' | 'claude-desktop' | 'cursor' | 'vscode' | 'windsurf' | 'antigravity' | 'chatgpt' | 'custom';

export interface ClientInfo {
  id: ClientId;
  name: string;
  where: string;
  transport: 'http' | 'stdio' | 'either';
}

export const CLIENTS: ClientInfo[] = [
  { id: 'claude-code', name: 'Claude Code', where: 'Terminal', transport: 'either' },
  { id: 'claude-desktop', name: 'Claude Desktop', where: 'claude_desktop_config.json', transport: 'stdio' },
  { id: 'cursor', name: 'Cursor', where: '.cursor/mcp.json', transport: 'either' },
  { id: 'vscode', name: 'VS Code', where: '.vscode/mcp.json', transport: 'either' },
  { id: 'windsurf', name: 'Windsurf', where: '~/.codeium/windsurf/mcp_config.json', transport: 'either' },
  { id: 'antigravity', name: 'Antigravity', where: 'mcp_config.json', transport: 'either' },
  { id: 'chatgpt', name: 'ChatGPT / OpenAI Agents', where: 'Connector URL (HTTPS)', transport: 'http' },
  { id: 'custom', name: 'Any MCP client', where: 'URL or command', transport: 'either' },
];

export interface SetupInput {
  client: ClientId;
  transport: 'http' | 'stdio';
  url: string;
  repoPath: string;
}

export const DEFAULT_MCP_URL = 'http://localhost:8001/mcp';
export const DEFAULT_REPO = 'path/to/iFone';

const stdioCmd = (repo: string) => ({ command: 'python', args: [`${repo}/mcp/server.py`, '--stdio'] });

/** Ready-to-paste setup for one client. Text only: the UI never writes to the user's machine. */
export function setupSnippet(i: SetupInput): { file: string; lang: 'bash' | 'json'; body: string } {
  const info = CLIENTS.find((c) => c.id === i.client) ?? CLIENTS[CLIENTS.length - 1]!;
  const http = i.transport === 'http';
  if (i.client === 'claude-code') {
    return {
      file: 'Run in your project folder',
      lang: 'bash',
      body: http ? `claude mcp add --transport http quorum ${i.url}` : `claude mcp add quorum -- python ${i.repoPath}/mcp/server.py --stdio`,
    };
  }
  if (i.client === 'chatgpt') {
    return { file: 'Add as a connector. It must be reachable over HTTPS.', lang: 'bash', body: `Server URL:  ${i.url.replace('http://localhost', 'https://your-host')}\nTransport:   Streamable HTTP\nAuth:        none (pass your Quorum token as the token argument)` };
  }
  const entry = http ? { url: i.url } : stdioCmd(i.repoPath);
  const key = i.client === 'vscode' ? 'servers' : 'mcpServers';
  const body = JSON.stringify({ [key]: { quorum: i.client === 'vscode' && http ? { type: 'http', url: i.url } : entry } }, null, 2);
  return { file: info.where, lang: 'json', body };
}

/** Paste into the agent's rules so it uses the cheap paths first. */
export function agentRules(token: string, role: string): string {
  return [
    '# Quorum context rules',
    `Use the quorum MCP server for shared memory. Pass token="${token}" (${role}) on every call.`,
    '1. Read the map first: it tells you where things live. Do not load the whole graph.',
    '2. Call retrieve_context(query, k) with a small k. Ask again if you need more.',
    '3. Cite node ids (F3, C2) instead of repeating their text.',
    '4. Remember the epoch from each response. If it changes, call delta before acting.',
    '5. Record new knowledge with remember_fact or derive once, then reference its id.',
  ].join('\n');
}

export interface Probe {
  state: 'connected' | 'unreachable' | 'unexpected';
  latencyMs: number;
  detail: string;
}

/** Real reachability check against the MCP endpoint through the dev/preview proxy (live mode only). */
export async function probeMcp(path = '/mcp/'): Promise<Probe> {
  const t0 = performance.now();
  try {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json, text/event-stream' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-03-26', capabilities: {}, clientInfo: { name: 'quorum-console', version: '0.1.0' } } }),
      signal: AbortSignal.timeout(4000),
    });
    const latencyMs = Math.round(performance.now() - t0);
    if (res.ok) return { state: 'connected', latencyMs, detail: `HTTP ${res.status} from ${path}` };
    return { state: 'unexpected', latencyMs, detail: `HTTP ${res.status}. The server answered but did not accept the handshake.` };
  } catch (e) {
    return { state: 'unreachable', latencyMs: Math.round(performance.now() - t0), detail: e instanceof Error ? e.message : 'Network error' };
  }
}
