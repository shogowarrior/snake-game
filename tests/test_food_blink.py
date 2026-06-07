"""Food blink: the palette food color fades to black at each cycle boundary."""

import display
import game


def test_food_render_color_full_at_mid_cycle_black_at_ends():
    d = display.Display()
    g = game.SnakeGame(display=d, speed=10000)
    g.food_color = (200, 100, 50)

    g.engine.frame = game.FOOD_BLINK_FRAMES // 2
    assert g._food_render_color() == (200, 100, 50)

    g.engine.frame = 0
    assert g._food_render_color() == (0, 0, 0)
    g.engine.frame = game.FOOD_BLINK_FRAMES
    assert g._food_render_color() == (0, 0, 0)


def test_food_cell_is_black_in_fb_at_cycle_boundary():
    d = display.Display()
    g = game.SnakeGame(display=d, speed=10000)
    fx, fy = g.engine.food
    g.food_color = (200, 100, 50)

    g.engine.frame = game.FOOD_BLINK_FRAMES // 2
    d.draw_snake(g.engine, g._palette())
    assert d._fb[fy * 16 + fx] == (200, 100, 50)

    g.engine.frame = 0
    d.draw_snake(g.engine, g._palette())
    assert d._fb[fy * 16 + fx] == (0, 0, 0)
