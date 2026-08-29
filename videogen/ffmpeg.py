"""Locating, probing and running the ffmpeg binaries."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass


class FFmpegError(RuntimeError):
    """Raised when ffmpeg/ffprobe is missing, or exits non-zero."""


def _find(name: str, override: str | None) -> str:
    if override:
        if os.path.isfile(override) and os.access(override, os.X_OK):
            return override
        raise FFmpegError(f"{name} not executable at {override!r}")
    found = shutil.which(name)
    if not found:
        raise FFmpegError(
            f"{name} not found on PATH. Install it first:\n"
            "  macOS    brew install ffmpeg\n"
            "  Debian   sudo apt install ffmpeg\n"
            "  Windows  winget install Gyan.FFmpeg"
        )
    return found


@dataclass(frozen=True)
class Tools:
    ffmpeg: str
    ffprobe: str

    @classmethod
    def discover(cls, ffmpeg: str | None = None, ffprobe: str | None = None) -> "Tools":
        return cls(_find("ffmpeg", ffmpeg), _find("ffprobe", ffprobe))

    def has_filter(self, name: str) -> bool:
        out = subprocess.run(
            [self.ffmpeg, "-hide_banner", "-filters"],
            capture_output=True, text=True, check=False,
        ).stdout
        return re.search(rf"^ [TSC.]+ +{re.escape(name)} ", out, re.M) is not None


@dataclass(frozen=True)
class MediaInfo:
    """The handful of stream properties the builder actually needs."""

    path: str
    has_video: bool
    has_audio: bool
    width: int | None
    height: int | None
    duration: float | None

    @property
    def is_still(self) -> bool:
        """True for a single-frame input (jpg/png/webp), false for a movie."""
        return self.has_video and not self.has_audio and self.duration is None


def probe(tools: Tools, path: str) -> MediaInfo:
    if not os.path.isfile(path):
        raise FFmpegError(f"input file not found: {path}")
    proc = subprocess.run(
        [tools.ffprobe, "-v", "error", "-print_format", "json",
         "-show_streams", "-show_format", path],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        raise FFmpegError(f"ffprobe failed on {path}:\n{proc.stderr.strip()}")
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams", [])

    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration: float | None = None
    for raw in (data.get("format", {}).get("duration"),
                (video or {}).get("duration"),
                (audio or {}).get("duration")):
        try:
            value = float(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if value > 0:
            duration = value
            break

    # Still images report a duration on some builds; a single-frame count is
    # the reliable tell.
    if video is not None and audio is None:
        frames = video.get("nb_frames")
        if frames in ("1", 1) or video.get("codec_name") in {
            "mjpeg", "png", "webp", "bmp", "gif", "tiff",
        } and frames in (None, "N/A", "1", 1):
            duration = None

    return MediaInfo(
        path=path,
        has_video=video is not None,
        has_audio=audio is not None,
        width=int(video["width"]) if video and video.get("width") else None,
        height=int(video["height"]) if video and video.get("height") else None,
        duration=duration,
    )


def run(tools: Tools, args: list[str], *, total_seconds: float | None = None,
        quiet: bool = False) -> None:
    """Run ffmpeg, streaming a one-line progress readout to stderr."""
    cmd = [tools.ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error",
           "-progress", "pipe:1", "-stats_period", "0.5", *args]
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
    )
    assert proc.stdout is not None
    interactive = sys.stderr.isatty()
    for line in proc.stdout:
        if quiet or not line.startswith("out_time_ms="):
            continue
        try:
            done = int(line.split("=", 1)[1]) / 1_000_000
        except ValueError:
            continue
        if total_seconds:
            pct = min(100.0, done / total_seconds * 100)
            msg = f"  encoding {pct:5.1f}%  ({done:.1f}s / {total_seconds:.1f}s)"
        else:
            msg = f"  encoding {done:.1f}s"
        end = "\r" if interactive else "\n"
        print(msg, end=end, file=sys.stderr, flush=True)
    stderr = proc.stderr.read() if proc.stderr else ""
    proc.wait()
    if not quiet and interactive:
        print(file=sys.stderr)
    if proc.returncode != 0:
        raise FFmpegError(
            f"ffmpeg exited {proc.returncode}\n"
            f"{stderr.strip()}\n\ncommand: {' '.join(cmd)}"
        )
