#!/usr/bin/env bash
# INSPECTRON 34 — one-pass factory flash (boards #4+, first-picture-blessed
# firmware). Single plug-in per board:
#
#   1. plug a BLANK board in (RP2 Boot appears)   -> bash test/factory-flash.sh
#   2. script: picotool-flash CP -> wait CIRCUITPY -> copy EVERYTHING
#      (payload + blessed .mpy set from firmware/dist/mpy + code.py stub)
#      -> device-side file verify -> reset into the firmware
#   3. watch the splash come up, unplug, next board.
#
# The .mpy set is the STAGED, first-picture-verified build (regenerate with
# the loop in the repo docs if firmware changes — then re-verify on one board
# before batching). Serial verify catches macOS page-cache fakery.
set -euo pipefail
cd "$(dirname "$0")/.."
LOG=/tmp/inspectron-factory.log
exec > >(tee -a "$LOG") 2>&1
echo; echo "[$(date +%H:%M:%S)] ── factory-flash: new board ──"
S="$HOME/Downloads"
UF2="${UF2:-$HOME/Downloads/cp-yd16.uf2}"
[ -f "$UF2" ] || { echo "!! CircuitPython UF2 not found: $UF2"; echo "   download 'CircuitPython 10.2.1 for VCC-GND YD-RP2040 (16MB)' from circuitpython.org/board/vcc_gnd_yd_rp2040/ and save it there (or set UF2=/path)"; exit 1; }
ST7789="${ST7789:-firmware/dist/lib/adafruit_st7789.mpy}"

echo "=== 1/4 bootloader ==="
# Gate on ioreg, NOT `picotool info` — info segfaults on this Mac while the
# device settles; `picotool load` itself works. Retry load a few times.
FLASHED=no
for i in 1 2 3 4 5; do
  if ioreg -p IOUSB -w0 2>/dev/null | grep -q "RP2 Boot"; then
    if picotool load "$UF2" 2>&1 | tail -1 | grep -q "100%"; then
      picotool reboot >/dev/null 2>&1 || true
      echo "CircuitPython flashed"
      FLASHED=yes; break
    fi
    echo "load attempt $i failed — retrying"
  elif [ -d /Volumes/CIRCUITPY ] || ls /dev/cu.usbmodem* >/dev/null 2>&1; then
    echo "already running CircuitPython — skipping flash"; FLASHED=skip; break
  fi
  sleep 2
done
if [ "$FLASHED" = "no" ]; then
  echo "no board visible / load failed — replug (or hold BOOT while plugging)"; exit 1
fi

echo "=== 2/4 waiting for CIRCUITPY ==="
for i in $(seq 90); do [ -d /Volumes/CIRCUITPY ] && break; sleep 1; done
[ -d /Volumes/CIRCUITPY ] || { echo "no CIRCUITPY after 90s"; exit 1; }

echo "=== 3/4 payload + firmware (one pass) ==="
mkdir -p /Volumes/CIRCUITPY/lib /Volumes/CIRCUITPY/memes /Volumes/CIRCUITPY/secret
cp "$ST7789" /Volumes/CIRCUITPY/lib/adafruit_st7789.mpy
cp firmware/splash.gif /Volumes/CIRCUITPY/
cp firmware/dist/mpy/*.mpy /Volumes/CIRCUITPY/
printf 'import app\n' > /Volumes/CIRCUITPY/code.py
cp memes/*.gif /Volumes/CIRCUITPY/memes/
cp secret/*.gif /Volumes/CIRCUITPY/secret/
dot_clean -m /Volumes/CIRCUITPY 2>/dev/null || true
sync
echo "copied: $(ls /Volumes/CIRCUITPY/memes/*.gif | wc -l | xargs) memes, $(ls /Volumes/CIRCUITPY/secret/*.gif | wc -l | xargs) secret"
diskutil unmount CIRCUITPY | tail -1

echo "=== 4/4 byte-verify (remount, no replug) ==="
python3 test/verify-board.py "board"
