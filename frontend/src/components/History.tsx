import { copy } from '../copy';
import { graphBus } from '../graph/bus';
import type { FeedGroup } from '../state/reducer';
import { useStore, type FeedFilter } from '../state/store';
import { fmtTime, Empty, Skeleton } from './ui';

const FILTERS: FeedFilter[] = ['all', 'graph', 'actions', 'handoffs', 'system'];

export function HistoryFeed() {
  const feed = useStore((s) => s.feed);
  const filter = useStore((s) => s.feedFilter);
  const loaded = useStore((s) => s.loaded);
  const set = useStore((s) => s.set);
  const shown = feed.filter((f) => filter === 'all' || f.group === (filter as FeedGroup));

  return (
    <section className="panel history" aria-label={copy.history.title}>
      <div className="panel-top">
        <h2 className="panel-h">{copy.history.title}</h2>
        <label className="sr" htmlFor="feed-filter">{copy.history.filterLabel}</label>
        <select id="feed-filter" value={filter} onChange={(e) => set({ feedFilter: e.target.value as FeedFilter })}>
          {FILTERS.map((f) => (
            <option key={f} value={f}>
              {copy.history.filters[f]}
            </option>
          ))}
        </select>
      </div>
      {!loaded && <Skeleton lines={4} />}
      {loaded && shown.length === 0 && <Empty>{copy.history.empty}</Empty>}
      <ol className="feed" aria-live="polite" aria-relevant="additions">
        {shown.map((f) => (
          <li key={f.id} className={`feed-item tone-${f.tone}`}>
            <button
              className="feed-btn"
              disabled={!f.nodeId}
              onClick={() => {
                if (!f.nodeId) return;
                set({ selectedId: f.nodeId, tab: 'graph' });
                graphBus.focus.emit(f.nodeId);
              }}
            >
              <span className="feed-time num">{fmtTime(f.ts)}</span>
              <span className="feed-text">{f.text}</span>
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
