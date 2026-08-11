# digitalio stub — stateful no-op pins; logs output-value changes so the
# console shows the power LED and antenna LED activity.

import simcore


class Direction:
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"


class Pull:
    UP = "UP"
    DOWN = "DOWN"


class DriveMode:
    PUSH_PULL = "PUSH_PULL"
    OPEN_DRAIN = "OPEN_DRAIN"


class DigitalInOut:
    def __init__(self, pin):
        self._pin = pin
        self._direction = Direction.INPUT
        self._value = False
        self._pull = None

    @property
    def direction(self):
        return self._direction

    @direction.setter
    def direction(self, d):
        if d != self._direction:
            self._direction = d
            if d == Direction.INPUT:
                simcore.log("%s -> input (released)" % self._pin.name)

    def switch_to_output(self, value=False, drive_mode=DriveMode.PUSH_PULL):
        self._direction = Direction.OUTPUT
        self._set_value(value, announce_direction=True)

    def switch_to_input(self, pull=None):
        self._pull = pull
        self.direction = Direction.INPUT

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._set_value(v)

    def _set_value(self, v, announce_direction=False):
        v = bool(v)
        if v != self._value or announce_direction:
            self._value = v
            simcore.log("%s output -> %s"
                        % (self._pin.name, "HIGH" if v else "LOW"))

    @property
    def pull(self):
        return self._pull

    @pull.setter
    def pull(self, p):
        self._pull = p

    def deinit(self):
        pass
