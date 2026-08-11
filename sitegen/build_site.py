#!/usr/bin/env python3
"""Build the INSPECTRON BROADCAST AUTHORITY static puzzle site.

Case set: "Declassify the Broadcast Authority" CF-00..CF-09 (see CASES.md —
NEVER deploy that file). Emits site/index.html, site/puzzles/*.html,
site/404.html (GitHub Pages mirror of CF-09) and site/.nojekyll.
Fully static, self-contained, no external requests, works from file://.
Contains NO answers (validated by check_no_answers.py)."""
import base64
import io
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PUZ = SITE / "puzzles"

# Site root for the GitHub Pages 404 page's escape link. A relative link
# dead-ends (GH Pages serves 404.html AT the missing URL's depth, so
# "index.html" resolves relative to /puzzles/typo → another 404).
# "/" is right for a user site / custom domain; set "/<repo>/" for a
# project-pages deploy.
PAGES_BASE = "/"

FAVICON = ('data:image/svg+xml,<svg xmlns=%27http://www.w3.org/2000/svg%27 '
           'viewBox=%270 0 16 16%27><text y=%2713%27 font-size=%2713%27>'
           '&#128250;</text></svg>')


def exhibit(page_dir_depth, name, alt, pixel=False):
    """<img> tag for a site/assets exhibit with real width/height (so the
    page doesn't reflow as images arrive on slow wifi) + lazy loading."""
    from PIL import Image
    with Image.open(SITE / "assets" / name) as im:
        w, h = im.size
    cls = "exhibit pixel" if pixel else "exhibit"
    pre = "../" * page_dir_depth
    return (f'<img class="{cls}" src="{pre}assets/{name}" width="{w}" '
            f'height="{h}" loading="lazy"\n       alt="{alt}">')

# dotted + undotted forms of every case answer (see check_no_answers.py)
FORBIDDEN = ["034.1", "0341", "199.3", "1993", "080.0", "0800",
             "400.4", "4004", "170.4", "1704", "011.0", "0110",
             "023.0", "0230", "066.0", "0660", "404.0", "4040"]


def noise_data_uri():
    """Tiny grayscale noise tile as a data: URI, guaranteed free of
    forbidden digit runs in its base64 text."""
    from PIL import Image
    rng = random.Random(7)
    for attempt in range(200):
        img = Image.new("L", (40, 40))
        img.putdata([rng.randrange(256) for _ in range(1600)])
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode()
        if not any(f in b64 for f in FORBIDDEN):
            return "data:image/png;base64," + b64
    raise SystemExit("could not build clean noise tile")


NOISE = noise_data_uri()

CSS = """
:root {
  --ph: #3ce22c; --ph-dim: #2a9c20;
  --amber: #f0b429; --bg: #040704; --panel: rgba(10, 26, 9, .55);
  --line: #175c12;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--bg); color: var(--ph);
  font-family: "Courier New", ui-monospace, Menlo, Consolas, monospace;
  font-size: 16px; line-height: 1.55; min-height: 100vh;
  text-shadow: 0 0 7px rgba(60, 226, 44, .35);
  overflow-x: hidden;
}
body::before {
  content: ""; position: fixed; inset: 0; z-index: 9; pointer-events: none;
  background: repeating-linear-gradient(to bottom,
    rgba(0, 0, 0, .28) 0, rgba(0, 0, 0, .28) 1px, transparent 1px, transparent 3px);
  mix-blend-mode: multiply;
}
body::after {
  content: ""; position: fixed; inset: 0; z-index: 8; pointer-events: none;
  background-image: url("NOISE_URI");
  opacity: .05; animation: snowdrift .9s steps(4) infinite;
}
@keyframes snowdrift {
  0% { transform: translate(0, 0); } 25% { transform: translate(-11px, 7px); }
  50% { transform: translate(9px, -13px); } 75% { transform: translate(-6px, -5px); }
  100% { transform: translate(0, 0); }
}
.tube {
  max-width: 62rem; margin: 0 auto; padding: 1.6rem 1.2rem 3rem;
  animation: warmup 1.1s ease-out both;
}
@keyframes warmup { from { opacity: 0; filter: brightness(2.4) blur(2px); } }
a { color: var(--ph); }
a:hover { background: var(--ph); color: #041104; text-shadow: none; }
h1, h2, h3 { font-weight: 700; letter-spacing: .12em; }
h1 { font-size: 1.45rem; margin: .3rem 0; text-transform: uppercase; }
h2 { font-size: 1.05rem; color: var(--ph); text-transform: uppercase; }
.masthead { text-align: center; border-bottom: 3px double var(--line); padding-bottom: 1.1rem; }
.masthead img.seal { width: 122px; height: 122px; image-rendering: auto; }
.tagline { letter-spacing: .38em; color: var(--ph-dim); text-transform: uppercase; font-size: .8rem; }
.rule { border: 0; border-top: 1px dashed var(--line); margin: 1.4rem 0; }
.doc {
  border: 1px solid var(--line); background: var(--panel);
  padding: 1.1rem 1.3rem; margin: 1.3rem 0; position: relative;
}
.doc-head {
  display: flex; justify-content: space-between; flex-wrap: wrap; gap: .4rem;
  border-bottom: 1px solid var(--line); padding-bottom: .5rem; margin-bottom: .9rem;
  font-size: .78rem; letter-spacing: .18em; color: var(--ph-dim); text-transform: uppercase;
}
.stamp {
  display: inline-block; border: 2px solid var(--amber); color: var(--amber);
  text-shadow: 0 0 6px rgba(240, 180, 41, .5); padding: .1rem .55rem;
  transform: rotate(-2deg); letter-spacing: .22em; font-size: .74rem;
  text-transform: uppercase;
}
.stamp.green { border-color: var(--ph-dim); color: var(--ph); }
pre.flimsy {
  background: rgba(0, 0, 0, .45); border-left: 3px solid var(--line);
  padding: .8rem 1rem; overflow-x: auto; font-size: .92rem; line-height: 1.5;
  white-space: pre;
}
.transcript { color: var(--ph-dim); font-size: .92rem; }
.transcript em { color: var(--ph); font-style: normal; }
img.exhibit { display: block; max-width: 100%; height: auto; margin: 0 auto;
  border: 1px solid var(--line); }
img.pixel { image-rendering: pixelated; width: min(20rem, 88%); }
audio { width: 100%; margin: .6rem 0 .2rem; filter: sepia(1) hue-rotate(58deg) saturate(3.2); }
.dl { font-size: .85rem; letter-spacing: .06em; }
.grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(16.5rem, 1fr));
  gap: .9rem; margin-top: 1.2rem;
}
a.case {
  display: block; border: 1px solid var(--line); background: var(--panel);
  padding: .8rem .9rem; text-decoration: none; min-height: 9.5rem;
}
a.case:hover { background: rgba(60, 226, 44, .12); color: var(--ph); }
a.case:hover .cname { text-decoration: underline; }
.cno { font-size: .72rem; letter-spacing: .22em; color: var(--ph-dim); }
.cname { display: block; font-weight: 700; letter-spacing: .08em; margin: .35rem 0;
  text-transform: uppercase; }
.cmeta { font-size: .74rem; color: var(--ph-dim); letter-spacing: .1em; }
.glyph { color: var(--amber); text-shadow: 0 0 5px rgba(240, 180, 41, .45);
  letter-spacing: .18em; }
.teaser { font-size: .84rem; color: var(--ph-dim); margin-top: .45rem; }
.start { border-color: var(--amber); }
.start .cno::after { content: " · START HERE"; color: var(--amber); }
.notice { border: 1px dashed var(--amber); color: var(--amber); padding: .6rem .9rem;
  font-size: .82rem; letter-spacing: .08em; text-shadow: 0 0 6px rgba(240, 180, 41, .4); }
.bigconv {
  border: 2px solid var(--ph); padding: .9rem 1.1rem; margin: 1.3rem 0;
  font-size: 1.02rem; letter-spacing: .04em; background: rgba(0, 0, 0, .5);
}
.bigconv b { color: var(--amber); text-shadow: 0 0 6px rgba(240, 180, 41, .4); }
.glitch { animation: glitchpos 2.4s steps(2) infinite; }
@keyframes glitchpos {
  0%, 88% { transform: none; opacity: 1; }
  90% { transform: translate(-4px, 1px) skewX(3deg); opacity: .7; }
  93% { transform: translate(5px, -2px); opacity: 1; }
  96% { transform: translate(-2px, 0) skewX(-4deg); opacity: .5; }
}
.noseal {
  width: 122px; height: 122px; margin: 0 auto; border: 3px double var(--line);
  display: flex; align-items: center; justify-content: center; text-align: center;
  color: var(--ph-dim); font-size: .68rem; letter-spacing: .18em;
  text-transform: uppercase;
}
footer {
  margin-top: 2.4rem; border-top: 3px double var(--line); padding-top: 1rem;
  font-size: .78rem; color: var(--ph-dim); letter-spacing: .08em;
}
footer .conv { text-transform: uppercase; }
.smallprint { font-size: .78rem; color: var(--ph-dim); margin-top: .8rem; }
.backlink { letter-spacing: .18em; text-transform: uppercase; font-size: .8rem; }
.centered { text-align: center; }
@media (max-width: 40rem) {
  h1 { font-size: 1.2rem; }
  .tagline { letter-spacing: .22em; }
}
@media (prefers-reduced-motion: reduce) {
  *, body::before, body::after { animation: none !important; }
  .tube { animation: none; opacity: 1; filter: none; }
}
""".replace("NOISE_URI", NOISE)

# The tuning convention, playtest-hardened: whole numbers vs four-figure
# numbers get separate rules (the old single rule was self-contradictory
# for three-digit answers). Examples use a trap channel and the current
# year — never a case answer.
CONV_HTML = """Authority tuning convention &mdash; <b>whole numbers are
channels</b>: channel 42 reads 042.0; channel 500 reads 500.0. A
<b>subchannel</b> rides after the point: channel 7 subchannel 1 reads 007.1.
<b>Four-figure numbers</b> (years, codes) take the point before the final
digit: the year 2026 reads 202.6."""

OPERATION_SHEET = """<pre class="flimsy">RECEIVER OPERATION:
 1. Hold MODE ........... MASTER CONTROL panel
 2. CH&minus; then MODE ....... CASE FILES (the docket)
 3. Press MODE again .... FREQUENCY TUNER (the dial)
 4. CH+/CH&minus; spin digit .. short MODE hops to the next
 5. Hold MODE ........... channel commits</pre>
<p class="transcript">NOTE WELL: the Authority licenses the <em>full band</em>,
001.0 through 999.9 &mdash; channels of record fall anywhere on the dial. And the
Authority honors <em>conduct</em>: certain licenses are granted not for what you
dial, but for how you surf. The set is always watching.</p>"""


def shell(title, body, desc=None):
    meta_desc = (f'\n<meta name="description" content="{desc}">' if desc else "")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">{meta_desc}
<link rel="icon" href="{FAVICON}">
<title>{title}</title>
<style>{CSS}</style>
</head>
<body>
<div class="tube">
{body}
</div>
</body>
</html>
"""


# Creator credit — shown in every page footer.
CREDIT_HTML = ('<p class="smallprint">A SIGNAL FROM '
  '<a href="https://mindtricks.io" target="_blank" rel="noopener">MINDTRICKS.IO</a>'
  ' &middot; <a href="https://x.com/d4rkwyng" target="_blank" rel="noopener">'
  '@D4RKWYNG</a></p>')

TUNING_FOOTER = f"""<footer>
  <p class="conv">{CONV_HTML}</p>
  <p class="conv">The tuner takes three digits and a tenth: NNN.N &mdash;
  tune your own signal.</p>
  <p class="backlink"><a href="../index.html">&#9664; Return to the case index</a></p>
  <p class="smallprint">INSPECTRON BROADCAST AUTHORITY &middot; VOID WHERE SIGNAL PROHIBITED</p>
  {CREDIT_HTML}
</footer>"""


def puzzle_page(slug, caseno, codename, klass, glyph, body, title=None):
    head = f"""<header class="masthead">
  <img class="seal" src="../assets/seal.png" alt="Circular seal of the INSPECTRON Broadcast Authority: a CRT television with antenna">
  <h1>Inspectron Broadcast Authority</h1>
  <p class="tagline">Tune Your Own Signal</p>
</header>
<p class="doc-head" style="border:0;margin-top:1rem"><span>Case file {caseno}</span>
<span>Review class {klass} <span class="glyph">{glyph}</span></span></p>
<h2>{codename}</h2>"""
    html = shell(title or f"IBA &mdash; Case File {caseno}", head + body + TUNING_FOOTER)
    (PUZ / f"{slug}.html").write_text(html)
    return slug


# ---------------------------------------------------------------- pages
PUZ.mkdir(parents=True, exist_ok=True)

CASES = []  # (caseno, slug, codename, klass, glyph, teaser, tags)
G1, G2, G3, G4 = ("&#9646;&#9647;&#9647;&#9647;", "&#9646;&#9646;&#9647;&#9647;",
                  "&#9646;&#9646;&#9646;&#9647;", "&#9646;&#9646;&#9646;&#9646;")
GS = "&#9733;"


def add(caseno, slug, codename, klass, glyph, teaser, tags):
    CASES.append((caseno, slug, codename, klass, glyph, teaser, tags))


# CF-00 — SIGN-ON: STATION IDENT (onramp)
add("00", "station-ident", "Sign-On: Station Ident", "I", G1,
    "Prove reception. The Authority begins with itself.", "STATION IDENT")
puzzle_page("station-ident", "00", "Sign-On: Station Ident", "I", G1, f"""
<div class="bigconv">{CONV_HTML}</div>
<div class="doc">
  <div class="doc-head"><span>Proof of reception</span><span class="stamp green">Mandatory first review</span></div>
  {exhibit(1, "ident-card.png", "SMPTE color-bar station ident card. Lower third reads: IBA, Las Vegas, Subchannel 1. Proof of reception required.")}
  <hr class="rule">
  <p>Every licensed operator must first prove reception by tuning the
  Authority's own ident. <em>Our channel of record is the convention you are
  standing in &mdash; subchannel one.</em> Look down at your badge if you have
  forgotten where you are.</p>
  {OPERATION_SHEET}
</div>""")

# CF-01 — FIRST TRANSMISSION
add("01", "first-transmission", "First Transmission", "I", G1,
    "Every station signs on somewhere. Ours signed on in the desert.", "STATION PLAQUE")
puzzle_page("first-transmission", "01", "First Transmission", "I", G1, f"""
<div class="doc">
  <div class="doc-head"><span>Station history plaque</span><span class="stamp green">On file</span></div>
  {exhibit(1, "testpattern-001.png", "Color-bar test card. A station history plaque is burned into the lower third of the tube.")}
  <hr class="rule">
  <p class="transcript">PLAQUE TRANSCRIPT, FOR THE RECORD:</p>
  <pre class="flimsy">INSPECTRON BROADCAST AUTHORITY &mdash; STATION HISTORY PLAQUE
"FIRST BROADCAST: SANDS HOTEL &amp; CASINO, LAS VEGAS.
ROUGHLY ONE HUNDRED VIEWERS TUNED IN. ONE MAN RAN THE BOARD.
WE HAVE BEEN ON THE AIR EVERY SUMMER SINCE.
DIAL OUR SIGN-ON YEAR."</pre>
  <p class="transcript">The plaque speaks of the <em>station</em>, not the
  building. The station is younger than the hotel and louder every year.</p>
</div>""")

# CF-02 — KNOW YOUR SET
add("02", "know-your-set", "Know Your Set", "II", G2,
    "Present your apparatus for inspection.", "APPARATUS REQUIRED")
puzzle_page("know-your-set", "02", "Know Your Set", "II", G2, f"""
<p class="notice">APPARATUS REQUIRED &mdash; this review cannot proceed without a
licensed receiver present on the inspection bench.</p>
<div class="doc">
  <div class="doc-head"><span>Form IBA-345 &middot; Type Acceptance Division</span>
  <span class="stamp">Photocopy</span></div>
  {exhibit(1, "form-345.png", "Photocopied government form: Notice of Type Acceptance, rubber-stamped by the Type Acceptance Division.")}
  <hr class="rule">
  <p class="transcript">TRANSCRIPTION, FOR THE RECORD:</p>
  <p class="transcript">&ldquo;NOTICE TO LICENSEES. Every receiver manufactured under
  Authority contract carries its type-acceptance plate <em>at the standard
  address</em>. The plate is read, never written. The maker's mark is LIFE; the
  set answers to its name. Present your apparatus for inspection and state the
  address for the record &mdash; <em>the plate is engraved in the maker's
  hexadecimal, and the Authority speaks decimal</em>.
  VOID WHERE SIGNAL PROHIBITED.&rdquo;</p>
  <p class="transcript smallprint">Inspection port: see chassis markings SDA / SCL / GND.
  Any badge that speaks. Any village that listens. The maker publishes the
  service data.</p>
</div>""")

# CF-03 — COUNT THE FRAMES
add("03", "count-the-frames", "Count the Frames", "II", G2,
    "Four bits wide, and it ran the whole station.", "FILM EXHIBIT")
puzzle_page("count-the-frames", "03", "Count the Frames", "II", G2, f"""
<div class="doc">
  <div class="doc-head"><span>Engineering film &middot; maintenance reel</span><span class="stamp green">Declassified</span></div>
  <p>NOVEMBER 1971. Four bits wide, twenty-three hundred transistors, and it
  ran the whole station &mdash; master control on a sliver of silicon the size of a
  fingernail. The Authority never bought a second model. It never needed to.</p>
  <p>AUTHORIZATION: <em>dial the model</em>.</p>
  {exhibit(1, "mcp-reel.gif", "Animated engineering film: a film-leader countdown, then a slow pan over a stylized chip die photo. A frame counter in the corner stutters and skips.")}
  <p class="dl"><a href="../assets/mcp-reel.gif" download>&#9660; download mcp-reel.gif</a>
  <span class="transcript">(a bonus confirmation for the frame-counters &mdash; the
  specifications above already name the model)</span></p>
  <hr class="rule">
  <p class="transcript">VERIFICATION, for the careful: the model number reads
  the same in both directions, and its digits sum to eight. For the very
  careful: the projectionist reports the reel <em>drops frames</em> &mdash; and what
  a dropped frame shows, it shows only once.</p>
</div>""")

# CF-04 — THE ONLY WINNING MOVE
add("04", "only-winning-move", "The Only Winning Move", "III", G3,
    "After the anthem, after the test tone: the carrier persists.", "AUDIO EXHIBIT")
puzzle_page("only-winning-move", "04", "The Only Winning Move", "III", G3, f"""
<div class="doc">
  <div class="doc-head"><span>Program log &middot; final reel</span><span class="stamp">Carrier persists</span></div>
  <pre class="flimsy">02:00 &mdash; LATE MOVIE: "SHALL WE PLAY A GAME?" (1983)
04:11 &mdash; SIGN-OFF. ANTHEM. TEST TONE.
04:12 &mdash; [CARRIER PERSISTS]</pre>
  <p class="notice">MONITOR AT LOW GAIN &mdash; the carrier does not care for your ears.</p>
  <audio controls preload="none" src="../assets/signoff.wav"></audio>
  <p class="dl"><a href="../assets/signoff.wav" download>&#9660; download signoff.wav</a>
  <span class="transcript">(recorded off-air, 8 kHz mono)</span></p>
  <hr class="rule">
  <p class="transcript">MONITOR'S NOTE, typed at the desk: <em>the persistent
  carrier sings in Bell's oldest tongue &mdash; three hundred symbols to the second,
  patient as a metronome. Mid-reel it repeats itself backwards, as if checking
  its own work.</em></p>
</div>""")

# CF-05 — SIGNAL INTRUSION
add("05", "signal-intrusion", "Signal Intrusion", "II", G2,
    "He was never caught.", "INCIDENT REPORT")
puzzle_page("signal-intrusion", "05", "Signal Intrusion", "II", G2, f"""
<div class="doc">
  <div class="doc-head"><span>Incident report &middot; interference desk</span><span class="stamp">Unsolved</span></div>
  {exhibit(1, "intrusion-still.png", "Heavily glitched CRT still: a masked silhouette behind venetian-blind stripes, picture tearing, broadcast noise.")}
  <hr class="rule">
  <p>22 NOV 1987, LATE EVENING. THE SECOND CITY. During a science-fiction
  serial, a pirate in a rubber mask seized the tower of a public broadcasting
  station for a minute and a half of gibberish the tapes still cannot explain.
  He was never caught. He never transmitted again.</p>
  <p>The Authority does not forgive the interruption. It forgives the
  <em>station</em>. AUTHORIZATION: <em>dial the seat that was stolen</em>.</p>
</div>""")

# CF-06 — TEST CARD LINEAGE (knock)
add("06", "test-card-lineage", "Test Card Lineage", "III", G3,
    "The last seat is empty. It always was.", "STATION KNOCK")
puzzle_page("test-card-lineage", "06", "Test Card Lineage", "III", G3, f"""
<div class="doc">
  <div class="doc-head"><span>Succession record &middot; house of cards</span><span class="stamp green">Lineage certified</span></div>
  {exhibit(1, "lineage.png", "Triptych of three stylized television test cards, each printed with one large letter: C, F, and W.")}
  <hr class="rule">
  <pre class="flimsy">CARD C &mdash; 1948. Monochrome. A circle and frequency wedges.
         THE FOUNDER.
CARD F &mdash; 1967. Colour. The girl, the clown doll, the
         blackboard, dead centre of the grid. REIGNED FOR
         FOUR DECADES.
CARD W &mdash; The widescreen heir. THE LAST OF THE LINE.</pre>
  <p>Each card is known by a single letter, and <em>the procession has always
  been counted</em> &mdash; count each card's place in it.</p>
  <p>AUTHORIZATION: honor the succession ON YOUR SET. Visit each seat in
  order of accession &mdash; surf to it or dial it, the set is listening either
  way. Linger on each seat until the carrier is held; a channel you merely
  pass through does not register. <em>The last seat is empty. It always
  was.</em></p>
</div>""")

# CF-07 — TRANQUILITY DESCENT (knock)
add("07", "tranquility-descent", "Tranquility Descent", "III", G3,
    "The landing is the license.", "STATION KNOCK")
puzzle_page("tranquility-descent", "07", "Tranquility Descent", "III", G3, f"""
<div class="doc">
  <div class="doc-head"><span>Relay station dossier</span><span class="stamp green">Intercept, archived</span></div>
  {exhibit(1, "dsky.png", "Pixel-art display and keyboard panel with green electroluminescent segment digits; the computer-activity light is lit.")}
  <hr class="rule">
  <p>RELAY STATION: SEA OF TRANQUILITY, 20 JUL 1969. The finest broadcast the
  Authority ever intercepted was narrated from the surface of the Moon, and
  the computer that flew it worked in numbered PROGRAMS: P63, the braking
  burn. P64, the approach. And the one under which the Eagle actually set
  down &mdash; P66. (P65 was never flown; the commander took it semi-manual.)
  Five times the computer complained &mdash; 1202s, a lone 1201 &mdash; and flew on,
  every time. (Those alarm numbers are the story's colour, not your dial.)</p>
  <p>AUTHORIZATION: <em>fly the descent on your dial</em>. Three programs, in
  order. Between programs the set holds its breath &mdash; <em>twice</em> &mdash; and
  static is the sound of a held breath, not a refusal. THE LANDING IS THE
  LICENSE.</p>
</div>""")

# CF-08 — FIELD CONTACT (social)
add("08", "field-contact", "Field Contact", GS, GS,
    "The handshake is the license.", "FIELD REVIEW")
puzzle_page("field-contact", "08", "Field Contact", GS, GS, f"""
<p class="notice">NO DIAL &mdash; FIELD REVIEW.</p>
<div class="doc">
  <div class="doc-head"><span>Examiner's field protocol</span><span class="stamp green">Standing order</span></div>
  <p>This review has no channel of record and cannot be completed at a desk.
  The Authority licenses OPERATORS, and operators are found in the field.</p>
  <p>Seat your receiver on any badge that speaks. Introduce yourself; the
  sets will introduce themselves. <em>The handshake is the license.</em></p>
  <p class="transcript">No badge to seat against yet? This is the only license
  that waits for the field &mdash; every other case can be closed solo, at the
  dial. Leave this one open and return when a set is near.</p>
  <p class="transcript">The set will know. The set always knows.</p>
</div>""")

# CF-09 — MASTER CONTROL (meta; staged 404)
add("09", "master-control", "Master Control", "IV", G4,
    "Who licenses the licensors?", "RECORD MISSING")

MC_BODY = """<header class="masthead">
  <div class="noseal glitch">SEAL<br>NOT<br>FOUND</div>
  <h1 class="glitch">Inspectron Broadcast Auth&#9608;rity</h1>
  <p class="tagline">Tune Y&#9608;ur Own Signal</p>
</header>
<div class="doc" style="margin-top:2rem">
  <div class="doc-head"><span>Case file 09 &middot; Master Control</span>
  <span class="stamp">Record missing</span></div>
  <pre class="flimsy glitch">FILE NOT FOUND &mdash; ERROR 404

NO SUCH CASE.  NO SUCH DIVISION.
RECORDS OF THE "BROADCAST AUTHORITY" ...... NOT FOUND
PERSONNEL AT MASTER CONTROL ............... NOT FOUND
THERE WAS NEVER ANYONE AT MASTER CONTROL.

EVERY PIRATE ON THIS BAND LICENSED THEMSELVES.

THE ERROR IS THE FINDING.  FILE IT.</pre>
  <p class="transcript centered">A finding is filed where every number on this
  set is filed &mdash; on the dial. The Authority left you exactly one number.</p>
  <p class="transcript centered">tune your own signal. you always did.</p>
</div>
<!-- you read source. of course you do. there is no easter egg down here,
     because there is no master control. there never was. the error is the
     finding -- you know what to do with a finding. -->"""

(PUZ / "master-control.html").write_text(
    shell("IBA &mdash; FILE NOT FOUND", MC_BODY + TUNING_FOOTER))

# GitHub Pages 404 mirror (root-level; self-contained, no asset refs)
FOF_FOOTER = f"""<footer>
  <p class="conv">{CONV_HTML}</p>
  <p class="backlink"><a href="{PAGES_BASE}">&#9664; Return to the case index</a></p>
  <p class="smallprint">INSPECTRON BROADCAST AUTHORITY &middot; VOID WHERE SIGNAL PROHIBITED</p>
  {CREDIT_HTML}
</footer>"""
(SITE / "404.html").write_text(shell("IBA &mdash; FILE NOT FOUND", MC_BODY + FOF_FOOTER))
(SITE / ".nojekyll").write_text("")


# ---------------------------------------------------------------- about
# Colophon: breaks the fiction to credit the makers. Leak-safe (no answers).
ABOUT_BODY = f"""<header class="masthead">
  <img class="seal" src="assets/seal.png" alt="Circular seal of the INSPECTRON Broadcast Authority: a CRT television with antenna">
  <h1>Station Registration</h1>
  <p class="tagline">Who Runs This Band</p>
</header>
<div class="doc">
  <div class="doc-head"><span>Colophon &middot; for the record</span><span class="stamp green">On file</span></div>
  <p>The INSPECTRON BROADCAST AUTHORITY is a fiction. There is no Authority,
  no Licensing Division, no channel of record &mdash; only an <b>INSPECTRON 34</b>:
  a small CRT-television-shaped Simple Add-On (SAO) built for <b>DEF CON 34</b>.
  It plays meme GIFs as TV channels, and it hides this game &mdash; the case files
  on this site declassify frequencies you dial on the set itself.
  <em>Tune your own signal.</em></p>
  <p>Designed, fabricated, and programmed by <b>@d4rkwyng</b> &mdash; a
  <a href="https://mindtricks.io" target="_blank" rel="noopener">MINDTRICKS.IO</a>
  production.</p>
  <p class="transcript">Find the operator:
  <a href="https://x.com/d4rkwyng" target="_blank" rel="noopener">x.com/@d4rkwyng</a>
  &middot; <a href="https://mindtricks.io" target="_blank" rel="noopener">mindtricks.io</a></p>
  <hr class="rule">
  <p class="smallprint">All exhibits are original pastiches and all broadcasts
  are parody; no affiliation with any actual broadcaster, agency, or the
  programs referenced in the case files. VOID WHERE SIGNAL PROHIBITED.</p>
  <p class="backlink"><a href="index.html">&#9664; Return to the case index</a></p>
</div>
<footer>
  <p class="smallprint">INSPECTRON BROADCAST AUTHORITY &middot; VOID WHERE SIGNAL PROHIBITED</p>
  {CREDIT_HTML}
</footer>"""
(SITE / "about.html").write_text(shell(
    "IBA &mdash; Station Registration", ABOUT_BODY,
    desc="About INSPECTRON 34 — a DEF CON 34 CRT-TV SAO and puzzle by @d4rkwyng / mindtricks.io."))


# ---------------------------------------------------------------- index
cards = []
for caseno, slug, codename, klass, glyph, teaser, tags in CASES:
    start = " start" if caseno == "00" else ""
    cards.append(f"""<a class="case{start}" href="puzzles/{slug}.html">
  <span class="cno">CASE FILE {caseno}</span>
  <span class="cname">{codename}</span>
  <span class="cmeta">REVIEW CLASS {klass} <span class="glyph">{glyph}</span> &middot; {tags}</span>
  <p class="teaser">{teaser}</p>
</a>""")

index_body = f"""<header class="masthead">
  <img class="seal" src="assets/seal.png" alt="Circular seal of the INSPECTRON Broadcast Authority: a CRT television with antenna">
  <h1>Inspectron Broadcast Authority</h1>
  <p class="tagline">Tune Your Own Signal</p>
  <p class="transcript">LICENSING DIVISION &middot; PIRATE STATION AMNESTY PROGRAM &middot; SUMMER SESSION, LAS VEGAS</p>
</header>

<div class="doc">
  <div class="doc-head"><span>Public notice</span><span class="stamp green">Now in effect</span></div>
  <p>The Authority does not jam pirate stations. The Authority <em>licenses</em>
  them. Any operator may petition for a channel of record by completing a
  licensing review from the case files below. Each review, correctly concluded,
  yields exactly one channel &mdash; a frequency of the form NNN.N. That channel is
  yours. Tune it and transmit.</p>
  <p>Reviews are graded by class, I through IV. Class I reviews require only wit.
  Higher classes require tooling, patience, and in certain cases the licensed
  apparatus itself on your bench &mdash; or another operator entirely. The Authority
  confirms nothing in writing: <em>the receiver is the examiner</em>. A correct
  channel unlocks the programming it licenses. An incorrect channel yields
  static, as it should.</p>
</div>

<div class="doc">
  <div class="doc-head"><span>Receiver operation &middot; INSPECTRON</span><span class="stamp green">Service sheet</span></div>
  {OPERATION_SHEET}
</div>

<div class="bigconv">{CONV_HTML}</div>

<h2>Case files awaiting review</h2>
<div class="grid">
{chr(10).join(cards)}
</div>

<footer>
  <p>Begin with CASE FILE 00. The Authority recommends solving in ascending
  order of review class, but the band is open and the Authority is not your
  supervisor.</p>
  <p class="smallprint">SERVICE NOTE: older sets respond to the classics.</p>
  <p class="smallprint"><a href="about.html">Station registration &amp; colophon &#9658;</a></p>
  <p class="smallprint">INSPECTRON BROADCAST AUTHORITY &middot; NO CARRIER LEFT BEHIND &middot;
  VOID WHERE SIGNAL PROHIBITED</p>
  {CREDIT_HTML}
</footer>"""

(SITE / "index.html").write_text(shell(
    "Inspectron Broadcast Authority", index_body,
    desc="The Broadcast Authority licenses pirate stations. Complete a case file, earn a channel of record, tune your own signal. A DEF CON 34 SAO companion."))

print("wrote", SITE / "index.html")
print("wrote", SITE / "404.html", "+ .nojekyll")
for c in CASES:
    print("wrote", PUZ / (c[1] + ".html"))
print("wrote", PUZ / "master-control.html")
