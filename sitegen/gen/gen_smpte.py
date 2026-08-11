#!/usr/bin/env python3
"""ident-card.png — CF-00 exhibit: SMPTE color-bar station ident card with
the slug 'IBA · LAS VEGAS · SUBCHANNEL 1'. Contains NO digits other than
the literal word SUBCHANNEL 1 (per spec: the convention number never
appears). Tiny easter egg in the PLUGE strip for people who zoom in."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 960, 720
OUT = Path(__file__).resolve().parents[2] / 'site' / 'assets' / "ident-card.png"
FONT = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"

BARS = [(180, 180, 180), (180, 180, 16), (16, 180, 180), (16, 180, 16),
        (180, 16, 180), (180, 16, 16), (16, 16, 180)]
CASTS = [(16, 16, 180), (19, 19, 19), (180, 16, 180), (19, 19, 19),
         (16, 180, 180), (19, 19, 19), (180, 180, 180)]
PLUGE = [(0, 33, 76), (255, 255, 255), (50, 0, 106), (19, 19, 19),
         (9, 9, 9), (19, 19, 19), (29, 29, 29), (19, 19, 19)]

img = Image.new("RGB", (W, H), (0, 0, 0))
d = ImageDraw.Draw(img)

bar_h = int(H * 0.52)
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

# easter egg: near-black text hidden in the dark PLUGE cell (zoom to read)
f_egg = ImageFont.truetype(FONT, 13)
d.text((int(3.05 * pw), bar_h + cast_h + pluge_h // 2 - 7),
       "IF YOU CAN READ THIS, YOU ARE THE EXAMINER",
       font=f_egg, fill=(31, 31, 31))

# lower third: ident slug
band_y = bar_h + cast_h + pluge_h
d.rectangle([0, band_y, W, H], fill=(4, 10, 4))
GREEN = (57, 255, 20)
DIM = (32, 150, 24)
lines = [
    ("INSPECTRON BROADCAST AUTHORITY", DIM, 24),
    ("IBA · LAS VEGAS · SUBCHANNEL 1", GREEN, 34),
    ("PROOF OF RECEPTION REQUIRED", DIM, 20),
]
y = band_y + 24
for text, col, size in lines:
    f = ImageFont.truetype(FONT, size)
    tw = d.textlength(text, font=f)
    d.text(((W - tw) / 2, y), text, font=f, fill=col)
    y += size + 16

for yy in range(0, H, 3):
    d.line([(0, yy), (W, yy)], fill=(0, 0, 0), width=1)

img.save(OUT)
print("wrote", OUT, img.size)
