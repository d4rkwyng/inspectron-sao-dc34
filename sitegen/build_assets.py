#!/usr/bin/env python3
"""Derive the small site assets from the official seal (deterministic).

  site/assets/seal.webp     256x256 retina WebP of seal.png (shown at 122 CSS px)
  site/favicon.ico          16+32(+48) px ICO from the seal
  site/assets/og-share.png  1200x630 share card (seal + wordmark, site palette)
  site/assets/og-share.webp same card, WebP

Only real site assets + the site palette; no answers anywhere. Run before
build_site.py (the committed outputs are normally enough; re-run only if the
seal changes).  Needs Pillow."""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / "site" / "assets"
BG, PH, PH_DIM, LINE = (4, 7, 4), (60, 226, 44), (42, 156, 32), (23, 92, 18)
FONT_DIRS = ["/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
             "/Library/Fonts/Courier New Bold.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"]


def font(size):
    for p in FONT_DIRS:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    raise SystemExit("no monospace bold font found")


def spaced(d, xy, text, f, fill, tracking):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + tracking


def width(d, text, f, tracking):
    return sum(d.textlength(c, font=f) + tracking for c in text) - tracking


seal = Image.open(A / "seal.png").convert("RGBA")

# 1. WebP at 2x display size
seal.resize((256, 256), Image.LANCZOS).save(A / "seal.webp", "WEBP", quality=88, method=6)

# 2. favicon.ico
ico = seal.resize((64, 64), Image.LANCZOS)
ico.save(ROOT / "site" / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])

# 3. share card
W, H = 1200, 630
im = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(im)
d.rectangle([24, 24, W - 25, H - 25], outline=LINE, width=2)
d.rectangle([32, 32, W - 33, H - 33], outline=LINE, width=1)
S = 400
im.paste(seal.resize((S, S), Image.LANCZOS), (90, (H - S) // 2), seal.resize((S, S), Image.LANCZOS))
x0 = 540
f1, f2, f3 = font(68), font(30), font(26)
glow = Image.new("RGB", (W, H), (0, 0, 0))
gd = ImageDraw.Draw(glow)
spaced(gd, (x0, 205), "INSPECTRON 34", f1, (40, 150, 30), 3)
glow = glow.filter(ImageFilter.GaussianBlur(9))
im = ImageChops.add(im, glow)
d = ImageDraw.Draw(im)
spaced(d, (x0, 205), "INSPECTRON 34", f1, PH, 3)
d.line([x0, 312, x0 + 580, 312], fill=LINE, width=2)
spaced(d, (x0, 336), "TUNE YOUR OWN SIGNAL", f2, (240, 180, 41), 9)
spaced(d, (x0, 400), "INSPECTRON BROADCAST AUTHORITY", f3, PH_DIM, 4)
spaced(d, (x0, 440), "A DEF CON 34 SAO PUZZLE", f3, PH_DIM, 4)
# scanlines
sc = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(sc)
for y in range(0, H, 3):
    sd.line([0, y, W, y], fill=(0, 0, 0, 70))
im = Image.alpha_composite(im.convert("RGBA"), sc).convert("RGB")
im.save(A / "og-share.png", optimize=True)
im.save(A / "og-share.webp", "WEBP", quality=85, method=6)
for n in ("seal.webp", "og-share.png", "og-share.webp"):
    print(n, (A / n).stat().st_size)
print("favicon.ico", (ROOT / "site" / "favicon.ico").stat().st_size)
