# Snake project restructure: shared engine + platform adapters

**Date:** 2026-04-29
**Scope:** Whole repository. Renames `src/ai/` → `src/desktop/` and `src/led_matrix/` → `src/embedded/`, extracts the duplicated Snake game logic into a shared `common/` package, introduces a `Policy` interface, makes the existing greedy AI a selectable policy on the embedded build, and stubs a future learned policy. Folds in a small set of latent bug fixes that intersect the refactor naturally. Also modernises the dev environment: replaces `requirements.txt` with a `uv`-managed `pyproject.toml` and adds `ruff` (lint + format), `mypy` (typing), and `pre-commit` config.

## Background

Today the repo has two near-duplicate `SnakeGame` implementations:

- [src/ai/snake_game.py](../../../src/ai/snake_game.py) — pixel-space (`BLOCK_SIZE` math, `Point` namedtuple), pygame-aware constructor, RL-friendly `play_step(action)` returning `(reward, done, score)`.
- [src/led_matrix/game.py](../../../src/led_matrix/game.py) — cell-space (0..15, wrapping torus), drives a NeoPixel renderer, has a built-in greedy `ai_move()` and a gradient draw loop.

`Direction` and `hsv_to_rgb` already live in [src/common/common.py](../../../src/common/common.py); the shared-code pattern is established but minimal.

The current package names are misleading:

- `src/ai/` is the *desktop* build. Both builds have AI (DQN vs greedy); the real distinction is the runtime — CPython + pygame + PyTorch vs MicroPython + NeoPixel.
- `src/led_matrix/` describes hardware, not architecture.

There are also several latent bugs in `src/ai/`:

- [src/ai/game.py:103-136](../../../src/ai/game.py#L103-L136) defines `get_action` twice; the second definition silently shadows the first (the εₘᵢₙ-clamped epsilon schedule is dead code).
- [src/ai/game.py:145](../../../src/ai/game.py#L145) calls `SnakeGame(... led_matrix=led_matrix)` but [src/ai/snake_game.py:17](../../../src/ai/snake_game.py#L17) doesn't accept `led_matrix`. `play()` would raise `TypeError` if invoked.
- [src/ai/ui.py:31](../../../src/ai/ui.py#L31) reads `game.game_size` but [src/ai/snake_game.py:20](../../../src/ai/snake_game.py#L20) defines `grid_size`. `render_info` would raise `AttributeError`.
- [src/ai/snake_game.py:50](../../../src/ai/snake_game.py#L50) — `place_food` recurses unboundedly (same flaw the LED build's `generate_food` already fixed).
- [src/ai/model.py:11](../../../src/ai/model.py#L11) — `Linear_QNet` is instantiated as `Linear_QNet(11, 256, 3)` but the active `get_state` returns 6 features; the input dimension mismatch crashes the first forward pass.

The non-learning play path (`learning=False`) doesn't render and doesn't handle keyboard input meaningfully because `update_ui` is only called inside the per-step loop's outer `while True`, after the inner game-over loop has exited.

## Goals

- Each top-level package is named for what it *is* — a runtime adapter (`desktop/`, `embedded/`).
- A single `SnakeEngine` lives in `common/`. Both adapters drive it.
- A `Policy` interface lives in `common/`. The existing greedy AI is one implementation; a stubbed `LearnedPolicy` is another.
- The embedded build picks a policy via a constant in `main.py`. Default is `"greedy"` (matches today's behaviour).
- The latent PC-side bugs above are fixed inline.
- Both adapters use cell-space coordinates; pixel translation happens only in the desktop renderer.
- Dev environment: `uv` for dependency management, `ruff` for lint + format, `mypy` for type checking, `pre-commit` to wire them into the workflow, and a baseline `pytest` config so the first test costs nothing to add.

## Non-goals

- Training the learned policy. Only the interface seam + a stub. Loading actual weights, the PyTorch → emlearn export, model shrinking, and retraining are deferred to a follow-up project.
- Refactoring inside each platform beyond what the rename + extract requires (no separate input/AI/runtime split inside `desktop/`; the embedded build keeps its current file boundaries except where the engine extraction forces a change).
- Score-logging unification. PC continues to use CSV + sqlite; embedded continues to use `high_score.txt`.
- Unit tests. The repo has no test harness today; adding one is its own project. (The pytest config does land — it's just empty.)
- Reachability of `embedded/wlan.py` (still commented out) — leave as-is.
- CI/CD configuration. Pre-commit covers local hygiene; wiring GitHub Actions or similar is deferred.

## Design

### Target layout

```text
src/
  common/                    # MicroPython-safe shared code (no numpy/torch/pygame/typing)
    __init__.py
    direction.py             # Direction enum (extracted from common.py)
    colors.py                # hsv_to_rgb + gradient interpolation (extracted from common.py + LED game.py)
    engine.py                # NEW: SnakeEngine — cell-space wrapping torus, no rendering
    policy.py                # NEW: Policy interface
  desktop/                   # was: src/ai/
    __init__.py
    main.py                  # was: game.py — Agent + train/play loop, drives common.engine.SnakeEngine
    model.py                 # PyTorch Linear_QNet + QTrainer (input dim fixed; otherwise unchanged)
    renderer.py              # was: ui.py — pygame draw + info pane, only place that knows BLOCK_SIZE
    plot.py                  # was: helper.py — matplotlib live plot
  embedded/                  # was: src/led_matrix/
    __init__.py
    boot.py                  # unchanged
    main.py                  # runner + POLICY constant ("greedy" | "learned")
    game.py                  # thin adapter: holds engine + palette + score, drives renderer + policy
    display.py               # NeoPixel + glyphs (unchanged behaviour; xy_to_index argument names follow new convention)
    greedy_policy.py         # NEW: current ai_move logic conformed to Policy
    learned_policy.py        # NEW: stub. Raises NotImplementedError on instantiation today.
    wlan.py                  # unchanged (commented stubs)
docs/
  superpowers/specs/         # specs land here
  superpowers/plans/         # plans land here
README.md                    # updated layout, names, and deployment notes
pyproject.toml               # NEW — replaces requirements.txt; deps + tool config (ruff, mypy, pytest)
uv.lock                      # NEW — generated by `uv lock`; committed
.python-version              # NEW — pins Python (3.11)
.pre-commit-config.yaml      # NEW — runs ruff + mypy on commit
```

`requirements.txt` is removed. `pyproject.toml` is the single source of truth for runtime deps, dev deps, and tool config.

### Coordinate convention

The shared engine standardises on `(x, y)` = `(column, row)`. This is the standard graphics convention and matches pygame pixel space; the LED build's current `(row, column)` convention is the outlier.

Concretely:

- `Direction` deltas: `RIGHT (+x)`, `LEFT (-x)`, `DOWN (+y)`, `UP (-y)`.
- `engine.head` is `(col, row)` with both in `0..15`.
- The desktop renderer multiplies by `BLOCK_SIZE` to draw: `pygame.Rect(x*BLOCK_SIZE, y*BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE)`.
- The embedded renderer translates `(col, row)` → flat NeoPixel index. `display.xy_to_index(x, y)` keeps its name and signature, but its body is updated so that `x` is column and `y` is row (today the body assumes `x` is row). The serpentine wiring of the panel is unchanged.

The DQN's state vector reports head and food in cell coordinates (`0..15`), not pixels. The existing `model/model.pth` checkpoint is invalidated by this — accepted; the user will retrain.

### `common/direction.py`

```python
class Direction:
    RIGHT = 1
    LEFT = 2
    UP = 3
    DOWN = 4
```

Plain class with int constants — MicroPython-safe. Same values as today; no behavioural change.

### `common/colors.py`

```python
def hsv_to_rgb(h, s, v):
    """Convert HSV to (r, g, b) ints in 0..255. h wraps; s, v in [0, 1]."""
    # body unchanged from src/common/common.py

def gradient_color(index, length, start_color, end_color):
    """Linear interpolation between two RGB tuples. index ∈ [0, length)."""
    if length <= 1:
        return start_color
    factor = index / (length - 1)
    return tuple(int(s + factor * (e - s)) for s, e in zip(start_color, end_color))
```

`hsv_to_rgb` is moved as-is from [src/common/common.py:8-36](../../../src/common/common.py#L8-L36). `gradient_color` is extracted from [src/led_matrix/game.py:32-47](../../../src/led_matrix/game.py#L32-L47) with a minor fix: today's `factor = index / length` never reaches 1.0 (the brightest end_color is unreachable); `index / (length - 1)` does.

### `common/engine.py`

```python
from common.direction import Direction
from random import choice

_DELTAS = {
    Direction.RIGHT: (1, 0),
    Direction.LEFT:  (-1, 0),
    Direction.DOWN:  (0, 1),
    Direction.UP:    (0, -1),
}

class SnakeEngine:
    """Headless snake on a wrapping torus. Cell-space (x=col, y=row), 0..size-1.
    Pure Python, MicroPython-safe (no numpy, typing, dataclasses, enum)."""

    def __init__(self, size=16, start=None):
        self.size = size
        self.snake = [start if start is not None else (size // 2, size // 2)]
        self.direction = Direction.RIGHT
        self.score = 0
        self.frame = 0
        self.game_over = False
        self.food = None
        self._place_food()

    @property
    def head(self):
        return self.snake[0]

    def set_direction(self, direction):
        """Set heading. Rejects 180° reversals (no-op if direction is the opposite of current)."""
        opposites = {
            Direction.UP: Direction.DOWN,
            Direction.DOWN: Direction.UP,
            Direction.LEFT: Direction.RIGHT,
            Direction.RIGHT: Direction.LEFT,
        }
        if opposites.get(self.direction) == direction:
            return
        self.direction = direction

    def step(self, direction=None):
        """Advance one tick. Returns (game_over, reward, score).

        reward is +10 on food, -10 on game-over, 0 otherwise. Callers that don't
        need reward (the embedded build) can ignore it."""
        if self.game_over:
            return True, 0, self.score
        if direction is not None:
            self.set_direction(direction)
        self.frame += 1

        x, y = self.head
        dx, dy = _DELTAS[self.direction]
        new_head = ((x + dx) % self.size, (y + dy) % self.size)

        if new_head in self.snake:
            self.game_over = True
            return True, -10, self.score

        self.snake.insert(0, new_head)
        if new_head == self.food:
            self.score += 1
            self._place_food()
            return self.game_over, 10, self.score

        self.snake.pop()
        return False, 0, self.score

    def _place_food(self):
        free = [(x, y) for x in range(self.size) for y in range(self.size)
                if (x, y) not in self.snake]
        if not free:
            self.game_over = True
            self.food = self.head
            return
        self.food = choice(free)
```

Notes:

- `step()` returns `(game_over, reward, score)`. The desktop Agent uses all three; the embedded loop uses just `game_over` and `score`.
- `_place_food` is bounded (no recursion). On a full board it sets `game_over` and assigns a placeholder.
- The RL "stuck-game" timeout (`frame > 100 * len(snake)`) is **not** in the engine — it's an RL training concern. The desktop Agent enforces it externally by reading `engine.frame`.
- The engine has no concept of wall collision. The board wraps, and self-collision is the only failure mode. Same as today on both platforms.

### `common/policy.py`

```python
class Policy:
    """Picks the next direction given the current engine state.

    Implementations:
      - embedded.greedy_policy.GreedyPolicy
      - embedded.learned_policy.LearnedPolicy (stub today; emlearn-backed later)
      - desktop.main.Agent (the DQN; conforms but isn't swapped at runtime)
    """

    def decide(self, engine):
        """Return a Direction.* value, or None to keep the current heading."""
        raise NotImplementedError
```

Tiny by design — it's a seam, not a framework. Returning `None` lets a policy decline to set a direction; the engine will continue in its current heading.

The greedy LED policy and the desktop DQN are conceptually different shapes (greedy peeks at engine state directly; DQN takes a feature vector + outputs an action index that maps back to a direction), but both can be wrapped behind `decide(engine) -> Direction`.

### `desktop/main.py` (was `src/ai/game.py`)

Changes:

- `from common.engine import SnakeEngine`; the local `SnakeGame` import is gone.
- `play()` instantiates `SnakeEngine(size=16)` instead of `SnakeGame(...)`.
- The `Agent.get_state(engine)` reads `engine.head`, `engine.food`, `engine.direction`, `len(engine.snake)` — the same six features as today, just from cell coords. Numerical magnitudes shrink ~20×.
- The two `get_action` definitions collapse to one — keeping the original `epsilon = 80 - self.n_games` schedule (the active one today). The clamped-epsilon variant is removed; if it's wanted later it lives behind a flag.
- The training-stall guard moves out of the engine and into the agent loop: `if engine.frame > 100 * len(engine.snake): done = True; reward = -10`.
- The `led_matrix=` kwarg threaded through `play()` is removed (it was dead and broken).
- The non-learning branch's UI updates are moved inside its inner loop so the player can actually see the game.

### `desktop/model.py` (was `src/ai/model.py`)

- `Linear_QNet(11, 256, 3)` → `Linear_QNet(6, 256, 3)`. Input dim now matches the active state vector. Otherwise unchanged.

### `desktop/renderer.py` (was `src/ai/ui.py`)

- `update_ui(game, engine)` and `render_info(game, engine, record_score, num_games)` take the engine explicitly. `game` retains pygame display + font + clock.
- All cell→pixel conversion happens here (`x * BLOCK_SIZE`, etc.).
- The `game.game_size` reference is replaced with `game.grid_size_px` — a new attribute on the desktop adapter equal to `GRID_SIZE * BLOCK_SIZE` (today's `grid_size`, renamed for clarity that it's a pixel dimension). `render_info` blits the info pane below the play area at `y = grid_size_px`.

### `embedded/game.py`

Shrinks from ~220 lines to ~50. Responsibilities now:

- Hold `engine = SnakeEngine(size=16)`.
- Hold the per-game palette (`base_hue`, `start_color`, `end_color`).
- Hold the policy instance, chosen by `main.py`.
- Loop: `policy.decide(engine)` → `engine.step(direction)` → `renderer.draw(engine, palette)` → sleep.
- On `engine.game_over`: read/write `high_score.txt`, call `display.display_scores(high, current)`, sleep 5s.

The methods `move_snake`, `change_direction`, `ai_move`, `generate_food` are gone (moved to engine + greedy_policy). `draw_snake` stays in `display.py` (it already owns the NeoPixel object); its signature becomes `draw_snake(engine, palette)`. The previous-frame snake cells (`_prev_snake_cells`) and the cached `gradient_colors` move into `display.py` as module-level state, since rendering is the only thing that cares about them.

### `embedded/greedy_policy.py`

```python
from common.policy import Policy
from common.direction import Direction

_DELTAS = {
    Direction.UP:    (0, -1),
    Direction.DOWN:  (0, 1),
    Direction.LEFT:  (-1, 0),
    Direction.RIGHT: (1, 0),
}

class GreedyPolicy(Policy):
    """Wrapped-distance greedy AI. Picks the legal neighbour cell that minimises
    Manhattan distance to the food, with axis-wise wrapping.

    Behaviour matches the current src/led_matrix/game.py ai_move() exactly."""

    def decide(self, engine):
        head_x, head_y = engine.head
        food_x, food_y = engine.food
        size = engine.size
        snake = engine.snake

        def wrapped(a, b):
            d = abs(a - b)
            return min(d, size - d)

        candidates = []
        for d, (dx, dy) in _DELTAS.items():
            nx, ny = (head_x + dx) % size, (head_y + dy) % size
            if (nx, ny) in snake:
                continue
            dist = wrapped(nx, food_x) + wrapped(ny, food_y)
            candidates.append((dist, d))

        if not candidates:
            return None  # all neighbours blocked; engine will run into itself next step
        candidates.sort(key=lambda t: t[0])
        return candidates[0][1]
```

Behaviourally identical to today's `ai_move`, but separated from the engine and conformed to `Policy.decide(engine) -> Direction`. The `(0, -1)` etc. deltas use the new `(x=col, y=row)` convention.

### `embedded/learned_policy.py` (stub)

```python
from common.policy import Policy

WEIGHTS_PATH = 'model_weights.bin'  # placeholder; format TBD when training is wired up

class LearnedPolicy(Policy):
    """Stub for an emlearn-backed inference policy.

    When implemented (Bridge A: PyTorch DQN → sklearn MLPRegressor → emlearn export),
    this will load WEIGHTS_PATH on construction and run inference each tick.

    Today it raises so a misconfigured POLICY constant fails loudly at startup
    rather than silently falling back."""

    def __init__(self):
        raise NotImplementedError(
            "LearnedPolicy is not implemented yet. "
            "Set POLICY = 'greedy' in embedded/main.py."
        )

    def decide(self, engine):
        raise NotImplementedError
```

Failing loudly is intentional: a typo'd `POLICY = "lerned"` should crash at boot, not silently degrade.

### `embedded/main.py`

```python
from game import SnakeGame
# from wlan import start_wlan

POLICY = "greedy"   # "greedy" | "learned"


def run_game():
    # start_wlan()
    while True:
        game = SnakeGame(policy_name=POLICY)
        game.start_game()
        while not game.engine.game_over:
            game.tick()
        game.end_game()


try:
    run_game()
except KeyboardInterrupt:
    pass
```

`SnakeGame.__init__` reads `policy_name`, instantiates the corresponding policy class, and stores it. An unknown name raises `ValueError` immediately.

### `common/` deployment to the ESP32

`common/` becomes a multi-file package. MicroPython supports packages with `__init__.py` natively, so the deployment step is:

```bash
mpremote cp -r src/common/ :/common
mpremote cp src/embedded/*.py :/
```

`src/embedded/*.py` lands flat at the device root (matching today's deployment); `common/` lands as a package directory. Imports like `from common.engine import SnakeEngine` resolve correctly on both CPython (via `PYTHONPATH=src`) and MicroPython (via the on-device package).

The README will document this.

## Tooling

The dev environment moves to a modern uv-based stack. None of this constrains the embedded build — MicroPython doesn't see any of it; lint and type checks run against `src/common/` and `src/desktop/` (with `src/embedded/` covered by ruff but skipped by mypy due to flat-import deployment, see below).

### Dependency management — `uv`

`requirements.txt` is replaced by a PEP 621 `pyproject.toml`. Lockfile is `uv.lock` (committed). Python is pinned via `.python-version`.

```toml
[project]
name = "snake-game"
version = "0.1.0"
description = "Snake with a DQN agent (desktop) and a NeoPixel build (ESP32)."
requires-python = ">=3.11,<3.13"
dependencies = [
    "torch",
    "pygame",
    "matplotlib",
    "numpy",
    "pandas",
    "plotly>=6.0.0rc0",
    "ipykernel",
    "nbformat",
]

[dependency-groups]
dev = [
    "ruff>=0.7.0",
    "mypy>=1.13",
    "pytest>=8.0",
    "pre-commit>=4.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/common", "src/desktop"]
# src/embedded/ is intentionally excluded — it ships to the ESP32 via
# mpremote, not pip, and its flat imports don't cope with package layout.
```

`uv sync` installs the project in editable mode, so `from common.engine import SnakeEngine` resolves both at the REPL and under `python -m desktop.main`.

Common workflows:

```bash
uv sync                           # install runtime + dev deps into .venv/
uv run python -m desktop.main     # run the desktop game
uv run pytest                     # run tests (when they exist)
uv run ruff check src/            # lint
uv run ruff format src/           # format
uv run mypy                       # type check (uses pyproject.toml config)
uv lock --upgrade                 # refresh the lockfile
```

The `embedded/` build is *not* installed via uv — the deployment path stays `mpremote cp ... :/`. uv just manages the host-side dev tooling and the desktop runtime.

### Lint + format — `ruff`

Single tool replaces black + isort + flake8. Config in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 120
target-version = "py311"
extend-exclude = [".mypy_cache", "model", "db", "notebooks"]

[tool.ruff.lint]
select = [
    "E4", "E7", "E9",       # pycodestyle (syntax-ish)
    "F",                     # pyflakes (undefined names, unused imports)
    "I",                     # isort
    "N801", "N802", "N803",  # naming
    "PLE", "PLW",            # pylint errors + warnings
    "UP",                    # pyupgrade
]
ignore = [
    "PLR2004",  # magic-value-comparison — too noisy in game code
]
```

Rule selection mirrors the conventions used in the wider organisation's repos (line-length 120, similar lint set), trimmed for this project's scale.

### Type checking — `mypy`

```toml
[tool.mypy]
python_version = "3.11"
files = ["src/common", "src/desktop"]
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false   # incremental — turn on later
disable_error_code = ["import-untyped"]

# MicroPython-only modules — no stubs on CPython.
[[tool.mypy.overrides]]
module = ["neopixel", "machine", "webrepl", "network"]
ignore_missing_imports = true
```

`src/embedded/` is **excluded** from mypy by being absent from `files`. The reason is structural, not philosophical: the embedded code uses flat imports (`from game import SnakeGame`) that resolve on the ESP32 device root but not under CPython without `mypy_path` tweaks. Bringing it under strict typing is deferred — ruff still lints it.

### Pre-commit hooks

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-format
        name: ruff format
        entry: uv run ruff format
        language: system
        types: [python]
      - id: ruff-lint
        name: ruff lint
        entry: uv run ruff check --fix
        language: system
        types: [python]
      - id: mypy
        name: mypy
        entry: uv run mypy
        language: system
        types: [python]
        pass_filenames: false
        files: ^src/(common|desktop)/
```

Install once with `pre-commit install`. README documents this.

### pytest config

No tests today, but the config is cheap to have ready:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
junit_family = "xunit2"
```

The first test for `common/engine.py` then costs nothing to wire up.

## Bug fixes folded in

These are cheap and intersect the refactor naturally:

1. `Linear_QNet(11, 256, 3)` → `Linear_QNet(6, 256, 3)` to match the active 6-feature state vector. (`desktop/model.py`)
2. Remove the second `get_action` definition; keep the original. (`desktop/main.py`)
3. Remove the dead `led_matrix=` kwarg from `play()`. (`desktop/main.py`)
4. Use `grid_size_px` (or equivalent) consistently in `renderer.py`; fix the `game.game_size` reference. (`desktop/renderer.py`)
5. Replace recursive `place_food` with the bounded list-comprehension from the engine. (folded into `common/engine.py`'s `_place_food`; the desktop adapter no longer has its own)
6. The non-learning play branch in `play()` now updates the UI inside the inner loop so the human can see the game. (`desktop/main.py`)

## Risks & mitigations

- **Cell-space switch invalidates the trained DQN.** Accepted — the user will retrain. Mitigated for future invalidations: the README will note that changes to the state vector require retraining.
- **MicroPython package import on ESP32.** MicroPython supports packages, but specific board firmware sometimes ships with frozen modules at the device root. Mitigation: keep `common/` paths short and avoid name collisions with frozen modules. `direction`, `colors`, `engine`, `policy` are all unique enough.
- **`embedded/main.py`'s top-level imports are flat (`from game import ...`)** because the embedded files land at device root. This must stay flat — using `from embedded.game import ...` would not work on the device. Mitigated by the deployment layout described above.
- **Coordinate convention flip in the LED renderer.** Today `xy_to_index(x, y)` treats `x` as row. After the flip, `x` is column. The serpentine wiring depends on which row's pixels are reversed; we update the body accordingly. Mitigated: a one-line change with a clear test (run a game, verify the snake moves right when `direction = RIGHT`).
- **Learned-policy stub crashing at boot if accidentally selected.** Intentional — surfaces config errors immediately rather than masking them.

## Alternatives considered

- **Rename only (no engine extraction).** Cheaper, but doesn't address the duplicated game logic, which is the bigger maintenance issue.
- **Keep pixel coordinates in the engine.** Would let the desktop renderer stay unchanged but pollutes the engine with rendering concerns and forces the embedded build to multiply/divide unnecessarily. Rejected.
- **Boot-time GPIO toggle for policy selection** (Q4 option C). Cute but speculative — no input pins are wired today. Rejected.
- **Config-file policy selection** (Q4 option B). Avoids redeploys but adds runtime parsing for marginal benefit. Rejected for KISS.
- **`enum.Enum` for `Direction`.** Not available in MicroPython without extra modules. Plain class with int constants is the established pattern.

## Future work (deferred)

- **Bridge A**: PyTorch DQN → sklearn `MLPRegressor` (weight copy) → emlearn export → `embedded/learned_policy.py` actually loads + runs inference.
- **Model shrinking** before shipping (256 hidden → 16 or 32) to fit comfortably in ESP32 RAM and run fast in pure Python or via emlearn.
- **Testing harness** for `common/engine.py`. The engine has no I/O dependencies and is the natural place to start adding tests.
- **Score-logging unification** if/when the embedded build wants persistent run history.
- **`embedded/wlan.py`** — uncomment + wire if WebREPL is wanted.
