# Quorum frontend design plan

Direction: a forensic ledger drawn on drafting paper. Quiet, light, precise.
The belief graph is evidence; the UI never decorates it.

## Palette (tokens as CSS variables)

| Role | Token | Hex | Text use |
|---|---|---|---|
| Canvas | `--vellum` | #E6EBEF | background only |
| Panel | `--paper` | #F7F9FA | background only |
| Ink | `--ink` | #101C2B | body, lines |
| Secondary | `--graphite` | #566577 | secondary text |
| Healthy | `--verdigris` | #17806D | fills, rings, 4.5:1 on paper for text |
| Quarantined | `--stamp` | #C62F1B | rings, dashed edges |
| Out of date | `--ochre` | #B5760F | rings only; text uses #8A5A0B |
| Superseded | `--pencil` | #8D9AA8 | ghosts, never body text |
| Review/human | `--ultramarine` | #3B3FD1 | review actions, "viewing the past" frame |

Hairline: ink at 14%. No gradients, glow or glass. Every text/background pair
is checked with a script (`npm run contrast`) before it ships; pencil and
ochre (#B5760F) are never used for text.

## Type

- Schibsted Grotesk 400/500/700 for UI, headings, big numerals (tabular figures).
- JetBrains Mono only for ids, Cypher and drawer timestamps.
- Scale 12, 13, 14, 16, 20, 28, 44. Sentence case. Lines under 80 characters.
- Both families bundled via `@fontsource`; no network at runtime.

## Layout

Header (tenant, mode, epoch, invariants, connection) over three columns
(History + scenario controls | graph canvas | containment report + inspector)
over a timeline bar. Desktop-first: 1440 target, 1280 comfortable, 1024 usable.

## Principles

1. The canvas is the signature: faint drafting grid, four labelled column rails
   (Sources, Facts, Conclusions, Actions) that encode causal order.
2. Boldness in two places only: the quarantine wave and the prompt diff.
3. Shape and glyph carry meaning, never color alone.
4. Radius varies by role (2 px panels, pill chips); not one card kit.
5. One orchestrated motion per major event; `prefers-reduced-motion` turns the
   wave into an instant state change with a short highlight.
6. Every number on screen comes from the API. Mock mode carries a permanent banner.

## Review against generic defaults

| Generic pattern | Risk in this plan | Change made |
|---|---|---|
| Dark mode with one neon accent | none, plan is light | kept light |
| Cream paper with a serif | vellum/paper could drift warm | kept cool blue-grey; sans only |
| Identical rounded cards | panels could all look alike | panels flat with hairlines; only chips are pills |
| All-caps tracked eyebrows | easy habit for section labels | banned; sentence-case labels |
| Mono for every small label | tempting for ids and counts | mono restricted to ids, Cypher, drawer timestamps |
| Arrow on every button | tempting for CTAs | buttons name the result, no arrows |
| Single blue-ish accent | ultramarine plus pale blue-grey can read "SaaS blue" | ultramarine reserved for human/review and the past-viewing frame, so it appears rarely and always means "a person decides" |

## Voice

Statuses: Healthy, Quarantined, Replaced by a newer fact, Out of date.
Actions: Staged, Held for review, Running, Ran, Cancelled, Rolling back,
Rolled back, Rollback failed, Needs a person.
Buttons: "Inject poisoned webhook", "Audit memory", "Restore", "Replace policy".
All strings live in `frontend/src/copy/`.

## Verification

`npm run verify` (typecheck, lint, unit tests, contract check, build), then
headless screenshots of each demo beat saved to `docs/screens/`, each critiqued
before the beat is called done.
