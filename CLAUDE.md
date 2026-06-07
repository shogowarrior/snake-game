# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common commands

```bash
uv sync                            # install deps (Python 3.11 pinned)
uv run python -m desktop.main      # train the DQN (headless by default)
uv run python src/sim/main.py      # run the embedded build on a pygame LED-matrix sim
uv run ruff check src/             # lint (also covers src/embedded)
uv run ruff format src/            # format
uv run mypy                        # type check — only src/common + src/desktop
uv run pytest                      # run all tests
uv run pytest tests/test_x.py::test_y -v   # run a single test
uv run pre-commit install          # one-time: ruff-format, ruff-lint, mypy on commit
```

To play the desktop build with the keyboard, edit the `__main__` block in [src/desktop/main.py](src/desktop/main.py) and set `learning = False, py_ui = True`.

To flash the embedded build to an ESP32, use the `flash-snake` skill (`.claude/skills/flash-snake/`) — it wraps `mpremote` with this repo's flat-deploy layout. Default port is `/dev/ttyUSB0`.

## Architecture

Three runtime targets share one engine. The split is enforced by import style and dependencies, not by build config — so changes that look local can break a sibling target.

```
src/common/    pure-Python, MicroPython-safe — engine, Direction, Policy, color helpers
src/desktop/   CPython + pygame + PyTorch DQN
src/embedded/  MicroPython on ESP32, NeoPixel — flat imports (no `embedded.` prefix)
src/sim/       runs embedded/ on CPython by shimming sys.modules + sys.path
```

### MicroPython-safety rules for `src/common/` and `src/embedded/`

These files run under MicroPython on the ESP32. They must avoid:

- `from typing import ...`, type hints, `dataclasses`, `enum`
- `numpy`, `pandas`, anything not in MicroPython stdlib
- f-strings work, but keep allocations cheap

`Direction` is a plain class with int constants ([src/common/direction.py](src/common/direction.py)) — not an `enum`, deliberately.

### Import conventions (target-specific)

The same module is reached via different paths from each target:

- **Desktop** uses package imports: `from common.engine import SnakeEngine`. Wheels are built from `src/common` + `src/desktop` (see [pyproject.toml](pyproject.toml) `[tool.hatch.build.targets.wheel]`).
- **Embedded** uses flat imports: files deploy to the device root, so `embedded/game.py` does `from display import draw_snake` and `from common.engine import SnakeEngine`. There is **no** `from embedded.X import ...`.
- **Sim** prepends `src/embedded` to `sys.path` and pre-installs fake `machine`/`neopixel` into `sys.modules` so the flat imports resolve under CPython without modifying the embedded files.

This is why mypy is scoped to `src/common` and `src/desktop` only ([pyproject.toml](pyproject.toml) `[tool.mypy] files`) — the flat embedded imports don't resolve under CPython without the sim's sys-path tweak. Ruff still lints `src/embedded/`.

### The engine boundary

[src/common/engine.py](src/common/engine.py) is the single source of truth for game state: cell-space `(x=col, y=row)`, 16×16 wrapping torus, no UI/IO. Both renderers drive the same engine.

Two invariants that bite if violated:

1. **Tail-following is legal.** `engine.step` excludes `snake[:-1]` (not the full snake) when checking self-collision because the tail vacates this tick. The greedy policy mirrors this rule in [src/embedded/greedy_policy.py](src/embedded/greedy_policy.py) — keep them in sync.
2. **The stall guard lives in the agent loop, not the engine.** `desktop/main.py` ends an episode when `engine.frame > STALL_FACTOR * len(engine.snake)`. The engine itself never times out.

Reward is `+10` on food, `-10` on game-over, `0` otherwise. The embedded build ignores the reward.

### Embedded display: `Display` class

[src/embedded/display.py](src/embedded/display.py) exports a single `Display` class that owns the only NeoPixel handle, the framebuffer (`_fb`), the rotation LUT (`_lut`), and the render-loop caches. No module-level mutable state and no `global` keyword anywhere — [src/embedded/main.py](src/embedded/main.py) constructs `Display()` once per process and passes the same instance into every `SnakeGame(display=...)`. Four things to know before editing:

- Drawers write to the framebuffer in natural `(x, y)` coords via `self.set_pixel(x, y, color)`, then `self.flush()` pushes the result to the LEDs. `flush()` is the only place rotation + serpentine apply (via the precomputed `_lut`). Don't poke `self.np[]` directly from a drawer.
- Rotation knob lives in [src/embedded/config.py](src/embedded/config.py) as `ROTATION` in degrees clockwise (`0 | 90 | 180 | 270`). Snake, food, and score all rotate together because everything flows through the same `flush()`.
- The render-loop caches (`_prev_snake_cells`, `_gradient_colors`, `_previous_snake_length`) live on the Display instance. `SnakeGame.__init__` calls `self.display.reset_draw_caches()` between games.
- Glyph bitmaps live in [src/embedded/glyphs.py](src/embedded/glyphs.py) as one flat `GLYPHS` dict (digits, letters, punctuation merged). `display.Display.display_char` looks them up here — add new glyphs in glyphs.py, not in display.py.

The food cell blinks when `config.FOOD_BLINK = True`: `SnakeGame._food_render_color` fades it to black each `config.FOOD_BLINK_FRAMES` cycle and swaps to a new random color at the black instant, so the fade + color choice live in `game.py` and `display.py` just renders the palette color. Set `FOOD_BLINK = False` for a steady food pixel; lower `FOOD_BLINK_FRAMES` for a faster blink.

### Adding a policy

Implement `decide(self, engine) -> Direction | None` from [src/common/policy.py](src/common/policy.py), register it in `_POLICIES` in [src/embedded/game.py](src/embedded/game.py), and select it via the `POLICY` constant at the top of [src/embedded/main.py](src/embedded/main.py). The desktop DQN agent conforms to the interface but isn't swapped at runtime.

`LearnedPolicy` is a stub that raises `NotImplementedError` at construction — selecting `POLICY = "learned"` fails loudly at boot, by design.

### Controller and manual mode

A Famicom/NES clone (4021 shift register) can drive the snake. [src/embedded/controller.py](src/embedded/controller.py) exposes `Controller.poll() -> (edges, held)` — edge-triggered names for SELECT/START/A/B, held names for the D-pad. `main.py` constructs one `Controller` and one `ControlState` (`auto` flag + live speed) and reuses them across games so mode/speed persist past a death.

- Button map: D-pad steers (manual only), SELECT toggles auto⇄manual, START resets immediately (saves a high score but skips the score screen), A/B step speed within `[SPEED_MIN, SPEED_MAX]`. `SnakeGame.tick()` returns `True` on START so `main.py` restarts without `end_game()`.
- Hold-to-rush: holding a D-pad direction (manual mode) multiplies the tick rate by `RUSH_MULTIPLIER` for a momentary burst — `_palette()` scales the rendered speed while `_rushing`, leaving the persisted A/B speed untouched.
- `AUTO_MODE` (boolean: `True` = AI, `False` = controller) and all pins, the bit→button map (`CONTROLLER_BITS`), and speed bounds live in [src/embedded/config.py](src/embedded/config.py). Clone wiring varies — run [src/embedded/probe.py](src/embedded/probe.py) on-device (`mpremote`), press each button, and re-map `CONTROLLER_BITS` from the printed bit indices. DATA uses an internal pull-up so an unwired/idle line reads "released" — no spurious input in auto mode.
- The sim swaps in [src/sim/fake_controller.py](src/sim/fake_controller.py) via `sys.modules["controller"]` (like `fake_machine`/`fake_neopixel`), mapping keys to buttons: arrows = D-pad, Enter = START, Right-Shift = SELECT, Z = A, X = B. So `uv run python src/sim/main.py` tests manual mode on a laptop.

### Checkpoints and logs

- `model/model.pth` — best-model checkpoint, saved when score beats the running record.
- `scores.csv` and `db/tests.sqlite` — per-game training logs (CSV append + SQLite insert).
- `high_score.txt` lives **on the device**, not in the repo — written by `embedded/game.save_high_score`.

The 2026-04-29 cell-space refactor invalidated any pre-refactor `model.pth`. Retrain from scratch; resume-from-checkpoint isn't wired up.

## Specs and plans

Design docs and implementation plans live under [docs/superpowers/](docs/superpowers/). Recent work:

- `2026-04-29-snake-restructure-design.md` / `-snake-restructure.md` — the cell-space refactor and three-target split.
- `2026-04-16-snake-led-colors-design.md` / `-snake-led-colors.md` — gradient palette + complementary food hue.
