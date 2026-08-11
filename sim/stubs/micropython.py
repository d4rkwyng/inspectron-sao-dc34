"""Desktop-sim stub for CircuitPython's `micropython` builtin module.

Only `const` is used by the firmware (code.py: `from micropython import
const`). On-device `const(x)` is a compile-time hint that folds x into a
constant; in plain CPython it is just the identity function, which is all
the simulator needs so code.py can import and run unmodified.
"""


def const(x):
    return x
