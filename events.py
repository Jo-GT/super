import pygame
import math
import random
import os
from constants import *
from entities import (Thug, Robot, BrainiacDrone, Metallo, LexGoon, LexMechSuit,
                      Civilian, BuriedCivilian, Animal, Projectile, load_game_sprite)

_SPRITES_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites")

_tree_sprite = None
_falling_sprite = None
_fire_frames = None


def _get_tree_sprite():
    global _tree_sprite
    if _tree_sprite is None:
        _tree_sprite = load_game_sprite("Environment/tree.png", (140, 140)) or False
    return _tree_sprite or None


def _get_falling_sprite():
    global _falling_sprite
    if _falling_sprite is None:
        _falling_sprite = load_game_sprite("Citizens/falling citizen.png", (67, 100)) or False
    return _falling_sprite or None


def _load_fire_frames():
    """Load fire.gif's animation frames, pre-extracted to individual PNGs
    (frame_00.png, frame_01.png, ...) with the flat white background already
    keyed to transparent. Pre-extracted because pygame/SDL_image only reads a
    GIF's first frame, and the previous approach of decoding fire.gif at
    runtime via cv2 silently produced no frames in the browser build (opencv
    has no WebAssembly build pygbag can load). Falls back to an empty list
    (procedural flame circles keep working) if the PNGs are missing."""
    global _fire_frames
    if _fire_frames is not None:
        return _fire_frames
    frames = []
    frames_dir = os.path.join(_SPRITES_ROOT, "Environment", "fire_frames")
    try:
        names = sorted(f for f in os.listdir(frames_dir) if f.lower().endswith(".png"))
        for name in names:
            surf = pygame.image.load(os.path.join(frames_dir, name)).convert_alpha()
            frames.append(pygame.transform.smoothscale(surf, (60, 90)))
    except Exception:
        frames = []
    _fire_frames = frames
    return _fire_frames


class BaseEvent:
    ACTIVATION_RADIUS = 320
    INNER_RADIUS      = 100

    def __init__(self, x, y, event_type):
        self.x, self.y = float(x), float(y)
        self.event_type = event_type
        self.category = EVENT_CAT[event_type]
        self.name = EVENT_NAMES[event_type]
        self.hint = EVENT_HINTS[event_type]
        self.active = False
        self.complete = False
        self.failed = False
        self._pulse = 0.0
        self._age = 0.0
        self.score_value = SCORE_TABLE[event_type]

    def dist_to(self, superman):
        return math.hypot(superman.x - self.x, superman.y - self.y)

    def check_activation(self, superman):
        if not self.active and self.dist_to(superman) < self.INNER_RADIUS:
            self.active = True
            self.on_activate(superman)

    def on_activate(self, superman):
        pass

    def update(self, dt, superman, particles):
        self._pulse += dt * 3.5
        self._age += dt
        self.check_activation(superman)

    def draw(self, surface, cam):
        if self.complete or self.failed:
            return
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)
        color = CAT_COLORS[self.category]
        if not self.active:
            r = int(24 + 6 * math.sin(self._pulse))
            gs = pygame.Surface((r * 2 + 8, r * 2 + 8), pygame.SRCALPHA)
            alpha = int(100 + 80 * abs(math.sin(self._pulse)))
            pygame.draw.circle(gs, (*color, alpha), (r + 4, r + 4), r)
            surface.blit(gs, (sx - r - 4, sy - r - 4))
            pygame.draw.circle(surface, color, (sx, sy), 16)
            pygame.draw.circle(surface, WHITE, (sx, sy), 16, 2)
            self._draw_icon(surface, sx, sy)

    def _draw_icon(self, surface, sx, sy):
        pass

    def get_ui_text(self):
        return self.name, self.hint

    def all_enemies_defeated(self, enemies):
        return all(not e.alive for e in enemies)


# ─── FIGHT EVENTS ─────────────────────────────────────────────────────────────

class FightEvent(BaseEvent):
    def __init__(self, x, y, event_type, enemy_factory, count):
        super().__init__(x, y, event_type)
        self.enemies = []
        self._enemy_factory = enemy_factory
        self._count = count
        self._spawned = False

    def on_activate(self, superman):
        self._spawned = True
        for i in range(self._count):
            a = i * (2 * math.pi / self._count) + random.uniform(-0.3, 0.3)
            d = random.uniform(80, 160)
            ex = self.x + math.cos(a) * d
            ey = self.y + math.sin(a) * d
            self.enemies.append(self._enemy_factory(ex, ey))

    def update(self, dt, superman, particles):
        super().update(dt, superman, particles)
        for e in self.enemies:
            e.update(dt, superman, particles)
        self.enemies = [e for e in self.enemies if e.alive]
        if self.active and not self.enemies and self._spawned:
            self.complete = True

    def draw(self, surface, cam):
        super().draw(surface, cam)
        for e in self.enemies:
            e.draw(surface, cam)

    def _draw_icon(self, surface, sx, sy):
        # Fist icon
        pygame.draw.circle(surface, WHITE, (sx, sy), 7)
        pygame.draw.line(surface, WHITE, (sx - 5, sy + 4), (sx + 5, sy + 4), 2)


def make_criminals_event(x, y):
    return FightEvent(x, y, EventType.FIGHT_CRIMINALS, Thug, random.randint(4, 5))

def make_robots_event(x, y):
    return FightEvent(x, y, EventType.FIGHT_ROBOTS, Robot, random.randint(2, 4))

def make_brainiac_event(x, y):
    return FightEvent(x, y, EventType.FIGHT_BRAINIAC, BrainiacDrone, 1)

def make_metallo_event(x, y):
    return FightEvent(x, y, EventType.FIGHT_METALLO, Metallo, 1)

def make_lex_goons_event(x, y):
    return FightEvent(x, y, EventType.FIGHT_LEX_GOONS, LexGoon, random.randint(4, 5))

def make_lex_mechsuit_event(x, y):
    return FightEvent(x, y, EventType.FIGHT_LEX_MECHSUIT, LexMechSuit, 1)


# ─── HOSTAGE SITUATION ────────────────────────────────────────────────────────

class HostageEvent(BaseEvent):
    INNER_RADIUS = 150

    def __init__(self, x, y):
        super().__init__(x, y, EventType.RESCUE_HOSTAGE)
        self.enemies = []
        self.hostage = None

    def on_activate(self, superman):
        for i in range(2):
            a = i * math.pi + random.uniform(-0.3, 0.3)
            self.enemies.append(Thug(self.x + math.cos(a) * 70, self.y + math.sin(a) * 70))
        self.hostage = Civilian(self.x, self.y, hostage=True)

    def update(self, dt, superman, particles):
        super().update(dt, superman, particles)
        for e in self.enemies:
            e.update(dt, superman, particles)
        self.enemies = [e for e in self.enemies if e.alive]
        if self.active and not self.enemies and self.hostage:
            self.hostage.hostage = False
            self.hostage.update(dt, superman)
            if self.hostage.saved:
                self.complete = True
        # Fail if Superman hits hostage (checked via projectile in game loop)

    def draw(self, surface, cam):
        super().draw(surface, cam)
        for e in self.enemies:
            e.draw(surface, cam)
        if self.hostage:
            self.hostage.draw(surface, cam)

    def _draw_icon(self, surface, sx, sy):
        pygame.draw.circle(surface, (220, 180, 130), (sx, sy - 2), 5)
        pygame.draw.line(surface, (220, 180, 130), (sx, sy + 3), (sx, sy + 10), 2)


# ─── BUILDING FIRE ────────────────────────────────────────────────────────────

class FireEvent(BaseEvent):
    INNER_RADIUS = 200
    TIMER = 55.0
    DOUSE_RATE = 0.4  # flame_hp per second of sustained, aimed freeze breath

    def __init__(self, x, y):
        super().__init__(x, y, EventType.RESCUE_FIRE)
        self.timer = self.TIMER
        # Building rect near x, y
        self.bldg = pygame.Rect(int(x) - 55, int(y) - 70, 110, 140)
        # Flame spots
        self.flames = [(x + random.randint(-50, 50), y + random.randint(-60, 50)) for _ in range(6)]
        self.flame_hp = [1.0] * len(self.flames)
        # Citizens at windows
        self.citizens = [
            Civilian(x + random.choice([-35, 0, 35]), y + random.randint(-50, 30))
            for _ in range(3)
        ]
        self._fire_t = 0.0

    def on_activate(self, superman):
        pass

    def update(self, dt, superman, particles):
        super().update(dt, superman, particles)
        self._fire_t += dt
        if not self.active:
            return

        self.timer -= dt
        if self.timer <= 0:
            self.failed = True
            return

        # Add fire particles
        alive_flames = sum(1 for fh in self.flame_hp if fh > 0)
        if alive_flames > 0 and random.random() < 0.35:
            fi = random.choice([i for i, fh in enumerate(self.flame_hp) if fh > 0])
            particles.fire_burst(self.flames[fi][0], self.flames[fi][1], count=4)

        # Freeze breath douses flames (continuous while aimed at them)
        if superman.freeze_active:
            for i, (fx, fy) in enumerate(self.flames):
                if self.flame_hp[i] > 0 and superman.freeze_covers(fx, fy):
                    self.flame_hp[i] = max(0, self.flame_hp[i] - self.DOUSE_RATE * dt)
                    if random.random() < 0.3:
                        particles.burst(fx, fy, ICE, count=3, speed=2)

        # Rescue citizens only after at least half flames out
        doused = sum(1 for fh in self.flame_hp if fh <= 0)
        if doused >= len(self.flames) // 2:
            for c in self.citizens:
                c.update(dt, superman)

        if all(c.saved for c in self.citizens):
            self.complete = True

    def draw(self, surface, cam):
        if self.complete or self.failed:
            return
        # Building
        br = pygame.Rect(self.bldg.x - cam.x, self.bldg.y - cam.y, self.bldg.w, self.bldg.h)
        pygame.draw.rect(surface, (75, 60, 55), br)
        pygame.draw.rect(surface, (50, 40, 35), br, 2)
        # Flame effects
        fire_frames = _load_fire_frames()
        for i, (fx, fy) in enumerate(self.flames):
            if self.flame_hp[i] > 0:
                fsx = int(fx - cam.x); fsy = int(fy - cam.y)
                if fire_frames:
                    idx = int(self._fire_t * 10 + i * 2) % len(fire_frames)
                    frame = fire_frames[idx]
                    scale = max(0.3, self.flame_hp[i])
                    fw = max(1, int(frame.get_width() * scale))
                    fh = max(1, int(frame.get_height() * scale))
                    scaled = pygame.transform.smoothscale(frame, (fw, fh))
                    rect = scaled.get_rect(midbottom=(fsx, fsy + 10))
                    surface.blit(scaled, rect)
                else:
                    fr = int(18 * self.flame_hp[i])
                    fs = pygame.Surface((fr * 3, fr * 3), pygame.SRCALPHA)
                    pygame.draw.circle(fs, (*FIRE_HOT, 200), (fr, fr + fr // 2), fr)
                    pygame.draw.circle(fs, (*FIRE_WARM, 180), (fr, fr), fr // 2)
                    surface.blit(fs, (fsx - fr, fsy - fr - fr // 2))
        # Citizens
        for c in self.citizens:
            c.draw(surface, cam)
        # Timer bar
        if self.active:
            sx = int(self.x - cam.x)
            sy = int(self.y - cam.y)
            ratio = self.timer / self.TIMER
            col = GREEN if ratio > 0.5 else (GOLD if ratio > 0.25 else RED)
            pygame.draw.rect(surface, (60, 0, 0), (sx - 40, sy - 90, 80, 8))
            pygame.draw.rect(surface, col, (sx - 40, sy - 90, int(80 * ratio), 8))
        super().draw(surface, cam)

    def _draw_icon(self, surface, sx, sy):
        # Flame
        pygame.draw.polygon(surface, FIRE_HOT, [(sx, sy - 8), (sx - 5, sy + 5), (sx + 5, sy + 5)])
        pygame.draw.circle(surface, FIRE_WARM, (sx, sy + 2), 4)


# ─── FALLING PERSON ───────────────────────────────────────────────────────────

class FallingEvent(BaseEvent):
    INNER_RADIUS = 350
    FALL_SPEED = 220.0

    def __init__(self, x, y):
        super().__init__(x, y, EventType.RESCUE_FALLING)
        self.person_x = float(x)
        self.person_y = float(y) - 280
        self.ground_y = float(y) + 60
        self.caught = False
        self.hit_ground = False
        self._started = False

    def on_activate(self, superman):
        self._started = True

    def update(self, dt, superman, particles):
        super().update(dt, superman, particles)
        if not self._started:
            return
        if self.caught or self.hit_ground:
            return
        self.person_y += self.FALL_SPEED * dt
        if math.hypot(superman.x - self.person_x, superman.y - self.person_y) < 35:
            self.caught = True
            particles.burst(self.person_x, self.person_y, YELLOW_S, 14, 4)
            self.complete = True
        if self.person_y >= self.ground_y:
            self.hit_ground = True
            self.failed = True

    def draw(self, surface, cam):
        if self.complete or self.failed:
            return
        super().draw(surface, cam)
        if not self._started:
            return
        sx = int(self.person_x - cam.x)
        sy = int(self.person_y - cam.y)
        # Person
        sprite = _get_falling_sprite()
        if sprite is not None:
            rect = sprite.get_rect(center=(sx, sy))
            surface.blit(sprite, rect)
            bar_y = rect.top - 12
        else:
            pygame.draw.circle(surface, FLESH, (sx, sy), 8)
            pygame.draw.line(surface, FLESH, (sx, sy + 8), (sx, sy + 22), 3)
            pygame.draw.line(surface, FLESH, (sx - 8, sy + 12), (sx + 8, sy + 12), 3)
            pygame.draw.line(surface, FLESH, (sx - 5, sy + 22), (sx, sy + 32), 3)
            pygame.draw.line(surface, FLESH, (sx + 5, sy + 22), (sx, sy + 32), 3)
            bar_y = sy - 20
        # Ground danger indicator
        gy = int(self.ground_y - cam.y)
        pygame.draw.line(surface, (RED[0], RED[1], RED[2]), (sx - 20, gy), (sx + 20, gy), 3)
        # Remaining distance
        progress = max(0, (self.ground_y - self.person_y) / (self.ground_y - (self.y - 280)))
        pygame.draw.rect(surface, (80, 0, 0), (sx - 20, bar_y, 40, 5))
        pygame.draw.rect(surface, RED, (sx - 20, bar_y, int(40 * progress), 5))

    def _draw_icon(self, surface, sx, sy):
        pygame.draw.circle(surface, FLESH, (sx, sy - 4), 5)
        pygame.draw.line(surface, FLESH, (sx, sy + 1), (sx, sy + 8), 2)


# ─── RUNAWAY CAR ──────────────────────────────────────────────────────────────

class Car:
    """Quacks like an Enemy -- {x, y, take_damage, freeze} -- so it rides along
    in main.py's all_enemies list and a Q-punch (Superman auto-dashes onto the
    nearest thing in range) stops it with no special-casing, the same trick
    Crate uses. HP is tuned so one punch (55) always ends it."""
    HP = 50
    minion_auto_attack = True

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.hp = self.HP
        self.alive = True

    def take_damage(self, amount):
        self.hp -= amount
        if self.hp <= 0:
            self.alive = False

    def freeze(self, duration):
        pass  # tires don't care; try_freeze needs the method to exist


class CarEvent(BaseEvent):
    INNER_RADIUS = 300
    CAR_SPEED = 200.0

    def __init__(self, x, y):
        super().__init__(x, y, EventType.RESCUE_CAR)
        angle = random.uniform(0, math.pi * 2)
        self.car_x = float(x)
        self.car_y = float(y)
        self.car_vx = math.cos(angle) * self.CAR_SPEED
        self.car_vy = math.sin(angle) * self.CAR_SPEED
        self.car_angle = angle
        self.stopped = False
        self._traveled = 0.0
        self.car = Car(self.car_x, self.car_y)
        self.enemies = [self.car]
        # Pedestrians in the path
        self.pedestrians = [
            Civilian(x + math.cos(angle) * random.uniform(150, 300) + random.uniform(-30, 30),
                     y + math.sin(angle) * random.uniform(150, 300) + random.uniform(-30, 30))
            for _ in range(3)
        ]

    def on_activate(self, superman):
        pass

    def update(self, dt, superman, particles):
        super().update(dt, superman, particles)
        if self.stopped:
            return
        # Stays parked -- and un-failable -- until Superman is close enough to
        # actually notice it. Previously it drove off (and could time out or
        # flatten a pedestrian) the instant it was spawned, often long before
        # the player was anywhere nearby to see it, let alone react.
        if not self.active:
            return

        if not self.car.alive:
            self.stopped = True
            particles.shockwave(self.car_x, self.car_y)
            self.complete = True
            return

        self.car_x += self.car_vx * dt
        self.car_y += self.car_vy * dt
        self.car.x, self.car.y = self.car_x, self.car_y
        self._traveled += math.hypot(self.car_vx, self.car_vy) * dt

        # Collision with Superman body also stops it (ram it while super-speeding)
        if math.hypot(superman.x - self.car_x, superman.y - self.car_y) < 30:
            if superman.speed_remaining > 0:
                self.stopped = True
                particles.shockwave(self.car_x, self.car_y)
                self.complete = True
                return

        # Car hits pedestrian
        for p in self.pedestrians:
            if not p.saved and math.hypot(self.car_x - p.x, self.car_y - p.y) < 28:
                self.failed = True

        # Car gone too far
        if self._traveled > 900:
            self.failed = True

    def draw(self, surface, cam):
        if self.complete or self.failed:
            return
        super().draw(surface, cam)
        # Pedestrians
        for p in self.pedestrians:
            p.draw(surface, cam)
        # Car
        sx = int(self.car_x - cam.x)
        sy = int(self.car_y - cam.y)
        angle = self.car_angle
        pts = [_rot_pt(sx, sy, *p, angle) for p in [(-22, -10), (22, -10), (24, -5), (24, 5), (22, 10), (-22, 10)]]
        pygame.draw.polygon(surface, (180, 30, 30), pts)
        pygame.draw.polygon(surface, (220, 50, 50), pts, 2)
        # Wheels
        for wx, wy in [(-14, -10), (14, -10), (-14, 10), (14, 10)]:
            wsx, wsy = _rot_pt(sx, sy, wx, wy, angle)
            pygame.draw.circle(surface, BLACK, (int(wsx), int(wsy)), 5)
        # Speed lines
        for i in range(3):
            ta = angle + math.pi + random.uniform(-0.3, 0.3)
            lx1, ly1 = _rot_pt(sx, sy, -24, random.randint(-8, 8), angle)
            lx2, ly2 = lx1 + math.cos(ta) * 20, ly1 + math.sin(ta) * 20
            pygame.draw.line(surface, (200, 200, 200), (int(lx1), int(ly1)), (int(lx2), int(ly2)), 1)

    def _draw_icon(self, surface, sx, sy):
        pygame.draw.rect(surface, (180, 30, 30), (sx - 8, sy - 4, 16, 8))
        pygame.draw.circle(surface, BLACK, (sx - 5, sy + 4), 3)
        pygame.draw.circle(surface, BLACK, (sx + 5, sy + 4), 3)


def _rot_pt(cx, cy, dx, dy, angle):
    c, s = math.cos(angle), math.sin(angle)
    return cx + dx * c - dy * s, cy + dx * s + dy * c


# ─── CAT IN TREE ──────────────────────────────────────────────────────────────

class CatEvent(BaseEvent):
    INNER_RADIUS = 80

    def __init__(self, x, y):
        super().__init__(x, y, EventType.ANIMAL_CAT)
        self.cat = Animal(x, y - 40, 'cat')

    def on_activate(self, superman):
        self.cat.saved = True
        self.complete = True

    def draw(self, surface, cam):
        if self.complete:
            return
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)
        tree = _get_tree_sprite()
        if tree is not None:
            rect = tree.get_rect(midbottom=(sx, sy + 55))
            surface.blit(tree, rect)
        else:
            pygame.draw.rect(surface, BROWN, (sx - 6, sy - 10, 12, 60))
            pygame.draw.circle(surface, PARK, (sx, sy - 20), 32)
            pygame.draw.circle(surface, (28, 75, 28), (sx, sy - 20), 32, 2)
        self.cat.draw(surface, cam)
        super().draw(surface, cam)

    def _draw_icon(self, surface, sx, sy):
        # Paw print
        pygame.draw.circle(surface, GREEN, (sx, sy), 5)
        for dx, dy in [(-5, -6), (5, -6), (-7, -1), (7, -1)]:
            pygame.draw.circle(surface, GREEN, (sx + dx, sy + dy), 3)


# ─── FLOODED ANIMAL SHELTER ───────────────────────────────────────────────────

class FloodEvent(BaseEvent):
    INNER_RADIUS = 280
    TIMER = 60.0

    def __init__(self, x, y):
        super().__init__(x, y, EventType.ANIMAL_FLOOD)
        self.timer = self.TIMER
        self.water_level = 0.0
        self.animals = [
            Animal(x + random.randint(-130, 130), y + random.randint(-80, 80))
            for _ in range(5)
        ]
        self.frozen_tiles: list[tuple] = []
        self._t = 0.0
        self.frozen = False

    def on_activate(self, superman):
        pass

    def update(self, dt, superman, particles):
        super().update(dt, superman, particles)
        self._t += dt
        if not self.active:
            return

        # Water rises, unless freeze breath is held near the animals — then it fully freezes in place
        self.frozen = superman.freeze_active and any(
            math.hypot(superman.x - a.x, superman.y - a.y) < 300
            for a in self.animals
        )
        if not self.frozen:
            self.water_level += 0.08 * dt
        self.timer -= dt

        for a in self.animals:
            a.update(dt, superman)

        if all(a.saved for a in self.animals):
            self.complete = True

        if self.timer <= 0 or self.water_level > 1.0:
            remaining = sum(1 for a in self.animals if not a.saved)
            if remaining > 0:
                self.failed = True

    def draw(self, surface, cam):
        if self.complete or self.failed:
            return
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)
        # Water
        wh = int(200 * self.water_level)
        if wh > 0:
            ws = pygame.Surface((300, wh + 10), pygame.SRCALPHA)
            ws.fill((*ICE, 160) if self.frozen else (*WATER_C, 130))
            surface.blit(ws, (sx - 150, sy + 80 - wh))
            if self.frozen:
                # Frozen crust: static jagged ice cracks instead of waves
                for i in range(5):
                    cx = sx - 150 + i * 70 + 20
                    cy = sy + 80 - wh + 4
                    pygame.draw.line(surface, (*WHITE, 200), (cx, cy), (cx + 18, cy + 10), 2)
                    pygame.draw.line(surface, (*WHITE, 200), (cx + 18, cy + 10), (cx + 6, cy + 20), 2)
            else:
                # Waves
                for i in range(3):
                    wave_x = int((self._t * 40 + i * 50) % 300)
                    pygame.draw.arc(surface, (*ICE, 180), (sx - 150 + wave_x - 20, sy + 82 - wh, 40, 10), 0, math.pi, 2)
        # Animals
        for a in self.animals:
            a.draw(surface, cam)
        # Timer bar
        ratio = self.timer / self.TIMER
        col = GREEN if ratio > 0.5 else (GOLD if ratio > 0.25 else RED)
        pygame.draw.rect(surface, (0, 0, 60), (sx - 40, sy - 70, 80, 8))
        pygame.draw.rect(surface, col, (sx - 40, sy - 70, int(80 * ratio), 8))
        super().draw(surface, cam)

    def _draw_icon(self, surface, sx, sy):
        pygame.draw.arc(surface, WATER_C, (sx - 8, sy - 5, 16, 10), 0, math.pi, 3)
        for dx, dy in [(-4, -7), (4, -7), (0, -3)]:
            pygame.draw.circle(surface, GREEN, (sx + dx, sy + dy), 3)


# ─── COLLAPSED BUILDING (RUBBLE SEARCH) ───────────────────────────────────────

class RubbleEvent(BaseEvent):
    INNER_RADIUS = 260
    TIMER        = 70.0
    FIELD_W, FIELD_H = 300, 180

    def __init__(self, x, y):
        super().__init__(x, y, EventType.RESCUE_RUBBLE)
        self.timer = self.TIMER

        # Slab quads are rotated once here rather than per frame: unlike the
        # runaway car these never move, so there's nothing to recompute.
        self.slabs = []
        for _ in range(18):
            ox = random.uniform(-self.FIELD_W / 2, self.FIELD_W / 2)
            oy = random.uniform(-self.FIELD_H / 2, self.FIELD_H / 2)
            w = random.uniform(26, 58)
            h = random.uniform(12, 26)
            a = random.uniform(0, math.pi)
            c, s = math.cos(a), math.sin(a)
            pts = [(ox + dx * c - dy * s, oy + dx * s + dy * c)
                   for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2),
                                  (w / 2, h / 2), (-w / 2, h / 2))]
            shade = random.choice([(92, 90, 86), (78, 76, 72), (104, 101, 96), (66, 64, 60)])
            self.slabs.append((pts, shade))

        self.rebar = []
        for _ in range(6):
            rx = random.uniform(-self.FIELD_W / 2, self.FIELD_W / 2)
            ry = random.uniform(-self.FIELD_H / 2, self.FIELD_H / 2)
            a = random.uniform(0, math.pi * 2)
            self.rebar.append((rx, ry, rx + math.cos(a) * 22, ry + math.sin(a) * 22))

        # Spread the victims out so the rescue run is a route, not one hover
        self.victims = []
        while len(self.victims) < random.randint(4, 5):
            vx = x + random.uniform(-self.FIELD_W / 2 + 20, self.FIELD_W / 2 - 20)
            vy = y + random.uniform(-self.FIELD_H / 2 + 20, self.FIELD_H / 2 - 20)
            if all(math.hypot(vx - v.x, vy - v.y) > 62 for v in self.victims):
                self.victims.append(BuriedCivilian(vx, vy))

    def on_activate(self, superman):
        pass

    def update(self, dt, superman, particles):
        super().update(dt, superman, particles)
        if not self.active:
            return
        self.timer -= dt

        for v in self.victims:
            if not v.revealed and superman.xray_reveals(v.x, v.y):
                v.revealed = True
                particles.burst(v.x, v.y, XRAY_C, count=12, speed=2.5, size=4, life=0.5)
            v.update(dt, superman)
            if v.saved and not v._dug:
                v._dug = True
                particles.burst(v.x, v.y, GRAY, count=16, speed=3, size=5, life=0.7, gravity=0.05)
                particles.burst(v.x, v.y, YELLOW_S, count=8, speed=3.5, size=4, life=0.4)

        # elif, not a second if: main.py checks complete and failed with two
        # independent ifs, so setting both in one frame pays out and penalises.
        if all(v.saved for v in self.victims):
            self.complete = True
        elif self.timer <= 0:
            self.failed = True

    def get_ui_text(self):
        found = sum(1 for v in self.victims if v.revealed)
        out = sum(1 for v in self.victims if v.saved)
        n = len(self.victims)
        if found < n:
            return self.name, f"{found}/{n} located, {out}/{n} out  -  X=X-Ray to scan the rubble"
        return self.name, f"All {n} located  -  {out}/{n} pulled out. Fly to each one!"

    def draw(self, surface, cam):
        if self.complete or self.failed:
            return
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)

        # Dust apron under the pile
        aw, ah = self.FIELD_W + 60, self.FIELD_H + 40
        apron = pygame.Surface((aw, ah), pygame.SRCALPHA)
        pygame.draw.ellipse(apron, (54, 50, 46, 120), apron.get_rect())
        surface.blit(apron, (sx - aw // 2, sy - ah // 2))

        for pts, shade in self.slabs:
            spts = [(sx + px, sy + py) for px, py in pts]
            pygame.draw.polygon(surface, shade, spts)
            dark = (max(0, shade[0] - 26), max(0, shade[1] - 26), max(0, shade[2] - 26))
            pygame.draw.polygon(surface, dark, spts, 2)
        for rx, ry, rx2, ry2 in self.rebar:
            pygame.draw.line(surface, (120, 76, 48), (sx + rx, sy + ry), (sx + rx2, sy + ry2), 2)

        for v in self.victims:
            v.draw(surface, cam)

        if self.active:
            ratio = max(0.0, self.timer / self.TIMER)
            col = GREEN if ratio > 0.5 else (GOLD if ratio > 0.25 else RED)
            pygame.draw.rect(surface, (40, 20, 0), (sx - 40, sy - 118, 80, 8))
            pygame.draw.rect(surface, col, (sx - 40, sy - 118, int(80 * ratio), 8))

        super().draw(surface, cam)

    def _draw_icon(self, surface, sx, sy):
        # Slab pile with a scan line across it
        pygame.draw.polygon(surface, LGRAY, [(sx - 9, sy + 5), (sx - 2, sy - 4), (sx + 4, sy + 5)])
        pygame.draw.polygon(surface, GRAY, [(sx - 2, sy + 5), (sx + 6, sy - 2), (sx + 9, sy + 5)])
        pygame.draw.line(surface, XRAY_C, (sx - 10, sy + 1), (sx + 10, sy + 1), 2)


# ─── LEXCORP DECOY CRATES ─────────────────────────────────────────────────────

class Crate:
    """A LexCorp crate.

    Deliberately quacks like an Enemy -- {x, y, take_damage, freeze} is the
    entire interface main.py's all_enemies list and Superman's three power
    methods touch -- so heat vision and Q-punch destroy it with no special
    casing anywhere. HP is tuned so a punch (55) one-shots it while heat vision
    (22 dps) needs ~2.3s of held aim, and the scorch that builds up in between
    is the warning that you are about to commit.
    """
    SIZE = 56
    HP   = 50
    # Which crate to destroy is the whole decision here, so no ally may make it
    minion_auto_attack = False

    def __init__(self, x, y, content):
        self.x, self.y = float(x), float(y)
        self.content = content          # 'bomb' | 'decoy' | 'lead'
        self.hp = self.HP
        self.alive = True
        self.scanned = False
        self.char = 0.0
        self._t = 0.0

    def take_damage(self, amount):
        self.hp -= amount
        self.char = min(1.0, 1.0 - self.hp / self.HP)
        if self.hp <= 0:
            self.alive = False

    def freeze(self, duration):
        pass                            # crates don't care; try_freeze needs it


class CrateEvent(BaseEvent):
    INNER_RADIUS = 240
    TIMER        = 75.0
    SPACING      = 150     # must stay > try_punch's 90px splash, or one punch
                           # takes out two crates and failure becomes accidental

    def __init__(self, x, y):
        super().__init__(x, y, EventType.FIGHT_LEX_CRATES)
        self.timer = self.TIMER
        contents = ['bomb', 'lead', 'decoy', 'decoy']
        random.shuffle(contents)
        h = self.SPACING // 2
        spots = [(-h, -h), (h, -h), (-h, h), (h, h)]
        self.crates = [Crate(x + ox, y + oy, c) for (ox, oy), c in zip(spots, contents)]
        # Exposed under the name main.py:485 looks for, so the crates land in
        # all_enemies and both destruction powers hit them for free. Never
        # reassign self.crates with a filter -- self.enemies aliases it.
        self.enemies = self.crates

    def on_activate(self, superman):
        pass

    def update(self, dt, superman, particles):
        super().update(dt, superman, particles)
        if not self.active:
            return
        self.timer -= dt

        for c in self.crates:
            c._t += dt
            if not c.scanned and superman.xray_reveals(c.x, c.y):
                c.scanned = True
            if c.char > 0 and c.alive and random.random() < 0.25 * c.char:
                particles.burst(c.x, c.y, GRAY, count=2, speed=1.2, size=3, life=0.5)

        # Resolve everything destroyed so far in one pass, because heat vision
        # is a line and two crates can share a row -- judging them one at a
        # time would set complete and failed in the same frame. If the bomb is
        # among the wreckage the job got done, and a splintered decoy is just
        # an empty box; only losing the bomb entirely is a failure.
        downed = [c for c in self.crates if not c.alive and not getattr(c, '_resolved', False)]
        for c in downed:
            c._resolved = True
            if c.content == 'bomb':
                particles.shockwave(c.x, c.y)
                particles.burst(c.x, c.y, FIRE_WARM, count=22, speed=4, size=6, life=0.6)
                particles.burst(c.x, c.y, GRAY, count=18, speed=3, size=5, life=0.8, gravity=0.06)
            else:
                particles.burst(c.x, c.y, LGRAY, count=20, speed=3.5, size=5, life=0.7, gravity=0.05)
        if downed and not self.complete and not self.failed:
            # Failure wins over success. Heat vision is a 520px line that goes
            # straight through a whole row, so without this precedence the
            # winning strategy is to sweep the beam over all four crates and
            # never scan anything -- which is the one thing this event is for.
            if any(c.content != 'bomb' for c in downed):
                self.failed = True
            else:
                self.complete = True

        if not self.complete and not self.failed and self.timer <= 0:
            particles.sonic_boom(self.x, self.y, FIRE_HOT)
            self.failed = True

    def get_ui_text(self):
        scanned = sum(1 for c in self.crates if c.scanned)
        n = len(self.crates)
        if scanned < n:
            return self.name, f"{scanned}/{n} crates scanned  -  X=X-Ray. Do NOT guess."
        return self.name, "Bomb identified  -  Q=Punch that crate. Nothing else."

    def draw(self, surface, cam):
        if self.complete or self.failed:
            return
        for c in self.crates:
            if c.alive:
                self._draw_crate(surface, cam, c)
        if self.active:
            sx = int(self.x - cam.x)
            sy = int(self.y - cam.y)
            ratio = max(0.0, self.timer / self.TIMER)
            col = GREEN if ratio > 0.5 else (GOLD if ratio > 0.25 else RED)
            pygame.draw.rect(surface, (60, 0, 0), (sx - 40, sy - 130, 80, 8))
            pygame.draw.rect(surface, col, (sx - 40, sy - 130, int(80 * ratio), 8))
        super().draw(surface, cam)

    def _draw_crate(self, surface, cam, c):
        s = Crate.SIZE
        sx = int(c.x - cam.x) - s // 2
        sy = int(c.y - cam.y) - s // 2

        if c.scanned:
            self._draw_radiograph(surface, sx, sy, s, c)
        else:
            # Every unscanned crate must be pixel-identical -- no random() in
            # this path, or the jitter itself becomes the tell.
            pygame.draw.rect(surface, (124, 96, 62), (sx, sy, s, s))
            for i in range(1, 4):
                pygame.draw.line(surface, (98, 74, 46),
                                 (sx, sy + i * s // 4), (sx + s, sy + i * s // 4), 2)
            pygame.draw.line(surface, (98, 74, 46), (sx, sy), (sx + s, sy + s), 2)
            pygame.draw.line(surface, (98, 74, 46), (sx + s, sy), (sx, sy + s), 2)
            for bx, by in ((sx, sy), (sx + s - 10, sy),
                           (sx, sy + s - 10), (sx + s - 10, sy + s - 10)):
                pygame.draw.rect(surface, DARK_GRAY, (bx, by, 10, 10))
            pygame.draw.polygon(surface, GOLD, [(sx + s // 2 - 7, sy + s // 2 + 6),
                                                (sx + s // 2, sy + s // 2 - 7),
                                                (sx + s // 2 + 7, sy + s // 2 + 6)], 2)
        pygame.draw.rect(surface, (34, 30, 26), (sx, sy, s, s), 3)

        if c.char > 0:
            glow = pygame.Surface((s, s), pygame.SRCALPHA)
            glow.fill((*FIRE_HOT, int(120 * c.char)))
            surface.blit(glow, (sx, sy))

        if c.scanned:
            pygame.draw.line(surface, XRAY_C, (sx + 3, sy + 3), (sx + 13, sy + 3), 2)
            pygame.draw.line(surface, XRAY_C, (sx + 3, sy + 3), (sx + 3, sy + 13), 2)

    def _draw_radiograph(self, surface, sx, sy, s, c):
        """Film-positive convention: dense material reads bright on a near-black
        plate. 44x44 of usable interior after the frame, and events.py loads no
        font, so every tell here has to be pictographic."""
        pygame.draw.rect(surface, (16, 22, 28), (sx, sy, s, s))
        ix, iy = sx + 6, sy + 6

        if c.content == 'bomb':
            bx = ix + 7
            for i in range(3):
                x0 = bx + i * 11
                pygame.draw.rect(surface, (206, 236, 246), (x0, iy + 8, 8, 26))
                pygame.draw.rect(surface, (128, 168, 184), (x0, iy + 8, 8, 26), 1)
            pygame.draw.rect(surface, (238, 250, 255), (bx - 2, iy + 19, 34, 3))
            pygame.draw.rect(surface, (232, 246, 252), (ix + 30, iy + 2, 11, 8))
            pygame.draw.rect(surface, (110, 150, 168), (ix + 30, iy + 2, 11, 8), 1)
            pygame.draw.lines(surface, (255, 255, 255), False,
                              [(ix + 30, iy + 8), (ix + 24, iy + 12),
                               (ix + 27, iy + 16), (ix + 18, iy + 14)], 2)
        elif c.content == 'lead':
            # The scan simply stops at the lining. The absence is the point.
            pygame.draw.rect(surface, (6, 6, 9), (ix - 3, iy - 3, s - 6, s - 6))
            for i in range(3):
                gy = iy + 8 + i * 14 + int(2 * math.sin(c._t * 3 + i))
                pygame.draw.line(surface, (0, 90, 100), (ix, gy), (ix + 44, gy), 1)
        else:
            for ox, oy, r in ((10, 12, 7), (26, 10, 6), (16, 30, 8), (32, 28, 5)):
                pygame.draw.circle(surface, (74, 92, 102), (ix + ox, iy + oy), r)
            pygame.draw.line(surface, (66, 84, 94), (ix + 2, iy + 22), (ix + 42, iy + 18), 2)

    def _draw_icon(self, surface, sx, sy):
        # Crate outline with a scan line
        pygame.draw.rect(surface, (150, 118, 76), (sx - 8, sy - 7, 16, 14))
        pygame.draw.rect(surface, DARK_GRAY, (sx - 8, sy - 7, 16, 14), 2)
        pygame.draw.line(surface, XRAY_C, (sx - 10, sy), (sx + 10, sy), 2)


# ─── FACTORY ──────────────────────────────────────────────────────────────────

EVENT_FACTORIES = {
    EventType.FIGHT_CRIMINALS: make_criminals_event,
    EventType.FIGHT_ROBOTS:    make_robots_event,
    EventType.FIGHT_BRAINIAC:  make_brainiac_event,
    EventType.FIGHT_METALLO:   make_metallo_event,
    EventType.FIGHT_LEX_GOONS:    make_lex_goons_event,
    EventType.FIGHT_LEX_MECHSUIT: make_lex_mechsuit_event,
    EventType.RESCUE_FIRE:     FireEvent,
    EventType.RESCUE_FALLING:  FallingEvent,
    EventType.RESCUE_CAR:      CarEvent,
    EventType.RESCUE_HOSTAGE:  HostageEvent,
    EventType.ANIMAL_CAT:      CatEvent,
    EventType.ANIMAL_FLOOD:    FloodEvent,
    EventType.RESCUE_RUBBLE:   RubbleEvent,
    EventType.FIGHT_LEX_CRATES: CrateEvent,
}


def spawn_random_event(x, y, exclude_types=None):
    choices = list(EventType)
    if exclude_types:
        choices = [t for t in choices if t not in exclude_types]
    etype = random.choice(choices)
    factory = EVENT_FACTORIES[etype]
    return factory(x, y)
