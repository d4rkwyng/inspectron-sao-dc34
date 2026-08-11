#!/usr/bin/env python3
"""Generate /splash.gif — the INSPECTRON 34 boot ident.

Designed in LANDSCAPE (240x134, how the panel reads) then ROTATE_90 to the
134x240 portrait the direct-render firmware needs (same recipe as convert.py:
even width, <=128-color palette from all frames, disposal=2). Small on purpose
(the dev rig has ~50KB free): a short static-burst -> phosphor-logo reveal.

    python3 firmware/gen_splash.py [out.gif]
"""
import sys
from PIL import Image, ImageDraw, ImageFont

W, H = 240, 134                      # landscape design canvas
OUT = sys.argv[1] if len(sys.argv) > 1 else "splash.gif"

# Theme variants (SETTINGS "THEME"): main text / dim rule / accent block.
# Keep in step with fbdraw._THEMES — the boot peek picks the file by the
# theme byte (code.py), so each variant must exist on the drive root.
THEMES = {
    "default": ((60, 226, 44), (26, 120, 20), (240, 180, 41)),
    "dc34":    ((60, 226, 44), (26, 120, 20), (170, 90, 240)),
    "inv":     ((240, 180, 41), (120, 90, 20), (60, 226, 44)),
}
GREEN, DIMG, AMBER = THEMES["default"]
BG = (4, 8, 4)


def _font(sz):
    for p in ("/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
              "/System/Library/Fonts/Menlo.ttc",
              "/Library/Fonts/Courier New.ttf"):
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            pass
    return ImageFont.load_default()


F_BIG = _font(30)
F_SUB = _font(13)
F_TINY = _font(11)


def _center(d, y, text, font, fill):
    b = d.textbbox((0, 0), text, font=font)
    d.text(((W - (b[2] - b[0])) // 2, y), text, font=font, fill=fill)


def _base(scanlines=True):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    if scanlines:
        for y in range(0, H, 3):
            d.line([(0, y), (W, y)], fill=(0, 0, 0))
    return img, d


def _static_frame(seed):
    # cheap deterministic snow (no RNG import needed for determinism)
    img, d = _base(scanlines=False)
    x = seed * 2654435761 & 0xFFFFFFFF
    for _ in range(1400):
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        px = x % W
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        py = x % H
        g = 90 + (x % 130)
        d.point((px, py), fill=(g, g, g))
    return img


def _logo_frame(bright=1.0, tag=0):
    img, d = _base()
    g = tuple(min(255, int(c * bright)) for c in GREEN)
    _center(d, 14, "INSPECTRON", F_BIG, g)
    _center(d, 48, "█ 34 █", F_BIG, AMBER)
    d.line([(30, 92), (W - 30, 92)], fill=DIMG)
    _center(d, 98, "TUNE YOUR OWN SIGNAL", F_SUB, g)
    _center(d, 116, "BROADCAST AUTHORITY", F_TINY, DIMG)
    # anti-merge tag: 1px at the extreme corner (hidden under the bezel) so PIL
    # can't collapse the identical steady frames into one — else the device's
    # 0.40s frame-clamp would gut the 3s hold into a single flash.
    img.putpixel((0, 0), ((tag * 37) % 256, (tag * 53) % 256, 5))
    return img


def build(out):
    frames = []
    # A. brief sign-on flicker (~0.26s)
    frames.append((_static_frame(1), 130))
    frames.append((_static_frame(2), 130))
    # B. logo holds STEADY ~3.2s (8 frames x 0.40s clamp; unique tags keep
    #    them distinct so the hold survives)
    for i in range(8):
        frames.append((_logo_frame(bright=1.0, tag=i + 3), 400))
    # C. THEN the flashing finale (~1.4s)
    for i in range(6):
        frames.append((_logo_frame(bright=(1.0 if i % 2 == 0 else 0.32),
                                   tag=i + 40), 230))

    # rotate to 134x240 portrait, quantize together to one shared palette
    port = [f.rotate(90, expand=True) for f, _ in frames]
    delays = [d for _, d in frames]
    assert port[0].size == (H, W) == (134, 240), port[0].size

    # shared 128-color palette from all frames (convert.py trick)
    montage = Image.new("RGB", (134, 240 * len(port)))
    for i, p in enumerate(port):
        montage.paste(p, (0, 240 * i))
    pal = montage.quantize(colors=64, dither=Image.NONE)
    q = [p.quantize(colors=64, palette=pal, dither=Image.NONE) for p in port]

    q[0].save(out, save_all=True, append_images=q[1:], loop=0,
              duration=delays, disposal=2, optimize=True,
              comment=b"INSP34-REENC")
    import os
    print("wrote %s: %d frames, %d bytes, %dx%d portrait"
          % (out, len(q), os.path.getsize(out), *q[0].size))


if len(sys.argv) > 1:                # explicit output = default theme only
    build(OUT)
else:                                # no args: emit all three theme variants
    for _name, _suffix in (("default", ""), ("dc34", "-dc34"),
                           ("inv", "-inv")):
        GREEN, DIMG, AMBER = THEMES[_name]
        build("splash%s.gif" % _suffix)
