"""Hydrology (design section 4.3): lakes, the drainage check, the drainage area the masks read, and the inflow a
child level receives from its parent.

    filled, info = fill_depressions(h, wrap=(False, False), sea_level=None)   # every cell's spill level, exact
    w = lakes(fields, level, threshold_m=..., mode='lake' | 'sediment', parent=(parent_level, parent_fields))
    r = routing_surface(filled)            # filled, tilted across every flat toward its outlet (float32-safe)
    A, iters = route_to_convergence(dev, r, cell, A0=..., A_in=...)    # GPU route_area until converged
    A_in, qs_in = inflow(parent_level, parent_fields, child_level)      # what crosses into a child's window

    stage ops (OPS): 'lakes' (params: mode 'lake' | 'sediment', threshold_m) and 'route' (drainage area to
    convergence). run.py runs both after every level's stages (lakes only on levels a process evolved), so a recipe
    names them only to change their settings (a glacial overdeepening filled with sediment, say).

Lakes. A closed depression deeper than max(1 m, 0.2 % of the main tile's relief) becomes a lake: flat water at its
spill level (`water` = depth, metres; build/water.py makes the lake mesh from it), the bed left as it is. With
mode 'sediment' it is filled to the spill level instead (flat floors; `deposit` records the fill). Shallower pits are
always filled with sediment: they are the solver's rounding, not landforms. A child level keeps its parent's lakes
(a lake whose spill lies outside the child's window is still a lake there) and adds its own.

Drainage area. route_area.glsl iterated on the routing surface (the filled surface with a small tilt across each
lake and flat toward its outlet, so the water crosses lakes) from the fluvial run's last area, until the largest
relative change over 128 iterations is under 1e-4. A child's border cells receive the parent's flow that crosses its
window edge (A_in, m^2; qs_in, m^3/yr): rivers entering the window carry their upstream catchment with them.

Moved from Ekigar's hydrology.py (design section 3; the triage found its fill and routing accurate):
fill_depressions (exact, on the graph of D8 basins; default wrap is now (False, False): the new levels are open
windows), route (D8 / D-infinity / MFD receivers on a filled surface, flats crossed by breadth-first distance),
accumulate (topological waves), horizon_occlusion (radius in metres), box_blur, flat_average, neighbour_table.
Its hydrology() mask set was tied to Ekigar's Heightfield and is replaced by masks.py.
"""
from __future__ import annotations

import heapq
import math

import numpy as np

from ..core import twins as T

F32 = np.float32

# neighbour offsets (di = column, dj = row) and their distances in texels: common.glsl's order (SW S SE W E NW N NE)
NBR = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
DIST = np.array([math.sqrt(2), 1.0, math.sqrt(2), 1.0, 1.0, math.sqrt(2), 1.0, math.sqrt(2)])
# D-infinity's eight facets as (cardinal, diagonal) NBR indices: E+NE, N+NE, N+NW, W+NW, W+SW, S+SW, S+SE, E+SE
DINF_FACETS = [(4, 7), (6, 7), (6, 5), (3, 5), (3, 0), (1, 0), (1, 2), (4, 2)]
NOWRAP = (False, False)


# ============================================================================ moved from Ekigar's hydrology ===

def neighbour_table(ny, nx, wrap=NOWRAP):
    """(8, ny*nx) int32 flat index of each cell's neighbours in NBR order, -1 off a non-periodic edge."""
    idx = np.arange(ny * nx, dtype=np.int32).reshape(ny, nx)
    return np.stack([v.ravel() for v in _neighbour_views(idx, wrap, -1)])


def _padded(a2d, wrap, fill):
    """a2d padded by one texel: wrapped on a periodic axis, `fill` beyond a non-periodic edge."""
    out = np.pad(a2d, 1, mode='constant', constant_values=fill)
    out[1:-1, 1:-1] = a2d
    if wrap[0]:
        out[1:-1, 0] = a2d[:, -1]
        out[1:-1, -1] = a2d[:, 0]
    if wrap[1]:
        out[0, 1:-1] = a2d[-1, :]
        out[-1, 1:-1] = a2d[0, :]
    if wrap[0] and wrap[1]:
        out[0, 0], out[0, -1], out[-1, 0], out[-1, -1] = a2d[-1, -1], a2d[-1, 0], a2d[0, -1], a2d[0, 0]
    else:                                                 # a corner past a non-periodic edge is off the map
        out[0, 0] = out[0, -1] = out[-1, 0] = out[-1, -1] = fill
    return out


def _neighbour_views(a2d, wrap, fill):
    """The eight neighbour arrays of a grid (NBR order) as views of one padded copy: no gathers."""
    ny, nx = a2d.shape
    pd = _padded(a2d, wrap, fill)
    return [pd[1 + dj:1 + dj + ny, 1 + di:1 + di + nx] for di, dj in NBR]


def _steepest(h, nbr, exclude=None, shape=None, wrap=NOWRAP):
    """D8 steepest-descent receiver of every cell (-1 = none lower) and its drop per texel."""
    n = h.size
    h2 = h.reshape(shape)
    best = np.zeros(shape)
    kbest = np.full(shape, -1, dtype=np.int8)
    for k, hn in enumerate(_neighbour_views(h2, wrap, np.inf)):
        s = (h2 - hn) / DIST[k]
        better = s > best
        best[better] = s[better]
        kbest[better] = k
    kb = kbest.ravel()
    rec = np.full(n, -1, dtype=np.int64)
    has = kb >= 0
    cells = np.nonzero(has)[0]
    rec[cells] = nbr[kb[cells], cells]
    if exclude is not None:
        rec[exclude] = -1
    return rec, best.ravel()


def _terminal_of(rec):
    """Each cell's terminal (pit) along its receiver chain, by pointer jumping."""
    n = rec.size
    t = np.where(rec >= 0, rec, np.arange(n))
    while True:
        t2 = t[t]
        if np.array_equal(t2, t):
            return t
        t = t2


def fill_depressions(height, wrap=NOWRAP, sea_level=None):
    """Every cell's spill level (the priority-flood fill), exactly, via the graph of D8 basins: each cell descends
    to a pit; adjacent basins meet at a pass of height max(h_a, h_b); a priority flood over the basins from the
    outlet gives each basin its minimax level; filled = max(h, level). Outlets: an open (non-periodic) edge, the sea
    (cells at or below sea_level), and on a tile periodic on both axes with no sea, the lowest basin. Returns
    (filled (ny, nx) float64, info = {'basins', 'outlet'})."""
    h = np.asarray(height, dtype=np.float64)
    ny, nx = h.shape
    hf = h.ravel()
    n = hf.size
    nbr = neighbour_table(ny, nx, wrap)
    sea = np.zeros(n, dtype=bool) if sea_level is None else hf <= sea_level
    rec, _ = _steepest(hf, nbr, exclude=sea, shape=(ny, nx), wrap=wrap)
    term = _terminal_of(rec)
    open_edge = not (wrap[0] and wrap[1])
    root_cell = None
    if sea.any():
        outlet = 'sea'
    elif open_edge:
        outlet = 'edge'
    else:
        root_cell = int(np.argmin(hf))
        outlet = 'lowest basin'
    labels_raw = term.copy()
    if sea.any():
        labels_raw[sea[term]] = -1                      # everything draining into the sea is the outlet
    if root_cell is not None:
        labels_raw[term == term[root_cell]] = -1
    uniq, lab = np.unique(labels_raw, return_inverse=True)
    lab = lab.astype(np.int64)
    has_out = uniq[0] == -1
    if has_out:
        OUT = 0
        B = len(uniq)
    else:
        OUT = len(uniq)
        B = len(uniq) + 1
    # pass edges between adjacent basins: four directions cover every 8-connected pair once
    ea, eb, ep = [], [], []
    for k in (4, 6, 7, 5):                               # E, N, NE, NW
        idx = nbr[k]
        ok = idx >= 0
        a = np.nonzero(ok)[0]
        b = idx[ok].astype(np.int64)
        diff = lab[a] != lab[b]
        a, b = a[diff], b[diff]
        ea.append(lab[a])
        eb.append(lab[b])
        ep.append(np.maximum(hf[a], hf[b]))
    if open_edge:                                         # an open edge drains off the map at the edge cell's height
        j, i = np.divmod(np.arange(n), nx)
        edge = np.zeros(n, dtype=bool)
        if not wrap[0]:
            edge |= (i == 0) | (i == nx - 1)
        if not wrap[1]:
            edge |= (j == 0) | (j == ny - 1)
        c = np.nonzero(edge & (lab != OUT))[0]
        ea.append(lab[c])
        eb.append(np.full(c.size, OUT, dtype=np.int64))
        ep.append(hf[c])
    ea = np.concatenate(ea) if ea else np.zeros(0, np.int64)
    eb = np.concatenate(eb) if eb else np.zeros(0, np.int64)
    ep = np.concatenate(ep) if ep else np.zeros(0)
    lo, hi = np.minimum(ea, eb), np.maximum(ea, eb)
    key = lo * B + hi
    order = np.lexsort((ep, key))
    key, ep, lo, hi = key[order], ep[order], lo[order], hi[order]
    first = np.ones(key.size, dtype=bool)
    first[1:] = key[1:] != key[:-1]
    lo, hi, ep = lo[first], hi[first], ep[first]
    # priority flood over the basin graph from the outlet: level = minimax pass height
    src = np.concatenate([lo, hi])                       # both directions of every pass, as adjacency lists
    dst = np.concatenate([hi, lo])
    wts = np.concatenate([ep, ep])
    o = np.argsort(src, kind='stable')
    start_l = np.concatenate([[0], np.cumsum(np.bincount(src, minlength=B))]).tolist()
    nb_l = dst[o].tolist()
    pw_l = wts[o].tolist()
    level_l = [np.inf] * B
    level_l[OUT] = -np.inf
    done_l = [False] * B
    heap = [(-np.inf, OUT)]
    while heap:
        lv, u = heapq.heappop(heap)
        if done_l[u]:
            continue
        done_l[u] = True
        for e in range(start_l[u], start_l[u + 1]):
            v = nb_l[e]
            if done_l[v]:
                continue
            nl = pw_l[e] if pw_l[e] > lv else lv
            if nl < level_l[v]:
                level_l[v] = nl
                heapq.heappush(heap, (nl, v))
    level = np.asarray(level_l)
    level[~np.isfinite(level)] = -np.inf               # basins the flood never reached keep their own height
    filled = np.maximum(hf, level[lab])
    return filled.reshape(ny, nx), {'basins': int(B - 1), 'outlet': outlet}


def route(filled, wrap=NOWRAP, sea_level=None, method='d8', exponent=1.1):
    """Receivers of every cell on a filled surface: strictly downhill, and across flats toward the nearest lower
    cell by breadth-first distance. Returns (receivers (8, N) int64 with -1 for none, weights (8, N), terminal
    (N,) bool). 'd8' one receiver; 'dinf' (Tarboton) splits between the two neighbours of the steepest facet;
    'mfd' spreads over every lower neighbour by slope^exponent."""
    W = np.asarray(filled, dtype=np.float64)
    ny, nx = W.shape
    w = W.ravel()
    n = w.size
    nbr = neighbour_table(ny, nx, wrap)
    sea = np.zeros(n, dtype=bool) if sea_level is None else w <= sea_level
    slopes = np.empty((8, n))
    for k, wn in enumerate(_neighbour_views(W, wrap, np.inf)):
        slopes[k] = ((W - wn) / DIST[k]).ravel()          # an off-map neighbour reads +inf: never downhill
    lower = slopes > 0
    has_lower = lower.any(0) & ~sea
    j, i = np.divmod(np.arange(n), nx)
    edge = np.zeros(n, dtype=bool)
    if not wrap[0]:
        edge |= (i == 0) | (i == nx - 1)
    if not wrap[1]:
        edge |= (j == 0) | (j == ny - 1)
    flat = ~has_lower & ~sea
    terminal = sea | (flat & edge)
    if wrap[0] and wrap[1] and not sea.any():
        terminal[int(np.argmin(w))] = True
    flat &= ~terminal
    recv = np.full((8, n), -1, dtype=np.int64)
    wgt = np.zeros((8, n))
    if method == 'd8':
        k = np.argmax(np.where(lower, slopes, -np.inf), axis=0)
        cells = np.nonzero(has_lower)[0]
        recv[0, cells] = nbr[k[cells], cells]
        wgt[0, cells] = 1.0
    elif method == 'mfd':
        s = np.where(lower, slopes, 0.0) ** exponent
        tot = s.sum(0)
        cells = has_lower
        for k in range(8):
            m = cells & lower[k]
            recv[k, m] = nbr[k, m]
            wgt[k, m] = s[k, m] / tot[m]
    elif method == 'dinf':
        big = float(np.nanmax(W)) + 1e9                   # off-map neighbours: far above, never downhill
        views = _neighbour_views(W, wrap, big)
        best_s = np.zeros(n)
        best_k = np.full(n, -1, dtype=np.int64)
        best_r = np.zeros(n)
        quarter = math.pi / 4
        for f, (k1, k2) in enumerate(DINF_FACETS):
            e1 = views[k1].ravel()
            e2 = views[k2].ravel()
            s1 = w - e1
            s2 = e1 - e2
            r = np.arctan2(s2, s1)
            sf = np.hypot(s1, s2)
            lo_ = r < 0
            hi_ = r > quarter
            sf = np.where(lo_, s1, np.where(hi_, (w - e2) / math.sqrt(2.0), sf))
            r = np.clip(r, 0.0, quarter)
            better = sf > best_s
            best_s = np.where(better, sf, best_s)
            best_k = np.where(better, f, best_k)
            best_r = np.where(better, r, best_r)
        cells = np.nonzero((best_k >= 0) & has_lower)[0]
        fk = best_k[cells]
        k1 = np.array([a for a, _ in DINF_FACETS])[fk]
        k2 = np.array([b for _, b in DINF_FACETS])[fk]
        p2 = best_r[cells] / quarter
        recv[0, cells] = nbr[k1, cells]
        wgt[0, cells] = 1.0 - p2
        two = p2 > 0
        recv[1, cells[two]] = nbr[k2[two], cells[two]]
        wgt[1, cells[two]] = p2[two]
        rest = np.nonzero(has_lower & (best_k < 0))[0]
        if rest.size:
            k = np.argmax(np.where(lower[:, rest], slopes[:, rest], -np.inf), axis=0)
            recv[0, rest] = nbr[k, rest]
            wgt[0, rest] = 1.0
    else:
        raise ValueError(f"route: method {method!r} is 'd8', 'dinf' or 'mfd'")
    if flat.any():                                        # flats: breadth-first from the cells that can drain
        frontier = np.nonzero(~flat)[0]
        seen = ~flat
        while frontier.size:
            cand = nbr[:, frontier].astype(np.int64).ravel()
            f = np.tile(frontier, 8)
            ok = cand >= 0
            c, f = cand[ok], f[ok]
            take = ~seen[c] & (w[c] == w[f])
            c, f = c[take], f[take]
            if not c.size:
                break
            c, first = np.unique(c, return_index=True)
            f = f[first]
            seen[c] = True
            recv[0, c] = f
            wgt[0, c] = 1.0
            frontier = c
        terminal |= flat & ~seen
    return recv, wgt, terminal


def accumulate(recv, wgt, terminal, area=None):
    """Flow accumulation over a routing (route()): each cell's own `area` (default 1) plus everything upstream,
    in topological waves. Returns (N,) float64."""
    n = recv.shape[1]
    acc = np.ones(n) if area is None else np.asarray(area, dtype=np.float64).ravel().copy()
    valid = recv >= 0
    src = np.broadcast_to(np.arange(n), recv.shape)[valid]
    dst = recv[valid]
    ww = wgt[valid]
    indeg = np.bincount(dst, minlength=n)
    order = np.argsort(src, kind='stable')
    src, dst, ww = src[order], dst[order], ww[order]
    start = np.searchsorted(src, np.arange(n + 1))
    frontier = np.nonzero(indeg == 0)[0]
    while frontier.size:
        cnt = start[frontier + 1] - start[frontier]
        tot = int(cnt.sum())
        if tot == 0:
            break
        e = np.repeat(start[frontier] - np.cumsum(np.concatenate([[0], cnt[:-1]])), cnt) + np.arange(tot)
        tgt = dst[e]
        flow = np.repeat(acc[frontier], cnt) * ww[e]
        touched, inv = np.unique(tgt, return_inverse=True)
        acc[touched] += np.bincount(inv, weights=flow)
        indeg[touched] -= np.bincount(inv)
        frontier = touched[indeg[touched] == 0]
    return acc


def _shifted(a, dx, dy, wrap):
    """a read at (col + dx, row + dy): wrapping on a periodic axis, holding the edge value on the other, plus a
    validity mask (False where the read fell off a non-periodic edge)."""
    ny, nx = a.shape
    if wrap[0] and wrap[1]:
        return np.roll(a, (-dy, -dx), axis=(0, 1)), None
    ok = None
    out = a
    if dx:
        if wrap[0]:
            out = np.roll(out, -dx, axis=1)
        else:
            idx = np.arange(nx) + dx
            ok = np.broadcast_to(((idx >= 0) & (idx < nx))[None, :], a.shape)
            out = out[:, np.clip(idx, 0, nx - 1)]
    if dy:
        if wrap[1]:
            out = np.roll(out, -dy, axis=0)
        else:
            idx = np.arange(ny) + dy
            oky = np.broadcast_to(((idx >= 0) & (idx < ny))[:, None], a.shape)
            ok = oky if ok is None else (ok & oky)
            out = out[np.clip(idx, 0, ny - 1), :]
    return out, ok


def horizon_occlusion(heights_m, texel_m, radius_m, wrap=NOWRAP, directions=16, steps=20):
    """Ambient occlusion from the horizon: in each of `directions` azimuths the highest elevation angle within
    radius_m, occlusion = mean sin(horizon angle). Returns (ny, nx), 1 = open sky."""
    z = np.asarray(heights_m, dtype=np.float32)
    R = float(radius_m)
    dists = (R / texel_m) * (np.arange(1, steps + 1) / steps) ** 1.6
    dists = np.maximum(dists, np.linspace(1, steps, steps) * 0.5)
    occl = np.zeros_like(z)
    for d in range(directions):
        a = 2 * math.pi * d / directions
        ca, sa = math.cos(a), math.sin(a)
        best = np.zeros_like(z)
        done = set()
        for t in dists:
            dx, dy = int(round(ca * t)), int(round(sa * t))
            if (dx, dy) in done or (dx == 0 and dy == 0):
                continue
            done.add((dx, dy))
            zs, ok = _shifted(z, dx, dy, wrap)
            zs = (zs - z) * np.float32(1.0 / (math.hypot(dx, dy) * texel_m))
            if ok is None:
                np.maximum(best, zs, out=best)
            else:
                best = np.where(ok, np.maximum(best, zs), best)
        occl += best / np.sqrt(1 + best * best)
    return np.clip(1.0 - occl.astype(np.float64) / directions, 0.0, 1.0)


def box_blur(a, radius, wrap=NOWRAP, passes=3):
    """Separable box blur (`passes` times: close to a Gaussian of sigma ~ radius) by running sums."""
    out = np.asarray(a, dtype=np.float64)
    r = int(max(1, radius))
    for _ in range(passes):
        for axis, wr in ((1, wrap[0]), (0, wrap[1])):
            n = out.shape[axis]
            if wr:
                pad = np.concatenate([np.take(out, np.arange(n - r - 1, n), axis=axis), out,
                                      np.take(out, np.arange(0, r), axis=axis)], axis=axis)
            else:
                pad = np.concatenate([np.repeat(np.take(out, [0], axis=axis), r + 1, axis=axis), out,
                                      np.repeat(np.take(out, [n - 1], axis=axis), r, axis=axis)], axis=axis)
            c = np.cumsum(pad, axis=axis)
            hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
            lo = np.take(c, np.arange(0, n), axis=axis)
            out = (hi - lo) / (2 * r + 1)
    return out


FLAT_SLOPE = (0.002, 0.02)         # rise per metre: dead flat below the first, routed ground above the second


def flat_average(values, flat_w, radius, wrap=NOWRAP):
    """`values` averaged over the flat ground around each cell (normalised convolution), mixed in by flat_w."""
    w = np.asarray(flat_w, dtype=np.float64)
    if not (w > 1e-6).any():
        return np.asarray(values, dtype=np.float64)
    num = box_blur(values * w, radius, wrap)
    den = box_blur(w, radius, wrap)
    avg = np.where(den > 1e-9, num / np.maximum(den, 1e-12), values)
    return values + (avg - values) * w


# ======================================================================================= lakes and routing ===

def _label(mask):
    from ..core.metrics import label
    return label(mask)


def depression_threshold(relief_m):
    """The design's depth for a closed depression to count (a lake): max(1 m, 0.2 % of the relief)."""
    return max(1.0, 0.002 * float(relief_m))


def flat_distance(surface, wrap=NOWRAP, sea_level=None):
    """Breadth-first steps (8-connected) across every flat of `surface` (cells with no strictly lower neighbour,
    joined to equal neighbours) from where it drains: a cell with a lower neighbour, an open edge, or the sea.
    0 off the flats."""
    W = np.asarray(surface, np.float64)
    ny, nx = W.shape
    n = W.size
    w = W.ravel()
    nbr = neighbour_table(ny, nx, wrap)
    lower = np.zeros(n, bool)
    for wn in _neighbour_views(W, wrap, np.inf):
        lower |= (W > wn).ravel()
    j, i = np.divmod(np.arange(n), nx)
    seed = lower.copy()
    if not wrap[0]:
        seed |= (i == 0) | (i == nx - 1)
    if not wrap[1]:
        seed |= (j == 0) | (j == ny - 1)
    if sea_level is not None:
        seed |= w <= sea_level
    dist = np.zeros(n)
    seen = seed.copy()
    frontier = np.nonzero(seed)[0]
    step = 0
    while frontier.size:
        step += 1
        cand = nbr[:, frontier].astype(np.int64).ravel()
        f = np.tile(frontier, 8)
        ok = cand >= 0
        c, f = cand[ok], f[ok]
        take = ~seen[c] & (w[c] == w[f])
        c = np.unique(c[take])
        if not c.size:
            break
        seen[c] = True
        dist[c] = step
        frontier = c
    return dist.reshape(ny, nx)


def routing_surface(filled, wrap=NOWRAP, sea_level=None):
    """The surface the drainage area is routed on: the filled surface, tilted across every flat (lakes, filled
    pits, dead-flat ground) by eps per step of its breadth-first distance from the outlet, eps a few float32 steps
    at the surface's height, so a GPU pass in float32 still sees the way down. float32."""
    filled = np.asarray(filled, np.float64)
    top = float(np.max(np.abs(filled))) if filled.size else 0.0
    eps = max(2e-3, 4.0 * float(np.spacing(np.float32(max(top, 1.0)))))
    return (filled + eps * flat_distance(filled, wrap, sea_level)).astype(F32)


def lakes(fields, level, threshold_m, mode='lake', parent=None, sea_level=None, wrap=NOWRAP, band=0, seam_hold=2,
          no_lake=None):
    """Fill a level's closed depressions (module doc), in place. Returns (filled float64, number of lakes).
    parent: (parent Level, parent Fields) to keep the parent's lakes on this level. band: a child level's border band
    in cells: a depression reaching into it is filled with sediment, not water. It is the seam's, not a lake: the band
    holds the parent's smoother channel while the level sharpens its own, so a river crossing the band ponds behind
    it, and the band's pins undo any fill during the run (filled to its spill it is a short flat reach). The seam's
    own seam_hold cells are never filled, so the level still meets its parent exactly there. no_lake: a bool mask
    (the flatten areas): a depression reaching into it fills with sediment, never water."""
    h = np.asarray(fields['h'], np.float64)
    filled, _info = fill_depressions(h, wrap, sea_level)
    depth = filled - h
    lab, n = _label(depth > 1e-4)
    water = np.zeros_like(h)
    nlakes = 0
    if n:
        maxd = np.zeros(n + 1)
        np.maximum.at(maxd, lab.ravel(), depth.ravel())
        big = maxd > threshold_m
        big[0] = False
        if band > 0:
            from ..core import grid as _g
            in_band = _g.edge_distance(h.shape) < band
            touches = np.zeros(n + 1, bool)
            touches[np.unique(lab[in_band & (lab > 0)])] = True
            big &= ~touches
        if no_lake is not None:                          # flatten areas: the API levels them; never a lake
            touches = np.zeros(n + 1, bool)
            touches[np.unique(lab[np.asarray(no_lake, bool) & (lab > 0)])] = True
            big &= ~touches
        lake_cells = big[lab]
        if mode == 'lake':
            water = np.where(lake_cells, depth, 0.0)
            fill_cells = (lab > 0) & ~lake_cells
        else:
            fill_cells = lab > 0
        nlakes = int(big.sum()) if mode == 'lake' else 0
        if band > 0:
            from ..core import grid as _g
            fill_cells &= _g.edge_distance(h.shape) > seam_hold        # the seam's cells stay the parent's
        if fill_cells.any():
            add = np.where(fill_cells, depth, 0.0)
            fields['h'] = (h + add).astype(F32)
            fields['deposit'] = (np.asarray(fields['deposit'], np.float64) + add).astype(F32) \
                if 'deposit' in fields else add.astype(F32)
    if parent is not None:
        water = np.maximum(water, _parent_lake_water(level, np.asarray(fields['h'], np.float64), *parent))
    fields['water'] = water.astype(F32)
    return filled, nlakes


def _parent_lake_water(level, h, plevel, pfields):
    """Water depth on this level under the parent's lakes: each parent lake cell (grown by one cell) is at its lake
    level, and child cells under it lower than that level hold water."""
    if 'water' not in pfields:
        return np.zeros_like(h)
    pw = np.asarray(pfields['water'], np.float64)
    if not (pw > 1e-6).any():
        return np.zeros_like(h)
    ph = np.asarray(pfields['h'], np.float64)
    surf = np.where(pw > 1e-6, ph + pw, -np.inf)
    grown = surf.copy()
    for wn in _neighbour_views(surf, NOWRAP, -np.inf):
        grown = np.maximum(grown, wn)
    i0 = int(round((level.x0 - plevel.x0) / plevel.cell))
    j0 = int(round((level.y0 - plevel.y0) / plevel.cell))
    f = int(round(plevel.cell / level.cell))
    jj = np.clip(j0 + np.arange(level.n) // f, 0, pw.shape[0] - 1)
    ii = np.clip(i0 + np.arange(level.n) // f, 0, pw.shape[1] - 1)
    L = grown[np.ix_(jj, ii)]
    return np.where(np.isfinite(L) & (L > h), L - h, 0.0)


def inflow(plevel, pfields, level, p=1.0, surface=None):
    """(A_in m^2, qs_in m^3/yr) on a child level's grid: the parent's drainage area and sediment flux that cross
    into the child's window, put on the child's edge cells where they enter (each parent cell's inflow shared by the
    child cells of its 2 x 2 block that lie on the window's edge). `surface`: the parent's routing surface (default
    its lake-filled, tilted h)."""
    n = level.n
    A_in = np.zeros((n, n), np.float64)
    qs_in = np.zeros((n, n), np.float64)
    if 'A' not in pfields:
        return A_in.astype(F32), qs_in.astype(F32)
    r_full = np.asarray(surface if surface is not None else
                        routing_surface(fill_depressions(pfields['h'])[0]), np.float64)
    pc = float(plevel.cell)
    NY, NX = r_full.shape
    i0 = int(round((level.x0 - plevel.x0) / pc))
    j0 = int(round((level.y0 - plevel.y0) / pc))
    m = int(round(level.side / pc))
    # only the window's edge matters: work on the window plus two parent cells around it (a neighbour q outside the
    # window needs its own neighbours for its weight sum)
    a0, a1 = max(j0 - 2, 0), min(j0 + m + 2, NY)
    b0, b1 = max(i0 - 2, 0), min(i0 + m + 2, NX)
    r = r_full[a0:a1, b0:b1]
    Ap = np.asarray(pfields['A'], np.float64)[a0:a1, b0:b1]
    qp = (np.asarray(pfields['qs'], np.float64)[a0:a1, b0:b1] if 'qs' in pfields else np.zeros_like(Ap))
    ny, nx = r.shape
    inside = np.zeros((ny, nx), bool)
    inside[j0 - a0:j0 - a0 + m, i0 - b0:i0 - b0 + m] = True
    ws = np.zeros((ny, nx))
    for k, (di, dj) in enumerate(NBR):
        rq, ok = T.shift(r, di, dj, T.BOUND_OPEN, fill=np.inf)
        s = (r - rq) / (DIST[k] * pc)
        ws += np.where(ok & (s > 0), np.power(np.maximum(s, 0.0), p), 0.0)
    inA = np.zeros((ny, nx))
    inQ = np.zeros((ny, nx))
    for k, (di, dj) in enumerate(NBR):
        rq, ok = T.shift(r, di, dj, T.BOUND_OPEN, fill=-np.inf)        # q = c + OFF[k], the would-be upstream
        oq, _ = T.shift(inside, di, dj, T.BOUND_OPEN, fill=True)
        up = ok & inside & ~oq & (rq > r)
        if not up.any():
            continue
        Aq, _ = T.shift(Ap, di, dj, T.BOUND_OPEN)
        qq, _ = T.shift(qp, di, dj, T.BOUND_OPEN)
        wq, _ = T.shift(ws, di, dj, T.BOUND_OPEN, fill=1.0)
        share = np.where(up, np.power(np.maximum((rq - r) / (DIST[k] * pc), 0.0), p) / np.maximum(wq, 1e-30), 0.0)
        inA += Aq * share
        inQ += qq * share
    pj, pi = np.nonzero((inA > 0) | (inQ > 0))
    if not pj.size:
        return A_in.astype(F32), qs_in.astype(F32)
    f = int(round(pc / level.cell))
    # each parent cell's inflow, shared by the child cells of its f x f block on the window's edge
    oy, ox = np.meshgrid(np.arange(f), np.arange(f), indexing='ij')
    cy = ((pj + a0 - j0) * f)[:, None] + oy.ravel()[None, :]
    cx = ((pi + b0 - i0) * f)[:, None] + ox.ravel()[None, :]
    on = ((cy == 0) | (cy == n - 1) | (cx == 0) | (cx == n - 1)) & (cy >= 0) & (cy < n) & (cx >= 0) & (cx < n)
    cnt = on.sum(1)
    keep = cnt > 0
    share_a = np.where(on, (inA[pj, pi] / np.maximum(cnt, 1))[:, None], 0.0)[keep]
    share_q = np.where(on, (inQ[pj, pi] / np.maximum(cnt, 1))[:, None], 0.0)[keep]
    sel = on[keep]
    np.add.at(A_in, (cy[keep][sel], cx[keep][sel]), share_a[sel])
    np.add.at(qs_in, (cy[keep][sel], cx[keep][sel]), share_q[sel])
    return A_in.astype(F32), qs_in.astype(F32)


# ============================================================================== drainage area on the device ===

@T.twin('route_area')
def route_area(s, u):
    from .fluvial import wpow
    h, ws, A0, Ain = s['st'][..., 0], s['wsumT'][..., 0], s['aT'][..., 0], s['pin'][..., 2]
    dx = u['uDx']
    A = dx * dx + Ain
    with np.errstate(over='ignore', invalid='ignore'):        # masked-out cells only (the GPU branches past them)
        for k in range(8):
            hq, ok = T.neighbour(h, k, u['uBound'])
            Aq, _ = T.neighbour(A0, k, u['uBound'])
            wq, _ = T.neighbour(ws, k, u['uBound'])
            up = ok & (hq > h)
            sl = np.where(up, (hq - h) / (T.LEN[k] * dx), F32(1))
            A = np.where(up, A + Aq * (wpow(sl, u['uP']) / np.maximum(wq, F32(1e-30))), A)
    return {'outA': A[..., None]}


def route_to_convergence(dev, surface, cell, A0=None, A_in=None, bound=T.BOUND_OPEN, p=1.0, tol=1e-4, check=128,
                         max_iter=None):
    """Drainage area (m^2, float32 (n, n)) on a fixed surface: route_area iterated from A0 (default one cell's
    area) until the largest relative change over `check` iterations is under tol. Returns (A, iterations)."""
    surface = np.asarray(surface, F32)
    ny, nx = surface.shape
    st = dev.texture(surface)
    W = dev.empty((ny, nx), 1)
    dev.run('flow_weights', {'st': st}, {'outW': W}, {'uDx': cell, 'uP': p, 'uBound': bound})
    z = np.zeros((ny, nx), F32)
    pin = dev.texture(T.rgba(z, z, z if A_in is None else np.asarray(A_in, F32), z))
    a0 = np.full((ny, nx), cell * cell, F32) if A0 is None else np.asarray(A0, F32)
    src, dst = dev.texture(a0), dev.empty((ny, nx), 1)
    max_iter = int(max_iter or 8 * max(ny, nx))
    prev = a0.astype(np.float64)
    it = 0
    while it < max_iter:
        for _ in range(check):
            dev.run('route_area', {'st': st, 'wsumT': W, 'aT': src, 'pin': pin}, {'outA': dst},
                    {'uDx': cell, 'uP': p, 'uBound': bound})
            src, dst = dst, src
        it += check
        cur = dev.read(src)[..., 0].astype(np.float64)
        change = float(np.max(np.abs(cur - prev) / np.maximum(cur, 1e-12)))
        prev = cur
        if change < tol:
            break
    return prev.astype(F32), it


# =================================================================================================== the ops ===

def op_lakes(fields, level, params, seed=0, ctx=None):
    """Stage 'lakes': fill the level's closed depressions now (module doc). params: mode 'lake' | 'sediment',
    threshold_m (default: the design's max(1 m, 0.2 % of relief))."""
    rel = (ctx.shared.get('relief') if ctx is not None else None) or float(np.ptp(np.asarray(fields['h'])))
    thr = float(params.get('threshold_m') or depression_threshold(rel))
    lakes(fields, level, thr, params.get('mode', 'lake'), sea_level=ctx.sea_level if ctx is not None else None)
    if ctx is not None:
        ctx.shared.setdefault('lake_modes', {})[level.index] = params.get('mode', 'lake')
    return fields


def op_route(fields, level, params, seed=0, ctx=None):
    """Stage 'route': the drainage area A to convergence on the lake-filled surface (module doc)."""
    from . import fluvial as FL
    dev = (ctx.device if ctx is not None and ctx.device is not None else FL.device())
    sea = ctx.sea_level if ctx is not None else None
    r = routing_surface(fill_depressions(fields['h'], sea_level=sea)[0], sea_level=sea)
    A_in = ctx.pins['A_in'] if ctx is not None and ctx.pins is not None else None
    A, _it = route_to_convergence(dev, r, level.cell, A0=fields.get('A'), A_in=A_in,
                                  tol=float(params.get('tol', 1e-4)))
    fields['A'] = A
    return fields


OPS = {'lakes': op_lakes, 'route': op_route}
