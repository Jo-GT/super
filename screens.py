"""Title, pause and game-over screens, and the title reveal player.

Every function here takes the target surface as its first argument. They used to
close over main.py's `screen` global, which would mean importing back from main
and creating the repo's first import cycle.
"""
import math
import os
import random

import pygame

from constants import *
from hud import draw_text, font_large, font_small, font_xl

_TITLE_FRAMES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "Title Page", "frames")
_TITLE_FRAME_FPS = 15.0


# ─── TITLE VIDEO ──────────────────────────────────────────────────────────────

class MenuVideo:
    """Plays the title reveal as a sequence of pre-rendered frame images
    (extracted once from the source mp4 via ffmpeg -- see Title Page/frames),
    holding on the last frame (the "PRESS START" card) rather than looping.
    Uses plain image loading rather than video decoding, so it works the same
    in the desktop build and the pygbag/WASM web build, where opencv isn't
    available. Falls back to no-op if the frames folder is missing."""

    def __init__(self, frames_dir, frame_fps):
        self._frames = []
        self._index = 0
        self._t = 0.0
        self._frame_dt = 1.0 / frame_fps
        self._done = False
        self.surface = None
        try:
            names = sorted(f for f in os.listdir(frames_dir) if f.lower().endswith(".jpg"))
            for name in names:
                self._frames.append(pygame.image.load(os.path.join(frames_dir, name)).convert())
        except Exception:
            self._frames = []
        if self._frames:
            self._set_frame(0)

    def _set_frame(self, index):
        self._index = index
        frame = self._frames[index]
        if frame.get_size() != (SCREEN_W, SCREEN_H):
            frame = pygame.transform.smoothscale(frame, (SCREEN_W, SCREEN_H))
        self.surface = frame

    def update(self, dt):
        if not self._frames or self._done:
            return
        self._t += dt
        while self._t >= self._frame_dt and not self._done:
            self._t -= self._frame_dt
            if self._index + 1 >= len(self._frames):
                self.release()
            else:
                self._set_frame(self._index + 1)

    def release(self):
        """Free the intro frames, keeping the final "PRESS START" card.
        Holds the last frame, not the current one, so quitting to the menu
        mid-intro doesn't leave it stuck on a half-played frame."""
        if self._frames:
            self._set_frame(len(self._frames) - 1)
        self._frames = []
        self._index = 0
        self._done = True

    def draw(self, surface):
        if self.surface is None:
            return False
        surface.blit(self.surface, (0, 0))
        return True


# ─── SCREENS ──────────────────────────────────────────────────────────────────

menu_video = MenuVideo(_TITLE_FRAMES_DIR, _TITLE_FRAME_FPS)

# Held for the whole run rather than rebuilt per frame — a full-screen SRCALPHA
# allocation every frame is the expensive path (see ScreenFlash).
_pause_dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
_pause_dim.fill((0, 0, 0, 160))

PAUSE_ITEMS = ("Resume", "Exit Game")


def draw_pause(surface, selected):
    """Menu over a dimmed still of the game. The caller draws the world first
    and does the flip, so this only lays the dim and the text on top."""
    surface.blit(_pause_dim, (0, 0))
    t = pygame.time.get_ticks() / 1000
    alpha = int(180 + 75 * abs(math.sin(t * 2)))

    draw_text(surface, "PAUSED", font_xl, GOLD, SCREEN_W // 2, 220, center=True)
    for i, label in enumerate(PAUSE_ITEMS):
        y = 330 + i * 56
        if i == selected:
            draw_text(surface, f"> {label} <", font_large, (*GOLD[:3], alpha),
                      SCREEN_W // 2, y, center=True)
        else:
            draw_text(surface, label, font_large, LGRAY, SCREEN_W // 2, y, center=True)

    # Sits under the items rather than at the foot of the screen — the HUD's
    # power-icon row lives down there and the two overlap illegibly.
    draw_text(surface, "UP/DOWN: Select   ENTER: Confirm   ESC: Resume",
              font_small, LGRAY, SCREEN_W // 2, 470, center=True)


def draw_menu(surface):
    t = pygame.time.get_ticks() / 1000
    alpha = int(180 + 75 * abs(math.sin(t * 2)))

    if menu_video.draw(surface):
        # Video already carries the title, skyline and its own "press start"
        # card, so just add a slim functional footer with the real key binds.
        foot_bg = pygame.Surface((SCREEN_W, 34), pygame.SRCALPHA)
        foot_bg.fill((0, 0, 0, 130))
        surface.blit(foot_bg, (0, SCREEN_H - 34))
        draw_text(surface, "WASD/Arrows: Fly   Mouse: Aim   ENTER: Begin   ESC: Quit",
                  font_small, (*GOLD[:3], alpha), SCREEN_W // 2, SCREEN_H - 17, center=True)
    else:
        # Fallback if the video/opencv isn't available
        surface.fill(SKY)
        # City silhouette
        for i in range(20):
            bw = random.randint(40, 90)
            bh = random.randint(80, 280)
            bx = i * 65 - 10
            by = SCREEN_H - bh - 30
            pygame.draw.rect(surface, (30, 32, 38), (bx, by, bw, bh))
        # Stars
        for i in range(60):
            sx2 = (i * 137) % SCREEN_W
            sy2 = (i * 97) % (SCREEN_H // 2)
            pygame.draw.circle(surface, WHITE, (sx2, sy2), 1)

        # Title
        draw_text(surface, "SUPERMAN", font_xl, YELLOW_S, SCREEN_W // 2, 130, center=True)
        draw_text(surface, "Guardian of Metropolis", font_large, BLUE_S, SCREEN_W // 2, 200, center=True)

        # Controls box
        bx2, by2 = SCREEN_W // 2 - 300, 250
        box_h = 300          # 8 rows at 36px from by2+16 end at ~by2+285
        bg = pygame.Surface((600, box_h), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 160))
        surface.blit(bg, (bx2, by2))
        pygame.draw.rect(surface, BLUE_S, (bx2, by2, 600, box_h), 2)
        controls = [
            ("WASD / Arrows", "Fly"),
            ("Space / Left Click", "Heat Vision (hold)"),
            ("F / Right Click", "Freeze Breath"),
            ("Q", "Super Punch (dash to enemy)"),
            ("Shift", "Super Speed"),
            ("X", "X-Ray Vision (burst)"),
            ("C", "Call Krypto (temporary ally)"),
            ("Mouse", "Aim direction"),
        ]
        for i, (key, desc) in enumerate(controls):
            y = by2 + 16 + i * 36
            draw_text(surface, key, font_small, YELLOW_S, bx2 + 20, y)
            draw_text(surface, desc, font_small, WHITE, bx2 + 220, y)

        # Start prompt
        draw_text(surface, "Press ENTER to begin", font_large, (*GOLD[:3], alpha), SCREEN_W // 2, 585, center=True)
        draw_text(surface, "ESC to quit", font_small, LGRAY, SCREEN_W // 2, 630, center=True)

    pygame.display.flip()


def draw_game_over(surface, score, reputation):
    surface.fill((10, 0, 20))
    draw_text(surface, "SUPERMAN HAS FALLEN", font_xl, RED, SCREEN_W // 2, 200, center=True)
    draw_text(surface, "Metropolis is in danger...", font_large, LGRAY, SCREEN_W // 2, 280, center=True)
    draw_text(surface, f"Final Score: {score:,}", font_large, GOLD, SCREEN_W // 2, 360, center=True)
    draw_text(surface, f"Reputation: {reputation}/100", font_large, LGRAY, SCREEN_W // 2, 410, center=True)
    t = pygame.time.get_ticks() / 1000
    alpha = int(180 + 75 * abs(math.sin(t * 2)))
    draw_text(surface, "Press ENTER to play again", font_large, (*WHITE[:3], alpha), SCREEN_W // 2, 500, center=True)
    draw_text(surface, "ESC for menu", font_small, LGRAY, SCREEN_W // 2, 550, center=True)
    pygame.display.flip()
