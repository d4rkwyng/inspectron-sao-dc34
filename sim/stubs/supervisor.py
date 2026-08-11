# supervisor stub.

import time as _time


class _Runtime:
    def __init__(self):
        self.autoreload = True
        self.serial_connected = True
        self.usb_connected = True
        self.run_reason = "STARTUP"


runtime = _Runtime()


def ticks_ms():
    return int(_time.monotonic() * 1000) & 0x3FFFFFFF


def reload():
    raise SystemExit("supervisor.reload() called")


def set_next_code_file(*args, **kwargs):
    pass
