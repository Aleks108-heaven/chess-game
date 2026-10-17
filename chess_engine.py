"""
Chess Engine Module
Handles all game logic: board state, move generation, move execution, and move history.

The rules implemented here are the ones written down in chess-rules.md (rule IDs such as J-09,
I-03 and A-07 refer to that file): the Junior core rules, the Intermediate special moves
(castling, en passant, promotion, insufficient material) and the Advanced end-of-game rules
(repetition, 50/75-move rules, claims, resignation, draw offers) plus FEN, UCI, SAN and PGN.

The engine knows nothing about the UI. ``play`` checks every move it is given, so a caller can
never put the game into an illegal state; ``make_move`` is the unchecked primitive underneath it.
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

_COLS = "abcdefgh"
_UCI_MOVE = re.compile(r"[a-h][1-8][a-h][1-8][qrbn]?")
_FEN_SQUARE = re.compile(r"[a-h][1-8]")

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# Results, as written in PGN (A-11).
RESULT_ONGOING = "*"
RESULT_WHITE_WINS = "1-0"
RESULT_BLACK_WINS = "0-1"
RESULT_DRAW = "1/2-1/2"

# Draw thresholds (A-03 .. A-06). Counters are half-moves; repetitions are occurrences.
REPETITION_CLAIM = 3        # claimable
REPETITION_AUTOMATIC = 5    # automatic
FIFTY_MOVE_CLAIM = 100      # claimable: 50 moves by each side without a pawn move or capture
SEVENTY_FIVE_MOVE_AUTOMATIC = 150

# A-08 project decision: after offering a draw, a player must make this many moves of their own
# before offering again, so an offer cannot be spammed.
DRAW_OFFER_INTERVAL = 10

PROMOTION_PIECES = "QRBN"

_KNIGHT_OFFSETS = ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1))
_KING_OFFSETS = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
_ROOK_DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))
_BISHOP_DIRECTIONS = ((-1, -1), (-1, 1), (1, -1), (1, 1))

_FEN_PIECES = {"P": "wP", "N": "wN", "B": "wB", "R": "wR", "Q": "wQ", "K": "wK",
               "p": "bP", "n": "bN", "b": "bB", "r": "bR", "q": "bQ", "k": "bK"}


class IllegalMoveError(ValueError):
    """A move was malformed, illegal in the position, or made after the game ended."""


class IllegalActionError(ValueError):
    """A claim, resignation or draw offer that the rules do not allow right now."""


@dataclass
class Move:
    """Represents a chess move."""
    start_row: int
    start_col: int
    end_row: int
    end_col: int
    piece_moved: str
    piece_captured: str
    is_pawn_promotion: bool = False
    is_enpassant: bool = False
    is_castle: bool = False
    promotion_piece: str = "Q"
    is_check: bool = False
    is_checkmate: bool = False
    disambiguation: str = ""

    def get_chess_notation(self) -> str:
        """Returns algebraic notation (SAN), e.g., Nf3, Bxe5+, O-O, e8=Q#."""
        if self.is_castle:
            notation = "O-O" if self.end_col > self.start_col else "O-O-O"
        else:
            piece_type = self.piece_moved[1]
            if piece_type == 'P':
                notation = ""
                if self.piece_captured != "--" or self.is_enpassant:
                    notation = _COLS[self.start_col] + "x"
                notation += _COLS[self.end_col] + str(8 - self.end_row)
                if self.is_pawn_promotion:
                    notation += "=" + self.promotion_piece
            else:
                notation = piece_type + self.disambiguation
                if self.piece_captured != "--":
                    notation += "x"
                notation += _COLS[self.end_col] + str(8 - self.end_row)

        if self.is_checkmate:
            notation += "#"
        elif self.is_check:
            notation += "+"

        return notation

    def get_coordinate_notation(self) -> str:
        """Returns UCI coordinate notation (e.g., e2e4; e7e8q for a promotion, A-11)."""
        text = f"{_COLS[self.start_col]}{8 - self.start_row}{_COLS[self.end_col]}{8 - self.end_row}"
        if self.is_pawn_promotion:
            text += self.promotion_piece.lower()
        return text

    def _identity(self) -> tuple:
        # A pawn reaching the last rank is four different moves (I-03), told apart by the piece.
        return (self.start_row, self.start_col, self.end_row, self.end_col,
                self.promotion_piece if self.is_pawn_promotion else "")

    def __eq__(self, other) -> bool:
        if not isinstance(other, Move):
            return False
        return self._identity() == other._identity()

    def __hash__(self) -> int:
        return hash(self._identity())


def _square_name(row: int, col: int) -> str:
    return f"{_COLS[col]}{8 - row}"


class ChessEngine:
    """
    Main chess engine class that handles:
    - Board state management (including everything a FEN holds, see section 3 of chess-rules.md)
    - Move generation with complete rules
    - Move execution with end-of-game detection, claims, resignation and draw offers
    - FEN / UCI / SAN / PGN conversion
    """

    def __init__(self):
        """Initialize the chess board with pieces in starting positions."""
        self.board: List[List[str]] = [
            ["bR", "bN", "bB", "bQ", "bK", "bB", "bN", "bR"],
            ["bP", "bP", "bP", "bP", "bP", "bP", "bP", "bP"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["wP", "wP", "wP", "wP", "wP", "wP", "wP", "wP"],
            ["wR", "wN", "wB", "wQ", "wK", "wB", "wN", "wR"]
        ]

        self.white_to_move: bool = True
        self.move_log: List[Move] = []

        self.white_king_location: Tuple[int, int] = (7, 4)
        self.black_king_location: Tuple[int, int] = (0, 4)

        self.in_check: bool = False
        self.checkmate: bool = False
        self.stalemate: bool = False
        self.draw_reason: str = ""

        # The result of the game and why it ended; "*" while it is still being played.
        self.result: str = RESULT_ONGOING
        self.result_reason: str = ""

        # Castling rights
        self.white_castle_kingside: bool = True
        self.white_castle_queenside: bool = True
        self.black_castle_kingside: bool = True
        self.black_castle_queenside: bool = True
        self.castle_rights_log: List[Tuple[bool, bool, bool, bool]] = [
            (True, True, True, True)
        ]

        # En passant: the square a pawn that just moved two squares jumped over. Kept for every
        # such move, even when nobody can capture; _ep_log remembers it for undo.
        self.enpassant_possible: Optional[Tuple[int, int]] = None
        self._ep_log: List[Optional[Tuple[int, int]]] = []

        # Draw detection
        self.halfmove_clock: int = 0
        self.halfmove_clock_log: List[int] = [0]

        # Draw offers (A-08)
        self.draw_offer_by: Optional[str] = None
        self._last_draw_offer: Dict[str, Optional[int]] = {"w": None, "b": None}

        # Where the game started, for the move numbers and the PGN header.
        self._start_white_to_move: bool = True
        self._start_fullmove: int = 1
        self.initial_fen: str = START_FEN

        # Position keys since the start of the game, the start itself included (A-02).
        self.position_history: List[str] = [self._get_board_hash()]

        # Move generation function mapping
        self._move_functions = {
            'P': self._get_pawn_moves,
            'R': self._get_rook_moves,
            'N': self._get_knight_moves,
            'B': self._get_bishop_moves,
            'Q': self._get_queen_moves,
            'K': self._get_king_moves
        }

    # --- Construction and conversion ---

    @classmethod
    def from_fen(cls, fen: str) -> "ChessEngine":
        """A game that starts from a FEN position. Raises ValueError for a malformed or
        impossible one (wrong number of kings, a pawn on the last rank, the side that just
        moved left in check...). Castling rights and an en passant square that the pieces
        cannot back up are dropped, as most FEN readers do."""
        if not isinstance(fen, str):
            raise ValueError("a FEN must be text")
        parts = fen.split()
        if not 4 <= len(parts) <= 6:
            raise ValueError(f"a FEN has 4 to 6 fields, found {len(parts)}: {fen!r}")
        placement, side, castling, ep = parts[:4]
        halfmove = cls._fen_counter(parts[4], "halfmove clock", 0) if len(parts) > 4 else 0
        fullmove = cls._fen_counter(parts[5], "fullmove number", 1) if len(parts) > 5 else 1

        ranks = placement.split("/")
        if len(ranks) != 8:
            raise ValueError(f"a FEN needs 8 ranks, found {len(ranks)}: {placement!r}")
        board: List[List[str]] = []
        for text in ranks:
            row: List[str] = []
            for ch in text:
                if ch in "12345678":
                    row += ["--"] * int(ch)
                elif ch in _FEN_PIECES:
                    row.append(_FEN_PIECES[ch])
                else:
                    raise ValueError(f"unknown FEN character {ch!r}")
            if len(row) != 8:
                raise ValueError(f"rank does not have 8 files: {text!r}")
            board.append(row)

        flat = [piece for row in board for piece in row]
        if flat.count("wK") != 1 or flat.count("bK") != 1:
            raise ValueError("each side needs exactly one king")
        if any(piece[1] == "P" for piece in board[0] + board[7]):
            raise ValueError("a pawn cannot stand on the first or last rank")
        if side not in ("w", "b"):
            raise ValueError(f"bad side to move: {side!r}")
        if castling != "-" and (set(castling) - set("KQkq") or len(set(castling)) != len(castling)):
            raise ValueError(f"bad castling field: {castling!r}")
        if ep != "-" and not (_FEN_SQUARE.fullmatch(ep) and ep[1] in "36"):
            raise ValueError(f"bad en passant square: {ep!r}")

        engine = cls()
        engine.board = board
        for row in range(8):
            for col in range(8):
                if board[row][col] == "wK":
                    engine.white_king_location = (row, col)
                elif board[row][col] == "bK":
                    engine.black_king_location = (row, col)
        engine.white_to_move = side == "w"

        # Rights only survive while the king and that rook still stand on their home squares.
        engine.white_castle_kingside = "K" in castling and board[7][4] == "wK" and board[7][7] == "wR"
        engine.white_castle_queenside = "Q" in castling and board[7][4] == "wK" and board[7][0] == "wR"
        engine.black_castle_kingside = "k" in castling and board[0][4] == "bK" and board[0][7] == "bR"
        engine.black_castle_queenside = "q" in castling and board[0][4] == "bK" and board[0][0] == "bR"
        engine.castle_rights_log = [engine._castle_rights()]

        engine.enpassant_possible = None
        if ep != "-":
            row, col = 8 - int(ep[1]), _COLS.index(ep[0])
            behind = row + 1 if engine.white_to_move else row - 1
            expected = (2 if engine.white_to_move else 5)
            pawn = "bP" if engine.white_to_move else "wP"
            if row == expected and board[row][col] == "--" and board[behind][col] == pawn:
                engine.enpassant_possible = (row, col)

        engine.halfmove_clock = halfmove
        engine.halfmove_clock_log = [halfmove]
        engine._start_white_to_move = engine.white_to_move
        engine._start_fullmove = fullmove

        # The side that just moved cannot be in check: the game would have ended already.
        engine.white_to_move = not engine.white_to_move
        left_in_check = engine._is_in_check()
        engine.white_to_move = not engine.white_to_move
        if left_in_check:
            raise ValueError("the side that is not to move is in check")

        engine.initial_fen = engine.to_fen()
        engine.position_history = [engine._get_board_hash()]
        engine.refresh_status()
        return engine

    @staticmethod
    def _fen_counter(text: str, name: str, minimum: int) -> int:
        if not text.isdigit() or int(text) < minimum:
            raise ValueError(f"bad {name}: {text!r}")
        return int(text)

    @property
    def fullmove_number(self) -> int:
        """Starts at 1 and goes up after each Black move (section 3)."""
        plies = len(self.move_log) + (0 if self._start_white_to_move else 1)
        return self._start_fullmove + plies // 2

    def to_fen(self) -> str:
        """The position as FEN (A-11). The en passant square is written only when a legal
        en passant capture exists, so equal positions give equal text (A-02)."""
        rows = []
        for row in self.board:
            text, empty = "", 0
            for piece in row:
                if piece == "--":
                    empty += 1
                    continue
                if empty:
                    text += str(empty)
                    empty = 0
                text += piece[1] if piece[0] == 'w' else piece[1].lower()
            rows.append(text + (str(empty) if empty else ""))
        castling = (("K" if self.white_castle_kingside else "")
                    + ("Q" if self.white_castle_queenside else "")
                    + ("k" if self.black_castle_kingside else "")
                    + ("q" if self.black_castle_queenside else "")) or "-"
        ep = "-"
        if self.enpassant_possible is not None and self._ep_capture_is_legal():
            ep = _square_name(*self.enpassant_possible)
        return (f"{'/'.join(rows)} {'w' if self.white_to_move else 'b'} {castling} {ep} "
                f"{self.halfmove_clock} {self.fullmove_number}")

    def _castle_rights(self) -> Tuple[bool, bool, bool, bool]:
        return (self.white_castle_kingside, self.white_castle_queenside,
                self.black_castle_kingside, self.black_castle_queenside)

    def get_piece_at(self, row: int, col: int) -> str:
        """Returns the piece at the given position."""
        return self.board[row][col]

    # --- Making and undoing moves ---

    def make_move(self, move: Move) -> bool:
        """Execute a move on the board WITHOUT checking it (see ``play`` for the checked one)."""
        self._ep_log.append(self.enpassant_possible)
        self.board[move.start_row][move.start_col] = "--"
        self.board[move.end_row][move.end_col] = move.piece_moved
        self.move_log.append(move)

        # Update king position
        if move.piece_moved == "wK":
            self.white_king_location = (move.end_row, move.end_col)
        elif move.piece_moved == "bK":
            self.black_king_location = (move.end_row, move.end_col)

        # Pawn promotion
        if move.is_pawn_promotion:
            self.board[move.end_row][move.end_col] = move.piece_moved[0] + move.promotion_piece

        # En passant capture
        if move.is_enpassant:
            self.board[move.start_row][move.end_col] = "--"

        # Update en passant possibility
        if move.piece_moved[1] == 'P' and abs(move.start_row - move.end_row) == 2:
            self.enpassant_possible = ((move.start_row + move.end_row) // 2, move.end_col)
        else:
            self.enpassant_possible = None

        # Castling move
        if move.is_castle:
            if move.end_col - move.start_col == 2:  # Kingside
                self.board[move.end_row][move.end_col - 1] = self.board[move.end_row][move.end_col + 1]
                self.board[move.end_row][move.end_col + 1] = "--"
            else:  # Queenside
                self.board[move.end_row][move.end_col + 1] = self.board[move.end_row][move.end_col - 2]
                self.board[move.end_row][move.end_col - 2] = "--"

        # Update halfmove clock (reset on pawn move or capture)
        if move.piece_moved[1] == 'P' or move.piece_captured != '--' or move.is_enpassant:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1
        self.halfmove_clock_log.append(self.halfmove_clock)

        # Update castling rights
        self._update_castle_rights(move)
        self.castle_rights_log.append(self._castle_rights())

        # Switch turns
        self.white_to_move = not self.white_to_move

        # Track position for repetition detection
        self.position_history.append(self._get_board_hash())

        return True

    def _undo(self) -> Optional[Move]:
        """Take back the last move and restore every piece of state it changed. Does not touch
        the game status (result, flags), so move generation can use it freely."""
        if not self.move_log:
            return None

        move = self.move_log.pop()

        self.board[move.start_row][move.start_col] = move.piece_moved
        self.board[move.end_row][move.end_col] = move.piece_captured

        self.white_to_move = not self.white_to_move

        if move.piece_moved == "wK":
            self.white_king_location = (move.start_row, move.start_col)
        elif move.piece_moved == "bK":
            self.black_king_location = (move.start_row, move.start_col)

        if move.is_enpassant:
            self.board[move.end_row][move.end_col] = "--"
            self.board[move.start_row][move.end_col] = move.piece_captured

        if move.is_castle:
            if move.end_col - move.start_col == 2:  # Kingside
                self.board[move.end_row][move.end_col + 1] = self.board[move.end_row][move.end_col - 1]
                self.board[move.end_row][move.end_col - 1] = "--"
            else:  # Queenside
                self.board[move.end_row][move.end_col - 2] = self.board[move.end_row][move.end_col + 1]
                self.board[move.end_row][move.end_col + 1] = "--"

        self.castle_rights_log.pop()
        (self.white_castle_kingside, self.white_castle_queenside,
         self.black_castle_kingside, self.black_castle_queenside) = self.castle_rights_log[-1]

        self.enpassant_possible = self._ep_log.pop()

        self.halfmove_clock_log.pop()
        self.halfmove_clock = self.halfmove_clock_log[-1]

        self.position_history.pop()
        return move

    def undo_move(self) -> Optional[Move]:
        """Undo the last move. The game is on again afterwards: the result, any pending draw
        offer and the check / mate flags are recomputed for the earlier position."""
        move = self._undo()
        if move is None:
            return None
        self.draw_offer_by = None
        self.result, self.result_reason = RESULT_ONGOING, ""
        self.checkmate = self.stalemate = False
        self.draw_reason = ""
        self.in_check = self._is_in_check()
        return move

    def get_valid_moves(self) -> List[Move]:
        """Returns all legal moves for the current player. A pawn reaching the last rank
        gives four moves, one per piece it can become (I-03)."""
        moves = self._get_all_possible_moves()

        if self.white_to_move:
            self._get_castle_moves(self.white_king_location[0], self.white_king_location[1], moves)
        else:
            self._get_castle_moves(self.black_king_location[0], self.black_king_location[1], moves)

        valid_moves = []
        for move in moves:
            self.make_move(move)
            self.white_to_move = not self.white_to_move
            if not self._is_in_check():
                valid_moves.append(move)
            self.white_to_move = not self.white_to_move
            self._undo()

        # Set disambiguation for algebraic notation
        self._set_move_disambiguations(valid_moves)

        return valid_moves

    def _set_move_disambiguations(self, valid_moves: List[Move]) -> None:
        """Set disambiguation strings for moves that need them in algebraic notation."""
        for move in valid_moves:
            if move.piece_moved[1] in ('P', 'K'):
                continue
            ambiguous = [m for m in valid_moves
                         if m.piece_moved == move.piece_moved
                         and m.end_row == move.end_row
                         and m.end_col == move.end_col
                         and (m.start_row != move.start_row or m.start_col != move.start_col)]
            if ambiguous:
                same_file = any(m.start_col == move.start_col for m in ambiguous)
                same_rank = any(m.start_row == move.start_row for m in ambiguous)
                if not same_file:
                    move.disambiguation = _COLS[move.start_col]
                elif not same_rank:
                    move.disambiguation = str(8 - move.start_row)
                else:
                    move.disambiguation = _COLS[move.start_col] + str(8 - move.start_row)

    def _get_all_possible_moves(self) -> List[Move]:
        """Returns all possible moves without considering checks."""
        moves = []
        for row in range(8):
            for col in range(8):
                piece = self.board[row][col]
                if piece != "--":
                    color = piece[0]
                    if (color == 'w' and self.white_to_move) or (color == 'b' and not self.white_to_move):
                        piece_type = piece[1]
                        self._move_functions[piece_type](row, col, moves)
        return moves

    def _add_pawn_move(self, moves: List[Move], row: int, col: int, end_row: int, end_col: int,
                       promotion_row: int) -> None:
        """A pawn move or capture; onto the last rank it becomes four moves (I-03)."""
        piece = self.board[row][col]
        captured = self.board[end_row][end_col]
        if end_row == promotion_row:
            for letter in PROMOTION_PIECES:
                moves.append(Move(row, col, end_row, end_col, piece, captured,
                                  is_pawn_promotion=True, promotion_piece=letter))
        else:
            moves.append(Move(row, col, end_row, end_col, piece, captured))

    def _get_pawn_moves(self, row: int, col: int, moves: List[Move]) -> None:
        """Generate all pawn moves from the given position."""
        if self.white_to_move:
            direction = -1
            start_row = 6
            enemy_color = 'b'
            promotion_row = 0
        else:
            direction = 1
            start_row = 1
            enemy_color = 'w'
            promotion_row = 7

        if self.board[row + direction][col] == "--":
            self._add_pawn_move(moves, row, col, row + direction, col, promotion_row)
            if row == start_row and self.board[row + 2 * direction][col] == "--":
                moves.append(Move(row, col, row + 2 * direction, col,
                                 self.board[row][col], "--"))

        for dc in [-1, 1]:
            new_col = col + dc
            if 0 <= new_col < 8:
                if self.board[row + direction][new_col][0] == enemy_color:
                    self._add_pawn_move(moves, row, col, row + direction, new_col, promotion_row)
                if self.enpassant_possible == (row + direction, new_col):
                    moves.append(Move(row, col, row + direction, new_col,
                                     self.board[row][col], self.board[row][new_col],
                                     is_enpassant=True))

    def _get_rook_moves(self, row: int, col: int, moves: List[Move]) -> None:
        self._get_sliding_moves(row, col, moves, _ROOK_DIRECTIONS)

    def _get_bishop_moves(self, row: int, col: int, moves: List[Move]) -> None:
        self._get_sliding_moves(row, col, moves, _BISHOP_DIRECTIONS)

    def _get_queen_moves(self, row: int, col: int, moves: List[Move]) -> None:
        self._get_rook_moves(row, col, moves)
        self._get_bishop_moves(row, col, moves)

    def _get_knight_moves(self, row: int, col: int, moves: List[Move]) -> None:
        ally_color = 'w' if self.white_to_move else 'b'
        for dr, dc in _KNIGHT_OFFSETS:
            new_row, new_col = row + dr, col + dc
            if 0 <= new_row < 8 and 0 <= new_col < 8:
                target = self.board[new_row][new_col]
                if target[0] != ally_color:
                    moves.append(Move(row, col, new_row, new_col,
                                     self.board[row][col], target))

    def _get_king_moves(self, row: int, col: int, moves: List[Move]) -> None:
        ally_color = 'w' if self.white_to_move else 'b'
        for dr, dc in _KING_OFFSETS:
            new_row, new_col = row + dr, col + dc
            if 0 <= new_row < 8 and 0 <= new_col < 8:
                target = self.board[new_row][new_col]
                if target[0] != ally_color:
                    moves.append(Move(row, col, new_row, new_col,
                                     self.board[row][col], target))

    def _get_sliding_moves(self, row: int, col: int, moves: List[Move],
                           directions: Tuple[Tuple[int, int], ...]) -> None:
        ally_color = 'w' if self.white_to_move else 'b'
        for dr, dc in directions:
            for i in range(1, 8):
                new_row, new_col = row + dr * i, col + dc * i
                if 0 <= new_row < 8 and 0 <= new_col < 8:
                    target = self.board[new_row][new_col]
                    if target == "--":
                        moves.append(Move(row, col, new_row, new_col,
                                         self.board[row][col], target))
                    elif target[0] != ally_color:
                        moves.append(Move(row, col, new_row, new_col,
                                         self.board[row][col], target))
                        break
                    else:
                        break
                else:
                    break

    def _get_castle_moves(self, row: int, col: int, moves: List[Move]) -> None:
        if self._is_in_check():
            return
        if self.white_to_move:
            if self.white_castle_kingside:
                self._check_kingside_castle(row, col, moves)
            if self.white_castle_queenside:
                self._check_queenside_castle(row, col, moves)
        else:
            if self.black_castle_kingside:
                self._check_kingside_castle(row, col, moves)
            if self.black_castle_queenside:
                self._check_queenside_castle(row, col, moves)

    def _check_kingside_castle(self, row: int, col: int, moves: List[Move]) -> None:
        if self.board[row][col + 1] == "--" and self.board[row][col + 2] == "--":
            if not self._square_under_attack(row, col + 1) and not self._square_under_attack(row, col + 2):
                moves.append(Move(row, col, row, col + 2, self.board[row][col], "--", is_castle=True))

    def _check_queenside_castle(self, row: int, col: int, moves: List[Move]) -> None:
        if (self.board[row][col - 1] == "--" and
            self.board[row][col - 2] == "--" and
            self.board[row][col - 3] == "--"):
            # b1 / b8 only has to be empty; the king never crosses it, so it may be attacked.
            if not self._square_under_attack(row, col - 1) and not self._square_under_attack(row, col - 2):
                moves.append(Move(row, col, row, col - 2, self.board[row][col], "--", is_castle=True))

    def _update_castle_rights(self, move: Move) -> None:
        if move.piece_moved == "wK":
            self.white_castle_kingside = False
            self.white_castle_queenside = False
        elif move.piece_moved == "bK":
            self.black_castle_kingside = False
            self.black_castle_queenside = False
        if move.start_row == 7 and move.start_col == 0:
            self.white_castle_queenside = False
        elif move.start_row == 7 and move.start_col == 7:
            self.white_castle_kingside = False
        elif move.start_row == 0 and move.start_col == 0:
            self.black_castle_queenside = False
        elif move.start_row == 0 and move.start_col == 7:
            self.black_castle_kingside = False
        if move.end_row == 7 and move.end_col == 0:
            self.white_castle_queenside = False
        elif move.end_row == 7 and move.end_col == 7:
            self.white_castle_kingside = False
        elif move.end_row == 0 and move.end_col == 0:
            self.black_castle_queenside = False
        elif move.end_row == 0 and move.end_col == 7:
            self.black_castle_kingside = False

    def _is_in_check(self) -> bool:
        if self.white_to_move:
            return self._square_under_attack(self.white_king_location[0], self.white_king_location[1])
        else:
            return self._square_under_attack(self.black_king_location[0], self.black_king_location[1])

    def _square_under_attack(self, row: int, col: int) -> bool:
        """True if a piece of the side NOT to move attacks the square, empty or not.

        Looks at the board directly instead of generating the opponent's moves: a pawn attacks
        diagonally even where it has nothing to capture (a castling king may not cross such a
        square), and a pawn's straight push attacks nothing.
        """
        board = self.board
        enemy = 'b' if self.white_to_move else 'w'

        pawn_row = row + 1 if enemy == 'w' else row - 1  # where an attacking pawn would stand
        if 0 <= pawn_row < 8:
            pawn = enemy + 'P'
            for dc in (-1, 1):
                c = col + dc
                if 0 <= c < 8 and board[pawn_row][c] == pawn:
                    return True

        knight = enemy + 'N'
        for dr, dc in _KNIGHT_OFFSETS:
            r, c = row + dr, col + dc
            if 0 <= r < 8 and 0 <= c < 8 and board[r][c] == knight:
                return True

        king = enemy + 'K'
        for dr, dc in _KING_OFFSETS:
            r, c = row + dr, col + dc
            if 0 <= r < 8 and 0 <= c < 8 and board[r][c] == king:
                return True

        queen = enemy + 'Q'
        for directions, slider in ((_ROOK_DIRECTIONS, enemy + 'R'), (_BISHOP_DIRECTIONS, enemy + 'B')):
            for dr, dc in directions:
                r, c = row + dr, col + dc
                while 0 <= r < 8 and 0 <= c < 8:
                    piece = board[r][c]
                    if piece != "--":
                        if piece == slider or piece == queen:
                            return True
                        break
                    r += dr
                    c += dc
        return False

    def _ep_capture_is_legal(self) -> bool:
        """True if the side to move has a LEGAL en passant capture (A-02, T-13): the capture
        must not leave its own king attacked, which the rank pin makes possible."""
        target = self.enpassant_possible
        if target is None:
            return False
        row, col = target
        white = self.white_to_move
        pawn_row = row + 1 if white else row - 1
        if not 0 <= pawn_row < 8 or self.board[row][col] != "--":
            return False
        own, enemy_pawn = ('wP', 'bP') if white else ('bP', 'wP')
        if self.board[pawn_row][col] != enemy_pawn:
            return False
        king_row, king_col = self.white_king_location if white else self.black_king_location
        for dc in (-1, 1):
            capturer_col = col + dc
            if 0 <= capturer_col < 8 and self.board[pawn_row][capturer_col] == own:
                self.board[pawn_row][capturer_col] = "--"
                self.board[pawn_row][col] = "--"
                self.board[row][col] = own
                attacked = self._square_under_attack(king_row, king_col)
                self.board[row][col] = "--"
                self.board[pawn_row][col] = enemy_pawn
                self.board[pawn_row][capturer_col] = own
                if not attacked:
                    return True
        return False

    # --- End of the game (Advanced rules) ---

    def _get_board_hash(self) -> str:
        """The position as a repetition key (A-02): piece placement, side to move, castling
        rights, and the en passant square only if a legal capture exists. Counters are ignored."""
        parts = []
        for row in self.board:
            parts.append(''.join(row))
        parts.append('w' if self.white_to_move else 'b')
        parts.append(f"{self.white_castle_kingside}{self.white_castle_queenside}")
        parts.append(f"{self.black_castle_kingside}{self.black_castle_queenside}")
        parts.append(str(self.enpassant_possible) if self._ep_capture_is_legal() else "None")
        return '|'.join(parts)

    def repetition_count(self) -> int:
        """How many times the current position has occurred in this game (counting now)."""
        return self.position_history.count(self.position_history[-1])

    def is_threefold_repetition(self) -> bool:
        """The current position has occurred three times: the player to move may claim (A-03)."""
        return self.repetition_count() >= REPETITION_CLAIM

    def is_fivefold_repetition(self) -> bool:
        """The current position has occurred five times: an automatic draw (A-04)."""
        return self.repetition_count() >= REPETITION_AUTOMATIC

    def is_fifty_move_draw(self) -> bool:
        """50 moves by each side without a pawn move or capture: claimable (A-05)."""
        return self.halfmove_clock >= FIFTY_MOVE_CLAIM

    def is_seventy_five_move_draw(self) -> bool:
        """75 moves by each side without a pawn move or capture: an automatic draw (A-06)."""
        return self.halfmove_clock >= SEVENTY_FIVE_MOVE_AUTOMATIC

    def is_draw(self) -> str:
        """The reason the game is drawn automatically right now, or "" (A-07, steps 3 to 5).
        Claimable draws are not included: see ``can_claim_draw``."""
        if self.is_insufficient_material():
            return "insufficient material"
        if self.is_fivefold_repetition():
            return "fivefold repetition"
        if self.is_seventy_five_move_draw():
            return "75-move rule"
        return ""

    def can_claim_draw(self) -> str:
        """The draw the player to move may claim (A-03, A-05): "threefold repetition",
        "50-move rule", or "" if there is nothing to claim or the game is over."""
        if self.result != RESULT_ONGOING:
            return ""
        if self.is_threefold_repetition():
            return "threefold repetition"
        if self.is_fifty_move_draw():
            return "50-move rule"
        return ""

    def is_insufficient_material(self) -> bool:
        """Checkmate is impossible for both sides (I-04): bare kings, a king and one minor
        piece against a bare king, or only bishops that all stand on squares of one colour.
        King and two knights, knight against knight and opposite-coloured bishops are NOT drawn
        automatically: a mate is still possible."""
        knights, bishop_colors = 0, set()
        for row in range(8):
            for col in range(8):
                piece = self.board[row][col]
                kind = piece[1]
                if piece == "--" or kind == 'K':
                    continue
                if kind == 'N':
                    knights += 1
                elif kind == 'B':
                    bishop_colors.add((row + col) % 2)
                else:  # a pawn, rook or queen can always force or allow mate
                    return False
        bishops_present = bool(bishop_colors)
        if knights == 0:
            return len(bishop_colors) <= 1      # bare kings, or bishops of one colour only
        return knights == 1 and not bishops_present   # king and a single knight

    def refresh_status(self, last_move: Optional[Move] = None) -> List[Move]:
        """Work out check, checkmate, stalemate and the automatic draws for the position on the
        board (A-07, in that order), and return the legal moves. ``last_move``, if given, gets
        its check / checkmate marks for the move list. ``play`` calls this after every move."""
        legal = self.get_valid_moves()
        self.in_check = self._is_in_check()
        self.checkmate = self.stalemate = False
        self.draw_reason = ""
        self.result, self.result_reason = RESULT_ONGOING, ""
        if last_move is not None:
            last_move.is_check = last_move.is_checkmate = False

        if not legal:
            if self.in_check:
                self.checkmate = True
                if last_move is not None:
                    last_move.is_checkmate = True
                self._end(RESULT_BLACK_WINS if self.white_to_move else RESULT_WHITE_WINS, "checkmate")
            else:
                self.stalemate = True
                self._end(RESULT_DRAW, "stalemate")
            return legal

        if self.in_check and last_move is not None:
            last_move.is_check = True
        reason = self.is_draw()
        if reason:
            self._end(RESULT_DRAW, reason)
        return legal

    def _end(self, result: str, reason: str) -> None:
        self.result, self.result_reason = result, reason
        self.draw_offer_by = None
        if result == RESULT_DRAW:
            self.draw_reason = reason

    # --- Checked entry points ---

    def move_from_uci(self, text: str) -> Move:
        """The legal move written like 'e2e4' or 'e7e8q'. Raises IllegalMoveError for text that
        is not a move, or for a move that is not legal here (including a promotion with no
        piece letter, or a letter on a move that is not a promotion)."""
        if not isinstance(text, str) or not _UCI_MOVE.fullmatch(text):
            raise IllegalMoveError(f"not a move: {text!r}")
        for move in self.get_valid_moves():
            if move.get_coordinate_notation() == text:
                return move
        raise IllegalMoveError(f"illegal move in this position: {text!r}")

    def play(self, move: Move) -> Move:
        """Make a move after checking it is legal, then update the game status. Returns the
        move as played. Raises IllegalMoveError if the game is over or the move is not one of
        ``get_valid_moves()``; the position is left untouched in that case."""
        if self.result != RESULT_ONGOING:
            raise IllegalMoveError(f"the game is over ({self.result_reason})")
        legal = self.get_valid_moves()
        for candidate in legal:
            if candidate == move:
                break
        else:
            raise IllegalMoveError(f"illegal move in this position: {move!r}")
        self.draw_offer_by = None  # making a move declines an open offer (A-08)
        self.make_move(candidate)
        self.refresh_status(candidate)
        return candidate

    def play_uci(self, text: str) -> Move:
        """``move_from_uci`` followed by ``play``."""
        return self.play(self.move_from_uci(text))

    def claim_draw(self) -> str:
        """The player to move claims a draw by repetition or by the 50-move rule (A-03, A-05).
        Returns the reason; raises IllegalActionError if there is nothing to claim."""
        reason = self.can_claim_draw()
        if not reason:
            raise IllegalActionError("there is no draw to claim in this position")
        self._end(RESULT_DRAW, reason)
        return reason

    def resign(self, color: str) -> None:
        """``color`` ('w' or 'b') resigns: the opponent wins at once (J-12, A-08)."""
        if color not in ("w", "b"):
            raise ValueError(f"color must be 'w' or 'b', not {color!r}")
        if self.result != RESULT_ONGOING:
            raise IllegalActionError("the game is already over")
        self._end(RESULT_BLACK_WINS if color == "w" else RESULT_WHITE_WINS, "resignation")

    def can_offer_draw(self, color: str) -> bool:
        """May ``color`` offer a draw now? Not when the game is over, an offer is already open,
        or this player offered within the last ``DRAW_OFFER_INTERVAL`` moves of their own."""
        if self.result != RESULT_ONGOING or self.draw_offer_by is not None:
            return False
        last = self._last_draw_offer.get(color)
        plies = len(self.move_log)
        return last is None or last > plies or plies - last >= 2 * DRAW_OFFER_INTERVAL

    def moves_until_draw_offer(self, color: str) -> int:
        """How many more full moves must be played before ``color`` may offer again (0 if now)."""
        last = self._last_draw_offer.get(color)
        plies = len(self.move_log)
        if last is None or last > plies:
            return 0
        remaining = 2 * DRAW_OFFER_INTERVAL - (plies - last)
        return max(0, (remaining + 1) // 2)

    def offer_draw(self, color: str) -> None:
        """``color`` offers a draw. The opponent answers with ``accept_draw`` or
        ``decline_draw``; making a move instead also declines it (A-08)."""
        if color not in ("w", "b"):
            raise ValueError(f"color must be 'w' or 'b', not {color!r}")
        if not self.can_offer_draw(color):
            raise IllegalActionError("a draw cannot be offered now")
        self.draw_offer_by = color
        self._last_draw_offer[color] = len(self.move_log)

    def accept_draw(self) -> None:
        """The open draw offer is accepted: the game is drawn by agreement (J-12)."""
        if self.draw_offer_by is None:
            raise IllegalActionError("there is no draw offer to accept")
        self._end(RESULT_DRAW, "agreement")

    def decline_draw(self) -> None:
        if self.draw_offer_by is None:
            raise IllegalActionError("there is no draw offer to decline")
        self.draw_offer_by = None

    # --- Notation (A-11) ---

    def san_moves(self) -> List[str]:
        """Every move played so far in SAN, with + and # marks and any disambiguation,
        worked out by replaying the game (so it is right even for moves made with
        ``make_move``)."""
        replay = ChessEngine.from_fen(self.initial_fen)
        notation: List[str] = []
        legal = replay.get_valid_moves()
        for move in self.move_log:
            played = next(candidate for candidate in legal if candidate == move)
            replay.make_move(played)
            legal = replay.get_valid_moves()
            in_check = replay._is_in_check()
            played.is_check, played.is_checkmate = in_check and bool(legal), in_check and not legal
            notation.append(played.get_chess_notation())
        return notation

    def to_pgn(self, white: str = "White", black: str = "Black", event: str = "Casual game",
               site: str = "Chess Game", game_date: Optional[date] = None) -> str:
        """The game as PGN text: the seven standard tags, the moves in SAN and the result."""
        def tag(name: str, value: str) -> str:
            clean = " ".join(str(value).split()).replace("\\", "\\\\").replace('"', '\\"')
            return f'[{name} "{clean}"]'

        when = (game_date or date.today()).strftime("%Y.%m.%d")
        tags = [tag("Event", event), tag("Site", site), tag("Date", when), tag("Round", "-"),
                tag("White", white), tag("Black", black), tag("Result", self.result)]
        if self.initial_fen != START_FEN:
            tags += [tag("SetUp", "1"), tag("FEN", self.initial_fen)]

        tokens: List[str] = []
        number, white_turn = self._start_fullmove, self._start_white_to_move
        for index, san in enumerate(self.san_moves()):
            if white_turn:
                tokens.append(f"{number}.")
            else:
                if index == 0:
                    tokens.append(f"{number}...")
                number += 1
            tokens.append(san)
            white_turn = not white_turn
        tokens.append(self.result)

        lines, line = [], ""
        for token in tokens:  # wrap the move text at 80 columns
            if line and len(line) + 1 + len(token) > 80:
                lines.append(line)
                line = token
            else:
                line = f"{line} {token}" if line else token
        lines.append(line)
        return "\n".join(tags) + "\n\n" + "\n".join(lines) + "\n"

    def reset_game(self) -> None:
        """Reset the game to initial state."""
        self.__init__()
