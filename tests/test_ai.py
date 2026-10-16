"""
ChessAI contract tests, laid out like an interface test plan (ID / priority / case / expected).

Priorities: H = must never break, M = important, L = nice to have.
"""

import copy
import threading
import time

import pytest

from ai.levels import DEFAULT_LEVEL_KEY, LEVELS, Level, get_level
from chess_ai import ChessAI, RandomAI
from chess_engine import ChessEngine
from tests.helpers import engine_from_fen, play

LEVEL_KEYS = [level.key for level in LEVELS]

BACK_RANK_MATE_IN_1 = "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1"        # Ra8#
LADDER_MATE_IN_2 = "7k/8/8/8/8/8/1R6/R3K3 w - - 0 1"                # Ra7 .. Kg8, Rb8#
FREE_QUEEN = "4k3/8/8/3q4/8/8/8/3RK3 w - - 0 1"                     # Rxd5 wins a queen
CHECKMATED = "R5k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1"                 # Black is mated
STALEMATED = "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"                       # Black has no move
MIDDLEGAME = ("r1bqk2r/ppp2ppp/1bnp1n2/4p3/1PB1P3/2PP1N2/P4PPP/RNBQK2R w KQkq - 1 7")


def middlegame_engine():
    return engine_from_fen(MIDDLEGAME)


def snapshot_engine(engine):
    return (copy.deepcopy(engine.board), engine.white_to_move, len(engine.move_log),
            engine.enpassant_possible, engine.halfmove_clock,
            (engine.white_castle_kingside, engine.white_castle_queenside,
             engine.black_castle_kingside, engine.black_castle_queenside))


# AI-01 (H) Valid position -> a legal move, at every level -----------------------------------
@pytest.mark.parametrize("key", LEVEL_KEYS)
@pytest.mark.parametrize("make_engine", [ChessEngine, middlegame_engine], ids=["opening", "middlegame"])
def test_every_level_returns_a_legal_move(key, make_engine):
    engine = make_engine()
    valid = engine.get_valid_moves()
    ai = ChessAI(key, seed=1)
    move = ai.choose_move(engine, valid)
    assert move in valid
    assert ai.fallback_count == 0


# AI-02 (H) No legal moves (mate or stalemate) -> None ---------------------------------------
@pytest.mark.parametrize("fen", [CHECKMATED, STALEMATED], ids=["checkmate", "stalemate"])
def test_no_legal_moves_returns_none(fen):
    engine = engine_from_fen(fen)
    assert engine.get_valid_moves() == []
    assert ChessAI("senior").choose_move(engine) is None


# AI-03 (H) A single legal move is returned without searching ---------------------------------
def test_forced_move_is_returned_immediately():
    # The rook on h2 covers a2 and b2, so Kb1 is White's only legal move.
    engine = engine_from_fen("7k/8/8/8/8/8/7r/K7 w - - 0 1")
    valid = engine.get_valid_moves()
    assert [m.get_coordinate_notation() for m in valid] == ["a1b1"]
    start = time.perf_counter()
    assert ChessAI("senior").choose_move(engine, valid) is valid[0]
    assert time.perf_counter() - start < 0.5


def test_forced_promotion_defaults_to_a_queen():
    # Every king move is covered, so a7-a8 is the only legal move.
    engine = engine_from_fen("6r1/P7/8/4k3/8/8/r7/7K w - - 0 1")
    valid = engine.get_valid_moves()
    assert [m.get_coordinate_notation() for m in valid] == ["a7a8"]
    move = ChessAI("senior").choose_move(engine, valid)
    assert move.is_pawn_promotion and move.promotion_piece == "Q"


# AI-04 (H) Mate in one is always played ------------------------------------------------------
@pytest.mark.parametrize("key", LEVEL_KEYS)
def test_mate_in_one_is_found_at_every_level(key):
    engine = engine_from_fen(BACK_RANK_MATE_IN_1)
    move = ChessAI(key, seed=3).choose_move(engine, engine.get_valid_moves())
    assert move.get_coordinate_notation() == "a1a8"


# AI-05 (H) Mate in two is found from Mid-level up ---------------------------------------------
@pytest.mark.parametrize("key", ["midlevel", "advanced", "senior"])
def test_mate_in_two_is_found_from_midlevel_up(key):
    engine = engine_from_fen(LADDER_MATE_IN_2)
    move = ChessAI(key, seed=5).choose_move(engine, engine.get_valid_moves())
    assert move.get_coordinate_notation() in {"a1a7", "b2b7"}


# AI-06 (H) A free queen is taken at every level -----------------------------------------------
@pytest.mark.parametrize("key", LEVEL_KEYS)
def test_free_queen_is_captured_at_every_level(key):
    engine = engine_from_fen(FREE_QUEEN)
    move = ChessAI(key, seed=11).choose_move(engine, engine.get_valid_moves())
    assert move.get_coordinate_notation() == "d1d5"


# AI-07 (M) The time limit is respected ----------------------------------------------------------
def test_time_limit_is_respected():
    quick = Level("quick", "Quick", "test", strength=3, max_depth=30, time_limit=0.4,
                  quiescence_plies=64, noise_cp=0, use_book=False)
    engine = middlegame_engine()
    ai = ChessAI(quick, seed=1)
    start = time.perf_counter()
    move = ai.choose_move(engine, engine.get_valid_moves())
    elapsed = time.perf_counter() - start
    assert move is not None
    assert elapsed < 0.4 + 1.0, f"search overran its 0.4s budget: {elapsed:.2f}s"


# AI-08 (M) An external stop ends the search promptly with a playable move -----------------------
def test_stop_event_ends_the_search_promptly():
    deep = Level("deep", "Deep", "test", strength=5, max_depth=40, time_limit=60,
                 quiescence_plies=64, noise_cp=0, use_book=False)
    engine = middlegame_engine()
    valid = engine.get_valid_moves()
    stop = threading.Event()
    threading.Timer(0.3, stop.set).start()
    start = time.perf_counter()
    move = ChessAI(deep, seed=1).choose_move(engine, valid, stop=stop)
    assert time.perf_counter() - start < 3.0
    assert move in valid


def test_stop_event_already_set_still_yields_a_legal_move():
    engine = middlegame_engine()
    valid = engine.get_valid_moves()
    stop = threading.Event()
    stop.set()
    assert ChessAI("senior", seed=1).choose_move(engine, valid, stop=stop) in valid


# AI-09 (H) The engine is never modified ----------------------------------------------------------
@pytest.mark.parametrize("key", ["junior", "senior"])
def test_choose_move_does_not_mutate_the_engine(key):
    engine = middlegame_engine()
    before = snapshot_engine(engine)
    ChessAI(key, seed=1).choose_move(engine, engine.get_valid_moves())
    assert snapshot_engine(engine) == before


# AI-10 (M) Unknown level -> clear error ------------------------------------------------------------
def test_unknown_level_is_rejected():
    with pytest.raises(ValueError, match="unknown level"):
        ChessAI("grandmaster")
    ai = ChessAI()
    with pytest.raises(ValueError, match="unknown level"):
        ai.set_level("grandmaster")
    with pytest.raises(ValueError):
        get_level(None)
    assert ai.level.key == DEFAULT_LEVEL_KEY  # a failed change leaves the level untouched


# AI-11 (M) Promotion piece is set on the returned move ----------------------------------------------
def test_promotion_move_carries_a_promotion_piece():
    engine = engine_from_fen("8/P6k/8/8/8/8/8/K7 w - - 0 1")
    move = ChessAI("senior", seed=1).choose_move(engine, engine.get_valid_moves())
    assert move.is_pawn_promotion and move.get_coordinate_notation() == "a7a8"
    assert move.promotion_piece == "Q"


# AI-12 (M) Same seed -> same decision ------------------------------------------------------------------
def test_same_seed_gives_the_same_choice_for_an_imperfect_level():
    engine = middlegame_engine()
    valid = engine.get_valid_moves()
    first = ChessAI("junior", seed=99).choose_move(engine, valid)
    second = ChessAI("junior", seed=99).choose_move(engine, valid)
    assert first.get_coordinate_notation() == second.get_coordinate_notation()


# AI-13 (H) Book moves are legal and only used where enabled -----------------------------------------------
def test_opening_move_comes_from_the_book_for_booked_levels():
    for seed in range(5):
        engine = ChessEngine()
        move = ChessAI("senior", seed=seed).choose_move(engine, engine.get_valid_moves())
        assert move.get_coordinate_notation() in {"e2e4", "d2d4", "c2c4", "g1f3"}
    assert not get_level("junior").use_book


# AI-14 (M) Cancel-and-restart does not corrupt anything -----------------------------------------------------
def test_cancelling_one_search_and_starting_another_is_safe():
    ai = ChessAI("advanced", seed=2)
    engine = middlegame_engine()
    valid = engine.get_valid_moves()
    results = []

    def worker(stop):
        results.append(ai.choose_move(engine, list(valid), stop=stop))

    stop_first = threading.Event()
    first = threading.Thread(target=worker, args=(stop_first,))
    first.start()
    time.sleep(0.05)
    stop_first.set()
    second = threading.Thread(target=worker, args=(threading.Event(),))
    second.start()
    first.join(10)
    second.join(10)
    assert len(results) == 2 and all(m is not None for m in results)
    assert ai.fallback_count == 0


# AI-15 (M) The ladder is well formed --------------------------------------------------------------------------
def test_ladder_is_ordered_from_junior_to_senior():
    assert LEVELS[0].name == "Junior" and LEVELS[-1].name == "Senior"
    assert [level.strength for level in LEVELS] == [1, 2, 3, 4, 5]
    assert len({level.key for level in LEVELS}) == len(LEVELS)
    depths = [level.max_depth for level in LEVELS]
    noise = [level.noise_cp for level in LEVELS]
    assert depths == sorted(depths) and len(set(depths)) == len(depths)
    assert noise == sorted(noise, reverse=True)
    assert all(level.time_limit > 0 and level.summary for level in LEVELS)
    assert DEFAULT_LEVEL_KEY in LEVEL_KEYS


# AI-16 (M) Misuse of the snapshot API fails loudly ------------------------------------------------------------------
def test_snapshot_requires_the_legal_move_list():
    engine = ChessEngine()
    with pytest.raises(ValueError, match="valid_moves"):
        ChessAI("junior").choose_move(ChessAI.snapshot(engine))


def test_snapshot_path_matches_the_direct_path():
    engine = middlegame_engine()
    valid = engine.get_valid_moves()
    direct = ChessAI("midlevel", seed=4).choose_move(engine, valid)
    via_snapshot = ChessAI("midlevel", seed=4).choose_move(ChessAI.snapshot(engine), valid)
    assert direct.get_coordinate_notation() == via_snapshot.get_coordinate_notation()


# AI-17 (H) Draw rules are respected inside the search ------------------------------------------------------------------
def test_search_prefers_a_win_to_a_repetition_draw():
    """Up a queen, Senior must not shuffle: it should make progress, not repeat."""
    engine = engine_from_fen("4k3/8/8/8/8/8/8/Q3K3 w - - 0 1")
    play(engine, "a1a4", "e8d8", "a4a1", "d8e8")  # a repeated position on the board
    move = ChessAI("senior", seed=1).choose_move(engine, engine.get_valid_moves())
    assert move.get_coordinate_notation() != "a1a4"


# AI-18 (M) The random baseline plays legally ------------------------------------------------------------------------------
def test_random_baseline_is_legal():
    engine = ChessEngine()
    valid = engine.get_valid_moves()
    assert RandomAI(1).choose_move(engine, valid) in valid
    assert RandomAI(1).choose_move(engine_from_fen(CHECKMATED)) is None


# AI-19 (L, slow) Endgame technique: the top level converts a queen up ------------------------------------------------------
@pytest.mark.slow
def test_senior_mates_with_king_and_queen_against_king():
    engine = engine_from_fen("8/8/8/4k3/8/8/8/KQ6 w - - 0 1")
    senior, defender = ChessAI("senior", seed=1), RandomAI(1)
    for _ply in range(100):
        valid = engine.get_valid_moves()
        if not valid:
            break
        ai = senior if engine.white_to_move else defender
        engine.make_move(ai.choose_move(engine, valid))
        assert not engine.is_draw(), "the queen ending was drawn"
    assert not engine.get_valid_moves() and engine._is_in_check(), "no checkmate within 50 moves"
