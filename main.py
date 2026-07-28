"""
Superman: Guardian of Metropolis
=================================
Controls:
  WASD / Arrow Keys  - Fly
  Mouse              - Aim direction
  Space / LMB        - Heat Vision (hold)
  F / RMB            - Freeze Breath
  Q                  - Super Punch (dash to nearest enemy)
  Shift              - Super Speed
"""

import pygame
import math
import random
import asyncio
import os

from constants import *
from city import City
from particles import ParticleSystem
from entities import Superman
from events import BaseEvent, spawn_random_event

try:
    import cv2
    _HAS_CV2 = True
except Exception:
    _HAS_CV2 = False

_TITLE_VIDEO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Title Page", "Superman Title.mp4")

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption(TITLE)
clock = pygame.time.Clock()

try:
    font_xl    = pygame.font.SysFont("Arial", 56, bold=True)
    font_large = pygame.font.SysFont("Arial", 34, bold=True)
    font_med   = pygame.font.SysFont("Arial", 22, bold=True)
    font_small = pygame.font.SysFont("Arial", 17)
    font_tiny  = pygame.font.SysFont("Arial", 14)
except Exception:
    font_xl    = pygame.font.Font(None, 56)
    font_large = pygame.font.Font(None, 34)
    font_med   = pygame.font.Font(None, 22)
    font_small = pygame.font.Font(None, 17)
    font_tiny  = pygame.font.Font(None, 14)

# ─── SOUND ────────────────────────────────────────────────────────────────────

_SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")


def _load_sound(filename):
    try:
        return pygame.mixer.Sound(os.path.join(_SOUNDS_DIR, filename))
    except Exception:
        return None


snd_wind   = _load_sound("flying wind noise.mp3")
snd_sprint = _load_sound("beginsprint.mp3")

try:
    pygame.mixer.music.load(os.path.join(_SOUNDS_DIR, "mainmenutheme.mp3"))
    _menu_music_ok = True
except Exception:
    _menu_music_ok = False


def play_menu_music():
    if _menu_music_ok and not pygame.mixer.music.get_busy():
        pygame.mixer.music.play(loops=-1)


def stop_menu_music():
    if _menu_music_ok:
        pygame.mixer.music.stop()


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def draw_text(surf, text, font, color, x, y, center=False, shadow=True):
    if shadow:
        s = font.render(text, True, BLACK)
        r = s.get_rect()
        if center:
            r.center = (x + 1, y + 1)
        else:
            r.topleft = (x + 1, y + 1)
        surf.blit(s, r)
    img = font.render(text, True, color)
    r = img.get_rect()
    if center:
        r.center = (x, y)
    else:
        r.topleft = (x, y)
    surf.blit(img, r)
    return r


def draw_bar(surf, x, y, w, h, ratio, full_col, empty_col=(60, 0, 0), label=None):
    pygame.draw.rect(surf, empty_col, (x, y, w, h))
    pygame.draw.rect(surf, full_col, (x, y, int(w * max(0, min(1, ratio))), h))
    pygame.draw.rect(surf, WHITE, (x, y, w, h), 1)
    if label:
        draw_text(surf, label, font_tiny, WHITE, x + w + 4, y, shadow=False)


def cooldown_icon(surf, x, y, size, color, label, cd_ratio, key_label):
    bg = pygame.Surface((size, size), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 140))
    surf.blit(bg, (x, y))
    pygame.draw.rect(surf, color, (x, y, size, size), 2)
    draw_text(surf, label, font_tiny, color, x + size // 2, y + size // 2, center=True, shadow=True)
    if cd_ratio > 0:
        overlay = pygame.Surface((size, size), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(180 * cd_ratio)))
        surf.blit(overlay, (x, y))
        draw_text(surf, f"{cd_ratio:.1f}s" if cd_ratio > 0.5 else "", font_tiny, WHITE,
                  x + size // 2, y + size // 2 + 6, center=True, shadow=False)
    draw_text(surf, key_label, font_tiny, LGRAY, x + 2, y + size - 14, shadow=False)


# ─── CAMERA ───────────────────────────────────────────────────────────────────

class Camera:
    def __init__(self):
        self.x = WORLD_W / 2 - SCREEN_W / 2
        self.y = WORLD_H / 2 - SCREEN_H / 2

    def update(self, tx, ty, dt):
        target_x = tx - SCREEN_W / 2
        target_y = ty - SCREEN_H / 2
        speed = min(1.0, 10 * dt)
        self.x += (target_x - self.x) * speed
        self.y += (target_y - self.y) * speed
        self.x = max(0, min(WORLD_W - SCREEN_W, self.x))
        self.y = max(0, min(WORLD_H - SCREEN_H, self.y))


# ─── HUD ──────────────────────────────────────────────────────────────────────

class HUD:
    MINIMAP_W = 200
    MINIMAP_H = 160
    MINIMAP_X = SCREEN_W - 210
    MINIMAP_Y = SCREEN_H - 170

    def __init__(self):
        self._score_anim = 0
        self._last_score = 0

    def draw(self, surface, superman, events, camera, active_event=None):
        # ── Health bar ───────────────────────────────────────────────────────
        hp_ratio = superman.hp / superman.MAX_HP
        hp_col = GREEN if hp_ratio > 0.5 else (GOLD if hp_ratio > 0.25 else RED)
        bg = pygame.Surface((224, 26), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 150))
        surface.blit(bg, (8, 8))
        draw_text(surface, "HP", font_tiny, LGRAY, 12, 12)
        draw_bar(surface, 34, 12, 180, 14, hp_ratio, hp_col)
        draw_text(surface, f"{int(superman.hp)}/{superman.MAX_HP}", font_tiny, WHITE, 220, 12)

        # ── Krypto warning ───────────────────────────────────────────────────
        if superman.krypto_debuff > 0:
            a = int(180 + 75 * abs(math.sin(pygame.time.get_ticks() * 0.005)))
            draw_text(surface, "KRYPTONITE!", font_med, (*KRYPTO, a), SCREEN_W // 2, 8, center=True)

        # ── Score ─────────────────────────────────────────────────────────────
        bg2 = pygame.Surface((180, 26), pygame.SRCALPHA)
        bg2.fill((0, 0, 0, 150))
        surface.blit(bg2, (SCREEN_W - 188, 8))
        draw_text(surface, f"Score: {superman.score:,}", font_med, GOLD, SCREEN_W - 184, 12, shadow=True)

        # Rep bar
        rep_ratio = superman.reputation / 100
        rep_col = LIME if rep_ratio > 0.6 else (GOLD if rep_ratio > 0.3 else RED)
        bg3 = pygame.Surface((180, 18), pygame.SRCALPHA)
        bg3.fill((0, 0, 0, 150))
        surface.blit(bg3, (SCREEN_W - 188, 38))
        draw_text(surface, "Rep", font_tiny, LGRAY, SCREEN_W - 185, 41)
        draw_bar(surface, SCREEN_W - 158, 41, 140, 10, rep_ratio, rep_col, (60, 30, 0))

        # ── Power icons ───────────────────────────────────────────────────────
        icon_y = SCREEN_H - 72
        icon_sz = 56
        powers = [
            ("HEAT\nVISN", FIRE_HOT,   superman.heat_cd,  superman.HEAT_CD,  "SPACE"),
            ("FRZE\nBRTH", ICE,         superman.freeze_cd, superman.FREEZE_CD, "F"),
            ("SPNCH",       YELLOW_S,   superman.punch_cd, superman.PUNCH_CD, "Q"),
            ("SPDS",        CYAN,        superman.speed_cd, superman.SPEED_CD, "SHIFT"),
        ]
        total_w = len(powers) * (icon_sz + 8) - 8
        start_x = SCREEN_W // 2 - total_w // 2
        for i, (label, col, cd, max_cd, key) in enumerate(powers):
            ix = start_x + i * (icon_sz + 8)
            ratio = cd / max_cd if max_cd > 0 else 0
            cooldown_icon(surface, ix, icon_y, icon_sz, col, label, ratio, key)

        # Speed remaining
        if superman.speed_remaining > 0:
            pct = superman.speed_remaining / superman.SPEED_DUR
            ix = start_x + 3 * (icon_sz + 8)
            pygame.draw.rect(surface, CYAN, (ix, icon_y + icon_sz - 6, int(icon_sz * pct), 4))

        # ── Active event banner ───────────────────────────────────────────────
        if active_event:
            name, hint = active_event.get_ui_text()
            cat = active_event.category
            col = CAT_COLORS[cat]
            banner_w = 700
            banner_h = 52
            bx = SCREEN_W // 2 - banner_w // 2
            by = SCREEN_H - 130
            bg_s = pygame.Surface((banner_w, banner_h), pygame.SRCALPHA)
            bg_s.fill((0, 0, 0, 170))
            surface.blit(bg_s, (bx, by))
            pygame.draw.rect(surface, col, (bx, by, banner_w, banner_h), 2)
            draw_text(surface, name, font_large, col, SCREEN_W // 2, by + 12, center=True)
            draw_text(surface, hint, font_tiny, LGRAY, SCREEN_W // 2, by + 36, center=True)

        # ── Minimap ───────────────────────────────────────────────────────────
        mm_surf = pygame.Surface((self.MINIMAP_W, self.MINIMAP_H), pygame.SRCALPHA)
        mm_surf.fill((0, 0, 0, 180))
        scale_x = self.MINIMAP_W / WORLD_W
        scale_y = self.MINIMAP_H / WORLD_H
        # Events
        for ev in events:
            if ev.complete or ev.failed:
                continue
            ex = int(ev.x * scale_x)
            ey = int(ev.y * scale_y)
            col = CAT_COLORS[ev.category]
            a = int(150 + 105 * abs(math.sin(pygame.time.get_ticks() * 0.003)))
            mm_dot = pygame.Surface((8, 8), pygame.SRCALPHA)
            pygame.draw.circle(mm_dot, (*col, a), (4, 4), 4)
            mm_surf.blit(mm_dot, (ex - 4, ey - 4))
        # Superman
        sx2 = int(superman.x * scale_x)
        sy2 = int(superman.y * scale_y)
        pygame.draw.circle(mm_surf, BLUE_S, (sx2, sy2), 3)
        pygame.draw.circle(mm_surf, WHITE, (sx2, sy2), 3, 1)
        # Viewport box
        vx = int(camera.x * scale_x)
        vy = int(camera.y * scale_y)
        vw = int(SCREEN_W * scale_x)
        vh = int(SCREEN_H * scale_y)
        pygame.draw.rect(mm_surf, (*WHITE, 80), (vx, vy, vw, vh), 1)
        pygame.draw.rect(mm_surf, WHITE, (0, 0, self.MINIMAP_W, self.MINIMAP_H), 1)
        surface.blit(mm_surf, (self.MINIMAP_X, self.MINIMAP_Y))
        draw_text(surface, "MAP", font_tiny, LGRAY, self.MINIMAP_X + 4, self.MINIMAP_Y + 2, shadow=False)

        # ── Nearby event prompt ───────────────────────────────────────────────
        for ev in events:
            if ev.complete or ev.failed or ev.active:
                continue
            d = ev.dist_to(superman)
            if d < ev.ACTIVATION_RADIUS:
                alpha = int(255 * (1 - d / ev.ACTIVATION_RADIUS))
                col = CAT_COLORS[ev.category]
                msg = f"Fly into event area to respond: {ev.name}"
                draw_text(surface, msg, font_small, (*col[:3], alpha), SCREEN_W // 2, SCREEN_H - 155, center=True)
                break


# ─── FLASH EFFECT ────────────────────────────────────────────────────────────

class ScreenFlash:
    def __init__(self):
        self.color = WHITE
        self.alpha = 0
        self._surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)

    def trigger(self, color=WHITE, alpha=180):
        self.color = color
        self.alpha = alpha

    def update(self, dt):
        self.alpha = max(0, self.alpha - 400 * dt)

    def draw(self, surface):
        if self.alpha > 0:
            self._surf.fill((*self.color[:3], int(self.alpha)))
            surface.blit(self._surf, (0, 0))


# ─── TITLE VIDEO ──────────────────────────────────────────────────────────────

class MenuVideo:
    """Decodes the title mp4 frame-by-frame and plays it once, holding on the
    last frame (the video's own "PRESS START" card) rather than looping the
    reveal. Falls back to no-op if opencv or the file isn't available, so the
    menu still works without the extra dependency."""

    def __init__(self, path):
        self.surface = None
        self._cap = None
        self._t = 0.0
        self._frame_dt = 1 / 30.0
        self._done = False
        if not _HAS_CV2:
            return
        cap = cv2.VideoCapture(path)
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            self._frame_dt = 1.0 / fps
            self._cap = cap
            self._advance()

    def _advance(self):
        ok, frame = self._cap.read()
        if not ok:
            self._done = True
            return
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = frame.shape[:2]
        surf = pygame.image.frombuffer(frame.tobytes(), (w, h), "RGB")
        if (w, h) != (SCREEN_W, SCREEN_H):
            surf = pygame.transform.smoothscale(surf, (SCREEN_W, SCREEN_H))
        self.surface = surf

    def update(self, dt):
        if not self._cap or self._done:
            return
        self._t += dt
        while self._t >= self._frame_dt and not self._done:
            self._t -= self._frame_dt
            self._advance()

    def draw(self, surface):
        if self.surface is None:
            return False
        surface.blit(self.surface, (0, 0))
        return True


# ─── GAME ─────────────────────────────────────────────────────────────────────

class Game:
    MAX_EVENTS   = 5
    SPAWN_TIMER  = 18.0
    MIN_SPAWN_D  = 500

    def __init__(self):
        self.city   = City(seed=42)
        self.camera = Camera()
        self.pfs    = ParticleSystem()
        start_x, start_y = WORLD_W // 2, WORLD_H // 2
        self.superman = Superman(start_x, start_y)
        self.camera.x = start_x - SCREEN_W / 2
        self.camera.y = start_y - SCREEN_H / 2
        self.events: list[BaseEvent] = []
        self.hud    = HUD()
        self.flash  = ScreenFlash()
        self._spawn_cd = 5.0
        self._active_event: BaseEvent | None = None
        self._notifications: list[tuple] = []  # (text, color, timer)
        self._wind_playing = False

        # Spawn initial events
        for _ in range(3):
            self._try_spawn_event()

    def _try_spawn_event(self):
        if len(self.events) >= self.MAX_EVENTS:
            return
        for _ in range(30):
            x, y = self.city.random_open_position()
            if math.hypot(x - self.superman.x, y - self.superman.y) > self.MIN_SPAWN_D:
                active_types = {e.event_type for e in self.events if not e.complete and not e.failed}
                ev = spawn_random_event(x, y, exclude_types=active_types)
                self.events.append(ev)
                return

    def notify(self, text, color=WHITE):
        self._notifications.append([text, color, 3.0])

    def handle_input(self, dt):
        keys = pygame.key.get_pressed()
        mouse_buttons = pygame.mouse.get_pressed()
        mx, my = pygame.mouse.get_pos()
        mouse_world = (mx + self.camera.x, my + self.camera.y)

        s = self.superman
        all_enemies = []
        for ev in self.events:
            if hasattr(ev, 'enemies'):
                all_enemies.extend(ev.enemies)

        # Heat Vision: Space or LMB (held down for a continuous beam)
        s.heat_firing = bool(keys[pygame.K_SPACE] or mouse_buttons[0])
        if s.heat_firing and s.heat_cd <= 0:
            s.try_heat_vision(all_enemies, self.pfs)

        # Freeze Breath: F or RMB (held for a continuous frost cone)
        s.freeze_active = bool(keys[pygame.K_f] or mouse_buttons[2])
        if s.freeze_active and s.freeze_cd <= 0:
            s.try_freeze(all_enemies, self.pfs)

        # Punch: Q
        if keys[pygame.K_q] and s.punch_cd <= 0:
            s.try_punch(all_enemies, self.pfs)
            self.flash.trigger(YELLOW_S, 60)

        # Speed: Shift
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            if s.try_speed() and snd_sprint:
                snd_sprint.play()

        s.update(dt, keys, mouse_world)

    def stop_sounds(self):
        if snd_wind:
            snd_wind.stop()
        self._wind_playing = False

    def update(self, dt):
        s = self.superman
        if not s.alive:
            return

        self.handle_input(dt)
        self.camera.update(s.x, s.y, dt)
        self.pfs.update(dt)
        self.flash.update(dt)

        # Flying wind loop: on while actually moving, off when hovering
        flying = math.hypot(s.vx, s.vy) > 0.8
        if snd_wind:
            if flying and not self._wind_playing:
                snd_wind.play(loops=-1)
                self._wind_playing = True
            elif not flying and self._wind_playing:
                snd_wind.stop()
                self._wind_playing = False

        # Notifications
        self._notifications = [[t, c, ti - dt] for t, c, ti in self._notifications if ti - dt > 0]

        # Events
        for ev in self.events:
            ev.update(dt, s, self.pfs)
            if ev.complete and not hasattr(ev, '_rewarded'):
                ev._rewarded = True
                s.score += ev.score_value
                s.reputation = min(100, s.reputation + 8)
                self.notify(f"+{ev.score_value}  {ev.name}", GOLD)
                self.flash.trigger(YELLOW_S, 80)
            if ev.failed and not hasattr(ev, '_penalised'):
                ev._penalised = True
                s.reputation = max(0, s.reputation - 12)
                self.notify(f"FAILED: {ev.name}", RED)
                self.flash.trigger(RED, 100)

        # Remove finished events
        self.events = [e for e in self.events if not (e.complete or e.failed)]

        # Spawn new events
        self._spawn_cd -= dt
        if self._spawn_cd <= 0:
            self._spawn_cd = self.SPAWN_TIMER + random.uniform(-4, 4)
            self._try_spawn_event()

        # Determine active event for HUD
        self._active_event = None
        best_d = 9999
        for ev in self.events:
            if ev.active:
                d = ev.dist_to(s)
                if d < best_d:
                    best_d = d
                    self._active_event = ev

        # Speed trail sparks
        if s.speed_remaining > 0:
            self.pfs.trail(s.x, s.y, CYAN, s.facing, count=4, speed=2.5, life=0.3, size=4)

    def draw(self):
        # World
        self.city.draw_ground(screen, self.camera)
        self.city.draw_buildings(screen, self.camera)

        # Events world elements
        for ev in self.events:
            ev.draw(screen, self.camera)

        # Particles (behind Superman)
        self.pfs.draw(screen, self.camera)

        # Superman
        self.superman.draw(screen, self.camera)

        # Heat vision beam (always exits the head, wherever the current pose puts it)
        if self.superman.heat_firing:
            sx = int(self.superman.head_pos[0] - self.camera.x)
            sy = int(self.superman.head_pos[1] - self.camera.y)
            ex = int(sx + math.cos(self.superman.facing) * Superman.HEAT_RANGE)
            ey = int(sy + math.sin(self.superman.facing) * Superman.HEAT_RANGE)
            # Beam (layered glow, drawn every frame the trigger is held for a solid long beam)
            beam_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            pygame.draw.line(beam_surf, (255, 255, 220, 90), (sx, sy), (ex, ey), 16)
            pygame.draw.line(beam_surf, (*FIRE_WARM, 160), (sx, sy), (ex, ey), 9)
            pygame.draw.line(beam_surf, (*FIRE_HOT, 230), (sx, sy), (ex, ey), 4)
            pygame.draw.line(beam_surf, (255, 255, 255, 255), (sx, sy), (ex, ey), 2)
            screen.blit(beam_surf, (0, 0))

        # Freeze breath cone (drawn continuously while held, exits the head)
        if self.superman.freeze_active:
            fx = int(self.superman.head_pos[0] - self.camera.x)
            fy = int(self.superman.head_pos[1] - self.camera.y)
            angle = self.superman.facing
            cone_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            pts = [(fx, fy)]
            reach = Superman.FREEZE_RANGE
            for da in range(-45, 46, 5):
                a = angle + math.radians(da)
                pts.append((fx + math.cos(a) * reach, fy + math.sin(a) * reach))
            if len(pts) > 2:
                pygame.draw.polygon(cone_surf, (*ICE, 90), pts)
                pygame.draw.polygon(cone_surf, (*CYAN, 60), pts, 2)
            screen.blit(cone_surf, (0, 0))

        # Flash
        self.flash.draw(screen)

        # HUD
        self.hud.draw(screen, self.superman, self.events, self.camera, self._active_event)

        # Notifications
        for i, (text, color, timer) in enumerate(reversed(self._notifications)):
            alpha = min(255, int(timer * 200))
            y = SCREEN_H // 2 - 60 - i * 32
            draw_text(screen, text, font_large, (*color[:3], alpha), SCREEN_W // 2, y, center=True)

    def can_use_heat_vision(self):
        return self.superman.heat_cd <= 0


# ─── MENU ─────────────────────────────────────────────────────────────────────

menu_video = MenuVideo(_TITLE_VIDEO_PATH)


def draw_menu():
    t = pygame.time.get_ticks() / 1000
    alpha = int(180 + 75 * abs(math.sin(t * 2)))

    if menu_video.draw(screen):
        # Video already carries the title, skyline and its own "press start"
        # card, so just add a slim functional footer with the real key binds.
        foot_bg = pygame.Surface((SCREEN_W, 34), pygame.SRCALPHA)
        foot_bg.fill((0, 0, 0, 130))
        screen.blit(foot_bg, (0, SCREEN_H - 34))
        draw_text(screen, "WASD/Arrows: Fly   Mouse: Aim   ENTER: Begin   ESC: Quit",
                  font_small, (*GOLD[:3], alpha), SCREEN_W // 2, SCREEN_H - 17, center=True)
    else:
        # Fallback if the video/opencv isn't available
        screen.fill(SKY)
        # City silhouette
        for i in range(20):
            bw = random.randint(40, 90)
            bh = random.randint(80, 280)
            bx = i * 65 - 10
            by = SCREEN_H - bh - 30
            pygame.draw.rect(screen, (30, 32, 38), (bx, by, bw, bh))
        # Stars
        for i in range(60):
            sx2 = (i * 137) % SCREEN_W
            sy2 = (i * 97) % (SCREEN_H // 2)
            pygame.draw.circle(screen, WHITE, (sx2, sy2), 1)

        # Title
        draw_text(screen, "SUPERMAN", font_xl, YELLOW_S, SCREEN_W // 2, 130, center=True)
        draw_text(screen, "Guardian of Metropolis", font_large, BLUE_S, SCREEN_W // 2, 200, center=True)

        # Controls box
        bx2, by2 = SCREEN_W // 2 - 300, 265
        bg = pygame.Surface((600, 240), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 160))
        screen.blit(bg, (bx2, by2))
        pygame.draw.rect(screen, BLUE_S, (bx2, by2, 600, 240), 2)
        controls = [
            ("WASD / Arrows", "Fly"),
            ("Space / Left Click", "Heat Vision (hold)"),
            ("F / Right Click", "Freeze Breath"),
            ("Q", "Super Punch (dash to enemy)"),
            ("Shift", "Super Speed"),
            ("Mouse", "Aim direction"),
        ]
        for i, (key, desc) in enumerate(controls):
            y = by2 + 16 + i * 36
            draw_text(screen, key, font_small, YELLOW_S, bx2 + 20, y)
            draw_text(screen, desc, font_small, WHITE, bx2 + 220, y)

        # Start prompt
        draw_text(screen, "Press ENTER to begin", font_large, (*GOLD[:3], alpha), SCREEN_W // 2, 540, center=True)
        draw_text(screen, "ESC to quit", font_small, LGRAY, SCREEN_W // 2, 590, center=True)

    pygame.display.flip()


def draw_game_over(score, reputation):
    screen.fill((10, 0, 20))
    draw_text(screen, "SUPERMAN HAS FALLEN", font_xl, RED, SCREEN_W // 2, 200, center=True)
    draw_text(screen, "Metropolis is in danger...", font_large, LGRAY, SCREEN_W // 2, 280, center=True)
    draw_text(screen, f"Final Score: {score:,}", font_large, GOLD, SCREEN_W // 2, 360, center=True)
    draw_text(screen, f"Reputation: {reputation}/100", font_large, LGRAY, SCREEN_W // 2, 410, center=True)
    t = pygame.time.get_ticks() / 1000
    alpha = int(180 + 75 * abs(math.sin(t * 2)))
    draw_text(screen, "Press ENTER to play again", font_large, (*WHITE[:3], alpha), SCREEN_W // 2, 500, center=True)
    draw_text(screen, "ESC for menu", font_small, LGRAY, SCREEN_W // 2, 550, center=True)
    pygame.display.flip()


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

async def main():
    state = 'menu'
    game: Game | None = None
    play_menu_music()

    while True:
        dt = clock.tick(FPS) / 1000.0
        dt = min(dt, 0.05)

        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                pygame.quit()
                return

        if state == 'menu':
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        stop_menu_music()
                        game = Game()
                        state = 'play'
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        return
            menu_video.update(dt)
            draw_menu()

        elif state == 'play':
            escape = any(e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE for e in events)
            if escape:
                game.stop_sounds()
                play_menu_music()
                state = 'menu'
            elif not game.superman.alive:
                game.stop_sounds()
                state = 'gameover'
            else:
                game.update(dt)
                game.draw()
                pygame.display.flip()

        elif state == 'gameover':
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        game = Game()
                        state = 'play'
                    if event.key == pygame.K_ESCAPE:
                        play_menu_music()
                        state = 'menu'
            draw_game_over(game.superman.score, game.superman.reputation)

        await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())
