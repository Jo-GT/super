import os
import pygame
from constants import *

_SPRITES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites")

# Keep in sync with main.HUD.MINIMAP_Y (= SCREEN_H - 170). Superman's popup is
# anchored just above this line so it never overlaps the minimap box, which
# occupies the screen's literal bottom-right corner.
_MINIMAP_TOP = SCREEN_H - 170


def _load_sprite(path, size):
    try:
        img = pygame.image.load(path).convert_alpha()
        return pygame.transform.smoothscale(img, size)
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


class DialogueBox:
    """One side's talking-portrait + speech bubble."""
    DISPLAY_TIME = 4.0
    FADE_TIME = 0.6
    MARGIN = 16
    BUBBLE_W = 260
    BUBBLE_H = 110
    GAP = 14

    def __init__(self, sprite_path, sprite_size, side, font, name, name_color):
        self.sprite = _load_sprite(sprite_path, sprite_size)
        self.sprite_size = sprite_size
        self.side = side  # 'left' (Lex, bottom-left) or 'right' (Superman, above minimap)
        self.font = font
        self.name = name
        self.name_color = name_color
        self.text = ""
        self.timer = 0.0
        self.portrait_rect, self.bubble_rect = self._compute_rects()

    def _compute_rects(self):
        w, h = self.sprite_size
        if self.side == 'left':
            portrait = pygame.Rect(self.MARGIN, SCREEN_H - self.MARGIN - h, w, h)
            bubble_bottom = SCREEN_H - 130 - 8  # 8px above HUD's event banner top
            bubble = pygame.Rect(portrait.right + self.GAP, bubble_bottom - self.BUBBLE_H,
                                  self.BUBBLE_W, self.BUBBLE_H)
        else:
            portrait_bottom = _MINIMAP_TOP - 8  # 8px above the minimap
            portrait = pygame.Rect(SCREEN_W - self.MARGIN - w, portrait_bottom - h, w, h)
            bubble = pygame.Rect(portrait.left - self.GAP - self.BUBBLE_W, portrait_bottom - self.BUBBLE_H,
                                  self.BUBBLE_W, self.BUBBLE_H)
        return portrait, bubble

    def show(self, text):
        self.text = text
        self.timer = self.DISPLAY_TIME

    def update(self, dt):
        self.timer = max(0.0, self.timer - dt)

    @property
    def visible(self):
        return self.timer > 0

    def draw(self, surface):
        if not self.visible:
            return
        alpha = 255 if self.timer > self.FADE_TIME else int(255 * (self.timer / self.FADE_TIME))

        # Portrait
        pr = self.portrait_rect
        if self.sprite is not None:
            img = self.sprite
            if alpha < 255:
                img = img.copy()
                img.set_alpha(alpha)
            surface.blit(img, pr)
        else:
            fallback = pygame.Surface(pr.size, pygame.SRCALPHA)
            fallback.fill((*self.name_color[:3], min(200, alpha)))
            surface.blit(fallback, pr)

        # Bubble
        br = self.bubble_rect
        bs = pygame.Surface(br.size, pygame.SRCALPHA)
        bs.fill((0, 0, 0, int(170 * alpha / 255)))
        pygame.draw.rect(bs, (*self.name_color[:3], alpha), bs.get_rect(), 2, border_radius=10)
        surface.blit(bs, br)

        # Tail (small triangle connecting bubble to portrait)
        if self.side == 'left':
            tail = [(br.left, br.bottom - 30), (br.left, br.bottom - 10), (pr.right, pr.top + 20)]
        else:
            tail = [(br.right, br.bottom - 30), (br.right, br.bottom - 10), (pr.left, pr.top + 20)]
        pygame.draw.polygon(surface, (*self.name_color[:3], alpha), tail)

        # Name + wrapped text
        name_surf = self.font.render(self.name, True, self.name_color[:3])
        surface.blit(name_surf, (br.x + 10, br.y + 8))
        for i, line in enumerate(_wrap_text(self.text, self.font, br.w - 20)):
            line_surf = self.font.render(line, True, (255, 255, 255))
            surface.blit(line_surf, (br.x + 10, br.y + 30 + i * 20))


class DialogueManager:
    def __init__(self, font):
        self.lex = DialogueBox(
            os.path.join(_SPRITES_DIR, "lexcorp", "lex_regular.png"), (72, 145),
            'left', font, "LEX LUTHOR", GOLD)
        self.superman = DialogueBox(
            os.path.join(_SPRITES_DIR, "superman", "superman standing flight.png"), (70, 115),
            'right', font, "SUPERMAN", BLUE_S)

    def trigger(self, lex_line, superman_line):
        self.lex.show(lex_line)
        self.superman.show(superman_line)

    def update(self, dt):
        self.lex.update(dt)
        self.superman.update(dt)

    def draw(self, surface):
        self.lex.draw(surface)
        self.superman.draw(surface)
