import { useEffect } from 'react';
import { flushSync } from 'react-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { Header } from './components/Header';
import { Banners, DevConsole, LoadError, Shortcuts, Toasts, VersionBlock } from './components/Overlays';
import { graphBus } from './graph/bus';
import { queryClient } from './state/queries';
import { startSession, stopSession } from './state/pipeline';
import { startAutopilot } from './state/autopilot';
import { Landing } from './landing/Landing';
import { useRoute } from './landing/hooks';
import { closePopovers, navMove, POPOVERS, useStore } from './state/store';
import { focusTrigger, rememberFocus } from './components/focus';
import { CommandPalette } from './components/CommandPalette';
import { ContextMenu } from './components/ContextMenu';
import { Benchmark } from './views/Benchmark';
import { Brain } from './views/Brain';
import { Console } from './views/Console';
import { Memory } from './views/Memory';
import { Tenants } from './views/Tenants';

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

export function App() {
  const route = useRoute();
  const view = useStore((s) => s.view);
  const vs = useStore((s) => s.versionState);
  const presentation = useStore((s) => s.presentation);
  const demo = useStore((s) => s.demo);
  const loaded = useStore((s) => s.loaded);
  useShortcuts();

  useEffect(() => {
    document.body.classList.toggle('on-landing', route === 'landing');
  }, [route]);

  useEffect(() => {
    if (route === 'app') void startSession();
    else stopSession();
  }, [route]);

  useEffect(() => {
    if (route !== 'app' || !loaded) return;
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
  }, [route, loaded]);

  if (route === 'landing') return <Landing />;

  return (
    <QueryClientProvider client={queryClient}>
      <div className={`app${presentation ? ' presenting' : ''}${demo ? ' demo' : ''}`}>
        <Header />
        <Banners />
        {vs === 'major' ? (
          <VersionBlock />
        ) : (
          <div className="stage">
            <div className="view" hidden={view !== 'console'}>
              <Console visible={view === 'console'} />
            </div>
            {view === 'memory' && <Memory />}
            {view === 'brain' && <Brain />}
            {view === 'tenants' && <Tenants />}
            {view === 'benchmark' && <Benchmark />}
          </div>
        )}
        <LoadError />
        <Toasts />
        <Shortcuts />
        <CommandPalette />
        <ContextMenu />
        {!presentation && <DevConsole />}
      </div>
    </QueryClientProvider>
  );
}
