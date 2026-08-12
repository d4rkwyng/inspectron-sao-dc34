# PROJECT HISTORY — INSPECTRON 34

Condensed build record. The living docs are `README.md` (what it is),
`ENGINEERING.md` (hardware/toolchain bible), `FLASHING.md` (flash/restore),
and the code itself (source of truth for behavior).

## Timeline

- **Jul 2026 — design + rev A.** KiCad 10, generated schematic
  (`gen_sch.py`), hand-finished PCB routed with the custom PathFinder
  router after Freerouting failed. ERC 0/0; DRC 0 violations + 2
  documented unconnected IOVDD pads (accepted exception). Fab pivoted
  PCBWay → JLCPCB quickturn to make the con window.
- **Jul 20–24 — firmware rewrite.** displayio was too slow/fragmenting on
  the RP2040 → direct-render engine (`fbdraw.py`, C-speed bitmaptools,
  bus-level CASET/RASET/RAMWR). The 264KB heap war: decoder (88KB) and
  framebuffer (64KB) take turns; boot-time pristine-heap GIF preopen;
  firmware ships precompiled `.mpy` (on-device compile fragments the heap
  fatally). Menu system, settings NVM block, salted-hash unlock table,
  station knocks, EAS interrupt. All brought up on a Pico H + Waveshare
  dev rig.
- **Jul 20 — puzzle site.** CF-00..CF-09 case set built, playtested to
  death before the con, answer-leak gate (`check_no_answers.py`) green.
  Deployed to inspectron34.com (Cloudflare Workers static assets).
- **Aug 4 — production.** Boards arrived (JLCPCB), screens hand-soldered,
  first picture same evening. Factory line built: golden-image flashing
  via picotool (~2 min/board, parallel daemon), device-side verification.
- **Fleet disposition (30 boards).** ~20 sold at the con. Of the rest:
  1 factory-original kept unflashed with the PCB intact, 1 maker's own,
  2 to friends, 1 traded, 1 donated to the Badgelife Village SAO museum,
  and 4 on the bench — 1 bad screen (fixable), 1 sticky button
  (fixable), 2 with suspect flash retention (the factory-line rejects).
- **Firmware v3 (shipping build):** boot splash, MASTER CONTROL menu
  (guide / case files / tuner / settings / about+QR), instant last-channel
  resume, antenna LED modes, on-device factory reset, DEF CON 34 sign on
  channel 34.
- **Aug 5–7 — firmware V4.** Badge detection ("ON BADGE" in MASTER
  CONTROL), trap channels play until surfed away, community channels at
  CH 100+, ANT LED PULSE mode, static-wipe fixes. Most badges sold at
  the con carried V4; earlier units were updated on the con floor via
  `test/v4-batch-update.sh`.
- **Aug 11 — firmware V5 (current release).** Post-con: UNLOCK ALL (the
  answers are public now), menu THEMES (DEFAULT / DC34 / INVERSE,
  including a themed boot splash picked pre-import by the NVM theme
  byte), SAVE + BACK settings row, real host-badge control over I2C
  (0xF2 fixed to the documented static burst; new 0xF5 ANT-mode
  register), plus heap/menu fixes from a line-by-line pre-release code crawl.
  Settings block bumped to v4 (+theme byte; unlocks untouched). Dead
  `secret/innout.gif` dropped (+554KB flash headroom). Blessed V5
  `.mpy` set + splash variants in `firmware/`; golden-inspectron34-v5
  captured Aug 11 from a blessed board (see FLASHING.md).

## Where things live

- Answers/spoilers: **only** in `sitegen/` (see the README warning)
- Fleet flashing: `test/` (`golden-flash.sh`, `factory-daemon.sh`)
- Quality gate: `test/quality.sh` (lint, unit tests, boot smoke,
  answer-leak check, memory budget)
