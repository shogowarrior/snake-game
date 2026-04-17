## Snake AI Game

Two implementations of Snake share the code in this repo:

* **PC version** ([src/ai/](src/ai/)) — Pygame UI with a Deep Q-Learning agent (PyTorch).
* **LED matrix version** ([src/led_matrix/](src/led_matrix/)) — MicroPython for an ESP32 driving a 16×16 NeoPixel matrix, using a greedy wrapped-distance AI.

Shared primitives (e.g. the `Direction` enum) live in [src/common/common.py](src/common/common.py).

### Features

* Customizable 16×16 grid (see `GRID_SIZE` in [src/ai/snake_game.py](src/ai/snake_game.py))
* Optional Pygame UI (toggle `py_ui` in [src/ai/game.py](src/ai/game.py))
* Deep Q-Network agent ([src/ai/model.py](src/ai/model.py)) with experience replay and ε-greedy exploration
* Live score / mean-score / moving-average plotting via matplotlib ([src/ai/helper.py](src/ai/helper.py))
* Per-game run logging to [scores.csv](scores.csv) and [db/tests.sqlite](db/tests.sqlite)
* Best-model checkpointing to [model/model.pth](model/model.pth)
* LED matrix build: gradient-colored snake, persistent high score (`high_score.txt`), WebREPL over Wi-Fi ([src/led_matrix/wlan.py](src/led_matrix/wlan.py))

### Project layout

```text
src/
  ai/          # PC / Pygame + PyTorch RL agent
  common/      # Shared Direction enum
  led_matrix/  # ESP32 + NeoPixel MicroPython build
model/         # Saved PyTorch checkpoints
db/            # SQLite run logs
notebooks/     # Exploration notebooks
scores.csv     # Per-game training scores
requirements.txt
```

### Requirements

See [requirements.txt](requirements.txt): `torch`, `pygame`, `matplotlib`, `pandas`, `plotly`, `nbformat`, `ipykernel`.

### To do

* Feature to resume training from existing [model/model.pth](model/model.pth)
* Fully unify the PC (`pygame`) and LED matrix (`micropython`) code paths
* Extend the SQLite schema to persist `moves` and `food_location` for the greedy version
* Modularize for easier configurability
