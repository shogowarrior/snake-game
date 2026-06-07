# Famicom controller + manual mode — design

## Goal

Let a Famicom/NES-style controller (4021 shift-register clone, `WM3012-V4`) drive
the embedded snake on the ESP32: a player steers the snake by hand, toggles
between the AI and manual control, resets, and tunes speed live.

## Hardware constraint

The 4021 protocol clocks out exactly **8 bits per read**:
`A, B, SELECT, START, UP, DOWN, LEFT, RIGHT`. The clone has 4 round buttons, but
turbo variants alias the extra two to A/B, so only **two distinct action buttons**
(A, B) are assumed. The wire colours / bit order vary per clone, so the bit→button
map is configurable and a probe tool reports the real mapping on-device.

## Button map

| Button        | Action                                        |
|---------------|-----------------------------------------------|
| D-pad U/D/L/R | Set snake direction (manual mode only)        |
| SELECT        | Toggle auto ⇄ manual (edge-triggered)         |
| START         | Reset game immediately (edge-triggered)       |
| A             | Speed up (+`SPEED_STEP`, clamped to `SPEED_MAX`) |
| B             | Speed down (−`SPEED_STEP`, clamped to `SPEED_MIN`) |
| D-pad (held)  | Hold-to-rush: ×`RUSH_MULTIPLIER` tick rate while a direction is held (manual only, momentary) |

`auto` mode = existing greedy/learned AI. `manual` = D-pad drives the engine.
SELECT/START/A/B work in **both** modes. Dropped from the original ask: "speed
toward food" (covered by toggling to auto) and "change gradient color" (already
re-rolls each new game) — no free buttons remain.

## Components

### `src/embedded/controller.py` (MicroPython-safe)

`Controller` owns the three Pins. DATA uses `Pin.IN, Pin.PULL_UP` so an idle or
unconnected line reads "released" — no spurious presses on controller-less
devices in auto mode.

- `read_bits()` → list of 8 ints (1 = pressed), active-low decoded. Raw, used by the probe.
- `poll()` → `(edges, held)` sets of button names. `edges` = newly pressed since
  last poll (SELECT/START/A/B); `held` = currently down (D-pad). Built on
  `_update(bits)`, which is the pure decode+edge seam the tests exercise.

### `src/embedded/probe.py` (device tool)

Loops, reads raw bits, prints each newly-pressed button to serial as
`bit <i> pressed -> <NAME>`. Run via mpremote to discover the real bit→button
map, then fix `CONTROLLER_BITS`.

### `src/embedded/config.py`

```python
AUTO_MODE = True             # True = AI, False = controller (toggle live with SELECT)
CONTROLLER_LATCH = 18
CONTROLLER_CLOCK = 5
CONTROLLER_DATA  = 19        # avoids NEOPIXEL_PIN (13)
CONTROLLER_BITS = {"A": 0, "B": 1, "SELECT": 2, "START": 3,
                   "UP": 4, "DOWN": 5, "LEFT": 6, "RIGHT": 7}
SPEED_STEP = 5
SPEED_MIN = 5
SPEED_MAX = 60
```

### `src/embedded/game.py`

- `ControlState` (`auto` flag + speed) — constructed once in `main.py` so mode and speed
  **persist across games**.
- `SnakeGame.__init__` gains `controller` and `state`. `tick()`: poll → apply
  SELECT (toggle), A/B (speed clamp) → if START, return `True` → choose direction
  (manual: D-pad from `held`; auto: policy) → step → render. D-pad maps to
  `Direction.*`; `engine.set_direction` already rejects 180° reversals.

### `src/embedded/main.py`

Constructs `Display`, `Controller`, `ControlState` once. Loop: a `tick()` that
returns `True` (START) breaks and restarts **without** `end_game()` — immediate
reset, no score screen, no high-score save (not a death).

### `src/sim/fake_controller.py` + `src/sim/main.py`

Fake `Controller` reading pygame keys (arrows = D-pad, Enter = START,
RShift = SELECT, Z = A, X = B), injected via `sys.modules["controller"]` like the
existing `fake_machine`/`fake_neopixel`. Lets manual mode be tested on a laptop.

## Tests

- `tests/test_controller.py` — `_update` decode + edge detection with scripted bits.
- `tests/test_manual_control.py` — stub controller into `SnakeGame`: manual D-pad
  steers, SELECT toggles, A/B clamp at bounds, START signals reset.

## Out of scope

Two-controller support, turbo/auto-fire, in-game menus, persisting mode/speed to flash.
