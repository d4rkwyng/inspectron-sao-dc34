#!/usr/bin/env python3
"""intrusion-still.png — CF-05 exhibit: heavily glitched CRT still of a
masked figure behind venetian-blind stripes. Original pastiche — no
likeness of the actual 1987 footage, no digits anywhere. Composition nods
at the iconic look (rounded mask, dark glasses band, fixed grin) for
people who already know, informative to no one who doesn't.
Palette-quantized + restrained noise to stay well under 150 KB (the first
cut was 1.1 MB of incompressible noise — 46% of the whole site)."""
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 800, 600
OUT = Path(__file__).resolve().parents[2] / 'site' / 'assets' / "intrusion-still.png"
CB = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"
rng = random.Random(11)          # seed is aesthetic only

img = Image.new("RGB", (W, H), (8, 8, 10))
d = ImageDraw.Draw(img)

# venetian-blind background: alternating warm/dark horizontal slats
for i, y in enumerate(range(0, H, 32)):
    warm = (88, 76, 54) if i % 2 == 0 else (26, 22, 20)
    jitter = rng.randint(-3, 3)
    d.rectangle([0, y + jitter, W, y + 22 + jitter], fill=warm)

# masked figure: rounded pale mask, dark glasses band, fixed grin
cx, cy = W // 2 - 24, H // 2 - 46
d.ellipse([cx - 92, cy - 122, cx + 92, cy + 96], fill=(168, 150, 122))    # mask
d.ellipse([cx - 92, cy - 122, cx + 92, cy + 96], outline=(60, 48, 38), width=5)
d.polygon([(cx - 190, H), (cx - 118, cy + 62), (cx + 118, cy + 62),
           (cx + 190, H)], fill=(14, 12, 12))                             # suit
d.rectangle([cx - 26, cy + 62, cx + 26, cy + 96], fill=(150, 132, 106))   # neck
d.rounded_rectangle([cx - 66, cy - 52, cx + 66, cy - 12], radius=16,
                    fill=(18, 14, 14))                                    # glasses
d.line([(cx - 92, cy - 34), (cx - 120, cy - 44)], fill=(18, 14, 14), width=9)
d.line([(cx + 92, cy - 34), (cx + 120, cy - 44)], fill=(18, 14, 14), width=9)
d.arc([cx - 46, cy - 12, cx + 46, cy + 54], 20, 160,
      fill=(74, 52, 40), width=7)                                         # grin
for gx in range(cx - 30, cx + 31, 12):                                    # teeth
    d.line([(gx, cy + 34), (gx, cy + 46)], fill=(74, 52, 40), width=3)

a = np.asarray(img, dtype=np.int16)

# horizontal tear bands: rows shifted sideways — kept off the face band
# so the figure stays legible; one mild tear crosses it for authenticity
face = (cy - 130, cy + 100)
placed = 0
while placed < 8:
    y0 = rng.randrange(H - 30)
    if face[0] - 20 < y0 < face[1]:
        continue
    band = rng.randrange(8, 26)
    a[y0:y0 + band] = np.roll(a[y0:y0 + band], rng.randrange(-60, 60), axis=1)
    placed += 1
a[cy - 8:cy + 2] = np.roll(a[cy - 8:cy + 2], 18, axis=1)

# RGB channel offset (chroma smear)
a[:, :, 0] = np.roll(a[:, :, 0], 4, axis=1)
a[:, :, 2] = np.roll(a[:, :, 2], -5, axis=1)

# broadcast noise — restrained amplitude so the PNG stays compressible
noise = np.random.default_rng(87).integers(-10, 10, size=a.shape)
a = np.clip(a + noise, 0, 255).astype(np.uint8)
img = Image.fromarray(a)

# rolling brightness bar + scanlines
d = ImageDraw.Draw(img, "RGBA")
d.rectangle([0, 168, W, 232], fill=(255, 255, 255, 24))
for yy in range(0, H, 3):
    d.line([(0, yy), (W, yy)], fill=(0, 0, 0, 110))

# monitor burn-in caption, no digits
f = ImageFont.truetype(CB, 26)
d.text((22, H - 46), "SIGNAL LOST // SIGNAL SEIZED", font=f, fill=(57, 255, 20, 200))

img = img.filter(ImageFilter.GaussianBlur(0.5))
img = img.quantize(colors=40, method=Image.MEDIANCUT, dither=Image.FLOYDSTEINBERG)
img.save(OUT, optimize=True)
print("wrote", OUT, img.size, OUT.stat().st_size, "bytes")
