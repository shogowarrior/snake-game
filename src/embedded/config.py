"""User-tunable constants for the embedded build.

Anything in this file is something a human might want to flip without reading
display.py. Hardware-wiring constants (NEOPIXEL_PIN, NUM_PIXELS) intentionally
stay in display.py since they're fixed by the solder.
"""

# Mounting rotation. One global value applied uniformly to everything drawn on
# the panel (snake, food, score). Pick the value that makes the score read
# upright in your physical setup, then commit. Changing this requires a re-flash.
ROTATION = "0"  # "0" | "90CW" | "180" | "90CCW"

# Score-text gradient (game-over screen). The score's lit pixels fade from
# START on the left to END on the right across the message's bounding box.
SCORE_GRADIENT_START = (0, 120, 220)  # cool blue
SCORE_GRADIENT_END = (220, 0, 140)  # magenta
