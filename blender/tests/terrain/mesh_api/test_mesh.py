"""The ring mesh, numerically, in plain Python (no bpy): build/mesh.py on synthetic nested levels whose windows sit
at odd offsets on their parents' grids, drawn at stride 2 with cores, so every seam case is exercised (shared
vertices, midpoints, lines inserted for off-lattice holes, fans on all four sides of every hole).

Checks
  watertight     the only open edges of the terrain triangles are the outermost window's border
  t-junctions    no vertex lies inside another triangle's edge
  orientation    every terrain triangle faces up and has area
  height_at      equals every vertex's z, and an independent oracle (the triangle that contains the point, found by
                 brute force over all triangles, interpolated barycentrically) at 2,000 points across rings and seams
  attributes     a bilinear attribute of the linear function x reads x at every vertex inside the outer border, seams
                 included (the seam rule interpolates it linearly)
  rebuild        the mesh rebuilt from its layout and vertex positions (what terrain_height_at does after a reload)
                 gives the same heights
  seam crease    on rough ground every level samples alike, a seam bends no more than an ordinary lattice line
  budget         triangles of a film stack (seven levels of 1024 cells, cores) and of a hero stack (2048), and the
                 time to build the film one

    python blender/tests/terrain/mesh_api/test_mesh.py
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..', '..')))
from eidoblend.terrain.build import mesh as M  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'mesh_api'))
rng = np.random.default_rng(5)


def surface(x, y):
    """A test ground with ridges, a tilt and a crease, in metres."""
    return (6.0 * np.sin(x / 7.3) * np.cos(y / 5.1) + 3.0 * np.sin((x + 2.0 * y) / 2.3) + 0.04 * x
            + 2.0 * np.abs(np.sin(x / 1.7 - y / 2.9)))


def nested(n, finest, nlev, offsets):
    """nlev windows of n cells, coarsest first, each half its parent's side, shifted by `offsets` parent cells from
    the centred position (odd offsets put the hole off a stride-2 lattice)."""
    c = finest * 2 ** (nlev - 1)
    wins = [M.Window(-n * c / 2.0, -n * c / 2.0, c, n)]
    for k in range(1, nlev):
        p = wins[-1]
        ox, oy = offsets[(k - 1) % len(offsets)]
        x0 = p.x0 + (n // 4 + ox) * p.cell
        y0 = p.y0 + (n // 4 + oy) * p.cell
        wins.append(M.Window(x0, y0, p.cell / 2.0, n))
    return wins


def level_arrays(wins, f):
    out = []
    for w in wins:
        xs = w.x0 + (np.arange(w.n) + 0.5) * w.cell
        ys = w.y0 + (np.arange(w.n) + 0.5) * w.cell
        X, Y = np.meshgrid(xs, ys)
        out.append(f(X, Y))
    return out


def oracle(rm, x, y):
    """z of each point on the triangle that contains it, found among all terrain triangles (brute force), and how
    many triangles contain it."""
    V = rm.verts.astype(np.float64)
    T = rm.tris[:rm.terrain_triangles]
    A, B, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    z = np.full(len(x), np.nan)
    hits = np.zeros(len(x), np.int64)
    eps = 1e-9
    for s in range(0, len(x), 64):
        px = x[s:s + 64, None]
        py = y[s:s + 64, None]
        d = (B[:, 1] - C[:, 1]) * (A[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (A[:, 1] - C[:, 1])
        l1 = ((B[:, 1] - C[:, 1]) * (px - C[:, 0]) + (C[:, 0] - B[:, 0]) * (py - C[:, 1])) / d
        l2 = ((C[:, 1] - A[:, 1]) * (px - C[:, 0]) + (A[:, 0] - C[:, 0]) * (py - C[:, 1])) / d
        l3 = 1.0 - l1 - l2
        inside = (l1 >= -eps) & (l2 >= -eps) & (l3 >= -eps)
        zz = l1 * A[:, 2] + l2 * B[:, 2] + l3 * C[:, 2]
        hits[s:s + 64] = inside.sum(1)
        first = np.argmax(inside, axis=1)
        z[s:s + 64] = zz[np.arange(len(first)), first]
    return z, hits


def seam_points(rm, n):
    """n points: a third uniform over the terrain, a third within a finest cell of a ring border, a third within a
    finest cell of a ring corner."""
    xmin, ymin, xmax, ymax = rm.bounds()
    u = rm.unit
    rings = rm.rings[1:]
    if not rings:
        return rng.uniform(xmin, xmax, n), rng.uniform(ymin, ymax, n)
    k = n // 3
    x = [rng.uniform(xmin, xmax, k)]
    y = [rng.uniform(ymin, ymax, k)]
    for _ in range(k):
        r = rings[rng.integers(len(rings))]
        side = rng.integers(4)
        t = rng.uniform(0, 1)
        x0, x1, y0, y1 = r.xm[0], r.xm[-1], r.ym[0], r.ym[-1]
        px = [x0, x1, x0 + t * (x1 - x0), x0 + t * (x1 - x0)][side]
        py = [y0 + t * (y1 - y0), y0 + t * (y1 - y0), y0, y1][side]
        x.append([px + rng.uniform(-u, u)])
        y.append([py + rng.uniform(-u, u)])
    for _ in range(n - 2 * k):
        r = rings[rng.integers(len(rings))]
        px = [r.xm[0], r.xm[-1]][rng.integers(2)]
        py = [r.ym[0], r.ym[-1]][rng.integers(2)]
        x.append([px + rng.uniform(-u, u)])
        y.append([py + rng.uniform(-u, u)])
    return np.concatenate(x), np.concatenate(y)


def check_case(label, wins, mesh_res, cores, results):
    hs = level_arrays(wins, surface)
    sx = level_arrays(wins, lambda X, Y: X)
    t0 = time.perf_counter()
    rm = M.build_rings(wins, hs, attributes={'sx': sx}, cores=cores, mesh_res=mesh_res)
    t_build = time.perf_counter() - t0
    r = {}
    # watertight: open edges = the outer border
    oe = rm.open_edges()
    V = rm.verts.astype(np.float64)
    xmin, ymin, xmax, ymax = rm.bounds()
    on_border = lambda v: (np.isclose(V[v, 0], xmin) | np.isclose(V[v, 0], xmax) |
                           np.isclose(V[v, 1], ymin) | np.isclose(V[v, 1], ymax))
    r0 = rm.rings[0]
    perim_edges = 2 * (len(r0.xs) - 1) + 2 * (len(r0.ys) - 1)
    r['open_edges'] = int(len(oe))
    r['open_edges_expected'] = perim_edges
    r['open_edges_all_on_border'] = bool(np.all(on_border(oe[:, 0]) & on_border(oe[:, 1])))
    r['t_junctions'] = rm.t_junctions()
    T = rm.tris[:rm.terrain_triangles]
    A, B, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    nz = (B[:, 0] - A[:, 0]) * (C[:, 1] - A[:, 1]) - (B[:, 1] - A[:, 1]) * (C[:, 0] - A[:, 0])
    r['min_twice_area_m2'] = float(nz.min())
    # height_at at the vertices
    nv = rm.skirt['first_vertex']
    hv = rm.height_at(V[:nv, 0], V[:nv, 1])
    r['vertex_max_err_m'] = float(np.abs(hv - V[:nv, 2]).max())
    # oracle
    x, y = seam_points(rm, 2000)
    zo, hits = oracle(rm, x, y)
    zh = rm.height_at(x, y)
    r['oracle_points'] = int(len(x))
    r['oracle_uncovered'] = int((hits == 0).sum())
    r['oracle_max_err_m'] = float(np.nanmax(np.abs(zo - zh)))
    r['surface_max_err_m'] = float(np.abs(zh - surface(x, y)).max())
    # attributes: x read back at every vertex inside the outer border
    inner = ~on_border(np.arange(nv))
    r['attr_max_err_m'] = float(np.abs(rm.attrs['sx'][:nv][inner] - V[:nv, 0][inner]).max())
    # rebuild from the layout
    lay = json.loads(json.dumps(rm.layout()))
    rb = M.rebuild(lay, rm.verts)
    r['rebuild_max_err_m'] = float(np.abs(rb.height_at(x, y) - zh).max())
    r['normals_up'] = bool(np.all(rm.normal_at(x, y)[:, 2] > 0))
    r['rings'] = [s.as_list() for s in rm.specs]
    r['triangles'] = rm.triangle_count
    r['vertices'] = int(len(rm.verts))
    r['build_s'] = round(t_build, 3)
    ok = (r['open_edges'] == perim_edges and r['open_edges_all_on_border'] and r['t_junctions'] == 0
          and r['min_twice_area_m2'] > 0 and r['vertex_max_err_m'] <= 1e-9 and r['oracle_uncovered'] == 0
          and r['oracle_max_err_m'] <= 1e-9 and r['attr_max_err_m'] <= 1e-4 and r['rebuild_max_err_m'] == 0.0
          and r['normals_up'])
    r['pass'] = bool(ok)
    results[label] = r
    print(f'[mesh] {label}: {"PASS" if ok else "FAIL"} tris {r["triangles"]} open {r["open_edges"]}/{perim_edges} '
          f't-junctions {r["t_junctions"]} vertex err {r["vertex_max_err_m"]:.2e} oracle err '
          f'{r["oracle_max_err_m"]:.2e} (uncovered {r["oracle_uncovered"]}) attr err {r["attr_max_err_m"]:.2e} '
          f'rebuild err {r["rebuild_max_err_m"]:.1e} build {t_build:.2f}s', flush=True)
    return rm, ok


def budget(results):
    """Triangles of the default film plan (two context levels, main, four hero levels, all 1024 cells) and of a hero
    plan (2048 cells), counted from the topology, and the full build time of the film one."""
    out = {}
    for label, n, nlev in (('film_7x1024', 1024, 7), ('hero_7x2048', 2048, 7), ('draft_3x512', 512, 3)):
        finest = 0.5 if n == 1024 else 0.25
        wins = nested(n, finest, nlev, [(0, 0)])
        origin, unit, iw = M._integer_windows(wins)
        specs = M.plan_rings(iw, cores=(nlev > 3))
        t0 = time.perf_counter()
        rings, nv, tris, perim = M._topology(specs, True)
        out[label] = dict(triangles=int(len(tris) + 2 * len(perim)), vertices=int(nv),
                          rings=[s.as_list() for s in specs], topology_s=round(time.perf_counter() - t0, 2))
    wins = nested(1024, 0.5, 7, [(3, -5), (-1, 2)])
    hs = [np.zeros((w.n, w.n), np.float32) + k for k, w in enumerate(wins)]
    t0 = time.perf_counter()
    rm = M.build_rings(wins, hs, attributes={f"m{i}": hs for i in range(30)}, cores=True)
    out['film_7x1024']['build_with_30_attributes_s'] = round(time.perf_counter() - t0, 2)
    out['film_7x1024']['triangles_built'] = rm.triangle_count
    results['budget'] = out
    f = out['film_7x1024']
    print(f'[mesh] budget: film 7 x 1024 -> {f["triangles"]:,} triangles ({f["vertices"]:,} vertices), built with 30 '
          f'attributes in {f["build_with_30_attributes_s"]} s; hero 7 x 2048 -> {out["hero_7x2048"]["triangles"]:,}; '
          f'draft 3 x 512 -> {out["draft_3x512"]["triangles"]:,}', flush=True)
    return f['triangles'] <= 3.5e6 and f['build_with_30_attributes_s'] <= 5.0


def rough(X, Y):
    """Rough ground: ridges at 600 m, 140 m and 80 m wavelengths and a crease, metres."""
    return (40.0 * np.sin(X / 97.0) * np.cos(Y / 71.0) + 12.0 * np.sin((X + 2.0 * Y) / 23.0)
            + 5.0 * np.abs(np.sin(X / 13.0 - Y / 17.0)) + 0.1 * X)


def crease_deg(rm, x, y, nx, ny, d):
    a = rm.normal_at(x - nx * d, y - ny * d, smooth=False)
    b = rm.normal_at(x + nx * d, y + ny * d, smooth=False)
    return np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', a, b), -1.0, 1.0)))


def border_points(r, inset, n=2000):
    x0, x1, y0, y1 = r.xm[0] + inset, r.xm[-1] - inset, r.ym[0] + inset, r.ym[-1] - inset
    k = n // 4
    t = np.random.default_rng(7).uniform(0.03, 0.97, k)
    xs = np.concatenate([x0 + t * (x1 - x0), x0 + t * (x1 - x0), np.full(k, x0), np.full(k, x1)])
    ys = np.concatenate([np.full(k, y0), np.full(k, y1), y0 + t * (y1 - y0), y0 + t * (y1 - y0)])
    nx = np.concatenate([np.zeros(k), np.zeros(k), -np.ones(k), np.ones(k)])
    ny = np.concatenate([-np.ones(k), np.ones(k), np.zeros(k), np.zeros(k)])
    return xs, ys, nx, ny


def seam_creases(results):
    """The seam rule alone: every level samples one rough surface, so any extra bend along a ring border is the
    mesh's. Across each seam, the angle between the triangle normals a quarter of a spacing either side, against
    ordinary lattice lines three spacings inside the child and outside in the parent: p50 and p99 may not exceed
    the ordinary lines' by more than 10 %."""
    wins = nested(512, 0.5, 5, [(0, 0)])
    rm = M.build_rings(wins, level_arrays(wins, rough), {}, cores=True, mesh_res=256)
    out, ok = {}, True
    for k in range(1, len(rm.rings)):
        c, p = rm.rings[k], rm.rings[k - 1]
        sc, sp = c.spec.sp * rm.unit, p.spec.sp * rm.unit
        seam = crease_deg(rm, *border_points(c, 0.0), 0.25 * min(sc, sp))
        ordinary = np.concatenate([crease_deg(rm, *border_points(c, 3 * sc), 0.25 * sc),
                                   crease_deg(rm, *border_points(c, -3 * sp), 0.25 * sp)])
        s50, s99, o50, o99 = (float(np.percentile(a, q)) for a, q in ((seam, 50), (seam, 99), (ordinary, 50),
                                                                      (ordinary, 99)))
        good = s50 <= 1.1 * o50 and s99 <= 1.1 * o99
        ok &= good
        out[f'seam{k}'] = dict(spacing_m=[sp, sc], seam_p50_p99_deg=[s50, s99], ordinary_p50_p99_deg=[o50, o99],
                               pass_=good)
        print(f'[mesh] seam crease {k} ({sp:g} -> {sc:g} m): seam p50/p99 {s50:.2f}/{s99:.2f} deg, ordinary lines '
              f'{o50:.2f}/{o99:.2f} deg {"PASS" if good else "FAIL"}', flush=True)
    results['seam_creases'] = out
    return ok


def main():
    os.makedirs(OUT, exist_ok=True)
    results = {}
    ok = True
    cases = [
        ('stride2_cores_odd_offsets', nested(96, 0.25, 5, [(3, -5), (-1, 2), (5, 5), (-7, 1)]), 48, True),
        ('stride1_no_cores', nested(64, 0.5, 4, [(1, -1), (-2, 3)]), 64, False),
        ('stride4_cores_odd_offsets', nested(128, 0.25, 3, [(5, -3), (-1, 7)]), 32, True),
        ('one_level', nested(80, 1.0, 1, [(0, 0)]), 40, False),
    ]
    for label, wins, res, cores in cases:
        _rm, good = check_case(label, wins, res, cores, results)
        ok &= good
    ok &= seam_creases(results)
    ok &= budget(results)
    results['pass'] = bool(ok)
    with open(os.path.join(OUT, 'test_mesh.json'), 'w') as f:
        json.dump(results, f, indent=1)
    print('[mesh] ' + ('ALL PASS' if ok else 'FAILURES'), flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
