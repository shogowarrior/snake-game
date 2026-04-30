import random
import sqlite3
from datetime import datetime

import numpy as np
import torch

from common.direction import Direction
from common.engine import SnakeEngine
from desktop.model import Linear_QNet, QTrainer
from desktop.plot import plot
from desktop.renderer import init_pygame, render_info, update_ui

BATCH_SIZE = 100
MAX_MEMORY = 100_000
LR = 0.001
WINDOW_SIZE = 25
GRID_SIZE = 16

# RL training-stall guard: end the episode once total frames exceed
# STALL_FACTOR * len(snake). This preserves the original behaviour
# (`frame_iteration > 100 * len(snake)` from the old SnakeGame). It's a
# rough "stuck game" detector — not a "frames since last food" timer.
# Lives in the agent loop, not the engine.
STALL_FACTOR = 100


class Agent:
    def __init__(self):
        self.n_games = 0
        self.epsilon = 0
        self.gamma = 0.9
        self.memory = []
        self.model = Linear_QNet(6, 256, 3)
        self.trainer = QTrainer(self.model, lr=LR, gamma=self.gamma)

    def get_state(self, engine):
        head_x, head_y = engine.head
        food_x, food_y = engine.food
        state = [
            engine.direction,
            food_x,
            food_y,
            head_x,
            head_y,
            len(engine.snake),
        ]
        return np.array(state, dtype=int)

    def remember(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))

    def train_long_memory(self):
        if len(self.memory) > BATCH_SIZE:
            mini_sample = random.sample(self.memory, BATCH_SIZE)
        else:
            mini_sample = self.memory

        states, actions, rewards, next_states, dones = zip(*mini_sample)
        self.trainer.train_step(states, actions, rewards, next_states, dones)

    def train_short_memory(self, state, action, reward, next_state, done):
        self.trainer.train_step(state, action, reward, next_state, done)

    def get_action(self, state):
        # Exploration / exploitation: linear epsilon decay over the first ~80 games.
        self.epsilon = 80 - self.n_games
        final_move = [0, 0, 0]
        if random.randint(0, 200) < self.epsilon:
            move = random.randint(0, 2)
            final_move[move] = 1
        else:
            state0 = torch.tensor(state, dtype=torch.float)
            prediction = self.model(state0)
            move = torch.argmax(prediction).item()
            final_move[move] = 1
        return final_move


def _action_to_direction(action, current_direction):
    """Map a [straight, right, left] one-hot action to a Direction.

    Direction is rotated relative to the current heading along the clockwise
    cycle RIGHT -> DOWN -> LEFT -> UP -> RIGHT.
    """
    clock_wise = [Direction.RIGHT, Direction.DOWN, Direction.LEFT, Direction.UP]
    idx = clock_wise.index(current_direction)
    if np.array_equal(action, [1, 0, 0]):
        return clock_wise[idx]
    if np.array_equal(action, [0, 1, 0]):
        return clock_wise[(idx + 1) % 4]
    return clock_wise[(idx - 1) % 4]


def _read_keyboard(pygame_state, current_direction):
    """Drain the pygame event queue. Returns the new direction (or current)."""
    import pygame

    new_dir = current_direction
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            raise SystemExit(0)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                new_dir = Direction.LEFT
            elif event.key == pygame.K_RIGHT:
                new_dir = Direction.RIGHT
            elif event.key == pygame.K_UP:
                new_dir = Direction.UP
            elif event.key == pygame.K_DOWN:
                new_dir = Direction.DOWN
    return new_dir


def play(learning, py_ui):
    plot_scores = []
    plot_mean_scores = []
    moving_mean_scores = []
    total_score = 0
    record = 0
    agent = Agent()
    engine = SnakeEngine(size=GRID_SIZE)
    pygame_state = init_pygame(GRID_SIZE) if py_ui else None

    connection = sqlite3.connect("db/tests.sqlite")
    cursor = connection.cursor()

    while True:
        if not learning:
            # Human/keyboard mode: play a single game with UI updates each tick.
            engine = SnakeEngine(size=GRID_SIZE)
            while not engine.game_over:
                if py_ui:
                    new_dir = _read_keyboard(pygame_state, engine.direction)
                    engine.set_direction(new_dir)
                    engine.step()
                    update_ui(pygame_state, engine)
                    render_info(pygame_state, engine, record, agent.n_games)
                    pygame_state.clock.tick(pygame_state.SPEED)
                else:
                    engine.step()
            print("Final Score", engine.score)
            if py_ui:
                import pygame
                pygame.quit()
            return

        # Learning mode.
        state_old = agent.get_state(engine)
        final_move = agent.get_action(state_old)
        new_dir = _action_to_direction(final_move, engine.direction)
        done, reward, score = engine.step(new_dir)

        # Stall guard — externalised from the engine.
        if not done and engine.frame > STALL_FACTOR * len(engine.snake):
            done = True
            reward = -10
            engine.game_over = True

        state_new = agent.get_state(engine)
        agent.train_short_memory(state_old, final_move, reward, state_new, done)
        agent.remember(state_old, final_move, reward, state_new, done)

        if py_ui:
            update_ui(pygame_state, engine)
            render_info(pygame_state, engine, record, agent.n_games)

        if done:
            engine = SnakeEngine(size=GRID_SIZE)
            agent.n_games += 1
            agent.train_long_memory()

            if score > record:
                record = score
                agent.model.save()

            plot_scores.append(score)
            total_score += score
            mean_score = total_score / agent.n_games
            plot_mean_scores.append(mean_score)

            window_size = WINDOW_SIZE if agent.n_games > WINDOW_SIZE else agent.n_games
            moving_mean_score = sum(plot_scores[-window_size:])
            moving_mean_scores.append(moving_mean_score / window_size)

            plot(plot_scores, plot_mean_scores, moving_mean_scores)

            with open("scores.csv", mode="a") as file:
                file.write(f"{agent.n_games},{datetime.now()},{score},N/A\n")

            cursor.execute("INSERT INTO test_results (score, params) VALUES (?, ?)", (score, "N/A"))
            connection.commit()

    # Unreachable in learning mode; cursor closes on exit.
    connection.close()


if __name__ == "__main__":
    learning = True
    py_ui = False
    play(learning, py_ui)
