"""Manual-mode control logic via a stub controller injected into SnakeGame."""

import display
import game

from common.direction import Direction


class StubController:
    def __init__(self, scripts):
        self._scripts = list(scripts)

    def poll(self):
        return self._scripts.pop(0)


def _game(scripts, auto=False, speed=20):
    state = game.ControlState(auto=auto, speed=speed)
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
    g = _game([({"SELECT"}, {"SELECT"})], auto=True)
    g.tick()
    assert g.state.auto is False


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


def _palette_speed(g):
    return g._palette()[3]


def test_hold_direction_rushes():
    g = _game([(set(), {"UP"})], speed=20)
    g.tick()
    assert _palette_speed(g) == 20 * game.RUSH_MULTIPLIER


def test_no_rush_when_no_direction_held():
    g = _game([(set(), set())], speed=20)
    g.tick()
    assert _palette_speed(g) == 20


def test_auto_mode_does_not_rush():
    g = _game([(set(), {"UP"})], auto=True, speed=20)
    g.tick()
    assert _palette_speed(g) == 20


def test_rush_stops_after_release():
    g = _game([(set(), {"UP"}), (set(), set())], speed=20)
    g.tick()
    assert _palette_speed(g) == 20 * game.RUSH_MULTIPLIER
    g.tick()
    assert _palette_speed(g) == 20


def test_rush_reflects_same_tick_speed_change():
    g = _game([({"A"}, {"UP"})], speed=20)  # speed-up + held direction same tick
    g.tick()
    assert g.state.speed == 20 + game.SPEED_STEP
    assert _palette_speed(g) == (20 + game.SPEED_STEP) * game.RUSH_MULTIPLIER


def test_reversed_direction_still_rushes_in_current_heading():
    g = _game([(set(), {"LEFT"})], speed=20)  # engine starts heading RIGHT
    g.tick()
    assert g.engine.direction == Direction.RIGHT  # 180 reversal rejected
    assert _palette_speed(g) == 20 * game.RUSH_MULTIPLIER  # but holding still rushes


def test_manual_reset_preserves_high_score(monkeypatch):
    saved = []
    monkeypatch.setattr(game, "load_high_score", lambda: 3)
    monkeypatch.setattr(game, "save_high_score", saved.append)
    g = _game([(set(), set())])

    g.engine.score = 7
    g.maybe_save_high_score()
    assert saved == [7]

    saved.clear()
    g.engine.score = 1
    g.maybe_save_high_score()
    assert saved == []
