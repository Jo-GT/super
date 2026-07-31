"""The menu, pause and game-over screens render, and the title video plays.

These live in main()'s state machine rather than in Game, so the smoke tests
never touch them. Two regressions came out of extracting them into screens.py,
both of which this file now covers:

* an `import random` was dropped, which only the procedural menu fallback uses
* MenuVideo loaded its frames in __init__, which runs at module import - before
  main.py calls set_mode(). Every .convert() raised, the class's own
  except-swallow hid it, and the title screen quietly became the fallback.

The second one is why test_title_video_actually_loads exists. Rendering tests
alone could not catch it: draw_menu() succeeds either way, it just draws
something different.
"""
import pygame
import pytest

import main
import screens


@pytest.fixture
def surface():
    return pygame.Surface((main.SCREEN_W, main.SCREEN_H))


@pytest.fixture
def video():
    """A fresh MenuVideo. The module-level `menu_video` is shared, and
    release() is destructive, so tests must not mutate it."""
    return screens.MenuVideo(screens._TITLE_FRAMES_DIR, screens._TITLE_FRAME_FPS)


def test_title_video_actually_loads(video):
    video.update(1 / 60)
    assert video._frames, (
        "no title frames loaded - the title screen has silently fallen back to "
        "the procedural skyline. Usually means .convert() ran before the display "
        "mode was set."
    )


def test_title_video_is_what_gets_drawn(video, surface):
    video.update(1 / 60)
    assert video.draw(surface) is True, "draw() returned False, so draw_menu " \
                                        "would render the fallback instead"


def test_title_video_holds_the_last_frame(video, surface):
    """It ends on the PRESS START card rather than looping or going blank."""
    for _ in range(500):
        video.update(1 / 60)
    assert video.draw(surface) is True


def test_release_keeps_a_card_to_draw(video, surface):
    """start_game() releases the frames to free ~390MB, but returning to the
    menu afterwards must still show something."""
    video.update(1 / 60)
    video.release()
    assert video._frames == []
    assert video.draw(surface) is True, "released the card as well as the frames"


def test_draw_menu(surface):
    screens.menu_video.update(1 / 60)
    screens.draw_menu(surface)


@pytest.mark.parametrize("selected", range(len(screens.PAUSE_ITEMS)))
def test_draw_pause(surface, selected):
    screens.draw_pause(surface, selected)


def test_draw_game_over(surface):
    screens.draw_game_over(surface, 12345, 55)


def test_menu_falls_back_when_frames_are_missing(surface, monkeypatch):
    """The fallback path still has to work - it is what a build without the
    Title Page folder gets. Exercised via a bad directory rather than by
    releasing the shared menu_video, which would break other tests."""
    empty = screens.MenuVideo("/nonexistent-frames", screens._TITLE_FRAME_FPS)
    monkeypatch.setattr(screens, "menu_video", empty)
    screens.draw_menu(surface)
    assert empty.draw(surface) is False


def test_screens_takes_a_surface_not_the_global():
    """They used to close over main.screen. Passing a surface in is what keeps
    screens.py from having to import main, which would be a cycle."""
    off = pygame.Surface((main.SCREEN_W, main.SCREEN_H))
    before = main.screen.copy()
    screens.draw_game_over(off, 1, 1)
    assert main.screen.get_rect() == before.get_rect()
    assert off.get_at((0, 0))[:3] == (10, 0, 20), "did not draw to the surface given"
