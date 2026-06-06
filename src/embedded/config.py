"""User-tunable constants for the embedded build.

Anything in this file is something a human might want to flip without reading
display.py.
"""

# GPIO pin the NeoPixel matrix DIN is wired to. Change to match your board.
NEOPIXEL_PIN = 13

# Global brightness scale (0.0 - 1.0) applied to every pixel inside flush().
BRIGHTNESS = 1.0

# Mounting rotation in degrees clockwise; pick what reads upright. Re-flash to change.
ROTATION = 0  # 0 | 90 | 180 | 270

# Game tick rate in frames per second. Higher = faster snake.
SPEED = 50

# Seconds to hold the game-over score on screen before starting a new game.
SCORE_DISPLAY_SECONDS = 2

# Pulse the food cell like a heartbeat (lub-dub + rest). False = steady pixel.
FOOD_HEARTBEAT = True
