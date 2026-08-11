#!/usr/bin/env python3
"""INSPECTRON 34 desktop simulator.

Runs firmware/code.py UNMODIFIED in CPython by shadowing the CircuitPython
modules (board, displayio, gifio, keypad, ...) with the stubs in sim/stubs/,
rendered to a pygame window at 4x (960x540).

Usage:
    python3 sim/run.py                      # interactive window
    python3 sim/run.py --selftest           # headless scripted run -> sim/out/
    python3 sim/run.py --selftest --frames 300

Keys: LEFT = CH_DOWN, RIGHT = CH_UP, M or DOWN = MODE (hold 1s = standby),
ESC or close window = quit.
"""

import argparse
import glob
import os
import sys

SIM_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SIM_DIR)
CODE_PY = os.path.join(REPO_DIR, "firmware", "code.py")


def main():
    parser = argparse.ArgumentParser(description="INSPECTRON 34 simulator")
    parser.add_argument("--selftest", action="store_true",
                        help="headless scripted run; dump PNGs to sim/out/")
    parser.add_argument("--frames", type=int, default=1700,
                        help="selftest frame budget (default 1700 — enough "
                             "to reach the deep listings/settings coverage)")
    parser.add_argument("--scale", type=int,
                        default=int(os.environ.get("INSPECTRON_SIM_SCALE", "4")),
                        help="window pixel scale (1 = true device pixels; default 4)")
    args = parser.parse_args()

    if args.selftest:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    # Stubs shadow any real modules of the same name; the firmware dir
    # follows so code.py's local imports (tuner, secrets_config) resolve.
    sys.path.insert(0, os.path.join(REPO_DIR, "firmware"))
    sys.path.insert(0, os.path.join(SIM_DIR, "stubs"))
    if args.selftest:
        # deterministic selftest: start with no persisted unlocks
        try:
            os.remove(os.path.join(SIM_DIR, "nvm.bin"))
        except OSError:
            pass
    import simcore
    simcore.SCALE = max(1, args.scale)
    import microcontroller  # noqa: F401 — loads/persists sim/nvm.bin even
    # though code.py doesn't import it itself

    # Use the REAL device packs (repo memes/ + secret/) when present — the
    # tiny generated test GIFs left 36 of 38 channels playing TAPE NOT ON
    # FILE. The generated set remains the fallback for pack-less checkouts;
    # INSPECTRON_SIM_TESTGIFS=1 forces it (deterministic tiny-GIF timing).
    memes_dir = os.path.join(SIM_DIR, "memes")
    secret_dir = os.path.join(SIM_DIR, "secret")
    if not os.environ.get("INSPECTRON_SIM_TESTGIFS"):
        if glob.glob(os.path.join(REPO_DIR, "memes", "*.gif")):
            memes_dir = os.path.join(REPO_DIR, "memes")
        if glob.glob(os.path.join(REPO_DIR, "secret", "*.gif")):
            secret_dir = os.path.join(REPO_DIR, "secret")
    simcore.configure(selftest=args.selftest, max_frames=args.frames,
                      memes_dir=memes_dir, secret_dir=secret_dir,
                      out_dir=os.path.join(SIM_DIR, "out"))
    print("[SIM] memes: %s | secret: %s" % (memes_dir, secret_dir))

    # Make sure there is something to play (and to unlock).
    if not (glob.glob(os.path.join(memes_dir, "*.gif"))
            and glob.glob(os.path.join(secret_dir, "*.gif"))):
        print("[SIM] test GIFs missing — generating sim/memes + sim/secret")
        sys.path.insert(0, SIM_DIR)
        import make_test_gifs
        make_test_gifs.main()

    if args.selftest:
        for old in glob.glob(os.path.join(SIM_DIR, "out", "frame_*.png")):
            os.remove(old)

    # The firmware reads on-device paths "/memes" and "/secret": remap them.
    real_listdir = os.listdir
    real_stat = os.stat
    os.listdir = lambda path=".": real_listdir(simcore.resolve_path(path))
    os.stat = lambda path, **kw: real_stat(simcore.resolve_path(path), **kw)

    # Pump the pygame event loop during firmware sleeps so the window stays
    # responsive in loops that don't refresh (e.g. standby). In selftest,
    # also clamp sleeps so static transitions don't eat the frame budget's
    # wall-clock time.
    import time
    real_sleep = time.sleep

    def sim_sleep(seconds):
        simcore.pump()
        real_sleep(min(seconds, 0.005) if args.selftest else seconds)

    time.sleep = sim_sleep

    print("[SIM] running %s" % CODE_PY)
    with open(CODE_PY) as f:
        source = f.read()
    code_globals = {"__name__": "__main__", "__file__": CODE_PY}
    try:
        exec(compile(source, CODE_PY, "exec"), code_globals)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 0
        print("[SIM] exit %d" % code)
        sys.exit(code)
    except KeyboardInterrupt:
        print("[SIM] interrupted")
        sys.exit(0)


if __name__ == "__main__":
    main()
