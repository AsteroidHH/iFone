import { useEffect, useState } from 'react';
import { API_MODE, session, type Role } from '../api/client';
import { subscribeDevLog, type DevLogEntry } from '../api/devlog';
import { CONTRACT_VERSION } from '../api/schemas';
import { copy } from '../copy';
import { setRole, startSession } from '../state/pipeline';
import { useStore } from '../state/store';
import { fmtTime } from './ui';

export function Toasts() {
  const toasts = useStore((s) => s.toasts);
  const drop = useStore((s) => s.dropToast);
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className="toast">
          <span>{t.text}</span>
          <button className="btn ghost icon" aria-label={copy.dismiss} onClick={() => drop(t.id)}>
            x
          </button>
        </div>
      ))}
    </div>
  );
}

export function Banners() {
  const conn = useStore((s) => s.conn);
  const stale = useStore((s) => s.graphStale);
  const resyncing = useStore((s) => s.resyncing);
  const vs = useStore((s) => s.versionState);
  const meta = useStore((s) => s.meta);
  const dismissed = useStore((s) => s.versionBannerDismissed);
  const set = useStore((s) => s.set);
  const presentation = useStore((s) => s.presentation);
  const demo = useStore((s) => s.demo);

  return (
    <div className="banners">
      {API_MODE === 'mock' && (
        <div className="banner mock" role="note">
          <strong>{copy.mockBanner}</strong>
          {!presentation && !demo && <span>{copy.mockBannerDetail}</span>}
        </div>
      )}
      {(stale || conn === 'offline') && (
        <div className="banner warn" role="alert">
          {copy.staleBanner}
        </div>
      )}
      {resyncing && (
        <div className="banner" role="status">
          {copy.resyncing}
        </div>
      )}
      {vs === 'minor' && !dismissed && meta && (
        <div className="banner" role="status">
          <span>{copy.versionMinor(CONTRACT_VERSION, meta.contract_version)}</span>
          <button className="btn ghost" onClick={() => set({ versionBannerDismissed: true })}>
            {copy.dismiss}
          </button>
        </div>
      )}
    </div>
  );
}

export function VersionBlock() {
  const meta = useStore((s) => s.meta);
  return (
    <div className="blocking" role="alertdialog" aria-labelledby="vb-title">
      <h1 id="vb-title">{copy.versionBlock.title}</h1>
      <p>{copy.versionBlock.body(CONTRACT_VERSION, meta?.contract_version ?? 'unknown')}</p>
    </div>
  );
}

export function LoadError() {
  const e = useStore((s) => s.loadError);
  if (!e) return null;
  return (
    <div className="blocking soft" role="alert">
      <h1>{copy.errors.panel(e.endpoint)}</h1>
      <p>{e.message}</p>
      <button className="btn primary" onClick={() => void startSession()}>
        {copy.retry}
      </button>
    </div>
  );
}

export function Shortcuts() {
  const open = useStore((s) => s.shortcutsOpen);
  const set = useStore((s) => s.set);
  if (!open) return null;
  return (
    <div className="modal-back" onClick={() => set({ shortcutsOpen: false })}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={copy.shortcuts.title} onClick={(e) => e.stopPropagation()}>
        <h2>{copy.shortcuts.title}</h2>
        <dl className="keys">
          {copy.shortcuts.items.map(([k, d]) => (
            <div key={k}>
              <dt>
                <kbd>{k}</kbd>
              </dt>
              <dd>{d}</dd>
            </div>
          ))}
        </dl>
        <button className="btn" onClick={() => set({ shortcutsOpen: false })} autoFocus>
          {copy.dismiss}
        </button>
      </div>
    </div>
  );
}

export function DevConsole() {
  const open = useStore((s) => s.devOpen);
  const demo = useStore((s) => s.demo);
  const set = useStore((s) => s.set);
  const role = useStore((s) => s.role);
  const [entries, setEntries] = useState<DevLogEntry[]>([]);
  useEffect(() => subscribeDevLog(setEntries), []);
  if (demo) return null;
  const errs = entries.filter((e) => e.level !== 'info').length;
  return (
    <aside className={`dev${open ? ' open' : ''}`}>
      <button className="dev-toggle" aria-expanded={open} onClick={() => set({ devOpen: !open })}>
        {copy.dev.title}
        {errs > 0 && <span className="dev-count num">{errs}</span>}
      </button>
      {open && (
        <div className="dev-body">
          <label className="dev-role">
            {copy.dev.actAs}
            <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
              <option value="human">human</option>
              <option value="auditor">auditor</option>
              <option value="agent">agent</option>
            </select>
          </label>
          <p className="muted">
            tenant {session.tenant}, contract {CONTRACT_VERSION}, {API_MODE}
          </p>
          {entries.length === 0 && <p className="muted">{copy.dev.empty}</p>}
          <ol className="dev-log mono">
            {[...entries].reverse().map((e) => (
              <li key={e.id} className={e.level}>
                {fmtTime(e.ts)} {e.message}
              </li>
            ))}
          </ol>
        </div>
      )}
    </aside>
  );
}
