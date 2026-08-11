#!/usr/bin/env python3
"""Prep GIFs for the INSPECTRON 34 Meme TV SAO (direct-render firmware).

Produces device-ready frames for the fbdraw/direct-bus.send playback path:
  * resized to 240x134 landscape (134 is EVEN -> after rotate the row width is
    4-byte aligned; an ODD width makes displayio pad rows and the frame shears)
  * rotated to 134x240 portrait (ROTATE_90) so the native-portrait N114 panel,
    mounted landscape, shows the meme upright
  * quantized to a 128-color palette built from ALL frames (so colors that only
    appear mid-animation, e.g. TMNT masks, survive), no dither (clean flats)
  * disposal=2 full frames (gifio.OnDiskGif needs whole frames), loop=0

Usage:
    python3 convert.py input.gif [input2.gif ...] -o memes/
    python3 convert.py https://media.tenor.com/.../thing.gif -o memes/
    python3 convert.py -m manifest.txt -o memes/
    python3 convert.py --maxframes 14 big.gif -o memes/   # cap frames to save space
    python3 convert.py clip.mp4 -o secret/                 # video needs ffmpeg

GIF/image inputs use PIL only (no ffmpeg). Video inputs (mp4/webm/...) are
decoded to frames with ffmpeg first, then run through the same PIL pipeline.

ORIENTATION NOTE: ROTATE_90 was calibrated on the Waveshare dev-rig mount.
Verify on the first-article production board; if upside-down flip the firmware
display rotation 0<->180, if mirrored/sideways change ROTATE here 90<->270.
"""

import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile
import urllib.request

# Landscape working size. HEIGHT must be EVEN (see docstring). 240x134 ~= the
# 240x135 panel (1px trimmed for alignment; imperceptible, prevents shear).
SRC_W, SRC_H = 240, 134
ROTATE = "ROTATE_90"        # PIL transpose used to make frames upright; see note
COLORS = 128
FRAME_MIN_MS = 80           # floor per-frame delay (RP2040 can't go faster cleanly)


def _pil():
    from PIL import Image, ImageSequence
    return Image, ImageSequence


def _load_frames(src, maxframes):
    """Return (frames_as_portrait_RGB, per_frame_durations_ms)."""
    Image, ImageSequence = _pil()
    im = Image.open(src)
    n = getattr(im, "n_frames", 1)
    step = 1 if (not maxframes or n <= maxframes) else -(-n // maxframes)
    frames, durs = [], []
    for i, f in enumerate(ImageSequence.Iterator(im)):
        if i % step:
            continue
        if maxframes and len(frames) >= maxframes:
            break
        # a kept frame stands in for `step` originals — scale its delay so the
        # loop keeps its real duration (10-of-40 frames at raw 100ms played 4x
        # fast; playback clamps to FRAME_MAX anyway, so long delays are safe)
        durs.append(max(FRAME_MIN_MS, (f.info.get("duration", 100) or 100) * step))
        rgb = f.convert("RGB").resize((SRC_W, SRC_H), Image.BILINEAR)
        frames.append(rgb.transpose(getattr(Image, ROTATE)))   # -> 134x240
    return frames, durs


def _quantize_all(frames, colors=COLORS):
    """Shared palette (default 128 colors) from ALL frames, no dither."""
    Image, _ = _pil()
    w, h = frames[0].size
    tall = Image.new("RGB", (w, h * len(frames)))
    for i, fr in enumerate(frames):
        tall.paste(fr, (0, i * h))
    pal = tall.quantize(colors=colors, method=Image.MEDIANCUT)
    return [fr.quantize(palette=pal, dither=Image.NONE) for fr in frames]


def _ffmpeg_to_gif(src, tmp, fps, seconds):
    """Video -> a plain GIF PIL can iterate (frames only; palette done later)."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("video input needs ffmpeg (brew install ffmpeg)")
    out = tmp / (src.stem + "_raw.gif")
    subprocess.run(
        ["ffmpeg", "-y", "-t", str(seconds), "-i", str(src),
         "-vf", f"fps={fps}", "-loop", "0", str(out)],
        check=True, capture_output=True)
    return out


def convert(src, out_dir, maxframes, fps, seconds, name=None, tmp=None, colors=None):
    stem = name or src.stem.lower().replace(" ", "_").replace("_raw", "")
    dst = out_dir / (stem + ".gif")
    if src.suffix.lower() in (".mp4", ".webm", ".mov", ".mkv", ".gifv"):
        src = _ffmpeg_to_gif(src, tmp, fps, seconds)
    frames, durs = _load_frames(src, maxframes)
    if not frames:
        raise RuntimeError("no frames decoded")
    q = _quantize_all(frames, colors or COLORS)
    for f in q:                     # Pillow bug: a TUPLE 'transparency' in
        f.info.pop("transparency", None)   # frame info hits `t & 0xFF` in the
        f.info.pop("background", None)     # GIF writer -> TypeError (giphy
    q[0].save(dst, save_all=True, append_images=q[1:], loop=0,
              duration=durs, disposal=2, optimize=False)
    verify(dst)


def verify(dst):
    Image, ImageSequence = _pil()
    img = Image.open(dst)
    delays = [f.info.get("duration", 0) for f in ImageSequence.Iterator(img)]
    n = len(delays)
    w, h = img.size
    ok = (w == SRC_H and h == SRC_W and w % 2 == 0)   # expect 134x240, even width
    kb = dst.stat().st_size // 1024
    print(f"  {dst.name}: {n} frames  {w}x{h}"
          f"{' OK' if ok else ' WRONG SIZE/ODD WIDTH!'}  {kb}KB"
          f"  delays {min(delays)}-{max(delays)}ms")
    if kb > 400:
        print(f"    SIZE: {kb}KB is on the large side. The stock pack leaves"
              f" well under 1MB free on the drive — aim for <=400KB per gif:"
              f" try --maxframes 12, --colors 64, or a shorter clip. (Or"
              f" delete a stock meme from /memes to make room; every gif on"
              f" the drive becomes a channel, community drops show as"
              f" CH 100+ on firmware V4+.)")


def fetch(url, tmp):
    name = url.split("/")[-1].split("?")[0] or "download.gif"
    dst = tmp / name
    print(f"  fetching {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r, open(dst, "wb") as f:
        f.write(r.read())
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="*")
    ap.add_argument("-m", "--manifest", type=pathlib.Path,
                    help="text file: one 'URL_or_path [output_name]' per line")
    ap.add_argument("-o", "--out", type=pathlib.Path, default=pathlib.Path("memes"))
    ap.add_argument("--colors", type=int, default=0,
                    help="palette size (default 128; 64 saves ~30%% for more frames)")
    ap.add_argument("--maxframes", type=int, default=0,
                    help="cap frames (0 = keep all; use e.g. 14 for the 2MB dev rig)")
    ap.add_argument("--fps", type=int, default=12, help="video decode fps")
    ap.add_argument("--seconds", type=float, default=6.0, help="max video length")
    args = ap.parse_args()

    try:
        import PIL  # noqa
    except ImportError:
        sys.exit("needs Pillow — pip install pillow")

    jobs = []
    if args.manifest:
        for raw in args.manifest.read_text().splitlines():
            line = raw.strip()
            if line and not line.startswith("#"):
                parts = line.split()
                jobs.append((parts[0], parts[1] if len(parts) > 1 else None))
    jobs += [(s, None) for s in args.inputs]
    if not jobs:
        sys.exit("nothing to do: pass files/URLs or --manifest FILE")

    args.out.mkdir(parents=True, exist_ok=True)
    print(f"Converting {len(jobs)} item(s) -> {SRC_H}x{SRC_W} ({ROTATE}, {COLORS}-color):")
    ok = fail = 0
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        for s, name in jobs:
            try:
                p = fetch(s, tmp) if s.startswith(("http://", "https://")) else pathlib.Path(s)
                convert(p, args.out, args.maxframes, args.fps, args.seconds, name, tmp,
                        colors=args.colors or None)
                ok += 1
            except Exception as e:
                print(f"  SKIP {s}: {e}")
                fail += 1
    print(f"done: {ok} converted, {fail} skipped")


if __name__ == "__main__":
    main()
