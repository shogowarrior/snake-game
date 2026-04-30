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
