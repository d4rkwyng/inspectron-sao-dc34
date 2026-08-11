#!/usr/bin/env python3
"""Deploy firmware to a PRODUCTION INSPECTRON 34 board over the serial REPL,
checksum-verified against real flash — the production-safe sibling of
rigdeploy.py.

WHY A SEPARATE TOOL (Aug 4, 2026): rigdeploy.py is for the DEV RIG. It plants
`/rigconfig.py` with `DEV_RIG = True`, which selects the Waveshare Pico-LCD
hat pins. Run against a real board that would drive the WRONG SPI/button/LED
pins -> black screen. This tool does the opposite: it REMOVES any rigconfig.py
so `from rigconfig import DEV_RIG` fails and DEV_RIG defaults to False
(production pins per pins.md), and it writes the mandatory two-line
`code.py` -> `import app` loader (the precompiled-boot scheme needs it; the
repo's full code.py must never land on the drive AS code.py or the on-device
compile shatters the heap -> first-GIF MemoryError).

What it deploys (serial, device-side checksum-verified): the five code
modules as .mpy (app<-code.py, ui, tuner, fbdraw, secrets_config) + the
code.py stub. Optionally the st7789 lib with --lib. It does NOT transfer the
GIF packs (12 MB over REPL base64 is impractical) — copy /memes and /secret
to the drive normally, then this tool verifies they are present.

Usage (from repo root, board on /dev/cu.usbmodem*, filesystem writable —
i.e. CIRCUITPY drive NOT mounted, or bootstrapped per rigdeploy's hint):
    python3 firmware/deploy_production.py
    python3 firmware/deploy_production.py --lib ~/Downloads/adafruit_st7789.mpy
    python3 firmware/deploy_production.py --no-reset

Requires mpy-cross matching CircuitPython 10.2.1 on PATH or at MPY_CROSS
(rigdeploy auto-fetches it). Copy the CircuitPython 10.x UF2 + the 10.x
adafruit_st7789.mpy into /lib + the GIF packs BEFORE running this.
"""

import argparse
import base64
import glob
import os
import sys

# reuse the rig tool's TESTED serial machinery (same directory)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rigdeploy import Rig, build, deploy, MODULES


def _write_text(rig, path, text):
    """Write a small TEXT file to the drive and verify it device-side."""
    b64 = base64.b64encode(text.encode()).decode()
    rig.buf = b""
    rig.send('import binascii', 0.3)
    rig.send('g = open("%s", "wb"); '
             'g.write(binascii.a2b_base64("%s")); g.close()' % (path, b64), 0.6)
    rig.send('__import__("os").sync()', 0.4)
    rig.send('print("TVRFY", __import__("os").stat("%s")[6], '
             'sum(open("%s","rb").read()))' % (path, path), 1.0)
    got = rig.expect("TVRFY ")
    want = "TVRFY %d %d" % (len(text.encode()), sum(text.encode()))
    if got != want:
        raise RuntimeError("stub verify failed for %s: %s != %s"
                           % (path, got, want))
    print("wrote %s: flash-verified (%d bytes)" % (path, len(text.encode())))


def _remove(rig, path):
    rig.send('try:\r __import__("os").remove("%s")\r'
             ' print("RM-OK")\rexcept OSError:\r print("RM-NONE")\r' % path, 0.8)
    verdict = rig.expect("RM-")
    print("%s: %s" % (path, "removed" if "RM-OK" in verdict else "absent (ok)"))


def _check(rig, expr, label, timeout=5.0):
    rig.buf = b""
    rig.send('try:\r print("CK %s", (%s))\rexcept Exception as e:\r'
             ' print("CK %s ERR", e)\r' % (label, expr, label), 0.8)
    line = rig.expect("CK %s" % label, timeout=timeout)
    print("  %s" % line)
    # a check fails on an exception (ERR) OR an in-band failure token — the
    # expr must emit WARN/EMPTY for the not-quite-exceptional bad states, or
    # the check would pass on any string (a bug the first cut had).
    return line is not None and not any(k in line
                                        for k in ("ERR", "WARN", "EMPTY"))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lib", metavar="PATH",
                    help="local adafruit_st7789.mpy (10.x) to serial-deploy "
                         "into /lib and checksum-verify")
    ap.add_argument("--no-reset", action="store_true")
    args = ap.parse_args()

    names = list(MODULES)                 # all five code modules
    blobs = build(names)

    ports = glob.glob("/dev/cu.usbmodem*")
    if not ports:
        sys.exit("no /dev/cu.usbmodem* — is the board plugged in?")
    rig = Rig(ports[0])
    print("interrupting firmware on %s..." % ports[0])
    rig.interrupt()

    rig.send('import storage', 0.3)
    rig.send('try:\r    storage.remount("/", readonly=False)\r'
             '    print("RW-YES")\rexcept Exception as e:\r'
             '    print("RW-NO", e)\r', 1.0)
    verdict = rig.expect("RW-")
    if "RW-NO" in verdict:
        os.write(rig.fd, b"\x04")          # resume firmware, don't park at REPL
        sys.exit(
            "filesystem is read-only (CIRCUITPY drive mounted): %s\n"
            "Bootstrap once, then re-run:\n"
            "  1. diskutil mount CIRCUITPY\n"
            "  2. printf 'import storage\\nstorage.disable_usb_drive()\\n'"
            " > /Volumes/CIRCUITPY/boot.py && sync\n"
            "  3. diskutil unmount /Volumes/CIRCUITPY\n"
            "  4. reset the board, re-run this tool "
            "(it removes boot.py at the end)" % verdict)

    # 1. the five code modules (.mpy, serial + device-checksum verified)
    for name in names:
        deploy(rig, name, blobs[name])

    # 2. the mandatory production code.py loader (NOT the full program)
    _write_text(rig, "/code.py", "import app\n")

    # 3. PRODUCTION PINS: ensure no rigconfig.py -> DEV_RIG defaults False
    _remove(rig, "/rigconfig.py")

    # 4. optional: serial-deploy the st7789 lib so we KNOW it landed (10.x)
    if args.lib:
        data = open(args.lib, "rb").read()
        rig.send('import os\rtry:\r os.mkdir("/lib")\rexcept OSError:\r pass\r', 0.5)
        deploy(rig, "lib/adafruit_st7789", data)   # writes /lib/adafruit_st7789.mpy

    # 5. bootstrap cleanup (if a boot.py was planted for the RO bypass)
    rig.send('import os\rif "boot.py" in os.listdir("/"):\r'
             '    os.remove("/boot.py")\r    os.sync()\r'
             '    print("BOOTSTRAP-REMOVED")\r\r', 1.0)

    # 6. pre-flight the things that silently black-screen a board
    print("pre-flight checks:")
    ok_lib = _check(rig, '__import__("adafruit_st7789") and "st7789-import-OK"',
                    "LIB")
    # mpy ABI: a .mpy built by the wrong mpy-cross version checksum-verifies
    # byte-perfect but raises ValueError at import -> black screen. Import the
    # four LIBRARY modules (a wrong ABI throws here); app.mpy shares their ABI
    # but runs main() on import, so the leaves are the proxy for it.
    ok_abi = _check(rig, '[__import__(m) for m in '
                    '("secrets_config","fbdraw","tuner","ui")] and "mpy-ABI-OK"',
                    "ABI", timeout=8.0)
    # production pins: rigconfig.py must be ABSENT (listdir returns the FULL
    # name "rigconfig.py" — the old check compared bare "rigconfig" and could
    # never trip, so a DEV_RIG=True board would ship with Waveshare pins)
    ok_dev = _check(rig, '"pins-production" if "rigconfig.py" not in '
                    '__import__("os").listdir("/") else "WARN-DEV-RIG-pins"', "DEV")
    ok_mem = _check(rig, '(lambda n: "memes=%d" % n if n > 0 else "EMPTY-memes")'
                    '(len([f for f in __import__("os").listdir("/memes") '
                    'if f.endswith(".gif")]))', "MEMES")
    ok_sec = _check(rig, '(lambda n: "secret=%d" % n if n > 0 else "EMPTY-secret")'
                    '(len([f for f in __import__("os").listdir("/secret") '
                    'if f.endswith(".gif")]))', "SECRET")
    print("pre-flight: lib=%s abi=%s pins=%s memes=%s secret=%s"
          % (ok_lib, ok_abi, ok_dev, ok_mem, ok_sec))
    if not (ok_lib and ok_abi and ok_dev and ok_mem and ok_sec):
        print("  !! PRE-FLIGHT FAILED — do NOT trust this board:")
        if not ok_lib:
            print("     - st7789 lib missing/incompatible: copy the 10.x "
                  "adafruit_st7789.mpy into /lib (or pass --lib)")
        if not ok_abi:
            print("     - a module .mpy failed to import (wrong mpy-cross ABI?) "
                  "-> it would black-screen at boot")
        if not ok_dev:
            print("     - rigconfig.py present -> DEV_RIG=True -> WRONG PINS "
                  "(Waveshare, not production). Remove /rigconfig.py.")
        if not ok_mem:
            print("     - /memes is empty -> no channels")
        if not ok_sec:
            print("     - /secret is empty -> every puzzle payoff shows TAPE "
                  "NOT ON FILE")

    if not args.no_reset:
        rig.send('import microcontroller')
        rig.send('microcontroller.reset()')
        print("reset sent — board is rebooting into the production build")


if __name__ == "__main__":
    main()
