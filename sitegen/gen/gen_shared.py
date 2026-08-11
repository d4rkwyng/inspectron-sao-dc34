#!/usr/bin/env python3
"""Shared site art:
  seal.png — circular INSPECTRON BROADCAST AUTHORITY seal (CRT + antenna),
             phosphor green on transparent, ring text + tagline."""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parents[2] / 'site' / 'assets'
CB = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"
GREEN = (57, 255, 20, 255)
DIM = (34, 160, 22, 255)

# ---------------------------------------------------------------- seal.png
S = 1024  # drawn 2x, saved 512
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
cx = cy = S // 2

def ring(r, w, col=GREEN):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=w)

ring(500, 10)
ring(478, 4)
ring(340, 4)

def ring_text(text, radius, start_deg, end_deg, size, col=GREEN, flip=False):
    f = ImageFont.truetype(CB, size)
    n = len(text)
    for k, ch in enumerate(text):
        frac = k / max(n - 1, 1)
        ang = math.radians(start_deg + (end_deg - start_deg) * frac)
        x = cx + radius * math.cos(ang)
        y = cy + radius * math.sin(ang)
        glyph = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glyph)
        gw = gd.textlength(ch, font=f)
        gd.text(((size * 2 - gw) / 2, size // 2), ch, font=f, fill=col)
        rot = math.degrees(ang) + (90 if not flip else -90)
        glyph = glyph.rotate(-rot, resample=Image.BICUBIC, center=(size, size))
        img.paste(glyph, (int(x - size), int(y - size)), glyph)

ring_text("INSPECTRON BROADCAST AUTHORITY", 408, 185, 355, 54)
ring_text("* TUNE YOUR OWN SIGNAL *", 402, 140, 40, 44, col=DIM, flip=True)

# CRT TV glyph: rounded body, screen, two leaning antennas with tip dots
body = [cx - 210, cy - 90, cx + 210, cy + 190]
d.rounded_rectangle(body, radius=42, outline=GREEN, width=12)
d.rounded_rectangle([cx - 172, cy - 54, cx + 116, cy + 152], radius=24,
                    outline=GREEN, width=8)
# raster lines inside screen
for i, yy in enumerate(range(cy - 34, cy + 140, 22)):
    d.line([(cx - 152, yy), (cx + 96, yy)], fill=DIM, width=5)
# control column dots
for yy in (cy - 20, cy + 34, cy + 88):
    d.ellipse([cx + 138, yy, cx + 174, yy + 36], outline=GREEN, width=7)
# antennas (leaning, like the board's prongs)
d.line([(cx - 40, cy - 90), (cx - 130, cy - 250)], fill=GREEN, width=12)
d.line([(cx + 40, cy - 90), (cx + 160, cy - 230)], fill=GREEN, width=12)
d.ellipse([cx - 152, cy - 274, cx - 108, cy - 230], fill=GREEN)   # ball tips
d.ellipse([cx + 140, cy - 252, cx + 180, cy - 212], fill=GREEN)
# static sparkle between antennas
f_sp = ImageFont.truetype(CB, 40)
for sx, sy, ch in [(cx - 20, cy - 240, "/"), (cx + 30, cy - 270, "*"),
                   (cx + 60, cy - 300, "·"), (cx - 60, cy - 300, "·")]:
    d.text((sx, sy), ch, font=f_sp, fill=DIM)

img = img.resize((512, 512), Image.LANCZOS)
img.save(ASSETS / "seal.png")
print("wrote", ASSETS / "seal.png", img.size)
