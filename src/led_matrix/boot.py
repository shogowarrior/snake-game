
from game import SnakeGame
from wlan import start_wlan


def run_game():
    start_wlan()
    while True:
        game = SnakeGame()
        game.start_game()
        while not game.game_over:
            game.ai_move()
            game.move_snake()
            game.draw_snake()
        game.end_game()

        # report what
        

# Start the game
run_game()
