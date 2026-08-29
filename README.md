# videogen

Turn a folder of images (or a JSON spec) into a finished video: Ken Burns pans,
crossfades, captions, voiceover and a music bed that ducks under the narration.

Wraps `ffmpeg` — no MoviePy, no pip dependencies, no frame-by-frame Python. The
whole video is built as a single filtergraph and encoded in one pass.

```bash
videogen from-dir ./photos --audio track.mp3 -o reel.mp4
```

## Requirements

Python 3.10+ and `ffmpeg` (with `ffprobe`) on your `PATH`:

| Platform | Install |
| --- | --- |
| macOS | `brew install ffmpeg` |
| Debian/Ubuntu | `sudo apt install ffmpeg` |
| Windows | `winget install Gyan.FFmpeg` |

Then, from the repo root:

```bash
pip install -e .          # installs the `videogen` command
pip install -e .[yaml]    # optional: lets you write specs in YAML
```

Without installing, `python -m videogen ...` works just as well.

## Two ways in

**A folder of images.** Sorted by filename, one clip each:

```bash
videogen from-dir ./photos -o reel.mp4 \
    --duration 3.5 --transition fade --audio track.mp3
```

**A spec file**, when you want per-clip control:

```bash
videogen render story.json -o story.mp4
```

To move from the first to the second, ask `from-dir` for the spec it generated
and edit that:

```bash
videogen from-dir ./photos --save-spec story.json -o reel.mp4
```

## Spec format

Paths inside a spec are resolved **relative to the spec file**. Top-level
`duration`, `motion`, `zoom`, `transition` and `caption` set defaults that any
clip can override.

```jsonc
{
  "width": 1920, "height": 1080, "fps": 30,
  "background": "black",          // letterbox colour: name, 0xRRGGBB, or #rrggbb
  "seed": 42,                     // makes "random" motion reproducible

  "duration": 4,                  // default seconds per clip
  "motion": "random",             // default Ken Burns move
  "transition": { "type": "fade", "duration": 0.6 },
  "caption": { "position": "bottom", "size": 52 },   // styling only, no text

  "music": {
    "path": "media/track.mp3",
    "volume": 0.25,               // 1.0 = untouched
    "fade_in": 1.5, "fade_out": 2.5,
    "loop": true,                 // repeat if shorter than the video
    "duck": true,                 // drop under narration automatically
    "start": 0                    // skip into the track
  },

  "clips": [
    { "path": "media/01.jpg", "caption": "Sunrise", "motion": "zoom-in" },
    { "path": "media/02.jpg", "duration": 6, "zoom": 1.4 },

    // duration "auto" makes the clip last as long as its voiceover
    { "path": "media/03.jpg", "duration": "auto", "narration": "media/vo.mp3" },

    // video clips keep their own audio; start/duration trim them
    { "path": "media/clip.mp4", "start": 12.5, "duration": 5, "volume": 0.6,
      "transition": "none" }      // hard cut into the next clip
  ]
}
```

A clip may be written as a bare string (`"media/01.jpg"`) when the defaults are
fine, and a caption as a bare string when you only want text.

### Fields

**Top level** — `width`, `height` (both must be even), `fps`, `background`,
`font`, `seed`, `music`, `clips`, plus the clip defaults `duration`, `motion`,
`zoom`, `transition`, `caption`.

**Per clip** — `path`, `duration` (number or `"auto"`), `motion`, `zoom`,
`caption`, `narration`, `start`, `transition`, `volume`.

**`motion`** (still images only) — `none`, `zoom-in`, `zoom-out`, `pan-left`,
`pan-right`, `pan-up`, `pan-down`, `random`. `zoom` sets how far the move
travels; `1.0` holds still.

**`transition.type`** — `none` (hard cut), `fade`, `fadeblack`, `fadewhite`,
`wipeleft/right/up/down`, `slideleft/right/up/down`, `circleopen`,
`circleclose`, `dissolve`, `smoothleft`, `smoothright`, `pixelize`, `radial`,
`hblur`. A clip's `transition` describes the join to the clip **after** it.

**`caption`** — `text`, `position` (`bottom`/`top`/`center`), `size`, `color`,
`box`, `box_color`, `margin`.

## CLI

```
videogen from-dir DIR [-o OUT]     build from a folder, sorted by filename
videogen render SPEC  [-o OUT]     build from a .json / .yaml spec
videogen probe FILE...             show what videogen sees in a file
```

Shared options: `--preset {720p,1080p,4k,vertical,square}`, `--width`,
`--height`, `--fps`, `--quality {fast,balanced,high}`, `--font`, `--seed`,
`--supersample N`, `--dry-run`, `--dump-graph FILE`, `--no-overwrite`, `-q`.

`from-dir` adds `--duration`, `--motion`, `--zoom`, `--transition`,
`--transition-duration`, `--audio`, `--audio-volume`, `--save-spec`.

```bash
# vertical cut for phones, quick clips, hard cuts
videogen from-dir ./photos -o story.mp4 --preset vertical \
    --duration 2.5 --transition none

# check the timing without waiting for an encode
videogen render story.json --dry-run

# see the filtergraph it would run
videogen render story.json --dump-graph graph.txt
```

## As a library

```python
from videogen import render, load, from_directory

render(load("story.json"), "story.mp4")
render(from_directory("./photos", duration=3), "reel.mp4", quality="high")
```

`render()` returns the output path, final duration, clip count, and any
warnings (a clamped transition, a capped duration) that the CLI prints as
`note:` lines.

## How it works

One `ffmpeg` invocation, one filtergraph, one encode pass:

1. **Fit** — each input is scaled to fit the frame without distortion and
   letterboxed against `background`.
2. **Move** — stills get `zoompan`. The crop is taken from a supersampled copy
   (`--supersample`, default 2×), because at 1× the integer crop offsets step
   visibly from frame to frame. Raise it for smoother motion, at the cost of
   encode time.
3. **Stitch** — `xfade` for transitions, `concat` for hard cuts. Every link is
   pinned to `AVTB`, since those two filters otherwise emit different
   timebases and `xfade` refuses to join them.
4. **Mix** — narration and clip audio are delayed to their start times and
   mixed; music is looped, faded, and pushed under the voices with
   `sidechaincompress` (measured at about 7 dB of ducking).
5. **Encode** — H.264 `yuv420p` with `+faststart`.

Caption text is written to a sidecar file and passed to `drawtext` via
`textfile=`, so colons, commas, quotes and newlines in your captions never have
to survive filtergraph escaping.

### Notes

- A crossfade is clamped to 90% of the shorter clip it joins, so neither clip
  can vanish entirely. You get a `note:` when that happens.
- Total duration is `sum(durations) − sum(transitions)`: crossfades overlap.
- A **mono** music or narration file comes out about 3 dB quieter than the
  source. That is ffmpeg's power-conserving mono→stereo upmix, not a bug —
  raise `volume` if it matters. Stereo sources pass through untouched.
- `duration: "auto"` needs a `narration` or a video input to measure; on a bare
  still it warns and falls back to 4s.

## Tests

```bash
python -m unittest discover -s tests
```

The end-to-end test renders a real file and skips itself if `ffmpeg` is
missing; everything else runs on stubbed probes.
