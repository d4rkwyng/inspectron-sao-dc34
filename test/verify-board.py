#!/usr/bin/env python3
"""Post-copy byte-verify: remount CIRCUITPY (a clean unmount already flushed
to the device, so a fresh mount re-reads genuine flash) and byte-compare the
staged firmware + stub + counts. No serial, no replug.
Usage: python3 test/verify-board.py [board-label]"""
import os, sys, time, subprocess, filecmp
label = sys.argv[1] if len(sys.argv) > 1 else "board"
for _ in range(15):
    if os.path.isdir("/Volumes/CIRCUITPY"): break
    subprocess.run(["diskutil","mount","CIRCUITPY"],capture_output=True)
    time.sleep(1)
else:
    raise SystemExit("[%s] CIRCUITPY never mounted" % label)
time.sleep(1)
ok = True
for name in ("app.mpy","ui.mpy","tuner.mpy","fbdraw.mpy","secrets_config.mpy"):
    same = filecmp.cmp("firmware/dist/mpy/"+name, "/Volumes/CIRCUITPY/"+name, shallow=False)
    print("  [%s] %-18s %s" % (label, name, "OK" if same else "BYTE MISMATCH")); ok &= same
stub = open("/Volumes/CIRCUITPY/code.py").read().strip() == "import app"
print("  [%s] code.py stub     %s" % (label, "OK" if stub else "WRONG")); ok &= stub
m = len([f for f in os.listdir("/Volumes/CIRCUITPY/memes") if f.endswith(".gif") and not f.startswith("._")])
s2 = len([f for f in os.listdir("/Volumes/CIRCUITPY/secret") if f.endswith(".gif") and not f.startswith("._")])
rig = "rigconfig.py" in os.listdir("/Volumes/CIRCUITPY")
print("  [%s] memes=%d secret=%d rigconfig=%s" % (label, m, s2, rig))
em = len([f for f in os.listdir("memes") if f.endswith(".gif")])
es = len([f for f in os.listdir("secret") if f.endswith(".gif")])
ok &= (m == em and s2 == es and not rig)
print("[%s] %s" % (label, "BOARD PASSED ✅ — splash should be on its screen; unplug, next board"
                   if ok else "!! FAILED byte-verify — set aside"))
sys.exit(0 if ok else 1)
