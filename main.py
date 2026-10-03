"""
Chess Game Interface
Handles all graphics and user input using Pygame.
Features: sound effects, drag-and-drop, pawn promotion choice,
captured pieces display, board flip, and AI opponent integration.
"""

import pygame
import sys
import math
import array
import copy
import random
import threading
from functools import lru_cache
from chess_engine import ChessEngine, Move
from chess_ai import ChessAI

# Fonts known to ship the chess glyphs (U+2654..U+265F), tried in order. SDL_ttf does not
# fall back per-glyph, so the whole symbol font has to contain them.
_SYMBOL_FONT_CANDIDATES = (
    "segoeuisymbol", "applesymbols", "dejavusans", "notosanssymbols2",
    "notosanssymbols", "freeserif", "arialunicodems", "symbola",
)


@lru_cache(maxsize=None)
def _symbol_font_path():
    for name in _SYMBOL_FONT_CANDIDATES:
        path = pygame.font.match_font(name)
        if path:
            return path
    return None


@lru_cache(maxsize=None)
def _symbol_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Return a font that can render chess glyphs, on Windows, macOS or Linux."""
    path = _symbol_font_path()
    if path:
        font = pygame.font.Font(path, size)
        font.set_bold(bold)
        return font
    return pygame.font.SysFont(None, size, bold=bold)


class ChessUI:
    """Main UI class for the chess game."""

    # Layout constants
    BOARD_WIDTH = BOARD_HEIGHT = 640
    MOVE_LOG_WIDTH = 300
    DIMENSION = 8
    SQUARE_SIZE = BOARD_WIDTH // DIMENSION
    MAX_FPS = 60
    FRAME_THICKNESS = 6

    # Pseudo-3D perspective board
    PERSPECTIVE_TOP_RATIO = 0.86  # far edge width as a fraction of the near edge
    PERSPECTIVE_GAMMA = 1.15      # >1 compresses far rows for a depth illusion
    PIECE_SCALE_FAR = 0.62
    PIECE_SCALE_NEAR = 1.0

    # Colors - Wood theme
    LIGHT_SQUARE = pygame.Color(240, 217, 181)
    DARK_SQUARE = pygame.Color(181, 136, 99)
    HIGHLIGHT_COLOR = pygame.Color(247, 247, 105)
    SELECTED_COLOR = pygame.Color(124, 252, 0)
    LAST_MOVE_FROM = pygame.Color(205, 210, 106)
    LAST_MOVE_TO = pygame.Color(168, 190, 72)
    CHECK_COLOR = pygame.Color(235, 67, 52)
    VALID_MOVE_DOT = pygame.Color(30, 30, 30)       # dark core, readable on light and dark squares
    VALID_MOVE_RING = pygame.Color(255, 255, 255)   # light halo keeps the dot visible on dark wood
    PROMO_HOVER = pygame.Color(200, 220, 255)

    # Wood / frame tokens
    WOOD_DARK = pygame.Color(42, 25, 14)
    WOOD_MID = pygame.Color(101, 67, 40)
    WOOD_LIGHT = pygame.Color(173, 132, 84)
    COORD_TEXT = pygame.Color(224, 198, 145)
    COORD_OUTLINE = pygame.Color(25, 15, 8)

    # Panel colors
    PANEL_BG = pygame.Color(38, 36, 33)
    PANEL_TEXT = pygame.Color(220, 220, 220)
    PANEL_DIM = pygame.Color(150, 150, 150)
    PANEL_ACCENT = pygame.Color(120, 170, 80)
    PANEL_DIVIDER = pygame.Color(70, 68, 65)
    PANEL_LATEST = pygame.Color(255, 255, 200)

    # Menu / control colors. White label text on BUTTON_* must stay >= 4.5:1 (WCAG AA),
    # including at the lightest point of the button gradient.
    MENU_TEXT = pygame.Color(255, 255, 255)
    MENU_SUBTLE = pygame.Color(170, 170, 170)
    MENU_LABEL = pygame.Color(200, 200, 200)
    BUTTON_COLOR = pygame.Color(40, 95, 145)
    BUTTON_HOVER = pygame.Color(50, 108, 160)
    BUTTON_BORDER = pygame.Color(20, 28, 42)
    FOCUS_RING = pygame.Color(255, 215, 90)

    # Piece value for material display
    PIECE_DISPLAY_VALUES = {'Q': 9, 'R': 5, 'B': 3, 'N': 3, 'P': 1}
    PIECE_ORDER = ['Q', 'R', 'B', 'N', 'P']

    def __init__(self):
        """Initialize Pygame and set up the display."""
        try:
            pygame.mixer.pre_init(44100, -16, 1, 512)
            pygame.init()
            pygame.display.set_caption('Chess Game')
            pygame.display.set_icon(self._create_app_icon())

            self.screen = pygame.display.set_mode(
                (self.BOARD_WIDTH + self.MOVE_LOG_WIDTH, self.BOARD_HEIGHT),
                pygame.DOUBLEBUF | pygame.HWSURFACE
            )
            self.clock = pygame.time.Clock()
        except pygame.error as e:
            print(f"Failed to initialize Pygame: {e}")
            sys.exit(1)

        # Fonts
        self.piece_font = _symbol_font(62)
        self.small_piece_font = _symbol_font(26)
        self.coord_font = pygame.font.SysFont("Arial", 13, bold=True)
        self.log_font = pygame.font.SysFont("Consolas", 14)
        self.title_font = pygame.font.SysFont("Arial", 22, bold=True)
        self.status_font = pygame.font.SysFont("Arial", 15)
        self.button_font = pygame.font.SysFont("Arial", 18, bold=True)
        self.material_font = pygame.font.SysFont("Arial", 13, bold=True)
        self.toggle_font = pygame.font.SysFont("Arial", 14, bold=True)
        self.menu_title_font = pygame.font.SysFont("Arial", 48, bold=True)
        self.over_font = pygame.font.SysFont("Arial", 30, bold=True)

        # Unicode chess pieces
        self.piece_symbols = {
            'wK': '\u2654', 'wQ': '\u2655', 'wR': '\u2656',
            'wB': '\u2657', 'wN': '\u2658', 'wP': '\u2659',
            'bK': '\u265A', 'bQ': '\u265B', 'bR': '\u265C',
            'bB': '\u265D', 'bN': '\u265E', 'bP': '\u265F'
        }

        # Pre-render piece images
        self.piece_images = {}
        self._create_piece_images()

        # Sound effects
        self._init_sounds()

        # Initialize engine
        self.engine = ChessEngine()

        # AI settings
        self.ai = ChessAI(depth=3)
        self.player_color = 'w'
        self.ai_thinking = False
        self.ai_move = None
        self.ai_lock = threading.Lock()
        self.ai_generation = 0  # bumped on reset so a stale search can't touch a new game

        # Game mode
        self.vs_ai = True
        self.show_menu = True
        self.menu_state = 'main'
        self.menu_focus = 0

        # Modal / transient UI state
        self.confirm_new_game = False
        self.move_scroll = 0              # pairs scrolled back from the latest move
        self.game_over_sound_at = None    # tick at which to play the game-over sound

        # Board orientation
        self.flip_board = False

        # 2D / 3D view toggle
        self.view_3d = False
        self.view_toggle_rect = pygame.Rect(
            self.BOARD_WIDTH + self.MOVE_LOG_WIDTH - 106, 8, 96, 28)
        self._persp_top_left = (self.BOARD_WIDTH * (1 - self.PERSPECTIVE_TOP_RATIO) / 2, 0)
        self._persp_top_right = (self.BOARD_WIDTH * (1 + self.PERSPECTIVE_TOP_RATIO) / 2, 0)
        self._persp_bottom_left = (0, self.BOARD_HEIGHT)
        self._persp_bottom_right = (self.BOARD_WIDTH, self.BOARD_HEIGHT)

        # UI state
        self.selected_square = None
        self.player_clicks = []
        self.valid_moves = []
        self.all_valid_moves = []
        self.game_over = False
        self.animating = False

        # Drag-and-drop state
        self.dragging = False
        self.drag_piece = None
        self.drag_start = None
        self.drag_pos = (0, 0)

        # Promotion state
        self.promotion_pending = None
        self.promotion_rects = []
        self.promotion_panel = pygame.Rect(0, 0, 0, 0)
        self.promotion_pieces = ['Q', 'R', 'B', 'N']
        self.promotion_names = {'Q': 'Queen', 'R': 'Rook', 'B': 'Bishop', 'N': 'Knight'}

        # Pre-rendered cached surfaces
        self._cached_board_surface = None
        self._cached_board_flipped = None
        self._cached_board_surface_3d = None
        self._cached_board_flipped_3d = None
        self._cached_check_glow = self._create_check_glow()
        self._cached_move_dot = self._create_move_dot()
        self._cached_capture_indicator = self._create_capture_indicator()
        self._cached_piece_shadow = self._create_piece_shadow()
        self._highlight_from = self._create_highlight_surface(self.LAST_MOVE_FROM, 130)
        self._highlight_to = self._create_highlight_surface(self.LAST_MOVE_TO, 130)
        self._highlight_selected = self._create_highlight_surface(self.SELECTED_COLOR, 140)
        self._cached_panel_surface = None
        self._cached_panel_move_count = -1
        self._cached_panel_state = None  # (white_to_move, game_over, ai_thinking)

        # Buttons
        self.buttons = {}
        self._create_buttons()

    def _create_app_icon(self) -> pygame.Surface:
        """Build a beveled, sphere-shaded wooden medallion icon with an embossed crown."""
        scale = 2  # render at 2x and downscale for smoother curves
        size = 64 * scale
        cx = cy = size // 2
        radius = cx - 3 * scale

        mask = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255), (cx, cy), radius)

        surf = pygame.Surface((size, size), pygame.SRCALPHA)

        # Drop shadow so the medallion appears to sit above the titlebar
        pygame.draw.circle(surf, (0, 0, 0, 110),
                            (cx + 3 * scale, cy + 4 * scale), radius)

        body = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(body, (72, 44, 26, 255), (cx, cy), radius)

        # Directional sphere shading: warm light wash from the upper-left...
        light = pygame.Surface((size, size), pygame.SRCALPHA)
        light_cx, light_cy = cx - radius // 2, cy - radius // 2
        for r in range(radius, 0, -2):
            alpha = int(70 * (1 - r / radius))
            pygame.draw.circle(light, (255, 235, 200, alpha), (light_cx, light_cy), r)
        light.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        body.blit(light, (0, 0))

        # ...and a cast shadow toward the lower-right, for a rounded, lit sphere look
        dark = pygame.Surface((size, size), pygame.SRCALPHA)
        dark_cx, dark_cy = cx + radius // 2, cy + radius // 2
        for r in range(radius, 0, -2):
            alpha = int(100 * (1 - r / radius))
            pygame.draw.circle(dark, (0, 0, 0, alpha), (dark_cx, dark_cy), r)
        dark.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        body.blit(dark, (0, 0))

        # Beveled metal rim: a mid-tone ring split into a lit half and a shaded half
        ring_width = 5 * scale
        ring_rect = pygame.Rect(cx - radius, cy - radius, radius * 2, radius * 2)
        pygame.draw.circle(body, (150, 112, 58, 255), (cx, cy), radius, ring_width)
        pygame.draw.arc(body, (235, 205, 130, 255), ring_rect,
                         math.radians(45), math.radians(225), ring_width)
        pygame.draw.arc(body, (85, 58, 26, 255), ring_rect,
                         math.radians(225), math.radians(405), ring_width)

        surf.blit(body, (0, 0))

        # Crown glyph, embossed: thick dark recessed outline, metallic gold fill shaded top-to-bottom
        icon_font = _symbol_font(38 * scale, bold=True)
        symbol = '♔'
        glyph_layer = pygame.Surface((size, size), pygame.SRCALPHA)
        for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)]:
            outline = icon_font.render(symbol, True, (30, 18, 10))
            glyph_layer.blit(outline, outline.get_rect(
                center=(cx + dx * scale, cy + dy * scale + 2 * scale)))
        fill = icon_font.render(symbol, True, (245, 222, 160))
        glyph_layer.blit(fill, fill.get_rect(center=(cx, cy + 2 * scale)))
        self._apply_vertical_shade(glyph_layer, top_factor=1.35, bottom_factor=0.6)
        surf.blit(glyph_layer, (0, 0))

        # Small glossy specular highlight for a polished, 3D finish
        glint = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.ellipse(glint, (255, 255, 255, 130),
                             (cx - radius // 2 - 6 * scale, cy - radius // 2 - 10 * scale,
                              16 * scale, 9 * scale))
        surf.blit(glint, (0, 0))

        return pygame.transform.smoothscale(surf, (64, 64))

    def _create_piece_images(self) -> None:
        """Pre-render piece images with shadows and outlines."""
        for piece, symbol in self.piece_symbols.items():
            surface = pygame.Surface((self.SQUARE_SIZE, self.SQUARE_SIZE), pygame.SRCALPHA)

            color = pygame.Color(255, 255, 255) if piece[0] == 'w' else pygame.Color(30, 30, 30)
            outline_color = pygame.Color(50, 50, 50) if piece[0] == 'w' else pygame.Color(200, 200, 200)

            # Drop shadow
            shadow_text = self.piece_font.render(symbol, True, pygame.Color(0, 0, 0, 60))
            shadow_rect = shadow_text.get_rect(center=(self.SQUARE_SIZE // 2 + 2, self.SQUARE_SIZE // 2 + 3))
            surface.blit(shadow_text, shadow_rect)

            # Outline
            for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                outline_text = self.piece_font.render(symbol, True, outline_color)
                outline_rect = outline_text.get_rect(center=(self.SQUARE_SIZE // 2 + dx, self.SQUARE_SIZE // 2 + dy))
                surface.blit(outline_text, outline_rect)

            # Main piece
            text = self.piece_font.render(symbol, True, color)
            text_rect = text.get_rect(center=(self.SQUARE_SIZE // 2, self.SQUARE_SIZE // 2))
            surface.blit(text, text_rect)

            self._apply_vertical_shade(surface)
            self.piece_images[piece] = surface

    def _apply_vertical_shade(self, surface: pygame.Surface,
                               top_factor: float = 1.28, bottom_factor: float = 0.62) -> None:
        """Multiply a top-to-bottom brightness gradient over a surface for a subtle 3D look."""
        w, h = surface.get_size()
        gradient = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(h):
            t = y / max(1, h - 1)
            factor = top_factor + (bottom_factor - top_factor) * t
            val = max(0, min(255, int(255 * factor)))
            pygame.draw.line(gradient, (val, val, val, 255), (0, y), (w, y))
        surface.blit(gradient, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    def _create_piece_shadow(self) -> pygame.Surface:
        """Pre-render a soft grounding shadow drawn beneath each piece."""
        surf = pygame.Surface((self.SQUARE_SIZE, self.SQUARE_SIZE), pygame.SRCALPHA)
        cx = self.SQUARE_SIZE // 2
        cy = int(self.SQUARE_SIZE * 0.84)
        for rw, rh, alpha in [(30, 11, 55), (23, 8, 80), (16, 6, 100)]:
            rect = pygame.Rect(cx - rw, cy - rh, rw * 2, rh * 2)
            pygame.draw.ellipse(surf, (0, 0, 0, alpha), rect)
        return surf

    def _init_sounds(self) -> None:
        """Generate chess sound effects procedurally."""
        try:
            self.sound_enabled = True
            sample_rate = 44100

            # Move sound - short wood click
            self.move_sound = self._generate_click_sound(sample_rate, 0.07, 700, 50, 0.25)
            # Capture sound - heavier impact
            self.capture_sound = self._generate_click_sound(sample_rate, 0.12, 450, 35, 0.35)
            # Check sound - alert tone
            self.check_sound = self._generate_tone_sound(sample_rate, 0.15, 880, 15, 0.2)
            # Castle sound - double click
            self.castle_sound = self._generate_castle_sound(sample_rate)
            # Game over sound
            self.game_over_sound = self._generate_tone_sound(sample_rate, 0.4, 330, 5, 0.15)
            # Promotion sound
            self.promote_sound = self._generate_tone_sound(sample_rate, 0.2, 660, 10, 0.2)
        except Exception:
            self.sound_enabled = False

    def _generate_click_sound(self, sr, duration, freq, decay_rate, volume):
        """Generate a percussive click sound."""
        n = int(sr * duration)
        buf = array.array('h', [0] * n)
        rng = random.Random(42)  # Deterministic for consistent sounds
        for i in range(n):
            t = i / sr
            envelope = math.exp(-t * decay_rate)
            noise = rng.uniform(-1, 1) * 0.4
            tone = math.sin(2 * math.pi * freq * t) * 0.6
            sample = (tone + noise) * envelope
            buf[i] = max(-32767, min(32767, int(sample * 32767 * volume)))
        return pygame.mixer.Sound(buffer=bytes(buf))

    def _generate_tone_sound(self, sr, duration, freq, decay_rate, volume):
        """Generate a tonal sound."""
        n = int(sr * duration)
        buf = array.array('h', [0] * n)
        for i in range(n):
            t = i / sr
            envelope = math.exp(-t * decay_rate)
            # Fade out at end
            fade = min(1.0, (n - i) / (sr * 0.03))
            sample = math.sin(2 * math.pi * freq * t) * envelope * fade
            buf[i] = max(-32767, min(32767, int(sample * 32767 * volume)))
        return pygame.mixer.Sound(buffer=bytes(buf))

    def _generate_castle_sound(self, sr):
        """Generate a castle sound (two clicks)."""
        duration = 0.18
        n = int(sr * duration)
        buf = array.array('h', [0] * n)
        rng = random.Random(99)
        for i in range(n):
            t = i / sr
            # Two click events
            env1 = math.exp(-t * 50)
            env2 = math.exp(-(t - 0.09) * 50) if t > 0.09 else 0
            envelope = env1 + env2 * 0.8
            noise = rng.uniform(-1, 1) * 0.3
            tone = math.sin(2 * math.pi * 600 * t) * 0.7
            sample = (tone + noise) * envelope
            buf[i] = max(-32767, min(32767, int(sample * 32767 * 0.25)))
        return pygame.mixer.Sound(buffer=bytes(buf))

    def _play_sound(self, move: Move) -> None:
        """Play appropriate sound for a move."""
        if not self.sound_enabled:
            return
        try:
            if move.is_checkmate or move.is_check:
                self.check_sound.play()
            elif move.is_castle:
                self.castle_sound.play()
            elif move.piece_captured != "--" or move.is_enpassant:
                self.capture_sound.play()
            elif move.is_pawn_promotion:
                self.promote_sound.play()
            else:
                self.move_sound.play()
        except Exception:
            pass

    def _create_check_glow(self) -> pygame.Surface:
        """Pre-render the radial check highlight (static, reusable)."""
        surf = pygame.Surface((self.SQUARE_SIZE, self.SQUARE_SIZE), pygame.SRCALPHA)
        cx, cy = self.SQUARE_SIZE // 2, self.SQUARE_SIZE // 2
        max_r = self.SQUARE_SIZE // 2
        # Draw fewer, thicker rings for performance
        for r in range(max_r, 0, -3):
            alpha = int(160 * (r / max_r))
            pygame.draw.circle(surf, (self.CHECK_COLOR.r, self.CHECK_COLOR.g,
                                      self.CHECK_COLOR.b, alpha), (cx, cy), r)
        return surf

    def _create_move_dot(self) -> pygame.Surface:
        """Pre-render the valid-move dot indicator."""
        surf = pygame.Surface((self.SQUARE_SIZE, self.SQUARE_SIZE), pygame.SRCALPHA)
        center = (self.SQUARE_SIZE // 2, self.SQUARE_SIZE // 2)
        ring, dot = self.VALID_MOVE_RING, self.VALID_MOVE_DOT
        pygame.draw.circle(surf, (ring.r, ring.g, ring.b, 150), center, 12)
        pygame.draw.circle(surf, (dot.r, dot.g, dot.b, 190), center, 10)
        return surf

    def _create_capture_indicator(self) -> pygame.Surface:
        """Pre-render the capture corner-triangle indicator."""
        surf = pygame.Surface((self.SQUARE_SIZE, self.SQUARE_SIZE), pygame.SRCALPHA)
        tri_size = 16
        corners = [
            [(0, 0), (tri_size, 0), (0, tri_size)],
            [(self.SQUARE_SIZE, 0), (self.SQUARE_SIZE - tri_size, 0), (self.SQUARE_SIZE, tri_size)],
            [(0, self.SQUARE_SIZE), (tri_size, self.SQUARE_SIZE), (0, self.SQUARE_SIZE - tri_size)],
            [(self.SQUARE_SIZE, self.SQUARE_SIZE), (self.SQUARE_SIZE - tri_size, self.SQUARE_SIZE),
             (self.SQUARE_SIZE, self.SQUARE_SIZE - tri_size)],
        ]
        for tri in corners:
            pygame.draw.polygon(surf, (self.VALID_MOVE_DOT.r, self.VALID_MOVE_DOT.g,
                                       self.VALID_MOVE_DOT.b, 200), tri)
        return surf

    def _create_highlight_surface(self, color: pygame.Color, alpha: int) -> pygame.Surface:
        """Pre-render a square highlight overlay."""
        surf = pygame.Surface((self.SQUARE_SIZE, self.SQUARE_SIZE), pygame.SRCALPHA)
        surf.fill((color.r, color.g, color.b, alpha))
        return surf

    # --- Pseudo-3D perspective board ---

    def _lerp(self, a: float, b: float, t: float) -> float:
        return a + (b - a) * t

    def _persp_point(self, u: float, v_raw: float) -> tuple:
        """Map board-fraction (u, v_raw) in [0,1]x[0,1] to a screen point on the
        perspective trapezoid. v_raw=0 is the far edge, v_raw=1 the near edge."""
        v = v_raw ** self.PERSPECTIVE_GAMMA
        top_x = self._lerp(self._persp_top_left[0], self._persp_top_right[0], u)
        bottom_x = self._lerp(self._persp_bottom_left[0], self._persp_bottom_right[0], u)
        x = self._lerp(top_x, bottom_x, v)
        y = self._lerp(self._persp_top_left[1], self._persp_bottom_left[1], v)
        return (x, y)

    def _persp_quad(self, visual_row: int, visual_col: int) -> tuple:
        """Return the four screen-space corners (tl, tr, br, bl) of a square,
        addressed by its visual position (0,0 = top-left as currently displayed)."""
        u0, u1 = visual_col / 8, (visual_col + 1) / 8
        v0, v1 = visual_row / 8, (visual_row + 1) / 8
        tl = self._persp_point(u0, v0)
        tr = self._persp_point(u1, v0)
        br = self._persp_point(u1, v1)
        bl = self._persp_point(u0, v1)
        return tl, tr, br, bl

    def _visual_rc(self, row: int, col: int) -> tuple:
        """Convert engine (row, col) to the visually-displayed (row, col), honoring flip."""
        if self.flip_board:
            return 7 - row, 7 - col
        return row, col

    def _board_coords_3d(self, pos: tuple) -> tuple:
        """Inverse-map a screen position to (row, col) under the perspective transform."""
        mx, my = pos
        if my < 0 or my >= self.BOARD_HEIGHT:
            return (-1, -1)
        v_screen = my / self.BOARD_HEIGHT
        v_raw = v_screen ** (1 / self.PERSPECTIVE_GAMMA)
        visual_row = min(7, int(v_raw * 8))

        left_x = self._lerp(self._persp_top_left[0], self._persp_bottom_left[0], v_screen)
        right_x = self._lerp(self._persp_top_right[0], self._persp_bottom_right[0], v_screen)
        if right_x <= left_x:
            return (-1, -1)
        u = (mx - left_x) / (right_x - left_x)
        if u < 0 or u > 1:
            return (-1, -1)
        visual_col = min(7, max(0, int(u * 8)))

        if self.flip_board:
            return 7 - visual_row, 7 - visual_col
        return visual_row, visual_col

    def _get_board_surface_3d(self) -> pygame.Surface:
        """Get or create the cached perspective board background."""
        if (self._cached_board_surface_3d is not None
                and self._cached_board_flipped_3d == self.flip_board):
            return self._cached_board_surface_3d

        surf = pygame.Surface((self.BOARD_WIDTH, self.BOARD_HEIGHT))
        surf.fill((20, 12, 7))
        self._fill_perspective_frame(surf)

        for visual_row in range(self.DIMENSION):
            for visual_col in range(self.DIMENSION):
                row, col = (7 - visual_row, 7 - visual_col) if self.flip_board else (visual_row, visual_col)
                is_light = (row + col) % 2 == 0
                base = self.LIGHT_SQUARE if is_light else self.DARK_SQUARE

                # Depth shading: far rows read slightly darker/cooler, near rows brighter,
                # reinforcing the illusion that the board recedes from the viewer.
                depth_t = visual_row / 7
                factor = 0.72 + 0.4 * depth_t
                color = (min(255, int(base.r * factor)), min(255, int(base.g * factor)),
                         min(255, int(base.b * factor)))

                tl, tr, br, bl = self._persp_quad(visual_row, visual_col)
                pygame.draw.polygon(surf, color, [tl, tr, br, bl])
                pygame.draw.polygon(surf, (0, 0, 0), [tl, tr, br, bl], 1)

        self._stroke_perspective_frame(surf)
        self._cached_board_surface_3d = surf
        self._cached_board_flipped_3d = self.flip_board
        return surf

    def _fill_perspective_frame(self, surf: pygame.Surface) -> None:
        """Fill the wooden wedge outside the board trapezoid, before squares are drawn
        on top -- so this only ever shows through in the sliver outside the board."""
        dark = self.WOOD_DARK
        outer = [
            (max(0, self._persp_top_left[0] - 10), 0),
            (min(self.BOARD_WIDTH - 1, self._persp_top_right[0] + 10), 0),
            (min(self.BOARD_WIDTH - 1, self._persp_bottom_right[0]), self.BOARD_HEIGHT - 1),
            (max(0, self._persp_bottom_left[0]), self.BOARD_HEIGHT - 1),
        ]
        pygame.draw.polygon(surf, dark, outer)

    def _stroke_perspective_frame(self, surf: pygame.Surface) -> None:
        """Draw the frame's bevel accents as outlines on top of the finished board,
        so they never blot out the squares underneath."""
        dark = self.WOOD_DARK
        light = self.WOOD_LIGHT
        outer = [
            (max(0, self._persp_top_left[0] - 10), 0),
            (min(self.BOARD_WIDTH - 1, self._persp_top_right[0] + 10), 0),
            (min(self.BOARD_WIDTH - 1, self._persp_bottom_right[0]), self.BOARD_HEIGHT - 1),
            (max(0, self._persp_bottom_left[0]), self.BOARD_HEIGHT - 1),
        ]
        inner = [self._persp_top_left, self._persp_top_right,
                 self._persp_bottom_right, self._persp_bottom_left]
        pygame.draw.polygon(surf, light, outer, 3)
        pygame.draw.polygon(surf, dark, inner, 2)

    def _get_board_surface(self) -> pygame.Surface:
        """Get or create the cached board background (squares + coordinates)."""
        if self._cached_board_surface is not None and self._cached_board_flipped == self.flip_board:
            return self._cached_board_surface

        surf = pygame.Surface((self.BOARD_WIDTH, self.BOARD_HEIGHT))
        for row in range(self.DIMENSION):
            for col in range(self.DIMENSION):
                board_row = 7 - row if self.flip_board else row
                board_col = 7 - col if self.flip_board else col
                is_light = (board_row + board_col) % 2 == 0
                color = self.LIGHT_SQUARE if is_light else self.DARK_SQUARE
                rect = pygame.Rect(col * self.SQUARE_SIZE, row * self.SQUARE_SIZE,
                                   self.SQUARE_SIZE, self.SQUARE_SIZE)
                pygame.draw.rect(surf, color, rect)
                self._draw_wood_grain(surf, rect, color, board_row * 8 + board_col)

        self._draw_board_frame(surf)

        # Coordinate labels drawn last, on top of the frame, in a fixed gold-on-dark
        # style so they stay legible whether they land on a square or the wood trim.
        for i in range(self.DIMENSION):
            if self.flip_board:
                rank_label = str(i + 1)
                file_label = chr(ord('h') - i)
            else:
                rank_label = str(8 - i)
                file_label = chr(ord('a') + i)

            self._draw_outlined_coord(surf, rank_label, (self.FRAME_THICKNESS + 2, i * self.SQUARE_SIZE + 3))
            self._draw_outlined_coord(surf, file_label,
                                       (i * self.SQUARE_SIZE + self.SQUARE_SIZE - 12, self.BOARD_HEIGHT - 16))

        self._cached_board_surface = surf
        self._cached_board_flipped = self.flip_board
        return surf

    def _draw_wood_grain(self, surf: pygame.Surface, rect: pygame.Rect,
                          base_color: pygame.Color, seed: int) -> None:
        """Blend faint noise streaks into a square for a wood-grain texture."""
        rng = random.Random(seed)
        streaks = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        for _ in range(10):
            y = rng.randint(0, rect.height)
            drift = rng.randint(-5, 5)
            thickness = rng.randint(1, 2)
            shade = rng.randint(-16, 12)
            r = max(0, min(255, base_color.r + shade))
            g = max(0, min(255, base_color.g + shade))
            b = max(0, min(255, base_color.b + shade))
            pygame.draw.line(streaks, (r, g, b, 45), (0, y), (rect.width, y + drift), thickness)
        surf.blit(streaks, rect.topleft)

        # Inset bevel: dark lip on top/left, bright lip on bottom/right, so each
        # square reads as a tile set slightly into the board rather than flat paint.
        edge = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.line(edge, (0, 0, 0, 40), (0, 0), (rect.width, 0), 2)
        pygame.draw.line(edge, (0, 0, 0, 40), (0, 0), (0, rect.height), 2)
        pygame.draw.line(edge, (255, 255, 255, 32), (0, rect.height - 2), (rect.width, rect.height - 2), 2)
        pygame.draw.line(edge, (255, 255, 255, 32), (rect.width - 2, 0), (rect.width - 2, rect.height), 2)
        surf.blit(edge, rect.topleft)

    def _draw_bevel_rect(self, surf: pygame.Surface, rect: pygame.Rect, thickness: int,
                          light_color, dark_color, raised: bool = True) -> None:
        """Draw a two-tone beveled border: raised (lit top/left) or inset (lit bottom/right)."""
        top_color = light_color if raised else dark_color
        bottom_color = dark_color if raised else light_color
        x, y, w, h = rect
        for i in range(thickness):
            pygame.draw.line(surf, top_color, (x + i, y + i), (x + w - 1 - i, y + i))
            pygame.draw.line(surf, top_color, (x + i, y + i), (x + i, y + h - 1 - i))
            pygame.draw.line(surf, bottom_color, (x + i, y + h - 1 - i), (x + w - 1 - i, y + h - 1 - i))
            pygame.draw.line(surf, bottom_color, (x + w - 1 - i, y + i), (x + w - 1 - i, y + h - 1 - i))

    def _draw_board_frame(self, surf: pygame.Surface) -> None:
        """Draw a thick, raised wooden frame trim around the board edge."""
        dark = self.WOOD_DARK
        mid = self.WOOD_MID
        light = self.WOOD_LIGHT
        thickness = self.FRAME_THICKNESS

        pygame.draw.rect(surf, mid, (0, 0, self.BOARD_WIDTH, self.BOARD_HEIGHT), thickness)
        self._draw_bevel_rect(surf, pygame.Rect(0, 0, self.BOARD_WIDTH, self.BOARD_HEIGHT),
                               thickness, light, dark, raised=True)
        # Groove separating the raised frame from the sunken board
        pygame.draw.rect(surf, dark, (thickness, thickness,
                                       self.BOARD_WIDTH - 2 * thickness,
                                       self.BOARD_HEIGHT - 2 * thickness), 1)

    def _draw_outlined_coord(self, surf: pygame.Surface, label: str, pos: tuple) -> None:
        """Draw a small gold coordinate label with a dark outline for legibility anywhere."""
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            shadow = self.coord_font.render(label, True, self.COORD_OUTLINE)
            surf.blit(shadow, (pos[0] + dx, pos[1] + dy))
        text = self.coord_font.render(label, True, self.COORD_TEXT)
        surf.blit(text, pos)

    def _create_buttons(self) -> None:
        """Create menu buttons."""
        bw, bh = 220, 50
        cx = (self.BOARD_WIDTH + self.MOVE_LOG_WIDTH) // 2

        board_cx = self.BOARD_WIDTH // 2
        self.buttons = {
            'back': pygame.Rect(cx - bw // 2, 440, bw, 44),
            'confirm_yes': pygame.Rect(board_cx - 110, 330, 100, 44),
            'confirm_no': pygame.Rect(board_cx + 10, 330, 100, 44),
            'vs_ai': pygame.Rect(cx - bw // 2, 220, bw, bh),
            'vs_human': pygame.Rect(cx - bw // 2, 290, bw, bh),
            'play_white': pygame.Rect(cx - bw // 2, 220, bw, bh),
            'play_black': pygame.Rect(cx - bw // 2, 290, bw, bh),
            'difficulty_easy': pygame.Rect(cx - bw // 2, 220, bw, bh),
            'difficulty_medium': pygame.Rect(cx - bw // 2, 290, bw, bh),
            'difficulty_hard': pygame.Rect(cx - bw // 2, 360, bw, bh),
        }

    # --- Main game loop ---

    def run(self) -> None:
        """Main game loop."""
        running = True
        self.all_valid_moves = self.engine.get_valid_moves()

        while running:
            mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.confirm_new_game:
                        self._handle_confirm_click(mouse_pos)
                    elif not self.show_menu and self.view_toggle_rect.collidepoint(mouse_pos):
                        self._toggle_view()
                    elif self.show_menu:
                        self._handle_menu_click(mouse_pos)
                    elif self.promotion_pending:
                        self._handle_promotion_click(mouse_pos)
                    elif not self.game_over and not self.animating and not self.ai_thinking:
                        if self._is_player_turn():
                            self._handle_mouse_down(mouse_pos)

                elif event.type == pygame.MOUSEMOTION:
                    if self.dragging:
                        self.drag_pos = event.pos
                    if self.show_menu:
                        for i, bid in enumerate(self._menu_options()):
                            if self.buttons[bid].collidepoint(event.pos):
                                self.menu_focus = i

                elif event.type == pygame.MOUSEWHEEL:
                    if not self.show_menu and mouse_pos[0] >= self.BOARD_WIDTH:
                        self.move_scroll = max(0, self.move_scroll + event.y)

                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    if self.dragging:
                        self._handle_mouse_up(mouse_pos)

                elif event.type == pygame.KEYDOWN:
                    self._handle_key(event.key)

            # AI move
            if (self.vs_ai and not self.show_menu and not self.game_over
                    and not self.ai_thinking and not self.animating
                    and self.promotion_pending is None):
                if not self._is_player_turn():
                    self._start_ai_move()

            # Deferred game-over sound (replaces a blocking delay)
            if (self.game_over_sound_at is not None
                    and pygame.time.get_ticks() >= self.game_over_sound_at):
                self.game_over_sound_at = None
                if self.sound_enabled:
                    try:
                        self.game_over_sound.play()
                    except Exception:
                        pass

            # Process AI result (held back while the menu is open)
            move = None
            with self.ai_lock:
                if self.ai_move is not None and not self.show_menu:
                    move = self.ai_move
                    self.ai_move = None

            if move is not None:
                # Check if AI move is a promotion
                if move.is_pawn_promotion:
                    move.promotion_piece = 'Q'  # AI always promotes to queen
                self._execute_move(move, animate=True)
                self.ai_thinking = False

            # Draw
            if self.show_menu:
                self._draw_menu(mouse_pos)
            else:
                self._draw_game_state()
                if self.promotion_pending:
                    self._draw_promotion_dialog(mouse_pos)
                if self.game_over:
                    self._draw_game_over_message()
                elif self.ai_thinking:
                    self._draw_thinking_indicator()
            if self.confirm_new_game:
                self._draw_confirm_dialog(mouse_pos)

            pygame.display.flip()
            self.clock.tick(self.MAX_FPS)
            pygame.event.pump()

        pygame.quit()
        sys.exit()

    # --- Input handling ---

    def _toggle_view(self) -> None:
        self.view_3d = not self.view_3d
        self._reset_selection()

    def _handle_key(self, key: int) -> None:
        """Route a key press to the active layer: confirm dialog > menu > promotion > game."""
        if self.confirm_new_game:
            if key in (pygame.K_y, pygame.K_RETURN, pygame.K_KP_ENTER):
                self.confirm_new_game = False
                self._reset_game()
            elif key in (pygame.K_n, pygame.K_ESCAPE):
                self.confirm_new_game = False
            return

        if self.show_menu:
            self._handle_menu_key(key)
            return

        if self.promotion_pending:
            if key == pygame.K_ESCAPE:
                self.promotion_pending = None
            else:
                letter = pygame.key.name(key).upper()
                if letter in self.promotion_pieces:
                    self._choose_promotion(letter)
            return

        if key == pygame.K_z:
            self._undo_move()
        elif key == pygame.K_r:
            self._request_new_game()
        elif key == pygame.K_v:
            self._toggle_view()
        elif key == pygame.K_ESCAPE:
            self.show_menu = True
            self.menu_state = 'main'
            self.menu_focus = 0
        elif key == pygame.K_PAGEUP:
            self.move_scroll += 3
        elif key == pygame.K_PAGEDOWN:
            self.move_scroll = max(0, self.move_scroll - 3)

    def _request_new_game(self) -> None:
        """Start over immediately if nothing is at stake, otherwise ask first."""
        if self.engine.move_log and not self.game_over:
            self.confirm_new_game = True
        else:
            self._reset_game()

    def _handle_confirm_click(self, pos: tuple) -> None:
        if self.buttons['confirm_yes'].collidepoint(pos):
            self.confirm_new_game = False
            self._reset_game()
        elif self.buttons['confirm_no'].collidepoint(pos):
            self.confirm_new_game = False

    def _menu_options(self) -> list:
        return {
            'main': ['vs_ai', 'vs_human'],
            'color_select': ['play_white', 'play_black', 'back'],
            'difficulty': ['difficulty_easy', 'difficulty_medium', 'difficulty_hard', 'back'],
        }[self.menu_state]

    def _handle_menu_key(self, key: int) -> None:
        options = self._menu_options()
        if key in (pygame.K_DOWN, pygame.K_TAB):
            self.menu_focus = (self.menu_focus + 1) % len(options)
        elif key == pygame.K_UP:
            self.menu_focus = (self.menu_focus - 1) % len(options)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._activate_menu(options[self.menu_focus])
        elif key == pygame.K_ESCAPE:
            if self.menu_state != 'main':
                self._activate_menu('back')
            elif self.engine.move_log:
                self.show_menu = False  # resume the game in progress

    def _activate_menu(self, button_id: str) -> None:
        """Apply a menu choice (shared by mouse and keyboard)."""
        self.menu_focus = 0
        if button_id == 'back':
            self.menu_state = 'main' if self.menu_state == 'color_select' else 'color_select'
        elif button_id == 'vs_ai':
            self.menu_state = 'color_select'
        elif button_id == 'vs_human':
            self.flip_board = False
            self._start_game(vs_ai=False)
        elif button_id in ('play_white', 'play_black'):
            self.player_color = 'w' if button_id == 'play_white' else 'b'
            self.flip_board = self.player_color == 'b'
            self.menu_state = 'difficulty'
        elif button_id.startswith('difficulty_'):
            self.ai.set_difficulty(button_id.split('_', 1)[1])
            self._start_game(vs_ai=True)

    def _start_game(self, vs_ai: bool) -> None:
        """Begin a fresh game from the menu."""
        self._reset_game()
        self.vs_ai = vs_ai
        self.show_menu = False

    def _is_player_turn(self) -> bool:
        if not self.vs_ai:
            return True
        current = 'w' if self.engine.white_to_move else 'b'
        return current == self.player_color

    def _board_coords(self, pos: tuple) -> tuple:
        """Convert screen position to board coordinates, accounting for flip."""
        if self.view_3d:
            return self._board_coords_3d(pos)
        col = pos[0] // self.SQUARE_SIZE
        row = pos[1] // self.SQUARE_SIZE
        if col >= self.DIMENSION:
            return (-1, -1)
        if self.flip_board:
            row = 7 - row
            col = 7 - col
        return (row, col)

    def _screen_coords(self, row: int, col: int) -> tuple:
        """Convert board coordinates to screen position, accounting for flip."""
        if self.flip_board:
            return ((7 - col) * self.SQUARE_SIZE, (7 - row) * self.SQUARE_SIZE)
        return (col * self.SQUARE_SIZE, row * self.SQUARE_SIZE)

    def _handle_mouse_down(self, pos: tuple) -> None:
        """Handle mouse button down: start drag or select piece."""
        row, col = self._board_coords(pos)
        if row < 0:
            return

        piece = self.engine.get_piece_at(row, col)
        current_color = 'w' if self.engine.white_to_move else 'b'

        if piece != "--" and piece[0] == current_color:
            if not self.view_3d:
                # Start dragging this piece
                self.dragging = True
                self.drag_piece = piece
                self.drag_start = (row, col)
                self.drag_pos = pos
            self.selected_square = (row, col)
            self.valid_moves = [m for m in self.all_valid_moves
                                if m.start_row == row and m.start_col == col]
        elif self.selected_square:
            # Click-to-move: try to move the already-selected piece here
            self._try_move(row, col)

    def _handle_mouse_up(self, pos: tuple) -> None:
        """Handle mouse button up: complete drag or treat as click-select."""
        if not self.dragging:
            return

        row, col = self._board_coords(pos)
        self.dragging = False

        if row < 0 or (row, col) == self.drag_start:
            # Dropped on same square or off-board: keep piece selected (click mode)
            self.drag_piece = None
            return

        # Try to make the move
        self._try_move(row, col)
        self.drag_piece = None

    def _try_move(self, end_row: int, end_col: int) -> None:
        """Attempt to make a move to the target square."""
        if not self.selected_square:
            return

        start_row, start_col = self.selected_square

        # Check if clicking on own piece -> change selection
        piece = self.engine.get_piece_at(end_row, end_col)
        current_color = 'w' if self.engine.white_to_move else 'b'
        if piece != "--" and piece[0] == current_color and (end_row, end_col) != self.selected_square:
            self.selected_square = (end_row, end_col)
            self.valid_moves = [m for m in self.all_valid_moves
                                if m.start_row == end_row and m.start_col == end_col]
            return

        # Find matching valid move
        candidate = Move(start_row, start_col, end_row, end_col,
                         self.engine.get_piece_at(start_row, start_col),
                         self.engine.get_piece_at(end_row, end_col))

        for valid_move in self.all_valid_moves:
            if candidate == valid_move:
                if valid_move.is_pawn_promotion:
                    # Show promotion dialog
                    self.promotion_pending = valid_move
                    self._reset_selection()
                else:
                    self._execute_move(valid_move, animate=True)
                return

        self._reset_selection()

    def _handle_promotion_click(self, pos: tuple) -> None:
        """Handle click on promotion dialog."""
        for i, rect in enumerate(self.promotion_rects):
            if rect.collidepoint(pos):
                self._choose_promotion(self.promotion_pieces[i])
                return
        if self.promotion_panel.collidepoint(pos):
            return  # clicked dialog chrome, not a choice
        # Click outside dialog -> cancel
        self.promotion_pending = None

    def _choose_promotion(self, piece: str) -> None:
        move = self.promotion_pending
        move.promotion_piece = piece
        self.promotion_pending = None
        self._execute_move(move, animate=False)

    def _handle_menu_click(self, pos: tuple) -> None:
        """Handle menu clicks (mouse)."""
        for button_id in self._menu_options():
            if self.buttons[button_id].collidepoint(pos):
                self._activate_menu(button_id)
                return

    # --- Move execution ---

    def _execute_move(self, move: Move, animate: bool = True) -> None:
        """Execute a move with animation and sound."""
        if animate and not self.view_3d:
            self._animate_move(move)
        self.engine.make_move(move)
        self._reset_selection()
        self.move_scroll = 0
        self.all_valid_moves = self.engine.get_valid_moves()

        # Set check / checkmate flags on the move for notation
        if len(self.all_valid_moves) == 0 and self.engine._is_in_check():
            move.is_checkmate = True
            self.engine.checkmate = True
            self.engine.in_check = True
            self.game_over = True
        elif len(self.all_valid_moves) == 0:
            self.engine.stalemate = True
            self.game_over = True
        else:
            self.engine.in_check = self.engine._is_in_check()
            if self.engine.in_check:
                move.is_check = True

        # Check for draw conditions
        if not self.game_over:
            draw_reason = self.engine.is_draw()
            if draw_reason:
                self.engine.draw_reason = draw_reason
                self.game_over = True

        self._play_sound(move)

        if self.game_over:
            self.game_over_sound_at = pygame.time.get_ticks() + 200

    def _reset_selection(self) -> None:
        self.selected_square = None
        self.player_clicks = []
        self.valid_moves = []
        self.dragging = False
        self.drag_piece = None
        self.drag_start = None

    def _start_ai_move(self) -> None:
        """Start AI move calculation in background."""
        self.ai_thinking = True
        generation = self.ai_generation
        valid_moves = list(self.all_valid_moves)

        def publish(move):
            # Drop the result if the game was reset while this search was running
            with self.ai_lock:
                if generation == self.ai_generation:
                    self.ai_move = move

        def think():
            try:
                # Search on a private copy so the AI's make_move/undo_move calls
                # never mutate the live engine the render loop is reading.
                engine_copy = copy.deepcopy(self.engine)
                publish(self.ai.get_best_move(engine_copy, valid_moves))
            except Exception as e:
                print(f"AI error: {e}")
                publish(valid_moves[0] if valid_moves else None)

        thread = threading.Thread(target=think, daemon=True)
        thread.start()

    def _undo_move(self) -> None:
        if self.promotion_pending:
            self.promotion_pending = None
            return
        if self.ai_thinking or self.animating:
            return  # the AI is searching the current position; undoing now would desync it
        self.engine.undo_move()
        if self.vs_ai and self.engine.move_log:
            self.engine.undo_move()
        self.all_valid_moves = self.engine.get_valid_moves()
        self.game_over = False
        self.game_over_sound_at = None
        self.move_scroll = 0
        self._reset_selection()

    def _reset_game(self) -> None:
        with self.ai_lock:
            self.ai_generation += 1  # invalidates any in-flight AI search
            self.ai_move = None
        self.engine.reset_game()
        self.all_valid_moves = self.engine.get_valid_moves()
        self.game_over = False
        self.game_over_sound_at = None
        self.ai_thinking = False
        self.promotion_pending = None
        self.confirm_new_game = False
        self.move_scroll = 0
        self.show_menu = True
        self.menu_state = 'main'
        self.menu_focus = 0
        self._cached_panel_surface = None
        self._reset_selection()

    # --- Animation ---

    def _animate_move(self, move: Move) -> None:
        """Animate piece movement with easing."""
        self.animating = True

        delta_row = move.end_row - move.start_row
        delta_col = move.end_col - move.start_col
        frames = 12

        for frame in range(frames + 1):
            # Ease-out interpolation
            t = frame / frames
            t = 1 - (1 - t) ** 2  # Quadratic ease-out
            row = move.start_row + delta_row * t
            col = move.start_col + delta_col * t

            self._draw_board()
            self._draw_highlights()
            self._draw_pieces(exclude=(move.start_row, move.start_col))

            # Draw moving piece
            sx, sy = self._screen_coords_float(row, col)
            self.screen.blit(self._cached_piece_shadow, (sx, sy))
            self.screen.blit(self.piece_images[move.piece_moved],
                             pygame.Rect(sx, sy, self.SQUARE_SIZE, self.SQUARE_SIZE))
            self._draw_side_panel()

            pygame.display.flip()
            self.clock.tick(60)

        self.animating = False

    def _screen_coords_float(self, row: float, col: float) -> tuple:
        """Convert float board coords to screen position for animation."""
        if self.flip_board:
            return ((7 - col) * self.SQUARE_SIZE, (7 - row) * self.SQUARE_SIZE)
        return (col * self.SQUARE_SIZE, row * self.SQUARE_SIZE)

    # --- Drawing ---

    def _draw_game_state(self) -> None:
        """Draw the complete game state."""
        self._draw_board()
        self._draw_highlights()
        self._draw_pieces()
        self._draw_dragged_piece()
        self._draw_side_panel()

    def _draw_board(self) -> None:
        """Draw the chess board from cached surface."""
        if self.view_3d:
            self.screen.blit(self._get_board_surface_3d(), (0, 0))
        else:
            self.screen.blit(self._get_board_surface(), (0, 0))

    def _draw_highlights(self) -> None:
        """Draw move highlights, check, and valid move indicators."""
        if self.view_3d:
            self._draw_highlights_3d()
            return

        # Last move highlight (using pre-rendered overlays)
        if self.engine.move_log:
            last_move = self.engine.move_log[-1]
            sx, sy = self._screen_coords(last_move.start_row, last_move.start_col)
            self.screen.blit(self._highlight_from, (sx, sy))
            sx, sy = self._screen_coords(last_move.end_row, last_move.end_col)
            self.screen.blit(self._highlight_to, (sx, sy))

        # Check highlight (pre-rendered radial glow)
        if self.engine.in_check:
            king_pos = (self.engine.white_king_location if self.engine.white_to_move
                        else self.engine.black_king_location)
            sx, sy = self._screen_coords(king_pos[0], king_pos[1])
            self.screen.blit(self._cached_check_glow, (sx, sy))
            # Outline ring: a shape cue so check isn't signalled by color alone
            pygame.draw.rect(self.screen, self.CHECK_COLOR,
                             (sx, sy, self.SQUARE_SIZE, self.SQUARE_SIZE), 4)

        # Selected square
        if self.selected_square:
            row, col = self.selected_square
            sx, sy = self._screen_coords(row, col)
            self.screen.blit(self._highlight_selected, (sx, sy))

            # Valid move indicators (use pre-rendered surfaces)
            for move in self.valid_moves:
                mx, my = self._screen_coords(move.end_row, move.end_col)
                if self.engine.get_piece_at(move.end_row, move.end_col) != "--" or move.is_enpassant:
                    self.screen.blit(self._cached_capture_indicator, (mx, my))
                else:
                    self.screen.blit(self._cached_move_dot, (mx, my))

    def _draw_highlights_3d(self) -> None:
        """Draw move highlights on the perspective board as translucent quads."""
        overlay = pygame.Surface((self.BOARD_WIDTH, self.BOARD_HEIGHT), pygame.SRCALPHA)

        def quad_for(row, col):
            vr, vc = self._visual_rc(row, col)
            return self._persp_quad(vr, vc)

        if self.engine.move_log:
            last_move = self.engine.move_log[-1]
            pygame.draw.polygon(overlay, (*self.LAST_MOVE_FROM[:3], 130),
                                 quad_for(last_move.start_row, last_move.start_col))
            pygame.draw.polygon(overlay, (*self.LAST_MOVE_TO[:3], 130),
                                 quad_for(last_move.end_row, last_move.end_col))

        if self.engine.in_check:
            king_pos = (self.engine.white_king_location if self.engine.white_to_move
                        else self.engine.black_king_location)
            king_quad = quad_for(*king_pos)
            pygame.draw.polygon(overlay, (*self.CHECK_COLOR[:3], 140), king_quad)
            pygame.draw.polygon(overlay, (*self.CHECK_COLOR[:3], 255), king_quad, 3)

        if self.selected_square:
            pygame.draw.polygon(overlay, (*self.SELECTED_COLOR[:3], 140),
                                 quad_for(*self.selected_square))

            for move in self.valid_moves:
                tl, tr, br, bl = quad_for(move.end_row, move.end_col)
                cx = (tl[0] + tr[0] + br[0] + bl[0]) / 4
                cy = (tl[1] + tr[1] + br[1] + bl[1]) / 4
                vr, _ = self._visual_rc(move.end_row, move.end_col)
                depth_t = vr / 7
                radius = int(6 + 6 * depth_t)
                is_capture = (self.engine.get_piece_at(move.end_row, move.end_col) != "--"
                              or move.is_enpassant)
                color = (*self.VALID_MOVE_DOT[:3], 200)
                halo = (*self.VALID_MOVE_RING[:3], 150)
                center = (int(cx), int(cy))
                pygame.draw.circle(overlay, halo, center, radius + 2)
                if is_capture:
                    pygame.draw.circle(overlay, color, center, radius, max(2, radius // 3))
                else:
                    pygame.draw.circle(overlay, color, center, radius)

        self.screen.blit(overlay, (0, 0))

    def _draw_pieces(self, exclude: tuple = None) -> None:
        """Draw all pieces on the board."""
        if self.view_3d:
            self._draw_pieces_3d(exclude)
            return
        for row in range(self.DIMENSION):
            for col in range(self.DIMENSION):
                if exclude and (row, col) == exclude:
                    continue
                if self.dragging and self.drag_start == (row, col):
                    continue
                piece = self.engine.get_piece_at(row, col)
                if piece != "--":
                    sx, sy = self._screen_coords(row, col)
                    self.screen.blit(self._cached_piece_shadow, (sx, sy))
                    self.screen.blit(self.piece_images[piece],
                                     pygame.Rect(sx, sy, self.SQUARE_SIZE, self.SQUARE_SIZE))

    def _draw_pieces_3d(self, exclude: tuple = None) -> None:
        """Draw pieces standing on the perspective board, scaled by depth,
        painted back-to-front so nearer (larger) pieces overlap correctly."""
        for visual_row in range(self.DIMENSION):
            for visual_col in range(self.DIMENSION):
                row, col = (7 - visual_row, 7 - visual_col) if self.flip_board else (visual_row, visual_col)
                if exclude and (row, col) == exclude:
                    continue
                piece = self.engine.get_piece_at(row, col)
                if piece == "--":
                    continue

                tl, tr, br, bl = self._persp_quad(visual_row, visual_col)
                anchor_x = (bl[0] + br[0]) / 2
                anchor_y = (bl[1] + br[1]) / 2
                depth_t = (visual_row + 1) / 8
                scale = self.PIECE_SCALE_FAR + (self.PIECE_SCALE_NEAR - self.PIECE_SCALE_FAR) * depth_t
                size = max(8, int(self.SQUARE_SIZE * scale))

                shadow = pygame.transform.smoothscale(self._cached_piece_shadow, (size, size))
                self.screen.blit(shadow, (anchor_x - size / 2, anchor_y - size * 0.42))

                img = pygame.transform.smoothscale(self.piece_images[piece], (size, size))
                # Never let a far, tall piece render above the board's top edge
                draw_y = max(1, anchor_y - size)
                self.screen.blit(img, (anchor_x - size / 2, draw_y))

    def _draw_dragged_piece(self) -> None:
        """Draw the piece being dragged at cursor position."""
        if self.dragging and self.drag_piece:
            x, y = self.drag_pos
            shadow_rect = pygame.Rect(x - self.SQUARE_SIZE // 2 + 4,
                                       y - self.SQUARE_SIZE // 2 + 6,
                                       self.SQUARE_SIZE, self.SQUARE_SIZE)
            self.screen.blit(self._cached_piece_shadow, shadow_rect)
            self.screen.blit(self.piece_images[self.drag_piece],
                             pygame.Rect(x - self.SQUARE_SIZE // 2,
                                         y - self.SQUARE_SIZE // 2,
                                         self.SQUARE_SIZE, self.SQUARE_SIZE))

    def _draw_side_panel(self) -> None:
        """Draw the side panel, using cached surface when state hasn't changed."""
        current_state = (self.engine.white_to_move, self.game_over, self.ai_thinking,
                         self.engine.in_check, self.move_scroll, self.flip_board)
        move_count = len(self.engine.move_log)

        if (self._cached_panel_surface is not None
                and self._cached_panel_move_count == move_count
                and self._cached_panel_state == current_state):
            self.screen.blit(self._cached_panel_surface, (self.BOARD_WIDTH, 0))
            self._draw_view_toggle_button()
            return

        panel = pygame.Surface((self.MOVE_LOG_WIDTH, self.BOARD_HEIGHT))
        base = self.PANEL_BG
        for py in range(self.BOARD_HEIGHT):
            t = py / max(1, self.BOARD_HEIGHT - 1)
            factor = 1.12 - 0.22 * t
            r = max(0, min(255, int(base.r * factor)))
            g = max(0, min(255, int(base.g * factor)))
            b = max(0, min(255, int(base.b * factor)))
            pygame.draw.line(panel, (r, g, b), (0, py), (self.MOVE_LOG_WIDTH, py))

        y = 10

        # --- Title ---
        title = self.title_font.render("Chess", True, self.PANEL_TEXT)
        panel.blit(title, (15, y))
        y += 32

        # --- Turn indicator ---
        turn = "White" if self.engine.white_to_move else "Black"
        icon = "\u2654" if self.engine.white_to_move else "\u265A"
        if self.game_over:
            turn_text, icon = "Game Over", None
        elif self.ai_thinking:
            turn_text = f"{turn} (thinking...)"
        elif self._is_player_turn():
            turn_text = f"{turn} to move"
        else:
            turn_text = f"{turn}'s turn"
        if self.engine.in_check and not self.game_over:
            turn_text += " - CHECK!"
        turn_surf = self._render_icon_text(icon, turn_text, self.status_font, self.PANEL_ACCENT)
        panel.blit(turn_surf, (15, y))
        y += 26

        # --- Divider ---
        pygame.draw.line(panel, self.PANEL_DIVIDER, (10, y), (self.MOVE_LOG_WIDTH - 10, y))
        y += 8

        # --- Captured pieces & material advantage ---
        captured_w, captured_b, advantage = self._get_captured_info()

        top_captured = captured_b if not self.flip_board else captured_w
        bottom_captured = captured_w if not self.flip_board else captured_b
        # Each row shows the pieces captured BY that side, i.e. the opponent's color.
        top_label = "White" if not self.flip_board else "Black"
        bottom_label = "Black" if not self.flip_board else "White"
        disp_advantage = advantage if not self.flip_board else -advantage

        cap_label = self.status_font.render(f"Captured by {top_label}:", True, self.PANEL_DIM)
        panel.blit(cap_label, (15, y))
        y += 20
        y = self._draw_captured_row_to(panel, 15, y, top_captured,
                                        'b' if not self.flip_board else 'w',
                                        disp_advantage if disp_advantage > 0 else 0)
        y += 6

        cap_label2 = self.status_font.render(f"Captured by {bottom_label}:", True, self.PANEL_DIM)
        panel.blit(cap_label2, (15, y))
        y += 20
        y = self._draw_captured_row_to(panel, 15, y, bottom_captured,
                                         'w' if not self.flip_board else 'b',
                                         -disp_advantage if disp_advantage < 0 else 0)
        y += 6

        # --- Divider ---
        pygame.draw.line(panel, self.PANEL_DIVIDER, (10, y), (self.MOVE_LOG_WIDTH - 10, y))
        y += 8

        # --- Move history ---
        moves = self.engine.move_log
        header_y = y
        y += 20
        max_y = self.BOARD_HEIGHT - 120

        total_pairs = (len(moves) + 1) // 2
        visible_pairs = (max_y - y) // 20
        scrollable = total_pairs > visible_pairs
        self.move_scroll = min(self.move_scroll, max(0, total_pairs - visible_pairs))
        end_pair = total_pairs - self.move_scroll
        start_pair = max(0, end_pair - visible_pairs)

        header_text = "Moves"
        if scrollable:
            header_text += "  (wheel / PgUp: earlier)" if self.move_scroll == 0 else "  (viewing earlier)"
        header = self.log_font.render(header_text, True, self.PANEL_DIM)
        panel.blit(header, (15, header_y))

        for pair_idx in range(start_pair, end_pair):
            i = pair_idx * 2
            if y > max_y:
                break
            move_num = pair_idx + 1
            white_move = moves[i].get_chess_notation()
            black_move = moves[i + 1].get_chess_notation() if i + 1 < len(moves) else ""

            is_last = (i == len(moves) - 1 or i + 1 == len(moves) - 1)
            text_color = self.PANEL_LATEST if is_last else self.PANEL_TEXT

            num_text = self.log_font.render(f"{move_num:>3}.", True, self.PANEL_DIM)
            panel.blit(num_text, (15, y))

            w_text = self.log_font.render(f"{white_move:<8}", True, text_color)
            panel.blit(w_text, (55, y))

            if black_move:
                b_text = self.log_font.render(black_move, True, text_color)
                panel.blit(b_text, (135, y))

            y += 20

        # --- Bottom instructions ---
        pygame.draw.line(panel, self.PANEL_DIVIDER,
                         (10, self.BOARD_HEIGHT - 107),
                         (self.MOVE_LOG_WIDTH - 10, self.BOARD_HEIGHT - 107))

        instructions = [("Z", "Undo move"), ("R", "New game"),
                        ("V", "Toggle 2D/3D"), ("ESC", "Menu")]
        iy = self.BOARD_HEIGHT - 97
        for key, action in instructions:
            text = self.log_font.render(f"[{key}] {action}", True, self.PANEL_DIM)
            panel.blit(text, (15, iy))
            iy += 22

        # Inset bevel along the board-facing edge so the panel reads as recessed
        panel_rect = pygame.Rect(0, 0, self.MOVE_LOG_WIDTH, self.BOARD_HEIGHT)
        self._draw_bevel_rect(panel, panel_rect, 2,
                               pygame.Color(90, 88, 84), pygame.Color(10, 9, 8), raised=False)

        self._cached_panel_surface = panel
        self._cached_panel_move_count = move_count
        self._cached_panel_state = current_state
        self.screen.blit(panel, (self.BOARD_WIDTH, 0))
        self._draw_view_toggle_button()

    def _draw_view_toggle_button(self) -> None:
        """Draw the always-live 2D/3D toggle pill in the panel's top-right corner."""
        rect = self.view_toggle_rect
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        label = "3D" if self.view_3d else "2D"
        self._draw_gradient_button(rect, f"View: {label}", self.toggle_font, hovered,
                                   radius=6, shadow=False, gloss=False)

    def _get_captured_info(self) -> tuple:
        """Get captured pieces for each side and material advantage."""
        captured_w = []  # White pieces captured (by black)
        captured_b = []  # Black pieces captured (by white)

        for move in self.engine.move_log:
            if move.piece_captured != "--":
                if move.piece_captured[0] == 'w':
                    captured_w.append(move.piece_captured[1])
                else:
                    captured_b.append(move.piece_captured[1])

        # Sort by piece value (highest first)
        captured_w.sort(key=lambda p: self.PIECE_DISPLAY_VALUES.get(p, 0), reverse=True)
        captured_b.sort(key=lambda p: self.PIECE_DISPLAY_VALUES.get(p, 0), reverse=True)

        # Material advantage (positive = white ahead)
        w_material = sum(self.PIECE_DISPLAY_VALUES.get(p, 0) for p in captured_b)
        b_material = sum(self.PIECE_DISPLAY_VALUES.get(p, 0) for p in captured_w)
        advantage = w_material - b_material

        return captured_w, captured_b, advantage

    def _draw_captured_row(self, x: int, y: int, captured: list, color: str, advantage: int) -> int:
        """Draw a row of captured piece symbols to screen. Returns new y."""
        return self._draw_captured_row_to(self.screen, x, y, captured, color, advantage)

    def _draw_captured_row_to(self, target: pygame.Surface, x: int, y: int, captured: list, color: str, advantage: int) -> int:
        """Draw a row of captured piece symbols to a target surface. Returns new y."""
        if not captured:
            empty_text = self.log_font.render("None", True, self.PANEL_DIM)
            target.blit(empty_text, (x, y))
            return y + 18

        dx = x
        max_x = self.MOVE_LOG_WIDTH - 50
        for piece_type in captured:
            key = color + piece_type
            symbol = self.piece_symbols.get(key, '?')
            surf = self.small_piece_font.render(symbol, True, self.PANEL_TEXT)
            target.blit(surf, (dx, y - 4))
            dx += 20
            if dx > max_x:
                dx = x
                y += 22

        if advantage > 0:
            adv_text = self.material_font.render(f"+{advantage}", True, self.PANEL_ACCENT)
            target.blit(adv_text, (dx + 4, y + 2))

        return y + 22

    def _draw_promotion_dialog(self, mouse_pos: tuple) -> None:
        """Draw pawn promotion choice dialog."""
        if not self.promotion_pending:
            return

        color = self.promotion_pending.piece_moved[0]

        # Dim the board
        overlay = pygame.Surface((self.BOARD_WIDTH, self.BOARD_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        # Screen-space dialog centered on the board, so it reads the same in 2D and 3D
        # and never depends on which square the pawn reached.
        tile, gap, pad = self.SQUARE_SIZE, 10, 20
        n = len(self.promotion_pieces)
        panel = pygame.Rect(0, 0, n * tile + (n - 1) * gap + 2 * pad, tile + 96)
        panel.center = (self.BOARD_WIDTH // 2, self.BOARD_HEIGHT // 2)
        self.promotion_panel = panel
        pygame.draw.rect(self.screen, self.PANEL_BG, panel, border_radius=10)
        pygame.draw.rect(self.screen, self.WOOD_LIGHT, panel, 2, border_radius=10)

        title = self.title_font.render("Promote pawn to:", True, self.PANEL_TEXT)
        self.screen.blit(title, title.get_rect(centerx=panel.centerx, y=panel.y + 12))

        self.promotion_rects = []
        for i, letter in enumerate(self.promotion_pieces):
            rect = pygame.Rect(panel.x + pad + i * (tile + gap), panel.y + 48, tile, tile)
            self.promotion_rects.append(rect)

            hovered = rect.collidepoint(mouse_pos)
            pygame.draw.rect(self.screen, self.PROMO_HOVER if hovered else self.LIGHT_SQUARE,
                             rect, border_radius=6)
            pygame.draw.rect(self.screen, self.FOCUS_RING if hovered else self.WOOD_DARK,
                             rect, 2, border_radius=6)
            self.screen.blit(self._cached_piece_shadow, rect)
            self.screen.blit(self.piece_images[color + letter], rect)

            caption = self.log_font.render(f"[{letter}] {self.promotion_names[letter]}",
                                           True, self.PANEL_TEXT)
            self.screen.blit(caption, caption.get_rect(centerx=rect.centerx, y=rect.bottom + 6))

    def _draw_thinking_indicator(self) -> None:
        """Draw AI thinking indicator."""
        # Pulsing effect
        pulse = abs(math.sin(pygame.time.get_ticks() / 500.0))
        alpha = int(180 + 75 * pulse)
        alpha = min(255, alpha)

        text = self.status_font.render("AI is thinking...", True, pygame.Color(255, 255, 120))
        rect = text.get_rect(centerx=self.BOARD_WIDTH // 2, y=8)
        bg = rect.inflate(24, 12)
        bg_surf = pygame.Surface((bg.width, bg.height), pygame.SRCALPHA)
        bg_surf.fill((0, 0, 0, min(200, alpha)))
        pygame.draw.rect(bg_surf, (255, 255, 120, min(80, alpha)), bg_surf.get_rect(), 1, border_radius=6)
        self.screen.blit(bg_surf, bg)
        self.screen.blit(text, rect)

    def _draw_game_over_message(self) -> None:
        """Draw game over overlay."""
        overlay = pygame.Surface((self.BOARD_WIDTH, self.BOARD_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        icon = None
        if self.engine.checkmate:
            winner = "Black" if self.engine.white_to_move else "White"
            icon = "\u265A" if self.engine.white_to_move else "\u2654"
            text = f"{winner} wins by checkmate!"
        elif self.engine.draw_reason:
            text = f"Draw - {self.engine.draw_reason}"
        else:
            text = "Draw by stalemate"

        text_surface = self._render_icon_text(icon, text, self.over_font, self.MENU_TEXT)
        self.screen.blit(text_surface,
                         text_surface.get_rect(centerx=self.BOARD_WIDTH // 2,
                                               centery=self.BOARD_HEIGHT // 2 - 20))

        sub = self.status_font.render("R: new game   |   Z: undo   |   Esc: menu",
                                      True, self.MENU_LABEL)
        self.screen.blit(sub,
                         sub.get_rect(centerx=self.BOARD_WIDTH // 2,
                                      centery=self.BOARD_HEIGHT // 2 + 20))

    def _draw_confirm_dialog(self, mouse_pos: tuple) -> None:
        """Modal 'discard the current game?' prompt (Y/Enter = yes, N/Esc = no)."""
        overlay = pygame.Surface((self.BOARD_WIDTH, self.BOARD_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        panel = pygame.Rect(0, 0, 340, 170)
        panel.center = (self.BOARD_WIDTH // 2, self.BOARD_HEIGHT // 2)
        pygame.draw.rect(self.screen, self.PANEL_BG, panel, border_radius=10)
        pygame.draw.rect(self.screen, self.WOOD_LIGHT, panel, 2, border_radius=10)

        title = self.title_font.render("Start a new game?", True, self.PANEL_TEXT)
        self.screen.blit(title, title.get_rect(centerx=panel.centerx, y=panel.y + 22))
        note = self.status_font.render("The current game will be lost.", True, self.MENU_LABEL)
        self.screen.blit(note, note.get_rect(centerx=panel.centerx, y=panel.y + 58))

        for bid, label in (('confirm_yes', "Yes (Y)"), ('confirm_no', "No (N)")):
            rect = self.buttons[bid]
            self._draw_gradient_button(rect, label, self.button_font,
                                       rect.collidepoint(mouse_pos), radius=8,
                                       focused=(bid == 'confirm_no'))

    def _draw_menu(self, mouse_pos: tuple) -> None:
        """Draw the menu for the current menu state."""
        self._draw_board()
        self._draw_pieces()

        center_x = (self.BOARD_WIDTH + self.MOVE_LOG_WIDTH) // 2
        overlay = pygame.Surface((self.BOARD_WIDTH + self.MOVE_LOG_WIDTH, self.BOARD_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self.screen.blit(overlay, (0, 0))

        title = self._render_icon_text("\u2654", "CHESS", self.menu_title_font,
                                       self.MENU_TEXT, trail_icon="\u265A")
        self.screen.blit(title, title.get_rect(centerx=center_x, y=90))

        subtitle = self.status_font.render("Classic chess with a 2D / 3D board",
                                           True, self.MENU_SUBTLE)
        self.screen.blit(subtitle, subtitle.get_rect(centerx=center_x, y=150))

        labels = {
            'vs_ai': ("Play vs Computer", None),
            'vs_human': ("2 Players", None),
            'play_white': ("Play as White", "\u2654"),
            'play_black': ("Play as Black", "\u265A"),
            'difficulty_easy': ("Easy", None),
            'difficulty_medium': ("Medium", None),
            'difficulty_hard': ("Hard", None),
            'back': ("Back", None),
        }
        prompts = {'color_select': "Choose your color:", 'difficulty': "Select difficulty:"}
        if self.menu_state in prompts:
            label = self.title_font.render(prompts[self.menu_state], True, self.MENU_LABEL)
            self.screen.blit(label, label.get_rect(centerx=center_x, y=182))

        for i, bid in enumerate(self._menu_options()):
            text, icon = labels[bid]
            rect = self.buttons[bid]
            self._draw_gradient_button(rect, text, self.button_font,
                                       rect.collidepoint(mouse_pos), radius=8,
                                       focused=(i == self.menu_focus), icon=icon)

        hint_text = "Up/Down: select    Enter: confirm    Esc: back"
        if self.menu_state == 'main' and self.engine.move_log:
            hint_text = "Up/Down: select    Enter: confirm    Esc: resume game"
        hint = self.log_font.render(hint_text, True, self.MENU_SUBTLE)
        self.screen.blit(hint, hint.get_rect(centerx=center_x, y=self.BOARD_HEIGHT - 36))

    def _render_icon_text(self, icon, text: str, font: pygame.font.Font, color,
                          trail_icon=None) -> pygame.Surface:
        """Render text with optional chess-glyph icons drawn in a font that actually has them
        (the UI text fonts don't, and SDL_ttf has no per-glyph fallback)."""
        icon_font = _symbol_font(font.get_height() + 4)
        parts = []
        if icon:
            parts.append(icon_font.render(icon, True, color))
        if text:
            parts.append(font.render(text, True, color))
        if trail_icon:
            parts.append(icon_font.render(trail_icon, True, color))
        gap = 6
        width = sum(p.get_width() for p in parts) + gap * (len(parts) - 1)
        height = max(p.get_height() for p in parts)
        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        x = 0
        for part in parts:
            surf.blit(part, (x, (height - part.get_height()) // 2))
            x += part.get_width() + gap
        return surf

    def _draw_gradient_button(self, rect: pygame.Rect, text: str, font: pygame.font.Font,
                              hovered: bool, radius: int = 8, focused: bool = False,
                              icon=None, shadow: bool = True, gloss: bool = True) -> None:
        """Shared raised button used by the menu, dialogs and the view toggle.
        The gradient is kept shallow so white labels stay >= 4.5:1 across the whole fill."""
        base = self.BUTTON_HOVER if hovered else self.BUTTON_COLOR

        if shadow:
            shadow_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(shadow_surf, (0, 0, 0, 90), shadow_surf.get_rect(), border_radius=radius)
            self.screen.blit(shadow_surf, rect.move(0, 3))

        button_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        h = rect.height
        for y in range(h):
            t = y / max(1, h - 1)
            factor = 1.08 - 0.4 * t
            color = (max(0, min(255, int(base.r * factor))),
                     max(0, min(255, int(base.g * factor))),
                     max(0, min(255, int(base.b * factor))))
            pygame.draw.line(button_surf, color, (0, y), (rect.width, y))
        mask = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
        button_surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        self.screen.blit(button_surf, rect.topleft)

        if gloss:
            gloss_rect = pygame.Rect(rect.x + 4, rect.y + 3, rect.width - 8, rect.height // 3)
            gloss_surf = pygame.Surface(gloss_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(gloss_surf, (255, 255, 255, 22), gloss_surf.get_rect(), border_radius=6)
            self.screen.blit(gloss_surf, gloss_rect)

        pygame.draw.rect(self.screen, self.BUTTON_BORDER, rect, 2, border_radius=radius)
        if focused:
            pygame.draw.rect(self.screen, self.FOCUS_RING, rect.inflate(8, 8), 2,
                             border_radius=radius + 3)

        label = self._render_icon_text(icon, text, font, self.MENU_TEXT)
        self.screen.blit(label, label.get_rect(center=rect.center))


def main():
    game = ChessUI()
    game.run()


if __name__ == "__main__":
    main()
