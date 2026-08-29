"""The video spec: parsing, validation and defaults.

A spec is plain data (JSON, or YAML when PyYAML happens to be installed) so a
video is reproducible from a file you can diff and check in.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field, replace

AUTO = "auto"

MOTIONS = ("none", "zoom-in", "zoom-out", "pan-left", "pan-right",
           "pan-up", "pan-down", "random")
_RANDOMISABLE = tuple(m for m in MOTIONS if m not in ("none", "random"))

# xfade transition names, plus our own "none" for a hard cut.
TRANSITIONS = ("none", "fade", "fadeblack", "fadewhite", "wipeleft", "wiperight",
               "wipeup", "wipedown", "slideleft", "slideright", "slideup",
               "slidedown", "circleopen", "circleclose", "dissolve", "smoothleft",
               "smoothright", "pixelize", "radial", "hblur")

POSITIONS = ("bottom", "top", "center")

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif")
VIDEO_SUFFIXES = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")


class SpecError(ValueError):
    """A spec that cannot be turned into a video, with a pointer to where."""


def _check(condition: bool, where: str, message: str) -> None:
    if not condition:
        raise SpecError(f"{where}: {message}")


def _number(value: object, where: str, *, minimum: float | None = None) -> float:
    _check(isinstance(value, (int, float)) and not isinstance(value, bool),
           where, f"expected a number, got {value!r}")
    number = float(value)  # type: ignore[arg-type]
    if minimum is not None:
        _check(number >= minimum, where, f"must be >= {minimum}, got {number}")
    return number


def _one_of(value: object, allowed: tuple[str, ...], where: str) -> str:
    _check(isinstance(value, str) and value in allowed, where,
           f"expected one of {', '.join(allowed)}; got {value!r}")
    return str(value)


def _unknown_keys(data: dict, allowed: set[str], where: str) -> None:
    extra = sorted(set(data) - allowed)
    if extra:
        raise SpecError(
            f"{where}: unknown field(s) {', '.join(extra)}. "
            f"Valid fields: {', '.join(sorted(allowed))}"
        )


@dataclass(frozen=True)
class Transition:
    type: str = "fade"
    duration: float = 0.6

    @classmethod
    def parse(cls, data: object, where: str, default: "Transition") -> "Transition":
        if data is None:
            return default
        if isinstance(data, str):
            return replace(default, type=_one_of(data, TRANSITIONS, where))
        _check(isinstance(data, dict), where, "expected an object or a string")
        assert isinstance(data, dict)
        _unknown_keys(data, {"type", "duration"}, where)
        kind = _one_of(data.get("type", default.type), TRANSITIONS, f"{where}.type")
        seconds = _number(data.get("duration", default.duration),
                          f"{where}.duration", minimum=0)
        return cls(type=kind, duration=0.0 if kind == "none" else seconds)

    @property
    def active(self) -> bool:
        return self.type != "none" and self.duration > 0


@dataclass(frozen=True)
class Caption:
    text: str
    position: str = "bottom"
    size: int = 48
    color: str = "white"
    box: bool = True
    box_color: str = "black@0.5"
    margin: int = 80

    @classmethod
    def parse(cls, data: object, where: str, defaults: "Caption | None",
              *, require_text: bool = True) -> "Caption | None":
        """Parse a caption. At the top level `require_text` is False, because
        that block only carries styling for the captions on individual clips."""
        if data is None:
            return None
        base = defaults or cls(text="")
        if isinstance(data, str):
            return replace(base, text=data)
        _check(isinstance(data, dict), where, "expected an object or a string")
        assert isinstance(data, dict)
        _unknown_keys(data, {"text", "position", "size", "color", "box",
                             "box_color", "margin"}, where)
        text = data.get("text", base.text)
        _check(isinstance(text, str), f"{where}.text", "expected a string")
        if require_text:
            _check(str(text).strip() != "", f"{where}.text",
                   "caption text must be a non-empty string")
        return cls(
            text=str(text),
            position=_one_of(data.get("position", base.position), POSITIONS,
                             f"{where}.position"),
            size=int(_number(data.get("size", base.size), f"{where}.size", minimum=1)),
            color=str(data.get("color", base.color)),
            box=bool(data.get("box", base.box)),
            box_color=str(data.get("box_color", base.box_color)),
            margin=int(_number(data.get("margin", base.margin),
                               f"{where}.margin", minimum=0)),
        )


@dataclass(frozen=True)
class Music:
    path: str
    volume: float = 0.25
    fade_in: float = 1.5
    fade_out: float = 2.5
    loop: bool = True
    duck: bool = True
    start: float = 0.0

    @classmethod
    def parse(cls, data: object, where: str, base_dir: str) -> "Music | None":
        if data is None:
            return None
        if isinstance(data, str):
            data = {"path": data}
        _check(isinstance(data, dict), where, "expected an object or a path string")
        assert isinstance(data, dict)
        _unknown_keys(data, {"path", "volume", "fade_in", "fade_out", "loop",
                             "duck", "start"}, where)
        _check("path" in data, where, "missing required field 'path'")
        return cls(
            path=_resolve(data["path"], base_dir, f"{where}.path"),
            volume=_number(data.get("volume", 0.25), f"{where}.volume", minimum=0),
            fade_in=_number(data.get("fade_in", 1.5), f"{where}.fade_in", minimum=0),
            fade_out=_number(data.get("fade_out", 2.5), f"{where}.fade_out", minimum=0),
            loop=bool(data.get("loop", True)),
            duck=bool(data.get("duck", True)),
            start=_number(data.get("start", 0.0), f"{where}.start", minimum=0),
        )


@dataclass(frozen=True)
class Clip:
    path: str
    duration: float | str = 4.0
    motion: str = "random"
    zoom: float = 1.18
    caption: Caption | None = None
    narration: str | None = None
    start: float = 0.0
    transition: Transition | None = None
    volume: float = 1.0

    @classmethod
    def parse(cls, data: object, where: str, base_dir: str,
              defaults: "Defaults") -> "Clip":
        if isinstance(data, str):
            data = {"path": data}
        _check(isinstance(data, dict), where, "expected an object or a path string")
        assert isinstance(data, dict)
        _unknown_keys(data, {"path", "duration", "motion", "zoom", "caption",
                             "narration", "start", "transition", "volume"}, where)
        _check("path" in data, where, "missing required field 'path'")

        raw_duration = data.get("duration", defaults.duration)
        if isinstance(raw_duration, str):
            _check(raw_duration == AUTO, f"{where}.duration",
                   f"expected a number or {AUTO!r}, got {raw_duration!r}")
            duration: float | str = AUTO
        else:
            duration = _number(raw_duration, f"{where}.duration", minimum=0.05)

        narration = data.get("narration")
        if narration is not None:
            narration = _resolve(narration, base_dir, f"{where}.narration")

        return cls(
            path=_resolve(data["path"], base_dir, f"{where}.path"),
            duration=duration,
            motion=_one_of(data.get("motion", defaults.motion), MOTIONS,
                           f"{where}.motion"),
            zoom=_number(data.get("zoom", defaults.zoom), f"{where}.zoom", minimum=1.0),
            caption=Caption.parse(data.get("caption"), f"{where}.caption",
                                  defaults.caption),
            narration=narration,
            start=_number(data.get("start", 0.0), f"{where}.start", minimum=0),
            transition=Transition.parse(data.get("transition"),
                                        f"{where}.transition", defaults.transition)
            if "transition" in data else None,
            volume=_number(data.get("volume", 1.0), f"{where}.volume", minimum=0),
        )


@dataclass(frozen=True)
class Defaults:
    """Clip-level settings a spec can set once at the top level."""

    duration: float | str = 4.0
    motion: str = "random"
    zoom: float = 1.18
    transition: Transition = field(default_factory=Transition)
    caption: Caption | None = None


@dataclass(frozen=True)
class Spec:
    clips: list[Clip]
    width: int = 1920
    height: int = 1080
    fps: int = 30
    background: str = "black"
    font: str | None = None
    music: Music | None = None
    defaults: Defaults = field(default_factory=Defaults)
    seed: int | None = None

    @classmethod
    def parse(cls, data: object, base_dir: str = ".") -> "Spec":
        _check(isinstance(data, dict), "spec", "expected a top-level object")
        assert isinstance(data, dict)
        _unknown_keys(data, {"clips", "width", "height", "fps", "background",
                             "font", "music", "transition", "duration", "motion",
                             "zoom", "caption", "seed"}, "spec")
        _check("clips" in data, "spec", "missing required field 'clips'")
        _check(isinstance(data["clips"], list) and data["clips"],
               "spec.clips", "expected a non-empty list of clips")

        raw_default_duration = data.get("duration", 4.0)
        if isinstance(raw_default_duration, str):
            _check(raw_default_duration == AUTO, "spec.duration",
                   f"expected a number or {AUTO!r}, got {raw_default_duration!r}")
            default_duration: float | str = AUTO
        else:
            default_duration = _number(raw_default_duration, "spec.duration",
                                       minimum=0.05)

        defaults = Defaults(
            duration=default_duration,
            motion=_one_of(data.get("motion", "random"), MOTIONS, "spec.motion"),
            zoom=_number(data.get("zoom", 1.18), "spec.zoom", minimum=1.0),
            transition=Transition.parse(data.get("transition"), "spec.transition",
                                        Transition()),
            caption=Caption.parse(data.get("caption"), "spec.caption", None,
                                  require_text=False),
        )

        font = data.get("font")
        if font is not None:
            font = _resolve(font, base_dir, "spec.font")

        spec = cls(
            clips=[Clip.parse(clip, f"spec.clips[{i}]", base_dir, defaults)
                   for i, clip in enumerate(data["clips"])],
            width=int(_number(data.get("width", 1920), "spec.width", minimum=16)),
            height=int(_number(data.get("height", 1080), "spec.height", minimum=16)),
            fps=int(_number(data.get("fps", 30), "spec.fps", minimum=1)),
            background=str(data.get("background", "black")),
            font=font,
            music=Music.parse(data.get("music"), "spec.music", base_dir),
            defaults=defaults,
            seed=int(data["seed"]) if data.get("seed") is not None else None,
        )
        _check(spec.width % 2 == 0 and spec.height % 2 == 0, "spec",
               "width and height must both be even (H.264 requires it)")
        return spec

    def transition_after(self, index: int) -> Transition:
        """The transition between clip `index` and the one after it."""
        explicit = self.clips[index].transition
        return explicit if explicit is not None else self.defaults.transition

    def resolve_motion(self, clip: Clip, index: int) -> str:
        if clip.motion != "random":
            return clip.motion
        rng = random.Random((self.seed if self.seed is not None else 0) * 1000 + index)
        return rng.choice(_RANDOMISABLE)


def _resolve(value: object, base_dir: str, where: str) -> str:
    _check(isinstance(value, str) and value.strip() != "", where,
           f"expected a path string, got {value!r}")
    path = os.path.expanduser(str(value))
    if not os.path.isabs(path):
        path = os.path.join(base_dir, path)
    return os.path.normpath(path)


def load(path: str) -> Spec:
    """Read a spec from a .json or .yaml/.yml file."""
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    if path.lower().endswith((".yaml", ".yml")):
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise SpecError(
                f"{path} is YAML but PyYAML is not installed. "
                "Run `pip install pyyaml`, or use a .json spec instead."
            ) from exc
        data = yaml.safe_load(text)
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SpecError(f"{path} is not valid JSON: {exc}") from exc
    return Spec.parse(data, base_dir=os.path.dirname(os.path.abspath(path)))


def from_directory(directory: str, **overrides: object) -> Spec:
    """Build a spec from every image/video in a directory, sorted by name."""
    if not os.path.isdir(directory):
        raise SpecError(f"not a directory: {directory}")
    suffixes = IMAGE_SUFFIXES + VIDEO_SUFFIXES
    names = sorted(
        name for name in os.listdir(directory)
        if name.lower().endswith(suffixes) and not name.startswith(".")
    )
    if not names:
        raise SpecError(
            f"no images or videos in {directory} "
            f"(looked for {', '.join(suffixes)})"
        )
    data: dict[str, object] = {"clips": [{"path": name} for name in names]}
    data.update({key: value for key, value in overrides.items() if value is not None})
    return Spec.parse(data, base_dir=os.path.abspath(directory))
