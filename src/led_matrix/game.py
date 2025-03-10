from common import Direction
from display import clear_screen, display_scores, NP, xy_to_index
from random import randint
from time import sleep


GAME_SIZE = 16
DEFAULT_SPEED = 50
HIGH_SCORE_FILE = 'high_score.txt'

# Function to load the high score from a file
def load_high_score():
    try:
        with open(HIGH_SCORE_FILE, 'r') as file:
            return int(file.read())  # Read the high score and convert to integer
    except (OSError, ValueError):
        return 0

# Function to save the high score to a file
def save_high_score(new_high_score):
    try:
        with open(HIGH_SCORE_FILE, 'w') as file:
            file.write(str(new_high_score))
    except OSError:
        print("Error saving high score.")

# Function to generate a random bright color where RGB values differ sufficiently to avoid grey
def get_rand_color():
    while True:
        r = randint(0, 175)
        g = randint(0, 175)
        b = randint(0, 175)
        
        # Check that the difference between each component is large enough to avoid grey tones
        if abs(r - g) > 50 and abs(g - b) > 50 and abs(b - r) > 50:
            return (r, g, b)

def get_gradient_color(index, 
                       length, 
                       start_color, 
                       end_color):
        """
        Returns a color that fades from start_color to end_color based on the index.
        :param index: The current index in the range (from 0 to length).
        :param length: The total number of steps in the gradient.
        :param start_color: The starting color of the gradient (RGB tuple).
        :param end_color: The ending color of the gradient (RGB tuple).
        :return: A tuple representing the interpolated color (R, G, B).
        """
        factor = index / length  # Scale factor for interpolation (between 0 and 1)

        # Interpolate each color channel (R, G, B) between start_color and end_color
        return tuple(int(start_c + factor * (end_c - start_c)) for start_c, end_c in zip(start_color, end_color))

class SnakeGame:
    def __init__(self, 
                 start_color=get_rand_color(), 
                 end_color=get_rand_color(), 
                 food_color=get_rand_color(), 
                 speed=DEFAULT_SPEED):
        self.snake = [(int(GAME_SIZE/2), int(GAME_SIZE/2))]
        self.speed = speed
        self.start_color = start_color
        self.end_color = end_color
        self.food_color = food_color
        self.previous_snake_length = len(self.snake)
        self.gradient_colors = []  # Store the calculated gradient colors
        self.direction = Direction.RIGHT  # Start moving to the right
        self.food = self.generate_food()
        self.game_over = False
        self.score = 0
        self.direction_changes = {
            Direction.UP: (-1, 0),     # Move up: decrease x
            Direction.DOWN: (1, 0),    # Move down: increase x
            Direction.LEFT: (0, -1),   # Move left: decrease y
            Direction.RIGHT: (0, 1)    # Move right: increase y
        }

    def generate_food(self):
        food = (randint(0, GAME_SIZE-1), randint(0, GAME_SIZE-1))
        self.food_color = get_rand_color() 
        if food in self.snake:
            self.generate_food()
                  

    def move_snake(self):
        head_x, head_y = self.snake[0]

        # Get the x and y changes for the current direction
        dx, dy = self.direction_changes[self.direction]

        # Final new head position
        new_head = ((head_x + dx) % 16, (head_y + dy) % 16)

        if new_head in self.snake:  # Check for collision with self
            self.game_over = True
            return

        self.snake.insert(0, new_head)

        if new_head == self.food:  # Snake eats the food
            self.score += 1
            self.food = self.generate_food()
        else:
            self.snake.pop()  # Remove tail unless food was eaten

    def change_direction(self, new_direction):
        # Prevent the snake from reversing on itself
        if (self.direction == Direction.UP and new_direction != Direction.DOWN) or \
           (self.direction == Direction.DOWN and new_direction != Direction.UP) or \
           (self.direction == Direction.LEFT and new_direction != Direction.RIGHT) or \
           (self.direction == Direction.RIGHT and new_direction != Direction.LEFT):
            self.direction = new_direction

    def ai_move(self):
        # Get the current head of the snake
        head_x, head_y = self.snake[0]
        # Get the food coordinates
        food_x, food_y = self.food

        # Function to compute wrapped distance between two points on the grid
        def wrapped_distance(p1, p2):
            return min(abs(p1 - p2), 16 - abs(p1 - p2))

        # Function to check if a position is a valid move (i.e., not an obstacle)
        def is_valid_move(new_x, new_y):
            return (new_x, new_y) not in self.snake  # Avoid snake body

        # Calculate the distance from the head to the food in each direction
        distances = {
            Direction.UP: (wrapped_distance(head_x - 1, food_x) + wrapped_distance(head_y, food_y),
                    (head_x - 1) % 16, head_y),
            Direction.DOWN: (wrapped_distance(head_x + 1, food_x) + wrapped_distance(head_y, food_y),
                    (head_x + 1) % 16, head_y),
            Direction.LEFT: (wrapped_distance(head_x, food_x) + wrapped_distance(head_y - 1, food_y),
                    head_x, (head_y - 1) % 16),
            Direction.RIGHT: (wrapped_distance(head_x, food_x) + wrapped_distance(head_y + 1, food_y),
                    head_x, (head_y + 1) % 16)
        }

        # Filter out invalid moves (store the whole tuple of (dist, new_x, new_y))
        valid_moves = {dir: (dist, new_x, new_y) for dir, (dist, new_x, new_y) in distances.items() if is_valid_move(new_x, new_y)}

        if valid_moves:
            # Choose the one with the smallest distance to the food (first element of the tuple)
            best_direction = min(valid_moves, key=lambda dir: valid_moves[dir][0])
            self.change_direction(best_direction)
        else:
            # No valid moves, game over (or you could have the AI make a random move)
            self.game_over = True



    # Function to draw the game state on the NeoPixel matrix with gradient snake
    def draw_snake(self):
        clear_screen()

        # Cache snake length to avoid multiple lookups
        snake_length = len(self.snake)

        # Recalculate gradient only if snake size has changed
        if snake_length != self.previous_snake_length:
            self.gradient_colors = [
                get_gradient_color(index, snake_length, self.start_color, self.end_color)
                for index in range(snake_length)
            ]
            self.previous_snake_length = snake_length  # Update the previous length

        # Draw snake with precomputed gradient
        for index, (x, y) in enumerate(self.snake):
            NP[xy_to_index(x, y)] = self.gradient_colors[index]
        
        # Draw food (assuming food is a class attribute)
        food_x, food_y = self.food  # Unpack food coordinates (x, y)
        NP[xy_to_index(food_x, food_y)] = self.food_color
        NP.write()

        # Game speed
        sleep(1/self.speed)

    def start_game(self):
        self.score = 0  # Reset current score
        self.high_score = load_high_score()  # Load high score from file

    def end_game(self):
        current_score = self.score
        high_score = load_high_score()
        if current_score > high_score:
            save_high_score(current_score)  # Save new high score to file
            high_score = current_score
        display_scores(high_score, current_score)
        sleep(5)
