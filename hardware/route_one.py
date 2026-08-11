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

def simplify(path):
    out = [path[0]]
    for k in range(1, len(path) - 1):
        (l0, i0, j0), (l1, i1, j1), (l2, i2, j2) = out[-1], path[k], path[k+1]
        if l0 == l1 == l2 and (i1 - i0, j1 - j0) == (i2 - i1, j2 - j1):
            continue
        out.append(path[k])
    out.append(path[-1])
    return out


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


# ---------------- single-net routing over existing board ----------------
net_spec = {}
hist = {}

for _t in board.GetTracks():
    if _t.GetClass() == "PCB_TRACK":
        soft_mark_seg(LN[_t.GetLayer()], mm(_t.GetStart()), mm(_t.GetEnd()),
                      ToMM(_t.GetWidth()), _t.GetNetname())
    else:
        _p = mm(_t.GetPosition())
        soft_mark_via(_p[0], _p[1], _t.GetNetname())


def cells_near(net, x, y, rad=5):
    out = set()
    for di in range(-rad, rad + 1):
        for dj in range(-rad, rad + 1):
            i, j = gx(x) + di, gy(y) + dj
            if 0 <= i < NX and 0 <= j < NY:
                o = hard[1][i][j]
                if o is None or o == net:
                    out.add((1, i, j))
    return out


def route_one(net, a, b, width=0.2):
    starts = cells_near(net, *a)
    goals = cells_near(net, *b)
    if not starts or not goals:
        print(net, "no start/goal cells")
        return False
    path = astar_pf(net, starts, goals, 1e9, width)
    if path is None:
        print(net, "NO PATH")
        return False
    def near_end(i, j):
        for (ex, ey) in (a, b):
            if math.hypot(wx_(i) - ex, wy(j) - ey) < 0.7:
                return True
        return False
    crossings = sum(1 for (L_, i, j) in path
                    if not near_end(i, j)
                    for n in soft_owners(soft02, L_, i, j) if n != net)
    if crossings:
        owners = {}
        for (L_, i, j) in path:
            if near_end(i, j):
                continue
            for n in soft_owners(soft02, L_, i, j):
                if n != net:
                    owners.setdefault(n, []).append(
                        (round(wx_(i), 2), round(wy(j), 2), "FB"[L_]))
        print(net, "would cross", crossings, "cells; owners:", owners)
        if not (width <= 0.16 and crossings <= 8):
            return False
        print("  slim-track exception: emitting anyway (DRC will verify)")
    emit(path, net, width)
    for endnode, exact in ((path[0], a), (path[-1], b)):
        L_, i, j = endnode
        gp = (wx_(i), wy(j))
        if math.hypot(exact[0] - gp[0], exact[1] - gp[1]) > 0.01:
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(vec(*gp)); t.SetEnd(vec(*exact))
            t.SetLayer(LMAP[L_]); t.SetWidth(FromMM(width))
            t.SetNet(board.FindNet(net))
            board.Add(t)
    print(net, "routed:", len(path), "cells")
    return True


if __name__ == "__main__":
    import json
    jobs = json.loads(sys.argv[1])
    okall = True
    for job in jobs:
        net, a, b = job[0], tuple(job[1]), tuple(job[2])
        w = job[3] if len(job) > 3 else 0.2
        okall &= route_one(net, a, b, w)
    pcbnew.SaveBoard(BOARD_PATH, board)
    print("saved; all ok:", okall)
