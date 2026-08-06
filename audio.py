"""Every sound the game makes: clip loading, music, and the beam's audio.

Split out of main.py so the beam sequencing can be reasoned about (and tested)
without a display attached. Nothing here draws or reads input.

One caveat that shapes every call site: `load_sound` returns None on failure
rather than raising, because a missing sound should not stop the game booting.
That means a renamed or corrupt file degrades to silence with no error anywhere,
which is exactly the kind of bug nobody notices. tests/test_assets.py exists to
catch it; if you add a Sound here, add it to REQUIRED_SOUNDS there too.
"""
import os

import pygame

SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Sounds")

# The clips below are loaded at import time, and main.py imports this module
# before it calls pygame.init(). So the mixer has to be brought up here: without
# it every Sound() raises, load_sound hands back None, and the whole game runs
# silently with nothing logged. Guarded because pygame.init() will call it again.
#
# buffer is explicit because SDL2's default (512 samples, ~12ms at 44100Hz) is
# sized for a native audio thread with real OS scheduling. pygbag's web build
# has no such thread -- audio, rendering and Python all take turns on the
# browser's single main thread -- so a frame running a touch long starves the
# mixer and the underrun pops as a click. Native playback has enough margin
# that this never mattered there; on the web build it's audible, especially on
# the streamed mixer.music track. A bigger buffer trades a little latency
# (~46ms at 2048) for headroom against that jitter.
if not pygame.mixer.get_init():
    try:
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
    except pygame.error:
        pass


def load_sound(filename):
    """Load a clip, or None if it is missing or unreadable. See module docstring."""
    try:
        return pygame.mixer.Sound(os.path.join(SOUNDS_DIR, filename))
    except Exception:
        return None


# ─── CLIPS ────────────────────────────────────────────────────────────────────

snd_wind      = load_sound("flying wind noise.ogg")
snd_sprint    = load_sound("beginsprint.ogg")
snd_freeze    = load_sound("freeze breath.ogg")
snd_punch     = load_sound("punch.ogg")
snd_xray      = load_sound("xrayvision.ogg")
snd_gameover  = load_sound("GameOver.ogg")
snd_gunshot   = load_sound("gunshot.ogg")
snd_reload    = load_sound("gun reload.ogg")
snd_ricochet  = load_sound("bullet ricochet.ogg")

# Heat vision is held down, so its sound has to sustain for as long as the
# player likes. The original heatvision.ogg is a self-contained 4s one-shot —
# charge-up, swell, blast, fade — so looping it whole replayed the swell and
# the fade every 4 seconds instead of holding a steady beam. It is split into
# three clips: an intro, a body that loops seamlessly, and a tail-off played
# on release. The intro opens on the blast already at full volume; two gentler
# starts were tried and rejected, and tools/build_heatvision_clips.py still
# carries their cut points if either is ever wanted back.
snd_heat_intro  = load_sound("heatvision-intro.ogg")
snd_heat_loop   = load_sound("heatvision-loop.ogg")
snd_heat_tail   = load_sound("heatvision-tail.ogg")
snd_heat_sizzle = load_sound("heatvision-sizzle.ogg")

# The intro runs on into the blast and fades out over its final LOOP_LEAD_IN
# seconds, so the looping body is faded in underneath it over the same window
# rather than stacking at full volume (which clipped). The window is also wide
# enough to absorb frame-timing jitter — the handover can only ever land late,
# and landing late just shortens the crossfade.
LOOP_LEAD_IN = 0.12

# The sizzle layers on top of the body loop while the beam is burning something,
# rather than replacing it. Swapping the body out would mean crossfading between
# two slices of the same tonal clip at an arbitrary moment, which comb-filters
# badly (up to 4.5dB swings depending where the switch lands); the sizzle is
# uncorrelated noise, so it just adds.
#
# Contact is held briefly after the last hit. Without that, sweeping the beam
# across enemies flickers the layer on and off several times a second.
CONTACT_HOLD = 0.20     # seconds to keep the sizzle up after the last hit
SIZZLE_FADE = 60        # ms, in and out
SIZZLE_VOLUME = 0.75    # the clip is built hot; balance it against the beam
                        # here rather than baking it in, so the asset keeps its
                        # headroom and this stays easy to nudge.

RELEASE_FADE = 25       # ms; the body loops at full volume, so cutting it dead
                        # mid-waveform clicks.

if snd_heat_sizzle:
    snd_heat_sizzle.set_volume(SIZZLE_VOLUME)


# ─── MUSIC ────────────────────────────────────────────────────────────────────

MENU_MUSIC_PATH = os.path.join(SOUNDS_DIR, "mainmenutheme.ogg")
BGM_MUSIC_PATH  = os.path.join(SOUNDS_DIR, "MainBGM.ogg")
_BGM_VOLUME     = 0.55
_PAUSE_DUCK     = 0.2   # fraction of normal volume while the pause menu is up
_current_music = None   # 'menu' | 'bgm' | None


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
    _play_music(MENU_MUSIC_PATH, 1.0, 'menu')


def play_bgm_music():
    _play_music(BGM_MUSIC_PATH, _BGM_VOLUME, 'bgm')


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


# ─── LOOPING SOUNDS ───────────────────────────────────────────────────────────

class LoopingSound:
    """A held sound that starts once and stops once.

    Both the flight wind and the freeze breath are driven by a level read that
    is true on every frame the condition holds, so each needs a latch to avoid
    retriggering 60 times a second. They had one each, spelled out inline.
    """

    def __init__(self, sound):
        self.sound = sound
        self.playing = False

    def set(self, should_play):
        if self.sound is None:
            return
        if should_play and not self.playing:
            self.sound.play(loops=-1)
            self.playing = True
        elif not should_play and self.playing:
            self.sound.stop()
            self.playing = False

    def stop(self):
        if self.sound is not None:
            self.sound.stop()
        self.playing = False


# ─── HEAT VISION BEAM ─────────────────────────────────────────────────────────

class BeamAudio:
    """Sequences the beam's four clips: intro, looping body, tail-off, sizzle.

    The trigger is a level read, so this tracks how far through the sequence we
    are rather than a single is-it-playing flag. `phase` is None, 'intro' or
    'loop'; the sizzle rides on top of whichever is playing.
    """

    def __init__(self):
        self.phase = None        # None | 'intro' | 'loop'
        self._t = 0.0            # seconds into the intro clip
        self._contact_t = 0.0    # time left on the contact hold
        self.sizzling = False

    def update(self, firing, contact, dt):
        if snd_heat_loop is None:
            return

        if not firing:
            if self.phase is not None:
                # Only tail off from a blast the player actually heard; an
                # intro cut short is its own ending.
                self.stop(tail=self.phase == 'loop')
            return

        self._update_sizzle(contact, dt)

        if self.phase is None:
            if snd_heat_intro:
                snd_heat_intro.play()
                self.phase = 'intro'
                self._t = 0.0
            else:
                snd_heat_loop.play(loops=-1)
                self.phase = 'loop'
        elif self.phase == 'intro':
            self._t += dt
            if self._t >= snd_heat_intro.get_length() - LOOP_LEAD_IN:
                snd_heat_loop.play(loops=-1, fade_ms=int(LOOP_LEAD_IN * 1000))
                self.phase = 'loop'

    def _update_sizzle(self, contact, dt):
        """Fade the burning-something layer in and out under the beam."""
        if snd_heat_sizzle is None:
            return
        if contact:
            self._contact_t = CONTACT_HOLD
        else:
            self._contact_t = max(0.0, self._contact_t - dt)

        want = self._contact_t > 0
        if want and not self.sizzling:
            snd_heat_sizzle.play(loops=-1, fade_ms=SIZZLE_FADE)
            self.sizzling = True
        elif not want and self.sizzling:
            snd_heat_sizzle.fadeout(SIZZLE_FADE)
            self.sizzling = False

    def stop(self, tail=False):
        """Release the beam. With tail=True it fades into the tail-off clip;
        without, everything cuts immediately (pause, death)."""
        for snd in (snd_heat_intro, snd_heat_loop):
            if not snd:
                continue
            if tail:
                snd.fadeout(RELEASE_FADE)
            else:
                snd.stop()
        if snd_heat_tail:
            if tail:
                snd_heat_tail.play()
            else:
                snd_heat_tail.stop()
        if snd_heat_sizzle:
            if tail:
                snd_heat_sizzle.fadeout(SIZZLE_FADE)
            else:
                snd_heat_sizzle.stop()
        self.phase = None
        self._t = 0.0
        self._contact_t = 0.0
        self.sizzling = False
