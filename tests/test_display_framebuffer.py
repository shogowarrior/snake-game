"""Framebuffer primitives — pixel writes, clear, layout."""

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
