import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { copy } from '../copy';
import { Chip, Empty, ErrorState, fmtDateTime, Skeleton } from '../components/ui';
import { getAgents, getProcedures, getResume } from '../state/endpoints';

function Agents({ selected, onPick }: { selected: string | null; onPick: (id: string) => void }) {
  const q = useQuery({ queryKey: ['agents'], queryFn: getAgents });
  return (
    <section className="panel" aria-label={copy.memory.agents}>
      <h2 className="panel-h">{copy.memory.agents}</h2>
      {q.isLoading && <Skeleton lines={4} />}
      {q.isError && <ErrorState error={q.error} onRetry={() => void q.refetch()} />}
      {q.data && q.data.length === 0 && <Empty>{copy.memory.noAgents}</Empty>}
      <ul className="agent-list">
        {q.data?.map((a) => (
          <li key={a.id}>
            <button className={`agent-row${selected === a.id ? ' on' : ''}`} aria-pressed={selected === a.id} onClick={() => onPick(a.id)}>
              <strong>{a.name}</strong>
              <span className="muted">{a.role}</span>
              <Chip>{copy.memory.tier[a.tier] ?? a.tier}</Chip>
              {a.last_active && <span className="muted num">{fmtDateTime(a.last_active)}</span>}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Procedures() {
  const q = useQuery({ queryKey: ['procedures'], queryFn: getProcedures });
  const list = [...(q.data ?? [])].sort((a, b) => b.rank_score - a.rank_score);
  return (
    <section className="panel" aria-label={copy.memory.procedures}>
      <h2 className="panel-h">{copy.memory.procedures}</h2>
      {q.isLoading && <Skeleton lines={4} />}
      {q.isError && <ErrorState error={q.error} onRetry={() => void q.refetch()} />}
      {q.data && q.data.length === 0 && <Empty>{copy.memory.noAgents}</Empty>}
      <ol className="procs">
        {list.map((p, i) => (
          <li key={p.id} className={i === 0 ? 'top' : ''}>
            <div className="proc-head">
              <strong>
                {i + 1}. {p.task_type.charAt(0).toUpperCase() + p.task_type.slice(1)} <span className="mono muted">{p.id}</span>
              </strong>
              <Chip tone={p.seeded ? 'neutral' : 'review'}>{p.seeded ? copy.memory.seeded : copy.memory.learned}</Chip>
            </div>
            <ol className="steps-list">
              {p.steps.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ol>
            <div className="rankbar" role="img" aria-label={`${copy.memory.rank} ${p.rank_score.toFixed(2)}`}>
              <i style={{ width: `${Math.round(p.rank_score * 100)}%` }} />
            </div>
            <p className="muted num">
              {copy.memory.rank} {p.rank_score.toFixed(2)}. {p.uses} {copy.memory.uses}, {p.successes} {copy.memory.wins}, {p.failures} {copy.memory.losses}.
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
}

function Resume({ agent }: { agent: string | null }) {
  const [shown, setShown] = useState<string | null>(null);
  const q = useQuery({ queryKey: ['resume', shown], queryFn: () => getResume(shown as string), enabled: !!shown });
  return (
    <section className="panel" aria-label={copy.memory.resumeTitle}>
      <h2 className="panel-h">{copy.memory.resumeTitle}</h2>
      <p className="muted">{copy.memory.resumeSub}</p>
      {!agent && <Empty>{copy.memory.resumeEmpty}</Empty>}
      {agent && (
        <button className="btn primary" onClick={() => setShown(agent)}>
          {copy.memory.resumeButton}
        </button>
      )}
      {shown && q.isLoading && <Skeleton lines={4} />}
      {shown && q.isError && <ErrorState error={q.error} onRetry={() => void q.refetch()} />}
      {shown && q.data && (
        <>
          <h3 className="sub">{copy.memory.summary}</h3>
          <p>{q.data.summary}</p>
          <ul className="memories">
            {q.data.memories.map((m) => (
              <li key={m.fact_id}>
                <strong>{m.text}</strong>
                {m.quote && <blockquote>{m.quote}</blockquote>}
                <p className="muted">
                  {copy.memory.source}: <span className="mono">{m.source_ref}</span>
                </p>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

export function Memory() {
  const [agent, setAgent] = useState<string | null>('agent_refunder');
  return (
    <div className="page memory">
      <Agents selected={agent} onPick={setAgent} />
      <Procedures />
      <Resume key={agent} agent={agent} />
    </div>
  );
}
