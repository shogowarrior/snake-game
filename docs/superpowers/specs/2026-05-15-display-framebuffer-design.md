# Display framebuffer refactor

Date: 2026-05-15

## Problem

`src/embedded/display.py` couples three concerns into one transform: drawing
coordinates, panel mounting rotation, and serpentine LED wiring. Every drawer
calls `NP[xy_to_index(x, y)] = color`, and `xy_to_index` simultaneously rotates
game-space by an `ORIENTATION` constant and applies the serpentine. The result:

- Drawers can't be reasoned about in isolation. "Is the score upright?" requires
  mentally undoing two transforms.
- The score has churned through 5+ commits (a02100f → 9861ae7 → 553515c →
  8b38edd → ...) trying to be visually correct because the rotation effect is
  invisible at the drawer's call site.
- The sim and hardware disagree about what "user view" means: the sim renders
  the post-serpentine `NP[]` buffer (panel-physical), and the user has
  confirmed hardware view = panel-physical view. So any rotation applied via
  `xy_to_index` is visible to the user; there is no second physical rotation
  to "cancel it out."

## Goal

Decouple drawing from rotation. Drawers write to a plain 16×16 framebuffer in
natural `(x, y)` coordinates. A single `flush()` step applies rotation +
serpentine when pushing the framebuffer to the LEDs. Sim and hardware render
the same post-flush buffer by construction.

## Non-goals

- Per-element rotation overrides. One global rotation applies uniformly to
  snake, food, and score.
- Runtime-mutable rotation. `ROTATION` is set once at startup; runtime mutation
  is out of scope.
- Changes to the desktop target, the engine, color helpers, or the pygame sim
  window's rendering code.
- Optimizing for visual effects beyond what exists today.

## Architecture

```text
src/embedded/
├── config.py           ── NEW. User-tunable constants only.
│       ROTATION: "0" | "90CW" | "180" | "90CCW"
│       SCORE_GRADIENT_START, SCORE_GRADIENT_END
│
├── display.py          ── refactored.
│       hardware constants (NEOPIXEL_PIN, NUM_PIXELS, NP)
│       framebuffer: _fb (flat list of 256 RGB tuples, _fb[y*16+x] = color)
│       LUT: _lut (256 ints, built once from config.ROTATION)
│       drawer API: set_pixel(x, y, color), clear(), flush()
│       drawers: draw_snake, display_char, display_message, display_scores
│       (all rewritten to use set_pixel/clear/flush; none aware of rotation
│        or wiring)
│
└── (everything else)   ── unchanged.
```

What goes away:

- `ORIENTATION` (display.py constant) → renamed `ROTATION` and moved to
  `config.py`.
- `xy_to_index`, `_physical_to_index` → removed. The rotation + serpentine math
  lives only in `_compute_lut`, called once at module load.
- Ad-hoc `NP[xy_to_index(x, y)] = color` calls in drawers → replaced with
  `set_pixel(x, y, color)`.

What stays:

- `NP` (the NeoPixel object) is still the device-facing buffer.
- Sim's `screen.py` renders `NP[]` unchanged — it now matches hardware by
  construction because both read the same post-flush bytes.
- `common/colors.py` (`gradient_color`, `hsv_to_rgb`) unchanged.
- Engine, game logic, palette generation in `game.py` unchanged.

## API

`config.py` (new):

```python
ROTATION = "0"                       # "0" | "90CW" | "180" | "90CCW"
SCORE_GRADIENT_START = (0, 120, 220)
SCORE_GRADIENT_END   = (220, 0, 140)
```

Module-level constants only. No setter functions, no init step. MicroPython-safe
(no `typing`, no `dataclass`, no `enum`).

`display.py` drawer-facing functions:

```python
def set_pixel(x, y, color):
    """Set framebuffer cell (x, y) to `color`, an (r, g, b) tuple.
    (x, y) are plain coords in 0..15 with no rotation/wiring awareness.
    Out-of-range is silently ignored."""

def clear():
    """Reset all 256 framebuffer cells to (0, 0, 0)."""

def flush():
    """Push the framebuffer to the LEDs via the precomputed LUT, then NP.write()."""
```

Existing drawer signatures unchanged:

```python
def draw_snake(engine, palette): ...
def display_char(char, offset_x=0, offset_y=0, color=WHITE, scale=1): ...
def display_message(message, offset_x=0, offset_y=0, color=WHITE, scale=1): ...
def display_scores(high_score, current_score): ...
def reset_draw_caches(): ...
```

The `color` argument on `display_char`/`display_message` may be either an
`(r, g, b)` tuple or a callable `(x, y) -> (r, g, b)`; callables are resolved
per-pixel inside the drawer and only resolved tuples are passed to `set_pixel`.
This keeps the score gradient closure working.

Each drawer ends with `flush()` (today they end with `NP.write()`).

`set_pixel` does **not** call `NP.write()`; only `flush()` does. Drawers must
not call `NP.write()` directly.

## Flush internals

The rotation + serpentine math runs once at module load and is cached in a
look-up table:

```python
def _compute_lut(rotation):
    lut = [0] * 256
    for y in range(16):
        for x in range(16):
            if rotation == "0":
                px, py = x, y
            elif rotation == "90CW":
                px, py = 15 - y, x
            elif rotation == "180":
                px, py = 15 - x, 15 - y
            else:  # "90CCW"
                px, py = y, 15 - x
            np_index = py * 16 + (px if py % 2 == 0 else 15 - px)
            lut[y * 16 + x] = np_index
    return lut

_lut = _compute_lut(config.ROTATION)

def flush():
    for i in range(256):
        NP[_lut[i]] = _fb[i]
    NP.write()
```

Inner loop is one array read, one array write, one NP write — no branching, no
arithmetic. The four rotation cases all collapse to "lookup and assign."

`_fb` is stored as a flat list `[(r, g, b)] * 256`, indexed `_fb[y*16+x]`. The
2D `[y][x]` view is a convention in docs, not a runtime structure.

## Data flow

Per frame:

```text
draw_snake(engine, palette)        OR    display_scores(high, cur)
  ├── set_pixel(...) for snake cells      ├── clear()
  ├── set_pixel(food)                     ├── set_pixel(...) for each lit
  ├── set_pixel(BLACK) for vacated cells  │   pixel of each digit, via the
  └── flush()                             │   gradient closure
                                          └── flush()
                                          ▼
                              flush() copies _fb → NP via _lut, NP.write()
                                          ▼
                            hardware lights LEDs / sim flush()
                            renders the same NP bytes
```

## Config location

User-tunable constants live in `embedded/config.py`. Hardware wiring constants
(`NEOPIXEL_PIN`, `NUM_PIXELS`) stay in `display.py` because they're truly fixed
(soldered).

Re-flashing is required to change config values. (A device-side `config.txt`
read at boot was considered and rejected for now as overkill — happy to revisit
if mounting orientation needs to change without re-flashing.)

## Migration

1. **Add the new layer in place, alongside the old one.**
   - Create `embedded/config.py` with `ROTATION` (initialized to today's
     `ORIENTATION` value), `SCORE_GRADIENT_START`, and `SCORE_GRADIENT_END`.
   - Update `display.py` to import the constants from `config`. Replace the
     local `ORIENTATION` with `from config import ROTATION as ORIENTATION`
     (temporary alias so the existing `xy_to_index` body needs zero edits in
     this commit). Remove the local `SCORE_GRADIENT_*` copies.
   - Behavior is identical after this commit; it's purely a constant move.
   - Add `_fb`, `set_pixel`, `clear`, `flush`, `_compute_lut`, `_lut` to
     `display.py`. Not yet called by drawers.
   - Keep `xy_to_index` / `_physical_to_index` for now.
2. **Migrate drawers one at a time, smallest first.**
   - `display_char` → `set_pixel`. Verify in sim and the verification harness.
   - `display_message` → `set_pixel`.
   - `display_scores` → `set_pixel` + `flush`.
   - `draw_snake` → `set_pixel` + `flush`. Verify carefully — highest-frequency
     caller.
3. **Delete the old surface.**
   - Remove `xy_to_index`, `_physical_to_index`, the temporary
     `ORIENTATION` alias, and `clear_screen` (the last optionally kept as a
     one-line alias to `clear` if anything external still calls it; nothing
     does today).
4. **Pick the right `ROTATION` value.**
   - One-file tweak. Flash, look, repeat. Decision: `ROTATION="0"` makes the
     score upright in user view (the goal that started this) and rotates
     snake/food to "natural" game-space orientation. Other values rotate
     everything uniformly. The user picks once and commits.
5. **Update the verification harness** (`/tmp/verify_score.py` from this
   session) to render the post-`flush` `NP[]` as ASCII, the same way
   `sim/screen.py` does. Used during step 2 to confirm each drawer migrates
   cleanly.

## Testing

New file `tests/test_display_framebuffer.py`, run under `uv run pytest`. Tests
import `display` with `fake_machine`/`fake_neopixel` swapped in via
`sys.modules` (the same trick `src/sim/main.py` uses), so they run under
CPython.

**Primitive tests:**

- `test_set_pixel_writes_fb` — `set_pixel(3, 5, RED)` then assert
  `_fb[5*16+3] == RED`.
- `test_set_pixel_out_of_range_silent` — `set_pixel(99, 99, RED)` doesn't raise
  and doesn't touch `_fb`.
- `test_clear_zeros_fb` — fill `_fb` with non-zero values, call `clear()`,
  assert all cells are `(0, 0, 0)`.

**LUT tests** (pin the rotation math forever):

- `test_lut_rotation_0` — `_compute_lut("0")[y*16+x]` equals serpentine of
  `(x, y)`. Verify the four corners and one odd-row cell.
- `test_lut_rotation_90CW` — `_compute_lut("90CW")[0]` equals
  `panel_serpentine(15, 0)`. Verify other corners.
- `test_lut_rotation_180` — analogous.
- `test_lut_rotation_90CCW` — analogous.

**Flush test:**

- `test_flush_pushes_fb_to_np` — for each of the four rotations, write a known
  pattern to `_fb`, build the LUT, call `flush()`, assert `NP[]` matches the
  expected post-rotation buffer.

**Drawer-level tests:**

- `test_display_scores_natural_orientation` — with `ROTATION="0"`, call
  `display_scores(0, 12)`, assert `_fb`'s lit cells match the expected
  positions for "1" at x=1..6 and "2" at x=9..14.
- `test_display_scores_gradient_endpoints` — assert `_fb` at the leftmost lit
  column matches `SCORE_GRADIENT_START` and the rightmost lit column matches
  `SCORE_GRADIENT_END`.

These pin the drawer's framebuffer output. Rotation is tested separately, so
drawer tests are rotation-independent.

**End-to-end visual verification:**

- Run the verification harness for each of the four `ROTATION` values, render
  the post-`flush` `NP[]` as ASCII, pick the one that matches hardware.
- `uv run python src/sim/main.py` — visually confirm a play-through looks
  correct. Sim reads post-`flush` `NP[]`, so this matches hardware by
  construction.
- Flash to the ESP32 (`flash-snake` skill) and reset.

**Not tested:**

- Color math (`gradient_color`, `hsv_to_rgb`) — unchanged module, has its own
  coverage if anyone wants to add it later.
- Pygame sim window rendering — manual visual.
- Hardware wiring — out of scope of any automated test.

## Trade-offs and consequences

- **One global rotation.** Score and snake/food rotate together. The user
  accepts that picking `ROTATION` for the score's sake also re-orients the
  game. Per-element rotation is explicitly out of scope.
- **Re-flash to change rotation.** Acceptable given how rarely mounting
  changes. Device-side config file is a future enhancement.
- **Memory.** `_fb` (256 RGB tuples) + `_lut` (256 ints) add ~12KB on
  MicroPython. ESP32 has ~200KB RAM; budget is fine.
- **Two-pass per frame.** Drawers fill `_fb`, `flush()` copies to `NP`. Inner
  loop is array-index-array-write; on a 16×16 panel at the current frame rate,
  cost is negligible.
- **Drawer correctness becomes locally verifiable.** Tests can assert
  framebuffer state without touching the LED strip or any rotation logic. The
  "score is rotated wrong" class of bug becomes structurally impossible at the
  drawer level.

## Open issues

None blocking. The `ROTATION` final value is a one-line decision made during
step 4 of migration (flash, look at hardware, pick the value that looks right,
commit).
