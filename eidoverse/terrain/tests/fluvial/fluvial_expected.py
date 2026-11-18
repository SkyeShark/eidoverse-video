"""Function fixtures of the fluvial package (PORT_PLAN.md 5.1 "function fixtures": a GPU replacement of numpy code
against that numpy function): the Blender edition's own numpy functions of solvers/fluvial.py and hillslope.py that
the port runs as kernels of its own (kernels/fluvial/), on small levels whose cells resolve every scale the draft floor
runs never reach (breakup and k_breakup at 60, 20 and 7 m need cells of 15 m and less, threshold_gain a level below
the main one), with every option the recipes do not use at draft (a tilt, a fault's length, a sea level, a refine
mode's own slopes, flatten areas). The functions are called with no device, so their noise is numpy's own world-noise
field (core/world_noise.field, the oracle the port's GPU noise is checked against).

    <Blender's python> -I eidoverse/terrain/tests/fluvial/fluvial_expected.py [out folder]

Writes <out>/manifest.json (cases: function, arguments, the level, outputs) and the arrays as little-endian .bin
files (float32 or float64, row 0 south). Default out: eidoverse/terrain/tests/out/fluvial/fixtures/. numpy only.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'parity'))
import _blender as B  # noqa: E402

B.bare_terrain_package()
import numpy as np  # noqa: E402

from eidoblend.terrain.core.levels import Level  # noqa: E402
from eidoblend.terrain.solvers import fluvial as FL  # noqa: E402
from eidoblend.terrain.solvers import hillslope as HS  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.normpath(os.path.join(HERE, '..', 'out', 'fluvial', 'fixtures'))
os.makedirs(OUT, exist_ok=True)
cases = []
counter = [0]


def arr(a):
    a = np.ascontiguousarray(a)
    dt = {np.dtype(np.float32): 'f32', np.dtype(np.float64): 'f64', np.dtype(np.int32): 'i32'}[a.dtype]
    counter[0] += 1
    name = f'a{counter[0]:05d}.bin'
    a.astype(a.dtype.newbyteorder('<')).tofile(os.path.join(OUT, name))
    return {'file': name, 'shape': list(a.shape), 'dtype': dt}


def lvl(n, cell, x0=None, y0=None, depth=0, role='main', index=0):
    x0 = -0.5 * n * cell if x0 is None else x0
    y0 = -0.5 * n * cell if y0 is None else y0
    return Level(index, role, float(x0), float(y0), n * cell, float(cell), n, None, 2, [], 16, depth)


def add(function, level, args, outputs, label):
    cases.append({'label': label, 'function': function, 'level': level.to_dict(), 'args': args,
                  'outputs': {k: arr(v) for k, v in outputs.items()}})


SEED = 7
# erodibility: roughness, k_breakup (scales resolved at 2 m), k_contrast, faults with wander and length
for cell, n in ((2.0, 160), (40.0, 128)):
    lv = lvl(n, cell, x0=-6000.0 if cell > 10 else 900.0, y0=1200.0)
    params = {'K': 2e-5, 'roughness': 0.6, 'roughness_scales_m': [2000.0, 300.0, 50.0, 12.0], 'k_breakup': 0.5,
              'breakup_scales_m': [60.0, 20.0, 7.0], 'k_contrast': 0.4, 'k_contrast_scales_m': [3000.0, 1500.0],
              'faults': [{'centre': [100.0, -200.0], 'azimuth_deg': 70.0, 'offset_m': 40.0, 'width_m': 60.0,
                          'k_factor': 3.5, 'wander_m': 30.0, 'wander_wavelength_m': 900.0, 'length_m': 500.0},
                         {'centre': [0.0, 0.0], 'azimuth_deg': 160.0, 'offset_m': -2300.0, 'width_m': 300.0,
                          'k_factor': 2.5}]}
    add('erodibility', lv, {'params': params, 'seed': SEED}, {'K': FL.erodibility(lv, params, SEED, None).astype(np.float64)},
        f'erodibility every term at {cell:g} m')
    add('fault_zones', lv, {'faults': params['faults'], 'seed': SEED},
        {'F': FL.fault_zones(params['faults'], lv, SEED, None).astype(np.float64)}, f'fault_zones at {cell:g} m')

# threshold: noise, breakup at the scales a 2 m level resolves, outcrops, the gain two levels below the main one
for cell, n, below in ((2.0, 160, 2), (20.0, 128, 0)):
    lv = lvl(n, cell, x0=300.0, y0=-700.0, depth=-below, role='hero' if below else 'main')
    params = {'threshold_deg': 29.0, 'threshold_noise': 0.2, 'threshold_scale_m': 400.0 if cell > 10 else 60.0,
              'breakup': 0.3, 'breakup_scales_m': [60.0, 20.0, 7.0], 'outcrops': 0.5, 'outcrop_scale_m': 120.0 if cell > 10 else 30.0,
              'threshold_gain': 0.08}
    add('threshold', lv, {'params': params, 'seed': SEED, 'below_main': below},
        {'Sc': FL.threshold(lv, params, SEED, None, below_main=below)}, f'threshold at {cell:g} m, {below} below the main')

# composite uplift and start: a shape with a regional background, a cut, a tilt; and a background alone (ridged)
lv = lvl(128, 150.0, x0=-9600.0, y0=-9600.0)
comp = {'shape': {'kind': 'ridge', 'centre': [0.0, 0.0], 'azimuth_deg': 70.0, 'length_m': 12000.0, 'width_m': 3000.0,
                  'spurs': 6, 'spur_length_m': 1500.0, 'texture': 0.3},
        'regional': {'kind': 'fbm', 'fraction': 0.5, 'wavelength_m': 6000.0, 'texture': 0.6, 'octaves': 3, 'blend': 0.1,
                     'cut': 1.25},
        'tilt': {'azimuth_deg': 120.0, 'per_km': 0.04, 'centre': [500.0, -300.0]}}
u = FL.composite_uplift(comp, lv, SEED, None)
add('composite_uplift', lv, {'params': comp, 'seed': SEED}, {'u': u}, 'composite_uplift: ridge + regional (cut) + tilt')
add('composite_start', lv, {'params': comp, 'seed': SEED, 'height_m': 600.0, 'roughness': 0.4, 'peak': float(np.max(u))},
    {'h': FL.composite_start(comp, u, lv, SEED, None, 600.0, 0.4, float(np.max(u)))}, 'composite_start of it')
comp2 = {'regional': {'kind': 'ridged', 'fraction': 0.9, 'wavelength_m': 2500.0, 'texture': 0.8, 'octaves': 3}}
u2 = FL.composite_uplift(comp2, lv, SEED + 1, None)
add('composite_uplift', lv, {'params': comp2, 'seed': SEED + 1}, {'u': u2}, 'composite_uplift: a ridged background alone')
add('composite_start', lv, {'params': comp2, 'seed': SEED + 1, 'height_m': 48.0, 'roughness': 0.6, 'peak': float(np.max(u2))},
    {'h': FL.composite_start(comp2, u2, lv, SEED + 1, None, 48.0, 0.6, float(np.max(u2)))}, 'composite_start of it')

# edge pins with a sea, and the rigid mask (sea and flatten areas)
lv = lvl(96, 10.0, x0=-480.0, y0=-480.0)
yy, xx = np.mgrid[0:96, 0:96]
h = (np.sin(xx / 9.0) * 6.0 + (yy - 40) * 0.3 + 2.0).astype(np.float32)
pins = FL.edge_pins(96, h, sea_level=0.75)
add('edge_pins', lv, {'h': arr(h), 'sea_level': 0.75}, {'pin_w': pins['pin_w'], 'pin_h': pins['pin_h']}, 'edge_pins with a sea')
ctx = FL.StageContext(plan=[lv], index=0, level=lv, sea_level=0.75,
                      flatten=[{'at': [40.0, -60.0], 'radius': 55.0, 'falloff': 30.0}, {'at': [-200.0, 150.0], 'radius': 20.0}])
add('sea_flat', lv, {'h': arr(h), 'sea_level': 0.75, 'flatten': ctx.flatten},
    {'rigid': FL._sea_flat({'h': h}, ctx, (96, 96)).astype(np.float32)}, '_sea_flat: the sea and two flatten areas')

# the lock's targets: offset block means of a rough field, blocks 2, 8, 16 and 32 at their four offsets
lv = lvl(256, 5.0)
rng = np.random.default_rng(11)
h0 = (1500.0 + np.cumsum(rng.standard_normal((256, 256)), 0) * 3.0 + np.cumsum(rng.standard_normal((256, 256)), 1) * 2.0
      ).astype(np.float32)
hid = arr(h0)
for b in (2, 8, 16, 32):
    half = max(b // 2, 1)
    mb = (256 // b + 1, 256 // b + 1)
    for px, py in FL.LOCK_PHASES:
        off = (px * half, py * half)
        add('offset_block_means', lv, {'h': hid, 'b': b, 'off': list(off), 'shape': list(mb)},
            {'tgt': FL.offset_block_means(h0, b, off, mb)[0].astype(np.float32)}, f'offset_block_means b {b} off {off}')

# the numbers of the driver (no cells): diffusivity, spacing, lock blocks, creep sub-steps
numbers = {
    'diffusivity': [[p, c, d, m, list(FL.diffusivity(p, c, d, m))] for p, c, d, m in (
        ({'K': 1.5e-5, 'valley_spacing_m': 320.0}, 23.4375, 0, 23.4375),
        ({'K': 1.5e-5, 'valley_spacing_m': 320.0, 'gullies': True}, 0.5, -3, 23.4375),
        ({'K': 1e-3, 'valley_spacing_m': 30.0, 'context_spacing_factor': 1.6}, 20.0, 6, 0.3125),
        ({'K': 4e-5, 'D': 0.01}, 7.8125, 0, 7.8125))],
    'lock_block': [[t, c, n, f, FL.lock_block(t, c, n, f)] for t, c, n, f in (
        (750.0, 23.4375, 512, 8), (320.0, 0.3125, 512, 2), (500.0, 31.25, 512, 8), (37.0, 1.0, 1000, 8), (90.0, 3.0, 384, 8))],
    'creep_substeps': [[dt, c, D, cap, ms, list(FL.creep_substeps(dt, c, D, cap, ms))] for dt, c, D, cap, ms in (
        (1602.56, 125.0, 0.0231, 5.0, 32), (4.0, 0.3125, 0.00133, 5.0, 32), (130.0, 1.0, 5.0, 5.0, 32), (300.0, 23.4, 0.0, 5.0, 32))],
    'soil_convexity': [[r, s, HS.soil_convexity(r, s)] for r, s in ((35.0, 560.0), (0.9, 30.0))],
    'soft_cap': [[r, c, float(HS.soft_cap(r, c))] for r, c in ((1.0, 4.0), (3.0, 4.0), (10.0, 4.0), (-2.0, 4.0))],
}
man = {'source': 'the Blender edition (blender/eidoblend/terrain), by tests/fluvial/fluvial_expected.py',
       'key': B.source_key(), 'versions': B.versions(), 'cases': cases, 'numbers': numbers}
with open(os.path.join(OUT, 'manifest.json'), 'w') as fh:
    json.dump(man, fh, indent=1)
print(f'[fixtures] {len(cases)} cases, {counter[0]} arrays in {OUT}')
