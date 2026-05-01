from time import sleep

import neopixel  # type: ignore
from machine import Pin  # type: ignore

from common.colors import gradient_color

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


# Game-space rotation. Change this to remount the panel in any of the four
# right-angle orientations without touching the renderers. Score text is drawn
# via panel_index and is unaffected — it always reads upright on the unrotated
# panel.
ORIENTATION = "90CW"  # "0" | "90CW" | "180" | "90CCW"


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


def panel_index(px, py):
    """Panel-natural (col, row) -> flat NeoPixel index. Serpentine only — no rotation.
    Use for score / overlay text that should read upright on the unrotated panel."""
    if py % 2 == 0:
        return py * 16 + px
    return py * 16 + (15 - px)


# Clear the screen
def clear_screen():
    NP.fill(BLACK)
    NP.write()


# Function to display a single character
def display_char(char, offset_x=0, offset_y=0, color=WHITE):
    char = char.upper()
    pattern = characters.get(char) or digits.get(char) or special_chars.get(char)

    if pattern is None:
        return

    # Iterate through each row and column in the pattern
    # Score text is drawn in the panel's natural orientation so it's readable
    # regardless of the game-space rotation in xy_to_index.
    for row_idx, row in enumerate(pattern):
        for col_idx, pixel in enumerate(row):
            px = offset_x + col_idx
            py = offset_y + row_idx
            if 0 <= px < 16 and 0 <= py < 16:
                if pixel == 1:
                    NP[panel_index(px, py)] = color
                else:
                    NP[panel_index(px, py)] = (0, 0, 0)


# Function to display a message
def display_message(message, offset_x=0, offset_y=0, color=WHITE):
    # clear_screen()  # Clear the display first

    for char in message:
        display_char(char, offset_x, offset_y, color)
        offset_x += 4  # Move to the right after displaying each character (3 for char + 1 padding)
        if offset_x >= 16:  # Stop if the next character would go out of bounds
            break
    NP.write()  # Send the data to the NeoPixel display


# Display high score and current score together on the 16x16 grid, centered horizontally
def display_scores(high_score, current_score):
    clear_screen()
    display_message(str(current_score), 1, 10, BLUE)
    # High score hidden for now — re-enable when layout is ready:
    # high_score_message = f"H:{high_score}"
    # display_message(high_score_message, 1, 2, GREEN)


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
