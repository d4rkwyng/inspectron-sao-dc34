# SITE ASSET SOURCES

All exhibits are generated programmatically — no recorded or third-party
material anywhere in `site/`. Generators live in `sitegen/gen/` (kept
OUTSIDE `site/` so the published site never contains answer strings).

Environment: `sim/.venv/bin/python` with `numpy`, `pillow` (already in
`sim/requirements.txt`). Regenerate everything with:

```sh
cd sitegen/gen
PY=../../sim/.venv/bin/python
$PY gen_shared.py      # seal.png
$PY gen_smpte.py       # ident-card.png        (CF-00)
$PY gen_testpattern.py # testpattern-001.png   (CF-01)
$PY gen_form345.py     # form-345.png          (CF-02)
$PY gen_filmreel.py    # mcp-reel.gif          (CF-03)
$PY gen_signoff.py     # signoff.wav           (CF-04)
$PY gen_intrusion.py   # intrusion-still.png   (CF-05)
$PY gen_testcards.py   # lineage.png           (CF-06)
$PY gen_dsky.py        # dsky.png              (CF-07)
$PY verify_signoff.py  # independent Bell-103 demod round-trip check
```

Then rebuild pages + validate:

```sh
sim/.venv/bin/python sitegen/build_site.py
python3 sitegen/check_no_answers.py     # must PASS before any deploy
```

## Asset notes

- **seal.png** — circular Authority seal (CRT + antennas), PIL-drawn.
- **ident-card.png** (CF-00) — SMPTE 75% bars + ident slug. Near-black
  easter-egg text in the PLUGE strip; no digits related to the answer.
- **testpattern-001.png** (CF-01) — SMPTE bars with the station-history
  plaque burned into the lower third. No digits anywhere.
- **form-345.png** (CF-02) — photocopied Form IBA-345 with grime, stamp,
  and the type-acceptance riddle. No frequency appears; the answer lives
  in the device's I2C descriptor.
- **mcp-reel.gif** (CF-03) — film-leader countdown (8-7-6-5), title card,
  then a 22-frame pan over a synthetic chip die. The FRAME counter skips
  values; each skip flashes one large digit for a single frame (step
  frame-by-frame to read them). The generator retries seeds until the
  encoded bytes contain no forbidden digit run.
- **signoff.wav** (CF-04, 8 kHz mono, 25.4 s) — anthem-style tones, 1 kHz
  test tone, silence, then Bell 103 originate AFSK (mark 1270 / space
  1070 Hz, 300 baud, 8-N-1) carrying the WarGames payload; the modem
  segment repeats REVERSED as a red herring. `verify_signoff.py` is an
  independently written noncoherent demodulator that recovers the payload
  byte-for-byte and confirms the reversed copy decodes to garbage.
- **intrusion-still.png** (CF-05) — original glitch-art pastiche:
  venetian-blind slats, masked figure (rounded mask, dark glasses band,
  fixed grin — a nod at the iconic look, no likeness of the actual 1987
  footage), row-shear tears kept off the face, RGB channel offset,
  restrained noise, 40-color palette quantization (~215KB; the first cut
  was 1.1MB of incompressible noise).
- **lineage.png** (CF-06) — triptych of three ORIGINAL test-card
  pastiches (mono circle card, colour grid card with centre vignette,
  widescreen card) lettered C / F / W. Era styling only.
- **dsky.png** (CF-07) — pixel-art Apollo DSKY panel, PIL-drawn.

## Leak policy

`check_no_answers.py` scans every deployed byte for all nine case answers
(dotted and undotted), knock-sequence literals, external URLs, broken
refs, and HTML structure. Text files get strict substring scans; binary
assets are scanned for standalone ASCII digit runs so image noise cannot
false-positive. It must exit 0 before `site/` is deployed anywhere.
