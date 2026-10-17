# INSPECTRON 34 desktop simulator

Runs `firmware/code.py` **unmodified** in CPython. The CircuitPython modules
(`board`, `displayio`, `gifio`, `keypad`, `pwmio`, `microcontroller`, ...)
are shadowed by the stubs in `sim/stubs/`, the firmware's local modules
(`tuner`, `secrets_config`) import as-is, and the 240x135 ST7789 is rendered
to a pygame window at 4x scale (960x540, title "INSPECTRON 34 SIM").

## Setup

```sh
python3.13 -m venv sim/.venv
sim/.venv/bin/pip install -r sim/requirements.txt
```

Use Python 3.9-3.13, not 3.14 — see the note at the top of
`sim/requirements.txt`: pygame 2.6.1 (latest release as of 2026-10-05) has an
upstream circular-import bug that breaks `pygame.font` under 3.14, which
takes out all on-screen text and the headless `--selftest`.

## Run

```sh
sim/.venv/bin/python sim/run.py
```

The on-device paths are remapped: `/memes` and `/secret` resolve to the
repo's real channel packs (`memes/`, `secret/`) when those hold GIFs, else
to `sim/memes/` and `sim/secret/`; `INSPECTRON_SIM_TESTGIFS=1` forces the
`sim/` copies. If the chosen dirs are empty, tiny test GIFs are generated
automatically (`sim/make_test_gifs.py`). Drop-in GIFs should be what the
device plays: 134x240 portrait, as produced by `firmware/convert.py`.

## Key bindings

| Key              | Board button    | Action                                |
|------------------|-----------------|---------------------------------------|
| LEFT arrow       | CH_DOWN (GP12)  | previous channel (static transition)  |
| RIGHT arrow      | CH_UP (GP13)    | next channel (static transition)      |
| M or DOWN arrow  | MODE (GP14)     | short press: brightness cycle; hold 1s: MASTER CONTROL menu |
| LEFT + RIGHT held ~0.7s | CH- & CH+ | MASTER CONTROL menu (in a sub-screen: back one level) |
| RIGHT held 2.5s  | CH_UP           | auto-scan on/off                      |
| LEFT held 2.5s   | CH_DOWN         | standby (any key wakes)               |
| B                | —               | queue one fake badge I2C read at 0x50 (first contact unlocks BADGE LINK) |
| T                | —               | toggle the 1:1 "actual size" inset    |
| 1 – 6            | —               | window pixel scale                    |
| ESC / close      | —               | quit the simulator                    |

The menu is described in `firmware/MENU_SPEC.md`. In the FREQ TUNER:
LEFT/RIGHT spin the current digit, M short-press hops to the next digit,
M held 1s attempts to tune. `firmware/secrets_config.py` holds only salted
hashes, so the sim gives no hint what to dial; the konami sequence
(up up down down up down mode) works too.

Backlight duty-cycle changes and LED pin states (power LED GP16, antenna
LEDs GP26/27) are printed to the console.

## Headless self-test

```sh
SDL_VIDEODRIVER=dummy sim/.venv/bin/python sim/run.py --selftest
```

Runs the firmware under the scripted key sequence in
`sim/stubs/simcore.py` (`SELFTEST_SCRIPT`) — channel change, brightness
cycle, MASTER CONTROL -> CASE FILES -> FREQ TUNER, a deliberate missed tune
(NO SIGNAL -> the Nedry channel), then with enough frames TV GUIDE watch
and a SETTINGS round trip — dumps every frame as `sim/out/frame_NNNN.png`,
and exits 0. `--frames N` changes the budget (default 1700; the quality
gate runs 400). The selftest deletes `sim/nvm.bin` at start so runs are
deterministic.

## Notes / limitations

- `i2ctarget` reports no badge traffic unless you press B, which queues one
  read request at 0x50; there is no way to inject badge command writes
  (0xF0-0xF5), and the boot-time host-badge probe always sees no badge.
- `microcontroller.nvm` is a 4096-byte array persisted to `sim/nvm.bin`
  (saved at exit) — tuner unlocks survive interactive restarts, exactly
  like the real nvm behavior.
- `time.sleep` is clamped to 5ms in `--selftest` only, so transitions don't
  dominate wall-clock time; interactive mode runs at real firmware timing.
- The stubs implement only the displayio subset the firmware uses (Bitmap,
  Palette + transparency, ColorConverter/RGB565_SWAPPED, TileGrid incl.
  repeated tiles, Group scale/x/y, manual `refresh()`). Per-cell tile
  indices other than 0 are not rendered.

## GIF playback speed

The sim emulates real-device pacing by default:
- delays <= 20ms are treated as 100ms (web-authoring convention browsers use)
- a ~55ms/frame floor approximates RP2040 gifio decode + SPI throughput (~15fps)

Set `INSPECTRON_SIM_FAST=1` to play raw GIF timings instead.
Note: real hardware will feel close to the default pacing; GIFs that only
look right with FAST=1 will look slow/fast on the actual board too — fix
the GIF's frame delays with firmware/convert.py rather than trusting a browser.
