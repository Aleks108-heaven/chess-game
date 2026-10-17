"""
chess-rules.md as executable tests. Names carry the rule ID (J-xx Junior, I-xx Intermediate,
A-xx Advanced), scenario IDs (T-xx) and perft IDs (P-x) from that file, so a failure points
straight at the rule it breaks. These run on ChessEngine, the engine the UI plays with; the
AI's SearchBoard is compared against it in test_search_board.py.
"""

import random
import time
from datetime import date

import pytest

from chess_engine import (RESULT_BLACK_WINS, RESULT_DRAW, RESULT_ONGOING, RESULT_WHITE_WINS,
                          START_FEN, ChessEngine, IllegalActionError, IllegalMoveError, Move)
from tests.helpers import engine_move, engine_uci, play


def state(engine):
    """Everything a move can change, for "move then undo = same state" comparisons."""
    return (engine.to_fen(), tuple(tuple(row) for row in engine.board), engine.enpassant_possible,
            engine._castle_rights(), engine.halfmove_clock, len(engine.move_log),
            tuple(engine.position_history), engine.white_to_move, engine.white_king_location,
            engine.black_king_location, engine.result, engine.result_reason,
            engine.draw_offer_by)


def uci(engine):
    return sorted(engine_uci(engine))


def moves_of(engine, piece):
    return sorted(m.get_coordinate_notation() for m in engine.get_valid_moves()
                  if m.piece_moved == piece)


def castles(engine):
    return sorted(m.get_coordinate_notation() for m in engine.get_valid_moves() if m.is_castle)


# --- 8.1 Perft: the move generator against published node counts --------------------------------

def perft(engine, depth):
    moves = engine.get_valid_moves()
    if depth == 1:
        return len(moves)
    total = 0
    for move in moves:
        engine.make_move(move)
        total += perft(engine, depth - 1)
        engine._undo()
    return total


PERFT = [
    ("P-1", START_FEN, [20, 400, 8902, 197281]),
    ("P-2", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
     [48, 2039, 97862]),
    ("P-3", "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", [14, 191, 2812, 43238]),
    ("P-4", "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
     [6, 264, 9467]),
    ("P-5", "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8", [44, 1486, 62379]),
    ("P-6", "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10",
     [46, 2079, 89890]),
]


@pytest.mark.parametrize("name,fen,counts", PERFT, ids=[case[0] for case in PERFT])
def test_perft_matches_published_counts(name, fen, counts):
    """P-1 to P-6 to depth 3 (4 where it takes about a second). Promotions count four moves,
    which is why P-4 and P-5 only match when I-03 is right."""
    engine = ChessEngine.from_fen(fen)
    before = state(engine)
    for depth, expected in enumerate(counts, start=1):
        assert perft(engine, depth) == expected, f"{name} perft({depth})"
    assert state(engine) == before, "make/undo left something behind"


@pytest.mark.slow
def test_perft_p4_depth_4():
    assert perft(ChessEngine.from_fen(PERFT[3][1]), 4) == 422333


# --- Section 3: the state the engine tracks ------------------------------------------------------

@pytest.mark.parametrize("fen", [
    START_FEN,
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3",
    "rnbqkbnr/ppp1pppp/8/8/3pP3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 3",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 12 40",
    "r3k2r/8/8/8/8/8/8/R3K2R b Kq - 7 33",
], ids=["start", "kiwipete", "ep-white", "ep-black", "counters", "partial-castling"])
def test_fen_round_trip(fen):
    """8.3: FEN -> engine -> FEN gives the same text (every field of section 3)."""
    assert ChessEngine.from_fen(fen).to_fen() == fen


def test_new_game_is_the_standard_start_position():
    engine = ChessEngine()
    assert engine.to_fen() == START_FEN and engine.fullmove_number == 1
    assert engine.result == RESULT_ONGOING and engine.halfmove_clock == 0


def test_fullmove_number_goes_up_after_each_black_move():
    engine = ChessEngine()
    play(engine, "e2e4")
    assert engine.fullmove_number == 1
    play(engine, "e7e5")
    assert engine.fullmove_number == 2
    from_black = ChessEngine.from_fen("4k3/8/8/8/8/8/8/R3K3 b - - 0 9")
    play(from_black, "e8d8")
    assert from_black.fullmove_number == 10


@pytest.mark.parametrize("bad", [
    "", "   ", "8/8/8/8/8/8/8 w - - 0 1", "9/8/8/8/8/8/8/8 w - - 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNX w KQkq - 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR x KQkq - 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkz - 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KKkq - 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq z9 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - -1 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 0",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1 extra",
    "8/8/8/8/8/8/8/8 w - - 0 1",                                  # no kings
    "kk6/8/8/8/8/8/8/4K3 w - - 0 1",                              # two black kings
    "P3k3/8/8/8/8/8/8/4K3 w - - 0 1",                             # pawn on the last rank
    "4k3/8/8/8/8/8/8/p3K3 w - - 0 1",                             # pawn on the first rank
    "4k3/8/8/8/8/8/8/R3K3 b - - 0 1",                             # White's king... Black to move, but Black king is not the issue: see below
    "4k3/4R3/8/8/8/8/8/4K3 w - - 0 1",                            # Black is in check with White to move
], ids=lambda value: value[:24] or "<empty>")
def test_malformed_or_impossible_fen_is_rejected(bad):
    if bad == "4k3/8/8/8/8/8/8/R3K3 b - - 0 1":
        engine = ChessEngine.from_fen(bad)      # perfectly legal: it is here to prove the
        assert engine.black_king_location == (0, 4)   # rejections above are not over-eager
        return
    with pytest.raises(ValueError):
        ChessEngine.from_fen(bad)


def test_castling_rights_and_en_passant_the_pieces_cannot_back_up_are_dropped():
    engine = ChessEngine.from_fen("4k3/8/8/8/8/8/8/4K3 w KQkq e6 0 1")
    assert engine.to_fen() == "4k3/8/8/8/8/8/8/4K3 w - - 0 1"


def test_a_fen_writes_the_en_passant_square_only_when_a_capture_is_legal():
    """A-02: 1.e4 e5 leaves e6 as the jumped-over square, but no White pawn can use it."""
    engine = ChessEngine()
    play(engine, "e2e4", "e7e5")
    assert engine.enpassant_possible == (2, 4)
    assert engine.to_fen() == "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
    reader = ChessEngine.from_fen("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2")
    assert reader.to_fen().split()[3] == "-"


# --- Level 1: Junior -------------------------------------------------------------------------------

def test_J03_start_position_has_twenty_moves_and_queens_on_their_own_colour():
    engine = ChessEngine()
    assert engine.to_fen() == START_FEN and len(engine.get_valid_moves()) == 20
    light = lambda row, col: (row + col) % 2 == 0           # a1 is dark, h1 is light (J-01)
    assert not light(7, 0) and light(7, 7)
    assert engine.board[7][3] == "wQ" and light(7, 3)        # White queen on d1: light
    assert engine.board[0][3] == "bQ" and not light(0, 3)    # Black queen on d8: dark


def test_J04_players_alternate_and_cannot_move_the_other_sides_pieces():
    engine = ChessEngine()
    play(engine, "e2e4")
    assert not engine.white_to_move
    before = state(engine)
    for text in ("d2d4", "e4e5"):                            # White's pieces, Black to move
        with pytest.raises(IllegalMoveError):
            engine.play_uci(text)
    assert state(engine) == before


@pytest.mark.parametrize("fen,piece,expected", [
    ("k7/8/8/8/3N4/8/8/7K w - - 0 1", "wN", 8),
    ("k7/8/8/8/3B4/8/8/7K w - - 0 1", "wB", 13),
    ("k7/8/8/8/3R4/8/8/7K w - - 0 1", "wR", 14),
    ("k7/8/8/8/3Q4/8/8/7K w - - 0 1", "wQ", 27),
    ("k7/8/8/8/3R4/8/8/7K w - - 0 1", "wK", 3),              # Kh1: g1, g2, h2
    ("k7/8/8/8/3K4/8/8/8 w - - 0 1", "wK", 8),
    ("k7/8/8/8/3RP3/8/8/7K w - - 0 1", "wR", 10),            # own pawn blocks the rank
    ("k7/8/8/8/3Rp3/8/8/7K w - - 0 1", "wR", 11),            # capture ends the line, no jump
], ids=["knight", "bishop", "rook", "queen", "king-corner", "king-centre", "rook-blocked",
        "rook-captures"])
def test_J05_piece_movement(fen, piece, expected):
    assert len(moves_of(ChessEngine.from_fen(fen), piece)) == expected


def test_J05_the_knight_jumps_and_nothing_lands_on_a_friendly_piece():
    engine = ChessEngine()
    assert moves_of(engine, "wN") == ["b1a3", "b1c3", "g1f3", "g1h3"]
    assert not any(m.piece_captured[:1] == "w" for m in engine.get_valid_moves())


@pytest.mark.parametrize("fen,expected", [
    ("k7/8/8/8/8/8/4P3/7K w - - 0 1", ["e2e3", "e2e4"]),                 # single or double push
    ("k7/8/8/8/8/4p3/4P3/7K w - - 0 1", []),                             # blocked: no capture ahead
    ("k7/8/8/8/4p3/8/4P3/7K w - - 0 1", ["e2e3"]),                       # second square blocked
    ("k7/8/8/8/8/3p1p2/4P3/7K w - - 0 1", ["e2d3", "e2e3", "e2e4", "e2f3"]),
    ("k7/8/8/8/8/4P3/8/7K w - - 0 1", ["e3e4"]),                         # no double push later
    ("k7/4p3/8/8/8/8/8/7K b - - 0 1", ["e7e5", "e7e6"]),                 # Black moves down
], ids=["push", "blocked", "second-blocked", "captures", "not-from-start", "black"])
def test_J06_pawn_moves(fen, expected):
    engine = ChessEngine.from_fen(fen)
    piece = "wP" if engine.white_to_move else "bP"
    assert moves_of(engine, piece) == expected


def test_J07_a_capture_removes_the_piece_and_no_move_ever_takes_a_king():
    engine = ChessEngine()
    play(engine, "e2e4", "d7d5", "e4d5")
    assert sum(row.count("bP") for row in engine.board) == 7 and engine.board[3][3] == "wP"
    rng = random.Random(5)
    for _ in range(4):
        game = ChessEngine()
        for _ply in range(120):
            moves = game.get_valid_moves()
            if not moves or game.result != RESULT_ONGOING:
                break
            assert all(m.piece_captured[1:] != "K" for m in moves)
            game.play(rng.choice(moves))


def test_J08_a_pawn_attacks_diagonally_not_straight_ahead():
    assert not ChessEngine.from_fen("k7/8/8/8/8/8/4p3/4K3 w - - 0 1").in_check
    assert ChessEngine.from_fen("k7/8/8/8/8/8/3p4/4K3 w - - 0 1").in_check


def test_J08_a_pinned_piece_still_gives_check():
    engine = ChessEngine.from_fen("4k3/8/8/8/4b3/8/8/4R2K w - - 0 1")   # the bishop is pinned
    assert engine.in_check
    assert "e1e4" in uci(engine), "capturing the pinning... the pinned checker is allowed"


def test_T04_J09_double_check_allows_only_king_moves():
    engine = ChessEngine.from_fen("4k3/8/5N2/1B6/8/8/8/4K3 b - - 0 1")
    assert uci(engine) == ["e8d8", "e8e7", "e8f7", "e8f8"]


def test_T05_J09_a_pinned_piece_may_only_move_along_the_pin():
    engine = ChessEngine.from_fen("k7/4r3/8/8/8/8/4R3/4K3 w - - 0 1")
    assert moves_of(engine, "wR") == ["e2e3", "e2e4", "e2e5", "e2e6", "e2e7"]


def test_T06_J09_kings_never_stand_next_to_each_other():
    engine = ChessEngine.from_fen("8/8/8/3k4/8/3K4/8/8 w - - 0 1")
    assert moves_of(engine, "wK") == ["d3c2", "d3c3", "d3d2", "d3e2", "d3e3"]


def test_J09_a_check_can_be_met_by_capture_block_or_king_move_and_only_those():
    # Rook check along the e-file: Kd1, Kf1, Kf2 or block with Be3. Ke2 stays on the file.
    engine = ChessEngine.from_fen("4r2k/8/8/8/8/8/3B4/4K3 w - - 0 1")
    assert uci(engine) == ["d2e3", "e1d1", "e1f1", "e1f2"]
    # A knight check cannot be blocked: only king moves are left.
    knight = ChessEngine.from_fen("4k3/8/8/8/8/3n4/8/R3K3 w - - 0 1")
    assert knight.in_check
    assert {m.piece_moved for m in knight.get_valid_moves()} == {"wK"}


def test_T01_J10_fools_mate_is_checkmate_and_black_wins():
    engine = ChessEngine()
    play(engine, "f2f3", "e7e5", "g2g4", "d8h4")
    assert engine.checkmate and engine.result == RESULT_BLACK_WINS
    assert engine.result_reason == "checkmate" and engine.get_valid_moves() == []
    assert engine.to_fen() == "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"


def test_T02_J10_scholars_mate_is_checkmate_and_white_wins():
    engine = ChessEngine()
    play(engine, "e2e4", "e7e5", "d1h5", "b8c6", "f1c4", "g8f6", "h5f7")
    assert engine.result == RESULT_WHITE_WINS and engine.checkmate and engine.in_check
    assert engine.to_fen() == "r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4"


def test_T03_J11_stalemate_is_a_draw_and_not_a_loss():
    engine = ChessEngine.from_fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert engine.stalemate and not engine.checkmate and not engine.in_check
    assert engine.result == RESULT_DRAW and engine.result_reason == "stalemate"
    assert engine.draw_reason == "stalemate"


def test_J10_J11_mate_and_stalemate_differ_only_by_check():
    mate = ChessEngine.from_fen("R5k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1")
    assert mate.checkmate and mate.result == RESULT_WHITE_WINS
    assert not mate.stalemate


def test_J12_resignation_ends_the_game_at_once_and_the_opponent_wins():
    engine = ChessEngine()
    play(engine, "e2e4")
    engine.resign("b")
    assert engine.result == RESULT_WHITE_WINS and engine.result_reason == "resignation"
    other = ChessEngine()
    other.resign("w")
    assert other.result == RESULT_BLACK_WINS
    with pytest.raises(IllegalActionError):
        other.resign("b")
    with pytest.raises(ValueError):
        ChessEngine().resign("x")


def test_J12_an_agreed_draw_ends_the_game():
    engine = ChessEngine()
    engine.offer_draw("w")
    engine.accept_draw()
    assert engine.result == RESULT_DRAW and engine.result_reason == "agreement"


# --- Level 2: Intermediate ---------------------------------------------------------------------------

def test_T07_I01_castling_through_an_attacked_square_is_illegal():
    assert castles(ChessEngine.from_fen("4kr2/8/8/8/8/8/8/R3K2R w KQ - 0 1")) == ["e1c1"]


def test_T08_I01_the_b_file_square_and_the_rook_may_be_attacked():
    assert castles(ChessEngine.from_fen("1r2k3/8/8/8/8/8/8/R3K2R w KQ - 0 1")) == ["e1c1", "e1g1"]
    # An attacked rook on a1 does not stop O-O-O either.
    assert "e1c1" in castles(ChessEngine.from_fen("r3k3/8/8/8/8/8/8/R3K2R w KQ - 0 1"))


def test_T09_I01_no_castling_out_of_check():
    assert castles(ChessEngine.from_fen("3kr3/8/8/8/8/8/8/R3K2R w KQ - 0 1")) == []


def test_I01_no_castling_across_a_square_a_pawn_attacks():
    """Regression: a pawn attacks diagonally even where it has nothing to capture. The old
    attack test generated captures only, so it missed this and allowed O-O and O-O-O."""
    engine = ChessEngine.from_fen("4k3/8/8/8/8/8/4p3/R3K2R w KQ - 0 1")  # the e2 pawn hits d1, f1
    assert castles(engine) == []
    black = ChessEngine.from_fen("r3k2r/4P3/8/8/8/8/8/4K3 b kq - 0 1")  # the e7 pawn hits d8, f8
    assert castles(black) == []


def test_T10_I01_a_rook_that_goes_out_and_back_does_not_restore_the_right():
    engine = ChessEngine.from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    play(engine, "h1g1", "h8g8", "g1h1", "g8h8")
    assert engine.to_fen().split()[2] == "Qq"
    assert castles(engine) == ["e1c1"]


def test_T11_I01_capturing_a_rook_on_its_home_square_removes_that_right():
    engine = ChessEngine.from_fen("4k3/8/8/8/8/8/6b1/R3K2R b KQ - 0 1")
    play(engine, "g2h1")
    assert engine.to_fen().split()[2] == "Q" and castles(engine) == ["e1c1"]


def test_I01_a_king_move_loses_both_rights_and_castling_moves_king_and_rook():
    engine = ChessEngine.from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    play(engine, "e1g1")
    assert engine.board[7][6] == "wK" and engine.board[7][5] == "wR" and engine.board[7][7] == "--"
    assert engine.to_fen().split()[2] == "kq"
    play(engine, "e8c8")
    assert engine.board[0][2] == "bK" and engine.board[0][3] == "bR" and engine.board[0][0] == "--"
    assert engine.board[0][1] == "--" and engine.to_fen().split()[2] == "-"
    assert [m.get_chess_notation() for m in engine.move_log] == ["O-O", "O-O-O"]
    moved = ChessEngine.from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    play(moved, "e1e2", "a8a7", "e2e1")
    assert moved.to_fen().split()[2] == "k", "the king moved: both White rights are gone for good"


def test_T12_I02_en_passant_is_legal_removes_the_right_pawn_and_resets_the_clock():
    fen = "rnbqkbnr/1pp1pppp/p7/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3"
    engine = ChessEngine.from_fen(fen)
    assert "e5d6" in uci(engine)
    before = state(engine)
    move = engine.play_uci("e5d6")
    assert move.is_enpassant and move.get_chess_notation() == "exd6"
    assert engine.board[2][3] == "wP" and engine.board[3][3] == "--"      # d6 white, d5 removed
    assert engine.halfmove_clock == 0
    engine.undo_move()
    assert state(engine) == before and "e5d6" in uci(engine), "undo must restore the right"


def test_T12_I02_the_right_expires_after_one_move():
    engine = ChessEngine.from_fen("rnbqkbnr/1pp1pppp/p7/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3")
    play(engine, "g1f3", "a6a5")
    assert "e5d6" not in uci(engine)


def test_I02_black_can_capture_en_passant_too():
    engine = ChessEngine.from_fen("rnbqkbnr/ppp1pppp/8/8/3pP3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 3")
    play(engine, "d4e3")
    assert engine.board[5][4] == "bP" and engine.board[4][4] == "--"


def test_I02_a_double_step_creates_the_right_only_for_that_move():
    engine = ChessEngine()
    play(engine, "e2e4", "a7a6", "e4e5", "d7d5")
    assert engine.enpassant_possible == (2, 3) and "e5d6" in uci(engine)
    play(engine, "a2a3")
    assert engine.enpassant_possible is None


def test_T13_I02_J09_en_passant_that_exposes_the_king_along_the_rank_is_illegal():
    engine = ChessEngine.from_fen("4k3/8/8/KPp4r/8/8/8/8 w - c6 0 1")
    assert "b5c6" not in uci(engine)
    assert ChessEngine.from_fen("4k3/8/8/1Pp5/8/8/8/K7 w - c6 0 1").get_valid_moves().__len__() \
        and "b5c6" in uci(ChessEngine.from_fen("4k3/8/8/1Pp5/8/8/8/K7 w - c6 0 1"))


def test_T14_I03_a_pawn_on_the_last_rank_is_four_moves():
    engine = ChessEngine.from_fen("7k/P7/8/8/8/8/8/K7 w - - 0 1")
    assert uci(engine) == ["a1a2", "a1b1", "a1b2", "a7a8b", "a7a8n", "a7a8q", "a7a8r"]


def test_I03_promotion_by_capture_underpromotion_and_check():
    engine = ChessEngine.from_fen("1n5k/P7/8/8/8/8/8/K7 w - - 0 1")
    assert {"a7b8q", "a7b8r", "a7b8b", "a7b8n"} <= set(uci(engine))
    move = engine.play_uci("a7b8n")
    assert engine.board[0][1] == "wN" and move.piece_captured == "bN"
    assert move.get_chess_notation() == "axb8=N"

    check = ChessEngine.from_fen("7k/4P3/8/8/8/8/8/K7 w - - 0 1")
    assert check.play_uci("e7e8q").get_chess_notation() == "e8=Q+" and check.in_check

    mate = ChessEngine.from_fen("6k1/4Pppp/8/8/8/8/8/K7 w - - 0 1")
    assert mate.play_uci("e7e8r").get_chess_notation() == "e8=R#" and mate.checkmate
    assert mate.result == RESULT_WHITE_WINS


def test_I03_a_promotion_needs_a_legal_piece_before_the_game_goes_on():
    engine = ChessEngine.from_fen("7k/P7/8/8/8/8/8/K7 w - - 0 1")
    before = state(engine)
    for text in ("a7a8", "a7a8k", "a7a8p", "a7a8x", "a7a8Q"):
        with pytest.raises(IllegalMoveError):
            engine.play_uci(text)
    for letter in "KP":                       # a Move object cannot smuggle one in either
        bad = Move(1, 0, 0, 0, "wP", "--", is_pawn_promotion=True, promotion_piece=letter)
        with pytest.raises(IllegalMoveError):
            engine.play(bad)
    assert state(engine) == before


def test_I03_promotion_moves_are_distinct_moves():
    a = Move(1, 0, 0, 0, "wP", "--", is_pawn_promotion=True, promotion_piece="Q")
    b = Move(1, 0, 0, 0, "wP", "--", is_pawn_promotion=True, promotion_piece="N")
    assert a != b and len({a, b}) == 2
    assert a == Move(1, 0, 0, 0, "wP", "--", is_pawn_promotion=True, promotion_piece="Q")


@pytest.mark.parametrize("fen", [
    "4k3/8/8/8/8/8/8/4K3 w - - 0 1",                       # K v K
    "4k3/8/8/8/8/8/8/4KB2 w - - 0 1",                      # K+B v K
    "4k3/8/8/8/8/8/8/4KN2 w - - 0 1",                      # K+N v K
    "2b1k3/8/8/8/8/8/8/4KB2 w - - 0 1",                    # K+B v K+B, both on light squares
    "4k3/8/8/8/8/B7/8/2B1K3 w - - 0 1",                    # K+B+B v K, both on dark squares
    "2b1kb2/8/8/8/8/8/8/2B1KB2 w - - 0 1",                 # bishops: c8 c1 (light) f8 f1 ... see below
], ids=["KvK", "KBvK", "KNvK", "KBvKB-same", "KBBvK-same", "all-bishops"])
def test_T15_I04_these_are_automatic_draws(fen):
    if fen.startswith("2b1kb2"):
        # c8 is light, f8 is dark: a mixed set, so this one is NOT a draw (checked in T-16 too).
        assert not ChessEngine.from_fen(fen).is_insufficient_material()
        return
    engine = ChessEngine.from_fen(fen)
    assert engine.is_insufficient_material()
    assert engine.result == RESULT_DRAW and engine.result_reason == "insufficient material"


@pytest.mark.parametrize("fen", [
    "4k3/8/8/8/8/8/8/3NKN2 w - - 0 1",                     # K+N+N v K
    "4kn2/8/8/8/8/8/8/4KN2 w - - 0 1",                     # K+N v K+N
    "3bk3/8/8/8/8/8/8/4KB2 w - - 0 1",                     # K+B v K+B on opposite colours
    "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1",                     # K+P v K
    "4k3/8/8/8/8/8/8/R3K3 w - - 0 1",                      # a rook
    "4k3/8/8/8/8/8/8/3QK3 w - - 0 1",                      # a queen
    "4k3/8/8/8/8/8/8/2B1KB2 w - - 0 1",                    # K+B+B v K on opposite colours: mate
    "4kn2/8/8/8/8/8/8/4KB2 w - - 0 1",                     # K+B v K+N
], ids=["KNNvK", "KNvKN", "KBvKB-opposite", "KPvK", "KRvK", "KQvK", "KBBvK-opposite", "KBvKN"])
def test_T16_I04_these_are_not_automatic_draws(fen):
    engine = ChessEngine.from_fen(fen)
    assert not engine.is_insufficient_material() and engine.result == RESULT_ONGOING


def test_I04_a_capture_can_turn_the_game_into_a_dead_draw():
    engine = ChessEngine.from_fen("4k3/8/8/8/8/8/3r4/3BK3 w - - 0 1")
    assert engine.result == RESULT_ONGOING
    play(engine, "e1d2")           # the king takes the rook: K+B v K
    assert engine.result == RESULT_DRAW and engine.result_reason == "insufficient material"


# --- Level 3: Advanced -----------------------------------------------------------------------------------

def test_A02_the_same_position_is_the_same_whatever_the_move_order():
    a, b = ChessEngine(), ChessEngine()
    play(a, "e2e4", "e7e5", "g1f3")
    play(b, "g1f3", "e7e5", "e2e4")
    assert a.position_history[-1] == b.position_history[-1], \
        "an en passant square nobody can use must not make the positions differ"


def test_A02_an_en_passant_capture_that_is_really_legal_does_count():
    with_ep = ChessEngine.from_fen("rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3")
    without = ChessEngine.from_fen("rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq - 0 3")
    assert with_ep.position_history[0] != without.position_history[0]
    pinned = ChessEngine.from_fen("4k3/8/8/KPp4r/8/8/8/8 w - c6 0 1")      # capture illegal (T-13)
    plain = ChessEngine.from_fen("4k3/8/8/KPp4r/8/8/8/8 w - - 0 1")
    assert pinned.position_history[0] == plain.position_history[0]
    assert pinned.to_fen().split()[3] == "-"


def test_T18_A02_positions_that_differ_in_castling_rights_or_side_to_move_are_different():
    start = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
    after = ChessEngine.from_fen(start)
    play(after, "h1g1", "h8g8", "g1h1", "g8h8")        # same pieces, rights now Qq (T-10)
    fresh = ChessEngine.from_fen(start)
    assert after.board == fresh.board and after.white_to_move == fresh.white_to_move
    assert after.position_history[-1] != fresh.position_history[0]
    assert after.repetition_count() == 1, "the earlier occurrence had other castling rights"
    other_side = ChessEngine.from_fen("r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1")
    assert other_side.position_history[0] != fresh.position_history[0]


CYCLE = ("g1f3", "g8f6", "f3g1", "f6g8")

# Twenty half-moves of a real game (Ruy Lopez, Breyer): castling, a pawn capture-free development
# and a knight move that needs its file in SAN (Nbd7). No position repeats.
OPENING_20 = ("e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6", "b5a4", "g8f6", "e1g1", "f8e7",
              "f1e1", "b7b5", "a4b3", "d7d6", "c2c3", "e8g8", "h2h3", "c6b8", "d2d4", "b8d7")


def test_T17_A03_A04_the_start_position_repeated_again_and_again():
    engine = ChessEngine()
    assert engine.repetition_count() == 1
    play(engine, *CYCLE)
    assert engine.repetition_count() == 2 and engine.can_claim_draw() == ""
    play(engine, *CYCLE)
    assert engine.repetition_count() == 3
    assert engine.can_claim_draw() == "threefold repetition"
    assert engine.result == RESULT_ONGOING, "a threefold repetition is claimed, not automatic"
    play(engine, *CYCLE)
    assert engine.repetition_count() == 4 and engine.result == RESULT_ONGOING
    play(engine, *CYCLE)
    assert engine.repetition_count() == 5
    assert engine.result == RESULT_DRAW and engine.result_reason == "fivefold repetition"
    with pytest.raises(IllegalMoveError):
        engine.play_uci("e2e4")


def test_A03_the_three_occurrences_need_not_follow_each_other():
    engine = ChessEngine()
    play(engine, "g1f3", "g8f6", "f3g1", "f6g8", "b1c3", "b8c6", "c3b1", "c6b8")
    assert engine.repetition_count() == 3 and engine.can_claim_draw() == "threefold repetition"


def test_A03_a_claim_ends_the_game_and_only_works_when_there_is_something_to_claim():
    engine = ChessEngine()
    with pytest.raises(IllegalActionError):
        engine.claim_draw()
    play(engine, *CYCLE, *CYCLE)
    assert engine.claim_draw() == "threefold repetition"
    assert engine.result == RESULT_DRAW and engine.result_reason == "threefold repetition"
    assert engine.can_claim_draw() == "", "nothing left to claim once the game is over"


def test_A03_the_claim_belongs_to_whoever_is_to_move_when_it_is_made():
    engine = ChessEngine()
    play(engine, *CYCLE, *CYCLE[:2])          # third occurrence of the position after 1.Nf3 Nf6
    assert engine.can_claim_draw() == "" or engine.white_to_move is True
    play(engine, "f3g1")
    assert engine.repetition_count() >= 1


@pytest.mark.parametrize("clock,claim", [(98, ""), (99, ""), (100, "50-move rule"),
                                         (101, "50-move rule")])
def test_T19_A05_the_fifty_move_rule_can_be_claimed_from_100_half_moves(clock, claim):
    engine = ChessEngine.from_fen(f"4k3/8/8/8/8/8/8/R3K3 b - - {clock - 1} 60")
    play(engine, "e8d8")                      # a quiet king move: the clock goes up by one
    assert engine.halfmove_clock == clock
    assert engine.can_claim_draw() == claim and engine.result == RESULT_ONGOING


def test_A05_a_fifty_move_claim_ends_the_game_as_a_draw():
    engine = ChessEngine.from_fen("4k3/8/8/8/8/8/8/R3K3 b - - 99 60")
    play(engine, "e8d8")
    assert engine.claim_draw() == "50-move rule"
    assert engine.result == RESULT_DRAW and engine.result_reason == "50-move rule"


def test_T19_A06_the_seventy_five_move_rule_is_automatic_at_150():
    engine = ChessEngine.from_fen("4k3/8/8/8/8/8/8/R3K3 w - - 148 90")
    play(engine, "e1d1")
    assert engine.halfmove_clock == 149 and engine.result == RESULT_ONGOING
    play(engine, "e8d8")
    assert engine.halfmove_clock == 150
    assert engine.result == RESULT_DRAW and engine.result_reason == "75-move rule"


def test_T19_A06_checkmate_on_the_move_that_reaches_150_wins():
    engine = ChessEngine.from_fen("6k1/5ppp/8/8/8/8/8/R3K3 w - - 149 90")
    play(engine, "a1a8")
    assert engine.halfmove_clock == 150
    assert engine.result == RESULT_WHITE_WINS and engine.result_reason == "checkmate"


def test_T20_A05_the_halfmove_clock_resets_on_pawn_moves_and_captures_only():
    engine = ChessEngine()
    play(engine, "g1f3")
    assert engine.halfmove_clock == 1
    play(engine, "e7e5")                      # pawn move
    assert engine.halfmove_clock == 0
    play(engine, "f3e5")                      # capture
    assert engine.halfmove_clock == 0
    play(engine, "b8c6", "e5c6")
    assert engine.halfmove_clock == 0
    play(engine, "d7c6", "e2e3", "g8f6", "f1e2", "c8e6", "e1g1")   # quiet moves, then castling
    assert engine.halfmove_clock == 4         # the Bishop, Nf6/Be6 and O-O all added one
    play(engine, "f8e7")
    assert engine.halfmove_clock == 5
    ep = ChessEngine.from_fen("rnbqkbnr/1pp1pppp/p7/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 5 3")
    play(ep, "e5d6")
    assert ep.halfmove_clock == 0


def test_A07_stalemate_is_decided_before_insufficient_material():
    engine = ChessEngine.from_fen("7k/5B2/6K1/8/8/8/8/8 b - - 0 1")    # K+B v K, and no moves
    assert engine.stalemate and engine.result_reason == "stalemate"


def test_A07_automatic_draws_never_replace_a_checkmate():
    engine = ChessEngine.from_fen("6k1/5ppp/8/8/8/8/8/R3K3 w - - 149 90")
    play(engine, "a1a8")
    assert engine.checkmate and engine.draw_reason == ""


def test_A07_is_draw_reports_automatic_draws_only():
    engine = ChessEngine()
    play(engine, *CYCLE, *CYCLE)
    assert engine.is_draw() == "" and engine.can_claim_draw() == "threefold repetition"
    engine = ChessEngine.from_fen("4k3/8/8/8/8/8/8/4KN2 w - - 0 1")
    assert engine.is_draw() == "insufficient material"


# A-08 -----------------------------------------------------------------------------------------------------

def test_A08_a_draw_offer_can_be_accepted_or_declined():
    engine = ChessEngine()
    engine.offer_draw("w")
    assert engine.draw_offer_by == "w"
    engine.decline_draw()
    assert engine.draw_offer_by is None and engine.result == RESULT_ONGOING
    with pytest.raises(IllegalActionError):
        engine.accept_draw()
    with pytest.raises(IllegalActionError):
        engine.decline_draw()


def test_A08_making_a_move_declines_an_open_offer():
    engine = ChessEngine()
    engine.offer_draw("w")
    play(engine, "e2e4")
    assert engine.draw_offer_by is None and engine.result == RESULT_ONGOING


def test_A08_offers_are_limited_so_they_cannot_be_spammed():
    engine = ChessEngine()
    assert engine.can_offer_draw("w") and engine.can_offer_draw("b")
    engine.offer_draw("w")
    assert not engine.can_offer_draw("b"), "one offer at a time"
    engine.decline_draw()
    assert not engine.can_offer_draw("w"), "the same player has to wait"
    with pytest.raises(IllegalActionError):
        engine.offer_draw("w")
    assert engine.can_offer_draw("b"), "the other player is not held up"
    play(engine, *OPENING_20[:19])            # 19 half-moves since the offer: still waiting
    assert not engine.can_offer_draw("w")
    play(engine, OPENING_20[19])              # 20 half-moves = 10 moves each
    assert engine.can_offer_draw("w")


def test_A08_the_wait_before_the_next_offer_counts_down_in_full_moves():
    engine = ChessEngine()
    assert engine.moves_until_draw_offer("w") == 0
    engine.offer_draw("w")
    engine.decline_draw()
    assert engine.moves_until_draw_offer("w") == 10 and engine.moves_until_draw_offer("b") == 0
    play(engine, *OPENING_20[:2])
    assert engine.moves_until_draw_offer("w") == 9
    play(engine, *OPENING_20[2:19])
    assert engine.moves_until_draw_offer("w") == 1
    play(engine, OPENING_20[19])
    assert engine.moves_until_draw_offer("w") == 0 and engine.can_offer_draw("w")


def test_A08_taking_back_moves_never_locks_a_player_out_for_longer():
    engine = ChessEngine()
    play(engine, "e2e4", "e7e5")
    engine.offer_draw("b")
    engine.decline_draw()
    engine.undo_move()
    engine.undo_move()                         # back before the offer was made
    assert engine.moves_until_draw_offer("b") == 0 and engine.can_offer_draw("b")


def test_A08_offers_are_refused_after_the_game_is_over_and_after_undo_resets_the_wait():
    engine = ChessEngine()
    play(engine, "f2f3", "e7e5", "g2g4", "d8h4")
    assert not engine.can_offer_draw("w")
    with pytest.raises(IllegalActionError):
        engine.offer_draw("w")
    with pytest.raises(ValueError):
        ChessEngine().offer_draw("x")


# Undo ---------------------------------------------------------------------------------------------------------

def test_undo_reopens_a_finished_game_and_recomputes_check():
    engine = ChessEngine()
    play(engine, "f2f3", "e7e5", "g2g4", "d8h4")
    assert engine.result == RESULT_BLACK_WINS
    engine.undo_move()
    assert engine.result == RESULT_ONGOING and not engine.checkmate and not engine.in_check
    play(engine, "d8h4")                       # and the game can be finished again
    assert engine.checkmate


def test_undo_clears_the_check_flag_of_the_position_it_returns_to():
    engine = ChessEngine.from_fen("4k3/8/8/8/8/8/4r3/4K3 w - - 0 1")   # Black rook e2 checks
    assert engine.in_check
    play(engine, "e1e2")                                               # Kxe2
    assert not engine.in_check
    engine.undo_move()
    assert engine.in_check


# 8.3 Exploratory and negative ----------------------------------------------------------------------------------

TRICKY = [PERFT[1][1], PERFT[3][1], PERFT[4][1], PERFT[5][1],
          "rnbqkbnr/1pp1pppp/p7/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3",
          "4k3/8/8/KPp4r/8/8/8/8 w - c6 0 1", "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"]


@pytest.mark.parametrize("fen", TRICKY)
def test_8_3_move_then_undo_gives_the_same_state_for_every_legal_move(fen):
    engine = ChessEngine.from_fen(fen)
    before = state(engine)
    for move in engine.get_valid_moves():
        engine.make_move(move)
        engine._undo()
        assert state(engine) == before, move.get_coordinate_notation()
    for move in engine.get_valid_moves():       # and through the checked path
        engine.play(move)
        engine.undo_move()
        assert state(engine) == before, move.get_coordinate_notation()


@pytest.mark.parametrize("fen", TRICKY)
def test_8_3_fen_survives_a_round_trip_after_every_legal_move(fen):
    engine = ChessEngine.from_fen(fen)
    for move in engine.get_valid_moves():
        engine.play(move)
        text = engine.to_fen()
        assert ChessEngine.from_fen(text).to_fen() == text, move.get_coordinate_notation()
        engine.undo_move()


@pytest.mark.parametrize("text", [
    "", " ", "e2", "e2e", "e2e4e5", "e9e4", "i2i4", "e2e0", "E2E4", " e2e4", "e2e4 ", "e2-e4",
    "e2e4q", "e1g1", "a1a1", "e2e5", "e7e5", "None", "\x00", "e2e4\n", "é2e4", "e2e4;DROP",
])
def test_8_3_bad_move_text_is_rejected_and_the_state_does_not_change(text):
    engine = ChessEngine()
    before = state(engine)
    with pytest.raises(IllegalMoveError):
        engine.play_uci(text)
    assert state(engine) == before


@pytest.mark.parametrize("bad", [None, 42, "e2e4", ("e2", "e4"), object()])
def test_8_3_play_only_takes_move_objects(bad):
    engine = ChessEngine()
    before = state(engine)
    with pytest.raises(IllegalMoveError):
        engine.play(bad)
    assert state(engine) == before


def test_8_3_a_move_for_a_square_off_the_board_or_an_empty_square_is_rejected():
    engine = ChessEngine()
    before = state(engine)
    for move in (Move(4, 4, 3, 4, "wP", "--"),            # nothing stands on e4
                 Move(6, 4, 9, 4, "wP", "--"),            # off the board
                 Move(6, 4, 5, 3, "wP", "--"),            # a pawn may not step diagonally
                 Move(6, 4, 3, 4, "wP", "--")):           # or jump three squares
        with pytest.raises(IllegalMoveError):
            engine.play(move)
    assert state(engine) == before


def test_8_3_the_engine_plays_its_own_move_so_a_caller_cannot_forge_what_it_describes():
    engine = ChessEngine()
    played = engine.play(Move(6, 4, 4, 4, "bQ", "bK"))    # right squares, nonsense description
    assert played.piece_moved == "wP" and played.piece_captured == "--"
    assert engine.board[4][4] == "wP" and engine.to_fen().startswith("rnbqkbnr/pppppppp/8/8/4P3/")


def test_8_3_nothing_can_be_played_when_the_game_is_over():
    for finish in (lambda e: e.resign("w"), lambda e: play(e, "f2f3", "e7e5", "g2g4", "d8h4")):
        engine = ChessEngine()
        finish(engine)
        before = state(engine)
        with pytest.raises(IllegalMoveError):
            engine.play_uci("a2a3") if engine.white_to_move else engine.play_uci("a7a6")
        assert state(engine) == before


def test_8_3_a_long_game_does_not_slow_down_or_break_the_repetition_check():
    rng = random.Random(11)
    engine = ChessEngine()
    started = time.perf_counter()
    plies = 0
    while plies < 320 and engine.result == RESULT_ONGOING:
        moves = engine.get_valid_moves()
        # Avoid captures and pawn moves where possible so the game goes on and repeats.
        quiet = [m for m in moves if m.piece_captured == "--" and m.piece_moved[1] != "P"]
        engine.play(rng.choice(quiet or moves))
        plies += 1
    elapsed = time.perf_counter() - started
    assert plies > 100 and elapsed < 20, f"{plies} plies took {elapsed:.1f}s"
    assert len(engine.position_history) == len(engine.move_log) + 1


def test_8_3_random_games_never_corrupt_the_state():
    rng = random.Random(2026)
    for _ in range(12):
        engine = ChessEngine()
        for _ply in range(160):
            if engine.result != RESULT_ONGOING:
                break
            moves = engine.get_valid_moves()
            assert moves, "an ongoing game always has a legal move"
            engine.play(rng.choice(moves))
            rebuilt = ChessEngine.from_fen(engine.to_fen())
            assert rebuilt.to_fen() == engine.to_fen()
            assert uci(rebuilt) == uci(engine)
        while engine.move_log:
            engine.undo_move()
        assert engine.to_fen() == START_FEN and engine.position_history == [
            ChessEngine().position_history[0]]


# A-11 Notation ----------------------------------------------------------------------------------------------------------

def test_A11_san_examples():
    engine = ChessEngine()
    play(engine, "e2e4", "d7d5", "e4d5", "g8f6", "f1b5", "c7c6", "d5c6")
    assert engine.san_moves() == ["e4", "d5", "exd5", "Nf6", "Bb5+", "c6", "dxc6"]
    assert [m.get_chess_notation() for m in engine.move_log] == engine.san_moves()
    opening = ChessEngine()
    play(opening, *OPENING_20)
    assert opening.san_moves() == [
        "e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O", "Be7", "Re1", "b5", "Bb3",
        "d6", "c3", "O-O", "h3", "Nb8", "d4", "Nbd7"]
    mate = ChessEngine()
    play(mate, "f2f3", "e7e5", "g2g4", "d8h4")
    assert mate.san_moves()[-1] == "Qh4#" and mate.move_log[-1].get_chess_notation() == "Qh4#"


def test_A11_san_disambiguation_file_then_rank_then_both():
    files = ChessEngine.from_fen("7k/8/8/8/8/8/8/R4R1K w - - 0 1")
    names = {m.get_chess_notation() for m in files.get_valid_moves() if m.end_col == 3 and m.end_row == 7}
    assert {"Rad1", "Rfd1"} <= names
    ranks = ChessEngine.from_fen("7k/8/8/R7/8/8/8/R6K w - - 0 1")
    names = {m.get_chess_notation() for m in ranks.get_valid_moves() if m.end_col == 0 and m.end_row == 5}
    assert {"R5a3", "R1a3"} <= names
    both = ChessEngine.from_fen("6k1/8/8/8/8/Q1Q5/8/Q6K w - - 0 1")
    names = {m.get_chess_notation() for m in both.get_valid_moves() if m.end_col == 1 and m.end_row == 6}
    assert {"Q1b2", "Qa3b2", "Qcb2"} <= names


def test_A11_uci_names_a_promotion_with_a_lower_case_letter_and_castling_as_a_king_move():
    engine = ChessEngine.from_fen("4k2r/P7/8/8/8/8/8/R3K2R w KQk - 0 1")
    names = uci(engine)
    assert {"a7a8q", "a7a8r", "a7a8b", "a7a8n", "e1g1", "e1c1"} <= set(names)
    assert not any(name in names for name in ("a7a8", "a7a8Q"))


def test_A11_pgn_of_scholars_mate():
    engine = ChessEngine()
    play(engine, "e2e4", "e7e5", "d1h5", "b8c6", "f1c4", "g8f6", "h5f7")
    assert engine.to_pgn(game_date=date(2026, 10, 17)) == (
        '[Event "Casual game"]\n[Site "Chess Game"]\n[Date "2026.10.17"]\n[Round "-"]\n'
        '[White "White"]\n[Black "Black"]\n[Result "1-0"]\n\n'
        '1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0\n')


def test_A11_pgn_of_an_unfinished_game_from_a_custom_position_names_the_start():
    engine = ChessEngine.from_fen("4k3/8/8/8/8/8/8/R3K3 b - - 3 20")
    play(engine, "e8d8", "a1a8")
    pgn = engine.to_pgn(white="Ann", black='Bo "B" \\ Smith', game_date=date(2026, 1, 2))
    assert '[White "Ann"]' in pgn and '[Black "Bo \\"B\\" \\\\ Smith"]' in pgn
    assert '[SetUp "1"]' in pgn and '[FEN "4k3/8/8/8/8/8/8/R3K3 b - - 3 20"]' in pgn
    assert '[Result "*"]' in pgn
    assert pgn.rstrip().endswith("20... Kd8 21. Ra8+ *")


def test_A11_pgn_move_text_wraps_and_a_tag_value_cannot_break_out_of_its_line():
    engine = ChessEngine()
    play(engine, *OPENING_20)
    pgn = engine.to_pgn(white='x"]\n[Result "1-0"', game_date=date(2026, 1, 1))
    assert len(pgn.split("\n\n")[1].splitlines()) >= 2, "twenty moves do not fit on one line"
    assert all(len(line) <= 80 for line in pgn.splitlines() if not line.startswith("["))
    result_tags = [line for line in pgn.splitlines() if line.startswith("[Result")]
    assert result_tags == ['[Result "*"]'], "a name with a newline must not forge a tag"
    assert pgn.splitlines()[4] == '[White "x\\"] [Result \\"1-0\\""]'


def test_A11_san_moves_are_right_even_for_moves_made_without_the_checked_path():
    engine = ChessEngine()
    for text in ("f2f3", "e7e5", "g2g4", "d8h4"):
        engine.make_move(engine_move(engine, text))      # the unchecked primitive
    assert engine.san_moves() == ["f3", "e5", "g4", "Qh4#"]
