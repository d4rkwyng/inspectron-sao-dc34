# INSPECTRON 34 Meme TV SAO — CircuitPython GIF player (direct-render)
# Plays GIFs from /memes on a 1.14" ST7789 (native 135x240, mounted landscape).
# Rendering is DIRECT (display.bus.send) via fbdraw — displayio was too slow on
# the RP2040 and its GIF pipeline fragmented RAM. See fbdraw.py + convert.py.
#
# CH+/CH- change channel (TV-static wipe + channel bug). MODE short-press
# cycles brightness, MODE hold (1s) -> MASTER CONTROL menu (guide / listings /
# dial / settings — see MENU_SPEC.md; CH+&CH- held together still works).
# CH+ alone 2.5s = auto-scan, CH- alone 2.5s = standby (one-finger mirrors —
# the two-button pinch was hard on a worn badge, rig feedback Jul 22).
# Konami -> hidden channel. Settings persist at NVM offset 91 (tuner.py).
#
# Pin map: pins.md (single source of truth).

import os
import time
import random
import gc

import board
import busio
import digitalio
import displayio
import fourwire
import gifio
import i2ctarget
import keypad
import pwmio
import supervisor
import struct
from micropython import const

# --- Antenna LEDs: claimed FIRST (v4) --------------------------------------
# The official DC34 badge sources current into a floating SAO GPIO, so the
# antenna tips half-glow from plug-in until something drives the pins. Claim
# them before ANY heavy boot work (display init + the gif preopen add whole
# seconds of glow) and hold duty 0. PWM, not digitalio: duty 0 still actively
# drives the pin low, and PWM is what enables ANT PULSE (breathe) mode.
# Pins here == P_ANT in the pin map below (GP26/27 on rig AND production).
ANT_MAX = 65535


class _AntPin:
    """digitalio-shaped facade over PWMOut so existing call sites keep
    working: switch_to_output(value=) -> full/zero duty; duty(d) for PULSE."""
    def __init__(self, pwm):
        self._p = pwm

    def switch_to_output(self, value=False):
        self._p.duty_cycle = ANT_MAX if value else 0

    def switch_to_input(self):          # legacy OFF: now actively driven low
        self._p.duty_cycle = 0

    def duty(self, d):
        self._p.duty_cycle = d


ants = [_AntPin(pwmio.PWMOut(_p, frequency=2000, duty_cycle=0))
        for _p in (board.GP26, board.GP27)]

# --- Las Vegas channel dial (hoisted: the boot peek below needs the map,
# and pure literals are heap-safe this early) -------------------------------
CHANNEL_MAP = {
    "stand_by": 2, "wargames": 3, "matrix": 4, "apple1984": 6,
    "colorbars": 7, "ncis": 8, "readingrainbow": 10, 
    "hacktheplanet": 13, "nedry": 15, "itcrowd_fire": 16, "printer": 17,
    "eas": 19, "mtv": 20, "beavis": 21, "fsociety": 22, "hackerman": 61,
    "alf": 25, 
    "tmnt": 30, "heman": 31,
    "transformers": 32, 
    "shamwow": 38, "slimjim": 39, 
    "koolaid": 41, "erasebutton": 48, "grant": 49,
    "area51": 51, "dvd": 52, "vegasstrip": 54, "riviera": 56, "fearloathing": 57,
    "homerbush": 5, "smurfs": 26, "scooby": 27, "ducktales": 29,
    "dinosaurs": 33, "wheresthebeef": 40, "peterknee": 50,
    "defcon34": 34,     # the convention's own channel: the flickering DC34
}                       # sign. A case unlock can add a SUBCHANNEL — the
                        # seat is no longer dead, the ident joins the dial
                        # (real ATSC numbering; answer table untouched)
DEAD_CHANNELS = (11, 23, 42, 66, 88)   # 34 went live: it's the DC34 sign now

# TV LISTINGS display names (<= 11 chars: the name column is 11 cells at
# scale 2 — curated beats filename stems truncated mid-word). Filenames
# stay as-is: they are load-bearing for CHANNEL_MAP and the drive.
SHOW_NAMES = {
    "stand_by": "STAND BY", "ncis": "NCIS", "matrix": "THE MATRIX",
    "apple1984": "MAC 1984",
    "colorbars": "COLOR BARS", "wargames": "WARGAMES",
    "readingrainbow": "RAINBOW", 
    "hacktheplanet": "HACK PLANET", "nedry": "NEDRY",
    "itcrowd_fire": "IT CROWD", "printer": "PC LOAD LTR",
    "eas": "EAS TEST", "mtv": "MTV", "beavis": "BEAVIS",
    "fsociety": "FSOCIETY", "hackerman": "HACKERMAN", 
    "alf": "ALF", 
    
    "tmnt": "TURTLES", "heman": "HE-MAN",
    "transformers": "AUTOBOTS", 
    
    "shamwow": "SHAMWOW", "slimjim": "SLIM JIM",
    "koolaid": "KOOL-AID",
    "erasebutton": "RED BUTTON",
    "grant": "DR GRANT", "area51": "AREA 51", "dvd": "DVD LOGO", "smurfs": "SMURFS", "scooby": "SCOOBY DOO",
    "ducktales": "DUCKTALES", "dinosaurs": "DINOSAURS",
    "wheresthebeef": "WHERES BEEF", "defcon34": "DEF CON 34",
    "vegasstrip": "THE STRIP", "riviera": "RIVIERA",
    "fearloathing": "BAT COUNTRY",
    "homerbush": "HOMER BUSH", "peterknee": "PETER KNEE",
}


def _boot_peek_path():
    """BOOT CH from the settings NVM block WITHOUT importing tuner (the
    heap must stay pristine here). Offsets hardcoded to the block at
    tuner._NVM_LEN == 91 — asserted after import. Secret NN.N channels
    are unreachable pre-import, hence the FIRST fallback rule."""
    try:
        from microcontroller import nvm as _nvm
        blk = bytes(_nvm[91:104])
        x = 0
        for v in blk[:-1]:
            x ^= v
        # blk[1] is the settings version = tuner._SET_VER (== 4 now: +theme
        # appended, so boot digits stay at blk[9]/blk[10]). This was 0x01
        # and silently disabled BOOT CH after the v2 bump — the assert on
        # _SET_VER below keeps them locked together.
        if blk[0] == 0x53 and blk[1] == 0x04 and blk[-1] == x:
            n = blk[9] * 10 + blk[10] // 10     # unpacked NNN.0 digits
            if n:
                for base, ch in CHANNEL_MAP.items():
                    if ch == n:
                        return "/memes/" + base + ".gif"
    except Exception:
        pass
    return None


# --- Boot-time GIF preopen (MUST stay this early) --------------------------
# The first OnDiskGif needs ~90KB of large allocations (64320 frame bitmap +
# ~24KB decoder workspace). Importing tuner/fbdraw and initializing the
# display fragments the heap below that — so the FIRST decoder is created
# HERE, on a pristine heap, and handed to the first play_gif. Every later
# open recycles this one's freed holes. (Cold-boot MemoryError chased on the
# dev rig, Jul 21: nothing allocated later can find the space.)
_BOOT_GIF = None
_BOOT_IS_SPLASH = False
_SPLASH_PAD = None
def _boot_peek_theme():
    """Theme index 0-2 from the raw settings block (same guarded read as
    _boot_peek_path) — picks the splash variant pre-import."""
    try:
        from microcontroller import nvm as _nvm
        blk = bytes(_nvm[91:104])
        x = 0
        for v in blk[:-1]:
            x ^= v
        if blk[0] == 0x53 and blk[1] == 0x04 and blk[-1] == x \
                and blk[11] <= 2:
            return blk[11]
    except Exception:
        pass
    return 0


_SPLASH_PATH = "/splash.gif"
_t = _boot_peek_theme()
if _t:
    try:                               # themed splash if the variant exists;
        _p = ("/splash-dc34.gif", "/splash-inv.gif")[_t - 1]
        os.stat(_p)                    # missing file -> default splash
        _SPLASH_PATH = _p
    except Exception:
        pass
_SPLASH_HOLD_S = 4.6   # ~0.3s sign-on + ~3s steady logo + ~1.4s flash finale
try:
    try:                               # boot ident: play /splash.gif once (if
        os.stat(_SPLASH_PATH)          # present) on the pristine heap, then
        # margin pad allocated BEFORE the decoder: freed together, the two
        # coalesce into a ~96KB hole. Without it the freed hole is EXACTLY
        # decoder-sized (88,344B) and the next open loses to allocation-order
        # + header overhead — 92KB free, nothing 64,320 contiguous, every
        # channel PLEASE STAND BY (same exact-fit disease as the old
        # 'sometimes STAND BY' bug; serial-traced on the rig Aug 4).
        _SPLASH_PAD = bytearray(8192)
        _BOOT_GIF = (_SPLASH_PATH,     # release it so the first channel opens
                     gifio.OnDiskGif(_SPLASH_PATH))   # into the freed hole
        _BOOT_IS_SPLASH = True
    except Exception:
        _BOOT_GIF = None
        _SPLASH_PAD = None
    if _BOOT_GIF is None:
        _bp = _boot_peek_path()
        if _bp:
            try:
                _BOOT_GIF = (_bp, gifio.OnDiskGif(_bp))
            except Exception:
                _BOOT_GIF = None
    if _BOOT_GIF is None:
        try:                               # fresh NVM: default to the DC34
            _BOOT_GIF = ("/memes/defcon34.gif",          # sign, not whatever
                         gifio.OnDiskGif("/memes/defcon34.gif"))  # sorts first
        except Exception:                                 # (alphabetical alf)
            _BOOT_GIF = None
    if _BOOT_GIF is None:
        for _f in sorted(os.listdir("/memes")):
            if _f.lower().endswith(".gif") and not _f.startswith("."):
                try:                       # a corrupt first file (yanked mid
                    _BOOT_GIF = ("/memes/" + _f,       # USB-write) must not
                                 gifio.OnDiskGif("/memes/" + _f))  # forfeit
                    break                              # the whole preopen —
                except Exception:                      # try the next gif
                    continue
except Exception:
    _BOOT_GIF = None

try:
    from adafruit_st7789 import ST7789
except (ImportError, ValueError) as _libe:
    # ImportError: lib absent. ValueError: incompatible .mpy — a 9.x bundle
    # adafruit_st7789.mpy on this 10.x runtime raises ValueError, which used
    # to sail past the guard into a bare traceback + black panel. Both mean
    # "wrong/missing st7789 lib" — surface the readable fix either way.
    raise RuntimeError("Bad/missing lib: copy the CircuitPython 10.x "
                       "adafruit_st7789.mpy into /lib (9.x .mpy is "
                       "incompatible) [%s]" % _libe) from _libe

import fbdraw as fb
import tuner
import ui

# --- Hardware config ------------------------------------------------------
# DEV_RIG True = Waveshare Pico-LCD-1.14 hat pins; False = production board
# (pins.md). Default is FALSE: the dev rig gets a one-line /rigconfig.py
# (planted by rigdeploy.py, never committed) — a forgotten flag edit must
# never ship 30 black-screen production boards.
try:
    from rigconfig import DEV_RIG
except ImportError:
    DEV_RIG = False

if DEV_RIG:
    P_SCK, P_MOSI = board.GP10, board.GP11
    P_DC, P_CS, P_RST, P_BL = board.GP8, board.GP9, board.GP12, board.GP13
    P_BTN = (board.GP17, board.GP15, board.GP3)     # DOWN=B, UP=A, MODE=joyC
    P_LED_PWR = board.GP25                           # onboard LED
else:
    P_SCK, P_MOSI = board.GP2, board.GP3
    P_DC, P_CS, P_RST, P_BL = board.GP4, board.GP5, board.GP6, board.GP7
    P_BTN = (board.GP12, board.GP13, board.GP14)     # DOWN, UP, MODE
    P_LED_PWR = board.GP16
P_I2C_SCL, P_I2C_SDA = board.GP1, board.GP0
P_ANT = (board.GP26, board.GP27)
SPI_HZ = 24_000_000    # 40MHz dropped bytes -> shear on the dev rig; retry on 1st article
DISP_ROT = 0           # 0/180 flip if upside-down on the production panel (see convert.py)

# --- Config ---------------------------------------------------------------
MEME_DIR = "/memes"
BRIGHTNESS_LEVELS = (0.6, 0.3, 0.85)   # idx order = MED/LOW/HIGH (settings)
LONG_PRESS_S = 1.0
TUNER_HOLD_S = 0.7
SCAN_HOLD_S = 2.5      # hold CH+ alone this long to toggle auto-scan (was 1.2 -> fired while surfing)
KNOCK_DWELL_S = 3.0    # sit on a channel this long for it to count as a station-knock "visit"

# Persisted settings (MENU_SPEC.md §4). SETTINGS is the RAM copy; the
# playback shortcuts (MODE-short brightness, CH+-hold scan) mutate it and
# it is diff-written to NVM on menu entry / settings exit / standby entry.
SETTINGS = tuner.settings_load()
_DWELL_OPTS = (4.0, 8.0, 15.0, 30.0)
_STANDBY_OPTS = (0, 300, 900, 1800)                        # OFF/5M/15M/30M
assert tuner._NVM_LEN == 91    # _boot_peek_path hardcodes the settings offset
assert tuner._SET_VER == 4     # _boot_peek_path hardcodes the version byte 0x04
assert tuner._SET_KEYS.index("boot_hi") == 7   # ...and digits at blk[9]/[10]

# EAS interrupt: the Emergency Alert System channel
# occasionally hijacks whatever's playing for a few seconds, then the
# station resumes — "We interrupt this broadcast..." Never fires while
# EAS itself is on, reschedules after each strike, disabled if the gif
# is absent (the 2MB dev rig may not carry it).
EAS_PATH = MEME_DIR + "/eas.gif"
EAS_EVERY_S = (480.0, 900.0)   # strike every 8-15 min
EAS_HOLD_S = 5.0
try:
    os.stat(EAS_PATH)
    _next_eas = time.monotonic() + EAS_EVERY_S[0] + \
        random.random() * (EAS_EVERY_S[1] - EAS_EVERY_S[0])
except OSError:
    _next_eas = None

# Derived playback globals (apply_settings() keeps AUTO_SCAN/SCAN_SECS in
# sync). FRAME_MIN/MAX and STATIC_FRAMES are FIXED (SPEED/STATIC WIPE rows
# removed — see apply_settings). 0.40 admits 3x-decimated 100ms sources at
# true pace; the inter-frame wait is sliced so long frames stay responsive.
STATIC_FRAMES = 4
SCAN_SECS = 8.0
AUTO_SCAN = False
FRAME_MIN, FRAME_MAX = 0.10, 0.40

# --- Display (direct-render) ----------------------------------------------
displayio.release_displays()
spi = busio.SPI(clock=P_SCK, MOSI=P_MOSI)
while not spi.try_lock():
    pass
spi.configure(baudrate=SPI_HZ)
spi.unlock()
bus = fourwire.FourWire(spi, command=P_DC, chip_select=P_CS,
                        reset=P_RST, baudrate=SPI_HZ)
display = ST7789(bus, width=135, height=240, rowstart=40, colstart=53,
                 rotation=DISP_ROT, auto_refresh=False, backlight_pin=None)
display.root_group = None    # direct render: drop the supervisor terminal's
                             # tiles/fonts — we only use the display's bus
backlight = pwmio.PWMOut(P_BL, frequency=2000)   # duty 0: OFF until main()
fb.init(display)     # display handle only; FB allocates lazily and recycles
                     # the GIF decoder's freed holes (see fbdraw + _BOOT_GIF)
# Power-on GRAM is random garbage; black it out BEFORE the backlight first
# turns on (row-buffer push — no framebuffer alloc while _BOOT_GIF pins
# the heap). Every shipped board flashed garbage at boot without this.
# Blackout covers the FULL 135-column panel (content only ever writes 134 —
# the 135th column is never touched again, so un-blacked it shows stale GRAM
# as a thin bar along one screen edge on every image; rig report Aug 4).
display.bus.send(42, struct.pack(">hh", 53, 53 + 135 - 1))
_blackrow = bytes(270)
for _i in range(240):                    # per-row RASET: each RAMWR restarts
    display.bus.send(43, struct.pack(">hh", 40 + _i, 40 + _i))
    display.bus.send(44, _blackrow)      # at the window origin
del _blackrow


def set_brightness(level):
    backlight.duty_cycle = int(level * 65535)


def apply_settings():
    """Push the SETTINGS dict into the derived playback globals.
    NOTE: FRAME_MIN/MAX are FIXED at (0.10, 0.40) — the SPEED setting was
    removed because NORM (0.22 cap) silently un-did the pack's decimation
    retune (3x-decimated 300ms sources played 36% fast — the ncis bug);
    STATIC_FRAMES fixed at 4 (the wipe is always wanted). Both NVM fields
    stay in the layout, just unread."""
    global AUTO_SCAN, SCAN_SECS
    AUTO_SCAN = bool(SETTINGS["auto_scan"])
    SCAN_SECS = _DWELL_OPTS[SETTINGS["dwell_idx"]]
    set_brightness(BRIGHTNESS_LEVELS[SETTINGS["bright_idx"]])
    fb.set_theme(SETTINGS.get("theme", 0))        # menu accent palette
    try:
        _ant_restore()                  # ANT LED base state (OFF/FLASH/ON)
    except NameError:
        pass                            # first call runs before ants exist


def _send_window(w, h):
    display.bus.send(42, struct.pack(">hh", 53, 53 + w - 1))
    display.bus.send(43, struct.pack(">hh", 40, 40 + h - 1))


# --- Power LED ------------------------------------------------------------
led_pwr = digitalio.DigitalInOut(P_LED_PWR)
led_pwr.switch_to_output(value=True)

# --- Badge link: antenna LEDs + I2C target at 0x50 ------------------------
# (ants themselves are claimed at the very top of the file — v4 — so the
# badge's SAO-GPIO current can't half-light a floating tip during boot)


def _ant_restore():
    """Base antenna state per SETTINGS ant_mode (0 OFF / 1 FLASH / 2 ON /
    3 PULSE)."""
    try:
        m = SETTINGS["ant_mode"]
    except Exception:
        m = 0
    for a in ants:
        if m == 2:
            a.switch_to_output(value=True)
        elif m != 1:
            a.switch_to_output(value=False)    # OFF/PULSE base = driven low
                                               # (v4: was high-Z input, which
                                               # half-lit on the badge)
        # FLASH/PULSE: ant_service animates from the next play-loop tick


_ant_sv = [0.0, False]


def ant_service(now):
    """FLASH: seesaw the antenna tips. PULSE: slow synchronized dim<->bright
    breathe (v4). Both driven from the play/menu loops."""
    m = SETTINGS["ant_mode"]
    if m == 1:
        if now >= _ant_sv[0]:
            _ant_sv[1] = not _ant_sv[1]
            ants[0].switch_to_output(value=_ant_sv[1])
            ants[1].switch_to_output(value=not _ant_sv[1])
            _ant_sv[0] = now + 0.25
    elif m == 3:
        ph = (now % 2.4) / 2.4          # 2.4s breathe period
        tri = ph * 2.0 if ph < 0.5 else (1.0 - ph) * 2.0
        d = int(ANT_MAX * tri * tri)    # squared ramp: perceptually smooth
        ants[0].duty(d)
        ants[1].duty(d)


def ant_blip(times=2):
    for _ in range(times):
        for a in ants:
            a.switch_to_output(value=True)
        time.sleep(0.04)
        for a in ants:
            a.switch_to_output(value=False)     # drive low (was high-Z) so the
        time.sleep(0.04)                        # off-phase stays dark on a badge
    _ant_restore()


# v4.3: host-badge detection. The OFFICIAL DC34 badge never initiates SAO
# I2C (same as DC32 — its firmware never scans the SAO bus), so waiting to
# be read at 0x50 means never knowing we're mounted. Instead, probe the bus
# as a controller for ONE moment at boot: on a badge the bus has pull-ups
# and the badge's own devices (0x3C OLED / 0x19 accel) ACK a scan; on bare
# USB there are no pull-ups and busio.I2C() raises immediately. Then the
# pins are handed to the i2ctarget as before.
def _badge_probe(tries=8):
    """True if the host badge's bus answers. The badge is an ACTIVE
    controller (it polls its accel), so a one-shot lock/scan can lose
    arbitration — retry. Off-badge, busio.I2C() raises instantly (no
    pull-ups), so the miss case is fast."""
    seen = None
    err = None
    ok = False
    try:
        p = busio.I2C(P_I2C_SCL, P_I2C_SDA)
        try:
            for _t in range(tries):
                if p.try_lock():
                    try:
                        seen = p.scan()
                    finally:
                        p.unlock()
                    if seen:
                        ok = True
                        break
                time.sleep(0.05)
        finally:
            p.deinit()
    except Exception as e:
        err = e
    print("badge probe:", ok, "seen", seen, "err", repr(err))
    return ok


ON_BADGE = _badge_probe()
tuner.ON_BADGE = ON_BADGE       # the menu's LINK row shows "ON BADGE" (ui.py)

_DESC = b"LIFE" + bytes([12, 0, 0, 0]) + b"INSPECTRON34"   # served on the fly;
_DLEN = const(20)                                          # == len(_DESC); no
assert len(_DESC) == _DLEN                                 # 256B buffer needed
try:
    sao_i2c = i2ctarget.I2CTarget(scl=P_I2C_SCL, sda=P_I2C_SDA, addresses=[0x50])
except Exception:
    sao_i2c = None
_eeprom_ptr = 0
_badge_cmds = []
_BADGE_CMD_CAP = const(8)   # DoS bound: a flooding badge can't grow the queue


def reprobe_badge():
    """Refresh ON BADGE on menu entry: the boot probe goes stale if the set
    is pulled off the badge while USB keeps it alive (or seated onto one).
    Briefly hands the pins from the 0x50 target to a controller probe and
    back — ~0.1s, and a badge read colliding with it just retries."""
    global sao_i2c
    if sao_i2c:
        try:
            sao_i2c.deinit()
        except Exception:
            pass
        sao_i2c = None
    tuner.ON_BADGE = _badge_probe(tries=2)
    try:
        sao_i2c = i2ctarget.I2CTarget(scl=P_I2C_SCL, sda=P_I2C_SDA,
                                      addresses=[0x50])
    except Exception:
        sao_i2c = None      # tolerated everywhere; next menu entry retries
_CMD_EVENTS = {0xF0: "up", 0xF1: "down", 0xF2: "staticburst", 0xF3: "blip",
               0xF4: "mode", 0xF5: "antmode"}
# v5: 0xF2 now does what INTERFACING.md always promised (a static burst —
# it was miswired to the first-contact "badge" event, so every 0xF2 write
# showed a bogus BADGE CONNECTED banner + a heap-churning rescan), and
# 0xF5 [0-3] lets the host badge set the ANT LED mode (OFF/FLASH/ON/PULSE).


def poll_badge():
    global _eeprom_ptr
    if sao_i2c is None:
        return False
    req = sao_i2c.request(timeout=-1)   # negative = check-once (0 = wait forever!)
    if not req:
        return False
    with req:
        if req.is_read:
            p = _eeprom_ptr                 # serve 16B from _DESC, zero-padded
            if p < _DLEN:                   # past the descriptor is all zeros
                chunk = _DESC[p:p + 16]
                req.write(chunk + bytes(16 - len(chunk)))
            else:
                req.write(b"\x00" * 16)
            _eeprom_ptr = (p + 16) % 256
        else:
            data = req.read()
            if data:
                reg = data[0]
                if reg >= 0xF0:
                    if len(_badge_cmds) < _BADGE_CMD_CAP:   # bounded: flood-safe
                        _badge_cmds.append((reg, data[1] if len(data) > 1 else 0))
                else:
                    _eeprom_ptr = reg % 256
    return True


def badge_cmd_event():
    blipped = False
    while _badge_cmds:
        reg, _val = _badge_cmds.pop(0)
        ev = _CMD_EVENTS.get(reg)
        if ev == "blip":
            # collapse a blip flood: at most ONE ant_blip per drain. Blipping
            # each queued 0xF3 inline froze playback ~0.16s * queue_len (up to
            # ~1.28s at the DoS cap) while a badge spammed blips.
            if not blipped:
                ant_blip(2)
                blipped = True
            continue
        if ev == "antmode":
            # applied INLINE so it works in every state that drains the
            # queue (playback, menus via poll_ui, standby wake) — persists
            # at the next settings save like any settings change
            SETTINGS["ant_mode"] = min(_val, 3)
            try:
                _ant_restore()
            except Exception:
                pass
            continue
        if ev:
            return ev
    return None


def service_badge(controls):
    """Serve one badge I2C burst, then return an event or None. A 256B
    descriptor read is 16 back-to-back requests; we drain the burst but
    BOUND it hard (a chatty badge or a bus scanner must never freeze
    playback or starve buttons — the obvious badge-flood DoS). Returns
    "badge" on first-ever contact, a command event, or None (plain
    descriptor traffic: caller keeps playing)."""
    controls.touch()                       # badge activity defers standby
    first = tuner.unlock_badge_link()
    quiet = time.monotonic() + 0.05
    hard = time.monotonic() + 0.08         # absolute cap on one drain
    while time.monotonic() < quiet:
        if time.monotonic() >= hard:
            break                          # flood: bail, resume next loop
        if poll_badge():
            quiet = time.monotonic() + 0.05
    ev = badge_cmd_event()
    if first:
        if ev in ("up", "down", "mode", "staticburst"):
            # first-ever contact arrived WITH a command: don't eat it — put
            # it back so it lands on the next drain after the banner
            _badge_cmds.insert(0, ({"up": 0xF0, "down": 0xF1, "mode": 0xF4,
                                    "staticburst": 0xF2}[ev], 0))
        return "badge"
    return ev


def poll_ui():
    """Badge poll for menu/guide/tuner screens: badge contact must still
    unlock BADGE LINK in there (it used to silently miss), and queued
    badge up/down commands are drained so they don't replay as surf
    events after the menu exits. Blips still blip."""
    ant_service(time.monotonic())      # FLASH mode animates in menus too
    if poll_badge():
        tuner.unlock_badge_link()
    while badge_cmd_event():
        pass


# --- Buttons --------------------------------------------------------------
keys = keypad.Keys(P_BTN, value_when_pressed=False, pull=True, max_events=16)
BTN_DOWN, BTN_UP, BTN_MODE = 0, 1, 2

# --- Las Vegas channel dial (CHANNEL_MAP/DEAD_CHANNELS live at the top of
# the file — the boot peek needs them before the heavy imports) -------------
def _chan_num(path):
    if path.startswith("static:"):
        return int(path[7:])
    base = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    if base in CHANNEL_MAP:
        return CHANNEL_MAP[base]
    if base in EXTRA_MAP:               # community drop: CH 100+
        return EXTRA_MAP[base]
    num = tuner.channel_of(path)
    if num:
        try:
            return float(num)
        except ValueError:
            return 999
    return 999


EXTRA_MAP = {}    # community drag-and-drop gifs: base -> stable CH 100+
                  # dial number (v4 — they all used to collapse to "CH 99")


def scan_memes():
    try:
        gifs = set(f for f in os.listdir(MEME_DIR)
                   if f.lower().endswith(".gif") and not f.startswith("."))
    except OSError:
        gifs = set()
    EXTRA_MAP.clear()                   # sorted by name -> stable across boots
    for _i, _b in enumerate(sorted(
            f.rsplit(".", 1)[0] for f in gifs
            if f.rsplit(".", 1)[0] not in CHANNEL_MAP)):
        EXTRA_MAP[_b] = 100 + _i
    # The FULL dial lineup exists regardless of which files are on this
    # drive — a mapped channel whose gif is missing (2MB dev rig, pruned
    # pack) plays the TAPE NOT ON FILE placeholder instead of vanishing.
    # Extra drag-and-drop gifs on the drive join the dial too.
    chans = [MEME_DIR + "/" + b + ".gif" for b in CHANNEL_MAP]
    chans.extend(MEME_DIR + "/" + f for f in gifs
                 if f.rsplit(".", 1)[0] not in CHANNEL_MAP)
    unlocked = tuner.unlocked_paths()
    chans.extend(unlocked)
    # int() of every unlock: NNN.n -> NNN so its dead-air seat prunes too
    live = set(int(_chan_num(p)) for p in unlocked)
    chans.extend("static:%d" % n for n in DEAD_CHANNELS if n not in live)
    chans.sort(key=_chan_num)
    if SETTINGS["order"]:               # SHUFFLE: surf order only — labels,
        _shuffle(chans)                 # knock visits, listings stay by number
    return chans


_SHUFFLE_SEED = None                    # per-boot: stable across rescans


def _shuffle(chans):
    global _SHUFFLE_SEED
    if _SHUFFLE_SEED is None:
        _SHUFFLE_SEED = random.getrandbits(16) or 1
    s = _SHUFFLE_SEED
    for i in range(len(chans) - 1, 0, -1):      # Fisher-Yates on a tiny LCG
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        j = s % (i + 1)
        chans[i], chans[j] = chans[j], chans[i]


def listings_rows(channels):
    """TV LISTINGS rows, always in dial order: (label, name, kind, path).
    Built from scan_memes() output ONLY — locked secrets structurally
    can't appear (see MENU_SPEC.md §3)."""
    rows = []
    for p in sorted(channels, key=_chan_num):
        if p.startswith("static:"):
            rows.append(("CH %02d" % int(p[7:]), "NO CARRIER", "dead", p))
            continue
        base = p.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        name = SHOW_NAMES.get(base, base.upper()[:11])
        num = tuner.channel_of(p)
        if num:                          # unlocked secret at its learned NN.N
            rows.append((num.lstrip("0") or "0", name, "secret", p))
        else:
            rows.append(("CH %02d" % (CHANNEL_MAP.get(base)
                         or EXTRA_MAP.get(base, 99)),
                         name, "meme", p))
    return rows


def channel_label(channels, idx):
    p = channels[idx % len(channels)]
    if p.startswith("static:"):
        return "CH %02d" % int(p[7:])
    num = tuner.channel_of(p)
    if num:
        return "CH " + num
    base = p.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return "CH %02d" % (CHANNEL_MAP.get(base) or EXTRA_MAP.get(base, 99))


def nedry_index(channels):
    for i, p in enumerate(channels):
        if p.endswith("/nedry.gif"):
            return i
    return None


def knock_dwell_cb(channels, channel):
    """Station-knock hook: dwelling on an INTEGER channel counts as a 'visit'
    (CF-06 = CH 3 -> CH 6 -> CH 23). Surfing past without dwelling must not
    count, and AUTO_SCAN's timed park is not a deliberate visit either.
    Returns a zero-arg callable for play_gif/play_dead_air, or None."""
    if AUTO_SCAN or not channels:
        return None
    n = _chan_num(channels[channel % len(channels)])
    if n != int(n):
        return None                       # licensed NN.N secret channels don't knock

    return lambda: tuner.knock_visit("%03d.0" % int(n))


# --- Rendering (fbdraw / direct) ------------------------------------------
def show_banner(text, seconds=0.9):
    fb.reclaim()
    fb.fill(fb.BLACK)
    x = max(0, (fb.LW - len(text) * 12) // 2)
    fb.text(x, 60, text, fb.AMBER, 2)
    fb.show()
    time.sleep(seconds)


def show_static(label=None):
    """TV-static wipe; antenna tips seesaw with it (boot/channel-change
    flash is always on — the ANT LED setting governs steady-state only)."""
    fb.reclaim()
    fb.ensure_noise()                  # v4: guarantee the wipe renders even on
                                       # a fragmented heap (was silently no-op)
    for _i in range(STATIC_FRAMES):
        ants[0].switch_to_output(value=(_i & 1) == 0)
        ants[1].switch_to_output(value=(_i & 1) == 1)
        fb.static(1)
    _ant_restore()
    if label:
        fb.fill(fb.BLACK)
        fb.text(6, 6, label, fb.GREEN, 2)
        fb.show()
        time.sleep(0.45)


def show_no_signal():
    fb.reclaim()
    bars = (fb.WHITE, fb._rgb(255, 255, 0), fb.CYAN, fb.GREEN,
            fb._rgb(255, 0, 255), fb.RED, fb._rgb(0, 0, 255), fb.BLACK)
    bw = fb.LW // len(bars)
    for i, c in enumerate(bars):
        fb.fillrect(i * bw, 0, bw, fb.LH, c)
    fb.text(66, 58, "NO SIGNAL", fb.WHITE, 2)
    fb.show()


def play_gif(path, controls, on_dwell=None, until_s=None):
    if path.startswith("static:"):
        return play_dead_air(controls, on_dwell)
    global _BOOT_GIF
    if _BOOT_GIF is not None and _BOOT_GIF[0] == path:
        odg = _BOOT_GIF[1]             # boot-preopened decoder (see top of file)
        _BOOT_GIF = None
        fb.release()
    else:
        try:
            os.stat(path)
        except OSError:                # in the lineup, not on this drive:
            return play_missing(path, controls, on_dwell, until_s)
        odg = None
        _last = None
        for _try in range(4):          # RP2040 GC coalesces adjacent free
            fb.release()               # blocks but never COMPACTS. release()
            gc.collect()               # frees FB+slack+noise+strips and does
            gc.collect()               # NOT re-pin (the old retry called
            gc.collect()               # reclaim() between tries, re-allocating
            try:                       # FB into the fragmented heap and making
                odg = gifio.OnDiskGif(path)   # the next try WORSE). Now every
                break                  # attempt opens on the maximally-free
            except MemoryError as e:   # heap; the SLACKS margin (fbdraw) means
                _last = e              # the 88KB fits without an exact hole.
            except (OSError, ValueError) as e:
                _last = e
                break                  # not a memory issue: don't spin
        if odg is None:
            # STILL can't open it (rare fragmentation, or a bad file): do NOT
            # return "up" — that bounces the operator off the channel (10->8
            # kicked back to 10 — the Jul 22 bug). Degrade to this channel's
            # PLACEHOLDER card and STAY put; a surf press leaves normally.
            print("gif open fail:", path, _last, "free", gc.mem_free())
            return play_missing(path, controls, on_dwell, until_s)
    try:
        _send_window(odg.bitmap.width, odg.bitmap.height)
        started = time.monotonic()
        while True:
            t0 = time.monotonic()
            try:
                display.bus.send(44, odg.bitmap)
                d = odg.next_frame()
            except (OSError, ValueError, RuntimeError, MemoryError):
                # frame error mid-play (file yanked, corrupt frame, or a
                # transient alloc): do NOT draw here — odg still pins ~88KB,
                # so allocating FB now would double-alloc and crash. Just
                # bail; the finally deinits odg + reclaims, and main's
                # up-handler repaints. (No crash, no VM reload.)
                return "up"
            if on_dwell is not None and t0 - started >= KNOCK_DWELL_S:
                r = on_dwell()
                on_dwell = None            # register the seat once per stay
                if r:
                    return ("knock", r)
            if AUTO_SCAN and t0 - started >= SCAN_SECS:
                return "up"
            if until_s is not None and t0 - started >= until_s:
                return None
            if _next_eas and path != EAS_PATH and until_s is None \
                    and t0 >= _next_eas:
                return "eas"
            # inter-frame wait, SLICED so buttons/badge stay responsive even
            # on a slow (decimated) frame — the 0.40 clamp is up to 400ms
            target = t0 + min(FRAME_MAX, max(FRAME_MIN, d))
            while True:
                event = controls()
                if event:
                    return event
                try:                       # a badge poke during playback must
                    if poll_badge():       # never bubble into the reload guard
                        ev = service_badge(controls)
                        if ev:
                            return ev
                except (MemoryError, OSError, ValueError, RuntimeError):
                    pass
                now = time.monotonic()
                ant_service(now)
                if now >= target:
                    break
                time.sleep(0.03 if target - now > 0.03 else target - now)
    finally:
        odg.deinit()
        gc.collect()
        fb.reclaim()


def play_missing(path, controls, on_dwell=None, until_s=None):
    """Placeholder for any channel whose gif isn't on this drive (2MB dev
    rig, or a user-pruned pack): the license/lineup is real, the tape
    isn't in the archive. A full station otherwise: knock dwell counts,
    auto-scan parks the normal SCAN_SECS (an instant skip read as "it
    auto-moves by itself" on the rig), EAS can strike. Card wording by
    kind: unlocked secret = LICENSED CHANNEL (earned), mapped station =
    PLEASE STAND BY (classic), trap/reward one-shots (no channel of
    record) = SIGNAL INTERCEPTED."""
    base = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    secret = tuner.channel_of(path)     # only resolves for unlocked secrets
    if secret:
        num, line2 = secret, "LICENSED CHANNEL"
    elif base in CHANNEL_MAP:
        num, line2 = "CH %02d" % CHANNEL_MAP[base], "PLEASE STAND BY"
    else:                               # trap gotcha / konami / badge reward
        num, line2 = "?", "SIGNAL INTERCEPTED"
    fb.reclaim()
    started = time.monotonic()
    while True:
        fb.snow(300)
        fb.fillrect(0, 30, 240, 74, fb.BLACK)
        fb.text((fb.LW - len(num) * 18) // 2, 36, num, fb.GREEN, 3)
        fb.text((fb.LW - len(line2) * 12) // 2, 66, line2, fb.AMBER, 2)
        fb.text(54, 88, "TAPE NOT ON FILE", fb.GREY, 1)
        fb.show()
        event = controls()
        if event:
            return event
        if poll_badge():
            ev = service_badge(controls)
            if ev:
                return ev
        if on_dwell is not None and time.monotonic() - started >= KNOCK_DWELL_S:
            r = on_dwell()
            on_dwell = None
            if r:
                return ("knock", r)
        if until_s is not None and time.monotonic() - started >= until_s:
            return None                 # bounded one-shot (trap placeholder)
        if AUTO_SCAN and time.monotonic() - started >= SCAN_SECS:
            return "up"
        if until_s is None and _next_eas and \
                time.monotonic() >= _next_eas:
            return "eas"
        ant_service(time.monotonic())   # FLASH mode on placeholders too
        time.sleep(0.06)                # throttle: was 100% CPU (power)


NS_COLORS = None    # built after fb import: NO SIGNAL text color rotation


def play_dead_air(controls, on_dwell=None):
    """A 'no station' channel: rolling snow + NO SIGNAL until you surf away.
    Dead channels are valid knock seats (CF-06's final seat is CH 23).
    Single show() per frame (snow + text together — pushing snow first made
    the text flash), and the text slowly rotates colors, old-TV style."""
    global NS_COLORS
    if NS_COLORS is None:
        NS_COLORS = (fb.WHITE, fb.GREEN, fb.CYAN, fb.AMBER, fb.RED)
    fb.reclaim()
    started = time.monotonic()
    while True:
        fb.snow(520)
        col = NS_COLORS[int((time.monotonic() - started) / 0.8) % len(NS_COLORS)]
        fb.text(66, 58, "NO SIGNAL", col, 2)
        fb.show()
        event = controls()
        if event:
            return event
        if poll_badge():
            ev = service_badge(controls)
            if ev:
                return ev
        if on_dwell is not None and time.monotonic() - started >= KNOCK_DWELL_S:
            r = on_dwell()
            on_dwell = None
            if r:
                return ("knock", r)
        if AUTO_SCAN and time.monotonic() - started >= SCAN_SECS:
            return "up"
        if _next_eas and time.monotonic() >= _next_eas:
            return "eas"
        ant_service(time.monotonic())   # FLASH mode on placeholders too
        time.sleep(0.06)                # throttle: was 100% CPU (power)


# --- Controls (unchanged logic) -------------------------------------------
class Controls:
    def __init__(self):
        self._mode_down_at = None
        self._up_down_at = None
        self._dn_down_at = None
        self._combo_fired = False
        self._scan_fired = False
        self._stby_fired = False
        self._history = []
        self._last_input = time.monotonic()

    def touch(self):
        """External (non-keypad) activity: resets the standby idle timer —
        badge I2C driving the set must not let the display blank (spec)."""
        self._last_input = time.monotonic()

    def reset(self):
        self._mode_down_at = None
        self._up_down_at = None
        self._dn_down_at = None
        self._combo_fired = False
        self._scan_fired = False
        self._stby_fired = False
        self._history = []
        self._last_input = time.monotonic()
        keys.events.clear()

    def _remember(self, name):
        self._history.append(name)
        if len(self._history) > 8:
            self._history.pop(0)
        n = len(tuner.KONAMI)
        if n and len(self._history) >= n and \
                tuple(self._history[-n:]) == tuple(tuner.KONAMI):
            self._history = []
            return True
        return False

    def __call__(self):
        now = time.monotonic()
        # Hold-gesture timing checks ONLY on a drained queue: during a slow
        # channel change (static wipe + gif open can exceed SCAN_HOLD_S) a
        # button RELEASE sits unread in the queue while "still held" state
        # goes stale — that fired SCAN ON from a short surf press (rig bug,
        # Jul 22; same race as the menu's double-step).
        if not len(keys.events):
            to = _STANDBY_OPTS[SETTINGS["standby_idx"]]
            if to and not AUTO_SCAN and now - self._last_input >= to:
                self._last_input = now  # no immediate refire after wake
                return "standby"        # (paused in AUTO_SCAN: shelf demos)
            if self._mode_down_at is not None:
                if now - self._mode_down_at >= LONG_PRESS_S:
                    self._mode_down_at = None
                    return "tuner"      # MODE hold -> MASTER CONTROL (the
                                        # one-finger menu gesture)
            if (not self._combo_fired and self._up_down_at is not None
                    and self._dn_down_at is not None
                    and now - max(self._up_down_at, self._dn_down_at) >= TUNER_HOLD_S):
                self._combo_fired = True
                return "tuner"
            if (not self._scan_fired and self._up_down_at is not None
                    and self._dn_down_at is None
                    and now - self._up_down_at >= SCAN_HOLD_S):
                self._scan_fired = True
                return "scan"
            if (not self._stby_fired and self._dn_down_at is not None
                    and self._up_down_at is None
                    and now - self._dn_down_at >= SCAN_HOLD_S):
                self._stby_fired = True
                return "standby"        # CH- hold: one-finger standby
        event = keys.events.get()
        if not event:
            return None
        self._last_input = now
        # Surf fires on RELEASE, not press (like MODE): press-and-hold for
        # scan/standby/combo must not surf channels on the way in — a
        # 2.5s scan hold used to cost a channel change (plus chatter
        # extras) before SCAN ON appeared (rig feedback, Jul 22).
        if event.pressed:
            if event.key_number == BTN_UP:
                self._up_down_at = now
            elif event.key_number == BTN_DOWN:
                self._dn_down_at = now
            elif event.key_number == BTN_MODE:
                self._mode_down_at = now
        else:
            if event.key_number == BTN_UP:
                was_tap = (self._up_down_at is not None
                           and not self._scan_fired
                           and not self._combo_fired
                           and self._dn_down_at is None)
                self._up_down_at = None
                self._scan_fired = False
                if self._dn_down_at is None:
                    self._combo_fired = False
                if was_tap:
                    return "konami" if self._remember("up") else "up"
            elif event.key_number == BTN_DOWN:
                was_tap = (self._dn_down_at is not None
                           and not self._stby_fired
                           and not self._combo_fired
                           and self._up_down_at is None)
                self._dn_down_at = None
                self._stby_fired = False
                if self._up_down_at is None:
                    self._combo_fired = False
                if was_tap:
                    return "konami" if self._remember("down") else "down"
            elif event.key_number == BTN_MODE and self._mode_down_at is not None:
                self._mode_down_at = None
                return "konami" if self._remember("mode") else "mode"
        return None


def main():
    controls = Controls()
    apply_settings()
    global _BOOT_GIF, _next_eas
    if _BOOT_IS_SPLASH and _BOOT_GIF is not None:
        # Play the splash from its preopened decoder WITHOUT allocating FB (a
        # bare frame-push loop, not play_gif — play_gif's finally reclaims FB,
        # which fragments the heap so the first channel MemoryErrors: the
        # "none of the channels available" regression, Aug 4). Then deinit and
        # re-preopen the boot channel into the freed CONTIGUOUS splash hole, so
        # it opens as reliably as the original pristine-heap preopen.
        odg = _BOOT_GIF[1]
        _BOOT_GIF = None
        try:
            _send_window(odg.bitmap.width, odg.bitmap.height)
            _end = time.monotonic() + _SPLASH_HOLD_S
            _sb = False
            while time.monotonic() < _end:
                try:
                    display.bus.send(44, odg.bitmap)
                    _d = odg.next_frame()
                except Exception:
                    break
                _sb = not _sb              # boot ident: antenna seesaw
                ants[0].switch_to_output(value=_sb)
                ants[1].switch_to_output(value=not _sb)
                controls()                 # drain buttons; ignored during splash
                try:
                    poll_badge()           # v4: answer the badge's SAO scan
                except Exception:          # DURING boot — it often probes the
                    pass                   # bus before we reach the play loop,
                                           # so it never "saw" us plugged in
                time.sleep(min(FRAME_MAX, max(FRAME_MIN, _d)))
            _ant_restore()
        except Exception:
            pass
        try:
            odg.deinit()
        except Exception:
            pass
        odg = None      # CRITICAL: main() never returns, so this local would
                        # otherwise pin the splash decoder's ~88KB for the whole
                        # session — every later channel open then starves at
                        # ~65KB free (the CH-19 PLEASE STAND BY bug, Aug 4)
        global _SPLASH_PAD
        _SPLASH_PAD = None   # free the margin pad WITH the decoder: the
        gc.collect()         # coalesced ~96KB hole beats exact-fit overhead
        gc.collect()
        gc.collect()
        _bp2 = _boot_peek_path()
        if not _bp2:
            try:
                os.stat("/memes/defcon34.gif")
                _bp2 = "/memes/defcon34.gif"   # default seat: the DC34 sign
            except Exception:
                pass
        if not _bp2:
            try:
                for _f in sorted(os.listdir("/memes")):
                    if _f.lower().endswith(".gif") and not _f.startswith("."):
                        _bp2 = "/memes/" + _f
                        break
            except Exception:
                pass
        if _bp2:
            try:
                _BOOT_GIF = (_bp2, gifio.OnDiskGif(_bp2))
            except Exception:
                _BOOT_GIF = None
    channels = scan_memes()
    channel = 0
    if _BOOT_GIF is not None and _BOOT_GIF[0] in channels:
        channel = channels.index(_BOOT_GIF[0])  # boot on the preopened station
    else:
        if _BOOT_GIF is not None:               # file vanished; don't leak it
            _BOOT_GIF[1].deinit()
            _BOOT_GIF = None
        for _i, _p in enumerate(channels):      # first real station, not dead air
            if not _p.startswith("static:"):
                channel = _i
                break
    standby = False
    knocked_idx = None      # channel index already knock-registered this stay

    if ON_BADGE:            # v4.3: we detected the HOST badge's bus at boot
        ant_blip(2)         # (the official badge never reads us — see the
        show_banner("BADGE CONNECTED", 1.0)   # probe at the badge-link block)

    while True:
        if not channels:
            show_no_signal()
            event = None
            while not event:
                event = controls()
                time.sleep(0.02)
            channels = scan_memes()
        else:
            idx = channel % len(channels)
            # LAST-CHANNEL RESUME (Aug 4): the instant a mapped channel
            # comes on, it becomes the boot channel (BOOT slot + _boot_peek_path
            # — zero NVM-layout change). Diff-write only, one save per channel
            # CHANGE (~50ms, hidden inside the static wipe); power-off any time
            # resumes right here.
            _p = channels[idx]
            if _p.startswith(MEME_DIR):
                _bn = CHANNEL_MAP.get(_p.rsplit("/", 1)[-1].rsplit(".", 1)[0])
                if _bn and (SETTINGS["boot_hi"] != _bn // 10
                            or SETTINGS["boot_lo"] != (_bn % 10) * 10):
                    SETTINGS["boot_hi"] = _bn // 10
                    SETTINGS["boot_lo"] = (_bn % 10) * 10
                    tuner.settings_save(SETTINGS)
            event = play_gif(
                channels[idx], controls,
                on_dwell=None if idx == knocked_idx
                else knock_dwell_cb(channels, channel))

        if isinstance(event, tuple) and event[0] == "knock":
            knocked_idx = channel % len(channels)
            if event[1] == "step":
                ant_blip(1)
                show_banner("CARRIER HELD", 0.8)
            else:                          # full sequence -> license granted
                ant_blip(3)
                show_banner("CHANNEL UNLOCKED", 1.2)
                channels = scan_memes()
                if event[1] in channels:
                    channel = channels.index(event[1])
                    knocked_idx = None     # fresh seat on the new channel
                show_static()
        elif event == "up":
            channel += 1
            knocked_idx = None
            ant_blip(1)
            show_static(channel_label(channels, channel))
        elif event == "down":
            channel -= 1
            knocked_idx = None
            ant_blip(1)
            show_static(channel_label(channels, channel))
        elif event == "mode":
            SETTINGS["bright_idx"] = \
                (SETTINGS["bright_idx"] + 1) % len(BRIGHTNESS_LEVELS)
            set_brightness(BRIGHTNESS_LEVELS[SETTINGS["bright_idx"]])
        elif event == "staticburst":       # 0xF2: the doc-promised static
            show_static(channel_label(channels, channel))   # burst — stay
            knocked_idx = None             # put (a fresh dwell clock is fair)
        elif event == "scan":
            global AUTO_SCAN
            SETTINGS["auto_scan"] ^= 1
            AUTO_SCAN = bool(SETTINGS["auto_scan"])
            ant_blip(2 if AUTO_SCAN else 1)
            show_banner("SCAN ON" if AUTO_SCAN else "SCAN OFF")
        elif event == "tuner":
            # CH+&CH- -> MASTER CONTROL (MENU_SPEC.md). The dispatcher
            # loops menu <-> sub-screens; any TUNE outcome exits the whole
            # UI back to TV through the pre-existing knock/trap/miss block.
            fb.reclaim()
            tuner.settings_save(SETTINGS)   # flush dirty playback shortcuts
            reprobe_badge()                 # LINK row shows live badge state
            unlocked = None
            watch = None
            while True:
                sel = ui.run_menu(keys, BTN_DOWN, BTN_UP, BTN_MODE,
                                  poll=poll_ui, combo_hold_s=TUNER_HOLD_S)
                if sel == "guide":
                    act = ui.run_guide(keys, BTN_DOWN, BTN_UP, BTN_MODE,
                                       poll=poll_ui,
                                       combo_hold_s=TUNER_HOLD_S)
                    if act == "tune":
                        sel = "tune"        # fall through to the dial
                    elif act == "timeout":
                        break
                    else:
                        continue            # BOTH: back to menu
                if sel == "tune":
                    unlocked = ui.run_tuner(keys, BTN_DOWN, BTN_UP, BTN_MODE,
                                            poll=poll_ui,
                                            long_press_s=LONG_PRESS_S,
                                            combo_hold_s=TUNER_HOLD_S)
                    if unlocked is None:
                        continue            # backed out: menu again
                    break                   # tune attempt exits the UI
                elif sel == "listings":
                    rows = listings_rows(channels)
                    cur_p = channels[channel % len(channels)]
                    start = 0
                    for _i, _r in enumerate(rows):
                        if _r[3] == cur_p:
                            start = _i
                            break
                    act = ui.run_listings(keys, BTN_DOWN, BTN_UP, BTN_MODE,
                                          rows, start=start, poll=poll_ui,
                                          combo_hold_s=TUNER_HOLD_S,
                                          auto_scroll=not SETTINGS["no_autoscroll"])
                    if isinstance(act, tuple):
                        watch = act[1]
                        break               # WATCH: park the TV there
                    if act == "timeout":
                        break
                elif sel == "settings":
                    bp = channels[channel % len(channels)]
                    bn = None
                    if bp.startswith(MEME_DIR):     # BOOT CH=HERE targets:
                        _b = bp.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                        # mapped channels only — an unmapped (user-dropped)
                        # gif would store 999, which the boot peek can
                        # never resolve back to a file
                        bn = CHANNEL_MAP.get(_b)
                    _cf_before = tuner.guide_progress()[0]
                    act = ui.run_settings(
                        keys, BTN_DOWN, BTN_UP, BTN_MODE, SETTINGS,
                        cur_chan=bn,
                        apply_brightness=lambda i:
                            set_brightness(BRIGHTNESS_LEVELS[i]),
                        poll=poll_ui, combo_hold_s=TUNER_HOLD_S)
                    apply_settings()
                    if tuner.guide_progress()[0] != _cf_before:
                        # UNLOCK ALL (or a badge contact mid-settings):
                        # rebuild the lineup NOW so TV GUIDE in this same
                        # menu session shows the fresh channels — the
                        # shared rescan below only runs after UI exit
                        _cur_p = channels[channel % len(channels)] \
                            if channels else None
                        channels = scan_memes()
                        if _cur_p in channels:   # keep the same station
                            channel = channels.index(_cur_p)
                    if act == "factory":
                        show_banner("FACTORY RESET", 1.2)
                        supervisor.reload()
                    if act == "timeout":
                        break
                elif sel == "about":
                    ui.run_about(keys, BTN_DOWN, BTN_UP, BTN_MODE,
                                 poll=poll_ui, combo_hold_s=TUNER_HOLD_S)
                    # any exit returns to the menu (loop)
                else:
                    break                   # exit row / BOTH / menu timeout
            controls.reset()
            if isinstance(unlocked, tuple) and unlocked[0] == "knock":
                # dialed knock step: tuner showed CARRIER HELD — stay put
                ant_blip(2)
                unlocked = None
            elif isinstance(unlocked, tuple) and unlocked[0] == "trap":
                # gotcha: play it once, no unlock, not kept. until_s both
                # bounds the joke (~5 loops, no screen hostage) AND
                # suppresses the EAS check — a due _next_eas was truncating
                # the trap to a single frame (caught Jul 22)
                trap_path = unlocked[1]
                unlocked = None
                # v4.2: traps play INDEFINITELY — you leave by surfing, like
                # any channel (the old 20s bound then auto-returned to the
                # channel, and THAT open hit heap fragmentation from the
                # rescan: "gif open fail ... allocating 64320 free 91984",
                # serial-traced Aug 6). No auto-return = no fragile reopen.
                # Hold a due EAS off for 30s so it can't stomp the gotcha.
                if _next_eas:
                    _next_eas = max(_next_eas, time.monotonic() + 30)
                while True:
                    ev = play_gif(trap_path, controls)
                    if ev == "mode":       # brightness works mid-trap too
                        SETTINGS["bright_idx"] = (SETTINGS["bright_idx"] + 1) \
                            % len(BRIGHTNESS_LEVELS)
                        set_brightness(BRIGHTNESS_LEVELS[SETTINGS["bright_idx"]])
                        continue
                    break
                if ev == "up":
                    channel += 1
                elif ev == "down":
                    channel -= 1
                # a trap NEVER changes the lineup — skip the shared
                # scan_memes() below (its ~100 string allocs shredded the
                # contiguous hole the next decoder needs; a surf never
                # rescans, which is why CH+/CH- always recovered)
                knocked_idx = None
                show_static(channel_label(channels, channel))
                fb.release()
                gc.collect(); gc.collect(); gc.collect()
                continue
            channels = scan_memes()      # pick up any fresh unlock
            knocked_idx = None
            if unlocked == "miss":
                # "you didn't say the magic word" — the Nedry denial channel
                ni = nedry_index(channels)
                if ni is not None:
                    channel = ni
                unlocked = None
            elif unlocked and unlocked in channels:
                ant_blip(3)
                channel = channels.index(unlocked)
            elif watch and watch in channels:
                channel = channels.index(watch)
            show_static(channel_label(channels, channel))
        elif event == "konami":
            unlocked = tuner.unlock_konami()
            ant_blip(3)
            show_static()
            channels = scan_memes()
            knocked_idx = None
            if unlocked and unlocked in channels:
                channel = channels.index(unlocked)
        elif event == "eas":
            # broadcast interruption: cut to the EAS channel, then resume
            _next_eas = time.monotonic() + EAS_EVERY_S[0] + \
                random.random() * (EAS_EVERY_S[1] - EAS_EVERY_S[0])
            ant_blip(3)
            show_static()
            ev2 = play_gif(EAS_PATH, controls, until_s=EAS_HOLD_S)
            if ev2 == "up":                # honor a surf during the alert
                channel += 1
                knocked_idx = None
            elif ev2 == "down":
                channel -= 1
                knocked_idx = None
            show_static(channel_label(channels, channel))
        elif event == "badge":
            ant_blip(3)
            show_banner("BADGE CONNECTED", 1.0)   # v4: visible confirmation the
                                                  # first time the badge reads us
            show_static()                  # channel unchanged: keep the knock seat
            cur = channels[channel % len(channels)] if channels else None
            channels = scan_memes()        # surface the just-unlocked BADGE LINK
            if cur in channels:            # keep the same station across the
                channel = channels.index(cur)   # re-sorted list (don't jump)
            elif channel >= len(channels):
                channel = 0
            knocked_idx = None             # list reindexed: drop stale knock idx
        elif event == "standby":
            standby = not standby
            if standby:
                try:                       # show WHY the panel goes dark, else a
                    fb.reclaim()           # button-hold reads as 'frozen/dead'
                    fb.fill(fb.NAVY)       # (the #1 con-floor support ticket)
                    fb.text(57, 44, "STANDBY", fb.AMBER, 3)
                    fb.text(42, 92, "PRESS ANY KEY", fb.GREEN, 2)
                    fb.show()
                    time.sleep(1.1)
                except Exception:
                    pass
                tuner.settings_save(SETTINGS)   # flush before the long park
                set_brightness(0)
                fb.blank_panel()           # ST7789 display-off: GRAM stops
                for _a in ants:            # v4: park the tips dark — FLASH
                    _a.switch_to_output(value=False)   # could strand one lit
                keys.events.clear()
                import microcontroller
                try:                       # halve core dynamic power in the
                    microcontroller.cpu.frequency = 48_000_000   # one state
                except Exception:          # whose whole job is saving power
                    pass
                while True:
                    if poll_badge():       # keep answering the badge bus while parked
                        tuner.unlock_badge_link()
                    e = keys.events.get()
                    if e and e.pressed:
                        break
                    time.sleep(0.05)       # 20Hz: enough for a keypress
                try:
                    microcontroller.cpu.frequency = 125_000_000
                except Exception:
                    pass
                standby = False
                controls.reset()
                while badge_cmd_event():   # queued badge cmds must not
                    pass                   # replay as surf events on wake
                fb.unblank_panel()
                show_static()              # repaint GRAM BEFORE the light —
                set_brightness(BRIGHTNESS_LEVELS[SETTINGS["bright_idx"]])
                # ...so the stale pre-standby frame never flashes on wake


supervisor.runtime.autoreload = False
try:
    main()
except Exception as e:                 # con survival: a crash must never
    import sys as _sys                 # freeze the badge — print, pause,
    _sys.print_exception(e)            # self-restart
    try:                               # release the badge bus first: a live
        if sao_i2c is not None:        # 0x50 target would clock-stretch the
            sao_i2c.deinit()           # shared bus (stalling the badge's own
    except Exception:                  # 0x3C/0x19 devices) for the whole pause
        pass
    time.sleep(3)
    supervisor.reload()
