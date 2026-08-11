#!/usr/bin/env bash
# Flash ALL RP2-Boot boards currently plugged in, in parallel.
# Plug 1..N blank boards (all showing bootloader), then run this.
set -uo pipefail
LOG=/tmp/inspectron-factory.log
exec > >(tee -a "$LOG") 2>&1
echo "[$(date +%H:%M:%S)] ── golden-flash-multi ──"
S="$HOME/Downloads"
IMG="$S/golden-inspectron34-v4.uf2"

# discover bus/address pairs for every RP2 Boot device via ioreg
PAIRS=$(python3 - <<'PY'
import subprocess, re, json
out = subprocess.run(["ioreg","-p","IOUSB","-l","-w0"],capture_output=True,text=True).stdout
pairs=[]
blocks = out.split("+-o ")
for b in blocks:
    if b.startswith("RP2 Boot"):
        addr = re.search(r'"USB Address" = (\d+)', b)
        loc  = re.search(r'"locationID" = (\d+)', b)
        if addr and loc:
            bus = (int(loc.group(1)) >> 24) & 0xFF
            pairs.append((bus, int(addr.group(1))))
for bus,a in pairs: print(f"{bus} {a}")
PY
)
if [ -z "$PAIRS" ]; then echo "no RP2 Boot devices found"; exit 1; fi
N=$(echo "$PAIRS" | wc -l | xargs)
echo "found $N bootloader device(s)"
# jobs must start in THIS shell (not a piped subshell) or wait can't see them
while read -r BUS ADDR; do
  (
    if picotool load -v --bus "$BUS" --address "$ADDR" "$IMG" 2>&1 | tail -1 | grep -q OK; then
      picotool reboot --bus "$BUS" --address "$ADDR" >/dev/null 2>&1 || true
      echo "  [slot $BUS:$ADDR] DONE ✅"
    else
      echo "  [slot $BUS:$ADDR] FAILED — retry this one solo"
    fi
  ) &
done <<< "$PAIRS"
wait
echo "ALL SLOTS FINISHED — watch for splashes"
