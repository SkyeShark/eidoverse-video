"""The family numbers (DESIGN.md section 10 item 4): each landform's own measurements, read off any heightfield in
metres (row 0 = south) at the matched pixel, so the same code measures the reference and the generated terrain.
Nothing needs hints from the generator; a recipe may pass some (`hints`) where it knows better (a crater centre, the
target dune spacing). Numpy only (the routing is solvers/hydro.py's).

    nums = family_numbers('crater', h, cell, hints=None)      # dict: the family's keys (below) + 'family'

    crater         crater_D_m, crater_d_over_D, rim_height_over_D, wall_slope_p99, ejecta_reach_R, rim_sides,
                   rim_roundness (std / mean of the rim radius over 72 azimuths: 0 is a perfect circle)
    volcano        profile_spearman (mean slope over 10 radial bins against radius: -1 = steepest at the top,
                   falling steadily), radial_aspect_frac (flank aspects within 30 degrees of radial), summit_crater_m,
                   flank_slope_top / _mid / _foot (degrees)
    cinder_cones   cone_count, cone_hw_max, cone_flank_p90 (of the cone with the largest H/W: the youngest),
                   cone_hw_median
    alpine_valley  u_exponent (median b of y = a x^b over 5 cross-sections of the trunk trough, both walls),
                   u_exponents, trough_width_m, hanging_step_m (largest), hanging_count (steps >= 100 m)
    canyon         benches_per_wall (the mean over 15 cross-sections x 2 walls; benches_median too), slope_bimodal (1
                   when the slope histogram peaks under 10 degrees and again at 25-50 degrees, the talus and ledges,
                   with a dip between), slope_peak_low / _high, slope_dip, cliff_tail_frac (over 45 degrees)
    mesas          caprock_frac, butte_wall_p90 (slope p90 of the cliff band below the caprock edges)
    dunes          dune_spacing_m (the peak of the slope spectrum), lee_aspect_peaks, slip_face_p99 (slope p99:
                   dry sand avalanches at 31-34 degrees, so a dune field's steepest 1 % sits at its slip faces)
    karst          summit_spacing_m (mean nearest-neighbour distance of the summits), summit_count, plain_frac
    coast          clifftop_p50_m / _p90_m (land height within 100 m of the shore), cliff_face_p90 (slope p90 of the
                   seaward 30 m), shore_len_km
    rolling_hills  ridge_convex_frac (ridge cells with convex curvature at 2 cells and 20 m)
"""
from __future__ import annotations

import math

import numpy as np

from .refs import grid
from eidoblend.terrain.core import metrics as M

FAMILIES = ('crater', 'volcano', 'cinder_cones', 'alpine_valley', 'canyon', 'mesas', 'dunes', 'karst', 'coast',
            'rolling_hills', 'fluvial_range', 'badlands', 'caldera')


# ------------------------------------------------------------------------------------------------- helpers ---

_HYDRO = []


def hydro():
    """route() and accumulate(): solvers/hydro.py."""
    if not _HYDRO:
        from eidoblend.terrain.solvers import hydro as H                    # noqa: WPS433 - owned elsewhere
        _HYDRO.append(H)
    return _HYDRO[0]


def max_filter(a, r):
    """Square max filter of half-width r cells (separable running max, edges clamped)."""
    out = np.asarray(a, dtype=np.float64)
    for axis in (0, 1):
        p = np.pad(out, [(r, r) if k == axis else (0, 0) for k in (0, 1)], mode='edge')
        n = out.shape[axis]
        acc = np.full_like(out, -np.inf)
        for k in range(2 * r + 1):
            sl = [slice(None), slice(None)]
            sl[axis] = slice(k, k + n)
            acc = np.maximum(acc, p[tuple(sl)])
        out = acc
    return out


def blur(a, sigma_px):
    from .match import gaussian
    return gaussian(a, sigma_px)


def sample(h, x, y):
    """Bilinear sample at fractional (column x, row y) indices, clamped."""
    ny, nx = h.shape
    x = np.clip(np.asarray(x, np.float64), 0, nx - 1)
    y = np.clip(np.asarray(y, np.float64), 0, ny - 1)
    x0 = np.minimum(np.floor(x).astype(np.int64), nx - 2)
    y0 = np.minimum(np.floor(y).astype(np.int64), ny - 2)
    fx, fy = x - x0, y - y0
    return ((h[y0, x0] * (1 - fx) + h[y0, x0 + 1] * fx) * (1 - fy)
            + (h[y0 + 1, x0] * (1 - fx) + h[y0 + 1, x0 + 1] * fx) * fy)


def radial_profile(h, cell, ci, cj, r_max_m, step_m=None, stat='mean'):
    """(r metres, azimuthal mean (or median) height) around cell (ci column, cj row), out to r_max_m."""
    step = step_m or cell
    rs = np.arange(0.0, r_max_m + step, step)
    az = np.linspace(0, 2 * math.pi, 72, endpoint=False)
    xs = ci + np.outer(rs / cell, np.cos(az))
    ys = cj + np.outer(rs / cell, np.sin(az))
    v = sample(h, xs, ys)
    return rs, (np.median(v, axis=1) if stat == 'median' else v.mean(axis=1))


def peaks(h, cell, radius_m, min_rel_m, max_n=60):
    """Local maxima standing min_rel_m above the lowest ground within 2 x radius: [(column, row, height)]."""
    r = max(1, int(round(radius_m / cell)))
    hb = blur(h, 0.7)
    mx = max_filter(hb, r)
    mn = -max_filter(-hb, 2 * r)
    cand = (hb >= mx - 1e-9) & (hb - mn >= min_rel_m)
    jj, ii = np.nonzero(cand)
    order = np.argsort(-(hb[jj, ii] - mn[jj, ii]))[:max_n]
    out, taken = [], []
    for k in order:
        i, j = int(ii[k]), int(jj[k])
        if any((i - a) ** 2 + (j - b) ** 2 < r * r for a, b in taken):
            continue
        taken.append((i, j))
        out.append((i, j, float(h[j, i])))
    return out


def drainage(h, cell):
    """(area m^2 (ny, nx), receivers (N,), filled): D8 drainage over the filled surface, the open edge draining."""
    H = hydro()
    filled, _ = M.fill_depressions(h, (False, False))
    recv, wgt, term = H.route(filled, wrap=(False, False), method='d8')
    acc = H.accumulate(recv, wgt, term)
    return (acc * cell * cell).reshape(h.shape), recv[0], filled


def trunk(h, cell, area=None, recv=None, min_frac=0.3):
    """The trunk river or valley floor through the tile, [(column, row), ...] from upstream to the outlet ([] when
    there is none). Two candidates, the lower one kept (a trunk is the lowest path):
      A. from the edge outlet with the largest drainage area, upstream along the largest donor each step;
      B. from the lowest edge cell that drains into the tile (a river entering it), downstream to the outlet.
    Inside one tile a through-flowing river's own catchment is small, so A alone climbs a side canyon at the first
    junction where the side canyon's in-tile area is larger (it did at Toroweap); B follows the river."""
    if area is None:
        area, recv, _ = drainage(h, cell)
    ny, nx = h.shape
    a = area.ravel()
    hz = np.asarray(h, np.float64).ravel()
    edge = np.zeros((ny, nx), bool)
    edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
    e = np.nonzero(edge.ravel())[0]
    cands = []
    donors_of = {}
    src = np.nonzero(recv >= 0)[0]
    for s in src[a[src] > 20 * cell * cell]:                             # only channels matter for the stem
        donors_of.setdefault(int(recv[s]), []).append(int(s))
    cur = int(e[np.argmax(a[e])])
    path, seen = [cur], {cur}
    while True:
        ds = [d for d in donors_of.get(cur, []) if d not in seen]
        if not ds:
            break
        cur = max(ds, key=lambda d: a[d])
        seen.add(cur)
        path.append(cur)
    cands.append(path[::-1])
    inflow = e[(recv[e] >= 0) & ~edge.ravel()[np.maximum(recv[e], 0)]]
    if inflow.size:
        cur = int(inflow[np.argmin(hz[inflow])])
        path, seen = [cur], {cur}
        while recv[cur] >= 0 and int(recv[cur]) not in seen:
            cur = int(recv[cur])
            seen.add(cur)
            path.append(cur)
        cands.append(path)
    cands = [p for p in cands if len(p) >= min_frac * max(nx, ny)]
    if not cands:
        return []
    best = min(cands, key=lambda p: float(np.median(hz[p])))
    jj, ii = np.divmod(np.array(best), nx)
    return list(zip(ii.tolist(), jj.tolist()))


def stations(path, n=5, lo=0.2, hi=0.8, half_window=6):
    """n points along a path between fractions lo..hi of its length, each with its unit direction (dx, dy)."""
    p = np.asarray(path, np.float64)
    seg = np.hypot(*np.diff(p, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    out = []
    for f in np.linspace(lo, hi, n):
        k = int(np.searchsorted(s, f * s[-1]))
        a, b = p[max(0, k - half_window)], p[min(len(p) - 1, k + half_window)]
        d = b - a
        L = math.hypot(*d) or 1.0
        out.append((p[k], d / L))
    return out


def section(h, cell, centre, direction, half_m):
    """The profile across a direction: (offsets metres, heights), offsets negative on the left."""
    nrm = np.array([-direction[1], direction[0]])
    t = np.arange(-half_m, half_m + cell * 0.5, cell * 0.5)
    pts = centre[None, :] + np.outer(t / cell, nrm)
    return t, sample(h, pts[:, 0], pts[:, 1])


# ------------------------------------------------------------------------------------------------ families ---

def crater(h, cell, hints=None):
    hints = hints or {}
    ny, nx = h.shape
    frac, count, thr, depth = M.depressions(h, cell)
    lab, n = M.label(depth > 1e-6)
    if 'centre' in hints:
        ci, cj = hints['centre']
    else:
        if n == 0:
            return dict(crater_found=0)
        area = np.bincount(lab.ravel(), minlength=n + 1)
        maxd = np.zeros(n + 1)
        np.maximum.at(maxd, lab.ravel(), depth.ravel())
        score = area * (maxd > thr)
        score[0] = 0
        L = int(np.argmax(score))
        jj, ii = np.nonzero(lab == L)
        ci, cj = float(ii.mean()), float(jj.mean())
        r_eq = math.sqrt(len(ii) / math.pi) * cell
    r_eq = hints.get('radius_m', locals().get('r_eq', 0.2 * nx * cell))
    rs, prof = radial_profile(h, cell, ci, cj, min(2.0 * r_eq, 0.5 * min(nx, ny) * cell))
    win = (rs > 0.4 * r_eq) & (rs < 1.6 * r_eq)
    R = float(rs[win][np.argmax(prof[win])])
    # per-azimuth rim: the highest point along each ray between 0.6 R and 1.4 R
    az = np.linspace(0, 2 * math.pi, 72, endpoint=False)
    rr = np.linspace(0.6 * R, 1.4 * R, 60)
    xs = ci + np.outer(np.cos(az), rr / cell)
    ys = cj + np.outer(np.sin(az), rr / cell)
    ray = sample(h, xs, ys)
    k = np.argmax(ray, axis=1)
    rim_r = rr[k]
    rim_h = ray[np.arange(72), k]
    R = float(rim_r.mean())
    D = 2.0 * R
    yy, xx = np.mgrid[0:ny, 0:nx]
    rad = np.hypot(xx - ci, yy - cj) * cell
    inner = rad < 0.5 * R
    floor = float(np.percentile(h[inner], 5)) if inner.any() else float(h.min())
    far = (rad > 2.5 * R) & (rad < 3.5 * R)
    if far.sum() < 20:
        far = rad > 0.85 * rad.max()
    plain = float(np.median(h[far]))
    rim = float(rim_h.mean())
    s = grid.slope_deg(h, cell)
    wall = rad < R
    rs2, prof2 = radial_profile(h, cell, ci, cj, min(4.0 * R, 0.5 * min(nx, ny) * cell))
    out_ = rs2 > R
    above = prof2[out_] - plain
    reach = rs2[out_][np.argmax(above < 0.1 * max(rim - plain, 1e-6))] if (above < 0.1 * max(rim - plain, 1e-6)).any() \
        else rs2[-1]
    spec = np.abs(np.fft.rfft(rim_r - rim_r.mean()))
    sides = int(np.argmax(spec[3:9]) + 3)
    return dict(crater_found=1, crater_D_m=D, crater_d_over_D=(rim - floor) / D, rim_height_over_D=(rim - plain) / D,
                wall_slope_p99=float(np.percentile(s[wall], 99)), ejecta_reach_R=float(reach / R), rim_sides=sides,
                rim_roundness=float(rim_r.std() / R))


def volcano(h, cell, hints=None):
    hints = hints or {}
    ny, nx = h.shape
    hb = blur(h, 2.0)
    if 'vent' in hints:
        ci, cj = hints['vent']
    else:
        cj, ci = np.unravel_index(int(np.argmax(hb)), hb.shape)
    ci, cj = float(ci), float(cj)
    r_edge = min(ci, cj, nx - 1 - ci, ny - 1 - cj) * cell
    # the azimuthal MEDIAN profile: hills around the cone (Fuji's Misaka and Tanzawa ranges) sit at a few azimuths
    # only, so the median follows the cone where a mean takes them in
    rs, prof = radial_profile(h, cell, ci, cj, r_edge, stat='median')
    base = float(np.percentile(h, 10))
    H = float(prof[:max(2, int(200 / cell))].max()) - base
    above = prof - base
    # the foot: where the median profile is 10 % of the height above the surroundings (an exponential cone never
    # ends; beyond this its apron is under 2-3 degrees and the bins only measure the plain)
    foot = rs[np.argmax(above < 0.10 * H)] if (above < 0.10 * H).any() else rs[-1]
    r1 = min(foot, 0.95 * r_edge)
    yy, xx = np.mgrid[0:ny, 0:nx]
    dx, dy = (xx - ci) * cell, (yy - cj) * cell
    rad = np.hypot(dx, dy)
    # the summit crater: the deepest closed depression within max(600 m, 6 % of the foot radius) of the summit
    _f, _c, _t, depth = M.depressions(h, cell)
    near = rad < max(600.0, 0.06 * foot)
    crater_m = float(depth[near].max()) if near.any() else 0.0
    r0 = max(0.04 * foot, 3 * cell, float(rs[np.argmax(prof)]) * 1.2)
    # the radial slope profile: the slope of the median profile, averaged in 10 bins from the crater rim to where
    # it falls under 3 degrees (the apron; Fuji: 2.8 degrees at 15 km) or the foot, whichever is nearer
    rslope = np.degrees(np.arctan(np.clip(-np.gradient(prof, rs), 0.0, None)))
    sm = np.convolve(rslope, np.ones(5) / 5, mode='same')
    low = np.nonzero((rs > 2 * r0) & (sm < 3.0))[0]
    if low.size:
        r1 = min(r1, float(rs[low[0]]))
    edges = np.linspace(r0, r1, 11)
    mean_s = np.array([float(rslope[(rs >= a) & (rs < b)].mean()) if ((rs >= a) & (rs < b)).any() else float('nan')
                       for a, b in zip(edges[:-1], edges[1:])])
    ok = np.isfinite(mean_s)
    rank_r = np.argsort(np.argsort(np.arange(10)[ok]))
    rank_s = np.argsort(np.argsort(mean_s[ok]))
    rho = float(np.corrcoef(rank_r, rank_s)[0, 1]) if ok.sum() >= 4 else float('nan')
    s = grid.slope_deg(h, cell)
    gx, gy = grid.gradient(h, cell)
    # the flank: steeper than 5 degrees, between the rim and where the median profile is 15 % of the height up
    r_flank = rs[np.argmax(above < 0.15 * H)] if (above < 0.15 * H).any() else r1
    flank = (rad > r0) & (rad < min(r1, r_flank)) & (s > 5.0)
    down = np.arctan2(-gy[flank], -gx[flank])
    radial = np.arctan2(dy[flank], dx[flank])
    diff = np.abs((down - radial + math.pi) % (2 * math.pi) - math.pi)
    radial_frac = float((diff < math.radians(30)).mean()) if flank.any() else float('nan')
    return dict(profile_spearman=rho, radial_aspect_frac=radial_frac, summit_crater_m=crater_m,
                volcano_height_m=H, volcano_foot_m=float(foot), flank_slope_top=float(mean_s[0]),
                flank_slope_mid=float(mean_s[4]), flank_slope_foot=float(mean_s[-1]),
                flank_slopes=[round(float(v), 2) for v in mean_s])


def summit_centre(h, cell, ci, cj, r_m=400.0, passes=3):
    """A cone's axis from one of its high points: the centroid of the cells within the top 15 % of the relief of a
    window around it, re-centred `passes` times. On a cone with a summit crater the highest point is on the rim;
    the rim ring's centroid is the axis."""
    ny, nx = h.shape
    r = max(2, int(round(r_m / cell)))
    for _ in range(passes):
        i, j = int(round(ci)), int(round(cj))
        j0, j1, i0, i1 = max(0, j - r), min(ny, j + r + 1), max(0, i - r), min(nx, i + r + 1)
        win = h[j0:j1, i0:i1]
        top, low = float(win.max()), float(win.min())
        jj, ii = np.nonzero(win >= top - 0.15 * (top - low))
        ci, cj = i0 + float(ii.mean()), j0 + float(jj.mean())
    return ci, cj


def cinder_cones(h, cell, hints=None):
    hints = hints or {}
    ny, nx = h.shape
    cones = []
    for ci, cj, top in peaks(h, cell, 250.0, 25.0, max_n=40):
        ci, cj = summit_centre(h, cell, ci, cj)
        r_max = min(1500.0, min(ci, cj, nx - 1 - ci, ny - 1 - cj) * cell)
        if r_max < 200:
            continue
        rs, prof = radial_profile(h, cell, ci, cj, r_max)
        sl = np.degrees(np.arctan(-np.gradient(prof, rs)))
        # the base: where the mean slope falls under 6 degrees, past the steepest part of the flank
        kmax = int(np.argmax(sl))
        rest = np.nonzero(sl[kmax:] < 6.0)[0]
        if not rest.size:
            continue
        kb = kmax + int(rest[0])
        Hc = float(prof[np.argmax(prof[:kb + 1])] - prof[kb])
        W = 2.0 * float(rs[kb])
        if Hc < 20 or W < 6 * cell:
            continue
        yy, xx = np.mgrid[0:ny, 0:nx]
        rad = np.hypot(xx - ci, yy - cj) * cell
        r_rim = float(rs[int(np.argmax(prof[:kb + 1]))])
        fl = (rad > max(r_rim, 0.15 * W / 2)) & (rad < 0.9 * rs[kb])
        s = grid.slope_deg(h, cell)
        p90 = float(np.percentile(s[fl], 90)) if fl.sum() > 10 else float('nan')
        cones.append(dict(col=ci, row=cj, H=Hc, W=W, hw=Hc / W, flank_p90=p90))
    if not cones:
        return dict(cone_count=0)
    best = max(cones, key=lambda c: c['hw'])
    return dict(cone_count=len(cones), cone_hw_max=best['hw'], cone_flank_p90=best['flank_p90'],
                cone_H_m=best['H'], cone_W_m=best['W'], cone_hw_median=float(np.median([c['hw'] for c in cones])),
                cones=[{k: (round(v, 3) if isinstance(v, float) else v) for k, v in c.items()} for c in cones])


def _walls(t, z, max_m=3000.0):
    """The two walls of a cross-section. The floor is the lowest point extended while within max(2 m, 2 % of the
    section's relief) of it; x is measured from the floor's centre. On each side the wall's steepest point within
    max_m, then the shoulder: the first point past it where the slope falls under max(15, 0.4 x the steepest) degrees
    (the top of the trough wall, not the peaks above it). Returns [(b, shoulder x m, shoulder y m), ...] per side:
    b of y = a x^b fitted from the floor centre to the shoulder (points over 2 % of the shoulder height)."""
    k0 = int(np.argmin(z))
    zf = float(z[k0])
    tol = max(2.0, 0.02 * float(z.max() - zf))
    lo, hi = k0, k0
    while lo > 0 and z[lo - 1] <= zf + tol:
        lo -= 1
    while hi < len(z) - 1 and z[hi + 1] <= zf + tol:
        hi += 1
    kc = (lo + hi) // 2
    out = []
    for side in (-1, 1):
        idx = np.arange(kc, -1, -1) if side < 0 else np.arange(kc, len(z))
        x = np.abs(t[idx] - t[kc])
        y = z[idx] - zf
        if len(x) < 8:
            out.append((float('nan'), float('nan'), float('nan')))
            continue
        sl = np.degrees(np.arctan(np.gradient(y, x)))
        reach = x <= max_m
        km = int(np.argmax(np.where(reach, sl, -90.0)))
        after = np.nonzero(sl[km:] < max(15.0, 0.4 * sl[km]))[0]
        ks = km + int(after[0]) if after.size else len(x) - 1
        xs, ys = x[1:ks + 1], y[1:ks + 1]
        good = (ys > 0.02 * max(y[ks], 1e-6)) & (xs > 0)
        b = float(np.polyfit(np.log(xs[good]), np.log(ys[good]), 1)[0]) if good.sum() >= 4 else float('nan')
        out.append((b, float(x[ks]), float(y[ks])))
    return out


def alpine_valley(h, cell, hints=None):
    area, recv, _filled = drainage(h, cell)
    path = trunk(h, cell, area, recv)
    if not path:
        return dict(u_exponent=float('nan'))
    hs = blur(h, 1.0)
    half = min(3500.0, 0.45 * h.shape[0] * cell)
    hw = max(3, int(150 / cell))
    bs, sh_x, sh_y = [], [], []
    for c, d in stations(path, 5, 0.15, 0.85, half_window=hw):
        t, z = section(hs, cell, c, d, half)
        for b, x, y in _walls(t, z):
            if math.isfinite(b):
                bs.append(b)
                sh_x.append(x)
                sh_y.append(y)
    if not bs:
        return dict(u_exponent=float('nan'))
    lip = float(np.median(sh_x))
    # hanging valleys: the lip line. At the trough's lip offset (the median shoulder distance) on each side, every
    # few cells along the trunk, the height above the trunk floor there. A trough wall stands high; a tributary mouth
    # is a notch in that line: a hanging valley's notch stays high above the floor (its lip), a graded tributary's
    # comes down near the floor. The steps are the notch heights.
    n_st = max(20, int(len(path) / max(2, int(60 / cell))))
    notches = []
    for side in (-1, 1):
        dl = []
        for c, d in stations(path, n_st, 0.1, 0.9, half_window=hw):
            t, z = section(hs, cell, c, d, lip + 4 * cell)
            k0 = int(np.argmin(np.abs(t)))
            zf = float(z[max(0, k0 - 2):k0 + 3].min())
            dl.append(float(np.interp(side * lip, t, z)) - zf)
        dl = np.array(dl)
        med = float(np.median(dl))
        w = max(2, n_st // 20)
        for k in range(len(dl)):
            seg = dl[max(0, k - w):k + w + 1]
            if dl[k] <= seg.min() + 1e-9 and dl[k] < 0.75 * med:
                notches.append(float(dl[k]))
    notches = np.array(notches) if notches else np.zeros(0)
    return dict(u_exponent=float(np.median(bs)), u_exponents=[round(b, 2) for b in bs],
                trough_width_m=2.0 * lip, trough_depth_m=float(np.median(sh_y)),
                hanging_step_m=float(notches.max()) if notches.size else 0.0,
                hanging_count=int((notches >= 100.0).sum()), notch_heights_m=[round(v) for v in notches])


def _benches(x, z, cell):
    """Benches on one canyon wall: x metres from the river outward, z heights, up to the wall's highest point. A
    bench is a tread (slope under 18 degrees, 3-sample smoothed) at least 2 cells wide with a riser (over 30 degrees)
    below it and a riser rising at least 10 m above it: a flat top with nothing above is the rim, not a bench."""
    k = int(np.argmax(z))
    x, z = x[:k + 1], z[:k + 1]
    if len(x) < 8:
        return 0
    sl = np.degrees(np.arctan(np.abs(np.gradient(z, x))))
    sl = np.convolve(sl, np.ones(3) / 3, mode='same')
    cls = np.where(sl > 30.0, 2, np.where(sl < 18.0, 0, 1))
    runs, start = [], 0
    for i in range(1, len(cls) + 1):
        if i == len(cls) or cls[i] != cls[start]:
            runs.append((int(cls[start]), start, i - 1))
            start = i
    count = 0
    for n, (c, a, b) in enumerate(runs):
        if c != 0 or x[b] - x[a] < 2 * cell:
            continue
        below = any(r[0] == 2 for r in runs[:n])
        above = [r for r in runs[n + 1:] if r[0] == 2]
        if below and above and z[above[0][2]] - z[above[0][1]] >= 10.0:
            count += 1
    return count


def canyon(h, cell, hints=None):
    # the slope histogram in 2-degree bins: flats (under 10 degrees) and a second peak of talus and ledge slopes
    # at 25-50 degrees with a dip between (Toroweap at 8 m: 0-5 degrees 24 %, 20-25 degrees 5.6 %, 30-35 degrees
    # 8.9 %); the cliffs are the tail beyond 45 degrees (cliff_tail_frac)
    s = grid.slope_deg(h, cell)
    hist, _e = np.histogram(s, bins=45, range=(0, 90))
    hist = np.convolve(hist, np.ones(3) / 3, mode='same')
    lo, dip, hi_ = float(hist[:5].max()), float(hist[5:13].min()), float(hist[12:26].max())
    bimodal = int(lo > 1.2 * dip and hi_ > 1.2 * dip)
    area, recv, _ = drainage(h, cell)
    path = trunk(h, cell, area, recv)
    benches = []
    if path:
        hs = blur(h, 0.7)
        # 15 cross-sections (30 walls): the count per wall is a small integer, and 5 sections (the design's) gave
        # medians that moved by 0.5-1.5 with where the sections fell
        for c, d in stations(path, 15, 0.15, 0.85, half_window=max(3, int(100 / cell))):
            t, z = section(hs, cell, c, d, 0.5 * h.shape[0] * cell)
            k0 = int(np.argmin(np.abs(t)))
            for side in (-1, 1):
                idx = np.arange(k0, -1, -1) if side < 0 else np.arange(k0, len(z))
                benches.append(_benches(np.abs(t[idx] - t[k0]), z[idx], cell))
    return dict(benches_per_wall=float(np.mean(benches)) if benches else float('nan'),
                benches_median=float(np.median(benches)) if benches else float('nan'), benches=benches,
                slope_bimodal=bimodal, slope_peak_low=lo / s.size, slope_peak_high=hi_ / s.size,
                slope_dip=dip / s.size, cliff_tail_frac=float((s > 45.0).mean()))


def _floor_surface(h, cell, block_m=1000.0):
    """A smooth 'local floor': the 10th percentile of each block, bilinearly spread."""
    ny, nx = h.shape
    b = max(4, int(round(block_m / cell)))
    nby, nbx = max(1, ny // b), max(1, nx // b)
    vals = np.zeros((nby, nbx))
    for j in range(nby):
        for i in range(nbx):
            vals[j, i] = np.percentile(h[j * b:(j + 1) * b, i * b:(i + 1) * b], 10)
    yy = (np.arange(ny) + 0.5) / b - 0.5
    xx = (np.arange(nx) + 0.5) / b - 0.5
    X, Y = np.meshgrid(xx, yy)
    return sample(vals, X, Y) if min(nby, nbx) > 1 else np.full_like(h, vals.mean())


def mesas(h, cell, hints=None):
    s = grid.slope_deg(h, cell)
    rel = h - _floor_surface(h, cell)
    top = float(np.percentile(rel, 99.9))
    cap = (rel > 0.6 * top) & (s < 12.0)
    edge = max_filter(cap.astype(np.float64), max(1, int(round(30 / cell)))) > 0
    band = edge & ~cap & (rel > 0.2 * top) & (s > 25.0)
    return dict(caprock_frac=float(cap.mean()),
                butte_wall_p90=float(np.percentile(s[band], 90)) if band.sum() > 10 else float('nan'),
                butte_relief_m=top)


def dune_spacing(h, cell):
    """The wavelength carrying the most slope: the peak of k^2 P(k) between 4 pixels and a quarter of the extent."""
    wl, P = M.radial_spectrum(h, cell, nbins=64)
    k = 1.0 / wl
    band = (wl >= 4 * cell) & (wl <= 0.25 * min(h.shape) * cell)
    sp = (k * k * P)[band]
    sp = np.convolve(sp, np.ones(3) / 3, mode='same')
    return float(wl[band][int(np.argmax(sp))])


def lee_peaks(h, cell, min_slope=20.0):
    """Peaks of the aspect histogram of the steep (slip-face) cells: 36 bins, circularly smoothed, a peak at least
    25 % of the largest and higher than its neighbours over +-30 degrees."""
    s = grid.slope_deg(h, cell)
    asp = grid.aspect_deg(h, cell)[s > min_slope]
    if asp.size < 50:
        return 0
    hist = np.bincount((asp // 10).astype(int) % 36, minlength=36).astype(np.float64)
    hist = (np.roll(hist, 1) + 2 * hist + np.roll(hist, -1)) / 4
    count = 0
    for k in range(36):
        win = [hist[(k + d) % 36] for d in (-3, -2, -1, 1, 2, 3)]
        if hist[k] >= 0.25 * hist.max() and hist[k] > max(win):
            count += 1
    return count


def dunes(h, cell, hints=None):
    s = grid.slope_deg(h, cell)
    out = dict(dune_spacing_m=dune_spacing(h, cell), lee_aspect_peaks=lee_peaks(h, cell),
               slip_face_p99=float(np.percentile(s, 99)))
    if hints and hints.get('target_spacing_m'):
        out['target_spacing_m'] = float(hints['target_spacing_m'])
    return out


def karst(h, cell, hints=None):
    pk = peaks(h, cell, 60.0, 30.0, max_n=400)
    s = grid.slope_deg(h, cell)
    plain = (s < 5.0) & (h < np.percentile(h, 50))
    if len(pk) < 3:
        return dict(summit_count=len(pk), summit_spacing_m=float('nan'), plain_frac=float(plain.mean()))
    p = np.array([(a, b) for a, b, _ in pk], np.float64) * cell
    d = np.hypot(p[:, None, 0] - p[None, :, 0], p[:, None, 1] - p[None, :, 1])
    np.fill_diagonal(d, np.inf)
    return dict(summit_count=len(pk), summit_spacing_m=float(d.min(axis=1).mean()), plain_frac=float(plain.mean()))


def coast(h, cell, hints=None, sea_level=0.0):
    sea = h <= sea_level + 0.3
    if not sea.any() or sea.all():
        return dict(shore_len_km=0.0)
    land = ~sea
    r1 = max(1, int(round(100 / cell)))
    near_sea = max_filter(sea.astype(np.float64), 1) > 0
    shore = land & near_sea
    top = max_filter(np.where(land, h, -np.inf), r1)
    tops = top[shore] - sea_level
    r30 = max(1, int(round(30 / cell)))
    seaward = land & (max_filter(sea.astype(np.float64), r30) > 0) & (h > sea_level + 5)
    s = grid.slope_deg(h, cell)
    return dict(clifftop_p50_m=float(np.percentile(tops, 50)), clifftop_p90_m=float(np.percentile(tops, 90)),
                cliff_face_p90=float(np.percentile(s[seaward], 90)) if seaward.sum() > 10 else float('nan'),
                shore_len_km=float(shore.sum() * cell / 1000.0))


def rolling_hills(h, cell, hints=None):
    sig = max(1.0, 100.0 / cell)
    rel = h - blur(h, sig)
    ridge = rel > np.percentile(rel, 85)
    out = {}
    for name, sc in (('2cells', 2.0), ('20m', max(1.0, 20.0 / cell))):
        hb = blur(h, sc)
        lap = (np.roll(hb, 1, 0) + np.roll(hb, -1, 0) + np.roll(hb, 1, 1) + np.roll(hb, -1, 1) - 4 * hb)
        inner = np.zeros_like(ridge)
        inner[2:-2, 2:-2] = True
        out[name] = float((lap[ridge & inner] < 0).mean())
    return dict(ridge_convex_frac=min(out.values()), ridge_convex_2cells=out['2cells'], ridge_convex_20m=out['20m'])


def caldera(h, cell, hints=None):
    """The caldera's own numbers (not in the design's table; read for the sheet): its rim diameter and the floor
    depth below the rim, by the crater reader."""
    c = crater(h, cell, hints)
    return {('caldera_' + k if not k.startswith('crater') else k.replace('crater', 'caldera')): v
            for k, v in c.items() if k in ('crater_found', 'crater_D_m', 'crater_d_over_D', 'wall_slope_p99')}


_FUNCS = {'crater': crater, 'volcano': volcano, 'cinder_cones': cinder_cones, 'alpine_valley': alpine_valley,
          'canyon': canyon, 'mesas': mesas, 'dunes': dunes, 'karst': karst, 'coast': coast,
          'rolling_hills': rolling_hills, 'caldera': caldera}


def family_numbers(family, h, cell, hints=None, sea_level=None):
    """The family's numbers of a surface (row 0 = south, metres) at `cell` metres. Families without numbers in the
    design (fluvial_range, badlands) return only {'family': ...}."""
    f = _FUNCS.get(family)
    out = {'family': family}
    if f is None:
        return out
    h = np.asarray(h, dtype=np.float64)
    if family == 'coast':
        out.update(coast(h, cell, hints, 0.0 if sea_level is None else sea_level))
    else:
        out.update(f(h, cell, hints))
    return out
