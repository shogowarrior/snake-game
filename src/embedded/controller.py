"""Famicom/NES 4021 shift-register controller. MicroPython-safe."""

try:
    from time import sleep_us
except ImportError:  # CPython (sim/tests) has no sleep_us
    from time import sleep

    def sleep_us(us):
        sleep(us / 1000000)


from config import CONTROLLER_BITS
from machine import Pin


class Controller:
    def __init__(self, latch, clock, data):
        self._latch = Pin(latch, Pin.OUT)
        self._clock = Pin(clock, Pin.OUT)
        # Pull-up so an idle/unconnected line reads released (buttons are active-low).
        self._data = Pin(data, Pin.IN, Pin.PULL_UP)
        self._latch.value(0)
        self._clock.value(0)
        self.by_index = {idx: name for name, idx in CONTROLLER_BITS.items()}
        self._prev = set()

    def read_bits(self):
        """Latch and clock out 8 bits; returns a list where 1 = pressed (active-low)."""
        bits = []
        self._latch.value(1)
        sleep_us(12)
        self._latch.value(0)
        sleep_us(6)
        for _ in range(8):
            bits.append(0 if self._data.value() else 1)
            self._clock.value(1)
            sleep_us(6)
            self._clock.value(0)
            sleep_us(6)
        return bits

    def _update(self, bits):
        curr = set()
        for i in range(8):
            if bits[i]:
                name = self.by_index.get(i)
                if name:
                    curr.add(name)
        edges = curr - self._prev
        self._prev = curr
        return edges, curr

    def poll(self):
        """Returns (edges, held): names newly pressed since last poll, and names currently down."""
        return self._update(self.read_bits())
