import { create } from 'zustand';
import type { GraphEdge, GraphNode, Meta } from '../api/schemas';
import type { Connection } from '../api/events';
import type { Role } from '../api/client';
import { emptyCore, type CoreState } from './reducer';

export type View = 'console' | 'memory' | 'brain' | 'tenants' | 'benchmark';
export type Tab = 'graph' | 'diff' | 'ledger' | 'insights';
export type InspectorTab = 'path' | 'details' | 'links' | 'cypher';
export type FeedFilter = 'all' | 'graph' | 'actions' | 'handoffs' | 'system';

export interface Toast {
  id: number;
  text: string;
}
export interface GraphFilters {
  kinds: Record<string, boolean>;
  statuses: Record<string, boolean>;
  hideHealthy: boolean;
  local: boolean;
  depth: number;
  gods: boolean;
}
export const defaultFilters = (): GraphFilters => ({
  kinds: { source: true, fact: true, conclusion: true, action: true },
  statuses: { HEALTHY: true, QUARANTINED: true, SUPERSEDED: true },
  hideHealthy: false,
  local: false,
  depth: 2,
  gods: false,
});
export interface CtxMenu {
  x: number;
  y: number;
  id: string;
}

export interface PastGraph {
  ts: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface UiState {
  view: View;
  tab: Tab;
  inspectorTab: InspectorTab;
  feedFilter: FeedFilter;
  listView: boolean;
  presentation: boolean;
  demo: boolean;
  devOpen: boolean;
  shortcutsOpen: boolean;
  legendOpen: boolean;
  selectedId: string | null;
  previewIds: string[];
  search: string;
  lockLayout: boolean;
  asOf: number | null;
  past: PastGraph | null;
  compareBase: PastGraph | null;
  reportRoot: string | null;
  conn: Connection;
  graphStale: boolean;
  resyncing: boolean;
  meta: Meta | null;
  versionState: 'ok' | 'minor' | 'major';
  versionBannerDismissed: boolean;
  loaded: boolean;
  loadError: { endpoint: string; message: string } | null;
  toasts: Toast[];
  role: Role;
  tenant: string;
  autopilot: boolean;
  brainQuestion: string | null;
  filters: GraphFilters;
  filtersOpen: boolean;
  pathIds: string[];
  ctxMenu: CtxMenu | null;
  paletteOpen: boolean;
  navStack: string[];
  navIdx: number;
}

interface Actions {
  set: (p: Partial<UiState>) => void;
  setCore: (fn: (c: CoreState) => CoreState) => void;
  pushToast: (text: string) => void;
  dropToast: (id: number) => void;
}

export type Store = CoreState & UiState & Actions;

const params = typeof location !== 'undefined' ? new URLSearchParams(location.search) : new URLSearchParams();
let toastId = 1;

export const useStore = create<Store>((set, get) => ({
  ...emptyCore(),
  view: 'console',
  tab: 'graph',
  inspectorTab: 'path',
  feedFilter: 'all',
  listView: false,
  presentation: false,
  demo: params.get('demo') === '1',
  devOpen: false,
  shortcutsOpen: false,
  legendOpen: false,
  selectedId: null,
  previewIds: [],
  search: '',
  lockLayout: false,
  asOf: null,
  past: null,
  compareBase: null,
  reportRoot: null,
  conn: 'connecting',
  graphStale: false,
  resyncing: false,
  meta: null,
  versionState: 'ok',
  versionBannerDismissed: false,
  loaded: false,
  loadError: null,
  toasts: [],
  role: 'human',
  tenant: 'acme',
  autopilot: false,
  brainQuestion: null,
  filters: defaultFilters(),
  filtersOpen: false,
  pathIds: [],
  ctxMenu: null,
  paletteOpen: false,
  navStack: [],
  navIdx: -1,
  set: (p) => set(p),
  setCore: (fn) => set((s) => fn(s)),
  pushToast: (text) => {
    const id = toastId++;
    set({ toasts: [...get().toasts.slice(-3), { id, text }] });
    setTimeout(() => get().dropToast(id), 5200);
  },
  dropToast: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),
}));

/** The graph the canvas shows: the past snapshot while time-travelling, otherwise the live graph. */
export function visibleGraph(s: Pick<Store, 'nodes' | 'edges' | 'past'>): { nodes: GraphNode[]; edges: GraphEdge[] } {
  if (s.past) return { nodes: s.past.nodes, edges: s.past.edges };
  return { nodes: Object.values(s.nodes), edges: Object.values(s.edges) };
}

/* Selection history, like back and forward in a notes app. */
let navigating = false;
useStore.subscribe((st, prev) => {
  if (navigating || st.selectedId === prev.selectedId || !st.selectedId) return;
  const stack = st.navStack.slice(0, st.navIdx + 1);
  if (stack[stack.length - 1] === st.selectedId) return;
  const next = [...stack, st.selectedId].slice(-40);
  useStore.setState({ navStack: next, navIdx: next.length - 1 });
});

export function navMove(delta: -1 | 1): string | null {
  const { navStack, navIdx } = useStore.getState();
  const idx = navIdx + delta;
  const id = navStack[idx];
  if (id === undefined) return null;
  navigating = true;
  useStore.setState({ navIdx: idx, selectedId: id });
  navigating = false;
  return id;
}
