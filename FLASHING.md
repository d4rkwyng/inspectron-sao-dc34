# Flashing / restoring an INSPECTRON 34

Three paths, easiest first. **You cannot brick it** — the RP2040's ROM
bootloader is permanent; worst case you re-do these steps.

> Adding your own memes needs **no flashing at all**: plug into a computer,
> the `CIRCUITPY` drive appears, drop 134×240 GIFs into `/memes`
> (`firmware/convert.py` preps any GIF/video to the right format).

## 1. Factory restore — the golden image (easiest)

Restores EVERYTHING: firmware, all channel packs, factory-fresh state
(unlock progress and settings are wiped — it's a full-flash image).

1. Download the current golden image, `golden-inspectron34-v5.zip`
   (unzip → the `.uf2`), from [inspectron34.com](https://inspectron34.com)
   or this repo's **[Releases](../../releases)** page
2. **Hold the BOOT button** (back of the board) while plugging into USB —
   a drive named **`RPI-RP2`** appears
3. Drag the `.uf2` onto `RPI-RP2`. The copy takes a few minutes (it's the
   whole 16 MB flash); the board reboots into the splash when done

If `RPI-RP2` never mounts (a few boards have shy USB mass-storage), use
[picotool](https://github.com/raspberrypi/picotool):

```bash
picotool load -v golden-inspectron34-v5.uf2
picotool reboot
```

Repo scripts do the same with retries: `bash test/golden-flash.sh`
(expects the image at `~/Downloads/`, or set `IMG=/path`), or
`bash test/factory-daemon.sh` to batch-flash many boards.

> The `test/*.sh` helper scripts are **macOS-only** (diskutil/ioreg). On
> Linux/Windows use path 1's drag-and-drop or bare `picotool` directly —
> they work everywhere.

## 2. Update just the firmware (keeps your GIFs + unlock progress)

The app ships **precompiled** — five `.mpy` files at the drive root, plus
(from V5) two themed splash GIFs. The blessed set lives in
`firmware/dist/mpy/`; the splash variants are `firmware/splash-dc34.gif`
and `firmware/splash-inv.gif`.

1. Plug in normally → `CIRCUITPY` mounts
2. Copy `firmware/dist/mpy/*.mpy` and the two `splash-*.gif` files onto
   the drive root (replacing any old ones); make sure `code.py` on the
   drive contains exactly `import app`
3. Eject properly, then **unplug/replug** (the firmware disables
   auto-reload — a power cycle boots the new build)

⚠️ Never copy the repo's full `code.py` onto the drive as `code.py`:
compiling it on-device fragments the RP2040 heap and the first GIF dies
with `MemoryError`. The two-line `import app` stub is load-bearing.

## 3. Build firmware from source

```bash
# 1. get mpy-cross matching CircuitPython 10.2.1 (or use firmware/.tools/)
# 2. compile the set
cd firmware
for m in app:code ui:ui tuner:tuner fbdraw:fbdraw secrets_config:secrets_config; do
  mpy-cross ${m##*:}.py -o dist/mpy/${m%%:*}.mpy
done
# 3. deploy per path 2 above, or provision a blank board end-to-end:
#    - flash CircuitPython 10.2.1 for "VCC-GND YD-RP2040" (16MB build,
#      pin-compatible) from circuitpython.org/board/vcc_gnd_yd_rp2040/
#      via RPI-RP2 — save as ~/Downloads/cp-yd16.uf2 for the script
#    - copy firmware/dist/lib/adafruit_st7789.mpy -> /lib
#    - copy memes/ + secret/ + firmware/splash.gif -> drive
#    - copy dist/mpy/*.mpy -> drive root, write code.py = "import app"
bash test/factory-flash.sh   # does all of the provisioning automatically
```

Validate changes before flashing a fleet: `bash test/quality.sh`
(lint + unit tests + boot smoke + answer-leak gate + memory budget), then
bless ON HARDWARE, then capture a new golden image:

```bash
# board in BOOT mode:
picotool save -a golden-new.uf2
```

## Factory reset (no computer needed)

Hold MODE → **SETTINGS** → **FACTORY RST** → MODE (arms, shows `SURE?`) →
MODE again. Wipes unlocks, settings, and resume state, then reboots.
