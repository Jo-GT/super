import pygame
import math
import random
import os
from constants import *

_SPRITES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites", "superman")


def _rot(cx, cy, dx, dy, angle):
    c, s = math.cos(angle), math.sin(angle)
    return cx + dx * c - dy * s, cy + dx * s + dy * c


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
    PUNCH_RANGE = 450
    HEAT_RANGE  = 520
    FREEZE_RANGE = 180
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
        self._trail: list[tuple] = []
        self.score = 0
        self.reputation = 50
        self.alive = True
        self.heat_firing = False
        self.freeze_active = False
        self.head_pos = (self.x, self.y)

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
        self._hit_flash  = max(0, self._hit_flash - dt)
        self.krypto_debuff = max(0, self.krypto_debuff - dt)

        if self.speed_remaining > 0:
            self.speed_remaining -= dt

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

    def can_use_heat_vision(self):
        return self.heat_cd <= 0

    def try_heat_vision(self, enemies, particles):
        if self.heat_cd > 0:
            return
        self.heat_cd = self.HEAT_CD
        hx, hy = self.head_pos
        tx = hx + math.cos(self.facing) * self.HEAT_RANGE
        ty = hy + math.sin(self.facing) * self.HEAT_RANGE
        particles.heat_beam(hx, hy, tx, ty)
        for e in enemies:
            if self._in_beam(e.x, e.y, tx, ty, 28):
                e.take_damage(self.HEAT_DPS * self.HEAT_CD)

    def try_freeze(self, enemies, particles):
        if self.freeze_cd > 0:
            return False
        self.freeze_cd = self.FREEZE_CD
        hx, hy = self.head_pos
        particles.frost_breath(hx, hy, self.facing, self.FREEZE_RANGE)
        for e in enemies:
            dx = e.x - hx
            dy = e.y - hy
            d = math.hypot(dx, dy)
            if d < self.FREEZE_RANGE:
                a = math.atan2(dy, dx)
                diff = abs((a - self.facing + math.pi) % (2 * math.pi) - math.pi)
                if diff < 0.75:
                    e.freeze(self.FREEZE_LOCK)
        return True

    def try_punch(self, enemies, particles):
        if self.punch_cd > 0:
            return
        nearest = None
        best_d = self.PUNCH_RANGE
        for e in enemies:
            d = math.hypot(e.x - self.x, e.y - self.y)
            if d < best_d:
                best_d = d; nearest = e
        if nearest is None:
            return
        self.punch_cd = self.PUNCH_CD
        self.x, self.y = nearest.x, nearest.y
        particles.shockwave(self.x, self.y)
        for e in enemies:
            if math.hypot(e.x - self.x, e.y - self.y) < 90:
                e.take_damage(self.PUNCH_DMG)

    def try_speed(self):
        if self.speed_cd > 0 or self.speed_remaining > 0:
            return False
        self.speed_remaining = self.SPEED_DUR
        self.speed_cd = self.SPEED_CD
        return True

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
        diff = abs((a - self.facing + math.pi) % (2 * math.pi) - math.pi)
        return diff < 0.75

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

        # Head position in world space: rotate the pose's local head offset by facing,
        # mirroring the same flip-then-rotate the sprite itself goes through below so
        # effects (heat vision) track the actual rendered head, not the body center.
        hdx, hdy = self.HEAD_OFFSET_HOVER if base is self._sprite_hover else self.HEAD_OFFSET_FLY
        c, s = math.cos(self.facing), math.sin(self.facing)
        hpx = hdx * c - hdy * s
        hpy = hdx * s + hdy * c
        if c < 0:
            hpy = -hpy
        self.head_pos = (self.x + hpx, self.y + hpy)

        if base is not None:
            # Flip horizontally when facing left, then rotate to match facing direction.
            # Sprites face right by default (angle 0). Rotation uses screen-space convention
            # where y increases downward, so clockwise = negative pygame angle.
            flip_x = math.cos(self.facing) < 0
            if flip_x:
                draw_sprite = pygame.transform.flip(base, True, False)
                # Mirror the angle across the y-axis so the flipped sprite tracks correctly
                angle_deg = math.degrees(self.facing - math.copysign(math.pi, self.facing))
            else:
                draw_sprite = base
                angle_deg = -math.degrees(self.facing)

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
            gs = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*FIRE_HOT, 200), (16, 16), 14)
            surface.blit(gs, (ex - 16, ey - 16))

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
    HP = 35; SPEED = 1.8; DMG = 0.0; COLOR = (80, 80, 80); RADIUS = 14

    def update(self, dt, superman, particles):
        self._base_update(dt)
        self._move_toward(superman.x, superman.y, dt)
        self.try_attack(superman, dt)

    def draw(self, surface, cam):
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)
        self._draw_base(surface, cam, (80, 80, 80))
        # Weapon stick
        ex = sx + int(math.cos(self._angle) * 18)
        ey = sy + int(math.sin(self._angle) * 18)
        c = WHITE if self._hit_flash > 0 else BROWN
        pygame.draw.line(surface, c, (sx, sy), (ex, ey), 3)
        pygame.draw.circle(surface, (60, 60, 60), (sx, sy), 6)


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
        elif d < target_d - 30:
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

    def __init__(self, x, y):
        super().__init__(x, y)
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


# ─── PROJECTILE ──────────────────────────────────────────────────────────────

class Projectile:
    def __init__(self, x, y, angle, speed, color, radius=5, life=2.0):
        self.x, self.y = float(x), float(y)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.color = color
        self.radius = radius
        self.life = life
        self.dead = False

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
        gs = pygame.Surface((self.radius * 4, self.radius * 4), pygame.SRCALPHA)
        pygame.draw.circle(gs, (*self.color, 120), (self.radius * 2, self.radius * 2), self.radius * 2)
        pygame.draw.circle(gs, (*self.color, 255), (self.radius * 2, self.radius * 2), self.radius)
        surface.blit(gs, (sx - self.radius * 2, sy - self.radius * 2))


# ─── CIVILIAN / ANIMAL ───────────────────────────────────────────────────────

class Civilian:
    def __init__(self, x, y, hostage=False):
        self.x, self.y = float(x), float(y)
        self.saved = False
        self.hostage = hostage
        self._t = 0.0

    def update(self, dt, superman):
        self._t += dt
        if not self.saved:
            d = math.hypot(superman.x - self.x, superman.y - self.y)
            if d < 30:
                self.saved = True

    def draw(self, surface, cam):
        if self.saved:
            return
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)
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


class Animal:
    TYPES = ['cat', 'dog', 'bird']

    def __init__(self, x, y, kind=None):
        self.x, self.y = float(x), float(y)
        self.saved = False
        self.kind = kind or random.choice(self.TYPES)
        self._t = 0.0

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
        if self.kind == 'cat':
            c = (200, 160, 100)
            pygame.draw.ellipse(surface, c, (sx - 10, sy - 7 + bob, 20, 14))
            # Ears
            pygame.draw.polygon(surface, c, [(sx - 8, sy - 7 + bob), (sx - 12, sy - 14 + bob), (sx - 4, sy - 7 + bob)])
            pygame.draw.polygon(surface, c, [(sx + 4, sy - 7 + bob), (sx + 12, sy - 14 + bob), (sx + 8, sy - 7 + bob)])
        elif self.kind == 'dog':
            c = (180, 130, 80)
            pygame.draw.ellipse(surface, c, (sx - 12, sy - 6 + bob, 24, 12))
            pygame.draw.circle(surface, c, (sx + 12, sy - 4 + bob), 7)
        else:  # bird
            c = (100, 160, 220)
            pygame.draw.ellipse(surface, c, (sx - 8, sy - 5 + bob, 16, 10))
            pygame.draw.polygon(surface, (255, 200, 50), [(sx + 8, sy + bob), (sx + 14, sy - 3 + bob), (sx + 8, sy - 3 + bob)])
        pygame.draw.circle(surface, WHITE, (sx, sy - 18 + bob), 10)
        gs = pygame.Surface((30, 30), pygame.SRCALPHA)
        pygame.draw.circle(gs, (*GREEN, int(100 + 80 * math.sin(self._t * 4))), (15, 15), 12, 2)
        surface.blit(gs, (sx - 15, sy - 28 + bob))
