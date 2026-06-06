from random import random, uniform

from config import SCORE_DISPLAY_SECONDS, SPEED
from greedy_policy import GreedyPolicy
from learned_policy import LearnedPolicy

from common.colors import hsv_to_rgb
from common.engine import SnakeEngine

GAME_SIZE = 16
HIGH_SCORE_FILE = "high_score.txt"

_POLICIES = {
    "greedy": GreedyPolicy,
    "learned": LearnedPolicy,
}


def load_high_score():
    try:
        with open(HIGH_SCORE_FILE) as f:
            return int(f.read())
    except (OSError, ValueError):
        return 0


def save_high_score(value):
    try:
        with open(HIGH_SCORE_FILE, "w") as f:
            f.write(str(value))
    except OSError:
        print("Error saving high score.")


class SnakeGame:
    """Embedded adapter: drives a SnakeEngine with a Policy, renders gradient
    snake + food via the injected Display, persists high score on game-over.
    """

    def __init__(self, *, display, policy_name="greedy", speed=SPEED):
        if policy_name not in _POLICIES:
            raise ValueError("Unknown policy: " + repr(policy_name) + ". Valid: " + ", ".join(sorted(_POLICIES)))

        self.display = display
        self.engine = SnakeEngine(size=GAME_SIZE)
        self.policy = _POLICIES[policy_name]()
        self.speed = speed

        # Per-game two-hue palette: start_color -> head (bright), end_color -> tail (dim).
        self.start_color = hsv_to_rgb(random(), 1.0, uniform(0.55, 1.00))
        self.end_color = hsv_to_rgb(random(), 1.0, uniform(0.08, 0.25))
        self.food_color = self._new_food_color()

        self.display.reset_draw_caches()

    def _new_food_color(self):
        return hsv_to_rgb(random(), 1.0, uniform(0.55, 0.85))

    def _palette(self):
        return (self.start_color, self.end_color, self.food_color, self.speed)

    def tick(self):
        """One frame: policy -> engine -> renderer."""
        direction = self.policy.decide(self.engine)
        prev_food = self.engine.food
        self.engine.step(direction)

        # Refresh food color when the snake actually ate.
        if self.engine.food != prev_food:
            self.food_color = self._new_food_color()

        self.display.draw_snake(self.engine, self._palette())

    def start_game(self):
        self.engine.score = 0
        self.high_score = load_high_score()

    def end_game(self):
        from time import sleep

        current_score = self.engine.score
        if current_score > load_high_score():
            save_high_score(current_score)
        self.display.display_scores(current_score, self.start_color, self.end_color)
        sleep(SCORE_DISPLAY_SECONDS)
