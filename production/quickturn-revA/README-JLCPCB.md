# JLCPCB order — INSPECTRON 34 rev A (SMT-only, display hand-soldered)

Why JLCPCB: every part on this BOM is an LCSC C-number — the board was designed for
this ecosystem. Parts that were unsourceable/overpriced at US houses (RP2040, ME6211,
HRO USB-C, TS-1187A) are all in-stock here, and fine-pitch board fab is cheap.

## Files to upload (all in this folder)

| JLCPCB slot | File |
|---|---|
| Gerber (PCB order) | `dc34-sao-revA-gerbers.zip` |
| BOM (PCBA step) | `dc34-sao-revA-BOM-jlcpcb.csv` |
| CPL / placement (PCBA step) | `dc34-sao-revA-CPL-jlcpcb.csv` |

## Steps

1. jlcpcb.com → **Order now** → upload `dc34-sao-revA-gerbers.zip`.
2. PCB options: 2-layer, 1.6 mm, **surface finish ENIG** (needed for the display flex +
   gold look), solder mask **black** (matte if offered), qty **5** (or more — board cost
   is tiny; assembly setup is the fixed cost).
3. Turn on **PCB Assembly** → **Assemble top & bottom sides** → Qty 5.
   - **Tooling/parts note (paste in):** "Do NOT populate J3 (TFT display) — hand-soldered
     after assembly. J1 is THT 2x3 header, mount on back. Leave J3 pads bare."
4. Upload **BOM** = `dc34-sao-revA-BOM-jlcpcb.csv`, **CPL** = `dc34-sao-revA-CPL-jlcpcb.csv`.
5. Parts match:
   - Actives auto-match by LCSC # (RP2040 C2040, flash C97521, LDO C82942, FETs C15127/
     C20917, D1 C8598, USB-C C165948, crystal C9002, switches C318884, LEDs C72043/C130719).
   - **Passives (100nF, 1uF, 10uF, all resistors) have no C-number** — JLC will prompt you
     to pick. Choose **Basic** parts by value+size (0402, 0805 for 10uF) to avoid
     extended-part feeder fees.

## MUST verify before you pay (2 minutes, prevents a dead batch)

- **Placement preview:** JLC overlays the CPL on the board render. Confirm parts sit on
  their pads and the outline shows the TV body + 2 antenna prongs. If everything is
  shifted by a constant offset, set the CPL origin to match the gerber origin.
- **Rotations on polarized parts** (KiCad↔JLC rotation offsets are a known quirk): check
  **D1** (cathode), **LED1/LED2/LED3**, **U1 pin 1**, **U2 pin 1**, **U3**, **J2 USB-C**
  in the preview. Fix any 90/180° rotation in JLC's editor before confirming.
- **J3 is absent** from BOM+CPL (correct) — you hand-solder the display after.

## After delivery

Hand-solder the 13-pin N114 display flex to J3: **pin 1 = TOP pad** (silk "1"), fold tail
under the panel per datasheet.

## Realistic timeline (order today)

Parts in stock → PCB fab 2-3 d → assembly 2-4 d → DHL 3-5 d ≈ **in hand ~Aug 1-4**.
Tight vs DC34 (Aug 6) but no sourcing wall to stall it. The only variable is
international shipping/customs — pick DHL, not economy.
