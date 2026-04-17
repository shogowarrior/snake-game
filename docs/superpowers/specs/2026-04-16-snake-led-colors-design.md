# Snake LED-matrix color & draw-loop refactor

**Date:** 2026-04-16
**Scope:** `src/led_matrix/game.py`. No changes to AI, game rules, wrapping, or the PC/Pygame variant in [src/ai/](../../../src/ai/).

## Background

`SnakeGame` has three issues affecting visual quality and correctness:

1. **Colors are frozen at class-definition time.** The constructor uses `start_color=get_rand_color()` etc. as default arguments ([src/led_matrix/game.py:57-59](../../../src/led_matrix/game.py#L57-L59)); Python evaluates those exactly once, so every new `SnakeGame()` instance reuses the same `start_color` and `end_color`. The gradient never varies from one game to the next.
2. **Random-RGB color picker with rejection sampling.** [src/led_matrix/game.py:28-36](../../../src/led_matrix/game.py#L28-L36) loops until each RGB channel differs from the others by ≥50, capped at 175/255. Works but is perceptually arbitrary and can spin many times on unlucky seeds.
3. **Full-screen redraw per frame.** `draw_snake` fills all 256 pixels to black and rewrites, even though typically only the head (one new cell) and tail (one dropped cell) change.

Additionally: `generate_food` recurses unboundedly and the constructor's `food_color` arg is dead code (overwritten on first food spawn).

## Goals

- Each new game picks fresh, vivid, distinct colors.
- Gradient is perceptually smooth (no mushy RGB midpoints).
- Food color always contrasts with the snake.
- `draw_snake` CPU cost drops from O(256) per frame to O(snake_length) per frame.
- `generate_food` is bounded and handles the "snake fills board" case.

## Non-goals

- Tests. The existing codebase has no test harness; adding one is out of scope.
- Extracting color helpers into `src/common/`. Keep them in `game.py`; move later if the PC version needs them.
- Changing gradient semantics (gradient still indexed along `self.snake`, head → tail).
- Rewriting `display.py` or `common.py`.

## Design

### 1. Correctness fixes

- Constructor accepts `start_color=None, end_color=None`; if `None`, colors are generated inside `__init__`. Each `SnakeGame()` now genuinely gets its own palette.
- Remove the `food_color` constructor parameter. It's overwritten by `generate_food` on first call, so the arg is dead code — delete it.
- Rewrite `generate_food`:
  ```python
  def generate_food(self):
      free = [(x, y)
              for x in range(GAME_SIZE)
              for y in range(GAME_SIZE)
              if (x, y) not in self.snake]
      if not free:
          self.game_over = True
          return self.snake[0]   # placeholder, game ends next tick
      self.food_color = self._new_food_color()
      return random.choice(free)
  ```
  Bounded, non-recursive, handles a full board gracefully.

### 2. Color strategy (HSV, single hue per game)

Add a pure-Python `hsv_to_rgb(h, s, v) -> (int, int, int)` helper (~7 lines, MicroPython-compatible). `h ∈ [0, 1)`, `s, v ∈ [0, 1]`. Outputs 0-255 ints, clamped.

Per-game setup inside `__init__`:

```python
self.base_hue = random.random()                                 # 0..1
self.start_color = hsv_to_rgb(self.base_hue, 1.0, 0.15)        # dim tail
self.end_color   = hsv_to_rgb(self.base_hue, 1.0, 0.70)        # bright head
```

- `s = 1.0` ⇒ fully saturated, never grey.
- `v` ranges from 0.15 (tail) to 0.70 (head) ⇒ monochrome gradient that fades dim → bright along the body. The 0.70 ceiling preserves the existing NeoPixel power budget (today's 175/255 ≈ 0.69 cap is preserved in intent).
- Single-hue coherence looks cleaner than two random colors.

Food color:

```python
def _new_food_color(self):
    h = (self.base_hue + 0.5 + random.uniform(-0.05, 0.05)) % 1.0
    return hsv_to_rgb(h, 1.0, 0.70)
```

- Complementary hue (180° offset) ⇒ always high contrast with the snake.
- Small ±0.05 jitter gives a little variation food-to-food.

### 3. Incremental draw loop

Track the previous frame's snake cells:

```python
self._prev_snake_cells = set()   # initialized in __init__
```

`draw_snake` becomes:

```python
def draw_snake(self):
    cur = set(self.snake)

    snake_length = len(self.snake)
    if snake_length != self.previous_snake_length:
        self.gradient_colors = [
            get_gradient_color(i, snake_length, self.start_color, self.end_color)
            for i in range(snake_length)
        ]
        self.previous_snake_length = snake_length

    # Clear cells that were snake last frame but aren't now (usually just the old tail).
    for (x, y) in self._prev_snake_cells - cur:
        NP[xy_to_index(x, y)] = BLACK

    # Repaint all current snake cells (gradient colors shift each move, so every cell is rewritten).
    for i, (x, y) in enumerate(self.snake):
        NP[xy_to_index(x, y)] = self.gradient_colors[i]

    # Food pixel.
    fx, fy = self.food
    NP[xy_to_index(fx, fy)] = self.food_color

    NP.write()
    self._prev_snake_cells = cur
    sleep(1 / self.speed)
```

**What this drops:** the `NP.fill(BLACK)` on 256 pixels every frame.
**What stays:** a single `NP.write()` per frame (no flicker).
**SPI traffic:** unchanged (the strip still clocks out 256 × 3 bytes per write).
**CPU win:** interpreter iterations per frame drop from ~256 + `snake_length` to `snake_length` + (at most 1 cleared cell) + 1 food. On a 16×16 matrix with snake length ~5-30, that's a ~10× reduction in Python-level pixel assignments per frame.

### 4. Files touched

- `src/led_matrix/game.py` — all changes above.

No changes needed to `display.py`, `boot.py`, `main.py`, or `common.py`.

## Risks & mitigations

- **`_prev_snake_cells` could desync.** Mitigated: it's assigned from `self.snake` at the end of every `draw_snake` call. New games construct a fresh `SnakeGame` so `_prev_snake_cells` starts empty. No failure mode identified.
- **HSV conversion output format mismatch.** Mitigation: `hsv_to_rgb` returns `(int, int, int)` with each channel in `0..255` to match what `neopixel.NeoPixel.__setitem__` expects.
- **Food placed onto snake during game-over.** When `generate_food` returns a placeholder because the board is full, `draw_snake` will happen to write the food pixel over the head on top of the gradient color. Visual glitch is one frame at most; `game_over` has already been set, and `end_game` fires next. Acceptable.

## Alternatives considered

- **Hue-pair gradient** (rainbow-through-body): pick `h0 = random`, `h1 = h0 + random(30°, 120°)`, interpolate hue linearly (shortest path). More colorful but busier. Noted as a 2-line swap if preferred.
- **Curated palette pool** (fire, ocean, forest, rainbow): recognizable themes but needs a hand-tuned list and is more code. Rejected for YAGNI.
- **Event-driven draw** (only redraw head + tail): would require pinning colors to grid cells rather than snake-list positions, which changes the gradient's visual semantics. Rejected — design goal is to preserve current look-and-feel while fixing correctness and CPU cost.
