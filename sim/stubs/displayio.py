# displayio stub — just the subset firmware/code.py uses:
# Bitmap (numpy-backed, shared with the bitmaptools stub), Palette,
# ColorConverter, Colorspace, TileGrid, Group, Display.

import numpy as np
import pygame

import simcore


def release_displays():
    pass


class Colorspace:
    RGB888 = "RGB888"
    RGB565 = "RGB565"
    RGB565_SWAPPED = "RGB565_SWAPPED"
    RGB555 = "RGB555"
    RGB555_SWAPPED = "RGB555_SWAPPED"


class Bitmap:
    """2D array of ints, bitmap[x, y] like CircuitPython. Backed by a
    numpy array (rows=y, cols=x) so bitmaptools/fourwire stubs are fast."""

    def __init__(self, width, height, value_count):
        self.width = width
        self.height = height
        self.value_count = value_count
        self._np = np.zeros((height, width), dtype=np.uint16)

    def __getitem__(self, key):
        if isinstance(key, tuple):
            x, y = key
            return int(self._np[y, x])
        return int(self._np.reshape(-1)[key])

    def __setitem__(self, key, value):
        if isinstance(key, tuple):
            x, y = key
            if not (0 <= x < self.width and 0 <= y < self.height):
                raise IndexError("pixel (%s,%s) out of range" % (x, y))
            self._np[y, x] = value
        else:
            self._np.reshape(-1)[key] = value

    def fill(self, value):
        self._np[:] = value

    @property
    def _data(self):
        # legacy list view for the old TileGrid render path
        return self._np.reshape(-1).tolist()


class Palette:
    def __init__(self, color_count):
        self._colors = [0] * color_count
        self._transparent = set()

    def __len__(self):
        return len(self._colors)

    def __getitem__(self, index):
        return self._colors[index]

    def __setitem__(self, index, color):
        if isinstance(color, (bytes, bytearray)):
            color = int.from_bytes(color, "big")
        self._colors[index] = int(color)

    def make_transparent(self, index):
        self._transparent.add(index)

    def make_opaque(self, index):
        self._transparent.discard(index)


def _rgb565_swapped_to_rgb888(v):
    v = ((v & 0xFF) << 8) | ((v >> 8) & 0xFF)   # un-swap the bytes
    r = (v >> 11) & 0x1F
    g = (v >> 5) & 0x3F
    b = v & 0x1F
    r = (r << 3) | (r >> 2)
    g = (g << 2) | (g >> 4)
    b = (b << 3) | (b >> 2)
    return (r << 16) | (g << 8) | b


def _rgb565_to_rgb888(v):
    r = (v >> 11) & 0x1F
    g = (v >> 5) & 0x3F
    b = v & 0x1F
    return (((r << 3) | (r >> 2)) << 16) | (((g << 2) | (g >> 4)) << 8) \
        | ((b << 3) | (b >> 2))


class ColorConverter:
    def __init__(self, input_colorspace=Colorspace.RGB888, dither=False):
        self.input_colorspace = input_colorspace
        self.dither = dither

    def to_rgb888(self, value):
        cs = self.input_colorspace
        if cs == Colorspace.RGB565_SWAPPED:
            return _rgb565_swapped_to_rgb888(value)
        if cs == Colorspace.RGB565:
            return _rgb565_to_rgb888(value)
        return value & 0xFFFFFF


class TileGrid:
    def __init__(self, bitmap, *, pixel_shader, width=1, height=1,
                 tile_width=None, tile_height=None, default_tile=0,
                 x=0, y=0):
        self.bitmap = bitmap
        self.pixel_shader = pixel_shader
        self.width = width
        self.height = height
        self.tile_width = tile_width or bitmap.width
        self.tile_height = tile_height or bitmap.height
        self.x = x
        self.y = y
        self.hidden = False


class Group:
    def __init__(self, *, scale=1, x=0, y=0):
        self.scale = scale
        self.x = x
        self.y = y
        self.hidden = False
        self._children = []

    def append(self, item):
        self._children.append(item)

    def insert(self, index, item):
        self._children.insert(index, item)

    def remove(self, item):
        self._children.remove(item)

    def pop(self, index=-1):
        return self._children.pop(index)

    def __len__(self):
        return len(self._children)

    def __iter__(self):
        return iter(self._children)

    def __getitem__(self, index):
        return self._children[index]


def _pixel_rgb(shader, value):
    if isinstance(shader, Palette):
        if value in shader._transparent:
            return None
        rgb = shader._colors[value] if value < len(shader._colors) else 0
    elif isinstance(shader, ColorConverter):
        rgb = shader.to_rgb888(value)
    else:
        rgb = int(value) & 0xFFFFFF
    return ((rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF)


def _render_tilegrid(surface, grid, ox, oy, scale):
    # All firmware TileGrids show tile 0 (default_tile) in every cell, so
    # tiling is just the bitmap repeated grid.width x grid.height times.
    bmp = grid.bitmap
    shader = grid.pixel_shader
    data = bmp._data
    w, h = bmp.width, bmp.height
    tw, th = grid.tile_width, grid.tile_height
    base_x = ox + grid.x * scale
    base_y = oy + grid.y * scale
    for ty in range(grid.height):
        for tx in range(grid.width):
            gx = base_x + tx * tw * scale
            gy = base_y + ty * th * scale
            if scale == 1:
                set_at = surface.set_at
                i = 0
                for y in range(min(h, th)):
                    py = gy + y
                    for x in range(min(w, tw)):
                        rgb = _pixel_rgb(shader, data[i])
                        i += 1
                        if rgb is not None:
                            set_at((gx + x, py), rgb)
            else:
                fill = surface.fill
                i = 0
                for y in range(min(h, th)):
                    py = gy + y * scale
                    for x in range(min(w, tw)):
                        rgb = _pixel_rgb(shader, data[i])
                        i += 1
                        if rgb is not None:
                            fill(rgb, pygame.Rect(gx + x * scale, py,
                                                  scale, scale))


def _render(surface, node, ox, oy, scale):
    if getattr(node, "hidden", False):
        return
    if isinstance(node, Group):
        gscale = scale * node.scale
        gx = ox + node.x * scale
        gy = oy + node.y * scale
        for child in node:
            _render(surface, child, gx, gy, gscale)
    elif isinstance(node, TileGrid):
        _render_tilegrid(surface, node, ox, oy, scale)


class Display:
    """Minimal displayio.Display: root_group + manual refresh()."""

    def __init__(self, bus, *, width, height, rotation=0, rowstart=0,
                 colstart=0, auto_refresh=True, backlight_pin=None,
                 brightness=1.0, **kwargs):
        self.bus = bus
        self.width = width
        self.height = height
        self.rotation = rotation
        self.auto_refresh = auto_refresh
        self.brightness = brightness
        self._root_group = None
        simcore.init_window(width, height)
        simcore.log("display %dx%d created (rotation=%d)"
                    % (width, height, rotation))

    @property
    def root_group(self):
        return self._root_group

    @root_group.setter
    def root_group(self, group):
        self._root_group = group

    def refresh(self, *args, **kwargs):
        surface = pygame.Surface((self.width, self.height))
        surface.fill((0, 0, 0))
        if self._root_group is not None:
            _render(surface, self._root_group, 0, 0, 1)
        simcore.present(surface)
        return True
