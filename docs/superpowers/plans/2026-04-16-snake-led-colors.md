# Snake LED-matrix color & draw-loop refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix color-generation correctness bugs in `SnakeGame`, replace the RGB random-color picker with a coherent single-hue HSV scheme, and cut `draw_snake` CPU cost by removing the per-frame 256-pixel clear.

**Architecture:** Put the pure-Python `hsv_to_rgb` helper in `src/common/common.py` next to the existing `Direction` primitive so it is importable from CPython for quick sanity checks and from MicroPython on the ESP32. All game-specific colour logic and the draw-loop rewrite stay in `src/led_matrix/game.py`.

**Tech Stack:** Python / MicroPython (ESP32), `neopixel` (firmware-provided), `random`.

**Reference spec:** [docs/superpowers/specs/2026-04-16-snake-led-colors-design.md](../specs/2026-04-16-snake-led-colors-design.md).

---

## File Structure

- **Modify:** `src/common/common.py` — add `hsv_to_rgb`.
- **Modify:** `src/led_matrix/game.py` — imports, `get_rand_color`, `__init__`, `_new_food_color` (new), `generate_food`, `draw_snake`.

No other files are touched. `boot.py`, `main.py`, `display.py`, and the PC version in `src/ai/` remain unchanged.

---

## Task 1: Add `hsv_to_rgb` to common.py

**Files:**
- Modify: `src/common/common.py`

- [ ] **Step 1: Append `hsv_to_rgb` to common.py**

After the `Direction` class, append:

```python


def hsv_to_rgb(h, s, v):
    """Convert HSV to an (r, g, b) tuple of ints in 0..255.

    h: hue in [0, 1) — values outside the range wrap.
    s: saturation in [0, 1].
    v: value in [0, 1].
    """
    if s <= 0.0:
        c = int(round(v * 255))
        return (c, c, c)
    h6 = (h % 1.0) * 6.0
    i = int(h6)
    f = h6 - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, p, v
    else:
        r, g, b = v, p, q
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))
```

- [ ] **Step 2: Sanity-check from CPython**

Run (from repo root):

```bash
PYTHONPATH=src/common python3 -c "
from common import hsv_to_rgb
assert hsv_to_rgb(0.0,    1.0, 1.0) == (255, 0,   0),   hsv_to_rgb(0.0,    1.0, 1.0)
assert hsv_to_rgb(1/3.0,  1.0, 1.0) == (0,   255, 0),   hsv_to_rgb(1/3.0,  1.0, 1.0)
assert hsv_to_rgb(2/3.0,  1.0, 1.0) == (0,   0,   255), hsv_to_rgb(2/3.0,  1.0, 1.0)
assert hsv_to_rgb(0.0,    0.0, 0.5) == (128, 128, 128), hsv_to_rgb(0.0,    0.0, 0.5)
assert hsv_to_rgb(0.0,    1.0, 0.0) == (0,   0,   0),   hsv_to_rgb(0.0,    1.0, 0.0)
assert hsv_to_rgb(1.5,    1.0, 1.0) == hsv_to_rgb(0.5, 1.0, 1.0), 'hue wrap'
print('hsv_to_rgb: OK')
"
```

Expected output:

```text
hsv_to_rgb: OK
```

- [ ] **Step 3: Commit**

```bash
git add src/common/common.py
git -c commit.gpgsign=false commit -m "feat(common): add hsv_to_rgb helper

Pure-Python HSV→RGB conversion, MicroPython-compatible. Backs the snake
gradient and food colour in the LED matrix game."
```

---

## Task 2: Replace `get_rand_color` with an HSV picker

**Files:**
- Modify: `src/led_matrix/game.py`

- [ ] **Step 1: Update the `common` import**

At [src/led_matrix/game.py:1](src/led_matrix/game.py#L1), change:

```python
from common import Direction
```

to:

```python
from common import Direction, hsv_to_rgb
```

- [ ] **Step 2: Expand the `random` imports**

At [src/led_matrix/game.py:3](src/led_matrix/game.py#L3), change:

```python
from random import randint
```

to:

```python
from random import choice, randint, random, uniform
```

(`randint` stays until Task 5 replaces the last caller.)

- [ ] **Step 3: Replace `get_rand_color`**

Replace lines 27-36 (the `get_rand_color` function and its comment):

```python
# Function to generate a random bright color where RGB values differ sufficiently to avoid grey
def get_rand_color():
    while True:
        r = randint(0, 175)
        g = randint(0, 175)
        b = randint(0, 175)
        
        # Check that the difference between each component is large enough to avoid grey tones
        if abs(r - g) > 50 and abs(g - b) > 50 and abs(b - r) > 50:
            return (r, g, b)
```

with:

```python
# Return a vivid random RGB color via HSV: full saturation, brightness matches
# the 175/255 NeoPixel power budget used previously.
def get_rand_color():
    return hsv_to_rgb(random(), 1.0, 0.70)
```

- [ ] **Step 4: Sanity-check**

Run:

```bash
PYTHONPATH=src/common python3 -c "
from common import hsv_to_rgb
from random import random
for _ in range(20):
    c = hsv_to_rgb(random(), 1.0, 0.70)
    # At s=1 one channel is exactly 0; at v=0.70 the max channel is ~178.
    assert min(c) == 0, c
    assert max(c) >= 170 and max(c) <= 179, c
print('get_rand_color replacement: OK')
"
```

- [ ] **Step 5: Commit**

```bash
git add src/led_matrix/game.py
git -c commit.gpgsign=false commit -m "refactor(led_matrix): HSV-based random colour

Replaces the rejection-sampling RGB picker with a single hsv_to_rgb
call. Always vivid, no loop, preserves the existing ~175/255 power cap."
```

---

## Task 3: Fix mutable default args and add `base_hue` / `_prev_snake_cells` state

**Files:**
- Modify: `src/led_matrix/game.py`

- [ ] **Step 1: Rewrite `SnakeGame.__init__`**

Replace lines 56-77 (the full `__init__` method) with:

```python
def __init__(self,
             start_color=None,
             end_color=None,
             speed=DEFAULT_SPEED):
    self.speed = speed

    # Per-game hue so successive games look fresh and coherent.
    if start_color is None or end_color is None:
        self.base_hue = random()
        if start_color is None:
            start_color = hsv_to_rgb(self.base_hue, 1.0, 0.15)  # dim tail
        if end_color is None:
            end_color = hsv_to_rgb(self.base_hue, 1.0, 0.70)   # bright head
    else:
        # Caller supplied a custom palette; food falls back to a random hue.
        self.base_hue = None

    self.snake = [(int(GAME_SIZE / 2), int(GAME_SIZE / 2))]
    self.start_color = start_color
    self.end_color = end_color
    self.previous_snake_length = 0
    self.gradient_colors = []
    self.direction = Direction.RIGHT
    self.food_color = None  # Assigned by generate_food.
    self.food = self.generate_food()
    self._prev_snake_cells = set()
    self.game_over = False
    self.score = 0
    self.direction_changes = {
        Direction.UP: (-1, 0),
        Direction.DOWN: (1, 0),
        Direction.LEFT: (0, -1),
        Direction.RIGHT: (0, 1),
    }
```

Notes:
- The `food_color` constructor parameter is removed — it was dead code (always overwritten by `generate_food`).
- `base_hue` stores the current game's hue; `None` signals "custom palette, use a random food hue."
- `_prev_snake_cells` seeds the incremental draw in Task 6.

- [ ] **Step 2: Parse-check the file**

Run:

```bash
python3 -c "import ast; ast.parse(open('src/led_matrix/game.py').read()); print('parses OK')"
```

Expected output: `parses OK`.

- [ ] **Step 3: Verify the freshness invariant from CPython**

This proves two successive games now get different `start_color` and `end_color`:

```bash
PYTHONPATH=src/common python3 -c "
from common import hsv_to_rgb
from random import random
hues = [random() for _ in range(5)]
assert len(set(hues)) == 5
starts = [hsv_to_rgb(h, 1.0, 0.15) for h in hues]
ends   = [hsv_to_rgb(h, 1.0, 0.70) for h in hues]
assert len(set(starts)) == 5 and len(set(ends)) == 5
print('mutable-default-fix logic: OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add src/led_matrix/game.py
git -c commit.gpgsign=false commit -m "fix(led_matrix): per-game start/end colours

Mutable default args on SnakeGame.__init__ were evaluated once at class
definition, so every new game reused the same gradient. Generate colours
inside __init__ from a fresh base_hue. Also drops the unused food_color
arg and seeds _prev_snake_cells for incremental drawing."
```

---

## Task 4: Add `_new_food_color`

**Files:**
- Modify: `src/led_matrix/game.py`

- [ ] **Step 1: Add the method inside `SnakeGame`**

Insert this method immediately before `generate_food` (currently at line 79):

```python
def _new_food_color(self):
    """Complementary hue to the snake base, plus tiny jitter for variety."""
    if self.base_hue is None:
        return hsv_to_rgb(random(), 1.0, 0.70)
    h = (self.base_hue + 0.5 + uniform(-0.05, 0.05)) % 1.0
    return hsv_to_rgb(h, 1.0, 0.70)
```

- [ ] **Step 2: Sanity-check that complement is high-contrast**

Run:

```bash
PYTHONPATH=src/common python3 -c "
from common import hsv_to_rgb
from random import uniform
# Snake red (hue=0) → food should land near cyan.
base = 0.0
h = (base + 0.5 + uniform(-0.05, 0.05)) % 1.0
c = hsv_to_rgb(h, 1.0, 0.70)
assert c[0] < 60, c                        # R dim
assert c[1] > 120 or c[2] > 120, c         # G or B bright
# Snake green (hue=1/3) → food should land near magenta.
base = 1/3.0
h = (base + 0.5 + uniform(-0.05, 0.05)) % 1.0
c = hsv_to_rgb(h, 1.0, 0.70)
assert c[1] < 60, c
assert c[0] > 120 or c[2] > 120, c
print('_new_food_color complement: OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add src/led_matrix/game.py
git -c commit.gpgsign=false commit -m "feat(led_matrix): complementary food colour

Food picks a hue ~180° from the snake's base_hue (with small jitter),
guaranteeing high-contrast against the gradient."
```

---

## Task 5: Rewrite `generate_food` with free-cell enumeration

**Files:**
- Modify: `src/led_matrix/game.py`

- [ ] **Step 1: Replace `generate_food`**

Replace the existing `generate_food` method (currently lines 79-84):

```python
def generate_food(self):
    food = (randint(0, GAME_SIZE-1), randint(0, GAME_SIZE-1))
    self.food_color = get_rand_color()
    if food in self.snake:
        return self.generate_food()
    return food
```

with:

```python
def generate_food(self):
    occupied = set(self.snake)
    free = [(x, y)
            for x in range(GAME_SIZE)
            for y in range(GAME_SIZE)
            if (x, y) not in occupied]
    if not free:
        # Board is full — player has effectively won; let the game end.
        self.game_over = True
        return self.snake[0]
    self.food_color = self._new_food_color()
    return choice(free)
```

- [ ] **Step 2: Drop `randint` from imports**

At [src/led_matrix/game.py:3](src/led_matrix/game.py#L3), change:

```python
from random import choice, randint, random, uniform
```

to:

```python
from random import choice, random, uniform
```

- [ ] **Step 3: Confirm `randint` is gone**

Run:

```bash
grep -n 'randint' src/led_matrix/game.py && echo 'FAIL: randint still referenced' || echo 'clean'
```

Expected output: `clean`.

(`get_rand_color` remains in the file as a tiny `hsv_to_rgb(random(), 1.0, 0.70)` wrapper — kept as a public module-level helper even though nothing else in this file calls it after the refactor.)

- [ ] **Step 4: Parse-check**

```bash
python3 -c "import ast; ast.parse(open('src/led_matrix/game.py').read()); print('parses OK')"
```

- [ ] **Step 5: Logic check for bounded free-cell selection**

```bash
python3 -c "
from random import choice
GAME_SIZE = 16
full = [(x, y) for x in range(GAME_SIZE) for y in range(GAME_SIZE)]
assert [c for c in full if c not in set(full)] == []
snake = [(0, 0)]
free = [(x, y) for x in range(GAME_SIZE) for y in range(GAME_SIZE) if (x, y) not in set(snake)]
assert len(free) == GAME_SIZE * GAME_SIZE - 1
pick = choice(free)
assert pick != (0, 0)
print('generate_food logic: OK')
"
```

- [ ] **Step 6: Commit**

```bash
git add src/led_matrix/game.py
git -c commit.gpgsign=false commit -m "refactor(led_matrix): bounded free-cell food generator

Replaces unbounded recursion in generate_food with explicit free-cell
enumeration + random.choice, and wires food_color to _new_food_color.
Sets game_over when the board fills."
```

---

## Task 6: Incremental `draw_snake`

**Files:**
- Modify: `src/led_matrix/game.py`

- [ ] **Step 1: Replace `draw_snake`**

Replace the entire `draw_snake` method (currently lines 155-180) with:

```python
# Draw the game state on the NeoPixel matrix with the gradient snake.
def draw_snake(self):
    cur = set(self.snake)

    # Cache the gradient only when length changes.
    snake_length = len(self.snake)
    if snake_length != self.previous_snake_length:
        self.gradient_colors = [
            get_gradient_color(index, snake_length, self.start_color, self.end_color)
            for index in range(snake_length)
        ]
        self.previous_snake_length = snake_length

    # Clear cells that were snake last frame but aren't now (usually just the dropped tail).
    for (x, y) in self._prev_snake_cells - cur:
        NP[xy_to_index(x, y)] = BLACK

    # Repaint current snake cells (gradient indexes shift as the snake moves).
    for index, (x, y) in enumerate(self.snake):
        NP[xy_to_index(x, y)] = self.gradient_colors[index]

    # Paint the food pixel.
    food_x, food_y = self.food
    NP[xy_to_index(food_x, food_y)] = self.food_color

    NP.write()
    self._prev_snake_cells = cur

    # Game speed.
    sleep(1 / self.speed)
```

Key points:
- **No `NP.fill(BLACK)`** and **one `NP.write()` per frame** — preserves the flicker-free behaviour already in place.
- Clearing uses `_prev_snake_cells - cur`, which is the set of cells the snake vacated (typically just the dropped tail; empty on the frame it eats food).

- [ ] **Step 2: Parse-check**

```bash
python3 -c "import ast; ast.parse(open('src/led_matrix/game.py').read()); print('parses OK')"
```

- [ ] **Step 3: Confirm no stray `NP.fill` or extra `NP.write` in `draw_snake`**

```bash
awk '/def draw_snake/,/^    def /' src/led_matrix/game.py | grep -nE 'NP\.(fill|write)'
```

Expected: exactly one `NP.write()` line, zero `NP.fill(` lines.

- [ ] **Step 4: Commit**

```bash
git add src/led_matrix/game.py
git -c commit.gpgsign=false commit -m "perf(led_matrix): incremental draw_snake

Skip the 256-pixel NP.fill every frame; only clear cells the snake
vacated (tracked via _prev_snake_cells). Cuts per-frame MicroPython
interpreter work from O(256) to O(snake_length)."
```

---

## Task 7: Deploy to the board and smoke-verify

**Files:** none modified — verification only.

- [ ] **Step 1: Upload the changed files**

With the ESP32 connected on `/dev/ttyUSB0`, run from the repo root:

```bash
timeout 30 python3 - <<'PY'
import serial, time, sys

PORT = '/dev/ttyUSB0'
FILES = [
    ('src/common/common.py', 'common.py'),
    ('src/led_matrix/game.py', 'game.py'),
]

s = serial.Serial(PORT, 115200, timeout=0.3)
time.sleep(1.5)
buf = b''
for _ in range(30):
    s.write(b'\x03')
    time.sleep(0.1)
    buf += s.read(4096)
    if b'>>>' in buf:
        break
assert b'>>>' in buf, f'no REPL prompt; got: {buf[-400:]!r}'

s.write(b'\r\x01')
time.sleep(0.2)
resp = s.read(4096)
assert b'raw REPL' in resp, resp[-200:]

def exec_raw(code):
    s.write(code.encode() + b'\x04')
    out = b''
    deadline = time.time() + 5
    while time.time() < deadline:
        out += s.read(4096)
        if out.endswith(b'\x04>'):
            break
    return out

for src, dst in FILES:
    data = open(src, 'rb').read()
    print(f'Uploading {dst} ({len(data)} bytes)')
    r = exec_raw(f"f=open({dst!r},'wb')\nw=f.write\n")
    assert b'Traceback' not in r, r
    for i in range(0, len(data), 256):
        r = exec_raw(f"w({data[i:i+256]!r})\n")
        assert b'Traceback' not in r, r[-300:]
    r = exec_raw("f.close()\n")
    assert b'Traceback' not in r, r

s.write(b'\x02')
time.sleep(0.2); s.read(4096)
s.write(b'\x04')        # soft reset → runs boot.py then main.py
time.sleep(0.3); s.close()
print('Uploaded and soft-reset.')
PY
```

Expected final line: `Uploaded and soft-reset.`

- [ ] **Step 2: Watch the panel for one game cycle**

Visually confirm:

1. Snake body shows a dim-to-bright **single-hue** gradient (no grey/muddy midpoints).
2. Food pixel is clearly a different, contrasting hue.
3. No black flash between frames.
4. After game-over → restart, the new snake is a **different** hue from the previous game (this proves the mutable-default bug is fixed).

- [ ] **Step 3: Confirm `mpremote` still works for future copies**

```bash
timeout 15 mpremote connect /dev/ttyUSB0 eval 'import os; print(sorted(os.listdir()))'
```

Expected: output contains `'common.py'` and `'game.py'` (among others). If mpremote errors with `could not enter raw repl`, hit the ESP32's reset button and retry within a few seconds — `main.py`'s `KeyboardInterrupt` handler should drop the REPL cleanly after that.

---

## Notes for the implementer

- **Power budget.** The 0.70 `v` ceiling preserves the original 175/255 RGB cap — don't raise it without re-checking NeoPixel current draw.
- **MicroPython availability.** `random.random`, `random.uniform`, and `random.choice` are all in MicroPython ≥ 1.23 — no compat shim required.
- **Single `NP.write()` per frame.** Do not add any other `NP.write()` calls inside `draw_snake`; that's exactly what caused the original flicker.
- **`_prev_snake_cells` lifecycle.** Assigned at the end of `draw_snake` from `set(self.snake)`. Don't touch it from any other method — it's purely a draw-cache.
- **Test harness.** The repo has no test runner; the per-task CPython sanity checks are deliberate one-liners. If a test runner is added later, migrate these into real unit tests.
