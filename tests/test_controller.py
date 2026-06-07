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


class _ScriptedData:
    """Fake DATA pin returning a preset value per read (active-low: 0 = pressed)."""

    def __init__(self, line_values):
        self._values = line_values
        self._i = 0

    def value(self, v=None):
        if v is not None:
            return None
        b = self._values[self._i]
        self._i += 1
        return b


def test_read_bits_decodes_active_low_in_order():
    c = _make()
    # DATA reads low (0) for A (bit 0) and RIGHT (bit 7); high (1) elsewhere.
    c._data = _ScriptedData([0, 1, 1, 1, 1, 1, 1, 0])
    bits = c.read_bits()
    assert bits == [1, 0, 0, 0, 0, 0, 0, 1]
    # And the decode maps those raw bits back to button names.
    assert c._update(bits)[1] == {"A", "RIGHT"}


def test_read_bits_all_released_is_all_zero():
    c = _make()
    c._data = _ScriptedData([1] * 8)
    assert c.read_bits() == [0] * 8
