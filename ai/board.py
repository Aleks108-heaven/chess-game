"""
SearchBoard: a compact mailbox position built for fast search.

ChessEngine is written for clarity and drives the UI; it regenerates every opponent move to
test a single square, which is far too slow to search with (roughly 130 nodes/s). SearchBoard
trades that clarity for speed:

* pseudo-legal move generation from precomputed target/ray tables, with the legality test done
  by a single "is my king attacked?" probe after the move is made;
* make/unmake that incrementally maintains the Zobrist hash, the material + piece-square
  score, the game phase and a pawn-only hash;
* moves packed into plain ints.

Move encoding (ints)::

    bits  0-5   from square
    bits  6-11  to square
    bits 12-14  promotion piece type (0 = none)
    bits 16-18  flag (FLAG_EP, FLAG_CASTLE, FLAG_DOUBLE)
    bits 20+    ordering score, only on moves returned by generate() (strip with MOVE_MASK)
"""

from __future__ import annotations

import random
from typing import List, Optional, Tuple

from .evaluation import PHASE_WEIGHT, PST_EG, PST_MG
from .pieces import (BISHOP, BLACK, BK, BP, BR, EMPTY, KING, KNIGHT, PAWN, QUEEN, ROOK, WHITE,
                     WK, WP, WR, letter_from_type, piece_code, square_from_name, square_name,
                     type_from_letter)

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

CASTLE_WK, CASTLE_WQ, CASTLE_BK, CASTLE_BQ = 1, 2, 4, 8

FLAG_EP, FLAG_CASTLE, FLAG_DOUBLE = 1, 2, 4

MOVE_MASK = (1 << 20) - 1
SCORE_SHIFT = 20

_FEN_PIECES = {"P": 1, "N": 2, "B": 3, "R": 4, "Q": 5, "K": 6,
               "p": 9, "n": 10, "b": 11, "r": 12, "q": 13, "k": 14}
_FEN_LETTERS = {v: k for k, v in _FEN_PIECES.items()}


# --- Precomputed tables -------------------------------------------------------------------

def _build_tables():
    knight, king, rook_rays, bishop_rays = [], [], [], []
    pawn_attacks = ([], [])  # [WHITE][sq] / [BLACK][sq]: squares a pawn standing on sq attacks

    def on_board(r, c):
        return 0 <= r < 8 and 0 <= c < 8

    def ray(r, c, dr, dc):
        out = []
        r, c = r + dr, c + dc
        while on_board(r, c):
            out.append(r * 8 + c)
            r, c = r + dr, c + dc
        return tuple(out)

    for sq in range(64):
        r, c = divmod(sq, 8)
        knight.append(tuple(
            (r + dr) * 8 + (c + dc)
            for dr, dc in ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1))
            if on_board(r + dr, c + dc)))
        king.append(tuple(
            (r + dr) * 8 + (c + dc)
            for dr in (-1, 0, 1) for dc in (-1, 0, 1)
            if (dr or dc) and on_board(r + dr, c + dc)))
        rook_rays.append(tuple(ray(r, c, dr, dc) for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))))
        bishop_rays.append(tuple(ray(r, c, dr, dc) for dr, dc in ((-1, -1), (-1, 1), (1, -1), (1, 1))))
        pawn_attacks[WHITE].append(tuple(
            (r - 1) * 8 + (c + dc) for dc in (-1, 1) if on_board(r - 1, c + dc)))
        pawn_attacks[BLACK].append(tuple(
            (r + 1) * 8 + (c + dc) for dc in (-1, 1) if on_board(r + 1, c + dc)))
    return knight, king, rook_rays, bishop_rays, pawn_attacks


KNIGHT_TARGETS, KING_TARGETS, ROOK_RAYS, BISHOP_RAYS, PAWN_ATTACKS = _build_tables()

# Castling rights that survive a move touching a given square (from or to).
CASTLE_MASK = [15] * 64
CASTLE_MASK[56] &= ~CASTLE_WQ
CASTLE_MASK[63] &= ~CASTLE_WK
CASTLE_MASK[60] &= ~(CASTLE_WK | CASTLE_WQ)
CASTLE_MASK[0] &= ~CASTLE_BQ
CASTLE_MASK[7] &= ~CASTLE_BK
CASTLE_MASK[4] &= ~(CASTLE_BK | CASTLE_BQ)

_zrng = random.Random(0x5EA4C8)  # fixed seed: hashes are reproducible across runs
ZOB_PIECE = [[_zrng.getrandbits(64) for _ in range(64)] for _ in range(15)]
ZOB_CASTLE = [_zrng.getrandbits(64) for _ in range(16)]
ZOB_EP = [_zrng.getrandbits(64) for _ in range(64)] + [0]  # ZOB_EP[-1] (no ep square) is 0
ZOB_SIDE = _zrng.getrandbits(64)

# Ordering score for a capture: most valuable victim first, least valuable attacker first.
_PROMOTION_SCORE = 50


def _capture_score(victim: int, attacker: int) -> int:
    return (victim * 8 + (7 - attacker)) << SCORE_SHIFT


class InvalidPositionError(ValueError):
    """Raised for a malformed FEN string."""


class SearchBoard:
    """A chess position with fast make/unmake. Squares are indexed row * 8 + col, a8 = 0."""

    __slots__ = ("sq", "side", "castling", "ep", "halfmove", "fullmove", "king_sq", "hash",
                 "mg", "eg", "phase", "pawn_key", "bishops", "stack", "keys")

    def __init__(self) -> None:
        self.sq: List[int] = [EMPTY] * 64
        self.side = WHITE
        self.castling = 0
        self.ep = -1
        self.halfmove = 0
        self.fullmove = 1
        self.king_sq = [60, 4]
        self.hash = 0
        self.mg = 0
        self.eg = 0
        self.phase = 0
        self.pawn_key = 0
        self.bishops = [0, 0]
        self.stack: List[tuple] = []
        self.keys: List[int] = []

    # --- Construction ---------------------------------------------------------------------

    @classmethod
    def start(cls) -> "SearchBoard":
        return cls.from_fen(START_FEN)

    @classmethod
    def from_fen(cls, fen: str) -> "SearchBoard":
        parts = fen.split()
        if len(parts) < 4:
            raise InvalidPositionError(f"FEN needs at least 4 fields: {fen!r}")
        placement, side, castling, ep = parts[:4]
        board = cls()

        rows = placement.split("/")
        if len(rows) != 8:
            raise InvalidPositionError(f"FEN placement needs 8 ranks: {placement!r}")
        for row, text in enumerate(rows):
            col = 0
            for ch in text:
                if ch.isdigit():
                    col += int(ch)
                elif ch in _FEN_PIECES:
                    if col > 7:
                        raise InvalidPositionError(f"rank overflows 8 files: {text!r}")
                    board.sq[row * 8 + col] = _FEN_PIECES[ch]
                    col += 1
                else:
                    raise InvalidPositionError(f"unknown FEN character {ch!r}")
            if col != 8:
                raise InvalidPositionError(f"rank does not have 8 files: {text!r}")

        if side not in ("w", "b"):
            raise InvalidPositionError(f"bad side to move: {side!r}")
        board.side = WHITE if side == "w" else BLACK

        for ch in ("" if castling == "-" else castling):
            bit = {"K": CASTLE_WK, "Q": CASTLE_WQ, "k": CASTLE_BK, "q": CASTLE_BQ}.get(ch)
            if bit is None:
                raise InvalidPositionError(f"bad castling field: {castling!r}")
            board.castling |= bit
        board.ep = -1 if ep == "-" else square_from_name(ep)
        board.halfmove = int(parts[4]) if len(parts) > 4 else 0
        board.fullmove = int(parts[5]) if len(parts) > 5 else 1

        board._finish_setup()
        return board

    def _finish_setup(self) -> None:
        """Validate the position and compute every incremental field from scratch."""
        white_kings = [s for s in range(64) if self.sq[s] == WK]
        black_kings = [s for s in range(64) if self.sq[s] == BK]
        if len(white_kings) != 1 or len(black_kings) != 1:
            raise InvalidPositionError("each side needs exactly one king")
        self.king_sq = [white_kings[0], black_kings[0]]
        # Drop castling rights the pieces cannot back up.
        for bit, king, rook, king_sq, rook_sq in (
                (CASTLE_WK, WK, WR, 60, 63), (CASTLE_WQ, WK, WR, 60, 56),
                (CASTLE_BK, BK, BR, 4, 7), (CASTLE_BQ, BK, BR, 4, 0)):
            if self.castling & bit and not (self.sq[king_sq] == king and self.sq[rook_sq] == rook):
                self.castling &= ~bit
        if self.ep != -1:
            # An en passant square is only meaningful on the 3rd/6th rank behind a pawn.
            ok = (self.ep >> 3 == 2 and self.side == WHITE and self.sq[self.ep + 8] == BP) or \
                 (self.ep >> 3 == 5 and self.side == BLACK and self.sq[self.ep - 8] == WP)
            if not ok:
                self.ep = -1
        self.recompute()
        self.stack = []
        self.keys = [self.hash]

    def recompute(self) -> None:
        """Rebuild hash, eval terms, phase and counters from the squares (used by tests too)."""
        h = 0
        mg = eg = phase = pawn_key = 0
        bishops = [0, 0]
        for s in range(64):
            p = self.sq[s]
            if not p:
                continue
            h ^= ZOB_PIECE[p][s]
            mg += PST_MG[p][s]
            eg += PST_EG[p][s]
            phase += PHASE_WEIGHT[p & 7]
            if p & 7 == PAWN:
                pawn_key ^= ZOB_PIECE[p][s]
            elif p & 7 == BISHOP:
                bishops[p >> 3] += 1
        h ^= ZOB_CASTLE[self.castling] ^ self._ep_hash()
        if self.side == BLACK:
            h ^= ZOB_SIDE
        self.hash, self.mg, self.eg, self.phase = h, mg, eg, phase
        self.pawn_key, self.bishops = pawn_key, bishops

    @classmethod
    def from_engine(cls, engine) -> "SearchBoard":
        """Snapshot a ChessEngine, including enough history to see repetitions.

        The move log is replayed from the standard start so the position keys line up with
        the game; if the replay does not reproduce the engine's board (it always should) the
        position is taken from the engine's state alone, with no repetition history.
        """
        replayed = cls._replay(engine)
        if replayed is not None:
            return replayed
        board = cls()
        for row in range(8):
            for col in range(8):
                board.sq[row * 8 + col] = piece_code(engine.board[row][col])
        board.side = WHITE if engine.white_to_move else BLACK
        board.castling = ((CASTLE_WK if engine.white_castle_kingside else 0)
                          | (CASTLE_WQ if engine.white_castle_queenside else 0)
                          | (CASTLE_BK if engine.black_castle_kingside else 0)
                          | (CASTLE_BQ if engine.black_castle_queenside else 0))
        ep = engine.enpassant_possible
        board.ep = -1 if ep is None else ep[0] * 8 + ep[1]
        board.halfmove = engine.halfmove_clock
        board._finish_setup()
        return board

    @classmethod
    def _replay(cls, engine) -> Optional["SearchBoard"]:
        board = cls.start()
        try:
            for move in engine.move_log:
                board.make(board.move_from_engine(move))
        except (KeyError, IndexError, ValueError):
            return None
        for row in range(8):
            for col in range(8):
                if board.sq[row * 8 + col] != piece_code(engine.board[row][col]):
                    return None
        if board.side != (WHITE if engine.white_to_move else BLACK):
            return None
        return board

    def move_from_engine(self, move) -> int:
        """Pack a ChessEngine Move into an int move for this board."""
        frm = move.start_row * 8 + move.start_col
        to = move.end_row * 8 + move.end_col
        promo = type_from_letter(move.promotion_piece) if move.is_pawn_promotion else 0
        flag = 0
        if move.is_enpassant:
            flag = FLAG_EP
        elif move.is_castle:
            flag = FLAG_CASTLE
        elif move.piece_moved[1] == "P" and abs(move.start_row - move.end_row) == 2:
            flag = FLAG_DOUBLE
        return frm | (to << 6) | (promo << 12) | (flag << 16)

    # --- Text conversion --------------------------------------------------------------------

    def to_fen(self) -> str:
        rows = []
        for row in range(8):
            text, empty = "", 0
            for col in range(8):
                p = self.sq[row * 8 + col]
                if not p:
                    empty += 1
                    continue
                if empty:
                    text += str(empty)
                    empty = 0
                text += _FEN_LETTERS[p]
            rows.append(text + (str(empty) if empty else ""))
        castling = "".join(ch for bit, ch in ((CASTLE_WK, "K"), (CASTLE_WQ, "Q"),
                                              (CASTLE_BK, "k"), (CASTLE_BQ, "q"))
                           if self.castling & bit) or "-"
        ep = "-" if self.ep == -1 else square_name(self.ep)
        return (f"{'/'.join(rows)} {'w' if self.side == WHITE else 'b'} {castling} {ep} "
                f"{self.halfmove} {self.fullmove}")

    @staticmethod
    def move_to_uci(move: int) -> str:
        text = square_name(move & 63) + square_name((move >> 6) & 63)
        promo = (move >> 12) & 7
        return text + letter_from_type(promo).lower() if promo else text

    def move_from_uci(self, text: str) -> int:
        """Find the legal move written like 'e2e4' or 'e7e8q'; ValueError if there is none."""
        for move in self.legal_moves():
            if self.move_to_uci(move) == text:
                return move
        raise ValueError(f"illegal move for this position: {text!r}")

    def copy(self) -> "SearchBoard":
        clone = SearchBoard()
        clone.sq = list(self.sq)
        clone.side, clone.castling, clone.ep = self.side, self.castling, self.ep
        clone.halfmove, clone.fullmove = self.halfmove, self.fullmove
        clone.king_sq = list(self.king_sq)
        clone.hash, clone.mg, clone.eg, clone.phase = self.hash, self.mg, self.eg, self.phase
        clone.pawn_key, clone.bishops = self.pawn_key, list(self.bishops)
        clone.stack = list(self.stack)
        clone.keys = list(self.keys)
        return clone

    def __repr__(self) -> str:
        return f"SearchBoard({self.to_fen()!r})"

    def _ep_hash(self) -> int:
        """Zobrist term for the en passant square, counted only if a pawn could capture there.

        Two positions that differ only by a double push nobody can answer are the same
        position for repetition and book purposes, so they must hash alike.
        """
        ep = self.ep
        if ep == -1:
            return 0
        b = self.sq
        if self.side == WHITE:
            pawn, behind = WP, ep + 8
        else:
            pawn, behind = BP, ep - 8
        col = ep & 7
        if (col > 0 and b[behind - 1] == pawn) or (col < 7 and b[behind + 1] == pawn):
            return ZOB_EP[ep]
        return 0

    # --- Attacks ----------------------------------------------------------------------------

    def is_attacked(self, sq: int, by: int) -> bool:
        """True if any piece of colour ``by`` attacks ``sq``."""
        b = self.sq
        shift = by << 3
        pawn = PAWN | shift
        for s in PAWN_ATTACKS[by ^ 1][sq]:
            if b[s] == pawn:
                return True
        knight = KNIGHT | shift
        for s in KNIGHT_TARGETS[sq]:
            if b[s] == knight:
                return True
        king = KING | shift
        for s in KING_TARGETS[sq]:
            if b[s] == king:
                return True
        rook, queen, bishop = ROOK | shift, QUEEN | shift, BISHOP | shift
        for line in ROOK_RAYS[sq]:
            for s in line:
                p = b[s]
                if p:
                    if p == rook or p == queen:
                        return True
                    break
        for line in BISHOP_RAYS[sq]:
            for s in line:
                p = b[s]
                if p:
                    if p == bishop or p == queen:
                        return True
                    break
        return False

    def in_check(self) -> bool:
        side = self.side
        return self.is_attacked(self.king_sq[side], side ^ 1)

    # --- Move generation --------------------------------------------------------------------

    def generate(self, captures_only: bool = False) -> Tuple[List[int], List[int]]:
        """Pseudo-legal moves as (captures, quiets).

        Captures (and queen promotions) carry an ordering score in the high bits; strip it
        with ``move & MOVE_MASK``. The caller must reject moves that leave its king attacked.
        With ``captures_only`` the quiet list is empty.
        """
        b = self.sq
        us = self.side
        them = us ^ 1
        captures: List[int] = []
        quiets: List[int] = []
        cap = captures.append
        quiet = quiets.append
        ep = self.ep

        if us == WHITE:
            push, start_lo, start_hi, promo_lo = -8, 48, 55, 8   # White promotes from row 1
        else:
            push, start_lo, start_hi, promo_lo = 8, 8, 15, 48    # Black promotes from row 6
        promo_hi = promo_lo + 7
        promotion_bonus = _PROMOTION_SCORE << SCORE_SHIFT

        for sq in range(64):
            p = b[sq]
            if not p or (p >> 3) != us:
                continue
            kind = p & 7

            if kind == PAWN:
                promoting = promo_lo <= sq <= promo_hi
                to = sq + push
                if b[to] == 0:
                    if promoting:
                        cap(sq | (to << 6) | (QUEEN << 12) | promotion_bonus)
                        if not captures_only:
                            quiet(sq | (to << 6) | (ROOK << 12))
                            quiet(sq | (to << 6) | (BISHOP << 12))
                            quiet(sq | (to << 6) | (KNIGHT << 12))
                    elif not captures_only:
                        quiet(sq | (to << 6))
                        if start_lo <= sq <= start_hi and b[to + push] == 0:
                            quiet(sq | ((to + push) << 6) | (FLAG_DOUBLE << 16))
                for to in PAWN_ATTACKS[us][sq]:
                    t = b[to]
                    if t and (t >> 3) != us:
                        score = _capture_score(t & 7, PAWN)
                        if promoting:
                            cap(sq | (to << 6) | (QUEEN << 12) | (score + promotion_bonus))
                            if not captures_only:
                                quiet(sq | (to << 6) | (ROOK << 12))
                                quiet(sq | (to << 6) | (BISHOP << 12))
                                quiet(sq | (to << 6) | (KNIGHT << 12))
                        else:
                            cap(sq | (to << 6) | score)
                    elif to == ep:
                        cap(sq | (to << 6) | (FLAG_EP << 16) | _capture_score(PAWN, PAWN))

            elif kind == KNIGHT:
                for to in KNIGHT_TARGETS[sq]:
                    t = b[to]
                    if not t:
                        if not captures_only:
                            quiet(sq | (to << 6))
                    elif (t >> 3) != us:
                        cap(sq | (to << 6) | _capture_score(t & 7, KNIGHT))

            elif kind == KING:
                for to in KING_TARGETS[sq]:
                    t = b[to]
                    if not t:
                        if not captures_only:
                            quiet(sq | (to << 6))
                    elif (t >> 3) != us:
                        cap(sq | (to << 6) | _capture_score(t & 7, KING))

            else:
                if kind != BISHOP:
                    for line in ROOK_RAYS[sq]:
                        for to in line:
                            t = b[to]
                            if not t:
                                if not captures_only:
                                    quiet(sq | (to << 6))
                            else:
                                if (t >> 3) != us:
                                    cap(sq | (to << 6) | _capture_score(t & 7, kind))
                                break
                if kind != ROOK:
                    for line in BISHOP_RAYS[sq]:
                        for to in line:
                            t = b[to]
                            if not t:
                                if not captures_only:
                                    quiet(sq | (to << 6))
                            else:
                                if (t >> 3) != us:
                                    cap(sq | (to << 6) | _capture_score(t & 7, kind))
                                break

        if not captures_only and self.castling:
            self._generate_castles(quiet, us, them)
        return captures, quiets

    def _generate_castles(self, quiet, us: int, them: int) -> None:
        b = self.sq
        rights = self.castling
        if us == WHITE:
            if rights & CASTLE_WK and not b[61] and not b[62]:
                if not self.is_attacked(60, them) and not self.is_attacked(61, them) \
                        and not self.is_attacked(62, them):
                    quiet(60 | (62 << 6) | (FLAG_CASTLE << 16))
            if rights & CASTLE_WQ and not b[59] and not b[58] and not b[57]:
                if not self.is_attacked(60, them) and not self.is_attacked(59, them) \
                        and not self.is_attacked(58, them):
                    quiet(60 | (58 << 6) | (FLAG_CASTLE << 16))
        else:
            if rights & CASTLE_BK and not b[5] and not b[6]:
                if not self.is_attacked(4, them) and not self.is_attacked(5, them) \
                        and not self.is_attacked(6, them):
                    quiet(4 | (6 << 6) | (FLAG_CASTLE << 16))
            if rights & CASTLE_BQ and not b[3] and not b[2] and not b[1]:
                if not self.is_attacked(4, them) and not self.is_attacked(3, them) \
                        and not self.is_attacked(2, them):
                    quiet(4 | (2 << 6) | (FLAG_CASTLE << 16))

    def legal_moves(self) -> List[int]:
        """Every legal move, captures first, with ordering scores stripped."""
        us = self.side
        them = us ^ 1
        captures, quiets = self.generate()
        captures.sort(reverse=True)
        legal = []
        for move in captures + quiets:
            move &= MOVE_MASK
            self.make(move)
            if not self.is_attacked(self.king_sq[us], them):
                legal.append(move)
            self.unmake()
        return legal

    # --- Make / unmake ----------------------------------------------------------------------

    def make(self, move: int) -> None:
        b = self.sq
        frm = move & 63
        to = (move >> 6) & 63
        promo = (move >> 12) & 7
        flag = (move >> 16) & 7
        us = self.side
        piece = b[frm]

        if flag == FLAG_EP:
            captured = PAWN | ((us ^ 1) << 3)
        else:
            captured = b[to]
        self.stack.append((move, captured, self.castling, self.ep, self.halfmove, self.hash,
                           self.mg, self.eg, self.phase, self.pawn_key, self.fullmove))

        zp = ZOB_PIECE
        mgt, egt = PST_MG, PST_EG
        h = self.hash ^ ZOB_SIDE
        if self.ep != -1:
            h ^= self._ep_hash()  # the old term, evaluated before the board changes
        mg, eg = self.mg, self.eg
        pk = self.pawn_key
        ptype = piece & 7

        # Lift the moving piece.
        b[frm] = EMPTY
        h ^= zp[piece][frm]
        mg -= mgt[piece][frm]
        eg -= egt[piece][frm]

        # Remove whatever it captures.
        if flag == FLAG_EP:
            cap_sq = to + 8 if us == WHITE else to - 8
            b[cap_sq] = EMPTY
            h ^= zp[captured][cap_sq]
            mg -= mgt[captured][cap_sq]
            eg -= egt[captured][cap_sq]
            pk ^= zp[captured][cap_sq]
        elif captured:
            h ^= zp[captured][to]
            mg -= mgt[captured][to]
            eg -= egt[captured][to]
            ctype = captured & 7
            if ctype == PAWN:
                pk ^= zp[captured][to]
            else:
                self.phase -= PHASE_WEIGHT[ctype]
                if ctype == BISHOP:
                    self.bishops[captured >> 3] -= 1

        # Drop the piece (or its promotion) on the target square.
        if promo:
            new_piece = promo | (us << 3)
            b[to] = new_piece
            h ^= zp[new_piece][to]
            mg += mgt[new_piece][to]
            eg += egt[new_piece][to]
            pk ^= zp[piece][frm]
            self.phase += PHASE_WEIGHT[promo]
            if promo == BISHOP:
                self.bishops[us] += 1
        else:
            b[to] = piece
            h ^= zp[piece][to]
            mg += mgt[piece][to]
            eg += egt[piece][to]
            if ptype == PAWN:
                pk ^= zp[piece][frm] ^ zp[piece][to]
            elif ptype == KING:
                self.king_sq[us] = to

        if flag == FLAG_CASTLE:
            if to > frm:
                rook_from, rook_to = to + 1, to - 1
            else:
                rook_from, rook_to = to - 2, to + 1
            rook = ROOK | (us << 3)
            b[rook_from] = EMPTY
            b[rook_to] = rook
            h ^= zp[rook][rook_from] ^ zp[rook][rook_to]
            mg += mgt[rook][rook_to] - mgt[rook][rook_from]
            eg += egt[rook][rook_to] - egt[rook][rook_from]

        old_rights = self.castling
        new_rights = old_rights & CASTLE_MASK[frm] & CASTLE_MASK[to]
        if new_rights != old_rights:
            h ^= ZOB_CASTLE[old_rights] ^ ZOB_CASTLE[new_rights]
            self.castling = new_rights

        if ptype == PAWN or captured:
            self.halfmove = 0
        else:
            self.halfmove += 1
        if us == BLACK:
            self.fullmove += 1

        self.side = us ^ 1
        if flag == FLAG_DOUBLE:
            self.ep = (frm + to) >> 1
            h ^= self._ep_hash()  # evaluated for the opponent, who is now to move
        else:
            self.ep = -1
        self.hash = h
        self.mg, self.eg, self.pawn_key = mg, eg, pk
        self.keys.append(h)

    def unmake(self) -> None:
        (move, captured, castling, ep, halfmove, h, mg, eg, phase, pk,
         fullmove) = self.stack.pop()
        self.keys.pop()
        b = self.sq
        frm = move & 63
        to = (move >> 6) & 63
        promo = (move >> 12) & 7
        flag = (move >> 16) & 7
        us = self.side ^ 1
        self.side = us

        if promo:
            piece = PAWN | (us << 3)
            if promo == BISHOP:
                self.bishops[us] -= 1
        else:
            piece = b[to]
            if piece & 7 == KING:
                self.king_sq[us] = frm
        b[frm] = piece

        if flag == FLAG_EP:
            b[to] = EMPTY
            b[to + 8 if us == WHITE else to - 8] = captured
        else:
            b[to] = captured
            if captured and captured & 7 == BISHOP:
                self.bishops[captured >> 3] += 1

        if flag == FLAG_CASTLE:
            if to > frm:
                rook_from, rook_to = to + 1, to - 1
            else:
                rook_from, rook_to = to - 2, to + 1
            b[rook_from] = b[rook_to]
            b[rook_to] = EMPTY

        self.castling, self.ep, self.halfmove = castling, ep, halfmove
        self.hash, self.mg, self.eg, self.phase = h, mg, eg, phase
        self.pawn_key, self.fullmove = pk, fullmove

    def make_null(self) -> None:
        """Pass the turn (used by null-move pruning)."""
        self.stack.append((0, 0, self.castling, self.ep, self.halfmove, self.hash,
                           self.mg, self.eg, self.phase, self.pawn_key, self.fullmove))
        self.hash ^= ZOB_SIDE
        if self.ep != -1:
            self.hash ^= self._ep_hash()
        self.ep = -1
        self.side ^= 1
        self.halfmove += 1
        self.keys.append(self.hash)

    def unmake_null(self) -> None:
        (_, _, castling, ep, halfmove, h, _, _, _, _, fullmove) = self.stack.pop()
        self.keys.pop()
        self.side ^= 1
        self.castling, self.ep, self.halfmove = castling, ep, halfmove
        self.hash, self.fullmove = h, fullmove

    # --- Game state -------------------------------------------------------------------------

    def is_repetition(self) -> bool:
        """True if the current position already occurred since the last irreversible move."""
        keys = self.keys
        h = self.hash
        low = len(keys) - 1 - self.halfmove
        i = len(keys) - 3
        if low < 0:
            low = 0
        while i >= low:
            if keys[i] == h:
                return True
            i -= 2
        return False

    def is_insufficient_material(self) -> bool:
        """Bare kings, or kings plus one minor piece: no side can force mate."""
        return self.pawn_key == 0 and self.phase <= 1

    def has_non_pawn_material(self, color: int) -> bool:
        b = self.sq
        for s in range(64):
            p = b[s]
            if p and (p >> 3) == color and (p & 7) not in (PAWN, KING):
                return True
        return False

    # --- Testing helpers --------------------------------------------------------------------

    def perft(self, depth: int) -> int:
        """Count leaf nodes of the legal-move tree (the standard move-generator check)."""
        if depth == 0:
            return 1
        us = self.side
        them = us ^ 1
        captures, quiets = self.generate()
        total = 0
        for move in captures + quiets:
            move &= MOVE_MASK
            self.make(move)
            if not self.is_attacked(self.king_sq[us], them):
                total += 1 if depth == 1 else self.perft(depth - 1)
            self.unmake()
        return total


__all__ = [
    "SearchBoard", "InvalidPositionError", "START_FEN", "MOVE_MASK", "SCORE_SHIFT",
    "FLAG_EP", "FLAG_CASTLE", "FLAG_DOUBLE", "CASTLE_WK", "CASTLE_WQ", "CASTLE_BK", "CASTLE_BQ",
]
