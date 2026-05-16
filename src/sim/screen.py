"""Pygame backend for the fake NeoPixel. Lazy-inits on first flush so importing
the module never opens a window (safe on headless machines that only do
import-time checks).
"""

import pygame

SIZE = 16  # 16x16 panel
CELL = 32  # px per LED
W = SIZE * CELL
H = SIZE * CELL
BG = (8, 8, 10)  # near-black panel background
BEZEL = (18, 18, 22)

_screen = None


def _init():
    global _screen  # noqa: PLW0603
    if _screen is not None:
        return
    pygame.init()
    _screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Snake — LED Matrix Sim")


def _index_to_physical(i):
    """Inverse of the serpentine in embedded/display.py: index -> (px, py).

    The embedded code already rotated game-space and applied serpentine before
    indexing, so drawing at (px, py) renders the panel as the user would see
    it physically.
    """
    py = i // SIZE
    off = i % SIZE
    px = off if py % 2 == 0 else (SIZE - 1 - off)
    return px, py


def flush(buffer):
    """Render the 256-pixel buffer. Called from fake_neopixel.NeoPixel.write()."""
    _init()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            raise SystemExit(0)

    _screen.fill(BG)
    radius = CELL // 2 - 4
    inner_r = CELL // 6

    for i, color in enumerate(buffer):
        px, py = _index_to_physical(i)
        cx = px * CELL + CELL // 2
        cy = py * CELL + CELL // 2

        # Subtle bezel under every LED so off-pixels still read as a panel cell.
        pygame.draw.rect(
            _screen,
            BEZEL,
            (px * CELL + 1, py * CELL + 1, CELL - 2, CELL - 2),
            border_radius=4,
        )

        if any(color):
            pygame.draw.circle(_screen, color, (cx, cy), radius)
            # Brighter highlight for an LED-like specular feel.
            highlight = tuple(min(255, c + 80) for c in color)
            pygame.draw.circle(_screen, highlight, (cx, cy), inner_r)

    pygame.display.flip()
