#!/usr/bin/env bash
# INSPECTRON 34 — per-board provisioning (CircuitPython + lib + packs + code).
# Run AFTER the CircuitPython UF2 is flashed (picotool load cp-yd16.uf2).
#
#   bash test/provision-board.sh
#
# Does: wait for CIRCUITPY -> copy lib + splash + memes/ + secret/ ->
# plant the one-boot bootstrap -> reset. Then REPLUG the board and run:
#   MPY_CROSS=$PWD/firmware/.tools/mpy-cross-10.2.1 python3 firmware/deploy_production.py
# (deploy_production verifies every module device-side + pre-flights.)
set -euo pipefail
cd "$(dirname "$0")/.."
ST7789="${ST7789:-firmware/dist/lib/adafruit_st7789.mpy}"

echo "waiting for CIRCUITPY (60s)..."
for i in $(seq 60); do [ -d /Volumes/CIRCUITPY ] && break; sleep 1; done
[ -d /Volumes/CIRCUITPY ] || { echo "no CIRCUITPY — is CircuitPython flashed?"; exit 1; }
df -h /Volumes/CIRCUITPY | tail -1 | awk '{print "partition:", $2, "(want ~15M)"}'

mkdir -p /Volumes/CIRCUITPY/lib /Volumes/CIRCUITPY/memes /Volumes/CIRCUITPY/secret
cp "$ST7789" /Volumes/CIRCUITPY/lib/adafruit_st7789.mpy && echo "lib ok"
cp firmware/splash.gif /Volumes/CIRCUITPY/ && echo "splash ok"
cp memes/*.gif /Volumes/CIRCUITPY/memes/ && echo "memes done ($(ls /Volumes/CIRCUITPY/memes/*.gif | wc -l | xargs))"
cp secret/*.gif /Volumes/CIRCUITPY/secret/ && echo "secret done ($(ls /Volumes/CIRCUITPY/secret/*.gif | wc -l | xargs))"
dot_clean -m /Volumes/CIRCUITPY 2>/dev/null || true
sync

printf 'import storage\nstorage.disable_usb_drive()\n' > /Volumes/CIRCUITPY/boot.py
sync; dot_clean -m /Volumes/CIRCUITPY 2>/dev/null || true; sync
diskutil unmount CIRCUITPY | tail -1

python3 - <<'PY'
import os,time,glob,termios
ports=glob.glob("/dev/cu.usbmodem*")
if not ports: raise SystemExit("no serial for the bootstrap reset")
fd=os.open(ports[0],os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
a=termios.tcgetattr(fd);a[0]=a[1]=a[3]=0;a[2]|=termios.CLOCAL|termios.CREAD;termios.tcsetattr(fd,termios.TCSANOW,a)
def wr(bs):
    while bs:
        try: n=os.write(fd,bs); bs=bs[n:]
        except BlockingIOError: time.sleep(0.02)
wr(b"\x03"); time.sleep(1.2)
wr(b"import microcontroller\r"); time.sleep(0.5)
wr(b"microcontroller.reset()\r"); time.sleep(0.3)
os.close(fd)
print("bootstrap reset sent")
PY
echo
echo ">>> NOW: unplug the board, plug it back in, then run:"
echo ">>>   MPY_CROSS=\$PWD/firmware/.tools/mpy-cross-10.2.1 python3 firmware/deploy_production.py"
