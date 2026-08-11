#!/usr/bin/env python3
"""signoff.wav — 'recorded off-air, 8 kHz mono'.
5 s anthem-style tones, 2 s 1 kHz test tone, 1 s silence, then Bell 103
originate AFSK (mark 1270 / space 1070 Hz, 300 baud, 8-N-1) carrying the
WarGames payload; the modem segment then repeats REVERSED (red herring)."""
import wave
from pathlib import Path

import numpy as np

FS = 8000
BAUD = 300
MARK, SPACE = 1270.0, 1070.0
OUT = Path(__file__).resolve().parents[2] / 'site' / 'assets' / "signoff.wav"

PAYLOAD = ("GREETINGS PROFESSOR FALKEN.\r\n"
           "A STRANGE GAME. THE ONLY WINNING MOVE IS TO TUNE.\r\n"
           "LAUNCH CODE FOLLOWS: CPE1704TKS\r\n"
           "STRIP THE LETTERS. KEEP THE DIGITS. DIAL.\r\n")


def tone(freq, dur, amp=0.5, fs=FS):
    t = np.arange(int(dur * fs)) / fs
    env = np.minimum(1, np.minimum(t / 0.01, (dur - t) / 0.01)) if dur > 0.03 else 1
    return amp * env * np.sin(2 * np.pi * freq * t)


def anthem():
    # slow brass-ish cadence, vaguely anthemic, ends on a held tonic
    notes = [(392, .55), (523, .55), (659, .55), (784, .8), (659, .45),
             (523, .45), (587, .6), (523, 1.05)]
    parts = []
    for f, dur in notes:
        t = np.arange(int(dur * FS)) / FS
        env = np.minimum(1, np.minimum(t / 0.02, (dur - t) / 0.08))
        w = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t)
             + 0.12 * np.sin(2 * np.pi * 3 * f * t))
        parts.append(0.35 * env * w)
    return np.concatenate(parts)


def afsk(bits):
    """Phase-continuous FSK of a bit sequence."""
    spb = FS / BAUD
    n_total = int(round(len(bits) * spb))
    freqs = np.empty(n_total)
    for i in range(n_total):
        freqs[i] = MARK if bits[min(int(i / spb), len(bits) - 1)] else SPACE
    phase = np.cumsum(2 * np.pi * freqs / FS)
    return 0.55 * np.sin(phase)


def uart_bits(text):
    bits = []
    for ch in text.encode("ascii"):
        bits.append(0)                       # start
        bits += [(ch >> k) & 1 for k in range(8)]  # LSB first
        bits.append(1)                       # stop
    return bits


def main():
    lead = [1] * int(2.0 * BAUD)            # 2 s mark carrier
    tail = [1] * int(1.0 * BAUD)            # 1 s carrier tail
    modem = afsk(lead + uart_bits(PAYLOAD) + tail)
    sig = np.concatenate([
        anthem(),                            # ~4.9 s
        tone(1000, 2.0, amp=0.45),           # 2 s test tone
        np.zeros(FS),                        # 1 s silence
        modem,                               # forward data
        np.zeros(int(0.5 * FS)),
        modem[::-1],                         # reversed red herring
        np.zeros(int(0.5 * FS)),
    ])
    # faint off-air hiss (doesn't hurt decode)
    rng = np.random.default_rng(1983)
    sig = sig + 0.004 * rng.standard_normal(len(sig))
    pcm = np.clip(sig, -1, 1)
    pcm = (pcm * 32000).astype("<i2")
    with wave.open(str(OUT), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FS)
        w.writeframes(pcm.tobytes())
    print(f"wrote {OUT} ({len(pcm)/FS:.1f} s, {OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
