import { useEffect, useRef } from 'react';
import { fineHover, onPointer, pointer, reducedMotion, refreshOver, startPointer } from './pointer';

const TARGET = 'a,button,[role="button"],.lp-pill,[data-cursor]';
const FIELD = 'input,select,textarea,[contenteditable="true"]';
const READ = '.lp-h1,.lp-h2,.lp-giant,.lp-lede,.lp-sub';

/**
 * One cursor, two parts. A small dot sits exactly on the pointer. A ring follows with a short ease and, over anything
 * clickable, opens up to that element's outline and inverts what is under it. Both are drawn with
 * mix-blend-mode: difference, so they read on the pale page and on the dark product window alike. A label can ride
 * along ("Live", "Click a node"). Over form fields the real cursor comes back.
 * It also writes --mx/--my onto every [data-spot] section so the dot-grid spotlight can follow the pointer.
 */
export function CursorRing() {
  const dot = useRef<HTMLElement>(null);
  const ring = useRef<HTMLElement>(null);
  const tag = useRef<HTMLElement>(null);
  const fill = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!fineHover() || reducedMotion() || !dot.current || !ring.current || !tag.current || !fill.current) return;
    startPointer();
    const d = dot.current;
    const r = ring.current;
    const tg = tag.current;
    const f = fill.current;
    let lastWake = 0;
    const s = { x: -100, y: -100, w: 34, h: 34, rad: 17 };
    let raf = 0;
    let lastTarget: Element | null = null;
    let mode = '';
    let spots: HTMLElement[] = [];
    const refresh = () => (spots = Array.from(document.querySelectorAll<HTMLElement>('[data-spot]')));
    refresh();
    const re = setInterval(refresh, 1500);

    const setMode = (m: string) => {
      if (m === mode) return;
      mode = m;
      r.dataset.mode = m;
      d.dataset.mode = m;
      document.documentElement.classList.toggle('cr-native', m === 'field');
    };

    const loop = () => {
      raf = 0;
      // A still pointer can end up over something new when the page scrolls or animates: ask again every frame.
      refreshOver();
      const over = pointer.over;
      const field = over?.closest(FIELD) ?? null;
      const t = field ? null : (over?.closest(TARGET) ?? null);
      const reading = !field && !t && !!over?.closest(READ);
      let gx = pointer.x;
      let gy = pointer.y;
      let gw = pointer.down ? 22 : 34;
      let gh = gw;
      let grad = gw / 2;
      setMode(field ? 'field' : t ? 'snap' : reading ? 'read' : '');
      if (t !== lastTarget) {
        lastTarget = t;
        const text = t?.closest('[data-cursor]')?.getAttribute('data-cursor') ?? '';
        tg.textContent = text;
        tg.classList.toggle('on', !!text);
      }
      if (t) {
        const b = t.getBoundingClientRect();
        if (b.width < 560 && b.height < 220) {
          gx = b.left + b.width / 2;
          gy = b.top + b.height / 2;
          // SVG boxes exclude their stroke and hover glow, so give them more room than HTML boxes.
          const pad = t instanceof SVGElement ? 30 : 12;
          gw = b.width + pad;
          gh = b.height + pad;
          grad = Math.min(gh / 2, 24);
        } else {
          gw = gh = 64;
          grad = 32;
        }
      } else if (reading) {
        gw = gh = 56;
        grad = 28;
      }
      const k = t ? 0.34 : 0.26;
      s.x += (gx - s.x) * k;
      s.y += (gy - s.y) * k;
      s.w += (gw - s.w) * 0.3;
      s.h += (gh - s.h) * 0.3;
      s.rad += (grad - s.rad) * 0.3;
      d.style.transform = `translate3d(${pointer.x}px, ${pointer.y}px, 0) translate(-50%, -50%)`;
      r.style.transform = `translate3d(${s.x}px, ${s.y}px, 0) translate(-50%, -50%)`;
      r.style.width = `${s.w}px`;
      r.style.height = `${s.h}px`;
      r.style.borderRadius = `${s.rad}px`;
      f.style.transform = r.style.transform;
      f.style.width = r.style.width;
      f.style.height = r.style.height;
      f.style.borderRadius = r.style.borderRadius;
      tg.style.transform = `translate3d(${s.x}px, ${s.y + s.h / 2 + 16}px, 0) translate(-50%, 0)`;
      const moving = Math.abs(gx - s.x) + Math.abs(gy - s.y) + Math.abs(gw - s.w) + Math.abs(gh - s.h) > 0.25;
      // Stay awake while hovering something (its box can change) and for a moment after any input or scroll.
      if (moving || t || reading || performance.now() - lastWake < 600) raf = requestAnimationFrame(loop);
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
      lastWake = performance.now();
      const on = pointer.seen;
      for (const el of [d, r, f]) el.classList.toggle('on', on);
      d.classList.toggle('down', pointer.down);
      r.classList.toggle('down', pointer.down);
      spot();
      if (!raf) raf = requestAnimationFrame(loop);
    };
    const off = onPointer(wake);
    const onScroll = () => {
      lastWake = performance.now();
      spot();
      if (!raf) raf = requestAnimationFrame(loop);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('wheel', onScroll, { passive: true });
    window.addEventListener('keydown', onScroll);
    window.addEventListener('resize', onScroll);
    document.documentElement.classList.add('cr-on');
    return () => {
      off();
      clearInterval(re);
      cancelAnimationFrame(raf);
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('wheel', onScroll);
      window.removeEventListener('keydown', onScroll);
      window.removeEventListener('resize', onScroll);
      document.documentElement.classList.remove('cr-on', 'cr-native');
    };
  }, []);

  return (
    <div className="cr" aria-hidden="true">
      <i ref={fill} className="cr-fill" />
      <i ref={ring} className="cr-ring" />
      <i ref={dot} className="cr-dot" />
      <b ref={tag} className="cr-tag" />
    </div>
  );
}
