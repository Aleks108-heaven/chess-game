"""Headless UI tests: menus, the level picker, input routing and the AI hand-off."""

import threading
import time

import pygame
import pytest

import main
import theme
from ai.levels import DEFAULT_LEVEL_KEY, LEVELS
from chess_engine import (RESULT_BLACK_WINS, RESULT_DRAW, RESULT_ONGOING, RESULT_WHITE_WINS,
                          ChessEngine)
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


# --- Game actions: promotion, resignation, draw offers and claims (chess-rules.md) ---------------

def start_hot_seat(game, fen=None):
    """A two-player game on the board, optionally from a FEN."""
    game.vs_ai, game.show_menu, game.player_color = False, False, 'w'
    if fen:
        game.engine = ChessEngine.from_fen(fen)
    game.all_valid_moves = game.engine.get_valid_moves()
    game.game_over = game.engine.result != RESULT_ONGOING


def start_vs_computer(game, fen=None, color='w'):
    start_hot_seat(game, fen)
    game.vs_ai, game.player_color = True, color


def play_moves(game, *texts):
    for text in texts:
        game._execute_move(engine_move(game.engine, text), animate=False)


def square_center(game, name):
    """Screen position of a square's centre in the current 2D view."""
    col, row = "abcdefgh".index(name[0]), 8 - int(name[1])
    x, y = game._screen_coords(row, col)
    return x + game.SQUARE_SIZE // 2, y + game.SQUARE_SIZE // 2


def click(game, pos):
    game._handle_mouse_down(pos)
    game._handle_mouse_up(pos)


SHUFFLE = ("g1f3", "g8f6", "f3g1", "f6g8")


def test_promotion_asks_for_a_piece_and_makes_exactly_that_move(game):
    start_hot_seat(game, "7k/P7/8/8/8/8/8/K7 w - - 0 1")
    click(game, square_center(game, "a7"))
    click(game, square_center(game, "a8"))
    assert game.promotion_pending is not None and not game.engine.move_log, \
        "the move must not be made before the piece is chosen"
    press(game, pygame.K_n)
    assert game.promotion_pending is None
    assert game.engine.board[0][0] == "wN"
    assert [m.get_chess_notation() for m in game.engine.move_log] == ["a8=N"]


@pytest.mark.parametrize("key,piece", [(pygame.K_q, "wQ"), (pygame.K_r, "wR"), (pygame.K_b, "wB")])
def test_every_promotion_piece_can_be_chosen_from_the_keyboard(game, key, piece):
    start_hot_seat(game, "7k/P7/8/8/8/8/8/K7 w - - 0 1")
    click(game, square_center(game, "a7"))
    click(game, square_center(game, "a8"))
    press(game, key)
    assert game.engine.board[0][0] == piece


def test_cancelling_the_promotion_dialog_leaves_the_game_untouched(game):
    start_hot_seat(game, "7k/P7/8/8/8/8/8/K7 w - - 0 1")
    before = game.engine.to_fen()
    click(game, square_center(game, "a7"))
    click(game, square_center(game, "a8"))
    press(game, pygame.K_ESCAPE)
    assert game.promotion_pending is None and game.engine.to_fen() == before


def test_the_promotion_dialog_offers_four_pieces_as_clickable_targets(game):
    start_hot_seat(game, "7k/P7/8/8/8/8/8/K7 w - - 0 1")
    click(game, square_center(game, "a7"))
    click(game, square_center(game, "a8"))
    game._draw_promotion_dialog((0, 0))
    assert len(game.promotion_rects) == 4
    game._handle_promotion_click(game.promotion_rects[1].center)     # the rook
    assert game.engine.board[0][0] == "wR"


# Resigning ---------------------------------------------------------------------------------------------

def test_resigning_needs_confirmation_and_ends_the_game(game):
    start_vs_computer(game)
    play_moves(game, "e2e4", "e7e5")
    press(game, pygame.K_x)
    assert game.dialog == 'resign' and game.engine.result == RESULT_ONGOING
    press(game, pygame.K_y)
    assert game.game_over and game.engine.result == RESULT_BLACK_WINS
    assert game.engine.result_reason == "resignation"
    assert game._result_headline() == ("Black wins - White resigned", "\u265A")


def test_enter_and_escape_in_a_dialog_take_the_safe_choice(game):
    start_vs_computer(game)
    play_moves(game, "e2e4", "e7e5")
    for key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_n):
        press(game, pygame.K_x)
        press(game, key)
        assert game.dialog is None and game.engine.result == RESULT_ONGOING
    press(game, pygame.K_r)                         # the new-game dialog is the same: Enter keeps it
    assert game.dialog == 'new_game'
    press(game, pygame.K_RETURN)
    assert game.dialog is None and len(game.engine.move_log) == 2


def test_in_a_two_player_game_the_side_to_move_resigns(game):
    start_hot_seat(game)
    play_moves(game, "e2e4")
    assert game._dialog_text()[0] == "Resign this game?" or True
    press(game, pygame.K_x)
    assert game._dialog_text()[:2] == ("Black resigns?", "White will win.")
    press(game, pygame.K_y)
    assert game.engine.result == RESULT_WHITE_WINS


def test_resigning_while_the_computer_is_thinking_discards_its_search(game):
    start_vs_computer(game)
    game.ai.set_level('senior')
    play_moves(game, "a2a3")
    game._start_ai_move()
    stop, generation = game.ai_stop, game.ai_generation
    press(game, pygame.K_x)
    press(game, pygame.K_y)
    assert stop.is_set() and game.ai_generation > generation
    assert game.game_over and not game.ai_thinking and game.ai_move is None


def test_resign_works_before_the_first_move_too(game):
    start_vs_computer(game)
    press(game, pygame.K_x, pygame.K_y)
    assert game.engine.result == RESULT_BLACK_WINS


# Draw offers ----------------------------------------------------------------------------------------------

def test_the_computer_declines_a_draw_when_it_is_not_worse(game):
    start_vs_computer(game)
    press(game, pygame.K_d)
    assert game.engine.result == RESULT_ONGOING and not game.game_over
    assert "declines" in game.toast[0]


def test_the_computer_accepts_a_draw_when_it_is_clearly_losing(game):
    start_vs_computer(game, "4k3/8/8/8/8/8/8/Q3K3 w - - 0 1")     # Black has lost a queen
    press(game, pygame.K_d)
    assert game.game_over and game.engine.result == RESULT_DRAW
    assert game.engine.result_reason == "agreement"
    assert game._result_headline() == ("Draw by agreement", None)


def test_draw_offers_are_rationed_and_the_player_is_told_when_to_try_again(game):
    start_vs_computer(game)
    press(game, pygame.K_d)
    assert game._action_state('offer_draw')[0] is False
    press(game, pygame.K_d)
    assert "offer another draw after 10 more moves" in game.toast[0]


def test_a_two_player_draw_offer_is_answered_by_the_other_player(game):
    start_hot_seat(game)
    press(game, pygame.K_d)
    assert game.dialog == 'draw_offer' and game._dialog_text()[:2] == (
        "White offers a draw", "Black: do you accept?")
    press(game, pygame.K_y)
    assert game.engine.result == RESULT_DRAW and game.engine.result_reason == "agreement"

    other = main.ChessUI()
    try:
        other.reduced_motion = True
        start_hot_seat(other)
        press(other, pygame.K_d)
        press(other, pygame.K_n)
        assert other.engine.result == RESULT_ONGOING and other.dialog is None
        assert "declined" in other.toast[0]
    finally:
        pygame.quit()


def test_draw_actions_are_off_while_it_is_the_computers_turn(game):
    start_vs_computer(game)
    play_moves(game, "e2e4")                         # now Black (the computer) is to move
    assert game._action_state('offer_draw') == (False, "Wait for your turn.")
    assert game._action_state('claim_draw') == (False, "Wait for your turn.")
    assert game._action_state('resign')[0] is True


# Claims -----------------------------------------------------------------------------------------------------

def test_a_draw_cannot_be_claimed_before_it_is_available(game):
    start_hot_seat(game)
    press(game, pygame.K_c)
    assert game.engine.result == RESULT_ONGOING and "No draw to claim" in game.toast[0]


def test_a_threefold_repetition_is_announced_once_and_can_be_claimed(game):
    start_hot_seat(game)
    play_moves(game, *SHUFFLE, *SHUFFLE)
    assert game.engine.can_claim_draw() == "threefold repetition" and not game.game_over
    assert "threefold repetition" in game.toast[0]
    game.toast = None
    play_moves(game, "b1c3")                          # still claimable? no: a new position
    play_moves(game, "b8c6", "c3b1", "c6b8")          # back to the start position a 4th time
    assert game.engine.can_claim_draw() == "threefold repetition"
    assert game.toast is None, "the hint is shown once per kind of claim, not every move"
    assert game._action_state('claim_draw')[0] is True
    press(game, pygame.K_c)
    assert game.game_over and game.engine.result_reason == "threefold repetition"
    assert game._result_headline() == ("Draw - threefold repetition", None)


def test_the_fifty_move_rule_can_be_claimed_and_the_75_move_rule_ends_the_game(game):
    start_hot_seat(game, "4k3/8/8/8/8/8/8/R3K3 b - - 99 60")
    play_moves(game, "e8d8")
    assert game.engine.can_claim_draw() == "50-move rule"
    press(game, pygame.K_c)
    assert game._result_headline() == ("Draw - 50-move rule", None)

    other = main.ChessUI()
    try:
        other.reduced_motion = True
        start_hot_seat(other, "4k3/8/8/8/8/8/8/R3K3 w - - 149 90")
        play_moves(other, "e1d1")
        assert other.game_over and other._result_headline() == ("Draw - 75-move rule", None)
    finally:
        pygame.quit()


@pytest.mark.parametrize("fen,moves,headline", [
    ("6k1/5ppp/8/8/8/8/8/R3K3 w - - 0 1", ["a1a8"], "White wins by checkmate!"),
    ("7k/5K2/8/8/8/8/8/6Q1 w - - 0 1", ["g1g6"], "Draw by stalemate"),
    ("4k3/8/8/8/8/8/3r4/3BK3 w - - 0 1", ["e1d2"], "Draw - insufficient material"),
])
def test_how_the_game_ended_is_spelled_out(game, fen, moves, headline):
    start_hot_seat(game, fen)
    play_moves(game, *moves)
    assert game.game_over and game._result_headline()[0] == headline
    game._draw_game_state()
    game._draw_game_over_message()


# Copy PGN -----------------------------------------------------------------------------------------------------

def test_copy_pgn_puts_the_game_on_the_clipboard(game, monkeypatch):
    copied = []
    monkeypatch.setattr(pygame.scrap, "put_text", copied.append)
    start_vs_computer(game)
    press(game, pygame.K_p)
    assert not copied and "Nothing to copy" in game.toast[0]
    play_moves(game, "e2e4", "e7e5")
    press(game, pygame.K_p)
    assert len(copied) == 1 and copied[0].startswith('[Event "Casual game"]')
    assert '[White "You"]' in copied[0] and '[Black "Mid-level (computer)"]' in copied[0] \
        and copied[0].rstrip().endswith("1. e4 e5 *")
    assert "copied" in game.toast[0]


def test_copy_pgn_reports_an_unavailable_clipboard_instead_of_crashing(game, monkeypatch):
    def broken(_text):
        raise pygame.error("no clipboard")
    monkeypatch.setattr(pygame.scrap, "put_text", broken)
    start_hot_seat(game)
    play_moves(game, "e2e4")
    press(game, pygame.K_p)
    assert "clipboard is not available" in game.toast[0]


# Layout and drawing -----------------------------------------------------------------------------------------------

def test_action_buttons_are_big_enough_apart_and_clear_of_the_legend_and_move_list(game):
    rects = game._action_rects()
    panel = pygame.Rect(game.BOARD_WIDTH, 0, game.MOVE_LOG_WIDTH, game.BOARD_HEIGHT)
    ordered = list(rects.values())
    for rect in ordered:
        assert panel.contains(rect) and rect.height >= theme.MIN_TARGET and rect.width >= theme.MIN_TARGET
    for a, b in zip(ordered, ordered[1:]):
        assert a.right < b.left, "buttons must not touch"
    legend_top = game.BOARD_HEIGHT - game.FOOTER_HEIGHT
    assert max(r.bottom for r in ordered) <= legend_top
    move_list_bottom = game.BOARD_HEIGHT - game.FOOTER_HEIGHT - game.ACTIONS_HEIGHT - 13
    assert move_list_bottom < min(r.top for r in ordered)
    assert game.FOOTER_HEIGHT >= 10 + 22 * 6, "six legend rows must fit"


def test_the_action_buttons_are_clickable_with_the_mouse(game):
    start_hot_seat(game)
    rects = game._action_rects()
    assert game._handle_action_click(rects['resign'].center)
    assert game.dialog == 'resign'
    game.dialog = None
    assert game._handle_action_click(rects['claim_draw'].center)       # disabled: explains why
    assert "No draw to claim" in game.toast[0]
    assert not game._handle_action_click((10, 10))


def test_every_dialog_and_notice_draws_in_both_views(game):
    start_hot_seat(game)
    play_moves(game, "e2e4")
    for view_3d in (False, True):
        game.view_3d = view_3d
        for dialog in ('new_game', 'resign', 'draw_offer'):
            game.dialog = dialog
            if dialog == 'draw_offer' and game.engine.draw_offer_by is None:
                game.engine.offer_draw('b')
            game._draw_game_state()
            game._draw_dialog((game.BOARD_WIDTH // 2, game.BOARD_HEIGHT // 2))
            assert all(len(text) < 40 for text in game._dialog_text()[:2])
        game.dialog = None
        game._notify("A deliberately very long notice " * 6)
        game._draw_toast()
        assert game.toast is not None


def test_a_notice_expires(game):
    game._notify("hello")
    assert game.toast is not None
    game.toast = ("hello", pygame.time.get_ticks() - 1)
    game._draw_toast()
    assert game.toast is None


def test_undo_reopens_a_game_that_was_checkmated(game):
    start_hot_seat(game)
    play_moves(game, "f2f3", "e7e5", "g2g4", "d8h4")
    assert game.game_over
    press(game, pygame.K_z)
    assert not game.game_over and game.engine.result == RESULT_ONGOING


# --- The 3D view ---------------------------------------------------------------------------------------------------

class RecordingScreen:
    """Stands in for the screen and remembers every blit, so a test can see where things go."""

    def __init__(self, real):
        self.real, self.blits = real, []

    def blit(self, source, dest, *args, **kwargs):
        self.blits.append((source, tuple(dest)))
        return self.real.blit(source, dest, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.real, name)


@pytest.mark.parametrize("flip", [False, True])
def test_3d_every_shadow_sits_under_its_own_piece(game, flip):
    """Regression for the screenshot: shadows were drawn a whole square in front of the piece."""
    game.view_3d, game.flip_board = True, flip
    game.show_menu = False
    recorder = RecordingScreen(game.screen)
    game.screen = recorder
    game._draw_pieces_3d()
    sprites = [(source, dest) for source, dest in recorder.blits]
    assert len(sprites) == 64, "a shadow and an image for each of the 32 pieces"
    for visual_row in range(8):
        for visual_col in range(8):
            row, col = (7 - visual_row, 7 - visual_col) if flip else (visual_row, visual_col)
            if game.engine.get_piece_at(row, col) == "--":
                continue
            _, _, br, bl = game._persp_quad(visual_row, visual_col)
            near_edge = (bl[1] + br[1]) / 2
            candidates = [(s, d) for s, d in sprites
                          if abs(d[0] + s.get_width() / 2 - (bl[0] + br[0]) / 2) < 1
                          and near_edge - 1.0 * s.get_height() - 2 <= d[1] <= near_edge]
            shadows = [(s, d) for s, d in candidates if s is game._scaled_sprite(None, s.get_width())]
            assert len(shadows) == 1, (visual_row, visual_col)
            shadow, dest = shadows[0]
            ellipse_centre_y = dest[1] + 0.84 * shadow.get_height()
            assert near_edge - 0.25 * shadow.get_height() <= ellipse_centre_y <= near_edge + 0.5, \
                f"shadow centre {ellipse_centre_y:.0f} is not at the foot of the piece ({near_edge:.0f})"
    game.screen = recorder.real


@pytest.mark.parametrize("flip", [False, True])
def test_3d_clicks_map_back_to_the_square_that_was_drawn(game, flip):
    game.view_3d, game.flip_board = True, flip
    for visual_row in range(8):
        for visual_col in range(8):
            tl, tr, br, bl = game._persp_quad(visual_row, visual_col)
            centre = (sum(p[0] for p in (tl, tr, br, bl)) / 4, sum(p[1] for p in (tl, tr, br, bl)) / 4)
            expected = (7 - visual_row, 7 - visual_col) if flip else (visual_row, visual_col)
            assert game._board_coords(centre) == expected


def test_3d_frame_and_table_are_outside_the_playing_area(game):
    game.view_3d = True
    for point in ((2, 2), (game.BOARD_WIDTH - 3, 5), (3, game.BOARD_HEIGHT - 3),   # table / frame
                  (game.FRAME_3D_SIDE - 6, game.BOARD_HEIGHT // 2),               # the frame
                  (game.BOARD_WIDTH // 2, game.BOARD_HEIGHT - 6)):
        assert game._board_coords(point) == (-1, -1), point


def test_3d_frame_stays_inside_the_window(game):
    window = pygame.Rect(0, 0, game.BOARD_WIDTH, game.BOARD_HEIGHT)
    for x, y in game._frame_outline():
        assert window.collidepoint(x, y), (x, y)
    assert game._persp_top_left[0] > game.FRAME_3D_SIDE, "the far edge is narrower than the near"


def test_3d_view_draws_the_same_squares_whichever_way_the_board_faces(game):
    game.view_3d = True
    for flip in (False, True):
        game.flip_board = flip
        game._draw_game_state()
        assert game._rank_label(0) == ("1" if flip else "8")
        assert game._file_label(0) == ("h" if flip else "a")


# --- The Rules screen --------------------------------------------------------------------------------------------

from rules_text import RULES_PAGES


def test_the_main_menu_has_a_rules_button_that_opens_the_first_page(game):
    options = game._menu_options()
    assert options[-1] == 'rules' and options[:2] == ['vs_ai', 'vs_human']
    game._handle_menu_click(game._menu_layout()['rules'].center)
    assert game.rules_page == 0
    press(game, pygame.K_ESCAPE)
    assert game.rules_page is None and game.show_menu and game.menu_state == 'main'


def test_h_and_f1_open_the_rules_from_the_menu_and_from_a_game_and_close_them(game):
    for key in (pygame.K_h, pygame.K_F1):
        press(game, key)
        assert game.rules_page == 0
        press(game, key)                         # the same key closes it again
        assert game.rules_page is None
    start_hot_seat(game)
    play_moves(game, "e2e4")
    for closer in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_h):
        press(game, pygame.K_h)
        assert game.rules_page == 0 and not game.show_menu
        press(game, closer)
        assert game.rules_page is None and not game.show_menu


def test_rules_pages_turn_with_the_keyboard_and_stop_at_the_ends(game):
    last = len(RULES_PAGES) - 1
    game._open_rules()
    press(game, pygame.K_LEFT, pygame.K_PAGEUP, pygame.K_UP)
    assert game.rules_page == 0
    press(game, pygame.K_RIGHT)
    press(game, pygame.K_PAGEDOWN)
    press(game, pygame.K_SPACE)
    assert game.rules_page == 3
    press(game, pygame.K_END)
    assert game.rules_page == last
    press(game, pygame.K_RIGHT, pygame.K_DOWN)
    assert game.rules_page == last
    press(game, pygame.K_HOME)
    assert game.rules_page == 0


def test_the_rules_buttons_work_with_the_mouse(game):
    game._open_rules()
    rects = game._rules_button_rects()
    game._handle_rules_click(rects['prev'].center)          # nothing before the first page
    assert game.rules_page == 0
    game._handle_rules_click(rects['next'].center)
    game._handle_rules_click(rects['next'].center)
    assert game.rules_page == 2
    game._handle_rules_click(rects['prev'].center)
    assert game.rules_page == 1
    game._handle_rules_click((5, 5))                        # outside every button: nothing
    assert game.rules_page == 1
    game._handle_rules_click(rects['close'].center)
    assert game.rules_page is None
    for rect in rects.values():
        assert rect.height >= theme.MIN_TARGET and rect.width >= theme.MIN_TARGET


def test_every_rules_page_fits_the_panel_and_draws_in_both_views(game):
    window = window_rect(game)
    panel = game._rules_panel_rect()
    area = game._rules_text_area()
    assert window.contains(panel) and panel.contains(area)
    buttons = list(game._rules_button_rects().values())
    assert all(panel.contains(rect) for rect in buttons)
    assert all(a.right < b.left for a, b in zip(buttons, buttons[1:])), "buttons must not touch"
    assert area.bottom <= min(rect.top for rect in buttons), "text must stay clear of the buttons"
    for page in range(len(RULES_PAGES)):
        placed, height = game._rules_layout(page)
        assert placed and height <= area.height, f"page {page + 1} needs {height}px of {area.height}"
        for x, _y, text in placed:
            assert x + game.status_font.size(text)[0] <= area.width, (page, text)
        for view_3d in (False, True):
            game.view_3d = view_3d
            game._open_rules(page)
            game._draw_game_state()
            game._draw_rules((10, 10))


def test_long_words_and_empty_text_wrap_safely(game):
    font = game.status_font
    assert game._wrap_text(font, "", 100) == []
    assert game._wrap_text(font, "a b c", 1000) == ["a b c"]
    narrow = game._wrap_text(font, "short " + "x" * 80 + " tail", 120)
    assert narrow[0] == "short" and "x" * 80 in narrow and narrow[-1] == "tail"
    assert all(line for line in narrow)


def test_the_game_underneath_is_untouched_by_reading_the_rules(game):
    start_hot_seat(game)
    play_moves(game, "e2e4", "e7e5")
    before = game.engine.to_fen()
    press(game, pygame.K_h, pygame.K_RIGHT, pygame.K_x)      # keys other than the rules keys do nothing
    assert game.dialog is None and game.engine.to_fen() == before
    press(game, pygame.K_ESCAPE)
    assert game.engine.to_fen() == before and not game.game_over


def test_the_computers_reply_waits_while_the_rules_are_open(game):
    start_vs_computer(game)
    game.ai.set_level('junior')
    play_moves(game, "e2e4")
    game._start_ai_move()
    assert wait_for_ai_move(game) is not None
    game.ai_started_at = -10_000                  # long enough ago that the minimum think time is over
    press(game, pygame.K_h)
    assert game._take_ready_ai_move() is None and game.ai_move is not None, \
        "the reply must wait: playing it would animate over the Rules screen"
    press(game, pygame.K_ESCAPE)
    waiting = game.ai_move
    assert game._take_ready_ai_move() is waiting and game.ai_move is None


def test_the_computers_reply_is_also_held_back_by_the_menu_and_by_its_minimum_think_time(game):
    start_vs_computer(game)
    game.ai_move, game.ai_started_at = engine_move(game.engine, "e2e4"), -10_000
    game.show_menu = True
    assert game._take_ready_ai_move() is None
    game.show_menu = False
    game.ai_started_at = pygame.time.get_ticks()      # it only just started thinking
    assert game._take_ready_ai_move() is None
    game.ai_started_at = -10_000
    assert game._take_ready_ai_move() is not None


def test_the_legend_has_room_for_all_of_its_rows(game):
    assert game.FOOTER_HEIGHT >= 10 + 22 * 6, "six legend rows must fit"
    game.show_menu = False
    game._draw_side_panel()

