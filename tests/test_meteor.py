"""The meteor's active path, plus a guard on the per-EventType lookup tables.

test_smoke.py only ever exercises a *dormant* meteor: Superman never moves and
MIN_SPAWN_D keeps every spawn outside the 350px activation radius. Everything
interesting therefore needs driving by hand here. Descent is driven by setting
ev.alt directly rather than stepping 26 real seconds of dt.
"""
import pygame
import pytest

import main
from constants import (CAT_COLORS, EVENT_CAT, EVENT_HINTS, EVENT_NAMES,
                       SCORE_TABLE, EventType)
from events import (EVENT_FACTORIES, FireEvent, Meteor, MeteorEvent,
                    RubbleEvent)
from particles import ParticleSystem

DT = 1 / 60


class _Sup:
    """The slice of Superman an event's update() actually touches."""

    def __init__(self, x=0.0, y=0.0):
        self.x, self.y = x, y
        self.heat_firing = False
        self.freeze_active = False
        self.xray_remaining = 0.0

    def heat_covers(self, wx, wy, threshold=28):
        return self.heat_firing


def _activated(x=1000.0, y=1000.0):
    """A meteor with its core built, without needing a real Superman nearby."""
    ev = MeteorEvent(x, y)
    sup = _Sup(x, y)
    ev.active = True
    ev.on_activate(sup)
    return ev, sup, ParticleSystem()


# ─── registration ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("etype", list(EventType))
def test_every_event_type_is_fully_registered(etype):
    """All five tables are unguarded dict lookups in BaseEvent.__init__, and
    spawn_random_event iterates list(EventType), so a new member missing an
    entry is a KeyError at spawn time -- which a 1-in-15 spawn share does not
    reliably reproduce by playing."""
    assert etype in EVENT_FACTORIES
    assert etype in EVENT_CAT and EVENT_CAT[etype] in CAT_COLORS
    assert etype in EVENT_NAMES
    assert etype in EVENT_HINTS
    assert etype in SCORE_TABLE


# ─── the two win routes ───────────────────────────────────────────────────────

def test_overload_completes_without_failing():
    ev, sup, pfs = _activated()
    sup.heat_firing = True
    for _ in range(int(7 / DT)):          # HEAT_RATE is 1/6 per second
        ev.update(DT, sup, pfs)
        assert not (ev.complete and ev.failed)
        if ev.complete:
            break
    assert ev.complete and not ev.failed
    assert ev.heat >= 1.0
    assert ev.spawned_events == []


def test_hp_depletion_completes_without_failing():
    ev, sup, pfs = _activated()
    for _ in range(4):                    # PUNCH_DMG 55 x 4 == Meteor.HP
        ev.core.take_damage(55)
    ev.update(DT, sup, pfs)
    assert ev.complete and not ev.failed
    assert not ev.core.alive


def test_heat_decays_when_the_beam_lapses():
    ev, sup, pfs = _activated()
    sup.heat_firing = True
    for _ in range(int(2 / DT)):
        ev.update(DT, sup, pfs)
    peak = ev.heat
    assert peak > 0
    sup.heat_firing = False
    for _ in range(int(2 / DT)):
        ev.update(DT, sup, pfs)
    assert ev.heat < peak


# ─── impact and the chain ─────────────────────────────────────────────────────

def test_impact_fails_and_queues_exactly_one_follow_up():
    ev, sup, pfs = _activated()
    ev.alt = 0.002                        # a few frames of descent from here
    for _ in range(10):
        ev.update(DT, sup, pfs)
        if ev.failed:
            break
    assert ev.failed and not ev.complete
    assert len(ev.spawned_events) == 1
    assert isinstance(ev.spawned_events[0], (FireEvent, RubbleEvent))


def test_impact_without_a_city_still_burns():
    """No city means no building was ever targeted, so it can only start a fire."""
    ev, sup, pfs = _activated()
    assert ev.city is None and not ev._hit_building
    ev.alt = 0.0
    ev.update(DT, sup, pfs)
    assert isinstance(ev.spawned_events[0], FireEvent)


def test_softened_fail_penalty():
    assert MeteorEvent.fail_penalty == 6


def test_a_driven_descent_never_sets_both_flags():
    ev, sup, pfs = _activated()
    for _ in range(int(30 / DT)):
        ev.update(DT, sup, pfs)
        assert not (ev.complete and ev.failed)
        if ev.complete or ev.failed:
            break
    assert ev.failed, "an unopposed meteor must land"


def test_freeze_slows_the_descent():
    slow, sup_s, pfs_s = _activated()
    fast, sup_f, pfs_f = _activated()
    for _ in range(int(3 / DT)):
        slow.core.freeze(0.35)            # what a held cone does, at 8Hz
        slow.update(DT, sup_s, pfs_s)
        fast.update(DT, sup_f, pfs_f)
    assert slow.alt > fast.alt


def test_descent_is_monotonic_even_under_permanent_freeze():
    """FROZEN_MUL is never 0, so the event always terminates."""
    ev, sup, pfs = _activated()
    prev = ev.alt
    for _ in range(int(5 / DT)):
        ev.core.freeze(0.35)
        ev.update(DT, sup, pfs)
        assert ev.alt < prev
        prev = ev.alt


# ─── the exploit the core-on-activate placement closes ────────────────────────

def test_dormant_meteor_exposes_no_target():
    """Heat reaches 520px and punch 450px, both beyond the 350px activation
    radius, so a core existing before activation could be destroyed -- and
    scored -- from outside the event."""
    ev = MeteorEvent(500.0, 500.0)
    assert ev.core is None
    assert ev.enemies == []


def test_dormant_meteor_does_not_move():
    ev = MeteorEvent(500.0, 500.0)
    sup, pfs = _Sup(5000.0, 5000.0), ParticleSystem()
    for _ in range(int(3 / DT)):
        ev.update(DT, sup, pfs)
    assert ev.alt == 1.0


def test_krypto_leaves_the_meteor_alone():
    assert Meteor.minion_auto_attack is False


# ─── the tuning the design depends on ─────────────────────────────────────────

def test_overload_beats_the_beams_own_hp_damage():
    """Heat vision drains HP as well as charging heat, because the core rides in
    self.enemies. If HP death arrived first the heat bar would be decorative."""
    from entities import Superman
    hp_route = Meteor.HP / Superman.HEAT_DPS
    overload_route = 1 / MeteorEvent.HEAT_RATE
    assert overload_route < hp_route


def test_prompt_radius_exceeds_activation_radius():
    """Otherwise the 'fly into event area' prompt could never fire -- the event
    would already be live before the player reached the prompt's range."""
    assert MeteorEvent.ACTIVATION_RADIUS > MeteorEvent.INNER_RADIUS


# ─── end to end, through a real Game ──────────────────────────────────────────

def test_follow_up_lands_in_the_live_event_list(monkeypatch):
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (False, False, False))
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (640, 360))
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: type(
        "K", (), {"__getitem__": lambda self, k: False})())
    game = main.start_game()
    try:
        game._mouse_gate = [False, False, False]
        game.events.clear()

        ev = MeteorEvent(game.superman.x, game.superman.y)
        ev.city = game.city
        game.events.append(ev)
        ev.active = True
        ev.on_activate(game.superman)
        ev.alt = 0.0

        game.update(DT)

        assert ev not in game.events, "the meteor should be cleaned up on impact"
        assert len(game.events) == 1
        assert isinstance(game.events[0], (FireEvent, RubbleEvent))
        assert game.events[0].city is game.city
        game.draw()
    finally:
        game.stop_sounds()
        main.stop_music()


def test_meteor_targets_a_real_building(monkeypatch):
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (False, False, False))
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (640, 360))
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: type(
        "K", (), {"__getitem__": lambda self, k: False})())
    game = main.start_game()
    try:
        x, y = game.city.random_open_position()
        ev = MeteorEvent(x, y)
        ev.city = game.city
        ev.active = True
        ev.on_activate(_Sup(x, y))
        assert ev._hit_building, "an open spawn should find a building nearby"
        assert any(b.rect.center == (ev.target_x, ev.target_y)
                   for b in game.city.buildings)
    finally:
        game.stop_sounds()
        main.stop_music()
