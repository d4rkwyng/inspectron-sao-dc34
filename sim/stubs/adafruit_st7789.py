# adafruit_st7789 stub — direct-render era: the panel is portrait-native
# but mounted landscape; the window is created landscape (240x135) and all
# pixels arrive via bus.send (see fourwire stub). No displayio refresh.

import simcore


class ST7789:
    def __init__(self, bus, *, width, height, rotation=0, rowstart=0,
                 colstart=0, auto_refresh=True, backlight_pin=None, **kwargs):
        self.bus = bus
        self.width = width
        self.height = height
        self.rotation = rotation
        self.auto_refresh = auto_refresh
        self.root_group = None
        simcore.init_window(240, 135)
        simcore.log("ST7789 %dx%d (direct render via bus.send)"
                    % (width, height))

    def refresh(self, *args, **kwargs):
        return True
