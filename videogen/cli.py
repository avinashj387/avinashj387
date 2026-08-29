"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import manifest
from .build import PRESETS, render
from .ffmpeg import FFmpegError, Tools
from .graph import DEFAULT_SUPERSAMPLE
from .manifest import MOTIONS, TRANSITIONS, SpecError

EPILOG = """\
examples:
  # every image in a folder, 4s each, crossfaded, with a music bed
  videogen from-dir ./photos --audio track.mp3 -o reel.mp4

  # vertical cut for phones, faster clips, hard cuts
  videogen from-dir ./photos -o story.mp4 --preset vertical \\
      --duration 2.5 --transition none

  # full control
  videogen render story.json -o story.mp4
"""

FRAME_PRESETS = {
    "1080p": (1920, 1080),
    "720p": (1280, 720),
    "4k": (3840, 2160),
    "vertical": (1080, 1920),
    "square": (1080, 1080),
}


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    try:
        return args.handler(args)
    except (SpecError, FFmpegError, FileExistsError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        print("\ninterrupted", file=sys.stderr)
        return 130


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="videogen",
        description="Assemble images, clips, captions and audio into a video "
                    "with ffmpeg.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    from_dir = subparsers.add_parser(
        "from-dir", help="build a slideshow from a folder of images/clips",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    from_dir.add_argument("directory", help="folder to read, sorted by filename")
    _add_shared(from_dir)
    from_dir.add_argument("--duration", type=float, default=4.0,
                          help="seconds per clip")
    from_dir.add_argument("--motion", choices=MOTIONS, default="random",
                          help="Ken Burns move applied to still images")
    from_dir.add_argument("--zoom", type=float, default=1.18,
                          help="how far the Ken Burns move travels (1.0 = still)")
    from_dir.add_argument("--transition", choices=TRANSITIONS, default="fade")
    from_dir.add_argument("--transition-duration", type=float, default=0.6,
                          metavar="SECONDS")
    from_dir.add_argument("--audio", metavar="FILE", help="background music track")
    from_dir.add_argument("--audio-volume", type=float, default=0.25,
                          metavar="GAIN", help="music gain, 1.0 = unchanged")
    from_dir.add_argument("--save-spec", metavar="FILE",
                          help="also write the generated spec here, to edit and "
                               "re-render with `videogen render`")
    from_dir.set_defaults(handler=_run_from_dir)

    render_cmd = subparsers.add_parser(
        "render", help="build from a .json/.yaml spec",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    render_cmd.add_argument("spec", help="path to the spec file")
    _add_shared(render_cmd)
    render_cmd.set_defaults(handler=_run_render)

    probe_cmd = subparsers.add_parser(
        "probe", help="print what videogen sees in a media file")
    probe_cmd.add_argument("files", nargs="+")
    probe_cmd.set_defaults(handler=_run_probe)

    return parser


def _add_shared(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-o", "--output", default="out.mp4", help="output file")
    parser.add_argument("--preset", choices=sorted(FRAME_PRESETS),
                        help="frame size shorthand")
    parser.add_argument("--width", type=int, help="overrides --preset")
    parser.add_argument("--height", type=int, help="overrides --preset")
    parser.add_argument("--fps", type=int, help="output frame rate")
    parser.add_argument("--quality", choices=sorted(PRESETS), default="balanced",
                        help="encoder speed/size trade-off")
    parser.add_argument("--supersample", type=int, default=DEFAULT_SUPERSAMPLE,
                        metavar="N",
                        help="Ken Burns oversampling; raise for smoother motion "
                             "at the cost of encode time")
    parser.add_argument("--font", help="TTF/OTF file used for captions")
    parser.add_argument("--seed", type=int,
                        help="makes 'random' motion reproducible")
    parser.add_argument("--no-overwrite", action="store_true",
                        help="fail instead of replacing an existing output")
    parser.add_argument("--dry-run", action="store_true",
                        help="resolve and validate, but do not encode")
    parser.add_argument("--dump-graph", metavar="FILE",
                        help="write the generated filtergraph here")
    parser.add_argument("-q", "--quiet", action="store_true")


def _frame_size(args: argparse.Namespace) -> tuple[int | None, int | None]:
    width = height = None
    if args.preset:
        width, height = FRAME_PRESETS[args.preset]
    if args.width:
        width = args.width
    if args.height:
        height = args.height
    return width, height


def _run_from_dir(args: argparse.Namespace) -> int:
    width, height = _frame_size(args)
    overrides: dict[str, object] = {
        "width": width, "height": height, "fps": args.fps,
        "duration": args.duration, "motion": args.motion, "zoom": args.zoom,
        "font": args.font, "seed": args.seed,
        "transition": {"type": args.transition,
                       "duration": args.transition_duration},
    }
    if args.audio:
        overrides["music"] = {"path": os.path.abspath(args.audio),
                              "volume": args.audio_volume}
    spec = manifest.from_directory(args.directory, **overrides)

    if args.save_spec:
        _write_spec(spec, args.save_spec)
        print(f"wrote spec  {args.save_spec}")
    return _render(spec, args)


def _run_render(args: argparse.Namespace) -> int:
    spec = manifest.load(args.spec)
    width, height = _frame_size(args)
    changes: dict[str, object] = {}
    if width:
        changes["width"] = width
    if height:
        changes["height"] = height
    if args.fps:
        changes["fps"] = args.fps
    if args.font:
        changes["font"] = os.path.abspath(args.font)
    if args.seed is not None:
        changes["seed"] = args.seed
    if changes:
        import dataclasses
        spec = dataclasses.replace(spec, **changes)  # type: ignore[arg-type]
    return _render(spec, args)


def _run_probe(args: argparse.Namespace) -> int:
    from .ffmpeg import probe
    tools = Tools.discover()
    for path in args.files:
        info = probe(tools, path)
        kind = "still image" if info.is_still else "video" if info.has_video else "audio"
        size = f"{info.width}x{info.height}" if info.width else "-"
        length = f"{info.duration:.2f}s" if info.duration else "-"
        audio = "yes" if info.has_audio else "no"
        print(f"{path}\n  type {kind}   size {size}   duration {length}   "
              f"audio {audio}")
    return 0


def _render(spec: manifest.Spec, args: argparse.Namespace) -> int:
    result = render(
        spec, args.output,
        quality=args.quality,
        supersample=args.supersample,
        overwrite=not args.no_overwrite,
        quiet=args.quiet,
        dump_graph=args.dump_graph,
        dry_run=args.dry_run,
    )
    for note in result.warnings:
        print(f"note: {note}", file=sys.stderr)
    verb = "would render" if args.dry_run else "rendered"
    if not args.quiet:
        print(f"{verb}  {result.output}  "
              f"({result.clips} clips, {result.duration:.1f}s, "
              f"{spec.width}x{spec.height} @ {spec.fps}fps)")
    return 0


def _write_spec(spec: manifest.Spec, path: str) -> None:
    """Dump the generated spec so it can be hand-edited and re-rendered.

    Paths are written relative to the spec file, because that is what
    `videogen render` resolves them against.
    """
    base = os.path.dirname(os.path.abspath(path))
    data: dict[str, object] = {
        "width": spec.width, "height": spec.height, "fps": spec.fps,
        "background": spec.background,
        "duration": spec.defaults.duration,
        "motion": spec.defaults.motion,
        "zoom": spec.defaults.zoom,
        "transition": {"type": spec.defaults.transition.type,
                       "duration": spec.defaults.transition.duration},
        "clips": [{"path": _relative(clip.path, base)} for clip in spec.clips],
    }
    if spec.seed is not None:
        data["seed"] = spec.seed
    if spec.font:
        data["font"] = spec.font
    if spec.music:
        data["music"] = {"path": _relative(spec.music.path, base),
                         "volume": spec.music.volume}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def _relative(target: str, base: str) -> str:
    """Path from `base` to `target`, falling back to absolute across drives."""
    try:
        return os.path.relpath(target, base).replace(os.sep, "/")
    except ValueError:  # pragma: no cover - Windows, different drives
        return target
