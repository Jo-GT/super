"""Events wake when they come into view.

entities.visible_rect duplicates main.Camera's clamp, because events.py cannot
import main.py. These tests are what keep the two from drifting apart.
"""
import math

import pytest

import main
from constants import SCREEN_H, SCREEN_W, WORLD_H, WORLD_W
from entities import visible_rect
from events import CatEvent, FireEvent, HostageEvent, make_criminals_event
from particles import ParticleSystem


class _Sup:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.heat_firing = False
        self.freeze_active = False
        self.xray_remaining = 0.0

    def heat_covers(self, wx, wy, threshold=28):
        return False


# ─── the duplicated clamp ─────────────────────────────────────────────────────

@pytest.mark.parametrize("px, py", [
    (WORLD_W / 2, WORLD_H / 2),          # middle: camera centred on the player
    (0, 0), (WORLD_W, WORLD_H),          # both corners: camera fully clamped
    (100, WORLD_H / 2), (WORLD_W - 100, WORLD_H / 2),
    (WORLD_W / 2, 60), (WORLD_W / 2, WORLD_H - 60),
    (SCREEN_W / 2, SCREEN_H / 2),        # exactly on the clamp boundary
])
def test_visible_rect_matches_a_settled_camera(px, py):
    cam = main.Camera()
    for _ in range(400):                 # let the exponential follow settle
        cam.update(px, py, 1 / 60)
    r = visible_rect(px, py)
    assert r.x == pytest.approx(cam.x, abs=1.0)
    assert r.y == pytest.approx(cam.y, abs=1.0)
    assert (r.w, r.h) == (SCREEN_W, SCREEN_H)


def test_visible_rect_never_leaves_the_world():
    for px in (-500, 0, WORLD_W / 2, WORLD_W, WORLD_W + 500):
        for py in (-500, 0, WORLD_H / 2, WORLD_H, WORLD_H + 500):
            r = visible_rect(px, py)
            assert 0 <= r.x <= WORLD_W - SCREEN_W
            assert 0 <= r.y <= WORLD_H - SCREEN_H


def test_player_is_inside_his_own_view():
    """Over the range Superman can actually occupy: entities.py:303 clamps him
    to 20px inside the world, and collidepoint excludes a Rect's right and
    bottom edges, so the literal world corner is neither reachable nor inside."""
    lo, hi_x, hi_y = 20, WORLD_W - 20, WORLD_H - 20
    for px, py in ((lo, lo), (WORLD_W / 2, WORLD_H / 2), (hi_x, hi_y),
                   (lo, hi_y), (hi_x, lo)):
        assert visible_rect(px, py).collidepoint(px, py)


# ─── activation ───────────────────────────────────────────────────────────────

MID = WORLD_W / 2


@pytest.mark.parametrize("factory", [
    make_criminals_event, FireEvent, CatEvent, HostageEvent,
])
def test_events_wake_on_sight_across_the_board(factory):
    """Well beyond every INNER_RADIUS (the largest is 350), but on screen."""
    ev = factory(MID + 600, MID)
    assert ev.INNER_RADIUS < 600, "test no longer proves anything"
    ev.update(1 / 60, _Sup(MID, MID), ParticleSystem())
    assert ev.active


@pytest.mark.parametrize("factory", [
    make_criminals_event, FireEvent, CatEvent, HostageEvent,
])
def test_events_stay_asleep_while_off_screen(factory):
    ev = factory(MID + 900, MID)
    ev.update(1 / 60, _Sup(MID, MID), ParticleSystem())
    assert not ev.active


def test_proximity_still_wakes_an_event_that_is_off_frame():
    """Reachable at the world edges, where the camera clamps and the player can
    sit far from the centre of his own view."""
    ev = CatEvent(30, 30)
    ev.update(1 / 60, _Sup(30, 30), ParticleSystem())
    assert ev.active


def _beacon_shown(ev):
    return not ev._arrived


def test_beacon_is_not_keyed_on_active():
    """Waking on sight would otherwise mean the in-world marker never drew."""
    ev = CatEvent(MID + 600, MID)
    ev.update(1 / 60, _Sup(MID, MID), ParticleSystem())
    assert ev.active and _beacon_shown(ev)
    ev.update(1 / 60, _Sup(MID + 600, MID), ParticleSystem())    # stood on it
    assert not _beacon_shown(ev)


def test_the_dot_clears_once_you_are_in_the_fight():
    """A fight's enemies spawn out to 160px, so a beacon keyed on the 100px
    activation range sat in the middle of the brawl."""
    ev = make_criminals_event(MID, MID)
    assert ev.BEACON_R > 160
    ev.update(1 / 60, _Sup(MID + 200, MID), ParticleSystem())
    assert ev.active and not _beacon_shown(ev)


def test_the_dot_stays_gone_once_you_have_been_there():
    """Latched, not a live range test: chasing a thug back out would otherwise
    pop the beacon up again behind you, mid-fight."""
    ev = make_criminals_event(MID, MID)
    ev.update(1 / 60, _Sup(MID + 100, MID), ParticleSystem())
    assert not _beacon_shown(ev)
    ev.update(1 / 60, _Sup(MID + 600, MID), ParticleSystem())    # gave chase
    assert not _beacon_shown(ev)


# ─── spawning ─────────────────────────────────────────────────────────────────

def test_events_spawn_out_of_frame():
    """MIN_SPAWN_D has to clear the viewport's half-diagonal, or a new event
    pops into existence already visible and immediately active."""
    assert main.Game.MIN_SPAWN_D > math.hypot(SCREEN_W / 2, SCREEN_H / 2)


# ─── fairness ─────────────────────────────────────────────────────────────────
# Waking on sight starts every clock while the player may still be a corner of
# the screen away. Anything with a deadline under a few seconds has to survive
# that trip, or the event is lost before it can be played.

CRUISE = 550.0                                    # measured: Superman.SPEED * 60
CORNER = math.hypot(SCREEN_W / 2, SCREEN_H / 2)   # furthest visible point, 734px
REACTION = 0.30
BUDGET = CORNER / CRUISE + REACTION               # ~1.64s


def test_a_falling_person_stays_catchable_from_the_screen_edge():
    from events import FallingEvent
    seconds = (FallingEvent(0, 0).ground_y + 280) / FallingEvent.FALL_SPEED
    assert seconds > BUDGET


def test_the_runaway_car_cannot_reach_a_pedestrian_before_you_do():
    """It used to place them 150-300px down the road, i.e. 0.6s at 200px/s."""
    import random

    from events import CarEvent
    random.seed(3)
    worst = min(
        min(math.hypot(p.x - ev.car_x, p.y - ev.car_y) for p in ev.pedestrians)
        / CarEvent.CAR_SPEED
        for ev in (CarEvent(2304, 2304) for _ in range(500))
    )
    assert worst > BUDGET


@pytest.mark.parametrize("name", ["FireEvent", "FloodEvent", "CrateEvent", "RubbleEvent"])
def test_the_long_timers_have_ample_headroom(name):
    import events
    assert getattr(events, name).TIMER > 10 * BUDGET


def test_the_cat_is_rescued_on_arrival_not_on_activation():
    """Its rescue used to ride on on_activate, back when activating meant you
    had already flown to the tree. On sight that handed it over instantly."""
    ev = CatEvent(MID + 600, MID)
    ev.update(1 / 60, _Sup(MID, MID), ParticleSystem())
    assert ev.active and not ev.complete
    ev.update(1 / 60, _Sup(MID + 600, MID), ParticleSystem())
    assert ev.complete and ev.cat.saved
