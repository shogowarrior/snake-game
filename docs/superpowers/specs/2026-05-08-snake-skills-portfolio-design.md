# Snake Skills Portfolio Design

**Date:** 2026-05-08
**Status:** Approved (user waived review gate)

## Goal

Codify the most-repeated workflows in this repo as project-local skills under
`.claude/skills/`, in a way that captures both user-invokable commands and
conventions that should guide Claude's behavior. Ship one tight skill in this
cycle and queue two more for follow-on cycles.

## Portfolio Overview

| Candidate | Status | Reason |
| --- | --- | --- |
| `flash-snake` | Already exists | Working — leave alone. |
| `embedded-display-tweak` | **Active — build now** | Highest-friction area in recent commits (10+ around score/rotation/colors). Codifies workflow + cross-refs without duplicating `display.py` comments. |
| `run-snake-sim` | **Not a skill — goes to CLAUDE.md** | One-line invocation (`uv run python src/sim/main.py`) with no flag matrix or judgment calls. Fails skill-creator's "don't create for mechanical constraints" test. |
| `new-policy` | Deferred — sketch only | No evidence of policy #3 on the horizon. Brainstorm again when adding one. |
| `train-policy` | Deferred — sketch only | `learned_policy.py` is still a stub; training output has nowhere to land yet. Brainstorm again when fleshing it out. |

## Active Skill: `embedded-display-tweak`

### File layout

Single file: `.claude/skills/embedded-display-tweak/SKILL.md`. No supporting
scripts, no `references/`, no `assets/`. The math lives in `display.py`'s
existing comments and the skill links there rather than duplicating.

Target length: ~150 lines / ~800 words. Same order of magnitude as
`flash-snake` (~80 lines).

### Frontmatter

```yaml
---
name: embedded-display-tweak
description: Use when changing src/embedded/display.py — score size/position, snake or food
  colors, panel rotation, brightness, or anything that affects how the 16x16 NeoPixel
  matrix renders. Trigger even when the user just says "make the score bigger", "rotate
  the display", "change the colors", or "the score is upside down" without naming display.py.
---
```

### Body sections

The skill body has 7 sections in this order.

#### 1. What this skill is for

One paragraph (~50 words). Frame: "When you're changing how the matrix looks,
follow this workflow and these invariants." Mention the cross-cutting nature of
display changes (panel rotation affects every renderer, score budget is fragile,
ghosting comes back if caches aren't reset).

#### 2. The edit loop

```text
edit display.py
  → uv run python src/sim/main.py     (host preview via curses)
  → user confirms render
  → flash-snake                        (push to ESP32)
  → visual check on hardware
```

Rule: Claude does not flash a `display.py` change without a sim preview first.
If the user explicitly skips the sim ("just flash it"), that is fine — but
Claude does not skip on its own initiative.

#### 3. Three coordinate spaces

Short table that names the territory but does not redo the math:

| Space | Where it lives | Translates to next via |
| --- | --- | --- |
| Game `(col, row)` | `engine.snake`, `engine.food` (0..15, 0..15) | `xy_to_index` |
| Panel `(px, py)` | implicit inside `xy_to_index` | `ORIENTATION` rotation |
| Strip index `0..255` | `NP[i]` | serpentine wiring (odd rows reversed) |

Pointer: math is in `src/embedded/display.py:89-101`.

#### 4. Layout invariants

Five bullets, each tied to a recent commit so future-Claude can see the
provenance:

- **16-wide score budget:** `width = len(s) * 4 * scale - scale`. Two-digit
  score at scale=2 = 14 px (max). scale=3 with "12" overflows (21 > 16).
  See `display_scores`.
- **Auto-center vs fixed offset:** `display_scores` auto-centers (game-over
  view, commit 243183b). Playing-view score uses fixed offsets and does not
  re-center as digits grow.
- **Reset caches between games:** `reset_draw_caches()` must run between games
  or you get ghosting from the previous snake (commit 553515c).
- **Glyph rotation gotcha:** glyph patterns are 5 rows × 3 cols. With
  `ORIENTATION` rotation, rows visually become columns — score may need its own
  rotation handling separate from snake/food (commits a02100f → 9861ae7 →
  553515c walked this back and forth).
- **Snake gradient direction:** head bright → tail dim, via `gradient_color` in
  `common/colors.py` (commit 3a19d83).

#### 5. Tweak checklist

One row per common request:

| Request | Edit | Verify |
| --- | --- | --- |
| Change snake/food colors | palette generator in `src/embedded/game.py` | sim |
| Resize score | `display_scores` `scale=` (watch width budget) | sim |
| Rotate panel | `ORIENTATION` constant (`display.py:83`) | sim |
| Adjust speed | palette `speed` in `src/embedded/game.py` | sim |
| Brightness | scale RGB tuples in `display.py` color constants | sim |

#### 6. What this skill does NOT do

Mirror `flash-snake`'s style:

- Does not flash. (`flash-snake` does that.)
- Does not know what the hardware actually shows — only what the host sim
  renders. The hardware visual check is still on the user.
- Does not regenerate ML models or change game logic.
- Does not edit `common/` types or the engine. Display-only.

#### 7. Worked example

~15 lines. Pulls the score-rotation case from commits a02100f → 9861ae7 →
553515c. Walks the symptom ("score reads sideways at ORIENTATION=90CW"), names
the cause (5×3 glyph rows rotate to columns at 90CW), and shows the fix space
(rotate glyph patterns at draw-time, or text-specific orientation), without
prescribing one — the user picks.

### What this skill explicitly does NOT include

- The `xy_to_index` math (already in `display.py:89-101` docstring).
- Why serpentine wiring exists (already in `display.py:86-88` comment).
- The `gradient_color` algorithm (in `common/colors.py`).
- An exhaustive gotcha catalogue — only the top 5 that recurred in commits.

Principle: skill = workflow + map of territory. Code comments = the math. No
duplication.

## CLAUDE.md Hand-off

The spec does not edit `CLAUDE.md` directly — that file is being updated in a
parallel session. Below is the verbatim text the other session should drop in.
If `CLAUDE.md` does not yet exist, the other session creates it; otherwise
these go in as new sections.

```markdown
## Running the host sim

Verify embedded display changes on the host before flashing:

    uv run python src/sim/main.py

This boots `src/embedded/main.py` with `fake_machine` and `fake_neopixel`
shimmed in, rendering the 16x16 panel via curses.

## Display change discipline

When changing `src/embedded/display.py`, sim-verify before flashing. The host
sim catches rotation, indexing, and layout bugs without burning a flash cycle.
The `embedded-display-tweak` skill enforces this loop automatically.
```

Cross-reference: the skill mentions running the sim; CLAUDE.md mentions the
skill. Each side is discoverable from the other.

## Deferred Skills

### `new-policy` (sketch)

**Trigger phrases:** "add a Q-learning policy", "scaffold a new policy",
"let me try a different AI".

**What it would do:** generate a Policy subclass under
`src/embedded/<name>_policy.py` following the contract in
`src/common/policy.py`, mirroring `greedy_policy.py` / `learned_policy.py`. Add
the wiring point in `src/embedded/main.py` (`POLICY` constant) and in
`src/desktop/main.py` if the policy runs on desktop.

**Why deferred:** no evidence of policy #3. `greedy` covers the current need;
`learned` is a stub. Brainstorm again when adding policy #3.

**Constraints to remember:**

- Embedded uses flat imports (`from greedy_policy import GreedyPolicy`).
- Policy must be ESP32-runnable (no heavy deps).
- `POLICY` constant in `embedded/main.py` is the single switch.

### `train-policy` (sketch)

**Trigger phrases:** "train a new model", "retrain the snake AI", "improve the
learned policy".

**What it would do:** orchestrate training end-to-end — run the desktop
trainer, log to `scores.csv`, save weights to `model/`, plot results via
`src/desktop/plot.py`, and convert the model into the form
`embedded/learned_policy.py` consumes.

**Why deferred:** `learned_policy.py` is a stub (commit 3eaf2d8). Until it is
actually wired up, training output has nowhere to land. The conversion step
from desktop weights → embedded-friendly format is unsolved engineering, not a
skill question. Brainstorm when fleshing out `learned_policy.py`.

**Constraints to remember:**

- Training lives in `src/desktop/`; embedded only consumes the result.
- `scores.csv` is the existing score log; plotting via `desktop/plot.py`.
- Model format conversion is the open question.

## Acceptance Criteria

This spec is satisfied when:

- [ ] `.claude/skills/embedded-display-tweak/SKILL.md` exists with frontmatter
  and the seven body sections described above.
- [ ] The skill is ~150 lines and ~800 words (same order of magnitude as
  `flash-snake`).
- [ ] The skill links to `display.py` line ranges instead of duplicating math.
- [ ] The CLAUDE.md hand-off text has been delivered to the other session
  (file edit done by them, not by this work).
- [ ] The deferred-skills sketches in this spec are preserved as future-work
  context.
- [ ] No new files outside `.claude/skills/embedded-display-tweak/` and
  `docs/superpowers/specs/` are created by this work.

## Out of Scope

- Editing `CLAUDE.md` (other session owns it).
- Building `run-snake-sim` as a skill.
- Detailed design of `new-policy` or `train-policy`.
- Adding sim snapshot mode (programmatic render verification). If the skill
  proves valuable and the user-in-loop verification feels heavy, this gets its
  own spec.
- Any change to `flash-snake`.
- Any change to `display.py`, `game.py`, or any source code.

## Follow-ons

- When adding policy #3: brainstorm `new-policy`.
- When fleshing out `learned_policy.py`: brainstorm `train-policy`.
- After a few real uses of `embedded-display-tweak`: assess whether sim
  snapshot mode is worth the work.
