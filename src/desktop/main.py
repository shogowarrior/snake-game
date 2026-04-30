import torch
import csv
import random

import numpy as np
import sqlite3

from collections import deque
from datetime import datetime
from common.direction import Direction

from desktop.model import Linear_QNet, QTrainer
from desktop.plot import plot
from desktop.renderer import render_info, update_ui
from desktop.snake_game import Point, SnakeGame

# PLOT_SKIP = 2
BATCH_SIZE = 100
MAX_MEMORY = 100_000
LR = 0.001
WINDOW_SIZE = 25


class Agent:

    def __init__(self):
        self.n_games = 0
        self.epsilon = 0  # randomness
        self.gamma = 0.9  # discount rate
        self.memory = [] #deque(maxlen=MAX_MEMORY)  # popleft()
        self.model = Linear_QNet(11, 256, 3)
        self.trainer = QTrainer(self.model, lr=LR, gamma=self.gamma)

    def get_state(self, game):
        head = game.snake[0]
        length = len(game.snake)
        point_l = Point(head.x - game.BLOCK_SIZE, head.y)
        point_r = Point(head.x + game.BLOCK_SIZE, head.y)
        point_u = Point(head.x, head.y - game.BLOCK_SIZE)
        point_d = Point(head.x, head.y + game.BLOCK_SIZE)

        dir_l = game.direction == Direction.LEFT
        dir_r = game.direction == Direction.RIGHT
        dir_u = game.direction == Direction.UP
        dir_d = game.direction == Direction.DOWN

        state = [
            # # Danger straight
            # (dir_r and game.is_collision(point_r))
            # or (dir_l and game.is_collision(point_l))
            # or (dir_u and game.is_collision(point_u))
            # or (dir_d and game.is_collision(point_d)),
            # # Danger right
            # (dir_u and game.is_collision(point_r))
            # or (dir_d and game.is_collision(point_l))
            # or (dir_l and game.is_collision(point_u))
            # or (dir_r and game.is_collision(point_d)),
            # # Danger left
            # (dir_d and game.is_collision(point_r))
            # or (dir_u and game.is_collision(point_l))
            # or (dir_r and game.is_collision(point_u))
            # or (dir_l and game.is_collision(point_d)),
            # Move direction
            # dir_l,
            # dir_r,
            # dir_u,
            # dir_d,
            # game.food.x < game.head.x,  # food left
            # game.food.x > game.head.x,  # food right
            # game.food.y < game.head.y,  # food up
            # game.food.y > game.head.y,  # food down
            # Extra 5 states
            game.direction,
            game.food.x,
            game.food.y,
            game.head.x,
            game.head.y,
            length,
        ]
        print(state)

        return np.array(state, dtype=int)

    def remember(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))  # popleft if MAX_MEMORY is reached

    def train_long_memory(self):
        if len(self.memory) > BATCH_SIZE:
            # mini_sample = self.memory[-BATCH_SIZE:]

            # random batch sampling  of size BATCH_SIZE from MAX_MEMORY
            mini_sample = random.sample(self.memory, BATCH_SIZE)
        else:
            mini_sample = self.memory

        states, actions, rewards, next_states, dones = zip(*mini_sample)
        self.trainer.train_step(states, actions, rewards, next_states, dones)
        # for state, action, reward, nexrt_state, done in mini_sample:
        #    self.trainer.train_step(state, action, reward, next_state, done)

    def train_short_memory(self, state, action, reward, next_state, done):
        self.trainer.train_step(state, action, reward, next_state, done)

    ## edited bvy dada
    def get_action(self, state):
        # random moves: tradeoff exploration / exploitation
        if self.n_games <= 500:
            self.epsilon = min(1/np.log(self.n_games + 1), 0.2) # 80 - self.n_games
        elif self.n_games > 500 and self.n_games <= 1000:
            self.epsilon = min(1/np.log(self.n_games + 1), 0.15) # 80 - self.n_games
        else:
            self.epsilon = min(1/np.log(self.n_games + 1), 0.1) # 80 - self.n_games
        final_move = [0, 0, 0]
        if random.uniform(0, 1) < self.epsilon:
            move = random.randint(0, 2)
            final_move[move] = 1
        else:
            state0 = torch.tensor(state, dtype=torch.float)
            prediction = self.model(state0)
            move = torch.argmax(prediction).item()
            final_move[move] = 1
        return final_move

    ## original
    def get_action(self, state):
        # random moves: tradeoff exploration / exploitation
        self.epsilon = 80 - self.n_games
        final_move = [0,0,0]
        if random.randint(0, 200) < self.epsilon:
            move = random.randint(0, 2)
            final_move[move] = 1
        else:
            state0 = torch.tensor(state, dtype=torch.float)
            prediction = self.model(state0)
            move = torch.argmax(prediction).item()
            final_move[move] = 1

        return final_move

def play(learning, py_ui, led_matrix):
    plot_scores = []
    plot_mean_scores = []
    moving_mean_scores = []
    total_score = 0
    record = 0
    agent = Agent()
    game = SnakeGame(learning=learning, py_ui=py_ui, led_matrix=led_matrix)
    
    # Connect to SQLite database
    connection = sqlite3.connect("db/tests.sqlite")
    cursor = connection.cursor()

    steps = 0
    while True:
        if not game.learning:
            # game loop
            while True:
                reward, game_over, score = game.play_step(action=None)
                if game_over == True:
                    break
            print("Final Score", score)
            if py_ui:
                game.quit()

        else:

            # load memory
            # agent.model.load()

            # get old state
            state_old = agent.get_state(game)

            # get move
            final_move = agent.get_action(state_old)

            # perform move and get new state
            reward, done, score = game.play_step(final_move)
            state_new = agent.get_state(game)

            # train short memory
            # if steps % 8 == 0 and steps > 8:
            #     agent.train_long_memory()
            agent.train_short_memory(state_old, final_move, reward, state_new, done)

            # remember
            agent.remember(state_old, final_move, reward, state_new, done)

            if done:
                # train long memory, plot result
                game.reset()
                agent.n_games += 1
                agent.train_long_memory()
                steps = 0

                if score > record:
                    record = score
                    agent.model.save()

                #print("Game", agent.n_games, "Score", score, "Record:", record)
                plot_scores.append(score)
                total_score += score

                # mean_score
                mean_score = total_score / agent.n_games
                plot_mean_scores.append(mean_score)

                # moving average
                window_size = WINDOW_SIZE if agent.n_games > WINDOW_SIZE else agent.n_games

                moving_mean_score = sum(plot_scores[-window_size:])
                moving_mean_scores.append(moving_mean_score/window_size)

                # if agent.n_games % PLOT_SKIP == 0:
                plot(plot_scores, plot_mean_scores, moving_mean_scores)

                # Append data to CSV
                with open("scores.csv", mode="a") as file:
                    file.write(f"{agent.n_games},{datetime.now()},{score},N/A\n")

                # send settings to sqlite for debugging
                cursor.execute("INSERT INTO test_results (score, params) VALUES (?, ?)", (score, "N/A"))
                connection.commit()
        if py_ui:
            update_ui(game)
            render_info(game, record, agent.n_games)
    
    connection.close()

if __name__ == "__main__":
    learning = True
    py_ui = False
    play(learning, py_ui)
