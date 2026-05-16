# Display framebuffer refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple drawing from rotation in `src/embedded/display.py` by introducing a 16×16 framebuffer that drawers fill in natural `(x, y)` coords; a single `flush()` step applies rotation + serpentine via a precomputed LUT to push the framebuffer to the LEDs. Centralize user-tunable constants (rotation, score gradient) in a new `src/embedded/config.py`.

**Architecture:** Drawers (`draw_snake`, `display_char`, `display_message`, `display_scores`) write colors into a module-level flat list `_fb[y*16+x]`. They know nothing about rotation or wiring. `flush()` reads a precomputed `_lut` (built once at module load from `config.ROTATION`) and copies `_fb` to `NP[]` in the right order, then `NP.write()`. Sim and hardware render the same post-`flush` buffer by construction.

**Tech Stack:** Python 3.11 (CPython on desktop + sim, MicroPython on ESP32), pytest, mpremote, neopixel/machine (fakes in sim). The embedded modules must avoid `typing`, `dataclasses`, `enum`, and other CPython-only stdlib.

**Spec:** [docs/superpowers/specs/2026-05-15-display-framebuffer-design.md](../specs/2026-05-15-display-framebuffer-design.md)

---

## Task 1: Test bootstrap (`tests/conftest.py`)

The embedded modules import `machine` and `neopixel` at load time. We pre-load the sim's fakes into `sys.modules`, add `src/` and `src/embedded` to `sys.path`, and stub out the sim's pygame flush so tests can call `NP.write()` headlessly.

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the conftest**

```python
"""Pytest bootstrap for embedded-target tests.

Pre-loads the sim's `machine`/`neopixel` fakes so importing `display` works
under CPython. Stubs `sim.screen.flush` so `NP.write()` never opens a pygame
window during tests.
"""
import sys
from pathlib import Path

TESTS = Path(__file__).parent.resolve()
ROOT = TESTS.parent
SRC = ROOT / "src"

# Path setup: `from common.colors import ...` and flat `import display` both work.
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC / "embedded"))

# Pre-load fakes BEFORE any test triggers `import display`.
from sim import fake_machine, fake_neopixel  # noqa: E402

sys.modules["machine"] = fake_machine
sys.modules["neopixel"] = fake_neopixel

# Headless: don't open a pygame window during tests.
from sim import screen  # noqa: E402

screen.flush = lambda buf: None
```

- [ ] **Step 2: Verify pytest collects (no tests yet, so it's empty but should not error)**

Run: `uv run pytest tests/ -q`
Expected: `no tests ran` with exit code 5 (no tests collected), no import errors.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test(embedded): conftest bootstraps fakes + sys.path for display tests"
```

---

## Task 2: Create `config.py` and re-route `display.py` imports

Move user-tunable constants out of `display.py` into a new module. Behavior unchanged — `ORIENTATION` becomes a temporary alias to `config.ROTATION` so the existing `xy_to_index` body needs zero edits.

**Files:**
- Create: `src/embedded/config.py`
- Modify: `src/embedded/display.py:1-16, 79-83`

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
def test_config_exposes_rotation_and_gradient_constants():
    import config

    assert config.ROTATION in ("0", "90CW", "180", "90CCW")
    # Each gradient endpoint is a 3-tuple of ints in 0..255.
    for endpoint in (config.SCORE_GRADIENT_START, config.SCORE_GRADIENT_END):
        assert isinstance(endpoint, tuple)
        assert len(endpoint) == 3
        assert all(isinstance(c, int) and 0 <= c <= 255 for c in endpoint)


def test_display_uses_rotation_from_config():
    import config
    import display

    # display.py keeps a temporary `ORIENTATION` alias pointing at config.ROTATION.
    assert display.ORIENTATION == config.ROTATION
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'config'`.

- [ ] **Step 3: Create `src/embedded/config.py`**

```python
"""User-tunable constants for the embedded build.

Anything in this file is something a human might want to flip without reading
display.py. Hardware-wiring constants (NEOPIXEL_PIN, NUM_PIXELS) intentionally
stay in display.py since they're fixed by the solder.
"""

# Mounting rotation. One global value applied uniformly to everything drawn on
# the panel (snake, food, score). Pick the value that makes the score read
# upright in your physical setup, then commit. Changing this requires a re-flash.
ROTATION = "90CW"  # "0" | "90CW" | "180" | "90CCW"

# Score-text gradient (game-over screen). The score's lit pixels fade from
# START on the left to END on the right across the message's bounding box.
SCORE_GRADIENT_START = (0, 120, 220)  # cool blue
SCORE_GRADIENT_END = (220, 0, 140)    # magenta
```

- [ ] **Step 4: Update `src/embedded/display.py` imports and remove the local `ORIENTATION`**

In `src/embedded/display.py`, replace lines 1–16 (top imports + constants) with:

```python
from time import sleep

import neopixel  # type: ignore
from machine import Pin  # type: ignore

from common.colors import gradient_color
from config import ROTATION, SCORE_GRADIENT_END, SCORE_GRADIENT_START

# Temporary alias so the existing xy_to_index body needs zero edits during
# the framebuffer migration. Removed in Task 9.
ORIENTATION = ROTATION

WHITE = (128, 128, 128)
BLACK = (0, 0, 0)
GREEN = (0, 128, 0)
RED = (128, 0, 0)
BLUE = (0, 0, 128)

NEOPIXEL_PIN = 13
NUM_PIXELS = 256
NP = neopixel.NeoPixel(Pin(NEOPIXEL_PIN), NUM_PIXELS)
```

Then delete the standalone `ORIENTATION = "90CW"` block at lines 79–83 (the comment block + the assignment) — that constant now lives in `config.py`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS for both tests.

- [ ] **Step 6: Run lint and existing checks**

Run: `uv run ruff check src/embedded/ src/embedded/config.py tests/`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add src/embedded/config.py src/embedded/display.py tests/test_config.py
git commit -m "refactor(embedded): extract user-tunable constants to config.py"
```

---

## Task 3: Framebuffer primitives — `_fb`, `set_pixel`, `clear`

Add the framebuffer storage and write API to `display.py`. No drawer changes yet — drawers still go through `xy_to_index`.

**Files:**
- Modify: `src/embedded/display.py` (add after the `NP = ...` line)
- Create: `tests/test_display_framebuffer.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_display_framebuffer.py`:

```python
"""Framebuffer primitives — pixel writes, clear, layout."""
import display


def _fb_lit_cells():
    """Return the set of (x, y) cells where the framebuffer is non-black."""
    return {
        (i % 16, i // 16) for i, color in enumerate(display._fb) if any(color)
    }


def test_fb_is_256_black_cells_at_module_load():
    # Reset to a known state first — other tests may have written.
    display.clear()
    assert len(display._fb) == 256
    assert all(c == (0, 0, 0) for c in display._fb)


def test_set_pixel_writes_in_natural_coords():
    display.clear()
    display.set_pixel(3, 5, (255, 0, 0))

    # _fb is flat, indexed y*16+x.
    assert display._fb[5 * 16 + 3] == (255, 0, 0)
    # No other cells touched.
    assert _fb_lit_cells() == {(3, 5)}


def test_set_pixel_out_of_range_is_silently_ignored():
    display.clear()
    display.set_pixel(-1, 0, (255, 0, 0))
    display.set_pixel(0, -1, (255, 0, 0))
    display.set_pixel(16, 0, (255, 0, 0))
    display.set_pixel(0, 16, (255, 0, 0))
    display.set_pixel(99, 99, (255, 0, 0))

    # Framebuffer untouched.
    assert all(c == (0, 0, 0) for c in display._fb)


def test_clear_zeros_every_cell():
    # Fill some cells.
    display.set_pixel(0, 0, (1, 2, 3))
    display.set_pixel(15, 15, (4, 5, 6))
    display.set_pixel(7, 8, (9, 10, 11))

    display.clear()

    assert all(c == (0, 0, 0) for c in display._fb)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_display_framebuffer.py -v`
Expected: FAIL with `AttributeError: module 'display' has no attribute '_fb'` (or `set_pixel`/`clear`).

- [ ] **Step 3: Add the framebuffer primitives to `display.py`**

Insert after the `NP = neopixel.NeoPixel(Pin(NEOPIXEL_PIN), NUM_PIXELS)` line (around line 16) and before the `digits = {` block (around line 18):

```python


# ---------------------------------------------------------------------------
# Framebuffer. Drawers write to `_fb` in natural (x, y) coords with no
# rotation or wiring awareness. `flush()` (added later) is the only thing
# that touches NP[].
# ---------------------------------------------------------------------------
_fb = [(0, 0, 0)] * 256  # flat: _fb[y * 16 + x]


def set_pixel(x, y, color):
    """Set framebuffer cell (x, y) to `color` (an (r, g, b) tuple).
    Out-of-range (x, y) is silently ignored."""
    if 0 <= x < 16 and 0 <= y < 16:
        _fb[y * 16 + x] = color


def clear():
    """Reset all 256 framebuffer cells to (0, 0, 0)."""
    for i in range(256):
        _fb[i] = (0, 0, 0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_display_framebuffer.py -v`
Expected: All four tests PASS.

- [ ] **Step 5: Run lint**

Run: `uv run ruff check src/embedded/display.py tests/test_display_framebuffer.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/embedded/display.py tests/test_display_framebuffer.py
git commit -m "feat(embedded): add framebuffer + set_pixel/clear primitives"
```

---

## Task 4: Rotation+serpentine LUT (`_compute_lut`)

Pin the rotation + serpentine math in one place and pre-compute the framebuffer-index → NP-index mapping once at module load.

**Files:**
- Modify: `src/embedded/display.py` (add after `clear()`)
- Modify: `tests/test_display_framebuffer.py` (append LUT tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_display_framebuffer.py`:

```python
def _serpentine(px, py):
    """Reference serpentine: panel (col, row) -> flat NP index."""
    return py * 16 + (px if py % 2 == 0 else 15 - px)


def test_compute_lut_rotation_0_is_pure_serpentine():
    lut = display._compute_lut("0")
    assert lut[0 * 16 + 0] == _serpentine(0, 0)        # top-left
    assert lut[0 * 16 + 15] == _serpentine(15, 0)      # top-right
    assert lut[15 * 16 + 0] == _serpentine(0, 15)      # bottom-left
    assert lut[15 * 16 + 15] == _serpentine(15, 15)    # bottom-right
    # Odd-row cell (py=1, px=3) should flip via serpentine.
    assert lut[1 * 16 + 3] == _serpentine(3, 1)        # i.e. 16 + (15-3) = 28


def test_compute_lut_rotation_90CW_maps_game_to_rotated_panel():
    lut = display._compute_lut("90CW")
    # game (x, y) -> panel (15-y, x)
    assert lut[0 * 16 + 0] == _serpentine(15, 0)
    assert lut[0 * 16 + 15] == _serpentine(15, 15)
    assert lut[15 * 16 + 0] == _serpentine(0, 0)
    assert lut[15 * 16 + 15] == _serpentine(0, 15)


def test_compute_lut_rotation_180_flips_both_axes():
    lut = display._compute_lut("180")
    # game (x, y) -> panel (15-x, 15-y)
    assert lut[0 * 16 + 0] == _serpentine(15, 15)
    assert lut[0 * 16 + 15] == _serpentine(0, 15)
    assert lut[15 * 16 + 0] == _serpentine(15, 0)
    assert lut[15 * 16 + 15] == _serpentine(0, 0)


def test_compute_lut_rotation_90CCW_maps_game_to_rotated_panel():
    lut = display._compute_lut("90CCW")
    # game (x, y) -> panel (y, 15-x)
    assert lut[0 * 16 + 0] == _serpentine(0, 15)
    assert lut[0 * 16 + 15] == _serpentine(15, 15)
    assert lut[15 * 16 + 0] == _serpentine(0, 0)
    assert lut[15 * 16 + 15] == _serpentine(15, 0)


def test_compute_lut_is_a_permutation_of_256_indices():
    # Every panel slot must be covered exactly once, for every rotation.
    for rot in ("0", "90CW", "180", "90CCW"):
        lut = display._compute_lut(rot)
        assert len(lut) == 256
        assert sorted(lut) == list(range(256))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_display_framebuffer.py -v -k compute_lut`
Expected: FAIL with `AttributeError: module 'display' has no attribute '_compute_lut'`.

- [ ] **Step 3: Add `_compute_lut` and the module-level `_lut` to `display.py`**

Insert immediately after the `clear()` function added in Task 3:

```python


def _compute_lut(rotation):
    """Build the framebuffer-index → NP-index mapping for a given rotation.

    Called once at module load (and from tests). For each framebuffer cell
    (x, y), determine the panel cell (px, py) after rotation, then the flat
    NP index via the serpentine wiring (odd panel rows run right-to-left).
    """
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


_lut = _compute_lut(ROTATION)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_display_framebuffer.py -v -k compute_lut`
Expected: All five LUT tests PASS.

- [ ] **Step 5: Run lint**

Run: `uv run ruff check src/embedded/display.py tests/test_display_framebuffer.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/embedded/display.py tests/test_display_framebuffer.py
git commit -m "feat(embedded): precompute rotation+serpentine LUT at module load"
```

---

## Task 5: `flush()` — push framebuffer to NP via LUT

Add the final piece of the new write path. Still no drawer migrations.

**Files:**
- Modify: `src/embedded/display.py` (add after `_lut = _compute_lut(...)`)
- Modify: `tests/test_display_framebuffer.py` (append flush tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_display_framebuffer.py`:

```python
def test_flush_copies_fb_to_np_via_lut():
    display.clear()
    display.set_pixel(0, 0, (10, 20, 30))
    display.set_pixel(15, 15, (40, 50, 60))
    display.set_pixel(3, 1, (70, 80, 90))  # odd row, exercises serpentine

    display.flush()

    # The framebuffer index for each cell:
    assert display.NP[display._lut[0 * 16 + 0]] == (10, 20, 30)
    assert display.NP[display._lut[15 * 16 + 15]] == (40, 50, 60)
    assert display.NP[display._lut[1 * 16 + 3]] == (70, 80, 90)


def test_flush_writes_every_cell_not_just_lit_ones():
    # After a clear+flush, every NP cell should be (0, 0, 0).
    display.clear()
    # Pre-pollute NP to confirm flush overwrites everything.
    for i in range(256):
        display.NP[i] = (99, 99, 99)
    display.flush()
    for i in range(256):
        assert display.NP[i] == (0, 0, 0), f"NP[{i}] not cleared"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_display_framebuffer.py -v -k flush`
Expected: FAIL with `AttributeError: module 'display' has no attribute 'flush'`.

- [ ] **Step 3: Add `flush()` to `display.py`**

Insert immediately after the `_lut = _compute_lut(ROTATION)` line:

```python


def flush():
    """Push the framebuffer to the LEDs via the precomputed LUT, then NP.write().

    The only place rotation + serpentine apply. Drawers write to _fb in plain
    (x, y); flush is what makes the pixels show up on the panel.
    """
    for i in range(256):
        NP[_lut[i]] = _fb[i]
    NP.write()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_display_framebuffer.py -v`
Expected: All tests (primitives + LUT + flush) PASS.

- [ ] **Step 5: Run lint**

Run: `uv run ruff check src/embedded/display.py tests/test_display_framebuffer.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/embedded/display.py tests/test_display_framebuffer.py
git commit -m "feat(embedded): flush() pushes framebuffer to NP via LUT"
```

---

## Task 6: Migrate `display_char` + `display_message` to framebuffer

Switch the text drawer pair to write through `set_pixel` and call `flush()` at the end. Add callable-color support so a per-pixel gradient is possible in Task 7.

**Files:**
- Modify: `src/embedded/display.py` (the `display_char` and `display_message` function bodies)
- Modify: `tests/test_display_framebuffer.py` (append display_char/display_message tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_display_framebuffer.py`:

```python
def test_display_char_writes_pattern_to_fb_at_offset():
    display.clear()
    # "1" pattern is [(0,1,0),(1,1,0),(0,1,0),(0,1,0),(1,1,1)]. At offset
    # (0, 0), scale=1, this puts lit pixels at the 'on' bits of the pattern.
    display.display_char("1", offset_x=0, offset_y=0, color=(255, 0, 0), scale=1)

    expected_lit = {
        (1, 0),               # row 0: (0,1,0)
        (0, 1), (1, 1),       # row 1: (1,1,0)
        (1, 2),               # row 2: (0,1,0)
        (1, 3),               # row 3: (0,1,0)
        (0, 4), (1, 4), (2, 4),  # row 4: (1,1,1)
    }
    actual_lit = {
        (i % 16, i // 16) for i, c in enumerate(display._fb) if any(c)
    }
    assert actual_lit == expected_lit
    # All lit cells use the requested color.
    for x, y in expected_lit:
        assert display._fb[y * 16 + x] == (255, 0, 0)


def test_display_char_accepts_callable_color():
    display.clear()

    def color_for(x, y):
        return (x, y, 0)

    display.display_char("1", offset_x=0, offset_y=0, color=color_for, scale=1)

    # Each lit pixel got the color from its own (x, y).
    assert display._fb[0 * 16 + 1] == (1, 0, 0)
    assert display._fb[1 * 16 + 0] == (0, 1, 0)
    assert display._fb[4 * 16 + 2] == (2, 4, 0)


def test_display_message_lays_out_chars_left_to_right():
    display.clear()
    # advance is 4*scale = 4 for scale=1. Two chars at offsets 0 and 4.
    display.display_message("12", offset_x=0, offset_y=0, color=(1, 1, 1), scale=1)

    # First char "1" at x=0..2; second char "2" at x=4..6 (3-wide patterns).
    lit_x = sorted({i % 16 for i, c in enumerate(display._fb) if any(c)})
    # We expect lit cells in both 0..2 and 4..6 ranges, and nothing at x=3 or x>=7.
    assert 0 in lit_x or 1 in lit_x or 2 in lit_x
    assert 4 in lit_x or 5 in lit_x or 6 in lit_x
    assert 3 not in lit_x
    for x in lit_x:
        assert x < 7


def test_display_message_calls_flush():
    # After display_message, NP should reflect the framebuffer (it called flush).
    display.clear()
    # Pre-pollute NP so we can confirm flush ran.
    for i in range(256):
        display.NP[i] = (99, 99, 99)

    display.display_message("1", offset_x=0, offset_y=0, color=(7, 7, 7), scale=1)

    # At least one NP cell should be (7, 7, 7) (the lit pixels), and the
    # remaining NP cells should be (0, 0, 0) (cleared by the framebuffer flush).
    sevens = sum(1 for c in display.NP.buf if c == (7, 7, 7))
    nines = sum(1 for c in display.NP.buf if c == (99, 99, 99))
    assert sevens > 0
    assert nines == 0  # all the pre-pollution got overwritten
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_display_framebuffer.py -v -k "display_char or display_message"`
Expected: tests fail — current `display_char` writes to `NP[xy_to_index(...)]` not `_fb`, and doesn't yet accept a callable color.

- [ ] **Step 3: Rewrite `display_char` and `display_message`**

In `src/embedded/display.py`, replace the `display_char` function (and the comment block above it) with:

```python
# Text drawing routes through the framebuffer (set_pixel) so it has no
# knowledge of rotation or wiring. `scale` blows each pattern pixel up to a
# scale x scale block. `color` may be an (r, g, b) tuple OR a callable
# `(x, y) -> (r, g, b)` for per-pixel coloring (gradients).
def display_char(char, offset_x=0, offset_y=0, color=WHITE, scale=1):
    char = char.upper()
    pattern = characters.get(char) or digits.get(char) or special_chars.get(char)
    if pattern is None:
        return

    color_is_callable = callable(color)
    for row_idx, row in enumerate(pattern):
        for col_idx, pixel in enumerate(row):
            if not pixel:
                continue
            for dx in range(scale):
                for dy in range(scale):
                    x = offset_x + col_idx * scale + dx
                    y = offset_y + row_idx * scale + dy
                    if 0 <= x < 16 and 0 <= y < 16:
                        set_pixel(x, y, color(x, y) if color_is_callable else color)
```

And replace `display_message` with:

```python
def display_message(message, offset_x=0, offset_y=0, color=WHITE, scale=1):
    advance = 4 * scale  # 3-col glyph + 1-col padding, both scaled
    for char in message:
        display_char(char, offset_x, offset_y, color, scale)
        offset_x += advance
        if offset_x >= 16:
            break
    flush()
```

Three behavior changes from the previous code:
1. `display_char` writes via `set_pixel` to `_fb` (not `NP[xy_to_index]`).
2. `display_char` only writes lit pixels — it no longer overwrites empty pattern cells with `(0, 0, 0)`. The caller is responsible for the background (`clear()`-ing first or trusting `flush()` to push a black framebuffer).
3. `display_message` calls `flush()` instead of `NP.write()`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_display_framebuffer.py -v`
Expected: All tests pass.

- [ ] **Step 5: Run lint**

Run: `uv run ruff check src/embedded/display.py tests/test_display_framebuffer.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/embedded/display.py tests/test_display_framebuffer.py
git commit -m "refactor(embedded): display_char + display_message use framebuffer"
```

---

## Task 7: Migrate `display_scores` to framebuffer + gradient

Replace the score's solid-color render with a horizontal gradient that uses the new callable-color path. The drawer becomes a small wrapper that clears the framebuffer, builds a gradient closure, and calls `display_message` (which calls `flush`).

**Files:**
- Modify: `src/embedded/display.py` (`display_scores`)
- Modify: `tests/test_display_framebuffer.py` (append score tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_display_framebuffer.py`:

```python
import config


def test_display_scores_clears_then_writes_score():
    # Pre-pollute the framebuffer with non-zero pixels.
    for i in range(256):
        display._fb[i] = (33, 33, 33)

    display.display_scores(high_score=0, current_score=12)

    # Pollution removed: only score pixels are lit.
    lit_count = sum(1 for c in display._fb if any(c))
    assert 0 < lit_count < 256


def test_display_scores_writes_two_digits_for_two_digit_score():
    display.clear()
    display.display_scores(high_score=0, current_score=12)

    # Two digit areas in the framebuffer, separated by a gap.
    lit_x = {i % 16 for i, c in enumerate(display._fb) if any(c)}
    # Score is centered: width = 2*4*2 - 2 = 14, offset_x = (16-14)//2 = 1.
    # First digit x range: 1..6 (cols 0,1,2 of "1" * scale 2).
    # Second digit x range: 9..14.
    assert lit_x.issubset(set(range(1, 7)) | set(range(9, 15)))
    assert lit_x & set(range(1, 7)), "first digit area not lit"
    assert lit_x & set(range(9, 15)), "second digit area not lit"


def test_display_scores_gradient_endpoints_match_config():
    display.clear()
    display.display_scores(high_score=0, current_score=12)

    # The leftmost lit column should carry SCORE_GRADIENT_START, the rightmost
    # lit column should carry SCORE_GRADIENT_END.
    lit_by_x = {}
    for i, c in enumerate(display._fb):
        if any(c):
            x = i % 16
            lit_by_x.setdefault(x, c)
    leftmost_x = min(lit_by_x)
    rightmost_x = max(lit_by_x)
    assert lit_by_x[leftmost_x] == config.SCORE_GRADIENT_START
    assert lit_by_x[rightmost_x] == config.SCORE_GRADIENT_END
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_display_framebuffer.py -v -k display_scores`
Expected: tests fail — current `display_scores` uses solid `BLUE`, has no gradient, and calls `clear_screen()` (which still hits NP directly).

- [ ] **Step 3: Rewrite `display_scores`**

In `src/embedded/display.py`, replace `display_scores` (and the comment above it) with:

```python
# Game-over score: centered, horizontally gradient-colored. Drawn into the
# framebuffer in natural coordinates — rotation is applied by flush() (via
# config.ROTATION), uniformly with the snake/food.
def display_scores(high_score, current_score):
    score_str = str(current_score)
    scale = 2
    # 4*scale per char, minus the trailing padding after the last char.
    width = len(score_str) * 4 * scale - scale
    offset_x = max(0, (16 - width) // 2)
    offset_y = (16 - 5 * scale) // 2
    left = offset_x

    def gradient(x, _y):
        return gradient_color(x - left, width, SCORE_GRADIENT_START, SCORE_GRADIENT_END)

    clear()
    display_message(score_str, offset_x, offset_y, gradient, scale=scale)
    # High score hidden for now — re-enable when layout is ready:
    # display_message(f"H:{high_score}", 1, 1, GREEN)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_display_framebuffer.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Run lint**

Run: `uv run ruff check src/embedded/display.py tests/test_display_framebuffer.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/embedded/display.py tests/test_display_framebuffer.py
git commit -m "refactor(embedded): display_scores uses framebuffer + gradient"
```

---

## Task 8: Migrate `draw_snake` to framebuffer

The highest-frequency caller. After this commit, every drawer in `display.py` goes through the framebuffer; `xy_to_index` becomes dead code.

**Files:**
- Modify: `src/embedded/display.py` (`draw_snake`, `reset_draw_caches`)
- Modify: `tests/test_display_framebuffer.py` (append snake tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_display_framebuffer.py`:

```python
class _FakeEngine:
    """Minimal stand-in for SnakeEngine — just exposes the attributes draw_snake reads."""

    def __init__(self, snake, food):
        self.snake = snake
        self.food = food


def test_draw_snake_writes_snake_cells_and_food_to_fb():
    display.clear()
    display.reset_draw_caches()

    engine = _FakeEngine(snake=[(5, 5), (5, 6), (5, 7)], food=(10, 10))
    palette = ((255, 0, 0), (0, 0, 64), (0, 255, 0), 1000)
    # speed=1000 so the sleep is ~1ms; doesn't matter for the framebuffer test.

    display.draw_snake(engine, palette)

    # Snake cells are lit with the gradient.
    for (x, y) in engine.snake:
        assert any(display._fb[y * 16 + x]), f"snake cell ({x},{y}) not lit"
    # Food cell is the food color.
    fx, fy = engine.food
    assert display._fb[fy * 16 + fx] == (0, 255, 0)


def test_draw_snake_clears_vacated_cells_in_fb():
    display.clear()
    display.reset_draw_caches()

    # First frame: snake at A.
    e1 = _FakeEngine(snake=[(5, 5), (5, 6)], food=(10, 10))
    display.draw_snake(e1, ((255, 0, 0), (0, 0, 64), (0, 255, 0), 1000))
    assert any(display._fb[6 * 16 + 5])

    # Second frame: snake moved; (5, 6) is vacated.
    e2 = _FakeEngine(snake=[(5, 4), (5, 5)], food=(10, 10))
    display.draw_snake(e2, ((255, 0, 0), (0, 0, 64), (0, 255, 0), 1000))

    # (5, 6) should now be black.
    assert display._fb[6 * 16 + 5] == (0, 0, 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_display_framebuffer.py -v -k draw_snake`
Expected: tests fail — current `draw_snake` writes to `NP[xy_to_index]` directly.

- [ ] **Step 3: Rewrite `draw_snake` and `reset_draw_caches`**

In `src/embedded/display.py`, replace `draw_snake` with:

```python
def draw_snake(engine, palette):
    """Paint one frame: snake gradient + food cell. Sleeps for the engine tick.

    palette is (start_color, end_color, food_color, speed) — provided by the
    embedded SnakeGame each frame.
    """
    global _prev_snake_cells, _gradient_colors, _previous_snake_length  # noqa: PLW0603

    start_color, end_color, food_color, speed = palette
    cur = set(engine.snake)

    snake_length = len(engine.snake)
    if snake_length != _previous_snake_length:
        _gradient_colors = [gradient_color(i, snake_length, start_color, end_color) for i in range(snake_length)]
        _previous_snake_length = snake_length

    # Clear cells that were snake last frame but aren't now.
    for x, y in _prev_snake_cells - cur:
        set_pixel(x, y, BLACK)

    # Repaint current snake cells.
    for i, (x, y) in enumerate(engine.snake):
        set_pixel(x, y, _gradient_colors[i])

    # Food pixel.
    fx, fy = engine.food
    set_pixel(fx, fy, food_color)

    flush()
    _prev_snake_cells = cur
    sleep(1 / speed)
```

And update `reset_draw_caches` to use the new `clear()` helper and push the cleared framebuffer once:

```python
def reset_draw_caches():
    """Call between games so the new game starts blank with fresh caches."""
    global _prev_snake_cells, _gradient_colors, _previous_snake_length  # noqa: PLW0603
    _prev_snake_cells = set()
    _gradient_colors = []
    _previous_snake_length = 0
    clear()
    flush()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_display_framebuffer.py -v`
Expected: All tests pass.

- [ ] **Step 5: Run lint**

Run: `uv run ruff check src/embedded/display.py tests/test_display_framebuffer.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/embedded/display.py tests/test_display_framebuffer.py
git commit -m "refactor(embedded): draw_snake + reset_draw_caches use framebuffer"
```

---

## Task 9: Delete the old surface

`xy_to_index`, `_physical_to_index`, `clear_screen`, and the temporary `ORIENTATION` alias are all dead code now. Remove them so the file shrinks and the new abstractions are the only path.

**Files:**
- Modify: `src/embedded/display.py`

- [ ] **Step 1: Confirm no remaining callers**

Run: `grep -rn "xy_to_index\|_physical_to_index\|clear_screen\|display\.ORIENTATION" src/ tests/`
Expected: matches only inside `src/embedded/display.py` (the definitions themselves). If there are any other matches, fix them first by switching to the new API and re-run.

- [ ] **Step 2: Delete the dead definitions and the alias**

In `src/embedded/display.py`:

1. Delete the `ORIENTATION = ROTATION` alias line (added in Task 2 just below the imports).
2. Delete the entire `xy_to_index` function and its preceding comment block.
3. Delete the entire `_physical_to_index` function (if it exists in the current file — check).
4. Delete the entire `clear_screen` function and its preceding comment block.

In `tests/test_config.py`:

5. Delete the `test_display_uses_rotation_from_config` test (added in Task 2) — the alias it asserted on no longer exists. Keep `test_config_exposes_rotation_and_gradient_constants`.

After this commit, the only rotation-aware code in `display.py` is `_compute_lut`.

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests still pass.

- [ ] **Step 4: Run lint**

Run: `uv run ruff check src/embedded/`
Expected: `All checks passed!`

- [ ] **Step 5: Sanity-check the sim still launches**

Run: `timeout 5 uv run python src/sim/main.py || true`
Expected: pygame window opens, you see a snake render briefly, then it exits via the timeout. Any traceback is a regression — investigate before continuing.

- [ ] **Step 6: Commit**

```bash
git add src/embedded/display.py
git commit -m "refactor(embedded): drop xy_to_index/clear_screen/ORIENTATION alias"
```

---

## Task 10: Verification harness (`scripts/preview_score.py`)

Replace the ad-hoc `/tmp/verify_score.py` from earlier this session with a checked-in script. It renders `NP[]` as ASCII for each rotation so you can eyeball "this is what the hardware will look like" before flashing.

**Files:**
- Create: `scripts/preview_score.py`

- [ ] **Step 1: Check whether `scripts/` exists**

Run: `ls scripts/ 2>/dev/null || echo "missing"`
Expected: either a listing (in which case skip mkdir) or `missing`. If `missing`, create the dir as part of step 2.

- [ ] **Step 2: Write the script**

Create `scripts/preview_score.py`:

```python
"""Preview the score render as ASCII for every rotation.

Run from the repo root:

    uv run python scripts/preview_score.py

This bypasses pygame entirely: it imports the embedded display module with
fakes pre-loaded, calls display_scores for a few sample scores, and prints
the post-flush NP buffer (the same bytes hardware lights up) as ASCII.

Use this to pick the right ROTATION value before flashing. Edit
src/embedded/config.py, re-run, eyeball, repeat.
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC / "embedded"))

from sim import fake_machine, fake_neopixel  # noqa: E402

sys.modules["machine"] = fake_machine
sys.modules["neopixel"] = fake_neopixel

from sim import screen  # noqa: E402

screen.flush = lambda buf: None  # headless

import config  # noqa: E402
import display  # noqa: E402

SIZE = 16


def np_to_panel(buffer):
    """Invert serpentine: buffer[i] -> panel grid[py][px]."""
    grid = [[(0, 0, 0)] * SIZE for _ in range(SIZE)]
    for i, color in enumerate(buffer):
        py = i // SIZE
        off = i % SIZE
        px = off if py % 2 == 0 else SIZE - 1 - off
        grid[py][px] = color
    return grid


def render_ascii(grid):
    return "\n".join(
        "".join("##" if any(c) else ". " for c in row) for row in grid
    )


def render_score(score):
    display.display_scores(0, score)
    return render_ascii(np_to_panel(display.NP.buf))


print(f"config.ROTATION = {config.ROTATION!r}")
print(f"display._lut is built for the above. Edit config.py and re-run to compare rotations.\n")
for score in (5, 12, 99):
    print(f"--- score = {score} ---")
    print(render_score(score))
    print()
```

- [ ] **Step 3: Run the script**

Run: `uv run python scripts/preview_score.py`
Expected: ASCII for scores 5, 12, 99 prints to stdout. For `ROTATION="0"`, the digits should read upright and side-by-side.

- [ ] **Step 4: Run lint**

Run: `uv run ruff check scripts/preview_score.py`
Expected: `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add scripts/preview_score.py
git commit -m "tools(embedded): scripts/preview_score.py renders score per rotation"
```

---

## Task 11: Pick the final `ROTATION` value on hardware

This is a manual verification + tiny config edit + flash. The framebuffer refactor is done as far as code; this is the moment we decide which rotation makes the score read correctly on the user's mounted panel.

**Files:**
- Modify: `src/embedded/config.py` (only the `ROTATION` line)

- [ ] **Step 1: Sim preview at the current value**

Run: `uv run python src/sim/main.py`
Expected: a pygame window opens; the snake renders and the score appears at game-over. Note how the score is laid out in the sim.

- [ ] **Step 2: Flash to hardware**

Use the `flash-snake` skill (or run the equivalent `mpremote` commands by hand). Confirm the matrix lights up and the snake renders.

- [ ] **Step 3: Look at the game-over score on hardware**

Play (or let the AI play) until the snake dies. Inspect the score render.

- [ ] **Step 4: If the score reads upright and side-by-side, you're done. If not:**

Edit `src/embedded/config.py` and try the next `ROTATION` value (e.g., `"0"` → `"90CW"` → `"180"` → `"90CCW"`). Re-flash and re-check. Stop when it looks right.

Run, after every edit: `uv run pytest tests/ -v` to make sure the change didn't break tests (it shouldn't — `ROTATION` is just a constant — but cheap insurance).

- [ ] **Step 5: Commit the final `ROTATION` value**

```bash
git add src/embedded/config.py
git commit -m "config(embedded): set ROTATION to <value> to match physical mount"
```

(Replace `<value>` with the chosen rotation, e.g., `0`.)

---

## Final verification checklist

After Task 11:

- [ ] `uv run pytest tests/ -v` — all tests green.
- [ ] `uv run ruff check src/ tests/ scripts/` — clean.
- [ ] `uv run mypy` — clean (only covers `src/common` and `src/desktop`; embedded is intentionally excluded).
- [ ] Sim: `uv run python src/sim/main.py` runs without errors; gameplay looks right; score reads correctly at game-over.
- [ ] Hardware: snake renders during play; score reads correctly at game-over.
- [ ] `git log --oneline` shows one commit per task with clear conventional-commit messages.
- [ ] `grep -rn "xy_to_index\|_physical_to_index\|clear_screen\b\|ORIENTATION" src/ tests/` returns no matches outside intentional references (none expected).

---

## Notes for the implementing engineer

- **MicroPython-safety.** Everything in `src/embedded/` and `src/common/` must avoid `typing` imports, `dataclass`, `enum`, and anything outside the MicroPython stdlib. f-strings are fine. Keep allocations cheap in hot paths (the inner loop of `flush` and `draw_snake` runs once per LED per frame).
- **Test runner.** Tests use the existing `uv run pytest` infra; `tests/conftest.py` (Task 1) handles all the `sys.modules` / `sys.path` plumbing.
- **Sim doesn't change.** `src/sim/screen.py` still renders `NP[]` directly. Because every drawer now ends in `flush()` (which pushes `_fb` → `NP`), what the sim shows is what the hardware lights. They match by construction.
- **Why `clear()` writes `(0, 0, 0)` not `BLACK`.** They're the same value; the loop body avoids a name lookup per cell on MicroPython. Cosmetic.
- **The score now writes only lit pixels.** Drawers no longer overwrite empty pattern cells with black. Callers that want a clean background must `clear()` first (or trust the framebuffer is already clean from a prior `clear()` / `reset_draw_caches`). `display_scores` does its own `clear()`; `display_message` does not.
