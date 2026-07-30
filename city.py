import pygame
import random
import math
from constants import *


def _outline(surf, color, r, w):
    """Border of r, as four filled bands.

    draw.rect with a width clips the rect to the surface and outlines what's
    left, which would draw a spurious edge along a tile seam for anything
    straddling one. Fills clip cleanly.
    """
    pygame.draw.rect(surf, color, (r.x, r.y, r.w, w))
    pygame.draw.rect(surf, color, (r.x, r.bottom - w, r.w, w))
    pygame.draw.rect(surf, color, (r.x, r.y, w, r.h))
    pygame.draw.rect(surf, color, (r.right - w, r.y, w, r.h))


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


class City:
    ROAD_W = 44
    BLOCK_W = 210
    BLOCK_H = 175
    TILE = 576          # 4608 / 576 = 8, so the world tiles with no remainder

    # Keyed by seed, not per instance: a new City is built for every run, but
    # the same seed always generates the same city, so rasterise it once.
    _TILE_CACHE = {}

    def __init__(self, seed=7):
        random.seed(seed)
        self.seed = seed
        self.buildings: list[Building] = []
        self.parks: list[pygame.Rect] = []
        self._tiles = None
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

    # ─── RENDERING ────────────────────────────────────────────────────────────

    def ensure_tiles(self):
        """Rasterise the city. Needs the display to be up, so not done in __init__."""
        tiles = City._TILE_CACHE.get(self.seed)
        if tiles is None:
            tiles = City._TILE_CACHE[self.seed] = self._build_tiles()
        self._tiles = tiles

    def _build_tiles(self):
        t = self.TILE
        tiles = {}
        for ty in range(WORLD_H // t):
            for tx in range(WORLD_W // t):
                surf = pygame.Surface((t, t))
                self._render_region(surf, tx * t, ty * t)
                tiles[(tx, ty)] = surf.convert()
        return tiles

    def _render_region(self, surf, ox, oy):
        """Draw the world rect starting at (ox, oy) into surf.

        Everything is positioned in world space, including the road dashes --
        those used to be laid out relative to the screen, so they slid along
        the roads as the camera moved.
        """
        w, h = surf.get_size()
        clip = pygame.Rect(0, 0, w, h)
        bw, bh, rw = self.BLOCK_W, self.BLOCK_H, self.ROAD_W
        surf.fill(ROAD)

        for x in range(0, WORLD_W, bw):
            strip = pygame.Rect(x - ox, -oy, rw, WORLD_H)
            if strip.colliderect(clip):
                pygame.draw.rect(surf, SIDEWALK, strip.clip(clip))
            cx = x + rw // 2 - ox
            if -2 <= cx <= w + 2:
                for wy in range(0, WORLD_H, bh):
                    dy = wy - oy
                    if -bh <= dy <= h:
                        pygame.draw.line(surf, ROAD_MRK, (cx, dy), (cx, dy + bh // 3), 2)

        for y in range(0, WORLD_H, bh):
            strip = pygame.Rect(-ox, y - oy, WORLD_W, rw)
            if strip.colliderect(clip):
                pygame.draw.rect(surf, SIDEWALK, strip.clip(clip))
            cy = y + rw // 2 - oy
            if -2 <= cy <= h + 2:
                for wx in range(0, WORLD_W, bw):
                    dx = wx - ox
                    if -bw <= dx <= w:
                        pygame.draw.line(surf, ROAD_MRK, (dx, cy), (dx + bw // 3, cy), 2)

        for park in self.parks:
            pr = pygame.Rect(park.x - ox, park.y - oy, park.w, park.h)
            if pr.colliderect(clip):
                pygame.draw.rect(surf, PARK, pr)
                _outline(surf, (28, 75, 28), pr, 2)

        for b in self.buildings:
            br = pygame.Rect(b.rect.x - ox, b.rect.y - oy, b.rect.w, b.rect.h)
            if not br.colliderect(clip):
                continue
            pygame.draw.rect(surf, b.color, br)
            top = (min(255, b.color[0] + 20), min(255, b.color[1] + 20), min(255, b.color[2] + 20))
            pygame.draw.line(surf, top, br.topleft, br.topright, 2)
            pygame.draw.line(surf, top, br.topleft, br.bottomleft, 1)
            for wr, lit in b.windows:
                wsr = pygame.Rect(wr.x - ox, wr.y - oy, wr.w, wr.h)
                if clip.colliderect(wsr):
                    pygame.draw.rect(surf, b.win_color if lit else (15, 20, 45), wsr)

    def draw(self, surface, cam):
        t = self.TILE
        # Truncate the camera once. pygame truncates float blit destinations
        # toward zero, so a tile at -100.7 and its neighbour at 475.3 land 575
        # apart instead of 576, leaving a seam that crawls as you fly.
        cx, cy = int(cam.x), int(cam.y)
        for ty in range(cy // t, (cy + SCREEN_H - 1) // t + 1):
            for tx in range(cx // t, (cx + SCREEN_W - 1) // t + 1):
                surface.blit(self._tiles[(tx, ty)], (tx * t - cx, ty * t - cy))

    def random_open_position(self):
        """Return a world position that is not inside a building."""
        for _ in range(50):
            x = random.randint(100, WORLD_W - 100)
            y = random.randint(100, WORLD_H - 100)
            if not any(b.rect.collidepoint(x, y) for b in self.buildings):
                return x, y
        return WORLD_W // 2, WORLD_H // 2
