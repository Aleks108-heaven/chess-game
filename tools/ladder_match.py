"""
Play matches between AI levels to check that the ladder really is ordered by strength.

    python tools/ladder_match.py junior associate --games 10
    python tools/ladder_match.py --ladder --games 8 --workers 6

Each side is a level key (see ai/levels.py) or "random". Colours alternate game by game and
each game gets its own seed, so a run is repeatable apart from wall-clock effects (time-capped
levels reach different depths on different hardware). A game is scored a draw after
``--max-plies`` plies. Results are reported from the first player's point of view.
"""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from typing import Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chess_ai import ChessAI, RandomAI  # noqa: E402
from chess_engine import RESULT_BLACK_WINS, RESULT_ONGOING, RESULT_WHITE_WINS, ChessEngine  # noqa: E402
from ai.levels import LEVELS  # noqa: E402


def make_player(name: str, seed: int):
    if name == "random":
        return RandomAI(seed)
    return ChessAI(name, seed=seed)


def play_game(white_name: str, black_name: str, seed: int, max_plies: int) -> Tuple[float, int]:
    """Play one game. Returns (white's score: 1 / 0.5 / 0, plies played)."""
    engine = ChessEngine()
    players = {"w": make_player(white_name, seed), "b": make_player(black_name, seed + 1)}
    for ply in range(max_plies):
        mover = "w" if engine.white_to_move else "b"
        engine.play(players[mover].choose_move(engine, engine.get_valid_moves()))
        if engine.result != RESULT_ONGOING:  # mate, stalemate, or an automatic draw
            break
        if engine.can_claim_draw():  # both programs always claim a draw they are entitled to
            return 0.5, ply + 1
    else:
        return 0.5, max_plies
    score = {RESULT_WHITE_WINS: 1.0, RESULT_BLACK_WINS: 0.0}.get(engine.result, 0.5)
    return score, len(engine.move_log)


def run_match(a: str, b: str, games: int, workers: int, max_plies: int, seed: int) -> None:
    jobs = []
    for g in range(games):
        a_is_white = g % 2 == 0
        white, black = (a, b) if a_is_white else (b, a)
        jobs.append((a_is_white, white, black, seed + 10 * g))

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(play_game, w, bl, s, max_plies) for _, w, bl, s in jobs]
        results = [f.result() for f in futures]

    wins = draws = losses = 0
    for (a_is_white, *_), (white_score, _plies) in zip(jobs, results):
        a_score = white_score if a_is_white else 1.0 - white_score
        if a_score == 1.0:
            wins += 1
        elif a_score == 0.0:
            losses += 1
        else:
            draws += 1
    total = wins + draws + losses
    print(f"{a:>10} vs {b:<10} +{wins} ={draws} -{losses}   score {100 * (wins + draws / 2) / total:5.1f}%"
          f"   (avg {sum(p for _, p in results) / total:.0f} plies)", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("players", nargs="*", help="two level keys (or 'random')")
    parser.add_argument("--ladder", action="store_true", help="play every adjacent pair of levels")
    parser.add_argument("--games", type=int, default=10)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--max-plies", type=int, default=240)
    parser.add_argument("--seed", type=int, default=2024)
    args = parser.parse_args()

    valid = {level.key for level in LEVELS} | {"random"}
    if args.ladder:
        keys = ["random"] + [level.key for level in LEVELS]
        pairs = list(zip(keys[1:], keys[:-1]))  # stronger level first
    elif len(args.players) == 2 and all(p in valid for p in args.players):
        pairs = [tuple(args.players)]
    else:
        parser.error(f"give two players from {sorted(valid)} or use --ladder")

    for a, b in pairs:
        run_match(a, b, args.games, args.workers, args.max_plies, args.seed)


if __name__ == "__main__":
    main()
