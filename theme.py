"""
Design tokens for the chess UI.

Two layers, each referencing only the one below:

1. **Primitives** - raw colours, named by hue and step, with no meaning attached.
2. **Semantic tokens** - what a colour is *for* (``PANEL_TEXT``, ``CARD_BG``...). The UI code
   uses these; swapping a theme means remapping this layer only.

Spacing and type use fixed scales so layout code never invents one-off numbers.

``CONTRAST_PAIRS`` lists every foreground/background pairing the UI draws as text or as a
meaningful control, each with the WCAG 2.x minimum it has to meet (4.5:1 for normal text,
3:1 for large text and UI components). ``tests/test_theme.py`` computes every ratio, so a
colour tweak that breaks legibility fails the build instead of shipping. Colours here are the
design values; the pairs use the lightest point of each gradient the UI draws behind text,
which is the worst case for light-on-dark text.
"""

from __future__ import annotations

from typing import List, Tuple

Color = Tuple[int, int, int]

# --- 1. Primitives ---------------------------------------------------------------------------

WOOD_950: Color = (25, 15, 8)
WOOD_900: Color = (42, 25, 14)
WOOD_700: Color = (101, 67, 40)
WOOD_500: Color = (173, 132, 84)
WOOD_300: Color = (224, 198, 145)
SAND_200: Color = (240, 217, 181)
SAND_500: Color = (181, 136, 99)

GREY_050: Color = (255, 255, 255)
GREY_150: Color = (220, 220, 220)
GREY_250: Color = (200, 200, 200)
GREY_300: Color = (170, 170, 170)
GREY_400: Color = (150, 150, 150)
GREY_500: Color = (140, 140, 140)
GREY_700: Color = (90, 88, 84)
GREY_750: Color = (70, 68, 65)
GREY_800: Color = (62, 60, 56)
GREY_850: Color = (50, 48, 45)
GREY_900: Color = (38, 36, 33)
GREY_950: Color = (30, 30, 30)

BLUE_900: Color = (20, 28, 42)
BLUE_600: Color = (40, 95, 145)
BLUE_500: Color = (50, 108, 160)
BLUE_100: Color = (200, 220, 255)

GREEN_500: Color = (120, 170, 80)
GREEN_400: Color = (124, 252, 0)
OLIVE_300: Color = (205, 210, 106)
OLIVE_500: Color = (168, 190, 72)

RED_500: Color = (235, 67, 52)
CRIMSON_900: Color = (120, 10, 10)

YELLOW_300: Color = (247, 247, 105)
GOLD_300: Color = (255, 215, 90)
CREAM_100: Color = (255, 255, 200)

# --- 2. Semantic tokens ----------------------------------------------------------------------

# Board
BOARD_LIGHT = SAND_200
BOARD_DARK = SAND_500
BOARD_HIGHLIGHT = YELLOW_300
BOARD_SELECTED = GREEN_400
BOARD_LAST_FROM = OLIVE_300
BOARD_LAST_TO = OLIVE_500
BOARD_CHECK = RED_500
BOARD_CHECK_OUTLINE = CRIMSON_900   # the glow is bright red; the outline is dark enough to read on both squares
BOARD_MOVE_DOT = GREY_950       # dark core: readable on light and dark squares
BOARD_MOVE_RING = GREY_050      # light halo keeps the dot visible on the dark squares
BOARD_PROMO_HOVER = BLUE_100

FRAME_DARK = WOOD_900
FRAME_MID = WOOD_700
FRAME_LIGHT = WOOD_500
COORD_TEXT = WOOD_300
COORD_OUTLINE = WOOD_950

# The table the 3D board stands on (top to bottom of the window)
TABLE_TOP = (30, 19, 11)
TABLE_BOTTOM = (50, 31, 18)

# Side panel
PANEL_BG = GREY_900
PANEL_TEXT = GREY_150
PANEL_DIM = GREY_400
PANEL_ACCENT = GREEN_500
PANEL_DIVIDER = GREY_750
PANEL_LATEST = CREAM_100

# Menu and controls
MENU_TEXT = GREY_050
MENU_SUBTLE = GREY_300
MENU_LABEL = GREY_250
BUTTON_BG = BLUE_600
BUTTON_BG_HOVER = BLUE_500
BUTTON_BORDER = BLUE_900
FOCUS_RING = GOLD_300
# A control that cannot be used right now: flat and grey, but still readable.
BUTTON_OFF_BG = GREY_800
BUTTON_OFF_TEXT = GREY_300
BUTTON_OFF_BORDER = GREY_700
# A short notice drawn over the board on a black scrim of this alpha (0-255).
TOAST_TEXT = GREY_050
TOAST_ALPHA = 215

# Level cards (the Junior -> Senior picker)
CARD_BG = GREY_850
CARD_BG_HOVER = GREY_800
CARD_BORDER = GREY_700
CARD_TITLE = GREY_050
CARD_TEXT = GREY_250
PIP_FILLED = GREEN_500
PIP_EMPTY = GREY_500

# Brightness multipliers at the top and bottom of the vertical gradients the UI draws.
PANEL_GRADIENT = (1.12, 0.90)
BUTTON_GRADIENT = (1.08, 0.68)
# The menu dims the board behind it with black at this alpha (0-255).
MENU_SCRIM_ALPHA = 200

# --- Spacing and type scales -----------------------------------------------------------------

SPACE_1, SPACE_2, SPACE_3, SPACE_4, SPACE_5, SPACE_6 = 4, 8, 12, 16, 24, 32

FONT_CAPTION = 13
FONT_MONO = 14
FONT_BODY = 15
FONT_LABEL = 18
FONT_TITLE = 22
FONT_HEADING = 30
FONT_DISPLAY = 48

# Minimum interactive target, in pixels (WCAG 2.2 AA asks for 24; platform guidance is higher).
MIN_TARGET = 40


# --- Contrast ----------------------------------------------------------------------------------

def shade(color: Color, factor: float) -> Color:
    """Multiply a colour's brightness, clamped to the valid range."""
    return tuple(max(0, min(255, int(c * factor))) for c in color)  # type: ignore[return-value]


def relative_luminance(color: Color) -> float:
    """WCAG 2.x relative luminance."""
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = color
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(foreground: Color, background: Color) -> float:
    """WCAG 2.x contrast ratio between two colours (1.0 - 21.0)."""
    a, b = relative_luminance(foreground), relative_luminance(background)
    lighter, darker = (a, b) if a >= b else (b, a)
    return (lighter + 0.05) / (darker + 0.05)


def scrimmed(color: Color, alpha: int = MENU_SCRIM_ALPHA) -> Color:
    """What a colour looks like under the menu's black scrim."""
    return shade(color, 1 - alpha / 255)


_PANEL_TOP = shade(PANEL_BG, PANEL_GRADIENT[0])
_BUTTON_TOP = shade(BUTTON_BG_HOVER, BUTTON_GRADIENT[0])
_MENU_BACKDROP = scrimmed(BOARD_LIGHT)  # the brightest thing the scrim ever covers

TEXT_MIN = 4.5       # WCAG 1.4.3, normal text
GRAPHIC_MIN = 3.0    # WCAG 1.4.11, UI components and meaningful graphics

# (what it is, foreground, background, minimum ratio)
CONTRAST_PAIRS: List[Tuple[str, Color, Color, float]] = [
    ("panel text on panel", PANEL_TEXT, _PANEL_TOP, TEXT_MIN),
    ("panel dim text on panel", PANEL_DIM, _PANEL_TOP, TEXT_MIN),
    ("panel accent text on panel", PANEL_ACCENT, _PANEL_TOP, TEXT_MIN),
    ("latest-move text on panel", PANEL_LATEST, _PANEL_TOP, TEXT_MIN),
    ("button label on button", MENU_TEXT, _BUTTON_TOP, TEXT_MIN),
    ("menu subtle text on scrim", MENU_SUBTLE, _MENU_BACKDROP, TEXT_MIN),
    ("menu label text on scrim", MENU_LABEL, _MENU_BACKDROP, TEXT_MIN),
    # Cards are tested on their hover colour: the lighter of the two, so the worst case.
    ("card title on hovered card", CARD_TITLE, CARD_BG_HOVER, TEXT_MIN),
    ("card summary on hovered card", CARD_TEXT, CARD_BG_HOVER, TEXT_MIN),
    ("strength pip (filled) on hovered card", PIP_FILLED, CARD_BG_HOVER, GRAPHIC_MIN),
    ("strength pip (empty) on hovered card", PIP_EMPTY, CARD_BG_HOVER, GRAPHIC_MIN),
    ("card border on scrim", CARD_BORDER, _MENU_BACKDROP, 1.5),
    ("focus ring on scrim", FOCUS_RING, _MENU_BACKDROP, GRAPHIC_MIN),
    ("focus ring on card", FOCUS_RING, CARD_BG, GRAPHIC_MIN),
    ("coordinate label on frame", COORD_TEXT, COORD_OUTLINE, TEXT_MIN),
    ("disabled button label on disabled button", BUTTON_OFF_TEXT, BUTTON_OFF_BG, TEXT_MIN),
    ("notice text over the lightest square", TOAST_TEXT, scrimmed(BOARD_LIGHT, TOAST_ALPHA), TEXT_MIN),
    ("table backdrop vs frame", FRAME_MID, TABLE_BOTTOM, 1.5),
    ("check outline on light square", BOARD_CHECK_OUTLINE, BOARD_LIGHT, GRAPHIC_MIN),
    ("check outline on dark square", BOARD_CHECK_OUTLINE, BOARD_DARK, GRAPHIC_MIN),
    ("move dot on light square", BOARD_MOVE_DOT, BOARD_LIGHT, GRAPHIC_MIN),
    ("move dot on dark square", BOARD_MOVE_DOT, BOARD_DARK, GRAPHIC_MIN),
]
