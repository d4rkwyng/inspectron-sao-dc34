#!/usr/bin/env python3
"""form-345.png — 1200px-wide photocopied government form for
'Form 345 — Notice of Type Acceptance'. Exact body text per spec.
No frequency appears anywhere (the answer lives in the device EEPROM)."""
import random
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1200, 900
OUT = Path(__file__).resolve().parents[2] / 'site' / 'assets' / "form-345.png"
COURIER = "/System/Library/Fonts/Supplemental/Courier New.ttf"
COURIER_B = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"

rng = random.Random(345)
img = Image.new("L", (W, H), 235)
d = ImageDraw.Draw(img)

# photocopy grime: noise + vertical streaks + edge shadow
for _ in range(14000):
    x, y = rng.randrange(W), rng.randrange(H)
    d.point((x, y), fill=rng.randrange(170, 232))
for _ in range(10):
    x = rng.randrange(W)
    d.line([(x, 0), (x + rng.randrange(-8, 8), H)], fill=rng.randrange(200, 225), width=1)
d.rectangle([0, 0, W - 1, 14], fill=140)
d.rectangle([0, H - 10, W - 1, H - 1], fill=150)

# double border
d.rectangle([28, 34, W - 28, H - 26], outline=20, width=3)
d.rectangle([40, 46, W - 40, H - 38], outline=20, width=1)

f_hdr = ImageFont.truetype(COURIER_B, 34)
f_sub = ImageFont.truetype(COURIER_B, 22)
f_body = ImageFont.truetype(COURIER, 26)
f_small = ImageFont.truetype(COURIER, 19)

def center(y, text, font, fill=15):
    tw = d.textlength(text, font=font)
    d.text(((W - tw) / 2, y), text, font=font, fill=fill)

center(70, "INSPECTRON BROADCAST AUTHORITY", f_hdr)
center(112, "TYPE ACCEPTANCE DIVISION", f_sub)
center(142, "NOTICE OF TYPE ACCEPTANCE", f_sub)
d.line([(60, 178), (W - 60, 178)], fill=20, width=2)

# form number, upper corner
d.rectangle([W - 250, 56, W - 60, 100], outline=20, width=2)
d.text((W - 236, 66), "FORM IBA-345", font=f_sub, fill=15)

body = ("NOTICE TO LICENSEES. Every receiver manufactured under Authority "
        "contract carries its type-acceptance plate at the standard address. "
        "The plate is read, never written. The maker's mark is LIFE; the set "
        "answers to its name. Present your apparatus for inspection and state "
        "the address for the record -- the Authority speaks decimal.")
y = 220
for line in textwrap.wrap(body, width=62):
    d.text((90, y), line, font=f_body, fill=25)
    y += 40
y += 24
center(y, "VOID WHERE SIGNAL PROHIBITED", f_sub, fill=25)
y += 70

# perforated divider + checkbox admin junk for flavor (no digits)
d.line([(60, y), (W - 60, y)], fill=90, width=1)
y += 26
for label in ("[ ] PLATE PRESENT", "[X] PLATE LEGIBLE", "[ ] CHANNEL VERIFIED"):
    d.text((110, y), label, font=f_small, fill=60)
    y += 30
d.text((640, y - 90), "EXAMINER: ______________________", font=f_small, fill=60)
d.text((640, y - 60), "STATION:  ______________________", font=f_small, fill=60)
d.text((640, y - 30), "DATE:     ______________________", font=f_small, fill=60)

# footer small print (exact spec text)
center(H - 90, "Inspection port: see chassis markings SDA / SCL / GND.", f_small, fill=45)

# rubber stamp, rotated, faded ink
stamp = Image.new("L", (760, 220), 255)
sd = ImageDraw.Draw(stamp)
sd.rectangle([4, 4, 755, 215], outline=0, width=6)
sf1 = ImageFont.truetype(COURIER_B, 42)
sf2 = ImageFont.truetype(COURIER_B, 34)
sd.text((60, 45), "INSPECTRON BROADCAST", font=sf1, fill=0)
sd.text((60, 115), "AUTHORITY — TYPE", font=sf2, fill=0)
sd.text((60, 158), "ACCEPTANCE DIVISION", font=sf2, fill=0)
stamp = stamp.rotate(-7, expand=True, fillcolor=255)
mask = stamp.point(lambda v: 255 - v)
# break up the ink like a real stamp
mrng = random.Random(7)
mpx = mask.load()
for yy in range(mask.height):
    for xx in range(0, mask.width, 2):
        if mrng.random() < 0.28:
            mpx[xx, yy] = 0
ink = Image.new("L", mask.size, 105)  # mid-grey "red ink photocopied to grey"
img.paste(ink, (350, 455), mask)

img = img.filter(ImageFilter.GaussianBlur(0.5))
img.convert("RGB").save(OUT)
print("wrote", OUT, img.size)
