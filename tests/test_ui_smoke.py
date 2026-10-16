"""Headless UI tests: menus, the level picker, input routing and the AI hand-off."""

import threading
import time

import pygame
import pytest

import main
import theme
from ai.levels import DEFAULT_LEVEL_KEY, LEVELS
from tests.helpers import engine_move


@pytest.fixture
def game():
    ui = main.ChessUI()
    ui.reduced_motion = True
    yield ui
    ui._cancel_ai()
    pygame.quit()


def press(game, *keys):
    for key in keys:
        game._handle_key(key)


def window_rect(game):
    return pygame.Rect(0, 0, game.BOARD_WIDTH + game.MOVE_LOG_WIDTH, game.BOARD_HEIGHT)


def test_built_in_self_test_passes():
    main.run_self_test()  # the same check the release build runs


# --- Menu flow -------------------------------------------------------------------------------

def test_keyboard_flow_starts_a_game_at_the_chosen_level(game):
    press(game, pygame.K_RETURN)                      # Play vs Computer
    assert game.menu_state == 'color_select'
    press(game, pygame.K_RETURN)                      # Play as White
    assert game.menu_state == 'difficulty'
    focused = game._menu_options()[game.menu_focus]
    assert focused == f'level_{DEFAULT_LEVEL_KEY}', "the cursor should start on the last level"
    press(game, pygame.K_DOWN, pygame.K_DOWN, pygame.K_RETURN)   # Mid-level -> Senior
    assert not game.show_menu and game.vs_ai
    assert game.level_key == 'senior' and game.ai.level.key == 'senior'
    assert game.player_color == 'w' and not game.flip_board


def test_playing_black_flips_the_board(game):
    press(game, pygame.K_RETURN, pygame.K_DOWN, pygame.K_RETURN)  # vs Computer -> Black
    assert game.player_color == 'b' and game.flip_board and game.menu_state == 'difficulty'


def test_every_level_card_can_be_chosen_with_the_mouse(game):
    for level in LEVELS:
        game.show_menu, game.menu_state = True, 'difficulty'
        card = game._menu_layout()[f'level_{level.key}']
        game._handle_menu_click(card.center)
        assert game.ai.level.key == level.key and not game.show_menu


def test_escape_walks_back_through_the_menus(game):
    press(game, pygame.K_RETURN, pygame.K_RETURN)
    assert game.menu_state == 'difficulty'
    press(game, pygame.K_ESCAPE)
    assert game.menu_state == 'color_select'
    press(game, pygame.K_ESCAPE)
    assert game.menu_state == 'main'
    press(game, pygame.K_ESCAPE)       # nothing to resume yet: stays on the menu
    assert game.show_menu


def test_resume_is_offered_only_when_a_game_is_in_progress(game):
    assert 'resume' not in game._menu_options()
    game.show_menu = False
    game.all_valid_moves = game.engine.get_valid_moves()
    game._execute_move(engine_move(game.engine, "e2e4"), animate=False)
    press(game, pygame.K_ESCAPE)       # open the menu over the game
    assert game.show_menu and game._menu_options()[0] == 'resume'
    press(game, pygame.K_RETURN)       # the first option is Resume
    assert not game.show_menu and len(game.engine.move_log) == 1


def test_two_player_mode_starts_without_an_ai(game):
    press(game, pygame.K_DOWN, pygame.K_RETURN)       # 2 Players
    assert not game.show_menu and not game.vs_ai


# --- Layout and content ------------------------------------------------------------------------

@pytest.mark.parametrize("state", ["main", "color_select", "difficulty"])
@pytest.mark.parametrize("in_progress", [False, True], ids=["fresh", "resumable"])
def test_menu_rects_fit_the_window_and_leave_room_for_focus_rings(game, state, in_progress):
    if in_progress:
        game.all_valid_moves = game.engine.get_valid_moves()
        game._execute_move(engine_move(game.engine, "e2e4"), animate=False)
    game.menu_state = state
    layout = game._menu_layout()
    assert set(layout) == set(game._menu_options())
    window = window_rect(game)
    rects = list(layout.values())
    for rect in rects:
        assert window.contains(rect), rect
        assert rect.height >= theme.MIN_TARGET, f"target too small: {rect}"
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            assert not a.inflate(8, 8).colliderect(b), "a focus ring would cover a neighbour"
    assert max(r.bottom for r in rects) < window.height - 36, "controls collide with the hint line"


def test_level_summaries_are_short_and_always_fit_their_card(game):
    card_text_width = game.CARD_WIDTH - 2 * theme.SPACE_4
    for level in LEVELS:
        assert len(level.summary) <= 60
        fitted = game._fit_text(game.status_font, level.summary, card_text_width)
        assert game.status_font.size(fitted)[0] <= card_text_width
    long_text = "A deliberately overlong summary " * 8
    fitted = game._fit_text(game.status_font, long_text, card_text_width)
    assert fitted.endswith("…") and game.status_font.size(fitted)[0] <= card_text_width


def test_every_screen_draws_in_both_views(game):
    for state in ("main", "color_select", "difficulty"):
        game.show_menu, game.menu_state = True, state
        game._draw_menu((10, 10))
    game.show_menu = False
    for view_3d in (False, True):
        game.view_3d = view_3d
        game._draw_game_state()


def test_panel_names_the_opponent_and_your_colour(game):
    game.vs_ai, game.level_key, game.player_color = True, 'junior', 'b'
    assert "Junior" in game._opponent_caption() and "Black" in game._opponent_caption()
    game.vs_ai = False
    assert game._opponent_caption() == "Two players"


# --- Preferences and keys ------------------------------------------------------------------------

def test_flip_and_mute_keys(game):
    game.show_menu = False
    press(game, pygame.K_f)
    assert game.flip_board
    press(game, pygame.K_f)
    assert not game.flip_board
    press(game, pygame.K_m)
    assert game.muted
    press(game, pygame.K_m)
    assert not game.muted


def test_reduced_motion_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("CHESS_REDUCED_MOTION", "1")
    ui = main.ChessUI()
    try:
        assert ui.reduced_motion
    finally:
        pygame.quit()
    monkeypatch.setenv("CHESS_REDUCED_MOTION", "0")
    ui = main.ChessUI()
    try:
        assert not ui.reduced_motion
    finally:
        pygame.quit()


# --- AI hand-off ------------------------------------------------------------------------------------

def wait_for_ai_move(game, seconds=20):
    deadline = time.time() + seconds
    while game.ai_move is None and time.time() < deadline:
        time.sleep(0.01)
    return game.ai_move


def test_ai_replies_with_a_legal_move_and_never_touches_the_live_engine(game):
    game.show_menu, game.vs_ai = False, True
    game.ai.set_level('associate')
    game.all_valid_moves = game.engine.get_valid_moves()
    game._execute_move(engine_move(game.engine, "e2e4"), animate=False)
    before_log = len(game.engine.move_log)
    game._start_ai_move()
    move = wait_for_ai_move(game)
    assert move is not None and move in game.all_valid_moves
    assert len(game.engine.move_log) == before_log, "the search must not move pieces on the live board"


def test_reset_cancels_a_search_in_flight_and_discards_its_result(game):
    game.show_menu, game.vs_ai = False, True
    game.ai.set_level('senior')
    game.all_valid_moves = game.engine.get_valid_moves()
    game._execute_move(engine_move(game.engine, "a2a3"), animate=False)  # out of book: a real search
    game._start_ai_move()
    stop = game.ai_stop
    game._reset_game()
    assert stop.is_set(), "the old search should have been told to stop"
    time.sleep(0.5)
    assert game.ai_move is None, "a result from before the reset must not leak into the new game"
    assert not game.ai_thinking


def test_ui_stays_responsive_while_the_senior_search_runs(game):
    """Drawing must keep up (well above a slideshow) while a deep search holds the CPU."""
    game.show_menu, game.vs_ai = False, True
    game.ai.set_level('senior')
    game.all_valid_moves = game.engine.get_valid_moves()
    game._execute_move(engine_move(game.engine, "a2a3"), animate=False)
    game._start_ai_move()
    time.sleep(0.2)
    frames = []
    started = time.perf_counter()
    while time.perf_counter() - started < 1.5:
        t = time.perf_counter()
        game._draw_game_state()
        game._draw_thinking_indicator()
        pygame.display.flip()
        game.clock.tick(60)
        frames.append(time.perf_counter() - t)
    game._cancel_ai()
    frames.sort()
    p95 = frames[int(len(frames) * 0.95) - 1]
    assert len(frames) >= 20, f"only {len(frames)} frames in 1.5s while the AI searched"
    assert p95 < 0.15, f"95th percentile frame time {p95 * 1000:.0f} ms"
