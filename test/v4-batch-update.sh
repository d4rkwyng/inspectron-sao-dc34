#!/usr/bin/env bash
# INSPECTRON 34 — batch firmware updater to FW V4 (macOS).
# Watches for CIRCUITPY drives (several at once is fine), copies the five
# precompiled .mpy onto each, remounts to defeat the write cache, verifies
# sha256 against flash, and ejects on success. Safe to leave running.
#
#   bash test/v4-batch-update.sh          # foreground
#   LOG=/tmp/v4.log bash test/v4-batch-update.sh &   # then: tail -f /tmp/v4.log
#
# A board is only touched if its app.mpy differs from the blessed build in
# firmware/dist/mpy — already-updated boards are skipped silently.
set -u
cd "$(dirname "$0")/.."
SRC=firmware/dist/mpy
LOG=${LOG:-/tmp/inspectron34-v4-update.log}
FILES=(app ui tuner fbdraw secrets_config)

say() { echo "[$(date '+%T')] $*" | tee -a "$LOG"; }

for f in "${FILES[@]}"; do
  [ -f "$SRC/$f.mpy" ] || { say "FATAL: missing $SRC/$f.mpy — build first"; exit 1; }
done
WANT=$(shasum -a 256 "$SRC/app.mpy" | cut -d' ' -f1)
say "daemon up — blessed app.mpy ${WANT:0:12}… — plug boards in"

while true; do
  for V in /Volumes/CIRCUITPY*; do
    [ -e "$V/code.py" ] || continue
    N=$(basename "$V")
    CUR=$(shasum -a 256 "$V/app.mpy" 2>/dev/null | cut -d' ' -f1)
    [ "$CUR" = "$WANT" ] && continue          # already V4
    STUB=$(head -c 20 "$V/code.py" 2>/dev/null | tr -d '[:space:]')
    [ "$STUB" = "importapp" ] || { say "$N: SKIP — code.py is not the import-app stub!"; continue; }
    say "$N: updating…"
    ok=1
    for f in "${FILES[@]}"; do cp "$SRC/$f.mpy" "$V/" || ok=0; done
    sync
    DEV=$(diskutil info "$V" | awk -F': *' '/Device Node/{print $2}')
    diskutil unmount "$DEV" >/dev/null 2>&1
    diskutil mount "$DEV" >/dev/null 2>&1
    sleep 1
    MP=$(diskutil info "$DEV" | awk -F': *' '/Mount Point/{print $2}')
    [ -n "$MP" ] || { say "$N: ERROR — did not remount, retrying next pass"; continue; }
    for f in "${FILES[@]}"; do
      S=$(shasum -a 256 "$SRC/$f.mpy" | cut -d' ' -f1)
      D=$(shasum -a 256 "$MP/$f.mpy" 2>/dev/null | cut -d' ' -f1)
      [ "$S" = "$D" ] || { ok=0; say "$N: VERIFY FAIL on $f.mpy"; }
    done
    if [ $ok = 1 ]; then
      sync; diskutil eject "$DEV" >/dev/null 2>&1
      say "$N: ✅ V4 verified + ejected — unplug, next board"
    else
      say "$N: ❌ left mounted for inspection (re-plugging retries)"
    fi
  done
  sleep 2
done
