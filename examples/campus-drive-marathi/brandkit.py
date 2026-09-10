"""Drawing primitives for the Eagle Hi-tech campus-drive reel.

Every frame is composed here, in Pillow, and handed to videogen as a finished
1080x1920 still. Marathi is shaped by Pillow's Raqm/HarfBuzz backend, so
conjuncts and matras come out correct - ffmpeg's drawtext cannot shape
Devanagari and would render it as reordered glyphs.
"""

from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920

# Palette sampled from the poster.
NAVY_DEEP = (5, 24, 60)
NAVY = (13, 45, 99)
NAVY_MID = (18, 60, 128)
NAVY_SOFT = (26, 80, 160)
GOLD = (255, 194, 14)
GOLD_LIGHT = (255, 216, 77)
CRIMSON = (168, 30, 34)
WHITE = (255, 255, 255)
ICE = (222, 233, 248)
STEEL = (146, 170, 204)

DEVA_BOLD = "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"
DEVA_REG = "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"
LAT_BOLD = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
LAT_REG = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"

# Devanagari shaping features: half-forms, reph, conjuncts, pre/post matras.
DEVA_FEATURES = ["liga", "clig", "calt", "akhn", "rphf", "rkrf", "blwf",
                 "half", "vatu", "pres", "abvs", "psts", "haln", "nukt"]

_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    key = (path, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(path, size)
    return _FONT_CACHE[key]


# --------------------------------------------------------------------------
# text
#
# Noto Sans Devanagari carries no Latin letters (and no U+00B7), so a string
# like "PF, ESIC इत्यादी" drawn in one font renders the Latin half as .notdef
# boxes. Every string is therefore split into script runs and each run drawn
# in the font that actually covers it, on one shared baseline.

_DEVA = set(range(0x0900, 0x0980)) | {0x200C, 0x200D}
_NEUTRAL = set(map(ord, " 0123456789,.()+-–—:/@!?%&'\u0964"))


def _partner(path: str) -> str:
    """The font covering the script `path` does not."""
    bold = "Bold" in path
    if "Devanagari" in path:
        return LAT_BOLD if bold else LAT_REG
    return DEVA_BOLD if bold else DEVA_REG


def _runs(body: str, path: str) -> list[tuple[str, str]]:
    """Split `body` into (text, font_path) runs. Neutrals stay with their
    neighbours so digits and punctuation never start a run of their own."""
    deva_primary = "Devanagari" in path
    other = _partner(path)
    out: list[list] = []
    for ch in body:
        if ord(ch) in _NEUTRAL:
            want = out[-1][1] if out else path
        elif ord(ch) in _DEVA:
            want = path if deva_primary else other
        else:
            want = other if deva_primary else path
        if out and out[-1][1] == want:
            out[-1][0] += ch
        else:
            out.append([ch, want])
    return [(text, face) for text, face in out] or [(body, path)]


def _draw_run(draw, xy, body, face, size, fill, anchor):
    draw.text(xy, body, font=font(face, size), fill=fill, anchor=anchor,
              features=DEVA_FEATURES, language="mr")


def measure(text: str, path: str, size: int) -> tuple[int, int]:
    probe = Image.new("RGB", (8, 8))
    drawer = ImageDraw.Draw(probe)
    width, height = 0, 0
    for body, face in _runs(text, path):
        box = drawer.textbbox((0, 0), body, font=font(face, size),
                              features=DEVA_FEATURES, language="mr")
        width += drawer.textlength(body, font=font(face, size),
                                   features=DEVA_FEATURES, language="mr")
        height = max(height, box[3] - box[1])
    return int(round(width)), height


def fit(text: str, path: str, size: int, max_width: int, min_size: int = 18) -> int:
    """Largest size <= `size` whose rendering fits `max_width`."""
    width, _ = measure(text, path, size)
    if width <= max_width:
        return size
    scaled = max(min_size, int(size * max_width / max(width, 1)))
    while scaled > min_size and measure(text, path, scaled)[0] > max_width:
        scaled -= 1
    return scaled


def _place(img: Image.Image, xy, body, path, size, fill, anchor):
    """Draw runs left to right on a shared baseline, honouring l/m/r anchors."""
    runs = _runs(body, path)
    draw = ImageDraw.Draw(img)
    if len(runs) == 1:
        _draw_run(draw, xy, body, runs[0][1], size, fill, anchor)
        return
    total = measure(body, path, size)[0]
    horizontal = anchor[0]
    x = xy[0] - total // 2 if horizontal == "m" else (
        xy[0] - total if horizontal == "r" else xy[0])
    ascent = font(path, size).getmetrics()[0]
    baseline = xy[1] + ascent if anchor[1] == "a" else xy[1]
    for run_body, face in runs:
        _draw_run(draw, (x, baseline), run_body, face, size, fill, "ls")
        x += draw.textlength(run_body, font=font(face, size),
                             features=DEVA_FEATURES, language="mr")


def text(img: Image.Image, xy: tuple[int, int], body: str, path: str, size: int,
         fill=WHITE, anchor: str = "la", spacing: int = 0, shadow: int = 0,
         glow: tuple | None = None) -> None:
    """Draw one line, optionally with a soft drop shadow or a coloured glow."""
    if glow is not None:
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        _place(layer, xy, body, path, size, glow + (170,), anchor)
        img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(18)))
    if shadow:
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        _place(layer, (xy[0], xy[1] + shadow), body, path, size,
               (0, 0, 0, 130), anchor)
        img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(shadow)))
    _place(img, xy, body, path, size, fill, anchor)


def tracked(img: Image.Image, xy: tuple[int, int], body: str, path: str, size: int,
            fill=WHITE, tracking: int = 8, center: bool = False) -> None:
    """Letter-spaced caps for Latin labels.

    Devanagari is never letter-spaced: pulling a cluster apart separates a
    matra from the consonant it belongs to, so such a string is drawn whole.
    """
    if any(ord(ch) in _DEVA for ch in body):
        text(img, xy, body, path, size, fill=fill, anchor="ma" if center else "la")
        return
    glyphs = list(body)
    widths = [measure(g, path, size)[0] if g != " " else size // 3 for g in glyphs]
    total = sum(widths) + tracking * (len(glyphs) - 1)
    x = xy[0] - total // 2 if center else xy[0]
    draw = ImageDraw.Draw(img)
    for glyph, width in zip(glyphs, widths):
        _draw_run(draw, (x, xy[1]), glyph, _runs(glyph, path)[0][1], size, fill, "la")
        x += width + tracking


def wrap(body: str, path: str, size: int, max_width: int) -> list[str]:
    lines, current = [], ""
    for word in body.split():
        trial = f"{current} {word}".strip()
        if measure(trial, path, size)[0] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def paragraph(img: Image.Image, xy: tuple[int, int], body: str, path: str, size: int,
              max_width: int, fill=ICE, leading: float = 1.45,
              center: bool = True) -> int:
    lines = wrap(body, path, size, max_width)
    step = int(size * leading)
    y = xy[1]
    for line in lines:
        text(img, (xy[0], y), line, path, size, fill=fill,
             anchor="ma" if center else "la")
        y += step
    return y


# --------------------------------------------------------------------------
# backgrounds


def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def gradient(colors: list[tuple], angle: float = 115.0) -> Image.Image:
    """Linear gradient across `angle` degrees, drawn small and scaled up."""
    small = Image.new("RGB", (180, 320))
    pixels = small.load()
    rad = math.radians(angle)
    dx, dy = math.cos(rad), math.sin(rad)
    span = abs(dx) * small.width + abs(dy) * small.height
    ox = 0 if dx >= 0 else small.width
    oy = 0 if dy >= 0 else small.height
    stops = len(colors) - 1
    for y in range(small.height):
        for x in range(small.width):
            t = (abs(x - ox) * abs(dx) + abs(y - oy) * abs(dy)) / span
            t = min(max(t, 0.0), 0.999999)
            seg = min(int(t * stops), stops - 1)
            pixels[x, y] = _lerp(colors[seg], colors[seg + 1], t * stops - seg)
    return small.resize((W, H), Image.LANCZOS).convert("RGBA")


def dot_grid(img: Image.Image, step: int = 48, radius: int = 2,
             alpha: int = 26) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for y in range(0, H + step, step):
        for x in range(0, W + step, step):
            draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                         fill=WHITE + (alpha,))
    img.alpha_composite(layer)


def glow_blob(img: Image.Image, center: tuple[int, int], radius: int,
              color=NAVY_SOFT, alpha: int = 150) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(
        (center[0] - radius, center[1] - radius,
         center[0] + radius, center[1] + radius), fill=color + (alpha,))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius // 2)))


def vignette(img: Image.Image, strength: int = 120) -> None:
    mask = Image.new("L", (W // 4, H // 4), 0)
    ImageDraw.Draw(mask).ellipse((-W // 8, -H // 12, W // 4 + W // 8, H // 4 + H // 12),
                                 fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(60)).resize((W, H), Image.LANCZOS)
    shade = Image.new("RGBA", (W, H), (0, 0, 0, strength))
    shade.putalpha(Image.eval(mask, lambda v: int((255 - v) * strength / 255)))
    img.alpha_composite(shade)


def diagonal_ribbon(img: Image.Image, y: int, height: int, color, alpha: int = 255,
                    slant: int = 90, x0: int = -60, x1: int = W + 60) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).polygon(
        [(x0, y), (x1, y - slant), (x1, y - slant + height), (x0, y + height)],
        fill=tuple(color) + (alpha,))
    img.alpha_composite(layer)


def chevron(img: Image.Image, x: int, y: int, size: int, color=GOLD,
            thickness: int = 14, alpha: int = 255) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).line(
        [(x, y - size), (x + size, y), (x, y + size)],
        fill=tuple(color) + (alpha,), width=thickness, joint="curve")
    img.alpha_composite(layer)


def rule(img: Image.Image, x: int, y: int, width: int, height: int = 8,
         color=GOLD, center: bool = False) -> None:
    left = x - width // 2 if center else x
    ImageDraw.Draw(img).rounded_rectangle(
        (left, y, left + width, y + height), radius=height // 2, fill=tuple(color))


def card(img: Image.Image, box: tuple[int, int, int, int], fill=(255, 255, 255, 20),
         radius: int = 34, outline=(255, 255, 255, 46), width: int = 2) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius=radius, fill=fill,
                                            outline=outline, width=width)
    img.alpha_composite(layer)


# --------------------------------------------------------------------------
# frame furniture


def base(kind: str = "navy") -> Image.Image:
    if kind == "navy":
        img = gradient([NAVY_DEEP, NAVY, NAVY_MID], 118)
        glow_blob(img, (860, 380), 520, NAVY_SOFT, 120)
        glow_blob(img, (140, 1560), 460, (12, 52, 112), 130)
    elif kind == "deep":
        img = gradient([(3, 16, 42), NAVY_DEEP, (10, 38, 84)], 100)
        glow_blob(img, (540, 900), 640, NAVY_SOFT, 90)
    elif kind == "gold":
        img = gradient([(255, 176, 8), GOLD, GOLD_LIGHT], 120)
        glow_blob(img, (760, 520), 520, (255, 232, 150), 110)
    else:  # light
        img = gradient([(242, 246, 252), ICE, (206, 222, 244)], 120)
    dot_grid(img, alpha=22 if kind in ("navy", "deep") else 34)
    return img


def header(img: Image.Image, right: str = "", on_gold: bool = False) -> None:
    ink = NAVY_DEEP if on_gold else WHITE
    accent = NAVY_DEEP if on_gold else GOLD
    rule(img, 86, 108, 84, 8, accent)
    tracked(img, (86, 138), "EAGLE HI-TECH", LAT_BOLD, 30, ink, tracking=6)
    if right:
        size = fit(right, DEVA_BOLD, 30, 420)
        text(img, (W - 86, 136), right, DEVA_BOLD, size,
             fill=accent, anchor="ra")


def footer(img: Image.Image, note: str = "8 – 9 सप्टेंबर 2026  ·  एकलहरे, नाशिक",
           on_gold: bool = False) -> None:
    ink = NAVY_DEEP if on_gold else STEEL
    line = (NAVY_DEEP + (70,)) if on_gold else (255, 255, 255, 40)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).line([(86, H - 150), (W - 86, H - 150)], fill=line, width=2)
    img.alpha_composite(layer)
    size = fit(note, DEVA_REG, 32, W - 172)
    text(img, (W // 2, H - 128), note, DEVA_REG, size, fill=ink, anchor="ma")


def finish(img: Image.Image, path: str) -> str:
    vignette(img, 110)
    img.convert("RGB").save(path, quality=96)
    return path
