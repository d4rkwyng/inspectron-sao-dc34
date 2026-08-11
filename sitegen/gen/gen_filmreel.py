#!/usr/bin/env python3
"""mcp-reel.gif — CF-03 exhibit: short engineering-film loop. Film-leader
countdown, then a slow pan across a stylized chip die with a stuttering
FRAME counter. The counter SKIPS values; at each skip a large glitch digit
flashes for exactly one frame — stepping frame-by-frame reveals the model
number one digit at a time (4, 0, 0, 4). No contiguous forbidden digit run
appears in any frame or in the encoded bytes (checked; regenerates with a
new aesthetic seed if the encoding randomly contains one)."""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 480, 360
OUT = Path(__file__).resolve().parents[2] / 'site' / 'assets' / "mcp-reel.gif"
CB = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"

FORBIDDEN = [b"4004", b"400.4", b"0341", b"1993", b"0800", b"1704",
             b"0110", b"0230", b"0660", b"4040"]

GLYPH_AT = {8: "4", 12: "0", 16: "0", 20: "4"}   # pan-frame index -> digit
# counter values: increments that skip over the glitch frames' "lost" count
COUNTER = ["FR %02d" % n for n in
           (1, 2, 3, 5, 6, 7, 9, 10, 11, 13, 14, 15, 17, 18, 19, 21, 22, 23,
            25, 26, 27, 29)]


def build(seed):
    rng = random.Random(seed)
    frames = []
    f_big = ImageFont.truetype(CB, 150)
    f_mid = ImageFont.truetype(CB, 28)
    f_ctr = ImageFont.truetype(CB, 22)

    # --- film leader countdown: 8..5 only (no forbidden digits, classic feel)
    for n in (8, 7, 6, 5):
        img = Image.new("L", (W, H), 180)
        d = ImageDraw.Draw(img)
        d.ellipse([W // 2 - 120, H // 2 - 120, W // 2 + 120, H // 2 + 120],
                  outline=40, width=6)
        d.line([(W // 2, H // 2 - 120), (W // 2, H // 2 + 120)], fill=90, width=3)
        d.line([(W // 2 - 120, H // 2), (W // 2 + 120, H // 2)], fill=90, width=3)
        t = str(n)
        tw = d.textlength(t, font=f_big)
        d.text(((W - tw) / 2, H / 2 - 105), t, font=f_big, fill=20)
        for _ in range(400):
            img.putpixel((rng.randrange(W), rng.randrange(H)), rng.randrange(256))
        frames.append(img.convert("P"))

    # title card
    img = Image.new("L", (W, H), 12)
    d = ImageDraw.Draw(img)
    for i, line in enumerate(("AUTHORITY ENGINEERING FILM",
                              "MASTER CONTROL PROCESSOR", "MAINTENANCE REEL")):
        tw = d.textlength(line, font=f_mid)
        d.text(((W - tw) / 2, 110 + i * 46), line, font=f_mid, fill=200)
    frames.append(img.convert("P"))

    # --- die pan: 22 frames sliding across a fake die shot
    die = Image.new("L", (W * 2, H), 30)
    dd = ImageDraw.Draw(die)
    for _ in range(260):                          # metal traces
        x0 = rng.randrange(W * 2 - 60)
        y0 = rng.randrange(H - 40)
        if rng.random() < 0.5:
            dd.rectangle([x0, y0, x0 + rng.randrange(20, 120), y0 + 3], fill=110)
        else:
            dd.rectangle([x0, y0, x0 + 3, y0 + rng.randrange(16, 80)], fill=95)
    for _ in range(30):                           # bond pads
        x0 = rng.randrange(W * 2 - 40)
        y0 = rng.choice((10, H - 34))
        dd.rectangle([x0, y0, x0 + 26, y0 + 22], fill=170, outline=60)
    for k in range(4):                            # register-file blocks
        x0 = 120 + k * 190
        dd.rectangle([x0, 120, x0 + 120, 240], outline=140, width=3)
        for gy in range(132, 236, 10):
            dd.line([(x0 + 8, gy), (x0 + 112, gy)], fill=70, width=1)

    for i in range(22):
        off = int(i * (W / 21))
        img = die.crop((off, 0, off + W, H)).copy()
        d = ImageDraw.Draw(img)
        if i in GLYPH_AT:                         # the one-frame glitch digit
            g = GLYPH_AT[i]
            for _ in range(1800):
                img.putpixel((rng.randrange(W), rng.randrange(H)), rng.randrange(256))
            tw = d.textlength(g, font=f_big)
            d.text(((W - tw) / 2 + 4, H / 2 - 101), g, font=f_big, fill=0)
            d.text(((W - tw) / 2, H / 2 - 105), g, font=f_big, fill=255)
            d.rectangle([10, H - 42, 150, H - 12], fill=30)
            d.text((18, H - 38), "FR --", font=f_ctr, fill=220)
        else:
            d.rectangle([10, H - 42, 150, H - 12], fill=30)
            d.text((18, H - 38), COUNTER[i], font=f_ctr, fill=220)
        for _ in range(250):
            img.putpixel((rng.randrange(W), rng.randrange(H)), rng.randrange(256))
        frames.append(img.convert("P"))

    from io import BytesIO
    buf = BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:],
                   duration=[450] * 4 + [900] + [260] * 22, loop=0, optimize=True)
    return buf.getvalue()


for seed in range(200):
    data = build(seed)
    if not any(f in data for f in FORBIDDEN):
        OUT.write_bytes(data)
        print("wrote", OUT, len(data), "bytes, seed", seed)
        break
else:
    raise SystemExit("no clean encoding found")
