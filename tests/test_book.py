"""Opening book: every line must be playable, and positions must match across move orders."""

import random

from ai.board import SearchBoard
from ai.book import BOOK_LINES, OpeningBook


def test_every_book_line_replays_and_every_reply_is_legal():
    book = OpeningBook()
    assert book.choose(SearchBoard.start(), random.Random(0)) is not None  # forces the build
    assert book.skipped == [], f"unplayable book sequences: {book.skipped}"

    problems = []
    for sequence, replies in BOOK_LINES.items():
        board = SearchBoard.start()
        for text in sequence.split():
            board.make(board.move_from_uci(text))
        legal = {board.move_to_uci(m) for m in board.legal_moves()}
        problems += [(sequence, r) for r in replies if r not in legal]
    assert problems == []


def test_book_finds_replies_after_a_transposition():
    book = OpeningBook({"g1f3 g8f6 g2g3": ["g7g6"]})
    board = SearchBoard.start()
    for text in ("g2g3", "g8f6", "g1f3"):  # same position, different move order
        board.make(board.move_from_uci(text))
    move = book.choose(board, random.Random(0))
    assert move is not None and board.move_to_uci(move) == "g7g6"


def test_book_is_silent_out_of_book():
    board = SearchBoard.start()
    for text in ("a2a3", "h7h6", "b1c3"):
        board.make(board.move_from_uci(text))
    assert OpeningBook().choose(board, random.Random(0)) is None


def test_book_ignores_an_illegal_reply_instead_of_playing_it():
    book = OpeningBook({"": ["e2e5", "e2e4"]})  # e2e5 is not a legal move
    for seed in range(10):
        move = book.choose(SearchBoard.start(), random.Random(seed))
        assert SearchBoard.move_to_uci(move) == "e2e4"
    assert OpeningBook({"": ["e2e5"]}).choose(SearchBoard.start(), random.Random(0)) is None
