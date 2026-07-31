"""The in-game overlay, and the text/bar primitives it shares with the screens.

Fonts live here rather than in main.py because this module and screens.py are
the only things that draw text, and screens.py imports them from here.
"""
import math

import pygame

from constants import *

# Fonts are built at import time, and main.py imports this module before it
# calls pygame.init(), so the font subsystem has to be brought up here or every
# SysFont/Font call raises. Same reason audio.py inits the mixer itself.
# Guarded because pygame.init() will call it again.
if not pygame.font.get_init():
    pygame.font.init()

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


# ─── PRIMITIVES ───────────────────────────────────────────────────────────────

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


def cooldown_icon(surf, x, y, size, color, label, cd_ratio, key_label, cd_secs=None):
    bg = pygame.Surface((size, size), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 140))
    surf.blit(bg, (x, y))
    pygame.draw.rect(surf, color, (x, y, size, size), 2)
    draw_text(surf, label, font_tiny, color, x + size // 2, y + size // 2, center=True, shadow=True)
    if cd_ratio > 0:
        overlay = pygame.Surface((size, size), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(180 * cd_ratio)))
        surf.blit(overlay, (x, y))
        # Real seconds left, not the 0..1 ratio this used to print with an "s"
        # stuck on the end -- that read "0.5s" with nine seconds still to go.
        # Sub-second cooldowns (heat 0.08s, freeze 0.12s) are skipped; a number
        # that small only flickers.
        if cd_secs is not None and cd_secs >= 0.5:
            secs = f"{cd_secs:.0f}s" if cd_secs >= 10 else f"{cd_secs:.1f}s"
            draw_text(surf, secs, font_tiny, WHITE,
                      x + size // 2, y + size // 2 + 6, center=True, shadow=False)
    draw_text(surf, key_label, font_tiny, LGRAY, x + 2, y + size - 14, shadow=False)



# ─── HUD ──────────────────────────────────────────────────────────────────────

class HUD:
    MINIMAP_W = 200
    MINIMAP_H = 160
    MINIMAP_X = SCREEN_W - 210
    MINIMAP_Y = SCREEN_H - 170

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
        # One row per power: (label, colour, cooldown 0..1, seconds remaining,
        # key, duration 0..1 or None). Everything a power needs lives on its own
        # line, so adding one is a single entry and an icon can't drift out of
        # step with its own bar -- they used to be separate calls that repeated
        # the label and colour, and a hardcoded bar index went stale the moment
        # a power was inserted ahead of it. Cooldown ratio and seconds are both
        # carried because they genuinely differ: Krypto reads fully dimmed while
        # he's deployed, yet has no cooldown pending.
        powers = [
            ("HEAT\nVISN", FIRE_HOT, superman.heat_cd / superman.HEAT_CD,     superman.heat_cd,   "SPACE", None),
            ("FRZE\nBRTH", ICE,      superman.freeze_cd / superman.FREEZE_CD, superman.freeze_cd, "F",     None),
            ("SPNCH",      YELLOW_S, superman.punch_cd / superman.PUNCH_CD,   superman.punch_cd,  "Q",     None),
            ("SPDS",       CYAN,     superman.speed_cd / superman.SPEED_CD,   superman.speed_cd,  "SHIFT",
             superman.speed_remaining / superman.SPEED_DUR if superman.speed_remaining > 0 else None),
            ("XRAY",       XRAY_C,   superman.xray_cd / superman.XRAY_CD,     superman.xray_cd,   "X",
             superman.xray_remaining / superman.XRAY_DUR if superman.xray_remaining > 0 else None),
        ]
        # Defensive: the game always builds a Krypto, but the HUD should degrade
        # to a missing icon rather than crash if that ever stops being true.
        if krypto is not None:
            powers.append(("KRYPTO", SILVER, krypto.cd_ratio, krypto.call_cd, "C",
                           krypto.timer / krypto.ACTIVE_DUR if krypto.state == 'active' else None))

        total_w = len(powers) * (icon_sz + 8) - 8
        start_x = SCREEN_W // 2 - total_w // 2
        for i, (label, col, cd_ratio, cd_secs, key, dur) in enumerate(powers):
            ix = start_x + i * (icon_sz + 8)
            cooldown_icon(surface, ix, icon_y, icon_sz, col, label, cd_ratio, key, cd_secs)
            if dur is not None:
                # After its own icon, so the bar lies over the dim overlay --
                # the same order the separate bar pass produced.
                pygame.draw.rect(surface, col, (ix, icon_y + icon_sz - 6, int(icon_sz * dur), 4))

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


