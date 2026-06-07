"""Keyboard-backed stand-in for embedded/controller.py, for the sim.

Maps pygame keys to the 8 controller buttons so manual mode can be tested on a
laptop: arrows = D-pad, Enter = START, Right-Shift = SELECT, Z = A, X = B.
"""

import pygame

_KEYMAP = {
    "UP": pygame.K_UP,
    "DOWN": pygame.K_DOWN,
    "LEFT": pygame.K_LEFT,
    "RIGHT": pygame.K_RIGHT,
    "START": pygame.K_RETURN,
    "SELECT": pygame.K_RSHIFT,
    "A": pygame.K_z,
    "B": pygame.K_x,
}


class Controller:
    def __init__(self, *args, **kwargs):
        self._prev = set()

    def poll(self):
        if not pygame.get_init():
            return set(), set()
        pygame.event.pump()
        keys = pygame.key.get_pressed()
        curr = {name for name, key in _KEYMAP.items() if keys[key]}
        edges = curr - self._prev
        self._prev = curr
        return edges, curr
