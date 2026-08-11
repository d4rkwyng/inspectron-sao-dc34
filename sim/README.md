# INSPECTRON 34 desktop simulator

Runs `firmware/code.py` **unmodified** in CPython. The CircuitPython modules
(`board`, `displayio`, `gifio`, `keypad`, `pwmio`, `microcontroller`, ...)
are shadowed by the stubs in `sim/stubs/`, the firmware's local modules
(`tuner`, `secrets_config`) import as-is, and the 240x135 ST7789 is rendered
to a pygame window at 4x scale (960x540, title "INSPECTRON 34 SIM").

## Setup

```sh
python3 -m venv sim/.venv
sim/.venv/bin/pip install pygame pillow
```

## Run

```sh
sim/.venv/bin/python sim/run.py
```

The on-device paths are remapped: `/memes` -> `sim/memes/`, `/secret` ->
`sim/secret/`. If either is empty, tiny test GIFs are generated
automatically (`sim/make_test_gifs.py`). Drop your own GIFs in — 240x135
or smaller.

## Key bindings

| Key              | Board button    | Action                                |
|------------------|-----------------|---------------------------------------|
| LEFT arrow       | CH_DOWN (GP12)  | previous channel (static transition)  |
| RIGHT arrow      | CH_UP (GP13)    | next channel (static transition)      |
| M or DOWN arrow  | MODE (GP14)     | short press: brightness cycle; hold 1s: standby toggle |
| LEFT + RIGHT held ~0.7s | CH- & CH+ | FREQUENCY TUNER (again to back out)  |
| ESC / close      | —               | quit the simulator                    |

In the tuner: LEFT/RIGHT spin the current digit, M short-press hops to the
next digit, M held 1s attempts to tune. Frequencies from
`firmware/secrets_config.py` (088.5 / 101.1 / 108.5) unlock hidden channels;
the konami sequence (up up down down up down mode) works too.

Backlight duty-cycle changes and LED pin states (power LED GP16, antenna
LEDs GP26/27) are printed to the console.

## Headless self-test

```sh
SDL_VIDEODRIVER=dummy sim/.venv/bin/python sim/run.py --selftest
```

Runs the firmware under a scripted key sequence — channel
change, brightness cycle, enter the tuner, dial 088.5, tune in, play the
unlocked secret channel — dumps every frame as `sim/out/frame_NNNN.png`,
and exits 0. `--frames N` changes the budget. The selftest deletes
`sim/nvm.bin` at start so runs are deterministic.

## Notes / limitations

- `i2ctarget` always reports no badge traffic (`request()` returns `None`),
  so the "badge" event path never fires in the sim.
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
