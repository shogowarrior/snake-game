from random import random, uniform

from config import (
    CONTROL_MODE,
    FOOD_BLINK,
    FOOD_BLINK_FRAMES,
    SCORE_DISPLAY_SECONDS,
    SPEED,
    SPEED_MAX,
    SPEED_MIN,
    SPEED_STEP,
)
from greedy_policy import GreedyPolicy
from learned_policy import LearnedPolicy

from common.colors import hsv_to_rgb
from common.direction import Direction
from common.engine import SnakeEngine

GAME_SIZE = 16
HIGH_SCORE_FILE = "high_score.txt"

_POLICIES = {
    "greedy": GreedyPolicy,
    "learned": LearnedPolicy,
}

_DPAD = {
    "UP": Direction.UP,
    "DOWN": Direction.DOWN,
    "LEFT": Direction.LEFT,
    "RIGHT": Direction.RIGHT,
}


def _dpad_direction(held):
    """First D-pad button held, in fixed priority; None keeps the current heading."""
    for name in ("UP", "DOWN", "LEFT", "RIGHT"):
        if name in held:
            return _DPAD[name]
    return None


class ControlState:
    """Mode + live speed shared across games so SELECT/A/B persist past a death."""

    def __init__(self, mode=CONTROL_MODE, speed=SPEED):
        self.mode = mode
        self.speed = speed


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

    def __init__(self, *, display, policy_name="greedy", speed=SPEED, controller=None, state=None):
        if policy_name not in _POLICIES:
            raise ValueError("Unknown policy: " + repr(policy_name) + ". Valid: " + ", ".join(sorted(_POLICIES)))

        self.display = display
        self.engine = SnakeEngine(size=GAME_SIZE)
        self.policy = _POLICIES[policy_name]()
        self.controller = controller
        if state is None and controller is not None:
            state = ControlState(speed=speed)
        self.state = state
        self.speed = state.speed if state is not None else speed

        # Per-game two-hue palette: start_color -> head (bright), end_color -> tail (dim).
        self.start_color = hsv_to_rgb(random(), 1.0, uniform(0.55, 1.00))
        self.end_color = hsv_to_rgb(random(), 1.0, uniform(0.08, 0.25))
        self.food_color = self._new_food_color()
        self._food_frame = 0  # engine.frame when current food appeared; blink phase resets here

        self.display.reset_draw_caches()

    def _new_food_color(self):
        return hsv_to_rgb(random(), 1.0, uniform(0.55, 0.85))

    def _food_render_color(self):
        """food_color faded by the blink envelope: black when food appears, full at mid-cycle."""
        if not FOOD_BLINK:
            return self.food_color
        age = self.engine.frame - self._food_frame
        p = (age % FOOD_BLINK_FRAMES) / FOOD_BLINK_FRAMES
        factor = 1.0 - 2.0 * abs(p - 0.5)
        r, g, b = self.food_color
        return (int(r * factor), int(g * factor), int(b * factor))

    def _palette(self):
        return (self.start_color, self.end_color, self._food_render_color(), self.speed)

    def _handle_input(self):
        """Apply controller input. Returns (direction, reset): reset True means START."""
        edges, held = self.controller.poll()
        if "SELECT" in edges:
            self.state.mode = "manual" if self.state.mode == "auto" else "auto"
        if "A" in edges:
            self.state.speed = min(SPEED_MAX, self.state.speed + SPEED_STEP)
        if "B" in edges:
            self.state.speed = max(SPEED_MIN, self.state.speed - SPEED_STEP)
        self.speed = self.state.speed
        if "START" in edges:
            return None, True
        if self.state.mode == "manual":
            return _dpad_direction(held), False
        return self.policy.decide(self.engine), False

    def tick(self):
        """One frame: input/policy -> engine -> renderer. Returns True if START was pressed."""
        if self.controller is not None:
            direction, reset = self._handle_input()
            if reset:
                return True
        else:
            direction = self.policy.decide(self.engine)
        prev_food = self.engine.food
        self.engine.step(direction)

        # New random food color on eat (phase resets to black), or at each blink's black instant.
        if self.engine.food != prev_food:
            self.food_color = self._new_food_color()
            self._food_frame = self.engine.frame
        elif FOOD_BLINK and (self.engine.frame - self._food_frame) % FOOD_BLINK_FRAMES == 0:
            self.food_color = self._new_food_color()

        self.display.draw_snake(self.engine, self._palette())
        return False

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
