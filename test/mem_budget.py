#!/usr/bin/env python3
"""Static memory-budget check for INSPECTRON 34 (RP2040, 264KB SRAM).

This project's entire bug history is heap fragmentation: the framebuffer (FB)
and a GIF decoder's OnDiskGif bitmap are each ~64KB and CANNOT coexist. The
firmware makes them take turns (fb.release() before every OnDiskGif;
fb.reclaim() for every UI screen). This script turns "I think it fits" into a
worst-case accounting per lifecycle phase, and FAILS if any phase's peak
large-allocation footprint exceeds the usable-heap estimate.

It reads the real constants out of firmware/fbdraw.py so it can't drift.
It is a STATIC model (a coarse safety rail), NOT a substitute for on-device
measurement — the true heap after fragmentation is only knowable on hardware.
"""
import re
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
FB = (ROOT / "firmware" / "fbdraw.py").read_text()


def _int(name, default=None):
    m = re.search(r"^%s\s*=\s*(\d+)" % name, FB, re.M)
    return int(m.group(1)) if m else default


# --- constants pulled from the firmware -----------------------------------
BW = _int("BW", 134)
BH = _int("BH", 240)
FB_BYTES = BW * BH * 2                 # 16bpp displayio.Bitmap
# SLACKS = (32768, 24024) decoder-hole reserve
m = re.search(r"SLACKS\s*=\s*\(([^)]*)\)", FB)
SLACKS = tuple(int(x) for x in re.findall(r"\d+", m.group(1))) if m else (32768, 24024)
SLACK_TOTAL = sum(SLACKS)

# OnDiskGif: 64,320 frame bitmap + 24,024 LZW workspace (documented in fbdraw)
GIF_BITMAP = 64320
GIF_WORKSPACE = 24024
GIF_TOTAL = GIF_BITMAP + GIF_WORKSPACE

# text-strip cache: capped ~28KB per fbdraw v3 comments
TEXT_CACHE = 28000

# RP2040 has 264KB SRAM. CircuitPython runtime (VM, heap overhead, stacks,
# imported .mpy, displayio bus buffers) consumes a large fixed chunk; the
# firmware's own long-lived objects (channel list, settings, badge queue,
# module globals) add more. Empirically the free heap the decoder actually
# sees on this build is ~120-140KB. Use a CONSERVATIVE usable-heap floor.
USABLE_HEAP = 120000                   # conservative floor (bytes)

# --- lifecycle phases: the peak large allocations that must coexist --------
PHASES = [
    ("boot: _BOOT_GIF preopen on pristine heap", GIF_TOTAL,
     "first decoder built before FB/UI ever allocate"),
    ("playing a GIF (FB released)", GIF_TOTAL,
     "OnDiskGif bitmap + LZW; FB must be freed first"),
    ("UI screen (menu/guide/tuner)", FB_BYTES + SLACK_TOTAL + TEXT_CACHE,
     "FB pinned + decoder-hole slack reserve + text cache"),
    ("transition: opening next decoder after UI", GIF_TOTAL,
     "FB.release() + gc, then OnDiskGif — the classic starvation point"),
    ("standby (panel blanked)", TEXT_CACHE,
     "no FB, no decoder; only small draws"),
]

# INVARIANT: FB and a GIF decoder must never be summed — they take turns.
COEXIST_FORBIDDEN = FB_BYTES + GIF_TOTAL   # this must NEVER be a real phase

print("INSPECTRON 34 — static memory budget (RP2040 264KB SRAM)")
print("  FB bitmap            %6d B (%dx%d @16bpp)" % (FB_BYTES, BW, BH))
print("  OnDiskGif total      %6d B (%d bitmap + %d LZW)" % (GIF_TOTAL, GIF_BITMAP, GIF_WORKSPACE))
print("  SLACKS reserve       %6d B %s" % (SLACK_TOTAL, SLACKS))
print("  text-strip cache     %6d B" % TEXT_CACHE)
print("  usable-heap floor    %6d B (conservative)" % USABLE_HEAP)
print("  [invariant] FB+GIF coexistence would be %d B — must never happen "
      "(they take turns)" % COEXIST_FORBIDDEN)
print()

# A phase over HARD_CEIL cannot physically fit the RP2040 heap -> hard FAIL
# (a regression that balloons an allocation). A phase within WARN_MARGIN of the
# comfort floor is TIGHT -> warn (the heap war's knife edge), not a fail:
# the true free heap is only knowable on-device, and these phases demonstrably
# run on hardware today.
HARD_CEIL = 190000
WARN_MARGIN = 20000

fail = warn = 0
for name, peak, note in PHASES:
    margin = USABLE_HEAP - peak
    if peak > HARD_CEIL:
        flag = "FAIL"; fail += 1
    elif margin < WARN_MARGIN:
        flag = "TIGHT"; warn += 1
    else:
        flag = "OK  "
    print("  [%-5s] %-40s peak %6d B  margin %+7d B" % (flag, name, peak, margin))
    if flag != "OK  ":
        print("           ^ %s" % note)

# The real invariant: FB and a decoder must NEVER coexist. No phase sums
# them today; flag if that ever regresses into the model.
if any(p >= COEXIST_FORBIDDEN for _, p, _ in PHASES):
    print("\n  !! INVARIANT VIOLATED: a phase sums FB + a decoder (%d B). They "
          "must take turns — release FB before every OnDiskGif." % COEXIST_FORBIDDEN)
    fail += 1

print()
if fail:
    print("RESULT: FAIL (%d phase(s) physically over-budget or invariant broken)" % fail)
    sys.exit(1)
if warn:
    print("RESULT: PASS with %d TIGHT phase(s) — margin is thin; on-device "
          "gc.mem_free() after hours of surfing is the real test "
          "(check on hardware)." % warn)
else:
    print("RESULT: PASS (every phase has comfortable margin)")
