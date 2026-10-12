"""Synthesize the Mise film's soundtrack in code: 120 BPM, 20 s, UI sounds on the beat grid.

    python video/score.py   -> video/score.wav
"""
import wave
from pathlib import Path
import numpy as np

SR, DUR, BPM = 44100, 20.0, 120
BEAT = 60 / BPM
N = int(SR * DUR)
t_all = np.arange(N) / SR
mix = np.zeros(N)
rng = np.random.default_rng(7)


def add(sig, at, gain=1.0):
    i = int(at * SR)
    j = min(N, i + len(sig))
    mix[i:j] += sig[: j - i] * gain


def env(n, a=0.002, d=0.2):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / d)


def kick():
    n = int(0.35 * SR); t = np.arange(n) / SR
    f = 50 + 90 * np.exp(-t / 0.035)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.12)


def hat():
    n = int(0.06 * SR)
    x = rng.standard_normal(n)
    x = np.diff(np.concatenate([[0], x]))  # brighten
    return x * env(n, 0.0005, 0.015) * 0.5


def tick(freq=2200):
    n = int(0.05 * SR); t = np.arange(n) / SR
    return np.sin(2 * np.pi * freq * t) * env(n, 0.0005, 0.012)


def click():
    n = int(0.03 * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 3200 * t) * 0.6 + rng.standard_normal(n) * 0.4) * env(n, 0.0003, 0.006)


def whoosh(length=0.5):
    n = int(length * SR); t = np.arange(n) / SR
    x = rng.standard_normal(n)
    # sweep a simple one-pole low-pass cutoff up then down
    cut = 0.02 + 0.25 * np.sin(np.pi * t / length) ** 2
    y = np.zeros(n); acc = 0.0
    for i in range(n):
        acc += cut[i] * (x[i] - acc); y[i] = acc
    return y * np.sin(np.pi * t / length) ** 1.5 * 1.6


def ping(freq=1318.5):
    n = int(0.9 * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 2 * t)) * env(n, 0.002, 0.25)


def thump():
    n = int(1.6 * SR); t = np.arange(n) / SR
    f = 42 + 60 * np.exp(-t / 0.06)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.45)


def pad(chord, start, end, gain=0.08):
    n = int((end - start) * SR); t = np.arange(n) / SR
    s = sum(np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 1.003 * t) for f in chord)
    fade = np.minimum(1, t / 0.6) * np.minimum(1, (t[-1] - t) / 0.8)
    add(s * fade / len(chord), start, gain)


# rhythm: hats from the start, kick from beat 5, a quieter bar under the lockup
for b in range(40):
    at = b * BEAT
    add(hat(), at + BEAT / 2, 0.35 if b < 36 else 0.15)
    if 5 <= b < 36:
        add(kick(), at, 0.55 if b >= 10 else 0.4)
# pad: Dmaj7 -> Bm7 -> Gmaj7 -> A, two bars each from beat 10
chords = [[146.8, 185.0, 220.0, 277.2], [123.5, 146.8, 185.0, 220.0], [98.0, 123.5, 146.8, 185.0], [110.0, 138.6, 164.8, 220.0]]
for k, start in enumerate(np.arange(5.0, 18.0, 2.0)):
    pad(chords[k % 4], start, start + 2.05)
pad([146.8, 185.0, 220.0, 293.7], 18.0, 20.0, 0.1)

# UI sounds on the grid
for at in [0.25, 0.75, 1.25, 1.75]: add(tick(1760), at, 0.35)
for at in [3.0, 3.5, 4.0]: add(tick(1320), at, 0.3)
for at in [4.45, 9.0, 12.5, 15.5, 18.0]: add(whoosh(0.55), at - 0.15, 0.22)
add(click(), 7.5, 0.6)
for at in [10.5, 11.0, 11.5]: add(tick(2350), at, 0.4)
add(ping(), 13.5, 0.22)
add(click(), 17.0, 0.6)
add(thump(), 18.5, 0.9)
add(ping(880), 18.5, 0.12)

mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.89
fade = np.minimum(1, (DUR - t_all) / 0.6)
mix *= fade
pcm = (np.stack([mix, mix], 1) * 32767).astype(np.int16)
out = Path(__file__).parent / "score.wav"
with wave.open(str(out), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print("score ->", out)
