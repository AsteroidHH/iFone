import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { copy } from '../copy';
import { getPreview } from '../state/endpoints';
import { useStore, visibleGraph } from '../state/store';
import { goToTime } from '../state/timetravel';
import { GraphAdapter } from './adapter';
import { graphBus } from './bus';
import { COL_X } from './layout';
import { ListView } from './ListView';

export function GraphCanvas({ active }: { active: boolean }) {
  const host = useRef<HTMLDivElement>(null);
  const adapter = useRef<GraphAdapter | null>(null);
  const rails = useRef<(HTMLDivElement | null)[]>([]);
  const [hover, setHover] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const loaded = useStore((s) => s.loaded);
  const nodeCount = useStore((s) => (s.past ? s.past.nodes.length : Object.keys(s.nodes).length));
  const selectedId = useStore((s) => s.selectedId);
  const search = useStore((s) => s.search);
  const locked = useStore((s) => s.lockLayout);
  const listView = useStore((s) => s.listView);
  const asOf = useStore((s) => s.asOf);
  const set = useStore((s) => s.set);
  const legendOpen = useStore((s) => s.legendOpen);

  useEffect(() => {
    if (!host.current) return;
    const a = new GraphAdapter(host.current, {
      onSelect: (id) => useStore.getState().set({ selectedId: id }),
      onHover: setHover,
      onViewport: (pan, zoom) => {
        rails.current.forEach((el, i) => {
          if (el) el.style.transform = `translateX(${pan.x + (COL_X[i] ?? 0) * zoom}px)`;
        });
      },
    });
    adapter.current = a;
    const ro = new ResizeObserver(() => {
      if (host.current && host.current.clientWidth > 0) a.resized();
    });
    ro.observe(host.current);
    const sync = (fit: boolean) => {
      const g = visibleGraph(useStore.getState());
      a.syncAll(g.nodes, g.edges, fit);
    };
    if (useStore.getState().loaded) sync(true);
    const offs = [
      graphBus.full.on(() => sync(true)),
      graphBus.delta.on((d) => {
        const st = useStore.getState();
        a.applyDelta(st.nodes, st.edges, d);
      }),
      graphBus.fit.on(() => a.fit(true)),
      graphBus.focus.on((id) => a.focus(id)),
      graphBus.relayout.on(() => {
        const g = visibleGraph(useStore.getState());
        a.relayout(g.nodes, g.edges);
      }),
      graphBus.collapse.on(() => {
        a.toggleCollapse(useStore.getState().selectedId);
        setCollapsed(a.isCollapsed(useStore.getState().selectedId));
      }),
    ];
    return () => {
      ro.disconnect();
      offs.forEach((o) => o());
      a.destroy();
      adapter.current = null;
    };
  }, []);

  useEffect(() => {
    if (loaded && adapter.current) {
      const g = visibleGraph(useStore.getState());
      adapter.current.syncAll(g.nodes, g.edges, true);
    }
  }, [loaded]);

  useEffect(() => {
    adapter.current?.setSelected(selectedId);
    setCollapsed(adapter.current?.isCollapsed(selectedId) ?? false);
  }, [selectedId]);
  useEffect(() => adapter.current?.setSearch(search), [search]);
  useEffect(() => adapter.current?.setLocked(locked), [locked]);
  useEffect(() => {
    if (!active || !adapter.current) return;
    adapter.current.cy.resize();
    adapter.current.fit(false);
  }, [active, listView]);

  const preview = useQuery({
    queryKey: ['preview', hover],
    queryFn: () => getPreview(hover as string),
    enabled: !!hover && !asOf,
    staleTime: 1000,
  });
  useEffect(() => {
    const ids = hover && preview.data && !asOf ? preview.data.node_ids : [];
    adapter.current?.setDry(ids.length > 1 ? ids : []);
    set({ previewIds: ids });
  }, [hover, preview.data, asOf, set]);

  const dry = preview.data;

  return (
    <div className={`canvas-wrap${asOf ? ' is-past' : ''}`} hidden={!active}>
      <div className="canvas-tools" role="toolbar" aria-label="Graph tools">
        <button className="btn" onClick={() => graphBus.fit.emit()} title="F">
          {copy.canvas.fit}
        </button>
        <button className="btn" disabled={!selectedId} onClick={() => graphBus.collapse.emit()}>
          {collapsed ? copy.canvas.expand : copy.canvas.collapse}
        </button>
        <button className="btn" onClick={() => graphBus.relayout.emit()}>
          {copy.canvas.relayout}
        </button>
        <button className="btn" aria-pressed={locked} onClick={() => set({ lockLayout: !locked })}>
          {locked ? copy.canvas.unlock : copy.canvas.lock}
        </button>
        <label className="search">
          <span className="sr">{copy.canvas.search}</span>
          <input
            id="graph-search"
            type="search"
            placeholder={`${copy.canvas.search} (/)`}
            value={search}
            onChange={(e) => set({ search: e.target.value })}
          />
        </label>
        <button className="btn" aria-pressed={listView} onClick={() => set({ listView: !listView })} title="L">
          {listView ? copy.canvas.graph : copy.canvas.list}
        </button>
        <button className="btn ghost" aria-expanded={legendOpen} onClick={() => set({ legendOpen: !legendOpen })}>
          {copy.canvas.legendTitle}
        </button>
      </div>

      {legendOpen && (
        <div className="legend" role="note">
          <p>{copy.canvas.legend.shapes}</p>
          <p>{copy.canvas.legend.state}</p>
        </div>
      )}

      <div className="canvas-stage">
        <div className="grid" aria-hidden="true" />
        <div className="rails" aria-hidden="true">
          {copy.rails.map((r, i) => (
            <div key={r} className="rail" ref={(el) => (rails.current[i] = el)}>
              <span>{r}</span>
            </div>
          ))}
        </div>
        <div ref={host} className="cy" role="img" aria-label={copy.canvas.graphAria} />
        {loaded && nodeCount === 0 && <p className="canvas-empty">{copy.canvas.empty}</p>}
        {listView && <ListView />}
        {asOf && (
          <div className="past-bar" role="status">
            <strong>{copy.canvas.pastFrame}</strong>
            <span className="mono">{new Date(asOf).toLocaleTimeString([], { hour12: false })}</span>
            <button className="btn" onClick={() => void goToTime(null)}>
              {copy.canvas.backToNow}
            </button>
          </div>
        )}
        {dry && hover && dry.node_ids.length > 1 && !asOf && (
          <div className="dry-run" role="status">
            <strong>{copy.containment.dryRun}</strong>
            <span>
              {copy.containment.dryRunLine(
                dry.facts,
                dry.conclusions,
                dry.actions.staged,
                dry.actions.executed_reversible + dry.actions.executed_compensable,
                dry.actions.executed_irreversible,
              )}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
