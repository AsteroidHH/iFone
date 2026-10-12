/** One shared pointer tracker for every cursor-driven effect on the landing page. */
export const pointer = { x: -9999, y: -9999, down: false, seen: false, over: null as Element | null };

const subs = new Set<() => void>();
let started = false;

export const reducedMotion = () => typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
export const fineHover = () => typeof matchMedia !== 'undefined' && matchMedia('(hover: hover) and (pointer: fine)').matches;

export function startPointer() {
  if (started || typeof window === 'undefined') return;
  started = true;
  window.addEventListener(
    'pointermove',
    (e) => {
      pointer.x = e.clientX;
      pointer.y = e.clientY;
      pointer.seen = true;
      pointer.over = e.target instanceof Element ? e.target : null;
      subs.forEach((f) => f());
    },
    { passive: true },
  );
  window.addEventListener('pointerdown', () => {
    pointer.down = true;
    subs.forEach((f) => f());
  });
  window.addEventListener('pointerup', () => {
    pointer.down = false;
    subs.forEach((f) => f());
  });
  document.addEventListener('pointerleave', () => {
    pointer.seen = false;
    subs.forEach((f) => f());
  });
}

export function onPointer(f: () => void): () => void {
  subs.add(f);
  return () => {
    subs.delete(f);
  };
}
