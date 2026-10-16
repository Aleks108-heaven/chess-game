# ♔ Chess Game ♚

[![CI](https://github.com/Aleks108-heaven/chess-game/actions/workflows/ci.yml/badge.svg)](https://github.com/Aleks108-heaven/chess-game/actions/workflows/ci.yml)

A Python chess game with a graphical interface built using Pygame. Play against a computer opponent at **five levels, from Junior to Senior**, or challenge a friend in 2-player mode, on a wood-themed board that switches between a flat 2D view and a tilted pseudo-3D perspective view.

## Download

Windows users can grab the standalone app (no Python needed) from the [Releases page](https://github.com/Aleks108-heaven/chess-game/releases):

- **Installer:** run `ChessGame-v<version>-windows-x64-setup.exe`. It installs for your user account (no administrator prompt), adds a Start Menu entry and can be removed from *Apps > Installed apps*.
- **Portable:** unzip `ChessGame-v<version>-windows-x64.zip` and run `ChessGame.exe`.

The builds are **not code-signed**, so Windows may show a SmartScreen or application-control warning; verify the download against `SHA256SUMS.txt` from the release.

## Features

- **Play vs the computer, Junior to Senior** - five levels chosen on the start screen (see [AI levels](#ai-levels))
- **2 Player Mode** - Play against a friend locally
- **2D / 3D View Toggle** - Switch anytime between a flat board and a tilted perspective view with depth-scaled, standing pieces
- **Wood-Themed Graphics** - Procedural wood-grain squares, a beveled wooden frame, embossed/shaded pieces with grounding shadows, and a custom window/taskbar icon
- **Drag-and-Drop & Click-to-Move** - Move pieces either way (2D view); click-to-move only in 3D view
- **Move Animation** - Smooth eased piece movement (2D view)
- **Pawn Promotion** - Interactive choice dialog for Queen/Rook/Bishop/Knight
- **Move History & Material Tracking** - Algebraic notation log and captured-piece/material-advantage display
- **Visual Highlights** - Valid moves, last move, check warnings, and selected square
- **Board Flip** - Flips automatically when you play Black, or on demand with `F`
- **Procedural Sound Effects** - Move, capture, check, castle, promotion, and game-over sounds generated at runtime (no audio files); mute with `M`
- **Undo Support** - Take back moves with a single keypress
- **Accessible by design** - full keyboard control of menus, visible focus, contrast checked against WCAG 2.x by the test suite, and a reduced-motion switch

## AI levels

Each level is defined by what the engine is *allowed* to do, not by a rating claim:

| Level | Looks ahead | Think-time cap | Follows captures | Deliberate slips | Opening book |
| ----- | ----------- | -------------- | ---------------- | ---------------- | ------------ |
| **Junior** | 1 move | 1 s | no (hangs pieces) | frequent | no |
| **Associate** | 2 moves | 1.5 s | 2 plies | often | yes |
| **Mid-level** *(default)* | 3 moves | 2 s | 6 plies | sometimes | yes |
| **Advanced** | up to 5 moves | 3 s | fully | never (searches less deeply than Senior) | yes |
| **Senior** | up to 8 moves | 5 s | fully | never | yes |

Depth is the binding limit on typical hardware and the time cap is a safety net, so the levels stay distinct on faster and slower machines. In practice, measured on the development machine across five varied positions, Mid-level reaches its 3 moves in 0-1.2 s and Senior reaches 7-8 moves in 1-5 s. Every level always plays a mate in one when it sees it, and never talks itself out of a mate it has found.

**How the ladder was checked.** `tools/ladder_match.py` plays levels against each other with alternating colours. On the development machine (Python 3.15, one search thread per game), results for the stronger side were:

| Match | Result |
| ----- | ------ |
| Junior vs a random mover | 12 wins, 0 draws, 0 losses |
| Associate vs Junior | 12 - 0 - 0 |
| Mid-level vs Associate | 12 - 0 - 0 |
| Advanced vs Mid-level | 10 - 0 - 0 |
| Senior vs Advanced | 8 - 1 - 1 |

These are self-play results: they show the ladder is strictly ordered, **not** how strong any level is against people, and they are not Elo ratings. Time-capped levels reach different depths on different hardware.

**Under the hood** (`ai/` package): a fast mailbox board with incremental Zobrist hashing and evaluation; iterative-deepening alpha-beta with a transposition table, quiescence search, null-move pruning, late-move reductions and killer/history move ordering; a tapered piece-square evaluation with pawn structure, bishop pair and an endgame "mop-up" term; and a position-keyed opening book. The move generator is verified against the published perft node counts for six standard test positions and cross-checked move-for-move against the game's own `ChessEngine`.

## Installation

1. Make sure you have Python 3.11 or newer installed
2. Create and activate a virtual environment (recommended):

   ```bash
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   ```

3. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   > **Note:** this project depends on [`pygame-ce`](https://pyga.me/) (the actively-maintained Community Edition fork of Pygame), since it ships wheels for newer Python versions where upstream `pygame` may not yet have a prebuilt wheel. It's a drop-in replacement — code still does `import pygame`.

## Usage

Run the game:

```bash
python main.py
```

Other options: `python main.py --version`, and `python main.py --self-test` (draws every screen and plays one turn against the computer headlessly, then exits with status 0 on success).

## Controls

| Key                         | Action                                                       |
| --------------------------- | ------------------------------------------------------------ |
| `Z`                         | Undo move (disabled while the computer is thinking)          |
| `R`                         | New game (asks to confirm if a game is in progress)          |
| `V`                         | Toggle 2D / 3D view                                          |
| `F`                         | Flip the board                                               |
| `M`                         | Mute / unmute sound                                          |
| `ESC`                       | Open menu (in the menu: go back, or resume the current game) |
| `Up` / `Down` / `Tab`       | Move focus in menus                                          |
| `Enter` / `Space`           | Activate the focused menu item                               |
| `Q` `R` `B` `N`             | Choose a promotion piece                                     |
| Mouse wheel / `PgUp` `PgDn` | Scroll the move history                                      |

The **View: 2D/3D** button in the top-right of the side panel switches the board view at any time during a game. Set the environment variable `CHESS_REDUCED_MOTION=1` to turn off the move animation and the pulsing "thinking" indicator.

## How to Play

1. Launch the game and choose **Play vs Computer** or **2 Players**
2. Against the computer, choose your colour, then your opponent (Junior to Senior)
3. Click a piece (or drag it, in 2D view) - valid moves will be highlighted
4. Click a highlighted square to move the piece
5. The game ends on checkmate, stalemate, or one of the standard draw conditions (fifty-move rule, threefold repetition, insufficient material)

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest -q                  # whole suite (about 45 s)
python -m pytest -q -m "not slow"    # skip the endgame and random-game checks
python tools/ladder_match.py --ladder --games 10    # re-check the level ladder
```

The suite covers the move generator (published perft counts, FEN, castling/en passant/promotion rules), a differential check against `ChessEngine`, the AI contract (every level returns a legal move, finds mates, takes a free queen, respects time limits and cancellation, never mutates the engine), the opening book, the design-token contrast ratios, and the UI flows (menus, level picker, input routing, the AI hand-off, and frame rate while Senior is searching). The AI tests in `tests/test_ai.py` are numbered `AI-01`... with a priority, in the style of an interface test plan.

### Building a release

```bash
pip install -r requirements-build.txt
python tools/build_release.py        # tests, PyInstaller build, self-test, zip, setup installer, SHA-256
```

Output lands in `dist/`. The build refuses to produce an artifact unless the test suite passes and the packaged program passes its own `--self-test`; the installer is then installed into a temporary folder, self-tested and uninstalled. The installer needs [Inno Setup 6](https://jrsoftware.org/isinfo.php) (`winget install JRSoftware.InnoSetup`); pass `--no-installer` to build the zip only. The version comes from `version.py`; add an entry to `CHANGELOG.md` for each release.

## Project Structure

```text
├── main.py              # Game UI, rendering (2D + pseudo-3D), input handling (Pygame), CLI
├── theme.py             # Design tokens (colours, spacing, type scale) + WCAG contrast helpers
├── chess_engine.py      # Chess rules for the UI: move generation and game state
├── chess_ai.py          # The computer opponent (public API, level handling)
├── ai/                  # Search internals
│   ├── board.py         #   fast mailbox board, make/unmake, FEN, perft
│   ├── evaluation.py    #   tapered evaluation, pawn structure, mop-up
│   ├── search.py        #   iterative-deepening alpha-beta
│   ├── levels.py        #   the Junior -> Senior ladder
│   └── book.py          #   opening book
├── tests/               # pytest suite
├── tools/               # ladder_match.py, build_release.py, make_icon.py
├── installer/           # Inno Setup script for the Windows installer
├── assets/icon.ico      # executable icon (rendered by tools/make_icon.py)
├── version.py           # release version
├── requirements*.txt    # runtime / dev / build dependencies (pinned)
└── CHANGELOG.md
```

## Requirements

- Python 3.11+
- `pygame-ce` (see `requirements.txt`; dev and build extras in `requirements-dev.txt` / `requirements-build.txt`)

## Troubleshooting

**`can't open file '...\main.py': [Errno 2] No such file or directory`**
Your terminal isn't in the project folder. `cd` into it first, then run the game:

```bash
cd path\to\chess-game
python main.py
```

**`ModuleNotFoundError: No module named 'pygame'`**
You're running a Python interpreter that doesn't have the dependency installed — usually because the virtual environment isn't activated (or doesn't exist yet). Fix:

```bash
cd path\to\chess-game
python -m venv .venv          # only if .venv doesn't exist yet
.venv\Scripts\activate         # Windows
pip install -r requirements.txt
python main.py
```

**`ModuleNotFoundError: No module named 'pygame.base'`** (or a similar import error from inside `pygame`)
The virtual environment was created with an older Python than the one now running it (for example after a Python upgrade through a package manager), so `pygame-ce`'s compiled files no longer match. Reinstall it into the venv:

```bash
pip install --force-reinstall --no-deps pygame-ce==2.5.8
```

or delete `.venv` and recreate it as above.

**No prebuilt `pygame`/`pygame-ce` wheel for your Python version**
If `pip install -r requirements.txt` tries to build from source and fails, your Python version is too new for a prebuilt wheel yet. Either install a slightly older Python (3.11/3.12 are well-supported), or install the latest `pygame-ce` directly (`pip install --upgrade pygame-ce`), which tends to add new-version wheels faster than upstream `pygame`.

**`RuntimeWarning: import sprite: DLL load failed ... An Application Control policy has blocked this file`**
Windows application control (WDAC / Smart App Control) blocked one optional pygame module. The game does not use it and runs normally.

## Known Limitations

- The AI is written in pure Python, so even Senior searches roughly 6-8 plies in the time cap; it has no endgame tablebases or pondering and is not a match for a dedicated engine. Level strength was validated by self-play only, not against human players.
- Search time caps are wall-clock, so the exact depth reached varies with the machine.
- 3D view uses click-to-move only (no drag-and-drop) and skips move animation.
- Pieces are Unicode glyphs rendered from a system font (Segoe UI Symbol, Apple Symbols, DejaVu Sans, etc.), so their look varies by OS; there is no bundled piece set yet.
- The board itself is mouse-only (menus, dialogs and promotion are keyboard-accessible).
- No clocks, save/load, network play, or PGN/FEN import-export yet.
- The prebuilt release is Windows x64 only and is not code-signed.

## Security Notes

- No user-supplied file paths, network input, or `eval`/`exec`/`pickle`/`shell=True` usage in the game. The only subprocess use is the release build script, with argument lists and no shell.
- Runtime and dev dependencies are pinned in the requirements files; Dependabot is configured for pip and GitHub Actions. CI runs with read-only repository permissions.
- The computer's search is bounded in time and memory (wall-clock cap per move, capped transposition table).
- If multiplayer, save/load, or PGN import are added later: validate all external input, use fixed/allowlisted file paths, and treat any player-supplied text (names, chat) as untrusted.

## License

This project is open source and available for personal use.
