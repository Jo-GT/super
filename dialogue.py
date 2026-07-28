import os
import pygame
from constants import *

_SPRITES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites")

BAR_H = 170
PORTRAIT_H = 130
PORTRAIT_MARGIN = 16

_NAME_FONT = None
_TEXT_FONT = None


def _ensure_fonts():
    # Deferred until first use: pygame.font isn't initialized yet when this
    # module is imported (main.py imports it before calling pygame.init()).
    global _NAME_FONT, _TEXT_FONT
    if _NAME_FONT is None:
        try:
            _NAME_FONT = pygame.font.SysFont("Arial", 20, bold=True)
            _TEXT_FONT = pygame.font.SysFont("Arial", 24, bold=True)
        except Exception:
            _NAME_FONT = pygame.font.Font(None, 20)
            _TEXT_FONT = pygame.font.Font(None, 24)


def _load_face_sprite(path, crop_frac, height):
    """Load an image and crop to the face/head region (crop_frac as
    (x0, y0, x1, y1) fractions of the source image), scaled to a fixed
    height while preserving the crop's aspect ratio."""
    try:
        img = pygame.image.load(path).convert_alpha()
        w, h = img.get_size()
        x0, y0, x1, y1 = crop_frac
        rect = pygame.Rect(int(x0 * w), int(y0 * h), int((x1 - x0) * w), int((y1 - y0) * h))
        face = img.subsurface(rect).copy()
        aspect = face.get_width() / face.get_height()
        return pygame.transform.smoothscale(face, (int(height * aspect), height))
    except Exception:
        return None


def _wrap_text(text, font, max_width):
    words = text.split(' ')
    lines, cur = [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if font.size(trial)[0] > max_width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


class Speaker:
    """One side's talking-face portrait + line of text, drawn inside the
    shared bottom dialogue bar."""
    DISPLAY_TIME = 4.0
    FADE_TIME = 0.6

    def __init__(self, sprite_path, crop_frac, side, name, name_color):
        self.sprite = _load_face_sprite(sprite_path, crop_frac, PORTRAIT_H)
        self.side = side  # 'left' (Lex) or 'right' (Superman)
        self.name = name
        self.name_color = name_color
        self.text = ""
        self.timer = 0.0

    def show(self, text):
        self.text = text
        self.timer = self.DISPLAY_TIME

    def update(self, dt):
        self.timer = max(0.0, self.timer - dt)

    @property
    def visible(self):
        return self.timer > 0

    @property
    def alpha(self):
        return 255 if self.timer > self.FADE_TIME else int(255 * (self.timer / self.FADE_TIME))

    def draw(self, surface, bar_y):
        if not self.visible:
            return
        alpha = self.alpha
        portrait_w = self.sprite.get_width() if self.sprite is not None else PORTRAIT_H
        py = bar_y + (BAR_H - PORTRAIT_H) // 2

        if self.side == 'left':
            px = PORTRAIT_MARGIN
            text_x0 = px + portrait_w + 22
            text_x1 = SCREEN_W // 2 - 22
        else:
            px = SCREEN_W - PORTRAIT_MARGIN - portrait_w
            text_x0 = SCREEN_W // 2 + 22
            text_x1 = px - 22

        # Portrait (zoomed face crop)
        if self.sprite is not None:
            img = self.sprite
            if alpha < 255:
                img = img.copy()
                img.set_alpha(alpha)
            frame = pygame.Rect(px - 4, py - 4, portrait_w + 8, PORTRAIT_H + 8)
            pygame.draw.rect(surface, (*self.name_color[:3], alpha), frame, 3, border_radius=8)
            surface.blit(img, (px, py))
        else:
            fallback = pygame.Surface((portrait_w, PORTRAIT_H), pygame.SRCALPHA)
            fallback.fill((*self.name_color[:3], min(200, alpha)))
            surface.blit(fallback, (px, py))

        # Name tag + wrapped dialogue text
        name_surf = _NAME_FONT.render(self.name, True, self.name_color[:3])
        name_surf.set_alpha(alpha)
        surface.blit(name_surf, (text_x0, bar_y + 18))
        for i, line in enumerate(_wrap_text(self.text, _TEXT_FONT, text_x1 - text_x0)):
            line_surf = _TEXT_FONT.render(line, True, (255, 255, 255))
            line_surf.set_alpha(alpha)
            surface.blit(line_surf, (text_x0, bar_y + 48 + i * 28))


class DialogueManager:
    def __init__(self):
        _ensure_fonts()
        self.lex = Speaker(
            os.path.join(_SPRITES_DIR, "lexcorp", "lex_regular.png"),
            (0.14, 0.0, 0.86, 0.28), 'left', "LEX LUTHOR", GOLD)
        self.superman = Speaker(
            os.path.join(_SPRITES_DIR, "superman", "superman standing flight.png"),
            (0.34, 0.02, 0.82, 0.27), 'right', "SUPERMAN", BLUE_S)

    def trigger(self, lex_line, superman_line):
        self.lex.show(lex_line)
        self.superman.show(superman_line)

    def update(self, dt):
        self.lex.update(dt)
        self.superman.update(dt)

    @property
    def visible(self):
        return self.lex.visible or self.superman.visible

    def draw(self, surface):
        if not self.visible:
            return
        bar_y = SCREEN_H - BAR_H
        alpha = max(self.lex.alpha if self.lex.visible else 0,
                    self.superman.alpha if self.superman.visible else 0)

        bg = pygame.Surface((SCREEN_W, BAR_H), pygame.SRCALPHA)
        bg.fill((6, 6, 14, int(210 * alpha / 255)))
        pygame.draw.line(bg, (*WHITE, int(120 * alpha / 255)), (0, 0), (SCREEN_W, 0), 2)
        pygame.draw.line(bg, (*LGRAY, int(90 * alpha / 255)),
                          (SCREEN_W // 2, 14), (SCREEN_W // 2, BAR_H - 14), 1)
        surface.blit(bg, (0, bar_y))

        self.lex.draw(surface, bar_y)
        self.superman.draw(surface, bar_y)
