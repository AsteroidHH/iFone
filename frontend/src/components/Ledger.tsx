import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { ApiError } from '../api/client';
import type { Handoff } from '../api/schemas';
import { copy } from '../copy';
import { graphBus } from '../graph/bus';
import { actionDisplayState, actionTone } from '../state/actionState';
import { getActions, getHandoffs, reviewHandoff } from '../state/endpoints';
import { queryClient } from '../state/queries';
import { useStore } from '../state/store';
import { Chip, Empty, ErrorState, Skeleton } from './ui';

function useNow(ms = 500) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(t);
  }, [ms]);
  return now;
}

function LeaseRing({ until }: { until: number }) {
  const now = useNow();
  const total = 60_000;
  const left = Math.max(0, until - now);
  const frac = Math.min(1, left / total);
  const r = 11;
  const c = 2 * Math.PI * r;
  return (
    <span className="lease" title={left ? copy.ledger.lease(Math.ceil(left / 1000)) : copy.ledger.leaseExpired}>
      <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
        <circle cx="14" cy="14" r={r} fill="none" stroke="var(--hairline)" strokeWidth="3" />
        <circle
          cx="14"
          cy="14"
          r={r}
          fill="none"
          stroke={left ? 'var(--ultramarine)' : 'var(--stamp)'}
          strokeWidth="3"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - frac)}
          transform="rotate(-90 14 14)"
        />
      </svg>
      <span className="num">{left ? Math.ceil(left / 1000) : 0}s</span>
    </span>
  );
}

function HandoffCard({ h }: { h: Handoff }) {
  const race = useStore((s) => s.claimRace);
  const pushToast = useStore((s) => s.pushToast);
  const set = useStore((s) => s.set);
  const now = useNow(250);
  const raced = race && race.handoffId === h.id && now - race.ts < 4000 ? race : null;
  const decide = useMutation({
    mutationFn: (d: 'approve' | 'reject') => reviewHandoff(h.id, d),
    onSuccess: (_r, d) => {
      pushToast(copy.toasts.reviewed(d === 'approve' ? 'approved' : 'rejected'));
      void queryClient.invalidateQueries({ queryKey: ['handoffs'] });
    },
    onError: (e) => {
      pushToast(e instanceof ApiError && e.code === 'FORBIDDEN_ROLE' ? copy.toasts.reviewForbidden : copy.errors.generic(e instanceof ApiError ? e.code : 'ERROR', 'Could not record the decision.'));
    },
  });
  const needsHuman = h.kind !== 'TASK' && h.status !== 'COMPLETED';

  return (
    <li className={`handoff kind-${h.kind}${raced ? ' racing' : ''}`}>
      <div className="handoff-head">
        <Chip tone={h.kind === 'TASK' ? 'neutral' : 'ultra'}>{copy.ledger.kinds[h.kind] ?? h.kind}</Chip>
        <Chip tone={h.status === 'COMPLETED' ? 'good' : h.status === 'TIMED_OUT' ? 'bad' : 'neutral'}>
          {copy.ledger.handoffStatus[h.status] ?? h.status}
        </Chip>
        {h.status === 'IN_PROGRESS' && h.lease_until && <LeaseRing until={h.lease_until} />}
      </div>
      <p className="handoff-task">{h.task}</p>
      {h.claimed_by && <p className="muted">{copy.ledger.claimedBy(h.claimed_by)}</p>}
      {raced && (
        <p className="race" role="status">
          <span className="winner">{copy.ledger.race(raced.winner)}</span>
          {raced.losers.map((l) => (
            <span key={l} className="loser">
              {l}: {copy.ledger.lost}
            </span>
          ))}
        </p>
      )}
      <div className="handoff-actions">
        {h.context_root_id && (
          <button
            className="btn ghost"
            onClick={() => {
              set({ selectedId: h.context_root_id ?? null, tab: 'graph' });
              if (h.context_root_id) graphBus.focus.emit(h.context_root_id);
            }}
          >
            Show in graph
          </button>
        )}
        {needsHuman && (
          <>
            <button className="btn review" disabled={decide.isPending} onClick={() => decide.mutate('approve')}>
              {copy.ledger.approve}
            </button>
            <button className="btn" disabled={decide.isPending} onClick={() => decide.mutate('reject')}>
              {copy.ledger.reject}
            </button>
          </>
        )}
      </div>
    </li>
  );
}

export function Ledger() {
  const actions = useQuery({ queryKey: ['actions'], queryFn: getActions });
  const handoffs = useQuery({ queryKey: ['handoffs'], queryFn: getHandoffs });
  const set = useStore((s) => s.set);
  const reviews = (handoffs.data ?? []).filter((h) => h.kind !== 'TASK');
  const tasks = (handoffs.data ?? []).filter((h) => h.kind === 'TASK');

  return (
    <div className="ledger">
      <section className="panel" aria-label={copy.ledger.actionsTitle}>
        <h2 className="panel-h">{copy.ledger.actionsTitle}</h2>
        {actions.isLoading && <Skeleton lines={4} />}
        {actions.isError && <ErrorState error={actions.error} onRetry={() => void actions.refetch()} />}
        {actions.data && actions.data.length === 0 && <Empty>{copy.ledger.noActions}</Empty>}
        <ul className="actions">
          {actions.data?.map((a) => {
            const ds = actionDisplayState(a);
            return (
              <li key={a.id}>
                <button
                  className="action-row"
                  onClick={() => {
                    set({ selectedId: a.id, tab: 'graph' });
                    graphBus.focus.emit(a.id);
                  }}
                >
                  <strong>{a.label}</strong>
                  <Chip tone={actionTone(ds)}>{copy.actionState[ds]}</Chip>
                  <span className="muted meta">
                    {a.action ? (copy.ledger.reversibility[a.action.reversibility] ?? a.action.reversibility) : ''}
                    {a.action?.compensation
                      ? `. Rollback ${copy.ledger.rollbackStatus[a.action.compensation.status] ?? 'unknown'}, ${a.action.compensation.attempts} attempt${a.action.compensation.attempts === 1 ? '' : 's'}`
                      : ''}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </section>
      <section className="panel" aria-label={copy.ledger.handoffsTitle}>
        <h2 className="panel-h">{copy.ledger.review}</h2>
        {handoffs.isLoading && <Skeleton lines={3} />}
        {handoffs.isError && <ErrorState error={handoffs.error} onRetry={() => void handoffs.refetch()} />}
        {handoffs.data && reviews.length === 0 && <Empty>{copy.ledger.noHandoffs}</Empty>}
        <ul className="handoffs">{reviews.map((h) => <HandoffCard key={h.id} h={h} />)}</ul>
        <h2 className="panel-h second">{copy.ledger.handoffsTitle}</h2>
        {handoffs.data && tasks.length === 0 && <Empty>{copy.ledger.noHandoffs}</Empty>}
        <ul className="handoffs">{tasks.map((h) => <HandoffCard key={h.id} h={h} />)}</ul>
      </section>
    </div>
  );
}
