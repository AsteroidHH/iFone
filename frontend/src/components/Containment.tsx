import { useQuery } from '@tanstack/react-query';
import { copy } from '../copy';
import { graphBus } from '../graph/bus';
import { getReport } from '../state/endpoints';
import { useStore } from '../state/store';
import { ErrorState, Skeleton, useCountUp } from './ui';

function Stat({ label, value, big }: { label: string; value: number; big?: boolean }) {
  const v = useCountUp(value);
  return (
    <div className={`stat${big ? ' big' : ''}`}>
      <dd className="num">{v}</dd>
      <dt>{label}</dt>
    </div>
  );
}

export function Containment() {
  const root = useStore((s) => s.reportRoot);
  const set = useStore((s) => s.set);
  const nodes = useStore((s) => s.nodes);
  const q = useQuery({
    queryKey: ['report', root],
    queryFn: () => getReport(root as string),
    enabled: !!root,
  });

  if (!root) return null;
  return (
    <section className="panel containment" aria-label={copy.containment.title} aria-live="polite">
      <div className="panel-top">
        <h2 className="panel-h">{copy.containment.title}</h2>
        <button className="btn ghost icon" aria-label={copy.containment.dismiss} onClick={() => set({ reportRoot: null })}>
          x
        </button>
      </div>
      {q.isLoading && (
        <>
          <p className="muted">{copy.containment.loading}</p>
          <Skeleton lines={3} />
        </>
      )}
      {q.isError && <ErrorState error={q.error} onRetry={() => void q.refetch()} />}
      {q.data && (
        <>
          <p className="muted root-line">{nodes[q.data.root_id]?.label ?? q.data.root_id}</p>
          <dl className="stats">
            <Stat big label={`${copy.containment.time} (${copy.containment.ms})`} value={q.data.ms_to_containment} />
            <Stat label={copy.containment.facts} value={q.data.facts} />
            <Stat label={copy.containment.conclusions} value={q.data.conclusions} />
            <Stat label={copy.containment.cancelled} value={q.data.actions_cancelled} />
            <Stat label={copy.containment.compensated} value={q.data.actions_compensated} />
            <Stat label={copy.containment.escalated} value={q.data.actions_escalated} />
          </dl>
          <h3 className="sub">{copy.containment.byDepth}</h3>
          <ol className="depths">
            {q.data.node_ids_by_depth.map((ids, d) => (
              <li key={d}>
                <span className="depth-label">{copy.containment.hop(d)}</span>
                <span className="depth-nodes">
                  {ids.map((id) => (
                    <button
                      key={id}
                      className="nodechip"
                      onClick={() => {
                        set({ selectedId: id, tab: 'graph' });
                        graphBus.focus.emit(id);
                      }}
                    >
                      {nodes[id]?.label ?? id}
                    </button>
                  ))}
                </span>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
