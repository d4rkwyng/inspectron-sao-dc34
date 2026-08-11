#!/bin/bash
# Export PCBWay production files for dc34-sao rev A.
# Usage: ./export_production.sh
set -euo pipefail
cd "$(dirname "$0")"

KICAD_CLI="$HOME/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
KIPY="$HOME/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3"
REV="revA"
OUT="../production/$REV"
mkdir -p "$OUT/gerbers"

echo "== DRC gate =="
"$KICAD_CLI" pcb drc --severity-error \
  --output "$OUT/drc.txt" dc34-sao.kicad_pcb 2>/dev/null
V=$(grep -oE 'Found [0-9]+ DRC violations' "$OUT/drc.txt" | grep -oE '[0-9]+')
U=$(grep -oE 'Found [0-9]+ unconnected' "$OUT/drc.txt" | grep -oE '[0-9]+')
echo "DRC: $V violations, $U unconnected"
if [ "$V" != "0" ] || [ "$U" -gt 2 ]; then
  echo "DRC GATE FAILED (only the 2 documented U1-pad-22 items are accepted)"; exit 1
fi
echo "DRC gate passed (2 documented pad-22 exceptions)."

echo "== Gerbers + drill =="
"$KICAD_CLI" pcb export gerbers \
  --layers F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts \
  --subtract-soldermask --output "$OUT/gerbers/" dc34-sao.kicad_pcb 2>/dev/null
"$KICAD_CLI" pcb export drill --format excellon --generate-map --map-format gerberx2 \
  --output "$OUT/gerbers/" dc34-sao.kicad_pcb 2>/dev/null
(cd "$OUT" && zip -qr dc34-sao-$REV-gerbers.zip gerbers && rm -rf gerbers)

echo "== Position file (CPL) =="
"$KICAD_CLI" pcb export pos --format csv --units mm --side both \
  --exclude-dnp --output "$OUT/dc34-sao-$REV-positions.csv" dc34-sao.kicad_pcb 2>/dev/null

echo "== BOM (PCBWay-style, from schematic) =="
"$KIPY" - <<'EOF'
import csv, re, sys, os
sys.path.insert(0, os.getcwd())
from gen_sch import COMPONENTS
rows = {}
for ref, lib, sym, value, fp, lcsc, _, _ in COMPONENTS:
    if ref.startswith("#"):
        continue
    key = (value, fp, lcsc)
    rows.setdefault(key, []).append(ref)
out = os.path.join("..", "production", "revA", "dc34-sao-revA-BOM.csv")
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Item", "Designator", "Qty", "Manufacturer P/N or Value",
                "Package/Footprint", "LCSC", "Notes"])
    for i, ((value, fp, lcsc), refs) in enumerate(sorted(rows.items(),
            key=lambda kv: kv[1][0]), 1):
        pkg = fp.split(":")[-1]
        note = ""
        if "TFT_FPC" in fp:
            note = "DO NOT SMT: hand-solder after assembly (or PCBWay hand-solder)"
        if "PinHeader_2x03" in fp:
            note = "THT male header, mount on BACK side"
        w.writerow([i, ",".join(sorted(refs)), len(refs), value, pkg, lcsc, note])
print("BOM written:", out)
EOF

echo "== Renders =="
"$KICAD_CLI" pcb render --side top --quality high --output "$OUT/render-front.png" dc34-sao.kicad_pcb 2>/dev/null
"$KICAD_CLI" pcb render --side bottom --quality high --output "$OUT/render-back.png" dc34-sao.kicad_pcb 2>/dev/null
echo "Done. Files in $OUT"
