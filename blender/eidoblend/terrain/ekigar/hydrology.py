"""The plan's tier-B masks (TERRAIN_GENERATOR_PLAN.md sections 5, 6 and 14) over a finished height grid, in numpy:
depression filling and lake levels, flow routing and accumulation (D8, D-infinity or multiple-flow-direction), and
the masks the plan derives from them (flow accumulation, channels, lakes, wetness / moisture, deposition, horizon
occlusion, vegetation density). Ekigar lists these as its own remaining gaps (docs/STATUS.md: "global flow direction/
accumulation, routed river networks and priority-flood water levels"); the plan specifies them, and this is that
specification built for the port, not a copy of Ekigar code.

    h = hydrology(hf)                         # or hf.hydrology(): cached on the Heightfield
    h['accumulation'], h['channels'], h['lake'], h['wetness'], h['moisture'], h['deposition'], h['occlusion'],
    h['vegetation']                           # (N, N) masks in 0..1
    h['filled'], h['lakeDepth_m'], h['catchment_m2'], h['area_cells'], h['terminal']      # raw arrays

How it works, so its numbers can be trusted:
- fill_depressions: every cell's lowest possible spill level, computed exactly on the graph of D8 basins (each cell
  descends to a pit; adjacent basins meet at a pass of height max(h_a, h_b); a priority flood over the basins from
  the outlet gives each basin its minimax level; filled = max(h, level)). That is the priority-flood result, at the
  cost of a flood over basins instead of cells. Outlets: an open (non-periodic) edge, the sea (cells at or below
  sea_level), and on a tile periodic on both axes with no sea, the lowest basin.
- flow routing on the filled surface (D8, Tarboton's D-infinity or multiple-flow-direction): strictly downhill
  everywhere, and across flats and lake surfaces toward the spill by breadth-first distance, so the graph is acyclic
  and every cell's water reaches exactly one terminal cell.
  Accumulation runs in topological waves (vectorised); the plan's conservation check (section 14) holds:
  the terminals hold exactly the cell count.
- on dead-flat ground that walk is arbitrary (straight hatching, angular mosaics), so the masks built on the routed
  area (accumulation, wetness, moisture, deposition) read it averaged over the surrounding flat there
  (flat_average), and channels stay off flats; the raw arrays keep the routed values.
"""
from __future__ import annotations

import heapq
import math

import numpy as np

# neighbour offsets (di = column, dj = row) and their distances in texels
NBR = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
DIST = np.array([math.sqrt(2), 1.0, math.sqrt(2), 1.0, 1.0, math.sqrt(2), 1.0, math.sqrt(2)])
# D-infinity's eight facets as (cardinal, diagonal) NBR indices: E+NE, N+NE, N+NW, W+NW, W+SW, S+SW, S+SE, E+SE
DINF_FACETS = [(4, 7), (6, 7), (6, 5), (3, 5), (3, 0), (1, 0), (1, 2), (4, 2)]


def neighbour_table(ny, nx, wrap=(True, True)):
    """(8, ny*nx) int32 flat index of each cell's neighbours in NBR order, -1 off a non-periodic edge (views of one
    padded index grid, stacked)."""
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


def _steepest(h, nbr, exclude=None, shape=None, wrap=(True, True)):
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


def fill_depressions(height, wrap=(True, True), sea_level=None):
    """Every cell's spill level (the priority-flood fill), exactly, via the graph of D8 basins. Returns
    (filled (ny, nx), info) with info = {'basins', 'outlet': how the outlet was chosen}."""
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


def route(filled, wrap=(True, True), sea_level=None, method='d8', exponent=1.1):
    """Receivers of every cell on a filled surface: strictly downhill, and across flats toward the nearest lower
    cell by breadth-first distance. Returns (receivers (8, N) int64 with -1 for none, weights (8, N), terminal
    (N,) bool). D8 gives each cell one receiver; 'dinf' (Tarboton) splits between the two neighbours of the
    steepest facet, free of D8's eight-direction bias; 'mfd' spreads over every lower neighbour by slope^exponent."""
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
        # Tarboton's D-infinity: the steepest of the eight triangular facets around the cell (each a cardinal
        # neighbour e1 and the diagonal e2 beside it), its flow split between e1 and e2 by the angle of the facet's
        # slope. Both receivers are strictly lower whenever the split is not clamped, so the routing stays acyclic.
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
        # a cell with a lower neighbour but no downhill facet (all its lower neighbours behind higher ones) falls
        # back to its steepest single receiver
        rest = np.nonzero(has_lower & (best_k < 0))[0]
        if rest.size:
            k = np.argmax(np.where(lower[:, rest], slopes[:, rest], -np.inf), axis=0)
            recv[0, rest] = nbr[k, rest]
            wgt[0, rest] = 1.0
    else:
        raise ValueError(f"route: method {method!r} is 'd8', 'dinf' or 'mfd'")
    # flats (lake surfaces, plateaus): breadth-first from the cells that can drain, over equal heights
    if flat.any():
        frontier = np.nonzero(~flat)[0]
        seen = ~flat
        while frontier.size:
            cand = nbr[:, frontier].astype(np.int64).ravel()          # all eight directions at once (k-major)
            f = np.tile(frontier, 8)
            ok = cand >= 0
            c, f = cand[ok], f[ok]
            take = ~seen[c] & (w[c] == w[f])
            c, f = c[take], f[take]
            if not c.size:
                break
            c, first = np.unique(c, return_index=True)               # each newly reached cell once, first finder
            f = f[first]
            seen[c] = True
            recv[0, c] = f
            wgt[0, c] = 1.0
            frontier = c
        # flats with no way out at their own height (should not remain after a fill) become terminals
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
    # CSR of each cell's outgoing edges
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
        # sized by the wave, not the grid: a long river is thousands of small waves
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
        return np.roll(a, (-dy, -dx), axis=(0, 1)), None            # one copy for both axes
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


def horizon_occlusion(heights_m, texel_m, wrap=(True, True), directions=16, radius_m=None, steps=20):
    """Ambient occlusion from the horizon: in each of `directions` azimuths the highest elevation angle within
    radius_m (default 6 % of the tile), occlusion = mean sin(horizon angle). Returns (ny, nx), 1 = open sky.
    Each march step reads the grid at a whole-texel offset (a shift, not a gather)."""
    z = np.asarray(heights_m, dtype=np.float32)
    ny, nx = z.shape
    R = radius_m if radius_m is not None else 0.06 * nx * texel_m
    dists = (R / texel_m) * (np.arange(1, steps + 1) / steps) ** 1.6       # texels, denser near the cell
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
            zs -= z
            zs *= np.float32(1.0 / (math.hypot(dx, dy) * texel_m))
            if ok is None:
                np.maximum(best, zs, out=best)
            else:
                best = np.where(ok, np.maximum(best, zs), best)
        occl += best / np.sqrt(1 + best * best)
    return np.clip(1.0 - occl.astype(np.float64) / directions, 0.0, 1.0)


def box_blur(a, radius, wrap=(True, True), passes=3):
    """Separable box blur (`passes` times: close to a Gaussian of sigma ~ radius) by running sums, O(N) whatever the
    radius; wraps on a periodic axis, holds the edge on the other."""
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


def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


FLAT_SLOPE = (0.002, 0.02)         # rise per metre: dead flat below the first, routed ground above the second


def flat_average(values, flat_w, radius, wrap=(True, True)):
    """`values` averaged over the flat ground around each cell (normalised convolution: box blurs of values * w and
    of w, w = flat_w), mixed in by flat_w. On dead-flat ground the routing is a breadth-first walk to the spill, so
    the accumulation there is the walk's pattern (straight hatching, angular mosaics), not the ground's; masks read
    this average there instead. Where flat_w is 0 the values are untouched."""
    w = np.asarray(flat_w, dtype=np.float64)
    if not (w > 1e-6).any():
        return np.asarray(values, dtype=np.float64)
    num = box_blur(values * w, radius, wrap)
    den = box_blur(w, radius, wrap)
    avg = np.where(den > 1e-9, num / np.maximum(den, 1e-12), values)
    return values + (avg - values) * w


def hydrology(hf, method='mfd', sea_level=None, occlusion=True, channel_area=0.004, wetness_range=(2.0, 16.0),
              grass_line=0.62, exponent=1.1, lake_depth_m=1.0, tree_slope=(0.80, 0.97), channel_method='dinf',
              flat_radius=0.03):
    """The tier-B mask set of a Heightfield (see the module doc).

    sea_level     a field height: cells at or below it are sea (an outlet)
    method        the routing behind wetness and deposition: 'mfd' (default, spreads over every lower neighbour, the
                  usual choice for wetness), 'dinf' or 'd8'
    channel_method  the routing behind the accumulation and channel masks: 'dinf' (default: Tarboton's
                  D-infinity, narrow channels without D8's eight-spoke bias, which on a smooth cone draws eight
                  straight rays) or 'd8'
    channel_area  the catchment, as a fraction of the tile, at which a channel is fully on (it fades in from a
                  quarter of that)
    lake_depth_m  the water depth at which the lake mask is fully on (shallower ponds fade in)
    grass_line    the tree line, in normalised height (GetTreesAmount's GRASS_HEIGHT, which is absolute in its demo)
    tree_slope    the band of the surface normal's up component over which trees thin out; the demo's (0.95, 1.0)
                  keeps them under 18 degrees, which suits its gentle terrain and strips a mountain bare
    flat_radius   on dead-flat ground (slope under FLAT_SLOPE) the routing is a breadth-first walk to the spill, so
                  the accumulation, wetness, moisture and deposition masks read the routed area averaged over the
                  flat around each cell, this fraction of the tile out (flat_average), instead of the walk's
                  hatching; channels stay off flats altogether
    The accumulation, channel and wetness masks treat lakes as water (accumulation and channels 0, wetness 1); the
    raw arrays (area_cells, catchment_m2) keep the routed values everywhere."""
    wrap = (hf.tile.x > 0, hf.tile.y > 0)
    h = hf.height
    ny, nx = h.shape
    texel = hf.world_size / nx
    filled, info = fill_depressions(h, wrap, sea_level)
    recv, wgt, term = route(filled, wrap, sea_level, channel_method, exponent)
    A8 = accumulate(recv, wgt, term).reshape(ny, nx)
    if method == channel_method:
        A = A8
    else:
        recv, wgt, term = route(filled, wrap, sea_level, method, exponent)
        A = accumulate(recv, wgt, term).reshape(ny, nx)
    N = float(h.size)
    m = hf.masks()
    slope_m = np.hypot(*np.gradient(hf.heights_m, texel))                 # rise per metre
    depth_m = (filled - h) * hf.metres_per_unit
    lake = _smooth(0.0, lake_depth_m, depth_m) * (depth_m > 1e-9)
    if sea_level is not None:
        lake = np.maximum(lake, (h <= sea_level).astype(np.float64))
    land = 1.0 - lake
    # on dead-flat ground the route is a breadth-first walk to the spill, straight and arbitrary: no channel there,
    # and the area-based masks take the routed area averaged over the flat around them (in log space, so one long
    # walk line does not flood its whole flat)
    routed_w = _smooth(FLAT_SLOPE[0], FLAT_SLOPE[1], slope_m)
    flat_w = 1.0 - routed_w
    flat_r = max(2, int(round(flat_radius * nx)))
    accum = flat_average(np.log1p(A8), flat_w, flat_r, wrap) / np.log1p(N) * land
    channels = _smooth(0.25, 1.0, A8 / (channel_area * N)) * land * routed_w
    lnA = flat_average(np.log(A), flat_w, flat_r, wrap)
    accum_m = flat_average(np.log1p(A), flat_w, flat_r, wrap) / np.log1p(N)
    twi = lnA + np.log(texel) - np.log(np.maximum(slope_m, 1e-3))          # topographic wetness index
    wet = np.maximum(np.clip((twi - wetness_range[0]) / (wetness_range[1] - wetness_range[0]), 0.0, 1.0), lake)
    # moisture: wetness, raised near water (a blurred lake mask: about 2 % of the tile out from the shore)
    near = np.clip(box_blur(lake, max(1, int(0.02 * nx)), wrap) * 2.0, 0.0, 1.0)
    moisture = np.maximum(wet, near)
    # deposition: where a large upstream area arrives on gentle, concave ground (the plan's flow + concavity)
    gentle = 1.0 - _smooth(0.15, 0.6, slope_m)
    deposition = (np.clip(accum_m ** 1.5 * 1.6, 0.0, 1.0) * gentle * np.clip(0.3 + m['concave'] * 1.5, 0.0, 1.0)
                  * land)
    out = {'accumulation': accum, 'channels': channels, 'lake': lake, 'wetness': wet, 'moisture': moisture,
           'deposition': deposition,
           'filled': filled, 'lakeDepth_m': depth_m, 'catchment_m2': A8 * texel * texel, 'area_cells': A8,
           'area_cells_spread': A, 'terminal': term.reshape(ny, nx), 'info': info}
    if occlusion:
        occ = horizon_occlusion(hf.heights_m, texel, wrap)
        out['occlusion'] = occ
        lo, hi = float(h.min()), float(h.max())
        hn = (h - lo) / max(hi - lo, 1e-9)
        normal_y = 1.0 / np.sqrt(1.0 + slope_m * slope_m)
        # GetTreesAmount's four terms (phacelle_bufferA_erosion.glsl:208), with its absolute GRASS_HEIGHT band moved
        # to normalised height and the horizon occlusion standing in for its erosion-delta occlusion: under the tree
        # line, out of deep occlusion, on gentle ground, off the creases of the ridge channel; then wetter is denser
        ridge = np.asarray(hf.aux)
        veg = (_smooth(grass_line + 0.05, grass_line + 0.01, hn + 0.01 + (occ - 0.8) * 0.05)
               * _smooth(0.0, 0.4, occ) * _smooth(tree_slope[0], tree_slope[1], normal_y)
               * _smooth(-1.4, 0.0, ridge))
        out['vegetation'] = np.clip(veg * land * (0.5 + 0.5 * moisture), 0.0, 1.0)
    return out


HYDROLOGY_MASKS = ['accumulation', 'channels', 'lake', 'wetness', 'moisture', 'deposition', 'occlusion',
                   'vegetation']

__all__ = ['neighbour_table', 'fill_depressions', 'route', 'accumulate', 'horizon_occlusion', 'box_blur', 'hydrology',
           'flat_average', 'FLAT_SLOPE', 'HYDROLOGY_MASKS']
