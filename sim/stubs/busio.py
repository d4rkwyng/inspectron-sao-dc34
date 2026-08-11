# busio stub — SPI as a stateful no-op.


class SPI:
    def __init__(self, clock=None, MOSI=None, MISO=None):
        self._locked = False
        self.baudrate = 250_000

    def try_lock(self):
        self._locked = True
        return True

    def configure(self, *, baudrate=100_000, polarity=0, phase=0, bits=8):
        self.baudrate = baudrate

    def unlock(self):
        self._locked = False

    def deinit(self):
        pass


class I2C:
    def __init__(self, scl=None, sda=None, frequency=100_000):
        self._locked = False

    def try_lock(self):
        self._locked = True
        return True

    def unlock(self):
        self._locked = False

    def scan(self):
        return []

    def deinit(self):
        pass
