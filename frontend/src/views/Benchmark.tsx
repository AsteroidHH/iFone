import { useQuery } from '@tanstack/react-query';
import type { BenchResults } from '../api/schemas';
import { copy } from '../copy';
import { Empty, ErrorState, fmtDateTime, Skeleton } from '../components/ui';
import { getBench } from '../state/endpoints';

const SYS_COLORS = ['var(--verdigris)', 'var(--graphite)', 'var(--pencil)'];

function Bars({ rows, unit, max }: { rows: { label: string; value: number }[]; unit: string; max: number }) {
  return (
    <ul className="bars">
      {rows.map((r) => (
        <li key={r.label}>
          <span className="bar-label">{r.label}</span>
          <span className="bar-track">
            <i style={{ width: `${Math.max(1, (r.value / max) * 100)}%` }} />
          </span>
          <span className="num bar-value">
            {r.value}
            {unit}
          </span>
        </li>
      ))}
    </ul>
  );
}

function Poison({ data }: { data: BenchResults['poison'] }) {
  return (
    <section className="panel wide" aria-label={copy.bench.poison}>
      <h2 className="panel-h">{copy.bench.poison}</h2>
      <p className="muted">
        {copy.bench.leaked}, {copy.bench.wrong.toLowerCase()}, {copy.bench.ttc.toLowerCase()}.
      </p>
      <div className="poison-grid">
        {data.map((d) => (
          <div key={d.depth} className="poison-col">
            <h3 className="sub">{copy.bench.depth(d.depth)}</h3>
            <ul className="bars">
              {d.systems.map((s, i) => (
                <li key={s.name}>
                  <span className="bar-label">{s.name}</span>
                  <span className="bar-track">
                    <i style={{ width: `${Math.max(1, s.leaked_rate * 100)}%`, background: SYS_COLORS[i % SYS_COLORS.length] }} />
                  </span>
                  <span className="num bar-value">{Math.round(s.leaked_rate * 100)}% leaked</span>
                </li>
              ))}
            </ul>
            <table className="mini">
              <thead>
                <tr>
                  <th>System</th>
                  <th>{copy.bench.wrong}</th>
                  <th>{copy.bench.ttc}</th>
                </tr>
              </thead>
              <tbody>
                {d.systems.map((s) => (
                  <tr key={s.name}>
                    <td>{s.name}</td>
                    <td className="num">{s.wrongly_quarantined}</td>
                    <td className="num">{s.ms_to_containment} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </section>
  );
}

export function Benchmark() {
  const q = useQuery({ queryKey: ['bench'], queryFn: getBench });
  const d = q.data;
  return (
    <div className="page bench">
      {q.isLoading && <Skeleton lines={8} />}
      {q.isError && <ErrorState error={q.error} onRetry={() => void q.refetch()} />}
      {d && (
        <>
          <section className="panel wide" aria-label={copy.bench.params}>
            <h2 className="panel-h">{copy.bench.title}</h2>
            <p className="num">
              {copy.bench.generated}: {fmtDateTime(d.generated_at)}
            </p>
            <dl className="kv params">
              {Object.entries(d.params).map(([k, v]) => (
                <div key={k}>
                  <dt>{k.replace(/_/g, ' ')}</dt>
                  <dd>{String(v)}</dd>
                </div>
              ))}
            </dl>
          </section>
          <section className="panel" aria-label={copy.bench.concurrency}>
            <h2 className="panel-h">{copy.bench.concurrency}</h2>
            <p className="bignum num">
              {d.concurrency.ops_per_s.toLocaleString()} <span className="muted">{copy.bench.opsPerS}</span>
            </p>
            <p className="muted">{d.concurrency.agents} agents</p>
            <Bars
              unit=" ms"
              max={Math.max(d.concurrency.p99_ms, 1)}
              rows={[
                { label: 'p50', value: d.concurrency.p50_ms },
                { label: 'p95', value: d.concurrency.p95_ms },
                { label: 'p99', value: d.concurrency.p99_ms },
              ]}
            />
          </section>
          <section className="panel" aria-label={copy.bench.handoff}>
            <h2 className="panel-h">{copy.bench.handoff}</h2>
            <p className="bignum num">{Math.round(d.handoff_race.single_winner_rate * 100)}%</p>
            <p className="muted">
              {copy.bench.singleWinner}: {d.handoff_race.handoffs} handoffs, {d.handoff_race.claimers} claimers each.
            </p>
            <h2 className="panel-h second">{copy.bench.invalidation}</h2>
            <p className="bignum num">{d.invalidation_under_load.violations}</p>
            <p className="muted">{copy.bench.violations(d.invalidation_under_load.violations)}</p>
          </section>
          {d.poison.length ? <Poison data={d.poison} /> : <Empty>{copy.bench.empty}</Empty>}
        </>
      )}
    </div>
  );
}
