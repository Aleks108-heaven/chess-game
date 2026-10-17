# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [1.2.0] - 2026-10-17

The game now follows `chess-rules.md` (all three levels of it), the 3D board is fixed and framed,
and the Windows installer puts the game in Program Files.

### Added

- **A Rules screen** inside the game: *Rules* in the main menu, or `H` / `F1` at any time. Five
  pages (the board and pieces; check, checkmate and stalemate; special moves; draws and how a game
  ends; playing here), turned with the arrow keys or the buttons, closed with `Esc`. Its text
  lives in `rules_text.py`, takes its numbers from the engine, and is tested against it and
  against `chess-rules.md`. The computer's reply waits while it is open.
- **Resign, offer a draw, claim a draw.** Buttons below the move list (and `X`, `D`, `C`). The
  computer accepts a draw only when it is clearly worse (about a pawn or more behind); with two
  players the other player answers. A button that cannot be used is grey and says why when
  clicked. The *Claim draw* button lights up, with a notice, when a claim becomes possible.
- **Fivefold repetition and the 75-move rule** end the game automatically (they were missing).
- **Copy the game as PGN** with `P`.
- **Notices** (short messages over the board) and a generic confirmation dialog.
- `chess-rules.md` is part of the project, with a new section 10 recording the decisions it
  leaves open (manual claims, draw-offer limits, what is and is not implemented).
- `tests/test_rules.py`: every scenario (T-01 to T-20) and the six perft positions of the rules
  file, plus the bad-input and undo cases, on the game's own engine; `tests/test_installer_script.py`
  pins the installer's promises. The suite grew from 134 to over 380 tests, and the engine was also
  checked against python-chess on 400 played games (about 49,000 positions, with every kind of
  draw, mate and promotion) and 2,000 random endings, and against published perft counts down to
  depth 4 and 5.
- Engine API (no UI code): `from_fen`/`to_fen`, `play` and `play_uci` (checked moves),
  `result`/`result_reason`, `can_claim_draw`/`claim_draw`, `resign`, `offer_draw`/`accept_draw`,
  `san_moves`/`to_pgn`.

### Changed

- **Threefold repetition and the 50-move rule are now claimed**, as in the rules of chess, instead
  of ending the game by themselves. The computer never claims a draw.
- **The installer installs for all users into `C:\Program Files\Chess Game`** and asks for
  administrator approval. Earlier per-user installs (1.1.0 and older) are removed when it runs; use
  `/CURRENTUSER` to install without administrator rights. The "Launch" option starts the game as
  the ordinary user, not elevated. Installing into Program Files does not remove the
  unknown-publisher warning of an unsigned download.
- A pawn reaching the last rank is four moves for the engine, one per piece, so the computer can
  choose an under-promotion (for example to avoid stalemate). UCI text carries the piece (`e7e8q`).
- In a dialog, `Enter` and `Esc` now take the safe choice (the focused button, No / Decline); `Y`
  confirms. Before, `Enter` confirmed "Start a new game?" while the focus ring sat on No.
- The 3D board sits inside a wooden frame on a table, with rank and file labels like the 2D board;
  the perspective is gentler (far edge 92% of the near edge, was 86%).

### Fixed

- **Castling through a square attacked only by a pawn was allowed.** The engine's attack test
  generated captures only, so a pawn's diagonal attack on an empty square was missed (for
  example a Black pawn on e2 against O-O and O-O-O).
- **3D view:** every piece shadow was drawn a whole square in front of its piece; the board ran
  flush to the window edges with dark empty wedges at the top corners and no frame.
- Repetition counting ignored the starting position, so a position seen three times from the
  first move was not noticed, and counted an en passant square nobody could use as a difference
  between otherwise identical positions.
- Insufficient material missed kings with several bishops that all stand on one colour.
- Taking back a move that gave check left the "in check" marker on, so the red glow showed on the
  wrong king.
- The computer's view of a game that was set up from a FEN now includes the moves played since
  (it could not see repetitions there); only tests and tools start games that way.
- The slow test "Senior mates with king and queen against king" failed now and then (in 1.1.0
  too): Senior's wall-clock search cap made its moves depend on how busy the machine was. The
  test now fixes Senior's depth and lifts the cap, so it gives the same game every time.

## [1.1.0] - 2026-10-16

No gameplay changes: this release adds a Windows installer.

### Added

- **Windows setup installer** (`ChessGame-v1.1.0-windows-x64-setup.exe`, built with Inno Setup
  from `installer/ChessGame.iss`). Installs per user without an administrator prompt (the wizard
  can install for all users instead), adds Start Menu and optional desktop shortcuts, appears in
  *Apps > Installed apps* and uninstalls cleanly. Installing a newer version over an older one
  upgrades it in place. The portable zip is still published.
- `tools/build_release.py` builds the installer, then installs it silently into a temporary
  folder, runs the installed program's `--self-test` and uninstalls it before the release is
  accepted. `--no-installer` builds the zip only.

## [1.0.0] - 2026-10-16

First tagged release.

### Added

- **Five-level computer opponent, Junior to Senior.** Pick a level on the new start screen
  (level cards with strength pips and a one-line description). Levels differ in search depth,
  think-time cap, how far they follow captures, how often they slip, and whether they use the
  opening book. See the README for how the ladder was checked.
- **A new search engine** (`ai/` package): fast mailbox board with incremental hashing and
  evaluation, iterative-deepening alpha-beta with a transposition table, quiescence search,
  null-move pruning, late-move reductions and an endgame "mop-up" so it can convert won
  endings. Roughly 600x the node rate of the previous AI (about 80,000 vs 130 nodes/s on the
  development machine).
- Position-based opening book (finds book moves after move-order transpositions).
- Start screen: *Resume game* button, remembers your last level, opponent shown in the side panel,
  "thinking" indicator shows the opponent's name and search depth.
- Keyboard: `F` flips the board, `M` mutes sound. Optional `CHESS_REDUCED_MOTION=1` turns off
  the move animation and pulsing indicator.
- `python main.py --version` and `--self-test` (draws every screen and plays a turn headlessly).
- Design tokens (`theme.py`) with computed WCAG contrast checks; 134-test suite (`pytest`);
  strength-ladder match runner (`tools/ladder_match.py`); Windows release build
  (`tools/build_release.py`) that tests the packaged program before zipping it.
- Dependabot configuration for pip and GitHub Actions.

### Changed

- CI now installs pinned dev requirements, runs the full test suite on Python 3.11-3.13, runs the
  headless self-test, and uses read-only workflow permissions.
- Design values moved from `main.py` into `theme.py`; the computer chooses its own promotion piece.
- The search runs on a private snapshot of the position instead of a deep copy of the live engine.

### Fixed

- The red "check" outline was 2.84:1 against light squares and about 1.2:1 against dark ones
  (below the 3:1 WCAG minimum for meaningful graphics); it is now a darker crimson that clears
  3:1 on both.
- The old "Hard" level took 30 s per move and returned scores corrupted by its own timeout.
- Three opening-book lines named moves that were not legal (Ruy Lopez `Ba4`/`Bxc6`, Petrov
  `Nxe5`) and were silently skipped; they are fixed and a test now replays every book line.
- Starting a second game window in one process failed because cached fonts outlived
  `pygame.quit()`.
- Menu title and subtitle no longer collide.

[1.2.0]: https://github.com/Aleks108-heaven/chess-game/releases/tag/v1.2.0
[1.1.0]: https://github.com/Aleks108-heaven/chess-game/releases/tag/v1.1.0
[1.0.0]: https://github.com/Aleks108-heaven/chess-game/releases/tag/v1.0.0
