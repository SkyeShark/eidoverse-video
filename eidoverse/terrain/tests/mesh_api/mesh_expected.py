"""Blender's ring mesh, as fixtures for the mesh and API package's tests (PORT_PLAN.md 7.3, 7.4, 8.2 P4).

The Blender edition's own build/mesh.py and build/water.py, run by the Blender edition's own Python (Blender 5.2's
bundled Python 3.13, numpy 2.3.4: the plan's C6), on

  synthetic   the nested levels of blender/tests/terrain/mesh_api/test_mesh.py (windows at odd offsets on their
              parents' grids, strides 1, 2 and 4, with and without cores: every seam case), its own test surface
  saves       the levels of Blender Terrain.save files (<name>.npz + .json): their h fields, plan and mesh_res,
              cores when the plan has a hero level, as api._assemble_terrain builds them

and dumped per case into <out>/<case>/: the ring specs, layout() and ring_table(), every ring's lattice (xs, ys, the
vertex index grid, the heights as written, the lattice lines in metres), the vertices, triangles and
vertex_normals(), height_at / normal_at at 2,000 points across rings and seams, the open edges and T-junctions, the
triangles per ring, point attributes (two test fields on the synthetic stacks, one absent on every other level; the
saves' slope and flow masks; and mesh.py's own `level`), the seam creases of test_seam_crease.py (the points too),
and each level's lake geometry (build/water.py). The port's mesh is compared with these (mesh_test.mjs,
seam_test.mjs, water_test.mjs, collider_test.mjs).

    <Blender's python> -I -B eidoverse/terrain/tests/mesh_api/mesh_expected.py [--out DIR] [--cases a,b]
        [--save NAME=PATH]...

The Blender edition is found beside eidoverse/ (a merged checkout) or at $EIDO_BLENDER_EDITION (the root of a
checkout of the blender branch). Saves: --save NAME=PATH (PATH without or with .npz), else the default names
below looked up in that checkout's ignored output folders; a missing one is skipped, with the command that makes
it. -B keeps Python from writing bytecode into the Blender checkout, which these fixtures only read.
"""
import argparse
import json
import os
import platform
import subprocess
import sys
import time
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..'))
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'mesh_api', 'fixtures'))
RECORDED_COMMIT = '3dda52e'             # build/mesh.js's; water.py and test_mesh.py have not changed since f90c6fc
SOURCES = ['blender/eidoblend/terrain/build/mesh.py', 'blender/eidoblend/terrain/build/water.py',
           'blender/eidoblend/terrain/core/metrics.py', 'blender/tests/terrain/mesh_api/test_mesh.py']
ATTRIBUTE_MASKS = ('slope', 'flow')     # the masks a save's mesh is built with as point attributes, where it has them
# default saves: (name, path below the Blender checkout, without .npz)
DEFAULT_SAVES = [
    ('lauterbrunnen_film', 'blender/tests/terrain/out/surface_data/snap/lauterbrunnen'),
    ('fluvial_range_film', 'blender/tests/terrain/out/surface_data/snap/fluvial_range'),
    ('real_place_film_nofocus', 'blender/tests/terrain/out/surfacing_judge/terrains/real_place'),
    ('sea_cliffs_film', 'blender/tests/terrain/out/surfacing_judge/terrains/sea_cliffs'),      # a sea
    ('caldera_film', 'blender/tests/terrain/out/surfacing_judge/terrains/caldera'),            # a crater lake
]


def blender_edition():
    for root in (REPO, os.environ.get('EIDO_BLENDER_EDITION', '')):
        if root and os.path.isdir(os.path.join(root, 'blender', 'eidoblend', 'terrain', 'core')):
            return os.path.normpath(root)
    sys.exit('mesh_expected.py: no Blender edition: set EIDO_BLENDER_EDITION to the root of a checkout of the '
             'blender branch')


BLE = blender_edition()
sys.path.insert(0, os.path.join(BLE, 'blender'))
sys.path.insert(0, os.path.join(BLE, 'blender', 'tests', 'terrain', 'mesh_api'))
from eidoblend.terrain.build import mesh as M  # noqa: E402
from eidoblend.terrain.build import water as W  # noqa: E402
from eidoblend.terrain.core import levels as LV  # noqa: E402
import test_mesh as TM  # noqa: E402  (its main() is guarded; its rng is not used here)


def source_state():
    """The Blender checkout's commit and whether the sources these fixtures run differ from the recorded commit."""
    def git(*a):
        try:
            return subprocess.run(['git', '-C', BLE, *a], capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception:
            return None
    changed = {}
    for s in SOURCES:
        d = git('diff', '--stat', RECORDED_COMMIT, '--', s)
        changed[s] = bool(d)
    return dict(head=git('rev-parse', '--short', 'HEAD'), recorded=RECORDED_COMMIT, changed_since_recorded=changed)


class Dump:
    def __init__(self, folder):
        self.folder = folder
        os.makedirs(folder, exist_ok=True)
        self.arrays = {}

    def put(self, name, a, dtype):
        a = np.ascontiguousarray(np.asarray(a, dtype))
        fn = name + '.bin'
        a.tofile(os.path.join(self.folder, fn))
        self.arrays[name] = dict(file=fn, dtype={np.float32: 'f32', np.float64: 'f64', np.int32: 'i32',
                                                  np.uint32: 'u32'}[dtype], shape=list(a.shape))


def points(rm, plan, n, rng):
    """n points: a quarter uniform over the main tile (or the whole mesh), a quarter over the first hero level (or
    the finest level), the rest within two vertex spacings of a ring border (every ring after the first, cores
    included) or of its corners (test_api_blender.py's seam_and_ring_points, with the synthetic stacks' fallbacks)."""
    xmin, ymin, xmax, ymax = rm.bounds()
    k = n // 4
    if plan is not None:
        main = [lv for lv in plan if lv.role == 'main'][0]
        heroes = [lv for lv in plan if lv.role == 'hero']
        a = (main.x0, main.y0, main.x1, main.y1)
        b = (heroes[0].x0, heroes[0].y0, heroes[0].x1, heroes[0].y1) if heroes else a
    else:
        a = (xmin, ymin, xmax, ymax)
        w = rm.windows[-1]
        b = (w.x0, w.y0, w.x0 + w.side, w.y0 + w.side)
    xs = [rng.uniform(a[0], a[2], k), rng.uniform(b[0], b[2], k)]
    ys = [rng.uniform(a[1], a[3], k), rng.uniform(b[1], b[3], k)]
    rings = rm.rings[1:] or rm.rings
    for q in range(n - 2 * k):
        r = rings[q % len(rings)]
        sp = r.spec.sp * rm.unit
        x0, x1, y0, y1 = r.xm[0], r.xm[-1], r.ym[0], r.ym[-1]
        if q % 3 == 2:
            px, py = (x0, x1)[rng.integers(2)], (y0, y1)[rng.integers(2)]
        else:
            s = rng.integers(4)
            tt = rng.uniform(0, 1)
            px = [x0, x1, x0 + tt * (x1 - x0), x0 + tt * (x1 - x0)][s]
            py = [y0 + tt * (y1 - y0), y0 + tt * (y1 - y0), y0, y1][s]
        xs.append([px + rng.uniform(-2 * sp, 2 * sp)])
        ys.append([py + rng.uniform(-2 * sp, 2 * sp)])
    return np.concatenate(xs), np.concatenate(ys)


def creases(rm):
    """test_seam_crease.py's measure on this mesh: per seam, the crease across the ring border and across ordinary
    lattice lines three spacings inside the child and outside in the parent (degrees, 2,000 points each), and the
    points and step each was measured at (x, y, the unit normal across the line, the half step)."""
    out = {}
    for k in range(1, len(rm.rings)):
        child, parent = rm.rings[k], rm.rings[k - 1]
        sc, sp = child.spec.sp * rm.unit, parent.spec.sp * rm.unit
        rec = dict(spacing_m=[sp, sc])
        for part, inset, d in (('seam', 0.0, 0.25 * min(sc, sp)), ('inner', 3 * sc, 0.25 * sc),
                               ('outer', -3 * sp, 0.25 * sp)):
            pts = TM.border_points(child, inset)
            rec[part] = TM.crease_deg(rm, *pts, d)
            rec[part + '_points'] = np.stack(pts, 1)
            rec[part + '_step'] = float(d)
        out[k] = rec
    return out


def ring_triangle_counts(rm):
    return [int(len(M._ring_triangles(r, rm.rings[k + 1] if k + 1 < len(rm.rings) else None)))
            for k, r in enumerate(rm.rings)]


def dump_mesh(case, rm, plan, man, d, rng):
    t0 = time.perf_counter()
    man['layout'] = json.loads(json.dumps(rm.layout()))
    man['specs'] = [s.as_list() for s in rm.specs]
    man['origin'] = [float(rm.origin[0]), float(rm.origin[1])]
    man['unit'] = float(rm.unit)
    man['vertices'] = int(len(rm.verts))
    man['triangles'] = int(len(rm.tris))
    man['terrain_triangles'] = int(rm.terrain_triangles)
    man['skirt'] = rm.skirt
    man['bounds'] = list(rm.bounds())
    man['ring_triangles'] = ring_triangle_counts(rm)
    man['ring_table'] = json.loads(json.dumps(rm.ring_table()))
    man['ring_table_from_layout'] = json.loads(json.dumps(M.ring_table(rm.layout())))
    man['attributes'] = sorted(rm.attrs)
    for n, a in rm.attrs.items():
        d.put('attr_' + n, a, np.float32)
    rings = []
    for k, r in enumerate(rm.rings):
        d.put(f'xs_{k}', r.xs, np.int32)
        d.put(f'ys_{k}', r.ys, np.int32)
        d.put(f'idx_{k}', r.idx, np.int32)
        d.put(f'Z_{k}', r.Z, np.float32)
        d.put(f'xm_{k}', r.xm, np.float32)
        d.put(f'ym_{k}', r.ym, np.float32)
        rings.append(dict(spec=r.spec.as_list(), hole=list(r.hole) if r.hole else None,
                          hole_lines=list(r.hole_lines) if r.hole_lines else None, v0=int(r.v0),
                          own=int(r.own.sum()), nx=int(len(r.xs)), ny=int(len(r.ys))))
    man['rings'] = rings
    d.put('verts', rm.verts, np.float32)
    d.put('tris', rm.tris, np.int32)
    vn = rm.vertex_normals()
    d.put('vn', vn, np.float64)
    nv = rm.skirt['first_vertex'] if rm.skirt else len(rm.verts)
    man['open_edges'] = int(len(rm.open_edges()))
    r0 = rm.rings[0]
    man['open_edges_expected'] = 2 * (len(r0.xs) - 1) + 2 * (len(r0.ys) - 1)
    man['t_junctions'] = int(rm.t_junctions())
    x, y = points(rm, plan, 2000, rng)
    d.put('px', x, np.float64)
    d.put('py', y, np.float64)
    d.put('hz', rm.height_at(x, y), np.float64)
    d.put('ring_of', rm.ring_of(x, y), np.int32)
    d.put('n_smooth', rm.normal_at(x, y, smooth=True), np.float64)
    d.put('n_flat', rm.normal_at(x, y, smooth=False), np.float64)
    # height_at at every terrain vertex (its own z) and outside the outermost window (its edge)
    hv = rm.height_at(rm.verts[:nv, 0].astype(np.float64), rm.verts[:nv, 1].astype(np.float64))
    man['vertex_height_max_err_m'] = float(np.abs(hv - rm.verts[:nv, 2]).max())
    xmin, ymin, xmax, ymax = rm.bounds()
    ox = np.array([xmin - 100.0, xmax + 37.5, 0.5 * (xmin + xmax), xmin - 1e4])
    oy = np.array([0.5 * (ymin + ymax), ymin - 3.25, ymax + 1e3, ymin - 1e4])
    d.put('outside_xy', np.stack([ox, oy], 1), np.float64)
    d.put('outside_z', rm.height_at(ox, oy), np.float64)
    cr = creases(rm)
    man['creases'] = {}
    for k, c in cr.items():
        for part in ('seam', 'inner', 'outer'):
            d.put(f'crease_{part}_{k}', c[part], np.float64)
            d.put(f'crease_{part}_points_{k}', c[part + '_points'], np.float64)
        p = lambda a, q: float(np.percentile(a, q))  # noqa: E731
        ref = np.concatenate([c['inner'], c['outer']])
        good = (p(c['seam'], 50) <= p(ref, 50) * 1.25 + 0.1 and p(c['seam'], 99) <= p(ref, 99) * 1.25 + 0.1)
        man['creases'][str(k)] = dict(spacing_m=c['spacing_m'], seam_p50_p90_p99=[p(c['seam'], q) for q in (50, 90, 99)],
                                      ordinary_p50_p90_p99=[p(ref, q) for q in (50, 90, 99)], pass_=bool(good),
                                      steps_m=dict(seam=c['seam_step'], inner=c['inner_step'], outer=c['outer_step']))
    man['seconds_dump_mesh'] = round(time.perf_counter() - t0, 2)


def dump_lakes(plan, fields, rm, sea, man, d):
    """build/water.py's lake cells and geometry per level (lake_objects without Blender), and the sea grid."""
    class _T:                                   # what water.lake_objects reads of a Terrain
        pass
    t = _T()
    t.levels = plan
    t.info = dict(sea_level=sea)
    t.ring = rm
    t.height_at = rm.height_at
    lakes = []
    for k, (lv, f) in enumerate(zip(plan, fields)):
        child = plan[k + 1] if k + 1 < len(plan) else None
        cells = W._lake_cells(lv, f, child, 0.5, sea)
        if not cells:
            continue
        verts, quads = W.lake_geometry(lv, cells)
        depth = np.maximum(verts[:, 2] - rm.height_at(verts[:, 0], verts[:, 1]), 0.0)
        d.put(f'lake_verts_{k}', verts, np.float32)
        d.put(f'lake_vertsd_{k}', verts, np.float64)
        d.put(f'lake_quads_{k}', quads, np.int32)
        d.put(f'lake_depth_{k}', depth, np.float32)
        lakes.append(dict(level=k, lakes=[dict(level_m=float(z), cells=int(c.sum())) for z, c in cells],
                          vertices=int(len(verts)), quads=int(len(quads))))
    man['lakes'] = lakes
    if sea is not None:
        xmin, ymin, xmax, ymax = rm.bounds()
        n = W.SEA_GRID
        xs, ys = np.linspace(xmin, xmax, n), np.linspace(ymin, ymax, n)
        X, Y = np.meshgrid(xs, ys)
        verts = np.stack([X.ravel(), Y.ravel(), np.full(X.size, float(sea))], 1)
        depth = np.maximum(float(sea) - rm.height_at(verts[:, 0], verts[:, 1]), 0.0)
        d.put('sea_verts', verts, np.float32)
        d.put('sea_depth', depth, np.float32)
        man['sea'] = dict(level_m=float(sea), n=n)


def synthetic_cases():
    """test_mesh.py's own cases: (label, windows, mesh_res, cores)."""
    return [
        ('stride2_cores_odd_offsets', TM.nested(96, 0.25, 5, [(3, -5), (-1, 2), (5, 5), (-7, 1)]), 48, True),
        ('stride1_no_cores', TM.nested(64, 0.5, 4, [(1, -1), (-2, 3)]), 64, False),
        ('stride4_cores_odd_offsets', TM.nested(128, 0.25, 3, [(5, -3), (-1, 7)]), 32, True),
        ('one_level', TM.nested(80, 1.0, 1, [(0, 0)]), 40, False),
        ('rough_5x512_cores', TM.nested(512, 0.5, 5, [(0, 0)]), 256, True),
    ]


def run_synthetic(label, wins, res, cores, out, base_man):
    t0 = time.perf_counter()
    surf = TM.rough if label.startswith('rough') else TM.surface
    hs = TM.level_arrays(wins, surf)
    hs32 = [np.asarray(h, np.float32) for h in hs]
    # two point attributes: a field every level has, and one that every other level lacks (None: 0 there)
    wave = [np.asarray(a, np.float32) for a in TM.level_arrays(wins, lambda X, Y: 0.5 + 0.5 * np.sin(X / 9.0) * np.cos(Y / 7.0))]
    ramp = [np.asarray(a, np.float32) if k % 2 == 0 else None
            for k, a in enumerate(TM.level_arrays(wins, lambda X, Y: 0.01 * X - 0.02 * Y + 3.0))]
    attrs = dict(wave=wave, ramp=ramp)
    rm = M.build_rings(wins, hs32, attrs, cores=cores, mesh_res=res)
    d = Dump(os.path.join(out, label))
    man = dict(base_man, case=label, kind='synthetic', surface=surf.__name__, mesh_res=res, cores=cores,
               windows=[[w.x0, w.y0, w.cell, w.n] for w in wins])
    for k, h in enumerate(hs32):
        d.put(f'h_{k}', h, np.float32)
        d.put(f'in_wave_{k}', wave[k], np.float32)
        if ramp[k] is not None:
            d.put(f'in_ramp_{k}', ramp[k], np.float32)
    man['attribute_inputs'] = dict(wave=[True] * len(wins), ramp=[a is not None for a in ramp])
    man['seconds_build'] = round(time.perf_counter() - t0, 2)
    dump_mesh(label, rm, None, man, d, np.random.default_rng(11))
    man['arrays'] = d.arrays
    with open(os.path.join(d.folder, 'manifest.json'), 'w') as f:
        json.dump(man, f, indent=1)
    print(f'[mesh_expected] {label}: {man["triangles"]:,} triangles, {man["vertices"]:,} vertices, open edges '
          f'{man["open_edges"]}/{man["open_edges_expected"]}, t-junctions {man["t_junctions"]}', flush=True)


def run_save(label, base, out, base_man):
    t0 = time.perf_counter()
    with open(base + '.json', encoding='utf-8') as f:
        meta = json.load(f)
    plan = [LV.Level.from_dict(dd) for dd in meta['plan']]
    fields = [dict() for _ in plan]
    masks = [dict() for _ in plan]
    with np.load(base + '.npz', allow_pickle=False) as z:
        for k in z.files:
            lvl, kind, nm = k.split('__', 2)
            if kind == 'f' and nm in ('h', 'water', 'bed'):
                fields[int(lvl[1:])][nm] = z[k]
            elif kind == 'm' and nm in ATTRIBUTE_MASKS:
                masks[int(lvl[1:])][nm] = z[k].astype(np.float32)      # float32, as Terrain.load hands them on
    t_load = time.perf_counter() - t0
    cores = any(lv.role == 'hero' for lv in plan)
    mesh_res = int(meta.get('mesh_res') or M.MESH_RES)
    # the masks as point attributes, as api._assemble_terrain passes them ({name: [per level, or None]})
    names = sorted(set().union(*[set(m) for m in masks]))
    attrs = {n: [m.get(n) for m in masks] for n in names}
    t1 = time.perf_counter()
    rm = M.build_rings(plan, [f['h'] for f in fields], attrs, cores=cores, mesh_res=mesh_res)
    t_build = time.perf_counter() - t1
    d = Dump(os.path.join(out, label))
    rel = os.path.relpath(base, BLE).replace('\\', '/')
    man = dict(base_man, case=label, kind='save', save=rel, recipe=meta['recipe']['name'], quality=meta.get('quality'),
               focus=meta.get('focus'), mesh_res=mesh_res, cores=cores, sea_level=meta.get('sea_level'),
               plan=meta['plan'], seconds_load=round(t_load, 2), seconds_build=round(t_build, 2))
    dump_mesh(label, rm, plan, man, d, np.random.default_rng(11))
    dump_lakes(plan, fields, rm, meta.get('sea_level'), man, d)
    man['arrays'] = d.arrays
    with open(os.path.join(d.folder, 'manifest.json'), 'w') as f:
        json.dump(man, f, indent=1)
    print(f'[mesh_expected] {label}: {len(plan)} levels, {man["triangles"]:,} triangles, {man["vertices"]:,} '
          f'vertices, open edges {man["open_edges"]}/{man["open_edges_expected"]}, t-junctions {man["t_junctions"]}, '
          f'built in {t_build:.1f} s', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--cases')
    ap.add_argument('--save', action='append', default=[], help='NAME=PATH of a Blender Terrain.save (no extension)')
    a = ap.parse_args()
    want = set(a.cases.split(',')) if a.cases else None
    base_man = dict(python=platform.python_version(), python_executable=os.path.basename(sys.executable),
                    numpy=np.__version__, zlib=zlib.ZLIB_VERSION, source=source_state(),
                    made=time.strftime('%Y-%m-%d %H:%M:%S'))
    os.makedirs(a.out, exist_ok=True)
    for label, wins, res, cores in synthetic_cases():
        if want is None or label in want:
            run_synthetic(label, wins, res, cores, a.out, base_man)
    saves = dict((n, os.path.join(BLE, p)) for n, p in DEFAULT_SAVES)
    for s in a.save:
        n, _, p = s.partition('=')
        saves[n] = os.path.splitext(p)[0] if p.endswith('.npz') or p.endswith('.json') else p
    for label, base in saves.items():
        if want is not None and label not in want:
            continue
        if not (os.path.isfile(base + '.npz') and os.path.isfile(base + '.json')):
            print(f'[mesh_expected] SKIP {label}: no save at {base}.npz; make one with\n    bash run_blender.sh '
                  'blender/eidoblend/terrain/bake.py --recipe real_place --param dem=lauterbrunnen --focus 583.7,1908.9 '
                  '--seed 1 --quality film --save --out <dir>\nand pass --save NAME=<dir>/<name>', flush=True)
            continue
        run_save(label, base, a.out, base_man)
    with open(os.path.join(a.out, 'versions.json'), 'w') as f:
        json.dump(base_man, f, indent=1)


if __name__ == '__main__':
    main()
