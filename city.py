import pygame
import random
import math
from constants import *


class Building:
    def __init__(self, x, y, w, h, color):
        self.rect = pygame.Rect(x, y, w, h)
        self.color = color
        self.win_color = (200, 220, 255) if random.random() > 0.4 else (255, 245, 170)
        self.windows = []
        gap = 14
        for wy in range(y + 8, y + h - 4, gap):
            for wx in range(x + 6, x + w - 4, gap):
                lit = random.random() > 0.45
                self.windows.append((pygame.Rect(wx, wy, 6, 6), lit))

    def draw(self, surface, cam):
        sr = pygame.Rect(self.rect.x - cam.x, self.rect.y - cam.y, self.rect.w, self.rect.h)
        vp = pygame.Rect(0, 0, SCREEN_W, SCREEN_H)
        if not sr.colliderect(vp):
            return
        pygame.draw.rect(surface, self.color, sr)
        top = (min(255, self.color[0] + 20), min(255, self.color[1] + 20), min(255, self.color[2] + 20))
        pygame.draw.line(surface, top, sr.topleft, sr.topright, 2)
        pygame.draw.line(surface, top, sr.topleft, sr.bottomleft, 1)
        for wr, lit in self.windows:
            wsr = pygame.Rect(wr.x - cam.x, wr.y - cam.y, wr.w, wr.h)
            if vp.colliderect(wsr):
                c = self.win_color if lit else (15, 20, 45)
                pygame.draw.rect(surface, c, wsr)


class City:
    ROAD_W = 44
    BLOCK_W = 210
    BLOCK_H = 175

    def __init__(self, seed=7):
        random.seed(seed)
        self.buildings: list[Building] = []
        self.parks: list[pygame.Rect] = []
        self._generate()

    def _generate(self):
        bw, bh = self.BLOCK_W, self.BLOCK_H
        rw = self.ROAD_W
        x = 0
        col_xs = []
        while x < WORLD_W:
            col_xs.append(x)
            x += bw
        y = 0
        row_ys = []
        while y < WORLD_H:
            row_ys.append(y)
            y += bh

        for ry in row_ys:
            for cx in col_xs:
                bx = cx + rw
                by = ry + rw
                bww = bw - rw - 2
                bhh = bh - rw - 2
                if bww < 20 or bhh < 20:
                    continue
                if random.random() < 0.13:
                    self.parks.append(pygame.Rect(bx, by, bww, bhh))
                    continue
                self._fill_block(bx, by, bww, bhh)

    def _fill_block(self, bx, by, bw, bh):
        n = random.randint(1, 3)
        color = lambda: random.choice(BLDG_COLORS)
        if n == 1:
            h = random.randint(max(20, bh // 2), bh)
            self.buildings.append(Building(bx + 2, by + 2, bw - 4, h - 4, color()))
        elif n == 2:
            sp = random.randint(bw // 3, 2 * bw // 3)
            h1 = random.randint(max(20, bh // 2), bh)
            h2 = random.randint(max(20, bh // 2), bh)
            self.buildings.append(Building(bx + 2, by + 2, sp - 4, h1 - 4, color()))
            self.buildings.append(Building(bx + sp + 2, by + 2, bw - sp - 4, h2 - 4, color()))
        else:
            sp = random.randint(bw // 3, 2 * bw // 3)
            sy2 = random.randint(bh // 3, 2 * bh // 3)
            for (fx, fy, fw, fh) in [
                (bx + 2, by + 2, sp - 4, sy2 - 4),
                (bx + sp + 2, by + 2, bw - sp - 4, sy2 - 4),
                (bx + 2, by + sy2 + 2, sp - 4, bh - sy2 - 4),
                (bx + sp + 2, by + sy2 + 2, bw - sp - 4, bh - sy2 - 4),
            ]:
                if fw > 12 and fh > 12:
                    self.buildings.append(Building(fx, fy, fw, fh, color()))

    def draw_ground(self, surface, cam):
        surface.fill(ROAD)
        vp = pygame.Rect(cam.x - 10, cam.y - 10, SCREEN_W + 20, SCREEN_H + 20)
        bw, bh, rw = self.BLOCK_W, self.BLOCK_H, self.ROAD_W
        # sidewalk strips
        x = 0
        while x < WORLD_W:
            sr = pygame.Rect(x - cam.x, -cam.y, rw, WORLD_H)
            pygame.draw.rect(surface, SIDEWALK, sr.clip(pygame.Rect(0, 0, SCREEN_W, SCREEN_H)))
            # road markings (center dashes)
            cx2 = x + rw // 2 - cam.x
            for dy in range(0, SCREEN_H + bh, bh):
                pygame.draw.line(surface, ROAD_MRK, (cx2, dy), (cx2, dy + bh // 3), 2)
            x += bw
        y = 0
        while y < WORLD_H:
            sr = pygame.Rect(-cam.x, y - cam.y, WORLD_W, rw)
            pygame.draw.rect(surface, SIDEWALK, sr.clip(pygame.Rect(0, 0, SCREEN_W, SCREEN_H)))
            cy2 = y + rw // 2 - cam.y
            for dx in range(0, SCREEN_W + bw, bw):
                pygame.draw.line(surface, ROAD_MRK, (dx, cy2), (dx + bw // 3, cy2), 2)
            y += bh
        for park in self.parks:
            pr = pygame.Rect(park.x - cam.x, park.y - cam.y, park.w, park.h)
            if pr.colliderect(pygame.Rect(0, 0, SCREEN_W, SCREEN_H)):
                pygame.draw.rect(surface, PARK, pr)
                pygame.draw.rect(surface, (28, 75, 28), pr, 2)

    def draw_buildings(self, surface, cam):
        for b in self.buildings:
            b.draw(surface, cam)

    def random_open_position(self):
        """Return a world position that is not inside a building."""
        for _ in range(50):
            x = random.randint(100, WORLD_W - 100)
            y = random.randint(100, WORLD_H - 100)
            if not any(b.rect.collidepoint(x, y) for b in self.buildings):
                return x, y
        return WORLD_W // 2, WORLD_H // 2
