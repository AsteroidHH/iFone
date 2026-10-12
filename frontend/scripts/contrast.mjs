// Verifies every text/background pairing used in the UI meets WCAG AA (4.5:1) for text, 3:1 for UI strokes.
import { readFileSync } from 'node:fs';

const css = readFileSync(new URL('../src/styles/tokens.css', import.meta.url), 'utf8');
const tokens = Object.fromEntries([...css.matchAll(/--([a-z-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2]]));

const lum = (hex) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
};
const ratio = (a, b) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};

// [foreground token or hex, background token, minimum ratio, where it is used]
const pairs = [
  ['ink', 'paper', 4.5, 'body text on panels'],
  ['ink', 'vellum', 4.5, 'body text on canvas'],
  ['graphite', 'paper', 4.5, 'secondary text on panels'],
  ['graphite', 'vellum', 4.5, 'secondary text on canvas'],
  ['paper', 'ink', 4.5, 'header text'],
  ['verdigris-text', 'verdigris-wash', 4.5, 'healthy chip'],
  ['verdigris-text', 'paper', 4.5, 'healthy text'],
  ['stamp-text', 'stamp-wash', 4.5, 'quarantined chip'],
  ['stamp-text', 'paper', 4.5, 'quarantined text'],
  ['ochre-text', 'ochre-wash', 4.5, 'out-of-date chip'],
  ['ochre-text', 'paper', 4.5, 'out-of-date text'],
  ['ochre-text', 'vellum', 4.5, 'mock banner'],
  ['#2d31b0', 'ultramarine-wash', 4.5, 'review chip'],
  ['#ffffff', 'ultramarine', 4.5, 'review button'],
  ['ink', 'stamp-wash', 4.5, 'removed diff line'],
  ['paper', 'verdigris', 3, 'ui stroke'],
  ['verdigris', 'paper', 3, 'healthy ring'],
  ['stamp', 'paper', 3, 'quarantined ring and edges'],
  ['ink', 'ochre-wash', 4.5, 'mock banner body'],
];

let bad = 0;
for (const [fg, bg, min, use] of pairs) {
  const a = fg.startsWith('#') ? fg : tokens[fg];
  const b = bg.startsWith('#') ? bg : tokens[bg];
  if (!a || !b) {
    console.error(`missing token for ${fg} / ${bg}`);
    bad++;
    continue;
  }
  const r = ratio(a, b);
  const ok = r >= min;
  if (!ok) bad++;
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${r.toFixed(2).padStart(5)}  (min ${min})  ${fg} on ${bg}  ${use}`);
}
console.log('Never used for text: pencil, ochre (#b5760f). Shape and glyph always accompany colour.');
process.exit(bad ? 1 : 0);
