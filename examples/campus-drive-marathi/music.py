"""An original corporate music bed, synthesised from scratch.

Additive synthesis only - no samples, no loops, nothing licensed. The
arrangement thins out at the top and fills in as the reel goes on, so the
contact and call-to-action land on the fullest bar.
"""

from __future__ import annotations

import wave

import numpy as np

SR = 44100
BPM = 104.0
BEAT = 60.0 / BPM
BAR = BEAT * 4

# Bm - G - D - A, one bar each: a bright, unresolved-then-resolving loop.
CHORDS = [(59, 62, 66), (55, 59, 62), (50, 57, 62, 66), (57, 61, 64)]
ROOTS = [47, 43, 38, 45]


def hz(midi: float) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def _env(n: int, attack: float, decay: float, sustain: float = 0.0) -> np.ndarray:
    """Attack-decay envelope; `sustain` holds a floor before the decay ends."""
    t = np.arange(n) / SR
    rise = np.clip(t / max(attack, 1e-4), 0, 1)
    fall = np.exp(-t / max(decay, 1e-4))
    return rise * (fall * (1 - sustain) + sustain)


def _tone(freq: float, n: int, harmonics: int = 6, tilt: float = 1.6,
          detune: float = 0.0) -> np.ndarray:
    """Additive tone: no filter needed, so it stays fully vectorised."""
    t = np.arange(n) / SR
    out = np.zeros(n)
    for h in range(1, harmonics + 1):
        out += np.sin(2 * np.pi * freq * h * (1 + detune) * t) / (h ** tilt)
    return out


def _add(buffer: np.ndarray, start: float, signal: np.ndarray, gain: float,
         pan: float = 0.0) -> None:
    i = int(start * SR)
    n = min(len(signal), buffer.shape[0] - i)
    if n <= 0:
        return
    left = gain * (1 - max(pan, 0.0) * 0.7)
    right = gain * (1 + min(pan, 0.0) * 0.7)
    buffer[i:i + n, 0] += signal[:n] * left
    buffer[i:i + n, 1] += signal[:n] * right


def _kick(n: int) -> np.ndarray:
    t = np.arange(n) / SR
    pitch = 120 * np.exp(-t / 0.028) + 46
    phase = 2 * np.pi * np.cumsum(pitch) / SR
    return np.sin(phase) * np.exp(-t / 0.115)


def _hat(n: int, decay: float = 0.035) -> np.ndarray:
    noise = np.random.default_rng(7).standard_normal(n + 1)
    return np.diff(noise) * np.exp(-np.arange(n) / SR / decay)


def compose(total: float, path: str) -> str:
    """Write `total` seconds of music to `path` as a 16-bit stereo WAV."""
    length = int((total + 2.5) * SR)
    buf = np.zeros((length, 2), dtype=np.float64)
    rng = np.random.default_rng(11)

    bars = int(np.ceil((total + 2.0) / BAR))
    for bar in range(bars):
        at = bar * BAR
        chord = CHORDS[bar % 4]
        root = ROOTS[bar % 4]
        # Sections: intro / build / main / lift.
        drums = at >= BAR * 4
        full = at >= BAR * 8
        lift = at >= BAR * 20

        # Sustained pad, two detuned voices for width.
        pad_n = int(BAR * 1.05 * SR)
        for note in chord:
            env = _env(pad_n, 0.32, 3.4, sustain=0.55)
            for side, detune in ((-0.6, -0.0016), (0.6, 0.0016)):
                voice = _tone(hz(note), pad_n, harmonics=7, tilt=1.7,
                              detune=detune) * env
                _add(buf, at, voice, 0.085 if not full else 0.105, side)

        # Sub bass, one note per beat with a little push on the off-beat.
        if drums:
            for beat in range(4):
                n = int(BEAT * 0.92 * SR)
                env = _env(n, 0.006, 0.34, sustain=0.25)
                note = _tone(hz(root), n, harmonics=3, tilt=2.2) * env
                _add(buf, at + beat * BEAT, note, 0.30)

        # Plucked arpeggio in eighths, climbing the chord.
        steps = 8 if not lift else 16
        span = BAR / steps
        for step in range(steps):
            note = chord[step % len(chord)] + (12 if step >= len(chord) * 2 else 0)
            n = int(span * 2.1 * SR)
            env = _env(n, 0.004, 0.22)
            voice = _tone(hz(note), n, harmonics=4, tilt=2.0) * env
            gain = 0.075 if not full else 0.095
            _add(buf, at + step * span, voice, gain, pan=0.35 * (-1) ** step)

        # Drums.
        if drums:
            for beat in (0, 2):
                _add(buf, at + beat * BEAT, _kick(int(0.32 * SR)), 0.55)
            if full:
                _add(buf, at + 3 * BEAT, _kick(int(0.32 * SR)), 0.40)
            for eighth in range(8):
                if eighth % 2 == 1 or lift:
                    n = int(0.06 * SR)
                    _add(buf, at + eighth * BEAT / 2, _hat(n), 0.10,
                         pan=0.25 * (-1) ** eighth)

        # Counter-melody once the reel reaches the pay-off.
        if lift:
            top = chord[-1] + 12
            n = int(BAR * 0.6 * SR)
            env = _env(n, 0.05, 1.1, sustain=0.3)
            _add(buf, at + BEAT, _tone(hz(top), n, harmonics=5, tilt=2.1) * env,
                 0.075, pan=-0.2)

        # A short noise riser into each new section.
        if bar in (3, 7, 19):
            n = int(BAR * SR)
            sweep = np.linspace(0, 1, n) ** 2.4
            riser = np.diff(rng.standard_normal(n + 1)) * sweep
            _add(buf, at, riser, 0.055)

    # Fades and a gentle soft-clip so nothing spikes.
    fade_in = int(1.6 * SR)
    buf[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
    tail_start = int((total - 3.2) * SR)
    tail = buf.shape[0] - tail_start
    buf[tail_start:] *= np.linspace(1, 0, tail)[:, None]

    buf /= max(np.abs(buf).max(), 1e-9)
    buf = np.tanh(buf * 1.35) / np.tanh(1.35)
    buf *= 0.89

    with wave.open(path, "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(SR)
        out.writeframes((buf * 32767).astype("<i2").tobytes())
    return path


if __name__ == "__main__":
    compose(70.0, "media/music.wav")
