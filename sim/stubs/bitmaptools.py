# bitmaptools stub — the subset fbdraw v3 uses, on numpy-backed Bitmaps.
import numpy as np


def fill_region(dest, x1, y1, x2, y2, value):
    dest._np[y1:y2, x1:x2] = value


def blit(dest, source, x, y, *, x1=0, y1=0, x2=None, y2=None,
         skip_source_index=None, skip_dest_index=None):
    x2 = source.width if x2 is None else x2
    y2 = source.height if y2 is None else y2
    src = source._np[y1:y2, x1:x2]
    h, w = src.shape
    if x >= dest.width or y >= dest.height:
        return
    w = min(w, dest.width - x)
    h = min(h, dest.height - y)
    src = src[:h, :w]
    region = dest._np[y:y + h, x:x + w]
    if skip_source_index is None:
        region[:] = src
    else:
        m = src != skip_source_index
        region[m] = src[m]


def rotozoom(dest, source, *, ox=0, oy=0, px=0, py=0, angle=0, scale=1.0,
             skip_index=None, **_kw):
    # firmware only uses angle=0 + integer scale, anchor (0,0)->(0,0)-style
    assert angle == 0, "sim rotozoom supports angle=0 only"
    s = int(round(scale))
    scaled = np.repeat(np.repeat(source._np, s, axis=0), s, axis=1)
    dx, dy = ox - px * s, oy - py * s
    h, w = scaled.shape
    sx0 = -dx if dx < 0 else 0
    sy0 = -dy if dy < 0 else 0
    dx, dy = max(0, dx), max(0, dy)
    w = min(w - sx0, dest.width - dx)
    h = min(h - sy0, dest.height - dy)
    if w <= 0 or h <= 0:
        return
    src = scaled[sy0:sy0 + h, sx0:sx0 + w]
    region = dest._np[dy:dy + h, dx:dx + w]
    if skip_index is None:
        region[:] = src
    else:
        m = src != skip_index
        region[m] = src[m]


def arrayblit(bitmap, data, x1=0, y1=0, x2=None, y2=None, skip_index=None):
    x2 = bitmap.width if x2 is None else x2
    y2 = bitmap.height if y2 is None else y2
    a = np.frombuffer(bytes(data), dtype=np.uint16)
    bitmap._np[y1:y2, x1:x2] = a.reshape(y2 - y1, x2 - x1)
