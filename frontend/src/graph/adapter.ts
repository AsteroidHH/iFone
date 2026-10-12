import cytoscape, { type Core, type EdgeSingular, type NodeSingular } from 'cytoscape';
import type { GraphEdge, GraphNode } from '../api/schemas';
import { copy } from '../copy';
import { actionDisplayState } from '../state/actionState';
import { colOf, COL_X, freeSlot, GAP_Y, layoutAll } from './layout';
import { P } from './palette';

export interface AdapterHandlers {
  onSelect: (id: string | null) => void;
  onHover: (id: string | null) => void;
  onViewport: (pan: { x: number; y: number }, zoom: number) => void;
}

const reduced = () => typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
const uri = (svg: string) => `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;

function actionIcon(color: string, blocked: boolean, confirmed: boolean): string {
  const bolt = `<path d="M19 6 L10 21 H17 L15 32 L27 15 H20 Z" fill="${color}"/>`;
  const lock = blocked
    ? `<g transform="translate(24 3)"><rect x="0" y="5" width="11" height="8" fill="${P.ultramarine}"/><path d="M2 5 V3 a3.5 3.5 0 0 1 7 0 V5" fill="none" stroke="${P.ultramarine}" stroke-width="1.6"/></g>`
    : '';
  const check = confirmed
    ? `<path d="M24 8 L28 12 L35 3" fill="none" stroke="${P.verdigris}" stroke-width="2.4"/>`
    : '';
  return uri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 38 38">${bolt}${lock}${check}</svg>`);
}

function toData(n: GraphNode): cytoscape.NodeDataDefinition {
  const isAction = n.kind === 'action';
  const display = isAction ? copy.actionState[actionDisplayState(n)] : '';
  const color = n.status === 'QUARANTINED' ? P.stamp : n.status === 'SUPERSEDED' ? P.pencil : P.ink;
  return {
    id: n.id,
    label: n.label,
    label2: isAction ? `${n.label}\n${display}` : n.label,
    kind: n.kind,
    status: n.status,
    stale: n.stale && n.status === 'HEALTHY' ? 1 : 0,
    decision: n.is_decision ? 1 : 0,
    img: isAction ? actionIcon(color, n.action?.gate === 'BLOCKED' && !n.action.executed, !!n.action?.confirmed) : '',
  };
}

const style: cytoscape.StylesheetJson = [
  {
    selector: 'node',
    style: {
      'font-family': '"Schibsted Grotesk", system-ui, sans-serif',
      'font-size': 12,
      color: P.ink,
      label: 'data(label2)',
      'text-valign': 'bottom',
      'text-halign': 'center',
      'text-margin-y': 6,
      'text-wrap': 'wrap',
      'text-max-width': '150px',
      'text-background-color': P.paper,
      'text-background-opacity': 0.82,
      'text-background-padding': '1px',
      'min-zoomed-font-size': 7,
      'background-color': P.paper,
      'border-width': 2,
      'border-color': P.ink,
      'overlay-opacity': 0,
      'overlay-padding': 8,
      'transition-property': 'opacity',
      'transition-duration': 160,
    },
  },
  { selector: 'node[kind="source"]', style: { shape: 'cut-rectangle', width: 46, height: 34, 'border-width': 1.5 } },
  { selector: 'node[kind="fact"]', style: { shape: 'ellipse', width: 34, height: 34 } },
  { selector: 'node[kind="conclusion"]', style: { shape: 'round-rectangle', width: 64, height: 32 } },
  {
    selector: 'node[kind="conclusion"][decision > 0]',
    style: { shape: 'rectangle', width: 66, height: 38, 'border-style': 'double', 'border-width': 5 },
  },
  {
    selector: 'node[kind="action"]',
    style: {
      shape: 'rectangle',
      width: 38,
      height: 38,
      'background-image': 'data(img)',
      'background-fit': 'contain',
      'background-clip': 'none',
      'background-width': '100%',
      'background-height': '100%',
    },
  },
  { selector: 'node[status="HEALTHY"]', style: { 'border-color': P.verdigris } },
  { selector: 'node[kind="source"][status="HEALTHY"]', style: { 'border-color': P.ink } },
  {
    selector: 'node[status="QUARANTINED"]',
    style: { 'border-color': P.stamp, 'border-style': 'dashed', 'background-color': P.stampWash, color: P.stamp },
  },
  {
    selector: 'node[status="SUPERSEDED"]',
    style: { 'border-color': P.pencil, 'background-color': P.vellum, color: P.graphite, opacity: 0.55 },
  },
  { selector: 'node[status="UNKNOWN"]', style: { 'border-color': P.graphite, 'border-style': 'dotted' } },
  { selector: 'node[stale > 0]', style: { 'border-color': P.ochre, 'border-style': 'dotted', 'border-width': 3 } },
  { selector: 'node:selected', style: { 'overlay-color': P.ink, 'overlay-opacity': 0.12, 'overlay-padding': 9 } },
  { selector: 'node.dry', style: { 'overlay-color': P.stamp, 'overlay-opacity': 0.22, 'overlay-padding': 10 } },
  { selector: 'node.pulse', style: { 'overlay-color': P.stamp, 'overlay-opacity': 0.4, 'overlay-padding': 18 } },
  { selector: '.faded', style: { opacity: 0.18 } },
  { selector: '.hidden', style: { display: 'none' } },
  {
    selector: 'edge',
    style: {
      width: 1.4,
      'line-color': P.edge,
      'target-arrow-color': P.edge,
      'target-arrow-shape': 'triangle',
      'arrow-scale': 0.9,
      'curve-style': 'bezier',
      opacity: 0.9,
    },
  },
  { selector: 'edge[type="SUPPORTS"]', style: { 'line-style': 'dashed', 'line-dash-pattern': [6, 4] } },
  { selector: 'edge[type="FROM_SOURCE"]', style: { width: 0.9, 'target-arrow-shape': 'none' } },
  {
    selector: 'edge[type="CONTRADICTS"]',
    style: { 'line-color': P.stamp, 'target-arrow-color': P.stamp, 'target-arrow-shape': 'tee', width: 2.4 },
  },
  {
    selector: 'edge[type="SUPERSEDES"]',
    style: { 'line-color': P.pencil, 'target-arrow-color': P.pencil, 'line-style': 'dashed', 'line-dash-pattern': [14, 7] },
  },
  {
    selector: 'edge[tq > 0][type!="CONTRADICTS"]',
    style: { 'line-color': P.stamp, 'target-arrow-color': P.stamp, 'line-style': 'dashed', 'line-dash-pattern': [5, 4] },
  },
  { selector: 'edge.dry', style: { 'line-color': P.stamp, 'target-arrow-color': P.stamp, width: 2.4 } },
];

export class GraphAdapter {
  readonly cy: Core;
  private timers = new Set<ReturnType<typeof setTimeout>>();
  private collapsedRoots = new Set<string>();
  private fresh = new Set<string>();
  private search = '';
  private autoFit = true;
  private fitTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(container: HTMLElement, private h: AdapterHandlers) {
    this.cy = cytoscape({
      container,
      style,
      elements: [],
      minZoom: 0.25,
      maxZoom: 2.5,
      boxSelectionEnabled: false,
      autoungrabify: false,
    });
    this.cy.on('tap', 'node', (e) => h.onSelect((e.target as NodeSingular).id()));
    this.cy.on('tap', (e) => {
      if (e.target === this.cy) h.onSelect(null);
    });
    this.cy.on('mouseover', 'node', (e) => h.onHover((e.target as NodeSingular).id()));
    this.cy.on('mouseout', 'node', () => h.onHover(null));
    this.cy.on('viewport', () => h.onViewport(this.cy.pan(), this.cy.zoom()));
    const manual = () => {
      this.autoFit = false;
    };
    container.addEventListener('wheel', manual, { passive: true });
    container.addEventListener('pointerdown', manual);
    h.onViewport(this.cy.pan(), this.cy.zoom());
  }

  destroy() {
    if (this.fitTimer) clearTimeout(this.fitTimer);
    this.timers.forEach(clearTimeout);
    this.timers.clear();
    this.cy.destroy();
  }

  private later(ms: number, fn: () => void) {
    const t = setTimeout(() => {
      this.timers.delete(t);
      fn();
    }, ms);
    this.timers.add(t);
  }

  syncAll(nodes: GraphNode[], edges: GraphEdge[], fit = true) {
    this.timers.forEach(clearTimeout);
    this.timers.clear();
    this.fresh.clear();
    const pos = layoutAll(nodes, edges);
    const sel = this.cy.$(':selected').map((n) => n.id());
    this.cy.batch(() => {
      this.cy.elements().remove();
      this.cy.add(nodes.map((n) => ({ group: 'nodes' as const, data: toData(n), position: pos[n.id] ?? { x: 0, y: 0 } })));
      const ids = new Set(nodes.map((n) => n.id));
      this.cy.add(
        edges
          .filter((e) => ids.has(e.source) && ids.has(e.target))
          .map((e) => ({ group: 'edges' as const, data: this.edgeData(e, nodes) })),
      );
    });
    sel.forEach((id) => this.cy.getElementById(id).select());
    this.applyCollapse();
    this.applySearch();
    if (fit) this.fit(false);
  }

  private edgeData(e: GraphEdge, nodes?: GraphNode[]) {
    const tgt = nodes ? nodes.find((n) => n.id === e.target) : undefined;
    const status = tgt ? tgt.status : (this.cy.getElementById(e.target).data('status') as string | undefined);
    return { id: e.id, source: e.source, target: e.target, type: e.type, tq: status === 'QUARANTINED' ? 1 : 0 };
  }

  private columnYs(col: number, except?: string): number[] {
    return this.cy
      .nodes()
      .filter((n: NodeSingular) => n.id() !== except && COL_X.indexOf(Math.round(n.position('x'))) === col)
      .map((n: NodeSingular) => n.position('y'));
  }

  /** Adds new elements and updates changed ones. Existing positions never move. */
  applyDelta(nodes: Record<string, GraphNode>, edges: Record<string, GraphEdge>, d: { ids: string[]; edgeIds: string[]; delays: Record<string, number> }) {
    for (const id of d.ids) {
      const n = nodes[id];
      if (!n) continue;
      const existing = this.cy.getElementById(id);
      if (existing.empty()) {
        const col = colOf(n);
        const ys = this.columnYs(col);
        const want = ys.length ? Math.max(...ys) + GAP_Y : 0;
        this.cy.add({ group: 'nodes', data: toData(n), position: { x: COL_X[col] ?? 0, y: want } });
        this.fresh.add(id);
        this.applySearch();
        this.scheduleFit();
      } else {
        const delay = d.delays[id] ?? 0;
        const quarantining = n.status === 'QUARANTINED' || existing.data('status') === 'QUARANTINED';
        if (delay > 0 || (quarantining && id in d.delays)) {
          this.later(delay, () => this.updateNode(n, true));
        } else {
          this.updateNode(n, id in d.delays);
        }
      }
    }
    for (const eid of d.edgeIds) {
      const e = edges[eid];
      if (!e || this.cy.getElementById(eid).nonempty()) continue;
      if (this.cy.getElementById(e.source).empty() || this.cy.getElementById(e.target).empty()) continue;
      this.cy.add({ group: 'edges', data: this.edgeData(e) });
      this.adopt(e);
    }
  }

  /** A freshly added node moves once, next to its first parent, then stays put. */
  private adopt(e: GraphEdge) {
    if (e.type === 'CONTRADICTS' || e.type === 'SUPERSEDES') return;
    const child = this.cy.getElementById(e.target);
    if (!this.fresh.has(e.target) || child.empty()) return;
    const parent = this.cy.getElementById(e.source);
    if (parent.empty()) return;
    const col = COL_X.indexOf(Math.round(child.position('x')));
    const y = freeSlot(this.columnYs(col, e.target), parent.position('y'));
    child.position({ x: child.position('x'), y });
    this.fresh.delete(e.target);
  }

  private updateNode(n: GraphNode, pulse: boolean) {
    const el = this.cy.getElementById(n.id);
    if (el.empty()) return;
    el.data(toData(n));
    el.connectedEdges().forEach((edge: EdgeSingular) => {
      const t = this.cy.getElementById(edge.data('target') as string);
      edge.data('tq', t.data('status') === 'QUARANTINED' ? 1 : 0);
    });
    if (pulse) this.pulse(el);
  }

  private pulse(el: NodeSingular) {
    el.addClass('pulse');
    this.later(reduced() ? 260 : 520, () => el.removeClass('pulse'));
  }

  resized() {
    this.cy.resize();
    if (this.autoFit) this.fitView(false);
    else this.h.onViewport(this.cy.pan(), this.cy.zoom());
  }

  private scheduleFit() {
    if (!this.autoFit) return;
    if (this.fitTimer) clearTimeout(this.fitTimer);
    this.fitTimer = setTimeout(() => {
      if (this.autoFit) this.fitView(true);
    }, 220);
  }

  fit(animate = true) {
    this.autoFit = true;
    this.fitView(animate);
  }

  private fitView(animate: boolean) {
    const els = this.cy.elements(':visible');
    if (els.empty()) return;
    if (animate && !reduced()) this.cy.animate({ fit: { eles: els, padding: 56 } }, { duration: 260 });
    else this.cy.fit(els, 56);
    this.h.onViewport(this.cy.pan(), this.cy.zoom());
  }

  focus(id: string) {
    const el = this.cy.getElementById(id);
    if (el.empty()) return;
    this.cy.$(':selected').unselect();
    el.select();
    if (reduced()) this.cy.center(el);
    else this.cy.animate({ center: { eles: el } }, { duration: 240 });
  }

  setSelected(id: string | null) {
    this.cy.$(':selected').unselect();
    if (id) this.cy.getElementById(id).select();
  }

  setDry(ids: string[]) {
    this.cy.elements('.dry').removeClass('dry');
    if (!ids.length) return;
    const set = new Set(ids);
    this.cy.nodes().forEach((n) => {
      if (set.has(n.id())) n.addClass('dry');
    });
    this.cy.edges().forEach((e) => {
      if (set.has(e.data('source') as string) && set.has(e.data('target') as string)) e.addClass('dry');
    });
  }

  setSearch(q: string) {
    this.search = q.trim().toLowerCase();
    this.applySearch();
  }

  private applySearch() {
    this.cy.batch(() => {
      this.cy.elements().removeClass('faded');
      if (!this.search) return;
      this.cy.nodes().forEach((n) => {
        if (!String(n.data('label')).toLowerCase().includes(this.search)) n.addClass('faded');
      });
      this.cy.edges().addClass('faded');
    });
  }

  setLocked(locked: boolean) {
    this.cy.nodes().ungrabify();
    if (!locked) this.cy.nodes().grabify();
  }

  relayout(nodes: GraphNode[], edges: GraphEdge[]) {
    const pos = layoutAll(nodes, edges);
    this.cy.batch(() => {
      this.cy.nodes().forEach((n) => {
        const p = pos[n.id()];
        if (p) n.position(p);
      });
    });
    this.fit(true);
  }

  toggleCollapse(id: string | null) {
    if (!id) return;
    if (this.collapsedRoots.has(id)) this.collapsedRoots.delete(id);
    else this.collapsedRoots.add(id);
    this.applyCollapse();
  }

  isCollapsed(id: string | null) {
    return !!id && this.collapsedRoots.has(id);
  }

  private applyCollapse() {
    this.cy.batch(() => {
      this.cy.elements().removeClass('hidden');
      for (const root of this.collapsedRoots) {
        if (this.cy.getElementById(root).empty()) continue;
        const seen = new Set<string>();
        const queue = [root];
        while (queue.length) {
          const cur = queue.shift() as string;
          this.cy.edges().forEach((e) => {
            const type = e.data('type') as string;
            if (e.data('source') !== cur || (type !== 'LEADS_TO' && type !== 'SUPPORTS')) return;
            const t = e.data('target') as string;
            if (!seen.has(t)) {
              seen.add(t);
              queue.push(t);
            }
          });
        }
        seen.forEach((id) => {
          const el = this.cy.getElementById(id);
          el.addClass('hidden');
          el.connectedEdges().addClass('hidden');
        });
      }
    });
  }
}
