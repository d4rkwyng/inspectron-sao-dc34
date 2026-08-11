# ENGINEERING NOTES — INSPECTRON 34 (DEF CON 34 SAO)

Retro CRT-TV shaped SAO for DEF CON 34 (Aug 6–9, 2026). RP2040 + 16MB flash +
1.14" ST7789V TFT plays drag-and-drop meme GIFs; CircuitPython mounts the board
as a USB drive. Powered from the DC34 badge SAO port (3.0V) or USB-C.
By @d4rkwyng. ~30 boards, JLCPCB quickturn, matte black + ENIG.

## Status (as of Aug 11, 2026 — post-con)
- rev A design **complete**: ERC 0/0, DRC **0 violations + 2 documented
  unconnected** (see "IOVDD exception" below). Production files exported.
- Ordering pivoted **PCBWay → JLCPCB quickturn** (see HANDOFF; files in
  `production/quickturn-revA/`). **Boards ARRIVED Aug 4.** Dev rig (Pico H,
  Waveshare Pico-LCD-1.14) in service since ~Jul 20; firmware fully
  rig-validated.
- First-article + batch assembly **done** (Aug 4–5): screens hand-soldered,
  ~20 boards sold at DEF CON 34, most on firmware V4; **V5 (Aug 11) is
  the current release**. See `HANDOFF.md` for the timeline + fleet
  disposition.

## THE most important thing
`hardware/dc34-sao.kicad_pcb` contains **hand edits made after generation**
(antenna LEDs, silk art, INSPECTRON nameplate, logos, routing, zones).
**Never re-run `gen_pcb.py` against it — that regenerates from the PLACE
table and destroys everything.** The generators are kept for reference and
for the netlist/BOM source of truth (`gen_sch.py` COMPONENTS table).
Same for the black-ENIG stackup block: it was injected textually into the
board's `(setup` section so renders show matte black; regeneration loses it.

## Key design facts
- **DC34 SAO spec**: badge rail is **3.0V not 3.3V**, 100mA total across both
  ports. Badge I2C already has devices at 0x3C/0x19. Unkeyed 2x3 header,
  pin 1 = 3.0V. Designed for the badge's **right port**; board may extend max
  21mm inboard of the header. Theme is "Agency" — tagline silk:
  "TUNE YOUR OWN SIGNAL".
- **Badge interactivity**: antenna-tip LEDs (0402) on SAO_GPIO1/2 via 470R
  (R12/R13). CORRECTED (Jul 17, verified from DC32 firmware source): official
  badges have historically NOT driven SAO GPIOs — our firmware owns the
  antenna show (blips on channel change/badge contact); any badge that does
  drive the pins lights them as a bonus. Firmware serves a badge.team
  v4.2terbo descriptor at **I2C 0x50** ("LIFE" + "INSPECTRON34"), byte-
  verified against the spec, plus command registers 0xF0-0xF4 (see
  firmware/INTERFACING.md) and a badge-contact channel unlock.
- **Power path**: AO3401A P-FET mux — badge 3.0V has no diode drop; USB 5V →
  ME6211C33 LDO → B5819W → VDD ≈ 3.0V (so USB_VDD runs ~0.1V below the
  RP2040 USB datasheet minimum — empirically fine at room temp; first-article
  test covers full-load enumeration on two hosts). Backlight is a low-side
  AO3400A NMOS, PWM on GP7, default 60%; **R6 = 1Ω** (was 4.7Ω — panel LED
  Vf 2.9–3.1V @ 20mA leaves ~zero headroom at 3.0V, so R6 barely matters;
  1Ω maximizes brightness, PWM is the real current control).
- **Pin map**: `firmware/pins.md` is the single source of truth.
- RUN pin uses the RP2040 internal pullup (R4 was deleted — unroutable, and
  the Pico ships the same way).

### IOVDD exception (the 2 DRC unconnected items)
RP2040 pads **22 AND 10** (two of the six IOVDD pads) are entombed behind
the escape comb / button-escape walls and could not be reached (every via
candidate corridor is 0.02–0.05mm too narrow — verified exhaustively
Jul 16). IOVDD is a shared on-die ring fed by the other four IOVDD pads
(1, 33, 42, 49); the whole GPIO bank draws ~2mA. Accepted as an engineering
exception — **`export_production.sh` fails if unconnected > 2**, codified.
(Earlier docs claimed only pad 22; a later re-audit turned up pad 10's
isolated fill sliver was the second DRC item all along.)

### TFT footprint pin order (CRITICAL, fixed Jul 16 night)
The N114 panel datasheet front view has pin 13 LEFT / pin 1 RIGHT at the
tail; mounted landscape-tail-right with the fold-under, **panel pin 1 lands
at the TOP of the pad column**. The original footprint had pin 1 at the
bottom — every signal except CS was mirrored (dead display). Fixed by
mirroring J3's pad positions on the live board + re-plumbing the escape
stubs (MOSI/SCK/DC/RST/LEDK/LEDA/VDD re-landed; CS unchanged), and
mirroring `lib/dc34-sao.pretty/TFT_FPC_13P_N114.kicad_mod`. Pin 1 silk "1"
is now at the TOP pad; the hand-solder notes in `production/quickturn-revA/README-JLCPCB.md` match.

## Repo layout
- `hardware/` — KiCad 10 project + toolchain. Custom footprints in
  `lib/dc34-sao.pretty` (13-pin TFT flex, TS-1187A) and `lib/logo.pretty`.
- `firmware/` — CircuitPython `code.py` (GIF player + I2C target + puzzle
  game), `tuner.py` (dial + NVM unlocks + station knock + settings),
  `ui.py` + `fbdraw.py` (menu system, C-speed direct render — see
  `MENU_SPEC.md`), `secrets_config.py` (**GENERATED** salted-hash table —
  regenerate via `sitegen/gen_secrets.py`, NEVER hand-edit),
  `convert.py`, `reencode.py`, `pins.md`.
- `site/` — deployed puzzle site (static, answer-free). `sitegen/` —
  builders + **ALL ANSWERS** (`CASES.md`, `gen_secrets.py`) — never deploy
  to the live site; public in the repo post-con (README spoiler warning).
- `sim/` — pygame desktop simulator; runs `firmware/code.py` unmodified.
- `memes/` + `secret/` — device GIF packs (~14.8MB pack, ~0.7MB free on the 15.7MB partition).
- `production/` — fab exports per revision; `quickturn-revA/README-JLCPCB.md`
  is the record of the order actually placed.
- `design/` — final renders (front/back/assembled/on-badge).
- `test/` — factory flashing tools + the quality gate.

**Project state lives in `HANDOFF.md`** — this file is the hardware/
toolchain bible; HANDOFF is the build record.

## Toolchain / gotchas (hard-won)
- KiCad 10.0.4 lives at `~/Applications/KiCad/KiCad.app` (brew cask needed
  sudo; app was copied from the DMG). CLI:
  `~/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`. Its bundled
  python (needed for pcbnew scripting):
  `.../Frameworks/Python.framework/Versions/3.9/bin/python3`.
- pcbnew standalone scripts need `wx.App(redirect=False)`, and run with
  `PYTHONFAULTHANDLER=1` + `-u` or crashes are silent.
- **`board.Remove()` corrupts SWIG iterators** — always two-stage scripts:
  mutate + save, then reload + continue. Deleting by stale references leaves
  "ghost" tracks; enumerate by exact coordinates.
- `FOOTPRINT.Flip(pos, pcbnew.FLIP_DIRECTION_LEFT_RIGHT)`; `board.Add(fp)`
  **before** Flip or segfault. `PCB_VIA.GetWidth(layer)` needs the layer arg.
- Board local coords: sheet origin offset **ORG = 100.0** (board top-left at
  sheet (100,100)). Board body 58×42mm; antenna prongs above y=0, tips at
  ball centers L(27.5,−9.097) r1.503 and R(48.3,−8.187) r1.313. The prongs
  LEAN — straight tip-to-base lines exit the outline; use the centerlines
  L(31.5,0)→(27.5,−9.1), R(41.5,0)→(48.3,−8.19).
- Routing was done with the **custom PathFinder router**
  (`hardware/pathfinder.py`, `route_one.py`) — negotiated congestion, 0.12mm
  grid, dual swath grids for exact clearance legality. Freerouting 2.1.0 was
  abandoned (repeatable maze-search exceptions).
- Power: GND zone on F.Cu, VDD zone on B.Cu **plus routed VDD links** —
  zone-only power fragments into islands behind the fine-pitch escape combs.
- Vias are tented front+back in board setup (renders may still show dimples).
- Design rules: clearance 0.12, track 0.15, via 0.45/0.2, edge 0.25.

## Verification loop
1. `kicad-cli sch erc` (expect 0/0) and `kicad-cli pcb drc` (expect 0
   violations, exactly 2 unconnected).
2. `hardware/export_production.sh` — gates on DRC, then writes gerbers/BOM/
   positions/renders to `production/revA/`.
3. Renders: front/back come from the export; `render-assembled.png` is a PIL
   composite (testcard pasted into the bezel — mapping: find board bbox in
   the render, px = origin + mm·scale; **framing is NOT stable between
   kicad-cli runs**, always re-measure).
4. Firmware: `python3 -m py_compile firmware/*.py`, then
   `SDL_VIDEODRIVER=dummy sim/.venv/bin/python sim/run.py --selftest`
   (exit 0 = pass; `rm sim/nvm.bin` first for determinism).
5. Site: `sim/.venv/bin/python sitegen/build_site.py` then
   `python3 sitegen/check_no_answers.py` — **must PASS (0 findings)
   before `site/` goes anywhere public**.
6. After editing the answer table: `python3 sitegen/gen_secrets.py`
   regenerates `firmware/secrets_config.py`; bump `tuner.VERSION` if the
   table changes after boards ship.
