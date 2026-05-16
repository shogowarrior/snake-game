from sim import screen


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
        screen.flush(self.buf)
