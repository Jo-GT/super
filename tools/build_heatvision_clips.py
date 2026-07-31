#!/usr/bin/env python3
"""Cut Sounds/heatvision.ogg into the clips the beam sound is assembled from.

heatvision.ogg is a self-contained 4s one-shot: quiet charge-up, swell, blast,
fade-out. Heat vision is held down, though, so looping that whole clip replayed
the swell and the fade every 4 seconds instead of sustaining. Instead it is cut
into an intro, a body that loops, and a tail-off played on release.

Three intros are produced: "full" keeps the quiet charge-up, "swell" starts at
the swell, "punch" skips the ramp entirely and opens on the blast landing.
main.py picks between them with HEAT_INTRO_VARIANT.

Two details matter and are easy to get wrong:

* The loop's wrap-around is *phase-aligned* - the end was chosen by correlating
  against the start, so the two splice together coherently. An arbitrary loop
  point comb-filters, because the beam is tonal rather than noisy; the first
  attempt here dropped 9dB at the seam.
* Crossfade curves are picked per join. The wrap blends correlated, in-phase
  material, so it is linear (equal-power overshoots and clips). The intro-to-body
  handover happens at whatever moment a frame lands on, so its phase is
  arbitrary; that one gets a curve that is equal-power *against pygame's linear
  fade-in*, since the body is started with Sound.play(fade_ms=...).

Run from anywhere; rewrites the four Sounds/heatvision-*.ogg files in place.
Requires ffmpeg and numpy.
"""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 48000
SOUNDS = Path(__file__).resolve().parent.parent / "Sounds"
SRC = SOUNDS / "heatvision.ogg"

CHARGE_START = 0.000    # quiet charge-up begins
SWELL_START = 0.180     # ramp up to the blast begins
PUNCH_START = 0.360     # the blast lands, at full volume - no ramp before it
LOOP_START = 1.066      # see below; the intro runs to here
LOOP_END = 2.056330     # chosen by correlation against LOOP_START
CONTACT_END = 3.069000  # ditto, against LOOP_END
TAIL_START = 3.575      # the blast begins decaying
TAIL_END = 4.020

# LOOP_START is deliberately well past the start of the blast (~0.36s). The
# blast is not a smooth drone: its first 0.4s is the swell ringing out, 3-4dB
# hotter than the rest, and the stretch after it dips. Looping from there put
# that accent-then-drop at the top of every repeat, which is heard as the swell
# and tail-off coming back round even though the splice itself is seamless.
# 1.066-3.070s is the flat middle of the blast, and its loudest moment falls
# mid-loop rather than on the seam, so nothing draws the ear to the wrap.
#
# That middle is split in two at LOOP_END. The first half is the beam's idle
# hum; the second has a different character and is cut as a separate loop,
# heatvision-contact.ogg, held back for a beam-hitting-something sound. Nothing
# plays it yet. The two are contiguous, and each is independently phase-aligned
# so either can loop on its own.

HANDOVER = 0.120        # intro fade-out, mirrored by HEAT_LOOP_LEAD_IN in main.py
WRAP = 0.020            # loop wrap-around blend
TAIL_FADE_IN = 0.025    # mirrors the loop's fadeout on release
PUNCH_FADE_IN = 0.005   # just enough to stop the punch intro clicking


def decode(path: Path) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
        capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def encode(samples: np.ndarray, path: Path) -> None:
    tmp = path.with_suffix(".tmp.wav")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(tmp),
         "-c:a", "libvorbis", "-q:a", "6", "-ar", str(SR), "-ac", "2", str(path)],
        check=True)
    tmp.unlink()
    peak = 20 * np.log10(max(np.abs(samples).max(), 1e-9))
    print(f"  {path.name:<32} {len(samples)/SR:6.3f}s  peak {peak:6.2f} dBFS"
          f"  {path.stat().st_size:>7,} bytes")


def build_intro(x: np.ndarray, start: float, name: str, fade_in: float = 0.0) -> None:
    """Intro, running on into the blast and fading out over the handover.

    pygame fades the body in linearly, so this fades out as sqrt(1 - t**2):
    the two then sum to constant power for arbitrary relative phase.

    fade_in is for intros that open mid-waveform at volume rather than out of
    silence - a few ms, too short to hear as a fade but enough to stop the click.
    """
    clip = x[int(start * SR):int(LOOP_START * SR)].copy()
    if fade_in:
        f = int(fade_in * SR)
        clip[:f] *= np.linspace(0, 1, f, endpoint=False)[:, None]
    d = int(HANDOVER * SR)
    t = np.linspace(0, 1, d, endpoint=False)[:, None]
    clip[-d:] *= np.sqrt(1 - t ** 2)
    encode(clip, SOUNDS / name)


def build_loop(x: np.ndarray, start: float, end: float, name: str) -> None:
    """A seamless loop of [start, end).

    The last WRAP seconds are blended over the WRAP seconds leading into start,
    which keeps the phase alignment the endpoints were chosen for. Linear, not
    equal-power: the two are correlated and in phase, so they add coherently.
    """
    s, e, d = int(start * SR), int(end * SR), int(WRAP * SR)
    body = x[s - d:e - d].copy()
    wrap = x[e - d:e]                 # phase-aligned with body[:d]
    t = np.linspace(0, 1, d, endpoint=False)[:, None]
    body[:d] = wrap * (1 - t) + body[:d] * t
    encode(body, SOUNDS / name)


def build_tail(x: np.ndarray) -> None:
    """Tail-off. Starts mid-waveform at full blast, so it needs a fade-in or it
    clicks; the curve pairs with the linear fadeout main.py applies to the body."""
    clip = x[int(TAIL_START * SR):int(TAIL_END * SR)].copy()
    d = int(TAIL_FADE_IN * SR)
    t = np.linspace(0, 1, d, endpoint=False)[:, None]
    clip[:d] *= np.sqrt(1 - (1 - t) ** 2)
    encode(clip, SOUNDS / "heatvision-tail.ogg")


def main() -> None:
    x = decode(SRC)
    print(f"{SRC.name}: {len(x)/SR:.3f}s")
    build_intro(x, CHARGE_START, "heatvision-intro-full.ogg")
    build_intro(x, SWELL_START, "heatvision-intro-swell.ogg")
    build_intro(x, PUNCH_START, "heatvision-intro-punch.ogg", fade_in=PUNCH_FADE_IN)
    build_loop(x, LOOP_START, LOOP_END, "heatvision-loop.ogg")
    build_loop(x, LOOP_END, CONTACT_END, "heatvision-contact.ogg")
    build_tail(x)


if __name__ == "__main__":
    main()
