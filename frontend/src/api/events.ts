import { fetchEventSource } from '@microsoft/fetch-event-source';
import { API_MODE, tokenFor } from './client';
import { devLog } from './devlog';
import { SseEvent } from './schemas';
import { mockBackend } from '../mocks/backend';

export type Connection = 'connecting' | 'live' | 'reconnecting' | 'offline';

interface Handlers {
  lastSeq: () => number;
  onEvent: (e: SseEvent) => void;
  onStatus: (c: Connection) => void;
}

function accept(raw: unknown, onEvent: (e: SseEvent) => void) {
  const r = SseEvent.safeParse(raw);
  if (r.success) {
    onEvent(r.data);
    return;
  }
  const t = (raw as { type?: string } | null)?.type ?? 'unknown';
  devLog('warn', `Ignored SSE event "${t}": ${r.error.issues[0]?.path.join('.') ?? ''} ${r.error.issues[0]?.message ?? ''}`, true);
}

/** Opens the event stream and returns a close function. Mock mode and live mode share the same validation path. */
export function openEventStream(h: Handlers): () => void {
  if (API_MODE === 'mock') {
    h.onStatus('live');
    return mockBackend.subscribe(tokenFor(), h.lastSeq(), (env) => accept(JSON.parse(JSON.stringify(env)), h.onEvent));
  }

  const ctl = new AbortController();
  const token = tokenFor();
  h.onStatus('connecting');
  void fetchEventSource('/api/events', {
    signal: ctl.signal,
    openWhenHidden: true,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(h.lastSeq() > 0 ? { 'Last-Event-ID': String(h.lastSeq()) } : {}),
    },
    async onopen(res) {
      if (!res.ok) throw new Error(`events ${res.status}`);
      h.onStatus('live');
    },
    onmessage(msg) {
      if (!msg.data) return;
      try {
        accept(JSON.parse(msg.data), h.onEvent);
      } catch {
        devLog('warn', 'Ignored an SSE message that was not JSON.', true);
      }
    },
    onclose() {
      h.onStatus('reconnecting');
    },
    onerror() {
      h.onStatus('reconnecting');
      return 2000;
    },
  });
  return () => {
    ctl.abort();
    h.onStatus('offline');
  };
}
