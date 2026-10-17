# Chess Rules: Junior to Advanced

Rules specification for the chess game in this project. Written for people and for Claude Code.

- **Based on:** standard chess as in the FIDE Laws of Chess (2023 edition). Check the FIDE Rules Commission page (rcc.fide.com) for newer editions.
- **Version:** 1.0, 2026-10-17.
- **Test data:** every position and number in section 8 was checked with python-chess 1.11.2.
- **Rule IDs:** `J-xx` Junior (Level 1), `I-xx` Intermediate (Level 2), `A-xx` Advanced (Level 3), `T-xx` tests, `P-x` perft positions.

---

## 1. How to use this file

1. This file is the single source of truth for the game rules. If the code and this file disagree, ask the user before changing either one.
2. Build level by level. Finish and test Level 1 before Level 2, and Level 2 before Level 3.
3. Use rule IDs in test names and code comments, for example `test_I02_en_passant_expires_after_one_move`.
4. Keep the rules engine separate from the UI, the network and the clock. It must be testable with no UI.
5. The engine must check every move, even if the UI only shows legal moves. Never trust the client.
6. If a rule is missing or unclear, do not guess. Ask.

## 2. Levels at a glance

| Level | Name | Adds | Typical use |
| --- | --- | --- | --- |
| 1 | Junior | Board, piece moves, capture, check, checkmate, stalemate | Teaching mode, first playable version |
| 2 | Intermediate | Castling, en passant, promotion, insufficient material | All move rules of real chess |
| 3 | Advanced | Repetition, 50/75-move rules, dead positions, clocks, draw offers, notation | Full competitive rules |

Level 1 alone is a simplified teaching game. It is not full chess.

## 3. State the engine must track (from day one)

Even if Level 1 does not use all of these, store them from the start. They are part of the FEN format, and Levels 2 and 3 need them. Adding them later usually means rewriting the move logic.

- Piece placement (64 squares)
- Side to move
- Castling rights: 4 flags (White kingside, White queenside, Black kingside, Black queenside)
- En passant target square (or none)
- Halfmove clock: half-moves since the last pawn move or capture
- Fullmove number: starts at 1, goes up by 1 after each Black move
- Move list and position history (needed for repetition and take-backs)
- Result and reason (checkmate, stalemate, resignation, agreement, repetition, 50/75-move rule, insufficient material, time)

---

## 4. Level 1: Junior (core rules)

### J-01 Board

- 8x8 squares, alternating light and dark.
- Files `a`-`h` from left to right, ranks `1`-`8` from bottom to top (from White's side).
- Square `a1` is dark. Square `h1` is light.

### J-02 Pieces

- Each player has 16 pieces: 1 king, 1 queen, 2 rooks, 2 bishops, 2 knights, 8 pawns.
- White has the light pieces. Black has the dark pieces.

### J-03 Start position

- White pawns are on rank 2. The other White pieces are on rank 1, from `a` to `h`: rook, knight, bishop, queen, king, bishop, knight, rook.
- Black is the mirror image on ranks 7 and 8. Each queen starts on her own colour: White queen on `d1`, Black queen on `d8`.
- FEN: `rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1`

### J-04 Turns

- White moves first. Then the players move in turn.
- A player must move. Passing is not allowed.
- One move per turn. (Castling counts as one move.)

### J-05 How pieces move

- **King:** one square in any direction.
- **Rook:** any number of empty squares along a rank or a file.
- **Bishop:** any number of empty squares along a diagonal. It always stays on the colour it started on.
- **Queen:** moves like a rook or a bishop.
- **Knight:** two squares in one direction and one square sideways (an "L" shape). It is the only piece that can jump over other pieces.
- **Pawn:** see J-06.
- Rook, bishop and queen cannot jump over pieces.
- A piece cannot move to a square that holds a piece of its own colour.

### J-06 Pawn

- Moves one square straight forward if that square is empty. White moves up the board (rank number grows). Black moves down.
- From its starting rank (rank 2 for White, rank 7 for Black) it may instead move two squares straight forward, if both squares are empty.
- Captures one square diagonally forward. It cannot capture straight ahead. It cannot move diagonally unless it captures. It never moves backward.
- For en passant and promotion, see Level 2.

### J-07 Capturing

- A piece captures by moving onto a square with an opponent's piece. The captured piece leaves the game.
- Capturing is never forced.
- The king is never captured. The game ends before that (see J-10).

### J-08 Check

- A king is in check when an opponent's piece attacks its square.
- Pawns attack diagonally forward, not straight ahead.
- A pinned piece still gives check. (Pinned means: moving it would expose its own king.)

### J-09 Legal moves

- A move is legal only if, after the move, your own king is not attacked.
- So you cannot: move your king to an attacked square; move a pinned piece off the line between its king and the pinning piece (it may move along that line, even capturing the pinning piece); ignore a check.
- Kings can never stand next to each other.
- If you are in check, there are three ways out: move the king to a safe square; capture the attacking piece; block the line (only against a rook, bishop or queen that has at least one square between it and the king).
- Double check (two attackers at once): only a king move is legal.

### J-10 Checkmate

- The player to move is in check and has no legal move. That player loses. The game is over.

### J-11 Stalemate

- The player to move is not in check and has no legal move. The game is a draw. The game is over.

### J-12 Resignation and agreed draw

- A player may resign at any time. The opponent wins.
- If both players agree to a draw, the game is a draw.

> **Piece values** (not a rule; only for hints, scores or AI): pawn 1, knight 3, bishop 3, rook 5, queen 9.

---

## 5. Level 2: Intermediate (special moves)

### I-01 Castling

One move of the king and one rook, on the player's first rank. The king moves two squares towards the rook. The rook jumps to the square the king crossed.

| Move | King | Rook | Squares that must be empty | King must not be attacked on |
| --- | --- | --- | --- | --- |
| White O-O | e1 → g1 | h1 → f1 | f1, g1 | e1, f1, g1 |
| White O-O-O | e1 → c1 | a1 → d1 | b1, c1, d1 | e1, d1, c1 |
| Black O-O | e8 → g8 | h8 → f8 | f8, g8 | e8, f8, g8 |
| Black O-O-O | e8 → c8 | a8 → d8 | b8, c8, d8 | e8, d8, c8 |

Castling is legal only if all of these are true:

1. The king has never moved.
2. That rook has never moved and has not been captured.
3. All squares between the king and the rook are empty.
4. The king is not in check now, does not pass over an attacked square, and does not land on an attacked square (last column of the table).

Notes:

- For queenside castling, `b1` (`b8`) must be empty, but it may be attacked. The rook may be attacked too.
- Castling rights are lost for good when: the king moves (both sides); a rook moves (that side); a rook is captured on its starting square (that side). A rook that goes out and comes back does not restore the right.
- Castling is one move. UCI: `e1g1`, `e1c1`, `e8g8`, `e8c8`. SAN: `O-O`, `O-O-O`.

### I-02 En passant

A special pawn capture. It is legal only if all of these are true:

1. On the opponent's previous move, a pawn moved two squares forward from its starting square.
2. Your pawn is on the same rank, on the file next to that pawn. (For White this is rank 5. For Black it is rank 4.)
3. You capture on your very next move. After any other move, the right is gone.
4. The capture does not leave your own king in check (see J-09).

How it works: your pawn moves diagonally forward to the square the enemy pawn jumped over. The enemy pawn is removed from its own square, which is NOT the square where your pawn lands.

Example: White pawn on `e5`. Black plays `d7-d5`. White may play `exd6` (en passant). The White pawn lands on `d6`. The Black pawn on `d5` is removed.

Notes:

- Store an `en_passant_target` square after every two-square pawn move. Clear it after the next move.
- Special case: both pawns leave the same rank at once. An enemy rook or queen on that rank may then attack your king, and the capture is illegal (see T-13).
- En passant counts as a pawn move and a capture: the halfmove clock goes back to 0.

### I-03 Promotion

- When a pawn reaches the last rank (rank 8 for White, rank 1 for Black), it MUST become a queen, rook, bishop or knight of the same colour, in the same move.
- The player chooses freely. The choice is not limited to captured pieces, so a player can have two or more queens.
- A pawn cannot stay a pawn, and cannot become a king.
- Promotion can happen on a straight move or on a capture.
- The new piece works at once. It can give check or checkmate immediately.
- Choosing a rook, bishop or knight is called underpromotion. It is legal, and sometimes the best move (for example, to avoid stalemate).
- Implementation: one pawn move to the last rank is 4 different moves (`e7e8q`, `e7e8r`, `e7e8b`, `e7e8n`). The UI must ask the player. The move generator and the AI must produce all four. The game must not continue before the piece is chosen.

### I-04 Insufficient material (automatic draw)

The game is a draw at once when checkmate is impossible for both sides. Minimum set to implement:

- King vs king
- King + bishop vs king
- King + knight vs king
- Kings and bishops only, with all bishops (of both sides) on squares of the same colour

These are NOT automatic draws (checkmate is still possible): king + 2 knights vs king; king + knight vs king + knight; king + bishop vs king + bishop on opposite colours; any position with a pawn, rook or queen. For fully blocked positions, see A-01.

---

## 6. Level 3: Advanced (full end-of-game rules, clocks, notation)

### A-01 Dead position (general rule)

A dead position is one where no series of legal moves, even with the worst play by both sides, can end in checkmate. The game is a draw at once. I-04 covers the common cases. A full detector must also find rare blocked positions (for example, locked pawn chains that no king can reach). This is hard, so treat it as optional. If you skip it, the fivefold and 75-move rules still end the game.

### A-02 What "the same position" means

Two positions are the same only if ALL of these are equal: piece placement; side to move; castling rights; en passant possibility (counted only if an en passant capture is really legal). Move counters are ignored. The same position can be reached by different move orders.

Implementation: use as a key the first four FEN fields, with the en passant square written only when a legal en passant capture exists (python-chess does this by default). You may clear the history after any pawn move or capture, because earlier positions can never come back.

### A-03 Threefold repetition (claim)

When the same position appears for the third time (not necessarily in a row), the player to move can claim a draw. Project setting: manual claim (like FIDE) or automatic draw. Decide once and write it in this file.

### A-04 Fivefold repetition (automatic)

When the same position appears for the fifth time, the game is a draw. No claim needed.

### A-05 Fifty-move rule (claim)

If 50 moves by each player (100 half-moves) pass with no pawn move and no capture, the player to move can claim a draw. Use the halfmove clock: set it to 0 after any pawn move or capture, otherwise add 1 after every half-move (castling and king moves too). Claim allowed when the clock is 100 or more.

### A-06 Seventy-five-move rule (automatic)

If 75 moves by each player (150 half-moves) pass with no pawn move and no capture, the game is a draw at once. If the move that reaches 150 is checkmate, checkmate wins.

### A-07 Order of end-of-game checks (after every move)

1. Checkmate
2. Stalemate
3. Dead position / insufficient material
4. Fivefold repetition
5. Seventy-five-move rule

Then offer the claims (threefold repetition, fifty-move rule) to the player to move. Resignation, agreed draw and time forfeit are separate events (A-08, A-09).

### A-08 Resignation and draw offers

- Resignation ends the game at once. The resigning player loses.
- A player may offer a draw. The opponent accepts or declines. Accepting ends the game as a draw. An offer is also declined when the opponent makes a move.
- Project decision: limit draw offers (for example, one per player every N moves) so they cannot be spammed.

### A-09 Clock and time forfeit (optional feature)

- Each player has a time budget. The clock of the player to move counts down, and it switches after each move.
- Common formats: base time + increment (add X seconds after each move), or delay (count down only after a delay).
- If a player's time reaches zero, that player loses on time. Exception: if the opponent can never checkmate by any legal series of moves, the game is a draw. Start simple: the opponent has only a king, so it is a draw. (Positions already drawn by I-04 end earlier.) Otherwise the flagged player loses.
- The server clock is the only real clock. The client clock is only a display. Decide how to treat a move that arrives just after the time ran out, and write it in this file.

### A-10 Touch-move (over-the-board play only, optional)

In a real game, a player who touches one of their own pieces must move it if a legal move exists, and a player who touches an opponent's piece must capture it if possible. A digital game does not need this. If you offer take-backs, make it a casual-mode option, and switch it off in strict mode.

### A-11 Notation and data formats

- **Squares:** file letter + rank number, for example `e4`.
- **SAN (move lists for people):** piece letters `K Q R B N`; no letter for pawns; `x` capture; `+` check; `#` checkmate; `O-O` and `O-O-O` castling; `=Q` promotion. Examples: `e4`, `Nf3`, `Bxe5`, `exd5`, `Qh4#`, `e8=Q+`. If two pieces of the same type can reach the same square, add the file (`Rad8`), else the rank (`R1a4`), else both.
- **UCI (moves for engines):** from-square + to-square + promotion letter in lower case: `e2e4`, `e7e8q`. Castling is the king move: `e1g1`.
- **FEN (one position on one line), 6 fields:** (1) pieces from rank 8 to rank 1, `/` between ranks, digits for empty squares, upper case = White; (2) side to move, `w` or `b`; (3) castling rights, `KQkq` or `-`; (4) en passant square or `-`; (5) halfmove clock; (6) fullmove number.
- **PGN (a whole game):** tag pairs `Event`, `Site`, `Date`, `Round`, `White`, `Black`, `Result`, then the moves in SAN and the result.
- **Results:** `1-0` White wins, `0-1` Black wins, `1/2-1/2` draw, `*` game not finished.

---

## 7. Most likely defects (check these first)

Risk-based priority: J-09, I-01, I-02 and I-03 cause most real bugs. Test them first.

1. Castling rights not removed when a rook is captured on its home square (T-11), or restored after a rook goes out and back (T-10).
2. Castling allowed out of check or through an attacked square, or wrongly blocked because `b1`/`b8` is attacked (T-07 to T-09).
3. En passant: old target square not cleared after one move; wrong pawn removed; the rank-pin case missed (T-12, T-13).
4. Promotion: only the queen is generated; promotion by capture missing; the game continues before the player chooses (T-14).
5. Pins and check: a pinned piece leaves the pin line; double check answered with a non-king move; kings next to each other (T-04 to T-06).
6. Checkmate and stalemate mixed up. They differ only by "is the king in check?" (T-01 to T-03).
7. Repetition ignores castling rights or the en passant square, or compares positions with a different side to move (T-17, T-18).
8. Halfmove clock not reset on a pawn move or capture (also en passant), or reset by mistake on castling or a king move (T-19, T-20).
9. Undo bugs: after a take-back, castling rights, the en passant square, a captured piece or a promoted pawn are not restored. Check with "move then undo = same state" and with perft (P-1 to P-6).
10. Security and reliability: trusting moves or clock times sent by the client; accepting malformed move text; unlimited game history. Validate everything on the server.
11. Performance: legal-move generation is the hot path (AI, hints). Measure perft speed and avoid creating new objects for every node.

## 8. Test checklist

Techniques used: equivalence partitioning (piece types x blocked / pinned / in check), boundary value analysis (counters 99/100, 149/150; repetition 2/3/5), state transition testing (playing → check → checkmate / stalemate / draw). All tests are automatable unit tests. Suggested CI plan: depth 3 or less on every commit; deeper perft depths nightly.

### 8.1 Perft (move-generator test)

Perft counts all positions after N half-moves. If your numbers match, your move generator is almost certainly right. Standard positions (Chess Programming Wiki, "Perft Results"). Values are leaf-node counts for depth 1 / 2 / 3 / 4 (/ 5):

- **P-1 start position** `rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1`: 20 / 400 / 8,902 / 197,281 / 4,865,609
- **P-2 "Kiwipete"** `r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1`: 48 / 2,039 / 97,862 / 4,085,603
- **P-3** `8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1`: 14 / 191 / 2,812 / 43,238 / 674,624
- **P-4** `r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1`: 6 / 264 / 9,467 / 422,333
- **P-5** `rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8`: 44 / 1,486 / 62,379 / 2,103,487
- **P-6** `r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10`: 46 / 2,079 / 89,890 / 3,894,594

### 8.2 Scenario tests

| ID | Rules | Setup | Expected result |
| --- | --- | --- | --- |
| T-01 | J-10 | Fool's mate: `1.f3 e5 2.g4 Qh4#` | Checkmate after 4 half-moves. Black wins (`0-1`). Final FEN: `rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3` |
| T-02 | J-10 | Scholar's mate: `1.e4 e5 2.Qh5 Nc6 3.Bc4 Nf6 4.Qxf7#` | Checkmate. White wins (`1-0`). Final FEN: `r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4` |
| T-03 | J-11 | `7k/5Q2/6K1/8/8/8/8/8 b - - 0 1` | Black has no legal move and is not in check: stalemate, draw (`1/2-1/2`) |
| T-04 | J-09 | Double check: `4k3/8/5N2/1B6/8/8/8/4K3 b - - 0 1` | Only king moves are legal: Kd8, Ke7, Kf7, Kf8 |
| T-05 | J-09 | Pinned rook: `k7/4r3/8/8/8/8/4R3/4K3 w - - 0 1` | The White rook on e2 can move only along the e-file (e3 to e7, capturing on e7). No sideways moves |
| T-06 | J-09 | Kings: `8/8/8/3k4/8/3K4/8/8 w - - 0 1` | White king moves: c2, c3, d2, e2, e3 only (not c4, d4, e4) |
| T-07 | I-01 | `4kr2/8/8/8/8/8/8/R3K2R w KQ - 0 1` | O-O illegal (f1 attacked). O-O-O legal |
| T-08 | I-01 | `1r2k3/8/8/8/8/8/8/R3K2R w KQ - 0 1` | O-O and O-O-O both legal (b1 is attacked, and that is allowed) |
| T-09 | I-01 | `3kr3/8/8/8/8/8/8/R3K2R w KQ - 0 1` | King is in check: no castling |
| T-10 | I-01 | From `r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1` play `Rg1 Rg8 Rh1 Rh8` | Castling rights are now `Qq`. White O-O illegal, O-O-O legal |
| T-11 | I-01 | `4k3/8/8/8/8/8/6b1/R3K2R b KQ - 0 1`, Black plays `Bxh1` | Rights become `Q`. White O-O illegal |
| T-12 | I-02 | `rnbqkbnr/1pp1pppp/p7/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3` | `exd6` en passant is legal. White pawn lands on d6, Black pawn on d5 is removed, halfmove clock is 0. If White plays another move first (for example `Nf3 a5`), en passant is no longer legal |
| T-13 | I-02, J-09 | `4k3/8/8/KPp4r/8/8/8/8 w - c6 0 1` | `bxc6` en passant is illegal (it would expose the king to the rook on h5) |
| T-14 | I-03 | `7k/P7/8/8/8/8/8/K7 w - - 0 1` | Exactly 7 legal moves: a8=Q, a8=R, a8=B, a8=N, Ka2, Kb1, Kb2 |
| T-15 | I-04 | K vs K; K+B vs K; K+N vs K; K+B vs K+B with bishops on the same colour | Automatic draw |
| T-16 | I-04 | K+N+N vs K; K+N vs K+N; K+B vs K+B on opposite colours; K+P vs K | No automatic draw |
| T-17 | A-03, A-04 | From the start position play `Nf3 Nf6 Ng1 Ng8` again and again | After 1 cycle: start position seen 2 times, nothing happens. After 2 cycles: 3 times, draw can be claimed. After 4 cycles: 5 times, automatic draw |
| T-18 | A-02 | Same piece placement, but castling rights differ (see T-10) | Not the same position. Counts are separate |
| T-19 | A-05, A-06 | Halfmove clock at 99, 100, 149, 150 | 99: no claim. 100: claim allowed. 149: no automatic draw. 150: automatic draw. Checkmate on the move that reaches 150 wins: `6k1/5ppp/8/8/8/8/8/R3K3 w - - 149 90`, `Ra8#` is checkmate, not a draw |
| T-20 | A-05 | Halfmove clock after one move | Pawn move: 0. Capture: 0. En passant: 0. Quiet piece move, king move, castling: +1 |
| T-21 | A-09 | Player A runs out of time | Opponent has only a king: draw. Opponent has a rook: A loses on time |

### 8.3 Exploratory and negative ideas

- **Random play-outs:** play thousands of random legal games. At every position compare the legal moves, the check / checkmate / stalemate flags and the FEN with a trusted library (in test code only, for example python-chess or chess.js).
- **Round trips:** FEN → board → FEN must give the same text. Move then undo must give the same state.
- **Bad input:** malformed move text, squares outside the board, moving the other side's piece, moving when the game is over, a promotion without a piece letter. Every case must be rejected and the state must not change.
- **Long games:** a game of more than 300 half-moves must not slow down or crash the repetition check.

---

## 9. What should I check additionally? (open questions and out of scope)

Open questions (answer them and write the answers in this file):

- Which language and framework is the project in? Own rules engine or a library? Own engine: full control and learning, but more bugs and more time. Library: fewer bugs and faster, but less control. In both cases, keep this file and the tests. They also work as acceptance tests for a library.
- Which features are needed: clocks, online play, an AI opponent, hints for Junior mode, take-backs, saving games (PGN)?
- Draw claims (A-03, A-05): manual or automatic?
- Time forfeit (A-09): how do you treat late moves and lag?

Out of scope for now: Chess960 and other variants, rating systems, tournament pairing, arbiter penalties for illegal moves, over-the-board scoresheet rules.

---

## 10. Project decisions (answers to section 9, written 2026-10-17)

These were decided when the game was brought in line with this file. They are the project's choices where the rules above leave one open, so change them here first if you disagree, then change the code. Nothing in sections 1 to 8 was altered.

**Stack.** Python 3.11+ and Pygame. The rules engine is our own, in `chess_engine.py`, with no UI code in it. The computer opponent searches with a second, much faster board (`ai/board.py`); the two engines are checked against each other move for move, and both against the perft numbers in section 8.1. The tests in `tests/test_rules.py` are named by the rule and scenario IDs above (`test_T12_I02_...`, `test_J09_...`, `test_perft_...`).

**Features.**

| Feature | Decision |
| --- | --- |
| AI opponent | Yes, five levels called Junior to Senior. These are **opponent strengths, not the rule levels** of section 2: the game always plays all of Levels 1, 2 and 3. There is no "Level 1 only" teaching mode and no hint system. |
| Take-backs | Yes (`Z`). It is a casual game, so there is no strict mode (A-10 does not apply). |
| Saving games | The game is copied to the clipboard as PGN (`P`, A-11). There is no file saving and no PGN import. |
| Clocks, time forfeit (A-09) | **Not implemented.** The question about late moves and lag stays open until a clock exists. |
| Online play | No. |
| Chess960, variants | Out of scope, as in section 9. |

**Draw claims (A-03, A-05): manual, as in FIDE.** The player to move can claim a draw by threefold repetition or by the 50-move rule. The side panel has a *Claim draw* button (key `C`) that is active only when a claim is possible, and the player is told once per game, for each kind of claim, when it first becomes possible. Fivefold repetition and the 75-move rule (A-04, A-06) are automatic. The computer never claims a draw; the human can.

**End-of-game order (A-07)** is the order in the file: checkmate, stalemate, insufficient material, fivefold repetition, 75-move rule. Checkmate on the move that reaches 150 half-moves wins (T-19).

**Resignation and draw offers (J-12, A-08).**

- Resigning asks for confirmation. Against the computer you resign; with two players the side to move does.
- A player may offer a draw on their own turn, and again only after 10 more moves (full moves of the game, counted from the previous offer).
- Two players: the other player answers *Accept* or *Decline*. Making a move instead also declines.
- The computer accepts only when a short search (depth 4, at most 0.25 s) finds it about a pawn (100 centipawns) or more behind, and declines otherwise. The rule is the same at every strength level.

**Dead positions (A-01).** Only the cases in I-04 are detected, including any number of bishops that all stand on one square colour. The general detector for blocked positions is skipped, as A-01 allows; the fivefold and 75-move rules still end such games.

**Promotion (I-03).** The move generator produces four moves for a pawn reaching the last rank (the perft numbers in 8.1 count them that way). The UI asks which piece before anything is played, and the computer chooses among all four, including under-promotion to avoid stalemate.

**Notation (A-11).**

- UCI text gives the promotion piece in lower case (`e7e8q`).
- The engine writes the en passant square in a FEN only when a legal en passant capture exists, as python-chess does. A FEN that lists an unusable square is accepted and written back without it. Castling rights and en passant squares the pieces cannot back up are dropped when a FEN is read.
- The engine rejects a malformed FEN, a position with the side that just moved in check, a pawn on the first or last rank, and a wrong number of kings.

**The Rules screen.** The game has a Rules screen (menu button, or `H`) with five pages that explain sections 4 to 6 to players in plain words. Its text is `rules_text.py`; the thresholds on it come from the engine's constants, and `tests/test_rules_text.py` checks them against this file. This file remains the source of truth: change it first, then the screen.

**Checking moves (section 1, rule 5; section 8.3).** `ChessEngine.play` checks every move: it refuses a move after the game is over, a move for the wrong side, a malformed or illegal move, and a promotion without a legal piece. The state is left untouched in each case. It plays its own copy of the matching legal move, so a caller cannot forge what the move captures. `make_move` is the unchecked primitive underneath.
