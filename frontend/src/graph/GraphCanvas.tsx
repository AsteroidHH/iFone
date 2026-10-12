import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { shallow } from 'zustand/shallow';
import { Icon } from '../components/Icon';
import { copy } from '../copy';
import { getPreview } from '../state/endpoints';
import { useStore, visibleGraph } from '../state/store';
import { goToTime } from '../state/timetravel';
import { GraphAdapter } from './adapter';
import { graphBus } from './bus';
import { COL_X, NODE_W } from './layout';
import { ListView } from './ListView';

const KINDS = ['source', 'fact', 'conclusion', 'action'];

export function GraphCanvas({ active }: { active: boolean }) {
  const host = useRef<HTMLDivElement>(null);
  const adapter = useRef<GraphAdapter | null>(null);
  const rails = useRef<(HTMLDivElement | null)[]>([]);
  const [hover, setHover] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [welcomeGone, setWelcomeGone] = useState(false);
  const loaded = useStore((s) => s.loaded);
  const counts = useStore((s) => {
    const nodes = visibleGraph(s).nodes;
    return KINDS.map((k) => nodes.filter((n) => n.kind === k).length);
  }, shallow);
  const selectedId = useStore((s) => s.selectedId);
  const search = useStore((s) => s.search);
  const locked = useStore((s) => s.lockLayout);
  const listView = useStore((s) => s.listView);
  const asOf = useStore((s) => s.asOf);
  const set = useStore((s) => s.set);
  const legendOpen = useStore((s) => s.legendOpen);
  const started = useStore((s) => s.eventLog.length > 0);
  const nodeCount = counts.reduce((a, b) => a + b, 0);

  useEffect(() => {
    if (!host.current) return;
    const a = new GraphAdapter(host.current, {
      onSelect: (id) => useStore.getState().set({ selectedId: id }),
      onHover: setHover,
      onViewport: (pan, zoom) => {
        const w = (NODE_W + 56) * zoom;
        rails.current.forEach((el, i) => {
          if (!el) return;
          el.style.width = `${w}px`;
          el.style.transform = `translateX(${pan.x + (COL_X[i] ?? 0) * zoom - w / 2}px)`;
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
      <div className="canvas-stage">
        <div className="grid" aria-hidden="true" />
        <div className="rails" aria-hidden="true">
          {copy.rails.map((r, i) => (
            <div key={r} className="rail" ref={(el) => (rails.current[i] = el)}>
              <span className="rail-label">
                {r}
                <b className="num">{counts[i]}</b>
              </span>
            </div>
          ))}
        </div>
        <div ref={host} className="cy" role="img" aria-label={copy.canvas.graphAria} />

        <div className="canvas-tools" role="toolbar" aria-label="Graph tools">
          <label className="search">
            <Icon name="search" size={15} />
            <span className="sr">{copy.canvas.search}</span>
            <input
              id="graph-search"
              type="search"
              placeholder={`${copy.canvas.search}  /`}
              value={search}
              onChange={(e) => set({ search: e.target.value })}
            />
          </label>
          <div className="seg" role="group" aria-label="View">
            <button className={`seg-btn${!listView ? ' on' : ''}`} aria-pressed={!listView} onClick={() => set({ listView: false })}>
              <Icon name="graph" size={14} />
              {copy.canvas.graph}
            </button>
            <button className={`seg-btn${listView ? ' on' : ''}`} aria-pressed={listView} onClick={() => set({ listView: true })} title="L">
              <Icon name="list" size={14} />
              {copy.canvas.list}
            </button>
          </div>
          <button className="btn quiet" disabled={!selectedId} onClick={() => graphBus.collapse.emit()}>
            <Icon name="collapse" size={14} />
            {collapsed ? copy.canvas.expand : copy.canvas.collapse}
          </button>
        </div>

        <div className="zoomdock" role="group" aria-label="Zoom">
          <button className="iconbtn" aria-label={copy.canvas.fit} title={`${copy.canvas.fit} (F)`} onClick={() => graphBus.fit.emit()}>
            <Icon name="fit" size={16} />
          </button>
          <button className="iconbtn" aria-label="Zoom in" onClick={() => adapter.current?.zoomBy(1.25)}>
            +
          </button>
          <button className="iconbtn" aria-label="Zoom out" onClick={() => adapter.current?.zoomBy(0.8)}>
            -
          </button>
          <button className="iconbtn" aria-label={copy.canvas.relayout} title={copy.canvas.relayout} onClick={() => graphBus.relayout.emit()}>
            <Icon name="refresh" size={15} />
          </button>
          <button className="iconbtn" aria-pressed={locked} aria-label={locked ? copy.canvas.unlock : copy.canvas.lock} title={locked ? copy.canvas.unlock : copy.canvas.lock} onClick={() => set({ lockLayout: !locked })}>
            <Icon name="lock" size={15} />
          </button>
        </div>

        <div className={`legend${legendOpen ? ' open' : ''}`}>
          <button className="legend-toggle" aria-expanded={legendOpen} onClick={() => set({ legendOpen: !legendOpen })}>
            <Icon name="help" size={14} />
            {copy.canvas.legendTitle}
          </button>
          {legendOpen && (
            <div className="legend-body" role="note">
              <p>{copy.canvas.legend.shapes}</p>
              <p>{copy.canvas.legend.state}</p>
            </div>
          )}
        </div>

        {loaded && nodeCount === 0 && <p className="canvas-empty">{copy.canvas.empty}</p>}
        {!started && !welcomeGone && !asOf && nodeCount > 0 && (
          <div className="welcome" role="note">
            <span className="welcome-ico">
              <Icon name="sparkle" size={18} />
            </span>
            <div>
              <h3>{copy.welcome.title}</h3>
              <p>{copy.welcome.body}</p>
            </div>
            <button className="iconbtn" aria-label={copy.dismiss} onClick={() => setWelcomeGone(true)}>
              <Icon name="x" size={14} />
            </button>
          </div>
        )}
        {listView && <ListView />}
        {asOf && (
          <div className="past-bar" role="status">
            <Icon name="clock" size={15} />
            <strong>{copy.canvas.pastFrame}</strong>
            <span className="mono">{new Date(asOf).toLocaleTimeString([], { hour12: false })}</span>
            <button className="btn" onClick={() => void goToTime(null)}>
              <Icon name="back" size={14} />
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
