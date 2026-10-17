"""
The rules of chess as the game's Rules screen shows them (Menu > Rules, or the H key).

Plain text only, no pygame, so tests can check it. It is a player-friendly summary of
chess-rules.md, which stays the source of truth. The numbers (how many repetitions, how many
moves) are taken from chess_engine, so this screen cannot say something the engine does not do.

A paragraph that starts with "- " is a bullet point; the Rules screen draws it with a bullet and
a hanging indent. Keep to ASCII: the screen's font is a plain text font.
"""

from typing import Tuple

from chess_engine import (DRAW_OFFER_INTERVAL, FIFTY_MOVE_CLAIM, REPETITION_AUTOMATIC,
                          REPETITION_CLAIM, SEVENTY_FIVE_MOVE_AUTOMATIC)

Page = Tuple[str, Tuple[str, ...]]

RULES_PAGES: Tuple[Page, ...] = (
    ("The board and the pieces", (
        "The game is played on 8 by 8 squares. White moves first, then the players take turns. "
        "Passing is not allowed.",
        "Each side starts with a king, a queen, two rooks, two bishops, two knights and eight pawns.",
        "- King: one square in any direction.",
        "- Rook: any number of empty squares along a row or a column.",
        "- Bishop: any number of empty squares along a diagonal. It always stays on the colour "
        "of square it started on.",
        "- Queen: moves like a rook or a bishop.",
        "- Knight: two squares one way and one square sideways, an L shape. It is the only piece "
        "that can jump over others.",
        "- Pawn: one square straight forward (two squares from its starting square), but it "
        "captures one square diagonally forward. It never moves backward.",
        "Rooks, bishops and queens cannot jump over pieces. A piece captures by moving onto an "
        "opponent's piece, and can never move onto a square holding a piece of its own colour. "
        "Capturing is never forced.",
    )),
    ("Check, checkmate and stalemate", (
        "A king is in check when an opponent's piece attacks its square. You may never make a "
        "move that leaves your own king in check.",
        "If you are in check you must get out of it in one of three ways:",
        "- move the king to a square that is not attacked;",
        "- capture the piece that gives check;",
        "- block the line between that piece and your king (only possible against a rook, "
        "bishop or queen).",
        "A piece standing between its own king and an attacker is pinned: it may only move along "
        "that line. Against a double check only the king can move. The two kings can never "
        "stand next to each other.",
        "Checkmate: you are in check and have no legal move. You lose and the game is over.",
        "Stalemate: you are not in check but have no legal move. The game is a draw.",
    )),
    ("Special moves", (
        "Castling. In one move the king moves two squares towards a rook and that rook jumps "
        "over to the square the king crossed. It is allowed only if:",
        "- neither the king nor that rook has ever moved (a rook that goes out and comes back "
        "does not count), and the rook has not been captured;",
        "- all the squares between them are empty;",
        "- the king is not in check, does not pass over an attacked square, and does not land on "
        "an attacked square.",
        "En passant. If an opponent's pawn moves two squares and lands beside your pawn, you may "
        "capture it as if it had moved only one square. You must do it on your very next move, "
        "or the right is gone.",
        "Promotion. A pawn that reaches the far row must become a queen, rook, bishop or knight "
        "of its colour at once. You choose, and the game asks. Taking a rook, bishop or knight "
        "is called under-promotion and is sometimes the best move, for example to avoid "
        "stalemate.",
    )),
    ("Draws and how a game ends", (
        "A game ends by checkmate, by resignation (a player may resign at any time and the "
        "opponent wins), or as a draw. A draw happens when:",
        "- stalemate arises;",
        "- neither side can possibly give checkmate (insufficient material): only the two kings; "
        "a king and one bishop or one knight against a king; or kings with bishops that all "
        "stand on the same colour of square. The game ends at once;",
        f"- the same position occurs {REPETITION_CLAIM} times (same player to move, same "
        f"castling and en passant rights): the player to move can CLAIM a draw. After "
        f"{REPETITION_AUTOMATIC} times the game is drawn automatically;",
        f"- {FIFTY_MOVE_CLAIM // 2} moves by each side pass with no pawn move and no capture: "
        f"the player to move can CLAIM a draw. After {SEVENTY_FIVE_MOVE_AUTOMATIC // 2} moves "
        f"the game is drawn automatically, unless the last move was checkmate;",
        "- both players agree to a draw.",
    )),
    ("Playing here", (
        "Click a piece, then a highlighted square (in the 2D view you can also drag the piece). "
        "When a pawn reaches the far row you pick the new piece.",
        "Offer draw (D): the computer accepts only when it is clearly worse, and never claims a "
        "draw itself. With two players the other player is asked. After an offer, the same "
        f"player can offer again only after {DRAW_OFFER_INTERVAL} more moves.",
        "Claim draw (C): lights up when a repetition or the 50-move rule allows it. "
        "Resign (X) asks you to confirm.",
        "Other keys: Z takes back a move, R starts a new game, V switches 2D and 3D, F flips "
        "the board, M mutes the sound, P copies the game as PGN, H shows this page, Esc opens "
        "the menu.",
        "The five computer levels, Junior to Senior, are opponent strengths. They are not rule "
        "levels: every game uses all of the rules in these pages.",
        "The full rules, and the choices made where they leave one open, are in chess-rules.md.",
    )),
)
