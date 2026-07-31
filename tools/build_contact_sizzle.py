#!/usr/bin/env python3
"""Synthesise Sounds/heatvision-sizzle.ogg - the layer added while the beam is
actually burning something.

Synthesised rather than sampled so it is ours to ship, and so it can be tuned
against the beam instead of the other way round.

It is built to sit *on top of* heatvision-loop.ogg, which meant two constraints:

* It must not be another slice of heatvision.ogg. Anything cut from that clip
  correlates with the body loop and comb-filters when the two are summed - the
  same problem that ruled out crossfading to heatvision-contact.ogg. Noise from
  a different source is uncorrelated, so it simply adds.
* It sits above the beam in the spectrum (emphasis 1.5-9kHz, rolled off below)
  so it reads as extra bite rather than muddying the body, whose energy is
  centred around 4.6kHz with a strong low fundamental.

The loop is seamless by construction, not by crossfading: the noise is built as
a random-phase spectrum and inverse-transformed, so the result is inherently
periodic over its own length. The crackle impulses and the slow wobble are
wrapped/whole-cycle for the same reason. There is no seam to hide.

Run from anywhere; rewrites Sounds/heatvision-sizzle.ogg. Requires ffmpeg+numpy.

SEED is fixed so the audio is reproducible, but the file is not byte-reproducible
- see the note in build_heatvision_clips.py about ffmpeg's random Ogg serial.
"""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 48000
SOUNDS = Path(__file__).resolve().parent.parent / "Sounds"
OUT = SOUNDS / "heatvision-sizzle.ogg"

LENGTH = 1.0            # seconds; also the loop period
SEED = 20260731         # fixed so rebuilds are identical

LO_CUT = 1500.0         # roll off below this, to stay out of the beam's body
HI_CUT = 9000.0         # and above this, so it doesn't get hissy
CRACKLES = 48           # arcing impulses per second
CRACKLE_DECAY = 0.012   # seconds
CRACKLE_DEPTH = 1.8     # how much a crackle lifts the noise
WOBBLE_HZ = 3.0         # slow level movement, whole cycles over LENGTH
WOBBLE_DEPTH = 0.15
TARGET_RMS_DB = -16.0   # the body loop sits at about -10 dB
DRIVE = 4.0             # soft-clip the crackle peaks; without it the peak-to-RMS
                        # ratio forces the whole layer ~7dB quieter than target
PEAK_CEILING = 0.30     # so body+sizzle stays under full scale when they sum


def periodic_noise(n: int, rng: np.random.Generator) -> np.ndarray:
    """Band-shaped noise that is exactly periodic over n samples."""
    f = np.fft.rfftfreq(n, 1 / SR)
    with np.errstate(divide="ignore", invalid="ignore"):
        hp = (f / LO_CUT) ** 2 / (1 + (f / LO_CUT) ** 2)
    lp = 1 / (1 + (f / HI_CUT) ** 4)
    mag = np.nan_to_num(hp * lp)
    spec = mag * np.exp(2j * np.pi * rng.random(len(f)))
    spec[0] = 0
    return np.fft.irfft(spec, n)


def crackle_envelope(n: int, rng: np.random.Generator) -> np.ndarray:
    """Sparse decaying impulses, wrapped so the envelope is periodic too."""
    imp = np.zeros(n)
    d = int(CRACKLE_DECAY * SR)
    decay = np.exp(-np.arange(d) / (d / 3))
    for _ in range(int(CRACKLES * LENGTH)):
        p = int(rng.integers(0, n))
        imp[(p + np.arange(d)) % n] += decay * rng.uniform(0.5, 1.5)
    return 1.0 + CRACKLE_DEPTH * imp


def main() -> None:
    rng = np.random.default_rng(SEED)
    n = int(LENGTH * SR)

    x = periodic_noise(n, rng)
    x *= crackle_envelope(n, rng)
    cycles = np.arange(n) / SR * WOBBLE_HZ
    x *= 1 + WOBBLE_DEPTH * np.sin(2 * np.pi * cycles)

    x /= np.abs(x).max()
    x = np.tanh(x * DRIVE) / np.tanh(DRIVE)     # tame the crackle transients
    x *= 10 ** (TARGET_RMS_DB / 20) / np.sqrt((x ** 2).mean())
    peak = np.abs(x).max()
    if peak > PEAK_CEILING:      # the body loop peaks near -3 dBFS; leave room
        x *= PEAK_CEILING / peak

    stereo = np.stack([x, np.roll(x, n // 3)], axis=1)   # decorrelate the sides

    tmp = OUT.with_suffix(".tmp.wav")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(stereo, -1, 1) * 32767).astype("<i2").tobytes())
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(tmp),
         "-c:a", "libvorbis", "-q:a", "6", "-ar", str(SR), "-ac", "2", str(OUT)],
        check=True)
    tmp.unlink()

    rms = 20 * np.log10(np.sqrt((stereo.mean(axis=1) ** 2).mean()))
    print(f"  {OUT.name:<28} {LENGTH:.3f}s  RMS {rms:6.2f} dB  "
          f"peak {20*np.log10(np.abs(stereo).max()):6.2f} dBFS  "
          f"{OUT.stat().st_size:>7,} bytes")


if __name__ == "__main__":
    main()
