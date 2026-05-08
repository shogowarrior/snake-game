---
name: embedded-display-tweak
description: Use when changing src/embedded/display.py — score size/position, snake or food
  colors, panel rotation, brightness, or anything that affects how the 16x16 NeoPixel
  matrix renders. Trigger even when the user just says "make the score bigger", "rotate
  the display", "change the colors", or "the score is upside down" without naming display.py.
---

# Embedded display tweak

## What this skill is for

When you're changing how the 16x16 NeoPixel matrix renders, follow this workflow
and these invariants. Display changes are cross-cutting: panel rotation affects
every renderer, the score has a fragile width budget, and the draw caches will
ghost the previous game if you don't reset them. The lessons from a dozen recent
commits live here so you don't re-derive them each time.

## The edit loop

```text
edit src/embedded/display.py
  → uv run python src/sim/main.py     (host preview via curses)
  → user confirms render
  → flash-snake                        (push to ESP32, see flash-snake skill)
  → visual check on hardware
```

Rule: do not flash a `display.py` change without a sim preview first. If the
user explicitly says "just flash it", that is fine. Do not skip the sim on your
own initiative — the sim catches rotation, indexing, and layout bugs without
burning a flash cycle.

## Three coordinate spaces

`display.py` mixes three coordinate spaces. The math lives in the file's own
docstrings (`xy_to_index`, around `display.py:89`); this skill just names the
territory so you know which transform applies where.

| Space | Where it lives | Translates to next via |
| --- | --- | --- |
| Game `(col, row)` | `engine.snake`, `engine.food` (each value 0..15) | `xy_to_index` |
| Panel `(px, py)` | implicit inside `xy_to_index` | `ORIENTATION` rotation |
| Strip index `0..255` | `NP[i]` | serpentine wiring (odd rows reversed) |

## Layout invariants worth knowing

Five recurring gotchas. Each is tied to the commit that introduced or fixed it
so future-you can see the provenance.

- **16-wide score budget.** `width = len(s) * 4 * scale - scale`. A two-digit
  score at scale=2 is 14 px — the maximum that fits. scale=3 with `"12"`
  overflows (21 > 16). See `display_scores`.
- **Auto-center vs fixed offset.** `display_scores` auto-centers (game-over
  view, commit 243183b). Playing-view score uses fixed offsets and does not
  re-center as digits grow.
- **Reset caches between games.** `reset_draw_caches()` must run between games
  or you get ghosting from the previous snake (commit 553515c).
- **Glyph rotation gotcha.** Glyph patterns are 5 rows × 3 cols. With
  `ORIENTATION` rotation, rows visually become columns — score may need its own
  rotation handling separate from snake/food (commits a02100f → 9861ae7 →
  553515c walked this back and forth).
- **Snake gradient direction.** Head bright → tail dim, via `gradient_color` in
  `common/colors.py` (commit 3a19d83).

## Tweak checklist

One row per common request. "sim" in the Verify column means run
`uv run python src/sim/main.py` and visually confirm the render before flashing.

| Request | Edit | Verify |
| --- | --- | --- |
| Change snake/food colors | palette generator in `src/embedded/game.py` | sim |
| Resize score | `display_scores` `scale=` (watch the width budget) | sim |
| Rotate panel | `ORIENTATION` constant (`display.py:83`) | sim |
| Adjust speed | palette `speed` in `src/embedded/game.py` | sim |
| Brightness | scale RGB tuples in `display.py` color constants | sim |

## What this skill does NOT do

- Does not flash. Use the `flash-snake` skill for that.
- Does not know what the hardware actually shows — only what the host sim
  renders. The hardware visual check is still the user's call.
- Does not regenerate ML models or change game logic.
- Does not edit `common/` types or the game engine. Display-only.

## Worked example: "the score is upside-down at 90CW"

This case ate three commits (a02100f → 9861ae7 → 553515c) before it stuck.

**Symptom.** With `ORIENTATION="90CW"`, the snake and food rotate correctly but
the score reads sideways.

**Cause.** Glyph patterns in `display.py` are 5 rows × 3 cols, drawn row by row.
`xy_to_index` rotates game-space by `ORIENTATION`. At 90CW, the glyph rows
visually become columns on the panel — so the digits look rotated even though
the math "rotated" them.

**Fix space (pick one, sim-verify, then flash):**

- Pre-rotate glyph patterns inside `display_char` to compensate for
  `ORIENTATION`.
- Give the score its own orientation independent of the game (skip
  `xy_to_index` for text and use a text-specific mapper).
- Lay out the score in a panel-region that doesn't rotate (a fixed corner).

The right answer depends on what reads cleanly to the player. Sim-verify each
candidate before flashing.
