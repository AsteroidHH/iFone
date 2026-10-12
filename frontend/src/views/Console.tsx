import { copy } from '../copy';
import { Icon } from '../components/Icon';
import { Crumbs } from '../components/Crumbs';
import { Insights } from '../components/Insights';
import { Containment } from '../components/Containment';
import { HistoryFeed } from '../components/History';
import { Inspector } from '../components/Inspector';
import { Ledger } from '../components/Ledger';
import { PromptDiff } from '../components/PromptDiff';
import { ScenarioControls } from '../components/Scenario';
import { Timeline } from '../components/Timeline';
import { GraphCanvas } from '../graph/GraphCanvas';
import { useStore, type Tab } from '../state/store';

const TABS: Tab[] = ['graph', 'diff', 'ledger', 'insights'];
const TAB_ICON: Record<Tab, string> = { graph: 'graph', diff: 'doc', ledger: 'bolt', insights: 'chart' };

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
        <div className="center-head">
          <div className="seg" role="tablist">
            {TABS.map((t) => (
              <button key={t} role="tab" aria-selected={tab === t} className={`seg-btn${tab === t ? ' on' : ''}`} onClick={() => set({ tab: t })}>
                <Icon name={TAB_ICON[t]} size={14} />
                {copy.tabs[t]}
              </button>
            ))}
          </div>
          {tab === 'graph' && <Crumbs />}
        </div>
        <GraphCanvas active={visible && tab === 'graph'} />
        {tab === 'diff' && <PromptDiff />}
        {tab === 'ledger' && <Ledger />}
        {tab === 'insights' && <Insights />}
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
