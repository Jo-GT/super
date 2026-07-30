import pygame
import math
import random
from constants import *


class Particle:
    def __init__(self, x, y, vx, vy, color, life, size=4, fade=True, gravity=0):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = float(vx), float(vy)
        self.color = color
        self.life = life
        self.max_life = life
        self.size = size
        self.fade = fade
        self.gravity = gravity

    def update(self, dt):
        self.x += self.vx * dt * 60
        self.y += self.vy * dt * 60
        self.vy += self.gravity * dt * 60
        self.vx *= 0.97
        self.vy *= 0.97
        self.life -= dt

    def draw(self, surface, cam):
        if self.life <= 0:
            return
        alpha = int(255 * (self.life / self.max_life)) if self.fade else 255
        alpha = max(0, min(255, alpha))
        sz = max(1, int(self.size * (self.life / self.max_life)))
        sx = int(self.x - cam.x)
        sy = int(self.y - cam.y)
        r, g, b = self.color
        c = (r, g, b, alpha)
        s = pygame.Surface((sz * 2, sz * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, c, (sz, sz), sz)
        surface.blit(s, (sx - sz, sy - sz))

    @property
    def dead(self):
        return self.life <= 0


class ParticleSystem:
    def __init__(self):
        self.particles: list[Particle] = []
        self.rings: list[dict] = []

    def add(self, p: Particle):
        self.particles.append(p)

    def burst(self, x, y, color, count=12, speed=3, size=5, life=0.5, gravity=0):
        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            spd = random.uniform(speed * 0.5, speed)
            self.add(Particle(x, y, math.cos(angle) * spd, math.sin(angle) * spd,
                               color, random.uniform(life * 0.5, life), size, gravity=gravity))

    def trail(self, x, y, color, angle, spread=0.4, count=3, speed=1.5, life=0.25, size=3):
        back = angle + math.pi
        for _ in range(count):
            a = back + random.uniform(-spread, spread)
            spd = random.uniform(speed * 0.5, speed)
            self.add(Particle(x, y, math.cos(a) * spd, math.sin(a) * spd,
                               color, life, size))

    def fire_burst(self, x, y, count=6):
        for _ in range(count):
            angle = random.uniform(-math.pi / 3, -math.pi * 2 / 3)
            spd = random.uniform(1, 3)
            c = FIRE_HOT if random.random() > 0.5 else FIRE_WARM
            self.add(Particle(x + random.randint(-15, 15), y,
                               math.cos(angle) * spd, math.sin(angle) * spd,
                               c, random.uniform(0.3, 0.8), random.randint(4, 8)))

    def frost_breath(self, x, y, angle, reach=180, half_angle=0.55, count=10):
        for _ in range(count):
            a = angle + random.uniform(-half_angle, half_angle)
            dist = random.uniform(0.15, 1.0) * reach
            bx = x + math.cos(a) * dist
            by = y + math.sin(a) * dist
            spd = random.uniform(0.4, 1.3)
            color = ICE if random.random() > 0.35 else (200, 240, 255)
            self.add(Particle(bx, by, math.cos(a) * spd, math.sin(a) * spd,
                               color, random.uniform(0.3, 0.5), random.randint(3, 7)))

    def heat_beam(self, x1, y1, x2, y2, count=8):
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length == 0:
            return
        nx, ny = dx / length, dy / length
        perp_x, perp_y = -ny, nx
        for _ in range(count):
            t = random.uniform(0, 1)
            bx = x1 + nx * t * length + perp_x * random.uniform(-6, 6)
            by = y1 + ny * t * length + perp_y * random.uniform(-6, 6)
            c = FIRE_HOT if random.random() > 0.5 else (255, 120, 0)
            self.add(Particle(bx, by, perp_x * random.uniform(-0.5, 0.5),
                               perp_y * random.uniform(-0.5, 0.5),
                               c, random.uniform(0.05, 0.15), random.randint(3, 6)))

    def shockwave(self, x, y):
        self.burst(x, y, YELLOW_S, count=20, speed=5, size=6, life=0.4)
        self.burst(x, y, WHITE, count=10, speed=3, size=4, life=0.3)

    def sonic_boom(self, x, y, color=CYAN):
        self.rings.append({'x': x, 'y': y, 'age': 0.0, 'life': 0.45, 'color': color})
        self.rings.append({'x': x, 'y': y, 'age': 0.08, 'life': 0.45, 'color': WHITE})
        self.burst(x, y, color, count=24, speed=7, size=5, life=0.35)
        self.burst(x, y, WHITE, count=14, speed=5, size=4, life=0.25)

    def update(self, dt):
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if not p.dead]
        for r in self.rings:
            r['age'] += dt
        self.rings = [r for r in self.rings if r['age'] < r['life']]

    def draw(self, surface, cam):
        vp = pygame.Rect(0, 0, SCREEN_W, SCREEN_H)
        for r in self.rings:
            t = max(0.0, r['age'] / r['life'])
            radius = int(16 + 260 * t)
            alpha = max(0, int(220 * (1 - t)))
            if alpha <= 0:
                continue
            sx = int(r['x'] - cam.x)
            sy = int(r['y'] - cam.y)
            d = radius * 2 + 8
            s = pygame.Surface((d, d), pygame.SRCALPHA)
            pygame.draw.circle(s, (*r['color'][:3], alpha), (radius + 4, radius + 4), radius, 4)
            surface.blit(s, (sx - radius - 4, sy - radius - 4))
        for p in self.particles:
            sx = int(p.x - cam.x)
            sy = int(p.y - cam.y)
            if vp.collidepoint(sx, sy):
                p.draw(surface, cam)
