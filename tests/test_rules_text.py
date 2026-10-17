"""The Rules screen's text: it must agree with the engine and with chess-rules.md."""

import re
from pathlib import Path

import pytest

import chess_engine
from rules_text import RULES_PAGES

ROOT = Path(__file__).resolve().parent.parent
ALL_TEXT = "\n".join(paragraph for _title, paragraphs in RULES_PAGES for paragraph in paragraphs)


def page_text(index):
    return "\n".join(RULES_PAGES[index][1])


def test_there_are_five_titled_pages_with_something_on_each():
    assert [title for title, _ in RULES_PAGES] == [
        "The board and the pieces", "Check, checkmate and stalemate", "Special moves",
        "Draws and how a game ends", "Playing here"]
    for _title, paragraphs in RULES_PAGES:
        assert paragraphs and all(p.strip() for p in paragraphs)


def test_the_text_is_plain_ascii_so_any_font_can_draw_it():
    for _title, paragraphs in RULES_PAGES:
        for paragraph in paragraphs:
            assert paragraph.isascii() and "\n" not in paragraph, paragraph
    assert all(title.isascii() for title, _ in RULES_PAGES)


def test_every_piece_and_every_special_move_is_explained():
    pieces = page_text(0).lower()
    for word in ("king", "queen", "rook", "bishop", "knight", "pawn", "capture"):
        assert word in pieces, word
    special = page_text(2).lower()
    for word in ("castling", "en passant", "promotion", "under-promotion"):
        assert word in special, word
    ending = page_text(1).lower() + page_text(3).lower()
    for word in ("check", "checkmate", "stalemate", "pinned", "double check", "resign",
                 "insufficient material"):
        assert word in ending, word


def test_the_draw_numbers_come_from_the_engine_and_say_claim_or_automatic_correctly():
    draws = page_text(3)
    assert f"occurs {chess_engine.REPETITION_CLAIM} times" in draws
    assert f"After {chess_engine.REPETITION_AUTOMATIC} times the game is drawn automatically" in draws
    assert f"{chess_engine.FIFTY_MOVE_CLAIM // 2} moves by each side" in draws
    assert f"After {chess_engine.SEVENTY_FIVE_MOVE_AUTOMATIC // 2} moves" in draws
    assert draws.count("CLAIM") == 2, "threefold repetition and the 50-move rule are claimed"
    assert f"{chess_engine.DRAW_OFFER_INTERVAL} more moves" in page_text(4)


def test_the_numbers_on_the_screen_match_the_rules_file():
    """chess-rules.md is the source of truth: its thresholds must be the ones shown."""
    rules = (ROOT / "chess-rules.md").read_text(encoding="utf-8")
    assert "A-03 Threefold repetition (claim)" in rules and "A-04 Fivefold repetition (automatic)" in rules
    assert "(100 half-moves)" in rules and "(150 half-moves)" in rules
    assert chess_engine.FIFTY_MOVE_CLAIM == 100 and chess_engine.SEVENTY_FIVE_MOVE_AUTOMATIC == 150
    assert chess_engine.REPETITION_CLAIM == 3 and chess_engine.REPETITION_AUTOMATIC == 5
    assert "10 more moves" in rules, "section 10 records the draw-offer wait shown on the screen"


@pytest.mark.parametrize("key,words", [
    ("D", "Offer draw"), ("C", "Claim draw"), ("X", "Resign"),
    ("Z", "takes back"), ("R", "new game"), ("V", "2D and 3D"), ("F", "flips"),
    ("M", "mutes"), ("P", "PGN"), ("H", "this page"), ("Esc", "menu"),
])
def test_the_keys_named_on_the_last_page_are_the_ones_the_game_uses(key, words):
    assert re.search(rf"\b{key}\b", page_text(4)) and words in page_text(4), (key, words)


def test_the_rules_levels_are_not_confused_with_the_computer_levels():
    assert "not rule levels" in page_text(4) and "Junior to Senior" in page_text(4)
