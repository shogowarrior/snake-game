import torch
import random
import numpy as np
from collections import deque
from snake_game import SnakeGame, Direction, Point
from model import Linear_QNet, QTrainer
from helper import plot
from ui import update_ui, render_info

MAX_MEMORY = 100_000
BATCH_SIZE = 256
LR = 0.001
PLOT_SKIP = 100

class Agent:

    def __init__(self):
        self.n_games = 0
        self.epsilon = 0  # randomness
        self.gamma = 0.9  # discount rate
        self.memory = [] #deque(maxlen=MAX_MEMORY)  # popleft()
        self.model = Linear_QNet(16, 16, 3)
        self.trainer = QTrainer(self.model, lr=LR, gamma=self.gamma)

    def get_state(self, game):
        head = game.snake[0]
        length = len(game.snake)
        point_l = Point(head.x - 20, head.y)
        point_r = Point(head.x + 20, head.y)
        point_u = Point(head.x, head.y - 20)
        point_d = Point(head.x, head.y + 20)

        dir_l = game.direction == Direction.LEFT
        dir_r = game.direction == Direction.RIGHT
        dir_u = game.direction == Direction.UP
        dir_d = game.direction == Direction.DOWN

        state = [
            # # Danger straight
            (dir_r and game.is_collision(point_r))
            or (dir_l and game.is_collision(point_l))
            or (dir_u and game.is_collision(point_u))
            or (dir_d and game.is_collision(point_d)),
            # Danger right
            (dir_u and game.is_collision(point_r))
            or (dir_d and game.is_collision(point_l))
            or (dir_l and game.is_collision(point_u))
            or (dir_r and game.is_collision(point_d)),
            # Danger left
            (dir_d and game.is_collision(point_r))
            or (dir_u and game.is_collision(point_l))
            or (dir_r and game.is_collision(point_u))
            or (dir_l and game.is_collision(point_d)),
            # Move direction
            dir_l,
            dir_r,
            dir_u,
            dir_d,
            # Food location
            game.food.x,
            game.food.y,
            game.head.x,
            game.head.y,
            length,
            game.food.x < game.head.x,  # food left
            game.food.x > game.head.x,  # food right
            game.food.y < game.head.y,  # food up
            game.food.y > game.head.y,  # food down
        ]

        return np.array(state, dtype=int)

    def remember(self, state, action, reward, next_state, done):
        self.memory.append(
            (state, action, reward, next_state, done)
        )  # popleft if MAX_MEMORY is reached

    def train_long_memory(self):
        # import pdb
        # pdb.set_trace()
        if len(self.memory) > BATCH_SIZE:
            # mini_sample = self.memory[-BATCH_SIZE:] 
            mini_sample = random.sample(self.memory, BATCH_SIZE)  # list of tuples
        else:
            mini_sample = self.memory

        states, actions, rewards, next_states, dones = zip(*mini_sample)
        self.trainer.train_step(states, actions, rewards, next_states, dones)
        # for state, action, reward, nexrt_state, done in mini_sample:
        #    self.trainer.train_step(state, action, reward, next_state, done)

    def train_short_memory(self, state, action, reward, next_state, done):
        self.trainer.train_step(state, action, reward, next_state, done)

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


def play(learning, py_ui, led_matrix):
    plot_scores = []
    plot_mean_scores = []
    total_score = 0
    record = 0
    agent = Agent()
    game = SnakeGame(learning=learning, py_ui=py_ui, led_matrix=led_matrix)

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
            # agent.train_short_memory(state_old, final_move, reward, state_new, done)

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
                mean_score = total_score / agent.n_games
                plot_mean_scores.append(mean_score)
                if agent.n_games % PLOT_SKIP == 0:
                    plot(plot_scores, plot_mean_scores)
        if py_ui:
            update_ui(game)
            render_info(game, record, agent.n_games)

if __name__ == "__main__":
    learning = True
    py_ui = False
    led_matrix = False
    play(learning, py_ui, led_matrix)