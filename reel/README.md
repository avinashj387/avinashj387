# Campus Drive reel — build pipeline

Renders the 75-second vertical Marathi recruitment reel described in
[`docs/eaglehitech-campus-drive-marathi-reel.md`](../docs/eaglehitech-campus-drive-marathi-reel.md)
into a finished MP4. Everything in the video is generated here — there is no
stock footage, no licensed music and no third-party artwork — so the output is
free to post commercially.

## How it works

`reel.html` is the whole film. It is a single 1080×1920 page holding all twelve
scenes plus a small deterministic animation engine: `window.seek(t)` places
every element exactly where it belongs at time `t`, with no reliance on the
browser's animation clock. That makes the render reproducible frame for frame.

`render.js` drives it. Chromium (the one Playwright already ships) loads the
page, calls `seek(i/30)` for each of the 2250 frames, screenshots the viewport
and pipes the PNG straight into `ffmpeg` — nothing touches disk between the
browser and the encoder.

Chromium is doing the typesetting on purpose. Marathi needs real complex-text
shaping for conjuncts and matras (मातोश्री, सुवर्णसंधी, प्रक्रिया); `ffmpeg`'s
`drawtext` renders those incorrectly because it has no shaping engine.

`music.py` synthesises the bed from oscillators and noise — kick, clap, hats,
sub bass, pluck arpeggio, pad and brass over a I–V–vi–IV progression in D major
at 120 BPM. The energy curve follows the production plan: it builds through the
intro, peaks on the salary scene, drops for the hostel scene, and climaxes on
the call to action.

`finish.sh` muxes picture and music, normalises to −14 LUFS, cuts the 30-second
WhatsApp version (picture spliced from the reel, bed laid underneath
continuously so the music does not jump), and grabs the cover still.

## Requirements

- Node with `playwright`
- `ffmpeg` with `libx264` and `aac`
- Fonts installed system-wide: **Mukta** (Devanagari), **Poppins** (Latin and
  figures), **Noto Color Emoji**
- Python 3 with `numpy`

## Build

```bash
export FF=/path/to/ffmpeg
node render.js                 # writes video_silent.mp4  (~15 min)
python3 music.py               # writes music.wav         (~4 s)
FF=$FF ./finish.sh             # writes out/
```

Output in `out/`:

| File | What it is |
| --- | --- |
| `campus-drive-reel-75s.mp4` | full reel — Instagram Reels, YouTube Shorts, Facebook |
| `campus-drive-whatsapp-30s.mp4` | short cut for WhatsApp Status |
| `thumbnail-1080x1920.png` | cover still |

## Editing the video

Content lives in the markup of `reel.html`, one `<section class="scene">` per
scene. Timing lives in the `S` table and the `an(...)` calls below it — `an(id,
start, duration, from, to, easing)`. Change a number, re-run `render.js`.

To drop in real footage later, put the clip behind a scene as a `<video>`
element and seek it from `seek(t)` alongside everything else; the text layers
are already separate and need no changes. The AI generation prompts for those
clips are in the production plan, scene by scene.
