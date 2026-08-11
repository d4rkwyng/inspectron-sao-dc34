#!/usr/bin/env python3
"""Generate tiny test GIFs (PIL only).

sim/memes/  (regular channels, on-device /memes):
- channel1.gif: full-screen color-cycling bars with a moving block.
(All gifs are saved 134x240 PORTRAIT — the device recipe: even-width
landscape frame rotated 90deg, matching firmware/convert.py.)
- channel2.gif: 120x68 (tests the firmware's centering math) bouncing box.

sim/secret/ (hidden channels, on-device /secret — see secrets_config.py):
- offgrid.gif, deadair.gif, agency.gif, konami.gif: purple pulse cards, so
  the tuner/konami unlock paths have something real to play.
"""

import os

from PIL import Image, ImageDraw

SIM_DIR = os.path.dirname(os.path.abspath(__file__))
MEMES_DIR = os.path.join(SIM_DIR, "memes")
SECRET_DIR = os.path.join(SIM_DIR, "secret")

# 20ms/frame keeps the headless selftest quick.
FRAME_MS = 20


def make_channel1(path):
    frames = []
    colors = [(255, 0, 0), (255, 160, 0), (255, 255, 0), (0, 255, 0),
              (0, 200, 255), (0, 0, 255), (200, 0, 255), (255, 255, 255)]
    n = 12
    for f in range(n):
        img = Image.new("RGB", (240, 134), (0, 0, 0))
        d = ImageDraw.Draw(img)
        bar_w = 240 // len(colors)
        for i, c in enumerate(colors):
            d.rectangle([i * bar_w, 0, (i + 1) * bar_w - 1, 134],
                        fill=colors[(i + f) % len(colors)])
        x = int(f * (240 - 40) / (n - 1))
        d.rectangle([x, 50, x + 40, 90], fill=(0, 0, 0))
        d.rectangle([x + 4, 54, x + 36, 86], fill=(255, 255, 255))
        frames.append(img)
    frames = [f.transpose(Image.ROTATE_90) for f in frames]
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=FRAME_MS, loop=0)


def make_channel2(path):
    frames = []
    n = 10
    for f in range(n):
        img = Image.new("RGB", (120, 68), (10, 10, 60))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 119, 67], outline=(255, 255, 0))
        y = int(abs((f % (2 * (n // 2))) - n // 2) * 40 / (n // 2))
        d.ellipse([48 + f, 8 + y, 68 + f, 28 + y], fill=(255, 60, 60))
        d.line([0, 60, 119, 60], fill=(0, 255, 0), width=3)
        frames.append(img)
    frames = [f.transpose(Image.ROTATE_90) for f in frames]
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=FRAME_MS, loop=0)


def make_secret(path, label_rgb):
    """Pulsing 'secret station' card with a distinctive corner color."""
    frames = []
    n = 8
    for f in range(n):
        v = 40 + int(abs((f % n) - n / 2) * 40)
        img = Image.new("RGB", (240, 134), (v, 0, v))
        d = ImageDraw.Draw(img)
        d.rectangle([8, 8, 231, 126], outline=(255, 0, 255), width=2)
        d.rectangle([16, 16, 48, 48], fill=label_rgb)
        d.line([20, 100, 220, 100 - f * 6], fill=(255, 255, 255), width=2)
        frames.append(img)
    frames = [f.transpose(Image.ROTATE_90) for f in frames]
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=FRAME_MS, loop=0)


def main():
    os.makedirs(MEMES_DIR, exist_ok=True)
    os.makedirs(SECRET_DIR, exist_ok=True)
    written = []
    for name, fn in (("channel1.gif", make_channel1),
                     ("channel2.gif", make_channel2)):
        p = os.path.join(MEMES_DIR, name)
        fn(p)
        written.append(p)
    for name, rgb in (("offgrid.gif", (255, 255, 0)),
                      ("deadair.gif", (0, 255, 255)),
                      ("agency.gif", (255, 128, 0)),
                      ("konami.gif", (0, 255, 0))):
        p = os.path.join(SECRET_DIR, name)
        make_secret(p, rgb)
        written.append(p)
    print("wrote:\n  " + "\n  ".join(written))


if __name__ == "__main__":
    main()
