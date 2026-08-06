import pygame
import math
import random
import os
from constants import *
import audio

_SPRITES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites", "superman")
_LEXCORP_SPRITES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites", "lexcorp")


def _load_lex_sprite(filename, size):
    try:
        path = os.path.join(_LEXCORP_SPRITES_DIR, filename)
        img = pygame.image.load(path).convert_alpha()
        return pygame.transform.smoothscale(img, size)
    except Exception:
        return None


_GAME_SPRITES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites")


def load_game_sprite(rel_path, size):
    """Load a sprite from anywhere under sprites/ (rel_path uses forward
    slashes, e.g. "Metallo/metallo.png"), scaled to an exact size."""
    try:
        path = os.path.join(_GAME_SPRITES_DIR, *rel_path.split("/"))
        img = pygame.image.load(path).convert_alpha()
        return pygame.transform.smoothscale(img, size)
    except Exception:
        return None


def load_sprite_sheet(rel_path, frame_count, frame_size):
    """Load a horizontal strip sheet from anywhere under sprites/, split into
    frame_count equal-width frames, each scaled to a common frame_size (w, h)."""
    try:
        path = os.path.join(_GAME_SPRITES_DIR, *rel_path.split("/"))
        sheet = pygame.image.load(path).convert_alpha()
        sw, sh = sheet.get_size()
        fw = sw // frame_count
        frames = []
        for i in range(frame_count):
            frame = sheet.subsurface((i * fw, 0, fw, sh))
            frames.append(pygame.transform.smoothscale(frame, frame_size))
        return frames
    except Exception:
        return []


_KRYPTO_SPRITES_DIR = os.path.join(_GAME_SPRITES_DIR, "Krypto")
_KRYPTO_SCALE = 0.34  # single physical scale applied to both sheets so the bite
                      # pose's taller lunge reads as the same dog, just airborne


def _krypto_pose_spans(sheet, frame_count, min_gap=8):
    """Column ranges of each pose, or None if the sheet doesn't look as expected.

    The Krypto sheets aren't an even grid - the poses sit at irregular intervals
    and the widths don't divide by the frame count - so slicing at fixed offsets
    clips each dog and drags the previous pose's tail into the next cell. Find
    the poses by their transparent gutters instead. Gaps under min_gap are holes
    inside a pose (the art has a few 1px ones), not gutters between poses.
    """
    sw, sh = sheet.get_size()
    filled = [sheet.subsurface((x, 0, 1, sh)).get_bounding_rect(min_alpha=1).height > 0
              for x in range(sw)]
    runs, start = [], None
    for x in range(sw):
        if filled[x] and start is None:
            start = x
        elif not filled[x] and start is not None:
            runs.append((start, x - 1))
            start = None
    if start is not None:
        runs.append((start, sw - 1))

    spans = []
    for x0, x1 in runs:
        if spans and x0 - spans[-1][1] - 1 < min_gap:
            spans[-1] = (spans[-1][0], x1)
        else:
            spans.append((x0, x1))
    return spans if len(spans) == frame_count else None


def _load_krypto_frames(filename, frame_count):
    try:
        path = os.path.join(_KRYPTO_SPRITES_DIR, filename)
        sheet = pygame.image.load(path).convert_alpha()
        sw, sh = sheet.get_size()
        spans = _krypto_pose_spans(sheet, frame_count)
        if spans is None:  # unexpected art: fall back to an even grid
            fw = sw // frame_count
            spans = [(i * fw, i * fw + fw - 1) for i in range(frame_count)]
        # One cell size for every pose, so the dog keeps a single scale and
        # doesn't pop between frames. Full sheet height keeps the artist's
        # vertical bob and the bite pose's lunge.
        cell_w = max(x1 - x0 + 1 for x0, x1 in spans)
        tw, th = max(1, round(cell_w * _KRYPTO_SCALE)), max(1, round(sh * _KRYPTO_SCALE))
        frames = []
        for x0, x1 in spans:
            cell = pygame.Surface((cell_w, sh), pygame.SRCALPHA)
            cell.blit(sheet, ((cell_w - (x1 - x0 + 1)) // 2, 0), (x0, 0, x1 - x0 + 1, sh))
            frames.append(pygame.transform.smoothscale(cell, (tw, th)))
        return frames
    except Exception:
        return []


def _load_krypto_sound(filename):
    try:
        return pygame.mixer.Sound(os.path.join(_KRYPTO_SPRITES_DIR, filename))
    except Exception:
        return None


_ANIMAL_SPRITE_FILES = {
    'cat': ["black cat.png", "brown cat.png", "white cat.png"],
    'dog': ["black dog.png", "brown dog.png", "white dog.png"],
    'bird': ["bird.png"],
}
_ANIMAL_TARGET_H = {'cat': 30, 'dog': 24, 'bird': 20}
_animal_sprite_cache = {}


def _get_animal_sprite(kind, filename):
    key = (kind, filename)
    if key not in _animal_sprite_cache:
        try:
            path = os.path.join(_GAME_SPRITES_DIR, "Animals", filename)
            img = pygame.image.load(path).convert_alpha()
            w, h = img.get_size()
            th = _ANIMAL_TARGET_H[kind]
            tw = max(1, round(th * w / h))
            _animal_sprite_cache[key] = pygame.transform.smoothscale(img, (tw, th))
        except Exception:
            _animal_sprite_cache[key] = False
    return _animal_sprite_cache[key] or None


def _rot(cx, cy, dx, dy, angle):
    c, s = math.cos(angle), math.sin(angle)
    return cx + dx * c - dy * s, cy + dx * s + dy * c


def visible_rect(px, py):
    """The world rect on screen while the camera follows (px, py).

    Mirrors main.Camera.update: it centres on its target and then clamps to the
    world, so near an edge the view is not centred on the player at all and a
    plain box around him would be wrong. Events need this to know when they have
    come into view, and events.py cannot import main.py (which imports it), so
    the clamp is duplicated here -- tests/test_visibility.py drives a real
    Camera and pins the two together.
    """
    cx = max(0, min(WORLD_W - SCREEN_W, px - SCREEN_W / 2))
    cy = max(0, min(WORLD_H - SCREEN_H, py - SCREEN_H / 2))
    return pygame.Rect(int(cx), int(cy), SCREEN_W, SCREEN_H)


def draw_health_bar(surface, x, y, hp, max_hp, width=30):
    pygame.draw.rect(surface, (60, 0, 0), (x - width // 2, y, width, 5))
    ratio = max(0, hp / max_hp)
    col = GREEN if ratio > 0.5 else (GOLD if ratio > 0.25 else RED)
    if ratio > 0:
        pygame.draw.rect(surface, col, (x - width // 2, y, int(width * ratio), 5))


# ─── SUPERMAN ────────────────────────────────────────────────────────────────

class Superman:
    SPEED      = 5.8
    ACCEL      = 0.9
    DRAG       = 0.80
    MAX_HP     = 100
    HEAT_CD    = 0.08
    FREEZE_CD  = 0.12
    FREEZE_LOCK = 0.35
    PUNCH_CD   = 1.8
    SPEED_CD   = 14.0
    SPEED_DUR  = 4.0
    XRAY_CD    = 9.0
    XRAY_DUR   = 5.0
    PUNCH_RANGE = 450
    HEAT_RANGE  = 520
    FREEZE_RANGE = 180
    XRAY_RANGE  = 520
    PUNCH_DMG   = 55
    HEAT_DPS    = 22

    # Local head offset (from sprite center, unrotated/unflipped) for each pose,
    # measured from the actual sprite art so heat vision always exits the head.
    HEAD_OFFSET_FLY   = (32, -12)
    HEAD_OFFSET_HOVER = (4, -23)

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.facing = 0.0
        self.hp = self.MAX_HP
        self._regen_pause = 0.0
        self._hit_flash = 0.0
        self.krypto_debuff = 0.0
        self.heat_cd = 0.0
        self.freeze_cd = 0.0
        self.punch_cd = 0.0
        self.speed_cd = 0.0
        self.speed_remaining = 0.0
        self.xray_cd = 0.0
        self.xray_remaining = 0.0
        self._trail: list[tuple] = []
        self.score = 0
        self.reputation = 50
        self.alive = True
        self.heat_firing = False
        self.freeze_active = False
        self.head_pos = (self.x, self.y)
        self.aim_world = None    # last cursor position, for aiming the beam

        # Sprites: flying (moving), hover (idle), death
        self._sprite_fly   = Superman._load_sprite("superman flying.png",          (96, 44))
        self._sprite_hover = Superman._load_sprite("superman standing flight.png", (44, 72))
        self._sprite_death = Superman._load_sprite("super-death.png",              (110, 38))

    @staticmethod
    def _load_sprite(filename, size):
        try:
            path = os.path.join(_SPRITES_DIR, filename)
            img = pygame.image.load(path).convert_alpha()
            return pygame.transform.smoothscale(img, size)
        except Exception:
            return None

    @property
    def rect(self):
        return pygame.Rect(int(self.x) - 14, int(self.y) - 14, 28, 28)

    def take_damage(self, amount, krypto_mult=True):
        if krypto_mult and self.krypto_debuff > 0:
            amount *= 1.6
        self.hp = max(0, self.hp - amount)
        self._regen_pause = 2.5
        self._hit_flash = 0.25
        if self.hp <= 0:
            self.alive = False

    def update(self, dt, keys, mouse_world):
        # Cooldowns
        self.heat_cd     = max(0, self.heat_cd  - dt)
        self.freeze_cd   = max(0, self.freeze_cd - dt)
        self.punch_cd    = max(0, self.punch_cd  - dt)
        self.speed_cd    = max(0, self.speed_cd  - dt)
        self.xray_cd     = max(0, self.xray_cd   - dt)
        self._hit_flash  = max(0, self._hit_flash - dt)
        self.krypto_debuff = max(0, self.krypto_debuff - dt)

        if self.speed_remaining > 0:
            self.speed_remaining -= dt
            if self.speed_remaining <= 0:
                self.speed_remaining = 0.0
                self.speed_cd = self.SPEED_CD  # ran the full duration -> full cooldown

        if self.xray_remaining > 0:
            # No early cancel, so unlike speed this always charges the full cooldown
            self.xray_remaining -= dt
            if self.xray_remaining <= 0:
                self.xray_remaining = 0.0
                self.xray_cd = self.XRAY_CD

        if self._regen_pause > 0:
            self._regen_pause -= dt
        elif self.hp < self.MAX_HP:
            rate = 5.0 * (0.4 if self.krypto_debuff > 0 else 1.0)
            self.hp = min(self.MAX_HP, self.hp + rate * dt)

        # Facing toward mouse
        dx = mouse_world[0] - self.x
        dy = mouse_world[1] - self.y
        if dx * dx + dy * dy > 4:
            self.facing = math.atan2(dy, dx)
        self.aim_world = mouse_world

        # Movement
        spd = self.SPEED * (3.0 if self.speed_remaining > 0 else 1.0)
        spd *= 0.55 if self.krypto_debuff > 0 else 1.0
        ax = ay = 0.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:    ay -= self.ACCEL
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  ay += self.ACCEL
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  ax -= self.ACCEL
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: ax += self.ACCEL
        if ax and ay:
            ax *= 0.7071; ay *= 0.7071

        self.vx = (self.vx + ax * spd) * self.DRAG
        self.vy = (self.vy + ay * spd) * self.DRAG
        mag = math.hypot(self.vx, self.vy)
        cap = spd * 1.6
        if mag > cap:
            self.vx = self.vx / mag * cap
            self.vy = self.vy / mag * cap

        self.x = max(20, min(WORLD_W - 20, self.x + self.vx))
        self.y = max(20, min(WORLD_H - 20, self.y + self.vy))

        # Cape trail
        if math.hypot(self.vx, self.vy) > 0.5:
            self._trail.append((self.x, self.y, 0.0))
        self._trail = [(tx, ty, ta + dt) for tx, ty, ta in self._trail if ta + dt < 0.35]

    # ── Powers ────────────────────────────────────────────────────────────────

    def aim_angle(self):
        """Direction from the head to the cursor, for anything fired from it.

        Deliberately not self.facing: that is measured from the body centre and
        drives the sprite. Heat vision and freeze breath both leave the head, so
        aiming them along facing sent them parallel to the body-to-cursor line
        but offset from it by the head offset, and they visibly missed what you
        were pointing at.
        """
        if self.aim_world is None:
            return self.facing
        dx = self.aim_world[0] - self.head_pos[0]
        dy = self.aim_world[1] - self.head_pos[1]
        if dx * dx + dy * dy < 4:      # cursor on the head; no meaningful angle
            return self.facing
        return math.atan2(dy, dx)

    def heat_beam_target(self):
        """Far end of the beam: out from the head, through the cursor, to range."""
        a = self.aim_angle()
        hx, hy = self.head_pos
        return (hx + math.cos(a) * self.HEAT_RANGE,
                hy + math.sin(a) * self.HEAT_RANGE)

    def heat_beam_hits(self, enemies):
        """Whether the beam is touching anything right now.

        Deliberately separate from try_heat_vision's damage pass, which is
        rate-limited to HEAT_CD (12.5Hz). The contact sound wants a per-frame
        answer or it lags the visual by up to 80ms.
        """
        tx, ty = self.heat_beam_target()
        return any(self._in_beam(e.x, e.y, tx, ty, 28) for e in enemies)

    def try_heat_vision(self, enemies, particles):
        if self.heat_cd > 0:
            return
        self.heat_cd = self.HEAT_CD
        hx, hy = self.head_pos
        tx, ty = self.heat_beam_target()
        particles.heat_beam(hx, hy, tx, ty)
        for e in enemies:
            if self._in_beam(e.x, e.y, tx, ty, 28):
                e.take_damage(self.HEAT_DPS * self.HEAT_CD)

    def try_freeze(self, enemies, particles):
        if self.freeze_cd > 0:
            return False
        self.freeze_cd = self.FREEZE_CD
        hx, hy = self.head_pos
        aim = self.aim_angle()
        particles.frost_breath(hx, hy, aim, self.FREEZE_RANGE)
        for e in enemies:
            dx = e.x - hx
            dy = e.y - hy
            d = math.hypot(dx, dy)
            if d < self.FREEZE_RANGE:
                a = math.atan2(dy, dx)
                diff = abs((a - aim + math.pi) % (2 * math.pi) - math.pi)
                if diff < 0.75:
                    e.freeze(self.FREEZE_LOCK)
        return True

    def try_punch(self, enemies, particles):
        if self.punch_cd > 0:
            return False
        nearest = None
        best_d = self.PUNCH_RANGE
        for e in enemies:
            d = math.hypot(e.x - self.x, e.y - self.y)
            if d < best_d:
                best_d = d; nearest = e
        if nearest is None:
            return False
        self.punch_cd = self.PUNCH_CD
        self.x, self.y = nearest.x, nearest.y
        particles.shockwave(self.x, self.y)
        for e in enemies:
            if math.hypot(e.x - self.x, e.y - self.y) < 90:
                e.take_damage(self.PUNCH_DMG)
        return True

    def try_speed(self):
        if self.speed_cd > 0 or self.speed_remaining > 0:
            return False
        self.speed_remaining = self.SPEED_DUR
        return True

    def stop_speed(self):
        # Toggled off early: only charge cooldown for the time actually used
        if self.speed_remaining <= 0:
            return
        used = self.SPEED_DUR - self.speed_remaining
        self.speed_cd = self.SPEED_CD * (used / self.SPEED_DUR)
        self.speed_remaining = 0.0

    def try_xray(self):
        if self.xray_cd > 0 or self.xray_remaining > 0:
            return False
        self.xray_remaining = self.XRAY_DUR
        return True

    def xray_reveals(self, wx, wy):
        """True while an X-ray burst is up and (wx, wy) is inside the scan sphere.

        A radius, not a cone like freeze_covers: freeze breath is aimed and held,
        so the player is already looking at whatever they're dousing. The X-ray
        burst runs on a timer while the player keeps flying and keeps aiming the
        mouse at other things, and a cone would blink buried objects in and out
        as the mouse moved. Centred on the body, not head_pos -- it's a sphere
        around him, not something emitted from his face.
        """
        if self.xray_remaining <= 0:
            return False
        return math.hypot(wx - self.x, wy - self.y) < self.XRAY_RANGE

    def _in_beam(self, px, py, tx, ty, threshold=28):
        ax, ay = self.head_pos
        bx, by = tx, ty
        dx, dy = bx - ax, by - ay
        lsq = dx * dx + dy * dy
        if lsq == 0:
            return False
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / lsq))
        closest_x = ax + t * dx
        closest_y = ay + t * dy
        return math.hypot(px - closest_x, py - closest_y) < threshold

    def freeze_covers(self, wx, wy):
        hx, hy = self.head_pos
        dx, dy = wx - hx, wy - hy
        d = math.hypot(dx, dy)
        if d > self.FREEZE_RANGE:
            return False
        a = math.atan2(dy, dx)
        diff = abs((a - self.aim_angle() + math.pi) % (2 * math.pi) - math.pi)
        return diff < 0.75

    def heat_covers(self, wx, wy, threshold=28):
        """Whether the heat beam's line passes within `threshold` of (wx, wy).

        The counterpart to freeze_covers, and the same contract: it answers
        about geometry only, so the caller gates on self.heat_firing the way
        FireEvent gates its douse on freeze_active.

        Exists because try_heat_vision applies damage in HEAT_CD ticks against
        an enemy list. Anything that instead accumulates against the beam
        smoothly over dt -- a charge meter rather than a health pool -- has to
        ask per frame, and doing that from outside meant reaching into _in_beam
        and re-deriving the endpoint. threshold is a parameter because a target
        that visibly grows wants a hitbox that grows with it.
        """
        tx, ty = self.heat_beam_target()
        return self._in_beam(wx, wy, tx, ty, threshold)

    def draw(self, surface, cam):
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)

        # Cape trail
        for i, (tx, ty, ta) in enumerate(reversed(self._trail)):
            ratio = max(0.0, 1.0 - ta / 0.35)
            alpha = int(210 * ratio)
            tsz = max(2, int(8 * ratio))
            ts = pygame.Surface((tsz * 2 + 2, tsz * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(ts, (*CAPE_RED, alpha), (tsz, tsz), tsz)
            surface.blit(ts, (int(tx - cam.x) - tsz, int(ty - cam.y) - tsz))

        # Choose sprite based on state
        spd = math.hypot(self.vx, self.vy)
        if not self.alive:
            base = self._sprite_death
        elif spd > 0.8:
            base = self._sprite_fly
        else:
            base = self._sprite_hover

        # The hover pose is a tall standing figure, so it only ever mirrors -- tilting it
        # would lay him on his side. Flying and death poses rotate to point at the cursor.
        upright = base is self._sprite_hover
        flip_x = math.cos(self.facing) < 0

        # Head position in world space, put through the same flip/rotate the sprite gets
        # below so effects (heat vision) track the actual rendered head, not the body center.
        hdx, hdy = self.HEAD_OFFSET_HOVER if upright else self.HEAD_OFFSET_FLY
        if upright:
            hpx, hpy = (-hdx if flip_x else hdx), hdy
        else:
            # Mirroring across x and then rotating by (180 - facing) comes out the same as
            # negating the local y offset and rotating by facing.
            if flip_x:
                hdy = -hdy
            c, s = math.cos(self.facing), math.sin(self.facing)
            hpx = hdx * c - hdy * s
            hpy = hdx * s + hdy * c
        self.head_pos = (self.x + hpx, self.y + hpy)

        if base is not None:
            # Sprites face right at angle 0, so mirror horizontally when the cursor is on
            # his left. pygame rotates counter-clockwise while facing is in y-down screen
            # space, hence the negation; and a mirrored sprite starts out pointing left
            # (180), so it needs 180 - facing to end up along facing.
            draw_sprite = pygame.transform.flip(base, True, False) if flip_x else base
            if upright:
                rotated = draw_sprite
            else:
                angle_deg = (180.0 - math.degrees(self.facing)) if flip_x else -math.degrees(self.facing)
                rotated = pygame.transform.rotate(draw_sprite, angle_deg)
            rect = rotated.get_rect(center=(sx, sy))

            # Tint overlays (hit flash → white; kryptonite → green)
            if self._hit_flash > 0:
                tinted = rotated.copy()
                tinted.fill((180, 180, 180, 0), special_flags=pygame.BLEND_RGB_ADD)
                surface.blit(tinted, rect)
            elif self.krypto_debuff > 0:
                tinted = rotated.copy()
                tinted.fill((0, 50, 0, 0), special_flags=pygame.BLEND_RGB_ADD)
                surface.blit(tinted, rect)
            else:
                surface.blit(rotated, rect)
        else:
            # Fallback if sprites failed to load
            pygame.draw.circle(surface, BLUE_S, (sx, sy), 16)
            pygame.draw.circle(surface, YELLOW_S, (sx, sy), 6)

        # Heat vision eye glow, anchored to the head
        if self.heat_firing:
            ex = int(self.head_pos[0] - cam.x)
            ey = int(self.head_pos[1] - cam.y)
            gs = pygame.Surface((16, 16), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*FIRE_HOT, 200), (8, 8), 6)
            surface.blit(gs, (ex - 8, ey - 8))

        # Krypto aura
        if self.krypto_debuff > 0:
            ks = pygame.Surface((60, 60), pygame.SRCALPHA)
            alpha = int(80 + 60 * abs(math.sin(pygame.time.get_ticks() * 0.005)))
            pygame.draw.circle(ks, (*KRYPTO, alpha), (30, 30), 28)
            surface.blit(ks, (sx - 30, sy - 30))

        # Speed aura
        if self.speed_remaining > 0:
            ss = pygame.Surface((60, 60), pygame.SRCALPHA)
            pygame.draw.circle(ss, (*CYAN, 60), (30, 30), 28)
            surface.blit(ss, (sx - 30, sy - 30))

        # HP bar (only when damaged)
        if self.hp < self.MAX_HP:
            draw_health_bar(surface, sx, sy - 28, self.hp, self.MAX_HP, 36)


# ─── ENEMIES ─────────────────────────────────────────────────────────────────

class Enemy:
    SPEED = 1.5
    HP    = 40
    DMG   = 6.0
    RADIUS = 14
    COLOR  = GRAY

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.hp = self.HP
        self.max_hp = self.HP
        self.frozen = 0.0
        self._angle = 0.0
        self._hit_flash = 0.0
        self.alive = True
        self.attack_cd = 0.0

    @property
    def rect(self):
        r = self.RADIUS
        return pygame.Rect(int(self.x) - r, int(self.y) - r, r * 2, r * 2)

    def take_damage(self, amount):
        self.hp -= amount
        self._hit_flash = 0.2
        if self.hp <= 0:
            self.alive = False

    def freeze(self, duration):
        self.frozen = max(self.frozen, duration)

    def _move_toward(self, tx, ty, dt, speed_mul=1.0):
        dx, dy = tx - self.x, ty - self.y
        d = math.hypot(dx, dy)
        if d > 2:
            spd = self.SPEED * speed_mul * (0.25 if self.frozen > 0 else 1.0)
            self.x += dx / d * spd
            self.y += dy / d * spd
        self._angle = math.atan2(ty - self.y, tx - self.x)

    def _base_update(self, dt):
        self._hit_flash = max(0, self._hit_flash - dt)
        if self.frozen > 0:
            self.frozen -= dt
        self.attack_cd = max(0, self.attack_cd - dt)

    def try_attack(self, superman, dt):
        d = math.hypot(superman.x - self.x, superman.y - self.y)
        if d < 35 and self.attack_cd <= 0:
            if self.DMG > 0:
                superman.take_damage(self.DMG)
            self.attack_cd = 1.0

    def _draw_base(self, surface, cam, color=None):
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)
        c = WHITE if self._hit_flash > 0 else (color or self.COLOR)
        if self.frozen > 0:
            c = ICE
        pygame.draw.circle(surface, c, (sx, sy), self.RADIUS)
        pygame.draw.circle(surface, BLACK, (sx, sy), self.RADIUS, 2)
        draw_health_bar(surface, sx, sy - self.RADIUS - 8, self.hp, self.max_hp, self.RADIUS * 2)

    def update(self, dt, superman, particles):
        pass

    def draw(self, surface, cam):
        pass


class Thug(Enemy):
    """Gun-toting street criminal: closes in to shooting range, then holds
    position alternating idle/shoot until its clip is spent, reloads, repeats."""
    # Bulletproof: regular gunfire just ricochets off Superman (see the hit
    # handling in update() below), so ordinary thug/goon bullets do 0 damage.
    HP = 35; SPEED = 1.8; DMG = 0; COLOR = (80, 80, 80); RADIUS = 14

    # LexGoon reskins this class and turns it off; the Lex-employed goons stay
    # silent while the generic street thugs get gunshot/reload clips.
    GUN_SOUNDS = True

    STOP_RANGE    = 260   # stands and shoots once this close instead of closing in
    SHOT_SPEED    = 5.5
    SHOT_INTERVAL = 2.2
    MAG_SIZE      = 3
    RELOAD_TIME   = 1.7   # matches the 17-frame reload animation at RELOAD_FPS

    IDLE_FPS   = 8
    WALK_FPS   = 12
    SHOT_FPS   = 12
    RELOAD_FPS = 10

    _FRAME_SIZE = (96, 96)
    _idle_frames = None
    _walk_frames = None
    _shot_frames = None
    _reload_frames = None
    _loaded = False

    def __init__(self, x, y):
        super().__init__(x, y)
        if not Thug._loaded:
            Thug._idle_frames   = load_sprite_sheet("Generic Criminal Goons/Idle_2.png", 11, self._FRAME_SIZE)
            Thug._walk_frames   = load_sprite_sheet("Generic Criminal Goons/Walk.png", 10, self._FRAME_SIZE)
            Thug._shot_frames   = load_sprite_sheet("Generic Criminal Goons/Shot.png", 4, self._FRAME_SIZE)
            Thug._reload_frames = load_sprite_sheet("Generic Criminal Goons/reload.png", 17, self._FRAME_SIZE)
            Thug._loaded = True
        self.projectiles: list[Projectile] = []
        self.shot_cd = random.uniform(0, self.SHOT_INTERVAL)
        self.shots_fired = 0
        self.reload_t = 0.0
        self.face_right = False
        self._anim_state = 'idle'
        self._anim_t = 0.0
        self._frame = 0

    def _frames_for(self, state):
        return {'idle': self._idle_frames, 'walk': self._walk_frames,
                'shot': self._shot_frames, 'reload': self._reload_frames}[state]

    def _set_anim(self, state):
        self._anim_state = state
        self._frame = 0
        self._anim_t = 0.0

    def _tick_anim(self, dt, fps, loop=True):
        frames = self._frames_for(self._anim_state)
        if not frames:
            return
        step = 1.0 / fps
        self._anim_t += dt
        while self._anim_t >= step:
            self._anim_t -= step
            if self._frame + 1 < len(frames):
                self._frame += 1
            elif loop:
                self._frame = 0
            # else: hold on the last frame

    def update(self, dt, superman, particles):
        self._base_update(dt)
        dx, dy = superman.x - self.x, superman.y - self.y
        d = math.hypot(dx, dy)
        self._angle = math.atan2(dy, dx)
        if dx:
            self.face_right = dx > 0
        self.shot_cd = max(0.0, self.shot_cd - dt)

        if self.reload_t > 0:
            if self._anim_state != 'reload':
                self._set_anim('reload')
                if self.GUN_SOUNDS and audio.snd_reload:
                    audio.snd_reload.play()
            self.reload_t = max(0.0, self.reload_t - dt)
            self._tick_anim(dt, self.RELOAD_FPS, loop=False)
            if self.reload_t <= 0:
                self.shots_fired = 0
        elif d > self.STOP_RANGE:
            if self._anim_state != 'walk':
                self._set_anim('walk')
            self._move_toward(superman.x, superman.y, dt)
            self._tick_anim(dt, self.WALK_FPS, loop=True)
        elif self.shot_cd <= 0:
            self.shot_cd = self.SHOT_INTERVAL
            self.shots_fired += 1
            self._set_anim('shot')
            if self.GUN_SOUNDS and audio.snd_gunshot:
                audio.snd_gunshot.play()
            self.projectiles.append(
                Projectile(self.x, self.y, self._angle, self.SHOT_SPEED, (255, 210, 120), 3, 1.6, shape='bullet'))
            particles.burst(self.x + math.cos(self._angle) * 22, self.y + math.sin(self._angle) * 22,
                             (255, 200, 80), 4, 2)
            if self.shots_fired >= self.MAG_SIZE:
                self.reload_t = self.RELOAD_TIME
            self._tick_anim(dt, self.SHOT_FPS, loop=False)
        else:
            if self._anim_state not in ('idle', 'shot'):
                self._set_anim('idle')
            fps = self.SHOT_FPS if self._anim_state == 'shot' else self.IDLE_FPS
            self._tick_anim(dt, fps, loop=(self._anim_state != 'shot'))

        for proj in self.projectiles:
            proj.update(dt)
            if proj.hits_superman(superman):
                superman.take_damage(self.DMG)
                if audio.snd_ricochet:
                    audio.snd_ricochet.play()
                particles.burst(superman.x, superman.y, SILVER, 6, 4, size=3, life=0.3)
                particles.burst(superman.x, superman.y, (255, 210, 120), 5, 2)
                particles.ricochet(superman.x, superman.y, proj.angle)
                proj.dead = True
        self.projectiles = [p for p in self.projectiles if not p.dead]

    def draw(self, surface, cam):
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)
        frames = self._frames_for(self._anim_state)
        sprite = frames[self._frame % len(frames)] if frames else None
        if sprite is not None:
            img = sprite
            if self._hit_flash > 0:
                img = sprite.copy(); img.fill((180, 180, 180, 0), special_flags=pygame.BLEND_RGB_ADD)
            elif self.frozen > 0:
                img = sprite.copy(); img.fill((0, 60, 90, 0), special_flags=pygame.BLEND_RGB_ADD)
            # Sheet's native pose faces right; flip when facing left.
            draw_img = img if self.face_right else pygame.transform.flip(img, True, False)
            rect = draw_img.get_rect(midbottom=(sx, sy + self.RADIUS))
            surface.blit(draw_img, rect)
            draw_health_bar(surface, sx, rect.top - 8, self.hp, self.max_hp, self.RADIUS * 2)
        else:
            self._draw_base(surface, cam, (80, 80, 80))
            # Weapon stick
            ex = sx + int(math.cos(self._angle) * 18)
            ey = sy + int(math.sin(self._angle) * 18)
            c = WHITE if self._hit_flash > 0 else BROWN
            pygame.draw.line(surface, c, (sx, sy), (ex, ey), 3)
            pygame.draw.circle(surface, (60, 60, 60), (sx, sy), 6)
        for proj in self.projectiles:
            proj.draw(surface, cam)


class LexGoon(Thug):
    """Thug reskinned with the LexCorp goon sprite; stats/AI unchanged from
    Thug, falls back to Thug's procedural look if the sprite fails to load."""
    GUN_SOUNDS = False
    _SPRITE_SIZE = (40, 75)
    _sprite = None

    def __init__(self, x, y):
        super().__init__(x, y)
        if LexGoon._sprite is None:
            LexGoon._sprite = _load_lex_sprite("lex_goon.png", self._SPRITE_SIZE) or False

    def draw(self, surface, cam):
        sprite = LexGoon._sprite
        if not sprite:
            super().draw(surface, cam)
            return
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)
        img = sprite
        if self._hit_flash > 0:
            img = sprite.copy()
            img.fill((180, 180, 180, 0), special_flags=pygame.BLEND_RGB_ADD)
        elif self.frozen > 0:
            img = sprite.copy()
            img.fill((0, 60, 90, 0), special_flags=pygame.BLEND_RGB_ADD)
        # This sprite's head is turned to its left, so flip when facing right
        # (the opposite of the Thug sheets, which are drawn facing right).
        if self.face_right:
            img = pygame.transform.flip(img, True, False)
        rect = img.get_rect(center=(sx, sy))
        surface.blit(img, rect)
        draw_health_bar(surface, sx, rect.top - 8, self.hp, self.max_hp, self.RADIUS * 2)
        for proj in self.projectiles:
            proj.draw(surface, cam)


class Robot(Enemy):
    HP = 55; SPEED = 1.2; DMG = 4.0; COLOR = SILVER; RADIUS = 16
    SHOT_CD = 2.2; SHOT_SPEED = 4.5

    def __init__(self, x, y):
        super().__init__(x, y)
        self.shot_cd = random.uniform(0, self.SHOT_CD)
        self.projectiles: list[Projectile] = []
        self._orbit_angle = random.uniform(0, math.pi * 2)

    def update(self, dt, superman, particles):
        self._base_update(dt)
        self.shot_cd = max(0, self.shot_cd - dt)
        spd_m = 0.25 if self.frozen > 0 else 1.0

        # Orbit Superman at ~200px
        target_d = 200
        dx = superman.x - self.x; dy = superman.y - self.y
        d = math.hypot(dx, dy)
        if d > target_d + 30:
            self._move_toward(superman.x, superman.y, dt, spd_m)
        elif d < target_d - 30 and d > 0:
            self.x -= dx / d * self.SPEED * spd_m
            self.y -= dy / d * self.SPEED * spd_m
        else:
            self._orbit_angle += 0.8 * dt * spd_m
            self.x = superman.x + math.cos(self._orbit_angle) * target_d
            self.y = superman.y + math.sin(self._orbit_angle) * target_d

        self._angle = math.atan2(dy, dx)

        if self.shot_cd <= 0 and d < 400:
            self.shot_cd = self.SHOT_CD
            self.projectiles.append(Projectile(self.x, self.y, self._angle, self.SHOT_SPEED, RED, 8, 1.5))

        for proj in self.projectiles:
            proj.update(dt)
            if proj.hits_superman(superman):
                superman.take_damage(self.DMG)
                particles.burst(superman.x, superman.y, RED, 6, 2)
                proj.dead = True
        self.projectiles = [p for p in self.projectiles if not p.dead]

    def draw(self, surface, cam):
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)
        c = WHITE if self._hit_flash > 0 else (SILVER if self.frozen <= 0 else ICE)
        pts = [_rot(sx, sy, *p, self._angle) for p in [(-14, -10), (14, -10), (16, -5), (16, 5), (14, 10), (-14, 10)]]
        pygame.draw.polygon(surface, c, pts)
        pygame.draw.polygon(surface, DARK_GRAY, pts, 2)
        # Core
        pygame.draw.circle(surface, (0, 80, 200), (sx, sy), 5)
        # Eye
        ex, ey = _rot(sx, sy, 16, 0, self._angle)
        pygame.draw.circle(surface, RED, (int(ex), int(ey)), 4)
        draw_health_bar(surface, sx, sy - 24, self.hp, self.max_hp, 32)
        for proj in self.projectiles:
            proj.draw(surface, cam)


class BrainiacDrone(Enemy):
    HP = 80; SPEED = 2.2; DMG = 12.0; COLOR = KRYPTO; RADIUS = 18
    TELEPORT_CD = 3.5; SHOT_CD = 1.8; SHOT_SPEED = 5.5

    def __init__(self, x, y):
        super().__init__(x, y)
        self.teleport_cd = self.TELEPORT_CD
        self.shot_cd = random.uniform(0, self.SHOT_CD)
        self.projectiles: list[Projectile] = []
        self._t = 0.0

    def update(self, dt, superman, particles):
        self._base_update(dt)
        self._t += dt
        self.teleport_cd = max(0, self.teleport_cd - dt)
        self.shot_cd = max(0, self.shot_cd - dt)
        spd_m = 0.25 if self.frozen > 0 else 1.0

        dx = superman.x - self.x; dy = superman.y - self.y
        d = math.hypot(dx, dy)
        self._move_toward(superman.x, superman.y, dt, spd_m * 0.5)

        if self.teleport_cd <= 0 and self.frozen <= 0:
            self.teleport_cd = self.TELEPORT_CD
            angle = random.uniform(0, math.pi * 2)
            self.x = superman.x + math.cos(angle) * random.uniform(150, 280)
            self.y = superman.y + math.sin(angle) * random.uniform(150, 280)
            particles.burst(self.x, self.y, KRYPTO, 12, 3)

        if self.shot_cd <= 0 and d < 500:
            self.shot_cd = self.SHOT_CD
            for offset in [-0.15, 0, 0.15]:
                a = self._angle + offset
                self.projectiles.append(Projectile(self.x, self.y, a, self.SHOT_SPEED, KRYPTO, 6, 1.8))

        for proj in self.projectiles:
            proj.update(dt)
            if proj.hits_superman(superman):
                superman.take_damage(12)
                particles.burst(superman.x, superman.y, KRYPTO, 6, 2)
                proj.dead = True
        self.projectiles = [p for p in self.projectiles if not p.dead]

    def draw(self, surface, cam):
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)
        r = self.RADIUS
        pulse = int(r + 4 * math.sin(self._t * 5))
        c = WHITE if self._hit_flash > 0 else (KRYPTO if self.frozen <= 0 else ICE)
        gs = pygame.Surface((pulse * 2 + 4, pulse * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(gs, (*c, 80), (pulse + 2, pulse + 2), pulse)
        surface.blit(gs, (sx - pulse - 2, sy - pulse - 2))
        pygame.draw.circle(surface, c, (sx, sy), r)
        pygame.draw.circle(surface, BLACK, (sx, sy), r, 2)
        # Circuit lines
        for i in range(4):
            a = i * math.pi / 2 + self._t
            ex, ey = sx + math.cos(a) * r, sy + math.sin(a) * r
            pygame.draw.line(surface, (0, 180, 50), (sx, sy), (int(ex), int(ey)), 2)
        draw_health_bar(surface, sx, sy - 28, self.hp, self.max_hp, 36)
        for proj in self.projectiles:
            proj.draw(surface, cam)


class Metallo(Enemy):
    HP = 220; SPEED = 0.9; DMG = 18.0; COLOR = (85, 90, 95); RADIUS = 26
    KRYPTO_RADIUS = 160; KRYPTO_DPS = 18.0; SHOT_CD = 2.5; SHOT_SPEED = 3.5

    _SPRITE_SIZE = (85, 90)
    _sprite = None

    def __init__(self, x, y):
        super().__init__(x, y)
        if Metallo._sprite is None:
            Metallo._sprite = load_game_sprite("Metallo/metallo.png", self._SPRITE_SIZE) or False
        self.shot_cd = 1.0
        self.projectiles: list[Projectile] = []
        self._t = 0.0

    def update(self, dt, superman, particles):
        self._base_update(dt)
        self._t += dt
        self.shot_cd = max(0, self.shot_cd - dt)
        spd_m = 0.25 if self.frozen > 0 else 1.0

        dx = superman.x - self.x; dy = superman.y - self.y
        d = math.hypot(dx, dy)
        self._move_toward(superman.x, superman.y, dt, spd_m)
        self._angle = math.atan2(dy, dx)

        # Kryptonite aura damage (own tick skips the krypto_debuff multiplier it just
        # set, so it doesn't compound with itself every frame; other sources still
        # get the 1.6x bonus while Superman is debuffed)
        if d < self.KRYPTO_RADIUS:
            superman.krypto_debuff = 0.5
            superman.take_damage(self.KRYPTO_DPS * dt, krypto_mult=False)

        if self.shot_cd <= 0 and d < 500:
            self.shot_cd = self.SHOT_CD
            self.projectiles.append(Projectile(self.x, self.y, self._angle, self.SHOT_SPEED, KRYPTO, 10, 2.5))

        for proj in self.projectiles:
            proj.update(dt)
            if proj.hits_superman(superman):
                superman.take_damage(20)
                proj.dead = True
        self.projectiles = [p for p in self.projectiles if not p.dead]

    def draw(self, surface, cam):
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)
        r = self.RADIUS

        # Krypto aura
        ks = pygame.Surface((self.KRYPTO_RADIUS * 2, self.KRYPTO_RADIUS * 2), pygame.SRCALPHA)
        alpha = int(25 + 15 * abs(math.sin(self._t * 2)))
        pygame.draw.circle(ks, (*KRYPTO, alpha), (self.KRYPTO_RADIUS, self.KRYPTO_RADIUS), self.KRYPTO_RADIUS)
        surface.blit(ks, (sx - self.KRYPTO_RADIUS, sy - self.KRYPTO_RADIUS))

        sprite = Metallo._sprite
        if sprite:
            img = sprite
            if self._hit_flash > 0:
                img = sprite.copy(); img.fill((180, 180, 180, 0), special_flags=pygame.BLEND_RGB_ADD)
            elif self.frozen > 0:
                img = sprite.copy(); img.fill((0, 60, 90, 0), special_flags=pygame.BLEND_RGB_ADD)
            flip = math.cos(self._angle) < 0
            draw_img = pygame.transform.flip(img, True, False) if flip else img
            rect = draw_img.get_rect(center=(sx, sy))
            surface.blit(draw_img, rect)
        else:
            c = WHITE if self._hit_flash > 0 else (ICE if self.frozen > 0 else (85, 90, 95))
            pts = [_rot(sx, sy, *p, self._angle) for p in [(-22, -14), (22, -14), (24, -7), (24, 7), (22, 14), (-22, 14)]]
            pygame.draw.polygon(surface, c, pts)
            pygame.draw.polygon(surface, DARK_GRAY, pts, 3)

        # Kryptonite core (pulsing)
        kr = int(9 + 4 * abs(math.sin(self._t * 3)))
        pygame.draw.circle(surface, KRYPTO, (sx, sy), kr)
        ks2 = pygame.Surface((kr * 2 + 8, kr * 2 + 8), pygame.SRCALPHA)
        pygame.draw.circle(ks2, (*KRYPTO, 150), (kr + 4, kr + 4), kr + 4)
        surface.blit(ks2, (sx - kr - 4, sy - kr - 4))

        draw_health_bar(surface, sx, sy - 38, self.hp, self.max_hp, 52)
        for proj in self.projectiles:
            proj.draw(surface, cam)


class LexMechSuit(Enemy):
    """Highest-tier boss: Lex Luthor piloting a mech suit. Modeled on Metallo's
    template (HP/timers/projectiles/pulsing core/bigger health bar) but trades
    Metallo's passive kryptonite-aura DoT for an active missile-barrage +
    melee-stomp pattern, since this isn't a kryptonite-powered enemy."""
    HP = 320; SPEED = 0.85; DMG = 24.0; COLOR = (170, 40, 40); RADIUS = 30
    BARRAGE_CD = 4.0; SHOT_SPEED = 4.0
    STOMP_RANGE = 90; STOMP_CD = 3.0

    _SPRITE_SIZE = (150, 158)
    _sprite = None

    def __init__(self, x, y):
        super().__init__(x, y)
        if LexMechSuit._sprite is None:
            LexMechSuit._sprite = _load_lex_sprite("lex_mechsuit.png", self._SPRITE_SIZE) or False
        self.barrage_cd = 1.5
        self.stomp_cd = self.STOMP_CD
        self.projectiles: list[Projectile] = []
        self._t = 0.0

    def update(self, dt, superman, particles):
        self._base_update(dt)
        self._t += dt
        self.barrage_cd = max(0, self.barrage_cd - dt)
        self.stomp_cd = max(0, self.stomp_cd - dt)
        spd_m = 0.25 if self.frozen > 0 else 1.0

        dx = superman.x - self.x; dy = superman.y - self.y
        d = math.hypot(dx, dy)
        self._move_toward(superman.x, superman.y, dt, spd_m)
        self._angle = math.atan2(dy, dx)

        if self.barrage_cd <= 0 and d < 520:
            self.barrage_cd = self.BARRAGE_CD
            for offset in (-0.2, 0.0, 0.2):
                a = self._angle + offset
                self.projectiles.append(Projectile(self.x, self.y, a, self.SHOT_SPEED, RED, 9, 2.2))

        if d < self.STOMP_RANGE and self.stomp_cd <= 0:
            self.stomp_cd = self.STOMP_CD
            superman.take_damage(self.DMG)
            particles.shockwave(self.x, self.y)

        for proj in self.projectiles:
            proj.update(dt)
            if proj.hits_superman(superman):
                superman.take_damage(16)
                proj.dead = True
        self.projectiles = [p for p in self.projectiles if not p.dead]

    def draw(self, surface, cam):
        sx = int(self.x - cam.x); sy = int(self.y - cam.y)
        sprite = LexMechSuit._sprite

        pr = int(self.RADIUS + 10 + 6 * math.sin(self._t * 2))
        gs = pygame.Surface((pr * 2, pr * 2), pygame.SRCALPHA)
        alpha = int(30 + 20 * abs(math.sin(self._t * 2)))
        pygame.draw.circle(gs, (*RED, alpha), (pr, pr), pr)
        surface.blit(gs, (sx - pr, sy - pr))

        if sprite:
            img = sprite
            if self._hit_flash > 0:
                img = sprite.copy(); img.fill((180, 180, 180, 0), special_flags=pygame.BLEND_RGB_ADD)
            elif self.frozen > 0:
                img = sprite.copy(); img.fill((0, 60, 90, 0), special_flags=pygame.BLEND_RGB_ADD)
            flip = math.cos(self._angle) < 0
            draw_img = pygame.transform.flip(img, True, False) if flip else img
            rect = draw_img.get_rect(center=(sx, sy))
            surface.blit(draw_img, rect)
        else:
            c = WHITE if self._hit_flash > 0 else (ICE if self.frozen > 0 else self.COLOR)
            pts = [_rot(sx, sy, *p, self._angle) for p in [(-26, -16), (26, -16), (28, -8), (28, 8), (26, 16), (-26, 16)]]
            pygame.draw.polygon(surface, c, pts)
            pygame.draw.polygon(surface, DARK_GRAY, pts, 3)

        kr = int(9 + 4 * abs(math.sin(self._t * 3)))
        pygame.draw.circle(surface, (255, 60, 40), (sx, sy), kr)

        draw_health_bar(surface, sx, sy - 50, self.hp, self.max_hp, 60)
        for proj in self.projectiles:
            proj.draw(surface, cam)


# ─── PROJECTILE ──────────────────────────────────────────────────────────────

class Projectile:
    def __init__(self, x, y, angle, speed, color, radius=5, life=2.0, shape='orb'):
        self.x, self.y = float(x), float(y)
        self.angle = angle
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.color = color
        self.radius = radius
        self.life = life
        self.dead = False
        self.shape = shape  # 'orb': soft glowing blast (robots/energy weapons)
                             # 'bullet': thin tracer streak (gun-toting thugs/goons)

    def update(self, dt):
        self.x += self.vx * 60 * dt
        self.y += self.vy * 60 * dt
        self.life -= dt
        if self.life <= 0:
            self.dead = True

    def hits_superman(self, superman):
        if self.dead:
            return False
        d = math.hypot(superman.x - self.x, superman.y - self.y)
        if d < 20:
            self.dead = True
            return True
        return False

    def draw(self, surface, cam):
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)
        if self.shape == 'bullet':
            length = self.radius * 5
            tx = sx - math.cos(self.angle) * length
            ty = sy - math.sin(self.angle) * length
            pygame.draw.line(surface, self.color, (tx, ty), (sx, sy), max(1, self.radius // 2))
            pygame.draw.circle(surface, WHITE, (sx, sy), max(1, self.radius // 2))
            return
        gs = pygame.Surface((self.radius * 4, self.radius * 4), pygame.SRCALPHA)
        pygame.draw.circle(gs, (*self.color, 120), (self.radius * 2, self.radius * 2), self.radius * 2)
        pygame.draw.circle(gs, (*self.color, 255), (self.radius * 2, self.radius * 2), self.radius)
        surface.blit(gs, (sx - self.radius * 2, sy - self.radius * 2))


# ─── CIVILIAN / ANIMAL ───────────────────────────────────────────────────────

class Civilian:
    HOSTAGE_RUN_SPEED = 2.6
    HOSTAGE_ANIM_FPS  = 10

    _hostage_idle = None
    _hostage_run_frames = None
    _hostage_loaded = False

    def __init__(self, x, y, hostage=False):
        self.x, self.y = float(x), float(y)
        self.saved = False
        self.hostage = hostage
        # self.hostage flips to False once freed (enemies defeated); this stays
        # True forever so the sprite branch still applies during the fleeing run.
        self.was_hostage = hostage
        self._t = 0.0
        self._anim_t = 0.0
        self._frame = 0
        self.face_right = True

        if hostage and not Civilian._hostage_loaded:
            Civilian._hostage_idle = load_game_sprite("Citizens/Hostage/hostage.png", (59, 52))
            Civilian._hostage_run_frames = load_sprite_sheet("Citizens/Hostage/hostage run.png", 10, (88, 88))
            Civilian._hostage_loaded = True

    def update(self, dt, superman):
        self._t += dt
        if self.saved:
            return

        if self.was_hostage and not self.hostage:
            # Freed: run to Superman instead of just standing around waiting.
            dx, dy = superman.x - self.x, superman.y - self.y
            d = math.hypot(dx, dy)
            if dx:
                self.face_right = dx > 0
            frames = Civilian._hostage_run_frames
            if frames:
                step = 1.0 / self.HOSTAGE_ANIM_FPS
                self._anim_t += dt
                while self._anim_t >= step:
                    self._anim_t -= step
                    self._frame = (self._frame + 1) % len(frames)
            if d < 30:
                self.saved = True
            elif d > 1:
                spd = min(self.HOSTAGE_RUN_SPEED, d)
                self.x += dx / d * spd
                self.y += dy / d * spd
        else:
            d = math.hypot(superman.x - self.x, superman.y - self.y)
            if d < 30:
                self.saved = True

    def draw(self, surface, cam):
        if self.saved:
            return
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)

        if self.was_hostage:
            if self.hostage:
                img = Civilian._hostage_idle
            else:
                frames = Civilian._hostage_run_frames
                sprite = frames[self._frame % len(frames)] if frames else None
                # Sheet's native pose faces right; flip only when running left.
                img = pygame.transform.flip(sprite, True, False) if (sprite and not self.face_right) else sprite
            if img is not None:
                rect = img.get_rect(midbottom=(sx, sy + 16))
                surface.blit(img, rect)
                return

        bob = int(2 * math.sin(self._t * 4))
        c = MAROON if self.hostage else (220, 180, 130)
        pygame.draw.circle(surface, c, (sx, sy + bob), 8)
        pygame.draw.circle(surface, BLACK, (sx, sy + bob), 8, 1)
        # Arms
        pygame.draw.line(surface, c, (sx - 8, sy + bob + 4), (sx + 8, sy + bob + 4), 3)
        # Legs
        pygame.draw.line(surface, c, (sx - 4, sy + bob + 8), (sx - 4, sy + bob + 16), 3)
        pygame.draw.line(surface, c, (sx + 4, sy + bob + 8), (sx + 4, sy + bob + 16), 3)
        if not self.hostage:
            # Distress wave
            wa = int(40 + 20 * math.sin(self._t * 6))
            ws = pygame.Surface((wa * 2, wa * 2), pygame.SRCALPHA)
            a = int(80 * (0.5 + 0.5 * math.sin(self._t * 6)))
            pygame.draw.circle(ws, (255, 200, 0, a), (wa, wa), wa, 2)
            surface.blit(ws, (sx - wa, sy - wa + bob))


class BuriedCivilian(Civilian):
    """A Civilian trapped under rubble, invisible and un-rescuable until an
    X-ray burst has found them.

    A subclass rather than a flag on Civilian because three behaviours change:
    the base draws a yellow distress ring that would broadcast the position for
    free, it auto-rescues on proximity (which would let you clear the field
    blind and skip the mechanic entirely), and a buried body wants an X-ray
    silhouette rather than a bobbing pedestrian.
    """
    RESCUE_R = 34   # a shade wider than Civilian's 30 -- they're under a slab

    def __init__(self, x, y):
        super().__init__(x, y)
        self.revealed = False
        self._dug = False   # one-shot latch for the extraction dust burst

    def update(self, dt, superman):
        self._t += dt
        if self.revealed and not self.saved:
            if math.hypot(superman.x - self.x, superman.y - self.y) < self.RESCUE_R:
                self.saved = True

    def draw(self, surface, cam):
        if self.saved or not self.revealed:
            return
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)
        pulse = 0.5 + 0.5 * math.sin(self._t * 4.5)

        # Locator ring. Replaces the base distress wave -- this one is earned,
        # so it is allowed to shout.
        r = 26
        ring = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(ring, (*XRAY_C, int(90 + 90 * pulse)), (r + 2, r + 2), r, 2)
        surface.blit(ring, (sx - r - 2, sy - r - 2))

        # X-ray silhouette: dense material bright, same convention as the crates
        body = (215, 240, 250)
        pygame.draw.ellipse(surface, body, (sx - 9, sy - 5, 18, 12))
        pygame.draw.circle(surface, body, (sx - 12, sy - 8), 5)
        for i in range(3):
            pygame.draw.line(surface, (150, 190, 205),
                             (sx - 6, sy - 2 + i * 4), (sx + 6, sy - 2 + i * 4), 1)
        pygame.draw.line(surface, body, (sx + 4, sy + 2), (sx + 14, sy + 8), 3)
        pygame.draw.line(surface, body, (sx + 2, sy + 5), (sx + 10, sy + 12), 3)

        # Bobbing chevron so they stay findable across a 300px field
        my = sy - 40 + int(3 * math.sin(self._t * 4.5))
        pygame.draw.polygon(surface, XRAY_C,
                            [(sx - 7, my), (sx + 7, my), (sx, my + 9)])


class Animal:
    TYPES = ['cat', 'dog', 'bird']

    def __init__(self, x, y, kind=None):
        self.x, self.y = float(x), float(y)
        self.saved = False
        self.kind = kind or random.choice(self.TYPES)
        self._t = 0.0
        self.sprite = None
        if self.kind in _ANIMAL_SPRITE_FILES:
            fname = random.choice(_ANIMAL_SPRITE_FILES[self.kind])
            self.sprite = _get_animal_sprite(self.kind, fname)

    def update(self, dt, superman):
        self._t += dt
        if not self.saved:
            if math.hypot(superman.x - self.x, superman.y - self.y) < 35:
                self.saved = True

    def draw(self, surface, cam):
        if self.saved:
            return
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)
        bob = int(2 * math.sin(self._t * 3))
        if self.sprite is not None:
            rect = self.sprite.get_rect(center=(sx, sy + bob))
            surface.blit(self.sprite, rect)
        elif self.kind == 'cat':
            c = (200, 160, 100)
            pygame.draw.ellipse(surface, c, (sx - 10, sy - 7 + bob, 20, 14))
            # Ears
            pygame.draw.polygon(surface, c, [(sx - 8, sy - 7 + bob), (sx - 12, sy - 14 + bob), (sx - 4, sy - 7 + bob)])
            pygame.draw.polygon(surface, c, [(sx + 4, sy - 7 + bob), (sx + 12, sy - 14 + bob), (sx + 8, sy - 7 + bob)])
            pygame.draw.circle(surface, WHITE, (sx, sy - 18 + bob), 10)
        elif self.kind == 'dog':
            c = (180, 130, 80)
            pygame.draw.ellipse(surface, c, (sx - 12, sy - 6 + bob, 24, 12))
            pygame.draw.circle(surface, c, (sx + 12, sy - 4 + bob), 7)
            pygame.draw.circle(surface, WHITE, (sx, sy - 18 + bob), 10)
        else:  # bird
            c = (100, 160, 220)
            pygame.draw.ellipse(surface, c, (sx - 8, sy - 5 + bob, 16, 10))
            pygame.draw.polygon(surface, (255, 200, 50), [(sx + 8, sy + bob), (sx + 14, sy - 3 + bob), (sx + 8, sy - 3 + bob)])
            pygame.draw.circle(surface, WHITE, (sx, sy - 18 + bob), 10)
        gs = pygame.Surface((30, 30), pygame.SRCALPHA)
        pygame.draw.circle(gs, (*GREEN, int(100 + 80 * math.sin(self._t * 4))), (15, 15), 12, 2)
        surface.blit(gs, (sx - 15, sy - 28 + bob))


# ─── KRYPTO (temporary ally) ─────────────────────────────────────────────────

class Krypto:
    """Superman's dog: whistled in, flies in fast, barks on arrival, then
    auto-attacks whatever's fighting Superman until his time runs out.

    States: idle -> calling (whistle playing) -> incoming (flying to Superman)
    -> active (fighting/orbiting) -> back to idle with the cooldown running.

    Objects in the enemies list may set `minion_auto_attack = False` to opt out
    of being targeted (see the target loop in update). Not everything an event
    exposes as an "enemy" is meant to be cleared by force -- some events use
    that list for things the player has to pick between deliberately, where an
    ally choosing on its own would resolve or fail the event on their behalf.
    Any future minion should honour the same flag.
    """

    CALL_CD       = 35.0
    ACTIVE_DUR    = 15.0
    SPAWN_DIST    = 480
    ARRIVE_SPEED  = 22
    CHASE_SPEED   = 10
    ORBIT_SPEED   = 1.4
    ORBIT_RADIUS  = 55
    LEASH_RANGE   = 380   # only engages enemies within this of Superman
    TELEPORT_DIST = 900   # snapped back to Superman's side if left this far behind
    ATTACK_RANGE  = 46
    ATTACK_CD     = 0.9
    ATTACK_DMG    = 14
    ANIM_FPS      = 10

    _run_frames = None
    _bite_frames = None
    _snd_whistle = None
    _snd_bark = None
    _loaded = False

    def __init__(self):
        if not Krypto._loaded:
            Krypto._run_frames  = _load_krypto_frames("krypto running sprite sheet.png", 5)
            Krypto._bite_frames = _load_krypto_frames("krypto bite sprite sheet.png", 5)
            Krypto._snd_whistle = _load_krypto_sound("krypto whistle.ogg")
            Krypto._snd_bark    = _load_krypto_sound("krypto bark.ogg")
            Krypto._loaded = True

        self.state = 'idle'  # idle | calling | incoming | active
        self.call_cd = 0.0
        self.timer = 0.0
        self.x = self.y = 0.0
        self.face_right = False
        self._orbit_angle = random.uniform(0, math.pi * 2)
        self._current_anim = 'run'
        self._anim_t = 0.0
        self._frame = 0
        self.attack_cd = 0.0

    @property
    def cd_ratio(self):
        """0 (ready) .. 1 (on cooldown or currently deployed) for the HUD icon."""
        if self.state != 'idle':
            return 1.0
        return self.call_cd / self.CALL_CD if self.CALL_CD else 0.0

    def can_call(self):
        return self.state == 'idle' and self.call_cd <= 0

    def call(self):
        if not self.can_call():
            return False
        self.state = 'calling'
        self.timer = self._snd_whistle.get_length() if self._snd_whistle else 1.2
        if self._snd_whistle:
            self._snd_whistle.play()
        return True

    def _animate(self, dt, name):
        if name != self._current_anim:
            self._current_anim = name
            self._frame = 0
            self._anim_t = 0.0
        frames = self._run_frames if name == 'run' else self._bite_frames
        if not frames:
            return
        self._anim_t += dt
        step = 1.0 / self.ANIM_FPS
        while self._anim_t >= step:
            self._anim_t -= step
            self._frame = (self._frame + 1) % len(frames)

    def update(self, dt, superman, enemies, particles):
        if self.state == 'idle':
            self.call_cd = max(0.0, self.call_cd - dt)
            return

        if self.state == 'calling':
            self.timer -= dt
            if self.timer <= 0:
                angle = random.uniform(0, math.pi * 2)
                self.x = superman.x + math.cos(angle) * self.SPAWN_DIST
                self.y = superman.y + math.sin(angle) * self.SPAWN_DIST
                self.state = 'incoming'
            return

        if self.state == 'incoming':
            dx, dy = superman.x - self.x, superman.y - self.y
            d = math.hypot(dx, dy)
            if dx:
                self.face_right = dx > 0
            self._animate(dt, 'run')
            if d < 44:
                self.state = 'active'
                self.timer = self.ACTIVE_DUR
                self.attack_cd = 0.0
                if self._snd_bark:
                    self._snd_bark.play()
                particles.burst(self.x, self.y, WHITE, 10, 2.5)
            else:
                self.x += dx / d * self.ARRIVE_SPEED
                self.y += dy / d * self.ARRIVE_SPEED
            return

        # active
        self.timer -= dt
        self.attack_cd = max(0.0, self.attack_cd - dt)
        if self.timer <= 0:
            self.state = 'idle'
            self.call_cd = self.CALL_CD
            return

        # Leash: snap back to Superman's side rather than get left far behind
        if math.hypot(superman.x - self.x, superman.y - self.y) > self.TELEPORT_DIST:
            angle = random.uniform(0, math.pi * 2)
            self.x = superman.x + math.cos(angle) * 160
            self.y = superman.y + math.sin(angle) * 160
            particles.burst(self.x, self.y, WHITE, 8, 2)

        nearest, best_d = None, self.LEASH_RANGE
        for e in enemies:
            # An event's enemies list is also how it exposes objects to the
            # player's own powers, so it can hold things that are a decision
            # rather than a fight. Those opt out here, otherwise a minion picks
            # for the player and the event resolves without them.
            if not e.alive or not getattr(e, 'minion_auto_attack', True):
                continue
            d = math.hypot(e.x - superman.x, e.y - superman.y)
            if d < best_d:
                best_d, nearest = d, e

        if nearest is not None:
            dx, dy = nearest.x - self.x, nearest.y - self.y
            d = math.hypot(dx, dy)
            if dx:
                self.face_right = dx > 0
            if d > self.ATTACK_RANGE:
                self._animate(dt, 'run')
                if d > 1:
                    self.x += dx / d * self.CHASE_SPEED
                    self.y += dy / d * self.CHASE_SPEED
            else:
                self._animate(dt, 'bite')
                if self.attack_cd <= 0:
                    self.attack_cd = self.ATTACK_CD
                    nearest.take_damage(self.ATTACK_DMG)
                    particles.burst(nearest.x, nearest.y, WHITE, 5, 2)
        else:
            self._orbit_angle += self.ORBIT_SPEED * dt
            tx = superman.x + math.cos(self._orbit_angle) * self.ORBIT_RADIUS
            ty = superman.y + math.sin(self._orbit_angle) * self.ORBIT_RADIUS
            dx, dy = tx - self.x, ty - self.y
            d = math.hypot(dx, dy)
            if dx:
                self.face_right = dx > 0
            self._animate(dt, 'run')
            if d > 2:
                self.x += dx / d * min(self.CHASE_SPEED, d)
                self.y += dy / d * min(self.CHASE_SPEED, d)

    def draw(self, surface, cam):
        if self.state not in ('incoming', 'active'):
            return
        frames = self._run_frames if self._current_anim == 'run' else self._bite_frames
        if not frames:
            return
        frame = frames[self._frame % len(frames)]
        img = pygame.transform.flip(frame, True, False) if self.face_right else frame
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)
        surface.blit(img, img.get_rect(center=(sx, sy)))
