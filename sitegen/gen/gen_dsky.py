#!/usr/bin/env python3
"""dsky.png — pixel-art Apollo DSKY display panel.
COMP ACTY lamp lit, VERB 16 NOUN 36 (monitor clock time), three registers
showing a mission clock. Drawn at 1x on a coarse grid, upscaled nearest
neighbor. Contains no answer digits."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[2] / 'site' / 'assets' / "dsky.png"
SCALE = 4
W, H = 240, 200  # 1x canvas -> 960x800

PANEL = (52, 54, 50)
PANEL_DK = (38, 40, 37)
BEZEL = (110, 112, 105)
GLASS = (10, 14, 10)
EL = (120, 255, 140)     # lit electroluminescent green
EL_DIM = (17, 28, 18)    # unlit segment ghost
LABEL = (200, 205, 195)

img = Image.new("RGB", (W, H), PANEL)
d = ImageDraw.Draw(img)

# 7-segment definitions: segments a,b,c,d,e,f,g on a wxh cell
SEGS = {
    "0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc",
    "5": "afgcd", "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abfgcd",
    "+": "+", "-": "g", " ": "",
}

def seg(dd, x, y, ch, w=7, h=11, t=2, on=EL):
    lit = SEGS.get(ch, "")
    def L(name, coords):
        col = on if name in lit else EL_DIM
        dd.rectangle(coords, fill=col)
    if lit == "+":
        dd.rectangle([x + w // 2 - 1, y + 2, x + w // 2, y + h - 3], fill=on)
        dd.rectangle([x + 1, y + h // 2 - 1, x + w - 2, y + h // 2], fill=on)
        return
    m = y + h // 2
    L("a", [x + 1, y, x + w - 2, y + t - 1])
    L("f", [x, y + 1, x + t - 1, m - 1])
    L("b", [x + w - t, y + 1, x + w - 1, m - 1])
    L("g", [x + 1, m - 1, x + w - 2, m])
    L("e", [x, m + 1, x + t - 1, y + h - 2])
    L("c", [x + w - t, m + 1, x + w - 1, y + h - 2])
    L("d", [x + 1, y + h - t, x + w - 2, y + h - 1])

def digits(dd, x, y, s, pitch=10, **kw):
    for i, ch in enumerate(s):
        seg(dd, x + i * pitch, y, ch, **kw)

font_path = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"
f_tiny = ImageFont.truetype(font_path, 8)
f_lbl = ImageFont.truetype(font_path, 9)

# outer bezel + screws
d.rectangle([2, 2, W - 3, H - 3], outline=BEZEL, width=2)
for sx, sy in [(6, 6), (W - 8, 6), (6, H - 8), (W - 8, H - 8)]:
    d.ellipse([sx - 2, sy - 2, sx + 2, sy + 2], fill=(20, 20, 20), outline=BEZEL)

# display glass area
d.rectangle([14, 12, W - 15, H - 13], fill=PANEL_DK, outline=BEZEL, width=1)

# --- top row: COMP ACTY lamp (lit) and PROG window
d.rectangle([22, 20, 74, 52], fill=(180, 255, 190), outline=BEZEL, width=1)
d.text((28, 25), "COMP", font=f_tiny, fill=(10, 40, 12))
d.text((28, 37), "ACTY", font=f_tiny, fill=(10, 40, 12))

d.rectangle([158, 18, 222, 24], fill=(0, 0, 0))
d.text((178, 17), "PROG", font=f_tiny, fill=LABEL)
d.rectangle([166, 26, 214, 52], fill=GLASS, outline=BEZEL, width=1)
digits(d, 176, 31, "00", pitch=13, w=9, h=17)

# --- VERB / NOUN row
d.rectangle([22, 62, 74, 68], fill=(0, 0, 0))
d.text((36, 61), "VERB", font=f_tiny, fill=LABEL)
d.rectangle([22, 70, 74, 98], fill=GLASS, outline=BEZEL, width=1)
digits(d, 33, 75, "16", pitch=13, w=9, h=18)

d.rectangle([166, 62, 218, 68], fill=(0, 0, 0))
d.text((180, 61), "NOUN", font=f_tiny, fill=LABEL)
d.rectangle([166, 70, 218, 98], fill=GLASS, outline=BEZEL, width=1)
digits(d, 177, 75, "36", pitch=13, w=9, h=18)

# --- three registers (V16N36: mission clock  hrs / min / 0.01 s)
regs = ["+00013", "+00042", "+02651"]
y0 = 106
for i, r in enumerate(regs):
    y = y0 + i * 30
    d.rectangle([22, y, 222, y + 1], fill=EL)  # green separator bar
    d.rectangle([22, y + 4, 222, y + 26], fill=GLASS, outline=BEZEL, width=1)
    digits(d, 138, y + 6, r, pitch=13, w=9, h=17)
    d.text((28, y + 9), f"R{i+1}", font=f_lbl, fill=LABEL)

img = img.resize((W * SCALE, H * SCALE), Image.NEAREST)

# soft phosphor glow pass on the lit green
from PIL import ImageFilter
glow_src = img.point(lambda v: v)  # copy
mask = Image.eval(img.split()[1], lambda g: 255 if g > 200 else 0).filter(
    ImageFilter.GaussianBlur(6))
green = Image.new("RGB", img.size, (40, 120, 55))
img = Image.composite(Image.blend(img, green, 0.5), img, mask.point(lambda v: min(v, 90)))
img.save(OUT)
print("wrote", OUT, img.size)
assert "2048" not in "".join(regs), "answer leak"
