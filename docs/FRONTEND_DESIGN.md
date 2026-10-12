# Console design

Direction: a print proof room, shared with the landing page. Cool off-white stock, ink black outlines, hard offset shadows on the pieces that matter, crop marks at the viewport corners, Bricolage Grotesque for headings, Silkscreen pixel numerals for anything countable, JetBrains Mono for labels and ids. State colours are signals only: mint for healthy, red for quarantined, amber for out of date, periwinkle for "a person decides".

History of the direction: the first console was a light ledger, then a dark "incident command room". The owner asked for the console to look like the landing page, so the console now uses the same system. The role names in `src/styles/tokens.css` did not change, only their values, which is why one stylesheet pass (`proof-room.css`) restyled every view.

## Tokens (`src/styles/tokens.css`)

| Role | Token | Value |
|---|---|---|
| Stock / card / inset | `--bg` / `--bg-2` / `--bg-3` / `--bg-4` | #f3f5f2 / #ffffff / #eef1ed / #e3e8e2 |
| Ink | `--text` / `--text-2` / `--text-3` | #0b1218 / #46525e / #5d6975 |
| Healthy | `--ok`, `--mint` | #07745e text, #3ddbb0 fill |
| Quarantined | `--bad`, `--redfill` | #c93420 text, #ff6a55 fill |
| Out of date | `--warn` | #8f5a00 |
| Person decides | `--person` | #3b3fd1 |
| Replaced | `--ghost` | #6b7783 |

`npm run contrast` checks every console and landing pair (text at 4.5:1, rings at 3:1). Colour never carries state alone: shape, border style, glyph or label always accompany it.

## Structure

- Header: brand (back to the landing page), view switcher with number keys, tenant, data-source chip, agent mode, epoch, invariants, connection, search button for the command palette, presentation mode, help.
- Console: left column holds the story stepper and history; the centre card holds the graph, prompt diff, actions and handoffs, and insights; the right column holds the containment report and inspector; the timeline runs underneath.
- Secondary pages use one template: numbered tag, giant title, one sentence, cards.

## The canvas

Node shapes keep their meaning: source (cut corners), fact (pill), conclusion (rounded box), decision (double border), action (square corners). Healthy nodes are mint with an ink outline; quarantined are red wash with a dashed red outline; out of date has a dotted amber outline; replaced are faded. Columns are fixed by kind, with a counted header each. Edges are orthogonal and turn dashed red once their target is quarantined.

## Navigation and analysis

Borrowed as ideas from Obsidian (graph view, local graph, backlinks, quick switcher, back and forward through notes) and Graphify (god nodes, communities, path and explain queries). All computed client-side from the live nodes and edges, with unit tests in `src/state/insights.test.ts`.

| Feature | Where | Notes |
|---|---|---|
| Command palette | Ctrl K, or the header search button | Fuzzy search over beliefs, views, story steps and canvas commands |
| Graph filters | Canvas toolbar | Kinds, statuses, "only what needs attention", highlight most connected nodes |
| Local graph | Filters, or the node context menu | The selection and everything within 1 to 4 hops, refit on change |
| Selection history | Back and forward buttons, Alt Left, Alt Right | Like back and forward in a notes app |
| Breadcrumb | Under the tabs | Console / Graph / kind / selected node |
| Backlinks | Inspector, Links tab | Built from, feeds, connection count, plain-language explanation |
| Context menu | Right-click a node | Center, inspect, trace to sources, local graph, preview blast radius, collapse, copy id |
| Minimap | Bottom left of the canvas | Click to move the view; selected node in amber |
| Path highlight | Insights, or the context menu | The shortest chain between two nodes, drawn on the graph |
| Insights tab | Centre card | Belief flow ribbons, health bar, activity over time, most connected nodes, communities, shortest path, explain the selection |
| Activity strip | Timeline | Event density behind the slider |
| Keyboard | `?` for the full list | 1 to 5 switch views; F fit; / search; L list; P presentation |

## Motion

Two orchestrated moments: the quarantine wave (each node pulses at 120 ms per hop) and the claim race. Everything else is a short response to a click. `prefers-reduced-motion` turns the wave into an instant change with a brief highlight.

## Voice

Plain and specific. Statuses: Healthy, Quarantined, Replaced by a newer fact, Out of date. Actions: Staged, Held for review, Ran, Rolled back, Needs a person. Buttons name the result. Errors say what failed and what to do. All strings live in `src/copy/`.

## Honesty

A "Sample data" chip sits in the header whenever the scripted in-browser backend is active; it explains itself on hover. Benchmark numbers and every other figure come from the API (or, in sample mode, from a labelled fixture).

## Verification

`npm run verify` runs typecheck, unit tests, contrast, contract check and the production build. `npm run screens`, `npm run qa`, `npm run landing` and `node scripts/feature-shots.mjs` drive the app headlessly; screenshots land in `docs/screens/` and are reviewed before a beat counts as done.
