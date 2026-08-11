#!/bin/bash
# finalize (zones + stitching) -> DRC -> renders
set -uo pipefail
cd "$(dirname "$0")"
PY="$HOME/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3"
CLI="$HOME/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"

echo "== finalize (zones + stitch) =="
PYTHONFAULTHANDLER=1 "$PY" -u gen_pcb.py --final 2>&1 | grep -vE 'Debug:|memory leak' | tail -3

echo "== DRC =="
"$CLI" pcb drc --severity-error --format report --output drc.txt dc34-sao.kicad_pcb 2>/dev/null
grep -E 'Found|violations|unconnected' drc.txt | head -5

echo "== renders =="
"$CLI" pcb render --side top --zoom 0.9 --output render-front.png dc34-sao.kicad_pcb 2>/dev/null
"$CLI" pcb render --side bottom --zoom 0.9 --output render-back.png dc34-sao.kicad_pcb 2>/dev/null
ls -la render-*.png 2>/dev/null
echo done
