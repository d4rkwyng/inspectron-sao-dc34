"""pytest setup: make the firmware modules importable under desktop CPython.

tuner.py binds `_NVM = microcontroller.nvm` at import. We inject a minimal
in-memory `microcontroller` stub (nvm only) BEFORE any test imports tuner, so
the suite is isolated from the sim's disk-persisting stub (no nvm.bin side
effects). sim/stubs is also on the path for `micropython.const` etc.
"""
import sys
import types
import pathlib

# Cache the STDLIB 'code' (and its importer 'pdb') before firmware/ goes on
# the path: firmware/code.py otherwise shadows them, and pytest's debugging
# plugin does 'import pdb' AFTER conftest loads — which imported the entire
# firmware (code.py runs main() at module level) and hung the whole suite.
import code   # noqa: F401
import pdb    # noqa: F401

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "firmware"))
sys.path.insert(0, str(ROOT / "sim" / "stubs"))

# minimal microcontroller stub (overrides the sim's persisting one)
_mc = types.ModuleType("microcontroller")
_mc.nvm = bytearray(4096)
sys.modules["microcontroller"] = _mc
