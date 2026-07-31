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

import audio
from audio import (BeamAudio, LoopingSound, duck_music, play_bgm_music,
                   play_menu_music, stop_music, unduck_music)
from constants import *
from hud import HUD, draw_text, font_large
from city import City
from particles import ParticleSystem
from entities import Superman, Krypto
from events import BaseEvent, spawn_random_event
from dialogue import DialogueManager
from screens import draw_game_over, draw_menu, draw_pause, menu_video, PAUSE_ITEMS

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption(TITLE)
clock = pygame.time.Clock()


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
        self.beam = BeamAudio()
        self.wind = LoopingSound(audio.snd_wind)
        self.freeze_loop = LoopingSound(audio.snd_freeze)
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
        self.beam.update(
            s.heat_firing, s.heat_firing and s.heat_beam_hits(all_enemies), dt)

        # Freeze Breath: F or RMB (held for a continuous frost cone)
        s.freeze_active = bool(keys[pygame.K_f] or mouse_buttons[2])
        if s.freeze_active and s.freeze_cd <= 0:
            s.try_freeze(all_enemies, self.pfs)
        self.freeze_loop.set(s.freeze_active)

        # Punch: Q
        if keys[pygame.K_q] and s.punch_cd <= 0:
            if s.try_punch(all_enemies, self.pfs):
                self.flash.trigger(YELLOW_S, 60)
                if audio.snd_punch:
                    audio.snd_punch.play()

        # Speed: Shift (toggle on/off)
        shift_down = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT])
        if shift_down and not self._shift_prev:
            if s.speed_remaining > 0:
                s.stop_speed()
            elif s.try_speed():
                self.pfs.sonic_boom(s.x, s.y)
                self.flash.trigger(CYAN, 70)
                if audio.snd_sprint:
                    audio.snd_sprint.play()
        self._shift_prev = shift_down

        # X-Ray Vision: X (one-shot burst, expires on its own)
        # Edge-detected like the shift toggle: keys is a level read, so without
        # this the sound would retrigger every frame X is held on cooldown.
        x_down = bool(keys[pygame.K_x])
        if x_down and not self._xray_prev:
            if s.try_xray():
                self.flash.trigger(XRAY_C, 50)
                if audio.snd_xray:
                    audio.snd_xray.play()
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
        """Silence everything the player is holding. Called on pause and death,
        so it has to cover every sound that can outlive a single frame."""
        self.wind.stop()
        self.freeze_loop.stop()
        self.beam.stop()
        if audio.snd_xray:
            audio.snd_xray.stop()

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
        self.wind.set(math.hypot(s.vx, s.vy) > 0.8)

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
            tx, ty = self.superman.heat_beam_target()   # same endpoint the hit test uses
            ex = int(tx - self.camera.x)
            ey = int(ty - self.camera.y)
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
            angle = self.superman.aim_angle()   # same angle the freeze test uses
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
            draw_menu(screen)

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
                if audio.snd_gameover:
                    audio.snd_gameover.play()
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
                draw_pause(screen, pause_sel)
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
            draw_game_over(screen, game.superman.score, game.superman.reputation)

        await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())
