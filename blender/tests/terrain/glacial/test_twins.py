"""The glacial package's plain-Python tests (numpy twins, no GPU; each under 5 s):

    python blender/tests/terrain/glacial/test_twins.py

  1. the jump flood's twin against the brute-force lower envelope at 64^2: every cell's nearest seed (distance
     metric) and its trough target (height metric, with random per-seed floor shares and fans: seedC), and the four
     best streams per cell
  2. the ice discharge on the twin device, iterated to convergence, closes its mass balance (accumulation + inflow
     - realised ablation = outflow) within 1e-6, with and without ice entering at the window's edge
  3. the cross-section prof(rho): continuous at the floor's edge, the cliff's toe and lip, the lip and the
     shoulder's edge, never falling outward; the recipe's trunk wall (alpine_valley's knobs) stands as Lauterbrunnen's
     do: its core at wall_deg, 70 degrees or more over 60 % of its height, 600 m within 250 m of the floor's edge
     (the judge's U-fit, judge/family._walls, on that section is recorded)
  4. graded_fill: the fill's top falls down-valley by at least the grade, never lowers a floor, and at each
     glacier's end reaches the river below it
  5. best_donor: every cell's donor drains into it, and it is the largest of them
  6. wall_flutes: the couloir-and-rib pattern runs down the fall line (it changes at least twice as fast across
     the slope as down it), the couloirs a minority of the wall (10-35 %)
  7. the shoulder cut (u_carve twin) on a straight trough cut into an old valley floor at the lip's height and into
     an old V-valley: beyond the lip the ground rises from the lip with no rim and no flat strip (8 degrees or more
     over its first 100 m), the old floor ends the cut lowered by shoulder_cut H at the lip, and beyond the cut's
     width the ground is untouched; with seedC's defaults the carve is the uniform one
  8. head_distance and the head taper: distance from each stream's head along its main stem; the trough grows in
     from a tenth of its size at a head (head_taper_factor, never 0)
  9. the recipe's carve with its head taper (twin device, a small V valley): every seed a trough of the recipe's
     shape and every carved cell carved by a trough within reach (a seed of no size is a level plane that the jump
     flood ranks first everywhere: on 11-13 the main tile got no trough)
 10. sharpen_walls: a trough carved on 31.25 m cells and inherited at 15.6 m gets its walls back at 15.6 m (within
     a quarter of the upsampled error and 15 m), the floor, the ground beyond the lip and the pinned band untouched
Writes blender/tests/terrain/out/glacial/twin_tests.json; exit code 1 on a failure.
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'core'))
import plain_import  # noqa: E402

plain_import.install()
sys.path.insert(0, TN)

import numpy as np  # noqa: E402

from eidoblend.terrain.core import twins as T  # noqa: E402
from eidoblend.terrain.solvers import fluvial as FL  # noqa: E402
from eidoblend.terrain.solvers import glacial as G  # noqa: E402
from eidoblend.terrain.solvers import hydro as HY  # noqa: E402

OUT = os.path.join(TN, 'out', 'glacial')
RESULTS, FAILED = {}, []
F32 = np.float32


def check(name, cond, detail=None, seconds=None):
    RESULTS[name] = {'ok': bool(cond), 'detail': detail, 'seconds': seconds}
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f': {detail}' if detail is not None else '') +
          (f' ({seconds:.2f} s)' if seconds is not None else ''), flush=True)
    if not cond:
        FAILED.append(name)


PROF = G.profile_uniforms({'floor_frac': 0.25, 'wall_toe': 0.3, 'wall_lip': 0.2, 'floor_rise': 0.06,
                           'shoulder_width': 1.5, 'shoulder_rise': 0.3, 'upper_wall': 1.5})


def seeds(n0, n1, cell, n_streams=8, per=10, seed=3):
    """Random seed cells in streams (each a short random walk), with their trough data: (cand0, seedA, seedB,
    flat indices)."""
    rng = np.random.default_rng(seed)
    cand = np.full((n0, n1, 4), -1.0, F32)
    A = np.zeros((n0, n1, 4), F32)
    B = np.zeros((n0, n1, 4), F32)
    B[..., 0] = 1.0
    used = []
    for s in range(n_streams):
        i, j = int(rng.integers(4, n1 - 4)), int(rng.integers(4, n0 - 4))
        W = rng.uniform(4.0, 12.0) * cell
        for _ in range(per):
            if j * n1 + i not in used:
                used.append(j * n1 + i)
                cand[j, i, 0] = j * n1 + i
                A[j, i] = ((i + 0.5 + rng.uniform(-0.4, 0.4)) * cell, (j + 0.5 + rng.uniform(-0.4, 0.4)) * cell,
                           rng.uniform(0.0, 300.0), rng.uniform(100.0, 400.0))
                B[j, i] = (W * rng.uniform(0.8, 1.2), s, rng.uniform(0.0, 30.0), rng.uniform(0.0, 20.0))
            i = int(np.clip(i + rng.integers(-1, 2), 0, n1 - 1))
            j = int(np.clip(j + rng.integers(-1, 2), 0, n0 - 1))
    return cand, A, B, np.array(used, np.int64)


def seeds_c(cand, seed=5):
    """A random seedC for the seed cells of cand: floor share factors 0.4-1.2, fans 0.2-2, shoulder cuts 0-0.3."""
    rng = np.random.default_rng(seed)
    C = G.default_seed_c(cand.shape)
    at = cand[..., 0] >= 0
    k = int(at.sum())
    C[at] = np.stack([rng.uniform(0.4, 1.2, k), rng.uniform(0.2, 2.0, k), rng.uniform(0.0, 0.3, k),
                      np.zeros(k)], 1).astype(F32)
    return C


def test_jump_flood():
    t0 = time.perf_counter()
    dev = FL.device('twin')
    n0 = n1 = 64
    cell = 10.0
    cand0, A, B, idx = seeds(n0, n1, cell)
    C = seeds_c(cand0)
    for metric, name in ((1, 'distance'), (0, 'trough target')):
        cT, _, _ = G.jump_flood_run(dev, cand0, A, B, cell, PROF, G.jfa_steps(n0, n0), metric, seedC=C)
        cand = dev.read(cT)
        got = G.decode_best(cand, A, B, cell, PROF, metric, slot='all', seedC=C)
        want = G.brute_force(idx, A, B, cell, PROF, metric, per_stream=True, seedC=C)
        tol = 1e-3 * max(1.0, float(np.nanmax(np.abs(np.where(np.isfinite(want), want, 0)))))
        first = np.abs(got[..., 0] - want[..., 0]) <= tol
        four = np.all((np.abs(got - want) <= tol) | (np.isinf(got) & np.isinf(want)), axis=-1)
        check(f'jump flood twin vs brute force, {name}: nearest', first.mean() >= 0.995,
              f'{first.mean() * 100:.2f} % of cells exact (worst {np.max(np.abs(got[..., 0] - want[..., 0])):.3g})')
        check(f'jump flood twin vs brute force, {name}: four best streams', four.mean() >= 0.98,
              f'{four.mean() * 100:.2f} % of cells have all four exact')
    RESULTS['jump flood twin vs brute force, distance: nearest']['seconds'] = round(time.perf_counter() - t0, 2)


def surface(n=96, cell=50.0, seed=5):
    """A filled routing surface: a tilted dome of rough ground (heights 0-2500 m)."""
    rng = np.random.default_rng(seed)
    jj, ii = np.mgrid[0:n, 0:n]
    r = np.hypot(ii - n / 2, jj - n * 0.3) / n
    h = 2500.0 * np.exp(-3.0 * r * r) + 300.0 * T.random_field((n, n), 0, 1, seed, smooth=3)
    h = h + 0.5 * rng.random((n, n))
    filled, _ = HY.fill_depressions(h)
    return HY.routing_surface(filled).astype(F32), cell


def test_mass_balance():
    dev = FL.device('twin')
    surf, cell = surface()
    recv = G.d8_receivers(surf, cell)
    params = {'ela_m': 1500.0}
    b = G.mass_balance(surf, 0.0, params)
    n = surf.shape[0]
    rng = np.random.default_rng(1)
    q_in = np.zeros((n, n), F32)
    q_in[0, rng.integers(0, n, 6)] = rng.uniform(1e5, 1e6, 6).astype(F32)
    for name, qi in (('no inflow', None), ('inflow at the edge', q_in)):
        t0 = time.perf_counter()
        Q, it = G.ice_flux_converge(dev, surf, b, cell, recv, 0.0, Q_in=qi, params=params, check=32)
        bud = G.flux_budget(Q, b, recv, cell, params, Q_in=qi)
        check(f'ice flux mass balance closes ({name})', abs(bud['rel_residual']) <= 1e-6 and bud['outflow'] > 0,
              f"accumulation {bud['accumulation']:.4g} + inflow {bud['inflow']:.4g} - ablation {bud['ablation']:.4g}"
              f" = outflow {bud['outflow']:.4g} (residual {bud['rel_residual']:.2e}, {it} iterations, glaciated "
              f"{(Q > 0).mean() * 100:.1f} %)", round(time.perf_counter() - t0, 2))


def test_profile():
    t0 = time.perf_counter()
    from eidoblend.terrain import recipes as RG
    from judge import family as FA
    eps = 1e-6
    _, stages = RG.get('alpine_valley').resolve({})
    gp = [s for s in stages if s.op == 'glacial'][0].params
    for name, u in (('a test profile', PROF), ("alpine_valley's", G.profile_uniforms(gp))):
        ff, sw, toe, lip = u['uFloorFrac'], u['uShW'], u['uToe'], u['uLip']
        knots = (ff, ff + toe * (1 - ff), 1.0 - lip * (1 - ff), 1.0, 1.0 + sw)
        jumps = [abs(float(G.prof(np.array([x + eps]), u, np.float64)[0] -
                           G.prof(np.array([x - eps]), u, np.float64)[0])) for x in knots]
        rho = np.linspace(0, 6, 6001)
        p = G.prof(rho, u, np.float64)
        check(f'{name} profile continuous at the floor edge, the toe, the lip and the shoulder edge',
              max(jumps) < 1e-4, f'jumps {[round(j, 6) for j in jumps]}')
        check(f'{name} profile never falls outward', bool(np.all(np.diff(p) >= -1e-12)))
    # the recipe's trunk wall, as the reviewer measured Lauterbrunnen's: 600-900 m at 70-85 degrees within a few
    # hundred metres
    u = G.profile_uniforms(gp)
    W, H = 0.5 * float(gp['trough_width_m']), float(gp['trough_depth_m'])
    r = np.linspace(0.0, 1.2 * W, 24001)
    z = H * G.prof(r / W, u, np.float64)
    edge = u['uFloorFrac'] * W
    sl = np.degrees(np.arctan(np.gradient(z, r)))
    dz = np.diff(z)
    steep = float(dz[sl[1:] >= 70.0].sum() / H)
    rise = float(np.interp(edge + 250.0, r, z))
    core = float(sl.max())
    t = np.arange(-3500, 3500.1, 4.0)
    rr = np.abs(t) / W
    zz = np.maximum(H * G.prof(rr, u, np.float64), G.fillz(rr, 0.0, H, u, np.float64))
    zz = np.minimum(zz, H + math.tan(math.radians(35.0)) * np.maximum(np.abs(t) - W, 0.0))
    bs = [w[0] for w in FA._walls(t, zz)]
    check("alpine_valley's trunk wall stands at wall_deg, 70 degrees or more over 60 % of its height, 600 m within "
          "250 m of the floor", abs(core - float(gp['wall_deg'])) <= 1.0 and steep >= 0.6 and rise >= 600.0,
          f"floor {2 * edge:.0f} m wide, core {core:.1f} deg (wall_deg {gp['wall_deg']:g}), {steep * 100:.0f} % of "
          f"the {H:.0f} m wall at 70 deg or more, {rise:.0f} m at 250 m from the floor; the judge's U-fit reads b "
          f"{[round(b, 2) for b in bs]}", round(time.perf_counter() - t0, 2))


def test_graded_fill():
    t0 = time.perf_counter()
    surf, cell = surface(n=80, cell=40.0, seed=9)
    recv = G.d8_receivers(surf, cell)
    A, _ = G.ice_flux_converge(FL.device('twin'), surf, np.ones_like(surf), cell, recv, 0.0,
                               params={'ice_width_m': 0.0}, check=32)
    mask = A >= 30 * cell * cell
    st = G.streams(mask, recv, A)
    idx = st['idx']
    jj, ii = np.divmod(idx, surf.shape[1])
    x, y = (ii + 0.5) * cell, (jj + 0.5) * cell
    rng = np.random.default_rng(2)
    zc = surf.ravel()[idx].astype(np.float64)
    zf = zc - rng.uniform(0, 120, idx.size)                                       # an uneven, overdeepened floor
    grade = 0.012
    fill = G.graded_fill(zf, np.zeros(idx.size), x, y, st, grade, outlet=zc)
    top = zf + fill
    rc = st['rcv']
    has = rc >= 0
    L = np.hypot(x - x[np.maximum(rc, 0)], y - y[np.maximum(rc, 0)])
    drop = top - top[np.maximum(rc, 0)]
    ok = np.all(drop[has] >= grade * L[has] - 1e-6)
    ends = ~has
    check('graded fill falls down-valley by at least the grade, never lowers a floor, and meets the river at '
          'each glacier\'s end', bool(ok) and bool(np.all(fill >= 0)) and bool(np.all(top[ends] >= zc[ends] - 1e-9)),
          f'{idx.size} seeds, {int(has.sum())} links, {int(ends.sum())} ends, fill max {fill.max():.1f} m',
          round(time.perf_counter() - t0, 2))


def test_best_donor():
    t0 = time.perf_counter()
    surf, cell = surface(n=64, cell=40.0, seed=4)
    recv = G.d8_receivers(surf, cell)
    A, _ = G.ice_flux_converge(FL.device('twin'), surf, np.ones_like(surf), cell, recv, 0.0,
                               params={'ice_width_m': 0.0}, check=32)
    up = G.best_donor(recv, A)
    n0, n1 = surf.shape
    r = recv.ravel().astype(np.int64)
    a = A.ravel()
    q = np.arange(n0 * n1)
    tgt = np.full(n0 * n1, -1, np.int64)                       # each cell's receiver cell (-1 none)
    for k in range(8):
        sel = r == k
        tgt[sel] = G._flat_neighbour(q[sel], k, n0, n1)
    has = tgt >= 0
    amax = np.full(n0 * n1, -1.0)                              # the largest donor's area at each receiver
    np.maximum.at(amax, tgt[has], a[q[has]])
    d = up
    drains = np.where(d >= 0, tgt[np.maximum(d, 0)] == q, amax < 0)
    largest = np.where(d >= 0, a[np.maximum(d, 0)] >= amax, True)
    bad = int((~drains | ~largest).sum())
    check('best_donor: each cell\'s donor drains into it and is its largest', bad == 0, f'{bad} bad of {n0 * n1}',
          round(time.perf_counter() - t0, 2))


def test_flutes():
    t0 = time.perf_counter()
    from eidoblend.terrain.core import levels as L
    lv = L.plan_levels(1000.0, 128, (0.0, 0.0), None, None, None)[0]
    X, Y = lv.xy()
    h = 0.8 * X + 0.1 * Y + 50.0 * np.sin(Y / 200.0)              # a slope falling west, its contours wavy
    f = G.wall_flutes(h, lv, {}, 1)
    across = float(np.abs(np.diff(f, axis=0)).mean())             # along y: across the fall line
    along = float(np.abs(np.diff(f, axis=1)).mean())              # along x: down the fall line
    weak = float((f < 0).mean())
    check('wall flutes run down the fall line, couloirs a minority of the wall',
          across >= 2.0 * along and 0.1 <= weak <= 0.35,
          f'change across / along the fall line {across / max(along, 1e-12):.1f}, couloirs {weak * 100:.0f} %',
          round(time.perf_counter() - t0, 2))


def test_trunk():
    """The horseshoe's trunk river (valley_uplift): the same course for the same seed; its bed falls down-valley,
    stands bench_m over the fill's graded line through the main tile and reaches outlet_m at the coarsest level's
    edge; its pins hold a connected channel (8-connected from the head to the edge) at that bed."""
    t0 = time.perf_counter()
    from eidoblend.terrain import recipes as RG
    from eidoblend.terrain.core import levels as L
    _, stages = RG.get('alpine_valley').resolve({})
    vu = [s for s in stages if s.op == 'valley_uplift'][0].params
    tr = dict(G.TRUNK, **vu['shape']['trunk'])
    plan = L.plan_levels(8000.0, 256, (0.0, 0.0), 4, None, None)
    top = plan[0]
    win = (top.x0, top.y0, top.side)
    c, c2 = G.trunk_course(vu['shape'], win, 1), G.trunk_course(vu['shape'], win, 1)
    pts, bed = c['points'], c['bed']
    on = (np.abs(pts[:, 0] - top.x0 - 0.5 * top.side) < 0.5 * top.side) & \
         (np.abs(pts[:, 1] - top.y0 - 0.5 * top.side) < 0.5 * top.side)
    last = int(np.nonzero(on)[0].max())
    left = (top.y0 + top.side) - pts[:, 1]                     # the course drains north: the distance to the edge
    main = (np.abs(pts[:, 0]) < 4000.0) & (pts[:, 1] > -2000.0) & (pts[:, 1] < 4000.0)
    over = bed[main] - float(tr['grade']) * left[main]
    lv = plan[0]
    pins, m = G.trunk_pins(c, lv, FL.edge_pins(lv.n, np.zeros((lv.n, lv.n), F32)))
    # connected: every channel cell has a channel neighbour, and the channel reaches the down-valley edge
    nb = np.zeros_like(m)
    for dj in (-1, 0, 1):
        for di in (-1, 0, 1):
            if dj or di:
                nb |= np.roll(np.roll(m, dj, 0), di, 1)
    connected = bool(np.all(nb[m])) and bool(m[-1, :].any())
    held = bool(np.all(pins['pin_w'][m] == 1.0))
    check("trunk river: the same course for a seed, its bed falling down-valley, bench_m over the fill's grade line "
          "in the main tile, at outlet_m on the edge; its channel pinned and connected",
          np.array_equal(pts, c2['points']) and bool(np.all(np.diff(bed) <= 1e-9))
          and abs(float(np.median(over)) - float(tr['bench_m'])) <= 25.0
          and abs(float(bed[last]) - float(tr['outlet_m'])) <= 5.0 and connected and held,
          f"{c['s'][-1] / 1000:.1f} km, bed {bed[0]:.0f} m at the head, {np.median(over):.0f} m over the grade line in "
          f"the main tile (bench_m {tr['bench_m']:g}), {bed[last]:.1f} m at the edge; {int(m.sum())} channel cells at "
          f"{lv.cell:g} m", round(time.perf_counter() - t0, 2))


def test_drainage_receivers():
    """The ice's receivers (drainage_receivers): on rough ground with closed basins, and on the case that broke the
    tilted routing surface (a cell 1 mm above a broad flat it drains into), every interior cell has a way down and
    every path ends at the grid's edge (no pits, no cycles)."""
    t0 = time.perf_counter()
    rng = np.random.default_rng(6)
    n = 96
    rough = 200.0 * T.random_field((n, n), 0, 1, 12, smooth=2).astype(np.float64) + rng.random((n, n))
    case = np.full((n, n), 100.0)
    case[:, :] += 0.5 * np.arange(n)[None, :]                       # a slope falling west to the edge ...
    case[30:60, 30:70] = 120.0                                      # ... with a broad dead-flat bench on it
    case[45, 70] = 120.001                                         # a cell draining onto the bench by 1 mm, 40
    case[40:50, 29] = 119.0                                         # steps from where the bench spills west (the
    #                                                                 tilted routing surface leaves it a pit)
    bad = []
    for name, h in (('rough ground with basins', rough), ('a cell 1 mm above a broad flat', case)):
        recv, filled = G.drainage_receivers(h, 10.0)
        rk = recv.ravel().astype(np.int64)
        idx = np.arange(n * n)
        j, i = np.divmod(idx, n)
        nxt = np.full(n * n, -1, np.int64)
        for k in range(8):
            di, dj = T.OFF[k]
            sel = rk == k
            nxt[sel] = (j[sel] + dj) * n + (i[sel] + di)
        p = np.where(nxt >= 0, nxt, idx)
        for _ in range(16):
            p = p[p]
        inner = np.zeros((n, n), bool)
        inner[1:-1, 1:-1] = True
        pits = int(((recv < 0) & inner).sum())
        stuck = int((~np.isin(p, np.nonzero(rk < 0)[0])).sum())
        ends_inside = int(inner.ravel()[p].sum())
        if pits or stuck or ends_inside:
            bad.append(f'{name}: {pits} pits, {stuck} paths in cycles, {ends_inside} ending inside')
    check('drainage receivers: no pits, no cycles, every path ends at the edge', not bad, '; '.join(bad) or
          'rough ground with basins and a cell 1 mm above a broad flat both drain', round(time.perf_counter() - t0, 2))


def test_shoulder_cut():
    """The shoulder cut (u_carve twin, alpine_valley's glacial parameters) on a straight trunk trough cut into an old
    valley floor level with the river (Lauterbrunnen's old floor, which left flat strips along both lips) and into
    an old V-valley at 30 degrees: beyond each lip the ground rises from the lip with no rim (never falls outward)
    and no flat strip (8 degrees or more over its first 100 m); on the old floor the lip stands shoulder_cut H under
    it and beyond the cut's reach the ground is untouched."""
    t0 = time.perf_counter()
    from eidoblend.terrain import recipes as RG
    values, stages = RG.get('alpine_valley').resolve({})
    gp = [s for s in stages if s.op == 'glacial'][0].params
    cu = G.carve_uniforms(gp)
    W, H, sc = 0.5 * float(gp['trough_width_m']), float(gp['trough_depth_m']), float(gp['shoulder_cut'])
    n0, n1, cell = 6, 420, 10.0
    i0 = n1 // 2
    x = (np.arange(n1) + 0.5) * cell
    x0 = (i0 + 0.5) * cell
    zc = 1000.0
    d = H + sc * H                                               # overdeepen 1 plus the shoulder cut (centrelines)
    zf = zc - d
    fill = (zc - float(values['bench_m'])) - zf
    cand = np.full((n0, n1, 4), -1.0, F32)
    A = np.zeros((n0, n1, 4), F32)
    B = np.zeros((n0, n1, 4), F32)
    B[..., 0] = 1.0
    for j in range(n0):
        cand[j, :, 0] = j * n1 + i0
        A[j, i0] = (x0, (j + 0.5) * cell, zf, H)
        B[j, i0] = (W, 0.0, fill, 0.0)
    C = G.default_seed_c((n0, n1))
    C[:, i0] = (1.0, 1.0, sc, 0.0)
    uni = dict(cu, uDx=cell, uJoin=float(G._p(gp, 'join_m')), uTrim=float(G._p(gp, 'trim_m')), uMorAt=0.6,
               uMorW=0.07, uNCirq=0, uCirqExp=2.0, uCirqFloor=0.35, uCirqOpen=2.5, uCirqTilt=0.14,
               uBound=T.BOUND_OPEN)
    bad = []
    notes = []
    for name, old in (('an old valley floor level with the river', np.full(n1, zc)),
                      ('an old V-valley at 30 degrees', zc + math.tan(math.radians(30.0)) * np.abs(x - x0))):
        h = np.repeat(old[None, :], n0, 0).astype(F32)
        out = G.u_carve({'candT': cand, 'seedA': A, 'seedB': B, 'seedC': C, 'st': T.rgba(h, h - 2.0),
                         'cirq': G.cirque_texture(np.zeros((0, 11)), None),
                         'pin': T.rgba(np.zeros((n0, n1), F32), np.zeros((n0, n1), F32))}, uni)
        hn = out['outS'][2, :, 0].astype(np.float64)
        for side in (-1.0, 1.0):
            r = side * (x - x0)
            sel = (r >= W) & (r <= W * (1.0 + cu['uShCutW']) + 400.0)
            o = np.argsort(r[sel])
            prof_out = hn[sel][o]
            rs = r[sel][o]
            falls = float(np.min(np.diff(prof_out)))
            first = float(np.interp(W + 100.0, rs, prof_out) - np.interp(W, rs, prof_out)) / 100.0
            notes.append(f'{name}, {"west" if side < 0 else "east"}: rises {math.degrees(math.atan(first)):.1f} deg over '
                         f'its first 100 m, worst outward fall {max(-falls, 0.0):.3f} m')
            if falls < -1e-3 or first < math.tan(math.radians(8.0)):
                bad.append(notes[-1])
        if name.startswith('an old valley floor'):
            lip = float(np.interp(x0 + W, x, hn))
            far = np.abs(x - x0) > W * (1.0 + cu['uShCutW']) + 30.0
            untouched = float(np.max(np.abs(hn[far] - old[far]))) if far.any() else 0.0
            notes.append(f'lip {zc - lip:.0f} m under the old floor (shoulder cut {sc * H:.0f} m), beyond the cut '
                         f'untouched within {untouched:.4f} m')
            if abs((zc - lip) - sc * H) > 15.0 or untouched > 1e-3:
                bad.append(notes[-1])
    check('the shoulder cut: beyond the lip the ground rises from it, no rim and no flat strip; the old floor ends '
          'the cut at the lip, untouched beyond', not bad, '; '.join(notes), round(time.perf_counter() - t0, 2))


def test_lip_open():
    """lip_open on a trough section (rho from the trough's axis): a clean cliff with a shoulder rising behind its lip
    is left exactly as it is; a 40 m rim standing on the lip with a gutter behind it (what the protected lip strip
    became on the finer levels) comes down, so the ground rises from the lip, and nothing inside the trough or
    beyond the band moves."""
    t0 = time.perf_counter()
    cell, W = 8.0, 575.0
    x = (np.arange(-600, 600) + 0.5) * cell
    rho = np.abs(x) / W
    u = G.profile_uniforms({'trough_width_m': 1150.0, 'trough_depth_m': 830.0, 'wall_deg': 76.0, 'wall_toe': 0.4,
                            'wall_lip': 0.2, 'shoulder_width': 1.5, 'shoulder_rise': 0.3, 'shoulder_exp': 1.0})
    clean = 830.0 * G.prof(rho, u, np.float64)
    gutter = np.where((rho > 1.06) & (rho < 1.25), -60.0 * np.sin(np.pi * (rho - 1.06) / 0.19), 0.0)
    rim = np.where((rho >= 0.99) & (rho <= 1.06), 40.0 * np.sin(np.pi * (rho - 0.99) / 0.07), 0.0)
    bad = []
    for name, prof_ in (('a clean lip', clean), ('a rim and gutter', clean + rim + gutter)):
        h = np.repeat(prof_[None, :], 5, 0)
        rr = np.repeat(rho[None, :], 5, 0)
        h1, drop = G.lip_open(h, rr, cell, 100.0)
        row, d = h1[2], drop[2]
        inside = rho < 0.95
        beyond = rho > 1.5
        moved_outside_band = float(np.max(np.abs(d[inside | beyond])))
        if name == 'a clean lip':
            if float(np.max(np.abs(d))) > 1e-6:
                bad.append(f'{name}: moved by {np.max(np.abs(d)):.3f} m')
        else:
            east = (x > 0) & (rho >= 1.0) & (rho <= 1.3)
            seg = row[east]
            rim_left = float(np.max(seg) - max(seg[-1], seg[0]))
            lip_z = float(np.interp(W, x, row))
            beh = float(np.min(row[(x > 0) & (rho > 1.0) & (rho < 1.3)]))
            if lip_z - beh > 5.0 or moved_outside_band > 1e-6:
                bad.append(f'{name}: the lip stands {lip_z - beh:.1f} m over the ground behind it after the opening '
                           f'(rim {rim_left:.1f} m), outside the band moved {moved_outside_band:.3g} m')
    check('lip_open: a clean lip untouched; a rim on the lip comes down to the ground behind it', not bad,
          '; '.join(bad) or 'clean lip exact; the 40 m rim levelled to the gutter behind it',
          round(time.perf_counter() - t0, 2))


def test_head_taper():
    """head_distance: each seed's distance up its main stem to its stream's head (0 at heads), and the recipe's
    centrelines tapering a trough in from its head (head_taper_factor: W, H and the overdeepening grow from a tenth
    of their size at the head to full size)."""
    t0 = time.perf_counter()
    surf, cell = surface(n=80, cell=40.0, seed=9)
    recv = G.d8_receivers(surf, cell)
    A, _ = G.ice_flux_converge(FL.device('twin'), surf, np.ones_like(surf), cell, recv, 0.0,
                               params={'ice_width_m': 0.0}, check=32)
    st = G.streams(A >= 30 * cell * cell, recv, A)
    jj, ii = np.divmod(st['idx'], surf.shape[1])
    x, y = (ii + 0.5) * cell, (jj + 0.5) * cell
    dist = G.head_distance(st, x, y)
    m = st['main']
    has = m >= 0
    seg = np.hypot(x - x[np.maximum(m, 0)], y - y[np.maximum(m, 0)])
    chain_ok = bool(np.allclose(dist[has], dist[m[has]] + seg[has])) and bool(np.all(dist[~has] == 0.0))
    W = np.full(dist.shape, 300.0)
    tp = G.head_taper_factor(dist, W, 2.0)
    order = np.argsort(dist)
    grows = (bool(np.allclose(tp[~has], G.HEAD_TAPER_MIN)) and G.HEAD_TAPER_MIN > 0.0
             and bool(np.all(np.diff(tp[order]) >= -1e-12)) and bool(np.allclose(tp[dist >= 600.0], 1.0)))
    check('head_distance runs up each main stem to its head; the taper grows a trough in from a tenth of its size at '
          'the head, never from nothing', chain_ok and grows,
          f'{st["idx"].size} seeds, {int((~has).sum())} heads, longest stem {dist.max():.0f} m, factor at the heads '
          f'{tp[~has].min():.2f}', round(time.perf_counter() - t0, 2))


def v_valley(n=64, cell=125.0):
    """A river valley 8 km long draining north (2 % gradient, 30-degree sides, ridges 2 km up), with two V
    tributaries a side: the coarsest level's kind of surface, small."""
    from eidoblend.terrain.core import levels as L
    lv = L.plan_levels(n * cell, n, (0.0, 0.0), None, None, None)[0]
    X, Y = lv.xy()
    river = 300.0 + 0.02 * (lv.side / 2 - Y)
    tan30 = math.tan(math.radians(30.0))
    h = river + tan30 * np.abs(X)
    for side in (-1.0, 1.0):
        for yt in (-1800.0, 1800.0):
            trib = river + 0.08 * np.clip(side * X, 0.0, None) + 0.7 * tan30 * np.abs(Y - yt)
            h = np.where(side * X > 400.0, np.minimum(h, np.maximum(trib, river + tan30 * 400.0)), h)
    return lv, (np.minimum(h, 2300.0) + 2.0 * T.random_field((n, n), 0, 1, 3, smooth=2)).astype(F32)


def test_head_taper_carve():
    """The carve with alpine_valley's glacial stage (its head taper, shoulder cut, box walls) on a small V valley,
    twin device: every seed a trough of the recipe's shape (H > 0, H / W the untapered ratio within the wobble), so
    no seed's target is a level plane, and every carved cell carved by a trough within reach (the best candidate's
    rho under 1 + the cap's and the shoulder cut's widths). With seeds of no size at the stream heads, their level
    planes ranked first everywhere and no trough was cut (11-13)."""
    from eidoblend.terrain.core.fields import Fields
    from eidoblend.terrain.recipes import alpine_valley as AV
    t0 = time.perf_counter()
    dev = FL.device('twin')
    lv, h = v_valley()
    _, stages = AV.ALPINE_VALLEY.resolve({})
    params = dict([s for s in stages if s.op == 'glacial'][0].params, ela_m=500.0, trough_depth_m=600.0,
                  cirques=False, channel_area_m2=1.0e6)
    recv, _ = G.drainage_receivers(h, lv.cell)
    b = G.mass_balance(h, 0.0, params)
    Q, _ = G.ice_flux_converge(dev, h, b, lv.cell, recv, 0.0, params=params, check=32)
    A, _ = G.ice_flux_converge(dev, h, np.ones_like(b), lv.cell, recv, 0.0, params=dict(params, ice_width_m=0.0),
                               check=32)
    cl = G.centrelines(h, Q, A, recv, lv, lv, params, 0.0, seed=1)
    ratio = cl['H'] / np.maximum(cl['W'], 1e-9)
    r0 = cl['Ht'] / cl['Wt']
    shape_ok = bool(np.all(cl['H'] > 0.0)) and bool(np.all((ratio > 0.6 / 1.4 * r0) & (ratio < 1.4 / 0.6 * r0)))
    fields = Fields(lv, {'h': h.copy(), 'bed': h.copy()})
    ctx = FL.StageContext(plan=[lv], index=0, level=lv, prepass=None, fresh=False, role='grow',
                          pins=FL.edge_pins(lv.n, h), shared={}, seed=1, base_elevation_m=0.0, device=dev,
                          log=lambda m: None)
    G.carve_level(fields, lv, params, 1, ctx, dev)
    rho = np.asarray(fields['trough_rho'], np.float64)
    cut = np.asarray(h, np.float64) - np.asarray(fields['h'], np.float64)
    reach = 1.0 + max(float(params['cut_width']), float(params['shoulder_cut_width']))
    carved = cut > 1.0
    own = float((rho[carved] <= reach + 0.05).mean()) if carved.any() else 0.0
    trough = float(np.asarray(fields['trough']).mean())
    ok = shape_ok and own >= 0.99 and trough > 0.05 and float(cut.max()) < float(np.ptp(h))
    check("the recipe's carve with its head taper: every seed a trough of the recipe's shape, every carved cell "
          "carved by a trough within reach", ok,
          f"{cl['idx'].size} seeds, H/W {ratio.min():.2f}..{ratio.max():.2f} (untapered {r0:.2f}); {own * 100:.1f} % "
          f"of the {int(carved.sum())} carved cells within rho {reach:.1f} of their best seed; trough "
          f"{trough * 100:.1f} % of the grid, deepest cut {cut.max():.0f} m", round(time.perf_counter() - t0, 2))


def test_sharpen_walls():
    """sharpen_walls: a trough at 15 degrees to the grid, carved on 31.25 m cells (the coarsest level's) with the
    recipe's cross-section, inherited at 15.6 m as a finer level inherits it (Catmull-Rom h and bed, bilinear the
    rest); the sharpening brings its walls to the cross-section evaluated at 15.6 m directly (the upsampled walls are
    off by tens of metres at the toe and the lip), and leaves the floor, the ground beyond the lip and the pinned
    border band as they were."""
    from eidoblend.terrain.core import grid as Gd
    from eidoblend.terrain.recipes import alpine_valley as AV
    t0 = time.perf_counter()
    _, stages = AV.ALPINE_VALLEY.resolve({})
    params = [s for s in stages if s.op == 'glacial'][0].params
    pu = G.profile_uniforms(params)
    W, H = 0.5 * float(params['trough_width_m']), float(params['trough_depth_m'])
    ff = pu['uFloorFrac']
    a = math.radians(15.0)

    def rho_at(n, cell):
        c = (np.arange(n) + 0.5) * cell - 0.5 * n * cell
        X, Y = np.meshgrid(c, c)
        return np.abs(X * math.cos(a) - Y * math.sin(a)) / W

    def target(rho, rock=False):
        k = np.ones_like(rho)
        return G.trough_target(rho, 100.0 * k, H * k, ff * k, 40.0 * k, pu['uFloorRise'] * k, pu, rock=rock)

    n, cell = 64, 31.25
    rc = rho_at(n, cell)
    parent = dict(h=target(rc), bed=target(rc, rock=True), trough_rho=rc, trough_zf=np.full((n, n), 100.0),
                  trough_H=np.full((n, n), H), trough_ff=np.full((n, n), ff), trough_fill=np.full((n, n), 40.0),
                  trough_rise=np.full((n, n), pu['uFloorRise']), trough_sharp=np.ones((n, n)),
                  carve=np.full((n, n), 300.0))
    child = {k: Gd.crop_upsample2(v, 0, 0, n, 'catmull' if k in ('h', 'bed') else 'bilinear').astype(np.float64)
             for k, v in parent.items()}
    before = child['h'].copy()
    pin_w = np.zeros((2 * n, 2 * n))
    pin_w[:6, :] = pin_w[-6:, :] = pin_w[:, :6] = pin_w[:, -6:] = 1.0
    G.sharpen_walls(child, None, params, pin_w)
    rf = rho_at(2 * n, 0.5 * cell)
    exact = target(rf)
    inner = np.zeros(rf.shape, bool)
    inner[8:-8, 8:-8] = True
    walls = inner & (rf > ff) & (rf < 1.0)
    err0 = float(np.abs(before - exact)[walls].max())
    err1 = float(np.abs(child['h'] - exact)[walls].max())
    floor = float(np.abs(child['h'] - before)[inner & (rf < ff - 0.08)].max())
    beyond = float(np.abs(child['h'] - before)[inner & (rf > 1.2)].max())
    pinned = float(np.abs(child['h'] - before)[pin_w > 0].max())
    ok = err1 <= 0.25 * err0 and err1 < 15.0 and floor < 0.5 and beyond < 1e-6 and pinned < 1e-9 and \
        bool(np.all(np.asarray(child['bed']) <= np.asarray(child['h']) + 1e-6))
    check('sharpen_walls: a finer level inherits a trough and gets its walls back at its own resolution, the floor '
          '(but for its fans\' curvature), the ground beyond the lip and the pinned band untouched', ok,
          f'the walls off the 15.6 m cross-section by {err0:.1f} m upsampled, {err1:.1f} m sharpened; the floor moved '
          f'{floor:.2g} m (the fans), beyond the lip {beyond:.2g} m, the pinned band {pinned:.2g} m',
          round(time.perf_counter() - t0, 2))


def main():
    for fn in (test_jump_flood, test_mass_balance, test_profile, test_graded_fill, test_best_donor, test_flutes,
               test_trunk, test_drainage_receivers, test_shoulder_cut, test_lip_open, test_head_taper,
               test_head_taper_carve, test_sharpen_walls):
        t0 = time.perf_counter()
        try:
            fn()
        except Exception as e:                                         # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(fn.__name__, False, f'{type(e).__name__}: {e}')
        took = time.perf_counter() - t0
        check(f'{fn.__name__} under 5 s', took < 5.0, f'{took:.2f} s')
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'twin_tests.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(results=RESULTS, failed=FAILED), f, indent=1)
    print(f"{len(RESULTS) - len(FAILED)}/{len(RESULTS)} passed", flush=True)
    sys.exit(1 if FAILED else 0)


main()
