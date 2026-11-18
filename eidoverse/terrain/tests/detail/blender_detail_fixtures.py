"""The detail package's function fixtures (PORT_PLAN.md 5.1, 8.2 row P12): the Blender edition's numpy code of
solvers/hydraulic.py and solvers/detail.py that becomes GPU code in the port, run on recorded inputs with every output
kept, each case with its own floor; and the inputs and twin results of the Blender detail tests the port's tests
repeat. numpy only: no Blender, no GPU (the twins run where the Blender ops would use the GPU: backend='numpy').

    <Blender's python> -I eidoverse/terrain/tests/detail/blender_detail_fixtures.py [--out <dir>] [--only a,b]
        [--patterns 5]

Run it with Blender's own Python (tests/_where.mjs blenderPython(): Python 3.13, numpy 2.3.4), never the system's
(plan C6); the manifest records the versions. The Blender edition is found as tests/parity/_blender.py finds it
($EIDO_BLENDER_EDITION, or blender/ in this checkout) and is only read. Writes, in tests/parity/fixtures.py's format
(its Store and FunctionRecorder, imported), <parity outputs>/<Blender key>/fixtures/functions/detail/.

The floor of a case (values.floor: {output: the largest max |d| / range}). The chaos floor's protocol (plan C1, 5.4)
applied to one call: the function run again five times with every float32 input moved by one ulp on half the cells
(+1 on a quarter, -1 on a quarter: tests/parity/_hooks.py nudge, default_rng([pattern, case, 17])) and, where it
evaluates world noise, that noise rounded to float32 and nudged the same way (the port evaluates it in float32 on the
GPU, as Blender's field_gpu does; this oracle's is numpy's float64 field()). The largest change of each output over
the five is what Blender's own code does under differences of a correct port's size; tests/detail/functions_test.mjs
grades each output at max(the plan's grade, 1.25 x its floor), as the plan grades a stage replay (5.3).

The groups (--only):
  hydraulic   rockness, anchor and anchor_scale_m, micro_relief (numpy's field()), finish, and op_hydraulic on two
              hillsides (a level with a parent and the border ramp, one without; with and without bed, kfac and
              rock_fail; 1, 20 and 150 steps; full and random rain; the runner's pins in a context)
  model       the inputs of the Blender GPU test's conservation runs (128^2, closed and periodic edges) and its
              300-step run against the twins (64^2): the twins' own result and the numbers the Blender test compares
  breakup     breakup_terms and breakup_uniforms (four parameter sets, five cells, 40 km from the origin, bedding on and
              off), strength through the twin (bedding resolved at 0.25 m cells), relax (1, 10 and 100 passes), and
              op_breakup in its three threshold modes
  gully       phacelle_noise 40 km from the origin, flow_direction (smoothed surface and a given flow), gully_relief
              and op_gully
  planation   op_planation (the datum from the 15th percentile with tilt, and a given datum)
A case is {label, group, function, args, inputs, outputs, values}: an op's inputs are its fields before (f__<name>)
and its pins (pin__<name>), its outputs the fields after; arrays row 0 south, float32 as the Fields hold them.
"""
from __future__ import annotations

import math
import os
import sys
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'parity'))
import _blender as B  # noqa: E402
import fixtures as FX  # noqa: E402
from _hooks import nudge  # noqa: E402

import numpy as np  # noqa: E402

F = np.float32
GROUPS = ('hydraulic', 'model', 'breakup', 'gully', 'planation')
STATE = dict(case=0, patterns=5, noise_rng=None)


def level(index, role, x0, y0, cell, n, parent=None, depth=0):
    from eidoblend.terrain.core.levels import Level
    return Level(index, role, float(x0), float(y0), n * float(cell), float(cell), int(n), parent=parent, depth=depth)


def install_noise_nudge():
    """While STATE['noise_rng'] is set, numpy's world noise comes back rounded to float32 and nudged by one ulp on
    half the cells (the floor's second perturbation point: what float32 noise is to the float64 oracle)."""
    from eidoblend.terrain.core import world_noise as N
    if getattr(N.field, '_detail_nudge', False):
        return
    orig = N.field

    def field(spec, x, y, seed=0):
        v = orig(spec, x, y, seed)
        if STATE['noise_rng'] is not None:
            v = nudge(np.asarray(v, F), STATE['noise_rng']).astype(np.float64)
        return v
    field._detail_nudge = True
    N.field = field


def span(a):
    a = np.asarray(a, np.float64)
    fin = a[np.isfinite(a)]
    if not fin.size:
        return 1.0
    return float(np.ptp(fin)) or float(np.max(np.abs(fin))) or 1.0


def floored(rec, label, fn_name, args, inputs, compute, values=None):
    """Record a case: compute(inputs) -> {output: array}, then its floor over STATE['patterns'] perturbed runs."""
    STATE['case'] += 1
    t0 = time.perf_counter()
    out0 = {k: np.array(v) for k, v in compute({k: np.array(v) for k, v in inputs.items() if v is not None}).items()}
    sec = time.perf_counter() - t0
    floor = {k: 0.0 for k in out0}
    for p in range(1, STATE['patterns'] + 1):
        rng = np.random.default_rng([p, STATE['case'], 17])
        inp = {}
        for k in sorted(inputs):
            v = inputs[k]
            if v is None:
                continue
            v = np.asarray(v)
            inp[k] = nudge(v, rng) if v.dtype == F and v.ndim >= 2 else np.array(v)
        STATE['noise_rng'] = np.random.default_rng([p, STATE['case'], 29])
        try:
            outp = compute(inp)
        finally:
            STATE['noise_rng'] = None
        for k, a in out0.items():
            b = np.asarray(outp[k], np.float64)
            a64 = np.asarray(a, np.float64)
            fin = np.isfinite(a64) & np.isfinite(b)
            d = float(np.max(np.abs(b[fin] - a64[fin]))) if fin.any() else 0.0
            floor[k] = max(floor[k], d / span(a))
    rec.case(label, fn_name, args, inputs, out0, values=dict(values or {}, floor=floor, seconds=round(sec, 3),
                                                              patterns=STATE['patterns']))
    print(f'[detail fixtures] {label}: {sec:.2f} s; floor ' +
          ', '.join(f'{k} {v:.1e}' for k, v in floor.items()), flush=True)


def fields_of(lv, arrays):
    from eidoblend.terrain.core.fields import Fields
    return Fields(lv, {k: np.asarray(v) for k, v in arrays.items()})


def op_case(rec, label, fn_name, fn, lv, arrays, params, seed, pins=None, **kw):
    """A Blender op on Fields made of `arrays` (and a context holding `pins`): before and after, with its floor."""
    inputs = {f'f__{k}': np.asarray(v, F) for k, v in arrays.items()}
    if pins is not None:
        inputs.update({f'pin__{k}': np.asarray(v, F) for k, v in pins.items()})

    def compute(inp):
        f = fields_of(lv, {k[3:]: v for k, v in inp.items() if k.startswith('f__')})
        ctx = None
        if pins is not None:
            ctx = types.SimpleNamespace(pins={k[5:]: v for k, v in inp.items() if k.startswith('pin__')}, log=None,
                                        device=None)
        fn(f, lv, dict(params), seed, log=lambda m: None, ctx=ctx, **kw)
        return {f'f__{k}': np.array(v) for k, v in f.items()}
    floored(rec, label, fn_name, dict(level=lv.to_dict(), params=params, seed=seed, ctx_pins=pins is not None, **kw),
            inputs, compute)


def hillside(n, seed=3, base=500.0):
    """The Blender detail twin test's hillside (test_detail_twins.hillside): cell units, a slope rising north over the
    southern 60 % with bumps, a flat plain below it."""
    from eidoblend.terrain.core import twins as T
    jj, ii = np.mgrid[0:n, 0:n].astype(np.float64)
    rise = np.clip(jj - 0.35 * n, 0.0, None) * 0.55
    b = base + rise + 1.5 * np.sin(ii / n * 7.0) * (rise > 0) + T.random_field((n, n), 0.0, 0.6, seed, smooth=2)
    return b.astype(F)


def slope_terrain(n, seed=3, base=500.0):
    """The Blender detail GPU test's slope (test_detail_gpu.slope_terrain), cell units."""
    from eidoblend.terrain.core import twins as T
    jj, ii = np.mgrid[0:n, 0:n].astype(np.float64)
    b = base + 0.45 * jj + 3.0 * np.sin(ii / n * 6.0) + T.random_field((n, n), 0.0, 2.0, seed, smooth=3)
    return b.astype(F)


# ------------------------------------------------------------------------------------------------- hydraulic ---

def hydraulic_cases(rec):
    from eidoblend.terrain.core import twins as T
    from eidoblend.terrain.core import grid as GR
    from eidoblend.terrain.solvers import hydraulic as HY
    for cell, sl in ((1.0, (35.0, 50.0)), (4.0, (20.0, 30.0))):
        h = T.random_field((80, 96), 0.0, 300.0, 21, smooth=2)
        floored(rec, f'rockness cell {cell} slope {sl}', 'hydraulic.rockness', dict(cell=cell, slope_deg=list(sl)),
                dict(h=h), lambda i, cell=cell, sl=sl: dict(rk=HY.rockness(i['h'], cell, sl)))
    jj, ii = np.mgrid[0:96, 0:112].astype(np.float64)
    change = (T.random_field((96, 112), -0.5, 0.5, 23, smooth=1).astype(np.float64)
              - 0.6 * np.exp(-((ii - 40.3) / 0.8) ** 2) + 2.0 * np.exp(-(((ii - 80) / 14.0) ** 2 + ((jj - 50) / 14.0) ** 2)))
    for scale in (3.0, 6.0, 12.0, 24.0, 2.4):
        floored(rec, f'anchor scale {scale} cells', 'hydraulic.anchor', dict(scale_cells=scale), dict(change=change.astype(F)),
                lambda i, scale=scale: dict(a=HY.anchor(i['change'].astype(np.float64), scale)))
    lvs = [level(5, 'hero', 0.0, 0.0, 1.0, 64, parent=4, depth=-3), level(3, 'hero', 0.0, 0.0, 4.0, 64, parent=2, depth=-1),
           level(2, 'main', 0.0, 0.0, 8.0, 64, parent=1, depth=0), level(0, 'context', 0.0, 0.0, 30.0, 64, depth=2)]
    rec.case('anchor_scale_m', 'hydraulic.anchor_scale_m', dict(levels=[lv.to_dict() for lv in lvs]), {}, {},
             values=dict(scales=[HY.anchor_scale_m(lv) for lv in lvs], given=HY.anchor_scale_m(lvs[0], 20.0)))
    for cell in (0.5, 4.0):
        lv = level(4, 'hero', 40123.0, -25311.0, cell, 96, parent=3, depth=-2)
        floored(rec, f'micro_relief cell {cell} 40 km out', 'hydraulic.micro_relief',
                dict(level=lv.to_dict(), seed=7002, amp_m=0.12 * cell, wavelength_m=3.0 * cell), {},
                lambda i, lv=lv, cell=cell: dict(r=HY.micro_relief(lv, 1 + 7001, 0.12 * cell, 3.0 * cell, backend='numpy')))
    # finish: the blend to the pins, the anchor, the record fields (on a hero level, and on a coarsest level)
    n = 96
    rng = np.random.default_rng(31)
    h_in = (T.random_field((n, n), 0.0, 900.0, 32, smooth=3).astype(np.float64) + 1200.0).astype(F)
    bump = T.random_field((n, n), -0.06, 0.06, 33).astype(F)
    dH = T.random_field((n, n), -0.4, 0.3, 34, smooth=1).astype(F)
    dB = (dH - T.random_field((n, n), 0.0, 0.3, 35)).astype(F)
    pw = GR.border_ramp(n, 16)
    ph = (h_in + rng.uniform(-0.2, 0.2, (n, n))).astype(F)
    tal = T.random_field((n, n), 0.0, 0.2, 36).astype(F)
    wet = T.random_field((n, n), 0.0, 0.01, 37).astype(F)
    olds = dict(wear=T.random_field((n, n), 0.0, 1.0, 38), deposit=T.random_field((n, n), 0.0, 1.0, 39),
                talus=T.random_field((n, n), 0.0, 0.5, 40))
    for tag, lv, anchor_m, seed_k, pins, with_old in (
            ('hero, anchor 12 m, seed kept 0.6, pins', level(5, 'hero', 0.0, 0.0, 1.0, n, parent=4, depth=-3), 12.0, 0.6, True, True),
            ('main, no anchor, no seed, pins', level(2, 'main', 0.0, 0.0, 8.0, n, parent=1), None, 0.0, True, False),
            ('coarsest, anchor given but no parent, no pins', level(0, 'context', 0.0, 0.0, 30.0, n), 90.0, 1.0, False, True)):
        inputs = dict(h_in=h_in, bump=bump, dH=dH, dB=dB, pw=pw if pins else None, ph=ph if pins else None, talus=tal,
                      wet=wet, **({f'old_{k}': v for k, v in olds.items()} if with_old else {}))

        def compute(i, lv=lv, anchor_m=anchor_m, seed_k=seed_k, pins=pins):
            h_base = i['h_in'].astype(np.float64) + seed_k * i['bump'].astype(np.float64)
            h_new = h_base + i['dH'].astype(np.float64)
            bed_new = h_base + i['dB'].astype(np.float64)
            f = fields_of(lv, dict(h=i['h_in'], **{k[4:]: v for k, v in i.items() if k.startswith('old_')}))
            w, hh = (i['pw'], i['ph']) if pins else (np.zeros((n, n)), i['h_in'])
            HY.finish(f, h_new, bed_new, h_base, np.asarray(w, np.float64), np.asarray(hh, np.float64),
                      talus=i['talus'].astype(np.float64), wet=i['wet'].astype(np.float64), level=lv, anchor_m=anchor_m)
            return {k: np.array(v) for k, v in f.items()}
        floored(rec, f'finish {tag}', 'hydraulic.finish', dict(level=lv.to_dict(), anchor_m=anchor_m, seed_k=seed_k, pins=pins),
                inputs, compute)
    # the op itself, through the twins: hillsides in metres on a hero level (border ramp, no ctx) and a coarsest one
    for tag, n, cell, extra, params, seed, parent in (
            ('hero 96 1 m, 1 step', 96, 1.0, (), {'steps': 1}, 3, 4),
            ('hero 96 1 m, 20 steps', 96, 1.0, (), {'steps': 20}, 3, 4),
            ('hero 96 1 m, 150 steps', 96, 1.0, (), {'steps': 150}, 3, 4),
            ('hero 64 0.5 m, bed and kfac, 20 steps, random rain', 64, 0.5, ('bed', 'kfac'), {'steps': 20, 'rain_cover': 0.5}, 5, 4),
            ('coarsest 64 4 m, rock_fail with Sc and bed, 20 steps', 64, 4.0, ('bed', 'Sc'), {'steps': 20, 'rock_fail': True}, 2, None),
            ('hero 64 2 m, no roughness, no anchor, 20 steps', 64, 2.0, (), {'steps': 20, 'roughness': 0.0, 'anchor': False}, 1, 3)):
        lv = level(5 if parent else 0, 'hero' if parent else 'context', 3000.0, -800.0, cell, n, parent=parent,
                   depth=-2 if parent else 1)
        h = hillside(n, seed=5, base=0.0).astype(np.float64) * cell + 1200.0
        arrays = dict(h=h.astype(F), wear=np.zeros((n, n), F))
        if 'bed' in extra:
            arrays['bed'] = (h - T.random_field((n, n), 0.0, 0.4 * cell, 41)).astype(F)
        if 'kfac' in extra:
            arrays['kfac'] = T.random_field((n, n), 0.6, 1.6, 42)
        if 'Sc' in extra:
            arrays['Sc'] = T.random_field((n, n), 0.4, 1.2, 43)
        op_case(rec, f'op_hydraulic {tag}', 'hydraulic.op_hydraulic', HY.op_hydraulic, lv, arrays, params, seed,
                backend='numpy')
    # with the runner's pins in a context (a band of its own, and a partly pinned disc)
    n, cell = 64, 1.0
    lv = level(5, 'hero', 3000.0, -800.0, cell, n, parent=4, depth=-2)
    h = (hillside(n, seed=6, base=0.0).astype(np.float64) * cell + 900.0).astype(F)
    pw2, ph2 = T.pin_pattern((n, n), 4, band=8, value=(0.0, 1.0))
    op_case(rec, 'op_hydraulic hero 64 1 m, context pins, 20 steps', 'hydraulic.op_hydraulic', HY.op_hydraulic, lv,
            dict(h=h), {'steps': 20}, 4, pins=dict(pin_w=pw2, pin_h=(h + ph2).astype(F)), backend='numpy')


def model_cases(rec):
    """The Blender GPU test's model runs (blender/tests/terrain/detail/test_detail_gpu.py): conservation inputs and
    the 300-step run against the twins."""
    from eidoblend.terrain.core import twins as T
    from eidoblend.terrain.solvers import hydraulic as HY
    n = 128
    closed = slope_terrain(n)
    periodic = (500.0 + T.random_field((n, n), 0.0, 30.0, 5, smooth=3)).astype(F)
    rec.case('conservation inputs (test_detail_gpu.test_conservation)', 'model.conservation',
             dict(steps=3000, every=100, seed=7, params={'rain_cover': 1.0}, erodibility=0.5, repose_tan=0.7),
             dict(closed=closed, periodic=periodic), {})
    n = 64
    b = slope_terrain(n, 9)
    p = HY.defaults({'roughness': 0.0})
    shape = b.shape
    src = T.rgba(np.ones(shape, F), None, np.full(shape, 0.5, F))
    par = T.rgba(np.full(shape, HY.BIG_TAN, F), np.full(shape, 0.7, F))
    pin = np.zeros(shape + (4,), F)
    t0 = time.perf_counter()
    rec_steps = []
    tw, ta = HY.run_numpy(b, b.copy(), src, par, pin, p, seed=7, mode=T.BOUND_OPEN, outflow=True, steps=300,
                          record=rec_steps)
    dh = tw[..., 0]
    totals = dict(wear_p99=float(np.percentile(-dh, 99)), water=float(tw[..., 1].sum()),
                  eroded=float(np.maximum(-dh, 0).sum()), deposited=float(np.maximum(dh, 0).sum()))
    rec.case('300 steps of the twins (test_detail_gpu.test_multistep_vs_twins)', 'model.run_numpy',
             dict(steps=300, seed=7, mode=0, outflow=True, params={'roughness': 0.0}, erodibility=0.5, repose_tan=0.7),
             dict(b=b), dict(state=tw, tacc=ta),
             values=dict(totals=totals, mass_first=rec_steps[0][2], mass_last=rec_steps[-1][2],
                         seconds=round(time.perf_counter() - t0, 2)))
    print(f'[detail fixtures] run_numpy 300 steps: {time.perf_counter() - t0:.1f} s', flush=True)


# --------------------------------------------------------------------------------------------------- breakup ---

PARAM_SETS = (
    ('default', {}),
    ('fluvial_range', {'rock_slope_deg': [28.0, 40.0], 'relief': 0.3,
                       'joints': [{'strike_deg': 15.0, 'spacing_m': 45.0, 'width_m': 9.0, 'stretch': 2.5, 'strength': 0.9,
                                   'depth_m': 3.5},
                                  {'strike_deg': 105.0, 'spacing_m': 60.0, 'width_m': 7.0, 'stretch': 2.0, 'strength': 0.7,
                                   'depth_m': 2.5}]}),
    ('alpine_valley scales', {'relief': 0.6, 'scales_m': [60.0, 20.0, 7.0]}),
    ('bedding', {'bedding': {'spacing_m': 6.0, 'width_m': 2.0, 'strength': 0.6, 'depth_m': 0.8, 'dip_deg': 3.0,
                             'azimuth_deg': 30.0}}),
)


def breakup_cases(rec):
    from eidoblend.terrain.core import twins as T
    from eidoblend.terrain.solvers import detail as DT
    for pname, pp in PARAM_SETS:
        p = DT._params(DT.BREAKUP, pp, 'breakup')
        for cell in (0.25, 0.5, 2.0, 4.0, 16.0):
            for seed in (1, 5):
                lv = level(3, 'hero', 40123.0, -25311.0, cell, 96, parent=2, depth=-1)
                terms, nt, bu = DT.breakup_terms(p, lv, seed)
                u = DT.breakup_uniforms(p, lv, nt, bu)
                rec.case(f'breakup_terms {pname} cell {cell} seed {seed}', 'detail.breakup_terms',
                         dict(params=pp, level=lv.to_dict(), seed=seed), {}, dict(terms=terms),
                         values=dict(n_terms=nt, uniforms=u))
    h = T.random_field((96, 96), 0.0, 300.0, 41, smooth=2)
    for pname, pp, cell, seed in (('default', {}, 0.5, 5), ('default', {}, 4.0, 5), ('bedding', PARAM_SETS[3][1], 0.25, 2),
                                  ('fluvial_range', PARAM_SETS[1][1], 2.0, 1)):
        p = DT._params(DT.BREAKUP, pp, 'breakup')
        lv = level(3, 'hero', 40123.0, -25311.0, cell, 96, parent=2, depth=-1)

        def compute(i, p=p, lv=lv, seed=seed):
            R, kf, sc, D = DT.strength(p, lv, i['h'], seed, backend='numpy')
            return dict(R=R, kfac=kf, sc_abs=sc, D=D)
        floored(rec, f'strength {pname} cell {cell}', 'detail.strength', dict(params=pp, level=lv.to_dict(), seed=seed),
                dict(h=h), compute)
    # relax: a debris cone and a rock step on a cohesive base, in cell units
    n = 48
    jj, ii = np.mgrid[0:n, 0:n].astype(np.float64)
    cone = np.maximum(8.0 - 0.5 * np.hypot(ii - 20, jj - 24), 0.0) * 2.0
    step = np.where(ii > 30, 12.0, 0.0)
    b0 = (300.0 + cone + step).astype(F)
    bed = (300.0 + step).astype(F)
    sc = np.where(ii > 28, math.tan(math.radians(60.0)), 1e3).astype(F)
    for iters in (1, 10, 100):
        def compute(i, iters=iters):
            dl, bed_rel, net = DT.relax(i['b0'], i['bed'], i['sc'], math.tan(math.radians(35.0)), iters, 0.06,
                                        backend='numpy', floor=-2.0)
            return dict(dl=dl, bed_rel=bed_rel, net=net)
        floored(rec, f'relax {iters} passes', 'detail.relax', dict(iterations=iters, rate=0.06, repose_deg=35.0, floor=-2.0),
                dict(b0=b0, bed=bed, sc=sc), compute)
    # the op, through the twins: its three threshold modes, with and without bed, K and Sc
    n = 96
    hb = (T.random_field((n, n), 0.0, 220.0, 44, smooth=2).astype(np.float64) + 800.0)
    for tag, pp, extra, seed, cell, parent in (
            ('relative, 2 m hero', {}, (), 1, 2.0, 2),
            ('field (Sc), bed and K, 4 m hero, 60 passes', {'iterations': 60}, ('Sc', 'bed', 'K'), 2, 4.0, 2),
            ('absolute, 1 m hero, no anchor, 60 passes', {'threshold': 'absolute', 'iterations': 60, 'anchor': False}, ('bed',), 3, 1.0, 2),
            ('relative, fluvial_range joints, main level 8 m (no parent), 60 passes',
             dict(PARAM_SETS[1][1], iterations=60), (), 1, 8.0, None)):
        lv = level(4 if parent else 0, 'hero' if parent else 'main', -260.0, 1380.0, cell, n, parent=parent,
                   depth=-1 if parent else 0)
        arrays = dict(h=hb.astype(F), talus=np.zeros((n, n), F))
        if 'bed' in extra:
            arrays['bed'] = (hb - T.random_field((n, n), 0.0, 1.5, 45)).astype(F)
        if 'Sc' in extra:
            arrays['Sc'] = T.random_field((n, n), 0.6, 1.4, 46)
        if 'K' in extra:
            arrays['K'] = T.random_field((n, n), 1e-6, 4e-6, 47)
        op_case(rec, f'op_breakup {tag}', 'detail.op_breakup', DT.op_breakup, lv, arrays, pp, seed, backend='numpy')


# ----------------------------------------------------------------------------------------------------- gully ---

def gully_cases(rec):
    from eidoblend.terrain.core import twins as T
    from eidoblend.terrain.core import world_noise as N
    from eidoblend.terrain.solvers import detail as DT
    n = 96
    lv = level(4, 'hero', 40123.0, -25311.0, 1.0, n, parent=3, depth=-2)
    X, Y = lv.xy()
    h = T.random_field((n, n), 0.0, 60.0, 51, smooth=3).astype(np.float64)
    dx, dy = DT.flow_direction(h, 1.0, 12.0)
    for o, lam in enumerate((12.0, 6.0)):
        ox, oy = N.lattice_offset(1 + 4242, o)

        def compute(i, lam=lam, ox=ox, oy=oy):
            c, sn, sdx, sdy = DT.phacelle_noise(X / lam, Y / lam, i['dx'].astype(np.float64), i['dy'].astype(np.float64),
                                                1.0, 0.25, 0.5, (ox, oy))
            return dict(c=c, s=sn, sdx=sdx, sdy=sdy)
        floored(rec, f'phacelle_noise 40 km out, wavelength {lam} m', 'detail.phacelle_noise',
                dict(level=lv.to_dict(), wavelength_m=lam, freq=1.0, offset=0.25, normalization=0.5,
                     lattice_offset=[int(ox), int(oy)]),
                dict(dx=dx.astype(F), dy=dy.astype(F)), compute)
    for smooth_m in (12.0, 5.0, 1.0):
        def compute(i, smooth_m=smooth_m):
            fx, fy = DT.flow_direction(i['h'].astype(np.float64), 1.0, smooth_m)
            return dict(dx=fx, dy=fy)
        floored(rec, f'flow_direction smoothed {smooth_m} m', 'detail.flow_direction', dict(cell=1.0, smooth_m=smooth_m),
                dict(h=h.astype(F)), compute)
    flow = (T.random_field((n, n), -1.0, 1.0, 52, smooth=2), T.random_field((n, n), -1.0, 1.0, 53, smooth=2))

    def compute_flow(i):
        fx, fy = DT.flow_direction(i['h'].astype(np.float64), 1.0, 12.0, flow=(i['flow_x'], i['flow_y']))
        return dict(dx=fx, dy=fy)
    floored(rec, 'flow_direction of a given flow', 'detail.flow_direction', dict(cell=1.0, smooth_m=12.0, flow=True),
            dict(h=h.astype(F), flow_x=flow[0], flow_y=flow[1]), compute_flow)
    for tag, pp, cell, use_flow in (('3 octaves, 1 m', {}, 1.0, False), ('3 octaves, 0.5 m, given flow', {}, 0.5, True),
                                    ('2 octaves, wavelength 20 m, amp 1 m, 2 m', {'octaves': 2, 'wavelength_m': 20.0, 'amp_m': 1.0}, 2.0, False)):
        lvg = level(4, 'hero', 40123.0, -25311.0, cell, n, parent=3, depth=-2)
        hg = (T.random_field((n, n), 0.0, 40.0 * cell, 54, smooth=3).astype(np.float64)
              + 0.45 * cell * np.mgrid[0:n, 0:n][0])
        p = DT._params(DT.GULLY, pp, 'gully')

        def compute(i, lvg=lvg, p=p, use_flow=use_flow):
            g, mask = DT.gully_relief(lvg, i['h'].astype(np.float64), p, 7,
                                      flow=(i['flow_x'], i['flow_y']) if use_flow else None)
            return dict(g=g, mask=mask)
        floored(rec, f'gully_relief {tag}', 'detail.gully_relief', dict(level=lvg.to_dict(), params=pp, seed=7, flow=use_flow),
                dict(h=hg.astype(F), **(dict(flow_x=flow[0], flow_y=flow[1]) if use_flow else {})), compute)
        arrays = dict(h=(hg + 300.0).astype(F))
        if use_flow:
            arrays.update(flow_x=flow[0], flow_y=flow[1], bed=(hg + 299.0).astype(F))
        op_case(rec, f'op_gully {tag}', 'detail.op_gully', DT.op_gully, lvg, arrays, pp, 7)


# ------------------------------------------------------------------------------------------------- planation ---

def planation_cases(rec):
    from eidoblend.terrain.core import twins as T
    from eidoblend.terrain.solvers import detail as DT
    n, cell = 128, 20.0
    for tag, pp, parent in (('datum from the 15th percentile, tilt 0.8 deg toward 30 deg, a child level',
                             {'tilt_deg': 0.8, 'azimuth_deg': 30.0}, 1),
                            ('datum 150 m, no tilt, the coarsest level (twin test)', {'datum_m': 150.0, 'tilt_deg': 0.0}, None)):
        lv = level(2 if parent else 0, 'main', -1280.0, -1280.0, cell, n, parent=parent)
        h = T.random_field((n, n), 0.0, 300.0, 4, smooth=3).astype(np.float64) + 100.0
        op_case(rec, f'op_planation {tag}', 'detail.op_planation', DT.op_planation, lv,
                dict(h=h.astype(F), bed=(h - 2.0).astype(F)), pp, 2, backend='numpy')


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out', default='')
    ap.add_argument('--only', default='')
    ap.add_argument('--patterns', type=int, default=5)
    a = ap.parse_args(B.script_args())
    only = {x for x in a.only.split(',') if x} or set(GROUPS)
    STATE['patterns'] = a.patterns
    edition = B.bare_terrain_package()
    install_noise_nudge()
    key = B.source_key(edition)
    out = os.path.abspath(a.out) if a.out else os.path.join(B.parity_root(), key['folder'], 'fixtures', 'functions', 'detail')
    store = FX.Store(out, 'functions/detail', key)
    v = B.versions()
    print(f"[detail fixtures] Blender edition {key['commit'][:7]} (field hash {key['field_hash'][:10]}), Python "
          f"{v['python']}, numpy {v['numpy']} -> {out}", flush=True)
    t0 = time.perf_counter()
    groups = []
    for g, fn in (('hydraulic', hydraulic_cases), ('model', model_cases), ('breakup', breakup_cases),
                  ('gully', gully_cases), ('planation', planation_cases)):
        if g not in only:
            continue
        rec = FX.FunctionRecorder(store, g)
        t1 = time.perf_counter()
        fn(rec)
        groups.append(dict(group=g, seconds=round(time.perf_counter() - t1, 2)))
    man = store.finish(groups=groups, made_by='tests/detail/blender_detail_fixtures.py', patterns=STATE['patterns'],
                       floor='every float32 input and the world noise moved by one float32 ulp on half the cells '
                             '(tests/parity/_hooks.py nudge), five patterns: values.floor per output, the largest '
                             'max |d| / range')
    print(f"[detail fixtures] {len(man['cases'])} cases, {man['arrays']} arrays, {man['bytes'] / 1e6:.1f} MB in "
          f"{time.perf_counter() - t0:.1f} s", flush=True)


if __name__ == '__main__':
    main()
