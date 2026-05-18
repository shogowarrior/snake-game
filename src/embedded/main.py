from config import BLE_LISTEN_SECONDS, BLE_OTA_ENABLED
from game import SnakeGame

POLICY = "greedy"  # "greedy" | "learned"


def run_game():
    if BLE_OTA_ENABLED:
        from ble_ota import listen

        listen(BLE_LISTEN_SECONDS)
    while True:
        game = SnakeGame(policy_name=POLICY)
        game.start_game()
        while not game.engine.game_over:
            game.tick()
        game.end_game()


try:
    run_game()
except KeyboardInterrupt:
    pass
