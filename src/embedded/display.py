from time import sleep

import neopixel  # type: ignore
from config import (
    BRIGHTNESS,
    NEOPIXEL_PIN,
    ROTATION,
)
from glyphs import GLYPHS
from machine import Pin  # type: ignore

from common.colors import gradient_color

__all__ = [
    "BLACK",
    "Display",
    "NUM_PIXELS",
    "WHITE",
]

WHITE = (128, 128, 128)
BLACK = (0, 0, 0)

NUM_PIXELS = 256
_VALID_ROTATIONS = (0, 90, 180, 270)


def _compute_lut(rotation):
    """Build the framebuffer-index → NP-index mapping for a given rotation.

    Rotation is in degrees, clockwise (0, 90, 180, 270). For each framebuffer
    cell (x, y), determine the panel cell (px, py) after rotation, then the
    flat NP index via the column-serpentine wiring (odd columns run bottom-to-top).
    """
    if rotation not in _VALID_ROTATIONS:
        raise ValueError("rotation must be 0|90|180|270, got " + repr(rotation))
    lut = [0] * 256
    for y in range(16):
        for x in range(16):
            if rotation == 0:
                px, py = x, y
            elif rotation == 90:
                px, py = 15 - y, x
            elif rotation == 180:
                px, py = 15 - x, 15 - y
            else:  # 270
                px, py = y, 15 - x
            np_index = px * 16 + (py if px % 2 == 0 else 15 - py)
            lut[y * 16 + x] = np_index
    return lut


class Display:
    """Owns the NeoPixel handle, the framebuffer, the rotation LUT, and the
    render-loop caches. All mutable display state lives here — no module-level
    state, no `global` keyword. Instantiate once per process and pass to
    consumers (`SnakeGame`).

    Drawers call `set_pixel` to write into `_fb` in natural (x, y) coords;
    `flush` is the only thing that applies rotation + serpentine wiring and
    pushes pixels to the LEDs.
    """

    def __init__(self):
        self.np = neopixel.NeoPixel(Pin(NEOPIXEL_PIN), NUM_PIXELS)
        self._fb = [(0, 0, 0)] * NUM_PIXELS  # flat: _fb[y * 16 + x]
        self._lut = _compute_lut(ROTATION)
        self._prev_snake_cells = set()
        self._gradient_colors = []
        self._previous_snake_length = 0

    def set_pixel(self, x, y, color):
        """Set framebuffer cell (x, y) to `color`. Out-of-range silently ignored."""
        if 0 <= x < 16 and 0 <= y < 16:
            self._fb[y * 16 + x] = color

    def clear(self):
        """Reset all 256 framebuffer cells to (0, 0, 0)."""
        for i in range(NUM_PIXELS):
            self._fb[i] = (0, 0, 0)

    def flush(self):
        """Push the framebuffer to the LEDs via the LUT, then NP.write().

        The only place rotation + serpentine apply, and the chokepoint where
        config.BRIGHTNESS is folded in so it scales snake, food, and score
        uniformly.
        """
        np, fb, lut = self.np, self._fb, self._lut
        if BRIGHTNESS >= 1.0:
            for i in range(NUM_PIXELS):
                np[lut[i]] = fb[i]
        else:
            for i in range(NUM_PIXELS):
                r, g, b = fb[i]
                np[lut[i]] = (int(r * BRIGHTNESS), int(g * BRIGHTNESS), int(b * BRIGHTNESS))
        np.write()

    def display_char(self, char, offset_x=0, offset_y=0, color=WHITE, scale=1):
        """Draw one 5x3 glyph into the framebuffer at (offset_x, offset_y).

        `color` may be an (r, g, b) tuple or a callable `(x, y) -> (r, g, b)`
        for per-pixel coloring (gradients).
        """
        pattern = GLYPHS.get(char.upper())
        if pattern is None:
            return

        color_is_callable = callable(color)
        for row_idx, row in enumerate(pattern):
            for col_idx, pixel in enumerate(row):
                if not pixel:
                    continue
                for dx in range(scale):
                    for dy in range(scale):
                        x = offset_x + col_idx * scale + dx
                        y = offset_y + row_idx * scale + dy
                        if 0 <= x < 16 and 0 <= y < 16:
                            self.set_pixel(x, y, color(x, y) if color_is_callable else color)

    def display_message(self, message, offset_x=0, offset_y=0, color=WHITE, scale=1):
        """Draw a string of glyphs left-to-right, then flush to the LEDs."""
        advance = 4 * scale  # 3-col glyph + 1-col padding, both scaled
        for char in message:
            self.display_char(char, offset_x, offset_y, color, scale)
            offset_x += advance
            if offset_x >= 16:
                break
        self.flush()

    def display_scores(self, current_score, start_color, end_color):
        """Game-over score: centered, horizontally gradient-colored.

        Gradient runs start_color -> end_color (the snake's head/tail hues).
        Drawn into the framebuffer in natural coordinates — rotation is
        applied by flush() (via config.ROTATION), uniformly with snake/food.
        """
        score_str = str(current_score)
        scale = 2
        width = len(score_str) * 4 * scale - scale
        offset_x = max(0, (16 - width) // 2)
        offset_y = (16 - 5 * scale) // 2
        left = offset_x

        def gradient(x, _y):
            return gradient_color(x - left, width, start_color, end_color)

        self.clear()
        self.display_message(score_str, offset_x, offset_y, gradient, scale=scale)

    def draw_snake(self, engine, palette):
        """Paint one frame: snake gradient + food cell. Sleeps for the engine tick.

        palette is (start_color, end_color, food_color, speed) — provided by the
        embedded SnakeGame each frame.
        """
        start_color, end_color, food_color, speed = palette
        cur = set(engine.snake)

        snake_length = len(engine.snake)
        if snake_length != self._previous_snake_length:
            self._gradient_colors = [
                gradient_color(i, snake_length, start_color, end_color) for i in range(snake_length)
            ]
            self._previous_snake_length = snake_length

        # Clear cells that were snake last frame but aren't now.
        for x, y in self._prev_snake_cells - cur:
            self.set_pixel(x, y, BLACK)

        # Repaint current snake cells.
        for i, (x, y) in enumerate(engine.snake):
            self.set_pixel(x, y, self._gradient_colors[i])

        # Food pixel — palette already carries the blink fade + color (see game.py).
        fx, fy = engine.food
        self.set_pixel(fx, fy, food_color)

        self.flush()
        self._prev_snake_cells = cur
        sleep(1 / speed)

    def reset_draw_caches(self):
        """Call between games so the new game starts blank with fresh caches."""
        self._prev_snake_cells = set()
        self._gradient_colors = []
        self._previous_snake_length = 0
        self.clear()
        self.flush()
