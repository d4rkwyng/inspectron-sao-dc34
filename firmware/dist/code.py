# CIRCUITPY /code.py — PRODUCTION LOADER (do not add logic here).
#
# The real program is the repo's firmware/code.py, shipped PRECOMPILED as
# /app.mpy. This two-line loader is all that runs as code.py, so the heap
# stays pristine for app.mpy's boot-time GIF preopen (_BOOT_GIF). Compiling
# the full program on-device instead fragments the RP2040 heap and the first
# OnDiskGif dies with MemoryError. See HANDOFF.md "DEPLOYMENT IS PRECOMPILED".
#
# firmware/deploy_production.py writes this file to the drive for you.
import app
