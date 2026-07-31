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
  X                  - X-Ray Vision (burst)
  C                  - Call Krypto (temporary ally)
"""

import pygame
import math
import random
import asyncio
import os

from constants import *
from city import City
from particles import ParticleSystem
from entities import Superman, Krypto
from events import BaseEvent, spawn_random_event
from dialogue import DialogueManager

_TITLE_FRAMES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Title Page", "frames")
_TITLE_FRAME_FPS = 15.0

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

_SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Sounds")


def _load_sound(filename):
    try:
        return pygame.mixer.Sound(os.path.join(_SOUNDS_DIR, filename))
    except Exception:
        return None


snd_wind      = _load_sound("flying wind noise.ogg")
snd_sprint    = _load_sound("beginsprint.ogg")
snd_heat      = _load_sound("heatvision.ogg")
snd_freeze    = _load_sound("freeze breath.ogg")
snd_punch     = _load_sound("punch.ogg")
snd_xray      = _load_sound("xrayvision.ogg")
snd_gameover  = _load_sound("GameOver.ogg")

_MENU_MUSIC_PATH = os.path.join(_SOUNDS_DIR, "mainmenutheme.ogg")
_BGM_MUSIC_PATH  = os.path.join(_SOUNDS_DIR, "MainBGM.ogg")
_BGM_VOLUME      = 0.55
_PAUSE_DUCK      = 0.2   # fraction of normal volume while the pause menu is up
_current_music = None  # 'menu' | 'bgm' | None


def _play_music(path, volume, tag):
    global _current_music
    if _current_music == tag:
        return
    try:
        pygame.mixer.music.load(path)
        pygame.mixer.music.set_volume(volume)
        pygame.mixer.music.play(loops=-1)
        _current_music = tag
    except Exception:
        pass


def play_menu_music():
    _play_music(_MENU_MUSIC_PATH, 1.0, 'menu')


def play_bgm_music():
    _play_music(_BGM_MUSIC_PATH, _BGM_VOLUME, 'bgm')


def duck_music():
    """Drop the music under the pause menu. _play_music won't reset the volume
    on the way back out (same tag = no-op), so resuming must unduck explicitly."""
    try:
        pygame.mixer.music.set_volume(_BGM_VOLUME * _PAUSE_DUCK)
    except Exception:
        pass


def unduck_music():
    try:
        pygame.mixer.music.set_volume(_BGM_VOLUME)
    except Exception:
        pass


def stop_music():
    global _current_music
    pygame.mixer.music.stop()
    _current_music = None


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

    def draw(self, surface, superman, events, camera, active_event=None, krypto=None):
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
            ("XRAY",        XRAY_C,      superman.xray_cd,  superman.XRAY_CD,  "X"),
        ]
        if krypto is not None:
            powers.append(("KRYPTO", SILVER, krypto.cd_ratio * krypto.CALL_CD, krypto.CALL_CD, "C"))
        total_w = len(powers) * (icon_sz + 8) - 8
        start_x = SCREEN_W // 2 - total_w // 2
        for i, (label, col, cd, max_cd, key) in enumerate(powers):
            ix = start_x + i * (icon_sz + 8)
            ratio = cd / max_cd if max_cd > 0 else 0
            cooldown_icon(surface, ix, icon_y, icon_sz, col, label, ratio, key)

        # Duration bars, for the powers that run for a period rather than firing
        # instantly. Position is derived from the row instead of hardcoded, so
        # adding or reordering a power can't leave a bar under the wrong icon --
        # which is exactly what happened to the index 4 here once XRAY took that
        # slot and pushed KRYPTO along. .index() raises if a label is renamed,
        # rather than silently drawing no bar at all.
        def duration_bar(label, pct, col):
            bx = start_x + [p[0] for p in powers].index(label) * (icon_sz + 8)
            pygame.draw.rect(surface, col, (bx, icon_y + icon_sz - 6, int(icon_sz * pct), 4))

        if superman.speed_remaining > 0:
            duration_bar("SPDS", superman.speed_remaining / superman.SPEED_DUR, CYAN)
        if superman.xray_remaining > 0:
            duration_bar("XRAY", superman.xray_remaining / superman.XRAY_DUR, XRAY_C)
        if krypto is not None and krypto.state == 'active':
            duration_bar("KRYPTO", krypto.timer / krypto.ACTIVE_DUR, SILVER)

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


# ─── EFFECT LAYER ─────────────────────────────────────────────────────────────
# One reused layer for the beam and cone. A fresh screen-sized SRCALPHA surface
# per effect per frame was the web build's worst cost -- alpha blitting has no
# SIMD path in wasm, so it scales with area, not with what's drawn.

_effect_layer = None


def _bbox(points, margin):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return pygame.Rect(int(min(xs)) - margin, int(min(ys)) - margin,
                       int(max(xs) - min(xs)) + margin * 2,
                       int(max(ys) - min(ys)) + margin * 2)


def _effect_region(points, margin):
    return _bbox(points, margin).clip(screen.get_rect())


def _effect_begin(region):
    """The shared layer, cleared over `region` only."""
    global _effect_layer
    if _effect_layer is None:
        _effect_layer = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    _effect_layer.fill((0, 0, 0, 0), region)
    return _effect_layer


def _effect_blit(layer, region):
    screen.blit(layer, region.topleft, region)


# ─── X-RAY WASH ───────────────────────────────────────────────────────────────
# Baked once and held for the whole run, same reasoning as ScreenFlash and
# _pause_dim: the tint and its scanlines never change, so there is nothing to
# redraw per frame and no full-screen SRCALPHA allocation to pay for. The
# surface is one line-gap taller than the screen so the scanlines can scroll by
# moving the blit's source rect rather than being redrawn.
#
# Both colours below are final pixel values, not increments: pygame's draw
# functions replace the pixel on an SRCALPHA surface instead of blending into
# it, so the scanline rows already carry the alpha they end up with.

_XRAY_LINE_GAP = 4
_xray_wash = pygame.Surface((SCREEN_W, SCREEN_H + _XRAY_LINE_GAP), pygame.SRCALPHA)
_xray_wash.fill((34, 6, 62, 118))
for _wy in range(0, SCREEN_H + _XRAY_LINE_GAP, _XRAY_LINE_GAP):
    pygame.draw.line(_xray_wash, (128, 62, 205, 165), (0, _wy), (SCREEN_W, _wy))


def draw_xray_wash(surface, phase):
    """One blit. `phase` scrolls the scanlines; nothing is re-rendered."""
    off = int(phase) % _XRAY_LINE_GAP
    surface.blit(_xray_wash, (0, 0), (0, off, SCREEN_W, SCREEN_H))


# ─── GAME ─────────────────────────────────────────────────────────────────────

class Game:
    MAX_EVENTS   = 7
    SPAWN_TIMER  = 9.0
    MIN_SPAWN_D  = 500

    def __init__(self):
        self.city   = City(seed=42)
        self.city.ensure_tiles()
        self.camera = Camera()
        self.pfs    = ParticleSystem()
        start_x, start_y = WORLD_W // 2, WORLD_H // 2
        self.superman = Superman(start_x, start_y)
        self.krypto = Krypto()
        self.camera.x = start_x - SCREEN_W / 2
        self.camera.y = start_y - SCREEN_H / 2
        self.events: list[BaseEvent] = []
        self.hud    = HUD()
        self.flash  = ScreenFlash()
        self.dialogue = DialogueManager()
        self._spawn_cd = 3.0
        self._active_event: BaseEvent | None = None
        self._notifications: list[tuple] = []  # (text, color, timer)
        self._wind_playing = False
        self._heat_playing = False
        self._freeze_playing = False
        self._shift_prev = False
        self._xray_prev = False
        self._c_prev = False

        # Mouse buttons are read as a level, not an edge, so the click that
        # started the game is still physically down for the first few frames
        # and would instantly fire heat vision. Mask any button already held at
        # construction until it has been released once.
        self._mouse_gate = [bool(b) for b in pygame.mouse.get_pressed()]

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
        mouse_buttons = list(pygame.mouse.get_pressed())
        for i, gated in enumerate(self._mouse_gate):
            if not gated:
                continue
            if mouse_buttons[i]:
                mouse_buttons[i] = False     # still held from the menu click
            else:
                self._mouse_gate[i] = False  # released: hand control back
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
        if snd_heat:
            if s.heat_firing and not self._heat_playing:
                snd_heat.play(loops=-1)
                self._heat_playing = True
            elif not s.heat_firing and self._heat_playing:
                snd_heat.stop()
                self._heat_playing = False

        # Freeze Breath: F or RMB (held for a continuous frost cone)
        s.freeze_active = bool(keys[pygame.K_f] or mouse_buttons[2])
        if s.freeze_active and s.freeze_cd <= 0:
            s.try_freeze(all_enemies, self.pfs)
        if snd_freeze:
            if s.freeze_active and not self._freeze_playing:
                snd_freeze.play(loops=-1)
                self._freeze_playing = True
            elif not s.freeze_active and self._freeze_playing:
                snd_freeze.stop()
                self._freeze_playing = False

        # Punch: Q
        if keys[pygame.K_q] and s.punch_cd <= 0:
            if s.try_punch(all_enemies, self.pfs):
                self.flash.trigger(YELLOW_S, 60)
                if snd_punch:
                    snd_punch.play()

        # Speed: Shift (toggle on/off)
        shift_down = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT])
        if shift_down and not self._shift_prev:
            if s.speed_remaining > 0:
                s.stop_speed()
            elif s.try_speed():
                self.pfs.sonic_boom(s.x, s.y)
                self.flash.trigger(CYAN, 70)
                if snd_sprint:
                    snd_sprint.play()
        self._shift_prev = shift_down

        # X-Ray Vision: X (one-shot burst, expires on its own)
        # Edge-detected like the shift toggle: keys is a level read, so without
        # this the sound would retrigger every frame X is held on cooldown.
        x_down = bool(keys[pygame.K_x])
        if x_down and not self._xray_prev:
            if s.try_xray():
                self.flash.trigger(XRAY_C, 50)
                if snd_xray:
                    snd_xray.play()
        self._xray_prev = x_down

        # Call Krypto: C (edge-triggered so a held key doesn't spam the notice)
        c_down = bool(keys[pygame.K_c])
        if c_down and not self._c_prev:
            if self.krypto.can_call():
                self.krypto.call()
            else:
                self.notify("Krypto is not listening to you right now", SILVER)
        self._c_prev = c_down

        s.update(dt, keys, mouse_world)

    def stop_sounds(self):
        if snd_wind:
            snd_wind.stop()
        if snd_heat:
            snd_heat.stop()
        if snd_freeze:
            snd_freeze.stop()
        if snd_xray:
            snd_xray.stop()
        self._wind_playing = False
        self._heat_playing = False
        self._freeze_playing = False

    def update(self, dt):
        s = self.superman
        if not s.alive:
            return

        self.handle_input(dt)
        self.camera.update(s.x, s.y, dt)
        self.pfs.update(dt)
        self.flash.update(dt)
        self.dialogue.update(dt)

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
            if ev.active and not getattr(ev, '_dialogue_intro_shown', False):
                if ev.event_type in LEX_EVENT_TYPES:
                    ev._dialogue_intro_shown = True
                    self.dialogue.trigger('lex', LEX_INTRO_LINES[ev.event_type], SUPERMAN_INTRO_LINES[ev.event_type])
                elif ev.event_type in METALLO_EVENT_TYPES:
                    ev._dialogue_intro_shown = True
                    self.dialogue.trigger('metallo', METALLO_INTRO_LINES[ev.event_type], SUPERMAN_VS_METALLO_INTRO_LINES[ev.event_type])
            if ev.complete and not hasattr(ev, '_rewarded'):
                ev._rewarded = True
                s.score += ev.score_value
                s.reputation = min(100, s.reputation + 8)
                self.notify(f"+{ev.score_value}  {ev.name}", GOLD)
                self.flash.trigger(YELLOW_S, 80)
                if ev.event_type in LEX_EVENT_TYPES:
                    self.dialogue.trigger('lex', LEX_DEFEAT_LINES[ev.event_type], SUPERMAN_DEFEAT_LINES[ev.event_type])
                elif ev.event_type in METALLO_EVENT_TYPES:
                    self.dialogue.trigger('metallo', METALLO_DEFEAT_LINES[ev.event_type], SUPERMAN_VS_METALLO_DEFEAT_LINES[ev.event_type])
            if ev.failed and not hasattr(ev, '_penalised'):
                ev._penalised = True
                s.reputation = max(0, s.reputation - 12)
                self.notify(f"FAILED: {ev.name}", RED)
                self.flash.trigger(RED, 100)
                if ev.event_type in LEX_FAIL_LINES:
                    self.dialogue.trigger('lex', LEX_FAIL_LINES[ev.event_type],
                                          SUPERMAN_FAIL_LINES[ev.event_type])

        # Remove finished events
        self.events = [e for e in self.events if not (e.complete or e.failed)]

        # Krypto companion
        all_enemies = []
        for ev in self.events:
            if hasattr(ev, 'enemies'):
                all_enemies.extend(ev.enemies)
        self.krypto.update(dt, s, all_enemies, self.pfs)

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
        self.city.draw(screen, self.camera)

        # X-ray wash: over the city, under everything else. Anything an event
        # only draws while revealed goes out in its normal draw() below and so
        # lands on top of the tint with no special-casing anywhere.
        if self.superman.xray_remaining > 0:
            draw_xray_wash(screen, self.superman.xray_remaining * 24.0)
            xsx = int(self.superman.x - self.camera.x)
            xsy = int(self.superman.y - self.camera.y)
            pygame.draw.circle(screen, XRAY_C, (xsx, xsy), Superman.XRAY_RANGE, 2)

        # Events world elements
        for ev in self.events:
            ev.draw(screen, self.camera)

        # Particles (behind Superman)
        self.pfs.draw(screen, self.camera)

        # Superman
        self.superman.draw(screen, self.camera)
        self.krypto.draw(screen, self.camera)

        # Heat vision beam (always exits the head, wherever the current pose puts it)
        if self.superman.heat_firing:
            sx = int(self.superman.head_pos[0] - self.camera.x)
            sy = int(self.superman.head_pos[1] - self.camera.y)
            ex = int(sx + math.cos(self.superman.facing) * Superman.HEAT_RANGE)
            ey = int(sy + math.sin(self.superman.facing) * Superman.HEAT_RANGE)
            # Beam (layered glow, drawn every frame the trigger is held for a solid long beam)
            region = _effect_region([(sx, sy), (ex, ey)], 10)   # 10 clears the 16px line
            beam_surf = _effect_begin(region)
            pygame.draw.line(beam_surf, (255, 255, 220, 90), (sx, sy), (ex, ey), 16)
            pygame.draw.line(beam_surf, (*FIRE_WARM, 160), (sx, sy), (ex, ey), 9)
            pygame.draw.line(beam_surf, (*FIRE_HOT, 230), (sx, sy), (ex, ey), 4)
            pygame.draw.line(beam_surf, (255, 255, 255, 255), (sx, sy), (ex, ey), 2)
            _effect_blit(beam_surf, region)

        # Freeze breath cone (drawn continuously while held, exits the head)
        if self.superman.freeze_active:
            fx = int(self.superman.head_pos[0] - self.camera.x)
            fy = int(self.superman.head_pos[1] - self.camera.y)
            angle = self.superman.facing
            pts = [(fx, fy)]
            reach = Superman.FREEZE_RANGE
            for da in range(-45, 46, 5):
                a = angle + math.radians(da)
                pts.append((fx + math.cos(a) * reach, fy + math.sin(a) * reach))
            region = _effect_region(pts, 4)   # 4 covers the 2px outline
            cone_surf = _effect_begin(region)
            if len(pts) > 2:
                pygame.draw.polygon(cone_surf, (*ICE, 90), pts)
                pygame.draw.polygon(cone_surf, (*CYAN, 60), pts, 2)
            _effect_blit(cone_surf, region)

        # Flash
        self.flash.draw(screen)

        # HUD
        self.hud.draw(screen, self.superman, self.events, self.camera, self._active_event, self.krypto)

        # Lex/Superman dialogue popups
        self.dialogue.draw(screen)

        # Notifications
        for i, (text, color, timer) in enumerate(reversed(self._notifications)):
            alpha = min(255, int(timer * 200))
            y = SCREEN_H // 2 - 60 - i * 32
            draw_text(screen, text, font_large, (*color[:3], alpha), SCREEN_W // 2, y, center=True)

    def can_use_heat_vision(self):
        return self.superman.heat_cd <= 0


# ─── MENU ─────────────────────────────────────────────────────────────────────

menu_video = MenuVideo(_TITLE_FRAMES_DIR, _TITLE_FRAME_FPS)

# Held for the whole run rather than rebuilt per frame — a full-screen SRCALPHA
# allocation every frame is the expensive path (see ScreenFlash).
_pause_dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
_pause_dim.fill((0, 0, 0, 160))

PAUSE_ITEMS = ("Resume", "Exit Game")


def draw_pause(selected):
    """Menu over a dimmed still of the game. The caller draws the world first
    and does the flip, so this only lays the dim and the text on top."""
    screen.blit(_pause_dim, (0, 0))
    t = pygame.time.get_ticks() / 1000
    alpha = int(180 + 75 * abs(math.sin(t * 2)))

    draw_text(screen, "PAUSED", font_xl, GOLD, SCREEN_W // 2, 220, center=True)
    for i, label in enumerate(PAUSE_ITEMS):
        y = 330 + i * 56
        if i == selected:
            draw_text(screen, f"> {label} <", font_large, (*GOLD[:3], alpha),
                      SCREEN_W // 2, y, center=True)
        else:
            draw_text(screen, label, font_large, LGRAY, SCREEN_W // 2, y, center=True)

    # Sits under the items rather than at the foot of the screen — the HUD's
    # power-icon row lives down there and the two overlap illegibly.
    draw_text(screen, "UP/DOWN: Select   ENTER: Confirm   ESC: Resume",
              font_small, LGRAY, SCREEN_W // 2, 470, center=True)


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
        bx2, by2 = SCREEN_W // 2 - 300, 250
        box_h = 300          # 8 rows at 36px from by2+16 end at ~by2+285
        bg = pygame.Surface((600, box_h), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 160))
        screen.blit(bg, (bx2, by2))
        pygame.draw.rect(screen, BLUE_S, (bx2, by2, 600, box_h), 2)
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
            draw_text(screen, key, font_small, YELLOW_S, bx2 + 20, y)
            draw_text(screen, desc, font_small, WHITE, bx2 + 220, y)

        # Start prompt
        draw_text(screen, "Press ENTER to begin", font_large, (*GOLD[:3], alpha), SCREEN_W // 2, 585, center=True)
        draw_text(screen, "ESC to quit", font_small, LGRAY, SCREEN_W // 2, 630, center=True)

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

def start_game():
    """Begin a run, freeing the ~390MB of title frames first."""
    menu_video.release()
    screen.fill(HUD_BG)
    draw_text(screen, "Preparing Metropolis...", font_large, LGRAY,
              SCREEN_W // 2, SCREEN_H // 2, center=True)
    pygame.display.flip()
    play_bgm_music()
    return Game()


async def main():
    state = 'menu'
    game: Game | None = None
    pause_sel = 0
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
                        game = start_game()
                        state = 'play'
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        return
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    # A click anywhere begins, which is what the title card's
                    # baked-in "PRESS START" has always implied.
                    game = start_game()
                    state = 'play'
            menu_video.update(dt)
            draw_menu()

        elif state == 'play':
            escape = any(e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE for e in events)
            if escape:
                # stop_sounds kills the looping wind/heat/freeze SFX, which would
                # otherwise drone on under the menu — polling stops, playback doesn't.
                # Their flags reset, so resuming re-triggers whatever is still held.
                game.stop_sounds()
                duck_music()
                pause_sel = 0
                state = 'pause'
            elif not game.superman.alive:
                game.stop_sounds()
                stop_music()
                if snd_gameover:
                    snd_gameover.play()
                state = 'gameover'
            else:
                game.update(dt)
                game.draw()
                pygame.display.flip()

        elif state == 'pause':
            # Not calling game.update() is the whole pause — every gameplay timer
            # is dt-threaded, so they all stop on their own.
            for event in events:
                if event.type != pygame.KEYDOWN:
                    continue
                if event.key == pygame.K_ESCAPE:
                    unduck_music()
                    state = 'play'
                elif event.key in (pygame.K_UP, pygame.K_w):
                    pause_sel = (pause_sel - 1) % len(PAUSE_ITEMS)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    pause_sel = (pause_sel + 1) % len(PAUSE_ITEMS)
                elif event.key == pygame.K_RETURN:
                    if PAUSE_ITEMS[pause_sel] == "Resume":
                        unduck_music()
                        state = 'play'
                    else:
                        unduck_music()
                        play_menu_music()
                        state = 'menu'
            if state == 'pause':
                game.draw()
                draw_pause(pause_sel)
                pygame.display.flip()

        elif state == 'gameover':
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        game = start_game()
                        state = 'play'
                    if event.key == pygame.K_ESCAPE:
                        play_menu_music()
                        state = 'menu'
            draw_game_over(game.superman.score, game.superman.reputation)

        await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())
