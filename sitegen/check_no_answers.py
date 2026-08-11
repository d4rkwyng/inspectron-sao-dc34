#!/usr/bin/env python3
"""Validate the built site (case set CF-00..CF-09):
1. No case-answer frequency string (with or without dot) anywhere in the
   site tree. HTML/text files get a strict substring scan; binary assets
   are scanned for the dotted forms plus undotted forms as STANDALONE
   ASCII digit runs (non-digit boundaries), so a PNG byte stream can't
   trip "0800"-style false positives.
2. No literal knock-sequence leak (3-6-23 / 63-64-66 in any separator
   style) in HTML.
3. No external requests (http/https/protocol-relative URLs) in HTML.
4. Every referenced local asset exists.
5. Every HTML file parses without structural errors (tag balance).
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"

# every case answer, dotted form
FREQS = ["034.1", "199.3", "080.0", "400.4", "170.4", "011.0",
         "023.0", "066.0", "404.0"]
UNDOTTED = [f.replace(".", "") for f in FREQS]
TEXT_EXT = {".html", ".txt", ".css", ".js", ".svg", ".md"}

# External hrefs permitted as NAVIGATION only (creator credits in the footer).
# These are anchor links, never resource loads (src) — "no external requests"
# in rule 3 still holds because the gate only allows them on href.
ALLOWED_EXTERNAL = ("https://mindtricks.io", "https://x.com/d4rkwyng")

# knock sequences: digits in order with any of - , > → / . or spaces between
def knock_re(a, b, c):
    sep = r"\s*(?:-|,|>|&gt;|&#8594;|/|\.)\s*"
    return re.compile(rf"(?<!\d){a}{sep}{b}{sep}{c}(?!\d)")

KNOCKS = [knock_re(3, 6, 23), knock_re(63, 64, 66),
          knock_re("03", "06", "23"), knock_re("063", "064", "066")]

fail = 0

print("== forbidden-string scan ==")
hits = 0
nfiles = 0
for f in sorted(SITE.rglob("*")):
    if not f.is_file():
        continue
    nfiles += 1
    data = f.read_bytes()
    is_text = f.suffix.lower() in TEXT_EXT
    for s in FREQS:                      # dotted: strict everywhere
        if s.encode() in data:
            print(f"HIT: {s!r} in {f}")
            hits += 1
    for s in UNDOTTED:
        if is_text:
            if s.encode() in data:
                print(f"HIT: {s!r} in {f}")
                hits += 1
        else:                            # binary: standalone ASCII run only
            if re.search(rb"(?<![0-9])" + s.encode() + rb"(?![0-9])", data):
                print(f"HIT (standalone run): {s!r} in {f}")
                hits += 1
    if is_text:
        text = data.decode(errors="replace")
        for kr in KNOCKS:
            if kr.search(text):
                print(f"HIT: knock sequence {kr.pattern!r} in {f}")
                hits += 1
print(f"{hits} hits across {nfiles} files")
fail += hits

VOID = {"meta", "img", "br", "hr", "audio", "link", "input", "source"}


class Check(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.path, self.stack, self.errs, self.refs = path, [], [], []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ("src", "href") and v:
                self.refs.append((k, v))
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errs.append(f"tag mismatch: </{tag}> vs stack {self.stack[-3:]}")
        else:
            self.stack.pop()


print("\n== HTML structure / external requests / asset references ==")
for f in sorted(SITE.rglob("*.html")):
    c = Check(f)
    c.feed(f.read_text())
    if c.stack:
        c.errs.append(f"unclosed tags: {c.stack}")
    for attr, r in c.refs:
        if re.match(r"^(https?:)?//", r):
            # Creator-credit links are allowed as navigation (href) only —
            # never as a resource load (src), so "no external requests" holds.
            if attr == "href" and any(r == a or r.startswith(a + "/")
                                      for a in ALLOWED_EXTERNAL):
                pass
            else:
                c.errs.append(f"external URL: {r}")
        elif r.startswith("data:") or r.startswith("#"):
            pass
        else:
            target = (f.parent / r.split("#")[0]).resolve()
            if not target.exists():
                c.errs.append(f"missing referenced file: {r}")
    if c.errs:
        fail += len(c.errs)
        for e in c.errs:
            print(f"{f.relative_to(SITE)}: {e}")
    else:
        print(f"{f.relative_to(SITE)}: OK ({len(c.refs)} refs)")

print("\nRESULT:", "FAIL" if fail else "PASS (0 findings)")
sys.exit(1 if fail else 0)
