import time

from sim import screen

# ESP32 spends ~49 ms/frame on MicroPython compute + LED write the host doesn't; emulate it so the sim runs at device cadence.
DEVICE_OVERHEAD_MS = 49


class NeoPixel:
    """Drop-in replacement for `neopixel.NeoPixel` that pushes to a pygame window
    on each `write()`. Indexing matches the device — same buffer layout, same
    serpentine, same orientation — so embedded/display.py runs unmodified.
    """

    def __init__(self, pin, n):
        self.n = n
        self.buf = [(0, 0, 0)] * n

    def __setitem__(self, i, color):
        self.buf[i] = tuple(color)

    def __getitem__(self, i):
        return self.buf[i]

    def fill(self, color):
        c = tuple(color)
        for i in range(self.n):
            self.buf[i] = c

    def write(self):
        time.sleep(DEVICE_OVERHEAD_MS / 1000)
        screen.flush(self.buf)
