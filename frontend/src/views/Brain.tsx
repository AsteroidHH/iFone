import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { copy } from '../copy';
import { Chip, Empty, ErrorState, fmtDateTime, Skeleton } from '../components/ui';
import { askBrain, getTrace, getWhoKnows } from '../state/endpoints';
import { useStore } from '../state/store';

function Ask() {
  const [q, setQ] = useState('');
  const prefill = useStore((s) => s.brainQuestion);
  const ask = useMutation({ mutationFn: (question: string) => askBrain(question) });

  useEffect(() => {
    if (prefill) {
      setQ(prefill);
      ask.mutate(prefill);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill]);

  return (
    <section className="panel ask" aria-label={copy.brain.title}>
      <h2 className="panel-h">{copy.brain.title}</h2>
      <form
        className="askform"
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim()) ask.mutate(q.trim());
        }}
      >
        <label className="sr" htmlFor="ask-q">{copy.brain.title}</label>
        <input id="ask-q" value={q} onChange={(e) => setQ(e.target.value)} placeholder={copy.brain.placeholder} />
        <button className="btn primary" disabled={ask.isPending || !q.trim()}>
          {copy.brain.ask}
        </button>
      </form>
      <div className="examples">
        {copy.brain.examples.map((x) => (
          <button
            key={x}
            className="btn ghost"
            onClick={() => {
              setQ(x);
              ask.mutate(x);
            }}
          >
            {x}
          </button>
        ))}
      </div>
      {ask.isPending && <Skeleton lines={3} />}
      {ask.isError && <ErrorState error={ask.error} onRetry={() => ask.mutate(q)} />}
      {ask.data?.refused && (
        <div className="answer refused" role="status">
          <Chip tone="bad">{copy.brain.refused}</Chip>
          <h3>{copy.brain.refusedWhy}</h3>
          <p>{ask.data.reason}</p>
        </div>
      )}
      {ask.data && !ask.data.refused && (
        <div className="answer" role="status">
          <p className="answer-text">{ask.data.answer}</p>
          <h3 className="sub">{copy.brain.citations}</h3>
          <ol className="cites">
            {ask.data.citations.map((c, i) => (
              <li key={i} className={c.stale ? 'old' : ''}>
                <div className="cite-head">
                  <strong>{c.source_title}</strong>
                  <span className="muted">
                    {copy.brain.version} {c.version}
                  </span>
                  <Chip tone={c.stale ? 'warn' : 'good'}>{c.stale ? copy.brain.outOfDate : copy.brain.current}</Chip>
                </div>
                {c.quote && <blockquote>{c.quote}</blockquote>}
                <p className="muted">
                  {copy.brain.owner}: {c.owner_team}. <span className="num">{fmtDateTime(c.valid_from)}</span>{' '}
                  {c.url && (
                    <a href={c.url} target="_blank" rel="noreferrer noopener">
                      Open source
                    </a>
                  )}
                </p>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}

function WhoKnows() {
  const [topic, setTopic] = useState('refund policy');
  const [committed, setCommitted] = useState('refund policy');
  const q = useQuery({ queryKey: ['who-knows', committed], queryFn: () => getWhoKnows(committed) });
  const max = Math.max(1, ...(q.data ?? []).map((p) => p.evidence_count));
  return (
    <section className="panel" aria-label={copy.brain.whoKnows}>
      <h2 className="panel-h">{copy.brain.whoKnows}</h2>
      <form
        className="askform"
        onSubmit={(e) => {
          e.preventDefault();
          setCommitted(topic);
        }}
      >
        <label className="sr" htmlFor="topic">{copy.brain.topic}</label>
        <input id="topic" value={topic} onChange={(e) => setTopic(e.target.value)} />
        <button className="btn">{copy.brain.lookup}</button>
      </form>
      {q.isLoading && <Skeleton lines={3} />}
      {q.isError && <ErrorState error={q.error} onRetry={() => void q.refetch()} />}
      {q.data && q.data.length === 0 && <Empty>{copy.brain.traceNone}</Empty>}
      <ol className="board">
        {q.data?.map((p) => (
          <li key={p.person}>
            <div className="board-head">
              <strong>{p.person}</strong>
              <span className="muted">{p.team}</span>
              <span className="num">{copy.brain.evidence(p.evidence_count)}</span>
            </div>
            <div className="rankbar">
              <i style={{ width: `${(p.evidence_count / max) * 100}%` }} />
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function Trace() {
  const nodes = useStore((s) => s.nodes);
  const decisions = Object.values(nodes).filter((n) => n.is_decision);
  const [id, setId] = useState('');
  const current = id || decisions[0]?.id || '';
  const q = useQuery({ queryKey: ['trace', current], queryFn: () => getTrace(current), enabled: !!current });
  return (
    <section className="panel" aria-label={copy.brain.traceTitle}>
      <h2 className="panel-h">{copy.brain.traceTitle}</h2>
      {decisions.length === 0 && <Empty>{copy.brain.traceEmpty}</Empty>}
      {decisions.length > 0 && (
        <label className="field">
          <span>{copy.brain.pickDecision}</span>
          <select value={current} onChange={(e) => setId(e.target.value)}>
            {decisions.map((d) => (
              <option key={d.id} value={d.id}>
                {d.label}
              </option>
            ))}
          </select>
        </label>
      )}
      {q.isLoading && current && <Skeleton lines={3} />}
      {q.isError && <ErrorState error={q.error} onRetry={() => void q.refetch()} />}
      {q.data && q.data.length === 0 && <Empty>{copy.brain.traceNone}</Empty>}
      <ol className="trace">
        {q.data?.map((r, i) => (
          <li key={i}>
            <strong>{r.claim}</strong>
            {r.quote && <blockquote>{r.quote}</blockquote>}
            <p className="muted">
              {r.source_title}, {copy.brain.version.toLowerCase()} {r.version}. {copy.brain.owner}: {r.owner}.{' '}
              <a href={r.url} target="_blank" rel="noreferrer noopener">
                Open source
              </a>
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function Brain() {
  return (
    <div className="page brain">
      <Ask />
      <WhoKnows />
      <Trace />
    </div>
  );
}
