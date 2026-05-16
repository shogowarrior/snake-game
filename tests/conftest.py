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
