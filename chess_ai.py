"""
Chess AI Module
Implements a computer opponent using Minimax with Alpha-Beta pruning.
Features opening book, move ordering, and positional evaluation.
"""

import random
import time
from typing import List, Optional
from chess_engine import ChessEngine, Move


class ChessAI:
    """
    AI opponent using Minimax with Alpha-Beta pruning,
    opening book for natural play, and move ordering for efficiency.
    """

    MAX_DEPTH = 5
    MAX_SEARCH_TIME = 30.0

    PIECE_VALUES = {
        'K': 0,
        'Q': 900,
        'R': 500,
        'B': 330,
        'N': 320,
        'P': 100
    }

    # Opening book: maps move sequence (coordinate notation) to list of good responses
    OPENING_BOOK = {
        # Starting position
        "": ["e2e4", "d2d4", "c2c4", "g1f3"],
        # 1.e4
        "e2e4": ["e7e5", "c7c5", "e7e6", "c7c6", "d7d5"],
        # 1.e4 e5
        "e2e4 e7e5": ["g1f3", "f1c4", "b1c3"],
        # 1.e4 e5 2.Nf3
        "e2e4 e7e5 g1f3": ["b8c6", "g8f6", "d7d6"],
        # 1.e4 e5 2.Nf3 Nc6 (Italian / Ruy Lopez)
        "e2e4 e7e5 g1f3 b8c6": ["f1b5", "f1c4", "d2d4"],
        # Italian Game: 3.Bc4
        "e2e4 e7e5 g1f3 b8c6 f1c4": ["f8c5", "g8f6"],
        # Italian Game: 3.Bc4 Bc5
        "e2e4 e7e5 g1f3 b8c6 f1c4 f8c5": ["c2c3", "d2d3", "b2b4"],
        # Italian Game: 3.Bc4 Nf6 (Two Knights)
        "e2e4 e7e5 g1f3 b8c6 f1c4 g8f6": ["d2d4", "d2d3", "b1c3"],
        # Ruy Lopez: 3.Bb5
        "e2e4 e7e5 g1f3 b8c6 f1b5": ["a7a6", "g8f6", "f8c5"],
        # Ruy Lopez: 3...a6
        "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6": ["f1a4", "f1c6"],
        # Scotch: 3.d4
        "e2e4 e7e5 g1f3 b8c6 d2d4": ["e5d4"],
        # Petrov: 2...Nf6
        "e2e4 e7e5 g1f3 g8f6": ["g1e5", "b1c3", "d2d4"],
        # Sicilian Defense: 1.e4 c5
        "e2e4 c7c5": ["g1f3", "b1c3", "c2c3"],
        "e2e4 c7c5 g1f3": ["d7d6", "b8c6", "e7e6"],
        "e2e4 c7c5 g1f3 d7d6": ["d2d4"],
        "e2e4 c7c5 g1f3 d7d6 d2d4": ["c5d4"],
        "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4": ["f3d4"],
        "e2e4 c7c5 g1f3 b8c6": ["d2d4", "f1b5"],
        "e2e4 c7c5 g1f3 e7e6": ["d2d4", "b1c3"],
        # French Defense: 1.e4 e6
        "e2e4 e7e6": ["d2d4"],
        "e2e4 e7e6 d2d4": ["d7d5"],
        "e2e4 e7e6 d2d4 d7d5": ["b1c3", "b1d2", "e4e5", "e4d5"],
        "e2e4 e7e6 d2d4 d7d5 b1c3": ["g8f6", "f8b4"],
        "e2e4 e7e6 d2d4 d7d5 e4e5": ["c7c5"],
        # Caro-Kann: 1.e4 c6
        "e2e4 c7c6": ["d2d4"],
        "e2e4 c7c6 d2d4": ["d7d5"],
        "e2e4 c7c6 d2d4 d7d5": ["b1c3", "e4e5", "e4d5"],
        # Scandinavian: 1.e4 d5
        "e2e4 d7d5": ["e4d5"],
        "e2e4 d7d5 e4d5": ["d8d5", "g8f6"],
        # 1.d4
        "d2d4": ["d7d5", "g8f6", "e7e6"],
        # Queen's Gambit: 1.d4 d5
        "d2d4 d7d5": ["c2c4", "g1f3", "c1f4"],
        "d2d4 d7d5 c2c4": ["e7e6", "c7c6", "d5c4"],
        # QGD: 2...e6
        "d2d4 d7d5 c2c4 e7e6": ["b1c3", "g1f3"],
        "d2d4 d7d5 c2c4 e7e6 b1c3": ["g8f6", "f8e7"],
        "d2d4 d7d5 c2c4 e7e6 g1f3": ["g8f6"],
        # Slav: 2...c6
        "d2d4 d7d5 c2c4 c7c6": ["g1f3", "b1c3"],
        # QGA: 2...dxc4
        "d2d4 d7d5 c2c4 d5c4": ["e2e3", "g1f3"],
        # London: 1.d4 d5 2.Bf4
        "d2d4 d7d5 c1f4": ["g8f6", "c7c5", "e7e6"],
        # Indian: 1.d4 Nf6
        "d2d4 g8f6": ["c2c4", "g1f3", "c1f4"],
        "d2d4 g8f6 c2c4": ["e7e6", "g7g6", "c7c5"],
        # King's Indian: 2.c4 g6
        "d2d4 g8f6 c2c4 g7g6": ["b1c3", "g1f3"],
        "d2d4 g8f6 c2c4 g7g6 b1c3": ["f8g7"],
        "d2d4 g8f6 c2c4 g7g6 b1c3 f8g7": ["e2e4", "g1f3"],
        # Nimzo-Indian: 2.c4 e6
        "d2d4 g8f6 c2c4 e7e6": ["b1c3", "g1f3"],
        "d2d4 g8f6 c2c4 e7e6 b1c3": ["f8b4"],
        # Benoni: 2.c4 c5
        "d2d4 g8f6 c2c4 c7c5": ["d4d5"],
        # English: 1.c4
        "c2c4": ["e7e5", "g8f6", "c7c5", "e7e6"],
        "c2c4 e7e5": ["b1c3", "g1f3", "g2g3"],
        "c2c4 g8f6": ["b1c3", "g1f3"],
        # Reti: 1.Nf3
        "g1f3": ["d7d5", "g8f6", "c7c5"],
        "g1f3 d7d5": ["g2g3", "c2c4", "d2d4"],
        "g1f3 g8f6": ["g2g3", "c2c4", "d2d4"],
    }

    PAWN_TABLE = [
        [0,  0,  0,  0,  0,  0,  0,  0],
        [50, 50, 50, 50, 50, 50, 50, 50],
        [10, 10, 20, 30, 30, 20, 10, 10],
        [5,  5, 10, 25, 25, 10,  5,  5],
        [0,  0,  0, 20, 20,  0,  0,  0],
        [5, -5,-10,  0,  0,-10, -5,  5],
        [5, 10, 10,-20,-20, 10, 10,  5],
        [0,  0,  0,  0,  0,  0,  0,  0]
    ]

    KNIGHT_TABLE = [
        [-50,-40,-30,-30,-30,-30,-40,-50],
        [-40,-20,  0,  0,  0,  0,-20,-40],
        [-30,  0, 10, 15, 15, 10,  0,-30],
        [-30,  5, 15, 20, 20, 15,  5,-30],
        [-30,  0, 15, 20, 20, 15,  0,-30],
        [-30,  5, 10, 15, 15, 10,  5,-30],
        [-40,-20,  0,  5,  5,  0,-20,-40],
        [-50,-40,-30,-30,-30,-30,-40,-50]
    ]

    BISHOP_TABLE = [
        [-20,-10,-10,-10,-10,-10,-10,-20],
        [-10,  0,  0,  0,  0,  0,  0,-10],
        [-10,  0,  5, 10, 10,  5,  0,-10],
        [-10,  5,  5, 10, 10,  5,  5,-10],
        [-10,  0, 10, 10, 10, 10,  0,-10],
        [-10, 10, 10, 10, 10, 10, 10,-10],
        [-10,  5,  0,  0,  0,  0,  5,-10],
        [-20,-10,-10,-10,-10,-10,-10,-20]
    ]

    ROOK_TABLE = [
        [0,  0,  0,  0,  0,  0,  0,  0],
        [5, 10, 10, 10, 10, 10, 10,  5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [0,  0,  0,  5,  5,  0,  0,  0]
    ]

    QUEEN_TABLE = [
        [-20,-10,-10, -5, -5,-10,-10,-20],
        [-10,  0,  0,  0,  0,  0,  0,-10],
        [-10,  0,  5,  5,  5,  5,  0,-10],
        [-5,  0,  5,  5,  5,  5,  0, -5],
        [0,  0,  5,  5,  5,  5,  0, -5],
        [-10,  5,  5,  5,  5,  5,  0,-10],
        [-10,  0,  5,  0,  0,  0,  0,-10],
        [-20,-10,-10, -5, -5,-10,-10,-20]
    ]

    KING_MIDDLE_TABLE = [
        [-30,-40,-40,-50,-50,-40,-40,-30],
        [-30,-40,-40,-50,-50,-40,-40,-30],
        [-30,-40,-40,-50,-50,-40,-40,-30],
        [-30,-40,-40,-50,-50,-40,-40,-30],
        [-20,-30,-30,-40,-40,-30,-30,-20],
        [-10,-20,-20,-20,-20,-20,-20,-10],
        [20, 20,  0,  0,  0,  0, 20, 20],
        [20, 30, 10,  0,  0, 10, 30, 20]
    ]

    KING_END_TABLE = [
        [-50,-40,-30,-20,-20,-30,-40,-50],
        [-30,-20,-10,  0,  0,-10,-20,-30],
        [-30,-10, 20, 30, 30, 20,-10,-30],
        [-30,-10, 30, 40, 40, 30,-10,-30],
        [-30,-10, 30, 40, 40, 30,-10,-30],
        [-30,-10, 20, 30, 30, 20,-10,-30],
        [-30,-30,  0,  0,  0,  0,-30,-30],
        [-50,-30,-30,-30,-30,-30,-30,-50]
    ]

    PIECE_TABLES = {
        'P': PAWN_TABLE,
        'N': KNIGHT_TABLE,
        'B': BISHOP_TABLE,
        'R': ROOK_TABLE,
        'Q': QUEEN_TABLE,
        'K': KING_MIDDLE_TABLE
    }

    def __init__(self, depth: int = 3):
        self.depth = min(depth, self.MAX_DEPTH)
        self.nodes_searched = 0
        self.search_start_time = 0
        self.timeout_reached = False

    def get_best_move(self, engine: ChessEngine, valid_moves: List[Move]) -> Optional[Move]:
        """Find the best move. Checks opening book first, then uses search."""
        if not valid_moves:
            return None

        # Try opening book first
        book_move = self._get_book_move(engine, valid_moves)
        if book_move is not None:
            return book_move

        self.nodes_searched = 0
        self.search_start_time = time.time()
        self.timeout_reached = False
        best_move = None

        # Order moves for better pruning
        ordered_moves = self._order_moves(engine, valid_moves)

        try:
            if engine.white_to_move:
                best_score = float('-inf')
                for move in ordered_moves:
                    if self._check_timeout():
                        break
                    engine.make_move(move)
                    score = self._minimax(engine, self.depth - 1, float('-inf'), float('inf'), False)
                    engine.undo_move()
                    if score > best_score:
                        best_score = score
                        best_move = move
                    elif score == best_score and random.random() < 0.3:
                        best_move = move
            else:
                best_score = float('inf')
                for move in ordered_moves:
                    if self._check_timeout():
                        break
                    engine.make_move(move)
                    score = self._minimax(engine, self.depth - 1, float('-inf'), float('inf'), True)
                    engine.undo_move()
                    if score < best_score:
                        best_score = score
                        best_move = move
                    elif score == best_score and random.random() < 0.3:
                        best_move = move
        except Exception as e:
            print(f"AI error: {e}. Selecting random move.")
            best_move = random.choice(valid_moves) if valid_moves else None

        if best_move is None and valid_moves:
            best_move = random.choice(valid_moves)

        return best_move

    def _get_book_move(self, engine: ChessEngine, valid_moves: List[Move]) -> Optional[Move]:
        """Try to find a move from the opening book."""
        move_seq = " ".join(m.get_coordinate_notation() for m in engine.move_log)

        if move_seq in self.OPENING_BOOK:
            book_responses = list(self.OPENING_BOOK[move_seq])
            random.shuffle(book_responses)

            for book_move_str in book_responses:
                for valid_move in valid_moves:
                    if valid_move.get_coordinate_notation() == book_move_str:
                        return valid_move
        return None

    def _order_moves(self, engine: ChessEngine, moves: List[Move]) -> List[Move]:
        """Order moves to improve alpha-beta pruning efficiency (MVV-LVA)."""
        def move_score(move):
            score = 0
            # Captures: prioritize capturing high-value pieces with low-value pieces
            if move.piece_captured != "--":
                score += 10 * self.PIECE_VALUES.get(move.piece_captured[1], 0) \
                         - self.PIECE_VALUES.get(move.piece_moved[1], 0)
            # Promotions
            if move.is_pawn_promotion:
                score += 900
            # Castling is generally good
            if move.is_castle:
                score += 60
            # Center control
            if move.end_row in (3, 4) and move.end_col in (3, 4):
                score += 20
            return score

        return sorted(moves, key=move_score, reverse=True)

    def _minimax(self, engine: ChessEngine, depth: int, alpha: float, beta: float,
                 maximizing: bool) -> float:
        """Minimax algorithm with alpha-beta pruning."""
        self.nodes_searched += 1

        if self._check_timeout():
            return 0

        valid_moves = engine.get_valid_moves()

        if len(valid_moves) == 0:
            if engine._is_in_check():
                return float('-inf') if maximizing else float('inf')
            else:
                return 0

        # Check for draws
        draw = engine.is_draw()
        if draw:
            return 0

        if depth == 0:
            return self._evaluate_position(engine)

        # Order moves for better pruning
        ordered_moves = self._order_moves(engine, valid_moves)

        if maximizing:
            max_eval = float('-inf')
            for move in ordered_moves:
                engine.make_move(move)
                eval_score = self._minimax(engine, depth - 1, alpha, beta, False)
                engine.undo_move()
                max_eval = max(max_eval, eval_score)
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break
            return max_eval
        else:
            min_eval = float('inf')
            for move in ordered_moves:
                engine.make_move(move)
                eval_score = self._minimax(engine, depth - 1, alpha, beta, True)
                engine.undo_move()
                min_eval = min(min_eval, eval_score)
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break
            return min_eval

    def _evaluate_position(self, engine: ChessEngine) -> float:
        """Evaluate current board position. Positive = white advantage."""
        if engine.checkmate:
            return float('-inf') if engine.white_to_move else float('inf')
        if engine.stalemate:
            return 0

        score = 0
        total_material = 0

        for row in range(8):
            for col in range(8):
                piece = engine.board[row][col]
                if piece != "--":
                    total_material += self.PIECE_VALUES.get(piece[1], 0)

        is_endgame = total_material < 2600

        for row in range(8):
            for col in range(8):
                piece = engine.board[row][col]
                if piece != "--":
                    piece_type = piece[1]
                    piece_value = self.PIECE_VALUES.get(piece_type, 0)

                    if piece_type == 'K' and is_endgame:
                        table = self.KING_END_TABLE
                    else:
                        table = self.PIECE_TABLES.get(piece_type)

                    if piece[0] == 'w':
                        positional_value = table[row][col] if table else 0
                        score += piece_value + positional_value
                    else:
                        positional_value = table[7 - row][col] if table else 0
                        score -= piece_value + positional_value

        # Mobility bonus
        current_moves = len(engine.get_valid_moves())
        engine.white_to_move = not engine.white_to_move
        opponent_moves = len(engine.get_valid_moves())
        engine.white_to_move = not engine.white_to_move

        if engine.white_to_move:
            score += (current_moves - opponent_moves) * 5
        else:
            score -= (current_moves - opponent_moves) * 5

        # Bishop pair bonus
        white_bishops = sum(1 for r in range(8) for c in range(8) if engine.board[r][c] == 'wB')
        black_bishops = sum(1 for r in range(8) for c in range(8) if engine.board[r][c] == 'bB')
        if white_bishops >= 2:
            score += 30
        if black_bishops >= 2:
            score -= 30

        return score

    def _check_timeout(self) -> bool:
        if time.time() - self.search_start_time > self.MAX_SEARCH_TIME:
            self.timeout_reached = True
            return True
        return False

    def set_difficulty(self, level: str) -> None:
        """Set AI difficulty: 'easy', 'medium', 'hard', 'expert'."""
        if not isinstance(level, str):
            self.depth = 3
            return
        difficulties = {
            'easy': 1,
            'medium': 2,
            'hard': 3,
            'expert': 4
        }
        self.depth = min(difficulties.get(level, 3), self.MAX_DEPTH)


class RandomAI:
    """Simple AI that makes random moves."""
    def get_best_move(self, engine: ChessEngine, valid_moves: List[Move]) -> Optional[Move]:
        if not valid_moves:
            return None
        return random.choice(valid_moves)
