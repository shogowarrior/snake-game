from random import choice

from common.direction import Direction

_DELTAS = {
    Direction.RIGHT: (1, 0),
    Direction.LEFT: (-1, 0),
    Direction.DOWN: (0, 1),
    Direction.UP: (0, -1),
}

_OPPOSITES = {
    Direction.UP: Direction.DOWN,
    Direction.DOWN: Direction.UP,
    Direction.LEFT: Direction.RIGHT,
    Direction.RIGHT: Direction.LEFT,
}


class SnakeEngine:
    """Headless snake on a wrapping torus. Cell-space (x=col, y=row), 0..size-1.

    Pure Python, MicroPython-safe (no numpy, typing, dataclasses, enum).
    Both renderers (pygame on desktop, NeoPixel on embedded) drive the same engine.
    """

    def __init__(self, size=16, start=None):
        self.size = size
        head = start if start is not None else (size // 2, size // 2)
        self.snake = [head]
        self.direction = Direction.RIGHT
        self.score = 0
        self.frame = 0
        self.game_over = False
        self.food = None
        self._place_food()

    @property
    def head(self):
        return self.snake[0]

    def set_direction(self, direction):
        """Set heading. Rejects 180° reversals (no-op if direction opposes current)."""
        if _OPPOSITES.get(self.direction) == direction:
            return
        self.direction = direction

    def step(self, direction=None):
        """Advance one tick. Returns (game_over, reward, score).

        reward is +10 on food, -10 on game-over, 0 otherwise. Callers that don't
        need reward (the embedded build) can ignore it.
        """
        if self.game_over:
            return True, 0, self.score
        if direction is not None:
            self.set_direction(direction)
        self.frame += 1

        x, y = self.head
        dx, dy = _DELTAS[self.direction]
        new_head = ((x + dx) % self.size, (y + dy) % self.size)

        # Tail cell is about to vacate on this tick — exclude it so tail-following is legal.
        if new_head in self.snake[:-1]:
            self.game_over = True
            return True, -10, self.score

        self.snake.insert(0, new_head)
        if new_head == self.food:
            self.score += 1
            self._place_food()
            return self.game_over, 10, self.score

        self.snake.pop()
        return False, 0, self.score

    def _place_food(self):
        free = [(x, y) for x in range(self.size) for y in range(self.size)
                if (x, y) not in self.snake]
        if not free:
            self.game_over = True
            self.food = self.head
            return
        self.food = choice(free)
