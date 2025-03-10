import pygame
import random
from enum import Enum
from collections import namedtuple
from common import Direction
import numpy as np

Point = namedtuple("Point", "x, y")

class SnakeGame:
    SPEED = 30
    GRID_SIZE = 16  # in actual pixels
    BLOCK_SIZE = 20
    PANE_WIDTH = 30  # Width for the right pane

    # Screen dimensions
    def __init__(self, learning=False, py_ui=True):
        self.learning = learning
        self.py_ui = py_ui
        self.grid_size = self.GRID_SIZE * self.BLOCK_SIZE
        
        # init display
        if self.py_ui:
            pygame.init()
            self.font = pygame.font.Font("arial.ttf", 16)
            self.display = pygame.display.set_mode((self.grid_size, self.grid_size + self.PANE_WIDTH))
            pygame.display.set_caption("Snake")
            self.clock = pygame.time.Clock()
        self.reset()

    def quit(self):
        pygame.quit()

    def reset(self):
        # init game state
        self.frame_iteration = 0
        self.direction = Direction.RIGHT
        self.head = (int(self.GRID_SIZE/2), int(self.GRID_SIZE/2))
        self.snake = [self.head]
        self.score = 0
        self.food = None
        self.place_food()
        

    def place_food(self) -> None:
        x = random.randint(0, (self.grid_size - self.BLOCK_SIZE) // self.BLOCK_SIZE) * self.BLOCK_SIZE
        y = random.randint(0, (self.grid_size - self.BLOCK_SIZE) // self.BLOCK_SIZE) * self.BLOCK_SIZE
        self.food = Point(x, y)
        if self.food in self.snake:
            self.place_food()

    def play_step(self, action=None):
        self.frame_iteration += 1

        if self.py_ui:
            # 1. collect user input
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    quit()
                if not self.learning:
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_LEFT:
                            self.direction = Direction.LEFT
                        elif event.key == pygame.K_RIGHT:
                            self.direction = Direction.RIGHT
                        elif event.key == pygame.K_UP:
                            self.direction = Direction.UP
                        elif event.key == pygame.K_DOWN:
                            self.direction = Direction.DOWN

        # 2. move
        self.move(action, self.direction)  # update the head
        self.snake.insert(0, self.head)

        # 3. check if game over
        reward = 0
        game_over = False
        
        if self.is_collision() or (self.learning and self.frame_iteration > 100 * len(self.snake)):
            game_over = True
            reward = -10
            return reward, game_over, self.score

        # 4. place new food or just move
        if self.head == self.food:
            self.score += 1
            reward = 10
            self.place_food()
        else:
            self.snake.pop()

        # 5. update ui and clock
        if self.py_ui:
            self.clock.tick(self.SPEED)
        
        # 6. return game over and score
        return reward, game_over, self.score

    def is_collision(self, pt=None):
        if pt is None:
            pt = self.head
        
        # hits itself
        if pt in self.snake[1:]:
            return True

        return False



    def move(self, action, direction):
        # [straight, right, left]
        if self.learning:
          clock_wise = [Direction.RIGHT, Direction.DOWN, Direction.LEFT, Direction.UP]
          idx = clock_wise.index(self.direction)

          if np.array_equal(action, [1, 0, 0]):
              new_dir = clock_wise[idx]  # no change
          elif np.array_equal(action, [0, 1, 0]):
              next_idx = (idx + 1) % 4
              new_dir = clock_wise[next_idx]  # right turn r -> d -> l -> u
          else:  # [0, 0, 1]
              next_idx = (idx - 1) % 4
              new_dir = clock_wise[next_idx]  # left turn r -> u -> l -> d
          self.direction = new_dir
        else:
          self.direction = direction

        x = self.head.x
        y = self.head.y
        if self.direction == Direction.RIGHT:
            x += self.BLOCK_SIZE
        elif self.direction == Direction.LEFT:
            x -= self.BLOCK_SIZE
        elif self.direction == Direction.DOWN:
            y += self.BLOCK_SIZE
        elif self.direction == Direction.UP:
            y -= self.BLOCK_SIZE

        x = x % self.grid_size
        y = y % self.grid_size
        self.head = Point(x, y)




