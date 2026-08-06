"""Guards against a silently missing sound.

`load_sound` swallows every exception and returns None, and every call site
null-checks, so a renamed or corrupt .ogg degrades to silence with no error
anywhere - no crash, no log, nothing. That is the failure this file exists to
catch, and the reason it asserts on loaded Sound objects rather than on paths:
a path check would pass on a file that is present but unreadable.

It imports `audio` rather than `main`, so it needs no display and covers the
case where audio.py is loaded on its own - which is real, because main.py
imports it before calling pygame.init().
"""
from pathlib import Path

import pytest

import audio

SOUNDS = Path(audio.SOUNDS_DIR)

# Every module-level Sound in audio.py. If you add one, add it here.
REQUIRED_SOUNDS = [
    "snd_wind",
    "snd_sprint",
    "snd_freeze",
    "snd_punch",
    "snd_xray",
    "snd_gameover",
    "snd_gunshot",
    "snd_reload",
    "snd_heat_intro",
    "snd_heat_loop",
    "snd_heat_tail",
    "snd_heat_sizzle",
]

# Present on disk but deliberately never loaded at runtime. Asserted explicitly
# so that neither "everything in Sounds/ must load" nor "anything unloaded is
# dead" gets applied to it by mistake.
NOT_LOADED_AT_RUNTIME = {
    # Build input for tools/build_heatvision_clips.py, which cuts the three
    # runtime beam clips out of it.
    "heatvision.ogg",
}


@pytest.mark.parametrize("name", REQUIRED_SOUNDS)
def test_sound_loaded(name):
    assert hasattr(audio, name), f"audio.{name} is gone - was it renamed?"
    snd = getattr(audio, name)
    assert snd is not None, (
        f"audio.{name} is None: load_sound swallowed a failure. The file is "
        f"missing, misnamed or unreadable, or the mixer was not up when this "
        f"module was imported. Either way the game would run silently."
    )
    assert snd.get_length() > 0, f"audio.{name} loaded but is empty"


def test_music_tracks_exist():
    """Music goes through pygame.mixer.music, which takes a path, so these
    cannot be checked by loading a Sound."""
    for path in (audio.MENU_MUSIC_PATH, audio.BGM_MUSIC_PATH):
        assert Path(path).is_file(), f"missing music track: {path}"


@pytest.mark.parametrize("filename", sorted(NOT_LOADED_AT_RUNTIME))
def test_reserved_clips_still_present(filename):
    """These are not loaded, so nothing else would notice them disappearing."""
    assert (SOUNDS / filename).is_file(), (
        f"{filename} is missing. It is not loaded at runtime, so no other test "
        f"and no amount of playing the game would catch this."
    )


def test_no_orphaned_pygbag_twins():
    """An abandoned web-encoding scheme left *-pygbag.ogg files behind. Nothing
    produces or reads them; they only ever bloated local builds."""
    strays = sorted(p.name for p in SOUNDS.glob("*-pygbag.ogg"))
    assert not strays, f"orphaned pygbag twins are back: {strays}"
