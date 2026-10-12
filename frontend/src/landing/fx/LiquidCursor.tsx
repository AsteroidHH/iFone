import { useEffect, useRef } from 'react';
import { fineHover, onPointer, pointer, reducedMotion, startPointer } from './pointer';

const N = 7;

/**
 * A chain of ink blobs trails the cursor on springs. A goo filter fuses them into one liquid body; it stretches
 * with speed and swells over anything clickable. One rAF loop, asleep whenever the cursor is still.
 */
export function LiquidCursor() {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!fineHover() || reducedMotion() || !host.current) return;
    startPointer();
    const dots = Array.from(host.current.querySelectorAll<HTMLElement>('.lq-dot'));
    const pos = dots.map(() => ({ x: -200, y: -200, vx: 0, vy: 0 }));
    let raf = 0;
    let swell = 1;
    let target = 1;
    let lastMove = 0;

    const loop = () => {
      raf = 0;
      let energy = 0;
      target = pointer.over?.closest('a,button,[role="button"],input,.lp-pill') ? 2.3 : pointer.down ? 0.7 : 1;
      swell += (target - swell) * 0.18;
      dots.forEach((d, i) => {
        const p = pos[i]!;
        const lead = i === 0 ? { x: pointer.x, y: pointer.y } : pos[i - 1]!;
        const k = 0.34 - i * 0.032;
        p.vx = (p.vx + (lead.x - p.x) * k) * 0.62;
        p.vy = (p.vy + (lead.y - p.y) * k) * 0.62;
        p.x += p.vx;
        p.y += p.vy;
        energy += Math.abs(p.vx) + Math.abs(p.vy) + Math.abs(lead.x - p.x) + Math.abs(lead.y - p.y);
        const size = (1 - i / (N + 2)) * swell;
        d.style.transform = `translate3d(${p.x.toFixed(1)}px, ${p.y.toFixed(1)}px, 0) translate(-50%, -50%) scale(${size.toFixed(3)})`;
      });
      if (energy > 0.4 || Math.abs(target - swell) > 0.01) raf = requestAnimationFrame(loop);
    };
    const wake = () => {
      lastMove = performance.now();
      host.current?.classList.toggle('live', pointer.seen);
      if (!raf) raf = requestAnimationFrame(loop);
    };
    const off = onPointer(wake);
    const idle = setInterval(() => {
      if (performance.now() - lastMove > 4000) host.current?.classList.remove('live');
    }, 2000);
    document.documentElement.classList.add('lq-on');
    return () => {
      off();
      clearInterval(idle);
      cancelAnimationFrame(raf);
      document.documentElement.classList.remove('lq-on');
    };
  }, []);

  return (
    <div ref={host} className="lq" aria-hidden="true">
      <svg width="0" height="0" focusable="false">
        <defs>
          <filter id="lq-goo" x="-20%" y="-20%" width="140%" height="140%" colorInterpolationFilters="sRGB">
            <feGaussianBlur in="SourceGraphic" stdDeviation="7" result="b" />
            <feColorMatrix in="b" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 22 -9" />
          </filter>
        </defs>
      </svg>
      <div className="lq-goo">
        {Array.from({ length: N }, (_, i) => (
          <i key={i} className="lq-dot" />
        ))}
      </div>
    </div>
  );
}
