"""
Chess Engine Module
Handles all game logic: board state, move generation, move execution, and move history.
Features complete rules with draw detection, algebraic notation, and pawn promotion choice.
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass

_COLS = "abcdefgh"


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
        """Returns algebraic notation (e.g., Nf3, Bxe5+, O-O)."""
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
        """Returns coordinate notation (e.g., e2e4)."""
        return f"{_COLS[self.start_col]}{8 - self.start_row}{_COLS[self.end_col]}{8 - self.end_row}"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Move):
            return False
        return (self.start_row == other.start_row and
                self.start_col == other.start_col and
                self.end_row == other.end_row and
                self.end_col == other.end_col)

    def __hash__(self) -> int:
        return hash((self.start_row, self.start_col, self.end_row, self.end_col))


class ChessEngine:
    """
    Main chess engine class that handles:
    - Board state management
    - Move generation with complete rules
    - Move execution with draw detection
    - Game state tracking
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

        # Castling rights
        self.white_castle_kingside: bool = True
        self.white_castle_queenside: bool = True
        self.black_castle_kingside: bool = True
        self.black_castle_queenside: bool = True
        self.castle_rights_log: List[Tuple[bool, bool, bool, bool]] = [
            (True, True, True, True)
        ]

        # En passant
        self.enpassant_possible: Optional[Tuple[int, int]] = None

        # Draw detection
        self.halfmove_clock: int = 0
        self.halfmove_clock_log: List[int] = [0]
        self.position_history: List[str] = []

        # Move generation function mapping
        self._move_functions = {
            'P': self._get_pawn_moves,
            'R': self._get_rook_moves,
            'N': self._get_knight_moves,
            'B': self._get_bishop_moves,
            'Q': self._get_queen_moves,
            'K': self._get_king_moves
        }

    def get_piece_at(self, row: int, col: int) -> str:
        """Returns the piece at the given position."""
        return self.board[row][col]

    def make_move(self, move: Move) -> bool:
        """Execute a move on the board."""
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
        self.castle_rights_log.append((
            self.white_castle_kingside, self.white_castle_queenside,
            self.black_castle_kingside, self.black_castle_queenside
        ))

        # Switch turns
        self.white_to_move = not self.white_to_move

        # Track position for repetition detection
        self.position_history.append(self._get_board_hash())

        return True

    def undo_move(self) -> Optional[Move]:
        """Undo the last move."""
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
        if self.castle_rights_log:
            rights = self.castle_rights_log[-1]
            self.white_castle_kingside = rights[0]
            self.white_castle_queenside = rights[1]
            self.black_castle_kingside = rights[2]
            self.black_castle_queenside = rights[3]

        if self.move_log:
            last_move = self.move_log[-1]
            if last_move.piece_moved[1] == 'P' and abs(last_move.start_row - last_move.end_row) == 2:
                self.enpassant_possible = ((last_move.start_row + last_move.end_row) // 2, last_move.end_col)
            else:
                self.enpassant_possible = None
        else:
            self.enpassant_possible = None

        # Restore halfmove clock
        self.halfmove_clock_log.pop()
        self.halfmove_clock = self.halfmove_clock_log[-1]

        # Restore position history
        if self.position_history:
            self.position_history.pop()

        self.checkmate = False
        self.stalemate = False
        self.draw_reason = ""

        return move

    def get_valid_moves(self) -> List[Move]:
        """Returns all legal moves for the current player."""
        temp_enpassant = self.enpassant_possible
        temp_castle_rights = (
            self.white_castle_kingside, self.white_castle_queenside,
            self.black_castle_kingside, self.black_castle_queenside
        )

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
            self.undo_move()

        self.enpassant_possible = temp_enpassant
        self.white_castle_kingside = temp_castle_rights[0]
        self.white_castle_queenside = temp_castle_rights[1]
        self.black_castle_kingside = temp_castle_rights[2]
        self.black_castle_queenside = temp_castle_rights[3]

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
            is_promotion = (row + direction == promotion_row)
            moves.append(Move(row, col, row + direction, col,
                             self.board[row][col], "--", is_pawn_promotion=is_promotion))
            if row == start_row and self.board[row + 2 * direction][col] == "--":
                moves.append(Move(row, col, row + 2 * direction, col,
                                 self.board[row][col], "--"))

        for dc in [-1, 1]:
            new_col = col + dc
            if 0 <= new_col < 8:
                if self.board[row + direction][new_col][0] == enemy_color:
                    is_promotion = (row + direction == promotion_row)
                    moves.append(Move(row, col, row + direction, new_col,
                                     self.board[row][col], self.board[row + direction][new_col],
                                     is_pawn_promotion=is_promotion))
                if self.enpassant_possible == (row + direction, new_col):
                    moves.append(Move(row, col, row + direction, new_col,
                                     self.board[row][col], self.board[row][new_col],
                                     is_enpassant=True))

    def _get_rook_moves(self, row: int, col: int, moves: List[Move]) -> None:
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        self._get_sliding_moves(row, col, moves, directions)

    def _get_bishop_moves(self, row: int, col: int, moves: List[Move]) -> None:
        directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        self._get_sliding_moves(row, col, moves, directions)

    def _get_queen_moves(self, row: int, col: int, moves: List[Move]) -> None:
        self._get_rook_moves(row, col, moves)
        self._get_bishop_moves(row, col, moves)

    def _get_knight_moves(self, row: int, col: int, moves: List[Move]) -> None:
        knight_moves = [
            (-2, -1), (-2, 1), (-1, -2), (-1, 2),
            (1, -2), (1, 2), (2, -1), (2, 1)
        ]
        ally_color = 'w' if self.white_to_move else 'b'
        for dr, dc in knight_moves:
            new_row, new_col = row + dr, col + dc
            if 0 <= new_row < 8 and 0 <= new_col < 8:
                target = self.board[new_row][new_col]
                if target[0] != ally_color:
                    moves.append(Move(row, col, new_row, new_col,
                                     self.board[row][col], target))

    def _get_king_moves(self, row: int, col: int, moves: List[Move]) -> None:
        king_moves = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1), (0, 1),
            (1, -1), (1, 0), (1, 1)
        ]
        ally_color = 'w' if self.white_to_move else 'b'
        for dr, dc in king_moves:
            new_row, new_col = row + dr, col + dc
            if 0 <= new_row < 8 and 0 <= new_col < 8:
                target = self.board[new_row][new_col]
                if target[0] != ally_color:
                    moves.append(Move(row, col, new_row, new_col,
                                     self.board[row][col], target))

    def _get_sliding_moves(self, row: int, col: int, moves: List[Move],
                           directions: List[Tuple[int, int]]) -> None:
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
        self.white_to_move = not self.white_to_move
        opponent_moves = self._get_all_possible_moves()
        self.white_to_move = not self.white_to_move
        for move in opponent_moves:
            if move.end_row == row and move.end_col == col:
                return True
        return False

    # --- Draw Detection ---

    def _get_board_hash(self) -> str:
        """Get a hashable representation of the current board position."""
        parts = []
        for row in self.board:
            parts.append(''.join(row))
        parts.append('w' if self.white_to_move else 'b')
        parts.append(f"{self.white_castle_kingside}{self.white_castle_queenside}")
        parts.append(f"{self.black_castle_kingside}{self.black_castle_queenside}")
        parts.append(str(self.enpassant_possible))
        return '|'.join(parts)

    def is_draw(self) -> str:
        """Check for draw conditions. Returns draw reason string or empty string."""
        if self.is_fifty_move_draw():
            return "50-move rule"
        if self.is_threefold_repetition():
            return "threefold repetition"
        if self.is_insufficient_material():
            return "insufficient material"
        return ""

    def is_fifty_move_draw(self) -> bool:
        """Check if 50-move rule applies (100 half-moves without pawn move or capture)."""
        return self.halfmove_clock >= 100

    def is_threefold_repetition(self) -> bool:
        """Check if the current position has occurred three times."""
        if len(self.position_history) < 5:
            return False
        current = self._get_board_hash()
        # Exclude the just-appended current entry so we count prior occurrences only.
        count = sum(1 for pos in self.position_history[:-1] if pos == current)
        return count >= 2  # Current position appeared 2+ times before = 3 total

    def is_insufficient_material(self) -> bool:
        """Check if neither side has sufficient material to checkmate."""
        pieces = {'w': [], 'b': []}
        for row in range(8):
            for col in range(8):
                piece = self.board[row][col]
                if piece != "--" and piece[1] != 'K':
                    pieces[piece[0]].append(piece[1])

        w, b = sorted(pieces['w']), sorted(pieces['b'])

        # K vs K
        if not w and not b:
            return True
        # K+B vs K or K+N vs K
        if (not w and b in [['B'], ['N']]) or (w in [['B'], ['N']] and not b):
            return True
        # K+B vs K+B with same-colored bishops
        if w == ['B'] and b == ['B']:
            w_bishop_color = b_bishop_color = None
            for row in range(8):
                for col in range(8):
                    piece = self.board[row][col]
                    if piece == 'wB':
                        w_bishop_color = (row + col) % 2
                    elif piece == 'bB':
                        b_bishop_color = (row + col) % 2
            if w_bishop_color == b_bishop_color:
                return True
        return False

    def reset_game(self) -> None:
        """Reset the game to initial state."""
        self.__init__()
