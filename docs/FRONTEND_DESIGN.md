# Quorum frontend design

Direction: an incident command room. Graphite surfaces, one signal colour per state, card-style evidence nodes on a dot grid, big numerals for the numbers that matter, and a guided story stepper so the first minute makes sense without a briefing.

This replaces the first plan (a light "forensic ledger on drafting paper"). That version was accurate but read as a prototype: flat, low contrast between regions, and no focal point. The brief's art direction is a starting point; the owner asked for a polished product, so the pack's light palette was dropped. The rules that mattered stay: status never rides on colour alone, nothing on screen is invented, the quarantine wave and the prompt diff are where the boldness goes.

## Palette (CSS variables in `src/styles/tokens.css`)

| Role | Token | Value | Used for |
|---|---|---|---|
| Page | `--bg` | #080d13 | background |
| Card | `--bg-2` / `--bg-3` / `--bg-4` | #0d141c / #121b25 / #19242f | surfaces, three steps of elevation |
| Text | `--text` / `--text-2` / `--text-3` | #e9eef4 / #a3b0bf / #8392a3 | body, secondary, captions |
| Healthy | `--ok` | #3ddbb0 | healthy rings, success |
| Quarantined | `--bad` | #ff6a55 | quarantine, dashed edges, errors |
| Out of date | `--warn` | #f4b94f | stale rings, sample-data chip |
| Person decides | `--person` | #8f9bff | review handoffs, replay mode, "viewing the past", Autopilot |
| Superseded | `--ghost` | #8190a3 | ghost nodes |

`npm run contrast` checks every text and surface pair at 4.5:1 and every ring at 3:1, compositing translucent tints over the surface they sit on. The periwinkle `--person` is reserved for "a person or a replay is in charge", so it never competes with the green and red state colours.

## Type

Schibsted Grotesk (400, 500, 700) for everything; tabular figures on numbers. JetBrains Mono only for ids, Cypher and server output. Scale 12, 13, 14, 16, 20, 28, 44. Sentence case. Both families are bundled, so the app works offline.

## Structure

- Header: brand, view switcher, then tenant, data source chip, agent mode, epoch, invariants, connection. Narrow widths drop labels before dropping meaning.
- Console: left column holds the story stepper and the history feed; the centre is the graph with floating search, view toggle and zoom dock; the right column holds the containment report (collapses when a node is selected) and the inspector; the timeline runs underneath.
- Secondary views use one page template: title, one sentence, cards.

## The canvas

Nodes are cards with the shape language kept from the brief: source (cut corners), fact (pill), conclusion (rounded box), decision (double border), action (square corners, bolt). State is carried by border style and a glyph as well as colour: solid green healthy, dashed red quarantined, dotted amber out of date, faded ghost for replaced, lock for held-for-review, check for confirmed. Columns are fixed by kind with a labelled, counted header per column. Edges are orthogonal, dashed red once their target is quarantined.

## Motion

Two orchestrated moments: the quarantine wave (each node pulses at 120 ms per hop) and the claim race. Everything else is a short response to a click. `prefers-reduced-motion` turns the wave into an instant change with a brief highlight.

## Voice

Plain and specific. Statuses: Healthy, Quarantined, Replaced by a newer fact, Out of date. Actions: Staged, Held for review, Ran, Rolled back, Needs a person. Buttons name the result. Errors say what failed and what to do. All strings are in `src/copy/`.

## Honesty

A "Sample data" chip sits in the header whenever the scripted in-browser backend is active; it explains itself on hover. Benchmark numbers and every other figure come from the API (or, in sample mode, from a labelled fixture).

## Verification

`npm run verify` runs typecheck, unit tests, contrast, contract check and the production build. `npm run screens` and `npm run qa` drive the full story headlessly; screenshots land in `docs/screens/` and are reviewed before a beat counts as done.
