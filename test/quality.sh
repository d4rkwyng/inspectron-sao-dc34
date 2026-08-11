#!/usr/bin/env bash
# INSPECTRON 34 — one-command quality gate (the fast checks, steps 1-6).
# Fails fast; run from anywhere. The heavier checks (design review, KiCad
# DRC, hardware-in-the-loop) run separately.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=sim/.venv/bin/python
RUFF=sim/.venv/bin/ruff
PYTEST=sim/.venv/bin/pytest
[ -x "$RUFF" ] && [ -x "$PYTEST" ] || { echo "missing dev tools — run: sim/.venv/bin/pip install -r sim/requirements.txt"; exit 1; }
fail=0
step(){ echo; echo "=== $1 ==="; }

step "1/6  syntax compile"
$PY -m py_compile firmware/*.py && echo "OK" || { echo "FAIL"; fail=1; }

step "2/6  lint (ruff: undefined names, dead imports, bug patterns)"
$RUFF check firmware/ deploy/ && echo "OK" || fail=1

step "3/6  firmware logic unit tests (pytest: NVM / settings / hash / boot-peek)"
$PYTEST -q test/ && echo "OK" || fail=1

step "4/6  boot + integration smoke (sim selftest, exit 0)"
rm -f sim/nvm.bin
if SDL_VIDEODRIVER=dummy INSPECTRON_SIM_TESTGIFS=1 $PY sim/run.py --selftest --frames 400 >/tmp/qa_selftest.log 2>&1; then
  echo "OK (exit 0)"
else
  echo "FAIL — tail of /tmp/qa_selftest.log:"; tail -6 /tmp/qa_selftest.log; fail=1
fi

step "5/6  answer-leak gate (site must ship zero answers)"
if $PY sitegen/check_no_answers.py >/tmp/qa_leak.log 2>&1; then
  tail -1 /tmp/qa_leak.log
else
  echo "FAIL:"; tail -4 /tmp/qa_leak.log; fail=1
fi

step "6/6  static memory budget (RP2040 heap phases)"
$PY test/mem_budget.py | tail -3 || fail=1

echo
if [ $fail -eq 0 ]; then
  echo "############  QUALITY GATE: PASS (steps 1-6)  ############"
else
  echo "############  QUALITY GATE: FAIL  ############"
fi
echo "(design review, KiCad ERC/DRC, and hardware bring-up run separately)"
exit $fail
