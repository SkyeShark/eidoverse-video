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

# ------------------------------------------------------------------------------------------------- write ---
manifest = {'source': 'tests/karst_coast/karst_coast_expected.py', 'key': B.source_key(), 'versions': B.versions(),
            'date': time.strftime('%Y-%m-%d %H:%M:%S'), 'seconds': round(time.perf_counter() - t_start, 2),
            'cases': cases}
B.write_json(MANIFEST, manifest)
print(f'{len(cases)} cases in {OUT} ({manifest["seconds"]} s)')
