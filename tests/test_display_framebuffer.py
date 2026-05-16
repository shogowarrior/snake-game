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
