import pygame

# rgb colors
WHITE = (255, 255, 255)
GREY = (127, 127, 127)
RED = (200, 0, 0)
BLUE1 = (0, 0, 255)
BLUE2 = (0, 100, 255)
BLACK = (0, 0, 0)

def update_ui(game):
    game.display.fill(BLACK)
    pygame.draw.rect(
        game.display, RED,
        pygame.Rect(game.food.x, game.food.y, game.BLOCK_SIZE, game.BLOCK_SIZE),
    )
    for pt in game.snake:
        pygame.draw.rect(
            game.display, BLUE1, pygame.Rect(pt.x, pt.y, game.BLOCK_SIZE, game.BLOCK_SIZE)
        )
        pygame.draw.rect(
            game.display, BLUE2, pygame.Rect(pt.x + 4, pt.y + 4, 12, 12)
        )
    


# Function to render game info on the right pane
def render_info(game, record_score, num_games):
    pane_y_start = game.game_size
    
    # Draw pane background
    pygame.draw.rect(game.display, GREY, (0, pane_y_start, game.game_size, game.PANE_WIDTH))

    # Number of games
    num_games = game.font.render(f"Games: {num_games}", True, WHITE)
    game.display.blit(num_games, (10, pane_y_start + 5))

    # Current Score
    curr_score = game.font.render(f"Score: {game.score}", True, WHITE)
    game.display.blit(curr_score, (135, pane_y_start + 5))

    # Record Score
    record_score = game.font.render(f"Max: {record_score}", True, WHITE)
    game.display.blit(record_score, (260, pane_y_start + 5))

  

    pygame.display.flip()
