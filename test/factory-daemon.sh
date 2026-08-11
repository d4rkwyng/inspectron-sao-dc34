#!/usr/bin/env bash
# INSPECTRON 34 mass-flash daemon. Flashes EVERY board that appears in
# BOOTSEL with $IMG, in parallel (one job per device), forever.
# Operator loop: hold BOOT + plug (up to 3 boards on separate ports),
# wait for splash, unplug, next. Watch /tmp/inspectron-factory.log.
set -u
IMG="${IMG:?set IMG=/path/to/golden.uf2}"
LOG=/tmp/inspectron-factory.log
LOCKS=/tmp/.flashlocks; mkdir -p "$LOCKS"
echo "[$(date +%H:%M:%S)] ── factory-daemon up (image: $(basename "$IMG")) ──" | tee -a "$LOG"
while true; do
  ioreg -p IOUSB -l -w0 2>/dev/null | python3 -c '
import sys, re
out = sys.stdin.read()
for b in out.split("+-o "):
    if b.startswith("RP2 Boot"):
        a = re.search(r"\"USB Address\" = (\d+)", b)
        l = re.search(r"\"locationID\" = (\d+)", b)
        if a and l:
            print(f"{(int(l.group(1))>>24)&0xFF} {a.group(1)}")
' | while read -r BUS ADDR; do
    L="$LOCKS/$BUS-$ADDR"
    if mkdir "$L" 2>/dev/null; then
      (
        echo "[$(date +%H:%M:%S)] [port $BUS:$ADDR] flashing..." >> "$LOG"
        if picotool load -v --bus "$BUS" --address "$ADDR" "$IMG" > "$LOCKS/$BUS-$ADDR.out" 2>&1 && grep -q OK "$LOCKS/$BUS-$ADDR.out"; then
          picotool reboot --bus "$BUS" --address "$ADDR" >/dev/null 2>&1
          echo "[$(date +%H:%M:%S)] [port $BUS:$ADDR] DONE ✅ — watch the splash, swap the board" >> "$LOG"
        else
          echo "[$(date +%H:%M:%S)] [port $BUS:$ADDR] FAILED ✗ — replug that board" >> "$LOG"
        fi
        sleep 8
        rmdir "$L" 2>/dev/null
      ) &
    fi
  done
  sleep 3
done
