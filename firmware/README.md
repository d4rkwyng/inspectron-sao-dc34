# DC34 Meme TV SAO — Firmware

CircuitPython GIF player. The SAO mounts as a USB drive (`CIRCUITPY`) —
drop `.gif` files into `/memes` and they become channels.

## Controls
- **CH+ / CH−**: next / previous meme (with TV-static transition)
- **MODE** short press: cycle brightness (60% → 30% → 85%)
- **MODE** hold 1s: MASTER CONTROL menu (guide / case files / tuner /
  settings). **CH+ & CH− held together** also opens it.
- **CH− held alone 2.5s**: standby (screen off); any button wakes.
  **CH+ held alone 2.5s**: auto-scan on/off.

## Install (PRECOMPILED — .mpy is MANDATORY, not an optimization)
On-device compilation of the full `code.py`+`tuner.py` fragments the RP2040
heap before boot and the first GIF dies with `MemoryError` — this bites the
16 MB production board exactly as it bit the 2 MB rig. So the drive gets a
two-line `code.py` loader (`import app`) plus the real program as `.mpy`.
**Use the deploy tool — it builds the `.mpy` set and verifies every write
against real flash (macOS page cache has silently faked CIRCUITPY writes):**

```bash
# dev rig  (Waveshare hat pins; plants rigconfig.py DEV_RIG=True)
python3 firmware/rigdeploy.py
# production board  (pins.md pins; DEV_RIG=False; writes the import-app stub)
python3 firmware/deploy_production.py --lib ~/Downloads/adafruit_st7789.mpy
```

Manual steps the tool assumes you did first:
1. Hold BOOT while plugging USB → `RPI-RP2` drive → copy the **CircuitPython
   10.2.1** 16 MB UF2 (Pico-pin-compatible build) → `CIRCUITPY` appears.
2. Copy the **CircuitPython 10.x** `adafruit_st7789.mpy` into `/lib`
   (a 9.x `.mpy` raises `ValueError` at boot → black screen), OR pass it to
   the deploy tool with `--lib`.
3. Copy the repo's `/memes` and `/secret` folders onto the drive (GIF packs
   are too large for the serial deploy path; ~14.8 MB of the 15.7 MB
   partition).
4. `secrets_config.py` is **generated** — regenerate via
   `python3 sitegen/gen_secrets.py`, never hand-edit; the deploy tool ships it.

## Prepping memes
```
brew install ffmpeg
python3 convert.py your-meme.gif -o /Volumes/CIRCUITPY/memes/
```
Anything ffmpeg reads works as input (GIF, mp4, webm...). Output is
**134x240 portrait** (even width), ≤6 s, 128-color palette from all frames,
`disposal=2` — the exact recipe the direct-render engine needs. A `240x135`
landscape GIF shears into half-screen garbage on the panel.

## Dev rig
Raspberry Pi Pico + generic 1.14" ST7789 240x135 breakout, wired per
`pins.md` GP numbers. Power the rig from a bench supply / 2xAA at **3.0V**
into VSYS and measure current: must stay under ~80mA worst case
(spec budget is 100mA across both badge SAO ports).
