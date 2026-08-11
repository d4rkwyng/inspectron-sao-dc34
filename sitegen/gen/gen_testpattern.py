#!/usr/bin/env python3
"""testpattern-001.png — SMPTE color-bar test card with the station history
plaque burned into the lower third, phosphor-green monospace, scanlines.
Contains NO digits and NO frequencies (per puzzle spec)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 960, 720
OUT = Path(__file__).resolve().parents[2] / 'site' / 'assets' / "testpattern-001.png"
FONT = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"

# 75% SMPTE bars
BARS = [(180, 180, 180), (180, 180, 16), (16, 180, 180), (16, 180, 16),
        (180, 16, 180), (180, 16, 16), (16, 16, 180)]
CASTS = [(16, 16, 180), (19, 19, 19), (180, 16, 180), (19, 19, 19),
         (16, 180, 180), (19, 19, 19), (180, 180, 180)]
PLUGE = [(0, 33, 76), (255, 255, 255), (50, 0, 106), (19, 19, 19),
         (9, 9, 9), (19, 19, 19), (29, 29, 29), (19, 19, 19)]

img = Image.new("RGB", (W, H), (0, 0, 0))
d = ImageDraw.Draw(img)

bar_h = int(H * 0.50)
cast_h = int(H * 0.065)
pluge_h = int(H * 0.10)
bw = W / 7
for i, c in enumerate(BARS):
    d.rectangle([int(i * bw), 0, int((i + 1) * bw) - 1, bar_h], fill=c)
for i, c in enumerate(CASTS):
    d.rectangle([int(i * bw), bar_h, int((i + 1) * bw) - 1, bar_h + cast_h], fill=c)
pw = W / len(PLUGE)
for i, c in enumerate(PLUGE):
    d.rectangle([int(i * pw), bar_h + cast_h, int((i + 1) * pw) - 1,
                 bar_h + cast_h + pluge_h], fill=c)

# lower third: black band, phosphor-green plaque text (exact spec wording)
band_y = bar_h + cast_h + pluge_h
d.rectangle([0, band_y, W, H], fill=(4, 10, 4))
GREEN = (57, 255, 20)
DIM = (32, 150, 24)
lines = [
    ("INSPECTRON BROADCAST AUTHORITY — STATION HISTORY PLAQUE", GREEN, 26),
    ('"FIRST BROADCAST: SANDS HOTEL & CASINO, LAS VEGAS.', DIM, 22),
    ("ROUGHLY ONE HUNDRED VIEWERS TUNED IN. ONE MAN RAN THE BOARD.", DIM, 22),
    ("WE HAVE BEEN ON THE AIR EVERY SUMMER SINCE.", DIM, 22),
    ('DIAL OUR SIGN-ON YEAR."', GREEN, 24),
]
y = band_y + 18
for text, col, size in lines:
    f = ImageFont.truetype(FONT, size)
    tw = d.textlength(text, font=f)
    d.text(((W - tw) / 2, y), text, font=f, fill=col)
    y += size + 12

# scanline + vignette overlay
overlay = Image.new("L", (W, H), 0)
od = ImageDraw.Draw(overlay)
for yy in range(0, H, 3):
    od.line([(0, yy), (W, yy)], fill=70, width=1)
img = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), img, overlay.point(lambda v: v // 2))
# slight phosphor bloom via cheap glow: skip; keep crisp

img.save(OUT)
print("wrote", OUT, img.size)
