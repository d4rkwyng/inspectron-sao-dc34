# fourwire stub — emulates the ST7789 GRAM for the direct-render path:
# send(42/43/44) = CASET/RASET/RAMWR. RAMWR data is either a numpy-backed
# displayio.Bitmap (fbdraw FB / gifio frame) or raw bytes (fbdraw bug()
# overlay, wire order hi-byte first). The panel window (cols 53..187,
# rows 40..279 portrait) renders to the landscape pygame window.
import struct

import numpy as np
import pygame

import simcore


class FourWire:
    def __init__(self, spi_bus, *, command=None, chip_select=None,
                 reset=None, baudrate=24_000_000, polarity=0, phase=0):
        self.spi_bus = spi_bus
        self.baudrate = baudrate
        self._gram = np.zeros((320, 240), dtype=np.uint16)   # [row, col] v565
        self._cols = (0, 239)
        self._rows = (0, 319)

    def send(self, command, data):
        if command == 42:                       # CASET
            self._cols = struct.unpack(">hh", bytes(data))
        elif command == 43:                     # RASET
            self._rows = struct.unpack(">hh", bytes(data))
        elif command == 44:                     # RAMWR
            c0, c1 = self._cols
            r0, r1 = self._rows
            w, h = c1 - c0 + 1, r1 - r0 + 1
            if hasattr(data, "_np"):            # Bitmap: values are SWAPPED
                v = data._np.astype(np.uint16).reshape(-1)[:w * h]
                v565 = ((v & 0xFF) << 8) | (v >> 8)
            else:                               # bytes: wire order hi, lo
                b = np.frombuffer(bytes(data), dtype=np.uint8)
                v565 = ((b[0::2].astype(np.uint16)) << 8) | b[1::2]
                v565 = v565[:w * h]
            # clamp to GRAM bounds like the controller (out-of-range
            # windows shear on real glass; landscape-era gifs did this)
            v = v565[:w * h].reshape(h, w)
            wc = min(w, 240 - c0)
            hc = min(h, 320 - r0)
            self._gram[r0:r0 + hc, c0:c0 + wc] = v[:hc, :wc]
            self._render()

    def _render(self):
        region = self._gram[40:280, 53:188]     # portrait 240 rows x 135 cols
        land = region[::-1, :].T                # landscape 135 rows x 240 cols
        r = ((land >> 11) & 0x1F).astype(np.uint8)
        g = ((land >> 5) & 0x3F).astype(np.uint8)
        b = (land & 0x1F).astype(np.uint8)
        rgb = np.dstack(((r << 3) | (r >> 2), (g << 2) | (g >> 4),
                         (b << 3) | (b >> 2)))
        surface = pygame.surfarray.make_surface(
            np.ascontiguousarray(rgb.transpose(1, 0, 2)))
        simcore.present(surface)

    def reset_bus(self):
        pass

    def deinit(self):
        pass
