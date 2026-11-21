"""Function fixtures of the volcanoes and craters package (PORT_PLAN.md 5.1 "function fixtures", 8.2 row P9: "profiles
against numpy (Fuji's slopes at 0, 10, 15 km; Pike's and Wood's ratios)", "quantile per numpy 2.3.4 at
volcanic.py:2865 (C6)"): the Blender edition's own numpy functions on inputs the floor runs do not reach alone:

  cone_slopes    exp_cone and exp_cone_slope_deg (the design's Fuji numbers, H 3700, 33 deg, R 18 km, and the FUJI
                 preset) at the rim, 5, 10, 15 km and the foot: the profile in doubles
  strato_rays    stratovolcano(x, y, **the stratovolcano recipe's cone without its rift) along rays from the vent,
                 east and north, 25 km at 5 m (heights)
  cone_rays      cinder_cone along rays from its vent: Wood's fresh cone (width 1000 m: H/W 0.18, crater/W 0.40) and
                 the SP_CRATER preset (heights), 0.6 W at 0.25 m
  crater_dims    crater_dimensions (Pike: simple 0.2 D and 0.036 D, the complex fits, the transition) for diameters
                 from 100 m to 100 km, on Earth and the Moon
  crater_rays    impact_crater (the METEOR_CRATER preset as the impact_crater recipe sets it, without its cliffs, and
                 with them) along rays east and north to 2.6 R at 0.5 m: its delta (heights)
  quantile       the playa's top of op_volcano_lakes (volcanic.py:2865): float(np.quantile(h[cells], q)) with h the
                 level's float32 heights as float64 and cells a depression's cells, for q from frac + 0.06 clipped to
                 0.95, on fields with ties and without
  hero ops       op_lava_rubble, op_cone_rills, impact.op_crater_blocks on levels of their own (no draft floor run
                 reaches them): the fields after each op
  presets        fuji_surface (40 km) and crater_lake_surface (15 km) on grids of 256 x 256

    <Blender's python> -I eidoverse/terrain/tests/volcanoes_craters/volcanic_expected.py [out folder]

Writes <out>/manifest.json (cases: function, arguments, the ray or field, inputs, outputs, the versions) and the
arrays as little-endian .bin files (float32, float64 or uint8). Default out: eidoverse/terrain/tests/out/
volcanoes_craters/fixtures/. numpy only; nothing is written into the Blender edition.
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

from eidoblend.terrain.solvers import impact as I  # noqa: E402
from eidoblend.terrain.solvers import volcanic as V  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.normpath(os.path.join(HERE, '..', 'out', 'volcanoes_craters',
                                                                          'fixtures'))
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
    dt = {np.dtype(np.float32): 'f32', np.dtype(np.float64): 'f64', np.dtype(np.uint8): 'u8'}[a.dtype]
    counter[0] += 1
    name = f'a{counter[0]:05d}.bin'
    a.astype(a.dtype.newbyteorder('<')).tofile(os.path.join(OUT, name))
    return {'file': name, 'shape': list(a.shape), 'dtype': dt}


def add(function, label, args, outputs=None, inputs=None, values=None, ray=None):
    cases.append({'label': label, 'function': function, 'args': args, 'ray': ray,
                  'inputs': {k: arr(v) for k, v in (inputs or {}).items()},
                  'outputs': {k: arr(v) for k, v in (outputs or {}).items()}, 'values': values or {}})


def ray(centre, direction, step, count):
    """Cell centres of a one-row (east) or one-column (north) grid from the centre: (x, y, the grid's origin)."""
    s = np.arange(count, dtype=np.float64)
    c = (float(centre[0]), float(centre[1]))
    if direction == 'east':
        ox, oy = c[0] - 0.5 * step, c[1] - 0.5 * step
        return ox + (s + 0.5) * step, np.full(count, oy + 0.5 * step), (ox, oy)
    ox, oy = c[0] - 0.5 * step, c[1] - 0.5 * step
    return np.full(count, ox + 0.5 * step), oy + (s + 0.5) * step, (ox, oy)


# ------------------------------------------------------------------------------------------- the cone's slopes
F = V.FUJI
for label, (H, R, up, rc) in {'the design (H 3700 m, 33 deg, R 18 km)': (3700.0, 18000.0, 33.0, 0.03 * 18000.0),
                              'the FUJI preset': (float(F['height_m']), float(F['radius_m']),
                                                  float(F['upper_slope_deg']), float(F['crater_radius_m']))}.items():
    lam = V.cone_decay_m(H, up)
    q = [rc, 5000.0, 10000.0, 15000.0, 0.999 * R]
    add('exp_cone', f'exp_cone, {label}', {'H': H, 'R': R, 'upper_slope_deg': up, 'rc': rc, 'r': q},
        values={'lambda': lam, 'z': [float(V.exp_cone(np.asarray([v]), H, R, lam, rc)[0]) for v in q],
                'slope_deg': [float(V.exp_cone_slope_deg(v, H, R, lam, rc)) for v in q]})

# ------------------------------------------------------------------------------------- the stratovolcano's rays
C0 = F['centre']
CONE = dict(centre=[0.0, 0.0], height_m=F['height_m'], radius_m=float(F['radius_m']), upper_slope_deg=F['upper_slope_deg'],
            crater_radius_m=F['crater_radius_m'], crater_depth_m=F['crater_depth_m'],
            crater_floor_frac=F['crater_floor_frac'], summit_platform_m=F['summit_platform_m'],
            elongation=F['elongation'], rift_azimuth_deg=F['rift_azimuth_deg'], radius_noise=F['radius_noise'],
            height_noise=F['height_noise'], seed=3,
            flank_craters=[dict(fc, at=[fc['at'][0] - C0[0], fc['at'][1] - C0[1]]) for fc in F['flank_craters']])
for d in ('east', 'north'):
    x, y, o = ray((0.0, 0.0), d, 5.0, 5000)
    z = V.stratovolcano(x, y, **CONE)['height']
    add('stratovolcano', f'stratovolcano ray {d}', CONE, outputs={'z': np.asarray(z, np.float64)},
        ray={'direction': d, 'origin': list(o), 'step': 5.0, 'count': 5000})

# ---------------------------------------------------------------------------------------- the cinder cones' rays
S = V.SP_CRATER
for label, cone in {"Wood's fresh cone (W 1000 m)": dict(at=[0.0, 0.0], width_m=1000.0),
                    'the SP_CRATER preset': dict(S)}.items():
    W = float(cone['width_m'])
    for d in ('east', 'north'):
        n = int(round(0.6 * W / 0.25))
        x, y, o = ray(cone['at'], d, 0.25, n)
        z = np.asarray(V.cinder_cone(x, y, **cone), np.float64)
        r = np.hypot(x - cone['at'][0], y - cone['at'][1])
        i = int(np.argmax(z))
        add('cinder_cone', f'cinder_cone {label} ray {d}', cone, outputs={'z': z},
            ray={'direction': d, 'origin': list(o), 'step': 0.25, 'count': n},
            values={'H_over_W': float((z.max() - z[-1]) / W), 'crater_over_W': float(2.0 * r[i] / W)})

# ------------------------------------------------------------------------------------------- Pike's numbers
for g, gname in ((I.G_EARTH, 'Earth'), (I.G_MOON, 'Moon')):
    for D in (100.0, 600.0, 1194.0, 1750.0, 2000.0, 3000.0, 10000.0, 20000.0, 100000.0):
        add('crater_dimensions', f'crater_dimensions D {D:.0f} m on {gname}', {'diameter_m': D, 'gravity': g},
            values=I.crater_dimensions(D, g))

# --------------------------------------------------------------------------------------------- the crater's rays
M = I.METEOR_CRATER
D0 = float(M['diameter_m'])
CLIFFS = dict(strong_deg=75.0, strong_frac=0.45, layer_m=[10.0, 30.0], sectors=9, talus_frac=0.8, talus_deg=39.0,
              face_deg=50.0, apron_vary=0.07, mounds_m=0.5)
CRATER = dict(centre=[0.0, 0.0], diameter_m=D0, depth_ratio=M['depth_ratio'], rim_ratio=M['rim_ratio'],
              fill_ratio=M['fill_ratio'], sides=M['sides'], polygon=0.15, polygon_azimuth_deg=M['polygon_azimuth_deg'],
              radius_noise=0.045, edge_noise=0.015, rim_noise=M['rim_noise'], crest_round=0.5,
              ejecta_reach=M['ejecta_reach'], rays=0.0, seed=1)
for label, p in {'METEOR_CRATER, a plain wall': dict(CRATER), 'METEOR_CRATER, the cliffs': dict(CRATER, cliffs=CLIFFS)}.items():
    for d in ('east', 'north'):
        n = int(round(1.3 * D0 / 0.5))
        x, y, o = ray((0.0, 0.0), d, 0.5, n)
        out = I.impact_crater(x, y, **p)
        add('impact_crater', f'impact_crater {label} ray {d}', p, outputs={'delta': np.asarray(out['delta'], np.float64)},
            ray={'direction': d, 'origin': list(o), 'step': 0.5, 'count': n})

# ------------------------------------------------------------------------------------- quantile (volcanic.py:2865)
rng = np.random.default_rng(2865)
for k, (n, ties) in enumerate(((96, False), (128, True), (200, False), (64, True))):
    h = (1800.0 + 40.0 * rng.standard_normal((n, n))).astype(np.float32)
    if ties:
        h = np.round(h * 4.0).astype(np.float32) / np.float32(4.0)          # quarter-metre steps: many ties
    yy, xx = np.mgrid[0:n, 0:n]
    cells = np.hypot(xx - 0.45 * n, yy - 0.55 * n) < (0.2 + 0.05 * k) * n
    for frac in (0.0, 0.04, 0.3, 0.5, 0.89, 0.95):
        q = min(max(frac + 0.06, 0.0), 0.95)
        hv = np.asarray(h, np.float64)
        top = float(np.quantile(hv[cells], q))
        add('quantile', f'quantile of {int(cells.sum())} cells of {n}^2{" with ties" if ties else ""}, q {q:.2f}',
            {'q': q}, inputs={'h': h, 'cells': cells}, values={'top': top})

# ------------------------------------------------------- the hero levels' ops (no draft floor run reaches them)
# op_lava_rubble, op_cone_rills and impact.op_crater_blocks run as ops on a level of their own ('cell<=4', 'cell<=5'
# and 'cell<=1.5' in the recipes: the draft floor runs stop at the main level), from synthetic fields: their fields
# after the op
from eidoblend.terrain.core.levels import Level  # noqa: E402


def level(x0, y0, cell, n):
    return Level(3, 'hero', float(x0), float(y0), n * float(cell), float(cell), n, 2, 1, [], 16, -1)


yy, xx = np.mgrid[0:256, 0:256]
lv = level(-64.0, -64.0, 0.5, 256)
lava = np.clip(1.2 - np.hypot(xx - 120.0, yy - 140.0) / 90.0, 0.0, 1.0).astype(np.float32)
f = {'h': np.full((256, 256), 1850.0, np.float32), 'bed': np.full((256, 256), 1849.0, np.float32), 'lava': lava}
inp = {k: v.copy() for k, v in f.items()}
V.op_lava_rubble(f, lv, {'scales_m': [8.0, 3.0, 1.2], 'amps_m': [1.2, 0.6, 0.3]}, 9)
add('op_lava_rubble', 'op_lava_rubble on a 0.5 m level over a flow', {'params': {'scales_m': [8.0, 3.0, 1.2],
    'amps_m': [1.2, 0.6, 0.3]}, 'seed': 9, 'level': lv.to_dict()}, inputs=inp,
    outputs={k: np.asarray(v, np.float32) for k, v in f.items()})

HERO = dict(at=[0.0, 0.0], width_m=1420.0, hw_ratio=0.188, crater_ratio=0.26, flank_deg=28.0, crater_wall_deg=30.0,
            crater_depth_frac=0.41, crest_round_m=6.0, rim_tilt=0.02, tilt_azimuth_deg=200.0, outline_noise=0.02,
            seed=9, age_yr=71000.0, kappa_t_m2=0.0)
lv = level(-800.0, -800.0, 4.0, 400)
x, y = lv.xy()
cone = np.asarray(V.cinder_cones(x, y, [dict(HERO)]), np.float64)
f = {'h': (2000.0 + cone).astype(np.float32), 'bed': np.full((400, 400), 1990.0, np.float32)}
inp = {k: v.copy() for k, v in f.items()}
rp = {'cones': [dict(HERO)], 'field': None, 'kappa_m2_per_yr': 0.002, 'depth_m': 1.5, 'spacing_m': 30.0}
V.op_cone_rills(f, lv, dict(rp), 9)
add('op_cone_rills', 'op_cone_rills on a 4 m level over SP Crater', {'params': rp, 'seed': 9, 'level': lv.to_dict()},
    inputs=inp, outputs={k: np.asarray(v, np.float32) for k, v in f.items()})

BLOCKS = dict(sets=[dict(spacing_m=24.0, size_m=[2.5, 9.0], density=0.45, rho=[0.6, 0.8, 0.95, 1.02],
                         height_frac=[0.35, 0.6]),
                    dict(spacing_m=8.0, size_m=[0.7, 2.5], density=0.3, rho=[0.5, 0.72, 0.97, 1.03],
                         height_frac=[0.3, 0.55]),
                    dict(spacing_m=7.0, size_m=[2.5, 7.0], density=0.8, rho=[0.0, 0.02, 0.55, 0.7],
                         height_frac=[0.05, 0.1], profile='mound')],
              crater={k: CRATER[k] for k in ('centre', 'diameter_m', 'sides', 'polygon', 'polygon_azimuth_deg',
                                             'radius_noise')})
lv = level(180.0, -220.0, 1.0, 512)
f = {'h': np.full((512, 512), 1700.0, np.float32), 'bed': np.full((512, 512), 1695.0, np.float32),
     'deposit': np.zeros((512, 512), np.float32)}
inp = {k: v.copy() for k, v in f.items()}
I.op_crater_blocks(f, lv, dict(BLOCKS), 11)
add('op_crater_blocks', 'op_crater_blocks on a 1 m level over the crater wall', {'params': BLOCKS, 'seed': 11,
    'level': lv.to_dict()}, inputs=inp, outputs={k: np.asarray(v, np.float32) for k, v in f.items()})

# ------------------------------------------------------------- the preset surfaces (fuji_surface, crater_lake_surface)
lv = level(300.0 - 20000.0, 260.0 - 20000.0, 156.25, 256)
x, y = lv.xy()
add('fuji_surface', 'fuji_surface, 40 km at 156 m', {'level': lv.to_dict()},
    outputs={'z': np.asarray(V.fuji_surface(x, y), np.float64)})
lv = level(-7500.0, -7500.0, 58.59375, 256)
x, y = lv.xy()
add('crater_lake_surface', 'crater_lake_surface, 15 km at 59 m', {'level': lv.to_dict()},
    outputs={'z': np.asarray(V.crater_lake_surface(x, y), np.float64)})

json.dump({'source': 'eidoverse/terrain/tests/volcanoes_craters/volcanic_expected.py', 'versions': B.versions(),
           'blender_commit': B.source_key().get('commit') if isinstance(B.source_key(), dict) else None,
           'cases': cases}, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=1)
print(f'{len(cases)} cases, {counter[0]} arrays -> {OUT}')
