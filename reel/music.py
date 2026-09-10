"""Original synthesised corporate-motivational bed for the campus-drive reel.

Everything here is generated from oscillators and noise, so the track carries no
third-party licence: it is safe to post commercially. 120 BPM, D major,
I-V-vi-IV, with the energy curve from the production plan (peak on the salary
scene, dip on the hostel scene, climax on the CTA).
"""
import math, struct, wave, numpy as np

SR, DUR = 44100, 75.0
N = int(SR * DUR)
T = np.arange(N) / SR
BPM = 120.0
BEAT = 60.0 / BPM            # 0.5 s
BAR = BEAT * 4               # 2.0 s

L = np.zeros(N); R = np.zeros(N)

def add(buf, start, sig, gain=1.0, pan=0.0):
    """Mix sig into L/R at start seconds, with equal-power pan (-1..1)."""
    i = int(start * SR)
    if i >= N: return
    s = sig[:N - i]
    gl = gain * math.cos((pan + 1) * math.pi / 4)
    gr = gain * math.sin((pan + 1) * math.pi / 4)
    L[i:i + len(s)] += s * gl
    R[i:i + len(s)] += s * gr

def adsr(n, a, d, s, r):
    e = np.zeros(n); a, d, r = int(a*SR), int(d*SR), int(r*SR)
    a, d, r = max(a,1), max(d,1), max(r,1)
    sus = max(n - a - d - r, 0)
    e[:a] = np.linspace(0, 1, a)
    e[a:a+d] = np.linspace(1, s, d)
    e[a+d:a+d+sus] = s
    e[a+d+sus:a+d+sus+r] = np.linspace(s, 0, min(r, n-a-d-sus))
    return e

def pluck(f, dur, detune=0.0):
    n = int(dur * SR); t = np.arange(n) / SR
    sig = (np.sin(2*np.pi*f*t) + 0.42*np.sin(4*np.pi*f*t) + 0.18*np.sin(6*np.pi*f*t)
           + 0.10*np.sin(2*np.pi*f*(1+detune)*t))
    return sig * np.exp(-t * 7.0) * adsr(n, 0.004, 0.05, 0.55, dur*0.5)

def bassnote(f, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    sig = np.sin(2*np.pi*f*t) + 0.30*np.sin(4*np.pi*f*t)
    return sig * adsr(n, 0.010, 0.12, 0.60, dur*0.45)

def padvoice(f, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    sig = np.zeros(n)
    for k, amp in ((1,1.0), (2,0.30), (3,0.14), (4,0.07)):
        for det in (-0.0016, 0.0, 0.0019):
            sig += amp * np.sin(2*np.pi*f*k*(1+det)*t)
    return sig / 4.2 * adsr(n, 0.55, 0.35, 0.80, 0.85)

def brass(f, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    sig = sum((1.0/k) * np.sin(2*np.pi*f*k*t) for k in range(1, 9))
    return sig * 0.34 * adsr(n, 0.14, 0.20, 0.72, 0.45)

def kick(dur=0.34):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 118 * np.exp(-t * 26) + 44
    return np.sin(2*np.pi*np.cumsum(f)/SR) * np.exp(-t * 8.5)

def hat(dur=0.055, tone=0.0):
    n = int(dur * SR); t = np.arange(n) / SR
    rng = np.random.default_rng(int(tone*1e6) % 9999)
    return rng.standard_normal(n) * np.exp(-t * (95 - tone*25)) * 0.30

def clap(dur=0.26):
    n = int(dur * SR); t = np.arange(n) / SR
    rng = np.random.default_rng(4242)
    body = rng.standard_normal(n) * np.exp(-t * 17)
    body += 0.5 * np.sin(2*np.pi*190*t) * np.exp(-t * 26)
    return body * 0.42

def whoosh(dur=0.55, up=True):
    n = int(dur * SR); t = np.arange(n) / SR
    rng = np.random.default_rng(77)
    nz = rng.standard_normal(n)
    # one-pole sweep to fake a filter move
    out = np.zeros(n); y = 0.0
    cut = np.linspace(0.02, 0.55, n) if up else np.linspace(0.55, 0.02, n)
    for i in range(n):
        y += cut[i] * (nz[i] - y); out[i] = y
    return out * np.sin(np.pi * t / dur) ** 2 * 0.55

def boom(dur=1.5):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 70 * np.exp(-t * 3.2) + 34
    return (np.sin(2*np.pi*np.cumsum(f)/SR) * np.exp(-t * 2.1)) * 0.9

# ---- harmony: D  A  Bm  G (2 s per chord) --------------------------------
NOTE = dict(D2=73.42,G2=98.00,A2=110.00,B2=123.47,D3=146.83,E3=164.81,Fs3=185.00,
            G3=196.00,A3=220.00,B3=246.94,Cs4=277.18,D4=293.66,E4=329.63,Fs4=369.99,
            G4=392.00,A4=440.00,B4=493.88,Cs5=554.37,D5=587.33,Fs5=739.99,A5=880.00)
PROG = [
    ('D2',  ['D4','Fs4','A4'],  ['D5','Fs5','A5']),
    ('A2',  ['Cs4','E4','A4'],  ['Cs5','E4','A5']),
    ('B2',  ['B3','D4','Fs4'],  ['Fs5','B4','D5']),
    ('G2',  ['G3','B3','D4'],   ['D5','G4','B4']),
]

def gains(t):
    """Energy curve from the production plan."""
    def ramp(a, b): return min(max((t-a)/(b-a), 0.0), 1.0)
    intro  = ramp(0.5, 3.0)
    build  = ramp(15.0, 23.0)
    peak1  = ramp(27.0, 28.4) * (1 - ramp(35.6, 36.6))          # salary
    dip    = 1 - 0.72 * (ramp(46.6, 47.6) * (1 - ramp(53.2, 54.2)))  # hostel
    rise2  = ramp(54.0, 60.0)
    climax = ramp(67.4, 68.3)
    tail   = 1 - ramp(71.9, 72.4)                                # drums stop at end screen
    base = (0.55 + 0.30*build + 0.25*rise2) * dip * tail
    return dict(
        drum = intro * base * (1 + 0.35*peak1 + 0.55*climax),
        bass = intro * (0.65 + 0.35*build) * dip * (1 - ramp(73.6, 74.6)),
        pluck= ramp(2.5, 5.0) * (0.55 + 0.45*build) * dip * (1 - ramp(73.6, 74.6)),
        pad  = (0.35 + 0.65*ramp(0.0, 2.0)) * (1 - 0.25*(1-dip)),
        horn = peak1 * 0.9 + climax * 1.0,
    )

# ---- pad + brass (per bar) ------------------------------------------------
bar = 0
while bar * BAR < DUR:
    t0 = bar * BAR
    root, triad, hi = PROG[bar % 4]
    g = gains(t0 + BAR/2)
    for i, nm in enumerate(triad):
        add(None, t0, padvoice(NOTE[nm], BAR + 0.5), 0.085 * g['pad'], (i-1)*0.55)
    if g['horn'] > 0.02:
        add(None, t0, brass(NOTE[root]*2, BAR*0.95), 0.10 * g['horn'], -0.15)
        add(None, t0, brass(NOTE[triad[2]], BAR*0.95), 0.075 * g['horn'], 0.15)
    bar += 1

# ---- rhythm section (per beat) -------------------------------------------
beat = 0
while beat * BEAT < DUR:
    t0 = beat * BEAT
    b_in_bar = beat % 4
    bar_i = (beat // 4) % 4
    root, triad, hi = PROG[bar_i]
    g = gains(t0)
    if g['drum'] > 0.02:
        if b_in_bar in (0, 2):
            add(None, t0, kick(), 0.62 * g['drum'])
        if b_in_bar == 2 and (beat // 4) % 2 == 1:
            add(None, t0 + BEAT*0.5, kick(0.24), 0.34 * g['drum'])
        if b_in_bar in (1, 3):
            add(None, t0, clap(), 0.30 * g['drum'])
        for h in range(2):
            add(None, t0 + h*BEAT/2, hat(tone=(beat*2+h) % 7 / 7),
                0.24 * g['drum'] * (1.0 if h == 0 else 0.62), 0.25 if h else -0.25)
    if g['bass'] > 0.02 and b_in_bar in (0, 2):
        add(None, t0, bassnote(NOTE[root], BEAT*1.85), 0.36 * g['bass'])
    if g['pluck'] > 0.02:
        for h in range(2):
            nm = hi[(beat*2 + h) % 3]
            add(None, t0 + h*BEAT/2, pluck(NOTE[nm], 0.46),
                0.115 * g['pluck'] * (1.0 if h == 0 else 0.72), ((beat+h) % 3 - 1) * 0.5)
    beat += 1

# ---- transition whooshes + impacts ---------------------------------------
SCENES = [6,12,17,23,28,36,41,47,54,63,68]
for s in SCENES:
    add(None, s - 0.5, whoosh(0.6, up=True), 0.30)
add(None, 0.0,  whoosh(1.6, up=True), 0.34)
for s in (28.0, 60.0, 68.0):
    add(None, s, boom(1.6), 0.42)
add(None, 71.95, boom(2.2), 0.30)

# ---- master --------------------------------------------------------------
def master(x):
    x = x * 0.92
    fi = int(1.2 * SR); x[:fi] *= np.linspace(0, 1, fi)
    fo = int(1.1 * SR); x[-fo:] *= np.linspace(1, 0, fo)
    # soft-knee limiter
    x = np.tanh(x * 1.18) * 0.86
    return x

L, R = master(L), master(R)
peak = max(np.abs(L).max(), np.abs(R).max())
L, R = L/peak*0.89, R/peak*0.89
inter = np.empty(N*2, dtype=np.float64); inter[0::2] = L; inter[1::2] = R
pcm = (np.clip(inter, -1, 1) * 32767).astype('<i2')
with wave.open('music.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print(f"music.wav  {DUR:.0f}s  peak={peak:.3f}")
