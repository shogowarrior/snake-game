"""Preview the score render as ASCII for every rotation, plus each glyph in
isolation so typos in `digits`/`characters` show up before flashing.

Run from the repo root:

    uv run python scripts/preview_score.py

This bypasses pygame entirely: it imports the embedded display module with
fakes pre-loaded, calls display_char/display_scores, and prints the post-flush
NP buffer (the same bytes hardware lights up) as ASCII.

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


def render_glyph(ch):
    """Render a single glyph at scale 1 from `digits` so the 5x3 shape is
    visible exactly as it's stored. Bypasses rotation/serpentine — this is
    a *pattern* preview, not a panel preview, so typos in `digits` jump out
    even when ROTATION is set to something exotic.
    """
    pattern = display.digits.get(ch) or display.characters.get(ch.upper())
    if pattern is None:
        return f"(no glyph for {ch!r})"
    return "\n".join("".join("##" if cell else ". " for cell in row) for row in pattern)


print(f"config.ROTATION = {config.ROTATION!r}")
print("display._lut is built for the above. Edit config.py and re-run to compare rotations.\n")

print("=" * 40)
print("Glyph shapes (5x3, scale 1, no rotation)")
print("Look for orphaned pixels or stroke discontinuities.")
print("=" * 40)
for ch in "0123456789":
    print(f"\n--- '{ch}' ---")
    print(render_glyph(ch))

print()
print("=" * 40)
print("Score renders (current ROTATION applied)")
print("=" * 40)
for score in (5, 12, 71, 99):
    print(f"\n--- score = {score} ---")
    print(render_score(score))
