"""
Piece and square vocabulary shared by the AI modules.

Squares use the same indexing as ChessEngine: ``sq = row * 8 + col`` with row 0 = rank 8,
so a8 = 0, h8 = 7, a1 = 56 and h1 = 63. Piece codes are the piece type for White (1-6)
and the piece type + 8 for Black (9-14); 0 is an empty square.
"""

from __future__ import annotations

WHITE, BLACK = 0, 1

EMPTY = 0
PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING = 1, 2, 3, 4, 5, 6

WP, WN, WB, WR, WQ, WK = 1, 2, 3, 4, 5, 6
BP, BN, BB, BR, BQ, BK = 9, 10, 11, 12, 13, 14

FILES = "abcdefgh"

_TYPE_FROM_LETTER = {"P": PAWN, "N": KNIGHT, "B": BISHOP, "R": ROOK, "Q": QUEEN, "K": KING}
_LETTER_FROM_TYPE = {v: k for k, v in _TYPE_FROM_LETTER.items()}


def piece_code(engine_piece: str) -> int:
    """'wP' -> 1, 'bK' -> 14, '--' -> 0."""
    if engine_piece == "--":
        return EMPTY
    return _TYPE_FROM_LETTER[engine_piece[1]] + (8 if engine_piece[0] == "b" else 0)


def engine_piece(code: int) -> str:
    """Inverse of :func:`piece_code`."""
    if code == EMPTY:
        return "--"
    return ("b" if code >> 3 else "w") + _LETTER_FROM_TYPE[code & 7]


def type_from_letter(letter: str) -> int:
    return _TYPE_FROM_LETTER[letter.upper()]


def letter_from_type(piece_type: int) -> str:
    return _LETTER_FROM_TYPE[piece_type]


def square_name(sq: int) -> str:
    return f"{FILES[sq & 7]}{8 - (sq >> 3)}"


def square_from_name(name: str) -> int:
    if len(name) != 2 or name[0] not in FILES or name[1] not in "12345678":
        raise ValueError(f"invalid square: {name!r}")
    return (8 - int(name[1])) * 8 + FILES.index(name[0])
