import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { API_MODE } from './api/client';
import { onBlocked, type Blocked } from './api/blocked';
import { fetchHealth, type HealthResult } from './api/health';
import { BlockScreen } from './components/BlockScreen';
import { Header } from './components/Header';
import { Banners, DevConsole, LoadError, Shortcuts, Toasts, VersionBlock } from './components/Overlays';
import { ContextMenu } from './components/ContextMenu';
import { focusTrigger, rememberFocus } from './components/focus';
import { Skeleton } from './components/ui';
import { graphBus } from './graph/bus';
import { startAutopilot } from './state/autopilot';
import { startSession, stopSession } from './state/pipeline';
import { queryClient } from './state/queries';
import { closePopovers, navMove, POPOVERS, useStore } from './state/store';
import { useLive } from './workspace/live';

// Everything heavy loads on demand: the graph engine only when the console is opened, each view only when visited.
const Console = lazy(() => import('./views/Console').then((m) => ({ default: m.Console })));
const Memory = lazy(() => import('./views/Memory').then((m) => ({ default: m.Memory })));
const Brain = lazy(() => import('./views/Brain').then((m) => ({ default: m.Brain })));
const Tenants = lazy(() => import('./views/Tenants').then((m) => ({ default: m.Tenants })));
const Benchmark = lazy(() => import('./views/Benchmark').then((m) => ({ default: m.Benchmark })));
const Context = lazy(() => import('./views/Context').then((m) => ({ default: m.Context })));
const Connect = lazy(() => import('./views/Connect').then((m) => ({ default: m.Connect })));
const Team = lazy(() => import('./views/Team').then((m) => ({ default: m.Team })));
const Activity = lazy(() => import('./views/Activity').then((m) => ({ default: m.Activity })));
const CommandPalette = lazy(() => import('./components/CommandPalette').then((m) => ({ default: m.CommandPalette })));

function ViewFallback() {
  return (
    <div className="page" aria-busy="true">
      <Skeleton lines={6} />
    </div>
  );
}

function useShortcuts() {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      const typing = !!t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable);
      const st = useStore.getState();
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K' || e.key === 'p' || e.key === 'P')) {
        e.preventDefault();
        if (!st.paletteOpen) rememberFocus();
        flushSync(() => st.set({ paletteOpen: !st.paletteOpen }));
        return;
      }
      if (e.altKey && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
        e.preventDefault();
        const id = navMove(e.key === 'ArrowLeft' ? -1 : 1);
        if (id) graphBus.focus.emit(id);
        return;
      }
      if (e.key === 'Escape') {
        if (st.paletteOpen) return;
        if (st.ctxMenu) {
          st.set({ ctxMenu: null });
          return;
        }
        if (POPOVERS.some((k) => st[k])) {
          const which = st.filtersOpen ? 'filters' : st.invariantsOpen ? 'invariants' : 'legend';
          closePopovers();
          focusTrigger(which);
          return;
        }
        if (st.shortcutsOpen) return;
        if (typing) {
          (t as HTMLElement).blur();
          if (st.search) st.set({ search: '' });
          return;
        }
        if (st.presentation) st.set({ presentation: false });
        else st.set({ selectedId: null, search: '', pathIds: [] });
        return;
      }
      if (typing || st.paletteOpen || e.metaKey || e.ctrlKey || e.altKey) return;
      switch (e.key) {
        case 'f':
        case 'F':
          graphBus.fit.emit();
          break;
        case '/':
          e.preventDefault();
          document.getElementById('graph-search')?.focus();
          break;
        case 'l':
        case 'L':
          st.set({ listView: !st.listView });
          break;
        case 'p':
        case 'P':
          st.set({ presentation: !st.presentation });
          break;
        case '?':
          rememberFocus();
          st.set({ shortcutsOpen: true });
          break;
        case '1':
          st.set({ view: 'console' });
          break;
        case '2':
          st.set({ view: 'memory' });
          break;
        case '3':
          st.set({ view: 'brain' });
          break;
        case '4':
          st.set({ view: 'tenants' });
          break;
        case '5':
          st.set({ view: 'benchmark' });
          break;
        case '6':
          st.set({ view: 'context' });
          break;
        case '7':
          st.set({ view: 'connect' });
          break;
        case '8':
          st.set({ view: 'team' });
          break;
        case '9':
          st.set({ view: 'activity' });
          break;
      }
    };
    const onPointer = (e: PointerEvent) => {
      const el = e.target as Element | null;
      if (el?.closest('[data-popover],[data-popover-trigger]')) return;
      closePopovers();
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('pointerdown', onPointer, true);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('pointerdown', onPointer, true);
    };
  }, []);
}

function Shell() {
  const view = useStore((s) => s.view);
  const vs = useStore((s) => s.versionState);
  const presentation = useStore((s) => s.presentation);
  const demo = useStore((s) => s.demo);
  const loaded = useStore((s) => s.loaded);
  const paletteOpen = useStore((s) => s.paletteOpen);
  useShortcuts();

  useEffect(() => {
    void startSession();
    return () => stopSession();
  }, []);

  useEffect(() => {
    useLive.getState().start(() => {
      const st = useStore.getState();
      return { graph: { nodes: Object.values(st.nodes), edges: Object.values(st.edges) }, tenant: st.tenant, epoch: st.epoch };
    });
    return () => useLive.getState().stop();
  }, []);

  // The palette must open instantly on first Ctrl+K, so fetch its chunk as soon as the console is up.
  useEffect(() => {
    const t = setTimeout(() => void import('./components/CommandPalette'), 300);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (!loaded) return;
    let want = false;
    try {
      want = sessionStorage.getItem('quorum:autoplay') === '1';
    } catch {
      /* storage can be unavailable */
    }
    if (!want) return;
    const t = setTimeout(() => {
      try {
        sessionStorage.removeItem('quorum:autoplay');
      } catch {
        /* ignore */
      }
      void startAutopilot();
    }, 900);
    return () => clearTimeout(t);
  }, [loaded]);

  return (
    <QueryClientProvider client={queryClient}>
      <div className={`app${presentation ? ' presenting' : ''}${demo ? ' demo' : ''}`}>
        {view === 'console' && <h1 className="sr-only">Quorum console</h1>}
        <Header />
        <Banners />
        {vs === 'major' ? (
          <VersionBlock />
        ) : (
          <div className="stage">
            <Suspense fallback={<ViewFallback />}>
              <div className="view" hidden={view !== 'console'}>
                <Console visible={view === 'console'} />
              </div>
              {view === 'memory' && <Memory />}
              {view === 'brain' && <Brain />}
              {view === 'tenants' && <Tenants />}
              {view === 'benchmark' && <Benchmark />}
              {view === 'context' && <Context />}
              {view === 'connect' && <Connect />}
              {view === 'team' && <Team />}
              {view === 'activity' && <Activity />}
            </Suspense>
          </div>
        )}
        <LoadError />
        <Toasts />
        <Shortcuts />
        {paletteOpen && (
          <Suspense fallback={null}>
            <CommandPalette />
          </Suspense>
        )}
        <ContextMenu />
        {!presentation && <DevConsole />}
      </div>
    </QueryClientProvider>
  );
}

/**
 * Live mode only starts the product once the backend says FalkorDB is ready, and takes it away again the moment it
 * is not. Sample-data builds skip the check because there is no backend.
 */
function useBackendGate() {
  const [result, setResult] = useState<HealthResult | null>(null);
  const [blocked, setBlocked] = useState<Blocked | null>(null);
  const [checking, setChecking] = useState(false);
  const alive = useRef(true);

  const poll = useCallback(async () => {
    const r = await fetchHealth();
    if (!alive.current) return;
    setResult(r);
    if (r.kind === 'ok') setBlocked(null);
  }, []);

  const recheck = useCallback(async () => {
    setChecking(true);
    await poll();
    if (alive.current) setChecking(false);
  }, [poll]);

  useEffect(() => {
    if (API_MODE === 'mock') return; // the sample build has no backend to ask
    alive.current = true;
    // The first poll is a network request; state is set when it answers, not during the effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void poll();
    const off = onBlocked((b) => {
      setBlocked(b);
      setResult((r) => (r?.kind === 'ok' ? { kind: 'blocked', health: { ...r.health, status: 'blocked', falkordb: { ...r.health.falkordb, up: false, error: b.reason }, steps: b.steps } } : r));
    });
    const t = setInterval(() => void poll(), 3000);
    return () => {
      alive.current = false;
      clearInterval(t);
      off();
    };
  }, [poll]);

  return { result, blocked, checking, recheck };
}

export default function ConsoleApp() {
  const gate = useBackendGate();
  if (API_MODE === 'mock') return <Shell />;
  const r = gate.result;
  if (!r) return <ViewFallback />;
  if (r.kind !== 'ok' || gate.blocked) {
    return <BlockScreen result={r} blocked={gate.blocked} checking={gate.checking} onRetry={() => void gate.recheck()} />;
  }
  const warnings = r.health.warnings;
  return (
    <>
      {warnings.length > 0 && (
        <div className="persist-warn" role="alert">
          {warnings.join(' ')}
        </div>
      )}
      <Shell />
    </>
  );
}
