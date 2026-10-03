# ♔ Chess Game ♚

[![CI](https://github.com/Aleks108-heaven/chess-game/actions/workflows/ci.yml/badge.svg)](https://github.com/Aleks108-heaven/chess-game/actions/workflows/ci.yml)

A Python chess game with a graphical interface built using Pygame. Play against an AI opponent or challenge a friend in 2-player mode, with a wood-themed board that can switch between a flat 2D view and a tilted pseudo-3D perspective view.

## Features

- **Play vs AI** - Minimax with alpha-beta pruning, move ordering, an opening book, and three difficulty levels (Easy/Medium/Hard)
- **2 Player Mode** - Play against a friend locally
- **2D / 3D View Toggle** - Switch anytime between a flat board and a tilted perspective view with depth-scaled, standing pieces
- **Wood-Themed Graphics** - Procedural wood-grain squares, a beveled wooden frame, embossed/shaded pieces with grounding shadows, and a custom window/taskbar icon
- **Drag-and-Drop & Click-to-Move** - Move pieces either way (2D view); click-to-move only in 3D view
- **Move Animation** - Smooth eased piece movement (2D view)
- **Pawn Promotion** - Interactive choice dialog for Queen/Rook/Bishop/Knight
- **Move History & Material Tracking** - Algebraic notation log and captured-piece/material-advantage display
- **Visual Highlights** - Valid moves, last move, check warnings, and selected square
- **Board Flip** - Automatically flips when playing as Black
- **Procedural Sound Effects** - Move, capture, check, castle, promotion, and game-over sounds generated at runtime (no audio files)
- **Undo Support** - Take back moves with a single keypress

## Installation

1. Make sure you have Python 3.x installed
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

## Controls

| Key                         | Action                                                       |
| --------------------------- | ------------------------------------------------------------ |
| `Z`                         | Undo move (disabled while the AI is thinking)                |
| `R`                         | New game (asks to confirm if a game is in progress)          |
| `V`                         | Toggle 2D / 3D view                                          |
| `ESC`                       | Open menu (in the menu: go back, or resume the current game) |
| `Up` / `Down` / `Tab`       | Move focus in menus                                          |
| `Enter` / `Space`           | Activate the focused menu button                             |
| `Q` `R` `B` `N`             | Choose a promotion piece                                     |
| Mouse wheel / `PgUp` `PgDn` | Scroll the move history                                      |

The **View: 2D/3D** button in the top-right of the side panel switches the board view at any time during a game.

## How to Play

1. Launch the game and select a game mode from the menu
2. If playing vs AI, choose your color (White or Black) and difficulty
3. Click a piece (or drag it, in 2D view) - valid moves will be highlighted
4. Click a highlighted square to move the piece
5. The game ends on checkmate, stalemate, or one of the standard draw conditions (fifty-move rule, threefold repetition, insufficient material)

## Project Structure

```text
├── main.py          # Game UI, rendering (2D + pseudo-3D), and input handling (Pygame)
├── chess_engine.py  # Chess rules, move generation, and game state
├── chess_ai.py      # Minimax/alpha-beta AI opponent with opening book
├── requirements.txt # Python dependencies
└── README.md        # This file
```

## Requirements

- Python 3.x
- `pygame-ce`

## Dependencies

- **Direct dependency:** `pygame-ce` (from `requirements.txt`), a community-maintained, API-compatible fork of `pygame`.
- Keep it updated periodically (`pip install --upgrade pygame-ce`) and watch its release notes for fixes.

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

**No prebuilt `pygame`/`pygame-ce` wheel for your Python version**
If `pip install -r requirements.txt` tries to build from source and fails, your Python version is too new for a prebuilt wheel yet. Either install a slightly older Python (3.11/3.12 are well-supported), or install the latest `pygame-ce` directly (`pip install --upgrade pygame-ce`), which tends to add new-version wheels faster than upstream `pygame`.

## Known Limitations

- The AI has no quiescence search or transposition table, so tactical strength is limited even at "Hard."
- 3D view uses click-to-move only (no drag-and-drop) and skips move animation.
- Pieces are Unicode glyphs rendered from a system font (Segoe UI Symbol, Apple Symbols, DejaVu Sans, etc.), so their look varies by OS; there is no bundled piece set yet.
- The board itself is mouse-only (menus, dialogs and promotion are keyboard-accessible).
- No save/load, network play, or PGN/FEN import-export yet.

## Security Notes

- No user-supplied file paths, network input, or `eval`/`exec` usage in this codebase.
- If multiplayer, save/load, or PGN import are added later: validate all external input, use fixed/allowlisted file paths, and treat any player-supplied text (names, chat) as untrusted.

## License

This project is open source and available for personal use.
