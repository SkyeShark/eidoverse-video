"""The terrain core's plain-Python tests (system Python with numpy, no GPU; Blender's Python works too):

    python blender/tests/terrain/core/test_core.py

  levels   plan_levels for 20 focus cases: every child on its parent's even grid lines, half its cell, at least
           16 parent cells inside, the focus at least 16 cells inside each hero window, the hero cell reached (or
           a warning saying why not); the design's 8 km example; focus outside the tile is an error;
           select_levels for every spec form
  fields   shape checks, inherit (Catmull-Rom reproduces a quadratic surface exactly, bilinear a linear one, U/K/Sc
           and pins skipped) along a whole plan
  expr     the mask language: precedence, functions, errors that name the token
  recipe   knobs ($ references, apply, range and nearest-name errors), JSON round trip, describe, op registry
  noise    deterministic, seeds differ, periodic tiles wrap, derivatives match finite differences, fbm std 1/3,
           a place has the same value whichever grid samples it
  io       heightmap png16 / r32 round trips, masks, PNG codec (all channel counts, 8/16 bit, other writers' filters)
  cache    keys stable and sensitive, atomic save / load, complete() only after meta, prune
  compose  stamp modes, smooth min/max, the stratovolcano cone's slopes (design 4.7), flatten exact and C1, uplift
           shapes smooth and bounded
  grid     upsampling reproduces linear fields, border ramp, slope / aspect conventions
Writes out/core/core_tests.json; exit 1 on a failure.
"""
import json
import math
import os
import shutil
import sys
import tempfile
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plain_import  # noqa: E402

OUT = plain_import.install()

import numpy as np  # noqa: E402

from eidoblend.terrain.core import (cache as CA, compose as C, expr as E, fields as F, grid as G,  # noqa: E402
                                    io as IO, levels as L, recipe as RC, world_noise as N)

FAILED = []
RESULTS = {}


def check(name, cond, detail=None):
    RESULTS[name] = {'ok': bool(cond), 'detail': detail}
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f': {detail}' if detail is not None else ''), flush=True)
    if not cond:
        FAILED.append(name)


def raises(fn, exc=Exception):
    try:
        fn()
    except exc as e:                                               # noqa: BLE001
        return str(e)
    return None


# ------------------------------------------------------------------------------------------------- levels ---

FOCUS_CASES = [
    # (label, size, resolution, centre, context, focus, hero)
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


def test_levels():
    rows = []
    for label, size, res, centre, ctx, focus, hero in FOCUS_CASES:
        warns = []
        if focus == 'cams':
            focus = [_Cam(-100, 50, 1.7), _Cam(-60, 70, 1.7)]
        plan = L.plan_levels(size, res, centre, ctx, focus, hero, warn=warns.append)
        ok = True
        why = []
        for lv in plan[1:]:
            p = plan[lv.parent]
            for a, b in ((lv.x0, p.x0), (lv.y0, p.y0), (lv.x1, p.x0), (lv.y1, p.y0)):
                k = (a - b) / (2 * p.cell)
                if abs(k - round(k)) > 1e-6:
                    ok, _ = False, why.append(f'{lv.index} not on even lines')
            if min(lv.x0 - p.x0, lv.y0 - p.y0, p.x1 - lv.x1, p.y1 - lv.y1) < 16 * p.cell - 1e-6 * p.cell:
                ok, _ = False, why.append(f'{lv.index} within 16 cells of its parent edge')
            if abs(lv.cell * 2 - p.cell) > 1e-9 * p.cell:
                ok, _ = False, why.append(f'{lv.index} cell not half')
            if lv.role == 'hero' and lv.n % 4:
                ok, _ = False, why.append(f'{lv.index} n {lv.n} not a multiple of 4')
            if lv.n > 2048:
                ok, _ = False, why.append(f'{lv.index} n {lv.n} > 2048')
            ij = lv.in_parent(plan)
            if ij[0] % 2 or ij[1] % 2 or ij[2] % 2:
                ok, _ = False, why.append(f'{lv.index} in_parent {ij} not even')
        main = [lv for lv in plan if lv.role == 'main'][0]
        if abs(main.side - size) > 1e-6 * size or main.n != res:
            ok, _ = False, why.append('main tile wrong')
        for lv in plan:
            if lv.role == 'context':
                if max(abs(lv.centre[0] - main.centre[0]), abs(lv.centre[1] - main.centre[1])) > lv.cell * 1.001:
                    ok, _ = False, why.append(f'context {lv.index} not centred')
        heroes = [lv for lv in plan if lv.role == 'hero']
        if focus is not None and hero:
            pts = L.focus_points(focus)
            for lv in heroes:
                if not bool(np.all(lv.contains(pts[:, 0], pts[:, 1], margin=16 * lv.cell))):
                    ok, _ = False, why.append(f'focus not 16 cells inside hero {lv.index}')
            reached = heroes and heroes[-1].cell <= hero * (1 + 1e-9)
            if not reached and not warns and main.cell > hero:
                ok, _ = False, why.append('hero cell not reached and no warning')
        elif heroes:
            ok, _ = False, why.append('hero levels without a focus or hero cell')
        n_ctx = sum(lv.role == 'context' for lv in plan)
        if n_ctx != (math.ceil(math.log2(ctx) - 1e-9) if ctx and ctx > 1 else 0):
            ok, _ = False, why.append(f'{n_ctx} context levels')
        rows.append({'case': label, 'levels': [repr(lv) for lv in plan], 'warnings': warns})
        check(f'plan_{label}', ok, f"{len(plan)} levels, cells {[round(lv.cell, 4) for lv in plan]}"
              + (f', warned: {warns[0][:90]}' if warns else '') + (f' PROBLEMS {why}' if why else ''))
    RESULTS['plan_cases'] = rows
    ex = L.plan_levels(8000, 1024, (0, 0), 4, (1200, -300), 0.5, warn=lambda m: None)
    # the design's example rounds the last level to "512 m at 0.5 m": halving 1000 m gives 500 m at 0.488 m
    want = [(32000, 31.25), (16000, 15.625), (8000, 7.8125), (4000, 3.90625), (2000, 1.953125), (1000, 0.9765625),
            (500, 0.48828125)]
    got = [(lv.side, lv.cell) for lv in ex]
    check('plan_design_example_seven_levels', got == want and all(lv.n == 1024 for lv in ex[:3]) and
          ex[0].prepass == (256, 512), {'got': got, 'prepass': ex[0].prepass, 'n': [lv.n for lv in ex]})
    check('plan_focus_outside_is_error', raises(lambda: L.plan_levels(8000, 1024, (0, 0), 4, (4100, 0), 0.5),
                                                ValueError) is not None)
    msg = raises(lambda: L.plan_levels(8000, 1022, (0, 0), 4, None, None), ValueError)
    check('plan_bad_resolution_names_nearest', msg is not None and '1016' in msg and '1024' in msg, msg)
    sel = {s: L.select_levels(s, ex, warn=lambda m: None) for s in
           ('all', 'first', 'last', 'context', 'main', 'hero', 'cell>=30', 'cell<=2', 'cell<1', 'resolves:2000',
            'resolves:300', 'resolves:100', 'resolves:1')}
    want_sel = {'all': [0, 1, 2, 3, 4, 5, 6], 'first': [0], 'last': [6], 'context': [0, 1], 'main': [2],
                'hero': [3, 4, 5, 6], 'cell>=30': [0], 'cell<=2': [4, 5, 6], 'cell<1': [5, 6],
                'resolves:2000': [0], 'resolves:300': [0], 'resolves:100': [2], 'resolves:1': [6]}
    check('select_levels_all_forms', sel == want_sel, sel)
    check('select_levels_list_and_index', L.select_levels(['main', 6, 'cell>=30'], ex) == [0, 2, 6])
    check('select_levels_bad_spec', raises(lambda: L.parse_levels_spec('cells>=3'), ValueError) is not None)


# ------------------------------------------------------------------------------------------------- fields ---

def test_fields():
    plan = L.plan_levels(4000, 128, (0, 0), 4, (300, -200), 2.0, warn=lambda m: None)

    def quad(x, y):
        return 0.0003 * x * x - 0.0002 * x * y + 0.0004 * y * y + 0.1 * x - 0.05 * y + 30.0

    x, y = plan[0].xy()
    f = F.Fields(plan[0], h=quad(x, y), bed=quad(x, y) - 2.0, A=0.5 * x + 0.25 * y + 1e4, U=np.ones_like(x))
    worst_h, worst_a = 0.0, 0.0
    for lv in plan[1:]:
        f = f.inherit(lv)
        xs, ys = lv.xy()
        inner = (slice(4, -4), slice(4, -4))
        worst_h = max(worst_h, float(np.abs(f['h'] - quad(xs, ys))[inner].max()))
        worst_a = max(worst_a, float(np.abs(f['A'] - (0.5 * xs + 0.25 * ys + 1e4))[inner].max()))
        if 'U' in f:
            break
    scale = float(np.abs(quad(*plan[0].xy())).max())
    check('fields_inherit_catmull_quadratic_exact', worst_h <= 2e-6 * scale + 1e-3,
          {'max_err_m': worst_h, 'levels': len(plan)})
    check('fields_inherit_bilinear_linear_exact', worst_a <= 2e-6 * 3e4, {'max_err': worst_a})
    check('fields_inherit_skips_U_K_Sc_pins', 'U' not in f and 'bed' in f, sorted(f))
    check('fields_shape_checked', raises(lambda: F.Fields(plan[1], h=np.zeros((5, 5))), ValueError) is not None)
    g = F.Fields(plan[1])
    g.new('h', 3.0)
    g.ensure('h', 9.0)
    g['bed'] = 1.0
    check('fields_new_ensure_scalar', float(g['h'][0, 0]) == 3.0 and float(g.thickness()[0, 0]) == 2.0 and
          g['h'].dtype == np.float32)
    pre = plan[0].with_cells(plan[0].prepass[0]) if plan[0].prepass else plan[0].with_cells(64)
    p0 = F.Fields(pre, h=quad(*pre.xy()))
    up = p0.inherit(plan[0].with_cells(pre.n * 2))
    check('fields_inherit_prepass_same_window', up['h'].shape == (pre.n * 2,) * 2)


# --------------------------------------------------------------------------------------------------- expr ---

def test_expr():
    env = {'slope': np.array([10.0, 38.5, 60.0]), 'wear': np.array([0.0, 1.0, 2.0]), 'deposit': np.array([1.0, 0.0,
                                                                                                         0.5])}
    e = E.parse('smoothstep(32, 45, slope) + 0.5*wear - 2*deposit')
    want = np.array([0 + 0 - 2, 0.5 + 0.5 - 0, 1 + 1 - 1])
    check('expr_design_example', np.allclose(e.eval(env), want), e.eval(env).tolist())
    check('expr_names', e.names() == {'slope', 'wear', 'deposit'})
    check('expr_precedence', np.allclose(E.parse('1 + 2 * 3 - -4 / 2').eval({}), 9.0) and
          np.allclose(E.parse('(1 + 2) * 3').eval({}), 9.0) and np.allclose(E.parse('2 - (3 - 4)').eval({}), 3.0))
    check('expr_functions', np.allclose(E.parse('max(wear, deposit, 0.7)').eval(env), [1.0, 1.0, 2.0]) and
          np.allclose(E.parse('min(wear, deposit)').eval(env), [0.0, 0.0, 0.5]) and
          np.allclose(E.parse('clamp(slope, 20, 50)').eval(env), [20, 38.5, 50]) and
          np.allclose(E.parse('abs(0 - wear)').eval(env), [0, 1, 2]) and
          np.allclose(E.parse('smoothstep(45, 32, slope)').eval(env), [1.0, 0.5, 0.0]))
    rt = E.parse(str(E.parse('a - (b - c) / (d * e)')))
    check('expr_text_round_trip', str(rt) == str(E.parse('a - (b - c) / (d * e)')) and
          np.isclose(rt.eval({'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5}), 1 - (2 - 3) / 20), str(rt))
    errs = {'unknown_function': raises(lambda: E.parse('smoothsetp(1, 2, x)')),
            'bad_char': raises(lambda: E.parse('slope ** 2')),
            'arity': raises(lambda: E.parse('smoothstep(1, x)')),
            'unclosed': raises(lambda: E.parse('min(a, b')),
            'unknown_name': raises(lambda: E.parse('slpoe * 2').eval(env))}
    check('expr_errors_name_the_problem', all(errs.values()) and 'smoothstep' in errs['unknown_function'] and
          'slope' in errs['unknown_name'], errs)


# ------------------------------------------------------------------------------------------------- recipe ---

def test_recipe():
    def spacing_to_D(p):
        f = p.stage('fluvial')
        f['D'] = f['K'] * (p['valley_spacing_m'] / 6.5) ** 2

    r = RC.Recipe('test_range', 'a test range', ['san_gabriel_mountains'],
                  {'size': 12000.0, 'resolution': 1024, 'context': 4, 'hero_cell': 0.5, 'palette': 'alpine'},
                  {'relief_m': RC.Knob(2000.0, 'm', (200.0, 6000.0), 'p99.5 relief'),
                   'valley_spacing_m': RC.Knob(400.0, 'm', (60.0, 3000.0), 'valley spacing', apply=spacing_to_D),
                   'kind': RC.Knob('star', 'choice', ['star', 'barchan'], 'dune kind')},
                  [RC.Stage('uplift', {'shape': {'kind': 'ridge', 'length_m': 9000}}),
                   RC.Stage('fluvial', {'K': 1.5e-5, 'relief_m': '$relief_m', 'list': ['$kind', 3]}, levels='all'),
                   RC.Stage('breakup', {'scales_m': [50, 15, 5]}, levels='hero', where='smoothstep(30, 45, slope)')])
    vals, stages = r.resolve({'relief_m': 2800})
    fl = stages[1].params
    check('recipe_resolve_refs_and_apply', vals['relief_m'] == 2800.0 and fl['relief_m'] == 2800.0 and
          fl['list'] == ['star', 3] and abs(fl['D'] - 1.5e-5 * (400 / 6.5) ** 2) < 1e-18 and
          r.stages[1].params['relief_m'] == '$relief_m', fl)
    msgs = {'unknown_knob': raises(lambda: r.resolve({'relief': 100})),
            'out_of_range': raises(lambda: r.resolve({'relief_m': 9e9})),
            'bad_choice': raises(lambda: r.resolve({'kind': 'linear'})),
            'bad_levels': raises(lambda: RC.Stage('x', levels='heroes')),
            'bad_where': raises(lambda: RC.Stage('x', where='slope >')),
            'not_json': raises(lambda: RC.Stage('x', {'a': object()}).to_dict())}
    check('recipe_errors', all(msgs.values()) and 'relief_m' in msgs['unknown_knob'], msgs)
    d = r.to_dict()
    s = json.dumps(d)
    r2 = RC.Recipe.from_dict(json.loads(s), base=r)
    v2, st2 = r2.resolve({'valley_spacing_m': 800})
    check('recipe_json_round_trip_keeps_apply', json.dumps(r2.to_dict()) == s and
          abs(st2[1].params['D'] - 1.5e-5 * (800 / 6.5) ** 2) < 1e-18)
    r3 = RC.Recipe.from_dict(json.loads(s))
    v3, st3 = r3.resolve()
    check('recipe_dict_without_base_has_no_apply', 'D' not in st3[1].params)
    txt = r.describe()
    check('recipe_describe', 'valley_spacing_m = 400.0 m' in txt and 'breakup on hero where' in txt, txt[:300])
    plan = L.plan_levels(12000, 1024, (0, 0), 4, (0, 0), 0.5, warn=lambda m: None)
    check('stage_select', stages[2].select(plan) == [lv.index for lv in plan if lv.role == 'hero'])
    RC.register_op('test_op_xyz', lambda *a: 1)
    check('op_registry', RC.get_op('test_op_xyz')() == 1 and 'test_op_xyz' in RC.op_names() and
          'test_op_xyz' in (raises(lambda: RC.get_op('test_op_xzy'), KeyError) or ''))


# -------------------------------------------------------------------------------------------------- noise ---

def test_noise():
    rng = np.random.default_rng(0)
    x, y = rng.uniform(-3e4, 3e4, 20000), rng.uniform(-3e4, 3e4, 20000)
    a = N.gradient(x, y, 400.0, seed=3)
    check('noise_deterministic', np.array_equal(a, N.gradient(x, y, 400.0, seed=3)))
    b = N.gradient(x, y, 400.0, seed=4)
    check('noise_seeds_differ', abs(np.corrcoef(a, b)[0, 1]) < 0.05, float(np.corrcoef(a, b)[0, 1]))
    per = 8000.0
    w = N.snap_wavelength(900.0, per)
    p1 = N.fbm(x, y, w, 4, seed=2, period_m=per)
    p2 = N.fbm(x + per, y - 3 * per, w, 4, seed=2, period_m=per)
    check('noise_periodic_tile_wraps', np.allclose(p1, p2, atol=1e-9) and abs(w - 888.888888) < 1e-3, w)
    check('noise_periodic_needs_dividing_wavelength',
          raises(lambda: N.fbm(x, y, 900.0, 2, period_m=per), ValueError) is not None)
    v, dx, dy = N.gradient(x, y, 250.0, seed=1, derivatives=True)
    e = 1e-3
    fdx = (N.gradient(x + e, y, 250.0, seed=1) - N.gradient(x - e, y, 250.0, seed=1)) / (2 * e)
    fdy = (N.gradient(x, y + e, 250.0, seed=1) - N.gradient(x, y - e, 250.0, seed=1)) / (2 * e)
    check('noise_derivatives_match_fd', np.allclose(dx, fdx, atol=1e-6) and np.allclose(dy, fdy, atol=1e-6),
          float(max(np.abs(dx - fdx).max(), np.abs(dy - fdy).max())))
    big = rng.uniform(-2e5, 2e5, (2, 400000))
    sd = float(N.fbm(big[0], big[1], 300.0, 5, seed=9).std())
    check('noise_fbm_std_one_third', abs(sd - 1 / 3) < 0.03, sd)
    lv_a = L.Level(0, 'main', -512.0, 64.0, 512.0, 4.0, 128)
    lv_b = L.Level(1, 'hero', -256.0, 128.0, 128.0, 2.0, 64)
    xa, ya = lv_a.xy()
    xb, yb = lv_b.xy()
    fa = N.fbm(xa, ya, 300.0, 4, seed=5)
    fb = N.fbm(xb, yb, 300.0, 4, seed=5)
    alone = np.array([N.fbm(xb[j, i], yb[j, i], 300.0, 4, seed=5) for j, i in ((0, 0), (17, 40), (63, 63))])
    check('noise_point_value_independent_of_grid', np.array_equal(alone, fb[[0, 17, 63], [0, 40, 63]]))
    check('noise_parent_and_child_agree', np.allclose(G.sample_bilinear(fa, lv_a.x0, lv_a.y0, 4.0, xb, yb), fb,
                                                      atol=0.02),
          float(np.abs(G.sample_bilinear(fa, lv_a.x0, lv_a.y0, 4.0, xb, yb) - fb).max()))
    spec = {'kind': 'sum', 'terms': [{'kind': 'fbm', 'wavelength_m': 2000, 'amp': 0.6},
                                     {'kind': 'ridged', 'wavelength_m': 300, 'amp': 0.3, 'seed': 1},
                                     {'kind': 'warp', 'amp_m': 100, 'wavelength_m': 800,
                                      'of': {'kind': 'gradient', 'wavelength_m': 120}}], 'offset': 1.0}
    fv = N.field(spec, x[:500], y[:500], seed=4)
    check('noise_field_spec', fv.shape == (500,) and np.isfinite(fv).all() and
          raises(lambda: N.field({'kind': 'perlin'}, x, y), ValueError) is not None)
    t0 = time.perf_counter()
    xx, yy = G.cell_centres(0, 0, 10.0, 128)
    N.field(spec, xx, yy)
    check('noise_twin_fast_at_128', time.perf_counter() - t0 < 5.0, round(time.perf_counter() - t0, 2))


# ----------------------------------------------------------------------------------------------------- io ---

def test_io():
    tmp = tempfile.mkdtemp(prefix='core_io_', dir=OUT)
    h = (np.random.default_rng(1).random((90, 70)) * 1234.5 + 400.0).astype(np.float64)
    meta = IO.export_heightmap(h, tmp, 7.8125, 'height', formats=('png16', 'r32', 'r16'), x0=-100.0, y0=50.0)
    h32, m32 = IO.read_heightmap(os.path.join(tmp, 'height.json'), prefer=('r32',))
    h16, _ = IO.read_heightmap(os.path.join(tmp, 'height.json'), prefer=('png16',))
    hr16, _ = IO.read_heightmap(os.path.join(tmp, 'height.json'), prefer=('r16',))
    step = (h.max() - h.min()) / 65535
    check('io_r32_round_trip_float32', np.allclose(h32, h.astype(np.float32), atol=0) and m32['cell_m'] == 7.8125)
    check('io_png16_round_trip_quantised', float(np.abs(h16 - h).max()) <= 0.5 * step + 1e-9 and
          float(np.abs(hr16 - h).max()) <= 0.5 * step + 1e-9, float(np.abs(h16 - h).max()))
    raw = IO.read_png(os.path.join(tmp, 'height.png'))
    check('io_png16_is_north_up', raw.shape == (90, 70) and raw[0, 0] == round((h[-1, 0] - h.min()) / (h.max() - h.min())
                                                                               * 65535))
    rng = np.random.default_rng(2)
    ok = True
    for dt in (np.uint8, np.uint16):
        for c in (1, 2, 3, 4):
            a = rng.integers(0, np.iinfo(dt).max, (13, 17, c), dtype=np.int64).astype(dt)
            back, info = IO.decode_png(IO.encode_png(a))
            ok = ok and np.array_equal(back, a) and info['channels'] == c
    check('io_png_codec_all_channels', ok)
    try:
        from PIL import Image
        pa = (np.add.outer(np.arange(40), np.arange(50)) * 3 % 256).astype(np.uint8)
        rgb = np.stack([pa, pa[::-1], 255 - pa], -1)
        p = os.path.join(tmp, 'pil.png')
        Image.fromarray(rgb).save(p, optimize=True)
        check('io_png_reads_other_writers_filters', np.array_equal(IO.read_png(p), rgb))
    except ImportError:
        check('io_png_reads_other_writers_filters', True, 'Pillow not available here: skipped')
    mm = IO.export_mask(np.linspace(0, 90, 70 * 90).reshape(90, 70), tmp, 'slope', 0, 90)
    check('io_mask_written', os.path.exists(os.path.join(tmp, 'slope.png')) and mm['hi'] == 90)
    shutil.rmtree(tmp, ignore_errors=True)


# -------------------------------------------------------------------------------------------------- cache ---

def test_cache():
    base = tempfile.mkdtemp(prefix='core_cache_', dir=OUT)
    plan = L.plan_levels(4000, 128, (0, 0), 2, (100, 100), 4.0, warn=lambda m: None)
    rec = RC.Recipe('k', 't', stages=[RC.Stage('fluvial', {'K': 1e-5})])
    k1 = CA.make_key(rec, {'relief_m': 100}, 4000, 128, 7, plan, [(100, 100)])
    k2 = CA.make_key(rec.to_dict(), {'relief_m': 100}, 4000, 128, 7, [lv.to_dict() for lv in plan], [[100, 100]])
    k3 = CA.make_key(rec, {'relief_m': 100}, 4000, 128, 8, plan, [(100, 100)])
    check('cache_key_stable_and_sensitive', k1 == k2 and k1 != k3 and len(k1) == 40)
    c = CA.Cache(k1, base)
    f = F.Fields(plan[0], h=np.random.default_rng(0).random((128, 128)), A=np.ones((128, 128)))
    c.save_level(0, f)
    check('cache_incomplete_before_meta', not c.complete())
    c.save_level(1, F.Fields(plan[1], h=np.zeros((plan[1].n,) * 2)))
    c.write_meta({'levels': 2, 'plan': plan})
    g = c.load_level(0, plan[0])
    check('cache_round_trip_exact', c.complete() and isinstance(g, F.Fields) and np.array_equal(g['h'], f['h']) and
          g.level is plan[0])
    CA.Cache('0' * 40, base).save_level(0, f)
    freed = CA.prune(keep_gb=0.0, base=base)
    check('cache_prune', freed > 0 and not os.listdir(base), freed)
    check('cache_code_hash', len(CA.code_hash()) == 40)
    shutil.rmtree(base, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ compose ---

def test_compose():
    a, b = np.linspace(-5, 5, 101), np.zeros(101)
    sm = C.smooth_min(a, b, 2.0)
    check('compose_smooth_min_below_min_and_c1', bool(np.all(sm <= np.minimum(a, b) + 1e-12)) and
          float(np.abs(np.diff(np.diff(sm))).max()) < 0.05)
    h = np.zeros(5)
    s = np.array([-1.0, 0.0, 1.0, 2.0, 3.0])
    check('compose_stamp_modes', np.allclose(C.stamp(h, s, 'max'), [0, 0, 1, 2, 3]) and
          np.allclose(C.stamp(h, s, 'min'), [-1, 0, 0, 0, 0]) and np.allclose(C.stamp(h, s, 'add'), s) and
          np.allclose(C.stamp(h, s, 'blend', mask=np.full(5, 0.5)), s / 2) and
          raises(lambda: C.stamp(h, s, 'mix'), ValueError) is not None)
    H, R, up = 3700.0, 18000.0, 33.0
    lam = H / math.tan(math.radians(up))
    spec = {'kind': 'cone', 'centre': [0, 0], 'radius_m': R, 'height_m': H, 'profile': 'exp', 'lambda_m': lam}
    r = np.array([0.0, 10000.0, 15000.0])
    d = 0.01
    slope = np.degrees(np.arctan((C.shape(spec, r, 0 * r) - C.shape(spec, r + d, 0 * r)) / d))
    # design 4.7's profile: tan(theta) = (H / lambda) e^(-r / lambda) / (1 - e^(-R / lambda)). The design quotes
    # 33 / 6.6 / 2.8 deg from the numerator alone; the normalising denominator (1 - e^-3.16 = 0.958) lifts them to
    # 34.1 / 6.7 / 2.8
    den = 1.0 - math.exp(-R / lam)
    want = [math.degrees(math.atan(H / lam * math.exp(-rr / lam) / den)) for rr in r]
    check('compose_stratovolcano_slopes', np.allclose(slope, want, atol=0.02),
          {'got': slope.round(3).tolist(), 'formula': np.round(want, 3).tolist()})
    x, y = G.cell_centres(-100, -100, 1.0, 200)
    hh = (0.3 * x + 0.1 * y).astype(np.float32)
    areas = [{'at': (10.0, -5.0), 'radius': 15.0, 'falloff': 10.0, 'height': None}]
    lv = L.Level(0, 'main', -100.0, -100.0, 200.0, 1.0, 200)
    zz = C.resolve_flat_heights(areas, [(lv, hh)])
    out = C.flatten_exact(hh, x, y, areas, zz)
    rr = np.hypot(x - 10, y + 5)
    check('compose_flatten_exact', np.allclose(out[rr <= 15], zz[0], atol=1e-4) and
          np.array_equal(out[rr >= 25.01], hh[rr >= 25.01]) and abs(zz[0] - (0.3 * 10 - 0.1 * 5)) < 0.3, zz)
    # C1: along a line through the falloff band, the largest second difference shrinks with the spacing squared
    # (a kink would make it shrink only linearly)
    def d2max(step):
        xs = np.arange(-30.0, 50.0, step) + 0.123
        ys = np.full_like(xs, -5.0)
        z = C.flatten_exact(0.3 * xs + 0.1 * ys, xs, ys, areas, zz).astype(np.float64)
        return float(np.abs(np.diff(z, 2)).max())
    r1, r2 = d2max(0.04), d2max(0.01)
    check('compose_flatten_c1', r2 / r1 < 0.12, {'second diff at 4 cm': r1, 'at 1 cm': r2, 'ratio': r2 / r1})
    check('compose_flatten_mask', C.flatten_mask(areas, x, y)[rr <= 25].min() == 1.0 and
          C.flatten_mask(areas, x, y)[rr > 25.5].max() == 0.0)
    # no creases: on a window across each shape's flank, the largest 5-point Laplacian shrinks with the cell size
    # squared (C1 or smoother); a crease (a kink) would shrink it only linearly
    ratios, vmax = {}, 0.0
    for kind, sp in (('dome', {'kind': 'dome', 'radius_m': 6000}),
                     ('ridge', {'kind': 'ridge', 'azimuth_deg': 30, 'length_m': 12000, 'width_m': 5000, 'spurs': 6}),
                     ('plateau', {'kind': 'plateau', 'radius_m': 5000, 'edge_m': 1500}),
                     ('massif', {'kind': 'massif', 'radius_m': 6000, 'peaks': 5})):
        laps = []
        for cell in (8.0, 2.0):
            X, Y = G.cell_centres(-1500, -1000, cell, int(round(400 / cell)))
            u = C.uplift(sp, X, Y, seed=3)
            laps.append(float(np.abs(u[1:-1, 2:] + u[1:-1, :-2] + u[2:, 1:-1] + u[:-2, 1:-1] - 4 * u[1:-1, 1:-1])
                              .max()))
        ratios[kind] = laps[1] / max(laps[0], 1e-30)
        X, Y = G.cell_centres(-8000, -8000, 125.0, 128)
        u = C.uplift(sp, X, Y, seed=3)
        vmax = max(vmax, float(u.max()))
        RESULTS[f'uplift_{kind}_range'] = [float(u.min()), float(u.max())]
    check('compose_uplift_no_creases', all(v < 0.12 for v in ratios.values()) and vmax < 2.0,
          {'laplacian ratio 2 m / 8 m (1/16 smooth, 1/4 a crease)': ratios, 'max': vmax})
    h0 = C.start_surface({'kind': 'ridge', 'length_m': 12000, 'width_m': 5000}, X, Y, seed=2, height_m=600.0)
    check('compose_start_surface', 0.0 <= float(h0.min()) and 300.0 < float(h0.max()) < 1000.0,
          [float(h0.min()), float(h0.max())])


# --------------------------------------------------------------------------------------------------- grid ---

def test_grid():
    x, y = G.cell_centres(10.0, -20.0, 2.0, (24, 30))
    lin = 3.0 * x - 2.0 * y + 7.0
    up_c = G.upsample2(lin, 'catmull')
    up_b = G.upsample2(lin, 'bilinear')
    x2, y2 = G.cell_centres(10.0, -20.0, 1.0, (48, 60))
    want = 3.0 * x2 - 2.0 * y2 + 7.0
    inner = (slice(4, -4), slice(4, -4))
    check('grid_upsample_linear_exact', np.allclose(up_c[inner], want[inner], atol=1e-4) and
          np.allclose(up_b[inner], want[inner], atol=1e-4))
    crop = G.crop_upsample2(lin, 6, 4, 10, 'catmull', mj=8)
    check('grid_crop_upsample_equals_full', np.allclose(crop, up_c[8:24, 12:32], atol=1e-5))
    w = G.border_ramp(64, 16)
    check('grid_border_ramp', w[0, 30] == 1.0 and w[16, 30] == 0.0 and w[32, 32] == 0.0 and 0 < w[8, 30] < 1)
    plane_e = 0.5 * x                                              # rises east: faces west
    plane_n = 0.5 * y                                              # rises north: faces south
    check('grid_slope_aspect_conventions', np.allclose(G.slope_deg(plane_e, 2.0), math.degrees(math.atan(0.5))) and
          np.allclose(G.aspect_deg(plane_e, 2.0), 270.0) and np.allclose(G.aspect_deg(plane_n, 2.0), 180.0))
    check('grid_from_north_up', np.array_equal(G.from_north_up(np.arange(6).reshape(3, 2)), [[4, 5], [2, 3], [0, 1]]))


def main():
    t0 = time.perf_counter()
    for fn in (test_levels, test_fields, test_expr, test_recipe, test_noise, test_io, test_cache, test_compose,
               test_grid):
        t = time.perf_counter()
        try:
            fn()
        except Exception:                                          # noqa: BLE001
            check(fn.__name__ + '_ran', False, traceback.format_exc()[-2000:])
        print(f'  ({fn.__name__}: {time.perf_counter() - t:.1f} s)', flush=True)
    RESULTS['failed'] = FAILED
    RESULTS['seconds'] = round(time.perf_counter() - t0, 1)
    with open(os.path.join(OUT, 'core_tests.json'), 'w', encoding='utf-8') as f:
        json.dump(RESULTS, f, indent=1, default=str)
    print(f"[core] {'ALL PASS' if not FAILED else 'FAILED: ' + ', '.join(FAILED)} in {RESULTS['seconds']} s")
    sys.exit(1 if FAILED else 0)


if __name__ == '__main__':
    main()
