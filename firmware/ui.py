# INSPECTRON 34 — menu system on fbdraw (MENU_SPEC.md is the contract)
# Decision logic lives in tuner.py — this module is visuals + input only.
#
# Universal grammar: CH+/- move/adjust (hold-to-repeat everywhere), MODE
# short selects/cycles, MODE hold is ONE big commit (TUNE, nothing else),
# CH+&CH- held = back exactly one level, idle timeouts strand-guard to TV.
#
# run_menu():     MASTER CONTROL root. Returns row key ("guide"/"listings"/
#                 "tune"/"settings"/"exit") | None (both) | "timeout".
# run_guide():    secrets-only progress board. "tune" | None | "timeout".
# run_listings(): the visible dial (rows prebuilt by code.py from
#                 scan_memes() ONLY — locked secrets structurally can't
#                 appear). ("watch", path) | None | "timeout".
# run_settings(): cycle-in-place list; mutates + SAVES on any exit.
# run_tuner():    the NNN.N dial. CH+/- spin digit (hold = auto-repeat),
#                 MODE short = next digit, MODE hold = tune.
#                 Returns: unlocked gif path | ("trap", path) | ("knock", freq)
#                 | "miss" | None (backed out). Same contract code.py handled
#                 on the displayio build. NO idle timeout (players read the
#                 puzzle site mid-dial).

import time

import fbdraw as fb
import tuner

_REPEAT_AFTER = 0.5
_REPEAT_EVERY = 0.15
# Generous idle cap for the tuner: long enough to read the puzzle site
# mid-dial (the reason there was no timeout), but a forgotten/bumped dial must
# eventually release so the TV can resume and its standby timer can run — a
# badge-powered set left lit on the dial otherwise never sleeps. Digits are
# saved on release, so reopening the tuner restores the exact position.
_TUNER_IDLE_S = 180


def _snow_bg(dots=260):
    fb.snow(dots)


def _hints(text):
    fb.text(4, fb.LH - 9, text, fb.GREY, 1)


# ------------------------------------------------------------- scaffold
def _list_loop(keys, key_down, key_up, key_mode, draw, on_move, on_select,
               poll=None, combo_hold_s=0.7, idle_s=None, animate=False):
    """Shared list-screen loop (menu/guide/listings/settings): poll()
    forwarding, CH+/- via on_move(+1/-1) with hold-to-repeat, MODE short
    -> on_select() (a non-None return exits with it), BOTH held -> None
    (back one level), idle_s without input -> "timeout" (strand-guard).
    animate=True redraws ~8fps (snow screens); False redraws only after
    input (opaque screens — full-frame python redraws are slow enough on
    the RP2040 that redrawing per event, not per tick, matters).

    ALL queued events are drained BEFORE the repeat/combo timing checks:
    checking "still held" with a release sitting in the queue is what
    made one press step twice on the rig (rig bug, Jul 21)."""
    fb.reclaim()
    keys.events.clear()                 # combo-refire discipline on entry
    up_at = down_at = None
    rpt_next = None
    last_frame = 0.0
    last_input = time.monotonic()
    dirty = True
    while True:
        now = time.monotonic()
        if poll:
            try:
                poll()
            except Exception:
                pass
        while True:                     # drain the whole queue first
            ev = keys.events.get()
            if not ev:
                break
            last_input = now
            dirty = True
            if ev.pressed:
                if ev.key_number == key_up:
                    up_at = now
                    on_move(1)
                elif ev.key_number == key_down:
                    down_at = now
                    on_move(-1)
                elif ev.key_number == key_mode:
                    r = on_select()
                    if r is not None:
                        return r
            else:
                if ev.key_number == key_up:
                    up_at = None
                elif ev.key_number == key_down:
                    down_at = None
        if idle_s and now - last_input >= idle_s:
            return "timeout"
        if up_at is not None and down_at is not None and \
                now - max(up_at, down_at) >= combo_hold_s:
            return None
        held = up_at if (up_at is not None and down_at is None) else \
            (down_at if (down_at is not None and up_at is None) else None)
        if held is None:
            rpt_next = None
        elif now - held >= _REPEAT_AFTER and \
                (rpt_next is None or now >= rpt_next):
            on_move(1 if up_at is not None else -1)
            rpt_next = now + _REPEAT_EVERY
            last_input = now
            dirty = True
        if (dirty or animate) and now - last_frame >= (0.12 if animate
                                                       else 0.03):
            last_frame = now
            draw()
            fb.show()
            dirty = False


def _bar_row(y, h=16):
    """Trinitron inverse-video highlight (the font has no '>' glyph)."""
    fb.fillrect(0, y - 2, fb.LW, h, fb.AMBER)


# ------------------------------------------------------------ main menu
# Naming (rig feedback, Jul 22): the secrets board is CASE FILES (matches
# the site's CF-## case numbers), the watchable lineup is TV GUIDE —
# "channel guide" vs "tv listings" were near-synonyms nobody could tell
# apart.
# TV GUIDE first (rig feedback): watching is the common case; the game
# board is one CH- away. Cursor pre-seats on row 0.
_MENU_ROWS = (("listings", "TV GUIDE"), ("guide", "CASE FILES"),
              ("tune", "FREQ TUNER"), ("settings", "SETTINGS"),
              ("about", "ABOUT"), ("exit", "EXIT TO TV"))


# cursor persists across a MODE-in / BOTH-out round trip: re-entering the
# menu after backing out of a sub-screen keeps you where you were, not row 0
_menu_cur = [0]


def run_menu(keys, key_down, key_up, key_mode, poll=None, combo_hold_s=0.7):
    """MASTER CONTROL root menu. Cursor persists across sub-screen round
    trips; the dial path is MODE-hold, then MODE from the remembered row."""
    cur = _menu_cur

    def draw():
        fb.fill(fb.NAVY)                # opaque bureau paperwork, not snow
        fb.text(4, 3, "MASTER CONTROL", fb.AMBER, 2)
        fb.text(190, 6, "CF %d/%d" % tuner.guide_progress(), fb.GREEN, 1)
        y = 20
        for i, (_key, label) in enumerate(_MENU_ROWS):
            if i == cur[0]:
                _bar_row(y)
                fb.text(8, y, label, fb.NAVY, 2)
            else:
                fb.text(8, y, label, fb.WHITE, 2)
            y += 15          # 6 rows now (ABOUT added): fit above the y=112 status
        link_up = tuner.badge_linked()  # live: flips the instant a badge
        on_badge = getattr(tuner, "ON_BADGE", False)   # host-badge probe (v4)
        fb.text(4, 112, "LINK UP" if link_up
                else ("ON BADGE" if on_badge else "LINK NO CARRIER"),
                fb.GREEN if (link_up or on_badge) else fb.GREY, 1)
        fb.text(196, 112, "FW V%d" % getattr(tuner, "BUILD", 0),
                fb.GREY, 1)     # the user-facing version is BUILD alone —
                                # tuner.VERSION is the NVM unlock-table rev
                                # and reads as gibberish next to "v4"
        _hints("CH+- MOVE  MODE OK  BOTH EXIT")

    def on_move(d):
        cur[0] = (cur[0] - d) % len(_MENU_ROWS)     # CH+ moves the bar up

    return _list_loop(keys, key_down, key_up, key_mode, draw, on_move,
                      lambda: _MENU_ROWS[cur[0]][0], poll=poll,
                      combo_hold_s=combo_hold_s, idle_s=30, animate=True)


def _scrollbar(top, vis, total, y0=22, h=98):
    """Track + AMBER thumb at the right edge. The +/- arrows were
    invisible feedback: with many identical SEALED rows, scrolling looked
    like nothing happened (rig feedback, Jul 22)."""
    if total <= vis:
        return
    fb.fillrect(233, y0, 4, h, _TRACK)
    th = max(10, h * vis // total)
    ty = y0 + (h - th) * top // (total - vis)
    fb.fillrect(233, ty, 4, th, fb.AMBER)


_TRACK = fb._rgb(45, 45, 45)


# --------------------------------------------------------------- guide
_TEASERS = ("SOME CARRIERS ANSWER ONLY TO A KNOCK",
            "DEAD AIR IS NOT ALWAYS DEAD",
            "CASE FILES AT INSPECTRON34.COM",
            "THE NETWORK REMEMBERS FIRST CONTACT",
            "QR IN ABOUT TUNES THE CASE SITE")


def run_guide(keys, key_down, key_up, key_mode, poll=None, combo_hold_s=0.7):
    """CASE FILES progress board (secrets only — see the _SLOTS
    load-bearing-secrecy note in tuner.py)."""
    rows = tuner.guide_rows()
    done, total = tuner.guide_progress()
    top = [0]
    VIS = 5
    t0 = time.monotonic()
    last = ((len(rows) - 1) // VIS) * VIS if rows else 0
    pages = last // VIS + 1

    def draw():
        # OPAQUE navy: any snow behind the rows (even with backing bars)
        # flickered around the text on the physical panel — twice-reported
        # rig feedback, Jul 22
        fb.fill(fb.NAVY)
        fb.text(4, 3, "CASE FILES", fb.AMBER, 2)
        fb.text(196, 6, "%d/%d" % (done, total), fb.GREEN, 1)
        y = 22
        for ch, name, unlocked in rows[top[0]:top[0] + VIS]:
            if unlocked:
                fb.text(4, y, (ch or "??.?"), fb.GREEN, 2)
                fb.text(76, y, (name or "")[:11], fb.WHITE, 2)
            else:
                fb.text(4, y, "--.-", fb.GREY, 2)
                fb.text(76, y, "SEALED", fb.GREY, 2)
            y += 20
        _scrollbar(top[0], VIS, len(rows))
        # footer rotates page+hint <-> mechanic teasers while sealed remain
        slot = int((time.monotonic() - t0) / 4)
        if done < total and slot % 2:
            fb.text(4, fb.LH - 9, _TEASERS[(slot // 2) % len(_TEASERS)],
                    fb.CYAN, 1)
        else:
            _hints("PG %d/%d  CH+- PAGE  MODE DIAL  BOTH BACK"
                   % (top[0] // VIS + 1, pages))

    def on_move(d):
        # page-at-a-time: line-scrolling past identical SEALED rows gave
        # no visible feedback (rig feedback: "should show pages")
        top[0] = max(0, min(last, top[0] - d * VIS))

    return _list_loop(keys, key_down, key_up, key_mode, draw, on_move,
                      lambda: "tune", poll=poll,
                      combo_hold_s=combo_hold_s, idle_s=120, animate=True)


# ------------------------------------------------------------ listings
def run_listings(keys, key_down, key_up, key_mode, rows, start=0, poll=None,
                 combo_hold_s=0.7, auto_scroll=True):
    """TV GUIDE: the visible dial as a remote control. rows =
    ((label, name, kind, path), ...) prebuilt by code.py; kind is
    "meme"/"dead"/"secret". Opens on the channel that was playing and
    AUTO-SCROLLS Prevue-Guide style until the first CH+/- press takes
    manual control (rig request: "cool if it scrolled")."""
    cur = [start % max(1, len(rows))]
    VIS = 4
    # None = manual mode; SETTINGS "TV SCROLL: OFF" starts manual (no auto-scroll)
    auto = [time.monotonic() if auto_scroll else None]

    def draw():
        if auto[0] is not None and time.monotonic() - auto[0] >= 1.2:
            auto[0] = time.monotonic()
            cur[0] = (cur[0] + 1) % len(rows)
        fb.fill(fb.NAVY)                # opaque like the board (readability)
        fb.text(4, 3, "TV GUIDE", fb.AMBER, 2)
        top = max(0, min(cur[0] - 1, len(rows) - VIS))
        y = 22
        for i in range(top, min(top + VIS, len(rows))):
            label, name, kind, _p = rows[i]
            sel = i == cur[0]
            if sel:
                _bar_row(y)
            ncol = fb.NAVY if sel else (
                fb.GREY if kind == "dead" else
                fb.AMBER if kind == "secret" else fb.GREEN)
            tcol = fb.NAVY if sel else \
                (fb.GREY if kind == "dead" else fb.WHITE)
            fb.text(8, y, label, ncol, 2)
            fb.text(96, y, name[:11], tcol, 2)
            y += 20
        _scrollbar(top, VIS, len(rows), h=76)
        _hints("CH+- SCROLL  MODE WATCH  BOTH BACK")

    def on_move(d):
        auto[0] = None                  # first press takes manual control
        cur[0] = (cur[0] - d) % len(rows)

    return _list_loop(keys, key_down, key_up, key_mode, draw, on_move,
                      lambda: ("watch", rows[cur[0]][3]), poll=poll,
                      combo_hold_s=combo_hold_s, idle_s=90, animate=True)


# ------------------------------------------------------------ settings
# SPEED + STATIC WIPE removed (SPEED un-did the pack's decimation retune;
# both are fixed in code.apply_settings). STANDBY promoted above the fold
# (it's the battery setting), BOOT CH last (its only surprise is persistent).
_SET_ROWS = (("BRIGHTNESS", ("MED", "LOW", "HIGH"), "bright_idx"),
             ("THEME", ("DEFAULT", "DC34", "INVERSE"), "theme"),
             ("STANDBY", ("OFF", "5M", "15M", "30M"), "standby_idx"),
             ("AUTO SCAN", ("OFF", "ON"), "auto_scan"),
             ("SCAN DWELL", ("4S", "8S", "15S", "30S"), "dwell_idx"),
             ("SURF ORDER", ("DIAL", "SHUFFLE"), "order"),
             ("TV SCROLL", ("ON", "OFF"), "no_autoscroll"),   # auto-scroll guide
             ("ANT LED", ("OFF", "FLASH", "ON", "PULSE"), "ant_mode"),
             ("RESUME", None, None),    # last-watched channel (auto-saved);
                                        # MODE = clear <-> pin HERE
             ("UNLOCK ALL", None, "unlockall"),  # two-step: grant every license
                                        # (post-con collector option — answers
                                        # are public; see tuner.unlock_all)
             ("FACTORY RST", None, "factory"),   # two-step: MODE arms, MODE wipes
             ("SAVE + BACK", None, "back"))      # explicit exit: the BOTH pinch
                                        # is hard on a worn badge (same reason
                                        # menu entry gained MODE-hold, Jul 22)


def _boot_label(s):
    n = s["boot_hi"] * 10 + s["boot_lo"] // 10   # _pack_digits of NNN.0
    return ("CH %d" % n) if n else "FIRST"


def run_settings(keys, key_down, key_up, key_mode, settings, cur_chan=None,
                 apply_brightness=None, poll=None, combo_hold_s=0.7):
    """SETTINGS: cycle-in-place. Mutates `settings` and SAVES on any exit
    (BOTH -> None back to menu; idle autosaves -> "timeout" -> TV — never
    silently discard). cur_chan = current channel as an int for BOOT CH =
    HERE, or None when it can't be a boot target (secret NN.N -> FIRST)."""
    cur = [0]
    VIS = 5
    armed = [None]                      # row index awaiting its 2nd MODE
                                        # (was a bool: with UNLOCK ALL and
                                        # FACTORY RST both on screen, one
                                        # armed flag lit BOTH rows "SURE?")

    def draw():
        fb.fill(fb.NAVY)
        fb.text(4, 3, "SETTINGS", fb.AMBER, 2)
        top = max(0, min(cur[0] - 2, len(_SET_ROWS) - VIS))
        y = 22
        for i in range(top, min(top + VIS, len(_SET_ROWS))):
            label, opts, key = _SET_ROWS[i]
            if key == "back":
                val = ""
            elif key == "factory":
                val = "SURE?" if armed[0] == i else "NO"
            elif key == "unlockall":
                val = "SURE?" if armed[0] == i else \
                    ("DONE" if tuner.all_unlocked() else "NO")
            elif opts is None:
                val = _boot_label(settings)
            else:
                val = opts[min(settings[key], len(opts) - 1)]
            sel = i == cur[0]
            if sel:
                _bar_row(y)
            fb.text(8, y, label, fb.NAVY if sel else fb.WHITE, 2)
            fb.text(152, y, val, fb.NAVY if sel else fb.GREEN, 2)
            y += 17
        if top > 0:
            fb.text(228, 22, "+", fb.AMBER, 1)
        if top + VIS < len(_SET_ROWS):
            fb.text(228, 100, "-", fb.AMBER, 1)
        _hints("CH+- ROW  MODE CHANGE  BOTH SAVE")

    def on_move(d):
        armed[0] = None                 # moving away disarms a 2-step row
        cur[0] = (cur[0] - d) % len(_SET_ROWS)

    def on_select():
        _label, opts, key = _SET_ROWS[cur[0]]
        if key == "back":
            return "back"               # exits the loop; saved below like BOTH
        if key == "factory":
            if armed[0] != cur[0]:
                armed[0] = cur[0]       # first MODE arms; second wipes
                return None
            tuner.factory_reset()
            return "factory"
        if key == "unlockall":
            if tuner.all_unlocked():
                return None             # nothing left to grant
            if armed[0] != cur[0]:
                armed[0] = cur[0]       # first MODE arms; second grants
                return None
            armed[0] = None
            fb.fill(fb.NAVY)            # the scan blocks a few seconds on
            fb.text(42, 60, "SCANNING BAND", fb.GREEN, 2)   # the RP2040 —
            fb.show()                   # never leave SURE? frozen meanwhile
            tuner.unlock_all()          # brute-learns the real numbers
            keys.events.clear()         # drop presses queued during the scan
            _bumper("CHANNELS UNLOCKED", fb.AMBER)  # 17ch*12px fits LW 240
            return None                 # back to settings; cell reads DONE
        if opts is None:                # BOOT CH: FIRST <-> HERE
            if settings["boot_hi"] or settings["boot_lo"]:
                settings["boot_hi"] = settings["boot_lo"] = 0
            elif cur_chan:
                settings["boot_hi"] = cur_chan // 10
                settings["boot_lo"] = (cur_chan % 10) * 10
        else:
            settings[key] = (settings[key] + 1) % len(opts)
            if key == "bright_idx" and apply_brightness:
                apply_brightness(settings[key])   # live, per cycle
            elif key == "theme":
                fb.set_theme(settings[key])       # live: this screen repaints
                                                  # in the new accents now
        return None                     # cycling never exits the screen

    r = _list_loop(keys, key_down, key_up, key_mode, draw, on_move,
                   on_select, poll=poll, combo_hold_s=combo_hold_s,
                   idle_s=20)
    if r != "factory":                  # a wiped block must NOT be re-saved
        tuner.settings_save(settings)
    return r


# --------------------------------------------------------------- about
# QR for https://inspectron34.com (v2, 25x25, ECC-L), rows packed MSB-first.
# Generated offline (qrcode lib); drawn 4px/module with a light quiet zone.
_QR_N = 25
_QR_ROWS = (33350783,17055041,24437085,24473437,24466781,17090625,33379711,
            38400,26139416,2703934,22525611,24207641,23381601,29088674,
            19713915,17356717,24961012,65808,33363281,17131281,24444916,
            24403907,24415373,17139057,33411529)


def _draw_qr(x0, y0, scale=4):
    quiet = 2 * scale
    side = _QR_N * scale + 2 * quiet
    fb.fillrect(x0, y0, side, side, fb.WHITE)
    for ry, rowbits in enumerate(_QR_ROWS):
        run = -1
        for rx in range(_QR_N):
            on = (rowbits >> (_QR_N - 1 - rx)) & 1
            if on and run < 0:
                run = rx
            if (not on or rx == _QR_N - 1) and run >= 0:
                end = rx + 1 if (on and rx == _QR_N - 1) else rx
                fb.fillrect(x0 + quiet + run * scale, y0 + quiet + ry * scale,
                            (end - run) * scale, scale, fb.BLACK)
                run = -1


def run_about(keys, key_down, key_up, key_mode, poll=None, combo_hold_s=0.7):
    """ABOUT: project + maker credits (mindtricks.io / x.com/d4rkwyng) and a
    scannable QR to inspectron34.com. Any key or a 30s idle returns to the
    menu. The panel font is uppercase and has no '@'."""
    fb.reclaim()
    keys.events.clear()
    last = time.monotonic()
    drawn = False
    while True:
        now = time.monotonic()
        if poll:
            try:
                poll()
            except Exception:
                pass
        pressed = False
        while True:
            ev = keys.events.get()
            if not ev:
                break
            last = now
            if ev.pressed:                  # any press leaves the info screen
                pressed = True
        if pressed or now - last >= 30:
            return None
        if not drawn:
            drawn = True
            fb.fill(fb.NAVY)
            # left column: credits. right: QR to the case-file site.
            fb.text(4, 4, "INSPECTRON 34", fb.AMBER, 1)
            fb.text(4, 18, "DEF CON 34", fb.GREEN, 1)
            fb.text(4, 36, "BY D4RKWYNG", fb.WHITE, 1)
            fb.text(4, 50, "MINDTRICKS.IO", fb.GREEN, 1)
            fb.text(4, 64, "X - D4RKWYNG", fb.GREEN, 1)
            fb.text(4, 84, "CASE FILES-", fb.AMBER, 1)
            fb.text(4, 98, "INSPECTRON34", fb.AMBER, 1)
            fb.text(4, 112, ".COM", fb.AMBER, 1)
            _draw_qr(122, 9, 4)          # 116px square, right side
            _hints("ANY KEY EXIT")
            fb.show()
        time.sleep(0.03)


# --------------------------------------------------------------- dial
def _draw_dial(digits, cursor):
    fb.fill(fb.NAVY)   # opaque: text on rolling snow shimmered (rig)
    fb.text(78, 4, "CHANNEL", fb.AMBER, 2)
    # big NNN.N readout: 5 glyph cells at scale 5 (30px each) centered
    text = "%d%d%d.%d" % (digits[0], digits[1], digits[2], digits[3])
    x0 = (fb.LW - 5 * 30) // 2
    for _i, _ch in enumerate(text):     # per-char: 11 cached glyph strips
        fb.text(x0 + _i * 30, 40, _ch, fb.GREEN, 5)
    slot = cursor if cursor < 3 else 4          # cell 3 is the dot
    fb.fillrect(x0 + slot * 30 + 2, 78, 24, 4, fb.AMBER)
    fb.text(216, 92, "CH", fb.GREEN, 1)
    _hints("CH+- SPIN  MODE NEXT  HOLD TUNE")


def _bumper(text, color, blinks=3):
    """Blinking centered bumper over static. fill() FIRST: snow() silently
    no-ops when the tiles can't allocate (menu context pins FB+cache), which
    left the banner drawn OVER the still-visible menu — unreadable."""
    w = len(text) * 12
    def _bg():
        fb.fill(fb.BLACK)
        _snow_bg(200)                   # texture when memory allows; opaque
    for _ in range(blinks):             # black base either way
        _bg()
        fb.text((fb.LW - w) // 2, 60, text, color, 2)
        fb.show()
        time.sleep(0.28)
        _bg()
        fb.show()
        time.sleep(0.12)
    _bg()
    fb.text((fb.LW - w) // 2, 60, text, color, 2)
    fb.show()
    time.sleep(0.6)


def _no_signal_burst(seconds=2.5):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        fb.fill(fb.BLACK)               # opaque base (snow may be starved)
        fb.snow(900)
        fb.text(66, 58, "NO SIGNAL", fb.RED, 2)
        fb.show()
        time.sleep(0.05)


def run_tuner(keys, key_down, key_up, key_mode, poll=None,
              long_press_s=1.0, combo_hold_s=0.7):
    """FREQUENCY TUNER. Blocks until tune attempt or exit; see module doc."""
    fb.reclaim()
    digits = tuner._load_last_digits()
    cursor = 0
    keys.events.clear()

    mode_down_at = None
    up_at = down_at = None
    rpt_next = None
    last_frame = 0.0
    last_input = time.monotonic()

    while True:
        now = time.monotonic()
        if poll:
            try:
                poll()
            except Exception:
                pass

        # Drain ALL queued events BEFORE the timing checks — same race fix
        # as _list_loop/Controls (a queued MODE release must not let the
        # long-press clock go stale through a slow dial frame and commit a
        # TUNE the player never asked for).
        while True:
            ev = keys.events.get()
            if not ev:
                break
            last_input = now
            if ev.pressed:
                if ev.key_number == key_up:
                    up_at = now
                    digits[cursor] = (digits[cursor] + 1) % 10
                elif ev.key_number == key_down:
                    down_at = now
                    digits[cursor] = (digits[cursor] - 1) % 10
                elif ev.key_number == key_mode:
                    mode_down_at = now
            else:
                if ev.key_number == key_up:
                    up_at = None
                elif ev.key_number == key_down:
                    down_at = None
                elif ev.key_number == key_mode and mode_down_at is not None:
                    mode_down_at = None      # short press: next digit
                    cursor = (cursor + 1) % 4

        # hold-to-repeat: one digit key held alone auto-spins (both = exit)
        held = up_at if (up_at is not None and down_at is None) else \
            (down_at if (down_at is not None and up_at is None) else None)
        if held is None:
            rpt_next = None
        elif now - held >= _REPEAT_AFTER:
            if rpt_next is None or now >= rpt_next:
                digits[cursor] = (digits[cursor]
                                  + (1 if up_at is not None else -1)) % 10
                rpt_next = now + _REPEAT_EVERY

        # MODE long-press: attempt to tune
        if mode_down_at is not None and now - mode_down_at >= long_press_s:
            mode_down_at = None
            freq = "%d%d%d.%d" % (digits[0], digits[1], digits[2], digits[3])
            tuner._save_last_digits(digits)
            path = tuner._unlock_freq(freq)
            if path is not None:
                _bumper("CHANNEL UNLOCKED", fb.AMBER)
                return path
            if tuner._fnv(freq) in tuner._TRAPS:
                fb.static(5)
                return ("trap", tuner._TRAPS[tuner._fnv(freq)])
            if tuner._knock_event(freq) == "step":
                # a knock step: acknowledge, don't punish (playtest: silent
                # static here made players abandon correct sequences)
                _bumper("CARRIER HELD", fb.GREEN, blinks=2)
                return ("knock", freq)
            _no_signal_burst()
            return "miss"

        # CH+ & CH- held together: back out to the menu
        if up_at is not None and down_at is not None and \
                now - max(up_at, down_at) >= combo_hold_s:
            tuner._save_last_digits(digits)
            return None

        # idle cap: release a forgotten/bumped dial so the TV resumes and its
        # standby timer can run (digits persist; reopening restores them)
        if now - last_input >= _TUNER_IDLE_S:
            tuner._save_last_digits(digits)
            return None

        if now - last_frame >= 0.08:
            last_frame = now
            _draw_dial(digits, cursor)
            fb.show()
