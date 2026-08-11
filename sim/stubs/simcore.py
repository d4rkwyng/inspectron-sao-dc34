# simcore — shared state for the INSPECTRON 34 desktop simulator stubs.
# Owns the pygame window, key event plumbing, path remapping, and the
# selftest harness (scripted keys + PNG dumps + frame-count exit).
#
# Import graph: stubs import simcore; simcore imports only pygame/stdlib.

import os
import time

import pygame

badge_probe_pending = 0   # B key queues fake badge I2C contacts
show_true_size = True     # T toggles the 1:1 "actual device pixels" inset

SIM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCALE = 4
WINDOW_TITLE = "INSPECTRON 34 SIM"

# --- runtime config (set by run.py before code.py executes) ----------------
SELFTEST = False
MAX_FRAMES = 200
OUT_DIR = os.path.join(SIM_DIR, "out")
MEMES_DIR = os.path.join(SIM_DIR, "memes")
SECRET_DIR = os.path.join(SIM_DIR, "secret")

_window = None
_disp_size = None
_frame = 0
_t0 = None
_script_i = 0

# key queues registered by keypad.Keys instances
_key_queues = []

# pygame key -> firmware key number (order given to keypad.Keys):
#   0 = CH_DOWN (GP12)   1 = CH_UP (GP13)   2 = MODE (GP14)
KEYMAP = {
    pygame.K_LEFT: 0,
    pygame.K_RIGHT: 1,
    pygame.K_m: 2,
    pygame.K_DOWN: 2,
}

# Scripted key sequence for --selftest: (seconds_from_start, key, pressed).
# Time-based because refresh cadence differs between GIF playback (~50fps
# for the 20ms test GIFs) and the tuner (~30fps ambient static).
SELFTEST_SCRIPT = [
    (0.2, 1, True), (0.3, 1, False),    # CH_UP: channel change + static
    (0.6, 2, True), (0.7, 2, False),    # MODE short press: brightness cycle
    (0.9, 1, True), (1.0, 0, True),     # hold CH+ & CH- -> MASTER CONTROL
    (2.0, 1, False), (2.05, 0, False),  #   (menu opens at ~1.7s)
    (2.4, 0, True), (2.5, 0, False),    # CH-: cursor TV GUIDE -> CASE FILES
    (2.8, 2, True), (2.9, 2, False),    # MODE: menu -> CASE FILES board
    (3.1, 2, True), (3.2, 2, False),    # MODE: board -> FREQ TUNER
    (3.5, 1, True), (3.6, 1, False),    # tuner: spin first digit
    (3.9, 2, True),                     # MODE long press: tune at ~4.9s
    (5.3, 2, False),                    # (miss -> NO SIGNAL -> nedry)
    # --- deep coverage (reached only with --frames >= ~900) ---
    (9.0, 1, True), (9.1, 0, True),     # combo -> MASTER CONTROL again
    (10.0, 1, False), (10.05, 0, False),
    (10.8, 2, True), (10.9, 2, False),  # MODE: row 0 = TV GUIDE opens
    (11.2, 0, True), (11.3, 0, False),  # scroll a row
    (11.6, 2, True), (11.7, 2, False),  # MODE WATCH -> park on channel
    (13.0, 1, True), (13.1, 0, True),   # combo -> menu once more
    (14.0, 1, False), (14.05, 0, False),
    (14.4, 0, True), (14.5, 0, False),  # down x3 -> SETTINGS
    (14.7, 0, True), (14.8, 0, False),
    (15.0, 0, True), (15.1, 0, False),
    (15.4, 2, True), (15.5, 2, False),  # open settings
    (15.8, 2, True), (15.9, 2, False),  # cycle AUTO SCAN -> ON
    (16.2, 2, True), (16.3, 2, False),  # -> OFF again (leave defaults)
    (16.6, 1, True), (16.7, 0, True),   # BOTH: save + back to menu
    (17.4, 1, False), (17.45, 0, False),
    (17.8, 1, True), (17.9, 0, True),   # BOTH again: exit to TV
    (18.6, 1, False), (18.65, 0, False),
]


def configure(selftest=False, max_frames=200, memes_dir=None, out_dir=None,
              secret_dir=None):
    global SELFTEST, MAX_FRAMES, MEMES_DIR, OUT_DIR, SECRET_DIR
    SELFTEST = selftest
    MAX_FRAMES = max_frames
    if memes_dir:
        MEMES_DIR = memes_dir
    if secret_dir:
        SECRET_DIR = secret_dir
    if out_dir:
        OUT_DIR = out_dir


def resolve_path(path):
    """Map on-device paths ('/memes', '/secret') into the sim tree."""
    if isinstance(path, str):
        for prefix, base in (("/memes", MEMES_DIR), ("/secret", SECRET_DIR)):
            if path == prefix or path.startswith(prefix + "/"):
                rest = path[len(prefix):].lstrip("/")
                return os.path.join(base, rest) if rest else base
        if path.startswith("/splash") and path.endswith(".gif"):
            # splash + theme variants live at the drive root — map them into
            return os.path.join(SIM_DIR, path[1:])   # sim/ (else boot skips them)
    return path


# --- window ---------------------------------------------------------------
def init_window(width, height):
    """Called by the displayio Display stub when the display is created."""
    global _window, _disp_size, _t0
    if _window is not None:
        return
    pygame.init()
    _disp_size = (width, height)
    _window = pygame.display.set_mode((width * SCALE, height * SCALE),
                                     pygame.RESIZABLE)
    pygame.display.set_caption(WINDOW_TITLE)
    _t0 = time.monotonic()
    if SELFTEST:
        os.makedirs(OUT_DIR, exist_ok=True)


def register_key_queue(queue):
    _key_queues.append(queue)


def push_key(key_number, pressed):
    ts = int(time.monotonic() * 1000)
    for q in _key_queues:
        q._push(key_number, pressed, ts)


def pump():
    """Translate pygame input into keypad events; honor window close."""
    global _script_i
    if _window is None:
        return
    if SELFTEST:
        t = time.monotonic() - _t0
        while (_script_i < len(SELFTEST_SCRIPT)
               and SELFTEST_SCRIPT[_script_i][0] <= t):
            _, key, pressed = SELFTEST_SCRIPT[_script_i]
            _script_i += 1
            log("selftest t=%.2f key %d %s"
                % (t, key, "press" if pressed else "release"))
            push_key(key, pressed)
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            raise SystemExit(0)
        if ev.type in (pygame.KEYDOWN, pygame.KEYUP):
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_b:
                globals()["badge_probe_pending"] = (
                    globals().get("badge_probe_pending", 0) + 1)
                continue
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_t:
                globals()["show_true_size"] = not show_true_size
                continue
            if ev.type == pygame.KEYDOWN and pygame.K_1 <= ev.key <= pygame.K_6:
                globals()["SCALE"] = ev.key - pygame.K_1 + 1
                pygame.display.set_mode(
                    (_disp_size[0] * SCALE, _disp_size[1] * SCALE),
                    pygame.RESIZABLE)
                continue
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                raise SystemExit(0)
            key = KEYMAP.get(ev.key)
            if key is not None:
                push_key(key, ev.type == pygame.KEYDOWN)


_font = None


def _init_font():
    global _font
    pygame.font.init()
    _font = pygame.font.SysFont("Menlo,Monaco,monospace", 11)


def present(surface):
    """Blit a display-sized surface to the window at 4x; drive selftest."""
    global _frame
    pump()
    scaled = pygame.transform.scale(
        surface, (_disp_size[0] * SCALE, _disp_size[1] * SCALE))
    _window.blit(scaled, (0, 0))
    if show_true_size and SCALE > 1:
        w, h = _disp_size
        margin = 8
        x = _window.get_width() - w - margin
        y = margin
        pygame.draw.rect(_window, (0, 0, 0),
                         (x - 3, y - 3, w + 6, h + 18))
        pygame.draw.rect(_window, (240, 180, 41),
                         (x - 2, y - 2, w + 4, h + 4), 1)
        _window.blit(surface, (x, y))       # raw = exactly the panel pixels
        if _font is None:
            _init_font()
        _window.blit(_font.render("ACTUAL 1.14in SIZE", True,
                                  (240, 180, 41)), (x - 2, y + h + 2))
    pygame.display.flip()

    if SELFTEST:
        pygame.image.save(
            _window, os.path.join(OUT_DIR, "frame_%04d.png" % _frame))
    _frame += 1
    if SELFTEST and _frame >= MAX_FRAMES:
        print("[SIM] selftest: %d frames rendered, exiting" % _frame)
        raise SystemExit(0)


def log(msg):
    print("[SIM] " + msg)
