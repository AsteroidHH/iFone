/**
 * End-to-end check of the console against a LIVE backend, with a real MCP client acting as an outside agent.
 *
 *   Needs: backend on :8000 started with QUORUM_EMBED_MCP=1 (so MCP and the API share one graph),
 *          the console built with VITE_API_MODE=live and served on BASE (default http://127.0.0.1:5174)
 *          with a config.json holding the demo tokens (see docs/LIVE_TESTING.md).
 *
 *   node scripts/live.mjs [BASE] [API]
 */
import { chromium } from 'playwright-core';

const BASE = process.argv[2] ?? 'http://127.0.0.1:5174';
const API = process.argv[3] ?? 'http://127.0.0.1:8000';
const results = [];
const check = (name, ok, extra = '') => {
  results.push({ name, ok });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${extra ? `  ${extra}` : ''}`);
};
const human = { Authorization: 'Bearer token_human' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ---- a tiny MCP client over streamable HTTP, standing in for Claude Code / Cursor ---- */
let sid = null;
let rid = 0;
async function rpc(method, params, notify = false) {
  const body = { jsonrpc: '2.0', method, ...(params ? { params } : {}), ...(notify ? {} : { id: ++rid }) };
  const res = await fetch(`${API}/mcp`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', accept: 'application/json, text/event-stream', ...(sid ? { 'mcp-session-id': sid } : {}) },
    body: JSON.stringify(body),
  });
  sid = res.headers.get('mcp-session-id') ?? sid;
  if (notify) return null;
  const text = await res.text();
  const line = text.split('\n').find((l) => l.startsWith('data:'));
  return JSON.parse(line ? line.slice(5) : text);
}
async function tool(name, args) {
  const out = await rpc('tools/call', { name, arguments: args });
  const t = out.result?.content?.[0]?.text ?? '{}';
  try {
    return JSON.parse(t);
  } catch {
    return { raw: t };
  }
}

await fetch(`${API}/api/scenario/reset`, { method: 'POST', headers: human });
await sleep(1200);

const browser = await chromium.launch({ channel: 'msedge' });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const problems = [];
page.on('pageerror', (e) => problems.push(`pageerror ${e}`));
page.on('console', (m) => m.type() === 'error' && !/Failed to load resource/.test(m.text()) && problems.push(`console ${m.text()}`));
const bad = [];
page.on('response', (r) => r.status() >= 400 && !r.url().includes('/mcp') && bad.push(`${r.status()} ${r.url().replace(BASE, '')}`));

const btn = (n) => page.getByRole('button', { name: n });
const text = (sel) => page.locator(sel).first().innerText();
const waitEnabled = async (n, ms = 30000) => {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    if (await btn(n).first().isEnabled().catch(() => false)) return true;
    await sleep(300);
  }
  return false;
};

await page.goto(`${BASE}/#/app`);
await page.locator('.story-btn').first().waitFor({ timeout: 10000 });
await sleep(1500);

/* ---- live mode, not sample mode ---- */
check('no sample-data chip in live mode', (await page.locator('.pill.sample').count()) === 0);
check('event stream connected', (await page.locator('.pill.conn.live').count()) === 1);
check('header does not claim simulated savings in live mode', (await page.locator('.pill.saved').count()) === 0);

/* ---- Connect page: real handshake with the real server ---- */
await page.keyboard.press('7');
await page.locator('.cn-status').waitFor({ timeout: 4000 });
await sleep(1500);
const status = await text('.cn-status');
check('MCP status is a real, connected handshake', status.includes('Connected') && !status.includes('simulated'), status.split('\n')[0]);
check('live feed is labelled as coming from the backend, not simulated', !(await page.locator('.cn-feeds .chip.warn', { hasText: 'Simulated' }).count()));

/* ---- an outside agent over MCP ---- */
await rpc('initialize', { protocolVersion: '2025-03-26', capabilities: {}, clientInfo: { name: 'live-qa', version: '1' } });
await rpc('notifications/initialized', undefined, true);
const listed = (await rpc('tools/list', {})).result.tools.map((t) => t.name);
check('MCP server lists the ten tools', listed.length === 10 && listed.includes('retrieve_context'), listed.join(','));
await page.keyboard.press('1');
await sleep(500);
await page.getByRole('button', { name: 'List view' }).click();
const wrote = await tool('remember_fact', { key: 'qa_window', value: '45', text: 'QA agent says the refund window is 45 days', token: 'token_agent_scout', id: 'fact_qa_mcp' });
check('agent can write a fact over MCP', wrote.fact_id === 'fact_qa_mcp', JSON.stringify(wrote).slice(0, 80));
await sleep(2500);
check('that fact appears in the console without a reload', (await page.locator('.list-row', { hasText: 'QA agent says' }).count()) > 0);
const got = await tool('retrieve_context', { query: 'refund window days', token: 'token_agent_scout', k: 5 });
check('agent can read it back with retrieve_context', JSON.stringify(got).includes('fact_qa_mcp'));
const blocked = await tool('quarantine', { root_id: 'fact_qa_mcp', token: 'token_agent_scout' });
check('an agent token cannot quarantine', blocked.success === false, blocked.error ?? '');
const q = await tool('quarantine', { root_id: 'fact_qa_mcp', token: 'token_auditor' });
check('an auditor token can quarantine', q.success === true);
await sleep(2500);
const afterQ = await tool('retrieve_context', { query: 'QA agent refund window', token: 'token_agent_scout', k: 5 });
check('retrieval no longer returns the quarantined fact', !JSON.stringify(afterQ).includes('fact_qa_mcp'));
check('console shows the quarantine', (await page.locator('.list-row', { hasText: 'QA agent says' }).first().innerText()).toLowerCase().includes('quarantined'));
await fetch(`${API}/api/scenario/reset`, { method: 'POST', headers: human });
await sleep(2500);

/* ---- the 90-second story against the real backend and real agents ---- */
for (const step of ['Inject poisoned webhook', 'Run agents', 'Audit memory', 'Replace policy']) {
  const ok = await waitEnabled(step);
  check(`step enabled in order: ${step}`, ok);
  if (!ok) break;
  await btn(step).first().click();
  await sleep(2500);
}
await sleep(1500);
const feed = await text('.feed');
check('feed shows the quarantine and the replacement', feed.includes('Quarantined') && feed.includes('Replaced'), feed.replace(/\s+/g, ' ').slice(0, 90));
check('scenario is not stuck running', !(await text('.progress')).toLowerCase().includes('running'));
check('no "Out of sync" loop', !(await page.locator('.banner, .blocking').allInnerTexts()).join(' ').includes('Out of sync'));

await page.getByRole('tab', { name: 'Insights' }).click();
await sleep(600);
check('Insights counts quarantined nodes from the real graph', Number((await text('.ins-kpi.bad')).match(/\d+/)?.[0] ?? 0) > 0);
await page.getByRole('tab', { name: 'Prompt diff' }).click();
await sleep(1200);
check('Prompt diff renders the before/after from the backend', (await page.locator('.belief-diff, .diff').count()) > 0);
await page.getByRole('tab', { name: /Actions and handoffs/ }).click();
await sleep(1200);
check('Actions and handoffs lists real handoffs', (await page.locator('.ledger, .handoff, .board li').count()) > 0);
await page.getByRole('tab', { name: 'Graph' }).click();

/* ---- the other views, on real data ---- */
await page.keyboard.press('2');
await sleep(1500);
check('Memory lists the real agents', (await page.locator('.agent-list li').count()) >= 3);
await page.keyboard.press('3');
await sleep(800);
await page.locator('#ask-q').fill('What is the refund window?');
await page.locator('.askform .btn.primary').click();
await sleep(2500);
check('Company brain answers or refuses with a trace', (await text('.page')).length > 300);
await page.keyboard.press('4');
await sleep(1500);
check('Tenants shows the isolation result', /denied/i.test(await text('.page')));
await page.keyboard.press('5');
await sleep(1500);
check('Benchmark shows recorded results', /ops|p99|ms/i.test(await text('.page')));
await page.keyboard.press('6');
await sleep(1500);
check('Context page works on the live graph', /\d+/.test(await text('.ctx-pct')));
await page.keyboard.press('8');
await sleep(800);
check('Team page renders', (await page.locator('.tm-table tbody tr').count()) > 0);

/* ---- health ---- */
await page.getByText('Dev console').click();
await sleep(400);
const dev = await text('.dev-drawer');
check('dev console has no validation failures', !/failed validation/.test(dev), dev.split('\n').filter((l) => /failed validation/.test(l)).join(' | '));
check('no failed requests other than MCP probes', bad.length === 0, bad.join(', '));

await browser.close();
const failed = results.filter((r) => !r.ok);
if (problems.length) console.error('PROBLEMS:\n' + problems.join('\n'));
console.log(`\n${results.length - failed.length}/${results.length} live checks passed, ${problems.length} console problems`);
process.exit(failed.length || problems.length ? 1 : 0);
