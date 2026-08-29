"""Measuring drawn text, so a headline can be shrunk to fit the frame.

drawtext has no notion of fitting: an over-long headline simply runs off the
frame. Glyph widths vary far too much for a character count to stand in for a
measurement (in DejaVu Sans Bold, "WWWWW" is 3.5x the width of "iiiii"), so the
text is drawn once and measured. Width scales linearly with font size, which
makes one measurement enough to solve for the largest size that fits.
"""

from __future__ import annotations

import subprocess

from .ffmpeg import Tools

# Text is measured at this size and scaled; big enough to avoid rounding noise,
# small enough that the measuring canvas stays cheap.
REFERENCE_SIZE = 40
CANVAS_WIDTH = 12000
CANVAS_HEIGHT = 400

# Ink lighter than this is treated as background (antialiasing fringe).
INK_THRESHOLD = 0


class TextFitter:
    """Shrinks text to fit a width, measuring each string once."""

    def __init__(self, tools: Tools, font: str | None):
        self.tools = tools
        self.font = font
        self._widths: dict[str, int] = {}

    def fit(self, text: str, requested: int, usable_width: int) -> int:
        """The largest size <= `requested` whose text fits `usable_width`.

        Multi-line text is governed by its widest line, so each is measured
        separately; measuring the joined string would over-shrink it.
        """
        if usable_width <= 0 or not text.strip():
            return requested
        lines = [line for line in text.split("\n") if line.strip()]
        reference = max((self.width_at_reference(line) for line in lines),
                        default=0)
        if reference <= 0:
            return requested
        largest = int(usable_width * REFERENCE_SIZE / reference)
        return max(1, min(requested, largest))

    def width_at_reference(self, text: str) -> int:
        if text not in self._widths:
            self._widths[text] = self._measure(text)
        return self._widths[text]

    def _measure(self, text: str) -> int:
        """Ink width of a single line drawn at REFERENCE_SIZE, in pixels."""
        from .graph import escape_path

        font_option = (f"fontfile={escape_path(self.font)}" if self.font
                       else "font=sans")
        # Text is passed inline rather than via a file so measuring stays
        # self-contained; the escaping only has to survive this one command.
        drawtext = (f"drawtext={font_option}:text={_escape_text(text)}"
                    f":fontsize={REFERENCE_SIZE}:fontcolor=white:x=10:y=10")
        try:
            frame = subprocess.run(
                [self.tools.ffmpeg, "-v", "error", "-f", "lavfi",
                 "-i", f"color=c=black:s={CANVAS_WIDTH}x{CANVAS_HEIGHT}",
                 "-vf", drawtext, "-frames:v", "1",
                 "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                capture_output=True, check=True).stdout
        except (subprocess.CalledProcessError, OSError):
            # Measuring is an optimisation; a failure just means no shrinking.
            return 0
        return _ink_width(frame, CANVAS_WIDTH, CANVAS_HEIGHT)


def _ink_width(frame: bytes, width: int, height: int) -> int:
    """Width of the drawn pixels within a black grayscale frame."""
    if len(frame) < width * height:
        return 0
    blank = bytes([INK_THRESHOLD])
    first, last = width, -1
    for row_index in range(height):
        row = frame[row_index * width:(row_index + 1) * width]
        trimmed = row.rstrip(blank)
        if not trimmed:
            continue
        # rstrip/lstrip do the scan in C, which keeps this cheap on a wide frame.
        last = max(last, len(trimmed) - 1)
        first = min(first, width - len(row.lstrip(blank)))
    return 0 if last < 0 else last - first + 1


def _escape_text(text: str) -> str:
    """Quote text for a drawtext `text=` option on the command line."""
    escaped = (text.replace("\\", r"\\\\")
                   .replace("'", r"\'")
                   .replace(":", r"\:")
                   .replace("%", r"\%"))
    return escaped.replace("\n", " ")
