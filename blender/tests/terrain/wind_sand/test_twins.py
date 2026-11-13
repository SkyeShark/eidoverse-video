"""Wind and sand in plain Python (system Python with numpy, no GPU): the slab model's twins.

    python blender/tests/terrain/wind_sand/test_twins.py

  - every twin's outputs match its kernel's //! declarations (the three kernel files and the avalanche source)
  - the transport gather equals the scatter it stands for (aeolian.scatter_step), slab for slab, in all three
    boundary modes, for 24 wind directions and three hop lengths, on a non-square 96 x 80 field
  - sand mass: conserved on a periodic grid through every pass (transport, avalanche, whole iterations); on an open
    grid it falls by exactly the slabs blown off the edge
  - the avalanche moves only sand, never more than a cell holds, and relaxes a sand pile to its angle of repose
  - the hop dithering is unbiased: the mean integer hop equals the real hop vector for any direction
  - the shadow of a ridge lies in its lee, inside the 15-degree line, and nowhere on the stoss side
  - determinism: one seed gives the same field bit for bit, another seed a different one
Each test runs in well under the design's 5 s. Results: out/wind_sand/twin_tests.json.
"""
import json
import math
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'core'))
import plain_import  # noqa: E402

plain_import.install()
OUT = os.path.normpath(os.path.join(plain_import.OUT, '..', 'wind_sand'))
os.makedirs(OUT, exist_ok=True)

import numpy as np  # noqa: E402

from eidoblend.terrain.core import gpu as G  # noqa: E402 - parse_spec / load_source need no GPU
from eidoblend.terrain.core import twins as T  # noqa: E402
from eidoblend.terrain.solvers import aeolian as A  # noqa: E402

FAILED = []
RESULTS = {}
SHAPE = (80, 96)                                   # non-square, so an axis mix-up fails


def check(name, cond, detail=None):
    RESULTS[name] = {'ok': bool(cond), 'detail': detail}
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f': {detail}' if detail is not None else ''), flush=True)
    if not cond:
        FAILED.append(name)


def fields(seed=0, sand_hi=6.0):
    bed = T.random_field(SHAPE, 0.0, 5.0, seed=seed + 1, smooth=2)
    sand = np.maximum(T.random_field(SHAPE, -2.0, sand_hi, seed=seed + 2, smooth=2), 0.0)
    return bed, sand.astype(np.float32)


def st_of(bed, sand):
    return np.stack([bed, sand], -1).astype(np.float32)


def test_declarations():
    bed, sand = fields()
    st = st_of(bed, sand)
    u = A.uniforms_for(A.params_for(), 4.0, 225.0, 3, 9, T.BOUND_OPEN)
    wind = A.unturned(SHAPE)
    sh = T.run_twin('dune_shadow', {'st': st, 'wind': wind}, u['dune_shadow'])
    plan = T.run_twin('dune_activate', {'st': st, 'shadow': sh['outShadow'], 'wind': wind}, u['dune_activate'])
    tr = T.run_twin('dune_transport', {'st': st, 'plan': plan['outPlan']}, u['dune_transport'])
    spec = G.parse_spec(A.AVALANCHE_SRC, 'dune_avalanche')
    av = T.run_twin(A.twin_avalanche, {'st': tr['outSt'], 'pins': np.zeros(SHAPE + (2,), np.float32)},
                    u['dune_avalanche'], spec=spec)
    shapes = {k: list(v[next(iter(v))].shape) for k, v in (('dune_shadow', sh), ('dune_activate', plan),
                                                              ('dune_transport', tr), ('dune_avalanche', av))}
    check('twins_match_kernel_declarations', True, shapes)
    for name in ('dune_shadow', 'dune_activate', 'dune_transport'):
        s = G.load_source(name)[2]
        check(f'{name}_uniforms_fit_push_constants', s.push_bytes() <= G.PUSH_LIMIT_BYTES,
              f'{s.push_bytes()} bytes')
    check('dune_avalanche_uniforms_fit_push_constants', spec.push_bytes() <= G.PUSH_LIMIT_BYTES,
          f'{spec.push_bytes()} bytes')


def test_gather_equals_scatter():
    bed, sand = fields(4)
    st = st_of(bed, sand)
    worst, lifted_tot, landed_tot, lost_tot, cases = 0.0, 0.0, 0.0, 0.0, 0
    t0 = time.perf_counter()
    for bound in (T.BOUND_OPEN, T.BOUND_PERIODIC, T.BOUND_PINNED):
        for hop in (1.5, 3.0, 4.7):
            for d in range(0, 360, 15):
                # long hops on (and overlapping the short ones at hop 1.5), the lift boost on
                p = A.params_for({'hop_cells': hop, 'p_lift': 0.3, 'long_factor': 2.0, 'speedup': 0.6,
                                  'lift_boost': 1.0})
                u = A.uniforms_for(p, 4.0, float(d), d, 17, bound)
                sh = A.twin_shadow({'st': st}, u['dune_shadow'])['outShadow']
                plan = A.twin_activate({'st': st, 'shadow': sh}, u['dune_activate'])['outPlan']
                g = A.twin_transport({'st': st, 'plan': plan}, u['dune_transport'])['outSt'][..., 1]
                s = A.scatter_step(st, plan, None, int(p['max_hops']), bound)
                worst = max(worst, float(np.abs(g.astype(np.float64) - s).max()))
                lifted = plan[..., 0].astype(np.float64)
                lost = float(lifted[plan[..., 3] < 0].sum())
                lifted_tot += float(lifted.sum())
                lost_tot += lost
                landed_tot += float(g.sum(dtype=np.float64) - (sand.sum(dtype=np.float64) - lifted.sum()))
                cases += 1
    check('transport_gather_equals_scatter', worst <= 1e-6 * float(sand.max()),
          {'cases': cases, 'worst |gather - scatter| m': worst, 'largest sand m': float(sand.max()),
           'seconds': round(time.perf_counter() - t0, 2)})
    check('every_lifted_slab_lands_once_or_leaves', abs(lifted_tot - lost_tot - landed_tot) <= 1e-6 * lifted_tot,
          {'lifted m': lifted_tot, 'landed m': landed_tot, 'blown off open edges m': lost_tot})


def test_mass():
    bed, sand = fields(7)
    tot0 = float(sand.sum(dtype=np.float64))
    t0 = time.perf_counter()
    sim = A.TwinSim(bed, sand, 4.0, T.BOUND_PERIODIC, {'hop_cells': 3.3}, seed=21)
    sim.run(A.KINDS['star']['winds'], 60, block=10)
    rel = float(sim.st[..., 1].sum(dtype=np.float64)) / tot0 - 1.0
    check('sand_mass_conserved_periodic', abs(rel) <= 1e-5,
          {'iterations': sim.it, 'relative change': rel, 'seconds': round(time.perf_counter() - t0, 2)})
    # open: what is lost is exactly what the plans say left the grid
    sim = A.TwinSim(bed, sand, 4.0, T.BOUND_OPEN, {'hop_cells': 3.3, 'aval_passes': 0}, seed=21)
    lost = 0.0
    for it in range(20):
        sim.step(225.0)
        pl = sim.last_plan
        lost += float(pl[..., 0][pl[..., 3] < 0].sum(dtype=np.float64))
    after = float(sim.st[..., 1].sum(dtype=np.float64))
    check('sand_mass_open_loses_only_outflow', abs(tot0 - lost - after) <= 1e-5 * tot0,
          {'start m': tot0, 'blown off m': lost, 'end m': after, 'residual m': tot0 - lost - after})


def test_avalanche():
    bed, sand = fields(9, sand_hi=12.0)
    u = A.uniforms_for(A.params_for({'creep': 0.0}), 2.0, 0.0, 0, 0, T.BOUND_PERIODIC)['dune_avalanche']
    uc = A.uniforms_for(A.params_for({'creep': 0.02}), 2.0, 0.0, 0, 0, T.BOUND_PERIODIC)['dune_avalanche']
    pins = np.zeros(SHAPE + (2,), np.float32)
    noisy = st_of(np.zeros(SHAPE, np.float32), 5.0 + T.random_field(SHAPE, -0.2, 0.2, seed=5))   # slab noise only
    smooth = noisy
    for _ in range(30):
        smooth = A.twin_avalanche({'st': smooth, 'pins': pins}, uc)['outSt']
    rough0 = float(np.abs(np.diff(noisy[..., 1], axis=1)).mean())
    rough1 = float(np.abs(np.diff(smooth[..., 1], axis=1)).mean())
    rel = float(smooth[..., 1].sum(dtype=np.float64) / noisy[..., 1].sum(dtype=np.float64) - 1.0)
    check('creep_smooths_slab_noise_and_conserves', rough1 < 0.8 * rough0 and abs(rel) <= 1e-5,
          {'mean |dh| between neighbours before': rough0, 'after 30 passes': rough1, 'relative mass change': rel})
    pins = np.zeros(SHAPE + (2,), np.float32)
    st = st_of(bed, sand)
    out = A.twin_avalanche({'st': st, 'pins': pins}, u)['outSt']
    rel = float(out[..., 1].sum(dtype=np.float64) / sand.sum(dtype=np.float64) - 1.0)
    check('avalanche_conserves_sand', abs(rel) <= 1e-6, {'relative change, one pass': rel})
    check('avalanche_never_moves_rock', np.array_equal(out[..., 0], st[..., 0]) and
          bool(np.all(out[..., 1][sand == 0] >= 0.0)) and bool(np.all(out[..., 1] >= 0.0)))
    bare = sand == 0
    gave = (out[..., 1] < sand - 1e-7) & bare
    check('avalanche_bare_cells_give_nothing', not gave.any())
    # a sand cone on a flat bed relaxes to the angle of repose
    n, cell = 64, 2.0
    jj, ii = np.mgrid[0:n, 0:n]
    r = np.hypot(ii - 31.5, jj - 31.5) * cell
    cone = np.maximum(40.0 - r * 1.5, 0.0).astype(np.float32)        # 56 degrees
    st = st_of(np.zeros((n, n), np.float32), cone)
    pins = np.zeros((n, n, 2), np.float32)
    t0 = time.perf_counter()
    for _ in range(400):
        st = A.twin_avalanche({'st': st, 'pins': pins}, u)['outSt']
    gy, gx = np.gradient(st[..., 1].astype(np.float64), cell)
    s = np.degrees(np.arctan(np.hypot(gx, gy)))
    p99 = float(np.percentile(s[st[..., 1] > 0.5], 99))
    check('avalanche_relaxes_to_repose', 29.0 <= p99 <= 34.0,
          {'cone flanks before deg': 56.3, 'p99 after 400 passes deg': round(p99, 2), 'repose deg': 31.0,
           'mass change': float(st[..., 1].sum(dtype=np.float64) / cone.sum(dtype=np.float64) - 1.0),
           'seconds': round(time.perf_counter() - t0, 2)})


def test_dither():
    worst = 0.0
    n = 400
    h = T.pcg(np.arange(n * n, dtype=np.int64))
    for d in range(0, 360, 10):
        for L in (1.7, 3.0, 4.35):
            hop = A.transport_dir(float(d)) * L
            vx, vy = A._hop_choice(h, np.float32(hop[0]), np.float32(hop[1]))
            err = math.hypot(float(vx.mean()) - hop[0], float(vy.mean()) - hop[1])
            worst = max(worst, err)
    check('hop_dither_unbiased_any_direction', worst <= 0.01,
          {'worst |mean hop - real hop| cells over 108 cases of 160000 sources': worst})


def test_shadow():
    n, cell = 96, 2.0
    jj, ii = np.mgrid[0:SHAPE[0], 0:n]
    x = ii * cell
    ridge = np.where(x < 80.0, x * math.tan(math.radians(12.0)), 80.0 * math.tan(math.radians(12.0))
                     - (x - 80.0) * math.tan(math.radians(32.0)))                 # stoss 12, lee 32 degrees
    ridge = np.maximum(ridge, 0.0).astype(np.float32)
    st = st_of(np.zeros_like(ridge), ridge)
    p = A.params_for({'shadow_lo_deg': 15.0, 'shadow_deg': 15.0, 'shadow_reach': 40})
    u = A.uniforms_for(p, cell, 270.0, 0, 0, T.BOUND_OPEN)['dune_shadow']      # a west wind: sand moves east
    sh = A.twin_shadow({'st': st}, u)['outShadow'][..., 0]
    row = sh[SHAPE[0] // 2]
    crest = 40
    top = float(ridge.max())
    # the lee: shadowed down to where the 15-degree line from the crest meets the ground (within the reach)
    lee_end = crest + int((top / math.tan(math.radians(15.0))) / cell)
    stoss_clear = bool(np.all(row[1:crest] == 0.0))
    lee_dark = bool(np.all(row[crest + 1:min(lee_end - 1, crest + 40)] == 1.0))
    beyond = bool(np.all(row[min(lee_end + 2, n - 1):] == 0.0)) if lee_end + 2 < crest + 40 else True
    check('shadow_in_the_lee_only', stoss_clear and lee_dark and beyond,
          {'stoss clear': stoss_clear, 'lee shadowed to the 15-degree line': lee_dark, 'clear beyond it': beyond,
           'crest col': crest, '15-degree line meets the ground at col': lee_end})


def test_determinism():
    bed, sand = fields(11)
    a = A.TwinSim(bed, sand, 4.0, T.BOUND_PERIODIC, {}, seed=3)
    b = A.TwinSim(bed, sand, 4.0, T.BOUND_PERIODIC, {}, seed=3)
    c = A.TwinSim(bed, sand, 4.0, T.BOUND_PERIODIC, {}, seed=4)
    for s in (a, b, c):
        s.run([(200.0, 1.0)], 15, block=15)
    check('same_seed_same_field', np.array_equal(a.st, b.st))
    check('other_seed_other_field', not np.array_equal(a.st, c.st))


def test_growth_pieces():
    """Gusts keep a regime's iterations and scatter each gust's direction around its wind; the time-averaged
    read-out conserves the sand; refinement levels blow the regime's last wind when asked to."""
    winds = [(28.0, 1.0), (148.0, 0.75), (268.0, 0.55)]
    plain = A.schedule(winds, 9000, 1000, 8.0, 3)
    gusty = A.schedule(winds, 9000, 1000, 8.0, 3, gust=100, spread_deg=25.0)
    offs = np.array([min(abs((d - w + 180.0) % 360.0 - 180.0) for w, _ in winds) for d, _b in gusty])
    g_ok = (A.schedule_length(gusty) == A.schedule_length(plain) and float(offs.max()) <= 8.0 + 4 * 25.0
            and 10.0 <= float(np.std(offs)) <= 30.0 and len(gusty) > len(plain))
    check('gust_schedule_keeps_the_regime_and_scatters', g_ok,
          {'iterations plain / gusty': [A.schedule_length(plain), A.schedule_length(gusty)],
           'gusts': len(gusty), 'max offset from the nearest wind, deg': float(offs.max()),
           'offset std, deg': float(np.std(offs))})
    bed, sand = fields(21)
    s = A.TwinSim(bed, sand, 4.0, T.BOUND_PERIODIC, {'block': 20}, seed=2)
    d, _b, m = s.run_averaged([(200.0, 1.0), (80.0, 0.6)], 64, 40, 4)
    rel = float(m.sum(dtype=np.float64) / sand.sum(dtype=np.float64) - 1.0)
    check('averaged_readout_conserves_sand', abs(rel) <= 1e-5 and d >= 64,
          {'iterations': d, 'relative change of the total': rel})
    # the plinth smoothing: speckle on a thin sheet goes, a dune above 3 x the speed-up's start is untouched, the
    # sheet's edge thins out onto the bare floor instead of standing as a step, and the floor away from it stays bare
    rng = np.random.default_rng(9)
    sheet = (20.0 + rng.normal(0.0, 2.0, (96, 96))).astype(np.float32)
    sheet[:, :20] = 0.0                                                   # bare rock
    jj, ii = np.mgrid[0:96, 0:96]
    dune = np.maximum(0.0, 200.0 - 6.0 * np.hypot(ii - 70.0, jj - 48.0))
    sand = np.maximum(sheet, dune).astype(np.float32)
    ps = A.resolve_params({'kind': 'star'})
    out = A.smooth_sheet(sand, ps, periodic=False)
    sig = float(ps['sheet_smooth_cells'])
    top = sand > 3.0 * ps['speed_from_m'] + 1.0
    thin = (sand > 0) & (sand < 25.0) & (ii > 24) & (ii < 40)
    far = int(math.ceil(20 - 3 * sig - 1))                                # columns beyond the Gaussian's reach
    step0 = float(np.abs(np.diff(sand[:, 14:26], axis=1)).max())
    step1 = float(np.abs(np.diff(out[:, 14:26], axis=1)).max())
    sm_ok = (bool(np.all(out[top] == sand[top])) and bool(np.all(out[:, :far] == 0.0)) and step1 < 0.5 * step0
             and float(np.std(np.diff(out[thin.nonzero()]))) < float(np.std(np.diff(sand[thin.nonzero()]))))
    check('plinth_smoothing_clears_the_sheet_and_feathers_its_edge', sm_ok,
          {'dune cells unchanged': bool(np.all(out[top] == sand[top])),
           f'floor bare beyond 3 sigma (columns 0-{far - 1})': bool(np.all(out[:, :far] == 0)),
           'largest step at the sheet edge before / after, m': [round(step0, 2), round(step1, 2)],
           'sheet roughness before / after, m': [round(float(np.std(np.diff(sand[thin.nonzero()]))), 3),
                                                  round(float(np.std(np.diff(out[thin.nonzero()]))), 3)]})
    last = A.refine_winds(A.resolve_params({'kind': 'star', 'refine_winds': 'last', 'wind_rotate_deg': 10.0}))
    last2 = A.refine_winds(A.resolve_params({'kind': 'star', 'refine_winds': 'last2', 'wind_rotate_deg': 10.0}))
    cyc = A.refine_winds(A.resolve_params({'kind': 'star', 'refine_winds': 'cycle'}))
    check('refinement_blows_the_last_season', last == [(278.0, 0.55)] and last2 == [(158.0, 0.75), (278.0, 0.55)]
          and len(cyc) == 3, {"'last'": last, "'last2'": last2, "'cycle'": cyc})
    # the main level takes the refine_* settings, a hero level its hero_* ones where given, the rest falls back
    from eidoblend.terrain.core import levels as L
    pr = A.resolve_params({'kind': 'star', 'refine_winds': 'last', 'refine_iters': 900, 'hero_winds': 'cycle',
                           'hero_block': 150, 'hero_average_iters': 0})
    main = A.refine_settings(pr, L.Level(2, 'main', 0.0, 0.0, 8000.0, 7.8125, 1024))
    hero = A.refine_settings(pr, L.Level(4, 'hero', 0.0, 0.0, 2000.0, 1.953125, 1024))
    pick = lambda name, hero_level: next(v for v in ((pr.get('hero_' + name) if hero_level else None),   # noqa: E731
                                                     pr.get('refine_' + name), pr.get(name)) if v is not None)
    rs_ok = (len(main['winds']) == 1 and main['iters'] == 900 and main['block'] == pick('block', False)
             and main['average_iters'] == pick('average_iters', False) and len(hero['winds']) == 3
             and hero['iters'] == pick('iters', True) and hero['block'] == 150 and hero['average_iters'] == 0
             and hero['smooth_cells'] == main['smooth_cells'] == pr['smooth_cells'])
    check('hero_levels_take_their_own_refinement', rs_ok, {'main': main, 'hero': hero})


def steering(seed=10, steer_deg=25.0, turn_deg=10.0, shape=SHAPE):
    """A Steering on a test grid: three smooth random fields of about unit variance, clipped at +-2."""
    n = np.stack([np.clip(3.0 * T.random_field(shape, -1.0, 1.0, seed=seed + k, smooth=6), -2.0, 2.0)
                  for k in range(3)])
    return A.Steering(n, steer_deg, turn_deg)


def test_steering():
    """The steered wind (Steering): every hop a source picks lies in the gather's box and at a corner of its own
    cell's turned hop, the gather still equals the scatter, each cell's mean hop follows its turned wind, a wind and
    its reverse are turned alike, sand is conserved, and a steering of zero is the unsteered model bit for bit."""
    bed, sand = fields(4)
    st = st_of(bed, sand)
    stg = steering()
    worst, outside, astray, cases = 0.0, 0, 0, 0
    t0 = time.perf_counter()
    for bound in (T.BOUND_OPEN, T.BOUND_PERIODIC, T.BOUND_PINNED):
        for hop in (1.5, 4.7):
            for d in (0.0, 100.0, 215.0, 290.0):
                p = A.params_for({'hop_cells': hop, 'p_lift': 0.3, 'long_factor': 2.0, 'speedup': 0.6,
                                  'lift_boost': 1.0, 'shadow_reach': 6})
                cs, turn = stg.for_wind(float(d))
                u = A.uniforms_for(p, 4.0, float(d) + 7.0, d, 17, bound, turn)    # a gust 7 degrees off its wind
                sh = A.twin_shadow({'st': st, 'wind': cs}, u['dune_shadow'])['outShadow']
                plan = A.twin_activate({'st': st, 'shadow': sh, 'wind': cs}, u['dune_activate'])['outPlan']
                lifted = plan[..., 0] > 0
                vx, vy = plan[..., 1], plan[..., 2]
                (x0, y0), (x1, y1) = u['dune_transport']['uVMin'], u['dune_transport']['uVMax']
                outside += int((lifted & ((vx < x0) | (vx > x1) | (vy < y0) | (vy > y1))).sum())
                g = A.twin_transport({'st': st, 'plan': plan}, u['dune_transport'])['outSt'][..., 1]
                s = A.scatter_step(st, plan, None, int(p['max_hops']), bound)
                worst = max(worst, float(np.abs(g.astype(np.float64) - s).max()))
                hx, hy = u['dune_activate']['uHop']
                c, sn = cs[..., 0], cs[..., 1]
                rest = lifted
                for m in (1.0, 2.0):                                     # the short hop and the long one
                    tx, ty = c * hx * m - sn * hy * m, sn * hx * m + c * hy * m
                    rest = rest & ~((np.abs(vx - tx) < 1.0 + 1e-4) & (np.abs(vy - ty) < 1.0 + 1e-4))
                astray += int(rest.sum())
                cases += 1
    check('steered_hops_inside_the_gather_box', outside == 0 and astray == 0,
          {'cases': cases, 'hops outside the box': outside,
           "hops not at a corner of their own cell's turned hop": astray,
           'seconds': round(time.perf_counter() - t0, 2)})
    check('steered_gather_equals_scatter', worst <= 1e-6 * float(sand.max()),
          {'worst |gather - scatter| m': worst, 'largest sand m': float(sand.max())})
    # each cell's mean hop over many iterations points along its own turned wind
    p = A.params_for({'hop_cells': 3.0, 'p_lift': 1.0, 'shadow_reach': 2})
    flat = st_of(np.zeros(SHAPE, np.float32), np.full(SHAPE, 5.0, np.float32))
    cs, turn = stg.for_wind(40.0)
    ang = np.arctan2(cs[..., 1], cs[..., 0])
    ax, ay, n = np.zeros(SHAPE), np.zeros(SHAPE), 0
    for it in range(60):
        u = A.uniforms_for(p, 4.0, 40.0, it, 5, T.BOUND_PERIODIC, turn)
        sh = A.twin_shadow({'st': flat, 'wind': cs}, u['dune_shadow'])['outShadow']
        plan = A.twin_activate({'st': flat, 'shadow': sh, 'wind': cs}, u['dune_activate'])['outPlan']
        ax += plan[..., 1]
        ay += plan[..., 2]
        n += 1
    base = math.atan2(A.transport_dir(40.0)[1], A.transport_dir(40.0)[0])
    err = np.degrees(np.abs((np.arctan2(ay / n, ax / n) - base - ang + math.pi) % (2 * math.pi) - math.pi))
    check('each_cell_hops_along_its_turned_wind', float(np.percentile(err, 95)) <= 6.0,
          {'turns on the grid, deg': [round(math.degrees(t), 1) for t in turn],
           'p95 |mean hop direction - turned wind|, deg (60 hops a cell)': round(float(np.percentile(err, 95)), 2)})
    a1, a2 = stg.angle(40.0), stg.angle(220.0)
    check('a_wind_and_its_reverse_turn_alike', float(np.abs(a1 - a2).max()) <= 1e-12 and float(np.std(a1)) > 0.05,
          {'max |turn(40) - turn(220)|, rad': float(np.abs(a1 - a2).max()),
           'turn std, deg': round(math.degrees(float(np.std(a1))), 2)})
    sim = A.TwinSim(bed, sand, 4.0, T.BOUND_PERIODIC, {'hop_cells': 3.3, 'shadow_reach': 8}, seed=21, steer=stg)
    sim.run(A.KINDS['star']['winds'], 30, block=5)
    rel = float(sim.st[..., 1].sum(dtype=np.float64) / sand.sum(dtype=np.float64) - 1.0)
    check('steered_sand_mass_conserved', abs(rel) <= 1e-5, {'iterations': sim.it, 'relative change': rel})
    a = A.TwinSim(bed, sand, 4.0, T.BOUND_PERIODIC, {'shadow_reach': 8}, seed=3)
    b = A.TwinSim(bed, sand, 4.0, T.BOUND_PERIODIC, {'shadow_reach': 8}, seed=3,
                  steer=steering(steer_deg=0.0, turn_deg=0.0))
    for s_ in (a, b):
        s_.run([(200.0, 1.0)], 10, block=10)
    check('zero_steering_is_the_unsteered_model', np.array_equal(a.st, b.st))


def _grain(a, cell):
    """The structure tensor of a field's gradient: (the compass trend its features run along, 0..180 degrees: across
    the dominant gradient; coherence 0 isotropic .. 1 every gradient one way)."""
    gy, gx = np.gradient(np.asarray(a, np.float64), float(cell))          # row 0 south: gy is d/dnorth
    jxx, jyy, jxy = float(np.mean(gx * gx)), float(np.mean(gy * gy)), float(np.mean(gx * gy))
    ev, vec = np.linalg.eigh(np.array([[jxx, jxy], [jxy, jyy]]))
    across = math.degrees(math.atan2(vec[0, 1], vec[1, 1]))              # the dominant gradient, compass
    return (across + 90.0) % 180.0, (ev[1] - ev[0]) / max(ev[1] + ev[0], 1e-30)


def test_supply_corridors():
    """The supply drawn out along an axis (stretch_periodic, start_fields' supply_stretch_m): the field keeps its
    mean and spread and stays periodic (the tile's opposite edges join as any two neighbours do), its features run
    along the axis (the gradient's structure tensor: coherent, and across the axis), start_fields uses it only when
    asked, and wind_rotate_deg turns the axis with the winds."""
    from eidoblend.terrain.core import levels as L
    lv = L.Level(0, 'context', -8000.0, -8000.0, 16000.0, 31.25, 512)
    res, ok = {}, True
    sn = A._fbm(lv, 2000.0, 2, 9, lv.side)
    _t0, coh0 = _grain(sn, lv.cell)
    res['unstretched coherence'] = round(coh0, 3)
    for axis in (90.0, 30.0, 155.0):
        st = A.stretch_periodic(sn, lv.cell, 1500.0, axis)
        inner = max(float(np.abs(np.diff(st, axis=0)).max()), float(np.abs(np.diff(st, axis=1)).max()))
        seam = max(float(np.abs(st[0] - st[-1]).max()), float(np.abs(st[:, 0] - st[:, -1]).max()))
        trend, coh = _grain(st, lv.cell)
        off = abs((trend - axis + 90.0) % 180.0 - 90.0)
        good = (abs(float(st.mean()) - float(sn.mean())) <= 1e-9 and abs(float(st.std()) / float(sn.std()) - 1.0)
                <= 1e-9 and seam <= inner and off <= 5.0 and coh >= 0.5 and coh0 <= 0.15)
        ok = ok and good
        res[f'axis {axis:g}'] = dict(trend_deg=round(trend, 1), coherence=round(coh, 3), seam=round(seam, 4),
                                     largest_neighbour_step=round(inner, 4))
    p = A.resolve_params({'kind': 'star', 'supply_wavelength_m': 2000.0, 'supply_stretch_m': 1500.0,
                          'supply_axis_deg': 90.0})
    _b, s1 = A.start_fields(lv, p, 1, period_m=lv.side)
    _b, s0 = A.start_fields(lv, dict(p, supply_stretch_m=0.0), 1, period_m=lv.side)
    _b, s2 = A.start_fields(lv, A.resolve_params({'kind': 'star', 'supply_wavelength_m': 2000.0,
                                                  'supply_stretch_m': 0.0}), 1, period_m=lv.side)
    used = (not np.array_equal(s1, s0)) and np.array_equal(s0, s2)
    pc = A.resolve_params({'kind': 'star', 'supply_wavelength_m': 2000.0, 'supply_var': 0.9, 'supply_cap': 1.3,
                           'seed_frac': 1e-9})
    _b, sc = A.start_fields(lv, pc, 1, period_m=lv.side)
    _b, su = A.start_fields(lv, dict(pc, supply_cap=None), 1, period_m=lv.side)
    capped = (float(sc.max()) <= 1.3 * pc['sand_m'] + 1e-3 and float(su.max()) > 1.6 * pc['sand_m']
              and np.array_equal(sc[su <= 1.3 * pc['sand_m'] - 1e-3], su[su <= 1.3 * pc['sand_m'] - 1e-3]))
    pr = A.resolve_params({'kind': 'star', 'supply_axis_deg': 90.0, 'wind_rotate_deg': 30.0})
    ok = ok and used and capped and abs(pr['supply_axis_deg'] - 120.0) <= 1e-9
    res['start_fields stretches only when asked'] = used
    res['supply_cap 1.3: thickest start sand / sand_m, capped and uncapped'] = [round(float(sc.max()) / pc['sand_m'], 3),
                                                                               round(float(su.max()) / pc['sand_m'], 3)]
    res['axis 90 with the winds turned 30'] = pr['supply_axis_deg']
    check('supply_corridors_run_along_their_axis', ok, res)


def main():
    t0 = time.perf_counter()
    for fn in (test_declarations, test_gather_equals_scatter, test_mass, test_avalanche, test_dither, test_shadow,
               test_determinism, test_growth_pieces, test_steering, test_supply_corridors):
        t = time.perf_counter()
        try:
            fn()
        except Exception:                                          # noqa: BLE001
            check(fn.__name__ + '_ran', False, traceback.format_exc()[-1500:])
        sec = time.perf_counter() - t
        RESULTS.setdefault('seconds_per_test', {})[fn.__name__] = round(sec, 2)
        print(f'  ({fn.__name__}: {sec:.1f} s)', flush=True)
    RESULTS['failed'] = FAILED
    RESULTS['seconds'] = round(time.perf_counter() - t0, 1)
    with open(os.path.join(OUT, 'twin_tests.json'), 'w', encoding='utf-8') as f:
        json.dump(RESULTS, f, indent=1, default=str)
    print(f"[wind_sand twins] {'ALL PASS' if not FAILED else 'FAILED: ' + ', '.join(FAILED)} in {RESULTS['seconds']} s")
    sys.exit(1 if FAILED else 0)


if __name__ == '__main__':
    main()
