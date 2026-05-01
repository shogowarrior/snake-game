---
name: flash-snake
description: Use when the user asks to flash, deploy, push, or run the embedded snake build on the ESP32 / NeoPixel matrix from this repo. Wraps `mpremote` with the paths this repo's `src/common/` + `src/embedded/` layout expects. Trigger even when the user just says "flash it", "push to device", "send to esp32", or "run on hardware" without naming a tool.
---

# Flash snake to ESP32

The embedded build runs on an ESP32 with MicroPython. Deploys are flat: `common/` lands as a package at the device root, alongside the loose `embedded/*.py` files (`main.py`, `boot.py`, `display.py`, ...).

## Default port

The ESP32 is normally on `/dev/ttyUSB0` on this machine (CP210x USB-serial bridge). If a different board is plugged in, see "Other ports" below.

## Recipe

From the repo root:

```bash
mpremote connect /dev/ttyUSB0 cp -r src/common/ :/common
mpremote connect /dev/ttyUSB0 cp src/embedded/*.py :/
mpremote connect /dev/ttyUSB0 reset
```

After `reset`, the matrix should start drawing within ~1 second. If it doesn't, jump to "Debugging" below.

Run all three commands explicitly with `connect /dev/ttyUSB0` rather than relying on `mpremote`'s auto-discovery — auto-discovery picks up other CDC devices (an LG monitor on this machine appears as `/dev/ttyACM0`) and can attach to the wrong one.

## Other ports

If the ESP32 is somewhere else, list candidates:

```bash
mpremote connect list
```

ESP32s show up as `/dev/ttyUSB*` (CP210x / CH340 bridge) or `/dev/ttyACM*` (native USB CDC). Substitute the right one in the three commands.

## Debugging

**Nothing on the matrix after reset.** Open the REPL and watch the boot log:

```bash
mpremote connect /dev/ttyUSB0 repl
```

`Ctrl-]` exits the REPL. Common causes:
- Stale `boot.py` references an old API. The current entry point is `main.py`; if `boot.py` still imports `SnakeGame.move_snake()` etc., it will raise `AttributeError` on boot. Either fix `boot.py` or delete it from the device with `mpremote connect /dev/ttyUSB0 rm :boot.py`.
- A file failed to copy (the previous run died mid-copy). Re-run the three-command recipe.

**`device busy` or `cannot open port`.** Another `mpremote` REPL is still attached. Close it (`Ctrl-]`) or kill stray `mpremote` processes.

**`No such file or directory: src/common/`.** You're not at the repo root. `cd` into the repo first.

## Why these paths

The embedded code uses flat imports — `from common.engine import SnakeEngine`, `from display import draw_snake`, etc. — that resolve from the device root. `src/common/` becomes `/common` (a package directory), and `src/embedded/*.py` go directly to `/`. This matches `pyproject.toml`'s convention that `src/embedded/` ships to the device via `mpremote` rather than via the wheel build.

## What this skill does NOT do

- Build, lint, or test before flashing. Run those separately if you want them as a gate (`uv run ruff check src/embedded/` and `uv run ruff format --check src/embedded/`).
- Merge to `main` or push to a remote. Flashing is independent of git state.
- Manage the high-score file on the device (`/high_score.txt`). It persists across flashes by design — delete it manually with `mpremote connect /dev/ttyUSB0 rm :high_score.txt` if you want a clean slate.
