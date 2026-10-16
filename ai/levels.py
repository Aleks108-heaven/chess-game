"""
The Junior -> Senior difficulty ladder.

A level is defined by what the engine is *allowed* to do, not by a rating claim:

* ``max_depth``    how many plies ahead it may search (the main strength knob);
* ``time_limit``   a hard wall-clock cap per move, so a slow machine never stalls the game;
* ``quiescence_plies``  how far it follows capture sequences before judging a position
                   (0 = not at all, so it "hangs" pieces it cannot see are defended);
* ``noise_cp``     standard deviation, in centipawns, of a random error added to every
                   candidate move's score, so weaker levels make human-style slips;
* ``use_book``     whether it plays known opening moves.

Depth is deliberately the binding limit on typical hardware and time the safety net, which
keeps the levels distinct from one another on fast and slow machines alike.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class Level:
    key: str
    name: str
    summary: str          # one line for the level card
    strength: int         # 1..5, drawn as pips in the UI
    max_depth: int
    time_limit: float     # seconds
    quiescence_plies: int
    noise_cp: float
    use_book: bool

    @property
    def is_imperfect(self) -> bool:
        """True if this level deliberately plays below its search's best move."""
        return self.noise_cp > 0


LEVELS: Tuple[Level, ...] = (
    Level("junior", "Junior", "Learning the ropes. Often misses what is attacked.",
          strength=1, max_depth=1, time_limit=1.0, quiescence_plies=0, noise_cp=160,
          use_book=False),
    Level("associate", "Associate", "Knows the basics. Slips on two-move tactics.",
          strength=2, max_depth=2, time_limit=1.5, quiescence_plies=2, noise_cp=75,
          use_book=True),
    Level("midlevel", "Mid-level", "Solid and tactical. Rarely gives away material.",
          strength=3, max_depth=3, time_limit=2.0, quiescence_plies=6, noise_cp=30,
          use_book=True),
    # From Advanced up there is no fuzz: noise forces a full-window search of every root move,
    # which costs several plies of depth, and these levels are meant to play their best find.
    Level("advanced", "Advanced", "Plans several moves ahead and punishes mistakes.",
          strength=4, max_depth=5, time_limit=3.0, quiescence_plies=64, noise_cp=0,
          use_book=True),
    Level("senior", "Senior", "Deep search, no free gifts. Plays to win.",
          strength=5, max_depth=8, time_limit=5.0, quiescence_plies=64, noise_cp=0,
          use_book=True),
)

DEFAULT_LEVEL_KEY = "midlevel"

_BY_KEY = {level.key: level for level in LEVELS}


def get_level(key: str) -> Level:
    """Look a level up by key. Raises ValueError for an unknown key."""
    try:
        return _BY_KEY[key]
    except (KeyError, TypeError):
        raise ValueError(f"unknown level {key!r}; choose one of {', '.join(_BY_KEY)}") from None
