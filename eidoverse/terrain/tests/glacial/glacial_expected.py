"""Function fixtures of the glacial package (PORT_PLAN.md 5.1 "function fixtures": a GPU replacement of numpy code
against that numpy function): the Blender edition's own numpy functions of solvers/glacial.py, run by Blender's own
Python on the inputs that matter.

    <Blender's python> -I eidoverse/terrain/tests/glacial/glacial_expected.py [--only carve,synthetic] [out folder]

  carve      the carve's input of the floor runs (alpine_valley seeds 1 and 2, the coarsest level's last pass: its
             'glacial' stage dump), and on it every step of carve_level that numpy runs: drainage_receivers,
             mass_balance, the ice discharge and the drainage area on the twin device (and Blender's GPU discharge
             from the dump, the one the run used), the centrelines (every per-seed array, the streams, smooth_along's
             inputs and outputs, head_distance, graded_fill), best_donor, the cirques (none at the recipe's ELA;
             again with cirque_ela_m 1800, where there are), seed_textures, the jump flood's steps and the uniforms;
             the twin's jump flood and U-carve on them
  synthetic  the Blender tests' own inputs (blender/tests/terrain/glacial/test_twins.py): the mass balance's dome
             (d8_receivers, the discharge and its budget with and without inflow), graded_fill, best_donor, the flutes
             on a slope, drainage_receivers on rough ground and on the 1 mm case, lip_open, head_distance and the
             taper, sharpen_walls on an inherited trough, the recipe's carve of the small V valley (twin device), the
             horseshoe uplift and the trunk river (the trunk needs solvers/rivers.py)

Writes <out>/manifest.json (cases: label, function, args, arrays) and the arrays as little-endian .bin files. Default
out: eidoverse/terrain/tests/out/glacial/fixtures/. numpy only (no Blender, no GPU).
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'parity'))
import _blender as B  # noqa: E402
import _hooks as HK  # noqa: E402

B.bare_terrain_package()
import numpy as np  # noqa: E402

from eidoblend.terrain.core import levels as L  # noqa: E402
from eidoblend.terrain.core import twins as T  # noqa: E402
from eidoblend.terrain.core import world_noise as WN  # noqa: E402
from eidoblend.terrain.core.fields import Fields  # noqa: E402
from eidoblend.terrain.solvers import fluvial as FL  # noqa: E402
from eidoblend.terrain.solvers import glacial as G  # noqa: E402
from eidoblend.terrain.solvers import hydro as HY  # noqa: E402

args = list(sys.argv[1:])
ONLY = None
if '--only' in args:
    i = args.index('--only')
    ONLY = set(args[i + 1].split(','))
    del args[i:i + 2]
OUT = args[0] if args else os.path.normpath(os.path.join(HERE, '..', 'out', 'glacial', 'fixtures'))
os.makedirs(OUT, exist_ok=True)
F32 = np.float32
DT = {np.dtype(np.float32): 'f32', np.dtype(np.float64): 'f64', np.dtype(np.int32): 'i32', np.dtype(np.uint8): 'u8'}
cases = []
counter = [0]
GROUP = ['x']                                            # array files are named per group: a partial run keeps the rest


def arr(a):
    a = np.ascontiguousarray(a)
    if a.dtype == np.bool_:
        a = a.astype(np.uint8)
    elif a.dtype == np.int64:
        a = a.astype(np.int32)
    counter[0] += 1
    name = f'{GROUP[0]}{counter[0]:05d}.bin'
    a.astype(a.dtype.newbyteorder('<')).tofile(os.path.join(OUT, name))
    return {'file': name, 'shape': list(a.shape), 'dtype': DT[a.dtype]}


def add(label, function, args_, arrays, level=None, values=None):
    c = {'label': label, 'function': function, 'args': B.jsonable(args_), 'arrays': {k: arr(v) for k, v in arrays.items()}}
    if level is not None:
        c['level'] = level.to_dict()
    if values is not None:
        c['values'] = B.jsonable(values)
    cases.append(c)
    print(f'[fixture] {label}: {", ".join(arrays)}', flush=True)


def want(group):
    return ONLY is None or group in ONLY


TWIN = FL.device('twin')

# ------------------------------------------------------------------------------------------------- the carve ---

if want('carve'):
    GROUP[0] = 'c'
    for f_ in os.listdir(OUT):
        if f_.startswith('c') and f_.endswith('.bin'):
            os.remove(os.path.join(OUT, f_))
    for seed in (1, 2):
        t0 = time.perf_counter()
        run = os.path.join(B.parity_root(), 'blender_f90c6fc_11d0dd93fa', f'alpine_valley_s{seed}_draft', 'base', 'stages')
        head = json.load(open(os.path.join(run, 'stages.json'), encoding='utf-8'))
        st = [s for s in head['stages'] if s['op'] == 'glacial' and s['level'] == 0 and s['context']['prepass'] is None][0]
        before = np.load(os.path.join(run, st['before']))
        after = np.load(os.path.join(run, st['after']))
        level = L.Level.from_dict(st['window'])
        main = L.Level.from_dict(head['plan'][head['main_index']])
        params = st['params']
        base = float(st['context']['base_elevation_m'] or 0.0)
        sea = st['context']['sea_level']
        s = int(st['seed']) + int(G._p(params, 'seed'))
        cell, n = float(level.cell), level.n
        h = np.asarray(before['h'], np.float64)
        recv, filled = G.drainage_receivers(h, cell, sea)
        surf = filled.astype(F32)
        b = G.mass_balance(h, base, params)
        if sea is not None:
            b = np.where(h <= sea, -float(G._p(params, 'b_abl_m')), b).astype(F32)
        Qt, it_q = G.ice_flux_converge(TWIN, surf, b, cell, recv, float(G._p(params, 'p_ice')), params=params)
        A, it_a = G.ice_flux_converge(TWIN, surf, np.ones_like(b), cell, recv, float(G._p(params, 'p_ice')),
                                      params=dict(params or {}, ice_width_m=0.0))
        Qg = np.asarray(after['ice_q'], F32)
        # the centrelines from the discharge the run used (Blender's GPU), the area from the twin (a sum of exact
        # cell areas along D8 paths: the same on every device)
        cl = G.centrelines(h, Qg, A, recv, level, main, params, base, s)
        stx = cl['streams']
        # smooth_along's inputs (the cells' centres, h and f at the seeds) and the head distance of the smoothed seeds
        jj, ii = np.divmod(stx['idx'], n)
        x0 = level.x0 + (ii + 0.5) * cell
        y0 = level.y0 + (jj + 0.5) * cell
        qref = float(cl['Q_ref'])
        f_all = np.minimum(np.power(np.maximum(np.asarray(Qg, np.float64), 0.0) / max(qref, 1e-30), 0.4),
                           float(G._p(params, 'f_max')))
        sig = float(G._p(params, 'smooth_cells'))
        xy = G.smooth_along(np.stack([x0, y0], 1), stx, sig, link_tributaries=True)
        dist = G.head_distance(stx, xy[:, 0], xy[:, 1])
        up = G.best_donor(recv, A)
        cq = G.cirques(cl, params, base, level, h=h, up=up, seed=s)
        p_low = dict(params, cirque_ela_m=1800.0)
        cq_low = G.cirques(cl, p_low, base, level, h=h, up=up, seed=s)
        cand0, sA, sB, sC = G.seed_textures(cl, level)
        pu, cu = G.profile_uniforms(params), G.carve_uniforms(params)
        wmax = float(np.max(cl['W']))
        reach = 1.0 + max(1.0 + 2.0 * pu['uShW'], cu['uCutW'], cu['uShCutW'])
        steps = G.jfa_steps(reach * wmax / cell, n)
        cT, _, _ = G.jump_flood_run(TWIN, cand0, sA, sB, cell, pu, steps, seedC=sC)
        cand = TWIN.read(cT)
        arrays = dict(h=np.asarray(before['h'], F32), bed=np.asarray(before['bed'], F32), recv=recv, filled=surf, b=b,
                      Q_twin=Qt, Q_gpu=Qg, A=A, up=up, f_all=f_all.astype(np.float64),
                      idx=stx['idx'], rcv=stx['rcv'], main=stx['main'], sid=stx['sid'], head=stx['head'],
                      cont=stx['cont'], x0=x0, y0=y0, xs=xy[:, 0], ys=xy[:, 1], x=cl['x'], y=cl['y'], zc=cl['zc'],
                      q=cl['q'], f=cl['f'], W=cl['W'], H=cl['H'], d=cl['d'], zf=cl['zf'], fill=cl['fill'],
                      moraine=cl['moraine'], floor_f=cl['floor_f'], rise_f=cl['rise_f'], head_dist=dist,
                      cirques=np.asarray(cq, np.float64).reshape(-1, 11), cirques_low=np.asarray(cq_low, np.float64).reshape(-1, 11),
                      cand0=cand0, seedA=sA, seedB=sB, seedC=sC, cand_twin=cand)
        add(f'carve input, alpine_valley seed {seed} (L0 pass 1)', 'carve', {
            'seed': s, 'base_elevation_m': base, 'sea_level': sea, 'params': params, 'main': main.to_dict(),
            'stage_call': st['call']}, arrays, level=level,
            values=dict(it_q=it_q, it_a=it_a, Q_ref=qref, Wt=cl['Wt'], Ht=cl['Ht'], dt=cl['dt'], S=int(stx['idx'].size),
                        streams=int(stx['sid'].max() + 1), steps=steps, wmax=wmax, profile_uniforms=pu, carve_uniforms=cu,
                        cirques=len(cq), cirques_low=len(cq_low), q_twin_vs_gpu=float(np.max(np.abs(Qt - Qg))),
                        seconds=round(time.perf_counter() - t0, 1)))

# --------------------------------------------------------------------------------------------- synthetic ---

if want('synthetic'):
    GROUP[0] = 's'
    for f_ in os.listdir(OUT):
        if f_.startswith('s') and f_.endswith('.bin'):
            os.remove(os.path.join(OUT, f_))
    # test_twins.surface: a filled routing surface, a tilted dome of rough ground
    def surface(n=96, cell=50.0, seed=5):
        rng = np.random.default_rng(seed)
        jj, ii = np.mgrid[0:n, 0:n]
        r = np.hypot(ii - n / 2, jj - n * 0.3) / n
        h = 2500.0 * np.exp(-3.0 * r * r) + 300.0 * T.random_field((n, n), 0, 1, seed, smooth=3)
        h = h + 0.5 * rng.random((n, n))
        filled, _ = HY.fill_depressions(h)
        return HY.routing_surface(filled).astype(F32), cell

    # the mass balance (test_mass_balance): d8_receivers, the discharge with and without inflow, the budget
    surf, cell = surface()
    recv = G.d8_receivers(surf, cell)
    params = {'ela_m': 1500.0}
    b = G.mass_balance(surf, 0.0, params)
    n = surf.shape[0]
    rng = np.random.default_rng(1)
    q_in = np.zeros((n, n), F32)
    q_in[0, rng.integers(0, n, 6)] = rng.uniform(1e5, 1e6, 6).astype(F32)
    for name, qi in (('no inflow', None), ('inflow at the edge', q_in)):
        Q, it = G.ice_flux_converge(TWIN, surf, b, cell, recv, 0.0, Q_in=qi, params=params, check=32)
        bud = G.flux_budget(Q, b, recv, cell, params, Q_in=qi)
        add(f'mass balance, {name}', 'ice_flux_converge', {'cell': cell, 'params': params, 'check': 32},
            dict(surf=surf, recv=recv, b=b, Q=Q, Q_in=qi if qi is not None else np.zeros((n, n), F32)),
            values=dict(iterations=it, budget=bud))

    # graded_fill and head_distance (test_graded_fill, test_head_taper) on the 80^2 surface's streams
    surf, cell = surface(n=80, cell=40.0, seed=9)
    recv = G.d8_receivers(surf, cell)
    A, _ = G.ice_flux_converge(TWIN, surf, np.ones_like(surf), cell, recv, 0.0, params={'ice_width_m': 0.0}, check=32)
    mask = A >= 30 * cell * cell
    st = G.streams(mask, recv, A)
    idx = st['idx']
    jj, ii = np.divmod(idx, surf.shape[1])
    x, y = (ii + 0.5) * cell, (jj + 0.5) * cell
    rng = np.random.default_rng(2)
    zc = surf.ravel()[idx].astype(np.float64)
    zf = zc - rng.uniform(0, 120, idx.size)
    fill = G.graded_fill(zf, np.zeros(idx.size), x, y, st, 0.012, outlet=zc)
    dist = G.head_distance(st, x, y)
    tp = G.head_taper_factor(dist, np.full(dist.shape, 300.0), 2.0)
    add('streams, graded_fill, head_distance on the 80^2 dome', 'streams', {'cell': cell, 'grade': 0.012},
        dict(surf=surf, recv=recv, A=A, mask=mask, idx=idx, rcv=st['rcv'], main=st['main'], sid=st['sid'],
             head=st['head'], cont=st['cont'], x=x, y=y, zc=zc, zf=zf, fill=fill, head_dist=dist, taper=tp))

    # best_donor (test_best_donor)
    surf, cell = surface(n=64, cell=40.0, seed=4)
    recv = G.d8_receivers(surf, cell)
    A, _ = G.ice_flux_converge(TWIN, surf, np.ones_like(surf), cell, recv, 0.0, params={'ice_width_m': 0.0}, check=32)
    add('best_donor on the 64^2 dome', 'best_donor', {'cell': cell}, dict(recv=recv, A=A, up=G.best_donor(recv, A)))

    # the flutes (test_flutes): a slope falling west, its contours wavy; numpy's world noise (no device). With each
    # its rounding floor (PORT_PLAN.md 5.4 on the function: its input h moved by one float32 ulp on half the cells,
    # default_rng([pattern, 1]), and the first noise field it makes moved likewise as it is made, the image the GPU
    # path's first world_noise_field dispatch writes, default_rng([pattern, 1, 0, 1]); five patterns): the largest
    # max |d| / range over them
    def flutes_floor(h_in, lv_, params_, seed_):
        base_ = G.wall_flutes(h_in.astype(F32), lv_, params_, seed_)
        rg = float(np.ptp(base_)) or 1.0
        worst = 0.0
        field0 = WN.field
        for pat in range(1, 6):
            first = [True]

            def nudged_field(*a, **k):
                out = field0(*a, **k)
                if first[0]:
                    first[0] = False
                    out = HK.nudge(np.asarray(out, F32), np.random.default_rng([pat, 1, 0, 1]))
                return out
            WN.field = nudged_field
            try:
                got = G.wall_flutes(HK.nudge(h_in.astype(F32), np.random.default_rng([pat, 1])), lv_, params_, seed_)
            finally:
                WN.field = field0
            worst = max(worst, float(np.max(np.abs(np.asarray(got, np.float64) - base_))) / rg)
        return worst

    lv = L.plan_levels(1000.0, 128, (0.0, 0.0), None, None, None)[0]
    X, Y = lv.xy()
    h = 0.8 * X + 0.1 * Y + 50.0 * np.sin(Y / 200.0)
    add('wall_flutes on a slope (128^2, 7.8 m)', 'wall_flutes', {'params': {}, 'seed': 1},
        dict(h=h.astype(F32), flutes=G.wall_flutes(h.astype(F32), lv, {}, 1)), level=lv,
        values=dict(floor=flutes_floor(h, lv, {}, 1)))
    lv2 = L.plan_levels(4000.0, 256, (300.0, -200.0), None, None, None)[0]
    X2, Y2 = lv2.xy()
    h2 = 600.0 + 0.3 * X2 - 0.5 * Y2 + 120.0 * np.sin(X2 / 700.0) * np.cos(Y2 / 900.0)
    pf = {'flute_weak': 0.6, 'flute_strong': 0.2}
    add('wall_flutes on a folded slope (256^2, 15.6 m)', 'wall_flutes', {'params': pf, 'seed': 8},
        dict(h=h2.astype(F32), flutes=G.wall_flutes(h2.astype(F32), lv2, pf, 8)), level=lv2,
        values=dict(floor=flutes_floor(h2, lv2, pf, 8)))

    # drainage_receivers (test_drainage_receivers): rough ground with basins; a cell 1 mm above a broad flat
    rng = np.random.default_rng(6)
    n = 96
    rough = 200.0 * T.random_field((n, n), 0, 1, 12, smooth=2).astype(np.float64) + rng.random((n, n))
    case = np.full((n, n), 100.0)
    case[:, :] += 0.5 * np.arange(n)[None, :]
    case[30:60, 30:70] = 120.0
    case[45, 70] = 120.001
    case[40:50, 29] = 119.0
    for name, hh in (('rough ground with basins', rough), ('a cell 1 mm above a broad flat', case)):
        hh = hh.astype(F32)                                          # a level's heights are float32
        recv, filled = G.drainage_receivers(hh, 10.0)
        add(f'drainage_receivers: {name}', 'drainage_receivers', {'cell': 10.0},
            dict(h=hh, recv=recv, filled=filled.astype(F32)))

    # lip_open (test_lip_open)
    cell, W = 8.0, 575.0
    xx = (np.arange(-600, 600) + 0.5) * cell
    rho = np.abs(xx) / W
    u = G.profile_uniforms({'trough_width_m': 1150.0, 'trough_depth_m': 830.0, 'wall_deg': 76.0, 'wall_toe': 0.4,
                            'wall_lip': 0.2, 'shoulder_width': 1.5, 'shoulder_rise': 0.3, 'shoulder_exp': 1.0})
    clean = 830.0 * G.prof(rho, u, np.float64)
    gutter = np.where((rho > 1.06) & (rho < 1.25), -60.0 * np.sin(np.pi * (rho - 1.06) / 0.19), 0.0)
    rim = np.where((rho >= 0.99) & (rho <= 1.06), 40.0 * np.sin(np.pi * (rho - 0.99) / 0.07), 0.0)
    for name, prof_ in (('a clean lip', clean), ('a rim and gutter', clean + rim + gutter)):
        hh = np.repeat(prof_[None, :], 16, 0).astype(F32)
        rr = np.repeat(rho[None, :], 16, 0).astype(F32)
        h1, drop = G.lip_open(np.asarray(hh, np.float64), np.asarray(rr, np.float64), cell, 100.0)
        add(f'lip_open: {name}', 'lip_open', {'cell': cell, 'radius_m': 100.0}, dict(h=hh, rho=rr, h1=h1, drop=drop))

    # sharpen_walls (test_sharpen_walls): a trough carved at 31.25 m inherited at 15.6 m
    from eidoblend.terrain.core import grid as Gd
    from eidoblend.terrain.recipes import alpine_valley as AV
    _, stages = AV.ALPINE_VALLEY.resolve({})
    gp = [s_ for s_ in stages if s_.op == 'glacial'][0].params
    pu = G.profile_uniforms(gp)
    W, H = 0.5 * float(gp['trough_width_m']), float(gp['trough_depth_m'])
    ff = pu['uFloorFrac']
    a = math.radians(15.0)

    def rho_at(n_, cell_):
        c = (np.arange(n_) + 0.5) * cell_ - 0.5 * n_ * cell_
        Xg, Yg = np.meshgrid(c, c)
        return np.abs(Xg * math.cos(a) - Yg * math.sin(a)) / W

    def target(r_, rock=False):
        k = np.ones_like(r_)
        return G.trough_target(r_, 100.0 * k, H * k, ff * k, 40.0 * k, pu['uFloorRise'] * k, pu, rock=rock)

    n, cell = 64, 31.25
    rc = rho_at(n, cell)
    parent = dict(h=target(rc), bed=target(rc, rock=True), trough_rho=rc, trough_zf=np.full((n, n), 100.0),
                  trough_H=np.full((n, n), H), trough_ff=np.full((n, n), ff), trough_fill=np.full((n, n), 40.0),
                  trough_rise=np.full((n, n), pu['uFloorRise']), trough_sharp=np.ones((n, n)),
                  carve=np.full((n, n), 300.0))
    child = {k: Gd.crop_upsample2(np.asarray(v, F32), 0, 0, n, 'catmull' if k in ('h', 'bed') else 'bilinear').astype(np.float64)
             for k, v in parent.items()}
    pin_w = np.zeros((2 * n, 2 * n))
    pin_w[:6, :] = pin_w[-6:, :] = pin_w[:, :6] = pin_w[:, -6:] = 1.0
    ins = {k: np.asarray(v, F32) for k, v in child.items()}
    fl = {k: np.asarray(v, F32) for k, v in child.items()}
    sharp = G.sharpen_walls(fl, None, gp, pin_w)
    add('sharpen_walls: a trough inherited at 15.6 m', 'sharpen_walls', {'params': gp},
        dict(**{f'in_{k}': v for k, v in ins.items()}, pin_w=pin_w.astype(F32), h=fl['h'], bed=fl['bed'],
             exact=target(rho_at(2 * n, 0.5 * cell)).astype(np.float64)), values=dict(sharpened_max_m=sharp))

    # the recipe's carve of the small V valley (test_head_taper_carve), twin device
    def v_valley(n_=64, cell_=125.0):
        lv_ = L.plan_levels(n_ * cell_, n_, (0.0, 0.0), None, None, None)[0]
        Xv, Yv = lv_.xy()
        river = 300.0 + 0.02 * (lv_.side / 2 - Yv)
        tan30 = math.tan(math.radians(30.0))
        hv = river + tan30 * np.abs(Xv)
        for side in (-1.0, 1.0):
            for yt in (-1800.0, 1800.0):
                trib = river + 0.08 * np.clip(side * Xv, 0.0, None) + 0.7 * tan30 * np.abs(Yv - yt)
                hv = np.where(side * Xv > 400.0, np.minimum(hv, np.maximum(trib, river + tan30 * 400.0)), hv)
        return lv_, (np.minimum(hv, 2300.0) + 2.0 * T.random_field((n_, n_), 0, 1, 3, smooth=2)).astype(F32)

    lv, h = v_valley()
    params = dict(gp, ela_m=500.0, trough_depth_m=600.0, cirques=False, channel_area_m2=1.0e6)

    def carve_of(h_in, pattern=None):
        fl_ = Fields(lv, {'h': h_in.copy(), 'bed': h_in.copy()})
        ctx_ = FL.StageContext(plan=[lv], index=0, level=lv, prepass=None, fresh=False, role='grow',
                               pins=FL.edge_pins(lv.n, h_in), shared={}, seed=1, base_elevation_m=0.0, device=TWIN,
                               log=lambda m: None)
        if pattern is None:
            return fl_, G.carve_level(fl_, lv, params, 1, ctx_, TWIN)
        # a perturbed run, as the stage floors' (tests/parity/_hooks.py, PORT_PLAN.md 5.4): every float32 field of
        # the level one ulp up on a quarter of the cells and down on a quarter at the op's entry (default_rng([pattern,
        # 1]), the fields in sorted order), and each kernel's images likewise right after its first dispatch in the
        # call (default_rng([pattern, 1, the kernel's index in first-dispatch order, 1]), the images in sorted order),
        # but the jump flood's: they hold packed cell indices, which a nudge turns into other seeds' (carve_floor.py)
        rng = np.random.default_rng([pattern, 1])
        for key in sorted(fl_.keys()):
            v = fl_[key]
            if isinstance(v, np.ndarray) and v.dtype == F32 and v.ndim == 2:
                fl_[key] = HK.nudge(v, rng)
        names = []
        run0 = TWIN.run

        def run(kernel, samplers, images, uniforms):
            out = run0(kernel, samplers, images, uniforms)
            name = kernel.name if hasattr(kernel, 'name') else kernel
            if name not in names:
                names.append(name)
                krng = np.random.default_rng([pattern, 1, len(names) - 1, 1])
                for k_ in sorted(images):
                    if name != 'jump_flood':
                        images[k_].a = HK.nudge(images[k_].a, krng)
            return out
        TWIN.run = run
        try:
            return fl_, G.carve_level(fl_, lv, params, 1, ctx_, TWIN)
        finally:
            del TWIN.run

    fields, rec = carve_of(h)
    # the carve's own floor (PORT_PLAN.md 5.4, as the stage floors measure it): the op-entry and in-op perturbations
    # above, five patterns; per field the largest max |d| / range over them
    floor = {}
    for pat in range(1, 6):
        fp, _ = carve_of(h, pat)
        for k, v in fields.items():
            if np.ndim(v) != 2 or k not in fp:
                continue
            a, b_ = np.asarray(v, np.float64), np.asarray(fp[k], np.float64)
            rg = float(np.ptp(a)) or 1.0
            floor[k] = max(floor.get(k, 0.0), float(np.max(np.abs(a - b_))) / rg)
    add('the recipe\'s carve of a small V valley (64^2 at 125 m, twin device)', 'carve_level',
        {'params': params, 'seed': 1, 'base_elevation_m': 0.0},
        dict(h_in=h, **{f'out_{k}': np.asarray(v, F32) for k, v in fields.items() if np.ndim(v) == 2}), level=lv,
        values=dict(record=rec, floor=floor))

    # the horseshoe uplift (numpy's compose.uplift: no device) and, when solvers/rivers.py imports, the trunk river
    _, stages = AV.ALPINE_VALLEY.resolve({})
    vu = [s_ for s_ in stages if s_.op == 'valley_uplift'][0].params
    plan = L.plan_levels(8000.0, 128, (0.0, 0.0), 4, None, None)
    top = plan[0]
    u_ = G.uplift_shape(vu['shape'], top, 1, None)
    course = G.trunk_course(vu['shape'], (top.x0, top.y0, top.side), 1)
    pins, m = G.trunk_pins(course, top, FL.edge_pins(top.n, np.zeros((top.n, top.n), F32)))
    add('the horseshoe uplift and the trunk river (alpine_valley defaults, seed 1, 128^2 coarsest level)', 'valley_uplift',
        {'shape': vu['shape'], 'seed': 1},
        dict(u=u_, points=course['points'], s=course['s'], bed=course['bed'], trunk=m, pin_w=pins['pin_w'],
             pin_h=pins['pin_h']), level=top, values=dict(peak=float(np.max(u_)), width_m=course['width_m']))

manifest = dict(source='blender/eidoblend/terrain/solvers/glacial.py by tests/glacial/glacial_expected.py',
                versions=B.versions(), date=time.strftime('%Y-%m-%d %H:%M:%S'), cases=cases)
mp = os.path.join(OUT, 'manifest.json')
old = json.load(open(mp, encoding='utf-8')) if os.path.exists(mp) and ONLY else None
if old:                                                  # a partial run keeps the other groups' cases
    keep = [c for c in old['cases'] if c['label'] not in {x['label'] for x in cases}]
    manifest['cases'] = keep + cases
B.write_json(mp, manifest)
print(f'{len(cases)} cases, {counter[0]} arrays -> {OUT}', flush=True)
