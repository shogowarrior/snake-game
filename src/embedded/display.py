from time import sleep

import neopixel  # type: ignore
from config import ROTATION, SCORE_GRADIENT_END, SCORE_GRADIENT_START  # noqa: F401
from machine import Pin  # type: ignore

from common.colors import gradient_color

# Temporary alias so the existing xy_to_index body needs zero edits during
# the framebuffer migration. Removed in Task 9.
ORIENTATION = ROTATION

WHITE = (128, 128, 128)
BLACK = (0, 0, 0)
GREEN = (0, 128, 0)
RED = (128, 0, 0)
BLUE = (0, 0, 128)

NEOPIXEL_PIN = 13
NUM_PIXELS = 256
NP = neopixel.NeoPixel(Pin(NEOPIXEL_PIN), NUM_PIXELS)

# Character patterns (5x3 grid for each character)
digits = {
    "0": [(1, 1, 1), (1, 0, 1), (1, 0, 1), (1, 0, 1), (1, 1, 1)],
    "1": [(0, 1, 0), (1, 1, 0), (0, 1, 0), (0, 1, 0), (1, 1, 1)],
    "2": [(1, 1, 1), (0, 0, 1), (1, 1, 1), (1, 0, 0), (1, 1, 1)],
    "3": [(1, 1, 1), (0, 0, 1), (1, 1, 1), (0, 0, 1), (1, 1, 1)],
    "4": [(1, 0, 1), (1, 0, 1), (1, 1, 1), (0, 0, 1), (0, 0, 1)],
    "5": [(1, 1, 1), (1, 0, 0), (1, 1, 1), (0, 0, 1), (1, 1, 1)],
    "6": [(1, 1, 1), (1, 0, 0), (1, 1, 1), (1, 0, 1), (1, 1, 1)],
    "7": [(1, 1, 1), (0, 0, 1), (0, 0, 1), (0, 1, 0), (0, 1, 0)],
    "8": [(1, 1, 1), (1, 0, 1), (1, 1, 1), (1, 0, 1), (1, 1, 1)],
    "9": [(1, 1, 1), (1, 0, 1), (1, 1, 1), (0, 0, 1), (1, 1, 1)],
}

characters = {
    "A": [(1, 1, 1), (1, 0, 1), (1, 1, 1), (1, 0, 1), (1, 0, 1)],
    "B": [(1, 1, 0), (1, 0, 1), (1, 1, 0), (1, 0, 1), (1, 1, 0)],
    "C": [(0, 1, 1), (1, 0, 0), (1, 0, 0), (1, 0, 0), (0, 1, 1)],
    "D": [(1, 1, 0), (1, 0, 1), (1, 0, 1), (1, 0, 1), (1, 1, 0)],
    "E": [(1, 1, 1), (1, 0, 0), (1, 1, 1), (1, 0, 0), (1, 1, 1)],
    "F": [(1, 1, 1), (1, 0, 0), (1, 1, 1), (1, 0, 0), (1, 0, 0)],
    "G": [(0, 1, 1), (1, 0, 0), (1, 0, 1), (1, 0, 1), (0, 1, 1)],
    "H": [(1, 0, 1), (1, 0, 1), (1, 1, 1), (1, 0, 1), (1, 0, 1)],
    "I": [(1, 1, 1), (0, 1, 0), (0, 1, 0), (0, 1, 0), (1, 1, 1)],
    "J": [(0, 0, 1), (0, 0, 1), (0, 0, 1), (1, 0, 1), (0, 1, 1)],
    "K": [(1, 0, 1), (1, 0, 1), (1, 1, 0), (1, 0, 1), (1, 0, 1)],
    "L": [(1, 0, 0), (1, 0, 0), (1, 0, 0), (1, 0, 0), (1, 1, 1)],
    "M": [(1, 0, 1), (1, 1, 1), (1, 0, 1), (1, 0, 1), (1, 0, 1)],
    "N": [(1, 0, 1), (1, 1, 1), (1, 1, 1), (1, 0, 1), (1, 0, 1)],
    "O": [(0, 1, 0), (1, 0, 1), (1, 0, 1), (1, 0, 1), (0, 1, 0)],
    "P": [(1, 1, 0), (1, 0, 1), (1, 1, 0), (1, 0, 0), (1, 0, 0)],
    "Q": [(0, 1, 0), (1, 0, 1), (1, 0, 1), (1, 1, 0), (0, 1, 1)],
    "R": [(1, 1, 0), (1, 0, 1), (1, 1, 0), (1, 1, 0), (1, 0, 1)],
    "S": [(0, 1, 1), (1, 0, 0), (0, 1, 1), (0, 0, 1), (1, 1, 0)],
    "T": [(1, 1, 1), (0, 1, 0), (0, 1, 0), (0, 1, 0), (0, 1, 0)],
    "U": [(1, 0, 1), (1, 0, 1), (1, 0, 1), (1, 0, 1), (0, 1, 1)],
    "V": [(1, 0, 1), (1, 0, 1), (1, 0, 1), (0, 1, 0), (0, 1, 0)],
    "W": [(1, 0, 1), (1, 0, 1), (1, 0, 1), (1, 1, 1), (1, 0, 1)],
    "X": [(1, 0, 1), (1, 0, 1), (0, 1, 0), (1, 0, 1), (1, 0, 1)],
    "Y": [(1, 0, 1), (1, 0, 1), (0, 1, 0), (0, 1, 0), (0, 1, 0)],
    "Z": [(1, 1, 1), (0, 0, 1), (0, 1, 0), (1, 0, 0), (1, 1, 1)],
}

special_chars = {
    "!": [(0, 1, 0), (0, 1, 0), (0, 1, 0), (0, 0, 0), (0, 1, 0)],
    "?": [(1, 1, 1), (0, 0, 1), (0, 1, 1), (0, 0, 0), (0, 1, 0)],
    ".": [(0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 1, 0)],
    "-": [(0, 0, 0), (0, 0, 0), (1, 1, 1), (0, 0, 0), (0, 0, 0)],
    "+": [(0, 1, 0), (0, 1, 0), (1, 1, 1), (0, 1, 0), (0, 1, 0)],
    "=": [(0, 0, 0), (1, 1, 1), (0, 0, 0), (1, 1, 1), (0, 0, 0)],
    ":": [(0, 0, 0), (0, 1, 0), (0, 0, 0), (0, 1, 0), (0, 0, 0)],
    ",": [(0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 1, 0), (1, 0, 0)],
    "#": [(0, 1, 0), (1, 1, 1), (0, 1, 0), (1, 1, 1), (0, 1, 0)],
    "*": [(1, 0, 1), (0, 1, 0), (1, 1, 1), (0, 1, 0), (1, 0, 1)],
    "/": [(0, 0, 1), (0, 1, 0), (0, 1, 0), (1, 0, 0), (0, 0, 0)],
    "\\": [(1, 0, 0), (0, 1, 0), (0, 1, 0), (0, 0, 1), (0, 0, 0)],
    "@": [(1, 1, 1), (1, 1, 0), (1, 1, 1), (1, 0, 1), (1, 1, 1)],
    " ": [(0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)],  # Empty space
}


# Coord -> flat NeoPixel index helpers for the 16x16 panel.
# Both apply the same serpentine-wiring rule (odd physical rows run right-to-left);
# they differ only in whether they rotate game-space first.
def xy_to_index(x, y):
    """Game-space (col, row) -> flat NeoPixel index. ORIENTATION rotation, then serpentine."""
    if ORIENTATION == "0":
        px, py = x, y
    elif ORIENTATION == "90CW":
        px, py = 15 - y, x
    elif ORIENTATION == "180":
        px, py = 15 - x, 15 - y
    else:  # "90CCW"
        px, py = y, 15 - x
    if py % 2 == 0:
        return py * 16 + px
    return py * 16 + (15 - px)


# Clear the screen
def clear_screen():
    NP.fill(BLACK)
    NP.write()


# Score text rotates with the game (via xy_to_index) so it reads upright from
# the same viewing angle the user plays at. `scale` blows each pattern pixel
# up to a scale x scale block.
def display_char(char, offset_x=0, offset_y=0, color=WHITE, scale=1):
    char = char.upper()
    pattern = characters.get(char) or digits.get(char) or special_chars.get(char)

    if pattern is None:
        return

    for row_idx, row in enumerate(pattern):
        for col_idx, pixel in enumerate(row):
            for dx in range(scale):
                for dy in range(scale):
                    x = offset_x + col_idx * scale + dx
                    y = offset_y + row_idx * scale + dy
                    if 0 <= x < 16 and 0 <= y < 16:
                        NP[xy_to_index(x, y)] = color if pixel else (0, 0, 0)


def display_message(message, offset_x=0, offset_y=0, color=WHITE, scale=1):
    advance = 4 * scale  # 3-col glyph + 1-col padding, both scaled
    for char in message:
        display_char(char, offset_x, offset_y, color, scale)
        offset_x += advance
        if offset_x >= 16:
            break
    NP.write()


# Display high score and current score together on the 16x16 grid, centered horizontally
def display_scores(high_score, current_score):
    clear_screen()
    score_str = str(current_score)
    scale = 2
    # 4*scale per char, minus the trailing padding after the last char.
    width = len(score_str) * 4 * scale - scale
    offset_x = max(0, (16 - width) // 2)
    offset_y = (16 - 5 * scale) // 2
    display_message(score_str, offset_x, offset_y, BLUE, scale=scale)
    # High score hidden for now — re-enable when layout is ready:
    # display_message(f"H:{high_score}", 1, 1, GREEN)


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
    global _prev_snake_cells, _gradient_colors, _previous_snake_length  # noqa: PLW0603

    start_color, end_color, food_color, speed = palette
    cur = set(engine.snake)

    snake_length = len(engine.snake)
    if snake_length != _previous_snake_length:
        _gradient_colors = [gradient_color(i, snake_length, start_color, end_color) for i in range(snake_length)]
        _previous_snake_length = snake_length

    # Clear cells that were snake last frame but aren't now.
    for x, y in _prev_snake_cells - cur:
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
    """Call between games so the new game starts blank with fresh caches."""
    global _prev_snake_cells, _gradient_colors, _previous_snake_length  # noqa: PLW0603
    _prev_snake_cells = set()
    _gradient_colors = []
    _previous_snake_length = 0
    clear_screen()
