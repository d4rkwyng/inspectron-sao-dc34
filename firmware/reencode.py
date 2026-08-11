#!/usr/bin/env python3
"""Shrink the device GIF pack in place (desktop tool, not device code).

Measured on this pack (Jul 2026): file size scales with FRAME COUNT — halving
frames cuts a gif to ~55-65% — while palette reduction (128->64) saves nothing
(LZW already eats palette redundancy). So the budget lever is frame rate:

  * big gifs (>= MIN_KB and >= MIN_FRAMES) -> keep every 2nd frame, DOUBLE the
    kept delays (loop length preserved; 12fps -> 6fps broadcast chop)
  * trap gifs (seen once as a gotcha) -> additionally cap the loop at TRAP_S
  * HEROES, small gifs, and short gifs are left untouched
  * everything re-saved with a shared 128-color palette from ALL kept frames

Delays after doubling are ~200ms, inside code.py's FRAME_MIN..FRAME_MAX
playback clamp (0.10-0.22s), so on-device pacing stays honest.

In-place and lossy: originals live in git history — restore any gif with
`git checkout <rev> -- memes/<name>.gif` before re-running with new settings.

Usage:
    python3 firmware/reencode.py            # rewrite memes/ + secret/
    python3 firmware/reencode.py --dry-run  # report only
"""

import argparse
import io
import pathlib

MIN_KB = 150         # smaller files aren't worth touching
MIN_FRAMES = 16      # don't decimate short animations into slideshows
TRAP_S = 3.0         # traps play once; cap their loop
COLORS = 128
STEP = 2

# gifs whose joke needs smooth motion: listed by stem, kept at full rate.
# (none by default — add e.g. "matrix" and rerun; restore from git first.)
HEROES = set()

# play-once gotcha channels — MUST mirror the gif stems in
# sitegen/gen_secrets.py TRAP_FREQS (hand-copied: gen_secrets holds
# plaintext answers and must never be imported by shipped tooling paths)
TRAPS = {"nogod67", "weed420", "spyvsspy", "dickbutt", "rickroll",
         "paperwork", "movedon"}


STAMP = b"INSP34-REENC"   # GIF comment marking an already-processed file:
                          # makes the pass idempotent (a second run would
                          # otherwise halve the frames AGAIN)


def reencode(path, dry):
    from PIL import Image, ImageSequence
    orig = path.stat().st_size
    im = Image.open(path)
    n = getattr(im, "n_frames", 1)
    stamped = im.info.get("comment", b"").startswith(STAMP)
    # The Jul 2026 laptop pack rebuild produced 240x135 LANDSCAPE gifs; the
    # direct-render firmware needs 134x240 portrait (convert.py recipe:
    # even width, ROTATE_90). Found on the rig Jul 21: landscape files
    # shear through the portrait CASET/RASET window. Fix geometry here,
    # stamped or not — correctness, not optimization.
    rotate = im.size == (240, 135)
    shrink = (not stamped and path.stem not in HEROES
              and orig >= MIN_KB * 1024 and n >= MIN_FRAMES)
    if not rotate and not shrink:
        return orig, orig, "kept"
    step = STEP if shrink else 1
    cap_ms = TRAP_S * 1000 if (shrink and path.stem in TRAPS) else None
    frames, durs = [], []
    for i, f in enumerate(ImageSequence.Iterator(im)):
        if i % step:
            continue
        d = (f.info.get("duration", 100) or 100) * step
        if cap_ms and sum(durs) + d > cap_ms:
            break
        fr = f.convert("RGB")
        if rotate:              # 240x135 -> 240x134 (EVEN width) -> 134x240
            # CROP one row, don't resize: interpolation smears the already-
            # quantized palette into LZW-hostile noise (measured: resize
            # bloated the pack 11.6 -> 18.2MB; crop keeps it flat)
            fr = fr.crop((0, 0, 240, 134)).transpose(Image.ROTATE_90)
        frames.append(fr)
        durs.append(d)
    w, h = frames[0].size
    tall = Image.new("RGB", (w, h * len(frames)))
    for i, fr in enumerate(frames):
        tall.paste(fr, (0, i * h))
    pal = tall.quantize(colors=COLORS, method=Image.MEDIANCUT)
    q = [fr.quantize(palette=pal, dither=Image.NONE) for fr in frames]
    buf = io.BytesIO()
    q[0].save(buf, format="GIF", save_all=True, append_images=q[1:], loop=0,
              duration=durs, disposal=2, optimize=False, comment=STAMP)
    data = buf.getvalue()
    # <10% win isn't worth halving the frames — unless we're fixing
    # orientation, which ships regardless of size
    if not rotate and len(data) >= orig * 0.9:
        return orig, orig, "kept (no win)"
    if not dry:
        path.write_bytes(data)
    note = f"{n}fr -> {len(q)}fr" + (" +portrait" if rotate else "")
    return orig, len(data), note


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("dirs", nargs="*", default=["memes", "secret"])
    args = ap.parse_args()
    total_before = total_after = 0
    for d in args.dirs or ["memes", "secret"]:
        for p in sorted(pathlib.Path(d).glob("*.gif")):
            before, after, note = reencode(p, args.dry_run)
            total_before += before
            total_after += after
            if note != "kept":
                print(f"  {p}: {before//1024}KB -> {after//1024}KB  {note}")
    print(f"pack: {total_before/1e6:.2f}MB -> {total_after/1e6:.2f}MB"
          f"{'  (dry run)' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
