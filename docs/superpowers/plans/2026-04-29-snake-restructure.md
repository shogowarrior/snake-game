# Snake project restructure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename `src/ai/` → `src/desktop/` and `src/led_matrix/` → `src/embedded/`; extract the duplicated `SnakeGame` logic into a shared `common/` package with a `SnakeEngine` and a `Policy` interface; make the existing greedy AI a selectable policy on the embedded build with a stub for a future learned policy; fold in a small set of latent bug fixes; modernise the dev environment to `uv` + `ruff` + `mypy` + `pre-commit`.

**Architecture:** Each top-level package is a runtime adapter (`desktop/` for CPython + pygame + PyTorch DQN, `embedded/` for MicroPython + NeoPixel) over a shared, headless `SnakeEngine`. Both adapters use cell-space coordinates `(x=col, y=row)`; pixel translation happens only in the desktop renderer. Strict MicroPython compatibility for everything in `common/` (no `numpy`, `enum`, `dataclasses`, `typing`).

**Tech Stack:** Python 3.11+, `uv` for deps, `ruff` for lint+format, `mypy` for typing, `pygame` + `torch` (desktop), MicroPython + `neopixel` (embedded). `hatchling` build backend so `python -m desktop.main` resolves imports against an editable install.

**Reference spec:** [docs/superpowers/specs/2026-04-29-snake-restructure-design.md](../specs/2026-04-29-snake-restructure-design.md).

---

## File Structure

**New files:**
- `pyproject.toml`, `.python-version`, `.pre-commit-config.yaml`, `tests/` (placeholder)
- `src/common/__init__.py`, `src/common/direction.py`, `src/common/colors.py`, `src/common/engine.py`, `src/common/policy.py`
- `src/desktop/__init__.py`, `src/embedded/__init__.py`
- `src/embedded/greedy_policy.py`, `src/embedded/learned_policy.py`

**Renamed files (`git mv`):**
- `src/ai/` → `src/desktop/`
  - `src/ai/game.py` → `src/desktop/main.py`
  - `src/ai/model.py` → `src/desktop/model.py`
  - `src/ai/ui.py` → `src/desktop/renderer.py`
  - `src/ai/helper.py` → `src/desktop/plot.py`
- `src/led_matrix/` → `src/embedded/` (each file keeps its name)

**Heavily rewritten files:**
- `src/desktop/main.py`, `src/desktop/renderer.py` — adapt to `SnakeEngine`, fix bugs.
- `src/embedded/game.py` — shrink ~220 → ~50 lines; thin adapter.
- `src/embedded/display.py` — coord convention flip; absorb `draw_snake` plus its caches.

**Deleted files:**
- `src/ai/snake_game.py` (logic moves to `common/engine.py`)
- `src/common/common.py` (split into `common/direction.py` + `common/colors.py`)
- `requirements.txt` (replaced by `pyproject.toml`)

**Modified files:**
- `README.md` — new layout, names, deployment notes, uv usage.

---

## Task 1: Tooling foundation (pyproject + uv + .python-version)

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `src/common/__init__.py` (empty — needed for hatch build to resolve)
- Create: `tests/__init__.py` (empty — pytest's testpaths config references it)

- [ ] **Step 1: Create `.python-version`**

```text
3.11
```

- [ ] **Step 2: Create `src/common/__init__.py`**

Empty file. Required so hatch's `packages = ["src/common"]` resolves.

- [ ] **Step 3: Create `tests/__init__.py`**

Empty file.

- [ ] **Step 4: Create `pyproject.toml`**

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
packages = ["src/common"]
# src/desktop is added to this list in Task 7 (after the rename from src/ai/).
# src/embedded is intentionally never added — it ships to the ESP32 via mpremote.

[tool.ruff]
line-length = 120
target-version = "py311"
extend-exclude = [".mypy_cache", "model", "db", "notebooks"]

[tool.ruff.lint]
select = [
    "E4", "E7", "E9",
    "F",
    "I",
    "N801", "N802", "N803",
    "PLE", "PLW",
    "UP",
]
ignore = [
    "PLR2004",
]

[tool.mypy]
python_version = "3.11"
files = ["src/common"]
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false
disable_error_code = ["import-untyped"]

[[tool.mypy.overrides]]
module = ["neopixel", "machine", "webrepl", "network"]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
junit_family = "xunit2"
```

Note: `mypy.files` only lists `src/common` for now; Task 7 adds `src/desktop` after the rename.

- [ ] **Step 5: Run `uv sync`**

```bash
uv sync
```

Expected: a `.venv/` directory is created, `uv.lock` is created, deps install. May take 1–2 minutes for `torch`.

- [ ] **Step 6: Verify the editable install resolves**

```bash
uv run python -c "import common; print('OK')"
```

Expected output: `OK`.

- [ ] **Step 7: Sanity-check ruff and mypy run**

```bash
uv run ruff --version
uv run mypy --version
```

Expected: both print version numbers without errors.

`mypy` against the empty `src/common/` should pass with `Success: no issues found in 0 source files`.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock .python-version src/common/__init__.py tests/__init__.py
git commit -m "chore: introduce uv, ruff, mypy, pytest tooling via pyproject"
```

---

## Task 2: Extract `common/direction.py`

**Files:**
- Create: `src/common/direction.py`
- Modify: `src/common/common.py` (temporary — `Direction` will be removed in Task 6)

- [ ] **Step 1: Create `src/common/direction.py`**

```python
class Direction:
    RIGHT = 1
    LEFT = 2
    UP = 3
    DOWN = 4
```

Plain class with int constants — MicroPython-safe. Same values as today's `src/common/common.py:1-5`.

- [ ] **Step 2: Verify import works**

```bash
uv run python -c "from common.direction import Direction; print(Direction.RIGHT)"
```

Expected output: `1`.

- [ ] **Step 3: Verify lint and type check pass for the new file**

```bash
uv run ruff check src/common/direction.py
uv run mypy src/common/direction.py
```

Expected: both pass with no issues.

- [ ] **Step 4: Commit**

```bash
git add src/common/direction.py
git commit -m "refactor(common): extract Direction into its own module"
```

---

## Task 3: Extract `common/colors.py`

**Files:**
- Create: `src/common/colors.py`

- [ ] **Step 1: Create `src/common/colors.py`**

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


def gradient_color(index, length, start_color, end_color):
    """Linear interpolation between two RGB tuples.

    index in [0, length). For length == 1 returns start_color.
    """
    if length <= 1:
        return start_color
    factor = index / (length - 1)
    return tuple(int(s + factor * (e - s)) for s, e in zip(start_color, end_color))
```

`hsv_to_rgb` is moved as-is from `src/common/common.py:8-36`. `gradient_color` is the renamed/rewritten `get_gradient_color` from `src/led_matrix/game.py:32-47`, with a one-character fix: `factor = index / (length - 1)` so the brightest end-color is reachable at `index == length - 1` (today's `factor = index / length` never reaches 1.0).

- [ ] **Step 2: Verify import + behaviour**

```bash
uv run python -c "
from common.colors import hsv_to_rgb, gradient_color
print(hsv_to_rgb(0.0, 1.0, 1.0))                    # pure red
print(hsv_to_rgb(0.333, 1.0, 1.0))                  # green-ish
print(gradient_color(0, 5, (0, 0, 0), (255, 0, 0))) # start
print(gradient_color(4, 5, (0, 0, 0), (255, 0, 0))) # end (full red)
"
```

Expected output:
```
(255, 0, 0)
(0, 255, 5)
(0, 0, 0)
(255, 0, 0)
```

(The green-ish hue produces `(0, 255, 5)` due to rounding of `t = v * (1 - s * (1 - f))` at `f ≈ 0.998`.)

- [ ] **Step 3: Lint and type check**

```bash
uv run ruff check src/common/colors.py
uv run mypy src/common/colors.py
```

Expected: both pass.

- [ ] **Step 4: Commit**

```bash
git add src/common/colors.py
git commit -m "refactor(common): extract colors module with hsv_to_rgb and gradient_color"
```

---

## Task 4: Add `common/policy.py`

**Files:**
- Create: `src/common/policy.py`

- [ ] **Step 1: Create `src/common/policy.py`**

```python
class Policy:
    """Picks the next direction given the current engine state.

    Implementations:
      - embedded.greedy_policy.GreedyPolicy   — wrapped-distance greedy
      - embedded.learned_policy.LearnedPolicy — stub today; emlearn-backed later
      - desktop.main.Agent                    — DQN; conforms but isn't swapped at runtime
    """

    def decide(self, engine):
        """Return a Direction.* value, or None to keep the current heading."""
        raise NotImplementedError
```

Tiny by design — it's a seam, not a framework.

- [ ] **Step 2: Verify import**

```bash
uv run python -c "
from common.policy import Policy
p = Policy()
try:
    p.decide(None)
except NotImplementedError:
    print('OK')
"
```

Expected output: `OK`.

- [ ] **Step 3: Lint and type check**

```bash
uv run ruff check src/common/policy.py
uv run mypy src/common/policy.py
```

Expected: both pass.

- [ ] **Step 4: Commit**

```bash
git add src/common/policy.py
git commit -m "refactor(common): add Policy interface"
```

---

## Task 5: Add `common/engine.py`

**Files:**
- Create: `src/common/engine.py`

- [ ] **Step 1: Create `src/common/engine.py`**

```python
from random import choice

from common.direction import Direction

_DELTAS = {
    Direction.RIGHT: (1, 0),
    Direction.LEFT: (-1, 0),
    Direction.DOWN: (0, 1),
    Direction.UP: (0, -1),
}

_OPPOSITES = {
    Direction.UP: Direction.DOWN,
    Direction.DOWN: Direction.UP,
    Direction.LEFT: Direction.RIGHT,
    Direction.RIGHT: Direction.LEFT,
}


class SnakeEngine:
    """Headless snake on a wrapping torus. Cell-space (x=col, y=row), 0..size-1.

    Pure Python, MicroPython-safe (no numpy, typing, dataclasses, enum).
    Both renderers (pygame on desktop, NeoPixel on embedded) drive the same engine.
    """

    def __init__(self, size=16, start=None):
        self.size = size
        head = start if start is not None else (size // 2, size // 2)
        self.snake = [head]
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
        """Set heading. Rejects 180° reversals (no-op if direction opposes current)."""
        if _OPPOSITES.get(self.direction) == direction:
            return
        self.direction = direction

    def step(self, direction=None):
        """Advance one tick. Returns (game_over, reward, score).

        reward is +10 on food, -10 on game-over, 0 otherwise. Callers that don't
        need reward (the embedded build) can ignore it.
        """
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

- [ ] **Step 2: Smoke-test the engine**

```bash
uv run python -c "
from common.engine import SnakeEngine
from common.direction import Direction

e = SnakeEngine(size=16)
print('initial head:', e.head)
print('initial direction:', e.direction)
print('food cell present:', e.food is not None)
print('food not on snake:', e.food not in e.snake)

# Step right; head x increments by 1.
go, r, s = e.step()
print('after one step: head =', e.head, 'go =', go, 'reward =', r)

# 180-degree reversal blocked: facing RIGHT, ask LEFT.
e.set_direction(Direction.LEFT)
print('after blocked reversal: direction =', e.direction)
"
```

Expected output (food cell varies):
```
initial head: (8, 8)
initial direction: 1
food cell present: True
food not on snake: True
after one step: head = (9, 8) go = False reward = 0
after blocked reversal: direction = 1
```

- [ ] **Step 3: Smoke-test wrapping**

```bash
uv run python -c "
from common.engine import SnakeEngine
from common.direction import Direction

e = SnakeEngine(size=16)
# Hard-set head to right edge, direction RIGHT, then step.
e.snake = [(15, 0)]
e.direction = Direction.RIGHT
e.step()
print('wrapped head:', e.head)
"
```

Expected: `wrapped head: (0, 0)`.

- [ ] **Step 4: Lint and type check**

```bash
uv run ruff check src/common/engine.py
uv run mypy src/common/engine.py
```

Expected: both pass.

- [ ] **Step 5: Commit**

```bash
git add src/common/engine.py
git commit -m "refactor(common): add headless SnakeEngine"
```

---

## Task 6: Migrate existing imports off `common/common.py` and delete it

The old `src/common/common.py` is still imported by `src/ai/snake_game.py` and `src/led_matrix/game.py`. Update those imports to point at the new `common/direction.py` and `common/colors.py`, then delete the old file.

**Files:**
- Modify: `src/ai/snake_game.py:5`
- Modify: `src/led_matrix/game.py:1`
- Delete: `src/common/common.py`

- [ ] **Step 1: Update `src/ai/snake_game.py` imports**

Change line 5 from:

```python
from common import Direction
```

To:

```python
from common.direction import Direction
```

- [ ] **Step 2: Update `src/led_matrix/game.py` imports**

Change line 1 from:

```python
from common import Direction, hsv_to_rgb
```

To:

```python
from common.colors import hsv_to_rgb
from common.direction import Direction
```

- [ ] **Step 3: Verify nothing else imports from `common.common`**

```bash
grep -rn "from common import" src/ || echo "clean"
grep -rn "from common.common" src/ || echo "clean"
```

Expected: both print `clean`.

- [ ] **Step 4: Delete the old file**

```bash
rm src/common/common.py
```

- [ ] **Step 5: Verify imports still resolve**

```bash
uv run python -c "from common.direction import Direction; from common.colors import hsv_to_rgb; print('OK')"
```

Expected output: `OK`.

(`src/ai/` and `src/led_matrix/` still won't lint/type-check yet — they're rewritten in later tasks. Don't run ruff/mypy across all of `src/` here.)

- [ ] **Step 6: Commit**

```bash
git add -u src/
git commit -m "refactor(common): split common.py into direction.py and colors.py"
```

---

## Task 7: Rename `src/ai/` → `src/desktop/`

Pure rename + import-path updates. No engine swap yet (that's Task 9). Pyproject is updated to register the new package.

**Files:**
- Rename: `src/ai/` → `src/desktop/`
- Rename: `src/ai/game.py` → `src/desktop/main.py`
- Rename: `src/ai/ui.py` → `src/desktop/renderer.py`
- Rename: `src/ai/helper.py` → `src/desktop/plot.py`
- (Keep: `src/desktop/snake_game.py`, `src/desktop/model.py` — renamed but body unchanged. Body changes in Tasks 8 and 9.)
- Modify: `pyproject.toml` (add `src/desktop` to wheel + mypy)

- [ ] **Step 1: `git mv` the directory**

```bash
git mv src/ai src/desktop
```

- [ ] **Step 2: `git mv` per-file renames inside `src/desktop/`**

```bash
git mv src/desktop/game.py src/desktop/main.py
git mv src/desktop/ui.py src/desktop/renderer.py
git mv src/desktop/helper.py src/desktop/plot.py
```

- [ ] **Step 3: Create `src/desktop/__init__.py`**

Empty file. Required for the desktop package to install editable.

- [ ] **Step 4: Update internal imports in `src/desktop/main.py`**

The file currently has:

```python
from snake_game import SnakeGame, Direction, Point
from model import Linear_QNet, QTrainer
from helper import plot
from ui import update_ui, render_info
```

Change to:

```python
from common.direction import Direction

from desktop.model import Linear_QNet, QTrainer
from desktop.plot import plot
from desktop.renderer import render_info, update_ui
from desktop.snake_game import Point, SnakeGame
```

(Engine swap and `Point`/`SnakeGame` removal happen in Task 9. This step keeps the file runnable through the rename.)

- [ ] **Step 5: Update internal imports in `src/desktop/snake_game.py`**

Already updated in Task 6 (line 5: `from common.direction import Direction`). No change here — verify with:

```bash
grep -n "from common" src/desktop/snake_game.py
```

Expected: `5:from common.direction import Direction`.

- [ ] **Step 6: Update `pyproject.toml`**

In `[tool.hatch.build.targets.wheel]`, change:

```toml
packages = ["src/common"]
```

to:

```toml
packages = ["src/common", "src/desktop"]
```

In `[tool.mypy]`, change:

```toml
files = ["src/common"]
```

to:

```toml
files = ["src/common", "src/desktop"]
```

- [ ] **Step 7: Re-sync uv to pick up the new package layout**

```bash
uv sync
```

Expected: completes quickly (no new deps; just rebuilds the editable install).

- [ ] **Step 8: Verify the desktop package imports**

```bash
uv run python -c "from desktop import main; print('OK')"
```

Expected output: `OK`.

(There may be runtime warnings about the existing bugs in `main.py`; those get fixed in Task 9. The import itself should succeed since we only updated paths.)

- [ ] **Step 9: Commit**

```bash
git add -u src/ pyproject.toml
git add src/desktop/__init__.py
git commit -m "refactor: rename src/ai to src/desktop and register as a package"
```

---

## Task 8: Rewrite `src/desktop/renderer.py` for cell-space

Renderer rewrite lands first so the `main.py` rewrite in Task 9 can import its new `init_pygame` / `update_ui` / `render_info` signatures. Was `src/desktop/ui.py` (renamed in Task 7 — body still original). Now translates engine cell coordinates into pygame pixels. Fixes the `game.game_size` typo by introducing a small `PygameState` namedtuple.

**Files:**
- Rewrite: `src/desktop/renderer.py`

- [ ] **Step 1: Replace `src/desktop/renderer.py` with the new content**

```python
from collections import namedtuple

import pygame

WHITE = (255, 255, 255)
GREY = (127, 127, 127)
RED = (200, 0, 0)
BLUE1 = (0, 0, 255)
BLUE2 = (0, 100, 255)
BLACK = (0, 0, 0)

BLOCK_SIZE = 20
PANE_WIDTH = 30
SPEED = 30

PygameState = namedtuple("PygameState", "display font clock grid_size_px SPEED")


def init_pygame(grid_size):
    """Initialise pygame and return a PygameState. Call once at startup."""
    pygame.init()
    font = pygame.font.Font("arial.ttf", 16)
    grid_size_px = grid_size * BLOCK_SIZE
    display = pygame.display.set_mode((grid_size_px, grid_size_px + PANE_WIDTH))
    pygame.display.set_caption("Snake")
    clock = pygame.time.Clock()
    return PygameState(display=display, font=font, clock=clock, grid_size_px=grid_size_px, SPEED=SPEED)


def update_ui(state, engine):
    """Repaint the play area for one frame."""
    state.display.fill(BLACK)
    fx, fy = engine.food
    pygame.draw.rect(
        state.display, RED,
        pygame.Rect(fx * BLOCK_SIZE, fy * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE),
    )
    for (x, y) in engine.snake:
        pygame.draw.rect(
            state.display, BLUE1,
            pygame.Rect(x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE),
        )
        pygame.draw.rect(
            state.display, BLUE2,
            pygame.Rect(x * BLOCK_SIZE + 4, y * BLOCK_SIZE + 4, 12, 12),
        )


def render_info(state, engine, record_score, num_games):
    """Render the info pane below the play area."""
    pane_y_start = state.grid_size_px

    pygame.draw.rect(state.display, GREY, (0, pane_y_start, state.grid_size_px, PANE_WIDTH))

    games_surface = state.font.render(f"Games: {num_games}", True, WHITE)
    state.display.blit(games_surface, (10, pane_y_start + 5))

    score_surface = state.font.render(f"Score: {engine.score}", True, WHITE)
    state.display.blit(score_surface, (135, pane_y_start + 5))

    record_surface = state.font.render(f"Max: {record_score}", True, WHITE)
    state.display.blit(record_surface, (260, pane_y_start + 5))

    pygame.display.flip()
```

Changes vs. today's `src/desktop/renderer.py` (which is the renamed-but-not-yet-rewritten `ui.py`):
- New `init_pygame` constructor returns a `PygameState` named tuple. Replaces the implicit pygame init that used to happen inside `SnakeGame.__init__`.
- `update_ui(state, engine)` and `render_info(state, engine, record, num_games)` take `engine` explicitly. All cell→pixel multiplication happens here.
- `state.grid_size_px` replaces the old `game.game_size`/`game.grid_size` confusion.
- The food rectangle and snake rectangles are drawn from cell coordinates (`x * BLOCK_SIZE`, `y * BLOCK_SIZE`).

After this task, `desktop/main.py` is the OLD body (still importing `SnakeGame` from `desktop.snake_game`); it imports `update_ui` and `render_info` from the renderer, but their signatures have changed. We do **not** run `main.py` between this task and Task 9. Linting `main.py` is also deferred to Task 9 — its current body still has the original bugs and is about to be rewritten.

- [ ] **Step 2: Verify the renderer's exports import cleanly**

```bash
uv run python -c "from desktop.renderer import init_pygame, update_ui, render_info; print('OK')"
```

Expected output: `OK`.

- [ ] **Step 3: Lint and type check the renderer**

```bash
uv run ruff check src/desktop/renderer.py
uv run mypy src/desktop/renderer.py
```

Expected: both pass.

- [ ] **Step 4: Commit**

```bash
git add -u src/desktop/renderer.py
git commit -m "refactor(desktop): renderer uses cell-space and a small PygameState"
```

---

## Task 9: Rewrite `src/desktop/main.py` to use `SnakeEngine`

The biggest desktop change. Swaps `SnakeGame` for `SnakeEngine`, drops the duplicate `get_action`, drops the dead `led_matrix=` kwarg, externalises the training-stall guard, and fixes the non-learning UI loop. Deletes `src/desktop/snake_game.py`.

**Files:**
- Rewrite: `src/desktop/main.py`
- Delete: `src/desktop/snake_game.py`

- [ ] **Step 1: Replace `src/desktop/main.py` with the new content**

```python
import csv
import random
import sqlite3
from datetime import datetime

import numpy as np
import torch

from common.direction import Direction
from common.engine import SnakeEngine
from desktop.model import Linear_QNet, QTrainer
from desktop.plot import plot
from desktop.renderer import init_pygame, render_info, update_ui

BATCH_SIZE = 100
MAX_MEMORY = 100_000
LR = 0.001
WINDOW_SIZE = 25
GRID_SIZE = 16

# RL training-stall guard: end the episode if the agent hasn't eaten in
# 100 * len(snake) frames. Lives in the agent loop, not the engine.
STALL_FACTOR = 100


class Agent:
    def __init__(self):
        self.n_games = 0
        self.epsilon = 0
        self.gamma = 0.9
        self.memory = []
        self.model = Linear_QNet(6, 256, 3)
        self.trainer = QTrainer(self.model, lr=LR, gamma=self.gamma)

    def get_state(self, engine):
        head_x, head_y = engine.head
        food_x, food_y = engine.food
        state = [
            engine.direction,
            food_x,
            food_y,
            head_x,
            head_y,
            len(engine.snake),
        ]
        return np.array(state, dtype=int)

    def remember(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))

    def train_long_memory(self):
        if len(self.memory) > BATCH_SIZE:
            mini_sample = random.sample(self.memory, BATCH_SIZE)
        else:
            mini_sample = self.memory

        states, actions, rewards, next_states, dones = zip(*mini_sample)
        self.trainer.train_step(states, actions, rewards, next_states, dones)

    def train_short_memory(self, state, action, reward, next_state, done):
        self.trainer.train_step(state, action, reward, next_state, done)

    def get_action(self, state):
        # Exploration / exploitation: linear epsilon decay over the first ~80 games.
        self.epsilon = 80 - self.n_games
        final_move = [0, 0, 0]
        if random.randint(0, 200) < self.epsilon:
            move = random.randint(0, 2)
            final_move[move] = 1
        else:
            state0 = torch.tensor(state, dtype=torch.float)
            prediction = self.model(state0)
            move = torch.argmax(prediction).item()
            final_move[move] = 1
        return final_move


def _action_to_direction(action, current_direction):
    """Map a [straight, right, left] one-hot action to a Direction.

    Direction is rotated relative to the current heading along the clockwise
    cycle RIGHT -> DOWN -> LEFT -> UP -> RIGHT.
    """
    clock_wise = [Direction.RIGHT, Direction.DOWN, Direction.LEFT, Direction.UP]
    idx = clock_wise.index(current_direction)
    if np.array_equal(action, [1, 0, 0]):
        return clock_wise[idx]
    if np.array_equal(action, [0, 1, 0]):
        return clock_wise[(idx + 1) % 4]
    return clock_wise[(idx - 1) % 4]


def _read_keyboard(pygame_state, current_direction):
    """Drain the pygame event queue. Returns the new direction (or current)."""
    import pygame

    new_dir = current_direction
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            raise SystemExit(0)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                new_dir = Direction.LEFT
            elif event.key == pygame.K_RIGHT:
                new_dir = Direction.RIGHT
            elif event.key == pygame.K_UP:
                new_dir = Direction.UP
            elif event.key == pygame.K_DOWN:
                new_dir = Direction.DOWN
    return new_dir


def play(learning, py_ui):
    plot_scores = []
    plot_mean_scores = []
    moving_mean_scores = []
    total_score = 0
    record = 0
    agent = Agent()
    engine = SnakeEngine(size=GRID_SIZE)
    pygame_state = init_pygame(GRID_SIZE) if py_ui else None

    connection = sqlite3.connect("db/tests.sqlite")
    cursor = connection.cursor()

    while True:
        if not learning:
            # Human/keyboard mode: play a single game with UI updates each tick.
            engine = SnakeEngine(size=GRID_SIZE)
            while not engine.game_over:
                if py_ui:
                    new_dir = _read_keyboard(pygame_state, engine.direction)
                    engine.set_direction(new_dir)
                    engine.step()
                    update_ui(pygame_state, engine)
                    render_info(pygame_state, engine, record, agent.n_games)
                    pygame_state.clock.tick(pygame_state.SPEED)
                else:
                    engine.step()
            print("Final Score", engine.score)
            if py_ui:
                import pygame
                pygame.quit()
            return

        # Learning mode.
        state_old = agent.get_state(engine)
        final_move = agent.get_action(state_old)
        new_dir = _action_to_direction(final_move, engine.direction)
        done, reward, score = engine.step(new_dir)

        # Stall guard — externalised from the engine.
        if not done and engine.frame > STALL_FACTOR * len(engine.snake):
            done = True
            reward = -10
            engine.game_over = True

        state_new = agent.get_state(engine)
        agent.train_short_memory(state_old, final_move, reward, state_new, done)
        agent.remember(state_old, final_move, reward, state_new, done)

        if py_ui:
            update_ui(pygame_state, engine)
            render_info(pygame_state, engine, record, agent.n_games)

        if done:
            engine = SnakeEngine(size=GRID_SIZE)
            agent.n_games += 1
            agent.train_long_memory()

            if score > record:
                record = score
                agent.model.save()

            plot_scores.append(score)
            total_score += score
            mean_score = total_score / agent.n_games
            plot_mean_scores.append(mean_score)

            window_size = WINDOW_SIZE if agent.n_games > WINDOW_SIZE else agent.n_games
            moving_mean_score = sum(plot_scores[-window_size:])
            moving_mean_scores.append(moving_mean_score / window_size)

            plot(plot_scores, plot_mean_scores, moving_mean_scores)

            with open("scores.csv", mode="a") as file:
                file.write(f"{agent.n_games},{datetime.now()},{score},N/A\n")

            cursor.execute("INSERT INTO test_results (score, params) VALUES (?, ?)", (score, "N/A"))
            connection.commit()

    # Unreachable in learning mode; cursor closes on exit.
    connection.close()


if __name__ == "__main__":
    learning = True
    py_ui = False
    play(learning, py_ui)
```

Notes on what changed vs. today's `src/desktop/main.py`:
- Imports `SnakeEngine` and `Direction` from `common`; no `SnakeGame` / `Point` imports.
- `Agent.get_state(engine)` reads cell-space coordinates from the engine.
- The εₘᵢₙ-clamped `get_action` variant is removed. The original `epsilon = 80 - self.n_games` schedule is the only one.
- The `led_matrix=` kwarg is gone — never accepted by anything, was dead.
- Stall guard moved out of the engine; lives in the agent loop.
- Non-learning branch updates the UI every tick, not after the game ends.
- `update_ui` and `render_info` are called with `pygame_state` (a small struct returned by `init_pygame`) instead of `game`.

`init_pygame`, `update_ui`, and `render_info` are the renderer signatures landed in Task 8. This file references them; they already exist by the time this task runs.

- [ ] **Step 2: Delete `src/desktop/snake_game.py`**

```bash
rm src/desktop/snake_game.py
```

- [ ] **Step 3: Verify import resolves at module level**

```bash
uv run python -c "import desktop.main; print('OK')"
```

Expected output: `OK`. (Runtime not exercised here — that's Task 11.)

- [ ] **Step 4: Lint the file**

```bash
uv run ruff check src/desktop/main.py
```

Expected: passes.

- [ ] **Step 5: Commit**

```bash
git add src/desktop/main.py
git rm src/desktop/snake_game.py
git commit -m "refactor(desktop): drive SnakeEngine; drop SnakeGame, dead kwargs, dup get_action"
```

---

## Task 10: Fix `src/desktop/model.py` input dimension

`Linear_QNet` is instantiated with `input_size=11` but the active state vector is 6 features. The fix is at the call site (`Agent.__init__` in `desktop/main.py`), already covered by Task 9. This task is a verification step plus a sweep for any other call sites that need updating.

**Files:**
- Verify (and possibly modify) `src/desktop/model.py` — usually no body change needed.

- [ ] **Step 1: Confirm the parameter name is unchanged in the model file**

```bash
grep -n "input_size" src/desktop/model.py
```

Expected: line 8 shows `def __init__(self, input_size, hidden_size, output_size, dropout=0.2):`. The parameter name stays — it's just the *call site* that was wrong, and Task 9 already passes `(6, 256, 3)`.

- [ ] **Step 2: Confirm there are no other `Linear_QNet(` callers with the wrong dimension**

```bash
grep -rn "Linear_QNet(" src/
```

Expected: exactly one match — `src/desktop/main.py` calling `Linear_QNet(6, 256, 3)`.

If any other call site appears with the old `(11, 256, 3)` (or any other wrong dim), edit it to `(6, 256, 3)`.

- [ ] **Step 3: Lint and type check the model file**

```bash
uv run ruff check src/desktop/model.py
uv run mypy src/desktop/model.py
```

Expected: both pass. (Mypy may flag the bare `torch` calls if no stubs are installed — `import-untyped` is suppressed in pyproject, so these get ignored.)

- [ ] **Step 4: Commit (only if Step 2 changed something)**

If Step 2 found and you fixed any wrong call sites:

```bash
git add -u src/desktop/model.py
git commit -m "fix(desktop): align Linear_QNet input dim with the 6-feature state vector"
```

If no changes were needed (the fix lived entirely inside `desktop/main.py` from Task 9), skip this commit. This is an expected outcome.

---

## Task 11: Verify the desktop build runs end-to-end

Smoke-test the whole desktop stack: training mode (no UI) for ~2 seconds, then human mode with UI for a few seconds, then quit.

**Files:** None modified.

- [ ] **Step 1: Run training mode with no UI**

```bash
timeout 5 uv run python -m desktop.main || true
```

This invokes `if __name__ == "__main__"` with `learning=True, py_ui=False`. `timeout 5` kills it after 5s; the trailing `|| true` swallows the resulting non-zero exit.

Expected output: many `INSERT INTO test_results ...` succeed (tests.sqlite exists), live matplotlib plot popping up, no Python tracebacks.

If sqlite errors appear ("no such table: test_results"), create the table:

```bash
uv run python -c "
import sqlite3
con = sqlite3.connect('db/tests.sqlite')
con.execute('CREATE TABLE IF NOT EXISTS test_results (id INTEGER PRIMARY KEY, score INTEGER, params TEXT)')
con.commit()
con.close()
print('OK')
"
```

Then re-run the training smoke test.

- [ ] **Step 2: Run human-play mode with UI**

Edit `src/desktop/main.py` `if __name__ == "__main__":` block:

```python
if __name__ == "__main__":
    learning = False
    py_ui = True
    play(learning, py_ui)
```

Then:

```bash
uv run python -m desktop.main
```

Expected: a 320×350 pygame window opens. Snake (blue) starts at center. Arrow keys steer. Snake moves at a steady cadence. Score updates in the bottom pane. Closing the window exits cleanly.

Play one game, watch it die when the snake hits itself. After "Final Score N" prints, the program exits.

- [ ] **Step 3: Revert the `__main__` block**

Change `learning` back to `True` and `py_ui` back to `False` (the default training entry point).

```python
if __name__ == "__main__":
    learning = True
    py_ui = False
    play(learning, py_ui)
```

- [ ] **Step 4: Commit (only if `db/tests.sqlite` was newly initialised)**

If you had to create the `test_results` table, the file is binary-changed but git ignores `db/*.sqlite` (or doesn't — check `.gitignore`). If git shows it as modified:

```bash
git status
```

If `db/tests.sqlite` is dirty, leave it uncommitted (it's local state). If it appears in `git status`, add it to `.gitignore`:

```bash
echo "db/*.sqlite" >> .gitignore
git add .gitignore
git commit -m "chore: ignore local sqlite run logs"
```

If everything is clean, no commit is needed for this task.

---

## Task 12: Rename `src/led_matrix/` → `src/embedded/`

Pure rename. Files keep their names; embedded uses flat imports so the contents need no rewrites for the rename itself. Body changes happen in Tasks 13–17.

**Files:**
- Rename: `src/led_matrix/` → `src/embedded/`
- Create: `src/embedded/__init__.py` (empty)

- [ ] **Step 1: `git mv` the directory**

```bash
git mv src/led_matrix src/embedded
```

- [ ] **Step 2: Create `src/embedded/__init__.py`**

Empty file.

- [ ] **Step 3: Verify imports in embedded files still resolve at the file level (syntax-only)**

Embedded code uses flat imports (`from game import SnakeGame`) that only resolve on the ESP32 device root. We can't run them under CPython without sys-path tweaks. Verify ruff parses each file:

```bash
uv run ruff check src/embedded/
```

Expected: ruff parses the files. There may be pre-existing lint warnings (long lines, unused imports) — these get cleaned up in subsequent tasks where each file is rewritten. Don't fix them now.

- [ ] **Step 4: Commit**

```bash
git add src/embedded/__init__.py
git add -u src/
git commit -m "refactor: rename src/led_matrix to src/embedded"
```

---

## Task 13: Update `src/embedded/display.py` for new coord convention and absorb `draw_snake`

Two changes:

1. Flip `xy_to_index(x, y)` so `x` is column and `y` is row (today's body assumes the opposite). The serpentine wiring inversion stays — it just keys off `y` (row parity) instead of `x`.
2. Add `draw_snake(engine, palette)` and the supporting module-level caches (`_prev_snake_cells`, `_gradient_colors`, `_previous_snake_length`). Today these live on the embedded `SnakeGame` instance; with the engine extraction they belong with the renderer.

**Files:**
- Modify: `src/embedded/display.py`

- [ ] **Step 1: Update the `xy_to_index` body**

Locate the function (currently `src/embedded/display.py:76-80`):

```python
def xy_to_index(x, y):
    if x % 2 == 0:
        return x * 16 + y  # Even rows (left to right)
    else:
        return x * 16 + (15 - y)  # Odd rows (right to left)
```

Replace with:

```python
def xy_to_index(x, y):
    """(col, row) → flat NeoPixel index, accounting for the panel's
    serpentine wiring (every other row is laid out right-to-left)."""
    if y % 2 == 0:
        return y * 16 + x
    return y * 16 + (15 - x)
```

The serpentine wiring on this panel reverses **rows** (every other physical row), so the parity check is on `y` (row index). With `(x=col, y=row)`, the flat index is `row * 16 + col` for even rows and `row * 16 + (15 - col)` for odd rows.

- [ ] **Step 2: Append `draw_snake` and its module state to `src/embedded/display.py`**

Add at the bottom of the file:

```python
from time import sleep

from common.colors import gradient_color

# Render-loop caches. Module state, not class state — `display.py` owns the
# only NeoPixel object and is the only place that draws.
_prev_snake_cells = set()
_gradient_colors = []
_previous_snake_length = 0


def draw_snake(engine, palette):
    """Paint one frame: snake gradient + food cell. Sleeps for the engine tick.

    palette is (start_color, end_color, food_color, speed) — provided by the
    embedded SnakeGame each frame.
    """
    global _prev_snake_cells, _gradient_colors, _previous_snake_length

    start_color, end_color, food_color, speed = palette
    cur = set(engine.snake)

    snake_length = len(engine.snake)
    if snake_length != _previous_snake_length:
        _gradient_colors = [
            gradient_color(i, snake_length, start_color, end_color)
            for i in range(snake_length)
        ]
        _previous_snake_length = snake_length

    # Clear cells that were snake last frame but aren't now.
    for (x, y) in _prev_snake_cells - cur:
        NP[xy_to_index(x, y)] = BLACK

    # Repaint current snake cells.
    for i, (x, y) in enumerate(engine.snake):
        NP[xy_to_index(x, y)] = _gradient_colors[i]

    # Food pixel.
    fx, fy = engine.food
    NP[xy_to_index(fx, fy)] = food_color

    NP.write()
    _prev_snake_cells = cur
    sleep(1 / speed)


def reset_draw_caches():
    """Call between games so the new game's first frame redraws cleanly."""
    global _prev_snake_cells, _gradient_colors, _previous_snake_length
    _prev_snake_cells = set()
    _gradient_colors = []
    _previous_snake_length = 0
```

- [ ] **Step 3: Lint the file**

```bash
uv run ruff check src/embedded/display.py
```

Expected: passes. (Mypy is configured to skip `src/embedded/`.)

- [ ] **Step 4: Smoke-test the import path on CPython**

The flat `from common.colors import gradient_color` should resolve via the editable install. The module-level `NP = neopixel.NeoPixel(...)` will fail because `neopixel` and `machine` only exist on MicroPython, but that's fine — we just want to confirm the rest of the file is syntactically valid:

```bash
uv run python -c "
import ast, pathlib
src = pathlib.Path('src/embedded/display.py').read_text()
ast.parse(src)
print('OK')
"
```

Expected output: `OK`.

- [ ] **Step 5: Commit**

```bash
git add -u src/embedded/display.py
git commit -m "refactor(embedded): xy_to_index uses (col, row); display owns draw_snake caches"
```

---

## Task 14: Add `src/embedded/greedy_policy.py`

Extract the wrapped-distance greedy AI from the old `src/embedded/game.py:140-176` (`ai_move`) into its own module, conformed to the `Policy` interface.

**Files:**
- Create: `src/embedded/greedy_policy.py`

- [ ] **Step 1: Create `src/embedded/greedy_policy.py`**

```python
from common.direction import Direction
from common.policy import Policy

_DELTAS = {
    Direction.UP: (0, -1),
    Direction.DOWN: (0, 1),
    Direction.LEFT: (-1, 0),
    Direction.RIGHT: (1, 0),
}


class GreedyPolicy(Policy):
    """Wrapped-distance greedy AI. Picks the legal neighbour that minimises
    Manhattan distance to the food, with axis-wise wrapping.

    Behaviour matches the embedded `ai_move()` in the previous codebase exactly.
    """

    def decide(self, engine):
        head_x, head_y = engine.head
        food_x, food_y = engine.food
        size = engine.size
        snake = engine.snake

        def wrapped(a, b):
            d = abs(a - b)
            return min(d, size - d)

        candidates = []
        for direction, (dx, dy) in _DELTAS.items():
            nx, ny = (head_x + dx) % size, (head_y + dy) % size
            if (nx, ny) in snake:
                continue
            dist = wrapped(nx, food_x) + wrapped(ny, food_y)
            candidates.append((dist, direction))

        if not candidates:
            return None
        candidates.sort(key=lambda t: t[0])
        return candidates[0][1]
```

The deltas use the new `(x=col, y=row)` convention (`UP` decrements row, `RIGHT` increments column).

- [ ] **Step 2: Smoke-test the policy on CPython**

```bash
uv run python -c "
from common.engine import SnakeEngine
import sys
sys.path.insert(0, 'src/embedded')
from greedy_policy import GreedyPolicy

e = SnakeEngine(size=16)
p = GreedyPolicy()
d = p.decide(e)
print('decided direction:', d)
print('direction is set:', d is not None)
"
```

Expected: prints a direction value (1, 2, 3, or 4) and `True`.

- [ ] **Step 3: Lint**

```bash
uv run ruff check src/embedded/greedy_policy.py
```

Expected: passes.

- [ ] **Step 4: Commit**

```bash
git add src/embedded/greedy_policy.py
git commit -m "refactor(embedded): extract greedy AI as a Policy implementation"
```

---

## Task 15: Add `src/embedded/learned_policy.py` (stub)

Loud-failing stub for the future emlearn-backed policy. Keeps the seam in place; raises `NotImplementedError` so a misconfigured `POLICY` constant fails at startup rather than silently degrading.

**Files:**
- Create: `src/embedded/learned_policy.py`

- [ ] **Step 1: Create `src/embedded/learned_policy.py`**

```python
from common.policy import Policy

WEIGHTS_PATH = "model_weights.bin"  # placeholder; format TBD when training is wired up


class LearnedPolicy(Policy):
    """Stub for an emlearn-backed inference policy.

    When implemented (Bridge A: PyTorch DQN -> sklearn MLPRegressor -> emlearn export),
    this class will load WEIGHTS_PATH on construction and run inference each tick.

    Today it raises so a misconfigured POLICY constant fails loudly at startup
    rather than silently falling back.
    """

    def __init__(self):
        raise NotImplementedError(
            "LearnedPolicy is not implemented yet. "
            "Set POLICY = 'greedy' in embedded/main.py."
        )

    def decide(self, engine):
        raise NotImplementedError
```

- [ ] **Step 2: Smoke-test the stub raises**

```bash
uv run python -c "
import sys
sys.path.insert(0, 'src/embedded')
from learned_policy import LearnedPolicy
try:
    LearnedPolicy()
    print('FAIL: expected NotImplementedError')
except NotImplementedError as e:
    print('OK:', e)
"
```

Expected output: `OK: LearnedPolicy is not implemented yet. Set POLICY = 'greedy' in embedded/main.py.`

- [ ] **Step 3: Lint**

```bash
uv run ruff check src/embedded/learned_policy.py
```

Expected: passes.

- [ ] **Step 4: Commit**

```bash
git add src/embedded/learned_policy.py
git commit -m "feat(embedded): stub LearnedPolicy (emlearn-backed, deferred)"
```

---

## Task 16: Rewrite `src/embedded/game.py` as a thin adapter

Today's `src/embedded/game.py` is ~220 lines: a duplicated `SnakeGame` plus rendering plus AI plus high-score I/O. It now becomes a small orchestrator: holds the `SnakeEngine`, picks a `Policy` by name, owns the per-game palette, and drives a `tick()` loop. Drawing is delegated to `display.draw_snake`; AI is delegated to the policy.

**Files:**
- Rewrite: `src/embedded/game.py`

- [ ] **Step 1: Replace `src/embedded/game.py` with the new content**

```python
from random import random, uniform

from common.colors import hsv_to_rgb
from common.engine import SnakeEngine
from display import display_scores, draw_snake, reset_draw_caches
from greedy_policy import GreedyPolicy
from learned_policy import LearnedPolicy

GAME_SIZE = 16
DEFAULT_SPEED = 50
HIGH_SCORE_FILE = "high_score.txt"

_POLICIES = {
    "greedy": GreedyPolicy,
    "learned": LearnedPolicy,
}


def load_high_score():
    try:
        with open(HIGH_SCORE_FILE, "r") as f:
            return int(f.read())
    except (OSError, ValueError):
        return 0


def save_high_score(value):
    try:
        with open(HIGH_SCORE_FILE, "w") as f:
            f.write(str(value))
    except OSError:
        print("Error saving high score.")


class SnakeGame:
    """Embedded adapter: drives a SnakeEngine with a Policy, renders gradient
    snake + food via display.draw_snake, persists high score on game-over.
    """

    def __init__(self, policy_name="greedy", speed=DEFAULT_SPEED):
        if policy_name not in _POLICIES:
            raise ValueError(
                "Unknown policy: " + repr(policy_name)
                + ". Valid: " + ", ".join(sorted(_POLICIES))
            )

        self.engine = SnakeEngine(size=GAME_SIZE)
        self.policy = _POLICIES[policy_name]()
        self.speed = speed

        # Per-game single-hue palette.
        self.base_hue = random()
        self.start_color = hsv_to_rgb(self.base_hue, 1.0, 0.15)  # dim tail
        self.end_color = hsv_to_rgb(self.base_hue, 1.0, 0.70)   # bright head
        self.food_color = self._new_food_color()

        reset_draw_caches()

    def _new_food_color(self):
        h = (self.base_hue + 0.5 + uniform(-0.05, 0.05)) % 1.0
        return hsv_to_rgb(h, 1.0, 0.70)

    def _palette(self):
        return (self.start_color, self.end_color, self.food_color, self.speed)

    def tick(self):
        """One frame: policy → engine → renderer."""
        direction = self.policy.decide(self.engine)
        prev_food = self.engine.food
        self.engine.step(direction)

        # Refresh food color when the snake actually ate.
        if self.engine.food != prev_food:
            self.food_color = self._new_food_color()

        draw_snake(self.engine, self._palette())

    def start_game(self):
        self.engine.score = 0
        self.high_score = load_high_score()

    def end_game(self):
        from time import sleep

        current_score = self.engine.score
        high_score = load_high_score()
        if current_score > high_score:
            save_high_score(current_score)
            high_score = current_score
        display_scores(high_score, current_score)
        sleep(5)
```

Notes:
- `SnakeGame` no longer owns the snake list, food, direction, or score — it delegates to `self.engine`.
- The greedy AI's `ai_move`, `move_snake`, `change_direction`, `generate_food`, `draw_snake` body, and gradient cache are gone — moved to engine + greedy_policy + display.
- `tick()` is the per-frame loop body. The runner in `main.py` calls it until `engine.game_over`.
- `policy_name` is validated at construction time. Unknown names raise `ValueError` immediately.
- The food-color refresh logic compares the new food cell to the previous one; if they differ, the engine ate (or wrapped via full-board game-over). This preserves the "food gets a fresh complementary hue per spawn" behaviour.

- [ ] **Step 2: Lint**

```bash
uv run ruff check src/embedded/game.py
```

Expected: passes.

- [ ] **Step 3: Smoke-parse the file**

```bash
uv run python -c "
import ast, pathlib
ast.parse(pathlib.Path('src/embedded/game.py').read_text())
print('OK')
"
```

Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add -u src/embedded/game.py
git commit -m "refactor(embedded): SnakeGame is a thin adapter over SnakeEngine + Policy"
```

---

## Task 17: Update `src/embedded/main.py` with the `POLICY` constant

**Files:**
- Modify: `src/embedded/main.py`

- [ ] **Step 1: Replace `src/embedded/main.py` with the new content**

```python
from game import SnakeGame
# from wlan import start_wlan

POLICY = "greedy"  # "greedy" | "learned"


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

The original loop called `game.ai_move(); game.move_snake(); game.draw_snake()`. The new `tick()` does all three in order.

- [ ] **Step 2: Lint**

```bash
uv run ruff check src/embedded/main.py
```

Expected: passes.

- [ ] **Step 3: Smoke-parse**

```bash
uv run python -c "
import ast, pathlib
ast.parse(pathlib.Path('src/embedded/main.py').read_text())
print('OK')
"
```

Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add -u src/embedded/main.py
git commit -m "feat(embedded): POLICY constant selects greedy or learned at startup"
```

---

## Task 18: Add pre-commit config

**Files:**
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Create `.pre-commit-config.yaml`**

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

- [ ] **Step 2: Install the hook**

```bash
uv run pre-commit install
```

Expected output: `pre-commit installed at .git/hooks/pre-commit`.

- [ ] **Step 3: Run all hooks once over staged files (sanity check)**

```bash
uv run pre-commit run --all-files
```

Expected: ruff format and ruff lint pass. mypy passes against `src/common/` and `src/desktop/`. There may be small auto-formatting changes (whitespace normalisation, import ordering) — those are fine; if any appear, stage and commit them in the next step.

- [ ] **Step 4: Commit (including any auto-fixes)**

```bash
git add .pre-commit-config.yaml
git add -u
git commit -m "chore: pre-commit hooks for ruff and mypy"
```

---

## Task 19: Update `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace `README.md` with the new content**

```markdown
## Snake AI Game

Two implementations of Snake share a common engine in this repo:

* **Desktop version** ([src/desktop/](src/desktop/)) — Pygame UI with a Deep Q-Learning agent (PyTorch).
* **Embedded version** ([src/embedded/](src/embedded/)) — MicroPython for an ESP32 driving a 16×16 NeoPixel matrix, with a wrapped-distance greedy AI as the default policy and a stubbed learned policy for future work.

Shared, MicroPython-safe game logic lives in [src/common/](src/common/): `direction.py` (the `Direction` enum), `colors.py` (HSV + gradient helpers), `engine.py` (the headless `SnakeEngine`), and `policy.py` (the `Policy` interface).

### Project layout

```text
src/
  common/          # shared engine, policy interface, color helpers
  desktop/         # CPython + pygame + PyTorch DQN
  embedded/        # MicroPython + NeoPixel
docs/superpowers/  # specs and implementation plans
model/             # saved PyTorch checkpoints
db/                # SQLite run logs
notebooks/         # exploration notebooks
scores.csv         # per-game training scores
pyproject.toml     # deps + tool config (ruff, mypy, pytest)
uv.lock            # uv lockfile
.python-version    # pinned Python (3.11)
```

### Setup (desktop)

```bash
uv sync
uv run python -m desktop.main      # train the DQN
```

To play with the keyboard, edit the `__main__` block in [src/desktop/main.py](src/desktop/main.py) to set `learning = False` and `py_ui = True`.

### Deploy (embedded)

The embedded build runs on an ESP32 with MicroPython. Files are deployed flat to the device root, with `common/` as a package alongside.

```bash
mpremote cp -r src/common/ :/common
mpremote cp src/embedded/*.py :/
mpremote reset
```

Pick a policy by editing the constant at the top of [src/embedded/main.py](src/embedded/main.py):

```python
POLICY = "greedy"   # or "learned" once that's wired up
```

The `learned` policy is a stub today — selecting it raises `NotImplementedError` at boot.

### Dev tooling

```bash
uv run ruff check src/         # lint
uv run ruff format src/        # format
uv run mypy                    # type check (covers src/common, src/desktop)
uv run pytest                  # tests (none yet)
uv run pre-commit install      # one-time: install git hooks
```

`src/embedded/` is excluded from mypy because it uses flat imports that resolve on the device root but not under CPython without sys-path tweaks. Ruff still lints it.

### Coordinate convention

The engine and renderers all use `(x=col, y=row)`. `Direction.RIGHT` increments `x`; `Direction.DOWN` increments `y`. The desktop renderer multiplies cells by `BLOCK_SIZE` to draw pygame rects; the embedded renderer translates `(col, row)` to a flat NeoPixel index in [src/embedded/display.py](src/embedded/display.py)'s `xy_to_index`.

### Features

* 16×16 wrapping torus (no walls — the snake comes out the other side).
* Cell-space `SnakeEngine` shared between desktop and embedded builds.
* DQN agent ([src/desktop/model.py](src/desktop/model.py)) with experience replay and ε-greedy exploration.
* Live score / mean-score / moving-average plotting via matplotlib ([src/desktop/plot.py](src/desktop/plot.py)).
* Per-game run logging to [scores.csv](scores.csv) and `db/tests.sqlite`.
* Best-model checkpointing to `model/model.pth`. Note: the cell-space refactor invalidated any pre-2026-04-29 checkpoints — retrain from scratch.
* Embedded gradient-colored snake with single-hue per-game palette and complementary-hue food.
* Persistent embedded high score (`high_score.txt`).

### To do

* Implement [src/embedded/learned_policy.py](src/embedded/learned_policy.py) via emlearn-micropython (Bridge A: PyTorch → sklearn `MLPRegressor` → emlearn export).
* Tests for `src/common/engine.py`.
* Resume training from an existing `model/model.pth`.
```

- [ ] **Step 2: Verify the markdown renders**

```bash
head -50 README.md
```

Expected: legible, well-structured markdown.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README for new layout, uv tooling, and deployment notes"
```

---

## Task 20: Final cleanup — remove `requirements.txt`, run all tools clean

**Files:**
- Delete: `requirements.txt`

- [ ] **Step 1: Confirm `pyproject.toml` covers everything in `requirements.txt`**

```bash
cat requirements.txt
```

Expected output:
```
ipykernel
matplotlib
nbformat
pandas
pygame
plotly==6.0.0rc0
torch
```

All seven are listed in `pyproject.toml`'s `[project] dependencies`. (Note: `numpy` is in `pyproject.toml` but not `requirements.txt`; this is correct — `numpy` is used by `src/desktop/main.py` and was a transitive dep through `torch` before; making it explicit is the right move.)

- [ ] **Step 2: Delete `requirements.txt`**

```bash
git rm requirements.txt
```

- [ ] **Step 3: Run all linters and type checks**

```bash
uv run ruff check src/
uv run ruff format --check src/
uv run mypy
```

Expected: all three pass.

If `ruff format --check` reports diffs, run `uv run ruff format src/` and re-stage.

- [ ] **Step 4: Run the desktop smoke test one more time**

```bash
timeout 5 uv run python -m desktop.main || true
```

Expected: training runs without tracebacks, matplotlib plot pops up, sqlite logs append.

- [ ] **Step 5: Final commit**

```bash
git add -u
git commit -m "chore: drop requirements.txt; pyproject.toml is the single source of truth"
```

- [ ] **Step 6: Review the branch**

```bash
git log --oneline main..HEAD
```

Expected: a clean, ordered series of conventional commits — one per task above (Tasks 9 and 11 may not have produced commits if their respective conditions were vacuous).

---

## Manual verification checklist

After completing all tasks:

- [ ] `uv sync` works on a fresh checkout.
- [ ] `uv run python -m desktop.main` enters training mode without traceback.
- [ ] Editing `desktop/main.py`'s `__main__` block to `learning=False, py_ui=True` lets a human play with arrow keys.
- [ ] `uv run ruff check src/` passes.
- [ ] `uv run mypy` passes.
- [ ] `uv run pre-commit run --all-files` passes.
- [ ] On the ESP32: `mpremote cp -r src/common/ :/common && mpremote cp src/embedded/*.py :/` lands all files cleanly. The snake runs with `POLICY = "greedy"` (default) and looks the same as before — single-hue gradient, complementary food, score display on game-over.
- [ ] On the ESP32: setting `POLICY = "learned"` and rebooting raises `NotImplementedError` at startup.
- [ ] README renders and links resolve.
