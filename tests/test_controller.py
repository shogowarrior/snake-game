"""Controller bit decode + edge detection (the pure _update seam)."""

import controller


def _make():
    return controller.Controller(18, 5, 19)


def test_update_decodes_pressed_bits():
    c = _make()
    bits = [0] * 8
    bits[0] = 1  # A
    bits[4] = 1  # UP
    edges, held = c._update(bits)
    assert edges == {"A", "UP"}
    assert held == {"A", "UP"}


def test_edge_fires_once_while_held():
    c = _make()
    held_bits = [0] * 8
    held_bits[2] = 1  # SELECT
    assert c._update(held_bits)[0] == {"SELECT"}
    edges, held = c._update(held_bits)
    assert edges == set()
    assert held == {"SELECT"}


def test_edge_refires_after_release():
    c = _make()
    bits = [0] * 8
    bits[3] = 1  # START
    c._update(bits)
    c._update([0] * 8)
    assert c._update(bits)[0] == {"START"}
