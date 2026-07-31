"""The menu, pause and game-over screens render.

These live in main()'s state machine rather than in Game, so the smoke tests
never touch them. Extracting them into screens.py dropped an `import random`
that only the procedural menu fallback uses, and nothing caught it - hence
this file, and hence the fallback being covered explicitly below.
"""
import pygame
import pytest

import main
import screens


@pytest.fixture
def surface():
    return pygame.Surface((main.SCREEN_W, main.SCREEN_H))


def test_draw_menu(surface):
    screens.menu_video.update(1 / 60)
    screens.draw_menu(surface)


@pytest.mark.parametrize("selected", range(len(screens.PAUSE_ITEMS)))
def test_draw_pause(surface, selected):
    screens.draw_pause(surface, selected)


def test_draw_game_over(surface):
    screens.draw_game_over(surface, 12345, 55)


def test_menu_falls_back_when_frames_are_gone(surface):
    """start_game() releases the title frames to free ~390MB, so any later
    return to the menu takes the procedural path, not the video one."""
    screens.menu_video.release()
    screens.draw_menu(surface)


def test_screens_takes_a_surface_not_the_global():
    """They used to close over main.screen. Passing a surface in is what keeps
    screens.py from having to import main, which would be a cycle."""
    off = pygame.Surface((main.SCREEN_W, main.SCREEN_H))
    before = main.screen.copy()
    screens.draw_game_over(off, 1, 1)
    assert main.screen.get_rect() == before.get_rect()
    assert off.get_at((0, 0))[:3] == (10, 0, 20), "did not draw to the surface given"
