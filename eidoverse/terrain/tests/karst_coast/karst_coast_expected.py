"""Function fixtures of the karst-and-coast package (PORT_PLAN.md 5.1 "function fixtures": a GPU replacement of numpy
code against that numpy function, and the plan's numbers): the Blender edition's own functions of solvers/karst.py
and solvers/coast.py, run by Blender's Python on inputs the floor runs do not reach.

    <Blender's python> -I eidoverse/terrain/tests/karst_coast/karst_coast_expected.py [out folder] [--only a,b]

Parts (--only):
  tables    coast._dirs(16) and _inv_dirs(16) (the fetch kernel's constants), karst's 16 gradient directions, the
            numpy noise functions at scattered points (noise2, fbm2, _noise1_periodic, pinnacles, _cluster_raw), the
            plan's small functions (wall_table, rib_harmonics, scarp_sectors, poisson_disc, _knn, _knn_median,
            _dijkstra, _chaikin, _resample, _curvature, _river_course), each on a few inputs
  evaluate  karst.evaluate on hero, film and draft windows of the seed-1 and seed-2 plans of the tower_karst floor runs
            (fenglin) and of a fengcong plan: every output, and the plan's cockpit floor map
  coast     coast.py's numpy parts that become kernels: land_shape, column_table, face_profile, beach_profile,
            scar_field's hash, sea_phi, retreat_field's arithmetic, on synthetic levels

Writes <out>/manifest.json (cases: function, arguments, outputs) and the arrays as little-endian .bin files. Default
out: eidoverse/terrain/tests/out/karst_coast/fixtures/. numpy only (no GPU).
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'parity'))
import _blender as B  # noqa: E402

B.bare_terrain_package()
import numpy as np  # noqa: E402

from eidoblend.terrain.solvers import coast as CO  # noqa: E402
from eidoblend.terrain.solvers import karst as K  # noqa: E402

args = [a for a in sys.argv[1:]]
ONLY = None
if '--only' in args:
    i = args.index('--only')
    ONLY = set(args[i + 1].split(','))
    del args[i:i + 2]
OUT = args[0] if args else os.path.normpath(os.path.join(HERE, '..', 'out', 'karst_coast', 'fixtures'))
os.makedirs(OUT, exist_ok=True)
MANIFEST = os.path.join(OUT, 'manifest.json')
old = B.read_json(MANIFEST, {}) or {}
cases = [c for c in old.get('cases', []) if ONLY is not None and c.get('part') not in ONLY]
counter = [max([int(f[1:6]) for f in os.listdir(OUT) if f.startswith('a') and f.endswith('.bin')] + [0])]
DT = {np.dtype(np.float32): 'f32', np.dtype(np.float64): 'f64', np.dtype(np.int32): 'i32', np.dtype(np.int64): 'i64',
      np.dtype(np.uint32): 'u32', np.dtype(np.int8): 'i8', np.dtype(np.uint8): 'u8', np.dtype(np.bool_): 'u8',
      np.dtype(np.complex128): 'c128'}


def arr(a):
    a = np.ascontiguousarray(a)
    if a.dtype == np.bool_:
        a = a.astype(np.uint8)
    dt = DT[a.dtype]
    counter[0] += 1
    name = f'a{counter[0]:05d}.bin'
    a.astype(a.dtype.newbyteorder('<')).tofile(os.path.join(OUT, name))
    return {'file': name, 'shape': list(a.shape), 'dtype': dt}


def add(part, function, args_, outputs, label, inputs=None):
    cases.append({'part': part, 'label': label, 'function': function, 'args': args_,
                  'inputs': {k: arr(v) for k, v in (inputs or {}).items()},
                  'outputs': {k: arr(np.asarray(v)) for k, v in outputs.items()}})


def want(part):
    return ONLY is None or part in ONLY


t_start = time.perf_counter()

# ------------------------------------------------------------------------------------------------- tables ---
F32 = np.float32
if want('tables'):
    add('tables', 'coast._dirs', {'n': 16}, {'dirs': CO._dirs(16), 'inv': CO._inv_dirs(16)}, 'the fetch directions')
    add('tables', 'karst._GX16', {}, {'gx': K._GX16, 'gy': K._GY16}, "karst's 16 gradient directions")
    # the whole jump flood on the twin device: blender/tests/terrain/coast/test_coast_gpu.py's wavy level set
    from eidoblend.terrain.solvers import fluvial as FL
    jj, ii = np.mgrid[0:80, 0:96].astype(np.float64)
    phi = (jj - 40 - 7 * np.sin(ii / 7.0) - 3 * np.cos(ii / 3.1)) * 1.3
    phi = np.where((ii - 70) ** 2 + (jj - 15) ** 2 < 36, 5.0, phi)
    phi32, pay = phi.astype(F32), (ii * 0.01 + jj * 0.001).astype(F32)
    d, p = CO.nearest_crossing(FL.device('twin'), phi32, pay)
    add('tables', 'coast.nearest_crossing', {}, {'d': d, 'payload': p},
        "the jump flood (seed + JFA+2) on the twin device, test_coast_gpu.py's wavy level set",
        inputs={'phi': phi32, 'pay': pay})
    from eidoblend.terrain.recipes import sea_cliffs as SCR
    col = SCR._flint_column()
    add('tables', 'sea_cliffs._flint_column', {}, {'thickness': np.array([r[1] for r in col['formations']], np.float64)},
        "the chalk face's flint column (default_rng(1907))")
    for name in ('chalk', 'moher'):
        zs, run = CO.column_table(name, 0.0)
        add('tables', 'coast.column_table', {'column': name}, {'zs': zs, 'run': run}, f'the {name} column table')

# ----------------------------------------------------------------------------------------------- evaluate ---
# karst.evaluate on windows the draft floor never reaches: hero cells (fluting at 2, 1 and 0.5 m; the ledges' field at
# 2.5 m and under; the benches where 13 m spans 4 cells), a film cell, a window across the main tile's edge (the
# floor map inside, the level's own cockpits outside), and a fengcong plan (the plinth, no river). The plans are the
# tower_karst recipe's (seed 1: its floor run's own call) and a fengcong one; the JS test makes them again.
FENGLIN = dict(kind='fenglin', spacing_m=210.0, median_height_m=150.0, wall_deg=82.0, cluster_cover=0.8, plinth_m=0.0,
               base_m=45.0, river=True, river_width_m=130.0)
FENGCONG = dict(kind='fengcong')
DOMAIN = [-16000.0, -16000.0, 32000.0]
MAIN = [-4000.0, -4000.0, 8000.0]
if want('evaluate'):
    plans = {}
    for name, seed, params in (('fenglin', 1, FENGLIN), ('fengcong', 3, FENGCONG)):
        t0 = time.perf_counter()
        plans[name] = K.plan_karst(seed, DOMAIN, params, [0.0, 0.0], MAIN)
        print(f'plan {name} seed {seed}: {plans[name].count} towers, {time.perf_counter() - t0:.1f} s', flush=True)
    windows = [('fenglin', 'hero 0.5 m (both flutes, ledges, benches)', 'H05', -300.0, 700.0, 0.5, 256),
               ('fenglin', 'hero 1 m (one flute)', 'H1', -380.0, 620.0, 1.0, 256),
               ('fenglin', 'hero 2 m (one flute, ledges)', 'H2', -500.0, 500.0, 2.0, 256),
               ('fenglin', 'hero 4 m (2 x 2 subsamples, benches off)', 'H4', -700.0, 300.0, 4.0, 256),
               ('fenglin', 'film 7.8 m', 'F8', -2000.0, -2000.0, 7.8125, 512),
               ('fenglin', 'across the main tile edge at 15.6 m (floor map and own cockpits)', 'E16', 2000.0, -1000.0, 15.625, 384),
               ('fengcong', 'fengcong 15.6 m (the plinth)', 'C16', -4000.0, -4000.0, 15.625, 512),
               ('fengcong', 'fengcong hero 1 m', 'C1', 200.0, -300.0, 1.0, 256)]
    for name, label, tag, x0, y0, cell, n in windows:
        plan = plans[name]
        t0 = time.perf_counter()
        out = K.evaluate(plan, x0, y0, cell, n)
        sec = time.perf_counter() - t0
        add('evaluate', 'karst.evaluate', {'plan': name, 'seed': plan.seed, 'params': FENGLIN if name == 'fenglin' else FENGCONG,
                                            'domain': DOMAIN, 'via': [0.0, 0.0], 'main': MAIN, 'x0': x0, 'y0': y0,
                                            'cell': cell, 'n': n, 'seconds': round(sec, 2)},
            {k: out[k] for k in ('h', 'bed', 'deposit', 'talus', 'water', 'plain', 'Sc', 'tower_id')},
            f'evaluate {name} {label}: {n}^2 at {cell:g} m from ({x0:g}, {y0:g})')
        print(f'evaluate {tag}: {sec:.1f} s', flush=True)
    for name, plan in plans.items():
        fx0, fy0, fcell, fmap = K._floor_map(plan)
        add('evaluate', 'karst._floor_map', {'plan': name, 'seed': plan.seed, 'x0': fx0, 'y0': fy0, 'cell': fcell},
            {'floors': fmap}, f'the floor map of the {name} plan ({fmap.shape[0]}^2 at {fcell:g} m)')

# ------------------------------------------------------------------------------------------------- coast ---
# op 'coast' on the twin device (numpy's world noise: the oracle of the GPU noise both editions run) on
# blender/tests/terrain/coast/test_coast_gpu.py's synthetic downland coast (256^2 at 4 m: headlands and bays), with
# that test's parameters (stacks, sheltered beaches) and with the chalk's (its bedded column, scars, a shingle beach of
# varying width); and op 'coast_land' on a fresh level. The Blender test's own grade for its GPU against this twin:
# the surface within 0.05 m on 99.9 % of cells.
if want('coast'):
    from eidoblend.terrain.core.fields import Fields
    from eidoblend.terrain.core.levels import Level
    from eidoblend.terrain.solvers import fluvial as FL
    TWIN = FL.device('twin')

    def synthetic_coast(n=256, cell=4.0):
        side = n * cell
        lv = Level(index=0, role='main', x0=-side / 2, y0=-side / 2, side=side, cell=cell, n=n)
        X, Y = lv.xy()
        land = 55.0 + 0.04 * Y + 9.0 * np.sin(X / 61.0) + 4.0 * np.cos(X / 23.0 + Y / 37.0)
        shore = -150.0 + 60.0 * np.sin(X / 170.0) + 25.0 * np.cos(X / 53.0)
        land = np.where(Y < shore, -5.0 - 0.01 * (shore - Y), land)
        return lv, land

    CHALK = dict(retreat_m=80.0, fetch_max_m=4000.0, column='chalk', column_dip_deg=1.0, column_dip_azimuth_deg=90.0,
                 weakness_scales_m=[1500.0, 600.0], weakness=0.06, crenel_m=1.0, crenel_scales_m=[60.0, 25.0],
                 talus_frac=0.07, talus_max_m=14.0, face_spread_deg=4.0, shingle_m=3.6, shingle_w_m=45.0,
                 shingle_berm=0.35, shingle_var=0.3, platform_top_m=-0.4, platform_rough_m=0.2,
                 platform_slope_deg=0.4, scars=0.45, beach_exposure=[0.25, 0.33])
    for label, params, seed in (
            ("test_coast_gpu.py's case (stacks 0.5, weakness 0.3, sheltered beaches)",
             {'retreat_m': 80.0, 'fetch_max_m': 4000.0, 'weakness': 0.3, 'stacks': 0.5, 'beach_exposure': [0.38, 0.46]}, 3),
            ("the chalk's parameters (the bedded column, scars, a shingle beach of varying width)", CHALK, 1)):
        lv, land = synthetic_coast()
        f = Fields(lv, {'h': land.astype(F32), 'bed': land.astype(F32)})
        ctx = FL.StageContext(plan=[lv], index=0, level=lv, fresh=False, role='grow', pins=None, shared={},
                              sea_level=0.0, device=TWIN, log=lambda m: None)
        t0 = time.perf_counter()
        CO.op_coast(f, lv, params, seed, ctx=ctx)
        add('coast', 'coast.op_coast', {'level': lv.to_dict(), 'params': params, 'seed': seed, 'sea_level': 0.0,
                                        'seconds': round(time.perf_counter() - t0, 2), 'log': ctx.shared.get('coast_log')},
            {k: np.asarray(f[k], np.float32) for k in f}, f'op coast on the twin: {label}', inputs={'land': land.astype(F32)})
    lv = Level(index=0, role='context', x0=-12000.0, y0=-12000.0, side=24000.0, cell=93.75, n=256)
    land_p = dict(azimuth_deg=200.0, offset_m=390.0, retreat_m=300.0, wiggle_m=120.0, U_m_per_yr=0.0, start_m=140.0,
                  start_roughness=0.04, start_scales_m=[3000.0], texture_scales_m=[6000.0, 3000.0],
                  wiggle_scale_m=2500.0, coast_frac=0.65, rise_m=3000.0, inland_gain=0.25, tilt_m=5000.0, texture=0.08)
    f = Fields(lv, {})
    ctx = FL.StageContext(plan=[lv], index=0, level=lv, fresh=True, role='grow', pins=None, shared={}, sea_level=0.0,
                          device=TWIN, log=lambda m: None)
    CO.op_coast_land(f, lv, land_p, 1, ctx=ctx)
    add('coast', 'coast.op_coast_land', {'level': lv.to_dict(), 'params': land_p, 'seed': 1},
        {k: np.asarray(f[k], np.float32) for k in f}, "op coast_land on a fresh level (sea_cliffs' chalk land)")

# ------------------------------------------------------------------------------------------------- write ---
manifest = {'source': 'tests/karst_coast/karst_coast_expected.py', 'key': B.source_key(), 'versions': B.versions(),
            'date': time.strftime('%Y-%m-%d %H:%M:%S'), 'seconds': round(time.perf_counter() - t_start, 2),
            'cases': cases}
B.write_json(MANIFEST, manifest)
print(f'{len(cases)} cases in {OUT} ({manifest["seconds"]} s)')
