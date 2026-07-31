"""Shared test setup.

The SDL driver overrides have to be in place before pygame is imported anywhere,
because `main.py` calls `pygame.init()` and `pygame.display.set_mode()` at module
scope - importing it boots the game. Setting them here, at collection time, is
what lets the suite run with no display and no audio device.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# The game modules live at the repo root, not in a package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
