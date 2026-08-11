#!/usr/bin/env python3
"""Generate the custom trap-channel GIFs (HANDOFF task 3) — tiny in-fiction
denial cards rendered with the firmware's own 5x7 font (extracted from
firmware/fbdraw.py so the look matches the device UI exactly).

  secret/paperwork.gif  -> trap 345.0  (CF-02's form number, dialed hopefully:
                           form 345 is a FORM, not a frequency)
  secret/movedon.gif    -> trap 009.0  (CF-05: the intruder hit ch 9 first —
                           wrong station, he moved on)

Filenames carry no digits (the /secret listing is visible to anyone who
mounts the drive); the numbers appear only in CONTENT, which you only see
after dialing them. Output is the device recipe: 240x134 landscape frames
rotated to 134x240 portrait, few colors, small (~5-10KB each).

Rerun after edits; no re-wiring needed (paths stay stable); the
channel mapping lives in gen_secrets.py TRAP_FREQS.
"""

import ast
import pathlib
import re

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent

# borrow the firmware font so the cards look native
_src = (ROOT / "firmware" / "fbdraw.py").read_text()
_m = re.search(r"_FONT=\{(.*?)\n\}", _src, re.S)
FONT = ast.literal_eval("{" + _m.group(1) + "}")

AMBER = (255, 176, 0)
GREEN = (0, 255, 90)
RED = (255, 40, 40)
GREY = (120, 120, 120)
NAVY = (10, 14, 44)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


def text(img, x, y, s, color, scale=1):
    p = img.load()
    for ch in s:
        g = FONT.get(ch.upper())
        if g:
            for ry in range(7):
                for rx in range(5):
                    if g[ry] & (0x10 >> rx):
                        for a in range(scale):
                            for b in range(scale):
                                px_, py_ = x + rx * scale + a, y + ry * scale + b
                                if 0 <= px_ < img.width and 0 <= py_ < img.height:
                                    p[px_, py_] = color
        x += 6 * scale


def center(img, y, s, color, scale):
    text(img, (img.width - len(s) * 6 * scale) // 2, y, s, color, scale)


def frame(bg=NAVY):
    return Image.new("RGB", (240, 134), bg)


def save(path, frames, delays):
    frames = [f.transpose(Image.ROTATE_90).quantize(colors=16) for f in frames]
    frames[0].save(path, save_all=True, append_images=frames[1:], loop=0,
                   duration=delays, disposal=2, optimize=True)
    print(f"  {path} ({path.stat().st_size // 1024}KB, {len(frames)} frames)")


def paperwork():
    frames, delays = [], []
    for blink in (True, False, True, False, True, True):
        f = frame(NAVY)
        for yy in (2, 130):
            for xx in range(0, 240, 12):
                text(f, xx, yy, "-", AMBER, 1)
        center(f, 12, "BROADCAST AUTHORITY", AMBER, 2)
        center(f, 34, "LICENSING DIVISION", GREY, 1)
        center(f, 52, "FORM 345", WHITE, 3)
        if blink:
            center(f, 84, "IS A FORM.", GREEN, 2)
            center(f, 102, "NOT A FREQUENCY.", GREEN, 2)
        else:
            center(f, 84, "RESUBMIT IN", GREY, 2)
            center(f, 102, "TRIPLICATE.", GREY, 2)
        frames.append(f)
        delays.append(700)
    save(ROOT / "secret" / "paperwork.gif", frames, delays)


def movedon():
    frames, delays = [], []
    for i in range(6):
        f = frame(BLACK)
        # sparse static
        import random
        random.seed(i * 7)
        p = f.load()
        for _ in range(260):
            p[random.randrange(240), random.randrange(134)] = \
                WHITE if random.random() < 0.8 else GREY
        center(f, 14, "CH 009", GREEN, 3)
        if i % 2:
            center(f, 56, "WRONG STATION.", RED, 2)
            center(f, 78, "HE MOVED ON.", WHITE, 2)
        else:
            center(f, 56, "WRONG STATION.", WHITE, 2)
            center(f, 78, "HE MOVED ON.", GREY, 2)
        center(f, 112, "KEEP LOOKING", GREY, 1)
        frames.append(f)
        delays.append(450)
    save(ROOT / "secret" / "movedon.gif", frames, delays)


if __name__ == "__main__":
    paperwork()
    movedon()
