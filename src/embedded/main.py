from display import Display
from game import SnakeGame

POLICY = "greedy"  # "greedy" | "learned"


def run_game():
    screen = Display()
    while True:
        game = SnakeGame(display=screen, policy_name=POLICY)
        game.start_game()
        while not game.engine.game_over:
            game.tick()
        game.end_game()


try:
    run_game()
except KeyboardInterrupt:
    pass
