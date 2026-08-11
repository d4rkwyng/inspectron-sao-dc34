# microcontroller stub — nvm is a 4096-byte bytearray persisted to
# sim/nvm.bin between runs (saved at interpreter exit).

import atexit
import os

import simcore

_NVM_PATH = os.path.join(simcore.SIM_DIR, "nvm.bin")
_NVM_SIZE = 4096


def _load():
    try:
        with open(_NVM_PATH, "rb") as f:
            data = bytearray(f.read(_NVM_SIZE))
    except OSError:
        data = bytearray()
    data.extend(bytes(_NVM_SIZE - len(data)))
    return data


nvm = _load()


def _save():
    try:
        with open(_NVM_PATH, "wb") as f:
            f.write(nvm)
    except OSError as e:
        simcore.log("nvm save failed: %s" % e)


atexit.register(_save)


class _Cpu:
    frequency = 125_000_000
    temperature = 27.0
    reset_reason = "POWER_ON"


cpu = _Cpu()


def reset():
    raise SystemExit("microcontroller.reset() called")
