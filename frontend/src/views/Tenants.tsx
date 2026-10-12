import { useQuery } from '@tanstack/react-query';
import { copy } from '../copy';
import { Chip, ErrorState, Skeleton } from '../components/ui';
import { getDenied } from '../state/endpoints';
import { useStore } from '../state/store';

export function Tenants() {
  const tenant = useStore((s) => s.tenant);
  const q = useQuery({ queryKey: ['denied', tenant], queryFn: getDenied });
  return (
    <div className="page tenants">
      <section className="panel wide" aria-label={copy.tenants.title}>
        <h2 className="panel-h">{copy.tenants.title}</h2>
        <p>{copy.tenants.intro}</p>
        {q.isLoading && <Skeleton lines={4} />}
        {q.isError && <ErrorState error={q.error} onRetry={() => void q.refetch()} />}
        {q.data && (
          <div className="denied">
            <div className="denied-flow">
              <div className="denied-box">
                <span className="muted">{copy.header.tenant}</span>
                <strong className="mono">{q.data.tenant}</strong>
              </div>
              <div className={`denied-arrow ${q.data.result === 'DENIED' ? 'bad' : 'warn'}`} aria-hidden="true">
                <svg width="120" height="24" viewBox="0 0 120 24">
                  <path d="M2 12 H98" stroke="currentColor" strokeWidth="2" strokeDasharray="6 4" />
                  <path d="M100 12 L90 6 M100 12 L90 18" stroke="currentColor" strokeWidth="2" />
                  <path d="M60 4 V20" stroke="currentColor" strokeWidth="3" />
                </svg>
              </div>
              <div className="denied-box target">
                <span className="muted">{copy.tenants.attempt}</span>
                <strong className="mono">{q.data.attempted_graph}</strong>
              </div>
            </div>
            <p className="denied-result">
              {copy.tenants.result}:{' '}
              <Chip tone={q.data.result === 'DENIED' ? 'good' : 'bad'}>
                {q.data.result === 'DENIED' ? copy.tenants.denied : q.data.result === 'ALLOWED' ? copy.tenants.allowed : copy.status.UNKNOWN}
              </Chip>
            </p>
            <h3 className="sub">{copy.tenants.detail}</h3>
            <pre className="mono server-said">{q.data.detail}</pre>
            <h3 className="sub">{copy.tenants.visible}</h3>
            <ul className="graphs mono">
              {q.data.visible_graph_names.map((g) => (
                <li key={g}>{g}</li>
              ))}
            </ul>
            <button className="btn" onClick={() => void q.refetch()}>
              {copy.tenants.run}
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
