#!/usr/bin/env python3
"""Deploy firmware to the dev rig over the SERIAL REPL — checksummed
against real flash (desktop tool; stdlib only, no pyserial).

WHY THIS EXISTS (Jul 22, 2026): copying .mpy files onto the CIRCUITPY
drive from macOS silently failed — the Mac's page cache accepted the
write and read it back (md5 "verified"!) while the device's flash kept
the old bytes. The rig ran stale UI for hours while every Mac-side check
passed. This tool writes through the CircuitPython REPL instead and
verifies length + checksum + a marker read from the DEVICE's own
filesystem. Trust device-side reads only.

Usage:
    python3 firmware/rigdeploy.py                 # build + deploy the four
                                                  # firmware modules
    python3 firmware/rigdeploy.py ui              # just one module
    python3 firmware/rigdeploy.py --no-reset      # skip the final reset

Requires: mpy-cross matching the rig's CircuitPython on PATH or at
MPY_CROSS; the rig on /dev/cu.usbmodem*. If the filesystem is read-only
(USB drive attached), the tool walks the one-boot bootstrap for you:
it needs the CIRCUITPY volume mounted once to plant boot.py.

code.py on the rig stays the two-line `import app` loader; code.py from
this repo compiles to app.mpy.
"""

import argparse
import base64
import glob
import os
import pathlib
import subprocess
import sys
import termios
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODULES = {"app": "code.py", "ui": "ui.py",
           "tuner": "tuner.py", "fbdraw": "fbdraw.py",
           "secrets_config": "secrets_config.py"}   # ship .mpy: on-device
           # compile of the hash table fragments the heap like everything else
MPY_CROSS = os.environ.get("MPY_CROSS", "mpy-cross")


class Rig:
    def __init__(self, port, settle_s=15):
        # the port node can exist while the device is still re-enumerating
        # after a reset — retry until it accepts termios setup
        end = time.monotonic() + settle_s
        while True:
            try:
                self.fd = os.open(port,
                                  os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
                termios.tcgetattr(self.fd)
                break
            except OSError:
                try:
                    os.close(self.fd)
                except Exception:
                    pass
                if time.monotonic() >= end:
                    raise
                time.sleep(1.0)
        attrs = termios.tcgetattr(self.fd)
        attrs[0] = attrs[1] = attrs[3] = 0          # raw
        attrs[2] |= termios.CLOCAL | termios.CREAD
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        self.buf = b""

    def send(self, line, wait=0.15):
        data = line.encode() + b"\r"
        while data:                       # O_NONBLOCK: retry partial/EAGAIN
            try:
                n = os.write(self.fd, data)
                data = data[n:]
            except BlockingIOError:
                self.drain()              # relieve backpressure, then retry
                time.sleep(0.02)
        time.sleep(wait)
        self.drain()

    def drain(self):
        try:
            while True:
                chunk = os.read(self.fd, 4096)
                if not chunk:
                    break
                self.buf += chunk
        except BlockingIOError:
            pass

    def expect(self, marker, timeout=5.0):
        """Wait for marker in output; return the full line containing it."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.drain()
            for ln in self.buf.decode("utf-8", "replace").splitlines():
                if marker in ln and not ln.lstrip().startswith((">>>", "...")):
                    return ln.strip()
            time.sleep(0.1)
        raise TimeoutError("no %r in rig output; tail: %r"
                           % (marker, self.buf[-200:]))

    def interrupt(self):
        os.write(self.fd, b"\x03")
        time.sleep(1.5)
        os.write(self.fd, b"\r")
        time.sleep(1.0)
        self.drain()
        self.buf = b""


def build(names):
    out = {}
    for name in names:
        # relative path, cwd=ROOT: mpy-cross bakes the source path string
        # into the output, so absolute paths make byte-sizes machine-
        # dependent and break checksum comparisons across checkouts
        dst = ROOT / "firmware" / (".rigdeploy-%s.mpy" % name)
        subprocess.run([MPY_CROSS, "firmware/" + MODULES[name],
                        "-o", str(dst)], check=True, cwd=str(ROOT))
        out[name] = dst.read_bytes()
        dst.unlink()
        print("built %s.mpy: %d bytes" % (name, len(out[name])))
    return out


def deploy(rig, name, data):
    b64 = base64.b64encode(data).decode()
    rig.buf = b""
    rig.send('f = open("/x.b64", "w")', 0.3)
    for i in range(0, len(b64), 120):
        rig.send('f.write("%s")' % b64[i:i + 120], 0.09)
    rig.send("f.close()", 1.0)
    # the close() flush can stall the REPL for a while on FAT-over-flash;
    # handshake before sending more or the next lines get dropped
    rig.send('print("SYNCA")', 0.3)
    rig.expect("SYNCA", timeout=12.0)
    rig.send('d = __import__("binascii").a2b_base64(open("/x.b64").read())', 0.5)
    rig.send('print("CHK", len(d), sum(d))', 0.5)
    got = rig.expect("CHK ", timeout=15.0)
    want = "CHK %d %d" % (len(data), sum(data))
    if got != want:
        raise RuntimeError("transfer mismatch: %s != %s" % (got, want))
    rig.send('g = open("/%s.mpy", "wb"); g.write(d); g.close()' % name, 0.5)
    rig.send('__import__("os").remove("/x.b64")')
    # a stale source .py SHADOWS the .mpy (CircuitPython imports .py first),
    # re-introducing the on-device compile we ship .mpy to avoid.
    # SINGLE-LINE exec form: the multi-line try/except left the REPL stuck in
    # an unclosed continuation block (no blank line to close it) and swallowed
    # every later command — first-article deploy failure, Aug 4.
    rig.send("exec(\"try:\\n __import__('os').remove('/%s.py')\\n"
             "except OSError:\\n pass\")" % name)
    rig.send('__import__("os").sync()', 0.5)
    # verify from the DEVICE's own filesystem — the whole point
    rig.send('print("VRFY", __import__("os").stat("/%s.mpy")[6], '
             'sum(open("/%s.mpy", "rb").read()))' % (name, name), 1.0)
    got = rig.expect("VRFY ")
    want = "VRFY %d %d" % (len(data), sum(data))
    if got != want:
        raise RuntimeError("flash verify failed: %s != %s" % (got, want))
    print("deployed %s.mpy: flash-verified (%d bytes, sum %d)"
          % (name, len(data), sum(data)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("modules", nargs="*", default=list(MODULES),
                    help="modules to deploy (default: all four)")
    ap.add_argument("--no-reset", action="store_true")
    args = ap.parse_args()
    names = args.modules or list(MODULES)
    for n in names:
        if n not in MODULES:
            sys.exit("unknown module %r (choose from %s)" % (n, list(MODULES)))
    blobs = build(names)

    ports = glob.glob("/dev/cu.usbmodem*")
    if not ports:
        sys.exit("no /dev/cu.usbmodem* — is the rig plugged in?")
    rig = Rig(ports[0])
    print("interrupting firmware on %s..." % ports[0])
    rig.interrupt()

    rig.send('import storage', 0.3)
    rig.send('try:\r    storage.remount("/", readonly=False)\r'
             '    print("RW-YES")\rexcept Exception as e:\r'
             '    print("RW-NO", e)\r', 1.0)
    verdict = rig.expect("RW-")
    if "RW-NO" in verdict:
        # resume the firmware before bailing — leaving the board parked at
        # the REPL freezes the display on its last frame (rig report)
        os.write(rig.fd, b"\x04")
        sys.exit(
            "filesystem is read-only (USB drive attached): %s\n"
            "Run the one-boot bootstrap, then re-run this tool:\n"
            "  1. diskutil mount CIRCUITPY\n"
            "  2. printf 'import storage\\nstorage.disable_usb_drive()\\n'"
            " > /Volumes/CIRCUITPY/boot.py && sync\n"
            "  3. diskutil unmount /Volumes/CIRCUITPY\n"
            "  4. reset the board (this tool's final step removes boot.py"
            " and restores the drive)" % verdict)

    for name in names:
        deploy(rig, name, blobs[name])

    # the rig identifies itself via /rigconfig.py (DEV_RIG defaults False
    # in the repo so production boards can never ship with rig pins)
    rig.send('g = open("/rigconfig.py", "w"); g.write("DEV_RIG = True\\n"); '
             'g.close(); __import__("os").sync()', 0.6)

    # clean up a bootstrap boot.py if one is present, then reset
    rig.send('import os\rif "boot.py" in os.listdir("/"):\r'
             '    os.remove("/boot.py")\r    os.sync()\r'
             '    print("BOOTSTRAP-REMOVED")\r\r', 1.0)
    if not args.no_reset:
        rig.send('import microcontroller')
        rig.send('microcontroller.reset()')
        print("reset sent — rig is rebooting into the new build")


if __name__ == "__main__":
    main()
