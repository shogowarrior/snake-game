"""Framebuffer primitives — pixel writes, clear, layout.

Each test that touches mutable state uses a fresh `Display` instance via the
`d` fixture. Module-level helpers (`_compute_lut`) are still referenced through
the `display` module.
"""

import display
import pytest


@pytest.fixture
def d():
    return display.Display()


def _fb_lit_cells(d):
    """Return the set of (x, y) cells where the framebuffer is non-black."""
    return {(i % 16, i // 16) for i, color in enumerate(d._fb) if any(color)}


def test_fb_is_256_black_cells_at_init(d):
    assert len(d._fb) == 256
    assert all(c == (0, 0, 0) for c in d._fb)


def test_set_pixel_writes_in_natural_coords(d):
    d.set_pixel(3, 5, (255, 0, 0))

    # _fb is flat, indexed y*16+x.
    assert d._fb[5 * 16 + 3] == (255, 0, 0)
    # No other cells touched.
    assert _fb_lit_cells(d) == {(3, 5)}


def test_set_pixel_out_of_range_is_silently_ignored(d):
    d.set_pixel(-1, 0, (255, 0, 0))
    d.set_pixel(0, -1, (255, 0, 0))
    d.set_pixel(16, 0, (255, 0, 0))
    d.set_pixel(0, 16, (255, 0, 0))
    d.set_pixel(99, 99, (255, 0, 0))

    # Framebuffer untouched.
    assert all(c == (0, 0, 0) for c in d._fb)


def test_clear_zeros_every_cell(d):
    d.set_pixel(0, 0, (1, 2, 3))
    d.set_pixel(15, 15, (4, 5, 6))
    d.set_pixel(7, 8, (9, 10, 11))

    d.clear()

    assert all(c == (0, 0, 0) for c in d._fb)


def _serpentine(px, py):
    """Reference column-serpentine: panel (col, row) -> flat NP index."""
    return px * 16 + (py if px % 2 == 0 else 15 - py)


def test_compute_lut_rotation_0_is_pure_serpentine():
    lut = display._compute_lut(0)
    assert lut[0 * 16 + 0] == _serpentine(0, 0)
    assert lut[0 * 16 + 15] == _serpentine(15, 0)
    assert lut[15 * 16 + 0] == _serpentine(0, 15)
    assert lut[15 * 16 + 15] == _serpentine(15, 15)
    # Odd-column cell (px=3, py=1) should flip via serpentine.
    assert lut[1 * 16 + 3] == _serpentine(3, 1)


def test_compute_lut_rotation_90cw_maps_game_to_rotated_panel():
    lut = display._compute_lut(90)
    # game (x, y) -> panel (15-y, x)
    assert lut[0 * 16 + 0] == _serpentine(15, 0)
    assert lut[0 * 16 + 15] == _serpentine(15, 15)
    assert lut[15 * 16 + 0] == _serpentine(0, 0)
    assert lut[15 * 16 + 15] == _serpentine(0, 15)


def test_compute_lut_rotation_180_flips_both_axes():
    lut = display._compute_lut(180)
    # game (x, y) -> panel (15-x, 15-y)
    assert lut[0 * 16 + 0] == _serpentine(15, 15)
    assert lut[0 * 16 + 15] == _serpentine(0, 15)
    assert lut[15 * 16 + 0] == _serpentine(15, 0)
    assert lut[15 * 16 + 15] == _serpentine(0, 0)


def test_compute_lut_rotation_90ccw_maps_game_to_rotated_panel():
    lut = display._compute_lut(270)
    # game (x, y) -> panel (y, 15-x)
    assert lut[0 * 16 + 0] == _serpentine(0, 15)
    assert lut[0 * 16 + 15] == _serpentine(0, 0)
    assert lut[15 * 16 + 0] == _serpentine(15, 15)
    assert lut[15 * 16 + 15] == _serpentine(15, 0)


def test_compute_lut_is_a_permutation_of_256_indices():
    for rot in (0, 90, 180, 270):
        lut = display._compute_lut(rot)
        assert len(lut) == 256
        assert sorted(lut) == list(range(256))


def test_flush_copies_fb_to_np_via_lut(d):
    d.set_pixel(0, 0, (10, 20, 30))
    d.set_pixel(15, 15, (40, 50, 60))
    d.set_pixel(3, 1, (70, 80, 90))  # odd row, exercises serpentine

    d.flush()

    assert d.np[d._lut[0 * 16 + 0]] == (10, 20, 30)
    assert d.np[d._lut[15 * 16 + 15]] == (40, 50, 60)
    assert d.np[d._lut[1 * 16 + 3]] == (70, 80, 90)


def test_flush_writes_every_cell_not_just_lit_ones(d):
    # After a clear+flush, every NP cell should be (0, 0, 0).
    # Pre-pollute NP to confirm flush overwrites everything.
    for i in range(256):
        d.np[i] = (99, 99, 99)
    d.flush()
    for i in range(256):
        assert d.np[i] == (0, 0, 0), f"NP[{i}] not cleared"


def test_display_char_writes_pattern_to_fb_at_offset(d):
    # "1" pattern is [(0,1,0),(1,1,0),(0,1,0),(0,1,0),(1,1,1)]. At offset
    # (0, 0), scale=1, this puts lit pixels at the 'on' bits of the pattern.
    d.display_char("1", offset_x=0, offset_y=0, color=(255, 0, 0), scale=1)

    expected_lit = {
        (1, 0),  # row 0: (0,1,0)
        (0, 1),
        (1, 1),  # row 1: (1,1,0)
        (1, 2),  # row 2: (0,1,0)
        (1, 3),  # row 3: (0,1,0)
        (0, 4),
        (1, 4),
        (2, 4),  # row 4: (1,1,1)
    }
    actual_lit = {(i % 16, i // 16) for i, c in enumerate(d._fb) if any(c)}
    assert actual_lit == expected_lit
    for x, y in expected_lit:
        assert d._fb[y * 16 + x] == (255, 0, 0)


def test_display_char_accepts_callable_color(d):
    def color_for(x, y):
        return (x, y, 0)

    d.display_char("1", offset_x=0, offset_y=0, color=color_for, scale=1)

    # Each lit pixel got the color from its own (x, y).
    assert d._fb[0 * 16 + 1] == (1, 0, 0)
    assert d._fb[1 * 16 + 0] == (0, 1, 0)
    assert d._fb[4 * 16 + 2] == (2, 4, 0)


def test_display_message_lays_out_chars_left_to_right(d):
    # advance is 4*scale = 4 for scale=1. Two chars at offsets 0 and 4.
    d.display_message("12", offset_x=0, offset_y=0, color=(1, 1, 1), scale=1)

    # First char "1" at x=0..2; second char "2" at x=4..6 (3-wide patterns).
    lit_x = sorted({i % 16 for i, c in enumerate(d._fb) if any(c)})
    assert 0 in lit_x or 1 in lit_x or 2 in lit_x
    assert 4 in lit_x or 5 in lit_x or 6 in lit_x
    assert 3 not in lit_x
    for x in lit_x:
        assert x < 7


def test_display_message_calls_flush(d):
    # After display_message, NP should reflect the framebuffer (it called flush).
    # Pre-pollute NP so we can confirm flush ran.
    for i in range(256):
        d.np[i] = (99, 99, 99)

    d.display_message("1", offset_x=0, offset_y=0, color=(7, 7, 7), scale=1)

    # At least one NP cell should be (7, 7, 7) (the lit pixels), and the
    # remaining NP cells should be (0, 0, 0) (cleared by the framebuffer flush).
    sevens = sum(1 for c in d.np.buf if c == (7, 7, 7))
    nines = sum(1 for c in d.np.buf if c == (99, 99, 99))
    assert sevens > 0
    assert nines == 0  # all the pre-pollution got overwritten


def test_display_scores_clears_then_writes_score(d):
    # Pre-pollute the framebuffer with non-zero pixels.
    for i in range(256):
        d._fb[i] = (33, 33, 33)

    d.display_scores(current_score=12, start_color=(0, 120, 220), end_color=(220, 0, 140))

    # Pollution removed: only score pixels are lit.
    lit_count = sum(1 for c in d._fb if any(c))
    assert 0 < lit_count < 256


def test_display_scores_writes_two_digits_for_two_digit_score(d):
    d.display_scores(current_score=12, start_color=(0, 120, 220), end_color=(220, 0, 140))

    # Two digit areas in the framebuffer, separated by a gap.
    lit_x = {i % 16 for i, c in enumerate(d._fb) if any(c)}
    # Score is centered: width = 2*4*2 - 2 = 14, offset_x = (16-14)//2 = 1.
    # First digit x range: 1..6 (cols 0,1,2 of "1" * scale 2).
    # Second digit x range: 9..14.
    assert lit_x.issubset(set(range(1, 7)) | set(range(9, 15)))
    assert lit_x & set(range(1, 7)), "first digit area not lit"
    assert lit_x & set(range(9, 15)), "second digit area not lit"


def test_display_scores_gradient_endpoints_match_args(d):
    start_color = (0, 120, 220)
    end_color = (220, 0, 140)
    d.display_scores(current_score=12, start_color=start_color, end_color=end_color)

    # Leftmost lit column carries start_color, rightmost carries end_color.
    lit_by_x = {}
    for i, c in enumerate(d._fb):
        if any(c):
            x = i % 16
            lit_by_x.setdefault(x, c)
    leftmost_x = min(lit_by_x)
    rightmost_x = max(lit_by_x)
    assert lit_by_x[leftmost_x] == start_color
    assert lit_by_x[rightmost_x] == end_color


class _FakeEngine:
    """Minimal stand-in for SnakeEngine — just exposes the attributes draw_snake reads."""

    def __init__(self, snake, food, frame=0):
        self.snake = snake
        self.food = food
        self.frame = frame


def test_draw_snake_writes_snake_cells_and_food_to_fb(d):
    engine = _FakeEngine(snake=[(5, 5), (5, 6), (5, 7)], food=(10, 10))
    palette = ((255, 0, 0), (0, 0, 64), (0, 255, 0), 1000)
    # speed=1000 so the sleep is ~1ms; doesn't matter for the framebuffer test.

    d.draw_snake(engine, palette)

    # Snake cells are lit with the gradient.
    for x, y in engine.snake:
        assert any(d._fb[y * 16 + x]), f"snake cell ({x},{y}) not lit"
    # Food cell is the food color.
    fx, fy = engine.food
    assert d._fb[fy * 16 + fx] == (0, 255, 0)


def test_draw_snake_clears_vacated_cells_in_fb(d):
    # First frame: snake at A.
    e1 = _FakeEngine(snake=[(5, 5), (5, 6)], food=(10, 10))
    d.draw_snake(e1, ((255, 0, 0), (0, 0, 64), (0, 255, 0), 1000))
    assert any(d._fb[6 * 16 + 5])

    # Second frame: snake moved; (5, 6) is vacated.
    e2 = _FakeEngine(snake=[(5, 4), (5, 5)], food=(10, 10))
    d.draw_snake(e2, ((255, 0, 0), (0, 0, 64), (0, 255, 0), 1000))

    # (5, 6) should now be black.
    assert d._fb[6 * 16 + 5] == (0, 0, 0)
