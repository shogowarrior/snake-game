from collections import namedtuple

import pygame

WHITE = (255, 255, 255)
GREY = (127, 127, 127)
RED = (200, 0, 0)
BLUE1 = (0, 0, 255)
BLUE2 = (0, 100, 255)
BLACK = (0, 0, 0)

BLOCK_SIZE = 20
PANE_WIDTH = 30
SPEED = 30

PygameState = namedtuple("PygameState", "display font clock grid_size_px SPEED")


def init_pygame(grid_size):
    """Initialise pygame and return a PygameState. Call once at startup."""
    pygame.init()
    font = pygame.font.Font("arial.ttf", 16)
    grid_size_px = grid_size * BLOCK_SIZE
    display = pygame.display.set_mode((grid_size_px, grid_size_px + PANE_WIDTH))
    pygame.display.set_caption("Snake")
    clock = pygame.time.Clock()
    return PygameState(display=display, font=font, clock=clock, grid_size_px=grid_size_px, SPEED=SPEED)


def update_ui(state, engine):
    """Repaint the play area for one frame."""
    state.display.fill(BLACK)
    fx, fy = engine.food
    pygame.draw.rect(
        state.display,
        RED,
        pygame.Rect(fx * BLOCK_SIZE, fy * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE),
    )
    for x, y in engine.snake:
        pygame.draw.rect(
            state.display,
            BLUE1,
            pygame.Rect(x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE),
        )
        pygame.draw.rect(
            state.display,
            BLUE2,
            pygame.Rect(x * BLOCK_SIZE + 4, y * BLOCK_SIZE + 4, 12, 12),
        )


def render_info(state, engine, record_score, num_games):
    """Render the info pane below the play area."""
    pane_y_start = state.grid_size_px

    pygame.draw.rect(state.display, GREY, (0, pane_y_start, state.grid_size_px, PANE_WIDTH))

    games_surface = state.font.render(f"Games: {num_games}", True, WHITE)
    state.display.blit(games_surface, (10, pane_y_start + 5))

    score_surface = state.font.render(f"Score: {engine.score}", True, WHITE)
    state.display.blit(score_surface, (135, pane_y_start + 5))

    record_surface = state.font.render(f"Max: {record_score}", True, WHITE)
    state.display.blit(record_surface, (260, pane_y_start + 5))

    pygame.display.flip()
