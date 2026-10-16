"""
Alpha-beta search over a SearchBoard.

Iterative deepening negamax with principal-variation search, a transposition table,
quiescence search, null-move pruning, late-move reductions, reverse futility pruning,
killer/history move ordering and check extensions. A depth cap, wall-clock deadline, node
cap and an external stop event can all end the search; whatever the last fully completed
iteration found is returned, so there is always a legal move to play.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .board import FLAG_EP, MOVE_MASK, SearchBoard
from .evaluation import evaluate

INF = 1_000_000
MATE = 100_000
MATE_BOUND = MATE - 512  # |score| above this means "forced mate"

MAX_PLY = 96
TT_EXACT, TT_LOWER, TT_UPPER = 0, 1, 2
TT_MAX_ENTRIES = 200_000

NULL_MOVE_MIN_DEPTH = 3
LMR_MIN_DEPTH = 3
LMR_FULL_DEPTH_MOVES = 3
RFP_MAX_DEPTH = 3
RFP_MARGIN = 130
BUDGET_CHECK_MASK = 2047  # look at the clock every 2048 nodes


@dataclass
class SearchLimits:
    """How long the search may run. ``None`` disables the corresponding limit."""
    max_depth: int = 4
    time_limit: Optional[float] = None
    node_limit: Optional[int] = None


@dataclass
class SearchResult:
    move: int = 0                 # best move (int-encoded); 0 only if there are no legal moves
    score: int = 0                # centipawns for the side to move, or a mate score
    depth: int = 0                # deepest fully completed iteration
    nodes: int = 0
    elapsed: float = 0.0
    scored_moves: List[Tuple[int, int]] = field(default_factory=list)  # exact-root mode only


ProgressCallback = Callable[[int, int, int, float, int], None]


class Searcher:
    """One searcher can be reused across moves; it owns the transposition table."""

    def __init__(self, table: Optional[Dict[int, tuple]] = None,
                 stop_event: Optional[threading.Event] = None,
                 quiescence_plies: int = 64) -> None:
        self.tt: Dict[int, tuple] = table if table is not None else {}
        self.stop_event = stop_event
        self.quiescence_plies = quiescence_plies
        self.generation = 0

        self.board: SearchBoard = SearchBoard.start()
        self.nodes = 0
        self.stopped = False
        self.deadline: Optional[float] = None
        self.node_limit: Optional[int] = None
        self._limits_active = False
        self._iter_best: Optional[Tuple[int, int]] = None
        self.killers: List[List[int]] = [[0, 0] for _ in range(MAX_PLY)]
        self.history: Dict[int, int] = defaultdict(int)

    # --- Public API -------------------------------------------------------------------------

    def search(self, board: SearchBoard, limits: SearchLimits, exact_root: bool = False,
               on_iteration: Optional[ProgressCallback] = None) -> SearchResult:
        """Search ``board`` (restored to its original state on return).

        With ``exact_root`` every root move is searched with a full window so each gets a true
        score (needed to choose a deliberately imperfect move); otherwise only the best move's
        score is exact, which is much faster.
        """
        self.board = board
        self.nodes = 0
        self.stopped = False
        self.generation += 1
        self.killers = [[0, 0] for _ in range(MAX_PLY)]
        self.history = defaultdict(int)
        if len(self.tt) > TT_MAX_ENTRIES:
            self.tt.clear()

        start = time.perf_counter()
        self.deadline = start + limits.time_limit if limits.time_limit else None
        self.node_limit = limits.node_limit
        self._limits_active = False

        result = SearchResult()
        root_moves = board.legal_moves()
        if not root_moves:
            return result
        result.move = root_moves[0]
        if len(root_moves) == 1:
            return result

        for depth in range(1, max(1, limits.max_depth) + 1):
            self._limits_active = depth > 1
            self._iter_best = None
            outcome = self._search_root(depth, root_moves, exact_root)
            if outcome is None:  # interrupted part-way through this iteration
                if self._iter_best is not None and not exact_root:
                    result.move, result.score = self._iter_best
                break
            move, score, scored = outcome
            result.move, result.score, result.depth = move, score, depth
            if exact_root:
                result.scored_moves = scored
                root_moves = [m for m, _ in sorted(scored, key=lambda ms: -ms[1])]
            else:
                root_moves.remove(move)
                root_moves.insert(0, move)

            elapsed = time.perf_counter() - start
            if on_iteration is not None:
                on_iteration(depth, score, self.nodes, elapsed, move)
            if not exact_root and abs(score) > MATE_BOUND and MATE - abs(score) <= depth:
                break  # a forced mate inside the horizon is already fully resolved
            if limits.time_limit and elapsed * 2.0 > limits.time_limit:
                break  # the next iteration would almost certainly not finish

        result.nodes = self.nodes
        result.elapsed = time.perf_counter() - start
        return result

    # --- Internals --------------------------------------------------------------------------

    def _budget_exceeded(self) -> bool:
        if self.stop_event is not None and self.stop_event.is_set():
            return True
        if not self._limits_active:
            return False
        if self.deadline is not None and time.perf_counter() >= self.deadline:
            return True
        return self.node_limit is not None and self.nodes >= self.node_limit

    def _search_root(self, depth: int, moves: List[int], exact: bool
                     ) -> Optional[Tuple[int, int, List[Tuple[int, int]]]]:
        board = self.board
        alpha = -INF
        best_score, best_move = -INF, 0
        scored: List[Tuple[int, int]] = []
        for i, move in enumerate(moves):
            board.make(move)
            if exact or i == 0:
                score = -self._search(depth - 1, -INF, INF if exact else -alpha, 1, True)
            else:
                score = -self._search(depth - 1, -alpha - 1, -alpha, 1, True)
                if score > alpha:
                    score = -self._search(depth - 1, -INF, -alpha, 1, True)
            board.unmake()
            if self.stopped:
                return None
            scored.append((move, score))
            if score > best_score:
                best_score, best_move = score, move
                if not exact:
                    alpha = score
                    self._iter_best = (move, score)
        return best_move, best_score, scored

    def _search(self, depth: int, alpha: int, beta: int, ply: int, allow_null: bool) -> int:
        self.nodes += 1
        if not (self.nodes & BUDGET_CHECK_MASK) and self._budget_exceeded():
            self.stopped = True
        if self.stopped:
            return 0

        board = self.board
        if board.halfmove >= 100 or board.is_repetition() or board.is_insufficient_material():
            return 0

        us = board.side
        them = us ^ 1
        in_check = board.is_attacked(board.king_sq[us], them)
        if in_check:
            depth += 1
        if ply >= MAX_PLY - 1:
            return evaluate(board)
        if depth <= 0:
            if self.quiescence_plies:
                return self._qsearch(alpha, beta, self.quiescence_plies)
            return evaluate(board)

        # Mate-distance pruning: no line can beat a mate we already know about.
        floor = ply - MATE
        if alpha < floor:
            alpha = floor
        ceiling = MATE - ply - 1
        if beta > ceiling:
            beta = ceiling
        if alpha >= beta:
            return alpha

        alpha_orig = alpha
        key = board.hash
        tt = self.tt
        entry = tt.get(key)
        tt_move = 0
        if entry is not None:
            tt_move = entry[3]
            if entry[0] >= depth:
                tt_score = entry[2]
                if tt_score > MATE_BOUND:
                    tt_score -= ply
                elif tt_score < -MATE_BOUND:
                    tt_score += ply
                flag = entry[1]
                if flag == TT_EXACT:
                    return tt_score
                if flag == TT_LOWER:
                    if tt_score > alpha:
                        alpha = tt_score
                elif tt_score < beta:
                    beta = tt_score
                if alpha >= beta:
                    return tt_score

        if not in_check and beta < MATE_BOUND:
            # Reverse futility pruning: far enough above beta that a quiet reply won't matter.
            if depth <= RFP_MAX_DEPTH:
                static = evaluate(board)
                if static - RFP_MARGIN * depth >= beta:
                    return static - RFP_MARGIN * depth
            # Null-move pruning: if passing the turn still beats beta, a real move will too.
            if (allow_null and depth >= NULL_MOVE_MIN_DEPTH
                    and board.has_non_pawn_material(us)):
                board.make_null()
                score = -self._search(depth - 3 - (depth >> 3), -beta, -beta + 1, ply + 1, False)
                board.unmake_null()
                if self.stopped:
                    return 0
                if score >= beta:
                    return beta if score > MATE_BOUND else score

        captures, quiets = board.generate()
        captures.sort(reverse=True)
        history = self.history
        if quiets:
            quiets.sort(key=history.__getitem__, reverse=True)
            killers = self.killers[ply]
            for k in (killers[1], killers[0]):
                if k and k in quiets:
                    quiets.remove(k)
                    quiets.insert(0, k)
        moves = [m & MOVE_MASK for m in captures]
        moves += quiets
        if tt_move:
            try:
                idx = moves.index(tt_move)
            except ValueError:
                idx = 0  # a hash collision: ignore the stored move rather than trust it
            if idx:
                moves.insert(0, moves.pop(idx))

        b = board.sq
        king_sq = board.king_sq
        best_score = -INF
        best_move = 0
        legal = 0
        for m in moves:
            is_quiet = not (b[(m >> 6) & 63] or (m >> 12) & 7 or ((m >> 16) & 7) == FLAG_EP)
            board.make(m)
            if board.is_attacked(king_sq[us], them):
                board.unmake()
                continue
            legal += 1
            if legal == 1:
                score = -self._search(depth - 1, -beta, -alpha, ply + 1, True)
            else:
                reduction = 0
                if (is_quiet and depth >= LMR_MIN_DEPTH and legal > LMR_FULL_DEPTH_MOVES
                        and not in_check and not board.is_attacked(king_sq[them], us)):
                    reduction = 1 if legal <= 8 or depth < 5 else 2
                score = -self._search(depth - 1 - reduction, -alpha - 1, -alpha, ply + 1, True)
                if score > alpha and reduction:
                    score = -self._search(depth - 1, -alpha - 1, -alpha, ply + 1, True)
                if alpha < score < beta:
                    score = -self._search(depth - 1, -beta, -alpha, ply + 1, True)
            board.unmake()
            if self.stopped:
                return 0
            if score > best_score:
                best_score, best_move = score, m
                if score > alpha:
                    alpha = score
                    if alpha >= beta:
                        if is_quiet:
                            ply_killers = self.killers[ply]
                            if ply_killers[0] != m:
                                ply_killers[1] = ply_killers[0]
                                ply_killers[0] = m
                            history[m] += depth * depth
                        break

        if legal == 0:
            return ply - MATE if in_check else 0

        if best_score >= beta:
            flag = TT_LOWER
        elif best_score > alpha_orig:
            flag = TT_EXACT
        else:
            flag = TT_UPPER
        stored = best_score
        if stored > MATE_BOUND:
            stored += ply
        elif stored < -MATE_BOUND:
            stored -= ply
        old = tt.get(key)
        if old is None or old[0] <= depth or old[4] != self.generation:
            tt[key] = (depth, flag, stored, best_move, self.generation)
        return best_score

    def _qsearch(self, alpha: int, beta: int, plies_left: int) -> int:
        """Resolve captures so a leaf is never scored in the middle of an exchange."""
        self.nodes += 1
        if not (self.nodes & BUDGET_CHECK_MASK) and self._budget_exceeded():
            self.stopped = True
        if self.stopped:
            return 0

        board = self.board
        stand_pat = evaluate(board)
        if stand_pat >= beta:
            return stand_pat
        if stand_pat > alpha:
            alpha = stand_pat
        if plies_left <= 0:
            return stand_pat

        us = board.side
        them = us ^ 1
        captures, _ = board.generate(captures_only=True)
        captures.sort(reverse=True)
        king_sq = board.king_sq
        best = stand_pat
        for m in captures:
            board.make(m & MOVE_MASK)
            if board.is_attacked(king_sq[us], them):
                board.unmake()
                continue
            score = -self._qsearch(-beta, -alpha, plies_left - 1)
            board.unmake()
            if self.stopped:
                return 0
            if score > best:
                best = score
                if score > alpha:
                    alpha = score
                    if alpha >= beta:
                        break
        return best
