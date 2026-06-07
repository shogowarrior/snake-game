# Embedded display: encapsulate state in a `Display` class

**Status:** Draft — 2026-05-17

## Why

`src/embedded/display.py` currently keeps mutable state (`_fb`, `_lut`, `NP`,
the render-loop caches `_prev_snake_cells` / `_gradient_colors` /
`_previous_snake_length`) at module scope. The render functions mutate that
state via the `global` keyword. This works but:

- Every render-loop function has to declare `global ...` to mutate caches.
- `display.py` mixes three layers: hardware singleton (`NP`), pure helpers
  (`_compute_lut`, `_heartbeat_factor`), draw primitives (`set_pixel`,
  `flush`, `display_char`), and stateful render functions
  (`draw_snake`, `reset_draw_caches`).
- The recent heartbeat feature would have added a fourth `global` declaration
  to the same set of functions. That was the trigger.

Goal: remove module-level mutable state and the `global` keyword from
`src/embedded/display.py` while keeping the public surface (rotation,
brightness, draw API) unchanged.

## What changes

### New module: `src/embedded/glyphs.py`

One flat dict, `GLYPHS`, merging the existing `digits`, `characters`, and
`special_chars` tables. Keys are uppercase characters; values are 5-row x
3-col bitmap lists. `__all__ = ["GLYPHS"]`.

Glyphs are pure data and don't belong in the renderer module.

### Refactored module: `src/embedded/display.py`

Module level keeps only:

- Color constants: `WHITE`, `BLACK`, `GREEN`, `RED`, `BLUE`, `NUM_PIXELS`.
- Pure helpers: `_compute_lut(rotation)`, `_heartbeat_factor(frame, speed)`.
- Class `Display`.
- `__all__` lists `Display` and the exported constants.

Class `Display` owns:

- `self.np` — the only `neopixel.NeoPixel` handle in the process.
- `self._fb` — the 256-cell framebuffer (list of (r,g,b) tuples).
- `self._lut` — rotation+serpentine lookup, computed from `config.ROTATION`
  at construction.
- `self._prev_snake_cells`, `self._gradient_colors`,
  `self._previous_snake_length` — render-loop caches.

Methods (all instance methods, no `global`):

- `set_pixel(x, y, color)`, `clear()`, `flush()`
- `display_char(char, offset_x, offset_y, color, scale)`,
  `display_message(message, offset_x, offset_y, color, scale)` —
  look glyphs up via `GLYPHS` from `glyphs.py`.
- `display_scores(high_score, current_score)`
- `draw_snake(engine, palette)` — pulses food via `_heartbeat_factor` when
  `config.FOOD_HEARTBEAT` is `True`.
- `reset_draw_caches()`

Behavior is unchanged from the current module-level functions. Rotation,
brightness, heartbeat envelope, gradient direction, score layout all match.

### Wiring: `src/embedded/game.py` and `src/embedded/main.py`

`SnakeGame.__init__` takes `display` as its first positional argument and
stores `self.display = display`. All previous module-level calls
(`draw_snake`, `display_scores`, `reset_draw_caches`) become method calls on
`self.display`.

`main.py`'s `run_game()` constructs `Display()` once and passes the same
instance to every `SnakeGame` it spawns. This keeps the NeoPixel handle a
process-singleton without making it a *module* singleton.

### Tests: `tests/test_display_framebuffer.py`

A pytest fixture builds a fresh `Display()` per test. Assertions translate
mechanically:

| Before | After |
| --- | --- |
| `display.set_pixel(...)` | `d.set_pixel(...)` |
| `display._fb[i]` | `d._fb[i]` |
| `display.NP[i]` | `d.np[i]` |
| `display._lut[i]` | `d._lut[i]` |
| `display.flush()`, `display.clear()`, … | `d.flush()`, `d.clear()`, … |

`display._compute_lut(...)` stays as a module function (tests already use
it that way). `display.FOOD_HEARTBEAT` stays a module attribute (imported
from config); tests that monkeypatch it keep working unchanged.

### Docs: `CLAUDE.md`

The "Embedded display: framebuffer + caches" section is rewritten to
describe the `Display` class, the glyphs split, and the
`main.py` → `SnakeGame(display=...)` wiring.

## Out of scope

- Rotation, color, or heartbeat behavior — unchanged.
- Type hints, dataclasses, or `enum` usage — `src/embedded/` is
  MicroPython-targeted and must stay free of those (CLAUDE.md rule).
- Desktop / sim renderers — no API touches there. The sim continues to
  import `embedded/main.py`, which is the only place that constructs
  `Display()`.
- Resume-from-checkpoint or anything in `src/desktop/`.

## Verification

1. `uv run python src/sim/main.py` — sim renders without traceback; the
   food cell visibly pulses (heartbeat already verified working).
2. `uv run pytest` — full test suite green.
3. `uv run ruff check src/ tests/` — clean.
4. `uv run mypy` — clean (scoped to `src/common` + `src/desktop`, so the
   refactor isn't directly checked, but won't break either).
5. Spot-check on hardware via the `flash-snake` skill — owner's call,
   outside the test loop.

## Risks

- **NeoPixel singleton drift.** If callers ever construct two `Display()`
  instances, both will allocate a `neopixel.NeoPixel` buffer for the same
  GPIO. `main.py` is the only constructor; this is enforced by convention,
  not by the type system.
- **Test coupling.** Tests reach into `_fb` and `np` directly. That's
  intentional for framebuffer assertions; the refactor preserves the
  leading-underscore convention so callers know it's internal.
- **Glyph dict rename.** The merged `GLYPHS` dict replaces three smaller
  dicts. No public API depended on `digits`/`characters`/`special_chars`
  being separate — only `display_char` looked them up. Tests don't touch
  these names directly.
