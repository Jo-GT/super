"""Geometry behind the off-screen event markers.

`_edge_point` and `_avoid_furniture` are module-level and pure, so this needs no
display and no Game -- which is the point of keeping them out of the class.
"""
import math

import pytest

from constants import SCREEN_H, SCREEN_W
from hud import (MARK_B, MARK_L, MARK_R, MARK_T, _avoid_furniture, _edge_point,
                 _rot_pt)

CENTRE = (SCREEN_W / 2, SCREEN_H / 2)


def _unit(dx, dy):
    d = math.hypot(dx, dy)
    return dx / d, dy / d


@pytest.mark.parametrize("dx, dy", [
    (1, 0), (-1, 0), (0, 1), (0, -1),
    (1, 1), (-1, 1), (1, -1), (-1, -1),
    (3, 1), (-1, 4), (0.2, -5),
])
def test_edge_point_lands_on_a_band_bound(dx, dy):
    """Every marker sits exactly on the band, never a pixel outside it."""
    x, y, edge = _edge_point(*CENTRE, *_unit(dx, dy))
    assert MARK_L - 0.001 <= x <= MARK_R + 0.001
    assert MARK_T - 0.001 <= y <= MARK_B + 0.001
    on_side = math.isclose(x, MARK_L) or math.isclose(x, MARK_R)
    on_cap = math.isclose(y, MARK_T) or math.isclose(y, MARK_B)
    assert on_side or on_cap
    assert edge == ('v' if on_side else 'h')


def test_edge_point_picks_the_side_the_target_is_on():
    x, _, edge = _edge_point(*CENTRE, *_unit(1, 0))
    assert (x, edge) == (MARK_R, 'v')
    x, _, edge = _edge_point(*CENTRE, *_unit(-1, 0))
    assert (x, edge) == (MARK_L, 'v')
    _, y, edge = _edge_point(*CENTRE, *_unit(0, 1))
    assert (y, edge) == (MARK_B, 'h')
    _, y, edge = _edge_point(*CENTRE, *_unit(0, -1))
    assert (y, edge) == (MARK_T, 'h')


def test_origin_is_superman_not_screen_centre():
    """The regression test for the whole design.

    Camera pinned at the world's top-left corner, so Superman is nowhere near
    the middle of the screen: world (200, 150) with camera (0, 0) puts him at
    screen (200, 150). The event at world (300, 2000) is below and slightly to
    his RIGHT, so the marker must land right of him.

    Measured from the screen centre (640, 360) the same event bears down and to
    the LEFT, which is where an arrow would point if the origin were the centre
    -- a wrong heading precisely in the corners where players get lost.
    """
    sup_sx, sup_sy = 200.0, 150.0
    ev_x, ev_y = 300.0, 2000.0

    ox = min(max(sup_sx, MARK_L + 1), MARK_R - 1)
    oy = min(max(sup_sy, MARK_T + 1), MARK_B - 1)
    mx, my, edge = _edge_point(ox, oy, *_unit(ev_x - 200.0, ev_y - 150.0))

    assert edge == 'h' and my == MARK_B
    assert mx > ox, "marker must sit right of Superman, not left"

    # And the centre-origin version really does disagree, so this test is
    # actually discriminating rather than trivially true.
    cx, _, _ = _edge_point(*CENTRE, *_unit(ev_x - CENTRE[0], ev_y - CENTRE[1]))
    assert cx < CENTRE[0]


def test_superman_outside_the_band_still_gives_a_valid_marker():
    """He can sit outside the band at a world edge; only the origin is clamped."""
    ox = min(max(5.0, MARK_L + 1), MARK_R - 1)
    oy = min(max(5.0, MARK_T + 1), MARK_B - 1)
    x, y, _ = _edge_point(ox, oy, *_unit(1, 2))
    assert MARK_L <= x <= MARK_R and MARK_T <= y <= MARK_B


def test_avoid_furniture_clears_the_power_row():
    x, y = _avoid_furniture(640.0, float(MARK_B), 'h')
    assert not (444 - 20 < x < 444 + 392 + 20)
    assert MARK_L <= x <= MARK_R


def test_avoid_furniture_clears_the_minimap():
    _, y = _avoid_furniture(float(MARK_R), 620.0, 'v')
    assert not (542 - 20 < y < 542 + 178 + 20)
    assert MARK_T <= y <= MARK_B


def test_avoid_furniture_leaves_a_clear_marker_alone():
    assert _avoid_furniture(200.0, float(MARK_T), 'h') == (200.0, MARK_T)


def test_rot_pt_needs_no_negation():
    """A local +x point rotated by atan2(dy, dx) points straight at the target."""
    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1), (3, -4)):
        ang = math.atan2(dy, dx)
        x, y = _rot_pt(0.0, 0.0, 10.0, 0.0, ang)
        ux, uy = _unit(dx, dy)
        assert x == pytest.approx(ux * 10, abs=1e-9)
        assert y == pytest.approx(uy * 10, abs=1e-9)
