"""Entry point for the desktop simulator.

Boots the same code that runs on the ESP32 by:
  1. Pre-loading fake `machine` and `neopixel` into sys.modules so
     `embedded/display.py` imports them instead of the device-only originals.
  2. Adding `src/embedded` to sys.path so the flat imports used on-device
     (`import display`, `import game`, `import greedy_policy`, ...) resolve.

Run from the repo root:

    uv run python src/sim/main.py
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent  # .../src
sys.path.insert(0, str(SRC))  # common, sim
sys.path.insert(0, str(SRC / "embedded"))  # flat embedded imports

from sim import fake_controller, fake_machine, fake_neopixel  # noqa: E402

sys.modules["machine"] = fake_machine
sys.modules["neopixel"] = fake_neopixel
sys.modules["controller"] = fake_controller

# Importing embedded/main.py runs run_game() at top level — exactly as on-device.
import main  # noqa: E402, F401
