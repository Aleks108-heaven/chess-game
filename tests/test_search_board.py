"""SearchBoard: move generation, incremental state, rules and conversions."""

import random

import pytest

from ai.board import START_FEN, InvalidPositionError, SearchBoard
from ai.pieces import engine_piece
from chess_engine import ChessEngine
from tests.helpers import board_pairs, engine_from_fen, engine_pairs, play, uci_set

# Canonical perft node counts (https://www.chessprogramming.org/Perft_Results).
PERFT_CASES = [
    ("startpos", START_FEN, [20, 400, 8902, 197281]),
    ("kiwipete", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
     [48, 2039, 97862]),
    ("position3", "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", [14, 191, 2812, 43238]),
    ("position4", "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
     [6, 264, 9467]),
    ("position5", "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8", [44, 1486, 62379]),
    ("position6", "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10",
     [46, 2079, 89890]),
]


def snapshot(board):
    return (board.hash, board.mg, board.eg, board.phase, board.pawn_key, tuple(board.bishops),
            board.castling, board.ep, board.halfmove, board.fullmove, board.side,
            tuple(board.king_sq), tuple(board.sq), len(board.stack), len(board.keys))


# --- Move generator correctness -----------------------------------------------------------

@pytest.mark.parametrize("name,fen,counts", PERFT_CASES, ids=[c[0] for c in PERFT_CASES])
def test_perft_matches_published_counts(name, fen, counts):
    board = SearchBoard.from_fen(fen)
    before = snapshot(board)
    for depth, expected in enumerate(counts, start=1):
        assert board.perft(depth) == expected, f"{name} perft({depth})"
    assert snapshot(board) == before  # make/unmake left nothing behind


def test_move_sets_match_chess_engine_on_tricky_positions():
    """Independent cross-check: the UI's ChessEngine and SearchBoard agree move for move."""
    tricky = [fen for name, fen, _ in PERFT_CASES[1:]] + ["8/8/8/KPp4r/8/8/8/7k w - c6 0 1"]
    for fen in tricky:
        engine = engine_from_fen(fen)
        board = SearchBoard.from_fen(fen)
        assert engine_pairs(engine) == board_pairs(board), fen
        for move in engine.get_valid_moves():  # one ply deeper
            engine.make_move(move)
            board.make(board.move_from_engine(move))
            assert engine_pairs(engine) == board_pairs(board), (fen, move.get_coordinate_notation())
            engine.undo_move()
            board.unmake()


@pytest.mark.slow
def test_random_games_stay_in_sync_with_chess_engine():
    rng = random.Random(1234)
    for game in range(5):
        engine, board = ChessEngine(), SearchBoard.start()
        for ply in range(90):
            moves = engine.get_valid_moves()
            assert engine_pairs(engine) == board_pairs(board), f"game {game} ply {ply}"
            if not moves:
                break
            move = rng.choice(moves)
            if move.is_pawn_promotion:
                move.promotion_piece = rng.choice("QRBN")
            engine.make_move(move)
            board.make(board.move_from_engine(move))


# --- Incremental state --------------------------------------------------------------------

def test_incremental_state_equals_full_recompute_and_unmake_restores():
    rng = random.Random(7)
    for _ in range(6):
        board = SearchBoard.start()
        start = snapshot(board)
        for _ply in range(120):
            moves = board.legal_moves()
            if not moves:
                break
            board.make(rng.choice(moves))
            fresh = SearchBoard.from_fen(board.to_fen())
            assert (board.hash, board.mg, board.eg, board.phase, board.pawn_key,
                    board.bishops) == (fresh.hash, fresh.mg, fresh.eg, fresh.phase,
                                       fresh.pawn_key, fresh.bishops), board.to_fen()
        while board.stack:
            board.unmake()
        assert snapshot(board) == start


def test_null_move_round_trip():
    board = SearchBoard.from_fen("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2")
    before = snapshot(board)
    board.make_null()
    assert board.side != before[10] and board.ep == -1
    board.unmake_null()
    assert snapshot(board) == before


def test_transposition_reaches_the_same_hash():
    a, b = SearchBoard.start(), SearchBoard.start()
    for text in ("g1f3", "g8f6", "g2g3"):
        a.make(a.move_from_uci(text))
    for text in ("g2g3", "g8f6", "g1f3"):
        b.make(b.move_from_uci(text))
    assert a.hash == b.hash


def test_en_passant_target_only_matters_when_a_capture_is_possible():
    """1.e4 e5 2.Nf3 and 1.Nf3 e5 2.e4 are the same position unless ep is really capturable."""
    a, b = SearchBoard.start(), SearchBoard.start()
    for text in ("e2e4", "e7e5", "g1f3"):
        a.make(a.move_from_uci(text))
    for text in ("g1f3", "e7e5", "e2e4"):
        b.make(b.move_from_uci(text))
    assert a.hash == b.hash


# --- Rules ----------------------------------------------------------------------------------

def test_castling_is_generated_when_legal():
    moves = uci_set(SearchBoard.from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"))
    assert {"e1g1", "e1c1"} <= moves


@pytest.mark.parametrize("fen,forbidden,allowed", [
    ("r3k2r/8/8/8/8/8/5r2/R3K2R w KQkq - 0 1", "e1g1", "e1c1"),   # f1 attacked: no O-O
    ("r3k2r/8/8/8/8/8/4r3/R3K2R w KQkq - 0 1", "e1g1", None),     # in check: no castling
    ("r3k2r/8/8/8/8/8/4r3/R3K2R w KQkq - 0 1", "e1c1", None),
    ("r3k2r/8/8/8/8/8/1r6/R3K2R w KQkq - 0 1", None, "e1c1"),     # b1 attacked is fine
    ("r3k2r/8/8/8/8/8/8/Rn2K2R w KQkq - 0 1", "e1c1", "e1g1"),    # piece in the way
], ids=["through-attack", "in-check-O-O", "in-check-O-O-O", "b1-attacked-ok", "blocked"])
def test_castling_restrictions(fen, forbidden, allowed):
    moves = uci_set(SearchBoard.from_fen(fen))
    if forbidden:
        assert forbidden not in moves
    if allowed:
        assert allowed in moves


def test_castling_rights_are_lost_when_king_or_rook_moves_or_rook_is_captured():
    board = SearchBoard.from_fen("4k3/8/8/8/8/8/6b1/R3K2R b KQ - 0 1")
    board.make(board.move_from_uci("g2h1"))      # captures the h1 rook
    assert "e1g1" not in uci_set(board) and "e1c1" in uci_set(board)

    board = SearchBoard.from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    board.make(board.move_from_uci("h1g1"))
    board.make(board.move_from_uci("h8g8"))
    board.make(board.move_from_uci("g1h1"))
    board.make(board.move_from_uci("g8h8"))      # rooks are back, but the rights are gone
    assert "e1g1" not in uci_set(board) and "e1c1" in uci_set(board)


def test_en_passant_capture_and_its_pin_exception():
    board = SearchBoard.from_fen("rnbqkbnr/ppp1pppp/8/8/3pP3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 3")
    assert "d4e3" in uci_set(board)
    board.make(board.move_from_uci("d4e3"))
    assert board.sq[4 * 8 + 4] == 0, "the captured pawn must disappear from e4"
    # Capturing en passant here would expose the white king to the rook: illegal.
    pinned = SearchBoard.from_fen("8/8/8/KPp4r/8/8/8/7k w - c6 0 1")
    assert "b5c6" not in uci_set(pinned)
    # The right to capture expires after one move.
    board = SearchBoard.from_fen("rnbqkbnr/ppp1pppp/8/8/3pP3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 3")
    board.make(board.move_from_uci("a7a6"))
    board.make(board.move_from_uci("a2a3"))
    assert "d4e3" not in uci_set(board)


def test_promotions_offer_all_four_pieces_including_captures():
    board = SearchBoard.from_fen("1n5k/P7/8/8/8/8/8/K7 w - - 0 1")
    moves = uci_set(board)
    assert {"a7a8q", "a7a8r", "a7a8b", "a7a8n", "a7b8q", "a7b8r", "a7b8b", "a7b8n"} <= moves
    board.make(board.move_from_uci("a7b8n"))
    assert board.sq[1] == 2, "an underpromotion must leave a white knight on b8"


def test_repetition_and_fifty_move_counters():
    board = SearchBoard.start()
    assert not board.is_repetition()
    for text in ("g1f3", "g8f6", "f3g1", "f6g8"):
        board.make(board.move_from_uci(text))
    assert board.is_repetition()
    assert board.halfmove == 4
    board.make(board.move_from_uci("e2e4"))
    assert board.halfmove == 0


@pytest.mark.parametrize("fen,expected", [
    ("8/8/8/4k3/8/8/8/K7 w - - 0 1", True),       # K v K
    ("8/8/8/4k3/8/8/8/K1N5 w - - 0 1", True),     # K+N v K
    ("8/8/8/4k3/8/8/8/KB6 w - - 0 1", True),      # K+B v K
    ("8/8/8/4k3/8/8/4P3/K7 w - - 0 1", False),    # a pawn can promote
    ("8/8/8/4k3/8/8/8/KR6 w - - 0 1", False),
    ("8/8/8/4k3/8/8/8/KQ6 w - - 0 1", False),
    ("8/8/8/4k3/8/8/8/KNN5 w - - 0 1", False),    # two knights: not automatically drawn
])
def test_insufficient_material(fen, expected):
    assert SearchBoard.from_fen(fen).is_insufficient_material() is expected


# --- FEN and engine conversion --------------------------------------------------------------

@pytest.mark.parametrize("fen", [
    START_FEN,
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "rnbqkbnr/ppp1pppp/8/8/3pP3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 3",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 12 40",
])
def test_fen_round_trip(fen):
    assert SearchBoard.from_fen(fen).to_fen() == fen


@pytest.mark.parametrize("bad", [
    "", "8/8/8/8/8/8/8 w - - 0 1", "9/8/8/8/8/8/8/8 w - - 0 1",
    "8/8/8/8/8/8/8/8 w - - 0 1",                              # no kings
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNX w KQkq - 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR x KQkq - 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkz - 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq z9 0 1",
])
def test_malformed_fen_is_rejected(bad):
    with pytest.raises((InvalidPositionError, ValueError)):
        SearchBoard.from_fen(bad)


def test_from_engine_replays_history_for_repetition_detection():
    engine = ChessEngine()
    play(engine, "g1f3", "g8f6", "f3g1", "f6g8")
    board = SearchBoard.from_engine(engine)
    assert len(board.keys) == 5
    assert board.is_repetition()
    assert board.to_fen().split()[:4] == SearchBoard.start().to_fen().split()[:4]


def test_from_engine_handles_a_custom_position_without_history():
    engine = engine_from_fen("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
    board = SearchBoard.from_engine(engine)
    assert board.to_fen().split()[:4] == (
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -".split())
    assert len(board.keys) == 1


def test_from_engine_after_en_passant_and_castling():
    engine = ChessEngine()
    play(engine, "e2e4", "a7a6", "e4e5", "d7d5", "e5d6", "g8f6", "g1f3", "b8c6",
         "f1e2", "e7e6", "e1g1")  # en passant capture, then castling
    board = SearchBoard.from_engine(engine)
    for r in range(8):
        for c in range(8):
            assert engine_piece(board.sq[r * 8 + c]) == engine.board[r][c]
    assert board.castling & 3 == 0  # White has castled
    assert len(board.keys) == len(engine.move_log) + 1
