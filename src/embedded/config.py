"""User-tunable constants for the embedded build.

Anything in this file is something a human might want to flip without reading
display.py.
"""

# GPIO pin the NeoPixel matrix DIN is wired to. Change to match your board.
NEOPIXEL_PIN = 13

# Global brightness scale (0.0 - 1.0) applied to every pixel inside flush().
BRIGHTNESS = 0.5

# Mounting rotation in degrees clockwise; pick what reads upright. Re-flash to change.
ROTATION = 0  # 0 | 90 | 180 | 270

# Game tick rate in frames per second. Higher = faster snake.
SPEED = 25

# Seconds to hold the game-over score on screen before starting a new game.
SCORE_DISPLAY_SECONDS = 2

# Blink the food cell: fade to black, then up as a new random color. False = steady pixel.
FOOD_BLINK = True

# Frames per food blink cycle (resets each food). Keep small — food is eaten in ~10 moves, so larger never completes.
FOOD_BLINK_FRAMES = 4

# Control mode at boot: "auto" runs the AI policy, "manual" reads the controller D-pad.
# SELECT toggles between them live.
CONTROL_MODE = "auto"  # "auto" | "manual"

# Famicom/NES controller (4021 shift register). Keep clear of NEOPIXEL_PIN (13).
CONTROLLER_LATCH = 18
CONTROLLER_CLOCK = 5
CONTROLLER_DATA = 19

# 4021 bit index (0-7) each button occupies. Clone wiring varies — run probe.py and re-map.
CONTROLLER_BITS = {
    "A": 0,
    "B": 1,
    "SELECT": 2,
    "START": 3,
    "UP": 4,
    "DOWN": 5,
    "LEFT": 6,
    "RIGHT": 7,
}

# A/B buttons step the live tick rate by this many FPS, clamped to [SPEED_MIN, SPEED_MAX].
SPEED_STEP = 5
SPEED_MIN = 5
SPEED_MAX = 60
