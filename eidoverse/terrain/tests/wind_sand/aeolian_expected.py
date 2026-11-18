"""The Blender edition's own solvers/aeolian.py on recorded inputs, for the port's wind-and-sand tests (PORT_PLAN.md
5.1: plan and function fixtures). numpy only: no Blender, no GPU (core/world_noise.py's field() stands in for its
GPU field where aeolian._fbm falls back to it, as it does outside Blender: numpy's float64 noise is the oracle).

    <Blender's python> -I eidoverse/terrain/tests/wind_sand/aeolian_expected.py [--out <dir>]

Run it with Blender's own Python (tests/_where.mjs blenderPython(): numpy 2.3.4), never the system's (plan C6); the
Blender edition is found as tests/parity/_blender.py finds it ($EIDO_BLENDER_EDITION, or blender/ in this checkout).
Writes <out> (default eidoverse/terrain/tests/out/wind_sand/fixtures/): manifest.json and one little-endian .bin per
array ({file, shape, dtype}, C order, row 0 south), the versions recorded.

  plans      resolve_params for every kind, the recipe's own stage parameters and the Great Sand Dunes' knobs;
             refine_settings and refine_winds on context, main and hero levels; growth_index on real plans;
             cycle_blocks, schedule (with and without gusts and wind triples), hop_box (unturned and steered, short
             and long hops), uniforms_for, check_grid's errors, normalise_winds' forms
  functions  start_fields (the star kind, stretched and not, the transverse kind) at small periodic levels and at the
             dunes run's growth level; steering_for and Steering.for_wind; stretch_periodic along three axes;
             denoise (periodic and mirrored, with and without pins); smooth_sheet; sample_periodic of the dunes run's
             tile to its context levels; spacing_peak, dune_height and slip_fraction of the dunes run's fields; the
             numpy twin loop (TwinSim) for 40 iterations from test_gpu.py's start, unturned and steered, every
             iteration's sand kept
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', 'parity')))
import _blender as B  # noqa: E402

import numpy as np  # noqa: E402


class Store:
    """A fixture folder: arrays written once per distinct content, the manifest at the end."""

    def __init__(self, folder):
        self.dir = folder
        os.makedirs(folder, exist_ok=True)
        for f in os.listdir(folder):
            if f.endswith('.bin') or f == 'manifest.json':
                os.remove(os.path.join(folder, f))
        self.files = {}

    def save(self, a):
        a = np.ascontiguousarray(np.asarray(a))
        dt = {'float32': 'f32', 'float64': 'f64', 'int32': 'i32', 'int64': 'i64', 'uint32': 'u32',
              'bool': 'u8', 'uint8': 'u8'}[str(a.dtype)]
        if a.dtype == np.bool_:
            a = a.astype(np.uint8)
        h = hashlib.sha1(a.tobytes() + repr((a.shape, dt)).encode()).hexdigest()
        name = self.files.get(h)
        if name is None:
            name = self.files[h] = f'a{len(self.files) + 1:05d}.bin'
            a.astype(a.dtype.newbyteorder('<'), copy=False).tofile(os.path.join(self.dir, name))
        return {'file': name, 'shape': list(a.shape), 'dtype': dt}


def js(v):
    """Plain JSON (tuples as lists, numpy numbers as numbers, NaN as {'nan': true})."""
    if isinstance(v, dict):
        return {str(k): js(x) for k, x in v.items()}
    if isinstance(v, np.ndarray):
        return js(v.tolist())
    if isinstance(v, (list, tuple)):
        return [js(x) for x in v]
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer, int)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return f if math.isfinite(f) else {'nan': True}
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(B.TERRAIN, 'tests', 'out', 'wind_sand', 'fixtures'))
    a = ap.parse_args(B.script_args())
    root = B.bare_terrain_package()
    from eidoblend.terrain.core import grid as _grid
    from eidoblend.terrain.core import levels as L
    from eidoblend.terrain.core import twins as T
    from eidoblend.terrain.solvers import aeolian as A
    S = Store(a.out)
    t0 = time.perf_counter()
    plans, funcs = [], []

    # ------------------------------------------------------------------------------------------- plans ---
    stage = {'kind': 'star', 'winds': None, 'wind_rotate_deg': 0.0, 'sand_m': 0.0, 'spacing_m': 0.0, 'bed_m': 0.0,
             'patchiness': 0.0}
    gsd = dict(stage, winds=[[282, 1.0], [102, 0.7], [192, 0.5]], sand_m=40, spacing_m=900, bed_m=30, patchiness=0.5)
    param_sets = [('defaults', None), ('star stage', stage), ('gsd stage', gsd)]
    for kind in ('barchan', 'transverse', 'linear'):
        param_sets.append((f'{kind} stage', dict(stage, kind=kind)))
    param_sets += [('star rotated 30', dict(stage, wind_rotate_deg=30.0)),
                   ('star with speed_from_m', {'kind': 'star', 'speed_from_m': 12.0, 'refine_winds': 'cycle'}),
                   ('linear sand 20', {'kind': 'linear', 'sand_m': 20.0, 'winds': [[100, 2], {'from_deg': 200}, 300]}),
                   ('transverse grow phases', {'kind': 'transverse', 'grow_phases': [[3000, {'p_lift': 0.1}], [3000, {}]]})]
    for label, params in param_sets:
        plans.append(dict(label=f'resolve_params {label}', function='resolve_params', params=params,
                          result=js(A.resolve_params(params))))
    for kind in ('barchan', 'transverse', 'linear'):
        try:
            A.resolve_params({'kind': kind + 'x'})
        except KeyError as e:
            plans.append(dict(label=f'resolve_params unknown kind {kind}x', function='resolve_params_error',
                              params={'kind': kind + 'x'}, error=str(e.args[0])))
    pr = A.resolve_params({'kind': 'star', 'refine_winds': 'last', 'refine_iters': 900, 'hero_winds': 'cycle',
                           'hero_block': 150, 'hero_average_iters': 0})
    for role, cell in (('context', 31.25), ('main', 7.8125), ('hero', 1.953125)):
        lv = L.Level(2, role, 0.0, 0.0, 1024 * cell, cell, 1024)
        for label, p in (('star', A.resolve_params(stage)), ('star overrides', pr), ('transverse', A.resolve_params(dict(stage, kind='transverse')))):
            plans.append(dict(label=f'refine_settings {label} {role}', function='refine_settings', params=js(p),
                              level=lv.to_dict(), result=js(A.refine_settings(p, lv))))
    for mode in ('last', 'last2', 'cycle', None):
        p = A.resolve_params(dict(stage, wind_rotate_deg=10.0))
        plans.append(dict(label=f'refine_winds {mode}', function='refine_winds', params=js(p), mode=mode,
                          result=js(A.refine_winds(p, mode))))
    # growth_index on the plans the recipe makes at draft, film and hero quality (core/levels.plan_levels)
    for quality in ('draft', 'film', 'hero'):
        for kind, size in (('star', 8000.0), ('barchan', 3000.0), ('transverse', 3000.0), ('linear', 10000.0)):
            Q = L.QUALITY[quality]
            focus = [(0.0, 0.0)] if Q['hero_cell'] else None
            plan = L.plan_levels(size, Q['resolution'], context=4, focus=focus, hero=0.5 if Q['hero_cell'] else None)
            p = A.resolve_params(dict(stage, kind=kind))
            warns = []
            g = A.growth_index(plan, p['spacing_m'], float(p['cells_per_spacing']), warn=warns.append)
            plans.append(dict(label=f'growth_index {kind} {quality}', function='growth_index',
                              plan=[lv.to_dict() for lv in plan], spacing_m=p['spacing_m'],
                              cells_per_spacing=float(p['cells_per_spacing']), result=g, warnings=warns))
    winds_cases = [A.KINDS['star']['winds'], A.KINDS['linear']['winds'], [(225.0, 1.0)], [(282, 1.0), (102, 0.7), (192, 0.5)],
                   [(10.0, 0.3), (190.0, 0.3), (100.0, 0.4)]]
    for w in winds_cases:
        for block in (1000, 200, 400, 150, 7):
            plans.append(dict(label=f'cycle_blocks {w} {block}', function='cycle_blocks', winds=js(w), block=block,
                              result=js(A.cycle_blocks(w, block))))
    sched_cases = [(A.KINDS['star']['winds'], 24000, 1000, 8.0, 138, 100, 30.0, True),
                   (A.KINDS['star']['winds'], 24000, 1000, 8.0, 269, 100, 30.0, True),
                   (A.KINDS['star']['winds'], 400, 400, 8.0, 138 + 26991, 100, 30.0, False),
                   (A.KINDS['linear']['winds'], 12000, 200, 8.0, 7, 0, 0.0, True),
                   ([(225.0, 1.0)], 12000, 200, 8.0, 3, 0, 0.0, False),
                   ([(225.0, 1.0)], 1, 200, 0.0, 0, 0, 0.0, False),
                   ([(282, 1.0), (102, 0.7), (192, 0.5)], 24000, 1000, 8.0, 4000000000, 100, 30.0, True),
                   (A.KINDS['star']['winds'], 9000, 1000, 8.0, 3, 100, 25.0, False),
                   (A.KINDS['star']['winds'], 40, 10, 8.0, 9, 4, 20.0, True)]
    for c in sched_cases:
        plans.append(dict(label=f'schedule {c[1]} it, block {c[2]}, seed {c[4]}, gust {c[5]}', function='schedule',
                          args=js(c), result=js(A.schedule(*c[:7], with_wind=c[7]))))
    rng = np.random.default_rng(11)
    for k in range(60):
        d = float(rng.uniform(0, 360))
        hop = A.transport_dir(d) * float(rng.choice([1.5, 3.0, 4.7]))
        long_f = float(rng.choice([1.0, 1.0, 2.0, 2.5]))
        lo = float(rng.uniform(-1.2, 0.2))
        turn = (0.0, 0.0) if k % 3 == 0 else (lo, lo + float(rng.uniform(0.0, 1.6)))
        plans.append(dict(label=f'hop_box #{k}', function='hop_box', hop=js(hop), long_f=long_f, turn=js(turn),
                          result=js(A.hop_box(hop, long_f, turn))))
    for k, (params, cell, d, it, seed, bound, turn) in enumerate((
            (A.resolve_params(stage), 15.625, 344.29, 0, 138, T.BOUND_PERIODIC, (-1.21, 1.43)),
            (A.resolve_params(dict(stage, kind='barchan')), 2.9296875, 225.0, 77, 7, T.BOUND_PINNED, (0.0, 0.0)),
            (A.params_for({'rise': 'upwind', 'long_factor': 2.0, 'speedup': 0.6, 'speed_pow': 0}), 4.0, 37.0, 3, 9,
             T.BOUND_OPEN, (-0.2, 0.3)),
            (A.resolve_params(dict(stage, kind='linear')), 19.53125, 120.0, 5000, 2**31 - 7, T.BOUND_PERIODIC, (0.0, 0.0)))):
        plans.append(dict(label=f'uniforms_for #{k}', function='uniforms_for', params=js(params), cell=cell, from_deg=d,
                          it=it, seed=seed, bound=bound, turn=js(turn),
                          result=js(A.uniforms_for(params, cell, d, it, seed, bound, turn))))
    for shape, params, bound in (((40, 30), {'hop_cells': 9.0}, T.BOUND_PERIODIC), ((30, 60), {'shadow_reach': 28}, T.BOUND_PERIODIC),
                                 ((30, 60), {'shadow_reach': 28}, T.BOUND_PINNED), ((64, 64), {}, T.BOUND_PERIODIC)):
        p = A.params_for(params)
        try:
            A.check_grid(shape, p, bound)
            err = None
        except ValueError as e:
            err = str(e)
        plans.append(dict(label=f'check_grid {shape} {params} {bound}', function='check_grid', shape=list(shape),
                          params=js(p), bound=bound, error=err))
    for w in ([(28.0, 1.0), (148.0, 0.0), (-30.0, 2.0)], [{'from_deg': 400.0, 'weight': 0.5}, 90, [12.5]], [(1.0, -1.0)], [(5.0, 0.0)]):
        try:
            res, err = js(A.normalise_winds(w)), None
        except ValueError as e:
            res, err = None, str(e)
        plans.append(dict(label=f'normalise_winds {w}', function='normalise_winds', winds=js(w), result=res, error=err))

    # --------------------------------------------------------------------------------------- functions ---
    def lv_of(n, cell, x0=None, y0=None, role='main', index=0):
        side = n * cell
        return L.Level(index, role, -0.5 * side if x0 is None else x0, -0.5 * side if y0 is None else y0, side, cell, n)

    star = A.resolve_params(stage)
    trans = A.resolve_params(dict(stage, kind='transverse'))
    cases = [('star 128 periodic', lv_of(128, 62.5), star, 1, True), ('star 128 no stretch', lv_of(128, 62.5),
             dict(star, supply_stretch_m=0.0), 2, True), ('star 128 open', lv_of(128, 62.5), star, 3, False),
             ('transverse 96 periodic', lv_of(96, 4.0), trans, 4, True),
             ('star 128 rotated', lv_of(128, 62.5), A.resolve_params(dict(stage, wind_rotate_deg=40.0)), 5, True)]
    for label, lv, p, seed, periodic in cases:
        per = lv.side if periodic else None
        bed, sand = A.start_fields(lv, p, seed, period_m=per)
        funcs.append(dict(label=f'start_fields {label}', function='start_fields', level=lv.to_dict(), params=js(p), seed=seed,
                          period_m=per, outputs=dict(bed=S.save(bed), sand=S.save(sand))))
        st = A.steering_for(lv, p, seed, period_m=per)
        if st is not None:
            outs = {'n': S.save(st.n.astype(np.float64))}
            turns = {}
            for theta in (28.0, 148.0, 268.0, 30.5):
                cs, turn = st.for_wind(theta)
                outs[f'cs_{theta:g}'] = S.save(cs)
                turns[f'{theta:g}'] = list(turn)
            funcs.append(dict(label=f'steering {label}', function='steering_for', level=lv.to_dict(), params=js(p), seed=seed,
                              period_m=per, steer=st.steer, turn_rad=st.turn, turns=turns, outputs=outs))
    # stretch_periodic along three axes, on a numpy fbm (test_supply_corridors' field)
    lv = L.Level(0, 'context', -8000.0, -8000.0, 16000.0, 31.25, 512)
    sn = A._fbm(lv, 2000.0, 2, 9, lv.side)
    for axis in (90.0, 30.0, 155.0):
        out = A.stretch_periodic(sn, lv.cell, 1500.0, axis)
        funcs.append(dict(label=f'stretch_periodic axis {axis:g}', function='stretch_periodic', cell=lv.cell, sigma_m=1500.0,
                          axis_deg=axis, inputs=dict(a=S.save(sn.astype(np.float32))), outputs=dict(out=S.save(out))))
    small = sn[:240, :200]                                                # a non-square, non-power-of-two tile
    for axis in (90.0, 63.0):
        out = A.stretch_periodic(small, 31.25, 900.0, axis)
        funcs.append(dict(label=f'stretch_periodic 240x200 axis {axis:g}', function='stretch_periodic', cell=31.25,
                          sigma_m=900.0, axis_deg=axis, inputs=dict(a=S.save(small.astype(np.float32))),
                          outputs=dict(out=S.save(out))))
    # denoise and smooth_sheet on a dune field's sand, periodic and open with the border band's pins
    floor = os.path.join(B.parity_root(), B.source_key(root)['folder'], 'dunes_s1_draft', 'base', 'stages')
    after = np.load(os.path.join(floor, 'L2_p0_00_dune_field_after.npz')) if os.path.isdir(floor) else None
    if after is not None:
        sand = np.asarray(after['sand'], np.float32)
        h = np.asarray(after['h'], np.float32)
        w = _grid.border_ramp(sand.shape[0], 16, 'smooth')
        pin_sand = np.maximum(sand * 0.9 - 1.0, 0.0).astype(np.float32)
        for sig in (0.5, 1.0, 2.0):
            funcs.append(dict(label=f'denoise periodic {sig:g}', function='denoise', sigma=sig, periodic=True,
                              inputs=dict(sand=S.save(sand)), outputs=dict(out=S.save(A.denoise(sand, sig, periodic=True)))))
            funcs.append(dict(label=f'denoise open pinned {sig:g}', function='denoise', sigma=sig, periodic=False,
                              inputs=dict(sand=S.save(sand), pin_w=S.save(w), pin_sand=S.save(pin_sand)),
                              outputs=dict(out=S.save(A.denoise(sand, sig, periodic=False, pin_w=w, pin_sand=pin_sand)))))
        funcs.append(dict(label='denoise sigma 0 pinned', function='denoise', sigma=0.0, periodic=False,
                          inputs=dict(sand=S.save(sand), pin_w=S.save(w), pin_sand=S.save(pin_sand)),
                          outputs=dict(out=S.save(A.denoise(sand, 0.0, periodic=False, pin_w=w, pin_sand=pin_sand)))))
        for label, p in (('star', star), ('star top 30', dict(star, sheet_top_m=30.0)), ('transverse', trans)):
            funcs.append(dict(label=f'smooth_sheet {label} periodic', function='smooth_sheet', params=js(p), periodic=True,
                              inputs=dict(sand=S.save(sand)), outputs=dict(out=S.save(A.smooth_sheet(sand, p, periodic=True)))))
            funcs.append(dict(label=f'smooth_sheet {label} open pinned', function='smooth_sheet', params=js(p), periodic=False,
                              inputs=dict(sand=S.save(sand), pin_w=S.save(w), pin_sand=S.save(pin_sand)),
                              outputs=dict(out=S.save(A.smooth_sheet(sand, p, periodic=False, pin_w=w, pin_sand=pin_sand)))))
        hdr = json.load(open(os.path.join(floor, 'stages.json'), encoding='utf-8'))
        plan = [L.Level(**d) for d in hdr['plan']]
        for i in (0, 1):
            for name, arr in (('sand', sand), ('bed', np.asarray(after['bed'], np.float32))):
                funcs.append(dict(label=f'sample_periodic {name} to level {i}', function='sample_periodic',
                                  src=plan[2].to_dict(), level=plan[i].to_dict(), inputs=dict(a=S.save(arr)),
                                  outputs=dict(out=S.save(A.sample_periodic(arr, plan[2], plan[i])))))
        funcs.append(dict(label='measures of the dunes run\'s main level', function='measures', cell=plan[2].cell,
                          inputs=dict(h=S.save(h), sand=S.save(sand)),
                          result=js(dict(spacing_peak=A.spacing_peak(h, plan[2].cell), dune_height=A.dune_height(sand),
                                         slip_fraction=A.slip_fraction(h, plan[2].cell, 31.0)))))
    else:
        print(f'[aeolian_expected] no dunes floor run at {floor}: denoise, smooth_sheet, sample_periodic and the '
              'measures are left out (tests/parity/floor_runs.sh --recipes dunes makes it)')
    # the twin loop: test_gpu.py test_many_iterations' start and schedule, every iteration's sand
    SHAPE = (80, 96)
    bed = T.random_field(SHAPE, 0.0, 5.0, seed=5 + 1, smooth=2)
    sand0 = np.maximum(T.random_field(SHAPE, -2.0, 6.0, seed=5 + 2, smooth=2), 0.0).astype(np.float32)
    n = np.stack([np.clip(3.0 * T.random_field(SHAPE, -1.0, 1.0, seed=30 + k, smooth=6), -2.0, 2.0) for k in range(3)])
    for name, stg in (('unturned', None), ('steered', A.Steering(n, 25.0, 10.0))):
        t = A.TwinSim(bed, sand0, 4.0, T.BOUND_PERIODIC, {'hop_cells': 3.0}, seed=9, steer=stg)
        sched = A.schedule(A.KINDS['star']['winds'], 40, 10, 8.0, 9, gust=4, spread_deg=20.0, with_wind=True)
        steps, sands, it = [], [], 0
        for d, b, w in sched:
            for _ in range(b):
                if it >= 40:
                    break
                t.step(d, w)
                steps.append([d, w])
                sands.append(np.array(t.st[..., 1]))
                it += 1
        outs = {'sand': S.save(np.stack(sands).astype(np.float32))}
        funcs.append(dict(label=f'twin loop {name}', function='twin_loop', cell=4.0, bound=T.BOUND_PERIODIC,
                          params={'hop_cells': 3.0}, seed=9, steps=js(steps), steer_deg=25.0 if stg else 0.0,
                          turn_deg=10.0 if stg else 0.0,
                          inputs=dict(bed=S.save(bed), sand=S.save(sand0), **({'n': S.save(n.astype(np.float32))} if stg else {})),
                          outputs=outs))
    man = dict(source='the Blender edition (blender/eidoblend/terrain/solvers/aeolian.py), by '
                      'tests/wind_sand/aeolian_expected.py', key=B.source_key(root), versions=B.versions(),
               date=time.strftime('%Y-%m-%d %H:%M:%S'), seconds=round(time.perf_counter() - t0, 1), plans=plans,
               functions=funcs)
    B.write_json(os.path.join(a.out, 'manifest.json'), man)
    print(f'[aeolian_expected] {len(plans)} plan cases, {len(funcs)} function cases in {man["seconds"]} s -> {a.out}')


if __name__ == '__main__':
    main()
