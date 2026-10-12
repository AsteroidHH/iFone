import { useMemo, useState } from 'react';
import { Icon } from '../components/Icon';
import { fmt } from '../context/tokens';
import { useStore } from '../state/store';
import { useLive } from '../workspace/live';
import { copyText } from '../workspace/clipboard';
import { CLIENTS, type ClientId } from '../workspace/mcp';
import { meshGroups, PLANS, seatsLimit, seatsUsed, useWorkspace, type MemberRole, type Plan, type Scope } from '../workspace/store';

const ROLE_HELP: Record<MemberRole, string> = {
  agent: 'Reads and writes memory, stages actions',
  auditor: 'Can quarantine and restore facts',
  human: 'Approves gate-blocked reviews',
};

function Org() {
  const w = useWorkspace((s) => s.w);
  const { rename, setPlan, setHub, reset } = useWorkspace.getState();
  const used = seatsUsed(w);
  const limit = seatsLimit(w);
  const pushToast = useStore((s) => s.pushToast);
  return (
    <section className="card wide tm-org" aria-label="Workspace">
      <label className="field">
        <span>Company</span>
        <input defaultValue={w.org} onBlur={(e) => rename(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()} />
      </label>
      <label className="field">
        <span>Plan</span>
        <select value={w.plan} onChange={(e) => setPlan(e.target.value as Plan)}>
          {(Object.keys(PLANS) as Plan[]).map((p) => (
            <option key={p} value={p}>
              {PLANS[p].label}: up to {PLANS[p].seats} seats, {PLANS[p].teams} teams
            </option>
          ))}
        </select>
      </label>
      <div className="tm-seats" aria-label={`${used} of ${limit} seats used`}>
        <div className="tm-seats-top">
          <span>Seats</span>
          <b className="num">
            {used} / {limit}
          </b>
        </div>
        <div className="ctx-track" aria-hidden="true">
          <i className={used >= limit ? 'bad' : 'ok'} style={{ width: `${Math.min(100, (used / limit) * 100)}%` }} />
        </div>
        <small className="muted">{PLANS[w.plan].note}</small>
      </div>
      <label className="field grow">
        <span>Workspace hub (where laptops meet)</span>
        <input defaultValue={w.hub} onBlur={(e) => setHub(e.target.value.trim())} spellCheck={false} />
      </label>
      <button
        className="btn quiet"
        onClick={() => {
          reset();
          pushToast('Workspace reset to the sample');
        }}
      >
        Reset sample
      </button>
    </section>
  );
}

function Teams() {
  const w = useWorkspace((s) => s.w);
  const { addTeam, setSeats, removeTeam } = useWorkspace.getState();
  const [name, setName] = useState('');
  const [seats, setSeatsN] = useState(5);
  const [err, setErr] = useState<string | null>(null);
  return (
    <section className="card wide" aria-label="Teams">
      <header className="card-h">
        <h2>Teams</h2>
        <span className="card-sub">
          {w.teams.length} of {PLANS[w.plan].teams}
        </span>
      </header>
      <ul className="tm-teams">
        {w.teams.map((t) => {
          const n = w.members.filter((m) => m.teamId === t.id).length;
          return (
            <li key={t.id} className="tm-team">
              <div>
                <b>{t.name}</b>
                <small className="muted num">
                  {n} of {t.seats} seats
                </small>
              </div>
              <div className="tm-stepper" role="group" aria-label={`${t.name} seats`}>
                <button aria-label={`Fewer seats for ${t.name}`} disabled={t.seats <= Math.max(1, n)} onClick={() => setSeats(t.id, t.seats - 1)}>
                  −
                </button>
                <span className="num">{t.seats}</span>
                <button aria-label={`More seats for ${t.name}`} onClick={() => setSeats(t.id, t.seats + 1)}>
                  +
                </button>
              </div>
              <button
                className="btn quiet"
                onClick={() => {
                  if (n === 0 || window.confirm(`Remove ${t.name} and its ${n} members?`)) removeTeam(t.id);
                }}
              >
                Remove
              </button>
            </li>
          );
        })}
      </ul>
      <form
        className="tm-form"
        onSubmit={(e) => {
          e.preventDefault();
          const r = addTeam(name, seats);
          setErr(r);
          if (!r) setName('');
        }}
      >
        <label className="field grow">
          <span>New team</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Customer success" />
        </label>
        <label className="field narrow">
          <span>Seats</span>
          <input type="number" min={1} max={200} value={seats} onChange={(e) => setSeatsN(Number(e.target.value) || 1)} />
        </label>
        <button className="btn primary">Add team</button>
      </form>
      <p className="tm-err" role="alert">
        {err}
      </p>
    </section>
  );
}

function Members() {
  const w = useWorkspace((s) => s.w);
  const { addMember, removeMember, rotateToken } = useWorkspace.getState();
  const presence = useLive((s) => s.presence);
  const per = useLive((s) => s.perMember);
  const set = useStore((s) => s.set);
  const pushToast = useStore((s) => s.pushToast);
  const [name, setName] = useState('');
  const [role, setRole] = useState<MemberRole>('agent');
  const [teamId, setTeamId] = useState(w.teams[0]?.id ?? '');
  const [client, setClient] = useState<ClientId>('claude-code');
  const [device, setDevice] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [shown, setShown] = useState<string | null>(null);
  const team = (id: string) => w.teams.find((t) => t.id === id)?.name ?? '—';

  return (
    <section className="card wide" aria-label="Members">
      <header className="card-h">
        <h2>Members and their AIs</h2>
        <span className="card-sub">Each person connects their own laptop and AI with their own token</span>
      </header>
      <div className="cn-table-wrap">
        <table className="cn-table tm-table">
          <thead>
            <tr>
              <th scope="col">Member</th>
              <th scope="col">Team</th>
              <th scope="col">AI client</th>
              <th scope="col">Status</th>
              <th scope="col">Calls</th>
              <th scope="col">Tokens saved</th>
              <th scope="col">Token</th>
              <th scope="col">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {w.members.map((m) => {
              const p = presence[m.id] ?? 'offline';
              const pm = per[m.id];
              return (
                <tr key={m.id}>
                  <th scope="row">
                    <div className="tm-who">
                      <span className="avatar">{m.name.slice(0, 1)}</span>
                      <span>{m.name}</span>
                      <small className="muted">
                        {m.role} · {m.device}
                      </small>
                    </div>
                  </th>
                  <td>{team(m.teamId)}</td>
                  <td>{CLIENTS.find((c) => c.id === m.client)?.name}</td>
                  <td>
                    <span className={`pres ${p}`} aria-hidden="true" /> {p}
                  </td>
                  <td className="num">{pm ? fmt(pm.calls) : '0'}</td>
                  <td className="num">{pm ? fmt(Math.max(0, pm.naive - pm.used)) : '0'}</td>
                  <td>
                    <code className="mono tm-token">{shown === m.id ? m.token : `${m.token.slice(0, 8)}••••••`}</code>
                    <button className="btn quiet" aria-label={`${shown === m.id ? 'Hide' : 'Show'} ${m.name}'s token`} onClick={() => setShown(shown === m.id ? null : m.id)}>
                      {shown === m.id ? 'Hide' : 'Show'}
                    </button>
                    <button className="btn quiet" aria-label={`Copy ${m.name}'s invite link`} onClick={() => void copyText(`${w.hub}/join?token=${m.token}`).then((ok) => pushToast(ok ? 'Invite link copied' : 'Copy was blocked', ok ? 'good' : 'warn'))}>
                      <Icon name="link" size={13} /> Invite
                    </button>
                  </td>
                  <td className="tm-actions">
                    <button className="btn quiet" onClick={() => set({ view: 'connect' })}>
                      Set up
                    </button>
                    <button className="btn quiet" onClick={() => rotateToken(m.id)}>
                      Rotate
                    </button>
                    <button className="btn quiet" onClick={() => removeMember(m.id)}>
                      Remove
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <form
        className="tm-form"
        onSubmit={(e) => {
          e.preventDefault();
          const r = addMember({ name, role, teamId, client, device: device.trim() || `${name.trim()}'s laptop` });
          setErr(r);
          if (!r) {
            setName('');
            setDevice('');
          }
        }}
      >
        <label className="field">
          <span>Name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Priya" />
        </label>
        <label className="field">
          <span>Team</span>
          <select value={teamId} onChange={(e) => setTeamId(e.target.value)}>
            {w.teams.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Role</span>
          <select value={role} onChange={(e) => setRole(e.target.value as MemberRole)}>
            {(Object.keys(ROLE_HELP) as MemberRole[]).map((r) => (
              <option key={r} value={r}>
                {r}: {ROLE_HELP[r]}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Their AI</span>
          <select value={client} onChange={(e) => setClient(e.target.value as ClientId)}>
            {CLIENTS.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <button className="btn primary">Add member</button>
      </form>
      <p className="tm-err" role="alert">
        {err}
      </p>
    </section>
  );
}

function Mesh() {
  const w = useWorkspace((s) => s.w);
  const { link, unlink, pauseLink } = useWorkspace.getState();
  const presence = useLive((s) => s.presence);
  const [a, setA] = useState('');
  const [b, setB] = useState('');
  const [scope, setScope] = useState<Scope>('team');
  const [err, setErr] = useState<string | null>(null);
  const groups = useMemo(() => meshGroups(w), [w]);
  const gOf = new Map<string, number>();
  groups.forEach((g, i) => g.forEach((id) => gOf.set(id, i)));
  const n = w.members.length;
  const R = 112;
  const pos = new Map(w.members.map((m, i) => [m.id, { x: 160 + R * Math.cos((i / Math.max(1, n)) * Math.PI * 2 - Math.PI / 2), y: 140 + R * Math.sin((i / Math.max(1, n)) * Math.PI * 2 - Math.PI / 2) }]));
  const name = (id: string) => w.members.find((m) => m.id === id)?.name ?? id;
  const shared = groups.filter((g) => g.length > 1);

  return (
    <section className="card wide" aria-label="Share context between members">
      <header className="card-h">
        <h2>Link members so their AIs share context</h2>
        <span className="chip warn" title="The workspace service is not in the backend yet. Links are saved in this browser. See docs/CONTRACT_PROPOSALS.md.">
          Preview
        </span>
      </header>
      <div className="tm-mesh">
        <svg viewBox="0 0 320 300" role="img" aria-label={`Mesh of ${n} members with ${w.links.length} links`}>
          {w.links.map((l) => {
            const p = pos.get(l.a);
            const q = pos.get(l.b);
            if (!p || !q) return null;
            return <line key={l.id} x1={p.x} y1={p.y} x2={q.x} y2={q.y} className={`tm-edge${l.paused ? ' paused' : ''} ${l.scope}`} />;
          })}
          {w.members.map((m) => {
            const p = pos.get(m.id)!;
            const st = presence[m.id] ?? 'offline';
            return (
              <g key={m.id} transform={`translate(${p.x} ${p.y})`}>
                <circle r="19" className={`tm-n g${(gOf.get(m.id) ?? 0) % 4}`} />
                <text y="5" textAnchor="middle" className="tm-n-t">
                  {m.name.slice(0, 1)}
                </text>
                <circle cx="14" cy="-14" r="5" className={`tm-pres ${st}`} />
                <text y="34" textAnchor="middle" className="tm-n-l">
                  {m.name}
                </text>
              </g>
            );
          })}
        </svg>
        <div className="tm-mesh-side">
          <p className="tm-sum" role="status">
            {shared.length ? (
              <>
                {shared.map((g) => g.map(name).join(', ')).join(' · ')} <span className="muted">share context through {w.links.filter((l) => !l.paused).length} active link(s).</span>
              </>
            ) : (
              'No one is linked yet. Link two members and their AIs will receive each other’s changes as cheap deltas, even from different laptops.'
            )}
          </p>
          <ul className="tm-links">
            {w.links.map((l) => (
              <li key={l.id}>
                <span>
                  <b>{name(l.a)}</b> ⇄ <b>{name(l.b)}</b> <small className="muted">{l.scope === 'commons' ? 'all shared memory' : 'team scope only'}</small>
                </span>
                <button className="btn quiet" aria-pressed={l.paused} onClick={() => pauseLink(l.id)}>
                  {l.paused ? 'Resume' : 'Pause'}
                </button>
                <button className="btn quiet" onClick={() => unlink(l.id)}>
                  Unlink
                </button>
              </li>
            ))}
          </ul>
          <form
            className="tm-form tight"
            onSubmit={(e) => {
              e.preventDefault();
              setErr(link(a, b, scope));
            }}
          >
            <label className="field">
              <span>From</span>
              <select value={a} onChange={(e) => setA(e.target.value)}>
                <option value="">Pick…</option>
                {w.members.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>To</span>
              <select value={b} onChange={(e) => setB(e.target.value)}>
                <option value="">Pick…</option>
                {w.members.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Share</span>
              <select value={scope} onChange={(e) => setScope(e.target.value as Scope)}>
                <option value="team">Team scope</option>
                <option value="commons">Everything</option>
              </select>
            </label>
            <button className="btn primary">Link</button>
          </form>
          <p className="tm-err" role="alert">
            {err}
          </p>
        </div>
      </div>
    </section>
  );
}

export function Team() {
  return (
    <div className="page tm">
      <header className="page-head">
        <p className="page-tag">
          <span>[08]</span> Team
        </p>
        <h1>One company, many teams, many AIs</h1>
        <p>Choose a plan, split people into teams, give each person their own token and AI, then link their MCP servers so context flows between laptops without anyone pasting anything.</p>
      </header>
      <Org />
      <Teams />
      <Members />
      <Mesh />
    </div>
  );
}
