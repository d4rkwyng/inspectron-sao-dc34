# pwmio stub — PWMOut that logs duty-cycle changes (backlight visibility).

import simcore


class PWMOut:
    def __init__(self, pin, *, frequency=500, duty_cycle=0,
                 variable_frequency=False):
        self._pin = pin
        self.frequency = frequency
        self._duty = duty_cycle

    @property
    def duty_cycle(self):
        return self._duty

    @duty_cycle.setter
    def duty_cycle(self, value):
        value = int(value)
        if value != self._duty:
            self._duty = value
            simcore.log("PWM %s duty -> %d (%.0f%%)"
                        % (self._pin.name, value, 100.0 * value / 65535))

    def deinit(self):
        pass
