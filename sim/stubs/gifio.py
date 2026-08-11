# gifio stub — OnDiskGif decoded with PIL. Frames are pre-converted to
# RGB565_SWAPPED ints; next_frame() updates the SAME .bitmap object in
# place (matching real gifio semantics) and returns the frame delay in
# seconds.

import os

import numpy as np
from PIL import Image, ImageSequence

import displayio
import simcore

# Timing realism (defaults ON; set INSPECTRON_SIM_FAST=1 to disable):
# 1. Browser-clamp: GIFs authored for the web use tiny delays (<=20ms)
#    expecting browsers to clamp them to 100ms. Honor that convention.
# 2. Hardware floor: RP2040 gifio decode + SPI push of a full 240x135
#    frame takes ~55-70ms, so the real board tops out around 15fps.
_REALISTIC = os.environ.get("INSPECTRON_SIM_FAST", "") != "1"
_BROWSER_CLAMP = 0.02    # delays at/below this...
_BROWSER_DELAY = 0.10    # ...are treated as this (web-authoring convention)
_HW_MIN_FRAME = 0.055    # RP2040 decode+SPI floor per full frame


def _rgb888_to_rgb565_swapped(r, g, b):
    v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
    return ((v & 0xFF) << 8) | ((v >> 8) & 0xFF)


class OnDiskGif:
    def __init__(self, file):
        path = simcore.resolve_path(file)
        img = Image.open(path)   # raises OSError on bad/missing file
        self.width = img.width
        self.height = img.height
        self._frames = []        # list of (pixel_list, delay_seconds)
        for frame in ImageSequence.Iterator(img):
            duration_ms = frame.info.get("duration", 100) or 100
            if _REALISTIC:
                d = duration_ms / 1000.0
                if d <= _BROWSER_CLAMP:
                    d = _BROWSER_DELAY
                duration_ms = max(d, _HW_MIN_FRAME) * 1000.0
            rgb = frame.convert("RGB")
            a = np.asarray(rgb, dtype=np.uint16).reshape(-1, 3)
            r, g, b = a[:, 0], a[:, 1], a[:, 2]
            v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
            swapped = ((v & 0xFF) << 8) | ((v >> 8) & 0xFF)
            self._frames.append((
                swapped.astype(np.uint16).reshape(rgb.height, rgb.width),
                duration_ms / 1000.0))
        img.close()
        if not self._frames:
            raise ValueError("no frames in " + path)
        self.frame_count = len(self._frames)
        self.bitmap = displayio.Bitmap(self.width, self.height, 65535)
        self._next = 0
        self.min_delay = min(d for _, d in self._frames)
        self.max_delay = max(d for _, d in self._frames)
        self.next_frame()        # real OnDiskGif loads the first frame

    @property
    def duration(self):
        return sum(d for _, d in self._frames)

    def next_frame(self):
        """Decode the next frame into .bitmap in place; return its delay (s)."""
        pixels, delay = self._frames[self._next]
        self.bitmap._np[:] = pixels
        self._next = (self._next + 1) % len(self._frames)
        return delay

    def deinit(self):
        self._frames = []
