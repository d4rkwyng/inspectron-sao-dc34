# Interfacing with INSPECTRON 34 over I2C

The INSPECTRON 34 SAO (DEF CON 34) is an I2C target at **0x50** on the SAO
bus. Any badge, SAO, or bus tool that can master I2C at 100–400kHz can talk
to it. 3.0V logic (3.3V tolerated).

## Who is this for
Badge firmware authors, SAO makers, and anyone with a Bus Pirate and
curiosity. Talking to the TV makes things happen on screen — and the first
I2C contact it ever receives unlocks a hidden channel on the device.
Yes, really: plugging it into a badge that speaks is itself a key.

## Identity descriptor (badge.team SAO v4.2terbo binary format)

Reads at 0x50 stream a 256-byte emulated EEPROM:

```
offset 0-3   "LIFE"            (magic, 4C 49 46 45)
offset 4     0x0C              (name length = 12)
offset 5     0x00              (driver name length)
offset 6     0x00              (driver data length)
offset 7     0x00              (extra driver count)
offset 8-19  "INSPECTRON34"    (name)
offset 20+   reserved          (who knows what's in the padding...)
```

- Reads return 16-byte chunks and auto-advance an internal pointer.
- A write of a single byte `< 0xF0` sets the read pointer (8-bit EEPROM
  addressing). 16-bit-style probes won't corrupt anything — this is an
  emulated ROM; write whatever you like at it.
- The descriptor survives the "repair byte 0" convention some badges use.

## Command registers (write to 0x50)

Write `[register]` or `[register, value]`:

| Reg  | Action |
|------|--------|
| 0xF0 | Channel up (with TV-static transition) |
| 0xF1 | Channel down |
| 0xF2 | Static burst on screen |
| 0xF3 | Antenna LED blip |
| 0xF4 | Cycle brightness |
| 0xF5 | Set antenna LED mode — write `[0xF5, n]`, n = 0 OFF / 1 FLASH / 2 ON / 3 PULSE (firmware V5+) |

Commands queue and are consumed by the main loop between GIF frames —
expect them to land within ~100ms during normal TV playback. While the
operator is in a menu screen or the set is in standby, screen-affecting
commands (0xF0/0xF1/0xF2/0xF4) are ignored rather than queued for later;
0xF3 and 0xF5 work in every state. Be a polite bus citizen: the badge's
own peripherals (0x3C, 0x19 on the DC34 badge) share this bus.

## GPIO lines

SAO GPIO1/GPIO2 carry the antenna-tip LEDs (red, 470R series, LED to GND).
Drive a line high (3.0V) and the corresponding antenna lights — no
firmware handshake needed. The INSPECTRON keeps these pins as inputs
except during its own brief animation blips (drive-high-then-release,
≤40ms), so a badge PWM-ing them for effects will win the line most of
the time. WS2812-style data blasted at GPIO1 (badge.team convention)
just makes the antenna flicker — harmless, arguably festive.

## Electrical notes

- Supply: 3.0V from the badge rail; the SAO draws ~35–60mA typical.
- The 0x50 target is implemented with CircuitPython `i2ctarget` —
  clock stretching is possible under load; masters should tolerate it.
- No pull-ups are added to the badge bus by this SAO.
