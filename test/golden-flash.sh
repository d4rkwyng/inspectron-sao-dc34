#!/usr/bin/env bash
# One-command board flash: plug a BLANK board (bootloader auto) -> run this.
# Writes the FULL golden image (firmware + packs + settings-clean FS),
# picotool-verified. ~1-2 min. Splash on screen = done.
set -uo pipefail
LOG=/tmp/inspectron-factory.log
exec > >(tee -a "$LOG") 2>&1
echo "[$(date +%H:%M:%S)] ── golden-flash ──"
IMG="${IMG:-$HOME/Downloads/golden-inspectron34-v5.uf2}"
[ -f "$IMG" ] || { echo "!! image not found: $IMG — download the v4 golden from inspectron34.com or the GitHub release (or set IMG=/path)"; exit 1; }
for i in 1 2 3 4 5; do
  if ioreg -p IOUSB -w0 2>/dev/null | grep -q "RP2 Boot"; then
    if picotool load -v "$IMG" 2>&1 | tail -1 | grep -q "OK"; then
      picotool reboot >/dev/null 2>&1 || true
      echo "BOARD DONE ✅ — watch the splash"
      exit 0
    fi
    echo "attempt $i failed, retrying"
  fi
  sleep 2
done
echo "!! no bootloader / load failed — replug the board"
exit 1
