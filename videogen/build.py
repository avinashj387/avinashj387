"""Orchestration: spec in, encoded video file out."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass

from . import graph
from .ffmpeg import Tools, run
from .manifest import Spec
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
        command = graph.build(timeline, workdir, supersample=supersample)
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
