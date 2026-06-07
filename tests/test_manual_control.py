"""Manual-mode control logic via a stub controller injected into SnakeGame."""

import display
import game

from common.direction import Direction


class StubController:
    def __init__(self, scripts):
        self._scripts = list(scripts)

    def poll(self):
        return self._scripts.pop(0)


def _game(scripts, mode="manual", speed=20):
    state = game.ControlState(mode=mode, speed=speed)
    return game.SnakeGame(
        display=display.Display(),
        controller=StubController(scripts),
        state=state,
        speed=speed,
    )


def test_manual_dpad_sets_direction():
    g = _game([(set(), {"UP"})])
    g.tick()
    assert g.engine.direction == Direction.UP


def test_select_toggles_mode():
    g = _game([({"SELECT"}, {"SELECT"})], mode="auto")
    g.tick()
    assert g.state.mode == "manual"


def test_speed_up_steps_and_clamps():
    g = _game([({"A"}, {"A"})], speed=20)
    g.tick()
    assert g.state.speed == 20 + game.SPEED_STEP

    g = _game([({"A"}, {"A"})], speed=game.SPEED_MAX)
    g.tick()
    assert g.state.speed == game.SPEED_MAX


def test_speed_down_clamps_to_min():
    g = _game([({"B"}, {"B"})], speed=game.SPEED_MIN)
    g.tick()
    assert g.state.speed == game.SPEED_MIN


def test_start_signals_reset_without_stepping():
    g = _game([({"START"}, {"START"})])
    frame_before = g.engine.frame
    assert g.tick() is True
    assert g.engine.frame == frame_before
