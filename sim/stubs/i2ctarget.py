# i2ctarget stub — press B in the sim window to simulate one badge I2C
# read at 0x50 (a descriptor probe, like an SAO-aware badge would send).
import simcore


class I2CTargetRequest:
    def __init__(self, is_read=True):
        self.address = 0x50
        self.is_read = is_read

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, n=-1, ack=True):
        return b""

    def write(self, buffer):
        print("[SIM] badge read %d bytes: %r" % (len(buffer), bytes(buffer)))
        return len(buffer)


class I2CTarget:
    def __init__(self, scl=None, sda=None, *, addresses=(), smbus=False):
        self.addresses = list(addresses)

    def request(self, *, timeout=-1):
        if getattr(simcore, "badge_probe_pending", 0) > 0:
            simcore.badge_probe_pending -= 1
            print("[SIM] badge I2C contact at 0x50")
            return I2CTargetRequest(is_read=True)
        return None

    def deinit(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False
