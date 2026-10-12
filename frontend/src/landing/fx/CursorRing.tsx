import { useEffect, useRef } from 'react';
import { fineHover, onPointer, pointer, reducedMotion, startPointer } from './pointer';

const TARGET = 'a,button,[role="button"],input,select,textarea,.lp-pill,[data-cursor]';

/**
 * Registration-mark cursor. A hard ink dot sits on the pointer; a ring trails it. Over anything clickable the ring
 * snaps to that element's outline and fills with mint, and a label ("Open", "Click") can ride along. It also
 * writes --mx/--my onto every [data-spot] section so the spotlight grid can follow the cursor.
 */
export function CursorRing() {
  const root = useRef<HTMLDivElement>(null);
  const dot = useRef<HTMLElement>(null);
  const ring = useRef<HTMLElement>(null);
  const label = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!fineHover() || reducedMotion() || !root.current || !dot.current || !ring.current || !label.current) return;
    startPointer();
    const d = dot.current;
    const r = ring.current;
    const lab = label.current;
    const s = { x: -100, y: -100, w: 38, h: 38, rad: 19, tx: 0, ty: 0 };
    let raf = 0;
    let lastTarget: Element | null = null;
    let spots: HTMLElement[] = [];
    const refresh = () => (spots = Array.from(document.querySelectorAll<HTMLElement>('[data-spot]')));
    refresh();
    const re = setInterval(refresh, 1500);

    const loop = () => {
      raf = 0;
      const t = pointer.over?.closest(TARGET) ?? null;
      let gx = pointer.x;
      let gy = pointer.y;
      let gw = pointer.down ? 26 : 38;
      let gh = gw;
      let grad = gw / 2;
      if (t !== lastTarget) {
        lastTarget = t;
        const text = t?.closest('[data-cursor]')?.getAttribute('data-cursor') ?? '';
        lab.textContent = text;
        r.classList.toggle('snap', !!t);
        r.classList.toggle('has-label', !!text);
      }
      if (t) {
        const b = t.getBoundingClientRect();
        if (b.width < 520 && b.height < 200) {
          gx = b.left + b.width / 2;
          gy = b.top + b.height / 2;
          gw = b.width + 10;
          gh = b.height + 10;
          grad = Math.min(gh / 2, 22);
        } else {
          gw = gh = 60;
          grad = 30;
        }
      }
      const k = t ? 0.3 : 0.2;
      s.x += (gx - s.x) * k;
      s.y += (gy - s.y) * k;
      s.w += (gw - s.w) * 0.25;
      s.h += (gh - s.h) * 0.25;
      s.rad += (grad - s.rad) * 0.25;
      d.style.transform = `translate3d(${pointer.x}px, ${pointer.y}px, 0) translate(-50%, -50%)`;
      r.style.transform = `translate3d(${s.x}px, ${s.y}px, 0) translate(-50%, -50%)`;
      r.style.width = `${s.w}px`;
      r.style.height = `${s.h}px`;
      r.style.borderRadius = `${s.rad}px`;
      const moving = Math.abs(gx - s.x) + Math.abs(gy - s.y) + Math.abs(gw - s.w) + Math.abs(gh - s.h) > 0.3;
      if (moving) raf = requestAnimationFrame(loop);
    };

    const spot = () => {
      for (const el of spots) {
        const b = el.getBoundingClientRect();
        if (b.bottom < 0 || b.top > innerHeight) continue;
        el.style.setProperty('--mx', `${pointer.x - b.left}px`);
        el.style.setProperty('--my', `${pointer.y - b.top}px`);
      }
    };
    const wake = () => {
      root.current?.classList.toggle('on', pointer.seen);
      root.current?.classList.toggle('down', pointer.down);
      spot();
      if (!raf) raf = requestAnimationFrame(loop);
    };
    const off = onPointer(wake);
    window.addEventListener('scroll', spot, { passive: true });
    document.documentElement.classList.add('cr-on');
    return () => {
      off();
      clearInterval(re);
      cancelAnimationFrame(raf);
      window.removeEventListener('scroll', spot);
      document.documentElement.classList.remove('cr-on');
    };
  }, []);

  return (
    <div ref={root} className="cr" aria-hidden="true">
      <i ref={ring} className="cr-ring">
        <b ref={label} className="cr-label" />
      </i>
      <i ref={dot} className="cr-dot" />
    </div>
  );
}
