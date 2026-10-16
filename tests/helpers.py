"""Shared test helpers: build a ChessEngine from FEN and compare engine/board move sets."""

from typing import List, Set, Tuple

from chess_engine import ChessEngine, Move

_FEN_TO_ENGINE = {"P": "wP", "N": "wN", "B": "wB", "R": "wR", "Q": "wQ", "K": "wK",
                  "p": "bP", "n": "bN", "b": "bB", "r": "bR", "q": "bQ", "k": "bK"}


def engine_from_fen(fen: str) -> ChessEngine:
    """A ChessEngine set up from a FEN string (the engine itself has no FEN support)."""
    parts = fen.split()
    engine = ChessEngine()
    engine.board = []
    for text in parts[0].split("/"):
        row: List[str] = []
        for ch in text:
            if ch.isdigit():
                row += ["--"] * int(ch)
            else:
                row.append(_FEN_TO_ENGINE[ch])
        engine.board.append(row)
    for r in range(8):
        for c in range(8):
            if engine.board[r][c] == "wK":
                engine.white_king_location = (r, c)
            elif engine.board[r][c] == "bK":
                engine.black_king_location = (r, c)
    engine.white_to_move = parts[1] == "w"
    engine.white_castle_kingside = "K" in parts[2]
    engine.white_castle_queenside = "Q" in parts[2]
    engine.black_castle_kingside = "k" in parts[2]
    engine.black_castle_queenside = "q" in parts[2]
    engine.castle_rights_log = [(engine.white_castle_kingside, engine.white_castle_queenside,
                                 engine.black_castle_kingside, engine.black_castle_queenside)]
    if parts[3] != "-":
        engine.enpassant_possible = (8 - int(parts[3][1]), "abcdefgh".index(parts[3][0]))
    engine.halfmove_clock = int(parts[4]) if len(parts) > 4 else 0
    engine.halfmove_clock_log = [engine.halfmove_clock]
    return engine


def play(engine: ChessEngine, *coordinate_moves: str) -> None:
    """Apply moves written like 'e2e4' to a ChessEngine, failing loudly on an illegal one."""
    for text in coordinate_moves:
        for move in engine.get_valid_moves():
            if move.get_coordinate_notation() == text:
                engine.make_move(move)
                break
        else:
            raise AssertionError(f"illegal move {text} in this position")


def engine_pairs(engine: ChessEngine) -> Set[Tuple[int, int]]:
    """Legal moves as a set of (from_square, to_square), promotions collapsed."""
    return {(m.start_row * 8 + m.start_col, m.end_row * 8 + m.end_col)
            for m in engine.get_valid_moves()}


def board_pairs(board) -> Set[Tuple[int, int]]:
    return {(m & 63, (m >> 6) & 63) for m in board.legal_moves()}


def uci_set(board) -> Set[str]:
    return {board.move_to_uci(m) for m in board.legal_moves()}


def engine_move(engine: ChessEngine, text: str) -> Move:
    for move in engine.get_valid_moves():
        if move.get_coordinate_notation() == text:
            return move
    raise AssertionError(f"illegal move {text}")
