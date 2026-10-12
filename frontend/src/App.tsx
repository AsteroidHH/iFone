import { useEffect } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { Header } from './components/Header';
import { Banners, DevConsole, LoadError, Shortcuts, Toasts, VersionBlock } from './components/Overlays';
import { graphBus } from './graph/bus';
import { queryClient } from './state/queries';
import { startSession, stopSession } from './state/pipeline';
import { startAutopilot } from './state/autopilot';
import { Landing } from './landing/Landing';
import { useRoute } from './landing/hooks';
import { useStore } from './state/store';
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
      if (e.key === 'Escape') {
        if (typing) (t as HTMLElement).blur();
        if (st.shortcutsOpen) st.set({ shortcutsOpen: false });
        else if (st.presentation) st.set({ presentation: false });
        else st.set({ selectedId: null, search: '' });
        return;
      }
      if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
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
          st.set({ shortcutsOpen: true });
          break;
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
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
        {!presentation && <DevConsole />}
      </div>
    </QueryClientProvider>
  );
}
