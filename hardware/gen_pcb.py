#!/usr/bin/env python3
"""Generate dc34-sao.kicad_pcb — DC34 Meme TV SAO board.

Run with KiCad's bundled python (needs pcbnew):
  ~/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 gen_pcb.py [--dump]

Board: 58x42mm retro CRT TV, rabbit-ear antennas on top.
Layers: F.Cu = GND pour (+ button trunk), B.Cu = VDD pour + signal routing.
SAO header top-left (right-badge-port orientation, <=21mm inboard rule).
"""

import math
import os
import re
import sys

import wx  # noqa: F401 — pcbnew's standalone mode needs a wx App context
_app = wx.App(redirect=False)

import pcbnew
from pcbnew import VECTOR2I, FromMM

HERE = os.path.dirname(os.path.abspath(__file__))
NETLIST = os.path.join(HERE, "netlist.net")
OUT = os.path.join(HERE, "dc34-sao.kicad_pcb")
SYS_FP = os.path.expanduser(
    "~/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")
PRJ_FP = os.path.join(HERE, "lib")

ORG_X, ORG_Y = 100.0, 100.0   # board top-left in sheet coords
W, H = 58.0, 42.0             # TV body

def P(x, y):
    """Board-local mm -> VECTOR2I sheet position."""
    return VECTOR2I(FromMM(ORG_X + x), FromMM(ORG_Y + y))


# --------------------------------------------------------------------------
# Netlist parsing (kicadsexpr)
# --------------------------------------------------------------------------

def _balanced(txt, start):
    depth = 0
    j = start
    while True:
        if txt[j] == '(':
            depth += 1
        elif txt[j] == ')':
            depth -= 1
            if depth == 0:
                return txt[start:j + 1]
        j += 1


def parse_netlist(path):
    txt = open(path).read()
    comps = {}
    for m in re.finditer(r'\(comp\s*\n', txt):
        blk = _balanced(txt, m.start())
        ref = re.search(r'\(ref "([^"]+)"\)', blk).group(1)
        fp = re.search(r'\(footprint "([^"]*)"\)', blk)
        comps[ref] = fp.group(1) if fp else ""
    nets = {}
    for m in re.finditer(r'\(net\s*\n\s*\(code', txt):
        blk = _balanced(txt, m.start())
        name = re.search(r'\(name "([^"]+)"\)', blk).group(1)
        nodes = re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', blk)
        nets[name] = nodes
    return comps, nets


# --------------------------------------------------------------------------
# Placement: ref -> (x, y, rot_deg, side)   side: 'F' or 'B'
# --------------------------------------------------------------------------

PLACE = {
    # front
    "J3":  (38.0, 22.0, 0, "F"),     # TFT pad row; panel spans x 11..42
    "SW1": (51.0, 20.0, 0, "F"),     # CH-
    "SW2": (51.0, 12.0, 0, "F"),     # CH+
    "SW3": (51.0, 28.0, 0, "F"),     # MODE
    "LED1": (32.0, 34.0, 0, "F"),
    # back: connectors / power
    "J1":  (18.08, 7.04, 90, "B"),   # SAO header, pin1(VCC) here
    "J2":  (44.0, 38.0, 180, "B"),   # USB-C, opening at bottom edge
    "U3":  (33.0, 37.0, 0, "B"),     # LDO
    "Q1":  (11.0, 13.0, 0, "B"),     # power mux
    "D1":  (27.0, 37.0, 90, "B"),
    "C17": (37.0, 34.5, 90, "B"),
    "C18": (29.5, 34.5, 90, "B"),
    "C19": (7.0, 13.0, 90, "B"),
    "R5":  (8.0, 22.0, 90, "B"),     # VBUS 100k pulldown
    "R9":  (50.0, 32.0, 90, "B"),    # CC1
    "R10": (52.2, 32.0, 90, "B"),   # CC2
    "R7":  (38.2, 28.4, 0, "B"),     # USB DP 27R
    "R8":  (38.2, 30.2, 0, "B"),     # USB DM 27R
    # back: MCU cluster
    "U1":  (26.0, 22.0, 180, "B"),
    "U2":  (33.5, 11.0, 90, "B"),    # QSPI flash above U1
    "Y1":  (21.0, 32.0, 0, "B"),
    "R1":  (16.5, 32.0, 90, "B"),
    "C1":  (25.5, 32.0, 90, "B"),
    "C2":  (16.5, 35.5, 90, "B"),
    "SW4": (46.0, 8.0, 0, "B"),      # BOOT
    "R2":  (40.0, 8.0, 0, "B"),
    # back: TFT backlight
    "Q2":  (43.5, 26.5, 0, "B"),
    "R6":  (43.5, 23.5, 0, "B"),
    "R11": (43.5, 29.5, 0, "B"),
    "R3":  (28.5, 33.0, 0, "B"),     # LED series
    # decoupling (back, around U1; chip body 7x7 at 22.5..29.5)
    "C3":  (19.0, 17.0, 90, "B"),
    "C4":  (32.8, 17.0, 90, "B"),
    "C5":  (19.0, 26.8, 90, "B"),
    "C6":  (32.8, 26.8, 90, "B"),
    "C7":  (20.5, 14.2, 0, "B"),
    "C8":  (26.0, 29.8, 0, "B"),
    "C9":  (24.0, 14.2, 0, "B"),
    "C10": (27.2, 14.2, 0, "B"),
    "C11": (37.5, 15.0, 0, "B"),     # flash decouple
    "C12": (22.6, 12.2, 0, "B"),     # DVDD
    "C13": (26.4, 12.2, 0, "B"),     # DVDD
    "C14": (24.5, 10.4, 0, "B"),     # DVDD 1uF
    "C15": (32.8, 19.8, 90, "B"),    # VREG_VIN 1uF
    "C16": (18.0, 22.0, 90, "B"),    # bulk 10u
    "C20": (44.0, 18.5, 90, "B"),    # TFT VDD
    "C21": (44.0, 15.0, 90, "B"),
    # test points (back, bottom-left row)
    "TP1": (10.0, 38.5, 0, "B"),
    "TP2": (13.5, 38.5, 0, "B"),
    "TP3": (17.0, 38.5, 0, "B"),
    "TP4": (20.5, 38.5, 0, "B"),
}

FP_DIR_OVERRIDE = {"dc34-sao": os.path.join(PRJ_FP, "dc34-sao.pretty")}


def load_fp(fpid):
    lib, name = fpid.split(":")
    path = FP_DIR_OVERRIDE.get(lib, os.path.join(SYS_FP, lib + ".pretty"))
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise SystemExit(f"footprint not found: {fpid}")
    return fp


# --------------------------------------------------------------------------
# Routing table: (net, [waypoints], width_mm)
# waypoint: ("pad", ref, pin) | (x, y) | ("via",) at previous point
# Routing layer starts at B.Cu; "via" toggles F.Cu/B.Cu.
# "L" between consecutive points: auto dx-then-dy elbow.
# --------------------------------------------------------------------------

SIG = 0.2
PWR = 0.5

# nets that connect purely through zones
ZONE_F = "GND"
ZONE_B = "VDD"


def main():
    dump = "--dump" in sys.argv
    comps, nets = parse_netlist(NETLIST)

    board = pcbnew.NewBoard(OUT)

    # net objects
    netmap = {}
    for name in nets:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netmap[name] = ni

    pad_net = {}   # (ref,pin) -> netname
    for name, nodes in nets.items():
        for ref, pin in nodes:
            pad_net[(ref, pin)] = name

    # footprints
    fps = {}
    for ref, fpid in sorted(comps.items()):
        if ref.startswith("#"):
            continue
        if ref not in PLACE:
            raise SystemExit(f"no placement for {ref}")
        x, y, rot, side = PLACE[ref]
        fp = load_fp(fpid)
        fp.SetReference(ref)
        board.Add(fp)
        fp.SetPosition(P(x, y))
        if side == "B":
            fp.Flip(P(x, y), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(rot)
        fps[ref] = fp
        for pad in fp.Pads():
            key = (ref, pad.GetNumber())
            if key in pad_net:
                pad.SetNet(netmap[pad_net[key]])

    def pad_pos(ref, pin):
        for pad in fps[ref].Pads():
            if pad.GetNumber() == pin:
                return pad.GetPosition()
        raise SystemExit(f"pad {ref}.{pin} not found")

    if dump:
        for ref in sorted(fps):
            for pad in fps[ref].Pads():
                p = pad.GetPosition()
                print(f"{ref}.{pad.GetNumber()} {pad.GetNetname() or '-':<14}"
                      f" ({pcbnew.ToMM(p.x)-ORG_X:.2f},{pcbnew.ToMM(p.y)-ORG_Y:.2f})"
                      f" {'B' if pad.IsFlipped() else 'F'}")
        return

    # ---- SAO header orientation assertion (front view):
    # 3.0V(1) bottom-right, GND(2) above it, GPIO1(5) bottom-left.
    p1, p2, p5 = pad_pos("J1", "1"), pad_pos("J1", "2"), pad_pos("J1", "5")
    assert p1.x > p5.x and abs(p1.y - p5.y) < FromMM(0.1), "J1 row wrong"
    assert p2.x == p1.x and p2.y < p1.y, "J1 col wrong"

    # ---- edge cuts: TV body rounded rect + rabbit ears
    EC = pcbnew.Edge_Cuts

    def seg(x1, y1, x2, y2, layer=EC, w=0.1):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(x1, y1)); s.SetEnd(P(x2, y2))
        s.SetLayer(layer); s.SetWidth(FromMM(w))
        board.Add(s)

    def arc3(sx, sy, mx, my, ex, ey, layer=EC, w=0.1):
        if "--chord-outline" in sys.argv and layer == EC:
            # freerouting chokes on arc outlines: approximate with chords
            seg(sx, sy, mx, my, layer, w)
            seg(mx, my, ex, ey, layer, w)
            return
        a = pcbnew.PCB_SHAPE(board)
        a.SetShape(pcbnew.SHAPE_T_ARC)
        a.SetArcGeometry(P(sx, sy), P(mx, my), P(ex, ey))
        a.SetLayer(layer); a.SetWidth(FromMM(w))
        board.Add(a)

    r = 3.0
    k = r * 0.2929  # 1-cos45 for arc midpoints
    # top edge (split by antenna bases at 30..33 and 40..43)
    seg(r, 0, 30, 0)
    seg(33, 0, 40, 0)
    seg(43, 0, W - r, 0)
    # right, bottom, left edges
    seg(W, r, W, H - r)
    seg(W - r, H, r, H)
    seg(0, H - r, 0, r)
    # corners
    arc3(W - r, 0, W - k, k, W, r)
    arc3(W, H - r, W - k, H - k, W - r, H)
    arc3(r, H, k, H - k, 0, H - r)
    arc3(0, r, k, k, r, 0)
    # left antenna (tilts left)
    seg(30, 0, 26.0, -9.0)
    seg(33, 0, 29.0, -9.0)
    arc3(26.0, -9.0, 27.5, -10.6, 29.0, -9.0)
    # right antenna (tilts right)
    seg(40, 0, 47.0, -8.0)
    seg(43, 0, 49.6, -8.0)
    arc3(47.0, -8.0, 48.3, -9.5, 49.6, -8.0)

    # ---- zones are added in --final mode (after autorouting)

    # ---- silkscreen art
    FS, BS = pcbnew.F_SilkS, pcbnew.B_SilkS

    def text(s, x, y, layer=FS, size=1.2, thick=0.2, angle=0):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(s)
        t.SetPosition(P(x, y))
        t.SetLayer(layer)
        t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
        t.SetTextThickness(FromMM(thick))
        t.SetTextAngleDegrees(angle)
        if layer == BS:
            t.SetMirrored(True)
        board.Add(t)

    def rect(x1, y1, x2, y2, layer=FS, w=0.15):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_RECT)
        s.SetStart(P(x1, y1)); s.SetEnd(P(x2, y2))
        s.SetLayer(layer); s.SetWidth(FromMM(w))
        s.SetFilled(False)
        board.Add(s)

    def circle(cx, cy, rad, layer=FS, w=0.15):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_CIRCLE)
        s.SetStart(P(cx, cy)); s.SetEnd(P(cx + rad, cy))
        s.SetLayer(layer); s.SetWidth(FromMM(w))
        board.Add(s)

    # screen bezel (double)
    rect(9.0, 11.0, 44.0, 33.0, w=0.3)
    rect(10.2, 12.2, 42.8, 31.8, w=0.15)
    # knob rings + labels
    for cy, lbl in [(12.0, "CH+"), (20.0, "CH-"), (28.0, "MODE")]:
        circle(51.0, cy, 3.4)
        text(lbl, 51.0, cy + 4.6, size=0.8, thick=0.15)
    # power LED label
    text("PWR", 32.0, 36.6, size=0.8, thick=0.15)
    # speaker grille
    for i in range(5):
        seg(7.0, 34.0 + i * 1.3, 19.0, 34.0 + i * 1.3, layer=FS, w=0.3)
    # nameplate + branding
    text("MEME-TRON 3400", 30.0, 36.8, size=1.4, thick=0.25)
    text("DC34", 52.5, 5.0, size=2.0, thick=0.35)
    # antenna silk
    seg(31.0, -1.0, 27.6, -8.6, layer=FS, w=0.3)
    seg(41.8, -1.0, 47.9, -7.6, layer=FS, w=0.3)
    circle(27.5, -9.3, 0.7, layer=FS, w=0.3)
    circle(48.3, -8.4, 0.7, layer=FS, w=0.3)
    # wood grain strips (subtle wavy lines top/bottom margins)
    for i, yy in enumerate([2.2, 4.4, 6.6]):
        seg(24.0 if yy < 5 else 22.0, yy, 56.0 - i * 3, yy, layer=FS, w=0.15)
    for i, yy in enumerate([39.8, 41.0]):
        seg(24.0, yy, 44.0 - i * 6, yy, layer=FS, w=0.15)

    # back silk: SAO pinout + credits
    text("3.0V", 18.08, 10.2, layer=BS, size=0.7, thick=0.13)
    text("GND", 18.08, 2.6, layer=BS, size=0.7, thick=0.13)
    text("SDA", 15.54, 10.2, layer=BS, size=0.7, thick=0.13)
    text("SCL", 15.54, 2.6, layer=BS, size=0.7, thick=0.13)
    text("G1", 13.0, 10.2, layer=BS, size=0.7, thick=0.13)
    text("G2", 13.0, 2.6, layer=BS, size=0.7, thick=0.13)
    text("<- BADGE (right SAO port)", 18.0, 12.6, layer=BS, size=0.9, thick=0.15)
    text("DC34 MEME TV SAO rev A", 29.0, 20.0, layer=BS, size=1.3, thick=0.22)
    text("@d4rkwyng 2026", 29.0, 22.4, layer=BS, size=1.0, thick=0.18)
    text("hold BOOT + plug USB = UF2", 29.0, 24.6, layer=BS, size=0.9, thick=0.15)
    text("BOOT", 46.0, 5.6, layer=BS, size=0.8, thick=0.15)
    for ref, lbl in [("TP1", "SWC"), ("TP2", "SWD"), ("TP3", "GND"),
                     ("TP4", "3V")]:
        x, y, _, _ = PLACE[ref]
        text(lbl, x, y + 1.9, layer=BS, size=0.6, thick=0.12)

    # ---- save + DSN export for freerouting
    pcbnew.SaveBoard(OUT, board)
    dsn = os.path.join(HERE, "dc34-sao.dsn")
    ok = pcbnew.ExportSpecctraDSN(board, dsn)
    print(f"Wrote {OUT}: {len(fps)} footprints, {board.GetNetCount()} nets; "
          f"DSN export: {ok}")


def finalize():
    """Load the routed board, add GND/VDD zones, fill, save."""
    board = pcbnew.LoadBoard(OUT)

    def add_zone(layer, netname, name):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(board.FindNet(netname))
        z.SetZoneName(name)
        pts = [P(-1, -12), P(W + 1, -12), P(W + 1, H + 1), P(-1, H + 1)]
        chain = pcbnew.SHAPE_LINE_CHAIN()
        for pt in pts:
            chain.Append(pt.x, pt.y)
        chain.SetClosed(True)
        z.Outline().AddOutline(chain)
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(FromMM(0.3))
        z.SetThermalReliefSpokeWidth(FromMM(0.4))
        z.SetMinThickness(FromMM(0.2))
        z.SetLocalClearance(FromMM(0.2))
        board.Add(z)

    add_zone(pcbnew.F_Cu, "GND", "gnd-front")
    add_zone(pcbnew.B_Cu, "VDD", "vdd-back")

    # Stitch vias: every back-side GND pad gets a via to the front pour,
    # every front-side VDD pad gets a via to the back pour. Offset chosen
    # collision-aware against all other pads and existing vias.
    all_pads = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            all_pads.append(pad)
    existing_vias = [t for t in board.GetTracks()
                     if t.GetClass() == "PCB_VIA"]
    existing_tracks = [t for t in board.GetTracks()
                       if t.GetClass() == "PCB_TRACK"]
    placed = []

    def _seg_dist(pos, a, b):
        px, py = pos.x, pos.y
        ax, ay, bx, by = a.x, a.y, b.x, b.y
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        if L2 == 0:
            return math.hypot(px - ax, py - ay)
        tt = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
        return math.hypot(px - (ax + tt * dx), py - (ay + tt * dy))

    def clear_at(pos, own_net):
        for pad in all_pads:
            if pad.GetNetname() == own_net:
                continue
            d = (pad.GetPosition() - pos).EuclideanNorm()
            if d < FromMM(0.8):
                return False
        for v in existing_vias:
            if (v.GetPosition() - pos).EuclideanNorm() < FromMM(0.75):
                return False
        for tr in existing_tracks:
            if tr.GetNetname() == own_net:
                continue
            lim = FromMM(0.3 + 0.13) + tr.GetWidth() // 2
            if _seg_dist(pos, tr.GetStart(), tr.GetEnd()) < lim:
                return False
        for p2 in placed:
            if (p2 - pos).EuclideanNorm() < FromMM(0.75):
                return False
        return True

    def seg_clear_for(netname, a, b, w=0.3):
        for tr in existing_tracks:
            if tr.GetNetname() == netname:
                continue
            need = FromMM(w / 2 + 0.13) + tr.GetWidth() // 2
            if _segseg(a, b, tr.GetStart(), tr.GetEnd()) < need:
                return False
        for v in existing_vias:
            if v.GetNetname() == netname:
                continue
            if _segseg(a, b, v.GetPosition(), v.GetPosition()) < \
                    FromMM(w / 2 + 0.13 + 0.3):
                return False
        for pad in all_pads:
            if pad.GetNetname() == netname:
                continue
            bb = pad.GetBoundingBox()
            r = max(bb.GetWidth(), bb.GetHeight()) // 2
            if _segseg(a, b, bb.Centre(), bb.Centre()) < \
                    FromMM(w / 2 + 0.13) + r:
                return False
        return True

    def _segseg(p, q, a, b):
        import math as _m

        def d(pt, s1, s2):
            ax, ay, bx, by = s1.x, s1.y, s2.x, s2.y
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            if L2 == 0:
                return _m.hypot(pt.x - ax, pt.y - ay)
            t = max(0.0, min(1.0, ((pt.x - ax) * dx + (pt.y - ay) * dy) / L2))
            return _m.hypot(pt.x - (ax + t * dx), pt.y - (ay + t * dy))
        return min(d(p, a, b), d(q, a, b), d(a, p, q), d(b, p, q))

    def stitch(pad, netname):
        import math as _m
        pos = pad.GetPosition()
        for r in (0.9, 1.2, 1.6, 2.0, 2.5, 3.0):
            for ang in range(0, 360, 30):
                vx = pos.x + FromMM(r * _m.cos(_m.radians(ang)))
                vy = pos.y + FromMM(r * _m.sin(_m.radians(ang)))
                vpos = VECTOR2I(int(vx), int(vy))
                if not clear_at(vpos, netname):
                    continue
                if not seg_clear_for(netname, pos, vpos):
                    continue
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(vpos)
                v.SetDrill(FromMM(0.3))
                v.SetWidth(FromMM(0.6))
                v.SetNet(board.FindNet(netname))
                board.Add(v)
                existing_vias.append(v)
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pos)
                t.SetEnd(vpos)
                t.SetLayer(pcbnew.B_Cu if pad.IsFlipped() else pcbnew.F_Cu)
                t.SetWidth(FromMM(0.3))
                t.SetNet(board.FindNet(netname))
                board.Add(t)
                existing_tracks.append(t)
                placed.append(vpos)
                return True
        print(f"WARN: no stitch spot for {pad.GetParentFootprint().GetReference()}"
              f".{pad.GetNumber()}")
        return False

    for fp in board.GetFootprints():
        for pad in fp.Pads():
            net = pad.GetNetname()
            if net == "GND" and pad.IsFlipped() and \
                    pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                stitch(pad, "GND")
            elif net == "VDD" and not pad.IsFlipped() and \
                    pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                stitch(pad, "VDD")

    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(OUT, board)
    print(f"Finalized {OUT} with zones + stitching")


if __name__ == "__main__":
    if "--final" in sys.argv:
        finalize()
    else:
        main()
