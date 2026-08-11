# INSPECTRON 34 — menu specification
#
# ⚠ STATUS (Aug 4): DESIGN-INTENT DOCUMENT. The implementation has moved on
# in places — settings block is ver 0x02 (not 0x01), SPEED and STATIC WIPE
# rows were REMOVED, TV SCROLL and standby-default 30M were added, the root
# menu gained an ABOUT row. Where this file and the code disagree, THE CODE
# IS THE CONTRACT (ui.py/tuner.py/code.py); this file explains the why.
# AMENDED Jul 22 (rig feedback): CHANNEL GUIDE renamed CASE FILES,
# TV LISTINGS renamed TV GUIDE (auto-scrolls until first input)
# (guide/listings names were too similar); guide is opaque NAVY and flips
# PAGES (PG n/m) instead of line-scrolling; MODE-hold opens the menu.
# Settled Jul 21 2026 after a few dead-end drafts.
# Implementation target: firmware/ui.py.

Notes: the font charset is A-Z 0-9 space `. - + * / ?` only; `_NVM_LEN` = 91; the poll_badge/unlock_badge_link gap in ui screens is real (code.py:515-522).

# INSPECTRON 34 — FINAL MENU SPECIFICATION (rev A firmware)

Base: the final skeleton after a few dead-end drafts, keeping what survived them: the idle-timeout discipline and poll-callback bugfix, the inverse-video highlight bar and boot-channel-as-number rule, the no-tuner-timeout rule and hold-to-repeat everywhere, the rotating teasers + NO CARRIER breadcrumbs + LINK status line, and the separate-listings resolution of the guide question.

---

## 1. MENU TREE

```
TV PLAYBACK  (code.py main loop — every existing gesture unchanged)
 |- CH+ / CH- short .......... surf up/down (static wipe + channel bug)
 |- MODE short ............... brightness cycle (updates RAM settings, dirty flag)
 |- MODE hold 1.0s ........... MASTER CONTROL (AMENDED Jul 22: the two-
 |                            button pinch was hard on a worn badge;
 |                            combo below still works as secondary)
 |- CH+ alone hold 2.5s ...... auto-scan toggle (updates RAM settings, dirty flag)
 |- CH- alone hold 2.5s ...... standby toggle (AMENDED Jul 22: was MODE
 |                            hold; now the one-finger mirror of scan)
 |- konami ................... easter egg (unchanged)
 |- CH+ & CH- held 0.7s ==========> MASTER CONTROL
     |
     MASTER CONTROL  [ui.run_menu — cursor pre-seated on CHANNEL GUIDE]
      |  CH+/CH- = move highlight (wraps; hold = auto-repeat 0.5s/0.15s)
      |  MODE short = select row      MODE hold = nothing (reserved)
      |  CH+ & CH- held 0.7s = exit to TV   |   idle 20s = exit to TV
      |  (dirty playback-shortcut settings are diff-written on menu ENTRY)
      |
      |-- CHANNEL GUIDE  (secrets-only progress board — content unchanged)
      |     CH+/CH- scroll (NEW: hold-to-repeat)  |  MODE short = FREQ TUNER
      |     footer rotates hint <-> mechanic teasers while sealed rows remain
      |     BOTH 0.7s = back to MASTER CONTROL   |  idle 30s = TV
      |
      |-- TV LISTINGS  (NEW — the visible dial, built from scan_memes() only)
      |     CH+/CH- move cursor (hold-to-repeat; opens on current channel)
      |     MODE short = WATCH: exit UI, TV parks on that channel
      |     BOTH 0.7s = back to MASTER CONTROL   |  idle 30s = TV
      |
      |-- FREQ TUNER  (run_tuner — internals byte-identical)
      |     CH+/CH- spin digit (hold-repeat) | MODE short = next digit
      |     MODE hold 1.0s = TUNE -> unlock/trap/knock/miss exits WHOLE UI
      |     to TV via the existing code.py contract
      |     BOTH 0.7s = back to MASTER CONTROL (dial saved)
      |     NO idle timeout (players read the puzzle site mid-dial)
      |
      |-- SETTINGS  (single-mode cycle-in-place list, 8 rows)
      |     CH+/CH- move highlight (hold-repeat) | MODE short = cycle value
      |     BOTH 0.7s = diff-write NVM + back to MASTER CONTROL
      |     idle 20s = AUTOSAVE + exit to TV (never silently discard)
      |
      '-- EXIT TO TV  (discoverable no-gesture exit)

Universal grammar: CH+/- move or adjust (always hold-to-repeat), MODE short
selects/cycles, MODE hold is one big commit (TUNE) and nothing elsewhere,
BOTH held 0.7s = back exactly one level. Each level-up needs release +
re-hold (keys.events.clear() on screen entry — the shipped combo-refire
discipline; the scaffold enforces it). Timeouts are the strand-guard.
```

## 2. ASCII MOCKUPS (240x134, all strings within the real font charset)

**MASTER CONTROL** — opaque NAVY "bureau paperwork" fill (not snow); title AMBER scale 2; rows scale 2 at 18px pitch; highlight = full-width AMBER fillrect with NAVY text (Trinitron inverse bar — the font has no `>` glyph); status line scale 1: `LINK NO CARRIER` GREY flips live to `LINK UP` GREEN when BADGE_SLOT is set; `FW V6` from tuner.VERSION.

```
+--------------------------------------+
| MASTER CONTROL               3/16    |
| #############################        |
| # CHANNEL GUIDE             #        |
| #############################        |
|   TV LISTINGS                        |
|   FREQ TUNER                         |
|   SETTINGS                           |
|   EXIT TO TV                         |
| LINK NO CARRIER          FW V6       |
| CH+- MOVE  MODE OK  BOTH EXIT        |
+--------------------------------------+
```

**CHANNEL GUIDE** — run_guide visuals verbatim (snow 120, GREEN/WHITE unlocked, GREY `--.-  SEALED`, +/- arrows). Footer alternates every 4s between the hint and one teaser, only while sealed rows remain: `SOME CARRIERS ANSWER ONLY TO A KNOCK` / `DEAD AIR IS NOT ALWAYS DEAD` / `THE NETWORK REMEMBERS FIRST CONTACT`.

```
+--------------------------------------+
| CHANNEL GUIDE                 3/16   |
|  34.1   IDENT                        |
|  --.-   SEALED                       |
|  --.-   SEALED                       |
|  88.5   SILICON                      |
|  --.-   SEALED                    -  |
|                                      |
| SOME CARRIERS ANSWER ONLY TO A KNOCK |
+--------------------------------------+
```

**TV LISTINGS** — snow 120 ("received over the air", like the guide); rows scale 2, 5 visible, 20px pitch; number GREEN (dead = GREY `NO CARRIER`, unlocked secrets = AMBER at their NN.N), name WHITE from filename; cursor = AMBER fillrect bar; opens scrolled to the channel that was playing.

```
+--------------------------------------+
| TV LISTINGS                          |
|  CH 22   FSOCIETY                 +  |
| ############################         |
| # CH 23  NO CARRIER        #         |
| ############################         |
|  CH 24   TOASTERS                    |
|  CH 25   ALF                      -  |
|                                      |
| CH+- SCROLL  MODE WATCH  BOTH BACK   |
+--------------------------------------+
```

**FREQ TUNER** — pixel-identical to shipped run_tuner (heavy snow, scale-5 GREEN digits, AMBER fillrect cursor bar, bumpers unchanged). Only the BOTH-exit destination changes (menu, not TV).

```
+--------------------------------------+
|              CHANNEL                 |
|                                      |
|         0  8  7  .  5                |
|         ####                         |
|                                      |
|                                CH    |
|                                      |
|                                      |
| CH+- SPIN  MODE NEXT  HOLD TUNE      |
+--------------------------------------+
```

**SETTINGS** — opaque NAVY like the root; labels WHITE, values GREEN right-aligned x=168, highlight AMBER bar; 8 rows, 5 visible, +/- arrows; no edit mode — MODE cycles the value in place (wraps); BRIGHTNESS applies to the PWM on every cycle.

```
+--------------------------------------+
| SETTINGS                             |
| #############################        |
| # AUTO SCAN            OFF  #        |
| #############################        |
|   SCAN DWELL           8S            |
|   STATIC WIPE          ON            |
|   BRIGHTNESS           MED           |
|   SPEED                NORM       -  |
|                                      |
| CH+- ROW  MODE CHANGE  BOTH SAVE     |
+--------------------------------------+
```

## 3. GUIDE-CONTENT DECISION

**Keep CHANNEL GUIDE secrets-only; ship the visible dial as the separate TV LISTINGS screen with MODE-to-WATCH.** The ordering-leak argument is decisive: any merged list sorted by channel number interleaves SEALED rows into numeric positions, and a sealed row bracketed between CH 33 and CH 35 is a triangulation oracle that defeats `_SLOTS`' deliberate hash-order — while avoiding that sort means two lists on one screen anyway, i.e. two screens. Splitting also preserves the guide's progress-board psychology (3/16 and a wall of SEALED taunts, undiluted by 43 free rows) and makes the no-leak property *structural*: TV LISTINGS is built exclusively from `scan_memes()` + `CHANNEL_MAP` (never `_PATHS`/`_SLOTS`), so locked secrets cannot appear by construction, dead channels render as already-public `NO CARRIER` rows (a deniable knock-seat map that quietly shrinks when CF-06 brings one alive), and unlocked secrets join the listings at their learned number in AMBER — the "dead channel comes alive" payoff. One keeper from the dead drafts: select-to-jump, which turns the listings into the remote control the 48-stop surf loop badly needs; the dwell gate (`knock_dwell_cb`) still applies on arrival (checked), so nothing about the game gets cheaper.

## 4. SETTINGS + NVM LAYOUT

All 8 settings are small enums, cycled in place. Defaults exactly reproduce today's shipped behavior.

| Row | Values (cycle order) | Applies |
|---|---|---|
| AUTO SCAN | OFF / ON | live (shared flag with CH+ hold gesture) |
| SCAN DWELL | 4S / 8S / 15S / 30S | on exit (SCAN_SECS) |
| STATIC WIPE | ON / OFF | on exit (STATIC_FRAMES 4 or 0) |
| BRIGHTNESS | MED / LOW / HIGH | LIVE per cycle (idx into BRIGHTNESS_LEVELS, shared with MODE-short) |
| SPEED | NORM / SLOW / FAST | on exit (FRAME_MIN,MAX = .10/.22, .14/.30, .08/.16) |
| SURF ORDER | DIAL / SHUFFLE | on exit (seeded per-boot shuffle of surf order only) |
| STANDBY | OFF / 5M / 15M / 30M | on exit (idle-since-last-keypress timer; paused while AUTO SCAN is on) |
| BOOT CH | FIRST / HERE | HERE captures the current channel NUMBER (integer channels only; on a secret NN.N channel it stores FIRST); value cell shows `FIRST` or `CH 27` |

**NVM: a self-versioned block appended at offset `tuner._NVM_LEN` (= 91), byte-per-field, NO tuner.VERSION bump** (unlock flags are player progress and settings churn must never wipe them, nor vice versa; bit-packing rejected — saves 5 bytes of 4KB and buys mask bugs).

```
off 91   magic        0x53 ('S')
off 92   settings ver 0x01
off 93   auto_scan    0/1                 (default 0)
off 94   dwell_idx    0-3 -> 4/8/15/30s   (default 1 = 8S)
off 95   static_wipe  0/1                 (default 1 = ON)
off 96   bright_idx   0-2 into BRIGHTNESS_LEVELS (0.6,0.3,0.85); labels MED/LOW/HIGH (default 0)
off 97   speed_idx    0-2 NORM/SLOW/FAST  (default 0)
off 98   order        0=DIAL 1=SHUFFLE    (default 0)
off 99   standby_idx  0-3 OFF/5/15/30 min (default 0)
off 100  boot_hi  }   tuner._pack_digits format, channel NUMBER not list
off 101  boot_lo  }   index (SHUFFLE-proof); 0,0 = FIRST (default)
off 102  checksum     XOR of bytes 91..101
```

Load: bad magic/version/checksum → factory defaults; additionally clamp every index against its option count (a corrupt byte can never crash the UI). Write: diff-write (compare-before-write, tuner's existing idiom) ONLY on settings-screen exit/autosave, plus on root-menu entry and standby entry if the playback shortcuts (brightness/scan) dirtied the RAM copy — never per keypress, never per surf.

## 5. IMPLEMENTATION NOTES

**ui.py (~+210 lines)**
- Extract a ~30-line list scaffold from run_guide's proven loop shape (10fps redraw, poll() forwarding, `keys.events.clear()` on entry, BOTH-combo detection, NEW: hold-to-repeat reusing `_REPEAT_AFTER`/`_REPEAT_EVERY`, NEW: optional idle-timeout arg, `fb.reclaim()` on entry). Menu, guide, listings, settings all instantiate it.
- `run_menu(...)` (~45): 5 rows, NAVY fill, AMBER inverse bar, LINK/FW footer, returns `"guide" | "listings" | "tune" | "settings" | None`; 20s timeout returns None.
- `run_guide` (~25 changed): keep `"tune"` return on MODE (site-documented flow survives via the pre-seated cursor: combo, MODE, MODE still reaches the dial); add repeat + 30s timeout + rotating teaser footer (module tuple, gated on `done < total`); BOTH now returns None to the *dispatcher* (destination decided by caller).
- `run_listings(rows, start_idx, ...)` (~55): takes prebuilt row tuples `(label, name, kind, path_or_None)` from code.py; returns `("watch", path)` or None. Never imports channel data itself.
- `run_settings(settings)` (~65): cycle-in-place over a static `((name, labels, key), ...)` table; live brightness apply via a callback; returns on BOTH/timeout after `tuner.settings_save()`.

**tuner.py (~+45 lines)**
- `_SET_OFF = _NVM_LEN`; `SETTINGS_DEFAULTS`; `settings_load() -> dict` (validate + clamp), `settings_save(dict)` (diff-write + checksum). RAM fallback mirrors the `_ram_flags` pattern when nvm is unavailable.
- Add the comment: `# _SLOTS hash order is LOAD-BEARING SECRECY — never re-sort sealed rows numerically.`

**code.py (~+120 lines)**
- Hoist `CHANNEL_MAP`/`DEAD_CHANNELS` above the `_BOOT_GIF` stanza (pure literals, safe); boot stanza peeks raw nvm bytes 91/92/100-102 (magic+checksum+boot number, heap-trivial) and preopens the mapped file if it exists, else first alphabetical — this is the mitigation that makes BOOT CH safe against the Jul 21 cold-boot MemoryError. Secret NN.N targets are unreachable pre-import, hence the FIRST fallback rule above.
- Replace bare globals `AUTO_SCAN`/`SCAN_SECS`/`STATIC_FRAMES`/`FRAME_MIN,MAX`/`brightness_idx` with one `SETTINGS` dict + `apply_settings()` (~20 lines), called at boot and settings-exit. MODE-short and CH+-hold gestures mutate the same dict + dirty flag.
- **Fix the live bug**: wrap the poll callback passed to every ui screen — `def poll_ui(): 
 if poll_badge(): tuner.unlock_badge_link()` — and drain `badge_cmd_event()` inside it (blips still blip; queued badge up/down commands must not replay as surf events after menu exit). Today badge contact inside guide/tuner silently misses the BADGE LINK unlock.
- Rewrite the `event == "tuner"` branch as a dispatcher while-loop around `run_menu`: guide→(None back to menu | "tune"→tuner), listings→("watch",path) sets `channel = channels.index(path)`, tuner results fall through to the **byte-identical** existing knock/trap/miss/nedry block, `controls.reset()` on every return. SHUFFLE applies to surf order only (`_chan_num`-keyed knock visits and labels are order-independent).
- Standby idle timer: track last keypress in `Controls`, check in main loop, reuse the existing standby branch; timer also resets on badge I2C activity and pauses while AUTO_SCAN is on (shelf demos must not blank).

**Render-cost caveat**: NAVY full fill + 5 scale-2 rows at 10fps is the heaviest pure-Python redraw yet; if the rig lags, switch menu/settings to dirty-only redraw (repaint on input) while keeping poll() at ~10Hz.

## 6. OPEN QUESTIONS

1. **Naming/fiction**: spec says `MASTER CONTROL` (service-menu authentic). Rename to `IBA FIELD OFFICE` to match the site's Licensing Division voice? One string; decide before the site copy update.
2. **Site pointer**: should the root menu footer carry the puzzle-site hostname next to `FW V6`? Needs the final hostname, drawable from `A-Z 0-9 . - /` (the font has no colon — adding a `:` glyph is 1 line if the URL needs one).
3. **BOOT CH = HERE on a secret channel** stores FIRST (pre-import resolution can't map /secret files). Acceptable for rev A, or extend the raw-peek to scan /secret filenames (+~10 lines in the boot stanza)?