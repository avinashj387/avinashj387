"""Flat vector icons drawn with Pillow primitives, echoing the poster's set."""

from __future__ import annotations

from PIL import Image, ImageDraw

Tile = Image.Image


def _tile(size: int) -> tuple[Tile, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _s(size: int, *values: float) -> tuple:
    """Scale unit-square coordinates (0..100) to the tile."""
    return tuple(v * size / 100.0 for v in values)


def calendar(size: int, color) -> Tile:
    img, d = _tile(size)
    d.rounded_rectangle(_s(size, 10, 20, 90, 90), radius=size * 0.08,
                        outline=color, width=max(2, size // 18))
    d.line(_s(size, 10, 40, 90, 40), fill=color, width=max(2, size // 18))
    d.line(_s(size, 30, 8, 30, 28), fill=color, width=max(2, size // 16))
    d.line(_s(size, 70, 8, 70, 28), fill=color, width=max(2, size // 16))
    for row in (55, 74):
        for col in (26, 48, 70):
            d.ellipse(_s(size, col - 5, row - 5, col + 5, row + 5), fill=color)
    return img


def pin(size: int, color) -> Tile:
    img, d = _tile(size)
    d.pieslice(_s(size, 18, 8, 82, 72), start=180, end=360, fill=color)
    d.polygon(_s(size, 18, 40, 82, 40, 50, 94), fill=color)
    hole = size * 0.11
    cx, cy = size * 0.5, size * 0.42
    d.ellipse((cx - hole, cy - hole, cx + hole, cy + hole), fill=(0, 0, 0, 0))
    return img


def people(size: int, color) -> Tile:
    img, d = _tile(size)
    d.ellipse(_s(size, 36, 12, 64, 40), fill=color)
    d.pieslice(_s(size, 24, 44, 76, 96), start=180, end=360, fill=color)
    d.ellipse(_s(size, 8, 26, 30, 48), fill=color)
    d.pieslice(_s(size, 0, 52, 34, 92), start=180, end=360, fill=color)
    d.ellipse(_s(size, 70, 26, 92, 48), fill=color)
    d.pieslice(_s(size, 66, 52, 100, 92), start=180, end=360, fill=color)
    return img


def factory(size: int, color) -> Tile:
    img, d = _tile(size)
    d.rectangle(_s(size, 68, 12, 80, 46), fill=color)          # chimney
    d.polygon(_s(size, 6, 88, 6, 56, 30, 70, 30, 56, 54, 70, 54, 44, 94, 44, 94, 88),
              fill=color)                                       # saw-tooth shed
    for x in (14, 38, 62, 78):                                  # windows
        d.rectangle(_s(size, x, 70, x + 8, 80), fill=(0, 0, 0, 0))
    return img


def building(size: int, color) -> Tile:
    img, d = _tile(size)
    d.rounded_rectangle(_s(size, 14, 16, 60, 90), radius=size * 0.04, fill=color)
    d.rounded_rectangle(_s(size, 62, 44, 90, 90), radius=size * 0.04, fill=color)
    for row in (26, 44, 62):
        for col in (22, 40):
            d.rectangle(_s(size, col, row, col + 10, row + 10), fill=(0, 0, 0, 0))
    d.rectangle(_s(size, 70, 56, 82, 68), fill=(0, 0, 0, 0))
    return img


def tools(size: int, color) -> Tile:
    img, d = _tile(size)
    width = max(3, size // 12)
    d.line(_s(size, 20, 84, 66, 34), fill=color, width=width)
    d.ellipse(_s(size, 58, 14, 88, 44), outline=color, width=width)
    d.line(_s(size, 78, 84, 34, 36), fill=color, width=width)
    d.ellipse(_s(size, 12, 14, 42, 44), outline=color, width=width)
    return img


def shield(size: int, color) -> Tile:
    img, d = _tile(size)
    d.polygon(_s(size, 50, 8, 88, 24, 88, 52, 50, 92, 12, 52, 12, 24), fill=color)
    d.line(_s(size, 32, 50, 45, 64, 70, 34), fill=(0, 0, 0, 0),
           width=max(3, size // 11), joint="curve")
    return img


def broom(size: int, color) -> Tile:
    img, d = _tile(size)
    width = max(3, size // 14)
    d.line(_s(size, 70, 10, 44, 50), fill=color, width=width)
    d.polygon(_s(size, 26, 48, 62, 48, 74, 90, 14, 90), fill=color)
    for x in (30, 44, 58):
        d.line(_s(size, x, 62, x - 4, 90), fill=(0, 0, 0, 0), width=max(2, size // 24))
    return img


def growth(size: int, color) -> Tile:
    img, d = _tile(size)
    for i, (x, top) in enumerate(((14, 62), (38, 46), (62, 30), (86, 14))):
        d.rounded_rectangle(_s(size, x - 9, top, x + 9, 90), radius=size * 0.03,
                            fill=color)
    d.polygon(_s(size, 74, 6, 96, 6, 96, 28), fill=color)
    return img


def handshake(size: int, color) -> Tile:
    """Partnership: two interlocking rings."""
    img, d = _tile(size)
    width = max(4, size // 11)
    d.ellipse(_s(size, 4, 26, 60, 82), outline=color, width=width)
    d.ellipse(_s(size, 40, 26, 96, 82), outline=color, width=width)
    return img


def check(size: int, color) -> Tile:
    img, d = _tile(size)
    d.ellipse(_s(size, 2, 2, 98, 98), fill=color)
    return img


def check_mark(size: int, color) -> Tile:
    img, d = _tile(size)
    d.line(_s(size, 22, 52, 42, 72, 78, 28), fill=color,
           width=max(3, size // 9), joint="curve")
    return img


def phone(size: int, color) -> Tile:
    img, d = _tile(size)
    d.rounded_rectangle(_s(size, 18, 6, 82, 94), radius=size * 0.16, fill=color)
    d.rounded_rectangle(_s(size, 28, 20, 72, 76), radius=size * 0.05, fill=(0, 0, 0, 0))
    return img


def mail(size: int, color) -> Tile:
    img, d = _tile(size)
    width = max(3, size // 16)
    d.rounded_rectangle(_s(size, 8, 22, 92, 78), radius=size * 0.06,
                        outline=color, width=width)
    d.line(_s(size, 12, 27, 50, 55, 88, 27), fill=color, width=width, joint="curve")
    return img


def globe(size: int, color) -> Tile:
    img, d = _tile(size)
    width = max(3, size // 18)
    d.ellipse(_s(size, 6, 6, 94, 94), outline=color, width=width)
    d.ellipse(_s(size, 32, 6, 68, 94), outline=color, width=width)
    d.line(_s(size, 8, 38, 92, 38), fill=color, width=width)
    d.line(_s(size, 8, 62, 92, 62), fill=color, width=width)
    return img


def spark(size: int, color) -> Tile:
    img, d = _tile(size)
    d.polygon(_s(size, 50, 4, 60, 40, 96, 50, 60, 60, 50, 96, 40, 60, 4, 50, 40, 40),
              fill=color)
    return img


def briefcase(size: int, color) -> Tile:
    img, d = _tile(size)
    width = max(3, size // 16)
    d.rounded_rectangle(_s(size, 8, 30, 92, 88), radius=size * 0.07,
                        outline=color, width=width)
    d.rounded_rectangle(_s(size, 34, 12, 66, 32), radius=size * 0.05,
                        outline=color, width=width)
    d.line(_s(size, 8, 56, 92, 56), fill=color, width=width)
    return img


def paste(canvas: Image.Image, tile: Tile, center: tuple[int, int]) -> None:
    canvas.alpha_composite(tile, (center[0] - tile.width // 2,
                                  center[1] - tile.height // 2))
