import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { API_MODE, tenants } from '../api/client';
import { copy } from '../copy';
import { getInvariants } from '../state/endpoints';
import { switchTenant } from '../state/pipeline';
import { useStore, type View } from '../state/store';
import { go } from '../landing/hooks';
import { tools } from '../copy/tools';
import { rememberFocus } from './focus';
import { Icon } from './Icon';
import { Skeleton } from './ui';

const VIEWS: { id: View; icon: string }[] = [
  { id: 'console', icon: 'console' },
  { id: 'memory', icon: 'memory' },
  { id: 'brain', icon: 'brain' },
  { id: 'tenants', icon: 'tenants' },
  { id: 'benchmark', icon: 'bench' },
];

function EpochBadge() {
  const epoch = useStore((s) => s.epoch);
  const [pulse, setPulse] = useState(false);
  const prev = useRef(epoch);
  useEffect(() => {
    if (prev.current !== epoch && prev.current !== 0) {
      setPulse(true);
      const t = setTimeout(() => setPulse(false), 1500);
      prev.current = epoch;
      return () => clearTimeout(t);
    }
    prev.current = epoch;
  }, [epoch]);
  return (
    <span className={`pill epoch${pulse ? ' pulse' : ''}`} title="Increments on every quarantine, restore and replacement">
      <Icon name="refresh" size={13} />
      {copy.epoch(epoch)}
    </span>
  );
}

function InvariantLight() {
  const inv = useStore((s) => s.invariant);
  const open = useStore((s) => s.invariantsOpen);
  const set = useStore((s) => s.set);
  const q = useQuery({ queryKey: ['invariants'], queryFn: getInvariants, enabled: open });
  const state = inv ? (inv.ok ? 'ok' : 'bad') : 'unknown';
  const text = inv ? (inv.ok ? copy.invariants.ok : copy.invariants.bad(inv.violations)) : copy.invariants.unknown;
  return (
    <div className="pop-wrap">
      <button className={`pill light ${state}`} aria-expanded={open} data-popover-trigger="invariants" onClick={() => set({ invariantsOpen: !open })}>
        <Icon name="shield" size={13} />
        {text}
      </button>
      {open && (
        <div className="popover" role="dialog" aria-label="Invariant checks" data-popover="invariants">
          <h3>Invariant checks</h3>
          {q.isLoading && <Skeleton lines={3} />}
          {q.isError && <p className="muted">{copy.errors.panel('GET /invariants')}</p>}
          {q.data && (
            <ul className="checks">
              {q.data.checks.map((c) => (
                <li key={c.name}>
                  <span className={`tick ${c.ok ? 'ok' : 'bad'}`}>
                    <Icon name={c.ok ? 'check' : 'x'} size={12} />
                  </span>
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
      <button className="brand" onClick={() => go('landing')} aria-label="Quorum home" title="Back to the landing page">
        <span className="brand-mark">
          <Icon name="logo" size={20} />
        </span>
        <span className="brand-name">{copy.appName}</span>
      </button>
      <nav aria-label={copy.header.menu} className="nav">
        {VIEWS.map((v) => (
          <button key={v.id} className={`navbtn${view === v.id ? ' on' : ''}`} aria-current={view === v.id ? 'page' : undefined} onClick={() => set({ view: v.id })}>
            <Icon name={v.icon} size={16} />
            <span className="nav-label">{copy.nav[v.id]}</span>
          </button>
        ))}
      </nav>
      <div className="status">
        <label className="tenant">
          <span className="sr">{copy.header.tenant}</span>
          <span className="tenant-dot" aria-hidden="true" />
          <select value={tenant} onChange={(e) => void switchTenant(e.target.value)} aria-label={copy.header.tenant}>
            {(tenants().length ? tenants() : [tenant]).map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        {API_MODE === 'mock' && (
          <span className="pill sample" title={copy.sampleHint}>
            <Icon name="sparkle" size={13} />
            {copy.sampleData}
          </span>
        )}
        <span className={`pill mode ${mode}`} title={copy.modeHint[mode] ?? ''}>
          {copy.mode[mode] ?? mode}
        </span>
        <EpochBadge />
        <InvariantLight />
        <span className={`pill conn ${conn}`} role="status">
          <span className="dot" aria-hidden="true" />
          <span className="conn-label">{copy.connection[conn]}</span>
        </span>
        <button className="palette-btn" onClick={() => {
            rememberFocus();
            set({ paletteOpen: true });
          }}
          aria-label={tools.palette.open} title={tools.palette.open}>
          <Icon name="search" size={15} />
          <span className="pb-label">Search</span>
          <kbd>Ctrl K</kbd>
        </button>
        <button className="iconbtn" aria-pressed={presentation} aria-label={copy.presentationMode} title={`${copy.presentationMode} (P)`} onClick={() => set({ presentation: !presentation })}>
          <Icon name="present" size={17} />
        </button>
        <button className="iconbtn" aria-label={copy.shortcuts.title} title={copy.shortcuts.title} onClick={() => {
            rememberFocus();
            set({ shortcutsOpen: true });
          }}
        >
          <Icon name="help" size={17} />
        </button>
      </div>
    </header>
  );
}
