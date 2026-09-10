#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render the Marathi narration to media/vo/*.wav, one file per scene.

Each line is time-fitted to the scene it belongs to: if the take runs long it
is gently sped up (never past 1.35x, where speech starts to sound comical)
rather than being allowed to bleed into the next scene.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from build import BOARD
from narration import EDGE_RATE, EDGE_VOICE, SCRIPT

VO = os.path.join(HERE, "media", "vo")
HEADROOM = 0.55          # leave a beat of silence at the end of each scene
MAX_TEMPO = 1.35


def duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def speak_espeak(text: str, path: str) -> None:
    subprocess.run(["espeak-ng", "-v", "mr", "-s", "172", "-p", "38",
                    "-a", "175", "-w", path, text], check=True)


def speak_edge(text: str, path: str) -> None:
    import asyncio

    import edge_tts

    mp3 = path.replace(".wav", ".mp3")

    async def go() -> None:
        await edge_tts.Communicate(text, EDGE_VOICE, rate=EDGE_RATE).save(mp3)

    asyncio.run(go())
    subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-i", mp3,
                    "-ar", "44100", "-ac", "1", path], check=True)
    os.remove(mp3)


def fit(path: str, budget: float) -> float:
    """Speed the take up if it overruns its scene; report the final length."""
    have = duration(path)
    target = max(budget - HEADROOM, 1.0)
    if have <= target:
        return have
    tempo = min(have / target, MAX_TEMPO)
    tmp = path + ".tmp.wav"
    subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-i", path,
                    "-filter:a", f"atempo={tempo:.4f}", tmp], check=True)
    os.replace(tmp, path)
    return duration(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=("edge", "espeak"), default="edge")
    args = parser.parse_args()

    os.makedirs(VO, exist_ok=True)
    budgets = {stem: seconds for stem, seconds, *_ in BOARD}
    speak = speak_edge if args.engine == "edge" else speak_espeak

    overruns = []
    for stem, line in SCRIPT:
        path = os.path.join(VO, f"{stem}.wav")
        speak(line, path)
        length = fit(path, budgets[stem])
        room = budgets[stem] - HEADROOM
        flag = "" if length <= room + 0.05 else "  <-- still long"
        if flag:
            overruns.append(stem)
        print(f"  {stem:<14} {length:5.2f}s / {budgets[stem]:.1f}s{flag}")

    if overruns:
        print("\nlonger than their scenes even at max tempo: "
              + ", ".join(overruns)
              + "\nshorten those lines in narration.py, or lengthen the scene "
                "in build.py's BOARD.")
    print(f"\n{len(SCRIPT)} takes in {VO}")
    print("now: python3 build.py --narration --skip-frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
