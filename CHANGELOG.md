# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

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

[1.1.0]: https://github.com/Aleks108-heaven/chess-game/releases/tag/v1.1.0
[1.0.0]: https://github.com/Aleks108-heaven/chess-game/releases/tag/v1.0.0
