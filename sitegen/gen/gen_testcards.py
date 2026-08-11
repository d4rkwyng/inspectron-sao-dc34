#!/usr/bin/env python3
"""lineage.png — CF-06 exhibit: triptych of three original test-card
pastiches in succession order, each carrying its single large letter
(C, F, W). Original artwork; era styling only, no third-party imagery.
The years appear in the page text, not here. No digits on the image."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PW, PH, GAP = 420, 560, 26
W, H = PW * 3 + GAP * 4, PH + GAP * 2
OUT = Path(__file__).resolve().parents[2] / 'site' / 'assets' / "lineage.png"
CB = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"

img = Image.new("RGB", (W, H), (6, 8, 6))
d = ImageDraw.Draw(img)
f_letter = ImageFont.truetype(CB, 150)
f_cap = ImageFont.truetype(CB, 24)


def letter(dd, box, ch, fill, outline=None):
    x0, y0, x1, y1 = box
    tw = dd.textlength(ch, font=f_letter)
    pos = ((x0 + x1 - tw) / 2, (y0 + y1) / 2 - 95)
    if outline:
        for ox, oy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
            dd.text((pos[0] + ox, pos[1] + oy), ch, font=f_letter, fill=outline)
    dd.text(pos, ch, font=f_letter, fill=fill)


def caption(dd, cx, y, text, fill):
    tw = dd.textlength(text, font=f_cap)
    dd.text((cx - tw / 2, y), text, font=f_cap, fill=fill)


# ---- panel 1: CARD C — monochrome circle-and-wedges era ----
p = Image.new("RGB", (PW, PH), (24, 24, 24))
pd = ImageDraw.Draw(p)
cx, cy, r = PW // 2, PH // 2 - 30, 150
for rr in (r, r - 26, r - 52):
    pd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(200, 200, 200), width=3)
for k in range(12):                              # frequency wedge spokes
    import math
    a = math.radians(k * 30)
    pd.line([(cx + (r - 52) * math.cos(a), cy + (r - 52) * math.sin(a)),
             (cx + r * math.cos(a), cy + r * math.sin(a))],
            fill=(160, 160, 160), width=2)
for i in range(8):                               # step wedge
    g = 25 + i * 28
    pd.rectangle([40 + i * 42, PH - 130, 40 + (i + 1) * 42 - 2, PH - 90], fill=(g, g, g))
pd.rectangle([0, 0, PW - 1, PH - 1], outline=(120, 120, 120), width=4)
letter(pd, (0, 0, PW, PH - 60), "C", (235, 235, 235), outline=(24, 24, 24))
caption(pd, PW // 2, PH - 60, "THE FOUNDER", (170, 170, 170))
img.paste(p, (GAP, GAP))

# ---- panel 2: CARD F — colour grid, centre vignette, chalk doodle ----
p = Image.new("RGB", (PW, PH), (28, 30, 34))
pd = ImageDraw.Draw(p)
cols = [(196, 60, 40), (210, 160, 40), (60, 150, 60), (50, 90, 170),
        (150, 60, 150), (60, 160, 160)]
cell = 60
for gy in range(0, PH, cell):                    # colour crosshatch grid
    for gx in range(0, PW, cell):
        pd.rectangle([gx, gy, gx + cell - 3, gy + cell - 3],
                     outline=(214, 214, 214), width=2)
for i, c in enumerate(cols):                     # colour bars top strip
    pd.rectangle([10 + i * 66, 12, 10 + (i + 1) * 66 - 4, 60], fill=c)
cx, cy, r = PW // 2, PH // 2, 128                # centre vignette: blackboard
pd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(230, 226, 214),
           outline=(40, 40, 40), width=4)
pd.rectangle([cx - 86, cy - 62, cx + 86, cy + 52], fill=(28, 60, 40),
             outline=(90, 60, 30), width=6)
pd.line([(cx - 50, cy + 16), (cx - 20, cy - 24), (cx + 10, cy + 16)],
        fill=(235, 235, 225), width=4)           # chalk noughts-and-crosses arc
pd.ellipse([cx + 26, cy - 26, cx + 62, cy + 10], outline=(235, 235, 225), width=4)
pd.rectangle([0, 0, PW - 1, PH - 1], outline=(214, 214, 214), width=4)
letter(pd, (0, PH - 260, PW, PH - 40), "F", (255, 255, 255), outline=(30, 30, 30))
caption(pd, PW // 2, PH - 44, "REIGNED FOR FOUR DECADES", (230, 230, 230))
img.paste(p, (GAP * 2 + PW, GAP))

# ---- panel 3: CARD W — the widescreen heir ----
p = Image.new("RGB", (PW, PH), (10, 10, 14))
pd = ImageDraw.Draw(p)
wy0, wy1 = PH // 2 - 118, PH // 2 + 118          # letterboxed widescreen frame
pd.rectangle([16, wy0, PW - 16, wy1], outline=(220, 220, 220), width=3)
bars = [(230, 230, 230), (220, 200, 40), (60, 200, 200), (70, 190, 70),
        (200, 70, 190), (210, 60, 50), (60, 70, 200)]
bw2 = (PW - 44) / len(bars)
for i, c in enumerate(bars):
    pd.rectangle([22 + int(i * bw2), wy0 + 8, 22 + int((i + 1) * bw2) - 2, wy1 - 60],
                 fill=c)
for gx in range(22, PW - 22, 30):                # convergence ticks
    pd.line([(gx, wy1 - 50), (gx, wy1 - 10)], fill=(150, 150, 150), width=1)
pd.rectangle([0, 0, PW - 1, PH - 1], outline=(120, 120, 130), width=4)
letter(pd, (0, 30, PW, 260), "W", (245, 245, 245), outline=(10, 10, 14))
caption(pd, PW // 2, PH - 60, "THE LAST OF THE LINE", (170, 170, 180))
img.paste(p, (GAP * 3 + PW * 2, GAP))

d = ImageDraw.Draw(img)
for yy in range(0, H, 3):
    d.line([(0, yy), (W, yy)], fill=(0, 0, 0), width=1)

img.save(OUT)
print("wrote", OUT, img.size)
