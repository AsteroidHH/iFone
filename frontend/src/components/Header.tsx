import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { tenants } from '../api/client';
import { copy } from '../copy';
import { getInvariants } from '../state/endpoints';
import { switchTenant } from '../state/pipeline';
import { useStore, type View } from '../state/store';
import { Skeleton } from './ui';

const VIEWS: View[] = ['console', 'memory', 'brain', 'tenants', 'benchmark'];

function EpochBadge() {
  const epoch = useStore((s) => s.epoch);
  const [pulse, setPulse] = useState(false);
  const prev = useRef(epoch);
  useEffect(() => {
    if (prev.current !== epoch && prev.current !== 0) {
      setPulse(true);
      const t = setTimeout(() => setPulse(false), 1400);
      prev.current = epoch;
      return () => clearTimeout(t);
    }
    prev.current = epoch;
  }, [epoch]);
  return (
    <span className={`badge epoch${pulse ? ' pulse' : ''}`} title="Increments on every quarantine, restore and replacement">
      {copy.epoch(epoch)}
    </span>
  );
}

function InvariantLight() {
  const inv = useStore((s) => s.invariant);
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: ['invariants'], queryFn: getInvariants, enabled: open });
  const state = inv ? (inv.ok ? 'ok' : 'bad') : 'unknown';
  const text = inv ? (inv.ok ? copy.invariants.ok : copy.invariants.bad(inv.violations)) : copy.invariants.unknown;
  return (
    <div className="pop-wrap">
      <button className={`badge light ${state}`} aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="dot" aria-hidden="true" />
        {text}
      </button>
      {open && (
        <div className="popover" role="dialog" aria-label="Invariant checks">
          {q.isLoading && <Skeleton lines={3} />}
          {q.isError && <p className="muted">{copy.errors.panel('GET /invariants')}</p>}
          {q.data && (
            <ul className="checks">
              {q.data.checks.map((c) => (
                <li key={c.name}>
                  <span className={`dot ${c.ok ? 'ok' : 'bad'}`} aria-hidden="true" />
                  <span>{c.name}</span>
                  <span className="num">{c.value}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

export function Header() {
  const view = useStore((s) => s.view);
  const set = useStore((s) => s.set);
  const meta = useStore((s) => s.meta);
  const conn = useStore((s) => s.conn);
  const tenant = useStore((s) => s.tenant);
  const presentation = useStore((s) => s.presentation);
  const mode = meta?.mode ?? 'UNKNOWN';

  return (
    <header className="header">
      <div className="brand">
        <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
          <circle cx="11" cy="11" r="8" fill="none" stroke="currentColor" strokeWidth="2.4" />
          <path d="M11 3 V11 L17 15" fill="none" stroke="currentColor" strokeWidth="2" />
        </svg>
        <span>{copy.appName}</span>
      </div>
      <nav aria-label={copy.header.menu} className="nav">
        {VIEWS.map((v) => (
          <button key={v} className={`navbtn${view === v ? ' on' : ''}`} aria-current={view === v ? 'page' : undefined} onClick={() => set({ view: v })}>
            {copy.nav[v]}
          </button>
        ))}
      </nav>
      <div className="status">
        <label className="tenant">
          <span className="sr">{copy.header.tenant}</span>
          <select value={tenant} onChange={(e) => void switchTenant(e.target.value)} aria-label={copy.header.tenant}>
            {(tenants().length ? tenants() : [tenant]).map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <span className={`badge mode ${mode}`} title={copy.modeHint[mode] ?? ''}>
          {copy.mode[mode] ?? mode}
        </span>
        <EpochBadge />
        <InvariantLight />
        <span className={`badge conn ${conn}`} role="status">
          <span className="dot" aria-hidden="true" />
          {copy.connection[conn]}
        </span>
        <button className="btn ghost" aria-pressed={presentation} onClick={() => set({ presentation: !presentation })} title="P">
          {copy.presentationMode}
        </button>
        <button className="btn ghost icon" aria-label={copy.shortcuts.title} onClick={() => set({ shortcutsOpen: true })}>
          ?
        </button>
      </div>
    </header>
  );
}
