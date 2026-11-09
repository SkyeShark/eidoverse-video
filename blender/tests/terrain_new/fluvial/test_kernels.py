"""The fluvial package's kernel tests (Blender, through a GPU slot):

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/terrain_new/fluvial/test_kernels.py

  1. parity: ONE dispatch of every kernel against its numpy twin on a non-square 96 x 80 field with pins, in the
     open, periodic and pinned modes, within 1e-4 x each output channel's range: flow_weights (p 1, 1.3),
     route_incise (n = 1 implicit with D-infinity and with D8; n = 1.5 explicit; a layered-rock column; closed basins
     filled and left), creep (nonlinear cap 5; linear cap 1), threshold_excess, threshold (isotropic and the pair
     excess, all material and loose only), route_area, and the lock's lock_restrict / lock_apply (blocks 2, 8, 16
     at the block grid's offsets 0 and half a block, edge blocks cut; the second stage on an R32F input)
  2. mass conservation: 300 creep sub-steps and 300 threshold iterations (isotropic, loose only, pair excess) on a
     rough 256^2 field, open and periodic: the sum of h unchanged within 1e-5 (relative)
  3. determinism: the fluvial stage run twice on the same 192^2 level gives bit-identical fields
  4. cost: one whole fluvial step at 1024^2 and 2048^2 (design section 9: <= 0.5 ms at 1024^2, <= 1.8 ms at
     2048^2), with and without the lock
Writes blender/tests/terrain_new/out/fluvial/kernel_tests.json; exit code 1 on a failure.
"""
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'core'))
import plain_import  # noqa: E402

plain_import.install()
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'fluvial'))
os.makedirs(OUT, exist_ok=True)

import numpy as np  # noqa: E402

from eidoblend.terrain.core import twins as T  # noqa: E402
from eidoblend.terrain.core import levels as L  # noqa: E402
from eidoblend.terrain.core.fields import Fields  # noqa: E402
from eidoblend.terrain.solvers import fluvial as FL  # noqa: E402
from eidoblend.terrain.solvers import hillslope as HS  # noqa: E402,F401
from eidoblend.terrain.solvers import hydro as HY  # noqa: E402,F401

RESULTS = {}
FAILED = []
F32 = np.float32


def check(name, cond, detail=None):
    RESULTS[name] = {'ok': bool(cond), 'detail': detail}
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f': {detail}' if detail is not None else ''), flush=True)
    if not cond:
        FAILED.append(name)


GPU = FL.device('gpu')
TWIN = FL.device('twin')


def parity(kernel, inputs, uniforms, out_shapes, tol=1e-4):
    """One dispatch on the GPU and on the twin device; compare every output channel within tol x its range."""
    got, want = {}, {}
    for dev, res in ((GPU, got), (TWIN, want)):
        tex = {k: dev.texture(v) for k, v in inputs.items()}
        outs = {k: dev.empty(shp[:2], shp[2]) for k, shp in out_shapes.items()}
        dev.run(kernel, tex, outs, uniforms)
        for k, t in outs.items():
            res[k] = dev.read(t)
    rep = T.compare(got, want, tol)
    return rep


def fields96(seed=1, relief=400.0):
    shape = (80, 96)
    h = T.random_field(shape, 0.0, relief, seed, smooth=1)
    A = T.random_field(shape, 100.0, 1e6, seed + 1)
    qs = T.random_field(shape, 0.0, 80.0, seed + 2)
    U = T.random_field(shape, 0.0, 3e-3, seed + 3, smooth=2)
    K = (1.5e-5 * (0.5 + T.random_field(shape, 0, 1, seed + 4, smooth=2))).astype(F32)
    Sc = (np.tan(np.radians(35.0)) * (0.85 + 0.3 * T.random_field(shape, 0, 1, seed + 5, smooth=2))).astype(F32)
    G = (0.5 * T.random_field(shape, 0, 1, seed + 6, smooth=2)).astype(F32)
    pw, ph = T.pin_pattern(shape, seed, band=4, value=(0.0, relief))
    rng = np.random.default_rng(seed + 9)
    Ain = np.where(rng.random(shape) > 0.97, rng.uniform(1e5, 1e7, shape), 0.0).astype(F32)
    qin = np.where(Ain > 0, rng.uniform(1.0, 50.0, shape), 0.0).astype(F32)
    loose = T.random_field(shape, 0.0, 6.0, seed + 10)
    mk = T.rgba(T.random_field(shape, 0, 5, seed + 11), T.random_field(shape, 0, 2, seed + 12),
                T.random_field(shape, 0, 2, seed + 13), loose)
    return dict(h=h, A=A, qs=qs, U=U, K=K, Sc=Sc, G=G, pw=pw, ph=ph, Ain=Ain, qin=qin, mk=mk)


def test_parity():
    f = fields96()
    shape = f['h'].shape
    st = T.rgba(f['h'], f['A'], f['qs'], T.random_field(shape, 0, 1, 77))
    par = T.rgba(f['U'], f['K'], f['Sc'], f['G'])
    pin = T.rgba(f['pw'], f['ph'], f['Ain'], f['qin'])
    one = np.zeros((1, 1), F32)
    S4 = shape + (4,)
    S1 = shape + (1,)
    col = (np.linspace(0.3, 3.0, 64) * (1.0 + 0.5 * np.sin(np.arange(64)))).astype(F32)
    zoff = T.random_field(shape, -40.0, 40.0, 31, smooth=2)
    worst = {}
    for mode_name, mode in T.BOUNDARY_CASES:
        wsum = None
        rep = parity('flow_weights', {'st': st}, {'uDx': 10.0, 'uP': 1.0, 'uBound': mode}, {'outW': S1})
        worst[f'flow_weights/{mode_name}'] = rep['worst']
        check(f'parity flow_weights {mode_name}', rep['ok'], T.report_text(rep).splitlines()[0])
        rep = parity('flow_weights', {'st': st}, {'uDx': 10.0, 'uP': 1.3, 'uBound': mode}, {'outW': S1})
        check(f'parity flow_weights p=1.3 {mode_name}', rep['ok'], f"worst {rep['worst']:.3g}")
        # the GPU's own wsum feeds the routing kernels on both devices (so both see the same weights)
        tw = GPU.empty(shape, 1)
        GPU.run('flow_weights', {'st': GPU.texture(st)}, {'outW': tw}, {'uDx': 10.0, 'uP': 1.0, 'uBound': mode})
        wsum = GPU.read(tw)
        base = {'uDx': 10.0, 'uDt': 128.0, 'uM': 0.5, 'uN': 1.0, 'uP': 1.0, 'uColZ0': 0.0, 'uColDz': 1.0,
                'uColN': 0, 'uSlope': 1, 'uPitFill': 1, 'uPitEps': 1e-3, 'uBound': mode}
        ins = {'st': st, 'wsumT': wsum, 'par': par, 'pin': pin, 'mk': f['mk'], 'kcol': one, 'zoff': one}
        rep = parity('route_incise', ins, base, {'outS': S4, 'outM': S4})
        worst[f'route_incise/{mode_name}'] = rep['worst']
        check(f'parity route_incise n=1 D-infinity {mode_name}', rep['ok'], T.report_text(rep).replace('\n', ' | '))
        rep = parity('route_incise', ins, dict(base, uSlope=0), {'outS': S4, 'outM': S4})
        worst[f'route_incise d8/{mode_name}'] = rep['worst']
        check(f'parity route_incise n=1 D8 {mode_name}', rep['ok'], f"worst {rep['worst']:.3g}")
        # pits: a field with closed basins (every 7th cell sunk 5 m), filled vs left to rise
        hp = f['h'].copy()
        hp[3::7, 3::7] -= 5.0
        st_p = T.rgba(hp, f['A'], f['qs'], T.random_field(shape, 0, 1, 77))
        tw = GPU.empty(shape, 1)
        GPU.run('flow_weights', {'st': GPU.texture(st_p)}, {'outW': tw}, {'uDx': 10.0, 'uP': 1.0, 'uBound': mode})
        for fillp in (1, 0):
            rep = parity('route_incise', dict(ins, st=st_p, wsumT=GPU.read(tw)), dict(base, uPitFill=fillp),
                         {'outS': S4, 'outM': S4})
            check(f'parity route_incise pits filled={fillp} {mode_name}', rep['ok'], f"worst {rep['worst']:.3g}")
        rep = parity('route_incise', ins, dict(base, uN=1.5), {'outS': S4, 'outM': S4})
        check(f'parity route_incise n=1.5 explicit {mode_name}', rep['ok'], f"worst {rep['worst']:.3g}")
        ins_c = dict(ins, kcol=col[None, :], zoff=zoff)
        rep = parity('route_incise', ins_c, dict(base, uColZ0=-50.0, uColDz=8.0, uColN=64),
                     {'outS': S4, 'outM': S4})
        check(f'parity route_incise column {mode_name}', rep['ok'], f"worst {rep['worst']:.3g}")
        for cap in (5.0, 1.0):
            rep = parity('creep', {'st': st, 'par': par, 'pin': pin},
                         {'uDx': 10.0, 'uDtSub': 0.9 * 100.0 / (3.4 * 0.5 * cap), 'uD': 0.5, 'uCap': cap,
                          'uBound': mode}, {'outS': S4})
            worst[f'creep cap {cap:g}/{mode_name}'] = rep['worst']
            check(f'parity creep cap={cap:g} {mode_name}', rep['ok'], f"worst {rep['worst']:.3g}")
        rep = parity(HS.EXCESS, {'st': st, 'par': par}, {'uDx': 10.0, 'uBound': mode}, {'outP': S1})
        worst[f'threshold_excess/{mode_name}'] = rep['worst']
        check(f'parity threshold_excess {mode_name}', rep['ok'], f"worst {rep['worst']:.3g}")
        tp = GPU.empty(shape, 1)                                  # the GPU's own excess feeds both devices
        GPU.run(HS.EXCESS, {'st': GPU.texture(st), 'par': GPU.texture(par)}, {'outP': tp},
                {'uDx': 10.0, 'uBound': mode})
        phi = GPU.read(tp)
        for iso in (1, 0):
            for loose in (0, 1):
                rep = parity('threshold', {'st': st, 'par': par, 'pin': pin, 'mk': f['mk'],
                                           'phiT': phi if iso else one},
                             {'uDx': 10.0, 'uRate': 0.12 if iso else 0.06, 'uLoose': loose, 'uIso': iso,
                              'uBound': mode}, {'outS': S4, 'outM': S4})
                worst[f'threshold iso {iso} loose {loose}/{mode_name}'] = rep['worst']
                check(f'parity threshold {"isotropic" if iso else "pair"} loose={loose} {mode_name}', rep['ok'],
                      f"worst {rep['worst']:.3g}")
        rep = parity('route_area', {'st': st, 'wsumT': wsum, 'aT': T.rgba(f['A']), 'pin': pin},
                     {'uDx': 10.0, 'uP': 1.0, 'uBound': mode}, {'outA': S1})
        worst[f'route_area/{mode_name}'] = rep['worst']
        check(f'parity route_area {mode_name}', rep['ok'], f"worst {rep['worst']:.3g}")
    for b in (2, 8, 16):
        for off in ((0, 0), (b // 2, 0), (b // 2, b // 2)):          # the cycling block grid, edge blocks cut
            m0, m1 = shape[0] // b + 1, shape[1] // b + 1
            tgt = FL.offset_block_means(f['h'], b, off, (m0, m1))[0] + T.random_field((m0, m1), -3, 3, 5)
            rep = parity(FL.LOCK_RESTRICT, {'st': st, 'tgt': tgt}, {'uB': b, 'uOff': off}, {'outR': (m0, m1, 1)})
            worst[f'lock_restrict b{b} off{off}'] = rep['worst']
            check(f'parity lock_restrict block {b} offset {off}', rep['ok'], f"worst {rep['worst']:.3g}")
            res = T.random_field((m0, m1), -5, 5, 6, smooth=1)
            rep = parity(FL.LOCK_APPLY, {'st': st, 'res': res, 'pin': pin, 'mk': f['mk']},
                         {'uGain': 1.0, 'uB': b, 'uOff': off}, {'outS': S4, 'outM': S4})
            worst[f'lock_apply b{b} off{off}'] = rep['worst']
            check(f'parity lock_apply block {b} offset {off}', rep['ok'], f"worst {rep['worst']:.3g}")
    # the two-stage restrict's second stage reads an R32F field of partial means, with the offset in partials
    part = T.random_field((40, 48), 0, 300, 9, smooth=1)
    rep = parity(FL.LOCK_RESTRICT, {'st': part, 'tgt': np.zeros((11, 13), F32)}, {'uB': 4, 'uOff': (2, 2)},
                 {'outR': (11, 13, 1)})
    check('parity lock_restrict on an R32F input (second stage, offset)', rep['ok'], f"worst {rep['worst']:.3g}")
    # creep's change counted in the layers (the fluvial step): h kept before, the difference into mk
    rep = parity(FL.H_KEEP, {'st': st}, {}, {'outH': (shape[0], shape[1], 1)})
    worst['h_keep'] = rep['worst']
    check('parity h_keep', rep['ok'], f"worst {rep['worst']:.3g}")
    h0 = (f['h'] + T.random_field(shape, -2, 2, 12, smooth=1)).astype(F32)
    rep = parity(FL.CREEP_LAYERS, {'st': st, 'h0': h0, 'mk': f['mk']}, {}, {'outM': S4})
    worst['creep_layers'] = rep['worst']
    check('parity creep_layers', rep['ok'], f"worst {rep['worst']:.3g}")
    RESULTS['parity_worst'] = worst


def test_conservation():
    n = 256
    h = T.random_field((n, n), 0.0, 300.0, 3, smooth=1)
    sc = (np.tan(np.radians(30.0)) * (0.8 + 0.4 * T.random_field((n, n), 0, 1, 4, smooth=2))).astype(F32)
    par = T.rgba(None, None, sc, None)
    z = np.zeros((n, n), F32)
    pin = T.rgba(z, z, z, z)
    loose = T.random_field((n, n), 0.0, 4.0, 5)
    out = {}
    for mode_name, mode in (('open', T.BOUND_OPEN), ('periodic', T.BOUND_PERIODIC)):
        for kind in ('creep', 'threshold', 'threshold_loose', 'threshold_pair'):
            S = FL.Pair(GPU, T.rgba(h))
            M = FL.Pair(GPU, T.rgba(z, z, z, loose))
            P, Q = GPU.texture(par), GPU.texture(pin)
            phi = None
            t0 = time.perf_counter()
            for _ in range(300):
                if kind == 'creep':
                    GPU.run('creep', {'st': S.src, 'par': P, 'pin': Q}, {'outS': S.dst},
                            {'uDx': 5.0, 'uDtSub': 0.9 * 25.0 / (3.4 * 0.3 * 5.0), 'uD': 0.3, 'uCap': 5.0,
                             'uBound': mode})
                    S.swap()
                else:
                    iso = 0 if kind == 'threshold_pair' else 1
                    phi = HS.threshold_pass(GPU, S, M, P, Q, 5.0, 0.12 if iso else 0.06, kind == 'threshold_loose',
                                            mode, iso, phi)
            hn = GPU.read(S.src)[..., 0].astype(np.float64)
            s0, s1 = float(h.astype(np.float64).sum()), float(hn.sum())
            rel = abs(s1 - s0) / abs(s0)
            moved = float(np.abs(hn - h).mean())
            out[f'{kind}/{mode_name}'] = dict(rel_sum_change=rel, mean_abs_change_m=moved,
                                              ms=round((time.perf_counter() - t0) * 1000, 1))
            check(f'conservation {kind} {mode_name} (300 passes)', rel <= 1e-5 and moved > 0.01,
                  f'sum change {rel:.2e} (relative), material moved {moved:.3f} m per cell on average')
    RESULTS['conservation'] = out


def level_of(n, cell, x0=0.0, y0=0.0, role='main'):
    return L.Level(0, role, x0, y0, n * cell, cell, n)


def test_determinism():
    n = 192
    lv = level_of(n, 40.0, -3840.0, -3840.0)
    outs = []
    for _ in range(2):
        f = Fields(lv)
        ctx = FL.StageContext(plan=[lv], index=0, level=lv, fresh=True, role='grow', device=GPU, log=lambda m: None)
        FL.op_uplift(f, lv, {'shape': {'kind': 'dome', 'centre': [0, 0], 'radius_m': 3000.0}}, 5, ctx=ctx)
        FL.op_fluvial(f, lv, {'age_myr': 0.4, 'relief_m': 900.0, 'breakup': 0.25, 'outcrops': 0.5}, 5, ctx=ctx)
        outs.append({k: np.array(v) for k, v in f.items()})
    same = all(np.array_equal(outs[0][k].view(np.uint32), outs[1][k].view(np.uint32)) for k in outs[0])
    check('determinism: the fluvial stage twice on one 192^2 level, bit for bit', same,
          f'fields compared: {sorted(outs[0])}')


def test_cost():
    rec = {}
    for n in (1024, 2048):
        cell = 10.0
        h = (T.random_field((n, n), 0, 2000, 1, smooth=2)).astype(F32)
        z = np.zeros((n, n), F32)
        par = T.rgba(z + 2e-3, z + 1.5e-5, z + 0.7, z + 0.5)
        lv = level_of(n, cell)
        f = {'h': h}
        pins = FL.edge_pins(n, h)
        # the production step (solvers/fluvial.py DEFAULTS): 2 isotropic threshold iterations at 0.12, each an
        # excess pass and an exchange pass
        iters, rate = FL.DEFAULTS['threshold_iters'], FL.THRESHOLD_RATE['iso']
        run = FL.FluvialRun(GPU, cell, f, par, pins, FL.PINNED, None, None)
        for _ in range(5):
            run.step(130.0, 0.05, 1, iters, rate, 5.0)
        run.height()
        t0 = time.perf_counter()
        steps = 200
        for _ in range(steps):
            run.step(130.0, 0.05, 1, iters, rate, 5.0)
        run.height()
        ms = (time.perf_counter() - t0) * 1000.0 / steps
        lock_run = FL.FluvialRun(GPU, cell, f, par, pins, FL.PINNED, None, h, 64)
        for _ in range(5):
            lock_run.step(130.0, 0.05, 1, iters, rate, 5.0)
        lock_run.height()
        t0 = time.perf_counter()
        for _ in range(steps):
            lock_run.step(130.0, 0.05, 1, iters, rate, 5.0)
        lock_run.height()
        ms_lock = (time.perf_counter() - t0) * 1000.0 / steps
        npass = 5 + 2 * iters
        rec[str(n)] = dict(step_ms=round(ms, 4), step_with_lock_ms=round(ms_lock, 4),
                           passes=f'flow_weights + route_incise + (h_keep + creep x1 + creep_layers) + '
                                  f'(threshold_excess + threshold) x{iters} = {npass} (+ the lock: 2-3)')
        target = 0.5 if n == 1024 else 1.8
        check(f'one fluvial step at {n}^2 <= {target} ms', ms <= target,
              f'{ms:.3f} ms ({ms_lock:.3f} ms with the lock), {npass} passes')
    RESULTS['cost'] = rec
    from eidoblend.terrain.core import gpu as G
    RESULTS['compile_ms'] = dict(G.COMPILE_MS)


def main():
    t0 = time.time()
    for fn in (test_parity, test_conservation, test_determinism, test_cost):
        try:
            fn()
        except Exception as e:                                        # noqa: BLE001
            traceback.print_exc()
            check(fn.__name__, False, f'{type(e).__name__}: {e}')
    RESULTS['seconds'] = round(time.time() - t0, 1)
    RESULTS['failed'] = FAILED
    with open(os.path.join(OUT, 'kernel_tests.json'), 'w') as f:
        json.dump(RESULTS, f, indent=1, default=str)
    print(f'[fluvial.kernels] {len(FAILED)} failed: {FAILED}' if FAILED else '[fluvial.kernels] all passed',
          flush=True)
    # os._exit, as core/test_gpu.py: Blender's shader destructors crash at interpreter teardown (the GL context is
    # gone by then), after every result is written
    os._exit(1 if FAILED else 0)


main()
