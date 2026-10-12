import { copy } from '../copy';
import { Containment } from '../components/Containment';
import { HistoryFeed } from '../components/History';
import { Inspector } from '../components/Inspector';
import { Ledger } from '../components/Ledger';
import { PromptDiff } from '../components/PromptDiff';
import { ScenarioControls } from '../components/Scenario';
import { Timeline } from '../components/Timeline';
import { GraphCanvas } from '../graph/GraphCanvas';
import { useStore, type Tab } from '../state/store';

const TABS: Tab[] = ['graph', 'diff', 'ledger'];

export function Console({ visible }: { visible: boolean }) {
  const tab = useStore((s) => s.tab);
  const presentation = useStore((s) => s.presentation);
  const set = useStore((s) => s.set);
  const reportRoot = useStore((s) => s.reportRoot);

  return (
    <div className={`console${presentation ? ' presenting' : ''}`}>
      {!presentation && (
        <aside className="col left">
          <ScenarioControls />
          <HistoryFeed />
        </aside>
      )}
      <main className="col center">
        <div className="tabs center-tabs" role="tablist">
          {TABS.map((t) => (
            <button key={t} role="tab" aria-selected={tab === t} className={`tab${tab === t ? ' on' : ''}`} onClick={() => set({ tab: t })}>
              {copy.tabs[t]}
            </button>
          ))}
        </div>
        <GraphCanvas active={visible && tab === 'graph'} />
        {tab === 'diff' && <PromptDiff />}
        {tab === 'ledger' && <Ledger />}
      </main>
      <aside className="col right">
        <Containment />
        {!presentation && <Inspector />}
        {presentation && !reportRoot && <p className="empty">{copy.containment.empty}</p>}
      </aside>
      {!presentation && <Timeline />}
    </div>
  );
}
