"""Orchestration: spec in, encoded video file out."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

from . import graph
from .ffmpeg import FFmpegError, Tools, run
from .manifest import Spec
from .textfit import TextFitter
from .timeline import Timeline, resolve

PRESETS = {
    "fast": ("veryfast", "23"),
    "balanced": ("medium", "20"),
    "high": ("slow", "18"),
}


@dataclass
class Result:
    output: str
    duration: float
    clips: int
    warnings: list[str]


def render(spec: Spec, output: str, *, tools: Tools | None = None,
           quality: str = "balanced", supersample: int = graph.DEFAULT_SUPERSAMPLE,
           overwrite: bool = True, quiet: bool = False,
           dump_graph: str | None = None, dry_run: bool = False) -> Result:
    """Render `spec` to `output`. Returns what was produced, plus any warnings."""
    tools = tools or Tools.discover()
    if quality not in PRESETS:
        raise ValueError(
            f"unknown quality {quality!r}; choose from {', '.join(PRESETS)}"
        )
    if not overwrite and os.path.exists(output):
        raise FileExistsError(f"{output} already exists (pass --overwrite to replace)")

    timeline = resolve(spec, tools)
    workdir = tempfile.mkdtemp(prefix="videogen-")
    try:
        _render_backdrops(tools, spec, timeline, workdir)
        fitter = TextFitter(tools, graph.find_font(spec.font))
        command = graph.build(
            timeline, workdir, supersample=supersample, fitter=fitter,
            center_lines=tools.supports_drawtext_option("text_align"),
        )
        if dump_graph:
            with open(dump_graph, "w", encoding="utf-8") as handle:
                handle.write(command.filtergraph + "\n")

        graph_path = os.path.join(workdir, "filtergraph.txt")
        with open(graph_path, "w", encoding="utf-8") as handle:
            handle.write(command.filtergraph)

        args = _encode_args(spec, timeline, command, graph_path, output, quality)
        if dry_run:
            return Result(output=output, duration=timeline.total,
                          clips=len(timeline.clips), warnings=timeline.warnings)

        parent = os.path.dirname(os.path.abspath(output))
        os.makedirs(parent, exist_ok=True)
        run(tools, args, total_seconds=timeline.total, quiet=quiet)
    finally:
        # Caption sidecars live here and are only needed during the encode.
        shutil.rmtree(workdir, ignore_errors=True)

    return Result(output=output, duration=timeline.total,
                  clips=len(timeline.clips), warnings=timeline.warnings)


def _render_backdrops(tools: Tools, spec: Spec, timeline: Timeline,
                      workdir: str) -> None:
    """Draw each title card's backdrop to a PNG.

    `gradients` animates and cannot be stilled, so a single frame is captured
    up front. That also lets a title card reuse the ordinary still-image path.
    """
    for clip in timeline.clips:
        if not clip.is_title:
            continue
        background = clip.clip.background or spec.background
        path = os.path.join(workdir, f"backdrop_{clip.index}.png")
        source = _backdrop_source(background, spec.width, spec.height)
        result = subprocess.run(
            [tools.ffmpeg, "-hide_banner", "-v", "error", "-y",
             "-f", "lavfi", "-i", source, "-frames:v", "1", path],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            raise FFmpegError(
                f"could not draw the backdrop for clip {clip.index} "
                f"(background {background!r}):\n{result.stderr.strip()}"
            )
        clip.source_path = path


def _backdrop_source(background: str, width: int, height: int) -> str:
    """An lavfi source describing a solid colour or a linear gradient."""
    if not background.startswith(graph.GRADIENT_PREFIX):
        return f"color=c={background}:s={width}x{height}"

    colors = [part.strip() for part
              in background[len(graph.GRADIENT_PREFIX):].split(",")
              if part.strip()]
    if len(colors) < 2:
        raise ValueError(
            f"background {background!r}: a gradient needs at least two colours, "
            'e.g. "gradient:#0a2540,#1a4d7a"'
        )
    if len(colors) > 8:
        raise ValueError(
            f"background {background!r}: a gradient takes at most 8 colours"
        )
    stops = ":".join(f"c{i}={color}" for i, color in enumerate(colors))
    return (f"gradients=s={width}x{height}:{stops}:n={len(colors)}"
            f":x0=0:y0=0:x1={width}:y1={height}")


def _encode_args(spec: Spec, timeline: Timeline, command: graph.Command,
                 graph_path: str, output: str, quality: str) -> list[str]:
    preset, crf = PRESETS[quality]
    args = ["-y", *command.inputs,
            "-filter_complex_script", graph_path,
            "-map", f"[{command.video_label}]"]
    if command.audio_label:
        args += ["-map", f"[{command.audio_label}]",
                 "-c:a", "aac", "-b:a", "192k", "-ar", str(graph.SAMPLE_RATE)]
    args += [
        "-c:v", "libx264", "-preset", preset, "-crf", crf,
        "-pix_fmt", "yuv420p",
        "-r", str(spec.fps),
        # Keeps the file streamable and seekable in browsers.
        "-movflags", "+faststart",
        "-t", f"{timeline.total:.4f}",
        output,
    ]
    return args
