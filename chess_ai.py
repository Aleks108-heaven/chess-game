"""
Chess AI: the computer opponent, from Junior to Senior.

``ChessAI`` is the only class the UI needs. It reads positions from a ``ChessEngine``, searches
them with the fast ``ai`` package, and hands back one of the engine's own ``Move`` objects.

Typical use (the search is CPU-bound, so run it off the UI thread)::

    ai = ChessAI("midlevel")
    position = ChessAI.snapshot(engine)            # cheap; do this on the UI thread
    move = ai.choose_move(position, engine.get_valid_moves(), stop=threading.Event())

The levels themselves live in ``ai/levels.py``.
"""

from __future__ import annotations

import random
import threading
from dataclasses import dataclass
from typing import List, Optional, Union

from ai.board import SearchBoard
from ai.book import OpeningBook
from ai.levels import DEFAULT_LEVEL_KEY, LEVELS, Level, get_level
from ai.pieces import QUEEN, WHITE, letter_from_type
from ai.search import MATE_BOUND, Searcher, SearchLimits
from chess_engine import ChessEngine, Move

__all__ = ["ChessAI", "RandomAI", "SearchProgress", "LEVELS", "DEFAULT_LEVEL_KEY", "Level",
           "get_level", "DRAW_ACCEPT_MARGIN_CP"]

BOOK_MAX_FULLMOVE = 15

# The computer accepts a draw offer only when it is this many centipawns behind or worse (100 is
# about one pawn). The same rule applies at every level.
DRAW_ACCEPT_MARGIN_CP = 100
_DRAW_CHECK_DEPTH, _DRAW_CHECK_SECONDS = 4, 0.25


@dataclass(frozen=True)
class SearchProgress:
    """A snapshot of the current search, safe to read from another thread."""
    depth: int = 0
    score_cp: int = 0
    nodes: int = 0
    elapsed: float = 0.0


class ChessAI:
    """Computer opponent whose strength is set by a :class:`Level`."""

    def __init__(self, level: Union[str, Level] = DEFAULT_LEVEL_KEY,
                 seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)
        self._book = OpeningBook()
        self._table: dict = {}
        self.progress = SearchProgress()
        self.fallback_count = 0  # times the search's move had to be replaced (should stay 0)
        self.level = get_level(level) if isinstance(level, str) else level

    # --- Configuration ----------------------------------------------------------------------

    def set_level(self, level: Union[str, Level]) -> None:
        """Change strength. Raises ValueError for an unknown level key."""
        self.level = get_level(level) if isinstance(level, str) else level

    def new_game(self) -> None:
        """Forget everything learned about the previous game."""
        self._table.clear()
        self.progress = SearchProgress()

    # --- Choosing a move --------------------------------------------------------------------

    @staticmethod
    def snapshot(engine: ChessEngine) -> SearchBoard:
        """Copy the engine's position into a private board the search thread can own."""
        return SearchBoard.from_engine(engine)

    def choose_move(self, source: Union[ChessEngine, SearchBoard],
                    valid_moves: Optional[List[Move]] = None,
                    stop: Optional[threading.Event] = None) -> Optional[Move]:
        """Pick a move for the side to move, or None if there are no legal moves.

        ``source`` is a ChessEngine or a :meth:`snapshot`. ``valid_moves`` are the engine's
        legal moves (required with a snapshot); the returned object is one of them (a
        promotion is four moves, one per piece, and the search picks among them). Setting
        ``stop`` makes the search return promptly with the best move found so far.
        """
        if isinstance(source, SearchBoard):
            board = source.copy()
            if valid_moves is None:
                raise ValueError("valid_moves is required when passing a SearchBoard")
        else:
            board = SearchBoard.from_engine(source)
            if valid_moves is None:
                valid_moves = source.get_valid_moves()
        if not valid_moves:
            return None

        self.progress = SearchProgress()
        if len(valid_moves) == 1:  # a forced move needs no thought
            return valid_moves[0]

        level = self.level
        move = 0
        if level.use_book and board.fullmove <= BOOK_MAX_FULLMOVE:
            move = self._book.choose(board, self._rng) or 0
        if not move:
            move = self._search(board, level, stop)
        return self._to_engine_move(move, valid_moves)

    def accepts_draw(self, source: Union[ChessEngine, SearchBoard], ai_is_white: bool) -> bool:
        """Would the computer accept a draw offered in this position (chess-rules.md, A-08)?

        It says yes only when a short search finds it clearly worse (``DRAW_ACCEPT_MARGIN_CP``
        behind), and no when it is level or ahead. Takes about a quarter of a second at most;
        it does not disturb the level's own search state.
        """
        board = (source.copy() if isinstance(source, SearchBoard)
                 else SearchBoard.from_engine(source))
        result = Searcher({}).search(board, SearchLimits(max_depth=_DRAW_CHECK_DEPTH,
                                                         time_limit=_DRAW_CHECK_SECONDS))
        to_move_is_white = board.side == WHITE
        ai_score = result.score if to_move_is_white == ai_is_white else -result.score
        return ai_score <= -DRAW_ACCEPT_MARGIN_CP

    def _search(self, board: SearchBoard, level: Level,
                stop: Optional[threading.Event]) -> int:
        def report(depth: int, score: int, nodes: int, elapsed: float, _move: int) -> None:
            self.progress = SearchProgress(depth, score, nodes, elapsed)

        searcher = Searcher(self._table, stop_event=stop,
                            quiescence_plies=level.quiescence_plies)
        limits = SearchLimits(max_depth=level.max_depth, time_limit=level.time_limit)
        result = searcher.search(board, limits, exact_root=level.is_imperfect,
                                 on_iteration=report)
        return self._apply_noise(result.move, result.scored_moves, level)

    def _apply_noise(self, best_move: int, scored_moves, level: Level) -> int:
        """Pick a deliberately imperfect move for the weaker levels."""
        if level.noise_cp <= 0 or not scored_moves:
            return best_move
        top_move, top_score = max(scored_moves, key=lambda item: item[1])
        if top_score > MATE_BOUND:
            return top_move  # never talk itself out of a mate it has found

        def fuzzed(item) -> float:
            _, score = item
            if abs(score) > MATE_BOUND:
                return score  # a forced loss stays a forced loss
            return score + self._rng.gauss(0.0, level.noise_cp)

        return max(scored_moves, key=fuzzed)[0]

    def _to_engine_move(self, move: int, valid_moves: List[Move]) -> Move:
        frm, to = move & 63, (move >> 6) & 63
        # A promotion is four legal moves; the one the search chose is told apart by its piece.
        promotion = letter_from_type((move >> 12) & 7 or QUEEN)
        for candidate in valid_moves:
            if (candidate.start_row * 8 + candidate.start_col == frm
                    and candidate.end_row * 8 + candidate.end_col == to
                    and (not candidate.is_pawn_promotion
                         or candidate.promotion_piece == promotion)):
                return candidate
        # The search and the engine disagree about legality: stay playable, but keep a record.
        self.fallback_count += 1
        return self._rng.choice(valid_moves)


class RandomAI:
    """Plays a random legal move. Used as the weakest baseline in strength tests."""

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)

    def choose_move(self, source, valid_moves=None, stop=None) -> Optional[Move]:
        if valid_moves is None:
            valid_moves = source.get_valid_moves()
        return self._rng.choice(valid_moves) if valid_moves else None
