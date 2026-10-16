"""
Render the game's procedural window icon into assets/icon.ico for the packaged executable.

    python tools/make_icon.py

The icon is drawn by ChessUI itself, so the exe icon always matches the window icon. The .ico
holds PNG-compressed images, which Windows Vista and later read natively.
"""

from __future__ import annotations

import io
import os
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIZES = (16, 24, 32, 48, 64)


def build_ico(images) -> bytes:
    """Pack [(size, png_bytes), ...] into an ICO container."""
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    directory = b""
    payload = b""
    for size, png in images:
        directory += struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
        payload += png
    return header + directory + payload


def main() -> None:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    sys.path.insert(0, str(ROOT))
    import pygame
    import main as game

    ui = game.ChessUI()
    base = ui._create_app_icon()
    images = []
    for size in SIZES:
        surface = base if size == base.get_width() else pygame.transform.smoothscale(base, (size, size))
        buffer = io.BytesIO()
        pygame.image.save(surface, buffer, "icon.png")
        images.append((size, buffer.getvalue()))
    pygame.quit()

    target = ROOT / "assets" / "icon.ico"
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(build_ico(images))
    print(f"wrote {target} ({target.stat().st_size} bytes, sizes {SIZES})")


if __name__ == "__main__":
    main()
