"""Preview the score render as ASCII for every rotation.

Run from the repo root:

    uv run python scripts/preview_score.py

This bypasses pygame entirely: it imports the embedded display module with
fakes pre-loaded, calls display_scores for a few sample scores, and prints
the post-flush NP buffer (the same bytes hardware lights up) as ASCII.

Use this to pick the right ROTATION value before flashing. Edit
src/embedded/config.py, re-run, eyeball, repeat.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC / "embedded"))

from sim import fake_machine, fake_neopixel  # noqa: E402

sys.modules["machine"] = fake_machine
sys.modules["neopixel"] = fake_neopixel

from sim import screen  # noqa: E402

screen.flush = lambda buf: None  # headless

import config  # noqa: E402
import display  # noqa: E402

SIZE = 16


def np_to_panel(buffer):
    """Invert serpentine: buffer[i] -> panel grid[py][px]."""
    grid = [[(0, 0, 0)] * SIZE for _ in range(SIZE)]
    for i, color in enumerate(buffer):
        py = i // SIZE
        off = i % SIZE
        px = off if py % 2 == 0 else SIZE - 1 - off
        grid[py][px] = color
    return grid


def render_ascii(grid):
    return "\n".join("".join("##" if any(c) else ". " for c in row) for row in grid)


def render_score(score):
    display.display_scores(0, score)
    return render_ascii(np_to_panel(display.NP.buf))


print(f"config.ROTATION = {config.ROTATION!r}")
print("display._lut is built for the above. Edit config.py and re-run to compare rotations.\n")
for score in (5, 12, 99):
    print(f"--- score = {score} ---")
    print(render_score(score))
    print()
