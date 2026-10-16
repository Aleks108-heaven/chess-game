"""
A small opening book.

``BOOK_LINES`` maps a move sequence (coordinate notation, e.g. "e2e4 e7e5") to the replies the
engine may choose from. At first use the lines are replayed and re-keyed by position hash,
so a move-order transposition into a known position still finds its book replies. The test
suite replays every line to make sure each move is legal.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional

from .board import SearchBoard

BOOK_LINES: Dict[str, List[str]] = {
    # Starting position
    "": ["e2e4", "d2d4", "c2c4", "g1f3"],
    # 1.e4
    "e2e4": ["e7e5", "c7c5", "e7e6", "c7c6", "d7d5"],
    # 1.e4 e5
    "e2e4 e7e5": ["g1f3", "f1c4", "b1c3"],
    "e2e4 e7e5 g1f3": ["b8c6", "g8f6", "d7d6"],
    # Italian / Ruy Lopez / Scotch
    "e2e4 e7e5 g1f3 b8c6": ["f1b5", "f1c4", "d2d4"],
    "e2e4 e7e5 g1f3 b8c6 f1c4": ["f8c5", "g8f6"],
    "e2e4 e7e5 g1f3 b8c6 f1c4 f8c5": ["c2c3", "d2d3", "b2b4"],
    "e2e4 e7e5 g1f3 b8c6 f1c4 g8f6": ["d2d4", "d2d3", "b1c3"],
    "e2e4 e7e5 g1f3 b8c6 f1b5": ["a7a6", "g8f6", "f8c5"],
    "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6": ["b5a4", "b5c6"],
    "e2e4 e7e5 g1f3 b8c6 d2d4": ["e5d4"],
    # Petrov: 2...Nf6
    "e2e4 e7e5 g1f3 g8f6": ["f3e5", "b1c3", "d2d4"],
    # Sicilian
    "e2e4 c7c5": ["g1f3", "b1c3", "c2c3"],
    "e2e4 c7c5 g1f3": ["d7d6", "b8c6", "e7e6"],
    "e2e4 c7c5 g1f3 d7d6": ["d2d4"],
    "e2e4 c7c5 g1f3 d7d6 d2d4": ["c5d4"],
    "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4": ["f3d4"],
    "e2e4 c7c5 g1f3 b8c6": ["d2d4", "f1b5"],
    "e2e4 c7c5 g1f3 e7e6": ["d2d4", "b1c3"],
    # French
    "e2e4 e7e6": ["d2d4"],
    "e2e4 e7e6 d2d4": ["d7d5"],
    "e2e4 e7e6 d2d4 d7d5": ["b1c3", "b1d2", "e4e5", "e4d5"],
    "e2e4 e7e6 d2d4 d7d5 b1c3": ["g8f6", "f8b4"],
    "e2e4 e7e6 d2d4 d7d5 e4e5": ["c7c5"],
    # Caro-Kann
    "e2e4 c7c6": ["d2d4"],
    "e2e4 c7c6 d2d4": ["d7d5"],
    "e2e4 c7c6 d2d4 d7d5": ["b1c3", "e4e5", "e4d5"],
    # Scandinavian
    "e2e4 d7d5": ["e4d5"],
    "e2e4 d7d5 e4d5": ["d8d5", "g8f6"],
    # 1.d4
    "d2d4": ["d7d5", "g8f6", "e7e6"],
    # Queen's Gambit and friends
    "d2d4 d7d5": ["c2c4", "g1f3", "c1f4"],
    "d2d4 d7d5 c2c4": ["e7e6", "c7c6", "d5c4"],
    "d2d4 d7d5 c2c4 e7e6": ["b1c3", "g1f3"],
    "d2d4 d7d5 c2c4 e7e6 b1c3": ["g8f6", "f8e7"],
    "d2d4 d7d5 c2c4 e7e6 g1f3": ["g8f6"],
    "d2d4 d7d5 c2c4 c7c6": ["g1f3", "b1c3"],
    "d2d4 d7d5 c2c4 d5c4": ["e2e3", "g1f3"],
    # London
    "d2d4 d7d5 c1f4": ["g8f6", "c7c5", "e7e6"],
    # Indian defences
    "d2d4 g8f6": ["c2c4", "g1f3", "c1f4"],
    "d2d4 g8f6 c2c4": ["e7e6", "g7g6", "c7c5"],
    "d2d4 g8f6 c2c4 g7g6": ["b1c3", "g1f3"],
    "d2d4 g8f6 c2c4 g7g6 b1c3": ["f8g7"],
    "d2d4 g8f6 c2c4 g7g6 b1c3 f8g7": ["e2e4", "g1f3"],
    "d2d4 g8f6 c2c4 e7e6": ["b1c3", "g1f3"],
    "d2d4 g8f6 c2c4 e7e6 b1c3": ["f8b4"],
    "d2d4 g8f6 c2c4 c7c5": ["d4d5"],
    # English
    "c2c4": ["e7e5", "g8f6", "c7c5", "e7e6"],
    "c2c4 e7e5": ["b1c3", "g1f3", "g2g3"],
    "c2c4 g8f6": ["b1c3", "g1f3"],
    # Reti
    "g1f3": ["d7d5", "g8f6", "c7c5"],
    "g1f3 d7d5": ["g2g3", "c2c4", "d2d4"],
    "g1f3 g8f6": ["g2g3", "c2c4", "d2d4"],
}


class OpeningBook:
    """Position-keyed book built once from BOOK_LINES."""

    def __init__(self, lines: Optional[Dict[str, List[str]]] = None) -> None:
        self._lines = BOOK_LINES if lines is None else lines
        self._by_position: Optional[Dict[int, List[str]]] = None
        self.skipped: List[str] = []  # lines that could not be replayed (should stay empty)

    def _build(self) -> Dict[int, List[str]]:
        table: Dict[int, List[str]] = {}
        for sequence, replies in self._lines.items():
            board = SearchBoard.start()
            try:
                for text in sequence.split():
                    board.make(board.move_from_uci(text))
            except ValueError:
                self.skipped.append(sequence)
                continue
            entry = table.setdefault(board.hash, [])
            for reply in replies:
                if reply not in entry:
                    entry.append(reply)
        return table

    def choose(self, board: SearchBoard, rng: random.Random) -> Optional[int]:
        """A random legal book reply for this position, or None if the book has none."""
        if self._by_position is None:
            self._by_position = self._build()
        replies = self._by_position.get(board.hash)
        if not replies:
            return None
        legal = {board.move_to_uci(m): m for m in board.legal_moves()}
        choices = [legal[r] for r in replies if r in legal]
        return rng.choice(choices) if choices else None
