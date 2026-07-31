#!/usr/bin/env python3
"""Cut Sounds/heatvision.ogg into the clips the beam sound is assembled from.

heatvision.ogg is a self-contained 4s one-shot: quiet charge-up, swell, blast,
fade-out. Heat vision is held down, though, so looping that whole clip replayed
the swell and the fade every 4 seconds instead of sustaining. Instead it is cut
into an intro, a body that loops, and a tail-off played on release.

Two intros are produced: "full" keeps the quiet charge-up, "swell" starts at the
swell. main.py picks between them with HEAT_INTRO_VARIANT.

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
BLAST_START = 0.600     # first fully-sustained sample; also the loop start
LOOP_END = 2.637896     # chosen by correlation against BLAST_START
TAIL_START = 3.575      # the blast begins decaying
TAIL_END = 4.020

HANDOVER = 0.120        # intro fade-out, mirrored by HEAT_LOOP_LEAD_IN in main.py
WRAP = 0.020            # loop wrap-around blend
TAIL_FADE_IN = 0.025    # mirrors the loop's fadeout on release


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


def build_intro(x: np.ndarray, start: float, name: str) -> None:
    """Intro, running on into the blast and fading out over the handover.

    pygame fades the body in linearly, so this fades out as sqrt(1 - t**2):
    the two then sum to constant power for arbitrary relative phase.
    """
    clip = x[int(start * SR):int(BLAST_START * SR)].copy()
    d = int(HANDOVER * SR)
    t = np.linspace(0, 1, d, endpoint=False)[:, None]
    clip[-d:] *= np.sqrt(1 - t ** 2)
    encode(clip, SOUNDS / name)


def build_loop(x: np.ndarray) -> None:
    s, e, d = int(BLAST_START * SR), int(LOOP_END * SR), int(WRAP * SR)
    body = x[s - d:e - d].copy()
    wrap = x[e - d:e]                 # phase-aligned with body[:d]
    t = np.linspace(0, 1, d, endpoint=False)[:, None]
    body[:d] = wrap * (1 - t) + body[:d] * t
    encode(body, SOUNDS / "heatvision-loop.ogg")


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
    build_loop(x)
    build_tail(x)


if __name__ == "__main__":
    main()
