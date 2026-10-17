"""Shared test helpers: build a ChessEngine from FEN and compare engine/board move sets."""

from typing import Set

from chess_engine import ChessEngine, Move


def engine_from_fen(fen: str) -> ChessEngine:
    """A ChessEngine set up from a FEN string (raises ValueError for a bad one)."""
    return ChessEngine.from_fen(fen)


def play(engine: ChessEngine, *coordinate_moves: str) -> None:
    """Apply moves written like 'e2e4' (or 'e7e8q') to a ChessEngine, failing loudly on an
    illegal one. Goes through ``ChessEngine.play``, so check, mate and draws are tracked."""
    for text in coordinate_moves:
        try:
            engine.play_uci(text)
        except ValueError as error:
            raise AssertionError(f"illegal move {text} in this position: {error}") from error


def engine_uci(engine: ChessEngine) -> Set[str]:
    """Legal moves as UCI text, one entry per promotion piece."""
    return {m.get_coordinate_notation() for m in engine.get_valid_moves()}


def uci_set(board) -> Set[str]:
    return {board.move_to_uci(m) for m in board.legal_moves()}


def engine_move(engine: ChessEngine, text: str) -> Move:
    for move in engine.get_valid_moves():
        if move.get_coordinate_notation() == text:
            return move
    raise AssertionError(f"illegal move {text}")
