"""Function fixtures of the glacial package on the Blender edition's GPU (PORT_PLAN.md 5.1, 5.3, 8.2 row P13): the
functions whose Blender counterpart on the GPU is not numpy's twin, run on the GPU device by Blender itself, on the
inputs of tests/glacial/glacial_expected.py's manifest:

  jump flood   each carve case (the floor runs' carve input: numpy's own seed textures cand0, seedA, seedB, seedC, its
               steps and profile uniforms): every pass of solvers/glacial.py jump_flood_run on the GPU device, so the
               port's candidates are compared with the kernel's own (the twin, numpy's float32 emulation of the
               kernel with numpy's rounding of pow and exp, can break a near tie the other way)
  wall_flutes  each flutes case: solvers/glacial.py wall_flutes with the GPU device, as refine_level and carve_level
               call it (dev = ctx.device): its noise from the world_noise_field kernel in float32 (core/world_noise.py
               field_gpu), where the fixture's numpy twin evaluates the noise in float64
  carve_level  the recipe's carve of the small V valley with the GPU device (the fixture's is the twin device's): the
               kernels' own float32 rounding, and their noise, as a Blender run has them

    bash run_blender.sh eidoverse/terrain/tests/glacial/gpu_fixtures.py -- [fixtures folder]   (a GPU job: on a shared
        machine behind $EIDO_GPU_WRAP)

Writes <fixtures>/gpu_fixtures.json ({cases: {label: {name: {file, shape, dtype}, ...}}, versions}) and its arrays
j00001.bin, ... beside the manifest; tests/glacial/functions_test.mjs reads them when they are there.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', 'parity')))
import _blender as B  # noqa: E402

B.import_blender_terrain()
from eidoblend.terrain.core import levels as L  # noqa: E402
from eidoblend.terrain.core.fields import Fields  # noqa: E402
from eidoblend.terrain.solvers import fluvial as FL  # noqa: E402
from eidoblend.terrain.solvers import glacial as G  # noqa: E402

args = B.script_args()
DIR = args[0] if args else os.path.normpath(os.path.join(HERE, '..', 'out', 'glacial', 'fixtures'))
F32 = np.float32
DTYPES = {'f32': '<f4', 'f64': '<f8', 'i32': '<i4', 'u8': 'u1'}
counter = [0]


def load(entry):
    a = np.fromfile(os.path.join(DIR, entry['file']), dtype=DTYPES[entry['dtype']])
    return a.reshape(entry['shape'])


def save(a):
    counter[0] += 1
    name = f'j{counter[0]:05d}.bin'
    np.asarray(a, F32).astype('<f4').tofile(os.path.join(DIR, name))
    return dict(file=name, shape=list(np.shape(a)), dtype='f32')


manifest = B.read_json(os.path.join(DIR, 'manifest.json'))
dev = FL.device('gpu')
out = {}
for c in manifest['cases']:
    if c['function'] == 'carve':
        v, lv = c['values'], c['level']
        cand0, sA, sB, sC = (load(c['arrays'][n]).astype(F32) for n in ('cand0', 'seedA', 'seedB', 'seedC'))
        cT, _, _ = G.jump_flood_run(dev, cand0, sA, sB, float(lv['cell']), v['profile_uniforms'], v['steps'], seedC=sC)
        cand = np.asarray(dev.read(cT), F32)
        twin = load(c['arrays']['cand_twin']).astype(F32).reshape(cand.shape)
        out[c['label']] = dict(cand_gpu=save(cand), slots_differing_from_twin=int(np.count_nonzero(cand != twin)))
        print(f"[gpu-fixtures] {c['label']}: the jump flood, {len(v['steps'])} passes: "
              f"{out[c['label']]['slots_differing_from_twin']} of {cand.size} slots differ from the twin", flush=True)
    elif c['function'] == 'wall_flutes':
        lv = L.Level.from_dict(c['level'])
        h = load(c['arrays']['h']).astype(F32)
        fl = np.asarray(G.wall_flutes(h, lv, c['args']['params'], int(c['args']['seed']), dev), np.float64)
        tw = load(c['arrays']['flutes']).astype(np.float64)
        rg = float(np.ptp(tw)) or 1.0
        out[c['label']] = dict(flutes_gpu=save(fl), gpu_vs_twin_over_range=float(np.max(np.abs(fl - tw))) / rg)
        print(f"[gpu-fixtures] {c['label']}: wall_flutes on the GPU, {out[c['label']]['gpu_vs_twin_over_range']:.3e} "
              'of range from the twin', flush=True)
    elif c['function'] == 'carve_level':
        lv = L.Level.from_dict(c['level'])
        h = load(c['arrays']['h_in']).astype(F32)
        fl_ = Fields(lv, {'h': h.copy(), 'bed': h.copy()})
        ctx = FL.StageContext(plan=[lv], index=0, level=lv, prepass=None, fresh=False, role='grow',
                              pins=FL.edge_pins(lv.n, h), shared={}, seed=1, base_elevation_m=0.0, device=dev,
                              log=lambda m: None)
        rec = G.carve_level(fl_, lv, c['args']['params'], int(c['args']['seed']), ctx, dev)
        ent = dict(record=B.jsonable(rec), fields={}, gpu_vs_twin_over_range={})
        for k, v in fl_.items():
            if np.ndim(v) != 2:
                continue
            ent['fields'][k] = save(v)
            if f'out_{k}' in c['arrays']:
                tw = load(c['arrays'][f'out_{k}']).astype(np.float64)
                rg = float(np.ptp(tw)) or 1.0
                ent['gpu_vs_twin_over_range'][k] = float(np.max(np.abs(np.asarray(v, np.float64) - tw))) / rg
        out[c['label']] = ent
        print(f"[gpu-fixtures] {c['label']}: the carve on the GPU, from the twin's: "
              + ', '.join(f'{k} {d:.1e}' for k, d in ent['gpu_vs_twin_over_range'].items()), flush=True)
B.write_json(os.path.join(DIR, 'gpu_fixtures.json'), dict(cases=out, versions=B.versions()))
print(os.path.join(DIR, 'gpu_fixtures.json'), flush=True)
