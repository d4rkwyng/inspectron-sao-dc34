"""Firmware pure-logic unit tests — the 'silent rot' surface (NVM, settings,
hashes, the boot-peek contract). Runs under desktop CPython via conftest's
microcontroller stub. No hardware, no answers.
"""
import pytest
import tuner


@pytest.fixture(autouse=True)
def fresh_nvm():
    # a blank (0x00) flash region before every test
    tuner._NVM = bytearray(4096)
    yield


# --- contract constants the boot path hardcodes ---------------------------
def test_nvm_contract():
    # code.py._boot_peek_path and its asserts depend on these exact values
    assert tuner._NVM_LEN == 91
    assert tuner._SET_OFF == 91
    assert tuner._SET_VER == 4
    assert tuner._SET_LEN == 13            # pinned literal: code.py peeks
    assert tuner._SET_KEYS.index("boot_hi") == 7   # nvm[91:104], digits at
    assert tuner._SET_KEYS.index("theme") == 9     # blk[9]/blk[10]


# --- settings block -------------------------------------------------------
def test_settings_defaults_on_blank():
    assert tuner.settings_load() == dict(zip(tuner._SET_KEYS, tuner.SETTINGS_DEFAULTS))


def test_settings_roundtrip():
    s = tuner.settings_load()
    s.update(bright_idx=2, standby_idx=1, order=1, boot_hi=6, boot_lo=10)
    tuner.settings_save(s)
    assert tuner.settings_load() == s


def test_settings_corruption_yields_defaults():
    # garbage in the block (bad magic) -> defaults, never a crash
    off, ln = tuner._SET_OFF, tuner._SET_LEN
    for i in range(off, off + ln):
        tuner._NVM[i] = 0xFF
    assert tuner.settings_load() == dict(zip(tuner._SET_KEYS, tuner.SETTINGS_DEFAULTS))


def test_settings_field_clamp():
    # a valid block whose field byte exceeds its max is clamped, not trusted
    tuner.settings_save(tuner.settings_load())
    off = tuner._SET_OFF
    idx = tuner._SET_KEYS.index("bright_idx")     # max 2
    blk = bytearray(tuner._NVM[off:off + tuner._SET_LEN])
    blk[2 + idx] = 99
    blk[-1] = tuner._set_cksum(blk[:-1])          # keep checksum valid
    tuner._NVM[off:off + tuner._SET_LEN] = blk
    assert tuner.settings_load()["bright_idx"] == tuner._SET_MAX[idx]


# --- last-dial persistence ------------------------------------------------
def test_last_dial_roundtrip():
    tuner._save_last_digits([1, 2, 3, 4])
    assert tuner._load_last_digits() == [1, 2, 3, 4]


# --- dial-string normalization --------------------------------------------
def test_norm_padding():
    assert tuner._norm("88.5") == "088.5"
    assert tuner._norm("123.4") == "123.4"
    assert len(tuner._norm("7.0")) == 5


# --- hash core ------------------------------------------------------------
def test_fnv_deterministic_and_distinct():
    assert tuner._fnv("123.4") == tuner._fnv("123.4")
    assert tuner._fnv("123.4") != tuner._fnv("123.5")


# --- the boot-peek encode/decode contract (channel -> settings bytes) -----
@pytest.mark.parametrize("ch", [3, 34, 61, 99])
def test_boot_peek_contract(ch):
    # ui.py encodes boot_hi = ch//10, boot_lo = (ch%10)*10 into the settings
    # block; code.py._boot_peek_path decodes n = blk[9]*10 + blk[10]//10.
    s = tuner.settings_load()
    s["boot_hi"] = ch // 10
    s["boot_lo"] = (ch % 10) * 10
    tuner.settings_save(s)
    blk = bytes(tuner._NVM[tuner._SET_OFF:tuner._SET_OFF + tuner._SET_LEN])
    hi_i = tuner._SET_KEYS.index("boot_hi")
    lo_i = tuner._SET_KEYS.index("boot_lo")
    assert blk[2 + hi_i] == ch // 10 and blk[2 + lo_i] == (ch % 10) * 10
    assert blk[2 + hi_i] * 10 + blk[2 + lo_i] // 10 == ch   # decode round-trips
