# DC34 Meme TV SAO — FREQUENCY TUNER + unlock persistence
# "TUNE YOUR OWN SIGNAL": hold CH+ and CH- together during playback to open
# the guide, MODE from there for the tuner. CH+/CH- spin the current digit
# (hold to auto-repeat), MODE short-press hops to the next digit, MODE
# long-press attempts to tune. secrets_config stores FNV-1a HASHES of the
# licensed frequencies (reading the file off the drive spoils nothing);
# unlock bits AND the dialed channel numbers persist in microcontroller.nvm
# behind a versioned magic header so a firmware re-flash does not wipe them.
# STATION KNOCK: ordered sequences (surfed-and-dwelt channels or dialed
# frequencies, same NNN.N namespace) acknowledged per-step with CARRIER
# HELD; completing one grants its license.
#
# Pure displayio (Bitmap/Palette/TileGrid/Group) + a built-in 5x7 glyph
# set drawn into a Bitmap: zero library deps beyond what code.py needs.
# CircuitPython 9 compatible; degrades gracefully if /secret is missing
# or nvm is unavailable (unlocks then last for the session only).



try:
    import microcontroller
    _NVM = microcontroller.nvm          # None on builds without nvm
except Exception:
    _NVM = None

try:
    from secrets_config import FREQS
except ImportError:
    FREQS = {}
try:
    from secrets_config import KONAMI
except ImportError:
    KONAMI = ("up", "up", "down", "down", "up", "down", "mode")
try:
    from secrets_config import KONAMI_GIF
except ImportError:
    KONAMI_GIF = None
try:
    from secrets_config import BADGE_GIF
except ImportError:
    BADGE_GIF = None
try:
    from secrets_config import TRAP_FREQS
except ImportError:
    TRAP_FREQS = {}
try:
    from secrets_config import KNOCKS
except ImportError:
    KNOCKS = ()
try:
    from secrets_config import SALT
except ImportError:
    SALT = ""


def _fnv(s):
    """Salted FNV-1a 32-bit of a normalized 'NNN.N' string, as 8 hex
    chars — matches sitegen/gen_secrets.py exactly."""
    x = 0x811C9DC5
    for c in (SALT + s).encode():
        x = ((x ^ c) * 0x01000193) & 0xFFFFFFFF
    return "%08x" % x

# --- NVM unlock storage -----------------------------------------------------
# Layout: b"IN34" + VERSION byte + MAX_SLOTS flag bytes (0 = locked,
# 1 = unlocked) + 2 bytes last-dial + MAX_SLOTS*2 bytes per-slot packed
# channel digits (the config only stores hashes, so the display number is
# learned at unlock time and remembered here). Header mismatch (fresh chip,
# or VERSION bump) reinitializes the block; matching header is left
# untouched across firmware updates.
MAGIC = b"IN34"
VERSION = 8                             # v8: 3 software-culture channels
BUILD = 5                               # v5: UNLOCK ALL settings row
                                        # firmware build tag, shown in ABOUT as
                                        # "FW V8.4". Free to bump per release —
                                        # unlike VERSION it is NOT in the NVM
                                        # header, so bumping it never wipes
                                        # player unlock progress.
                                        # moved visible->hidden (Jul 22);
                                        # earlier v7: FREQS table changed Jul 22
                                        # (elmothunder + trap re-paths) —
                                        # slot renumbering makes any v6
                                        # block's flags/channels misaligned
                                        # (stale rig NVM showed "--.-")
MAX_SLOTS = 28                          # headroom: FREQS + konami + badge + growth
KONAMI_SLOT = MAX_SLOTS - 1
BADGE_SLOT = MAX_SLOTS - 2              # auto-unlocked on first badge I2C contact
_HDR = len(MAGIC) + 1
_LAST_OFF = _HDR + MAX_SLOTS            # 2 bytes: packed last-dialed digits
_CHAN_OFF = _LAST_OFF + 2               # MAX_SLOTS*2: per-slot channel digits
_NVM_LEN = _CHAN_OFF + MAX_SLOTS * 2
_last_digits = None                     # session memory of the dial


def _pack_digits(d):
    return bytes([d[0] * 10 + d[1], d[2] * 10 + d[3]])


def _load_last_digits():
    """Last dialed frequency as [d,d,d,d], from session then nvm."""
    if _last_digits is not None:
        return list(_last_digits)
    if _nvm_ok():
        try:
            _flags()                    # ensure header valid
            a, b = _NVM[_LAST_OFF], _NVM[_LAST_OFF + 1]
            if a <= 99 and b <= 99 and (a or b):
                return [a // 10, a % 10, b // 10, b % 10]
        except Exception:
            pass
    return [0, 8, 7, 5]                 # factory dial position: 087.5


def _save_last_digits(d):
    global _last_digits
    _last_digits = list(d)
    if _nvm_ok():
        try:
            packed = _pack_digits(d)
            if bytes(_NVM[_LAST_OFF:_LAST_OFF + 2]) != packed:
                _NVM[_LAST_OFF:_LAST_OFF + 2] = packed
        except Exception:
            pass


def _norm(freq):
    """'88.5' -> '088.5' so hashes match the 4-digit NNN.N dial exactly."""
    return ("000" + str(freq))[-5:]


_PATHS = FREQS                          # hash -> gif path (read-only alias;
_TRAPS = TRAP_FREQS                     # dict() copies bought nothing — both
                                        # tables are membership+get only)
# slot i <-> i-th hash in sorted order. Changing FREQS renumbers slots —
# bump VERSION if the table changes after boards ship.
# _SLOTS hash order is LOAD-BEARING SECRECY — never re-sort sealed guide
# rows numerically: their sort position would become a triangulation
# oracle for the sealed channel numbers.
_SLOTS = sorted(_PATHS)[:BADGE_SLOT]
assert len(_PATHS) <= BADGE_SLOT, "too many FREQS: raise MAX_SLOTS + bump VERSION"

_ram_flags = bytearray(MAX_SLOTS)       # session fallback when nvm is out
_ram_chans = {}                         # slot -> 'NNN.N', session fallback


def _nvm_ok():
    if _NVM is None:
        return False
    try:
        return len(_NVM) >= _NVM_LEN
    except Exception:
        return False


def _flags():
    """Current unlock flags as a bytearray[MAX_SLOTS]."""
    if not _nvm_ok():
        return _ram_flags
    try:
        if bytes(_NVM[0:_HDR]) != MAGIC + bytes([VERSION]):
            _NVM[0:_NVM_LEN] = (MAGIC + bytes([VERSION])
                                + bytes(_NVM_LEN - _HDR))
        out = bytearray(_NVM[_HDR:_HDR + MAX_SLOTS])
    except Exception:
        return _ram_flags
    for i in range(MAX_SLOTS):          # merge session unlocks that failed
        if _ram_flags[i]:               # to hit flash
            out[i] = 1
    return out


def _set_chan(slot, freq):
    """Remember the plaintext channel for a slot (learned at unlock)."""
    _ram_chans[slot] = freq
    if _nvm_ok():
        try:
            d = [int(c) for c in freq if c != "."]
            off = _CHAN_OFF + slot * 2
            packed = _pack_digits(d)
            if bytes(_NVM[off:off + 2]) != packed:
                _NVM[off:off + 2] = packed
        except Exception:
            pass


def _get_chan(slot):
    """Stored 'NNN.N' for an unlocked slot, else None."""
    if slot in _ram_chans:
        return _ram_chans[slot]
    if _nvm_ok():
        try:
            off = _CHAN_OFF + slot * 2
            a, b = _NVM[off], _NVM[off + 1]
            if (a or b) and a <= 99 and b <= 99:
                return "%02d%d.%d" % (a, b // 10, b % 10)
        except Exception:
            pass
    return None


def _set_flag(slot):
    _ram_flags[slot] = 1                # always keep the session mirror
    if _nvm_ok():
        try:
            _flags()                    # ensure header exists
            if _NVM[_HDR + slot] != 1:
                _NVM[_HDR + slot:_HDR + slot + 1] = b"\x01"
        except Exception:
            pass                        # session-only unlock, still works


def factory_reset():
    """Wipe EVERYTHING persisted: unlocks, channels, last-dial, settings.
    (The old bench procedure only broke the game magic at offset 0 — bench
    BOOT CH/brightness shipped in boxes. This clears the whole region.)"""
    global _ram_flags, _ram_chans, _last_digits
    _ram_flags = bytearray(MAX_SLOTS)
    _ram_chans = {}
    _last_digits = None
    if _nvm_ok():
        try:
            _NVM[0:_SET_OFF + _SET_LEN] = bytes(_SET_OFF + _SET_LEN)
        except Exception:
            pass


# --- Settings block (MENU_SPEC.md §4) ---------------------------------------
# Appended AFTER the unlock block and SELF-versioned: settings churn must
# never wipe player progress, nor a VERSION bump wipe settings. Byte per
# field (bit-packing rejected: saves 5 bytes of 4KB, buys mask bugs).
_SET_OFF = _NVM_LEN                     # = 91; code.py's boot peek hardcodes it
_SET_MAGIC = 0x53                       # 'S'
_SET_VER = 4                            # v4: +theme (appended — boot_hi/lo
                                        # byte positions unchanged; bump
                                        # wipes settings only, never unlocks)
                                        # v2: standby default OFF->30M, and
                                        # speed_idx/static_wipe retired (kept
                                        # in the layout, no longer read)
_SET_KEYS = ("auto_scan", "dwell_idx", "ant_mode", "bright_idx",
             "no_autoscroll", "order", "standby_idx", "boot_hi", "boot_lo",
             "theme")
_SET_MAX = (1, 3, 3, 2, 1, 1, 3, 99, 99, 2)  # idx2 ant_mode 0-3 (v4: +PULSE),
                                             # idx4 no_autoscroll 0/1,
                                             # idx9 theme 0-2
SETTINGS_DEFAULTS = (0, 1, 0, 0, 0, 0, 3, 0, 0, 0)  # standby 30M: a forgotten
                                        # badge must not drain a host's AAs
_SET_LEN = 2 + len(_SET_KEYS) + 1       # magic + ver + fields + checksum


def _set_cksum(blk):
    x = 0
    for v in blk:
        x ^= v
    return x & 0xFF


def settings_load():
    """Settings dict; factory defaults on bad magic/version/checksum, and
    every index clamped so a corrupt byte can never crash the UI."""
    out = dict(zip(_SET_KEYS, SETTINGS_DEFAULTS))
    if _nvm_ok() and len(_NVM) >= _SET_OFF + _SET_LEN:
        try:
            blk = bytes(_NVM[_SET_OFF:_SET_OFF + _SET_LEN])
            if (blk[0] == _SET_MAGIC and blk[1] == _SET_VER
                    and blk[-1] == _set_cksum(blk[:-1])):
                for i, k in enumerate(_SET_KEYS):
                    out[k] = min(blk[2 + i], _SET_MAX[i])
        except Exception:
            pass
    return out


def settings_save(s):
    """Diff-write the settings block. Call on settings-screen exit/autosave,
    root-menu entry and standby entry — never per keypress or per surf."""
    if not (_nvm_ok() and len(_NVM) >= _SET_OFF + _SET_LEN):
        return
    try:
        blk = bytearray((_SET_MAGIC, _SET_VER))
        for i, k in enumerate(_SET_KEYS):
            blk.append(min(int(s.get(k, SETTINGS_DEFAULTS[i])), _SET_MAX[i]))
        blk.append(_set_cksum(blk))
        if bytes(_NVM[_SET_OFF:_SET_OFF + _SET_LEN]) != bytes(blk):
            _NVM[_SET_OFF:_SET_OFF + _SET_LEN] = bytes(blk)
    except Exception:
        pass


def badge_linked():
    """Has the badge-contact unlock happened? (menu LINK status line)"""
    return bool(_flags()[BADGE_SLOT])


# --- Unlock API (used by code.py) ------------------------------------------
def _name_from_path(p):
    """'/secret/badgelink.gif' -> 'BADGELINK' for the guide."""
    try:
        base = p.rsplit("/", 1)[-1]
        return base.rsplit(".", 1)[0].upper()[:12]
    except Exception:
        return "SIGNAL"


def guide_rows():
    """Rows for the Channel Guide progress board. Each row:
    (channel_or_None, name_or_None, unlocked). Locked rows hide their
    channel number and name so the board never leaks an answer (and the
    config only knows hashes anyway — the display number is the one
    remembered from the winning dial)."""
    flags = _flags()
    rows = []
    for i, h in enumerate(_SLOTS):
        up = bool(flags[i])
        rows.append((( _get_chan(i) or "**.*") if up else None,
                     _name_from_path(_PATHS[h]) if up else None, up))
    if KONAMI_GIF:
        up = bool(flags[KONAMI_SLOT])
        rows.append(("**.*" if up else None,
                     _name_from_path(KONAMI_GIF) if up else None, up))
    if BADGE_GIF:
        up = bool(flags[BADGE_SLOT])
        rows.append(("NET" if up else None,
                     _name_from_path(BADGE_GIF) if up else None, up))
    return rows


def channel_of(path):
    """Reverse-lookup: the channel-of-record for a /secret path, else None.
    Known only after unlock (the config stores hashes, not channels)."""
    for i, h in enumerate(_SLOTS):
        if _PATHS[h] == path:
            return _get_chan(i)
    if KONAMI_GIF and path == KONAMI_GIF:
        return "**.*"
    if BADGE_GIF and path == BADGE_GIF:
        return "NET"
    return None


def guide_progress():
    """(declassified, total) for the progress header."""
    rows = guide_rows()
    return sum(1 for r in rows if r[2]), len(rows)



def unlocked_paths():
    """Paths of ALL unlocked /secret GIFs — including files missing from
    disk (space-limited builds like the 2MB dev rig, or a user-pruned
    drive). A missing file used to silently drop the channel from the
    rotation; now code.py plays an in-fiction placeholder instead, so an
    earned license always has a channel."""
    flags = _flags()
    paths = []
    for i in range(len(_SLOTS)):
        if flags[i]:
            paths.append(_PATHS[_SLOTS[i]])
    if flags[KONAMI_SLOT] and KONAMI_GIF:
        paths.append(KONAMI_GIF)
    if flags[BADGE_SLOT] and BADGE_GIF:
        paths.append(BADGE_GIF)
    return paths


def unlock_badge_link():
    """First contact from a live badge unlocks the BADGE LINK channel."""
    if _flags()[BADGE_SLOT]:
        return False                    # already unlocked, no work
    _set_flag(BADGE_SLOT)
    return True


def unlock_konami():
    """Persist the konami unlock; returns its GIF path (or None)."""
    _set_flag(KONAMI_SLOT)
    return KONAMI_GIF


def all_unlocked():
    """True when every guide row is unlocked (SETTINGS row shows DONE)."""
    done, total = guide_progress()
    return done >= total


def unlock_all():
    """Grant every license (SETTINGS -> UNLOCK ALL, two-step confirm).
    Post-con collector option: the puzzle answers are public now, so the
    device offers the same shortcut. The config stores hashes, not
    frequencies, so the real channel numbers are LEARNED by brute-scanning
    the whole NNN.N dial — without this every slot showed **.* and the
    channels piled up unnumbered at the end of the dial.

    Blocks for a few seconds on the RP2040 (the caller shows SCANNING),
    so the loop is tuned for CircuitPython: the salt's FNV state is
    hashed ONCE and each frequency continues from it (no per-iteration
    string concat / salt re-hash), and NVM lands as two batched slice
    writes instead of up to ~54 per-slot flash rewrites."""
    base = 0x811C9DC5
    for c in SALT.encode():
        base = ((base ^ c) * 0x01000193) & 0xFFFFFFFF
    learned = {}                        # slot -> 'NNN.N'
    want = set(_SLOTS)
    for n in range(10000):
        if not want:
            break
        freq = "%03d.%d" % (n // 10, n % 10)
        x = base
        for c in freq.encode():
            x = ((x ^ c) * 0x01000193) & 0xFFFFFFFF
        h = "%08x" % x
        if h in want:
            want.discard(h)
            learned[_SLOTS.index(h)] = freq
    for i in range(len(_SLOTS)):        # RAM mirrors first: unlock works
        _ram_flags[i] = 1               # even with nvm unavailable, and a
    if KONAMI_GIF:                      # slot the scan missed still opens
        _ram_flags[KONAMI_SLOT] = 1     # (guide shows **.* for it)
    if BADGE_GIF:
        _ram_flags[BADGE_SLOT] = 1
    _ram_chans.update(learned)
    if _nvm_ok():
        try:
            _flags()                    # ensure header exists
            flags = bytearray(_NVM[_HDR:_HDR + MAX_SLOTS])
            for i in range(MAX_SLOTS):
                if _ram_flags[i]:
                    flags[i] = 1
            _NVM[_HDR:_HDR + MAX_SLOTS] = bytes(flags)
            chans = bytearray(_NVM[_CHAN_OFF:_CHAN_OFF + MAX_SLOTS * 2])
            for slot, freq in learned.items():
                d = [int(c) for c in freq if c != "."]
                chans[slot * 2:slot * 2 + 2] = _pack_digits(d)
            _NVM[_CHAN_OFF:_CHAN_OFF + MAX_SLOTS * 2] = bytes(chans)
        except Exception:
            pass                        # session-only unlock, still works


def _unlock_freq(freq):
    """freq: normalized NNN.N string. Sets the flag + remembers the
    channel for display; returns path or None."""
    h = _fnv(freq)
    if h in _PATHS and h in _SLOTS:
        slot = _SLOTS.index(h)
        _set_flag(slot)
        _set_chan(slot, freq)
        return _PATHS[h]
    return None


# --- Station knock ----------------------------------------------------------
# Ordered sequences from secrets_config.KNOCKS (step hashes). Events come
# from two sources in the same NNN.N namespace: code.py reports SURFED
# channels the operator dwelt on ('visit'), and the tuner reports DIALED
# frequencies. Each correct step is acknowledged (CARRIER HELD); the final
# step is always also a plain FREQS channel, so completing a knock grants
# the same license as dialing its last frequency.
_knock_prog = [0] * len(KNOCKS)
_knock_miss = [0] * len(KNOCKS)
_KNOCK_MISS_MAX = 3      # consecutive stray events an in-progress
                         # sequence survives before resetting


def _knock_event(freq):
    """freq: normalized NNN.N. Returns unlocked path, 'step', or None.
    In-progress sequences tolerate up to _KNOCK_MISS_MAX consecutive
    non-matching events before resetting — a single stray 3s dwell used
    to silently kill CF-06's long surf (caught in the CF-06 walkthrough). An event that
    advances ANY sequence never counts as a miss for the others."""
    h = _fnv(freq)
    out = None
    advanced = False
    for i, steps in enumerate(KNOCKS):
        p = _knock_prog[i]
        if p < len(steps) and h == steps[p]:
            _knock_prog[i] = p + 1
            _knock_miss[i] = 0
            advanced = True
            if _knock_prog[i] >= len(steps):
                _knock_prog[i] = 0
                path = _unlock_freq(freq)
                if path:
                    return path
            out = out or "step"
        elif h == steps[0]:
            _knock_prog[i] = 1          # restart the match on its first step
            _knock_miss[i] = 0
            advanced = True
            out = out or "step"
    if not advanced:
        for i in range(len(KNOCKS)):
            if _knock_prog[i]:
                _knock_miss[i] += 1
                if _knock_miss[i] >= _KNOCK_MISS_MAX:
                    _knock_prog[i] = 0
                    _knock_miss[i] = 0
    return out


def knock_visit(freq):
    """code.py hook: operator dwelt on a channel (or an unlock-relevant
    surf event). Returns unlocked path, 'step', or None."""
    return _knock_event(_norm(freq))
