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

json.dump({'source': 'eidoverse/terrain/tests/volcanoes_craters/volcanic_expected.py', 'versions': B.versions(),
           'blender_commit': B.source_key().get('commit') if isinstance(B.source_key(), dict) else None,
           'cases': cases}, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=1)
print(f'{len(cases)} cases, {counter[0]} arrays -> {OUT}')
