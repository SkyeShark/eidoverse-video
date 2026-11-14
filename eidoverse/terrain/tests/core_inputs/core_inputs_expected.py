"""The Blender edition's core, run on recorded inputs, for the core-inputs package's tests (PORT_PLAN.md 8.2, P2) to
check core/levels.js, grid.js, fields.js, recipe.js, expr.js, world_noise.js, compose.js and io.js against.

    <Blender's python> -I eidoverse/terrain/tests/core_inputs/core_inputs_expected.py [out_dir] [--big <dir>]

Run it with Blender's own Python (a Blender folder's <version>/python/bin/python), never another (PORT_PLAN.md 5.1):
the Blender edition computes with the numpy and zlib that Python carries (numpy 2.3.4 and zlib 1.3.1 in Blender 5.2).
numpy only; no Blender, no GPU. The default out_dir is tests/out/core_inputs/fixtures_<numpy version>/; the manifest
records the Python, numpy and zlib versions and the Blender commit.

The Blender edition is found at blender/ beside eidoverse/ in this checkout (a blender-branch checkout holds both
editions), else at $EIDO_BLENDER_EDITION (the root of a checkout of the blender branch). Its functions are the
oracles, called as they are:
    levels      plan_levels on test_core.py's 20 focus cases as written and at each quality (api.generate's
                resolution and hero cell), and on focus points whose window snaps fall exactly half way between two
                even grid lines (Python's round() goes to the even line there); select_levels in every form; errors
    python      round(), format() and difflib.get_close_matches on the values the port formats
    recipes     every registered recipe: to_dict(), describe(), resolve() with its defaults and two other knob
                sets, and the same through Recipe.from_dict without a base (no knob apply code); test_core.py's
                test recipe, whose apply the JS test defines again
    expr        parse trees, canonical text, names, values on 96 x 80 fields (float64), the errors
    noise       world_noise.field (float64) on non-square windows, 40 km out, periodic tiles and with a warp
                displacement; _leaf_terms' tables, lattice_offset, snap_wavelength, snap_freq
    compose     every shape kind, uplift of every kind (numpy's noise: the twin path), start_surface, every stamp
                mode, smooth_min / max, flatten_weight / mask / exact, resolve_flat_heights
    grid        upsample2, crop_upsample2, box_down, resample_box, sample_bilinear, edge_distance, border_ramp,
                gradient, slope_deg, aspect_deg, from_north_up
    fields      Fields.inherit along a plan and a pre-pass, thickness
    io          export_heightmap (png16, r32, r16), export_mask, encode_png for every channel count and depth,
                read_png of reference DEMs, hillshade and to_u8, a PNG with another filter, np.savez files of every
                dtype the terrain stores, and the Blender Terrain.save files named by $EIDO_TERRAIN_SAVES (paths
                separated by the path separator; default: the Blender edition's surfacing_judge saves, when present)
--big <dir> also writes <dir>/big_save.npz, a save over 4 GB made by np.savez as Terrain.save calls it (Terrain.save's
            key names and dtypes: float32 fields, float16 masks), for the streaming check.

Writes manifest.json and one little-endian .bin per array (row 0 = south, C order; f32, f64, f16, u8, u16, u32 or
i32 as the manifest says), and the io files beside them.
"""
import difflib
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import types
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))


def blender_edition():
    cands = [os.path.normpath(os.path.join(HERE, '..', '..', '..', '..')), os.environ.get('EIDO_BLENDER_EDITION', '')]
    for root in cands:
        if root and os.path.isdir(os.path.join(root, 'blender', 'eidoblend', 'terrain', 'core')):
            return root
    sys.exit('core_inputs_expected: no Blender edition (blender/eidoblend/terrain) here or at $EIDO_BLENDER_EDITION')


ROOT = blender_edition()
BLENDER_DIR = os.path.join(ROOT, 'blender')
TERRAIN_DIR = os.path.join(BLENDER_DIR, 'eidoblend', 'terrain')
sys.path.insert(0, BLENDER_DIR)
import eidoblend  # noqa: E402  (imports nothing)

pkg = types.ModuleType('eidoblend.terrain')                  # the bare package, as plain_import.py makes it
pkg.__path__ = [TERRAIN_DIR]
pkg.__package__ = 'eidoblend.terrain'
sys.modules['eidoblend.terrain'] = pkg
eidoblend.terrain = pkg

import numpy as np  # noqa: E402

from eidoblend.terrain.core import compose as C  # noqa: E402
from eidoblend.terrain.core import expr as E  # noqa: E402
from eidoblend.terrain.core import fields as F  # noqa: E402
from eidoblend.terrain.core import grid as G  # noqa: E402
from eidoblend.terrain.core import io as IO  # noqa: E402
from eidoblend.terrain.core import levels as L  # noqa: E402
from eidoblend.terrain.core import recipe as RC  # noqa: E402
from eidoblend.terrain.core import world_noise as N  # noqa: E402

args = [a for a in sys.argv[1:]]
BIG = None
if '--big' in args:
    i = args.index('--big')
    BIG = args[i + 1]
    del args[i:i + 2]
OUT = args[0] if args else os.path.join(HERE, '..', 'out', 'core_inputs', 'fixtures_' + np.__version__)
OUT = os.path.abspath(OUT)
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT, exist_ok=True)
_n = [0]
DT = {np.dtype(np.float32): 'f32', np.dtype(np.float64): 'f64', np.dtype(np.float16): 'f16',
      np.dtype(np.uint8): 'u8', np.dtype(np.uint16): 'u16', np.dtype(np.uint32): 'u32', np.dtype(np.int32): 'i32'}


def save(a, dtype=None):
    a = np.ascontiguousarray(np.asarray(a, dtype) if dtype is not None else np.asarray(a))
    if a.dtype == np.int64:
        a = a.astype(np.int32)
    if a.dtype == np.bool_:
        a = a.astype(np.uint8)
    if a.dtype not in DT:
        raise TypeError(f'save: {a.dtype}')
    _n[0] += 1
    name = f'c{_n[0]:04d}.bin'
    a.astype(a.dtype.newbyteorder('<')).tofile(os.path.join(OUT, name))
    return {'file': name, 'shape': list(a.shape), 'dtype': DT[a.dtype]}


def raises(fn):
    try:
        fn()
    except Exception as e:                                      # noqa: BLE001
        return f'{type(e).__name__}: {e}'
    return None


def git(*a):
    try:
        return subprocess.run(['git', '-C', ROOT, *a], capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:                                           # noqa: BLE001
        return ''


M = {'numpy': np.__version__, 'python': sys.version.split()[0], 'zlib': zlib.ZLIB_RUNTIME_VERSION,
     'python_executable': os.path.basename(sys.executable), 'blender_commit': git('rev-parse', 'HEAD'),
     'blender_package_changes': git('status', '--short', '--', 'blender/eidoblend/terrain/core')}
rng = np.random.default_rng(20261114)


# ------------------------------------------------------------------------------------------------- levels ---

FOCUS_CASES = [                                                  # test_core.py's, verbatim
    ('design_example_8km_ctx4', 8000, 1024, (0, 0), 4, (1200, -300), 0.5),
    ('point_at_centre', 8000, 1024, (0, 0), 4, (0, 0), 0.5),
    ('point_near_east_edge', 8000, 1024, (0, 0), 4, (3900, 0), 0.5),
    ('point_near_sw_corner', 8000, 1024, (0, 0), 4, (-3950, -3950), 0.5),
    ('point_on_tile_edge', 8000, 1024, (0, 0), 2, (4000, 100), 0.5),
    ('offset_centre', 12000, 1024, (50000, -20000), 4, (52000, -21000), 0.5),
    ('hero_quarter_metre', 8000, 2048, (0, 0), 4, (100, 200), 0.25),
    ('draft_512_no_hero', 6000, 512, (0, 0), 3, (100, 100), None),
    ('no_focus', 40000, 1024, (0, 0), 3, None, 0.5),
    ('walk_300m', 8000, 1024, (0, 0), 4, [(0, 0), (150, 120), (300, 260)], 0.5),
    ('walk_900m', 8000, 1024, (0, 0), 4, [(-450, 0), (0, 80), (450, 40)], 0.5),
    ('walk_1500m_caps_cells', 8000, 1024, (0, 0), 4, [(-750, 0), (750, 0)], 0.5),
    ('walk_6km_too_wide', 8000, 1024, (0, 0), 4, [(-3000, 0), (3000, 0)], 0.5),
    ('camera_like_objects', 3000, 1024, (0, 0), 2, 'cams', 0.5),
    ('meadow_160m', 160, 512, (0, 0), 2, (10, -5), 0.25),
    ('badlands_3km', 3000, 1000, (0, 0), 2, (500, 500), 0.5),
    ('fuji_40km', 40000, 1000, (0, 0), 3, (2000, -6000), 0.5),
    ('odd_size_9876m', 9876.5, 1024, (13.3, -7.7), 4, (-2222.2, 3333.3), 0.5),
    ('context_1_none', 8000, 1024, (0, 0), 1, (10, 10), 0.5),
    ('negative_coords_far', 5000, 512, (-123456.0, 987654.0), 4, (-123000.0, 987000.0), 0.5),
]


class _Cam:
    def __init__(self, x, y, z):
        self.location = (x, y, z)


def _scaled_resolution(res, quality):                           # api.py's, verbatim
    if not res:
        return None
    f = {'draft': 0.5, 'film': 1.0, 'hero': 2.0}[quality]
    return int(max(64, round(res * f / 8.0) * 8))


def half_snaps(size, res, centre, ctx, focus, hero, band=L.BAND):
    """How many of the hero windows' snaps round an exact half (where round() and a half-up rounding part)."""
    if focus is None or not hero:
        return 0
    pts = L.focus_points(focus)
    plan = L.plan_levels(size, res, centre, ctx, focus, hero, warn=lambda m: None)
    fcx, fcy = 0.5 * (pts[:, 0].min() + pts[:, 0].max()), 0.5 * (pts[:, 1].min() + pts[:, 1].max())
    count = 0
    for lv in plan:
        if lv.role != 'hero':
            continue
        p = plan[lv.parent]
        step = 2.0 * p.cell
        for v, o in ((fcx - lv.side / 2.0, p.x0), (fcy - lv.side / 2.0, p.y0)):
            q = (v - o) / step
            count += int(q - math.floor(q) == 0.5)
            lo = o + band * p.cell
            hi = o + p.side - band * p.cell - lv.side
            c = min(max(o + step * round(q), lo), hi)
            q2 = (c - o) / step
            count += int(q2 - math.floor(q2) == 0.5)
    return count


def plan_case(label, size, res, centre, ctx, focus, hero, **kw):
    warns = []
    cams = isinstance(focus, str) and focus == 'cams'
    f = [_Cam(-100, 50, 1.7), _Cam(-60, 70, 1.7)] if cams else focus
    row = {'label': label, 'size': size, 'resolution': res, 'centre': list(centre), 'context': ctx,
           'focus': [[-100, 50, 1.7], [-60, 70, 1.7]] if cams else focus, 'cameras': cams, 'hero': hero}
    row.update(kw)
    try:
        plan = L.plan_levels(size, res, centre, ctx, f, hero, warn=warns.append, **kw)
    except Exception as e:                                      # noqa: BLE001
        row['error'] = f'{type(e).__name__}: {e}'
        return row
    row['plan'] = [lv.to_dict() for lv in plan]
    row['repr'] = [repr(lv) for lv in plan]
    row['warnings'] = warns
    row['in_parent'] = [lv.in_parent(plan) for lv in plan]
    row['half_snaps'] = half_snaps(size, res, centre, ctx, f, hero) if not cams else 0
    row['with_cells'] = [lv.with_cells(m).to_dict() for lv in plan[:1] for m in (plan[0].prepass or [64])]
    return row


levels = {'cases': [], 'quality_cases': [], 'half_cases': [], 'errors': [], 'select': []}
for c in FOCUS_CASES:
    levels['cases'].append(plan_case(*c))
for c in FOCUS_CASES:
    label, size, res, centre, ctx, focus, hero = c
    for q, Q in L.QUALITY.items():
        r = _scaled_resolution(res, q)
        h = None if Q['hero_cell'] is None else (min(float(hero), Q['hero_cell']) if hero else Q['hero_cell'])
        levels['quality_cases'].append(plan_case(f'{label}@{q}', size, r, centre, ctx, focus, h))
# focus points whose first hero window snaps half way between the parent's even lines (x, y; even and odd halves)
for k_x, k_y in ((128, 100), (129, 101), (128, 101), (77, 160)):
    fx = 15.625 * (k_x + 0.5) - 2000.0
    fy = 15.625 * (k_y + 0.5) - 2000.0
    levels['half_cases'].append(plan_case(f'half_{k_x}_{k_y}', 8000, 1024, (0, 0), 4, (fx, fy), 0.5))
# a walk whose box centre sits on a half line of the second hero window (cell 1.953125, step 7.8125)
levels['half_cases'].append(plan_case('half_second_level', 8000, 1024, (0, 0), 4, [(3.90625, 0.0), (11.71875, 3.90625)],
                                      0.5))
levels['half_cases'].append(plan_case('half_draft_resolution_1000', 3000, _scaled_resolution(1000, 'draft'), (0, 0), 2,
                                      (500, 500), None))
for size, res, centre, ctx, focus, hero in ((8000, 1024, (0, 0), 4, (4100, 0), 0.5), (8000, 1022, (0, 0), 4, None, None),
                                            (8000, 60, (0, 0), 4, None, None), (-5, 1024, (0, 0), 4, None, None),
                                            (8000, 1024, (0, 0), 4, [5.0], 0.5)):
    levels['errors'].append(plan_case('error', size, res, centre, ctx, focus, hero))
levels['errors'].append(plan_case('band_8_max_512', 8000, 1024, (0, 0), 4, [(-300, 0), (300, 0)], 0.5, band=8,
                                  max_cells=512))
ex = L.plan_levels(8000, 1024, (0, 0), 4, (1200, -300), 0.5, warn=lambda m: None)
for s in ('all', 'first', 'last', 'context', 'main', 'hero', 'cell>=30', 'cell<=2', 'cell<1', 'cell>1', 'resolves:2000',
          'resolves:300', 'resolves:100', 'resolves:1', ' cell <= 3.90625 ', 'cell>=1e1', ['main', 6, 'cell>=30'], [-1, 0],
          3, 'heroes', 'cells>=3', 'cell>=1.2.3', 7, -8, ['all', 'bogus']):
    warns = []
    row = {'spec': s}
    try:
        row['picked'] = L.select_levels(s, ex, warn=warns.append)
        row['warnings'] = warns
    except Exception as e:                                      # noqa: BLE001
        row['error'] = f'{type(e).__name__}: {e}'
    levels['select'].append(row)
levels['select_plan'] = [lv.to_dict() for lv in ex]
M['levels'] = levels

# Python's own behaviours the port reproduces (rounding, formatting, difflib)
vals = [0.5, 1.5, 2.5, -0.5, -1.5, -2.5, 62.5, 2.5000000000000004, 0.49999999999999994, 2.675, 1e16 + 2, -0.0, 3.0,
        1280 / 512, 1000 * 0.5 / 8.0, 4096.5, -7.5, 1e-300, 123456.5, 0.5000000000000001]
fmt_vals = [0.0, -0.0, 1.0, 15.625, 0.48828125, 3.90625, 1.953125, 31.25, 7.8125, 12345.678, 1e-5, 1.5e-5, 123456789.0,
            0.000123456, 2.5, 0.125, 1e16, 1e-300, 5e-324, 1.7976931348623157e308, -2222.2, 9876.5, 0.1, 2 / 3,
            100.0, 999999.5, 9999995.0, 0.00015, 1234.5, 2.675]
M['python'] = {
    'round': [[v, round(v)] for v in vals],
    'format': [[v, s, format(v, s)] for v in fmt_vals for s in ('g', '.3g', '.4g', '.0f', '.2f', '.6e', '.1g')],
    'repr': [[v, repr(v)] for v in fmt_vals + [1e15, 1e-4, 0.0001234, 1.0000000000000002, 123e20]],
    'close': [[w, p, n, c, difflib.get_close_matches(w, p, n, c)] for w, p, n, c in (
        ('relief', ['relief_m', 'valley_spacing_m', 'kind'], 3, 0.5),
        ('slpoe', ['slope', 'wear', 'deposit'], 3, 0.6),
        ('smoothsetp', ['min', 'max', 'smoothstep', 'clamp', 'abs'], 2, 0.6),
        ('alpine', ['alpine_valley', 'badlands', 'caldera', 'canyon', 'cinder_cones', 'dunes', 'fluvial_range'], 3, 0.5),
        ('fluvail', ['fluvial', 'uplift', 'creep', 'talus', 'threshold', 'breakup', 'hydraulic'], 3, 0.5),
        ('abc', ['abd', 'abe', 'abf', 'xbc'], 3, 0.6),
        ('heroCell', ['hero_cell', 'heroCell', 'herocell', 'cell'], 3, 0.5),
        ('a' * 210, ['a' * 205 + 'b', 'b' * 210], 2, 0.1))]}


# ------------------------------------------------------------------------------------------------- recipes ---

from eidoblend.terrain import recipes as RG  # noqa: E402


def knob_sets(r):
    """Two knob sets besides the defaults: every numeric knob a quarter (then three quarters) into its range, every
    choice its last (then first) value, every bool flipped."""
    out = []
    for frac, pick in ((0.25, -1), (0.75, 0)):
        p = {}
        for k, kn in r.knobs.items():
            if kn.unit == 'choice' and kn.range:
                p[k] = list(kn.range)[pick]
            elif kn.unit == 'bool':
                p[k] = not bool(kn.default)
            elif kn.unit in ('list', 'name'):
                continue
            elif kn.range is not None and kn.range[0] is not None and kn.range[1] is not None:
                p[k] = float(kn.range[0]) + frac * (float(kn.range[1]) - float(kn.range[0]))
        out.append(p)
    return out


def resolved(r, params):
    try:
        v, st = r.resolve(params)
        return {'params': params, 'values': RC._jsonable(v), 'stages': [s.to_dict() for s in st]}
    except Exception as e:                                      # noqa: BLE001
        return {'params': params, 'error': f'{type(e).__name__}: {e}'}


recipes = {'failed': RG.failed(), 'recipes': {}}
for name in RG.names():
    r = RG.get(name)
    d = r.to_dict()
    nb = RC.Recipe.from_dict(json.loads(json.dumps(d)))
    sets = [None] + knob_sets(r)
    recipes['recipes'][name] = {'to_dict': d, 'describe': r.describe(), 'repr': repr(r),
                                'describe_dict': RC.Recipe.from_dict(json.loads(json.dumps(d)), base=r).describe(),
                                'resolve': [resolved(r, p) for p in sets],
                                'resolve_nobase': [resolved(nb, p) for p in sets],
                                'stage_reprs': [repr(RC.Stage.from_dict(json.loads(json.dumps(s.to_dict()))))
                                                for s in r.stages], 'labels': [s.label for s in r.stages]}


def spacing_to_D(p):                                            # test_core.py's apply; the JS test defines it again
    f = p.stage('fluvial')
    f['D'] = f['K'] * (p['valley_spacing_m'] / 6.5) ** 2


tr = RC.Recipe('test_range', 'a test range', ['san_gabriel_mountains'],
               {'size': 12000.0, 'resolution': 1024, 'context': 4, 'hero_cell': 0.5, 'palette': 'alpine'},
               {'relief_m': RC.Knob(2000.0, 'm', (200.0, 6000.0), 'p99.5 relief'),
                'valley_spacing_m': RC.Knob(400.0, 'm', (60.0, 3000.0), 'valley spacing', apply=spacing_to_D),
                'kind': RC.Knob('star', 'choice', ['star', 'barchan'], 'dune kind')},
               [RC.Stage('uplift', {'shape': {'kind': 'ridge', 'length_m': 9000}}),
                RC.Stage('fluvial', {'K': 1.5e-5, 'relief_m': '$relief_m', 'list': ['$kind', 3]}, levels='all'),
                RC.Stage('breakup', {'scales_m': [50, 15, 5]}, levels='hero', where='smoothstep(30, 45, slope)')],
               doc='a recipe for the tests')
recipes['test_recipe'] = {
    'to_dict': tr.to_dict(), 'describe': tr.describe(),
    'resolve': [resolved(tr, p) for p in (None, {'relief_m': 2800}, {'valley_spacing_m': 800, 'kind': 'barchan'})],
    'errors': {'unknown_knob': raises(lambda: tr.resolve({'relief': 100})),
               'out_of_range': raises(lambda: tr.resolve({'relief_m': 9e9})),
               'bad_choice': raises(lambda: tr.resolve({'kind': 'linear'})),
               'not_a_number': raises(lambda: tr.resolve({'relief_m': 'high'})),
               'bad_levels': raises(lambda: RC.Stage('x', levels='heroes')),
               'bad_where': raises(lambda: RC.Stage('x', where='slope >')),
               'bad_stage_key': raises(lambda: RC.Stage.from_dict({'op': 'x', 'level': 'all'})),
               'bad_unit': raises(lambda: RC.Knob(1.0, 'metres')),
               'no_stage': raises(lambda: RC.Params({}, tr.stages).stage('fluvail'))}}
recipes['from_stages'] = RC.Recipe.from_stages([{'op': 'fluvial', 'params': {'K': 1e-5}}, {'op': 'talus'}]).to_dict()
M['recipes'] = recipes


# ---------------------------------------------------------------------------------------------------- expr ---

H, W = 80, 96
env_np = {
    'slope': (rng.random((H, W)) * 70.0).astype(np.float32),
    'wear': (rng.random((H, W)) * 3.0).astype(np.float32),
    'deposit': np.round(rng.random((H, W)) * 2.0, 1).astype(np.float32),     # ties
    'h': (rng.standard_normal((H, W)) * 400.0 + 1200.0).astype(np.float32),
    'A': (10.0 ** (rng.random((H, W)) * 6.0)).astype(np.float32),
}
env_np['slope'][0, :8] = [0.0, 30.0, 32.0, 38.5, 45.0, 60.0, 90.0, 31.999]
EXPRS = ['smoothstep(32, 45, slope) + 0.5*wear - 2*deposit', '1 + 2 * 3 - -4 / 2', '(1 + 2) * 3', '2 - (3 - 4)',
         'max(wear, deposit, 0.7)', 'min(wear, deposit)', 'clamp(slope, 20, 50)', 'abs(0 - wear)',
         'smoothstep(45, 32, slope)', 'a - (b - c) / (d * e)', 'wear / (deposit + 0.5)', '-(-slope)', '+wear',
         'smoothstep(0, 1, deposit) * (1 - smoothstep(30, 50, slope))', 'clamp(h / 3000, 0, 1)', 'abs(h - 1200) / 400',
         '0.000123 * A + 1e-05', '2.5e3 - h', 'min(max(slope, 10), 40) - 25', '.5 * wear', '3. * deposit',
         'clamp(wear, 2, 1)', 'smoothstep(30, 45, slope)', 'A / 1e6 * (wear - deposit)',
         'max(smoothstep(32, 45, slope), 0.25 * min(wear, 1)) - abs(deposit - 1)', '1 - 2 - 3', '24 / 4 / 2',
         '2 * (3 + 4) * 5', 'slope', '7', 'min(1, 2, 3)', 'smoothstep(1, 1, 2)']
ERRS = ['smoothsetp(1, 2, x)', 'slope ** 2', 'smoothstep(1, x)', 'min(a, b', 'slope >', '', '   ', '1 +', 'abs()',
        'max(1)', '(1', '1)', 'slope wear', '2 % 3', 'f(1)']


def tree_json(n):
    if n[0] == 'num':
        return ['num', n[1]]
    if n[0] == 'name':
        return ['name', n[1]]
    if n[0] == 'neg':
        return ['neg', tree_json(n[1])]
    if n[0] == 'bin':
        return ['bin', n[1], tree_json(n[2]), tree_json(n[3])]
    return ['call', n[1], [tree_json(a) for a in n[2]]]


expr = {'env': {k: save(v) for k, v in env_np.items()}, 'cases': [], 'errors': []}
small = {'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5}
for t in EXPRS:
    e = E.parse(t)
    row = {'text': t, 'tree': tree_json(e.tree), 'str': str(e), 'names': sorted(e.names()),
           'round_trip': str(E.parse(str(e)))}
    try:
        v = e.eval(dict(env_np, **small) if set(e.names()) - set(env_np) else env_np)
        if np.ndim(v) == 0:
            row['scalar'] = float(v)
        else:
            row['value'] = save(np.asarray(v, np.float64))
    except Exception as ex_:                                    # noqa: BLE001
        row['eval_error'] = f'{type(ex_).__name__}: {ex_}'
    expr['cases'].append(row)
for t in ERRS:
    expr['errors'].append({'text': t, 'error': raises(lambda: E.parse(t))})
expr['unknown_name'] = raises(lambda: E.parse('slpoe * 2').eval(env_np))
M['expr'] = expr


# --------------------------------------------------------------------------------------------------- noise ---

WINDOWS = {
    'probe_40km': (40000.0, -12000.0, 7.5, 80, 96),             # the design probe's level, non-square here
    'origin_128': (-640.0, -640.0, 10.0, 128, 128),
    'tile_8km': (0.0, 0.0, 31.25, 256, 256),                   # a periodic tile: period 8000 m
    'far_200km': (-201234.5, 187654.25, 3.90625, 64, 96),
    'fine_hero': (1234.0, -987.0, 0.48828125, 96, 64),
}
SPECS = [
    ('gradient', {'kind': 'gradient', 'wavelength_m': 400.0}, ['origin_128', 'probe_40km', 'far_200km']),
    ('gradient_seeded', {'kind': 'gradient', 'wavelength_m': 50.0, 'seed': 3, 'amp': 2.0, 'offset': -1.0},
     ['probe_40km', 'fine_hero']),
    ('fbm', {'kind': 'fbm', 'wavelength_m': 2000.0, 'octaves': 5}, ['origin_128', 'probe_40km', 'far_200km']),
    ('fbm_lac3_gain', {'kind': 'fbm', 'wavelength_m': 900.0, 'octaves': 4, 'lacunarity': 3.0, 'gain': 0.6, 'seed': 9},
     ['origin_128']),
    ('fbm_one_octave', {'kind': 'fbm', 'wavelength_m': 120.0, 'octaves': 1}, ['fine_hero']),
    ('ridged', {'kind': 'ridged', 'wavelength_m': 300.0, 'octaves': 3, 'seed': 1}, ['origin_128', 'probe_40km']),
    ('const', {'kind': 'const', 'value': 2.5}, ['origin_128']),
    ('number', 0.75, ['origin_128']),
    ('sum_probe', {'kind': 'sum', 'terms': [{'kind': 'fbm', 'wavelength_m': 2000, 'octaves': 5, 'amp': 0.6},
                                            {'kind': 'ridged', 'wavelength_m': 300, 'octaves': 3, 'amp': 0.6, 'seed': 1},
                                            {'kind': 'gradient', 'wavelength_m': 50, 'amp': 0.3, 'seed': 2}]},
     ['probe_40km', 'origin_128']),
    ('sum_amp', {'kind': 'sum', 'amp': 1.5, 'offset': 0.25, 'seed': 4,
                 'terms': [{'kind': 'fbm', 'wavelength_m': 700, 'octaves': 3}, 0.5,
                           {'kind': 'gradient', 'wavelength_m': 90, 'amp': 0.2}]}, ['origin_128']),
    ('product', {'kind': 'product', 'terms': [{'kind': 'fbm', 'wavelength_m': 1500, 'octaves': 4, 'offset': 1.0},
                                              {'kind': 'ridged', 'wavelength_m': 400, 'octaves': 2, 'amp': 0.5}]},
     ['origin_128', 'probe_40km']),
    ('warp', {'kind': 'warp', 'amp_m': 100.0, 'wavelength_m': 800.0, 'seed': 2,
              'of': {'kind': 'gradient', 'wavelength_m': 120.0}}, ['origin_128', 'probe_40km']),
    ('nested', {'kind': 'sum', 'offset': 1.0, 'terms': [
        {'kind': 'fbm', 'wavelength_m': 2000, 'amp': 0.6},
        {'kind': 'ridged', 'wavelength_m': 300, 'amp': 0.3, 'seed': 1},
        {'kind': 'warp', 'amp_m': 100, 'wavelength_m': 800, 'of': {'kind': 'gradient', 'wavelength_m': 120}},
        {'kind': 'product', 'terms': [{'kind': 'gradient', 'wavelength_m': 600}, {'kind': 'const', 'value': 0.5}]}]},
     ['origin_128', 'probe_40km']),
    ('periodic_fbm', {'kind': 'fbm', 'wavelength_m': N.snap_wavelength(900.0, 8000.0), 'octaves': 4,
                      'period_m': 8000.0, 'seed': 2}, ['tile_8km']),
    ('periodic_ridged', {'kind': 'ridged', 'wavelength_m': 2000.0, 'octaves': 3, 'period_m': 8000.0},
     ['tile_8km']),
    ('periodic_warp', {'kind': 'warp', 'amp_m': 300.0, 'wavelength_m': 4000.0, 'period_m': 8000.0, 'octaves': 2,
                       'of': {'kind': 'gradient', 'wavelength_m': 500.0, 'period_m': 8000.0}}, ['tile_8km']),
]
noise = {'windows': {k: list(v) for k, v in WINDOWS.items()}, 'cases': [], 'terms': [], 'offsets': [], 'snaps': []}
for label, spec, wins in SPECS:
    for wn in wins:
        x0, y0, cell, h, w = WINDOWS[wn]
        x, y = G.cell_centres(x0, y0, cell, (h, w))
        for seed in (0, 7):
            v = N.field(spec, x, y, seed=seed)
            noise['cases'].append({'label': label, 'spec': spec, 'window': wn, 'seed': seed,
                                   'want': save(np.asarray(v, np.float64))})
# a displacement given to the evaluation (field_gpu's disp): the spec at the moved points
x0, y0, cell, h, w = WINDOWS['origin_128']
x, y = G.cell_centres(x0, y0, cell, (h, w))
dx = (40.0 * np.sin(x / 300.0) + 7.0).astype(np.float32)
dy = (25.0 * np.cos(y / 170.0) - 3.0).astype(np.float32)
for label, spec in (('disp_fbm', {'kind': 'fbm', 'wavelength_m': 500.0, 'octaves': 3}),
                    ('disp_warp', {'kind': 'warp', 'amp_m': 60.0, 'wavelength_m': 700.0,
                                   'of': {'kind': 'ridged', 'wavelength_m': 200.0, 'octaves': 2}})):
    v = N.field(spec, x + dx.astype(np.float64), y + dy.astype(np.float64), seed=5)
    noise['cases'].append({'label': label, 'spec': spec, 'window': 'origin_128', 'seed': 5,
                           'disp': [save(dx), save(dy)], 'want': save(np.asarray(v, np.float64))})
for spec, x0_, y0_ in (({'kind': 'fbm', 'wavelength_m': 2000, 'octaves': 5, 'amp': 0.6}, 40000.0, -12000.0),
                       ({'kind': 'ridged', 'wavelength_m': 300, 'octaves': 3, 'amp': 0.6, 'seed': 1}, 40000.0, -12000.0),
                       ({'kind': 'gradient', 'wavelength_m': 50, 'amp': 0.3, 'seed': 2}, -201234.5, 187654.25),
                       ({'kind': 'fbm', 'wavelength_m': N.snap_wavelength(900.0, 8000.0), 'octaves': 4,
                         'period_m': 8000.0}, 0.0, 0.0),
                       ({'kind': 'const', 'value': 3.0, 'seed': 4}, 0.0, 0.0),
                       ({'kind': 'fbm', 'wavelength_m': 3333.3, 'octaves': 6, 'lacunarity': 2.5, 'gain': 0.45,
                         'seed': -3}, -1e5, 2.5e4)):
    for seed in (0, 7, 123456789):
        terms, const = N._leaf_terms(spec, seed, x0_, y0_)
        noise['terms'].append({'spec': spec, 'seed': seed, 'x0': x0_, 'y0': y0_, 'const': const,
                               'terms': [list(t) for t in terms]})
for s in (0, 1, 2, 7, -3, 123456789, 2 ** 32 + 5, -(2 ** 33)):
    for o in (0, 1, 5):
        noise['offsets'].append([s, o, list(N.lattice_offset(s, o))])
noise['snaps'] = [[w, p, N.snap_wavelength(w, p)] for w, p in ((900.0, 8000.0), (888.0, 8000.0), (1e5, 8000.0),
                                                                (300.0, None), (7.0, 1000.0), (2.5, 10.0))]
noise['snap_freq'] = [[f, t, N.snap_freq(f, t)] for f, t in ((0.0011, 8000.0), (0.5, 3.0), (1e-6, 100.0), (0.3, None))]
noise['period_error'] = raises(lambda: N._period_cells(8000.0, 900.0))
noise['lacunarity_error'] = raises(lambda: N._octaves(900.0, 3, 2.5, 0.5, 8000.0))
noise['kind_error'] = raises(lambda: N.field({'kind': 'perlin'}, x, y))
M['noise'] = noise


# ------------------------------------------------------------------------------------------------- compose ---

CWIN = {'k16': (-8000.0, -8000.0, 125.0, 128, 128), 'k2': (-1500.0, -1000.0, 8.0, 50, 60),
        'vol': (-20000.0, -20000.0, 312.5, 128, 128), 'm1': (-100.0, -100.0, 1.0, 200, 200),
        'np': (37.5, -12.25, 2.5, 72, 88)}


def cxy(name):
    x0, y0, cell, h, w = CWIN[name]
    return G.cell_centres(x0, y0, cell, (h, w))


H_V, R_V, UP = 3700.0, 18000.0, 33.0
LAM = H_V / math.tan(math.radians(UP))
painted = (rng.random((20, 24)) * 50.0).astype(np.float64)
SHAPES = [
    ('cone_linear', {'kind': 'cone', 'centre': [100, -200], 'radius_m': 6000, 'height_m': 900}, 'k16'),
    ('cone_cosine', {'kind': 'cone', 'centre': [0, 0], 'radius_m': 5000, 'height_m': 1200, 'profile': 'cosine'}, 'k16'),
    ('cone_exp', {'kind': 'cone', 'centre': [0, 0], 'radius_m': R_V, 'height_m': H_V, 'profile': 'exp',
                  'lambda_m': LAM}, 'vol'),
    ('cone_exp_crater', {'kind': 'cone', 'centre': [500, -300], 'radius_m': R_V, 'height_m': H_V, 'profile': 'exp',
                         'lambda_m': LAM, 'crater_radius_m': 800}, 'vol'),
    ('bowl', {'kind': 'bowl', 'centre': [-300, 200], 'radius_m': 4000, 'depth_m': 600}, 'k16'),
    ('bowl_exp15', {'kind': 'bowl', 'centre': [0, 0], 'radius_m': 30, 'depth_m': 5, 'exponent': 1.5}, 'np'),
    ('profile', {'kind': 'profile', 'centre': [10, 20], 'r_m': [0, 20, 45, 70, 120], 'z_m': [30, 28, 10, -4, 0]}, 'np'),
    ('array', {'kind': 'array', 'values': painted.tolist(), 'x0': 20.0, 'y0': -20.0, 'cell': 7.0}, 'np'),
    ('field', {'kind': 'field', 'of': {'kind': 'fbm', 'wavelength_m': 3000, 'octaves': 3, 'amp': 100.0}}, 'k16'),
    ('dome', {'kind': 'dome', 'radius_m': 6000}, 'k16'),
    ('ridge', {'kind': 'ridge', 'azimuth_deg': 30, 'length_m': 12000, 'width_m': 5000, 'spurs': 6}, 'k16'),
    ('plateau', {'kind': 'plateau', 'radius_m': 5000, 'edge_m': 1500}, 'k16'),
    ('massif', {'kind': 'massif', 'radius_m': 6000, 'peaks': 5}, 'k16'),
]
compose = {'windows': {k: list(v) for k, v in CWIN.items()}, 'shapes': [], 'uplift': [], 'start': [], 'stamp': [],
           'smooth': [], 'flatten': []}
for label, spec, wn in SHAPES:
    x, y = cxy(wn)
    for seed in (0, 3):
        compose['shapes'].append({'label': label, 'spec': spec, 'window': wn, 'seed': seed,
                                  'want': save(np.asarray(C.shape(spec, x, y, seed), np.float64))})
UPL = [('dome', {'kind': 'dome', 'radius_m': 6000, 'centre': [300, -500]}),
       ('dome_nowarp_notex', {'kind': 'dome', 'radius_m': 4000, 'warp_m': 0, 'texture': 0}),
       ('ridge', {'kind': 'ridge', 'azimuth_deg': 30, 'length_m': 12000, 'width_m': 5000, 'spurs': 6}),
       ('ridge_8_spurs', {'kind': 'ridge', 'azimuth_deg': -75, 'length_m': 14000, 'width_m': 3500, 'spurs': 8,
                          'spur_length_m': 2500, 'seed': 4, 'texture': 0.4}),
       ('ridge_no_spurs', {'kind': 'ridge', 'length_m': 9000}),
       ('plateau', {'kind': 'plateau', 'radius_m': 5000, 'edge_m': 1500}),
       ('massif', {'kind': 'massif', 'radius_m': 6000, 'peaks': 5}),
       ('massif_9', {'kind': 'massif', 'radius_m': 5000, 'peaks': 9, 'warp_m': 900, 'texture': 0.1, 'seed': -2})]
for label, spec in UPL:
    for wn in ('k16', 'k2'):
        x, y = cxy(wn)
        for seed in (0, 3, 11):
            compose['uplift'].append({'label': label, 'spec': spec, 'window': wn, 'seed': seed,
                                      'want': save(np.asarray(C.uplift(spec, x, y, seed=seed), np.float64))})
# the spur and peak plans (numpy's Generator), for the JS plan check
plans = []
for label, spec in UPL:
    for seed in (0, 3, 11):
        s = int(seed) + int(spec.get('seed', 0))
        r_ = np.random.default_rng(abs(s) * 7919 + 17)
        draws = [float(r_.uniform(0, 1)) for _ in range(4)]
        plans.append({'label': label, 'seed': seed, 'first_draws': draws})
compose['plan_draws'] = plans
for label, spec, kw in (('ridge', {'kind': 'ridge', 'length_m': 12000, 'width_m': 5000}, {'height_m': 600.0}),
                        ('dome_peak', {'kind': 'dome', 'radius_m': 6000}, {'height_m': 900.0, 'peak': 0.8,
                                                                             'roughness': 0.25}),
                        ('cone_shape', {'kind': 'cone', 'radius_m': 7000, 'height_m': 1500}, {'height_m': 500.0})):
    x, y = cxy('k16')
    for seed in (2, 5):
        compose['start'].append({'label': label, 'spec': spec, 'window': 'k16', 'seed': seed, 'kw': kw,
                                 'want': save(np.asarray(C.start_surface(spec, x, y, seed=seed, **kw), np.float32))})
hs = (rng.standard_normal((H, W)) * 30.0 + 100.0).astype(np.float32)
ss = (rng.standard_normal((H, W)) * 30.0 + 100.0).astype(np.float32)
ms = rng.random((H, W)).astype(np.float32) * 1.4 - 0.2
compose['stamp_inputs'] = {'h': save(hs), 's': save(ss), 'mask': save(ms)}
for mode, wid in (('add', 0.0), ('max', 0.0), ('min', 0.0), ('smooth_max', 40.0), ('smooth_min', 25.0),
                  ('smooth_max', 0.0), ('blend', 0.0)):
    compose['stamp'].append({'mode': mode, 'width_m': wid,
                             'want': save(C.stamp(hs, ss, mode, wid, mask=ms if mode == 'blend' else None))})
compose['stamp_error'] = raises(lambda: C.stamp(hs, ss, 'mix'))
compose['stamp_blend_error'] = raises(lambda: C.stamp(hs, ss, 'blend'))
for k in (2.0, 0.0, 15.0):
    compose['smooth'].append({'k': k, 'min': save(np.asarray(C.smooth_min(hs, ss, k), np.float64)),
                              'max': save(np.asarray(C.smooth_max(hs, ss, k), np.float64))})
# flatten: areas with and without falloff, a radius through cell centres exactly, heights given and resolved
lv_a = L.Level(0, 'main', -100.0, -100.0, 200.0, 1.0, 200)
lv_b = L.Level(1, 'hero', -40.0, -40.0, 80.0, 0.5, 160)
xa, ya = lv_a.xy()
xb, yb = lv_b.xy()
ha = (0.3 * xa + 0.1 * ya + 3.0 * np.sin(xa / 9.0)).astype(np.float32)
hb = (0.3 * xb + 0.1 * yb + 3.0 * np.sin(xb / 9.0) + 0.01 * np.cos(yb)).astype(np.float32)
AREAS = [
    [{'at': (10.0, -5.0), 'radius': 15.0, 'falloff': 10.0, 'height': None}],
    [{'at': (0.5, 0.5), 'radius': 5.0, 'falloff': 0.0, 'height': None}],           # centres exactly on the circle
    [{'at': (-20.0, 30.0), 'radius': 12.5, 'falloff': 6.0, 'height': 4.25},
     {'at': (-12.0, 26.0), 'radius': 8.0, 'falloff': 0.0}, {'at': (60.0, -50.0), 'radius': 9.0, 'falloff': 20.0}],
    [{'at': (0.0, 0.0), 'radius': 0.2, 'falloff': 1.0}],                           # no centre inside on the hero level
]
for areas in AREAS:
    row = {'areas': [dict(a, at=list(a['at'])) for a in areas]}
    for nm, (lv, x, y, h) in (('a', (lv_a, xa, ya, ha)), ('b', (lv_b, xb, yb, hb))):
        row['weight_' + nm] = [save(np.asarray(C.flatten_weight(a, x, y), np.float64)) for a in C._areas(areas)]
        row['mask_' + nm] = save(C.flatten_mask(areas, x, y))
    try:
        z = C.resolve_flat_heights(areas, [(lv_a, ha), (lv_b, hb)])
        row['heights'] = z
        row['exact_a'] = save(C.flatten_exact(ha, xa, ya, areas, z))
        row['exact_b'] = save(C.flatten_exact(hb, xb, yb, areas, z))
    except Exception as e:                                      # noqa: BLE001
        row['error'] = f'{type(e).__name__}: {e}'
    compose['flatten'].append(row)
compose['flatten_levels'] = {'a': lv_a.to_dict(), 'b': lv_b.to_dict(), 'ha': save(ha), 'hb': save(hb)}
compose['flatten_outside'] = raises(lambda: C.resolve_flat_heights([{'at': (500.0, 0.0), 'radius': 5.0}], [(lv_a, ha)]))
compose['flatten_bad'] = raises(lambda: C._areas([{'at': (0.0, 0.0), 'radius': 0}]))
M['compose'] = compose


# ---------------------------------------------------------------------------------------------------- grid ---

gw = (rng.standard_normal((40, 52)) * 10.0 + np.add.outer(np.arange(40) * 0.7, np.arange(52) * -0.3)).astype(np.float32)
gx_, gy_ = G.cell_centres(10.0, -20.0, 2.0, (24, 30))
lin = (3.0 * gx_ - 2.0 * gy_ + 7.0).astype(np.float32)
big = (rng.random((96, 80)) * 2000.0 - 300.0).astype(np.float32)
terr = np.round(rng.random((64, 64)) * 5.0).astype(np.float32) * 13.0
grid = {'inputs': {'gw': save(gw), 'lin': save(lin), 'big': save(big), 'terr': save(terr)}, 'up': [], 'crop': [],
        'box': [], 'resample': [], 'bilinear': [], 'ramp': [], 'deriv': [], 'edge': []}
for nm, a in (('gw', gw), ('lin', lin), ('big', big)):
    for kind in ('catmull', 'bilinear', 'nearest'):
        grid['up'].append({'input': nm, 'kind': kind, 'want64': save(np.asarray(G._up1(G._up1(a, 0, kind), 1, kind))),
                           'want': save(G.upsample2(a, kind))})
for nm, a, i0, j0, m, mj, kind in (('gw', gw, 6, 4, 10, 8, 'catmull'), ('gw', gw, 0, 0, 16, None, 'catmull'),
                                   ('gw', gw, 40, 30, 12, 10, 'bilinear'), ('gw', gw, 1, 37, 20, 3, 'nearest'),
                                   ('big', big, 30, 40, 24, None, 'catmull'), ('gw', gw, -2, -1, 8, 6, 'catmull')):
    grid['crop'].append({'input': nm, 'i0': i0, 'j0': j0, 'm': m, 'mj': mj, 'kind': kind,
                         'want': save(G.crop_upsample2(a, i0, j0, m, kind, mj=mj))})
for nm, a, f in (('big', big, 2), ('big', big, 4), ('terr', terr, 8), ('gw', gw, 4)):
    grid['box'].append({'input': nm, 'f': f, 'want': save(np.asarray(G.box_down(a, f), np.float64))})
grid['box_error'] = raises(lambda: G.box_down(gw, 3))
for nm, a, s, d, nout in (('big', big, 7.5, 15.0, None), ('big', big, 7.5, 18.75, None), ('big', big, 2.0, 7.4, None),
                          ('gw', gw, 1.0, 3.7, (10, 13)), ('terr', terr, 30.0, 30.0, None), ('big', big, 1.0, 2.5, 30)):
    r = G.resample_box(a, s, d, nout)
    grid['resample'].append({'input': nm, 'src': s, 'dst': d, 'n_out': nout, 'want': save(np.asarray(r, np.float64))})
grid['resample_error'] = raises(lambda: G.resample_box(big, 2.0, 1.0))
pts = rng.uniform(-30.0, 260.0, (2, 500))
pts[:, :4] = [[-50.0, 10.0, 125.0, 400.0], [7.0, -80.0, 125.0, 300.0]]
grid['bilinear'] = {'input': 'gw', 'x0': -12.0, 'y0': 3.0, 'cell': 5.0, 'x': pts[0].tolist(), 'y': pts[1].tolist(),
                    'want': G.sample_bilinear(gw, -12.0, 3.0, 5.0, pts[0], pts[1]).tolist()}
for n, band, kind in ((64, 16, 'smooth'), (64, 16, 'linear'), (40, 5, 'smooth'), ((30, 50), 16, 'smooth'), (8, 16, 'linear')):
    grid['ramp'].append({'n': n, 'band': band, 'kind': kind, 'want': save(G.border_ramp(n, band, kind))})
for n in (17, (5, 9), 1):
    grid['edge'].append({'n': n, 'want': save(G.edge_distance(n).astype(np.int32))})
plane_e = (0.5 * gx_).astype(np.float32)
plane_n = (0.5 * gy_).astype(np.float32)
for nm, a, cell in (('gw', gw, 2.0), ('big', big, 7.5), ('plane_e', plane_e, 2.0), ('plane_n', plane_n, 2.0),
                    ('terr', terr, 1.0)):
    gxx, gyy = G.gradient(a, cell)
    grid['deriv'].append({'input': nm, 'cell': cell, 'data': save(a), 'gx': save(gxx), 'gy': save(gyy),
                          'slope': save(G.slope_deg(a, cell)), 'aspect': save(G.aspect_deg(a, cell))})
grid['north_up'] = {'data': save(gw), 'want': save(G.from_north_up(gw))}
grid['scalars'] = {'tan_deg': [[d, float(G.tan_deg(d))] for d in (0.0, 30.0, 45.0, 89.0, -20.0, 33.5)],
                   'deg_of_tan': [[t, float(G.deg_of_tan(t))] for t in (0.0, 0.5, 1.0, 10.0, -0.25)],
                   'index_of': [[x_, y_, list(map(float, G.index_of(x_, y_, -12.0, 3.0, 5.0)))]
                                for x_, y_ in ((0.0, 0.0), (-9.5, 5.5), (100.25, -7.0))]}
M['grid'] = grid


# -------------------------------------------------------------------------------------------------- fields ---

plan = L.plan_levels(4000, 128, (0, 0), 4, (300, -200), 2.0, warn=lambda m: None)


def quad(x, y):
    return 0.0003 * x * x - 0.0002 * x * y + 0.0004 * y * y + 0.1 * x - 0.05 * y + 30.0


x, y = plan[0].xy()
f0 = F.Fields(plan[0], h=quad(x, y), bed=quad(x, y) - 2.0, A=0.5 * x + 0.25 * y + 1e4, U=np.ones_like(x),
              wear=np.abs(np.sin(x / 300.0)), pin_w=np.zeros_like(x))
fields = {'plan': [lv.to_dict() for lv in plan], 'start': {k: save(v) for k, v in f0.items()}, 'levels': []}
f = f0
for lv in plan[1:]:
    f = f.inherit(lv)
    fields['levels'].append({'index': lv.index, 'names': sorted(f), **{k: save(v) for k, v in f.items()}})
g = f0.inherit(plan[1], rules={'A': 'nearest', 'wear': 'skip', 'U': 'bilinear'}, names=('h', 'A', 'wear', 'U'))
fields['rules'] = {'names': sorted(g), **{k: save(v) for k, v in g.items()}}
pre = plan[0].with_cells(64)
p0 = F.Fields(pre, h=quad(*pre.xy()), qs=np.cos(pre.xy()[0] / 500.0))
up = p0.inherit(plan[0].with_cells(128))
fields['prepass'] = {'level': pre.to_dict(), 'start_h': save(p0['h']), 'start_qs': save(p0['qs']),
                     'h': save(up['h']), 'qs': save(up['qs'])}
fields['thickness'] = save(f0.thickness())
fields['shape_error'] = raises(lambda: F.Fields(plan[1], h=np.zeros((5, 5))))
fields['inherit_error'] = raises(lambda: f0.inherit(plan[2]))
M['fields'] = fields


# ------------------------------------------------------------------------------------------------------ io ---

IOD = os.path.join(OUT, 'io')
os.makedirs(IOD, exist_ok=True)
io = {'heightmaps': [], 'masks': [], 'pngs': [], 'dems': [], 'npz': [], 'saves': []}
hm_rand = (np.random.default_rng(1).random((90, 70)) * 1234.5 + 400.0).astype(np.float32)
lo_, hi_ = 100.0, 100.0 + 65535 * 0.25
q = np.arange(90 * 70).reshape(90, 70) % 7
hm_terr = (lo_ + (np.arange(90 * 70).reshape(90, 70) * 37 % 65536) * 0.25 + (q == 3) * 0.125).astype(np.float32)
hm_terr[0, 0], hm_terr[-1, -1] = lo_, hi_                       # exact half-way quantisation points (k + 0.5)
hm_neg = (np.random.default_rng(3).standard_normal((64, 48)) * 50.0 - 20.0).astype(np.float32)
hm_neg[5, 5] = 1e-9
hm_neg[6, 6] = -1e-30
hm_flat = np.full((33, 41), 12.5, np.float32)
for name, h, kw in (('rand', hm_rand, {}), ('terraced', hm_terr, {}), ('neg', hm_neg, {}),
                    ('clipped', hm_rand, {'range_m': (700.0, 1400.0)}), ('flat', hm_flat, {}),
                    ('south_up', hm_neg, {'north_up': False, 'x0': -100.0, 'y0': 50.0})):
    meta = IO.export_heightmap(h, IOD, 7.8125, name, formats=('png16', 'r32', 'r16'), **kw)
    v = IO.read_png(os.path.join(IOD, name + '.png'))
    h16, _ = IO.read_heightmap(os.path.join(IOD, name + '.json'), prefer=('png16',))
    hr16, _ = IO.read_heightmap(os.path.join(IOD, name + '.json'), prefer=('r16',))
    io['heightmaps'].append({'name': name, 'kw': {k: (list(v_) if isinstance(v_, tuple) else v_) for k, v_ in kw.items()},
                             'data': save(h), 'meta': meta, 'pixels': save(v.astype(np.uint16)),
                             'read_png16': save(h16), 'read_r16': save(hr16)})
for name, m, kw in (('slope8', np.linspace(0, 90, 70 * 90).reshape(90, 70), {'lo': 0, 'hi': 90}),
                    ('slope16', np.linspace(0, 90, 70 * 90).reshape(90, 70), {'lo': 0, 'hi': 90, 'bits': 16}),
                    ('auto8', hm_neg.astype(np.float64), {}),
                    ('south8', hm_rand.astype(np.float64), {'north_up': False, 'lo': 500.0})):
    m = np.asarray(m, np.float32)                               # the port's masks are float32 fields
    meta = IO.export_mask(m, IOD, name, **kw)
    io['masks'].append({'name': name, 'kw': kw, 'data': save(np.asarray(m, np.float32)),
                        'data64': save(np.asarray(m, np.float64)), 'meta': meta,
                        'pixels': save(IO.read_png(os.path.join(IOD, name + '.png')))})
for dt in (np.uint8, np.uint16):
    for c in (1, 2, 3, 4):
        a = rng.integers(0, np.iinfo(dt).max, (13, 17, c), dtype=np.int64).astype(dt)
        fn = f'codec_{np.dtype(dt).name}_{c}.png'
        IO.write_png(os.path.join(IOD, fn), a)
        io['pngs'].append({'file': fn, 'data': save(a), 'channels': c, 'bits': 8 * np.dtype(dt).itemsize})


def idat_rows(path):
    """The decompressed IDAT (the filtered rows) of a PNG Blender wrote, and its IHDR."""
    with open(path, 'rb') as fh:
        data = fh.read()
    pos, idat, ihdr = 8, [], None
    while pos < len(data):
        n = int.from_bytes(data[pos:pos + 4], 'big')
        kind = data[pos + 4:pos + 8]
        if kind == b'IHDR':
            ihdr = data[pos + 8:pos + 8 + n]
        elif kind == b'IDAT':
            idat.append(data[pos + 8:pos + 8 + n])
        pos += 12 + n
    return np.frombuffer(zlib.decompress(b''.join(idat)), np.uint8), ihdr


for row in io['heightmaps'] + io['masks']:
    raw, ihdr = idat_rows(os.path.join(IOD, row['name'] + '.png'))
    row['filtered'] = save(raw)
    row['ihdr'] = ihdr.hex()
for row in io['pngs']:
    raw, ihdr = idat_rows(os.path.join(IOD, row['file']))
    row['filtered'] = save(raw)
    row['ihdr'] = ihdr.hex()
# a PNG with the Paeth filter on one row (another writer's): Blender's reader takes it, the port's raises naming it
img = (np.add.outer(np.arange(12), np.arange(10)) * 7 % 256).astype(np.uint8)
rows = []
for j in range(12):
    line = img[j].tobytes()
    rows.append(bytes([4 if j == 5 else 0]) + (line if j != 5 else bytes(10)))
paeth = IO._SIG + IO._chunk(b'IHDR', bytes.fromhex('0000000a0000000c0800000000')) + \
    IO._chunk(b'IDAT', zlib.compress(b''.join(rows))) + IO._chunk(b'IEND', b'')
with open(os.path.join(IOD, 'paeth.png'), 'wb') as fh:
    fh.write(paeth)
io['paeth'] = {'file': 'paeth.png', 'pixels': save(IO.read_png(os.path.join(IOD, 'paeth.png')))}
# reference DEMs where real_place reads them
dem_dirs = [d for d in os.environ.get('EIDO_TERRAIN_DEMS', '').split(os.pathsep) if d] + \
    [os.path.join(BLENDER_DIR, 'tests', 'terrain', 'reference', 'data')]
for nm in ('lauterbrunnen', 'crater_lake', 'palouse_hills', 'meteor_crater'):
    for d in dem_dirs:
        js = os.path.join(d, nm + '.json')
        if os.path.isfile(js):
            with open(js, encoding='utf-8') as fh:
                meta = json.load(fh)
            for key in ('height_png', 'water_mask_png'):
                if meta.get(key):
                    p = os.path.join(d, meta[key])
                    a = IO.read_png(p)
                    io['dems'].append({'name': nm, 'key': key, 'path': os.path.relpath(p, ROOT).replace('\\', '/'),
                                       'shape': list(a.shape), 'dtype': str(a.dtype),
                                       'sha1': hashlib.sha1(np.ascontiguousarray(a).tobytes()).hexdigest(),
                                       'sum': int(a.astype(np.int64).sum())})
            break
hsf = (np.add.outer(np.arange(64) * 3.0, np.zeros(80)) + 40.0 * np.sin(np.arange(80) / 7.0)).astype(np.float32)
io['hillshade'] = {'data': save(hsf), 'cell': 2.5, 'want': save(IO.hillshade(hsf, 2.5)),
                   'want2': save(IO.hillshade(hsf, 2.5, 200.0, 25.0, 3.0)), 'u8': save(IO.to_u8(IO.hillshade(hsf, 2.5)))}
# npz: np.savez of every dtype the terrain stores, and Terrain.save files
arrs = {'L0__f__h': hm_rand, 'L0__m__slope': hm_rand.astype(np.float16), 'L1__m__wear': hm_neg,
        'scalar64': np.float64(2.5), 'vec': np.arange(7, dtype=np.int32), 'img': rng.integers(0, 255, (9, 11, 3), dtype=np.int64).astype(np.uint8),
        'u16': rng.integers(0, 65535, (5, 6), dtype=np.int64).astype(np.uint16), 'f64': rng.random((4, 3)),
        'flags': rng.random((6, 6)) > 0.5, 'empty': np.zeros((0, 4), np.float32), 'u32': np.arange(10, dtype=np.uint32)}
np.savez(os.path.join(IOD, 'mixed.npz'), **arrs)
np.savez_compressed(os.path.join(IOD, 'mixed_compressed.npz'), **arrs)
io['npz'] = [{'file': 'mixed.npz', 'arrays': {k: {'dtype': np.asarray(v).dtype.str, 'shape': list(np.shape(v)),
                                                  'sha1': hashlib.sha1(np.ascontiguousarray(v).tobytes()).hexdigest()}
                                              for k, v in arrs.items()}},
             {'file': 'mixed_compressed.npz', 'compressed': True}]
saves = [s for s in os.environ.get('EIDO_TERRAIN_SAVES', '').split(os.pathsep) if s]
if not saves:
    d = os.path.join(BLENDER_DIR, 'tests', 'terrain', 'out', 'surfacing_judge', 'terrains')
    saves = [os.path.join(d, nm + '.npz') for nm in ('meadow', 'dunes', 'real_place') if os.path.isfile(os.path.join(d, nm + '.npz'))]
for p in saves:
    with np.load(p, allow_pickle=False) as z:
        names = list(z.files)
        info = {k: {'dtype': z[k].dtype.str, 'shape': list(z[k].shape),
                    'sha1': hashlib.sha1(np.ascontiguousarray(z[k]).tobytes()).hexdigest()} for k in names}
    io['saves'].append({'path': os.path.abspath(p), 'bytes': os.path.getsize(p), 'arrays': info, 'order': names,
                        'sha1': hashlib.sha1(open(p, 'rb').read()).hexdigest()})
if BIG:
    os.makedirs(BIG, exist_ok=True)
    big = {}
    n_ = 2048
    # 7 levels x (24 float32 fields + 30 float16 masks) at 2048 cells: 4.37 GB. Constant arrays are broadcast views
    # (np.savez writes them through nditer, as any array), so this process never holds 4 GB
    for lvl in range(7):
        for k in ('h', 'bed', 'A', 'qs', 'wear', 'deposit', 'talus', 'water', 'U', 'K', 'Sc', 'G', 'ice', 'lava',
                  'sand', 'pin_w', 'pin_h', 'K_factor', 'Sc_factor', 'lock', 'rock', 'soil', 'fill', 'lake'):
            big[f'L{lvl}__f__{k}'] = np.broadcast_to(np.float32(lvl * 100 + len(k) + 0.25), (n_, n_))
        for k in ('slope', 'flow', 'wetness', 'occlusion', 'snow', 'vegetation', 'peaks', 'channels', 'rock_toe',
                  'rock_shadow', 'aspect', 'northness', 'eastness', 'convex_20m', 'concave_20m', 'strata',
                  'convex_5m', 'concave_5m', 'convex_80m', 'concave_80m', 'curvature', 'sky', 'sun', 'wear',
                  'deposit', 'talus', 'water', 'scree', 'moss', 'ice'):
            big[f'L{lvl}__m__{k}'] = np.broadcast_to(np.float16((lvl + 1) * 0.01 * len(k)), (n_, n_))
    big['L0__f__h'] = (np.random.default_rng(9).random((n_, n_)) * 3000.0).astype(np.float32)
    big['L6__m__slope'] = (np.random.default_rng(10).random((n_, n_)) * 60.0).astype(np.float16)
    bp = os.path.join(BIG, 'big_save.npz')
    np.savez(bp, **big)
    h_ = hashlib.sha1()
    with open(bp, 'rb') as fh:
        while True:
            b = fh.read(1 << 24)
            if not b:
                break
            h_.update(b)
    io['big'] = {'path': os.path.abspath(bp), 'bytes': os.path.getsize(bp), 'sha1': h_.hexdigest(), 'order': list(big),
                 'arrays': {k: {'dtype': v.dtype.str, 'shape': list(v.shape),
                                'sha1': hashlib.sha1(v.tobytes()).hexdigest()} for k, v in big.items()}}
    del big
M['io'] = io

with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as fh:
    json.dump(M, fh, indent=1)
print(f'[core_inputs] {_n[0]} arrays, {len(levels["cases"]) + len(levels["quality_cases"]) + len(levels["half_cases"])} plans, '
      f'{len(noise["cases"])} noise cases, {len(compose["shapes"]) + len(compose["uplift"])} shapes, '
      f'{len(io["saves"])} Blender saves -> {OUT}')
