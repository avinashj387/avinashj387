#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the Eagle Hi-tech campus-drive reel end to end.

    python3 build.py                 # frames + music + spec + render
    python3 build.py --narration     # also mix the Marathi voice-over in

Output: 1080x1920, 9:16, ~70s, H.264 - ready for Reels, Shorts and WhatsApp.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

import music
import scenes

MEDIA = os.path.join(HERE, "media")
FRAMES = os.path.join(MEDIA, "frames")

# (frame stem, seconds, Ken Burns move, zoom, transition into the next clip)
BOARD = [
    ("01-hook",       4.4, "zoom-in",   1.07, ("fade",        0.50)),
    ("02-drive",      4.6, "zoom-out",  1.08, ("smoothleft",  0.50)),
    ("03-company",    5.0, "pan-up",    1.07, ("fade",        0.45)),
    ("04-college",    5.4, "zoom-in",   1.06, ("fadewhite",   0.50)),
    ("05-date",       5.6, "zoom-out",  1.08, ("slideup",     0.50)),
    ("06-venue",      4.6, "pan-right", 1.07, ("fade",        0.45)),
    ("07-eligible",   4.8, "zoom-in",   1.07, ("circleopen",  0.55)),
    ("08-pillars",    6.0, "pan-up",    1.06, ("wipeup",      0.50)),
    ("09-reasons_a",  6.2, "zoom-in",   1.06, ("slideleft",   0.45)),
    ("10-reasons_b",  5.0, "zoom-out",  1.07, ("fade",        0.50)),
    ("11-services",   7.0, "pan-up",    1.06, ("radial",      0.55)),
    ("12-scale",      4.6, "zoom-in",   1.09, ("fade",        0.50)),
    ("13-contact",    6.4, "pan-up",    1.06, ("smoothright", 0.55)),
    ("14-cta",        6.4, "zoom-out",  1.08, ("none",        0.00)),
]


def total_seconds() -> float:
    return (sum(item[1] for item in BOARD)
            - sum(item[4][1] for item in BOARD))


def make_spec(with_narration: bool) -> dict:
    clips = []
    for stem, seconds, motion, zoom, (kind, fade) in BOARD:
        clip: dict = {
            "path": f"media/frames/{stem}.png",
            "duration": seconds,
            "motion": motion,
            "zoom": zoom,
            "transition": {"type": kind, "duration": fade},
        }
        voice = os.path.join(MEDIA, "vo", f"{stem}.wav")
        if with_narration and os.path.exists(voice):
            clip["narration"] = f"media/vo/{stem}.wav"
        clips.append(clip)

    return {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "background": "#05183C",
        "seed": 11,
        "music": {
            "path": "media/music.wav",
            "volume": 0.30 if with_narration else 0.92,
            "fade_in": 1.2,
            "fade_out": 3.0,
            "loop": True,
            "duck": with_narration,
        },
        "clips": clips,
    }


def normalise(path: str) -> None:
    """Bring the mix to about -14 LUFS, where Reels/Shorts want it.

    Video is stream-copied, so this is a quick audio-only pass rather than a
    second encode.
    """
    tmp = path + ".norm.mp4"
    code = subprocess.call([
        "ffmpeg", "-hide_banner", "-v", "error", "-y", "-i", path,
        "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", tmp])
    if code == 0:
        os.replace(tmp, path)
        print("normalised to -14 LUFS")
    elif os.path.exists(tmp):
        os.remove(tmp)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--narration", action="store_true",
                        help="mix media/vo/*.wav under the frames")
    parser.add_argument("-o", "--output", default=None)
    parser.add_argument("--skip-frames", action="store_true")
    parser.add_argument("--quality", default="high")
    args = parser.parse_args()

    if not args.skip_frames:
        print("frames ...")
        scenes.build_all(FRAMES)
        print("music ...")
        music.compose(total_seconds(), os.path.join(MEDIA, "music.wav"))

    name = "spec-narrated.json" if args.narration else "spec.json"
    spec_path = os.path.join(HERE, name)
    with open(spec_path, "w", encoding="utf-8") as handle:
        json.dump(make_spec(args.narration), handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    output = args.output or os.path.join(
        HERE, "eagle-hitech-campus-drive"
        + ("-marathi-voiceover" if args.narration else "-marathi") + ".mp4")
    print(f"render -> {output}  ({total_seconds():.1f}s)")
    repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [repo_root] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    code = subprocess.call([sys.executable, "-m", "videogen", "render", spec_path,
                            "-o", output, "--quality", args.quality,
                            "--supersample", "3"], env=env)
    if code == 0:
        normalise(output)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
