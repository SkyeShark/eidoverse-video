"""Function fixtures of the layered-rock package (PORT_PLAN.md 5.1 "function fixtures": a GPU replacement of numpy code
against that numpy function): the Blender edition's own numpy functions of solvers/strata.py and solvers/rivers.py that
the port runs as kernels of its own (kernels/strata/), on levels and options the draft floor runs never reach: a hero
cell (0.5 m) under the river's channel, the falling bed with its starting surface, the hero levels' smooth trench, a
child level's border-band hold, op_incise's replaced final bed, faults and a fold, a tilted plateau with escarpments and
faded roughness, joints, the rock mass and its cores with wobble, the dry basins with the river's channel kept and a
held border, the caprock fraction. Functions that take a device are called with none, so their noise is numpy's own
world-noise field (core/world_noise.field, the oracle the port's GPU noise is checked against).

    <Blender's python> -I eidoverse/terrain/tests/layered_rock/layered_expected.py [out folder]

Writes <out>/manifest.json (cases: function, arguments, the level, inputs, outputs) and the arrays as little-endian
.bin files (float32, float64, int32 or uint8; row 0 south). Default out: eidoverse/terrain/tests/out/layered_rock/
fixtures/. numpy only.
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
from eidoblend.terrain.solvers import rivers as RV  # noqa: E402
from eidoblend.terrain.solvers import strata as S  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.normpath(os.path.join(HERE, '..', 'out', 'layered_rock', 'fixtures'))
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.endswith('.bin') or f == 'manifest.json':
        os.remove(os.path.join(OUT, f))
cases = []
counter = [0]


def arr(a):
    a = np.ascontiguousarray(a)
    if a.dtype == np.bool_:
        a = a.astype(np.uint8)
    dt = {np.dtype(np.float32): 'f32', np.dtype(np.float64): 'f64', np.dtype(np.int32): 'i32',
          np.dtype(np.uint8): 'u8', np.dtype(np.int64): 'i64'}[a.dtype]
    counter[0] += 1
    name = f'a{counter[0]:05d}.bin'
    a.astype(a.dtype.newbyteorder('<')).tofile(os.path.join(OUT, name))
    return {'file': name, 'shape': list(a.shape), 'dtype': dt}


def lvl(n, cell, x0=None, y0=None, depth=0, role='main', index=0):
    x0 = -0.5 * n * cell if x0 is None else x0
    y0 = -0.5 * n * cell if y0 is None else y0
    return Level(index, role, float(x0), float(y0), n * cell, float(cell), n, None, 2, [], 16, depth)


def add(function, level, args, inputs, outputs, label, values=None):
    cases.append({'label': label, 'function': function, 'level': level.to_dict(), 'args': args,
                  'inputs': {k: arr(v) for k, v in inputs.items()}, 'outputs': {k: arr(v) for k, v in outputs.items()},
                  'values': values or {}})


def rough(n, seed, scale=1.0, smooth=3):
    rng = np.random.default_rng(seed)
    a = rng.standard_normal((n, n))
    for _ in range(smooth):
        a = 0.25 * (np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1))
    return (scale * a).astype(np.float32)


# ---------------------------------------------------------------------------------------------- offset, zs ---
SPECS = {
    'dip, warp, fold': {'column': 'colorado_plateau', 'zs0_m': 360.0, 'dip_deg': 0.3, 'azimuth_deg': 60.0,
                        'warp': [[4000.0, 5.0], [900.0, 3.0], [250.0, 1.2], [80.0, 0.4]],
                        'fold': {'axis_deg': 235.0, 'through': [150.0, -80.0], 'rise_m': 120.0, 'half_width_m': 6000.0}},
    'faults, warp off, anticline': {'column': 'monument_valley', 'zs0_m': 140.0, 'dip_deg': 1.4, 'azimuth_deg': 160.0,
                                    'warp': [[3500.0, 0.0], [800.0, 2.5]],
                                    'faults': [{'at': [300.0, -200.0], 'strike_deg': 30.0, 'throw_m': 45.0, 'width_m': 60.0},
                                               {'at': [-900.0, 400.0], 'strike_deg': 115.0, 'throw_m': 20.0,
                                                'width_m': 15.0, 'down': 'right'}],
                                    'fold': {'axis_deg': 80.0, 'rise_m': -60.0, 'half_width_m': 2500.0}},
}
for (name, spec), (n, cell, x0, y0) in zip(SPECS.items(), ((96, 62.5, -3000.0, -2500.0), (128, 15.625, -1200.0, -700.0))):
    lv = lvl(n, cell, x0, y0)
    h = (rough(n, 3, 40.0) + 300.0).astype(np.float32)
    zoff = S.offset(spec, lv, 5, None)
    add('offset', lv, {'spec': spec, 'seed': 5}, {}, {'zoff': zoff.astype(np.float64)}, f'offset: {name}')
    add('zs_field', lv, {'spec': spec, 'seed': 5}, {'h': h}, {'zs': S.zs_field(h, spec, lv, 5, None)}, f'zs_field: {name}')

# ---------------------------------------------------------------------------------------------- the plateau ---
sp = S.strata_spec(SPECS['dip, warp, fold'])
for name, params, (n, cell) in (
        ('structural surface', {'surface_zs_m': 1765.0, 'roughness': [[3000.0, 6.0], [600.0, 2.5], [120.0, 0.8]]}, (96, 62.5)),
        ('older surface (no warp)', {'surface_zs_m': 410.0, 'follow_warp': False,
                                     'roughness': [[2500.0, 6.0], [600.0, 5.0], [200.0, 3.0], [60.0, 1.6], [25.0, 0.6]]},
         (128, 7.8125)),
        ('tilted plane, two edges, faded roughness', {'height_m': 25.0, 'tilt_deg': 2.0, 'tilt_azimuth_deg': 200.0,
                                                      'roughness': [[700.0, 4.0], [180.0, 3.0], [50.0, 1.2]],
                                                      'edges': [{'through': [0.0, -400.0], 'strike_deg': 90.0, 'drop_m': 125.0,
                                                                 'width_m': 480.0, 'wiggle_m': 240.0,
                                                                 'wiggle_wavelength_m': 800.0},
                                                                {'through': [0.0, 300.0], 'strike_deg': 270.0, 'drop_m': 65.0,
                                                                 'width_m': 720.0, 'wiggle_m': 160.0,
                                                                 'wiggle_wavelength_m': 700.0}],
                                                      'roughness_low': 0.35, 'roughness_fade': 0.3, 'seed': 3}, (128, 15.625)),
        ('one edge, no roughness', {'height_m': 100.0, 'roughness': [], 'edge': {'through': [200.0, 0.0], 'strike_deg': 20.0,
                                                                                 'drop_m': 80.0, 'width_m': 150.0}},
         (64, 31.25))):
    lv = lvl(n, cell)
    add('plateau_surface', lv, {'params': params, 'seed': 4, 'strata': sp}, {},
        {'h': S.plateau_surface(lv, params, 4, None, sp).astype(np.float64)}, f'plateau_surface: {name}')

# ------------------------------------------------------------------------------- joints, rock mass, cores ---
JOINTS = [{'strike_deg': 20.0, 'spacing_m': 650.0, 'width_m': 35.0},
          {'strike_deg': 80.0, 'spacing_m': 900.0, 'width_m': 35.0, 'strength': 0.7}]
CORES = {'spacing_m': 1800.0, 'radius_m': [300.0, 650.0], 'elongation': [1.0, 2.2], 'angles_deg': [20.0, 80.0],
         'strength': 3.0, 'region_m': 40000.0, 'exponent': 2.5, 'wobble': 0.2}
for n, cell, x0, y0 in ((128, 62.5, -4000.0, -4000.0), (128, 15.625, -600.0, -1500.0)):
    lv = lvl(n, cell, x0, y0)
    add('joint_field', lv, {'sets': JOINTS, 'seed': 6}, {}, {'j': S.joint_field(lv, JOINTS, 6, None)}, f'joint_field at {cell} m')
    rm = S.rock_mass(lv, [1500.0, 600.0, 240.0, 90.0, 35.0], 6, None)
    add('rock_mass', lv, {'scales': [1500.0, 600.0, 240.0, 90.0, 35.0], 'seed': 6}, {}, {'n': rm}, f'rock_mass at {cell} m')
    for spec, tag in ((CORES, 'wobble 0.2, power 2.5'), (dict(CORES, wobble=0.0, exponent=4.0, angles_deg=None), 'no wobble, power 4')):
        c = S.rock_cores(lv, spec, 6)
        add('rock_cores', lv, {'spec': spec, 'seed': 6}, {}, {'c': c}, f'rock_cores at {cell} m, {tag}')

# ----------------------------------------------------------------------------------------- the dry basins ---
for name, n, cell, hold, chan in (('pits, the channel keeps two', 96, 31.25, 0, True), ('held border', 96, 31.25, 2, False)):
    lv = lvl(n, cell)
    rng = np.random.default_rng(11)
    h = (rough(n, 12, 6.0, 4) + 50.0 + 0.002 * np.arange(n)[None, :] * cell).astype(np.float32)
    for k in range(14):                                       # pits of every size, some on the border band
        j, i = rng.integers(0, n, 2)
        r = rng.uniform(1.0, 5.0)
        yy, xx = np.mgrid[0:n, 0:n]
        h = np.where((yy - j) ** 2 + (xx - i) ** 2 < r * r, h - rng.uniform(0.5, 4.0), h).astype(np.float32)
    keep = np.zeros((n, n), bool)
    if chan:
        keep[:, n // 2 - 1:n // 2 + 1] = True
    dep = rough(n, 13, 0.5).clip(0.0, None).astype(np.float32)
    fields = {'h': h.copy(), 'deposit': dep.copy()}
    k = keep
    if chan:
        for ax in (0, 1):
            k = k | np.roll(k, 1, ax) | np.roll(k, -1, ax)
    cnt = S.fill_dry_basins(fields, k if chan else None, hold=hold)
    add('fill_dry_basins', lv, {'hold': hold, 'has_keep': chan}, {'h': h, 'deposit': dep, 'chan': keep.astype(np.float32)},
        {'h': fields['h'], 'deposit': fields['deposit']}, f'fill_dry_basins: {name}', {'filled': int(cnt)})

# ------------------------------------------------------------------------------------------- caprock ---
lv = lvl(128, 31.25)
main = lvl(64, 31.25)
h = (rough(128, 21, 60.0, 5) + 400.0).astype(np.float32)
zoff = S.offset(SPECS['faults, warp off, anticline'], lv, 5, None)
# caps inside the window's own stratigraphic heights (the main window is the level's middle 64 x 64 cells here), so
# the share is neither 0 nor 1, and one cap on a cell's own float32 zs (the tie of >=)
zs_win = (h.astype(np.float64) - zoff.astype(np.float64))[32:96, 32:96]
caps = [round(float(np.quantile(zs_win, q)), 1) for q in (0.2, 0.5, 0.8)] + [float(np.float32(zs_win[20, 40]))]
for cap in caps:
    add('caprock_fraction', lv, {'main': main.to_dict(), 'cap_zs': cap, 'spec': SPECS['faults, warp off, anticline'],
                                 'seed': 5},
        {'h': h}, {}, f'caprock_fraction at cap {cap:.6g} m', {'frac': S.caprock_fraction(h, zoff, lv, main, cap)})

# ----------------------------------------------------------------------------------- the river's channel and pins ---
RIVERS = {
    'canyon walk with pools': dict(kind='walk', through=[0.0, 0.0], flow_azimuth_deg=235.0, wiggle_deg=16.0,
                                   wiggle_wavelength_m=5000.0, width_m=80.0, bed_m=0.0, gradient=0.0015,
                                   schedule=[[0.0, 0.0], [0.6, 1.0], [1.0, 1.0]], pool_spacing_m=600.0, pool_depth_m=6.0,
                                   pool_riffle=0.06),
    'meanders with pools': dict(kind='kinoshita', through=[0.0, 0.0], centre='axis', flow_azimuth_deg=285.0,
                                wavelength_m=6000.0, sinuosity=4.3, skew=0.03, flat=0.02, vary=0.35, vary_scale=1.3,
                                vary_skew=0.05, min_neck_m=250.0, width_m=50.0, bed_m=0.0, gradient=0.0004,
                                schedule=[[0.0, 0.0], [0.7, 1.0], [1.0, 1.0]], pool_spacing_m=350.0, pool_depth_m=4.0,
                                pool_riffle=0.07),
}
for name, params in RIVERS.items():
    rv = RV.make_river(params, 1, 16000.0)
    # the starting surface the bed falls from, sampled on a coarse level
    top_lv = lvl(128, 125.0)
    top_h = (rough(128, 31, 30.0, 4) + 900.0).astype(np.float32)
    rv.sample_top(top_lv, top_h)
    for tag, lv, f, hold in (('main level, f 0.35', lvl(256, 15.625), 0.35, None),
                             ('hero level 0.5 m, f 1 (the smooth trench)', lvl(256, 0.5, 120.0, -60.0, role='hero', depth=-3), 1.0, None),
                             ('child level with the border band, f 1', lvl(256, 7.8125, -1000.0, -1000.0, depth=-1), 1.0, 'band')):
        n = lv.n
        base_w = np.zeros((n, n), np.float32)
        base_w[0, :] = base_w[-1, :] = base_w[:, 0] = base_w[:, -1] = 1.0
        base_h = (rough(n, 41, 4.0) + 800.0).astype(np.float32)
        hold_w = None
        if hold == 'band':
            d = np.minimum.reduce([np.arange(n)[None, :].repeat(n, 0), np.arange(n)[:, None].repeat(n, 1),
                                   n - 1 - np.arange(n)[None, :].repeat(n, 0), n - 1 - np.arange(n)[:, None].repeat(n, 1)])
            t = np.clip(d / 16.0, 0.0, 1.0)
            hold_w = (1.0 - t * t * (3.0 - 2.0 * t)).astype(np.float32)
            base_w = np.maximum(base_w, hold_w)
        z = np.zeros((n, n), np.float32)
        base = dict(pin_w=base_w, pin_h=base_h, A_in=z, qs_in=z)
        mask, s, dist = RV.channel(lv, rv.points, rv.width_m)
        pins, m = rv.pins(lv, base, f, hold=hold_w)
        ins = {'pin_w': base_w, 'pin_h': base_h, 'top_h': top_h}
        if hold_w is not None:
            ins['hold'] = hold_w
        add('river_pins', lv, {'river': params, 'seed': 1, 'extent': 16000.0, 'f': f, 'hold': hold_w is not None,
                               'top_level': top_lv.to_dict()},
            ins, {'mask': mask, 's': np.where(mask, s, 0.0), 'd': np.where(np.isfinite(dist), dist, -1.0),
                  'pin_w': pins['pin_w'], 'pin_h': pins['pin_h']},
            f'river channel and pins, {name}: {tag}', {'cells': int(mask.sum())})

# op_incise's replaced final bed (fluvial.py: piecewise linear in arc length, breakpoints at course points)
params = dict(kind='walk', flow_azimuth_deg=235.0, through=[500.0, -400.0], wiggle_deg=30.0, wiggle_wavelength_m=1800.0,
              width_m=40.0)
rv = RV.make_river(params, 2, 32000.0)
lv = lvl(256, 15.625)
sIn = rv.s[::7]
zg = 120.0 - 0.003 * (sIn - sIn[0]) - 8.0 * np.sin(sIn / 900.0) ** 2
zg = np.minimum.accumulate(zg)
g0, g1 = 0.003, 0.002


def graded(s, smooth=False):
    s = np.asarray(s, np.float64)
    out = np.interp(s, sIn, zg)
    out = np.where(s < sIn[0], zg[0] + g0 * (sIn[0] - s), out)
    return np.where(s > sIn[-1], zg[-1] - g1 * (s - sIn[-1]), out)


rv.final = graded
top_lv = lvl(128, 62.5)
top_h = (rough(128, 51, 20.0, 4) + 300.0).astype(np.float32)
rv.sample_top(top_lv, top_h)
n = lv.n
base_w = np.zeros((n, n), np.float32)
base_w[0, :] = base_w[-1, :] = base_w[:, 0] = base_w[:, -1] = 1.0
base_h = (rough(n, 52, 3.0) + 200.0).astype(np.float32)
z = np.zeros((n, n), np.float32)
pins, m = rv.pins(lv, dict(pin_w=base_w, pin_h=base_h, A_in=z, qs_in=z), 0.5)
add('river_pins_replaced_final', lv, {'river': params, 'seed': 2, 'extent': 32000.0, 'f': 0.5, 'every': 7, 'g0': g0, 'g1': g1,
                                      'top_level': top_lv.to_dict()},
    {'pin_w': base_w, 'pin_h': base_h, 'top_h': top_h, 'sIn': sIn, 'zg': zg},
    {'mask': m, 'pin_w': pins['pin_w'], 'pin_h': pins['pin_h']}, "river pins with op_incise's replaced final bed, f 0.5")

with open(os.path.join(OUT, 'manifest.json'), 'w') as fh:
    json.dump({'source': 'blender/eidoblend/terrain/solvers/strata.py and rivers.py, by tests/layered_rock/layered_expected.py',
               'versions': B.versions(), 'cases': cases}, fh, indent=1)
print(f'[layered_expected] {len(cases)} cases into {OUT}')
