from config import CONTROLLER_CLOCK, CONTROLLER_DATA, CONTROLLER_LATCH
from controller import Controller
from display import Display
from game import ControlState, SnakeGame

POLICY = "greedy"  # "greedy" | "learned"


def run_game():
    screen = Display()
    controller = Controller(CONTROLLER_LATCH, CONTROLLER_CLOCK, CONTROLLER_DATA)
    state = ControlState()
    while True:
        game = SnakeGame(display=screen, policy_name=POLICY, controller=controller, state=state)
        game.start_game()
        reset = False
        while not game.engine.game_over:
            if game.tick():  # START pressed
                reset = True
                break
        if not reset:
            game.end_game()


try:
    run_game()
except KeyboardInterrupt:
    pass
