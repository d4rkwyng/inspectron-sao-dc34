# fbdraw - direct ST7789 framebuffer, LANDSCAPE coords -> portrait buffer, no displayio render
#
# v3: the framebuffer is a displayio.Bitmap and ALL hot drawing is C calls
# (bitmaptools.fill_region / blit / rotozoom). Measured on the rig (Jul 21):
# the interpreter floor is ~0.7ms PER PYTHON OP — a bare `pass` loop
# iteration! — so any per-pixel or per-run python rendering costs hundreds
# of ms per frame (the menu took 2+ seconds to repaint). Text strings are
# rendered ONCE into small cached bitmaps (python at scale 1, scaled up in
# C by rotozoom), then each frame is ~a dozen C calls: fill + bars + one
# blit per string. Bitmap works with display.bus.send exactly like the
# gifio path (buffer protocol, 134*2 B rows, word-aligned).
import struct, random, gc
import displayio, bitmaptools

BW, BH = 134, 240          # portrait buffer (bitmap is BW wide, BH tall)
LW, LH = 240, 134          # landscape logical
FBN = BW*BH*2              # bytes sent to the panel
SLACKS = (32768, 24024)    # decoder-hole reserve. The decoder needs ~24024B
                           # LZW workspace + a 64320B frame bitmap = 88344
                           # EXACT. A reserve == exactly that has ZERO margin,
                           # so any transient allocation from the intervening
                           # screen (a placeholder card's text strips, a menu)
                           # left in the freed hole makes the open fail
                           # intermittently ("sometimes STAND BY"). The
                           # ~7KB the tile-freeing rework freed buys an 8KB
                           # margin here (32768 vs 24024): freeing FB+_slack
                           # now leaves ~97KB, so the 88KB decoder fits even
                           # with small interlopers. Falls back to 24024 if
                           # the bigger reserve can't be pinned. (Earlier the
                           # exact-fit was needed because the merged app had
                           # no spare; that rework changed it. rig bug:
                           # surfing onto a gif bounced straight off)
_disp = None
FB = None                  # displayio.Bitmap, lazily allocated by reclaim()
_slack = None              # companion bytearray freed together with FB
_SKIP = 0x0001             # transparent sentinel in text/glyph bitmaps

# Colors are PRE-SWAPPED RGB565 (hi/lo bytes exchanged): the bitmap stores
# uint16 little-endian and bus.send pushes raw memory, so the swap puts the
# high color byte on the wire first, same trick as gifio's RGB565_SWAPPED.
def _rgb(r,g,b):
    v=((r&0xF8)<<8)|((g&0xFC)<<3)|(b>>3)
    return ((v&0xFF)<<8)|(v>>8)
WHITE=_rgb(255,255,255); BLACK=0; NAVY=_rgb(10,14,44); GREEN=_rgb(0,255,90)
AMBER=_rgb(255,176,0); RED=_rgb(255,40,40); GREY=_rgb(120,120,120); CYAN=_rgb(0,220,220)

# SETTINGS "THEME": AMBER/GREEN are the two accent SLOTS every screen draws
# with (titles/highlight bar vs values/numbers) — set_theme() reassigns the
# pair and all callers pick it up live (fb.AMBER is looked up per call; the
# glyph cache keys on color, so old strips just age out of the LRU).
_THEMES = (((255,176,0), (0,255,90)),   # 0 DEFAULT: amber + green
           ((170,90,240), (0,255,90)),  # 1 DC34: purple + green
           ((0,255,90), (255,176,0)))   # 2 INVERSE: green + amber
def set_theme(i):
    global AMBER, GREEN
    a, g = _THEMES[i % len(_THEMES)]
    AMBER = _rgb(*a); GREEN = _rgb(*g)

def init(display):
    # display handle only — FB stays lazy, and noise tiles are NOT built
    # here anymore: carve()/release() free them during playback (they're the
    # 13KB that decides whether a gif opens), so building them eagerly at
    # boot was pure churn — freed unused before the first frame. They lazily
    # rebuild (~100ms) at the first static transition, which happens before
    # any snow is ever shown.
    global _disp; _disp=display
    gc.collect()
def release():                     # free the UI buffer so a GIF frame can allocate
    global FB, _slack, _noise; FB=None; _slack=None; _noise=None
    drop_cache()                   # strips + noise tiles are dead weight
    gc.collect()                   # during playback; tiles lazily rebuild
                                   # (~100ms) at the next static transition
def carve():
    # Free EVERYTHING nonessential before an OnDiskGif — measured on the
    # rig (Jul 24): the decoder needs 88,344B (64320 bitmap + 24024 LZW
    # workspace) and the heap had only 79,872 free with the tiles resident.
    # The ~13KB of noise tiles are the difference between every gif open
    # failing and all of them working; they lazily rebuild on next snow().
    global FB, _slack, _noise; FB=None; _slack=None; _noise=None
    drop_cache()
    gc.collect()
def reclaim():                     # re-acquire the pinned UI buffer after a GIF
    # TOTAL FUNCTION: must NEVER raise. Every draw op below no-ops when FB is
    # None, so a momentary starvation just skips a frame — the next reclaim
    # retries. An uncaught MemoryError here was THE "channel 99 lockup": it
    # escaped play_gif -> the reload guard -> crash-loop -> REPL (Jul 24).
    global FB, _slack
    if FB is None:
        for _step in range(3):
            gc.collect()
            try:
                FB=displayio.Bitmap(BW, BH, 65536)
                break
            except MemoryError:
                drop_cache()                  # shed strips, tiles, slack and
                _slack=None; _drop_noise()    # try again — never propagate
        if FB is None:
            return                            # degraded: callers no-op-draw
    if _slack is None:            # keep the freed hole decoder-sized —
        for _n in SLACKS:         # but NEVER re-pin over a live slack: the
            try:                  # new bytearray allocs beside the old one,
                _slack=bytearray(_n)  # MemoryErrors, and the fallback
                break                 # permanently downgrades to the
            except MemoryError:       # zero-margin 24024 reserve
                _slack=None       # try smaller; None = degraded (UI
                                  # works, next open needs luck)
def _drop_noise():
    global _noise; _noise=None
def fill(c):
    if FB is None: return
    bitmaptools.fill_region(FB, 0, 0, BW, BH, c)
def px(sx,sy,c):
    if FB is not None and 0<=sx<LW and 0<=sy<LH:
        FB[sy, 239-sx]=c
def fillrect(x,y,w,h,c):
    # landscape rect -> portrait rect, clipped (C fill)
    if FB is None: return
    if x<0: w+=x; x=0
    if y<0: h+=y; y=0
    if x+w>LW: w=LW-x
    if y+h>LH: h=LH-y
    if w<=0 or h<=0: return
    bitmaptools.fill_region(FB, y, 240-x-w, y+h, 240-x, c)
def hline(x,y,w,c): fillrect(x,y,w,1,c)
def vline(x,y,h,c): fillrect(x,y,1,h,c)
def rect(x,y,w,h,c):
    hline(x,y,w,c); hline(x,y+h-1,w,c); vline(x,y,h,c); vline(x+w-1,y,h,c)
# 5x7 glyphs packed: key i -> _FGLYPH[i*7:i*7+7]. Was a 43-entry dict of
# 7-int tuples (~2.4KB resident heap); bytes+find is ~380B and shrinks the
# .mpy too. bytes indexing returns ints, so g[ry] is unchanged. The .find()
# is one op per glyph per CACHE MISS only (strips are built once).
_FKEYS='CDEFRABJPQVWYSGIKLNOTUXMHZ 0123456789.-+*/?'
_FGLYPH=b'\x0e\x11\x10\x10\x10\x11\x0e\x1e\x11\x11\x11\x11\x11\x1e\x1f\x10\x10\x1e\x10\x10\x1f\x1f\x10\x10\x1e\x10\x10\x10\x1e\x11\x11\x1e\x14\x12\x11\x0e\x11\x11\x1f\x11\x11\x11\x1e\x11\x11\x1e\x11\x11\x1e\x07\x02\x02\x02\x02\x12\x0c\x1e\x11\x11\x1e\x10\x10\x10\x0e\x11\x11\x11\x15\x12\r\x11\x11\x11\x11\x11\n\x04\x11\x11\x11\x15\x15\x1b\x11\x11\x11\n\x04\x04\x04\x04\x0f\x10\x10\x0e\x01\x01\x1e\x0e\x11\x10\x17\x11\x11\x0f\x0e\x04\x04\x04\x04\x04\x0e\x11\x12\x14\x18\x14\x12\x11\x10\x10\x10\x10\x10\x10\x1f\x11\x19\x15\x13\x11\x11\x11\x0e\x11\x11\x11\x11\x11\x0e\x1f\x04\x04\x04\x04\x04\x04\x11\x11\x11\x11\x11\x11\x0e\x11\x11\n\x04\n\x11\x11\x11\x1b\x15\x15\x11\x11\x11\x11\x11\x11\x1f\x11\x11\x11\x1f\x01\x02\x04\x08\x10\x1f\x00\x00\x00\x00\x00\x00\x00\x0e\x11\x13\x15\x19\x11\x0e\x04\x0c\x04\x04\x04\x04\x0e\x0e\x11\x01\x02\x04\x08\x1f\x1f\x02\x04\x02\x01\x11\x0e\x02\x06\n\x12\x1f\x02\x02\x1f\x10\x1e\x01\x01\x11\x0e\x06\x08\x10\x1e\x11\x11\x0e\x1f\x01\x02\x04\x08\x08\x08\x0e\x11\x11\x0e\x11\x11\x0e\x0e\x11\x11\x0f\x01\x02\x0c\x00\x00\x00\x00\x00\x0c\x0c\x00\x00\x00\x1f\x00\x00\x00\x00\x04\x04\x1f\x04\x04\x00\x00\x15\x0e\x1f\x0e\x15\x00\x01\x01\x02\x04\x08\x10\x10\x0e\x11\x01\x06\x04\x00\x04'
def _glyph(ch):
    i=_FKEYS.find(ch)
    return _FGLYPH[i*7:i*7+7] if i>=0 else None

# --- cached string strips ---------------------------------------------------
# (string, color, scale) -> portrait-oriented Bitmap. Built once (~0.2s of
# python for a menu row, then C-scaled), blitted per frame in ONE C call.
# Bounded so a busy session can't eat the heap; dropped wholesale under
# memory pressure (play_gif's MemoryError retry calls drop_cache()).
_tcache = {}
_tcache_px = 0
_TCACHE_MAX_PX = 14000     # ~28KB of strips: with FB+slack (93KB) pinned
                           # during UI, a bigger cache exhausts the heap
                           # (rig crash: MemoryError building a menu strip)

def drop_cache():
    global _tcache, _tcache_px
    _tcache = {}; _tcache_px = 0
    gc.collect()

def _cost(key):
    s, _c, scale = key
    return 7 * scale * len(s) * 6 * scale

def _strip(s, c, scale):
    global _tcache_px
    key = (s, c, scale)
    st = _tcache.get(key)
    if st is not None:
        _tcache.pop(key)                 # LRU touch: move to the end so
        _tcache[key] = st                # eviction hits stale strips first
        return st
    need = _cost(key)
    # Evict least-recently-used strips until the new one fits. Wholesale
    # drop_cache() here made EVERY cursor move rebuild the whole screen
    # once a screen's working set neared the cap (caught Jul 22:
    # menu steady state ~13.3K px vs the 14K cap).
    while _tcache and _tcache_px + need > _TCACHE_MAX_PX:
        old = next(iter(_tcache))
        _tcache.pop(old)
        _tcache_px -= _cost(old)
    try:
        st = _build_strip(s, c, scale)
    except MemoryError:
        drop_cache()                     # evict everything and retry once
        try:
            st = _build_strip(s, c, scale)
        except MemoryError:
            return None                  # text() falls back to slow px path
    _tcache[key] = st
    _tcache_px += need
    return st


def _build_strip(s, c, scale):
    # scale-1 render (portrait local coords: (lx,ly) -> [ly, wl1-1-lx])
    wl = len(s)*6*scale
    wl1 = len(s)*6
    t1 = displayio.Bitmap(7, wl1, 65536)
    bitmaptools.fill_region(t1, 0, 0, 7, wl1, _SKIP)
    x0 = 0
    for ch in s:
        g = _glyph(ch.upper())
        if g:
            for ry in range(7):
                row = g[ry]
                for rx in range(5):
                    if row & (0x10 >> rx):
                        t1[ry, wl1-1-(x0+rx)] = c
        x0 += 6
    if scale == 1:
        return t1
    st = displayio.Bitmap(7*scale, wl, 65536)
    bitmaptools.fill_region(st, 0, 0, 7*scale, wl, _SKIP)
    bitmaptools.rotozoom(st, t1, angle=0, scale=scale,
                         ox=0, oy=0, px=0, py=0,  # anchor (0,0)->(0,0):
                         skip_index=_SKIP)        # exact integer scaling
    return st


def _slow_text(x, y, s, c, scale):
    # crash-proof fallback when the heap can't even fit a strip: slow
    # (~0.7ms/px) but a laggy frame beats a MemoryError reboot
    for ch in s:
        g = _glyph(ch.upper())
        if g:
            for ry in range(7):
                row = g[ry]
                for rx in range(5):
                    if row & (0x10 >> rx):
                        fillrect(x+rx*scale, y+ry*scale, scale, scale, c)
        x += 6*scale

def text(x,y,s,c,scale=1):
    if not s or FB is None:
        return
    st = _strip(s, c, scale)
    if st is None:
        _slow_text(x, y, s, c, scale)
        return
    wl = len(s)*6*scale
    # blit portrait: dest (y, 240-x-wl); blit clips at dest edges itself,
    # but negative dest coords need source-side trimming
    dx, dy = y, 240-x-wl
    x1 = -dx if dx < 0 else 0
    y1 = -dy if dy < 0 else 0
    if x1 >= st.width or y1 >= st.height:
        return
    bitmaptools.blit(FB, st, max(0, dx), max(0, dy),
                     x1=x1, y1=y1, skip_source_index=_SKIP)

# --- snow (TV static) -------------------------------------------------------
_noise = None              # two 134x24 noise tiles, built lazily (~0.1s once)

def _noise_tiles():
    global _noise
    if _noise is None:
        try:
            tiles = []
            for _ in range(2):
                # 2 tiles x 12 rows = 6.4KB (under the ~7.7KB the post-splash
                # heap leaves after FB+slack — the original 2x24/12.9KB tiles
                # starved and the wipe silently vanished). Variety comes from
                # snow()'s random per-band circular SHIFT, not tile count —
                # 2 tiles x 134 shift positions never reads as a repeat.
                t = displayio.Bitmap(BW, 12, 65536)
                bitmaptools.fill_region(t, 0, 0, BW, 12, BLACK)
                for _i in range(55):
                    t[random.randrange(BW), random.randrange(12)] = WHITE
                tiles.append(t)
            _noise = tiles
        except MemoryError:
            return None               # starved: snow() no-ops this frame
    return _noise

def ensure_noise():
    """Guarantee the static/snow tiles exist before a wipe, even on a
    post-splash / post-big-gif fragmented heap. The tiles are ~6.4KB and
    share the ~7.7KB left after FB+slack; fragmentation could starve them,
    and snow()/static() silently no-opped ("static wipe sometimes stops").
    If they won't fit, shed the decoder slack — the next play_gif re-pins it
    anyway — and retry once. Call after reclaim(), before static()."""
    global _slack
    gc.collect()
    if _noise_tiles() is not None:
        return
    _slack = None
    gc.collect()
    _noise_tiles()

def snow(dots=520):
    # tiled noise, randomized tile order per band: reads as rolling static.
    # `dots` kept for API compat (density is baked into the tiles).
    if FB is None: return
    tiles = _noise_tiles()
    if tiles is None:                 # starved: leave FB as-is, skip snow
        return
    for band in range(0, BH, 12):
        t = tiles[random.getrandbits(1)]
        s = random.randrange(BW)      # circular shift: 2 tiles x 134 offsets
        if s:                         # = effectively endless unique bands
            bitmaptools.blit(FB, t, 0, band, x1=s, y1=0, x2=BW, y2=12)
            bitmaptools.blit(FB, t, BW - s, band, x1=0, y1=0, x2=s, y2=12)
        else:
            bitmaptools.blit(FB, t, 0, band)

_WIN_C = struct.pack(">hh",53,53+BW-1)     # constant full-frame window:
_WIN_R = struct.pack(">hh",40,40+BH-1)     # precompute, don't re-pack/frame
def show():
    if FB is None: return             # nothing to push (starved frame)
    s=_disp.bus.send
    s(42,_WIN_C); s(43,_WIN_R); s(44,FB)

def blank_panel():                 # ST7789 DISPOFF: stop GRAM scan (~1-2mA
    _disp.bus.send(0x28,b"")       # -> ~10uA) for standby. Backlight is
def unblank_panel():               # already 0; this kills the panel too.
    _disp.bus.send(0x29,b"")

def static(frames=6, dots=650):
    for _ in range(frames):
        snow(dots)
        show()
