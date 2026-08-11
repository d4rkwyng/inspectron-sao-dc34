# board stub — RP2040 GPIO pin objects (identity tokens with names).


class Pin:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "board." + self.name


for _n in range(30):
    globals()["GP%d" % _n] = Pin("GP%d" % _n)

del _n
