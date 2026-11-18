"""The plant planner's checks (surfacing design 5.4, package 4, item 1 and 4), in plain Python: numpy, no Blender, no
GPU. They run on a small synthetic valley (_ground.py) with the family's own masks.

    python blender/tests/terrain/plants/test_plants.py [--only a,b] [--sheet]

  determinism   the same inputs give the same bytes (two plans, saved, compared byte for byte)
  radius        a larger radius keeps every spot of the smaller one, byte for byte; another focus keeps the spots
                both plans cover
  hard_core     no two plants of one priority closer than 0.75 x the sum of their radii; none within a placed
                plant's foot; the planner's order equals a plain sequential pass over the same candidates
  stature       krummholz: toward the treeline the trees stay low and stand closer
  density       stems per hectare where a species is at home lie in the ecotope's range_per_ha
  ground        every spot stands on height_at, with the triangle's normal; none on water or in a flatten area
  format        save / load round-trip; a Node reader (read_plants.mjs: fs and Float32Array) reads the same numbers
  pattern       the trees' pair correlation: none below the hard core, clustered at the cluster scale
  cover         the cover rasters: canopy from the placed crowns, canopy_expected from the density, shrubs; and
                canopy_far, the crowns beyond the instanced forest, taking over across its hand-off band; and
                expected_cover with no plan, the same rule
  ecotopes      every ecotope, recipe and place resolves, checks, and plans on the synthetic ground
  distance      the stream-distance transform against brute force
  around        understory seeded around another species' plants stands around them
  surface       with the surface bake's SurfaceData: maps read as SurfaceData.at reads them, rules on bake maps,
                snowpack kept clear, the cover rasters handed to the bake (add_maps) and read back
  edges         no step at a window edge: stems per hectare either side of every hero window's edge within 10 %
                (the judge's edge_density on the saved spots; edges_real.py does the same on real terrains)
  timing        10^4 trees and 10^5 shrubs planned within the design's 10 s
  rocks         the rock scatter with the toe bias off is what it was; on, the smallest rock grows toward the toe

--sheet also writes out/plants/synthetic_spots.png: the plan seen from above (to look at).
"""
import copy
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _ground as G  # noqa: E402

from eidoblend.terrain.build import ecotopes as E  # noqa: E402
from eidoblend.terrain.build import palettes as P  # noqa: E402
from eidoblend.terrain.build import plants as PL  # noqa: E402

RESULTS = []
F = {n: i for i, n in enumerate(PL.FIELDS)}
QUIET = dict(log=None)


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok)))
    print(('PASS ' if ok else 'FAIL ') + name + (': ' + detail if detail else ''), flush=True)
    return ok


def rows(a):
    """The records as a set of their bytes."""
    a = np.ascontiguousarray(a, '<f4')
    return {a[i].tobytes() for i in range(len(a))}


def file_bytes(spots, folder, stem='p'):
    paths = spots.save(os.path.join(folder, stem))
    return {os.path.basename(p): open(p, 'rb').read() for p in paths}


# ------------------------------------------------------------------------------------------------- checks ---

def test_determinism(t, tmp):
    a = PL.plan_plants(t, 'alpine', seed=4, **QUIET)
    b = PL.plan_plants(t, 'alpine', seed=4, **QUIET)
    fa, fb = file_bytes(a, os.path.join(tmp, 'a')), file_bytes(b, os.path.join(tmp, 'b'))
    check('determinism: two plans of the same inputs give the same files', fa.keys() == fb.keys()
          and all(fa[k] == fb[k] for k in fa),
          ', '.join(f'{k} {len(v):,} B' for k, v in fa.items()))
    c = PL.plan_plants(t, 'alpine', seed=5, **QUIET)
    check('determinism: another seed gives other spots',
          not rows(a.array('spruce')) & rows(c.array('spruce')), f"{a.count('spruce'):,} vs {c.count('spruce'):,}")
    return a


def test_radius(t):
    small = PL.plan_plants(t, 'alpine', radius_m=300.0, seed=4, **QUIET)
    big = PL.plan_plants(t, 'alpine', radius_m=520.0, seed=4, **QUIET)
    for name in small.names():
        s, b = rows(small.array(name)), rows(big.array(name))
        check(f'radius: {name}: every spot within 300 m is among those within 520 m, byte for byte',
              s <= b and len(s) == small.count(name), f'{len(s):,} of {len(b):,}; missing {len(s - b)}')
    # another focus: the trees both plans return in full (well inside both radii, where neither fades them out
    # nor thins them by distance) are the same trees
    fa, fb = (60.0, -120.0), (150.0, -40.0)
    A = PL.plan_plants(t, 'alpine', focus=fa, radius_m=500.0, seed=4, **QUIET)
    B = PL.plan_plants(t, 'alpine', focus=fb, radius_m=500.0, seed=4, **QUIET)
    for name in ('spruce', 'maple'):
        a, b = A.array(name), B.array(name)

        def common(r):
            return r[(np.hypot(r[:, 0] - fa[0], r[:, 1] - fa[1]) < 250.0) & (np.hypot(r[:, 0] - fb[0], r[:, 1] - fb[1]) < 250.0)]
        ca, cb = rows(common(a)), rows(common(b))
        check(f'radius: {name}: the spots two focuses both cover are the same', ca == cb and len(ca) > 0,
              f'{len(ca):,} and {len(cb):,}')


def _closest_violation(xa, ya, ra, xb, yb, rb, same):
    """The worst overlap between two sets: min over pairs of distance - 0.75 (ra + rb) (negative = too close)."""
    i, j, d = PL._pairs(xa, ya, xb, yb, 2.0 * PL.CORE_FACTOR * float(max(ra.max(), rb.max())) + 0.01)
    if same:
        k = i < j
        i, j, d = i[k], j[k], d[k]
    if not len(d):
        return 1.0, 0
    gap = d - PL.CORE_FACTOR * (ra[i] + rb[j])
    return float(gap.min()), int((gap < -0.003).sum())


def test_hard_core(t, spots):
    eco = E.get('alpine')
    by = {s['name']: s for s in eco['species']}
    xs, ys, rs, rf = {}, {}, {}, {}
    for n in spots.names():
        a = spots.array(n).astype(np.float64)
        xs[n], ys[n] = a[:, 0], a[:, 1]
        rs[n] = by[n]['core_m'] * a[:, 4]
        rf[n] = by[n]['foot_m'] * a[:, 4]
    trees = ['spruce', 'maple']
    x = np.concatenate([xs[n] for n in trees])
    y = np.concatenate([ys[n] for n in trees])
    r = np.concatenate([rs[n] for n in trees])
    gap, bad = _closest_violation(x, y, r, x, y, r, True)
    check('hard core: no two trees closer than 0.75 x the sum of their crown radii', bad == 0,
          f'{len(x):,} trees, the tightest pair {gap * 100:+.1f} cm from the limit')
    # the planner against a plain sequential pass over the same candidates
    rng = np.random.default_rng(3)
    n = 4000
    px, py = rng.uniform(0, 120, n), rng.uniform(0, 120, n)
    pr = rng.uniform(0.6, 2.4, n)
    rank = rng.permutation(n)
    acc, certain = PL._hard_core(px, py, pr, rank, np.zeros(n, bool))
    ref = np.zeros(n, bool)
    for k in np.argsort(rank):
        d = np.hypot(px[ref] - px[k], py[ref] - py[k])
        if not (d < PL.CORE_FACTOR * (pr[ref] + pr[k])).any():
            ref[k] = True
    check('hard core: the planner accepts what a sequential pass in mark order accepts',
          bool((acc == ref).all()) and bool(certain.all()), f'{int(acc.sum())} of {n} accepted')
    # a margin whose candidates are unknown: whatever the planner calls certain does not change when they appear
    inner = (px > 30) & (px < 90) & (py > 30) & (py < 90)
    sub = (px > 18) & (px < 102) & (py > 18) & (py < 102)
    edge = sub & ~((px > 18 + 3.6) & (px < 102 - 3.6) & (py > 18 + 3.6) & (py < 102 - 3.6))
    acc2, cert2 = PL._hard_core(px[sub], py[sub], pr[sub], rank[sub], edge[sub])
    same = acc2[cert2] == ref[sub][cert2]
    check('hard core: a decision called certain is the full plan\'s decision',
          bool(same.all()) and bool(cert2[inner[sub]].mean() > 0.9),
          f'{int(cert2.sum())} certain of {int(sub.sum())}, {100 * cert2[inner[sub]].mean():.1f} % of the inner ones')


def test_feet(t):
    """Shrubs and trees: a lower priority keeps clear of the feet of the plants placed before it."""
    eco = dict(title='test', species=[
        dict(name='tree', kind='tree', source=('seedthree', 'douglasFir', {}, [1]), size_m=(8.0, 20.0), core_m=3.0,
             foot_m=1.5, cluster=dict(parents_per_ha=150.0, mu=4.0, sigma_m=6.0), density='0.06'),
        dict(name='shrub', kind='shrub', source=('seedthree', 'blackbrush', {}, [1]), size_m=(0.5, 1.2), core_m=0.7,
             max_cell_m=None, cluster=dict(parents_per_ha=900.0, mu=5.0, sigma_m=3.0), density='0.45',
             shade=dict(tolerance=1.0, radius=1.0)),
    ])
    spots = PL.plan_plants(t, eco, radius_m=160.0, **QUIET)
    tr, sh = spots.array('tree').astype(np.float64), spots.array('shrub').astype(np.float64)
    gap, bad = _closest_violation(sh[:, 0], sh[:, 1], 0.7 * sh[:, 4], tr[:, 0], tr[:, 1], 1.5 * tr[:, 4], False)
    check('hard core: no shrub within 0.75 x (its radius + a tree\'s foot) of a tree', bad == 0 and len(sh) > 500,
          f'{len(sh):,} shrubs, {len(tr):,} trees, the tightest pair {gap * 100:+.1f} cm from the limit')
    gap, bad = _closest_violation(sh[:, 0], sh[:, 1], 0.7 * sh[:, 4], sh[:, 0], sh[:, 1], 0.7 * sh[:, 4], True)
    check('hard core: no two shrubs closer than 0.75 x the sum of their radii', bad == 0,
          f'the tightest pair {gap * 100:+.1f} cm from the limit')
    # shade: a shade-intolerant shrub thins out under the crowns
    eco['species'][1]['shade'] = dict(tolerance=0.0, radius=1.0)
    shy = PL.plan_plants(t, eco, radius_m=160.0, **QUIET).array('shrub').astype(np.float64)

    def under(a):
        i, j, d = PL._pairs(a[:, 0], a[:, 1], tr[:, 0], tr[:, 1], 3.0)
        m = np.zeros(len(a), bool)
        m[i[d < 0.6 * 3.0 * tr[j, 4]]] = True
        return float(m.mean())
    check('shade: a shrub with no shade tolerance stands under the crowns far less than a tolerant one',
          under(shy) < 0.4 * under(sh), f'{100 * under(shy):.1f} % under a crown against {100 * under(sh):.1f} %')


def test_stature(t):
    """Krummholz (design 4.2): toward the treeline the spruce stays low, and stunted trees stand closer."""
    eco = E.get('alpine')
    eco['constants'] = dict(eco['constants'], treeline_m=1350.0)      # the line inside the valley's altitudes
    for s in eco['species']:
        s['max_count'] = 10 ** 7                        # no scene budget: it would drop the smallest trees first
    a = PL.plan_plants(t, eco, seed=4, **QUIET).array('spruce').astype(np.float64)
    alt = a[:, 2] + float(t.info['base_elevation_m'])
    near_line = alt > 1350.0 - 120.0
    below = alt < 1350.0 - 450.0
    s_near, s_below = float(a[near_line, 4].mean()), float(a[below, 4].mean())
    gap, bad = _closest_violation(a[:, 0], a[:, 1], 2.3 * a[:, 4], a[:, 0], a[:, 1], 2.3 * a[:, 4], True)
    check('stature: toward the treeline the spruce stays low (krummholz), and keeps its hard core',
          near_line.sum() > 50 and below.sum() > 50 and s_near < 0.6 * s_below and bad == 0,
          f'mean height {s_near * 32:.1f} m within 120 m of the line ({int(near_line.sum())} trees), '
          f'{s_below * 32:.1f} m more than 450 m below it ({int(below.sum())}); the tightest pair '
          f'{gap * 100:+.1f} cm from the core')


def test_density(t, spots):
    eco = E.get('alpine')
    for s in eco['species']:
        st = spots.stats[s['name']]
        lo, hi = s['range_per_ha']
        ok = st['per_ha_home'] is not None and lo <= st['per_ha_home'] <= hi
        check(f"density: {s['name']}: stems per hectare where it is at home within {lo:g}-{hi:g}", ok,
              f"{st['per_ha_home']} per ha over {st['home_m2'] / 1e4:.2f} ha ({st['home_count']:,} plants; "
              f"{st['candidates']:,} candidates, {st['after_density']:,} after the density, {st['kept']:,} kept)")
        check(f"density: {s['name']}: the density stays under the cluster process's ceiling", st['clipped'] < 0.02,
              f"{100 * st['clipped']:.1f} % of candidates clipped, the largest density "
              f"{st['density_max'] * 1e4:.0f} per ha")


def test_ground(t, spots):
    worst = 0.0
    n_all = 0
    for n in spots.names():
        a = spots.array(n)
        z = t.height_at(a[:, 0].astype(np.float64), a[:, 1].astype(np.float64))
        slope = np.hypot(a[:, 7], a[:, 8]) / np.maximum(a[:, 9], 1e-6)
        # a float32 position is within 1 mm of the planned one: allow that times the slope, plus float32's z
        tol = 0.002 * (1.0 + slope) + 2e-4 * np.maximum(np.abs(z), 1.0) * 0.1
        worst = max(worst, float(np.max(np.abs(a[:, 2] - z) - tol)) if len(a) else 0.0)
        n_all += len(a)
        nn = t.normal_at(a[:, 0].astype(np.float64), a[:, 1].astype(np.float64))
        check(f'ground: {n}: the normal is the terrain\'s, unit, pointing up',
              len(a) == 0 or (float(np.abs(np.linalg.norm(a[:, 7:10], axis=1) - 1).max()) < 1e-5
                              and float((a[:, 9] > 0).mean()) == 1.0
                              and float(np.abs(a[:, 7:10] - nn).max()) < 2e-3))
        lv = a[:, 11].astype(int)
        cells = np.array([l.cell for l in t.levels])[lv]
        fin = np.zeros(len(a), int)
        for i, l in enumerate(t.levels):
            fin[np.asarray(l.contains(a[:, 0].astype(np.float64), a[:, 1].astype(np.float64)))] = i
        check(f'ground: {n}: the level recorded is the finest level holding the spot', bool((fin == lv).all()),
              f'cells {cells.min():g}-{cells.max():g} m' if len(a) else 'no spots')
    check('ground: every spot stands on height_at (none floats, none is buried)', worst <= 0.0,
          f'{n_all:,} spots; the worst is {worst * 1000:+.2f} mm past the float32 tolerance')
    # a species that keeps to fine levels (max_cell_m; every kind's default is any level) stands on no coarser one,
    # out past the finest window (128 m across)
    eco = E.get('alpine')
    eco['species'] = [dict(s, max_cell_m=0.5, max_radius_m=150.0, max_count=10 ** 6)
                      for s in eco['species'] if s['name'] == 'meadow grass']
    grass = PL.plan_plants(t, eco, seed=4, **QUIET).array('meadow grass')
    cells = np.array([l.cell for l in t.levels])[grass[:, 11].astype(int)]
    check('ground: a species keeps to the levels its max_cell_m allows', len(grass) > 0 and bool((cells <= 0.5).all()),
          f'{len(grass):,} bunches within 150 m, on cells of {cells.min():g}-{cells.max():g} m (max_cell_m 0.5)')
    # a flatten area and water are kept clear
    t2 = G.Ground(t.levels, [dict(m) for m in t.masks._stack], t._height, dict(t.info))
    t2.flats = [dict(at=[100.0, -100.0], radius=40.0)]
    for i, m in enumerate(t2.masks._stack):
        X, Y = t.levels[i].xy()
        m['water'] = np.where(np.hypot(X + 250.0, Y - 150.0) < 80.0, 1.5, 0.0).astype(np.float32)
    sp2 = PL.plan_plants(t2, eco, radius_m=600.0, **QUIET)
    a = np.concatenate([sp2.array(n) for n in sp2.names()])
    check('ground: no plant in a flatten area', not (np.hypot(a[:, 0] - 100.0, a[:, 1] + 100.0) < 40.0).any())
    check('ground: no plant on water', not (np.hypot(a[:, 0] + 250.0, a[:, 1] - 150.0) < 76.0).any(),
          f'{len(a):,} plants planned around a 160 m pond')


def test_format(t, spots, tmp):
    base = os.path.join(tmp, 'fmt', 'valley')
    paths = spots.save(base)
    back = PL.PlantSpots.load(base)
    same = all(np.array_equal(back.array(n), spots.array(n)) for n in spots.names())
    check('format: save then load gives the same records', same and back.names() == spots.names(),
          f'{len(paths)} files, {sum(os.path.getsize(p) for p in paths):,} B')
    a, b = spots.cover('main'), PL.PlantSpots.load(base, terrain=t).cover('main')
    check('format: loaded spots give the plan\'s cover rasters (the kept-cover profile and crowns travel in the file)',
          all(np.array_equal(a[k], b[k]) for k in a), ', '.join(sorted(a)))
    meta = json.load(open(paths[0], encoding='utf-8'))
    need = {'format', 'frame', 'terrain', 'focus', 'seed', 'ecotope', 'species'}
    sp = meta['species'][0]
    check('format: the description carries the design\'s keys',
          need <= set(meta) and meta['format'] == PL.FORMAT
          and {'name', 'kind', 'source', 'size_m', 'count', 'file', 'fields'} <= set(sp)
          and sp['fields'] == list(PL.FIELDS) and 'seedthree' in sp['source'] and 'seeds' in sp['source']
          and len(meta['terrain']['levels']) == len(t.levels) and len(meta['terrain']['levels'][0]) == 5,
          f"{meta['ecotope']}, levels {len(meta['terrain']['levels'])}, source {sp['source']}")
    # where a plan is kept: in the terrain's cache entry, one name per plan
    from types import SimpleNamespace
    from eidoblend.terrain.core import cache as C
    tk = G.Ground(t.levels, t.masks._stack, t._height, dict(t.info, cache_key='plants-test-key'))
    b = [PL.cache_base(tk, 'alpine', seed=4), PL.cache_base(tk, 'alpine', seed=4), PL.cache_base(tk, 'alpine', seed=5),
         PL.cache_base(tk, 'alpine', seed=4, radius_m=300.0), PL.cache_base(tk, 'alpine', seed=4,
                                                                          data=SimpleNamespace(key='bake-1'))]
    check('format: a plan\'s place in the terrain cache is its entry\'s folder, one name per plan',
          os.path.dirname(b[0]) == C.Cache('plants-test-key').path and b[0] == b[1] and len(set(b[1:])) == 4
          and PL.cache_base(t, 'alpine') is None, os.path.basename(b[0]))
    node = shutil.which('node')
    if not node:
        print('[skip] format: the Node reader (no node on PATH)')
        return
    out = os.path.join(tmp, 'fmt', 'node.json')
    r = subprocess.run([node, os.path.join(HERE, 'read_plants.mjs'), paths[0], out, os.path.join(tmp, 'fmt', 'echo')],
                       capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if r.returncode != 0:
        check('format: the Node reader runs', False, (r.stdout + r.stderr)[-400:])
        return
    js = json.load(open(out, encoding='utf-8'))
    ok = True
    detail = []
    for s in js['species']:
        a = spots.array(s['name']).astype(np.float64)
        echo = open(os.path.join(tmp, 'fmt', 'echo', s['file']), 'rb').read()
        orig = open(os.path.join(tmp, 'fmt', s['file']), 'rb').read()
        ok &= s['count'] == len(a) and s['stride'] == len(PL.FIELDS) and echo == orig
        for k, name in enumerate(PL.FIELDS):
            col = a[:, k]
            ok &= (not len(a)) or (abs(s['sum'][name] - float(col.sum())) <= 1e-6 * max(1.0, float(np.abs(col).sum()))
                                   and s['min'][name] == float(col.min()) and s['max'][name] == float(col.max()))
        if len(a):
            ok &= np.allclose(s['first_three'], [a[0, 0], a[0, 2], -a[0, 1]]) and s['first_three_yaw'] == a[0, 3]
        detail.append(f"{s['name']} {s['count']:,}")
    check('format: a plain Node reader (fs, Float32Array) reads the same records and writes back the same bytes', ok,
          ', '.join(detail))


def pair_correlation(x, y, edges, window):
    """g(r) of points inside a window (x0, y0, x1, y1), no edge correction beyond counting only pairs whose first
    point lies `max r` inside the window (so every ring is whole)."""
    x0, y0, x1, y1 = window
    rmax = float(edges[-1])
    inner = (x > x0 + rmax) & (x < x1 - rmax) & (y > y0 + rmax) & (y < y1 - rmax)
    inside = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
    lam = inside.sum() / ((x1 - x0) * (y1 - y0))
    i, j, d = PL._pairs(x[inner], y[inner], x[inside], y[inside], rmax)
    d = d[d > 1e-9]
    cnt, _ = np.histogram(d, edges)
    ring = math.pi * (edges[1:] ** 2 - edges[:-1] ** 2)
    return cnt / np.maximum(inner.sum() * lam * ring, 1e-12)


def test_pattern(t):
    # a uniform density, so the pattern is the process's own (clusters and hard core), not the terrain's: the species
    # grows on every substrate, or the valley's bare steep sides would keep it off a quarter of the window and the
    # pairs would gather at the scale of the valley (g(r) 1.2 out to 60 m)
    eco = dict(title='test', species=[dict(name='tree', kind='tree', source=('seedthree', 'douglasFir', {}, [1]),
                                           size_m=(14.0, 30.0), core_m=2.3,
                                           cluster=dict(parents_per_ha=40.0, mu=6.0, sigma_m=7.0), density='0.024',
                                           fade=(1.0, 1.0), lod_m_per_m=0.0,
                                           on=('water', 'snow', 'rock', 'talus', 'sand'))])
    a = PL.plan_plants(t, eco, focus=(0.0, 0.0), radius_m=900.0, **QUIET).array('tree').astype(np.float64)
    edges = np.array([0.0, 1.5, 2.5, 3.5, 5.0, 7.0, 10.0, 14.0, 20.0, 30.0, 45.0, 60.0])
    g = pair_correlation(a[:, 0], a[:, 1], edges, (-600.0, -600.0, 600.0, 600.0))
    smallest = PL.CORE_FACTOR * 2 * 2.3 * float(a[:, 4].min())
    check('pattern: no pair below the hard core', g[0] == 0.0 and g[1] < 0.05,
          f'g(0-1.5 m) = {g[0]:.3f}, g(1.5-2.5 m) = {g[1]:.3f}; the smallest pair distance allowed {smallest:.2f} m')
    # a Thomas process of 40 parents per ha at sigma 7 m: g(r) = 1 + exp(-r^2 / 4 sigma^2) / (4 pi sigma^2 kappa),
    # 1.37 at 4 m and 1.02 at 25 m; the hard core thins the closest offspring, so the clusters read a little looser
    thomas = 1.0 + np.exp(-(0.5 * (edges[1:] + edges[:-1])) ** 2 / (4 * 49.0)) / (4 * math.pi * 49.0 * 40e-4)
    check('pattern: clustered at the cluster scale (the Thomas process\'s shape), even beyond 4 sigma',
          g[3:6].mean() > 1.15 and g[3] > g[6] > g[8] and float(np.abs(g[-2:] - 1.0).max()) < 0.05,
          'g(r): ' + ', '.join(f'{lo:g}-{hi:g} m {v:.2f} ({w:.2f})' for lo, hi, v, w
                               in zip(edges[:-1], edges[1:], g, thomas)) + ' (in brackets the process without its core)')


def test_cover(t, spots):
    c = spots.cover('main')
    n = t.levels[0].n
    ok = all(c[k].shape == (n, n) and float(c[k].min()) >= 0.0 and float(c[k].max()) <= 1.0
             for k in ('canopy', 'canopy_expected', 'canopy_far', 'shrubs', 'shrubs_far'))
    check('cover: five rasters per level, 0..1, the level\'s size', ok,
          ', '.join(f'{k} mean {float(v.mean()):.3f} max {float(v.max()):.2f}' for k, v in c.items()))
    # inside the planned radius the placed crowns cover what the density expects (the same forest near and far)
    lv = t.levels[0]
    X, Y = lv.xy()
    f = spots.meta['focus'][0]
    inside = np.hypot(X - f[0], Y - f[1]) < 0.7 * 700.0
    forest = inside & (c['canopy_expected'] > 0.25)
    got, want = float(c['canopy'][forest].mean()), float(c['canopy_expected'][forest].mean())
    check('cover: in the forest the placed crowns cover what the density expects (within a quarter)',
          abs(got - want) < 0.25 * want, f'canopy {got:.3f} against canopy_expected {want:.3f} over '
                                         f'{int(forest.sum()) * lv.cell ** 2 / 1e4:.1f} ha')
    # open ground a crown's reach from any forest (the edge trees' crowns overhang the open ground beside them)
    reach = max(float(e.get('crown_m', e['core_m'])) for e in spots.species if e['kind'] == 'tree')
    k = int(math.ceil(reach / lv.cell))
    wooded = c['canopy_expected'] >= 0.02
    near = wooded.copy()
    for dj in range(-k, k + 1):
        for di in range(-k, k + 1):
            near |= np.roll(np.roll(wooded, dj, 0), di, 1)
    open_ = inside & ~near
    check('cover: where no trees are expected none stand', float(c['canopy'][open_].mean()) < 0.02,
          f"canopy {float(c['canopy'][open_].mean()):.4f} over {int(open_.sum()) * lv.cell ** 2 / 1e4:.1f} ha, "
          f"{reach:g} m from any forest")
    h = spots.cover('last')
    check('cover: a hero level draws single crowns', float(h['canopy'].max()) > 0.99 and float(h['canopy'].min()) == 0.0
          or float(h['canopy_expected'].max()) < 0.05,
          f"finest level canopy mean {float(h['canopy'].mean()):.3f}, expected {float(h['canopy_expected'].mean()):.3f}")
    ex = spots.cover_extra()
    from eidoblend.terrain.surface.maps import MAPS
    plant_maps = {k for k, m in MAPS.items() if m.made_by == 'plants'}
    check('cover: cover_extra gives every level of every plant map the surface bake registers, for its extra=',
          set(ex) == plant_maps and all(len(v) == len(t.levels) for v in ex.values()), ', '.join(sorted(ex)))
    return c


def test_handoff(t):
    """The far field (design 4.7): the cover the material draws (canopy_far, shrubs_far) takes over where the plan
    thins its plants out (the fade band, and the smallest dropped by distance), so placed and drawn cover make one
    stand: inside the radius the placed plants carry the expected cover, across the thinning the two add up to it,
    beyond it the drawn cover is all of it."""
    lv = t.levels[0]
    X, Y = lv.xy()

    def bands(placed_r, drawn_r, want_r, d, where, rows, what_bands):
        ok = True
        for lo, hi, what in what_bands:
            m = where & (d >= lo) & (d < hi)
            want = float(want_r[m].mean())
            placed, drawn = float(placed_r[m].mean()), float(drawn_r[m].mean())
            rows.append(f'{what} {lo:g}-{hi:g} m: placed {placed:.3f} + drawn {drawn:.3f} against {want:.3f}')
            if what == 'inside':
                ok &= abs(placed - want) < 0.25 * want and drawn < 0.1 * want
            elif what == 'across':
                ok &= abs(placed + drawn - want) < 0.25 * want and placed > 0.1 * want and drawn > 0.1 * want
            else:
                ok &= placed == 0.0 and abs(drawn - want) < 1e-6
        return ok
    spots = PL.plan_plants(t, 'alpine', radius_m=500.0, seed=4, **QUIET)
    c = spots.cover('main')
    f = spots.meta['focus'][0]
    d = np.hypot(X - f[0], Y - f[1])
    rows = []
    ok = bands(c['canopy'], c['canopy_far'], c['canopy_expected'], d, c['canopy_expected'] > 0.25, rows,
               ((120.0, 360.0, 'inside'), (410.0, 490.0, 'across'), (560.0, 800.0, 'beyond')))
    check('cover: the drawn crowns (canopy_far) take over where the plan thins the trees out: one forest', ok,
          '; '.join(rows))
    # shrubs: the desert's thin out by size from 120 m (the smallest kept grows 3 mm per metre) to their radius
    spots = PL.plan_plants(t, 'desert_sandstone', seed=4, **QUIET)
    c = spots.cover('main')
    placed = np.zeros((lv.n, lv.n))
    for n in spots.names():
        e = spots.entry(n)
        if e['kind'] != 'shrub':
            continue
        a = spots.array(n).astype(np.float64)
        PL._discs(placed, (a[:, 0] - lv.x0) / lv.cell, (a[:, 1] - lv.y0) / lv.cell,
                  e.get('crown_m', e['core_m']) * a[:, 4] / lv.cell)
    rows = []
    ok = bands(np.clip(placed, 0.0, 1.0), c['shrubs_far'], c['shrubs'], d, c['shrubs'] > 0.05, rows,
               ((20.0, 110.0, 'inside'), (180.0, 330.0, 'across'), (420.0, 700.0, 'beyond')))
    check('cover: the drawn shrub cover (shrubs_far) takes over where the plan thins the shrubs out', ok,
          '; '.join(rows))


def test_expected(t):
    """One forest rule (design 4.7, 5.4 package 4 item 6): expected_cover with no plan gives a plan's canopy_expected
    and shrubs on every level, its far cover is all of it, and a plan's canopy_far is 0 where its instances stand."""
    spots = PL.plan_plants(t, 'alpine', radius_m=500.0, seed=4, **QUIET)
    ex = PL.expected_cover(t, 'alpine')
    covers = [spots.cover(i) for i in range(len(t.levels))]
    same = all(np.array_equal(ex['canopy_expected'][i], covers[i]['canopy_expected'])
               and np.array_equal(ex['shrubs'][i], covers[i]['shrubs']) for i in range(len(t.levels)))
    check('expected cover: with no plan it is a plan\'s canopy_expected and shrubs, on every level, and all of it is '
          'left to the material', same and all(np.array_equal(ex['canopy_far'][i], ex['canopy_expected'][i])
                                               for i in range(len(t.levels))),
          f"canopy_expected mean on the main level {float(ex['canopy_expected'][0].mean()):.3f}")
    lv = t.levels[0]
    X, Y = lv.xy()
    f = spots.meta['focus'][0]
    inside = np.hypot(X - f[0], Y - f[1]) < 0.75 * 500.0
    far_in = float(covers[0]['canopy_far'][inside].max())
    check('expected cover: canopy_far is 0 where the instances stand', far_in < 1e-6,
          f'the largest canopy_far within 375 m of the focus {far_in:.2e}')


def test_ecotopes(t):
    bad = []
    for name in E.names():
        eco = E.get(name)
        bad += [f'{name}: {p}' for p in E.check(eco)]
    recipes = ['fluvial_range', 'alpine_valley', 'stratovolcano', 'caldera', 'cinder_cones', 'impact_crater',
               'canyon', 'incised_meanders', 'mesas_buttes', 'badlands', 'dunes', 'tower_karst', 'sea_cliffs',
               'rolling_hills', 'meadow']
    got = {}
    for r in recipes:
        eco = E.get('auto', recipe=r)
        got[r] = eco['name']
        bad += [f'{r}: {p}' for p in E.check(eco)]
    for place in P.PLACES:
        eco = E.get('auto', recipe='real_place', place=place, palette=P.PLACES[place]['palette'])
        bad += [f'{place}: {p}' for p in E.check(eco)]
    check('ecotopes: every palette, recipe and place has an ecotope that checks', not bad,
          '; '.join(bad) if bad else ', '.join(f'{r} -> {n}' for r, n in got.items()))
    check('ecotopes: a recipe\'s look is taken only with its own palette',
          E.get('auto', recipe='fluvial_range')['name'] == 'alpine+fluvial_range'
          and E.get('auto', recipe='fluvial_range', palette='volcanic')['name'] == 'volcanic')
    try:
        E.get(dict(title='x', species=[dict(name='a', kind='tree', source=('seedthree', 'pine', {}, [1]),
                                            density='0.01 * no_such_mask')]))
        named = False
    except ValueError as e:
        named = 'no_such_mask' in str(e)
    check('ecotopes: an unknown mask name is refused, by name', named)
    # every ecotope plans on the synthetic ground (its expressions evaluate; masks it lacks read 0)
    planned = {}
    for name in E.names():
        sp = PL.plan_plants(t, name, radius_m=150.0, **QUIET)
        planned[name] = len(sp)
    check('ecotopes: every ecotope plans on the synthetic ground', all(v >= 0 for v in planned.values()),
          ', '.join(f'{k} {v:,}' for k, v in planned.items()))


def test_distance():
    rng = np.random.default_rng(2)
    seed = rng.random((70, 90)) < 0.004
    seed[35, 10:60] = True
    d = PL._distance_to(seed, 3.0, 1.0e6)
    jj, ii = np.nonzero(seed)
    Y, X = np.indices(seed.shape)
    brute = np.sqrt(((X[..., None] - ii) ** 2 + (Y[..., None] - jj) ** 2).min(-1)) * 3.0
    err = np.abs(d - brute)
    check('distance: the stream-distance transform equals brute force', float(err.max()) < 0.75 and float((err > 1e-3).mean()) < 0.01,
          f'max error {err.max():.3f} m on a 3 m grid, {100 * (err > 1e-3).mean():.2f} % of cells off')
    check('distance: capped, and all the cap where no stream is',
          float(PL._distance_to(seed, 3.0, 20.0).max()) == 20.0
          and float(PL._distance_to(np.zeros((8, 8), bool), 3.0, 50.0).min()) == 50.0)


def test_derived(t):
    g = PL._Ground(t, None, dict(P.CONSTANTS, base_elevation_m=800.0, treeline_m=1950.0))
    xs = np.array([0.0, 30.0, -300.0, 400.0, 61.0])
    ys = np.array([0.0, -200.0, 100.0, -350.0, -119.0])
    pts = g.locate(xs, ys)
    slope = g.at(pts, 'slope')
    from eidoblend.terrain.core.grid import sample_bilinear
    ref = np.zeros(len(xs))
    for i in range(len(t.levels) - 1, -1, -1):
        lv = t.levels[i]
        m = (pts.level == i)
        ref[m] = sample_bilinear(t.masks.level(i)['slope'], lv.x0, lv.y0, lv.cell, xs[m], ys[m])
    check('derived: a mask at points is the finest level\'s bilinear value', bool(np.allclose(slope, ref, atol=1e-5)),
          f'levels {pts.level.tolist()}')
    dc = g.at(pts, 'dist_channel')
    check('derived: dist_channel is small on the valley axis and large up the side',
          dc[0] < 60.0 and dc[3] > 150.0, f'{np.round(dc, 1).tolist()} m')
    ins = g.at(pts, 'insolation')
    check('derived: insolation between 0 and 1 (the cosine with the place\'s climatological sun)',
          float(ins.min()) >= 0.0 and float(ins.max()) <= 1.0)
    check('derived: soil reads 0 where no deposit, talus or sand was made', float(np.abs(g.at(pts, 'soil')).max()) == 0.0)


def surface_data(t):
    """The surface bake's SurfaceData (terrain/surface, package 1's class) on the synthetic valley, made from maps
    given per level rather than baked (the bake's numpy twins take many minutes on these grids; its kernels need
    Blender): `settle` at the cell, `crease` on the detail grid at half the cell, as the bake lays them out, and
    `snowpack` 0.6 m east of x = 350 m."""
    from eidoblend.terrain import surface as S
    from eidoblend.terrain.surface import bake as B
    opts = B.resolve_options(t, None, {'maps': 'masks'})
    baked = []
    for lv in t.levels:
        X, Y = lv.xy()
        nd = int(round(lv.n * B.detail_factor(lv, opts)))
        c = (np.arange(nd) + 0.5) * lv.side / nd
        XD, YD = np.meshgrid(lv.x0 + c, lv.y0 + c)
        baked.append({'settle': (0.5 + 0.4 * np.sin(X / 90.0) * np.cos(Y / 70.0)).astype(np.float32),
                      'crease': np.tanh(np.sin(XD / 13.0) + np.cos(YD / 9.0)).astype(np.float32),
                      'snowpack': np.where(X > 350.0, 0.6, 0.0).astype(np.float32)})
    return S.SurfaceData(t, baked, {}, opts, 'plants-test')


def test_surface(t):
    sd = surface_data(t)
    rng = np.random.default_rng(5)
    x, y = rng.uniform(-1000.0, 1000.0, 4000), rng.uniform(-1000.0, 1000.0, 4000)
    x[:1000], y[:1000] = rng.uniform(-200.0, 300.0, 1000), rng.uniform(-350.0, 120.0, 1000)   # the hero windows
    g = PL._Ground(t, sd, dict(P.CONSTANTS))
    pts = g.locate(x, y)
    worst = {n: float(np.abs(g.at(pts, n) - sd.at(n, x, y)).max()) for n in ('settle', 'crease', 'slope', 'wetness')}
    check('surface data: the planner reads a map as SurfaceData.at does (the finest level holding the point, at the '
          'map\'s own texel)', max(worst.values()) < 1e-5,
          ', '.join(f'{n} {v:.1e}' for n, v in worst.items()) + f"; crease at {sd.maps(0)['crease'].shape[0]} texels "
          f"on a {t.levels[0].n}-cell level")
    eco = dict(title='test', species=[dict(name='shrub', kind='shrub', source=('seedthree', 'blackbrush', {}, [1]),
                                           size_m=(0.4, 1.0), core_m=0.5, max_cell_m=None, max_radius_m=300.0,
                                           cluster=dict(parents_per_ha=300.0, mu=4.0, sigma_m=3.0),
                                           density='0.1 * smoothstep(0.55, 0.7, settle)', lod_m_per_m=0.0,
                                           on=('rock', 'talus', 'sand'))])
    with_ = PL.plan_plants(t, eco, data=sd, **QUIET).array('shrub').astype(np.float64)
    without = PL.plan_plants(t, eco, **QUIET).array('shrub')
    s_at = sd.at('settle', with_[:, 0], with_[:, 1]) if len(with_) else np.zeros(0)
    check('surface data: a rule reading a bake map places plants with the bake, only where the map allows, and '
          'none without it', len(with_) > 300 and float(s_at.min()) >= 0.55 - 1e-6 and len(without) == 0,
          f'{len(with_):,} shrubs with the bake (settle {s_at.min():.3f}-{s_at.max():.3f} under them), '
          f'{len(without)} without')
    eco['species'][0].update(density='0.1', on=('rock', 'talus', 'sand', 'water'))
    snowy = PL.plan_plants(t, eco, focus=(300.0, -100.0), data=sd, **QUIET).array('shrub').astype(np.float64)
    sp_at = sd.at('snowpack', snowy[:, 0], snowy[:, 1])
    check('surface data: plants keep off the settled snow (snowpack over 0.2 m)',
          float(sp_at.max()) <= 0.2 and int((snowy[:, 0] < 340.0).sum()) > 300 and int((snowy[:, 0] > 360.0).sum()) == 0,
          f'{len(snowy):,} shrubs, {int((snowy[:, 0] < 340.0).sum()):,} west of the snow edge at x 350 m, '
          f'{int((snowy[:, 0] > 360.0).sum())} east of it')
    spots = PL.plan_plants(t, 'alpine', seed=4, data=sd, **QUIET)
    sd.add_maps(spots.cover_extra())
    fine = len(t.levels) - 1
    lv = t.levels[fine]
    tr = spots.array('spruce').astype(np.float64)
    inner = (tr[:, 0] > lv.x0 + 5) & (tr[:, 0] < lv.x0 + lv.side - 5) & (tr[:, 1] > lv.y0 + 5) \
        & (tr[:, 1] < lv.y0 + lv.side - 5) & (2.3 * tr[:, 4] > 1.0)
    c_at = sd.at('canopy', tr[inner, 0], tr[inner, 1]) if inner.any() else np.zeros(0)
    same = all(np.array_equal(sd.maps(i)['canopy'], spots.cover(i)['canopy']) for i in range(len(t.levels)))
    check('surface data: the cover rasters go into the bake (add_maps) and read back as SurfaceData maps',
          same and inner.sum() > 20 and float(np.median(c_at)) > 0.95 and float(c_at.min()) > 0.5,
          f"canopy under {int(inner.sum())} spruce trunks of the finest level: median {np.median(c_at):.2f}, "
          f"least {c_at.min():.2f}; canopy_expected and shrubs beside it")


UNTHINNED_M = {'tree': 700.0, 'shrub': 420.0, 'grass': 150.0, 'forb': 150.0, 'groundcover': 100.0}


def unthinned(eco, radius_m=None, **kw):
    """An ecotope with the view's thinning off (no distance thinning, no fade band, no cap, any level), every species
    out to radius_m (default by kind, UNTHINNED_M: a meadow's grass out to 700 m is 26 million candidates): the plan's
    placement itself, which the window-edge gate measures."""
    eco = E.get(eco, **kw) if isinstance(eco, str) else copy.deepcopy(eco)
    for s in eco['species']:
        s.update(max_count=10 ** 8, lod_m_per_m=0.0, fade=(1.0, 1.0), max_cell_m=None,
                 max_radius_m=radius_m or UNTHINNED_M[s['kind']])
    return eco


def edge_steps(t, eco, focus, tmp, seed=4, data=None, min_count=400, strip_m=50.0):
    """Per species and hero window edge: stems per hectare in strip_m strips either side (the judge's edge_density on
    the saved spots), the same on the terrain's coarse levels alone (_ground.CoarseView: the same candidates and
    densities, no window), and their quotient, the step the window makes: [dict(species, level, edge, inner, outer,
    ratio, ratio_coarse, step)], the edges with min_count plants a side."""
    sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..')))
    from surfacing_judge import plants as JP
    hero = PL.plan_plants(t, eco, focus=focus, seed=seed, data=data, **QUIET)
    coarse = PL.plan_plants(G.CoarseView(t), eco, focus=focus, seed=seed, data=data, **QUIET)
    out = []
    windows = [(float(lv.x0), float(lv.y0), float(lv.side)) for lv in t.levels if getattr(lv, 'role', '') == 'hero']
    for tag, sp in (('hero', hero), ('coarse', coarse)):
        sp.save(os.path.join(tmp, f'edges_{tag}'))
    jh, jc = JP.load(os.path.join(tmp, 'edges_hero')), JP.load(os.path.join(tmp, 'edges_coarse'))
    for nm in hero.names():
        rc = {(r['level'], r['edge']): r for r in JP.edge_density(jc, nm, windows, strip_m, min_count)}
        for r in JP.edge_density(jh, nm, windows, strip_m, min_count):
            c = rc.get((r['level'], r['edge']))
            if c is None:
                continue
            out.append(dict(species=nm, level=r['level'], edge=r['edge'], inner=r['inner'], outer=r['outer'],
                            inner_coarse=c['inner'], outer_coarse=c['outer'], ratio=r['ratio'],
                            ratio_coarse=c['ratio'], step=r['ratio'] / c['ratio']))
    return out


def test_edges(t, tmp):
    """No step at a window edge (design 5.4, package 4, item 5): stems per hectare of every species in 50 m strips
    either side of every hero window's edge, the plan's placement itself (its view's thinning off), set against the
    same strips of the same plan on the coarse levels alone: the ground's own gradient across 100 m (the valley's
    forest edge, its floor) is in both, a step the window makes only in the first. The densities read the coarse
    levels, so the window may change only what the finest level excludes."""
    rows = []
    worst = 0.0
    for eco in ('alpine', 'desert_sandstone'):
        for r in edge_steps(t, unthinned(eco), None, tmp):
            worst = max(worst, abs(r['step'] - 1.0))
            rows.append(f"{eco}/{r['species']} {r['level']}{r['edge'][0]} {r['inner']:.0f}/{r['outer']:.0f} per ha "
                        f"({100 * (r['ratio'] - 1.0):+.0f} %; without the window {100 * (r['ratio_coarse'] - 1.0):+.0f} "
                        f"%: step {100 * (r['step'] - 1.0):+.1f} %)")
    check('edges: no window edge steps stems per hectare by 10 % (against the same plan without the window)',
          rows and worst <= 0.10, f'{len(rows)} edges, worst step {100 * worst:.1f} %: ' + '; '.join(rows))


def test_around(t):
    eco = dict(title='test', species=[
        dict(name='tree', kind='tree', source=('seedthree', 'douglasFir', {}, [1]), size_m=(14.0, 30.0), core_m=2.5,
             cluster=dict(parents_per_ha=20.0, mu=3.0, sigma_m=9.0), density='0.006', fade=(1.0, 1.0)),
        dict(name='fern', kind='groundcover', source=('ph', 'celandine_01', {}), size_m=(0.2, 0.4), core_m=0.0,
             max_cell_m=None, max_radius_m=200.0, cluster=dict(parents_per_ha=100.0, mu=2.0, sigma_m=1.0),
             density='0.0', around=dict(species='tree', per=6.0, radius=1.4), fade=(1.0, 1.0), lod_m_per_m=0.0,
             shade=dict(tolerance=1.0, radius=1.0)),
    ])
    sp = PL.plan_plants(t, eco, radius_m=260.0, **QUIET)
    tr, fe = sp.array('tree').astype(np.float64), sp.array('fern').astype(np.float64)
    i, j, d = PL._pairs(fe[:, 0], fe[:, 1], tr[:, 0], tr[:, 1], 1.4 * 2.5 + 0.01)
    near = np.zeros(len(fe), bool)
    near[i[d <= 1.4 * 2.5 * tr[j, 4] + 0.01]] = True
    trees_in = int((np.hypot(tr[:, 0] - 60, tr[:, 1] + 120) < 190).sum())
    check('around: understory seeded around trees stands within its radius of one', len(fe) > 2 * trees_in > 0
          and bool(near.all()), f'{len(fe):,} around {len(tr):,} trees')


def test_timing(t):
    # the design's load (section 7): 10^4 trees and 10^5 shrubs; the shrubs keep every size at every distance here
    # (their kind thins them by distance, which would cap them at 333 m on this ground whatever the radius)
    eco = dict(title='test', species=[
        dict(name='tree', kind='tree', source=('seedthree', 'douglasFir', {}, [1]), size_m=(8.0, 30.0), core_m=2.3,
             cluster=dict(parents_per_ha=110.0, mu=6.0, sigma_m=7.0), max_radius_m=450.0,
             density='0.066 * smoothstep(8, 20, slope)', max_count=10 ** 7),
        dict(name='shrub', kind='shrub', source=('seedthree', 'blackbrush', {}, [1]), size_m=(0.4, 1.0), core_m=0.55,
             max_cell_m=None, max_radius_m=420.0, cluster=dict(parents_per_ha=700.0, mu=6.0, sigma_m=3.0),
             density='0.4', max_count=10 ** 7, lod_m_per_m=0.0),
    ])
    PL.plan_plants(t, eco, radius_m=50.0, **QUIET)        # the masks' first read (dist_channel, lazy tables)
    # the synthetic valley's heights are an analytic function with three octaves of value noise, far slower than a
    # Terrain's lookup on its ring mesh: its time is counted apart, and the planner is held to the budget
    spent = [0.0]

    def timed(fn):
        def call(*a, **k):
            t1 = time.perf_counter()
            out = fn(*a, **k)
            spent[0] += time.perf_counter() - t1
            return out
        return call
    tt = copy.copy(t)
    tt.height_at, tt.normal_at = timed(t.height_at), timed(t.normal_at)
    t0 = time.perf_counter()
    sp = PL.plan_plants(tt, eco, focus=(0.0, 0.0), **QUIET)
    dt = time.perf_counter() - t0
    nt, ns = sp.count('tree'), sp.count('shrub')
    check('timing: 10^4 trees and 10^5 shrubs planned within 10 s', nt >= 1e4 and ns >= 1e5 and dt - spent[0] <= 10.0,
          f'{nt:,} trees and {ns:,} shrubs: the planner {dt - spent[0]:.2f} s, and {spent[0]:.2f} s in the synthetic '
          f'terrain\'s height function')


def test_rocks(t):
    import importlib
    try:
        import bpy  # noqa: F401
    except ImportError:
        sys.modules.setdefault('bpy', type(sys)('bpy'))           # dressing imports bpy; place_rocks never calls it
        sys.modules.setdefault('mathutils', type(sys)('mathutils'))
        sys.modules['mathutils'].Matrix = object
    D = importlib.import_module('eidoblend.terrain.build.dressing')
    g = PL._Ground(t, None, dict(P.CONSTANTS, base_elevation_m=800.0, treeline_m=1950.0))

    def mask_at(name, x, y):
        x = np.asarray(x, np.float64)
        y = np.asarray(y, np.float64)
        if name == 'grain':                              # a stand-in for the bake's map: 0 west of x = 170, 1 east of 230
            return np.clip((x - 170.0) / 60.0, 0.0, 1.0)
        v = g.at(g.locate(x.ravel(), y.ravel()), name)
        return None if v is None else v.reshape(x.shape)
    spec = dict(density='0.6*smoothstep(22, 34, slope) + 0.02', size_m=(0.15, 3.0), alpha=2.1)
    kw = dict(mask_at=mask_at, height_at=t.height_at, normal_at=t.normal_at, focus=(200.0, 0.0), radius_m=80.0,
              seed=7, n_models=3, model_dims=[(1.0, 0.8, 0.5), (2.0, 1.5, 1.1), (0.4, 0.4, 0.3)])
    a = D.place_rocks(spec, **kw)
    digest = hashlib.sha1(b''.join(np.ascontiguousarray(a[k]).tobytes() for k in ('xyz', 'euler', 'scale', 'pick', 'size'))
                          ).hexdigest()
    b = D.place_rocks(dict(spec, toe_bias=0.0), **kw)
    same = all(np.array_equal(a[k], b[k]) for k in a)
    check('rocks: toe_bias 0 is the scatter without the key', same, f"{len(a['size']):,} rocks, sha1 {digest[:12]}")
    ref = os.path.join(HERE, 'rocks_before_toe_bias.json')
    if os.path.exists(ref):
        want = json.load(open(ref, encoding='utf-8'))
        if want.get('numpy') == np.__version__:
            check('rocks: the scatter is byte for byte what it was before the toe bias was added',
                  want['sha1'] == digest and want['count'] == len(a['size']),
                  f"{len(a['size']):,} rocks, sha1 {digest[:12]} (recorded {want['sha1'][:12]}, numpy {want['numpy']})")
        else:
            print(f"[skip] rocks: the recorded scatter was made with numpy {want.get('numpy')}, this is "
                  f"{np.__version__} (its random streams may differ)")
    # the bias itself, with no thinning by distance in the way: the same rocks in the same places, the smallest
    # growing with grain
    flat = dict(spec, lod_m_per_m=0.0)
    n0 = D.place_rocks(flat, **kw)
    c = D.place_rocks(dict(flat, toe_bias=2.0), **kw)
    west, east = c['xyz'][:, 0] < 170.0, c['xyz'][:, 0] > 230.0 - 0.2 * 60.0
    check('rocks: with a toe bias the smallest rock grows with grain (the same rocks in the same places)',
          np.array_equal(c['xyz'][:, :2], n0['xyz'][:, :2]) and np.array_equal(c['size'][west], n0['size'][west])
          and c['size'][west].min() < 0.16 and c['size'][east].min() >= 0.15 * (1 + 2.0 * 0.8) - 1e-9
          and bool((c['size'] >= n0['size'] - 1e-12).all()),
          f"smallest {c['size'][west].min():.2f} m where grain is 0, {c['size'][east].min():.2f} m where it is over "
          f"0.8; {len(c['size']):,} rocks either way")
    return digest, len(a['size'])


def sheet(t, spots, cover, path):
    """The plan from above: hillshade, the spots by species, and the cover rasters (a picture to look at)."""
    from PIL import Image, ImageDraw
    from eidoblend.terrain.core import io as IO
    lv = t.levels[0]
    X, Y = lv.xy()
    hs = IO.to_u8(IO.hillshade(t.height_at(X, Y), lv.cell))
    S = 4
    base = Image.fromarray(np.ascontiguousarray(hs[::-1])).resize((lv.n * S, lv.n * S), Image.BILINEAR).convert('RGB')
    dr = ImageDraw.Draw(base)
    colours = {'spruce': (20, 90, 40), 'maple': (150, 200, 60), 'meadow grass': (190, 220, 120),
               'meadow flowers': (255, 255, 255)}
    for n in spots.names():
        a = spots.array(n)
        px = (a[:, 0] - lv.x0) / lv.cell * S
        py = (lv.n - (a[:, 1] - lv.y0) / lv.cell) * S
        r = np.maximum(spots.entry(n)['core_m'] * a[:, 4] / lv.cell * S, 0.6)
        for x, y, rr in zip(px.tolist(), py.tolist(), r.tolist()):
            dr.ellipse([x - rr, y - rr, x + rr, y + rr], fill=colours.get(n, (200, 80, 200)))
    tiles = [base]
    for k in ('canopy', 'canopy_expected', 'shrubs'):
        im = Image.fromarray(np.ascontiguousarray((255 * cover[k][::-1]).astype(np.uint8)))
        tiles.append(im.resize((lv.n * S, lv.n * S), Image.NEAREST).convert('RGB'))
    W = lv.n * S
    out = Image.new('RGB', (W * 2, W * 2))
    for k, im in enumerate(tiles):
        out.paste(im, ((k % 2) * W, (k // 2) * W))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.save(path)
    print('[plants-test] wrote', path)


def main():
    argv = sys.argv[1:]
    only = set(argv[argv.index('--only') + 1].split(',')) if '--only' in argv else None

    def want(n):
        return only is None or n in only
    t0 = time.time()
    t = G.cached()
    print(f'[plants-test] the synthetic valley: {len(t.levels)} levels in {time.time() - t0:.1f} s', flush=True)
    tmp = tempfile.mkdtemp(prefix='plants_test_')
    try:
        spots = test_determinism(t, tmp) if want('determinism') else PL.plan_plants(t, 'alpine', seed=4, **QUIET)
        if want('radius'):
            test_radius(t)
        if want('hard_core'):
            test_hard_core(t, spots)
            test_feet(t)
        if want('stature'):
            test_stature(t)
        if want('density'):
            test_density(t, spots)
        if want('ground'):
            test_ground(t, spots)
        if want('format'):
            test_format(t, spots, tmp)
        if want('pattern'):
            test_pattern(t)
        cover = test_cover(t, spots) if want('cover') or '--sheet' in argv else None
        if want('cover'):
            test_handoff(t)
            test_expected(t)
        if want('ecotopes'):
            test_ecotopes(t)
        if want('distance'):
            test_distance()
            test_derived(t)
        if want('around'):
            test_around(t)
        if want('surface'):
            test_surface(t)
        if want('edges'):
            test_edges(t, tmp)
        if want('timing'):
            test_timing(t)
        if want('rocks'):
            test_rocks(t)
        if '--sheet' in argv:
            sheet(t, spots, cover, os.path.join(G.OUT, 'synthetic_spots.png'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [n for n, ok in RESULTS if not ok]
    print(f'[plants-test] {len(RESULTS) - len(bad)}/{len(RESULTS)} PASS'
          + ('; FAIL: ' + '; '.join(bad) if bad else ''), flush=True)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
