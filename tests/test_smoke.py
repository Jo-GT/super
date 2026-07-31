"""Headless boot-and-run.

Deliberately broad rather than precise: it drives a real Game through update()
and draw() with the powers held down, so anything that raises on a normal frame
- a renamed attribute, a bad blit, a missing sound guard - fails here. It does
not assert on gameplay outcomes, which are random (event spawns, enemy AI).
"""
import math

import pygame
import pytest

import main
from entities import Superman

FRAMES = 300          # 5 seconds at 60fps: long enough for the beam intro to
                      # hand over to the looping body, which is the sequencing
DT = 1 / 60           # most likely to break.


class _Keys:
    """pygame.key.get_pressed() returns an indexable of every scancode."""

    def __init__(self, held=()):
        self._held = set(held)

    def __getitem__(self, key):
        return key in self._held


@pytest.fixture
def game(monkeypatch):
    """A Game with input stubbed out, ready to be stepped."""
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (False, False, False))
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (640, 360))
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: _Keys())
    g = main.start_game()
    # start_game() is reached by clicking, so the click that started it is still
    # physically down and gets masked. Tests do not go through the menu.
    g._mouse_gate = [False, False, False]
    yield g
    g.stop_sounds()
    main.stop_music()


def _run(game, frames=FRAMES, held=(), monkeypatch=None):
    if held:
        monkeypatch.setattr(pygame.key, "get_pressed", lambda: _Keys(held))
    for _ in range(frames):
        game.update(DT)
        game.draw()


def test_idle_frames(game):
    _run(game)


def test_holding_heat_vision(game, monkeypatch):
    _run(game, held=(pygame.K_SPACE,), monkeypatch=monkeypatch)
    assert game.beam.phase == 'loop', (
        "the beam should have handed over from the intro clip to the looping "
        f"body within {FRAMES} frames, but phase is {game.beam.phase!r}"
    )


def test_holding_freeze_breath(game, monkeypatch):
    _run(game, held=(pygame.K_f,), monkeypatch=monkeypatch)
    assert game.superman.freeze_active


def test_release_stops_the_beam(game, monkeypatch):
    _run(game, frames=120, held=(pygame.K_SPACE,), monkeypatch=monkeypatch)
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: _Keys())
    _run(game, frames=30)
    assert game.beam.phase is None
    assert not game.beam.sizzling


def test_stop_sounds_resets_beam_state(game, monkeypatch):
    """Pause and death both go through stop_sounds(); if it misses a flag the
    beam can never restart."""
    _run(game, frames=120, held=(pygame.K_SPACE,), monkeypatch=monkeypatch)
    game.stop_sounds()
    assert game.beam.phase is None
    assert game.beam._contact_t == 0
    assert not game.beam.sizzling
    assert not game.wind.playing
    assert not game.freeze_loop.playing


def test_beam_passes_through_the_cursor(game):
    """The bug this branch fixed: the beam left the head but was aimed along
    `facing`, which is measured from the body centre, so it missed the cursor
    by the head offset."""
    s = game.superman
    game.update(DT)
    game.draw()                      # head_pos is assigned during draw()
    cursor = (640 + game.camera.x, 360 + game.camera.y)
    hx, hy = s.head_pos
    tx, ty = s.heat_beam_target()
    dx, dy = tx - hx, ty - hy
    perp = abs((cursor[0] - hx) * dy - (cursor[1] - hy) * dx) / math.hypot(dx, dy)
    assert perp < 0.01, f"cursor sits {perp:.2f}px off the beam line"


def test_freeze_cone_centres_on_the_cursor(game):
    s = game.superman
    game.update(DT)
    game.draw()
    cursor = (640 + game.camera.x, 360 + game.camera.y)
    a = math.atan2(cursor[1] - s.head_pos[1], cursor[0] - s.head_pos[0])
    off = abs((a - s.aim_angle() + math.pi) % (2 * math.pi) - math.pi)
    assert off < 1e-6, f"cone centre is {math.degrees(off):.2f}deg off the cursor"


def test_superman_survives_a_frame_without_a_cursor_angle():
    """aim_angle() has to cope with the cursor sitting exactly on the head,
    where there is no meaningful direction."""
    s = Superman.__new__(Superman)
    s.facing = 1.234
    s.head_pos = (100.0, 100.0)
    s.aim_world = (100.0, 100.0)
    assert s.aim_angle() == s.facing
    s.aim_world = None
    assert s.aim_angle() == s.facing
