from common.direction import Direction
from common.policy import Policy

_DELTAS = {
    Direction.UP: (0, -1),
    Direction.DOWN: (0, 1),
    Direction.LEFT: (-1, 0),
    Direction.RIGHT: (1, 0),
}


class GreedyPolicy(Policy):
    """Wrapped-distance greedy AI. Picks the legal neighbour that minimises
    Manhattan distance to the food, with axis-wise wrapping.

    Behaviour matches the embedded `ai_move()` in the previous codebase exactly.
    """

    def decide(self, engine):
        head_x, head_y = engine.head
        food_x, food_y = engine.food
        size = engine.size
        snake = engine.snake

        def wrapped(a, b):
            d = abs(a - b)
            return min(d, size - d)

        candidates = []
        for direction, (dx, dy) in _DELTAS.items():
            nx, ny = (head_x + dx) % size, (head_y + dy) % size
            if (nx, ny) in snake:
                continue
            dist = wrapped(nx, food_x) + wrapped(ny, food_y)
            candidates.append((dist, direction))

        if not candidates:
            return None
        candidates.sort(key=lambda t: t[0])
        return candidates[0][1]
