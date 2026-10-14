"""Firmware pure-logic unit tests — the 'silent rot' surface (NVM, settings,
hashes, the boot-peek contract). Runs under desktop CPython via conftest's
microcontroller stub. No hardware, no answers.
"""
import pytest
import tuner


@pytest.fixture(autouse=True)
def fresh_nvm(monkeypatch):
    # a blank (0x00) flash region AND blank session mirrors before every
    # test — tuner keeps module-level RAM state (_ram_flags, _ram_chans,
    # _last_digits, knock progress) that would otherwise leak across tests
    monkeypatch.setattr(tuner, "_NVM", bytearray(4096))
    monkeypatch.setattr(tuner, "_ram_flags", bytearray(tuner.MAX_SLOTS))
    monkeypatch.setattr(tuner, "_ram_chans", {})
    monkeypatch.setattr(tuner, "_last_digits", None)
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


# --- synthetic (answer-free) secret tables --------------------------------
_FAKE = ("012.3", "345.6", "678.9")


@pytest.fixture
def fake_secrets(monkeypatch):
    """Replace the real hash tables with a made-up salt + three made-up
    frequencies, so the unlock/knock logic is tested without any answer."""
    monkeypatch.setattr(tuner, "SALT", "TEST:")
    paths = {tuner._fnv(f): "/secret/t%d.gif" % i for i, f in enumerate(_FAKE)}
    monkeypatch.setattr(tuner, "_PATHS", paths)
    monkeypatch.setattr(tuner, "_SLOTS", sorted(paths)[:tuner.BADGE_SLOT])
    monkeypatch.setattr(tuner, "KONAMI_GIF", "/secret/k.gif")
    monkeypatch.setattr(tuner, "BADGE_GIF", "/secret/b.gif")
    return paths


def test_unlock_freq_persists_channel(fake_secrets):
    assert tuner._unlock_freq("345.6") == "/secret/t1.gif"
    assert tuner._unlock_freq("999.9") is None
    tuner._ram_chans.clear()                      # force the NVM read path
    assert tuner.channel_of("/secret/t1.gif") == "345.6"


def test_unlock_all_learns_real_numbers_into_nvm(fake_secrets):
    tuner.unlock_all()
    # drop the session mirrors: everything must come back from NVM alone
    tuner._ram_flags[:] = bytes(tuner.MAX_SLOTS)
    tuner._ram_chans.clear()
    for i, f in enumerate(_FAKE):
        assert tuner.channel_of("/secret/t%d.gif" % i) == f
    assert set(tuner.unlocked_paths()) == {
        "/secret/t0.gif", "/secret/t1.gif", "/secret/t2.gif",
        "/secret/k.gif", "/secret/b.gif"}
    assert tuner.all_unlocked()


def test_factory_reset_wipes_unlocks_and_settings(fake_secrets):
    tuner.unlock_all()
    s = tuner.settings_load()
    s["bright_idx"] = 2
    tuner.settings_save(s)
    tuner._save_last_digits([1, 2, 3, 4])
    tuner.factory_reset()
    assert tuner.unlocked_paths() == []
    assert tuner.settings_load() == dict(zip(tuner._SET_KEYS,
                                             tuner.SETTINGS_DEFAULTS))
    assert tuner._load_last_digits() == [0, 8, 7, 5]   # factory dial


def _knock_setup(monkeypatch, steps):
    seq = tuple(tuner._fnv(f) for f in steps)
    monkeypatch.setattr(tuner, "KNOCKS", (seq,))
    monkeypatch.setattr(tuner, "_knock_prog", [0])
    monkeypatch.setattr(tuner, "_knock_miss", [0])


def test_knock_survives_two_strays(fake_secrets, monkeypatch):
    # final step is a FREQS channel, as the firmware contract requires
    _knock_setup(monkeypatch, ("003.0", "006.0", "678.9"))
    assert tuner.knock_visit("3.0") == "step"
    assert tuner.knock_visit("50.0") is None       # stray 1
    assert tuner.knock_visit("51.0") is None       # stray 2 (< _KNOCK_MISS_MAX)
    assert tuner.knock_visit("6.0") == "step"
    assert tuner._knock_event("678.9") == "/secret/t2.gif"


def test_knock_resets_after_max_strays(fake_secrets, monkeypatch):
    _knock_setup(monkeypatch, ("003.0", "006.0", "678.9"))
    assert tuner.knock_visit("3.0") == "step"
    for n in range(tuner._KNOCK_MISS_MAX):
        tuner.knock_visit("%d.0" % (50 + n))
    assert tuner._knock_prog == [0]
    assert tuner.knock_visit("6.0") is None        # sequence was dropped


# --- the shipped secrets_config is internally consistent ------------------
# (hash-level checks only: nothing here reveals a frequency)
def test_shipped_secrets_config_consistent():
    import pathlib
    import secrets_config as sc
    root = pathlib.Path(__file__).resolve().parents[1]
    assert len(sc.FREQS) <= tuner.BADGE_SLOT
    assert not set(sc.FREQS) & set(sc.TRAP_FREQS)
    for seq in sc.KNOCKS:                          # completing a knock must
        assert seq[-1] in sc.FREQS                 # grant a real license
    paths = (list(sc.FREQS.values()) + list(sc.TRAP_FREQS.values())
             + [sc.KONAMI_GIF, sc.BADGE_GIF])
    missing = [p for p in paths if not (root / p.lstrip("/")).is_file()]
    assert not missing, missing
