"""Turning a spec into concrete durations, offsets and input indices."""

from __future__ import annotations

from dataclasses import dataclass, field

from .ffmpeg import MediaInfo, Tools, probe
from .manifest import AUTO, Clip, Spec, SpecError

# Silence after a voiceover ends, when a clip's duration follows its narration.
NARRATION_TAIL = 0.5
FALLBACK_DURATION = 4.0


# A title card's backdrop is generated at render time, so it is described
# rather than probed.
TITLE_INFO = MediaInfo("<title>", has_video=True, has_audio=False,
                       width=None, height=None, duration=None)


@dataclass
class ResolvedClip:
    index: int
    clip: Clip
    info: MediaInfo
    duration: float
    motion: str
    start: float = 0.0
    input_index: int = -1
    # The file ffmpeg actually reads. For a title card this is filled in with
    # the generated backdrop once it has been rendered.
    source_path: str = ""
    narration_info: MediaInfo | None = None
    narration_input_index: int | None = None
    # Crossfade to the following clip, after clamping. None until laid out.
    transition_out: float | None = None

    @property
    def is_title(self) -> bool:
        return self.clip.title is not None

    @property
    def is_still(self) -> bool:
        return self.info.is_still

    @property
    def has_own_audio(self) -> bool:
        return self.info.has_audio

    @property
    def end(self) -> float:
        return self.start + self.duration


@dataclass
class Timeline:
    spec: Spec
    clips: list[ResolvedClip]
    total: float
    music_input_index: int | None = None
    logo_input_index: int | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def has_audio(self) -> bool:
        return (self.spec.music is not None
                or any(c.narration_input_index is not None or c.has_own_audio
                       for c in self.clips))


def resolve(spec: Spec, tools: Tools) -> Timeline:
    """Probe every input, settle each clip's duration, and lay out the timeline."""
    notes: list[str] = []
    resolved: list[ResolvedClip] = []

    for index, clip in enumerate(spec.clips):
        if clip.title is not None:
            resolved.append(_title_clip(spec, clip, index, notes))
            continue

        info = probe(tools, clip.path)
        if not info.has_video:
            raise SpecError(
                f"spec.clips[{index}].path: {clip.path} has no video/image stream"
            )

        narration_info = probe(tools, clip.narration) if clip.narration else None
        if narration_info is not None and not narration_info.has_audio:
            raise SpecError(
                f"spec.clips[{index}].narration: {clip.narration} has no audio stream"
            )

        duration = _duration_for(clip, index, info, narration_info, notes)
        motion = spec.resolve_motion(clip, index) if info.is_still else "none"
        resolved.append(ResolvedClip(index=index, clip=clip, info=info,
                                     duration=duration, motion=motion,
                                     source_path=clip.path,
                                     narration_info=narration_info))

    _clamp_transitions(spec, resolved, notes)
    total = _lay_out(spec, resolved)
    _assign_input_indices(spec, resolved)

    timeline = Timeline(spec=spec, clips=resolved, total=total, warnings=notes)
    cursor = _next_index(resolved)
    if spec.music is not None:
        timeline.music_input_index = cursor
        cursor += 1
    if spec.logo is not None:
        timeline.logo_input_index = cursor
    return timeline


def _title_clip(spec: Spec, clip: Clip, index: int,
                notes: list[str]) -> ResolvedClip:
    duration = clip.duration
    if duration == AUTO:
        notes.append(
            f"clip {index} (title card): duration 'auto' has nothing to measure; "
            f"falling back to {FALLBACK_DURATION}s"
        )
        duration = FALLBACK_DURATION
    return ResolvedClip(index=index, clip=clip, info=TITLE_INFO,
                        duration=float(duration), motion=clip.motion)


def _duration_for(clip: Clip, index: int, info: MediaInfo,
                  narration: MediaInfo | None, notes: list[str]) -> float:
    if clip.duration != AUTO:
        duration = float(clip.duration)
        if not info.is_still and info.duration is not None:
            available = info.duration - clip.start
            if available <= 0:
                raise SpecError(
                    f"spec.clips[{index}].start: {clip.start}s is past the end of "
                    f"{clip.path} ({info.duration:.2f}s long)"
                )
            if duration > available + 0.05:
                notes.append(
                    f"clip {index} ({_name(clip.path)}): asked for {duration:.2f}s "
                    f"but only {available:.2f}s remains after start={clip.start}s; "
                    "using what is there"
                )
                duration = available
        return duration

    if narration is not None and narration.duration:
        return narration.duration + NARRATION_TAIL
    if not info.is_still and info.duration is not None:
        return max(0.05, info.duration - clip.start)
    notes.append(
        f"clip {index} ({_name(clip.path)}): duration 'auto' needs a narration or a "
        f"video input; falling back to {FALLBACK_DURATION}s"
    )
    return FALLBACK_DURATION


def _clamp_transitions(spec: Spec, clips: list[ResolvedClip],
                       notes: list[str]) -> None:
    """A crossfade cannot outlast the shorter of the two clips it joins."""
    for index in range(len(clips) - 1):
        transition = spec.transition_after(index)
        if not transition.active:
            continue
        # Leave a sliver of each clip un-faded so neither vanishes entirely.
        limit = min(clips[index].duration, clips[index + 1].duration) * 0.9
        if transition.duration > limit:
            notes.append(
                f"transition after clip {index}: {transition.duration:.2f}s is too "
                f"long for the neighbouring clips; shortened to {limit:.2f}s"
            )
            clips[index].transition_out = limit


def transition_duration(spec: Spec, clips: list[ResolvedClip], index: int) -> float:
    """Effective crossfade length after clamping, 0 for a hard cut."""
    transition = spec.transition_after(index)
    if not transition.active:
        return 0.0
    clamped = clips[index].transition_out
    return transition.duration if clamped is None else clamped


def _lay_out(spec: Spec, clips: list[ResolvedClip]) -> float:
    cursor = 0.0
    for index, clip in enumerate(clips):
        clip.start = cursor
        cursor += clip.duration
        if index < len(clips) - 1:
            cursor -= transition_duration(spec, clips, index)
    return cursor


def _assign_input_indices(spec: Spec, clips: list[ResolvedClip]) -> None:
    cursor = 0
    for clip in clips:
        clip.input_index = cursor
        cursor += 1
    for clip in clips:
        if clip.narration_info is not None:
            clip.narration_input_index = cursor
            cursor += 1


def _next_index(clips: list[ResolvedClip]) -> int:
    used = [c.input_index for c in clips]
    used += [c.narration_input_index for c in clips
             if c.narration_input_index is not None]
    return max(used) + 1


def _name(path: str) -> str:
    return path.rsplit("/", 1)[-1]
