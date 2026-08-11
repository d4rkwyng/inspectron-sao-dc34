#!/usr/bin/env python3
"""Verify signoff.wav: independent noncoherent Bell 103 demodulator recovers
the exact payload from the forward modem segment, and the reversed segment
does NOT contain it (red herring confirmed)."""
import wave
from pathlib import Path

import numpy as np

FS_EXPECT = 8000
BAUD = 300
MARK, SPACE = 1270.0, 1070.0
WAV = Path(__file__).resolve().parents[2] / 'site' / 'assets' / "signoff.wav"

PAYLOAD = ("GREETINGS PROFESSOR FALKEN.\r\n"
           "A STRANGE GAME. THE ONLY WINNING MOVE IS TO TUNE.\r\n"
           "LAUNCH CODE FOLLOWS: CPE1704TKS\r\n"
           "STRIP THE LETTERS. KEEP THE DIGITS. DIAL.\r\n")

with wave.open(str(WAV)) as w:
    fs = w.getframerate()
    assert fs == FS_EXPECT and w.getnchannels() == 1 and w.getsampwidth() == 2
    x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(float) / 32768

print(f"format OK: {fs} Hz mono 16-bit, {len(x)/fs:.1f} s")


def band_energy(sig, f):
    n = len(sig)
    t = np.arange(n) / fs
    c = np.exp(-2j * np.pi * f * t)
    win = int(round(fs / BAUD))
    kernel = np.ones(win) / win
    return np.abs(np.convolve(sig * c, kernel, mode="same"))


def demod(sig):
    """Noncoherent FSK -> UART 8N1 ASCII.
    Soft mark/space discriminator, then open-loop framing with the frame
    phase chosen by maximizing start/stop-bit validity (grid search)."""
    s = band_energy(sig, MARK) - band_energy(sig, SPACE)  # >0 = mark
    spb = fs / BAUD
    # first start-bit edge: first sustained negative dip after leading mark
    idx = np.where(s > 0.05)[0]
    if len(idx) == 0:
        return b""
    i0 = idx[0]
    dips = np.where(s[i0:] < -0.05)[0]
    if len(dips) == 0:
        return b""
    t0 = i0 + dips[0]

    def decode(phi):
        out, valid, total = [], 0, 0
        pos = phi
        n = len(s)
        while pos + 10 * spb < n:
            centers = [int(pos + (k + 0.5) * spb) for k in range(10)]
            bits = [1 if s[c] > 0 else 0 for c in centers]
            total += 1
            if bits[0] == 0 and bits[9] == 1:
                valid += 1
                out.append(sum(b << k for k, b in enumerate(bits[1:9])))
                pos += 10 * spb
            else:
                # idle mark between frames: slide one bit
                pos += spb
        return bytes(out), (valid / total if total else 0)

    best = max((decode(t0 + d) for d in np.linspace(-spb, spb, 81)),
               key=lambda r: r[1])
    return best[0]


# forward segment: locate the modem audio (after anthem+tone+silence ~ 8 s)
decoded = demod(x[int(7.5 * fs):]).decode("ascii", "replace")
i = decoded.find("GREETINGS")
assert i >= 0, decoded[:80]
fwd = decoded[i:i + len(PAYLOAD)]
assert fwd == PAYLOAD, repr(fwd)
print("forward decode: OK, payload recovered verbatim:")
print("  " + fwd.replace("\r\n", " / ").strip())
assert "CPE1704TKS" in fwd

# reversed tail must NOT decode to the payload
n_modem = len(decoded)
rev = demod(x[-int(len(x) / 3):]).decode("ascii", "replace")
assert "CPE1704TKS" not in rev and "GREETINGS" not in rev
print(f"reversed segment: OK (garbage, {len(rev)} bytes, no payload strings)")
print("signoff.wav VERIFIED")
