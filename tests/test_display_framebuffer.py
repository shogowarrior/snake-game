"""Framebuffer primitives — pixel writes, clear, layout."""

import config
import display


def _fb_lit_cells():
    """Return the set of (x, y) cells where the framebuffer is non-black."""
    return {(i % 16, i // 16) for i, color in enumerate(display._fb) if any(color)}


def test_fb_is_256_black_cells_at_module_load():
    # Reset to a known state first — other tests may have written.
    display.clear()
    assert len(display._fb) == 256
    assert all(c == (0, 0, 0) for c in display._fb)


def test_set_pixel_writes_in_natural_coords():
    display.clear()
    display.set_pixel(3, 5, (255, 0, 0))

    # _fb is flat, indexed y*16+x.
    assert display._fb[5 * 16 + 3] == (255, 0, 0)
    # No other cells touched.
    assert _fb_lit_cells() == {(3, 5)}


def test_set_pixel_out_of_range_is_silently_ignored():
    display.clear()
    display.set_pixel(-1, 0, (255, 0, 0))
    display.set_pixel(0, -1, (255, 0, 0))
    display.set_pixel(16, 0, (255, 0, 0))
    display.set_pixel(0, 16, (255, 0, 0))
    display.set_pixel(99, 99, (255, 0, 0))

    # Framebuffer untouched.
    assert all(c == (0, 0, 0) for c in display._fb)


def test_clear_zeros_every_cell():
    # Fill some cells.
    display.set_pixel(0, 0, (1, 2, 3))
    display.set_pixel(15, 15, (4, 5, 6))
    display.set_pixel(7, 8, (9, 10, 11))

    display.clear()

    assert all(c == (0, 0, 0) for c in display._fb)


def _serpentine(px, py):
    """Reference serpentine: panel (col, row) -> flat NP index."""
    return py * 16 + (px if py % 2 == 0 else 15 - px)


def test_compute_lut_rotation_0_is_pure_serpentine():
    lut = display._compute_lut("0")
    assert lut[0 * 16 + 0] == _serpentine(0, 0)  # top-left
    assert lut[0 * 16 + 15] == _serpentine(15, 0)  # top-right
    assert lut[15 * 16 + 0] == _serpentine(0, 15)  # bottom-left
    assert lut[15 * 16 + 15] == _serpentine(15, 15)  # bottom-right
    # Odd-row cell (py=1, px=3) should flip via serpentine.
    assert lut[1 * 16 + 3] == _serpentine(3, 1)  # i.e. 16 + (15-3) = 28


def test_compute_lut_rotation_90cw_maps_game_to_rotated_panel():
    lut = display._compute_lut("90CW")
    # game (x, y) -> panel (15-y, x)
    assert lut[0 * 16 + 0] == _serpentine(15, 0)
    assert lut[0 * 16 + 15] == _serpentine(15, 15)
    assert lut[15 * 16 + 0] == _serpentine(0, 0)
    assert lut[15 * 16 + 15] == _serpentine(0, 15)


def test_compute_lut_rotation_180_flips_both_axes():
    lut = display._compute_lut("180")
    # game (x, y) -> panel (15-x, 15-y)
    assert lut[0 * 16 + 0] == _serpentine(15, 15)
    assert lut[0 * 16 + 15] == _serpentine(0, 15)
    assert lut[15 * 16 + 0] == _serpentine(15, 0)
    assert lut[15 * 16 + 15] == _serpentine(0, 0)


def test_compute_lut_rotation_90ccw_maps_game_to_rotated_panel():
    lut = display._compute_lut("90CCW")
    # game (x, y) -> panel (y, 15-x)
    assert lut[0 * 16 + 0] == _serpentine(0, 15)
    assert lut[0 * 16 + 15] == _serpentine(0, 0)
    assert lut[15 * 16 + 0] == _serpentine(15, 15)
    assert lut[15 * 16 + 15] == _serpentine(15, 0)


def test_compute_lut_is_a_permutation_of_256_indices():
    # Every panel slot must be covered exactly once, for every rotation.
    for rot in ("0", "90CW", "180", "90CCW"):
        lut = display._compute_lut(rot)
        assert len(lut) == 256
        assert sorted(lut) == list(range(256))


def test_flush_copies_fb_to_np_via_lut():
    display.clear()
    display.set_pixel(0, 0, (10, 20, 30))
    display.set_pixel(15, 15, (40, 50, 60))
    display.set_pixel(3, 1, (70, 80, 90))  # odd row, exercises serpentine

    display.flush()

    # The framebuffer index for each cell:
    assert display.NP[display._lut[0 * 16 + 0]] == (10, 20, 30)
    assert display.NP[display._lut[15 * 16 + 15]] == (40, 50, 60)
    assert display.NP[display._lut[1 * 16 + 3]] == (70, 80, 90)


def test_flush_writes_every_cell_not_just_lit_ones():
    # After a clear+flush, every NP cell should be (0, 0, 0).
    display.clear()
    # Pre-pollute NP to confirm flush overwrites everything.
    for i in range(256):
        display.NP[i] = (99, 99, 99)
    display.flush()
    for i in range(256):
        assert display.NP[i] == (0, 0, 0), f"NP[{i}] not cleared"


def test_display_char_writes_pattern_to_fb_at_offset():
    display.clear()
    # "1" pattern is [(0,1,0),(1,1,0),(0,1,0),(0,1,0),(1,1,1)]. At offset
    # (0, 0), scale=1, this puts lit pixels at the 'on' bits of the pattern.
    display.display_char("1", offset_x=0, offset_y=0, color=(255, 0, 0), scale=1)

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
    actual_lit = {(i % 16, i // 16) for i, c in enumerate(display._fb) if any(c)}
    assert actual_lit == expected_lit
    # All lit cells use the requested color.
    for x, y in expected_lit:
        assert display._fb[y * 16 + x] == (255, 0, 0)


def test_display_char_accepts_callable_color():
    display.clear()

    def color_for(x, y):
        return (x, y, 0)

    display.display_char("1", offset_x=0, offset_y=0, color=color_for, scale=1)

    # Each lit pixel got the color from its own (x, y).
    assert display._fb[0 * 16 + 1] == (1, 0, 0)
    assert display._fb[1 * 16 + 0] == (0, 1, 0)
    assert display._fb[4 * 16 + 2] == (2, 4, 0)


def test_display_message_lays_out_chars_left_to_right():
    display.clear()
    # advance is 4*scale = 4 for scale=1. Two chars at offsets 0 and 4.
    display.display_message("12", offset_x=0, offset_y=0, color=(1, 1, 1), scale=1)

    # First char "1" at x=0..2; second char "2" at x=4..6 (3-wide patterns).
    lit_x = sorted({i % 16 for i, c in enumerate(display._fb) if any(c)})
    # We expect lit cells in both 0..2 and 4..6 ranges, and nothing at x=3 or x>=7.
    assert 0 in lit_x or 1 in lit_x or 2 in lit_x
    assert 4 in lit_x or 5 in lit_x or 6 in lit_x
    assert 3 not in lit_x
    for x in lit_x:
        assert x < 7


def test_display_message_calls_flush():
    # After display_message, NP should reflect the framebuffer (it called flush).
    display.clear()
    # Pre-pollute NP so we can confirm flush ran.
    for i in range(256):
        display.NP[i] = (99, 99, 99)

    display.display_message("1", offset_x=0, offset_y=0, color=(7, 7, 7), scale=1)

    # At least one NP cell should be (7, 7, 7) (the lit pixels), and the
    # remaining NP cells should be (0, 0, 0) (cleared by the framebuffer flush).
    sevens = sum(1 for c in display.NP.buf if c == (7, 7, 7))
    nines = sum(1 for c in display.NP.buf if c == (99, 99, 99))
    assert sevens > 0
    assert nines == 0  # all the pre-pollution got overwritten


def test_display_scores_clears_then_writes_score():
    # Pre-pollute the framebuffer with non-zero pixels.
    for i in range(256):
        display._fb[i] = (33, 33, 33)

    display.display_scores(high_score=0, current_score=12)

    # Pollution removed: only score pixels are lit.
    lit_count = sum(1 for c in display._fb if any(c))
    assert 0 < lit_count < 256


def test_display_scores_writes_two_digits_for_two_digit_score():
    display.clear()
    display.display_scores(high_score=0, current_score=12)

    # Two digit areas in the framebuffer, separated by a gap.
    lit_x = {i % 16 for i, c in enumerate(display._fb) if any(c)}
    # Score is centered: width = 2*4*2 - 2 = 14, offset_x = (16-14)//2 = 1.
    # First digit x range: 1..6 (cols 0,1,2 of "1" * scale 2).
    # Second digit x range: 9..14.
    assert lit_x.issubset(set(range(1, 7)) | set(range(9, 15)))
    assert lit_x & set(range(1, 7)), "first digit area not lit"
    assert lit_x & set(range(9, 15)), "second digit area not lit"


def test_display_scores_gradient_endpoints_match_config():
    display.clear()
    display.display_scores(high_score=0, current_score=12)

    # The leftmost lit column should carry SCORE_GRADIENT_START, the rightmost
    # lit column should carry SCORE_GRADIENT_END.
    lit_by_x = {}
    for i, c in enumerate(display._fb):
        if any(c):
            x = i % 16
            lit_by_x.setdefault(x, c)
    leftmost_x = min(lit_by_x)
    rightmost_x = max(lit_by_x)
    assert lit_by_x[leftmost_x] == config.SCORE_GRADIENT_START
    assert lit_by_x[rightmost_x] == config.SCORE_GRADIENT_END


class _FakeEngine:
    """Minimal stand-in for SnakeEngine — just exposes the attributes draw_snake reads."""

    def __init__(self, snake, food):
        self.snake = snake
        self.food = food


def test_draw_snake_writes_snake_cells_and_food_to_fb():
    display.clear()
    display.reset_draw_caches()

    engine = _FakeEngine(snake=[(5, 5), (5, 6), (5, 7)], food=(10, 10))
    palette = ((255, 0, 0), (0, 0, 64), (0, 255, 0), 1000)
    # speed=1000 so the sleep is ~1ms; doesn't matter for the framebuffer test.

    display.draw_snake(engine, palette)

    # Snake cells are lit with the gradient.
    for x, y in engine.snake:
        assert any(display._fb[y * 16 + x]), f"snake cell ({x},{y}) not lit"
    # Food cell is the food color.
    fx, fy = engine.food
    assert display._fb[fy * 16 + fx] == (0, 255, 0)


def test_draw_snake_clears_vacated_cells_in_fb():
    display.clear()
    display.reset_draw_caches()

    # First frame: snake at A.
    e1 = _FakeEngine(snake=[(5, 5), (5, 6)], food=(10, 10))
    display.draw_snake(e1, ((255, 0, 0), (0, 0, 64), (0, 255, 0), 1000))
    assert any(display._fb[6 * 16 + 5])

    # Second frame: snake moved; (5, 6) is vacated.
    e2 = _FakeEngine(snake=[(5, 4), (5, 5)], food=(10, 10))
    display.draw_snake(e2, ((255, 0, 0), (0, 0, 64), (0, 255, 0), 1000))

    # (5, 6) should now be black.
    assert display._fb[6 * 16 + 5] == (0, 0, 0)
