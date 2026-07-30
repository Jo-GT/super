# super

Superman: Guardian of Metropolis — a top-down action game built with pygame-ce.

**Play in your browser:** https://jo-gt.github.io/super/

## Requirements

- Python 3.10+
- Dependencies from `requirements.txt`

Install dependencies:

```
pip install -r requirements.txt
```

## Run on desktop

```
python main.py or py main.py
```

This opens a native window and runs the game directly.

## Run in a browser (via pygbag)

The game can also be built to WebAssembly and played in a browser tab.

```
pip install pygbag
python -m pygbag main.py
```

This builds the game and starts a local server, by default at:

```
http://localhost:8000
```

Open that URL in a browser to play. The first run takes longer since it downloads
the WebAssembly Python runtime; later runs are faster. If you change the code,
stop and re-run the `pygbag` command to rebuild — it does not hot-reload.

## Live deployment

Every push to `main` is built with pygbag and published to GitHub Pages by
`.github/workflows/deploy-pages.yml` — no manual build/copy step needed.

Live at: https://jo-gt.github.io/super/

## Controls

| Key                | Action                          |
|--------------------|----------------------------------|
| WASD / Arrow Keys  | Fly                              |
| Mouse              | Aim direction                    |
| Space / Left Click | Heat Vision (hold)                |
| F / Right Click    | Freeze Breath (hold)              |
| Q                  | Super Punch (dash to nearest enemy)|
| Shift              | Super Speed                      |
| ESC                | Pause (Resume / Exit Game)       |
