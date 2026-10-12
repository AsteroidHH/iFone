import { useInView } from '../hooks';

/** Recorded numbers only: the three measured latency percentiles from the benchmark run. */
const BARS: [string, number][] = [
  ['p50', 12.6],
  ['p95', 23.08],
  ['p99', 28.88],
];

export function LatencyChart() {
  const [ref, seen] = useInView<HTMLDivElement>(0.35);
  const max = 32;
  const W = 520;
  const rowH = 46;
  const left = 46;
  const ticks = [0, 10, 20, 30];
  return (
    <div ref={ref} className={`lp-chart${seen ? ' in' : ''}`}>
      <p className="lp-k">Latency under load · ms</p>
      <svg viewBox={`0 0 ${W} ${BARS.length * rowH + 34}`} role="img" aria-label="Measured latency: p50 12.60 milliseconds, p95 23.08, p99 28.88">
        {ticks.map((t) => {
          const x = left + (t / max) * (W - left - 16);
          return (
            <g key={t}>
              <line x1={x} x2={x} y1={0} y2={BARS.length * rowH} className="grid" />
              <text x={x} y={BARS.length * rowH + 22} textAnchor="middle" className="tick">
                {t}
              </text>
            </g>
          );
        })}
        {BARS.map(([name, v], i) => {
          const w = (v / max) * (W - left - 16);
          const y = i * rowH + 8;
          return (
            <g key={name}>
              <text x={0} y={y + 20} className="lab">
                {name}
              </text>
              <rect x={left} y={y} height={28} width={w} className="bar" style={{ transitionDelay: `${i * 140}ms` }} />
              <text x={left + w + 8} y={y + 20} className="val" style={{ transitionDelay: `${i * 140 + 500}ms` }}>
                {v.toFixed(2)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
