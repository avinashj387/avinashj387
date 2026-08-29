"""Building the ffmpeg command: input flags plus the filtergraph itself."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .manifest import Caption, Spec
from .timeline import ResolvedClip, Timeline, transition_duration

SAMPLE_RATE = 48000
AUDIO_FORMAT = (f"aformat=sample_fmts=fltp:sample_rates={SAMPLE_RATE}"
                ":channel_layouts=stereo")

# Ken Burns crops from an upscaled copy of the frame; without the headroom the
# integer crop offsets step visibly from frame to frame.
DEFAULT_SUPERSAMPLE = 2

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
)


@dataclass
class Command:
    inputs: list[str]
    filtergraph: str
    video_label: str
    audio_label: str | None
    total: float


def escape_path(path: str) -> str:
    """Escape a path for use inside a filtergraph option value."""
    return path.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def find_font(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    return next((path for path in _FONT_CANDIDATES if os.path.isfile(path)), None)


def build(timeline: Timeline, workdir: str, *,
          supersample: int = DEFAULT_SUPERSAMPLE,
          duck: bool = True) -> Command:
    spec = timeline.spec
    inputs = _input_args(timeline)
    chains: list[str] = []

    labels = [_video_chain(spec, clip, workdir, supersample, chains)
              for clip in timeline.clips]
    video_label = _stitch(spec, timeline, labels, chains)

    audio_label = _audio_chains(timeline, chains, duck=duck)

    return Command(inputs=inputs, filtergraph=";\n".join(chains),
                   video_label=video_label, audio_label=audio_label,
                   total=timeline.total)


# --------------------------------------------------------------------------
# inputs


def _input_args(timeline: Timeline) -> list[str]:
    args: list[str] = []
    for clip in timeline.clips:
        if clip.is_still:
            args += ["-loop", "1", "-framerate", str(timeline.spec.fps),
                     "-t", f"{clip.duration:.4f}", "-i", clip.clip.path]
        else:
            if clip.clip.start > 0:
                args += ["-ss", f"{clip.clip.start:.4f}"]
            args += ["-t", f"{clip.duration:.4f}", "-i", clip.clip.path]

    for clip in timeline.clips:
        if clip.narration_input_index is not None:
            assert clip.clip.narration is not None
            args += ["-i", clip.clip.narration]

    music = timeline.spec.music
    if music is not None:
        if music.loop:
            args += ["-stream_loop", "-1"]
        if music.start > 0:
            args += ["-ss", f"{music.start:.4f}"]
        args += ["-i", music.path]
    return args


# --------------------------------------------------------------------------
# video


def _video_chain(spec: Spec, clip: ResolvedClip, workdir: str,
                 supersample: int, chains: list[str]) -> str:
    width, height = spec.width, spec.height
    steps: list[str] = []

    if clip.is_still and clip.motion != "none":
        big_w, big_h = width * supersample, height * supersample
        steps += [_fit(big_w, big_h, spec.background), "setsar=1",
                  _zoompan(clip, spec, width, height)]
    else:
        steps += [_fit(width, height, spec.background), "setsar=1"]

    steps += [f"fps={spec.fps}", "format=pix_fmts=yuv420p",
              f"trim=duration={clip.duration:.4f}", "setpts=PTS-STARTPTS"]

    if clip.clip.caption is not None:
        steps.append(_drawtext(spec, clip.clip.caption, clip.index, workdir))

    # concat emits AVTB while fps emits 1/fps; xfade refuses to join links whose
    # timebases differ, so every clip is pinned to AVTB before stitching.
    steps.append("settb=AVTB")

    label = f"v{clip.index}"
    chains.append(f"[{clip.input_index}:v]" + ",".join(steps) + f"[{label}]")
    return label


def _fit(width: int, height: int, background: str) -> str:
    """Scale to fit inside the frame without distortion, then letterbox."""
    return (f"scale={width}:{height}:force_original_aspect_ratio=decrease:"
            f"flags=lanczos,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={background}")


def _zoompan(clip: ResolvedClip, spec: Spec, width: int, height: int) -> str:
    frames = max(2, round(clip.duration * spec.fps))
    # Linear progress across the clip, 0 -> 1, driven by the output frame index.
    progress = f"(on/{frames - 1})"
    zoom = clip.clip.zoom
    centre_x, centre_y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"

    if clip.motion == "zoom-in":
        expressions = (f"1+{zoom - 1:.6f}*{progress}", centre_x, centre_y)
    elif clip.motion == "zoom-out":
        expressions = (f"{zoom:.6f}-{zoom - 1:.6f}*{progress}", centre_x, centre_y)
    elif clip.motion == "pan-right":
        expressions = (f"{zoom:.6f}", f"(iw-iw/zoom)*{progress}", centre_y)
    elif clip.motion == "pan-left":
        expressions = (f"{zoom:.6f}", f"(iw-iw/zoom)*(1-{progress})", centre_y)
    elif clip.motion == "pan-down":
        expressions = (f"{zoom:.6f}", centre_x, f"(ih-ih/zoom)*{progress}")
    elif clip.motion == "pan-up":
        expressions = (f"{zoom:.6f}", centre_x, f"(ih-ih/zoom)*(1-{progress})")
    else:  # pragma: no cover - resolve_motion never yields anything else
        raise ValueError(f"unhandled motion {clip.motion!r}")

    z, x, y = expressions
    return (f"zoompan=z='{z}':x='{x}':y='{y}':d=1:"
            f"s={width}x{height}:fps={spec.fps}")


def _drawtext(spec: Spec, caption: Caption, index: int, workdir: str) -> str:
    # Captions go in a sidecar file so colons, quotes and commas in the text
    # never have to survive filtergraph escaping.
    text_path = os.path.join(workdir, f"caption_{index}.txt")
    with open(text_path, "w", encoding="utf-8") as handle:
        handle.write(caption.text)

    border = max(8, caption.size // 3)
    if caption.position == "top":
        y = f"{caption.margin}"
    elif caption.position == "center":
        y = "(h-text_h)/2"
    else:
        y = f"h-text_h-{caption.margin}"

    options = [
        f"textfile={escape_path(text_path)}",
        f"fontsize={caption.size}",
        f"fontcolor={caption.color}",
        "x=(w-text_w)/2",
        f"y={y}",
        "line_spacing=10",
    ]
    font = find_font(spec.font)
    if font:
        options.insert(0, f"fontfile={escape_path(font)}")
    else:
        options.insert(0, "font=sans")
    if caption.box:
        options += ["box=1", f"boxcolor={caption.box_color}",
                    f"boxborderw={border}"]
    return "drawtext=" + ":".join(options)


def _stitch(spec: Spec, timeline: Timeline, labels: list[str],
            chains: list[str]) -> str:
    merged = labels[0]
    for index in range(len(labels) - 1):
        nxt = labels[index + 1]
        seconds = transition_duration(spec, timeline.clips, index)
        out = f"m{index + 1}"
        if seconds > 0:
            kind = spec.transition_after(index).type
            offset = timeline.clips[index + 1].start
            chains.append(
                f"[{merged}][{nxt}]xfade=transition={kind}:"
                f"duration={seconds:.4f}:offset={offset:.4f}[{out}]"
            )
        else:
            chains.append(f"[{merged}][{nxt}]concat=n=2:v=1:a=0,settb=AVTB[{out}]")
        merged = out
    return merged


# --------------------------------------------------------------------------
# audio


def _audio_chains(timeline: Timeline, chains: list[str], *, duck: bool) -> str | None:
    spec = timeline.spec
    total = timeline.total
    voices: list[str] = []

    for clip in timeline.clips:
        source = None
        if clip.narration_input_index is not None:
            source = f"{clip.narration_input_index}:a"
        elif clip.has_own_audio:
            source = f"{clip.input_index}:a"
        if source is None:
            continue

        label = f"a{clip.index}"
        delay = max(0, int(round(clip.start * 1000)))
        steps = [
            AUDIO_FORMAT,
            f"atrim=duration={clip.duration:.4f}",
            "asetpts=PTS-STARTPTS",
        ]
        if clip.clip.volume != 1.0:
            steps.append(f"volume={clip.clip.volume:.4f}")
        if delay:
            steps.append(f"adelay={delay}:all=1")
        steps.append(f"apad=whole_dur={total:.4f}")
        chains.append(f"[{source}]" + ",".join(steps) + f"[{label}]")
        voices.append(label)

    voice_label = _merge(voices, "voices", total, chains)

    if spec.music is None:
        if voice_label is None:
            return None
        chains.append(f"[{voice_label}]atrim=duration={total:.4f},"
                      f"asetpts=PTS-STARTPTS[aout]")
        return "aout"

    music = spec.music
    steps = [AUDIO_FORMAT, f"volume={music.volume:.4f}",
             f"atrim=duration={total:.4f}", "asetpts=PTS-STARTPTS",
             f"apad=whole_dur={total:.4f}"]
    if music.fade_in > 0:
        steps.append(f"afade=t=in:st=0:d={music.fade_in:.4f}")
    if music.fade_out > 0:
        start = max(0.0, total - music.fade_out)
        steps.append(f"afade=t=out:st={start:.4f}:d={music.fade_out:.4f}")
    chains.append(f"[{timeline.music_input_index}:a]" + ",".join(steps) + "[music]")

    if voice_label is None:
        chains.append(f"[music]atrim=duration={total:.4f},asetpts=PTS-STARTPTS[aout]")
        return "aout"

    bed = "music"
    if duck and music.duck:
        # One copy of the voices keys the compressor, the other is heard.
        chains.append(f"[{voice_label}]asplit=2[voice_key][voice_out]")
        chains.append("[music][voice_key]sidechaincompress="
                      "threshold=0.03:ratio=6:attack=25:release=350[ducked]")
        bed, voice_label = "ducked", "voice_out"

    chains.append(f"[{bed}][{voice_label}]amix=inputs=2:duration=longest:"
                  f"normalize=0,atrim=duration={total:.4f},asetpts=PTS-STARTPTS[aout]")
    return "aout"


def _merge(labels: list[str], name: str, total: float,
           chains: list[str]) -> str | None:
    if not labels:
        return None
    if len(labels) == 1:
        return labels[0]
    joined = "".join(f"[{label}]" for label in labels)
    chains.append(f"{joined}amix=inputs={len(labels)}:duration=longest:"
                  f"normalize=0,apad=whole_dur={total:.4f}[{name}]")
    return name
