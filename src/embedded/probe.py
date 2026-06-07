"""Serial button probe: prints each newly-pressed button so you can map your clone.

Run on-device (mpremote run probe.py). Press each button; note the bit index it
reports, then fix CONTROLLER_BITS in config.py.
"""

from time import sleep_ms

from config import CONTROLLER_BITS, CONTROLLER_CLOCK, CONTROLLER_DATA, CONTROLLER_LATCH
from controller import Controller


def run_probe():
    controller = Controller(CONTROLLER_LATCH, CONTROLLER_CLOCK, CONTROLLER_DATA)
    by_index = {idx: name for name, idx in CONTROLLER_BITS.items()}
    print("Controller probe — press buttons (Ctrl-C to stop).")
    prev = [0] * 8
    while True:
        bits = controller.read_bits()
        for i in range(8):
            if bits[i] and not prev[i]:
                print("bit", i, "pressed ->", by_index.get(i, "?"))
        prev = bits
        sleep_ms(20)


try:
    run_probe()
except KeyboardInterrupt:
    pass
