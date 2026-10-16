"""
Static evaluation for the search.

Material and piece-square scores are maintained incrementally by SearchBoard (see the
PST_MG / PST_EG tables below, which hold signed White-minus-Black contributions), so a leaf
evaluation only has to blend them by game phase and add a few cheap structural terms.

Scores are centipawns. The piece-square tables are the widely published "simplified
evaluation function" tables (rank 8 first, from White's point of view).
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .pieces import (BISHOP, BLACK, BP, KING, KNIGHT, PAWN, QUEEN, ROOK, WHITE, WP)

PIECE_VALUE = {PAWN: 100, KNIGHT: 320, BISHOP: 330, ROOK: 500, QUEEN: 900, KING: 0}

# Game phase: how much non-pawn material is left (24 = full set, 0 = bare kings and pawns).
PHASE_WEIGHT = [0, 0, 1, 1, 2, 4, 0] + [0] * 8
MAX_PHASE = 24

TEMPO_BONUS = 10
BISHOP_PAIR_MG, BISHOP_PAIR_EG = 30, 45

_PAWN = [
    [0,   0,   0,   0,   0,   0,   0,   0],
    [50,  50,  50,  50,  50,  50,  50,  50],
    [10,  10,  20,  30,  30,  20,  10,  10],
    [5,   5,   10,  25,  25,  10,  5,   5],
    [0,   0,   0,   20,  20,  0,   0,   0],
    [5,   -5,  -10, 0,   0,   -10, -5,  5],
    [5,   10,  10,  -20, -20, 10,  10,  5],
    [0,   0,   0,   0,   0,   0,   0,   0],
]
_KNIGHT = [
    [-50, -40, -30, -30, -30, -30, -40, -50],
    [-40, -20, 0,   0,   0,   0,   -20, -40],
    [-30, 0,   10,  15,  15,  10,  0,   -30],
    [-30, 5,   15,  20,  20,  15,  5,   -30],
    [-30, 0,   15,  20,  20,  15,  0,   -30],
    [-30, 5,   10,  15,  15,  10,  5,   -30],
    [-40, -20, 0,   5,   5,   0,   -20, -40],
    [-50, -40, -30, -30, -30, -30, -40, -50],
]
_BISHOP = [
    [-20, -10, -10, -10, -10, -10, -10, -20],
    [-10, 0,   0,   0,   0,   0,   0,   -10],
    [-10, 0,   5,   10,  10,  5,   0,   -10],
    [-10, 5,   5,   10,  10,  5,   5,   -10],
    [-10, 0,   10,  10,  10,  10,  0,   -10],
    [-10, 10,  10,  10,  10,  10,  10,  -10],
    [-10, 5,   0,   0,   0,   0,   5,   -10],
    [-20, -10, -10, -10, -10, -10, -10, -20],
]
_ROOK = [
    [0,  0,  0,  0,  0,  0,  0,  0],
    [5,  10, 10, 10, 10, 10, 10, 5],
    [-5, 0,  0,  0,  0,  0,  0,  -5],
    [-5, 0,  0,  0,  0,  0,  0,  -5],
    [-5, 0,  0,  0,  0,  0,  0,  -5],
    [-5, 0,  0,  0,  0,  0,  0,  -5],
    [-5, 0,  0,  0,  0,  0,  0,  -5],
    [0,  0,  0,  5,  5,  0,  0,  0],
]
_QUEEN = [
    [-20, -10, -10, -5, -5, -10, -10, -20],
    [-10, 0,   0,   0,  0,  0,   0,   -10],
    [-10, 0,   5,   5,  5,  5,   0,   -10],
    [-5,  0,   5,   5,  5,  5,   0,   -5],
    [0,   0,   5,   5,  5,  5,   0,   -5],
    [-10, 5,   5,   5,  5,  5,   0,   -10],
    [-10, 0,   5,   0,  0,  0,   0,   -10],
    [-20, -10, -10, -5, -5, -10, -10, -20],
]
_KING_MG = [
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-20, -30, -30, -40, -40, -30, -30, -20],
    [-10, -20, -20, -20, -20, -20, -20, -10],
    [20,  20,  0,   0,   0,   0,   20,  20],
    [20,  30,  10,  0,   0,   10,  30,  20],
]
_KING_EG = [
    [-50, -40, -30, -20, -20, -30, -40, -50],
    [-30, -20, -10, 0,   0,   -10, -20, -30],
    [-30, -10, 20,  30,  30,  20,  -10, -30],
    [-30, -10, 30,  40,  40,  30,  -10, -30],
    [-30, -10, 30,  40,  40,  30,  -10, -30],
    [-30, -10, 20,  30,  30,  20,  -10, -30],
    [-30, -30, 0,   0,   0,   0,   -30, -30],
    [-50, -30, -30, -30, -30, -30, -30, -50],
]


def _flat(table: List[List[int]]) -> List[int]:
    return [v for row in table for v in row]


def _build_piece_square_tables() -> Tuple[List[List[int]], List[List[int]]]:
    """Signed per-piece-code tables: White pieces add, Black pieces (mirrored) subtract."""
    mg_tables = {PAWN: _PAWN, KNIGHT: _KNIGHT, BISHOP: _BISHOP, ROOK: _ROOK,
                 QUEEN: _QUEEN, KING: _KING_MG}
    eg_tables = dict(mg_tables)
    eg_tables[KING] = _KING_EG

    mg: List[List[int]] = [[0] * 64 for _ in range(15)]
    eg: List[List[int]] = [[0] * 64 for _ in range(15)]
    for piece_type in range(PAWN, KING + 1):
        value = PIECE_VALUE[piece_type]
        mg_flat, eg_flat = _flat(mg_tables[piece_type]), _flat(eg_tables[piece_type])
        for sq in range(64):
            mg[piece_type][sq] = value + mg_flat[sq]
            eg[piece_type][sq] = value + eg_flat[sq]
            mirrored = sq ^ 56  # flip the rank, keep the file
            mg[piece_type + 8][sq] = -(value + mg_flat[mirrored])
            eg[piece_type + 8][sq] = -(value + eg_flat[mirrored])
    return mg, eg


PST_MG, PST_EG = _build_piece_square_tables()

# Distance of each square from the centre (0 for d4/e4/d5/e5), used to herd a lone king.
CENTER_DISTANCE = [max(3 - (sq >> 3), (sq >> 3) - 4) + max(3 - (sq & 7), (sq & 7) - 4)
                   for sq in range(64)]

# Bonus for a passed pawn, indexed by how many ranks it has advanced from its own back rank.
PASSED_MG = (0, 5, 10, 20, 35, 60, 100, 0)
PASSED_EG = (0, 10, 20, 40, 70, 120, 200, 0)
ISOLATED_MG, ISOLATED_EG = 12, 18
DOUBLED_MG, DOUBLED_EG = 12, 20

# Only try to mate a lone king once the game is nearly bare and the lead is decisive.
MOPUP_PHASE_MAX = 8
MOPUP_MIN_LEAD = 450

_PAWN_CACHE: Dict[int, Tuple[int, int]] = {}
_PAWN_CACHE_MAX = 60_000


def _pawn_terms(board) -> Tuple[int, int]:
    """White-minus-Black (mg, eg) pawn-structure score, cached on the pawn-only hash."""
    key = board.pawn_key
    hit = _PAWN_CACHE.get(key)
    if hit is not None:
        return hit

    squares = board.sq
    w_count = [0] * 8
    b_count = [0] * 8
    w_max_row = [-1] * 8   # most-advanced White pawn of a file, from Black's point of view
    b_min_row = [8] * 8    # most-advanced Black pawn of a file, from White's point of view
    w_pawns: List[Tuple[int, int]] = []
    b_pawns: List[Tuple[int, int]] = []
    for sq in range(64):
        piece = squares[sq]
        if piece == WP:
            row, col = sq >> 3, sq & 7
            w_count[col] += 1
            w_pawns.append((row, col))
            if row > w_max_row[col]:
                w_max_row[col] = row
        elif piece == BP:
            row, col = sq >> 3, sq & 7
            b_count[col] += 1
            b_pawns.append((row, col))
            if row < b_min_row[col]:
                b_min_row[col] = row

    mg = eg = 0
    for row, col in w_pawns:
        if (col == 0 or not w_count[col - 1]) and (col == 7 or not w_count[col + 1]):
            mg -= ISOLATED_MG
            eg -= ISOLATED_EG
        passed = True
        for c in range(max(0, col - 1), min(7, col + 1) + 1):
            if b_min_row[c] < row:
                passed = False
                break
        if passed:
            advance = 7 - row
            mg += PASSED_MG[advance]
            eg += PASSED_EG[advance]
    for row, col in b_pawns:
        if (col == 0 or not b_count[col - 1]) and (col == 7 or not b_count[col + 1]):
            mg += ISOLATED_MG
            eg += ISOLATED_EG
        passed = True
        for c in range(max(0, col - 1), min(7, col + 1) + 1):
            if w_max_row[c] > row:
                passed = False
                break
        if passed:
            mg -= PASSED_MG[row]
            eg -= PASSED_EG[row]
    for col in range(8):
        if w_count[col] > 1:
            mg -= DOUBLED_MG * (w_count[col] - 1)
            eg -= DOUBLED_EG * (w_count[col] - 1)
        if b_count[col] > 1:
            mg += DOUBLED_MG * (b_count[col] - 1)
            eg += DOUBLED_EG * (b_count[col] - 1)

    if len(_PAWN_CACHE) >= _PAWN_CACHE_MAX:
        _PAWN_CACHE.clear()
    result = (mg, eg)
    _PAWN_CACHE[key] = result
    return result


def evaluate(board) -> int:
    """Score the position in centipawns from the point of view of the side to move."""
    phase = board.phase
    if phase > MAX_PHASE:
        phase = MAX_PHASE

    pawn_mg, pawn_eg = _pawn_terms(board)
    mg = board.mg + pawn_mg
    eg = board.eg + pawn_eg

    bishops = board.bishops
    if bishops[WHITE] >= 2:
        mg += BISHOP_PAIR_MG
        eg += BISHOP_PAIR_EG
    if bishops[BLACK] >= 2:
        mg -= BISHOP_PAIR_MG
        eg -= BISHOP_PAIR_EG

    score = (mg * phase + eg * (MAX_PHASE - phase)) // MAX_PHASE

    if phase <= MOPUP_PHASE_MAX and (score >= MOPUP_MIN_LEAD or score <= -MOPUP_MIN_LEAD):
        if score > 0:
            winner, loser = board.king_sq[WHITE], board.king_sq[BLACK]
        else:
            winner, loser = board.king_sq[BLACK], board.king_sq[WHITE]
        closeness = 14 - abs((winner >> 3) - (loser >> 3)) - abs((winner & 7) - (loser & 7))
        bonus = 10 * CENTER_DISTANCE[loser] + 4 * closeness
        score += bonus if score > 0 else -bonus

    if board.side == BLACK:
        score = -score
    return score + TEMPO_BONUS
