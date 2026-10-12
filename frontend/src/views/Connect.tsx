import { useEffect, useMemo, useState } from 'react';
import { API_MODE } from '../api/client';
import { Icon } from '../components/Icon';
import { fmt, pct } from '../context/tokens';
import { useStore } from '../state/store';
import { useLive, type Activity } from '../workspace/live';
import { copyText } from '../workspace/clipboard';
import { agentRules, CLIENTS, DEFAULT_MCP_URL, DEFAULT_REPO, MCP_TOOLS, setupSnippet, WHO_LABEL, type ClientId } from '../workspace/mcp';
import { useWorkspace } from '../workspace/store';

function ago(ts: number): string {
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (s < 5) return 'just now';
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  return `${Math.round(s / 3600)}h ago`;
}

const TONE: Record<string, string> = { connected: 'ok', simulated: 'warn', checking: 'neutral', unreachable: 'bad', unexpected: 'warn' };
const WORD: Record<string, string> = {
  connected: 'Connected',
  simulated: 'Sample data (simulated)',
  checking: 'Checking',
  unreachable: 'Not reachable',
  unexpected: 'Reachable, handshake refused',
};

function CopyBlock({ title, body, lang }: { title: string; body: string; lang?: string }) {
  const pushToast = useStore((s) => s.pushToast);
  return (
    <div className="cn-block">
      <div className="cn-block-h">
        <b>{title}</b>
        <span className="grow" />
        <button
          className="btn quiet"
          onClick={() => void copyText(body).then((ok) => pushToast(ok ? 'Copied' : 'Copy was blocked by the browser', ok ? 'good' : 'warn'))}
        >
          <Icon name="copy" size={14} /> Copy
        </button>
      </div>
      <pre className="terminal mono" data-lang={lang}>
        {body}
      </pre>
    </div>
  );
}

function Status() {
  const mcp = useLive((s) => s.mcp);
  const check = useLive((s) => s.checkMcp);
  const [url, setUrl] = useState(DEFAULT_MCP_URL);
  return (
    <section className="card wide cn-status" aria-label="MCP server status">
      <div className={`cn-light ${TONE[mcp.state]}`} aria-hidden="true" />
      <div className="cn-status-main">
        <h2>
          Quorum MCP server: <span className={`${TONE[mcp.state]}-text`}>{WORD[mcp.state]}</span>
        </h2>
        <p className="muted" role="status" aria-live="polite">
          {mcp.detail}
          {mcp.checkedAt > 0 && <> Checked {ago(mcp.checkedAt)}.</>}
        </p>
        {mcp.state === 'unreachable' && (
          <p className="cn-help">
            Start the backend with <code>docker compose up -d</code> (MCP is served from it at /mcp), then press Test connection.
          </p>
        )}
        {API_MODE === 'mock' && <p className="cn-help">This console is running on sample data, so nothing here talks to a real server. Switch to live mode to run the real handshake.</p>}
      </div>
      <dl className="cn-facts">
        <div>
          <dt>Endpoint</dt>
          <dd>
            <input className="cn-url mono" value={url} onChange={(e) => setUrl(e.target.value)} aria-label="MCP endpoint URL" spellCheck={false} />
          </dd>
        </div>
        <div>
          <dt>Latency</dt>
          <dd className="num">{mcp.state === 'unreachable' || mcp.state === 'checking' ? '—' : `${mcp.latencyMs} ms`}</dd>
        </div>
        <div>
          <dt>Tools</dt>
          <dd className="num">{MCP_TOOLS.filter((t) => !t.proposed).length} live</dd>
        </div>
      </dl>
      <button className="btn primary" onClick={() => void check()} disabled={mcp.state === 'checking'}>
        <Icon name="refresh" size={14} /> Test connection
      </button>
    </section>
  );
}

function Setup() {
  const members = useWorkspace((s) => s.w.members);
  const [client, setClient] = useState<ClientId>('claude-code');
  const [transport, setTransport] = useState<'http' | 'stdio'>('http');
  const [memberId, setMemberId] = useState(members[0]?.id ?? '');
  const [repo, setRepo] = useState(DEFAULT_REPO);
  const info = CLIENTS.find((c) => c.id === client)!;
  const tr = info.transport === 'http' ? 'http' : info.transport === 'stdio' ? 'stdio' : transport;
  const member = members.find((m) => m.id === memberId) ?? members[0];
  const snip = setupSnippet({ client, transport: tr, url: DEFAULT_MCP_URL, repoPath: repo });
  return (
    <section className="card wide" aria-label="Connect your AI">
      <header className="card-h">
        <h2>Connect your AI in three steps</h2>
        <span className="card-sub">Works with any MCP client</span>
      </header>
      <ol className="cn-steps">
        <li>
          <b>1. Start the server.</b> <span className="muted">Run it once per workspace.</span>
          <code className="cn-cmd mono">docker compose up</code>
        </li>
        <li>
          <b>2. Paste this into your client.</b> <span className="muted">Pick yours:</span>
          <div className="cn-clients" role="radiogroup" aria-label="AI client">
            {CLIENTS.map((c) => (
              <button key={c.id} role="radio" aria-checked={client === c.id} className={`cn-client${client === c.id ? ' on' : ''}`} onClick={() => setClient(c.id)}>
                {c.name}
              </button>
            ))}
          </div>
          <div className="cn-opts">
            {info.transport === 'either' && (
              <div className="seg" role="group" aria-label="Transport">
                {(['http', 'stdio'] as const).map((t) => (
                  <button key={t} className={`seg-btn${transport === t ? ' on' : ''}`} aria-pressed={transport === t} onClick={() => setTransport(t)}>
                    {t === 'http' ? 'HTTP (shared server)' : 'stdio (this laptop)'}
                  </button>
                ))}
              </div>
            )}
            {tr === 'stdio' && (
              <label className="field inline">
                <span>Path to the repo</span>
                <input value={repo} onChange={(e) => setRepo(e.target.value)} spellCheck={false} />
              </label>
            )}
          </div>
          <CopyBlock title={snip.file} body={snip.body} lang={snip.lang} />
        </li>
        <li>
          <b>3. Give the agent its rules and token.</b> <span className="muted">The tools take your token as an argument, so tell the agent which one.</span>
          <label className="field inline">
            <span>Member</span>
            <select value={member?.id ?? ''} onChange={(e) => setMemberId(e.target.value)}>
              {members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} · {m.role}
                </option>
              ))}
            </select>
          </label>
          {member ? <CopyBlock title="Paste into the agent's rules (CLAUDE.md, .cursorrules, system prompt)" body={agentRules(member.token, member.role)} /> : <p className="muted">Add a member on the Team page first.</p>}
        </li>
      </ol>
    </section>
  );
}

function Tools() {
  return (
    <section className="card wide" aria-label="MCP tools">
      <header className="card-h">
        <h2>Tools your agent gets</h2>
        <span className="card-sub">
          {MCP_TOOLS.filter((t) => !t.proposed).length} live, {MCP_TOOLS.filter((t) => t.proposed).length} proposed token savers
        </span>
      </header>
      <div className="cn-table-wrap">
        <table className="cn-table">
          <thead>
            <tr>
              <th scope="col">Tool</th>
              <th scope="col">What it does</th>
              <th scope="col">Who can call it</th>
              <th scope="col">How it saves tokens</th>
            </tr>
          </thead>
          <tbody>
            {MCP_TOOLS.map((t) => (
              <tr key={t.name} className={t.proposed ? 'proposed' : ''}>
                <th scope="row" className="mono">
                  {t.name}
                  {t.proposed && <em className="cn-tag">proposed</em>}
                </th>
                <td>
                  {t.summary}
                  <small className="muted mono">{t.args}</small>
                </td>
                <td>
                  <span className={`cn-role ${t.who}`}>{WHO_LABEL[t.who]}</span>
                  <small className="muted">{t.writes ? 'Writes' : 'Read only'}</small>
                </td>
                <td>{t.saves}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Row({ a }: { a: Activity }) {
  const saved = a.naive > 0 ? a.naive - a.used : 0;
  return (
    <li className="cn-row">
      <span className="avatar">{a.member.slice(0, 1)}</span>
      <div className="cn-row-main">
        <p>
          <b>{a.member}</b> <code className="cn-tool mono">{a.tool}</code>
          {a.via && <em className="cn-tag">via {a.via}</em>}
        </p>
        <small className="muted">{a.summary}</small>
      </div>
      <div className="cn-row-tok num" title="Tokens the agent received, and what a notes-style memory would have sent">
        {a.naive > 0 ? (
          <>
            <b>{fmt(a.used)}</b> <s className="muted">{fmt(a.naive)}</s>
            <small className="ok-text">−{pct(saved, a.naive)}%</small>
          </>
        ) : (
          <small className="muted">{fmt(a.used)} tok</small>
        )}
      </div>
      <time className="muted small">{ago(a.ts)}</time>
    </li>
  );
}

function Feeds() {
  const activity = useLive((s) => s.activity);
  const chats = useLive((s) => s.chats);
  const presence = useLive((s) => s.presence);
  const clear = useLive((s) => s.clear);
  const members = useWorkspace((s) => s.w.members);
  const [tab, setTab] = useState<'feed' | 'chats'>('feed');
  const [who, setWho] = useState('all');
  const [tool, setTool] = useState('all');
  const [paused, setPaused] = useState(false);
  const [frozen, setFrozen] = useState<Activity[]>([]);
  const [chatId, setChatId] = useState(members[0]?.id ?? '');
  const [, tick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => tick((n) => n + 1), 5000);
    return () => clearInterval(t);
  }, []);

  const source = paused ? frozen : activity;
  const rows = useMemo(() => source.filter((a) => (who === 'all' || a.memberId === who) && (tool === 'all' || a.tool === tool)), [source, who, tool]);
  const turns = chats[chatId] ?? [];
  const m = members.find((x) => x.id === chatId);

  return (
    <section className="card wide cn-feeds" aria-label="Live activity and chats">
      <header className="card-h">
        <div className="seg" role="tablist" aria-label="Activity">
          <button role="tab" aria-selected={tab === 'feed'} className={`seg-btn${tab === 'feed' ? ' on' : ''}`} onClick={() => setTab('feed')}>
            Live feed
          </button>
          <button role="tab" aria-selected={tab === 'chats'} className={`seg-btn${tab === 'chats' ? ' on' : ''}`} onClick={() => setTab('chats')}>
            Chats
          </button>
        </div>
        <span className="chip warn" title="Real activity needs the workspace service. This is generated in your browser from the real packer.">
          Simulated activity
        </span>
      </header>

      {tab === 'feed' ? (
        <>
          <div className="cn-filters">
            <label className="field inline">
              <span>Member</span>
              <select value={who} onChange={(e) => setWho(e.target.value)}>
                <option value="all">Everyone</option>
                {members.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field inline">
              <span>Tool</span>
              <select value={tool} onChange={(e) => setTool(e.target.value)}>
                <option value="all">All tools</option>
                {[...MCP_TOOLS.filter((t) => !t.proposed).map((t) => t.name), 'delta'].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <span className="grow" />
            <button
              className="btn quiet"
              aria-pressed={paused}
              onClick={() => {
                setFrozen(activity);
                setPaused((p) => !p);
              }}
            >
              <Icon name={paused ? 'play' : 'pause'} size={13} /> {paused ? 'Resume' : 'Pause'}
            </button>
            <button className="btn quiet" onClick={clear}>
              Clear
            </button>
          </div>
          {rows.length ? (
            <ul className="cn-list" aria-live={paused ? 'off' : 'polite'} aria-relevant="additions">
              {rows.slice(0, 60).map((a) => (
                <Row key={a.id} a={a} />
              ))}
            </ul>
          ) : (
            <p className="muted cn-empty">Nothing yet. Calls from connected agents appear here as they happen.</p>
          )}
        </>
      ) : (
        <div className="cn-chats">
          <ul className="cn-people" aria-label="Members">
            {members.map((x) => (
              <li key={x.id}>
                <button className={chatId === x.id ? 'on' : ''} onClick={() => setChatId(x.id)}>
                  <span className={`pres ${presence[x.id] ?? 'offline'}`} aria-label={presence[x.id] ?? 'offline'} />
                  <span>
                    {x.name}
                    <small className="muted">{CLIENTS.find((c) => c.id === x.client)?.name}</small>
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <div className="cn-thread" aria-label={`Conversation with ${m?.name ?? 'nobody'}`}>
            {turns.length ? (
              turns.map((t) => (
                <div key={t.id} className={`cn-turn ${t.from}`}>
                  <small className="muted">{t.from === 'user' ? m?.name : t.from === 'tool' ? 'Quorum MCP' : 'Assistant'}</small>
                  <p className={t.from === 'tool' ? 'mono' : ''}>{t.text}</p>
                  {t.tokens !== undefined && <small className="num ok-text">{fmt(t.tokens)} tokens sent</small>}
                </div>
              ))
            ) : (
              <p className="muted cn-empty">No conversation from {m?.name ?? 'this member'} yet. Sessions show the question, the MCP call and how many tokens it cost.</p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

const GROUPS = ['all', 'graph', 'actions', 'handoffs', 'system'] as const;

/** Live mode: the real event stream from the backend, not a simulation. */
function BackendFeed() {
  const feed = useStore((s) => s.feed);
  const conn = useStore((s) => s.conn);
  const [group, setGroup] = useState<(typeof GROUPS)[number]>('all');
  const rows = feed.filter((f) => group === 'all' || f.group === group);
  return (
    <section className="card wide cn-feeds" aria-label="Live activity from the backend">
      <header className="card-h">
        <h2>Live feed</h2>
        <span className="chip" title="Every event the backend streams to this console, including writes made by agents over MCP">
          From the backend · stream {conn}
        </span>
      </header>
      <div className="cn-filters" role="group" aria-label="Event type">
        {GROUPS.map((g) => (
          <button key={g} className={`cn-client${group === g ? ' on' : ''}`} aria-pressed={group === g} onClick={() => setGroup(g)}>
            {g}
          </button>
        ))}
      </div>
      {rows.length ? (
        <ul className="cn-list" aria-live="polite" aria-relevant="additions">
          {rows.slice(0, 80).map((f) => (
            <li key={f.id} className="cn-row">
              <span className={`avatar tone-${f.tone}`}>{f.group[0]?.toUpperCase()}</span>
              <div className="cn-row-main">
                <p>{f.text}</p>
                <small className="muted">{f.group} · event {f.seq}</small>
              </div>
              <span />
              <time className="muted small">{ago(f.ts)}</time>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted cn-empty">Nothing yet. Writes from agents, scenario steps and handoffs appear here as they happen.</p>
      )}
      <p className="cn-help">Per-agent chats and presence need the workspace service, which the backend does not have yet (docs/CONTRACT_PROPOSALS.md).</p>
    </section>
  );
}

export function Connect() {
  return (
    <div className="page cn">
      <header className="page-head">
        <p className="page-tag">
          <span>[07]</span> Connect
        </p>
        <h1>Plug any AI into one memory</h1>
        <p>Run one MCP server, paste a snippet into Claude, Cursor, VS Code or anything else that speaks MCP, and every agent reads and writes the same graph.</p>
      </header>
      <Status />
      <Setup />
      {API_MODE === 'mock' ? <Feeds /> : <BackendFeed />}
      <Tools />
    </div>
  );
}
