#!/usr/bin/env python3
"""Negotiated-congestion (rip-up & reroute) router for dc34-sao.

Run with KiCad's bundled python on a freshly generated board.
Hard obstacles: pads, escape stubs/vias, board bounds.
Soft obstacles: other nets' committed tracks — rippable.
"""

import heapq
import math
import sys

import wx
_app = wx.App(redirect=False)

import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

BOARD_PATH = "/Users/woodd/GitHub/dc34-sao/hardware/dc34-sao.kicad_pcb"
STEP = 0.12
CLEAR = 0.15
TRACK_W = 0.2
PWR_W = 0.35
VIA_DIA, VIA_DRILL = 0.6, 0.3
XMIN, XMAX, YMIN, YMAX = 0.6, 57.4, 0.6, 41.4
ORG = 100.0
NX = int((XMAX - XMIN) / STEP) + 1
NY = int((YMAX - YMIN) / STEP) + 1
INFL = CLEAR + TRACK_W / 2
VIA_COST = 28
DIAG = 1.4142
RIP_PENALTY = 25.0     # base soft-cell crossing cost in relaxed mode
MAX_ITER = 500

board = pcbnew.LoadBoard(BOARD_PATH)
F, B = pcbnew.F_Cu, pcbnew.B_Cu
LN = {F: 0, B: 1}
LMAP = {0: F, 1: B}


def mm(v):
    return (round(ToMM(v.x) - ORG, 4), round(ToMM(v.y) - ORG, 4))


def vec(x, y):
    return VECTOR2I(FromMM(ORG + x), FromMM(ORG + y))


def gx(x):
    return int(round((x - XMIN) / STEP))


def gy(y):
    return int(round((y - YMIN) / STEP))


def wx_(ix):
    return XMIN + ix * STEP


def wy(iy):
    return YMIN + iy * STEP


# ---------- hard obstacle grid: None | netname | "*" ----------
hard = [[[None] * NY for _ in range(NX)] for _ in range(2)]


def hard_disc(layer, x, y, r, net):
    i1, i2 = max(0, gx(x - r)), min(NX - 1, gx(x + r))
    j1, j2 = max(0, gy(y - r)), min(NY - 1, gy(y + r))
    for i in range(i1, i2 + 1):
        for j in range(j1, j2 + 1):
            if (wx_(i) - x) ** 2 + (wy(j) - y) ** 2 <= r * r:
                cur = hard[layer][i][j]
                if cur is None:
                    hard[layer][i][j] = net
                elif cur != net:
                    hard[layer][i][j] = "*"


def hard_seg(layer, a, b, r, net):
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    n = max(1, int(L / (STEP / 2)))
    for k in range(n + 1):
        t = k / n
        hard_disc(layer, a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]),
                  r, net)


def hard_rect(layer, x1, y1, x2, y2, margin, net):
    i1, i2 = max(0, gx(x1 - margin)), min(NX - 1, gx(x2 + margin))
    j1, j2 = max(0, gy(y1 - margin)), min(NY - 1, gy(y2 + margin))
    for i in range(i1, i2 + 1):
        for j in range(j1, j2 + 1):
            cur = hard[layer][i][j]
            if cur is None:
                hard[layer][i][j] = net
            elif cur != net:
                hard[layer][i][j] = "*"


# ---------- soft occupancy ----------
# swath grids per entrant width class: a cell in swath02 means "a 0.2mm
# track centered here would violate clearance against the marking net".
soft02 = {}    # cell -> {net: count}   (entrant width 0.2)
soft035 = {}   # cell -> {net: count}   (entrant width 0.35 / vias)
centers = {}   # net -> list of centerline cells
soft_journal = {}   # net -> list of (grid, cell)


def _mark(grid, layer, x, y, r, net, journal):
    i1, i2 = max(0, gx(x - r)), min(NX - 1, gx(x + r))
    j1, j2 = max(0, gy(y - r)), min(NY - 1, gy(y + r))
    for i in range(i1, i2 + 1):
        for j in range(j1, j2 + 1):
            if (wx_(i) - x) ** 2 + (wy(j) - y) ** 2 <= r * r:
                key = (layer, i, j)
                d = grid.setdefault(key, {})
                d[net] = d.get(net, 0) + 1
                journal.append((id(grid), key))


_GRIDS = {}


def soft_mark_seg(layer, a, b, w, net):
    """mark both swath grids + centerline for a segment of width w"""
    journal = soft_journal.setdefault(net, [])
    _GRIDS[id(soft02)] = soft02
    _GRIDS[id(soft035)] = soft035
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    n = max(1, int(L / (STEP / 2)))
    cl = centers.setdefault(net, [])
    for k in range(n + 1):
        t = k / n
        x = a[0] + t * (b[0] - a[0])
        y = a[1] + t * (b[1] - a[1])
        _mark(soft02, layer, x, y, w / 2 + CLEAR + 0.1, net, journal)
        _mark(soft035, layer, x, y, w / 2 + CLEAR + 0.175, net, journal)
        cl.append((layer, gx(x), gy(y)))


def soft_mark_via(x, y, net):
    journal = soft_journal.setdefault(net, [])
    _GRIDS[id(soft02)] = soft02
    _GRIDS[id(soft035)] = soft035
    cl = centers.setdefault(net, [])
    for L_ in (0, 1):
        _mark(soft02, L_, x, y, VIA_DIA / 2 + CLEAR + 0.1, net, journal)
        _mark(soft035, L_, x, y, VIA_DIA / 2 + CLEAR + 0.175, net, journal)
        cl.append((L_, gx(x), gy(y)))


def soft_owners(grid, layer, i, j):
    return grid.get((layer, i, j), {})


def rip(net):
    """remove net's committed copper from board and soft grids"""
    for item in committed_items.pop(net, []):
        board.Remove(item)
    for gid, key in soft_journal.pop(net, []):
        d = _GRIDS[gid].get(key)
        if d and net in d:
            d[net] -= 1
            if d[net] <= 0:
                del d[net]
    centers.pop(net, None)


committed_items = {}   # net -> [board items]


def add_track(a, b, layer, net, width, permanent=False):
    if abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6:
        return
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(vec(*a)); t.SetEnd(vec(*b))
    t.SetLayer(layer); t.SetWidth(FromMM(width))
    t.SetNet(board.FindNet(net))
    board.Add(t)
    if permanent:
        hard_seg(LN[layer], a, b, width / 2 + INFL, net)
    else:
        committed_items.setdefault(net, []).append(t)
        soft_mark_seg(LN[layer], a, b, width, net)


def add_via(x, y, net, permanent=False):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(vec(x, y))
    v.SetDrill(FromMM(VIA_DRILL)); v.SetWidth(FromMM(VIA_DIA))
    v.SetNet(board.FindNet(net))
    board.Add(v)
    if permanent:
        for L_ in (0, 1):
            hard_disc(L_, x, y, VIA_DIA / 2 + INFL, net)
    else:
        committed_items.setdefault(net, []).append(v)
        soft_mark_via(x, y, net)


# ---------- rasterize pads ----------
pads_by_key = {}
pad_net = {}
for fp in board.GetFootprints():
    ref = fp.GetReference()
    for pad in fp.Pads():
        bb = pad.GetBoundingBox()
        x1, y1 = ToMM(bb.GetLeft()) - ORG, ToMM(bb.GetTop()) - ORG
        x2, y2 = ToMM(bb.GetRight()) - ORG, ToMM(bb.GetBottom()) - ORG
        net = pad.GetNetname() or "*"
        onF = pad.IsOnLayer(F)
        onB = pad.IsOnLayer(B)
        if pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH,
                                  pcbnew.PAD_ATTRIB_NPTH):
            onF = onB = True
        if net.startswith("unconnected"):
            net = "*"
        if onF:
            hard_rect(0, x1, y1, x2, y2, INFL, net)
        if onB:
            hard_rect(1, x1, y1, x2, y2, INFL, net)
        pads_by_key.setdefault((ref, pad.GetNumber()), []).append(
            (mm(pad.GetPosition()), onB, fp))
        pad_net[(ref, pad.GetNumber())] = pad.GetNetname()

# ---------- escapes (permanent) ----------
NETS = [
    ("BADGE_SDA", [("U1", "2"), ("J1", "3")], TRACK_W),
    ("BADGE_SCL", [("U1", "3"), ("J1", "4")], TRACK_W),
    ("SAO_GPIO1", [("U1", "38"), ("J1", "5")], TRACK_W),
    ("SAO_GPIO2", [("U1", "39"), ("J1", "6")], TRACK_W),
    ("SWCLK", [("U1", "24"), ("TP1", "1")], TRACK_W),
    ("SWDIO", [("U1", "25"), ("TP2", "1")], TRACK_W),
    ("BTN_CH_DOWN", [("U1", "15"), ("SW1", "1")], TRACK_W),
    ("BTN_CH_UP", [("U1", "16"), ("SW2", "1")], TRACK_W),
    ("BTN_MODE", [("U1", "17"), ("SW3", "1")], TRACK_W),
    ("LED_PWR", [("U1", "27"), ("R3", "1")], TRACK_W),
    ("LED_A", [("R3", "2"), ("LED1", "2")], TRACK_W),
    ("USB_DP", [("U1", "47"), ("R7", "2")], TRACK_W),
    ("USB_DM", [("U1", "46"), ("R8", "2")], TRACK_W),
    ("BOOTSEL_SW", [("R2", "2"), ("SW4", "1")], TRACK_W),
    ("VBUS", [("J2", "A4"), ("U3", "1"), ("U3", "3"), ("C17", "1"),
              ("J2", "B4"), ("R5", "1"), ("Q1", "1")], PWR_W),
    ("VSAO", [("J1", "1"), ("Q1", "3"), ("C19", "1")], PWR_W),
    ("V33U", [("U3", "5"), ("C18", "1"), ("D1", "2")], PWR_W),
    ("USB_C_DM", [("J2", "B7"), ("R8", "1"), ("J2", "A7")], TRACK_W),
    ("USB_C_DP", [("J2", "A6"), ("J2", "B6"), ("R7", "1")], TRACK_W),
    ("CC1", [("J2", "A5"), ("R9", "1")], TRACK_W),
    ("CC2", [("J2", "B5"), ("R10", "1")], TRACK_W),
    ("XIN", [("U1", "20"), ("Y1", "1"), ("C1", "1")], TRACK_W),
    ("XOUT", [("U1", "21"), ("R1", "1")], TRACK_W),
    ("XTAL3", [("R1", "2"), ("Y1", "3"), ("C2", "1")], TRACK_W),
    ("QSPI_SS", [("U1", "56"), ("U2", "1"), ("R2", "1")], TRACK_W),
    ("QSPI_SD1", [("U1", "55"), ("U2", "2")], TRACK_W),
    ("QSPI_SD2", [("U1", "54"), ("U2", "3")], TRACK_W),
    ("QSPI_SD0", [("U1", "53"), ("U2", "5")], TRACK_W),
    ("QSPI_SCLK", [("U1", "52"), ("U2", "6")], TRACK_W),
    ("QSPI_SD3", [("U1", "51"), ("U2", "7")], TRACK_W),
    ("DVDD", [("U1", "45"), ("U1", "23"), ("U1", "50"), ("C14", "1"),
              ("C12", "1"), ("C13", "1")], PWR_W),
    ("TFT_SCK", [("U1", "4"), ("J3", "4")], TRACK_W),
    ("TFT_MOSI", [("U1", "5"), ("J3", "3")], TRACK_W),
    ("TFT_DC", [("U1", "6"), ("J3", "5")], TRACK_W),
    ("TFT_CS", [("U1", "7"), ("J3", "7")], TRACK_W),
    ("TFT_RST", [("U1", "8"), ("J3", "6")], TRACK_W),
    ("TFT_BL", [("U1", "9"), ("Q2", "1"), ("R11", "1")], TRACK_W),
    ("TFT_LEDK", [("Q2", "3"), ("J3", "11")], TRACK_W),
    ("TFT_LEDA", [("R6", "2"), ("J3", "12")], TRACK_W),
    ("VDD", [("Q1", "2"), ("D1", "1"), ("U2", "8"), ("C16", "1"),
             ("U1", "1"), ("U1", "10"), ("U1", "22"), ("U1", "33"),
             ("U1", "42"), ("U1", "49"), ("U1", "43"), ("U1", "44"),
             ("U1", "48"), ("C3", "1"), ("C4", "1"), ("C5", "1"),
             ("C6", "1"), ("C7", "1"), ("C8", "1"), ("C9", "1"), ("C10", "1"),
             ("C11", "1"), ("C15", "1"), ("C20", "1"), ("C21", "1"),
             ("R6", "1"), ("TP4", "1"), ("J3", "10")], PWR_W),
]
ROUTABLE = {e[0] for e in NETS}

escape_nodes = {}   # (ref, num) -> [(node, exactpoint)]


def _escape_end(ref, num, p, fp):
    if ref == "U1" and num == "23":
        return (p[0], p[1] - 1.05)
    if ref == "U1" and num == "19":
        return (p[0], p[1] + 1.9)
    if ref == "U1":
        cx, cy = mm(fp.GetPosition())
        dx, dy = p[0] - cx, p[1] - cy
        if abs(dx) > abs(dy):
            return (p[0] + (1.15 if dx > 0 else -1.15), p[1])
        return (p[0], p[1] + (1.15 if dy > 0 else -1.15))
    if ref == "J2":
        return (p[0], p[1] - 1.7)
    if ref == "J3":
        length = {"8": 3.0, "13": 3.0, "10": 3.6}.get(num, 2.4)
        return (p[0] - length, p[1])
    return None


for (ref, num), entries in sorted(pads_by_key.items()):
    if ref not in ("U1", "J2", "J3"):
        continue
    for (p, onB, fp) in entries:
        net = pad_net.get((ref, num)) or ""
        if net not in ROUTABLE:
            continue
        end = _escape_end(ref, num, p, fp)
        if end is None:
            continue
        layer = B if onB else F
        node = (LN[layer], gx(end[0]), gy(end[1]))
        snapped = (wx_(node[1]), wy(node[2]))
        add_track(p, snapped, layer, net, TRACK_W, permanent=True)
        escape_nodes.setdefault((ref, num), []).append((node, snapped))


def pad_nodes(ref, num, net):
    if (ref, num) in escape_nodes:
        return escape_nodes[(ref, num)]
    out = []
    for (p, onB, fp) in pads_by_key[(ref, num)]:
        Ls = [0, 1] if ref == "J1" else ([1] if onB else [0])
        for L_ in Ls:
            i, j = gx(p[0]), gy(p[1])
            for di in range(-4, 5):
                for dj in range(-4, 5):
                    ii, jj = i + di, j + dj
                    if 0 <= ii < NX and 0 <= jj < NY and \
                            hard[L_][ii][jj] in (None, net):
                        out.append(((L_, ii, jj), p))
    return out


# ---------- A* with optional soft-crossing ----------
def astar(net, starts, goals, relaxed):
    def hard_ok(L_, i, j):
        o = hard[L_][i][j]
        return o is None or o == net

    def soft_block(L_, i, j):
        return any(n != net for n in soft_owners(L_, i, j))

    def passable(L_, i, j):
        if not hard_ok(L_, i, j):
            return False
        if soft_block(L_, i, j):
            return relaxed   # allowed only in relaxed mode (with penalty)
        return True

    def via_ok(i, j):
        rad = int(round((VIA_DIA / 2 + CLEAR) / STEP))
        for di in range(-rad, rad + 1):
            for dj in range(-rad, rad + 1):
                if di * di + dj * dj > rad * rad:
                    continue
                ii, jj = i + di, j + dj
                if not (0 <= ii < NX and 0 <= jj < NY):
                    return False
                for L_ in (0, 1):
                    if not hard_ok(L_, ii, jj):
                        return False
                    if soft_block(L_, ii, jj) and not relaxed:
                        return False
        return True

    goalset = set(goals)
    glist = list(goals)

    def h(n):
        _, i, j = n
        return min(max(abs(i - gi), abs(j - gj)) +
                   0.414 * min(abs(i - gi), abs(j - gj))
                   for (_, gi, gj) in glist) * 1.45

    openq = []
    g = {}
    came = {}
    for s in starts:
        g[s] = 0.0
        heapq.heappush(openq, (h(s), 0.0, s, None))
    visited = set()
    budget = 140000
    while openq:
        budget -= 1
        if budget <= 0:
            return None
        f, gc, node, parent = heapq.heappop(openq)
        if node in visited:
            continue
        visited.add(node)
        came[node] = parent
        if node in goalset:
            path = [node]
            while came[path[-1]] is not None:
                path.append(came[path[-1]])
            return path[::-1]
        L_, i, j = node
        for di, dj, cost in ((1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1),
                             (1, 1, DIAG), (1, -1, DIAG), (-1, 1, DIAG),
                             (-1, -1, DIAG)):
            ii, jj = i + di, j + dj
            if not (0 <= ii < NX and 0 <= jj < NY):
                continue
            if not passable(L_, ii, jj):
                continue
            if di and dj and not (passable(L_, i, jj) and
                                  passable(L_, ii, j)):
                continue
            step_cost = cost
            if soft_block(L_, ii, jj):
                # history cost: much pricier to rip frequently-ripped nets
                hist = max((rips.get(n, 0) for n in
                            soft_owners(L_, ii, jj) if n != net), default=0)
                step_cost += RIP_PENALTY + 12.0 * hist
            hug = 0.0
            for hi, hj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                oi, oj = ii + hi, jj + hj
                if not (0 <= oi < NX and 0 <= oj < NY) or \
                        not hard_ok(L_, oi, oj):
                    hug = 0.4
                    break
            nn = (L_, ii, jj)
            ng = gc + step_cost + hug
            if nn not in g or ng < g[nn] - 1e-9:
                g[nn] = ng
                heapq.heappush(openq, (ng + h(nn), ng, nn, node))
        if via_ok(i, j):
            nn = (1 - L_, i, j)
            ng = gc + VIA_COST
            if nn not in g or ng < g[nn] - 1e-9:
                g[nn] = ng
                heapq.heappush(openq, (ng + h(nn), ng, nn, node))
    return None


def simplify(path):
    out = [path[0]]
    for k in range(1, len(path) - 1):
        (l0, i0, j0), (l1, i1, j1), (l2, i2, j2) = out[-1], path[k], path[k+1]
        if l0 == l1 == l2 and (i1 - i0, j1 - j0) == (i2 - i1, j2 - j1):
            continue
        out.append(path[k])
    out.append(path[-1])
    return out


def rip_set_for(path, net):
    victims = set()

    def collect(L_, i, j):
        for n in soft_owners(L_, i, j):
            if n != net:
                victims.add(n)

    prev = None
    rad = int(round((VIA_DIA / 2 + CLEAR) / STEP))
    for node in path:
        (L_, i, j) = node
        collect(L_, i, j)
        # corner-support cells only for the diagonal step actually taken
        if prev is not None and prev[0] == L_:
            pi, pj = prev[1], prev[2]
            if i != pi and j != pj:
                collect(L_, pi, j)
                collect(L_, i, pj)
        # via disc owners on both layers at layer transitions
        if prev is not None and prev[0] != L_:
            for di in range(-rad, rad + 1):
                for dj in range(-rad, rad + 1):
                    if di * di + dj * dj > rad * rad:
                        continue
                    ii, jj = i + di, j + dj
                    if 0 <= ii < NX and 0 <= jj < NY:
                        collect(0, ii, jj)
                        collect(1, ii, jj)
        prev = node
    return victims


def emit(path, net, width):
    path = simplify(path)
    prev = path[0]
    for node in path[1:]:
        (l0, i0, j0), (l1, i1, j1) = prev, node
        p0 = (wx_(i0), wy(j0))
        p1 = (wx_(i1), wy(j1))
        if l0 != l1:
            add_via(*p0, net)
        else:
            add_track(p0, p1, LMAP[l0], net, width)
        prev = node


# tie duplicate button pads
for sw in ("SW1", "SW2", "SW3", "SW4"):
    for num in ("1", "2"):
        entries = pads_by_key[(sw, num)]
        if len(entries) == 2:
            (pa, onB, _), (pb, _, _) = entries
            add_track(pa, pb, B if onB else F, pad_net[(sw, num)], TRACK_W,
                      permanent=True)


# ---------- PathFinder global negotiation ----------
net_spec = {e[0]: e for e in NETS}
hist = {}          # cell -> accumulated history penalty
PASSES = 60

def route_net(net, pres_fac):
    name, pins, width = net_spec[net]
    rip(net)
    tree = []
    first = pad_nodes(*pins[0], net)
    if not first:
        return [(net, pins[0], "no start")]
    tree.extend(n for n, _ in first)
    exact = {n: e for n, e in first}
    fails = []
    for term in pins[1:]:
        tn = pad_nodes(*term, net)
        if not tn:
            fails.append((net, term, "no goal"))
            continue
        exact.update({n: e for n, e in tn})
        goals = set(n for n, _ in tn)
        path = astar_pf(net, set(tree), goals, pres_fac, width)
        if path is None:
            fails.append((net, term, "no path"))
            continue
        emit(path, net, width)
        for endnode in (path[0], path[-1]):
            if endnode in exact:
                _, i, j = endnode
                gp = (wx_(i), wy(j))
                e = exact[endnode]
                if math.hypot(e[0] - gp[0], e[1] - gp[1]) > 0.01:
                    add_track(gp, e, LMAP[endnode[0]], net, width)
        tree.extend(n for n, _ in tn)
        tree.extend(path)
    return fails


def astar_pf(net, starts, goals, pres_fac, width=TRACK_W):
    grid = soft02 if width <= 0.25 else soft035

    def hard_ok(L_, i, j):
        o = hard[L_][i][j]
        return o is None or o == net

    def share_cost(L_, i, j):
        others = sum(1 for n in soft_owners(grid, L_, i, j) if n != net)
        c = 0.0
        if others:
            c += pres_fac * others
        c += hist.get((L_, i, j), 0.0)
        return c

    def via_ok(i, j):
        rad = int(round((VIA_DIA / 2 + CLEAR) / STEP))
        for di in range(-rad, rad + 1):
            for dj in range(-rad, rad + 1):
                if di * di + dj * dj > rad * rad:
                    continue
                ii, jj = i + di, j + dj
                if not (0 <= ii < NX and 0 <= jj < NY):
                    return False
                if not (hard_ok(0, ii, jj) and hard_ok(1, ii, jj)):
                    return False
        return True

    glist = list(goals)
    goalset = set(goals)

    def h(n):
        _, i, j = n
        return min(max(abs(i - gi), abs(j - gj)) +
                   0.414 * min(abs(i - gi), abs(j - gj))
                   for (_, gi, gj) in glist) * 1.45

    openq = []
    g = {}
    came = {}
    for s in starts:
        g[s] = 0.0
        heapq.heappush(openq, (h(s), 0.0, s, None))
    visited = set()
    budget = 140000
    while openq:
        budget -= 1
        if budget <= 0:
            return None
        f, gc, node, parent = heapq.heappop(openq)
        if node in visited:
            continue
        visited.add(node)
        came[node] = parent
        if node in goalset:
            path = [node]
            while came[path[-1]] is not None:
                path.append(came[path[-1]])
            return path[::-1]
        L_, i, j = node
        for di, dj, cost in ((1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1),
                             (1, 1, DIAG), (1, -1, DIAG), (-1, 1, DIAG),
                             (-1, -1, DIAG)):
            ii, jj = i + di, j + dj
            if not (0 <= ii < NX and 0 <= jj < NY):
                continue
            if not hard_ok(L_, ii, jj):
                continue
            if di and dj and not (hard_ok(L_, i, jj) and hard_ok(L_, ii, j)):
                continue
            extra = share_cost(L_, ii, jj)
            if di and dj:
                extra += 0.5 * (share_cost(L_, i, jj) + share_cost(L_, ii, j))
            nn = (L_, ii, jj)
            ng = gc + cost + extra
            if nn not in g or ng < g[nn] - 1e-9:
                g[nn] = ng
                heapq.heappush(openq, (ng + h(nn), ng, nn, node))
        if via_ok(i, j):
            extra = 0.0
            for L2 in (0, 1):
                o2 = sum(1 for n in soft_owners(soft035, L2, i, j)
                         if n != net)
                extra += pres_fac * o2 + hist.get((L2, i, j), 0.0)
            nn = (1 - L_, i, j)
            ng = gc + VIA_COST + extra
            if nn not in g or ng < g[nn] - 1e-9:
                g[nn] = ng
                heapq.heappush(openq, (ng + h(nn), ng, nn, node))
    return None


# tie duplicate button pads (permanent)
for sw in ("SW1", "SW2", "SW3", "SW4"):
    for num in ("1", "2"):
        entries = pads_by_key[(sw, num)]
        if len(entries) == 2:
            (pa, onB, _), (pb, _, _) = entries
            add_track(pa, pb, B if onB else F, pad_net[(sw, num)], TRACK_W,
                      permanent=True)

order = [e[0] for e in NETS]
final_fails = []
dirty = set(order)
for p in range(PASSES):
    pres = 1.5 * (1.35 ** p)
    fails = []
    import random
    rnd = random.Random(p)
    work = [n for n in order if n in dirty]
    rnd.shuffle(work)
    for net in work:
        fails.extend(route_net(net, pres))
    over = set()
    over_nets = set()
    for netname, cl in centers.items():
        w = net_spec[netname][2]
        grid = soft02 if w <= 0.25 else soft035
        for cell in cl:
            others = [n for n in soft_owners(grid, *cell) if n != netname]
            if others:
                over.add(cell)
                over_nets.add(netname)
                over_nets.update(others)
    dirty = set()
    for key in over:
        hist[key] = hist.get(key, 0.0) + 1.0
    dirty |= over_nets
    for f in fails:
        dirty.add(f[0])
    print(f"pass {p}: pres={pres:.1f} overused={len(over)} "
          f"fails={len(fails)} dirty={len(dirty)}", flush=True)
    if not over and not fails:
        final_fails = []
        break
    final_fails = fails

if final_fails:
    print("FAILS:", final_fails)
over = set()
for netname, cl in centers.items():
    w = net_spec[netname][2]
    grid = soft02 if w <= 0.25 else soft035
    for cell in cl:
        if any(n != netname for n in soft_owners(grid, *cell)):
            over.add(cell)
print("final overused cells:", len(over))
if not over and not final_fails:
    print("ALL NETS ROUTED CLEAN")
pcbnew.SaveBoard(BOARD_PATH, board)
print("saved:", len(board.GetTracks()), "track items")
