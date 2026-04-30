from game import SnakeGame

# from wlan import start_wlan

POLICY = "greedy"  # "greedy" | "learned"


def run_game():
    # start_wlan()
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
