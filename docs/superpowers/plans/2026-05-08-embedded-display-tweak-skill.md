# `embedded-display-tweak` Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Author the `embedded-display-tweak` skill defined in `docs/superpowers/specs/2026-05-08-snake-skills-portfolio-design.md` as a single markdown file under `.claude/skills/embedded-display-tweak/`.

**Architecture:** One file (`SKILL.md`) with YAML frontmatter and seven body sections. No supporting scripts, no `references/`, no `assets/`. The skill links to existing `display.py` line ranges instead of duplicating math.

**Tech Stack:** Plain markdown + YAML. No build step. Validated by IDE markdown linter (already running) and by manually checking that referenced `display.py` line numbers resolve to the symbols named in the skill.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `.claude/skills/embedded-display-tweak/SKILL.md` | The skill itself: frontmatter + body. Single ~150-line file. |

No other files created or modified by this plan. CLAUDE.md edits are owned by a parallel session and explicitly out of scope here.

---

## Task 1: Scaffold the skill file with frontmatter

**Files:**

- Create: `.claude/skills/embedded-display-tweak/SKILL.md`

- [ ] **Step 1: Create the directory and write the frontmatter + title**

```markdown
---
name: embedded-display-tweak
description: Use when changing src/embedded/display.py — score size/position, snake or food
  colors, panel rotation, brightness, or anything that affects how the 16x16 NeoPixel
  matrix renders. Trigger even when the user just says "make the score bigger", "rotate
  the display", "change the colors", or "the score is upside down" without naming display.py.
---

# Embedded display tweak
```

- [ ] **Step 2: Verify the frontmatter parses**

Run: `python -c "import yaml; doc = open('.claude/skills/embedded-display-tweak/SKILL.md').read(); body = doc.split('---', 2)[1]; print(yaml.safe_load(body))"`

Expected output: a Python dict with keys `name` and `description`. If yaml is not installed: `uv run python -c "..."`.

---

## Task 2: Section 1 — What this skill is for

**Files:**

- Modify: `.claude/skills/embedded-display-tweak/SKILL.md`

- [ ] **Step 1: Append the introductory paragraph**

Append after the title:

```markdown
## What this skill is for

When you're changing how the 16x16 NeoPixel matrix renders, follow this workflow
and these invariants. Display changes are cross-cutting: panel rotation affects
every renderer, the score has a fragile width budget, and the draw caches will
ghost the previous game if you don't reset them. The lessons from a dozen recent
commits live here so you don't re-derive them each time.
```

---

## Task 3: Section 2 — The edit loop

**Files:**

- Modify: `.claude/skills/embedded-display-tweak/SKILL.md`

- [ ] **Step 1: Append the edit loop section**

```markdown
## The edit loop

```text
edit src/embedded/display.py
  → uv run python src/sim/main.py     (host preview via curses)
  → user confirms render
  → flash-snake                        (push to ESP32, see flash-snake skill)
  → visual check on hardware
```

Rule: do not flash a `display.py` change without a sim preview first. If the user
explicitly says "just flash it", that is fine. Do not skip the sim on your own
initiative — the sim catches rotation, indexing, and layout bugs without burning
a flash cycle.
```

---

## Task 4: Section 3 — Three coordinate spaces

**Files:**

- Modify: `.claude/skills/embedded-display-tweak/SKILL.md`

- [ ] **Step 1: Verify the line range for `xy_to_index`**

Run: `sed -n '85,102p' src/embedded/display.py`

Expected: shows `xy_to_index` definition. Confirm the function body covers lines 89-101 (or note the actual range and use that in the skill).

- [ ] **Step 2: Append the section**

Use the verified line range:

```markdown
## Three coordinate spaces

`display.py` mixes three coordinate spaces. The math is in
`src/embedded/display.py:89-101` (or whatever the verified range is); this skill
just names the territory so you know which transform applies where.

| Space | Where it lives | Translates to next via |
| --- | --- | --- |
| Game `(col, row)` | `engine.snake`, `engine.food` (each value 0..15) | `xy_to_index` |
| Panel `(px, py)` | implicit inside `xy_to_index` | `ORIENTATION` rotation |
| Strip index `0..255` | `NP[i]` | serpentine wiring (odd rows reversed) |
```

---

## Task 5: Section 4 — Layout invariants

**Files:**

- Modify: `.claude/skills/embedded-display-tweak/SKILL.md`

- [ ] **Step 1: Verify each commit hash referenced**

Run: `git log --oneline | grep -E "243183b|553515c|a02100f|9861ae7|3a19d83" | head -10`

Expected: each commit appears. If a hash is wrong, look up the right one with `git log --oneline | grep <keyword>` (e.g. "rotate score", "between games", "head brighter").

- [ ] **Step 2: Append the section**

```markdown
## Layout invariants worth knowing

Five recurring gotchas. Each is tied to the commit that introduced or fixed it,
so future-you can see the provenance.

- **16-wide score budget:** `width = len(s) * 4 * scale - scale`. Two-digit
  score at scale=2 is 14 px — the maximum that fits. scale=3 with "12"
  overflows (21 > 16). See `display_scores`.
- **Auto-center vs fixed offset:** `display_scores` auto-centers (game-over
  view, commit 243183b). Playing-view score uses fixed offsets and does not
  re-center as digits grow.
- **Reset caches between games:** `reset_draw_caches()` must run between games
  or you get ghosting from the previous snake (commit 553515c).
- **Glyph rotation gotcha:** glyph patterns are 5 rows × 3 cols. With
  `ORIENTATION` rotation, rows visually become columns — the score may need
  its own rotation handling separate from snake/food (commits a02100f →
  9861ae7 → 553515c walked this back and forth).
- **Snake gradient direction:** head bright → tail dim, via `gradient_color`
  in `common/colors.py` (commit 3a19d83).
```

---

## Task 6: Section 5 — Tweak checklist

**Files:**

- Modify: `.claude/skills/embedded-display-tweak/SKILL.md`

- [ ] **Step 1: Verify referenced symbols exist**

Run: `grep -nE "ORIENTATION|display_scores|palette|gradient_color" src/embedded/display.py src/embedded/game.py src/common/colors.py 2>&1 | head -20`

Expected: each symbol appears at least once in the named files. Note the line of `ORIENTATION` in display.py — used in the table below.

- [ ] **Step 2: Append the section**

Use the verified `ORIENTATION` line number:

```markdown
## Tweak checklist

One row per common request. "sim" in the Verify column means run
`uv run python src/sim/main.py` and visually confirm.

| Request | Edit | Verify |
| --- | --- | --- |
| Change snake/food colors | palette generator in `src/embedded/game.py` | sim |
| Resize score | `display_scores` `scale=` (watch width budget) | sim |
| Rotate panel | `ORIENTATION` constant (`display.py:83`) | sim |
| Adjust speed | palette `speed` in `src/embedded/game.py` | sim |
| Brightness | scale RGB tuples in `display.py` color constants | sim |
```

---

## Task 7: Section 6 — What this skill does NOT do

**Files:**

- Modify: `.claude/skills/embedded-display-tweak/SKILL.md`

- [ ] **Step 1: Append the section**

```markdown
## What this skill does NOT do

Mirrors `flash-snake`'s style: name the boundaries.

- Does not flash. Use the `flash-snake` skill for that.
- Does not know what the hardware actually shows — only what the host sim
  renders. The hardware visual check is still the user's call.
- Does not regenerate ML models or change game logic.
- Does not edit `common/` types or the game engine. Display-only.
```

---

## Task 8: Section 7 — Worked example

**Files:**

- Modify: `.claude/skills/embedded-display-tweak/SKILL.md`

- [ ] **Step 1: Append the worked example**

```markdown
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
```

---

## Task 9: Lint and verify

**Files:**

- Verify: `.claude/skills/embedded-display-tweak/SKILL.md`

- [ ] **Step 1: Word count check**

Run: `wc -w .claude/skills/embedded-display-tweak/SKILL.md`

Expected: 700-900 words. If outside that range, trim or expand. (`flash-snake` is the reference point — same order of magnitude.)

- [ ] **Step 2: Confirm cross-references resolve**

Run: `grep -E "display\.py:[0-9]+" .claude/skills/embedded-display-tweak/SKILL.md`

For each `display.py:N` reference, verify the symbol named at that line still exists:

```bash
sed -n '83p;89,101p' src/embedded/display.py
```

If a line moved, update the reference.

- [ ] **Step 3: Manual read-through**

Open the file. Confirm:

- Frontmatter is valid YAML.
- Each section heading uses `##` (one level below the `#` title).
- The fenced `text` code block in section 2 closes properly.
- No "TODO", "TBD", or placeholder text remains.

---

## Task 10: Commit

**Files:**

- Stage: `.claude/skills/embedded-display-tweak/SKILL.md`

- [ ] **Step 1: Stage only the new skill file**

```bash
git add .claude/skills/embedded-display-tweak/SKILL.md
```

Do not stage `CLAUDE.md`, `src/sim/`, `src/embedded/display.py`, or any other modified file — those belong to other workstreams.

- [ ] **Step 2: Commit**

```bash
git commit -m "feat(skills): add embedded-display-tweak skill

Captures the workflow (sim-verify before flash) and the 5 layout invariants
that recurred in recent display.py commits. Links to display.py line ranges
instead of duplicating math. See spec at
docs/superpowers/specs/2026-05-08-snake-skills-portfolio-design.md."
```

No `Co-Authored-By` trailer (per global user preferences).

- [ ] **Step 3: Verify the commit**

Run: `git log --oneline -1 && git diff HEAD~1 --stat`

Expected: one new file `.claude/skills/embedded-display-tweak/SKILL.md`, ~150 lines added.

---

## Acceptance

- [ ] `.claude/skills/embedded-display-tweak/SKILL.md` exists.
- [ ] Frontmatter parses as YAML with `name` and `description` keys.
- [ ] All seven body sections present in order.
- [ ] Word count in 700-900 range.
- [ ] All `display.py:N` line references point at the symbols named.
- [ ] Markdown linter shows no warnings on the file.
- [ ] One commit on `main` containing only the new skill file.
