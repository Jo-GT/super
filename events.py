import pygame
import math
import random
from constants import *
from entities import Thug, Robot, BrainiacDrone, Metallo, LexGoon, LexMechSuit, Civilian, Animal, Projectile


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
        for i, (fx, fy) in enumerate(self.flames):
            if self.flame_hp[i] > 0:
                fsx = int(fx - cam.x); fsy = int(fy - cam.y)
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
        pygame.draw.circle(surface, FLESH, (sx, sy), 8)
        pygame.draw.line(surface, FLESH, (sx, sy + 8), (sx, sy + 22), 3)
        pygame.draw.line(surface, FLESH, (sx - 8, sy + 12), (sx + 8, sy + 12), 3)
        pygame.draw.line(surface, FLESH, (sx - 5, sy + 22), (sx, sy + 32), 3)
        pygame.draw.line(surface, FLESH, (sx + 5, sy + 22), (sx, sy + 32), 3)
        # Ground danger indicator
        gy = int(self.ground_y - cam.y)
        pygame.draw.line(surface, (RED[0], RED[1], RED[2]), (sx - 20, gy), (sx + 20, gy), 3)
        # Remaining distance
        progress = max(0, (self.ground_y - self.person_y) / (self.ground_y - (self.y - 280)))
        pygame.draw.rect(surface, (80, 0, 0), (sx - 20, sy - 20, 40, 5))
        pygame.draw.rect(surface, RED, (sx - 20, sy - 20, int(40 * progress), 5))

    def _draw_icon(self, surface, sx, sy):
        pygame.draw.circle(surface, FLESH, (sx, sy - 4), 5)
        pygame.draw.line(surface, FLESH, (sx, sy + 1), (sx, sy + 8), 2)


# ─── RUNAWAY CAR ──────────────────────────────────────────────────────────────

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

        self.car_x += self.car_vx * dt
        self.car_y += self.car_vy * dt
        self._traveled += math.hypot(self.car_vx, self.car_vy) * dt

        # Superman punch stops the car
        if superman.punch_cd > 0 and superman.punch_cd < 1.5:
            if math.hypot(superman.x - self.car_x, superman.y - self.car_y) < 80:
                self.stopped = True
                particles.shockwave(self.car_x, self.car_y)
                self.complete = True
                return

        # Collision with Superman body also stops it
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
        # Draw tree
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)
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

    def on_activate(self, superman):
        pass

    def update(self, dt, superman, particles):
        super().update(dt, superman, particles)
        self._t += dt
        if not self.active:
            return

        # Water rises (freeze breath held near animals slows the flood)
        freeze_factor = 0.2 if any(
            math.hypot(superman.x - a.x, superman.y - a.y) < 300 and superman.freeze_active
            for a in self.animals
        ) else 1.0
        self.water_level += 0.08 * freeze_factor * dt
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
            ws.fill((*WATER_C, 130))
            surface.blit(ws, (sx - 150, sy + 80 - wh))
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
}


def spawn_random_event(x, y, exclude_types=None):
    choices = list(EventType)
    if exclude_types:
        choices = [t for t in choices if t not in exclude_types]
    etype = random.choice(choices)
    factory = EVENT_FACTORIES[etype]
    return factory(x, y)
