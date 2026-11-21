"""Package 11 (karst half): tests of solvers/karst.py and recipes/tower_karst.py. Plain Python (numpy), no Blender.

    python blender/tests/terrain/karst/test_karst.py [name ...]     # all, or the named tests

Writes out/karst/test_results.json (every test's verdict, numbers and seconds). The design's checks for this half
(section 11, row 11): blue-noise spacing and tower profile wall angles; plus the measures beside the Li River
photographs (the plain's towers steep and cliffed, the clusters' cones wooded, pointed, not domed; not one profile
on the plain; a river with water at plain level and gravel bars), the fenglin / fengcong composition, world-space
consistency across levels and windows, a continuous base edge, no terraces nor lattice creases on the hero levels,
the op on core's level plan, the recipe, and the official judge against guilin_karst (judge/, through the radar
chain): every band.
"""
import json
import math
import os
import sys
import time
import traceback

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
TN = os.path.normpath(os.path.join(HERE, '..'))
OUT = os.path.join(TN, 'out', 'karst')
for p in (BLENDER, TN, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from eidoblend.terrain.solvers import karst as K  # noqa: E402

DOMAIN = (-16000.0, -16000.0, 32000.0)
MAIN = (-4000.0, -4000.0, 8000.0)
RESULTS = {}


def record(name, **numbers):
    RESULTS.setdefault(name, {}).update(numbers)


def slope_deg(h, cell):
    gy, gx = np.gradient(np.asarray(h, np.float64), cell)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def one_tower_plan(H=150.0, wall=82.0, kind=1, cone_deg=60.0, girth=0.75, b=0.0, seed=1, ledges=True, **over):
    """A plan holding a single tower at the origin (no cluster, no river, no noise of the footprint): a peak (kind
    1: one cone at cone_deg, its footprint girth x the cone's foot radius) or a spire (kind 0)."""
    base = dict(river=False, lobes_m=0.0, spurs=0.0, fluting_m=0.0, jag=0.0, cluster_cover=0.0, cockpit_fill=0.0,
                apron=0.0, base_m=0.0, base_rough_m=0.0)
    if not ledges:
        base['ledge_cover'] = 0.0
    pr = K.params_for(dict(base, **over))
    plan = K.KarstPlan(seed=seed, domain=(-500.0, -500.0, 1000.0), params=pr, salt=12345, strike=0.0,
                       cluster_threshold=1e9, cluster_band=1.0)
    r0 = H / math.tan(math.radians(cone_deg))
    one = lambda v: np.array([float(v)])                                       # noqa: E731
    plan.x, plan.y, plan.H, plan.F = one(0), one(0), one(H), one(0)
    plan.R, plan.wall, plan.kind, plan.floor = one(girth * r0), one(wall), np.array([kind], np.int8), one(-np.inf)
    plan.B, plan.reach = one(0), one(0)
    plan.elong, plan.axis, plan.lean, plan.lean_dir = one(0), one(0), one(0), one(0)
    plan.cluster, plan.interior, plan.spur = one(0), one(0), np.zeros((1, 4), complex)
    KM = int(pr['peaks_max'])
    nan = np.full((1, KM), np.nan)
    plan.npk = np.array([1], np.int64)
    plan.pk_dx, plan.pk_dy, plan.pk_h, plan.pk_r0 = nan.copy(), nan.copy(), nan.copy(), nan.copy()
    plan.pk_b, plan.pk_e, plan.pk_axis = nan.copy(), nan.copy(), nan.copy()
    plan.pk_dx[0, 0] = plan.pk_dy[0, 0] = 0.0
    plan.pk_h[0, 0], plan.pk_r0[0, 0], plan.pk_b[0, 0] = H, r0, b
    plan.pk_e[0, 0], plan.pk_axis[0, 0] = 0.0, 0.0
    D, Z, D0 = K.wall_table(np.random.default_rng(seed), H, wall, pr)
    plan.wall_D, plan.wall_Z, plan.wall_D0 = [D], [Z], [D0]
    return plan


# ------------------------------------------------------------------------------------------------- blue noise
def test_blue_noise_spacing():
    """Poisson-disc: no pair closer than the radius; near-maximal (little ground farther than r from every point);
    irregular (nearest-neighbour spread, no preferred lattice direction); a variable radius sets the density."""
    r = 100.0
    x, y, _ = K.poisson_disc(3, 0.0, 0.0, 3000.0, 3000.0, lambda a, b: np.full(np.shape(a), r), r, r)
    P = np.stack([x, y], 1)
    d = np.sqrt(((P[:, None] - P[None]) ** 2).sum(-1))
    np.fill_diagonal(d, np.inf)
    nn = d.min(1)
    assert nn.min() >= r * (1 - 1e-9), f'pair closer than r: {nn.min():.2f}'
    g = np.stack(np.meshgrid(np.arange(25, 2975, 10.0), np.arange(25, 2975, 10.0)), -1).reshape(-1, 2)
    gap = np.empty(len(g))
    for s in range(0, len(g), 4096):
        gap[s:s + 4096] = np.sqrt(((g[s:s + 4096, None] - P[None]) ** 2).sum(-1)).min(1)
    uncovered = float((gap > r).mean())
    assert uncovered < 0.03, f'not maximal: {uncovered:.3f} of the ground is farther than r from every point'
    cv = float(nn.std() / nn.mean())
    assert 0.04 < cv < 0.35, f'nearest-neighbour spread {cv:.3f}: a lattice (~0) or clumping (~0.5)'
    angs = []
    for sd in (3, 13, 23, 33):
        xx, yy, _ = K.poisson_disc(sd, 0.0, 0.0, 3000.0, 3000.0, lambda a, b: np.full(np.shape(a), r), r, r)
        PP = np.stack([xx, yy], 1)
        dd = np.sqrt(((PP[:, None] - PP[None]) ** 2).sum(-1))
        np.fill_diagonal(dd, np.inf)
        j = np.argmin(dd, 1)
        angs.append(np.arctan2(yy[j] - yy, xx[j] - xx))
    th = np.concatenate(angs)
    a4 = float(abs(np.exp(4j * th).mean()))
    a2 = float(abs(np.exp(2j * th).mean()))
    lim = 3.0 / math.sqrt(th.size)
    assert a4 < lim and a2 < lim, f'directional bias: 4-fold {a4:.3f}, 2-fold {a2:.3f} (limit {lim:.3f})'
    x2, y2, _ = K.poisson_disc(4, 0.0, 0.0, 4000.0, 2000.0, lambda a, b: np.where(a < 2000, 100.0, 250.0), 100.0,
                               250.0)
    west, east = int((x2 < 2000).sum()), int((x2 >= 2000).sum())
    ratio = west / max(east, 1)
    assert 4.0 < ratio < 8.5, f'density ratio {ratio:.2f}, expected about (250/100)^2 = 6.25'
    record('test_blue_noise_spacing', points=int(len(x)), nn_min_m=float(nn.min()), nn_median_m=float(np.median(nn)),
           nn_cv=cv, uncovered_frac=uncovered, harmonic_4fold=a4, harmonic_2fold=a2, harmonic_limit=lim,
           density_ratio_100_vs_250=ratio)


def test_plan_spacing_and_clusters():
    """The plan's centres: inside the clusters about spacing_m apart (median nearest neighbour within 25 %), much
    sparser on the plain; the main tile's cluster share is cluster_cover; the main tile holds a few hundred towers
    of mixed kinds, not the review's 1,100 alike."""
    plan = K.plan_karst(7, DOMAIN, {}, via=(0, 0), main=MAIN)
    inside = (np.abs(plan.x) < 4000) & (np.abs(plan.y) < 4000)
    x, y, m = plan.x[inside], plan.y[inside], plan.cluster[inside]
    P = np.stack([x, y], 1)
    d = np.sqrt(((P[:, None] - P[None]) ** 2).sum(-1))
    np.fill_diagonal(d, np.inf)
    nn = d.min(1)
    cl = m > 0.9
    pl = m < 0.1
    sp = plan.params['spacing_m']
    nn_cl = float(np.median(nn[cl]))
    assert abs(nn_cl / sp - 1.0) < 0.25, f'cluster nearest neighbour {nn_cl:.0f} m vs spacing {sp:.0f} m'
    g = np.linspace(-3990, 3990, 200)
    GX, GY = np.meshgrid(g, g)
    cover = float((K._cluster(plan, GX, GY)[0] > 0.5).mean())
    assert abs(cover - plan.params['cluster_cover']) < 0.05, f'main-tile cover {cover:.2f}'
    dens_cl = cl.sum() / max((K._cluster(plan, GX, GY)[0] > 0.9).mean() * 64.0, 1e-6)
    dens_pl = pl.sum() / max((K._cluster(plan, GX, GY)[0] < 0.1).mean() * 64.0, 1e-6)
    assert dens_pl < 0.2 * dens_cl, f'plain density {dens_pl:.2f}/km2 vs cluster {dens_cl:.2f}/km2'
    assert int(inside.sum()) < 950, f'{int(inside.sum())} towers in the main tile'
    record('test_plan_spacing_and_clusters', towers_in_main=int(inside.sum()), cluster_nn_median_m=nn_cl,
           main_cover=cover, density_cluster_per_km2=float(dens_cl), density_plain_per_km2=float(dens_pl))


# ----------------------------------------------------------------------------------------------- the profile
def test_profile_functions():
    """cone_profile: 1 at the apex, 0 at the foot, monotone for convexities -0.35..0.3; its slope at the apex is
    (1 - b) and at the foot (1 + b) times the mean (pointed: no flat top). wall_table: distance and height rise
    together; the wall bands stand at the wall's angle (+-2 degrees), the ledges are gentler, the ledge-free table
    is all wall; the table reaches past 1.3 x the height."""
    x = np.linspace(0, 1, 2001)
    for b in (-0.35, -0.1, 0.0, 0.15, 0.3):
        f = K.cone_profile(x, b)
        assert abs(f[0] - 1) < 1e-12 and abs(f[-1]) < 1e-12 and np.all(np.diff(f) < 0)
        s0 = -(f[1] - f[0]) / (x[1] - x[0])
        s1 = -(f[-1] - f[-2]) / (x[1] - x[0])
        assert abs(s0 - (1 - b)) < 2e-3 and abs(s1 - (1 + b)) < 2e-3, (b, s0, s1)
    pr = K.params_for({})
    D, Z, D0 = K.wall_table(np.random.default_rng(3), 150.0, 82.0, pr)
    assert np.all(np.diff(D) > 0) and np.all(np.diff(Z) > 0) and np.all(np.diff(D0) > 0)
    assert Z[-1] >= 1.3 * 150.0
    ang = np.degrees(np.arctan(np.diff(Z) / np.diff(D)))
    ang0 = np.degrees(np.arctan(np.diff(Z) / np.diff(D0)))
    walls, ledges = ang[1::2], ang[2::2]
    assert np.all(np.abs(walls - 82.0) <= 2.0 + 1e-9), walls
    assert np.all((ledges >= 40.0 - 1e-9) & (ledges <= 60.0 + 1e-9)), ledges
    assert np.all(ang0[1:] >= 80.0 - 1e-9)
    overall = math.degrees(math.atan(Z[-1] / D[-1]))
    assert overall >= 76.0, f'the ledged wall averages {overall:.1f} degrees'
    record('test_profile_functions', wall_bands_deg=[round(float(walls.min()), 1), round(float(walls.max()), 1)],
           ledges_deg=[round(float(ledges.min()), 1), round(float(ledges.max()), 1)],
           ledged_wall_overall_deg=round(overall, 1))


def test_tower_walls_and_summits():
    """A rasterised tower at 0.5 m (no noise): the wall from its foot up to where the cone takes over stands at its
    angle (the chord between 15 % and 85 % of the wall's height within 4 degrees, ledges off); the summit is pointed
    (the apex within 2 m of the tower's height and the mean slope over the 10 m from it still over 45 degrees: no
    dome); the foot is abrupt (from the plain to 5 m up within 2 m of ground distance)."""
    rows = {}
    for wall, cone, girth, b in ((82.0, 62.0, 0.7, -0.2), (86.0, 72.0, 0.85, 0.2), (78.0, 56.0, 0.65, 0.0)):
        plan = one_tower_plan(H=150.0, wall=wall, cone_deg=cone, girth=girth, b=b, ledges=False)
        out = K.evaluate(plan, -160.0, -160.0, 0.5, 640)
        h = out['h'].astype(np.float64) - out['plain'].astype(np.float64)
        top = h.max()
        assert abs(top - 150.0) < 2.0, f'summit {top:.1f} m, asked 150'
        R = float(plan.R[0])
        r0 = float(plan.pk_r0[0, 0])
        z_edge = 150.0 * float(K.cone_profile(R / r0, b))
        rr = np.arange(0, 160, 0.25)
        wall_s, near_apex, foot = [], [], []
        for a in np.radians(np.arange(16) * 22.5):
            xs, ys = rr * math.cos(a), rr * math.sin(a)
            i = np.clip(((xs + 160) / 0.5 - 0.5).astype(int), 0, 639)
            j = np.clip(((ys + 160) / 0.5 - 0.5).astype(int), 0, 639)
            z = h[j, i]
            r_lo = rr[np.argmax(z < 0.15 * z_edge)]
            r_hi = rr[np.argmax(z < 0.85 * z_edge)]
            wall_s.append(math.degrees(math.atan(0.7 * z_edge / max(r_lo - r_hi, 1e-6))))
            k = int(np.argmin(np.abs(rr - 10.0)))
            near_apex.append(math.degrees(math.atan((z[0] - z[k]) / 10.0)))
            r5 = rr[np.argmax(z < 5.0)]
            r0g = rr[np.argmax(z < 0.05)]
            foot.append(r0g - r5)
        med = float(np.median(wall_s))
        assert abs(med - wall) < 4.0, f'wall {med:.1f} deg, asked {wall}'
        assert float(np.median(near_apex)) > 45.0, f'apex {np.median(near_apex):.1f} deg: a dome'
        assert float(np.median(foot)) < 2.0, f'the foot spreads {np.median(foot):.1f} m'
        rows[f'wall_{wall:.0f}'] = dict(measured_deg=round(med, 1), apex_10m_deg=round(float(np.median(near_apex)), 1),
                                        foot_spread_m=round(float(np.median(foot)), 2), wall_height_m=round(z_edge, 1))
    record('test_tower_walls_and_summits', **rows)


def test_plan_kinds():
    """In the default plan. Cliffed forms stand where the plain undercuts a tower's foot: on the plain spires, peaks
    and blocks all present (each over 5 %), none over 70 % (not one profile), and most of the plain's and the
    cluster edges' towers (over 60 %) carry a collapse scarp; deep inside a cluster only cones (no spire, no block),
    26-40 degrees, no random scarp (0.35-0.6 deep): at most the edge scarp's taper, a third of that. The walls
    70-89 degrees with p10 >= 76; the plain's peaks' cones
    58-70 and the spires' 70-80 degrees; a tower's further peaks within 3 degrees of its own cone; heights spread
    (p90 / p10 >= 2.5); the plain's tallest towers massifs (of its towers over twice the median height at most 10 %
    single cones: a 400 m single cone on the plain read as a pyramid); the ribs never folding a cone (each cone's sum
    of m |a_m| under 1)."""
    plan = K.plan_karst(7, DOMAIN, {}, via=(0, 0), main=MAIN)
    deep = K.cone_weight(plan.cluster, plan.interior)
    on_plain = plan.cluster < 0.3
    shares = np.bincount(plan.kind[on_plain].astype(int), minlength=3) / max(int(on_plain.sum()), 1)
    assert np.all(shares > 0.05) and shares.max() < 0.7, shares
    inner = deep >= 0.9
    assert inner.sum() > 100 and np.all(plan.kind[inner] == 1), np.bincount(plan.kind[inner], minlength=3)
    assert plan.wall.min() >= 70.0 - 1e-9 and plan.wall.max() <= 89.0 + 1e-9 and np.percentile(plan.wall, 10) >= 76.0
    ang = np.degrees(np.arctan(plan.pk_h[:, 0] / plan.pk_r0[:, 0]))
    sp, pk = ang[plan.kind == 0], ang[plan.kind == 1]
    assert sp.min() >= 70.0 - 1e-6 and sp.max() <= 80.0 + 1e-6, (sp.min(), sp.max())
    # (the plain's peaks 58-70 degrees; deep inside a cluster the broad fengcong cones, 26-36 and up toward the
    # plain's angle at the cluster's edge)
    pk_plain = ang[(plan.kind == 1) & on_plain]
    assert pk_plain.min() >= 58.0 - 1e-6 and pk_plain.max() <= 70.0 + 1e-6, (pk_plain.min(), pk_plain.max())
    assert pk.min() >= 26.0 - 1e-6 and pk.max() <= 70.0 + 1e-6, (pk.min(), pk.max())
    pk_in = ang[inner]
    assert pk_in.max() <= 40.0, f'a cone deep inside a cluster at {pk_in.max():.1f} degrees'
    more = np.isfinite(plan.pk_h[:, 1])
    a2 = np.degrees(np.arctan(plan.pk_h[more, 1] / plan.pk_r0[more, 1]))
    assert np.abs(a2 - ang[more]).max() <= 3.0 + 1e-6, np.abs(a2 - ang[more]).max()
    Ht = plan.H + plan.F
    spread = float(np.percentile(Ht, 90) / np.percentile(Ht, 10))
    assert spread >= 2.5, f'heights p90 / p10 {spread:.2f}'
    tall = (Ht > 2.0 * K.DEFAULTS['median_height_m']) & on_plain
    single = tall & (plan.npk == 1) & (plan.kind != 2)
    single_share = float(single.sum() / max(tall.sum(), 1))
    assert single_share <= 0.10, f'{single_share:.0%} of the plain\'s tall towers are single cones'
    scarped = (plan.scarp[:, :, 2] > 0).any(1)
    with_scarp = float(scarped[deep < 0.5].mean())
    assert with_scarp >= 0.6, f'{with_scarp:.0%} of the plain\'s and the edges\' towers have a scarp'
    inner_depth = float(plan.scarp[inner, :, 2].max())
    assert inner_depth <= K.DEFAULTS['scarp_depth'][1] / 3.0, f'a scarp {inner_depth:.2f} deep inside a cluster'
    fold = (np.abs(plan.pk_rib) * K.RIB_ORDERS[None, None, :]).sum(-1).max()
    assert fold < 1.0, f'a cone whose ribs fold it: sum m |a_m| = {fold:.2f}'
    record('test_plan_kinds', plain_shares_spire_peak_block=shares.round(3).tolist(), inner_cones=int(inner.sum()),
           inner_cone_deg_p50_max=[round(float(np.median(pk_in)), 1), round(float(pk_in.max()), 1)],
           wall_p10_p50_p90=np.percentile(plan.wall, [10, 50, 90]).round(1).tolist(),
           height_p10_p50_p90=np.percentile(Ht, [10, 50, 90]).round(1).tolist(), height_spread=round(spread, 2),
           plain_tall_single_cone_share=round(single_share, 3), plain_edge_towers_with_scarps=round(with_scarp, 3),
           inner_scarp_depth_max=round(inner_depth, 3), rib_budget_max=round(float(fold), 3))


def test_tower_slopes():
    """The towers the Li River photographs show, steep and wooded to their tops with bare rock on the sheerest
    faces: fourteen towers of the default fenglin (seed 7) standing on the plain or at a cluster's edge, each
    evaluated at 1 m cells: their cells (a tower's wall or summit, or its massif body's wall, 15 m and more above the
    plain; not a body's skirt nor a cockpit's soil floor) have a median slope of 55 degrees or more and 10-30 % of
    them stand steeper than 70 (the cliffed feet and scarps; an earlier review measured 55 and 8 % on rounded towers
    it rejected, and 35 % over 70 stood bare grey from foot to top). And deep inside a cluster (a 2 km window at the
    tile's centre, 2 m cells), the fengcong cones are wooded cones, not domes and not walls: their cells' median
    slope 25-45 degrees, under 5 % of their cells over 60 degrees, and each cone, measured from its own foot (the
    col or the base it rises from) to its summit, no gentler in its upper 40 % than in its lower 60 % at the median
    over the cones (a dome's top is gentler). (Pooled over the window by the height above the plain, the two medians
    held the visible upper halves of cones of every size and stood equal within 0.05 degrees, so the noise of the
    ribs and knobs decided that check.)"""
    plan = K.plan_karst(7, DOMAIN, {}, via=(0, 0), main=MAIN)
    inm = (np.abs(plan.x) < 3500) & (np.abs(plan.y) < 3500)
    sel = np.nonzero(inm & ((plan.cluster < 0.3) | (plan.interior < 0.2)) & (plan.H + plan.F > 40))[0]
    pick = np.random.default_rng(3).choice(sel, size=min(14, sel.size), replace=False)
    walls = []
    for t in pick:
        side = 2.0 * plan.R[t] * (1 + plan.elong[t]) * 1.6 + 60.0
        n = int(side)
        out = K.evaluate(plan, plan.x[t] - side / 2, plan.y[t] - side / 2, 1.0, n, ss=1)
        h = out['h'].astype(np.float64)
        tw = (out['tower_id'] == t) & (h - out['plain'] > 15.0)
        if tw.sum() > 50:
            walls.append(slope_deg(h, 1.0)[tw])
    assert len(walls) >= 8, f'only {len(walls)} towers on the plain or at a cluster edge'
    a = np.concatenate(walls)
    med = float(np.median(a))
    over70 = float((a > 70.0).mean())
    assert med >= 55.0 and 0.10 <= over70 <= 0.30, f'tower cells: median {med:.1f} deg, {over70:.0%} over 70'
    out = K.evaluate(plan, -1000.0, -1000.0, 2.0, 1000)
    h = out['h'].astype(np.float64)
    s = slope_deg(h, 2.0)
    tid = out['tower_id']
    tw = (tid >= 0) & (h - out['plain'] > 15.0)
    up_h = (h - out['plain'])
    top = np.zeros(plan.count)
    np.maximum.at(top, tid[tw], up_h[tw])
    foot = np.full(plan.count, np.inf)
    np.minimum.at(foot, tid[tw], up_h[tw])
    rel = np.where(tw, up_h / np.maximum(top[np.maximum(tid, 0)], 1.0), 0.0)
    up_med, low_med = float(np.median(s[tw & (rel >= 0.6)])), float(np.median(s[tw & (rel < 0.6)]))
    all_med = float(np.median(s[tw]))
    over60 = float((s[tw] > 60.0).mean())
    diffs = []
    for t in np.unique(tid[tw]):
        m = tw & (tid == t)
        if m.sum() < 400:                       # 1600 m2: a cone the window holds, not a sliver at its edge
            continue
        r = (up_h[m] - foot[t]) / max(top[t] - foot[t], 1.0)
        if (r >= 0.6).sum() >= 30 and (r < 0.6).sum() >= 30:
            diffs.append(float(np.median(s[m][r >= 0.6]) - np.median(s[m][r < 0.6])))
    assert 25.0 <= all_med <= 45.0, f'the cluster cones: median {all_med:.1f} deg'
    assert over60 < 0.05, f'{over60:.1%} of the cluster cones\' cells over 60 degrees (walls inside a cluster)'
    assert len(diffs) >= 20, f'only {len(diffs)} cones held by the window'
    cone_diff = float(np.median(diffs))
    assert cone_diff >= 0.0, f'the cones\' upper 40 % stands {-cone_diff:.1f} deg gentler than their lower 60 % (domed)'
    record('test_tower_slopes', towers=len(walls), median_slope_deg=round(med, 1), share_over_70=round(over70, 3),
           share_over_80=round(float((a > 80.0).mean()), 3), cluster_median_deg=round(all_med, 1),
           cluster_upper_median_deg=round(up_med, 2), cluster_lower_median_deg=round(low_med, 2),
           cones=len(diffs), cone_upper_minus_lower_deg=round(cone_diff, 2),
           cones_steeper_on_top=round(float(np.mean(np.array(diffs) >= 0.0)), 2),
           cluster_share_over_60=round(over60, 3))


# ------------------------------------------------------------------------------ world space and the levels
def test_world_space_windows():
    """The same cells evaluated as part of a bigger window and of a smaller one agree (every input is a function of
    world position): p99 |dh| <= 0.05 m, max <= 0.5 m (smooth fields are interpolated on window-aligned lattices;
    the cockpit fill is left out here because its depressions are found per window)."""
    plan = K.plan_karst(11, DOMAIN, {'cockpit_fill': 0.0}, via=(0, 0), main=MAIN)
    big = K.evaluate(plan, -1024.0, -1024.0, 4.0, 512)['h']
    small = K.evaluate(plan, -512.0, -512.0, 4.0, 256)['h']
    d = np.abs(big[128:384, 128:384].astype(np.float64) - small)
    assert np.percentile(d, 99) <= 0.05 and d.max() <= 0.5, f'p99 {np.percentile(d, 99):.3f} max {d.max():.3f}'
    record('test_world_space_windows', dh_p99_m=float(np.percentile(d, 99)), dh_max_m=float(d.max()))


def test_parent_child_levels():
    """A child level (half the cell) box-averaged to its parent's cells matches the parent: mean |dh| <= 0.8 m,
    p99 <= 12 m (the child resolves finer lobes, ledges and sharper walls; no tower moves)."""
    plan = K.plan_karst(7, DOMAIN, {}, via=(0, 0), main=MAIN)
    parent = K.evaluate(plan, -2048.0, -2048.0, 8.0, 512)['h'].astype(np.float64)
    child = K.evaluate(plan, -1024.0, -1024.0, 4.0, 512)['h'].astype(np.float64)
    down = child.reshape(256, 2, 256, 2).mean(axis=(1, 3))
    d = np.abs(down - parent[128:384, 128:384])
    assert d.mean() <= 0.8 and np.percentile(d, 99) <= 12.0, f'mean {d.mean():.2f} p99 {np.percentile(d, 99):.2f}'
    record('test_parent_child_levels', dh_mean_m=float(d.mean()), dh_p99_m=float(np.percentile(d, 99)))


def test_window_shift():
    """The same world cells in two windows that differ by whole cells come out alike (h, bed, deposit, talus within
    1e-6 of their ranges), at the main level's 7.8125 m cells (2 x 2 subsamples), a hero level's 1 m and an off-grid
    0.49 m window. (The tower loop's window-local float32 metres rounded differently wherever the window started: a
    shift moved bed and deposit by up to 6e-5 of their ranges, talus by 2.3e-4.) The cockpit floors are left out:
    outside the main tile a window finds its own."""
    plan = K.plan_karst(1, DOMAIN, {}, via=(0, 0), main=MAIN)
    worst = {}
    for x0, y0, cell, n, (i, j) in ((-2000.0, -2000.0, 7.8125, 256, (5, 2)), (-1200.0, 300.0, 1.0, 384, (7, 3)),
                                    (-700.3, -200.1, 0.48828125, 384, (11, 5))):
        a = K.evaluate(plan, x0, y0, cell, n, fill=False)
        b = K.evaluate(plan, x0 + i * cell, y0 + j * cell, cell, n, fill=False)
        for k in ('h', 'bed', 'deposit', 'talus'):
            A = a[k][j:, i:].astype(np.float64)
            d = float(np.abs(A - b[k][:n - j, :n - i]).max()) / max(float(np.ptp(A)), 1e-6)
            worst[f'{cell:g}m_{k}'] = d
            assert d <= 1e-6, f'{k} at {cell:g} m moved by {d:.2e} of its range with the window'
    record('test_window_shift', max_change_of_range=worst)


def test_base_edge_continuous():
    """The common base's soil thins continuously as the base rises out of the plain, so a rounding difference in the
    base moves the rock and the soil by a rounding difference: the base's height times 1 + 2e-6 moves h, bed and
    deposit by under 1 mm on 31.25 m and 15.625 m levels (switched on where the base stood 0.5 m up, the rock and
    the soil stepped by alluvium_m + 0.5 m along that contour: one flipped subsample moved a cell's bed 3.1 m). And
    across the base's edge the soil changes smoothly: neighbouring cells where the base is 0-12 m up differ in
    deposit by at most 12 m x (their base heights' difference / 12 m) x 1.5 + 0.5 m."""
    plan = K.plan_karst(1, DOMAIN, {}, via=(0, 0), main=MAIN)
    orig = K._plinth_of
    moved = {}
    for x0, cell, n in ((-2000.0, 31.25, 128), (-1000.0, 15.625, 128)):
        a = K.evaluate(plan, x0, x0, cell, n, fill=False)
        K._plinth_of = lambda p, X, Y: orig(p, X, Y) * (1.0 + 2e-6)
        try:
            b = K.evaluate(plan, x0, x0, cell, n, fill=False)
        finally:
            K._plinth_of = orig
        for k in ('h', 'bed', 'deposit'):
            d = float(np.abs(a[k].astype(np.float64) - b[k]).max())
            moved[f'{cell:g}m_{k}'] = d
            assert d < 1e-3, f'{k} at {cell:g} m moved {d:.3f} m'
    # the soil across the base's edge, on a level at 1 cell = 1 subsample, the plain and the base alone (the towers
    # moved out of the window: their rock, buried under the alluvium past their feet, rightly thins the soil over it),
    # off the river: the soil's thickness changes by at most 1.5 x the base's rise between two cells, the
    # smoothstep's steepest, plus 5 cm
    import copy
    bare = copy.copy(plan)
    bare.x = plan.x + 1.0e7
    bare.floors = None
    G = K._Grid(-1000.0, -1000.0, 4.0, 500, 1)
    pm = G.smooth(lambda X, Y: K._plinth_of(plan, X, Y) * K._base_membership(plan, X, Y), 240.0)
    out = K.evaluate(bare, -1000.0, -1000.0, 4.0, 500, ss=1, fill=False)
    dep = out['deposit'].astype(np.float64)
    open_ = (out['water'] <= 0.0) & (out['h'] >= out['plain'] - 0.01)
    al = plan.params['alluvium_m']
    edge = (np.minimum(pm[:, 1:], pm[:, :-1]) < al) & (np.maximum(pm[:, 1:], pm[:, :-1]) > 0.0) & \
        open_[:, 1:] & open_[:, :-1]
    step = np.abs(np.diff(dep, axis=1))[edge]
    bound = 1.5 * np.abs(np.diff(pm, axis=1))[edge] + 0.05
    worst = float((step - bound).max()) if step.size else -1.0
    assert step.size > 50, f'only {step.size} cell pairs along the base\'s edge'
    assert worst <= 0.0, f'the soil steps {worst:.2f} m past its bound across the base\'s edge'
    record('test_base_edge_continuous', moved_m=moved, edge_pairs=int(step.size),
           edge_soil_step_max_m=round(float(step.max()), 3))


def test_cockpit_floors_meet_their_ground():
    """A cockpit's soil floor never stands above the ground beside it: on a hero level (1 m cells, a 600 m window under
    the plain_fields camera of seed 1), no pair of neighbouring cells jumps by over 2 m where the unfilled ground does
    not. (The floor map is found at 10 m: a basin it saw closed opened at 1 m through a narrower gap, and its floor ran
    on over the lower ground to end in steps of 2-28 m along the map's grid: 106 such pairs here.)"""
    plan = K.plan_karst(1, DOMAIN, {}, via=(0, 0), main=MAIN)
    a = K.evaluate(plan, 3243.0, -1632.0, 1.0, 600, fill=False)['h'].astype(np.float64)
    b = K.evaluate(plan, 3243.0, -1632.0, 1.0, 600)['h'].astype(np.float64)
    made = sum(int(((np.abs(np.diff(b, axis=ax)) - np.abs(np.diff(a, axis=ax))) > 2.0).sum()) for ax in (0, 1))
    filled = float((b - a > 0.05).mean())
    assert made == 0, f'{made} neighbour pairs where a soil floor steps over 2 m above its ground'
    record('test_cockpit_floors_meet_their_ground', fill_steps=made, filled_share=round(filled, 4))


def test_no_terraces_on_hero_levels():
    """The forested summit cones carry no terraces (the Li River photographs; benches every 13 m on the hero levels
    banded the towers green and grey, which the main level's height did not have): a lone peak at 0.5 m cells (no
    ledges, knobs, ribs or fluting), along 16 rays down its cone from 2 m off the apex to 15 m above its wall's brow,
    departs from its own 20 m running mean by at most 0.15 m rms (the cone's own curvature leaves 0.07; the benches
    made about 0.9 m)."""
    plan = one_tower_plan(H=150.0, wall=82.0, cone_deg=60.0, girth=0.7, b=0.1, ledges=False, peak_rough=0.0)
    out = K.evaluate(plan, -160.0, -160.0, 0.5, 640)
    h = out['h'].astype(np.float64) - out['plain'].astype(np.float64)
    R, r0 = float(plan.R[0]), float(plan.pk_r0[0, 0])
    z_edge = 150.0 * float(K.cone_profile(R / r0, 0.1))
    rr = np.arange(2.0, 160.0, 0.5)
    res = []
    for a in np.radians(np.arange(16) * 22.5):
        # bilinear along the ray (nearest cells drew a staircase of +-0.6 m on a 60 degree cone)
        fi = np.clip((rr * math.cos(a) + 160) / 0.5 - 0.5, 0.0, 638.999)
        fj = np.clip((rr * math.sin(a) + 160) / 0.5 - 0.5, 0.0, 638.999)
        i, j = fi.astype(int), fj.astype(int)
        ti, tj = fi - i, fj - j
        z = ((h[j, i] * (1 - ti) + h[j, i + 1] * ti) * (1 - tj) + (h[j + 1, i] * (1 - ti) + h[j + 1, i + 1] * ti) * tj)
        cone = z > z_edge + 15.0                   # (the 20 m window kept clear of the brow's rounded corner)
        z = z[:np.argmin(cone) if not cone.all() else cone.size]
        if z.size < 80:
            continue
        run = np.convolve(z, np.ones(41) / 41.0, mode='valid')
        res.append(float(np.sqrt(np.mean((z[20:-20] - run) ** 2))))
    assert len(res) >= 12, f'only {len(res)} rays down the cone'
    worst = max(res)
    assert worst <= 0.15, f'the cone departs from its running mean by {worst:.2f} m rms: terraces'
    record('test_no_terraces_on_hero_levels', rays=len(res), rms_m_max=round(worst, 4))


def test_no_lattice_creases_on_hero_levels():
    """The towers' flanks carry no grid of creases on the hero levels: on 1 m cells (the 600 m window under the
    plain_fields camera of seed 1), along each axis and for every lattice step the smooth world fields are sampled at
    here (2, 3, 5 and 7 cells), the slope changes from cell to cell as much at one phase of the step as at any other
    (the medians of the phases within 1.4 of each other, on tower cells over 15 m above the plain). (The fields were
    interpolated bilinearly, their slope jumping at every lattice line: the cones' jitter, scaled by the distance
    from an apex, stood a crease every 5 m, its slope change 20 times the flank's own between them.)"""
    plan = K.plan_karst(1, DOMAIN, {}, via=(0, 0), main=MAIN)
    x0, y0 = 3243.0, -1632.0
    out = K.evaluate(plan, x0, y0, 1.0, 600, fill=False)
    h = out['h'].astype(np.float64)
    tower = (out['tower_id'] >= 0) & (h - out['plain'] > 15.0)
    ratios = {}
    for k in (2, 3, 5, 7):
        for ax, origin in ((1, x0), (0, y0)):
            jump = np.abs(np.diff(h, n=2, axis=ax))
            m = tower[:, 1:-1] if ax == 1 else tower[1:-1, :]
            phase = (np.arange(jump.shape[ax]) + 1 + int(origin)) % k
            sel = (lambda p: (slice(None), phase == p)) if ax == 1 else (lambda p: (phase == p, slice(None)))
            meds = [float(np.median(jump[sel(p)][m[sel(p)]])) for p in range(k)]
            ratios[f'{k}_{"x" if ax == 1 else "y"}'] = round(max(meds) / max(min(meds), 1e-9), 3)
    worst = max(ratios, key=ratios.get)
    assert ratios[worst] <= 1.4, f'creases every {worst} cells: a phase changes slope {ratios[worst]:.1f} x as much'
    record('test_no_lattice_creases_on_hero_levels', tower_cells=int(tower.sum()), phase_ratio=ratios)


def test_determinism():
    """The same seed gives the same surface, bit for bit; another seed another surface."""
    a = K.evaluate(K.plan_karst(3, DOMAIN, {}, via=(0, 0), main=MAIN), -500.0, -500.0, 8.0, 128)['h']
    b = K.evaluate(K.plan_karst(3, DOMAIN, {}, via=(0, 0), main=MAIN), -500.0, -500.0, 8.0, 128)['h']
    c = K.evaluate(K.plan_karst(4, DOMAIN, {}, via=(0, 0), main=MAIN), -500.0, -500.0, 8.0, 128)['h']
    assert np.array_equal(a, b)
    assert np.abs(a - c).max() > 10.0


# ------------------------------------------------------------------------------------------ the composition
def _depressions(h, cell):
    from eidoblend.terrain.core import metrics as M
    frac, count, thr, depth = M.depressions(h, cell)
    return frac, count, thr, depth


def test_fenglin_composition():
    """Default fenglin at 16 m over the main tile: a plain (slope < 5 and below the median height) of 0.17-0.36 of
    the tile, a river with water and no rock in it, closed depressions (cockpits, poljes) with flat floors (the
    judge's rule: >= 50 % of their lower half under 8 degrees) over >= 80 % of their area."""
    plan = K.plan_karst(7, DOMAIN, {}, via=(0, 0), main=MAIN)
    out = K.evaluate(plan, -4000.0, -4000.0, 16.0, 500)
    h = out['h'].astype(np.float64)
    s = slope_deg(h, 16.0)
    plain = float(((s < 5.0) & (h < np.median(h))).mean())
    assert 0.17 <= plain <= 0.36, f'plain fraction {plain:.3f}'
    wet = out['water'] > 0.5
    assert wet.mean() > 0.003, 'no river in the main tile'
    assert np.all(h[wet] <= out['plain'][wet] + 0.01), 'rock in the river channel'
    frac, count, thr, depth = _depressions(h + out['water'], 16.0)
    from eidoblend.terrain.core import metrics as M
    lab, n = M.label(depth > 1e-6)
    flat_area = bowl_area = 0
    for k in range(1, n + 1):
        cells = lab == k
        dk = depth[cells]
        if dk.max() <= thr:
            continue
        low = dk >= 0.5 * dk.max()
        if (s[cells][low] < 8.0).mean() >= 0.5:
            flat_area += cells.sum()
        else:
            bowl_area += cells.sum()
    share = flat_area / max(flat_area + bowl_area, 1)
    assert share >= 0.8, f'flat-floored share of the closed depressions {share:.2f}'
    record('test_fenglin_composition', plain_frac=plain, river_frac=float(wet.mean()), depression_frac=frac,
           depression_count=count, flat_floored_share=float(share))


def test_cluster_massifs():
    """The review's "packed shoulder to shoulder in even clusters ... termite mounds": a cluster stands as one massif
    with its peaks on it, not as separate cones on a low plain. Default fenglin, seed 1, the main tile at 8 m: inside
    the clusters (membership over 0.7) at most 30 % of the ground lies under 30 m above the plain (separate cones on
    a 25 m base left 52 %; Guilin's 30 m radar tile holds 44 % of its whole area 50 m and more up), and between
    neighbouring cluster towers the lowest ground on the straight line joining them stands at 35-80 % of the lower
    one's height at the median (cols high on the massif, not plain-level gaps: 20 % before the bodies; not a plateau
    with knobs on it either)."""
    plan = K.plan_karst(1, DOMAIN, {}, via=(0, 0), main=MAIN)
    out = K.evaluate(plan, -4000.0, -4000.0, 8.0, 1000)
    h = out['h'].astype(np.float64) - out['plain']
    xs = -4000.0 + (np.arange(1000) + 0.5) * 8.0
    X, Y = np.meshgrid(xs, xs)
    m, _ = K._cluster(plan, X, Y)
    inside = m > 0.7
    low = float((h[inside] < 30.0).mean())
    assert low <= 0.30, f'{low:.0%} of the clusters under 30 m above the plain'
    inm = (np.abs(plan.x) < 3800) & (np.abs(plan.y) < 3800) & (plan.cluster > 0.7)
    ix = np.nonzero(inm)[0]
    nb, dist = K._knn(plan.x[ix], plan.y[ix], 3, 1.5 * plan.params['spacing_m'])
    s = np.linspace(0.0, 1.0, 60)
    rat = []
    for a in range(ix.size):
        for c in range(3):
            b = nb[a, c]
            if b < 0:
                continue
            qx = plan.x[ix[a]] + (plan.x[ix[b]] - plan.x[ix[a]]) * s
            qy = plan.y[ix[a]] + (plan.y[ix[b]] - plan.y[ix[a]]) * s
            qi = np.clip(((qx + 4000.0) / 8.0).astype(int), 0, 999)
            qj = np.clip(((qy + 4000.0) / 8.0).astype(int), 0, 999)
            Hm = min(plan.H[ix[a]] + plan.F[ix[a]], plan.H[ix[b]] + plan.F[ix[b]])
            rat.append(float(h[qj, qi].min()) / max(Hm, 1.0))
    col = float(np.median(rat))
    assert 0.35 <= col <= 0.8, f'cols at {col:.2f} of the lower tower at the median'
    record('test_cluster_massifs', cluster_share_under_30m=round(low, 3), col_share_median=round(col, 3),
           pairs=len(rat))


def test_river():
    """The river at the main tile's sharpest bend (0.5 m cells across it): its water is one flat surface (every wet
    cell's h + water within 1 cm of the plan's level), at least 2.5 m deep at its deepest, the deepest line on the
    outer half of the bend, a gravel point bar on the inner side (ground above the water inside the channel's
    half-width), a cut bank on the outer side (from the water's edge to 1.5 m above it within 8 m), and the plain
    river_bank_m (+-1 m) above the water beyond the banks."""
    plan = K.plan_karst(1, DOMAIN, {}, via=(0, 0), main=MAIN)
    P, kap = plan.river_mid, plan.river_kappa
    inside = np.nonzero((np.abs(P[:, 0]) < 3500) & (np.abs(P[:, 1]) < 3500))[0]
    k = inside[np.argmax(np.abs(kap[inside]))]
    c = P[k]
    t = P[k + 1] - P[k - 1]
    t /= np.hypot(*t)
    nrm = np.array([-t[1], t[0]])                       # left of the flow
    out = K.evaluate(plan, c[0] - 160.0, c[1] - 160.0, 0.5, 640)
    h, w = out['h'].astype(np.float64), out['water'].astype(np.float64)
    wet = w > 0.01
    lvl = h[wet] + w[wet]
    assert np.abs(lvl - plan.water_level).max() < 0.01, f'the water is not flat: {lvl.min():.3f} .. {lvl.max():.3f}'
    hw = float(np.interp(plan.river_s[k], plan.river_s, plan.river_hw))
    d = np.arange(-1.6 * hw, 1.6 * hw, 0.5)
    q = c[None, :] + d[:, None] * nrm[None, :]
    ii = np.clip(((q[:, 0] - (c[0] - 160.0)) / 0.5 - 0.5).astype(int), 0, 639)
    jj = np.clip(((q[:, 1] - (c[1] - 160.0)) / 0.5 - 0.5).astype(int), 0, 639)
    prof = h[jj, ii]
    ws = plan.water_level
    inner = 1.0 if kap[k] > 0 else -1.0                  # a left turn has its inner bank on the left
    u = d * inner                                       # metres toward the inner bank
    deep = float(ws - prof.min())
    u_deep = float(u[np.argmin(prof)])
    assert deep >= 2.5, f'deepest water {deep:.2f} m'
    assert u_deep < 0.0, f'the deepest line is on the inner half ({u_deep:.1f} m toward the inner bank)'
    on_inner = (u > 0.3 * hw) & (u < hw)
    assert (prof[on_inner] > ws).any(), 'no point bar above the water on the inner side'
    outer = u < 0
    dry = outer & (prof >= ws)
    assert dry.any(), 'no outer bank'
    u_edge = float(u[dry].max())                         # the outer water's edge (the dry cell nearest the axis)
    high = outer & (prof >= ws + 1.5)
    rise = float(u_edge - u[high].max()) if high.any() else 99.0
    assert rise <= 8.0, f'the outer bank rises 1.5 m over {rise:.1f} m'
    bank = float(np.median(prof[np.abs(d) > 1.4 * hw]))
    assert abs(bank - (ws + plan.params['river_bank_m'])) < 1.0, f'the plain at the banks {bank - ws:.2f} m up'
    record('test_river', bend_radius_m=round(1.0 / abs(float(kap[k])), 1), half_width_m=round(hw, 1),
           deepest_m=round(deep, 2), deepest_toward_outer_m=round(-u_deep, 1),
           bar_top_above_water_m=round(float(prof[on_inner].max() - ws), 2), outer_bank_rise_m=round(rise, 1),
           bank_above_water_m=round(bank - ws, 2), width_range_m=[round(2 * float(plan.river_hw.min())),
                                                                 round(2 * float(plan.river_hw.max()))])


def test_fengcong_composition():
    """fengcong at 16 m: no river, almost no plain (< 0.1), closed depressions (cockpits) over >= 2 % of the tile,
    their floors perched on the common base (median floor >= 15 m above the plain) and mostly flat."""
    plan = K.plan_karst(5, DOMAIN, {'kind': 'fengcong'}, via=(0, 0), main=MAIN)
    out = K.evaluate(plan, -4000.0, -4000.0, 16.0, 500)
    h = out['h'].astype(np.float64)
    assert out['water'].max() == 0.0
    s = slope_deg(h, 16.0)
    on_plain = float(((s < 5.0) & (h - out['plain'] < 3.0)).mean())
    assert on_plain < 0.1, f'plain-level ground {on_plain:.3f}'
    frac, count, thr, depth = _depressions(h, 16.0)
    assert frac >= 0.02, f'closed depressions {frac:.3f} of the tile'
    floors = h[(depth > thr) & (s < 8.0)] - out['plain'][(depth > thr) & (s < 8.0)]
    assert np.median(floors) >= 15.0, f'median cockpit floor {np.median(floors):.1f} m above the plain'
    record('test_fengcong_composition', plain_level_frac=on_plain, depression_frac=frac, depression_count=count,
           cockpit_floor_median_m=float(np.median(floors)))


def test_fluting_on_hero_levels():
    """On a 0.5 m level the walls carry vertical flutes: along a horizontal ring round a tower's wall the radius
    varies by flutes 2-10 m apart."""
    plan = one_tower_plan(H=150.0, wall=84.0, cone_deg=64.0, girth=0.6, fluting_m=1.2, ledges=False)
    fine = K.evaluate(plan, -96.0, -96.0, 0.5, 384)['h'].astype(np.float64)
    zc = 30.0
    ang = np.radians(np.arange(0, 360, 0.25))
    rr = np.arange(5, 95, 0.1)
    radius = []
    for a in ang:
        xs, ys = rr * math.cos(a), rr * math.sin(a)
        i = np.clip(((xs + 96) / 0.5 - 0.5).astype(int), 0, 383)
        j = np.clip(((ys + 96) / 0.5 - 0.5).astype(int), 0, 383)
        radius.append(rr[np.argmax(fine[j, i] < zc)])
    radius = np.array(radius)
    wiggle = float(np.std(radius - np.convolve(radius, np.ones(81) / 81, 'same')))
    assert wiggle > 0.2, f'no flutes: ring radius std {wiggle:.3f} m'
    record('test_fluting_on_hero_levels', ring_radius_detrended_std_m=wiggle)


# ------------------------------------------------------------------------------------- the op and the recipe
def test_op_on_core_levels():
    """The stage op on core's level plan (2 km main at 128 cells, context 2, a hero window): every level gets h,
    bed, deposit, talus, water and Sc; one plan serves all levels (domain from the coarsest); the river's water is
    one flat level on every level (the lake builder draws each wet region flat at its median level: so it draws the
    river as the water surface it is, its pieces on two levels meeting at one level); a child agrees with its parent
    where they overlap (box-averaged: mean |dh| <= 1.0 m, or 2.5 m under a horizon parent of 25 m cells and more: a
    spire 20-50 m wide is only its 2 x 2 subsamples' mean there, and in this plan's 236 towers a few such spires
    set the mean, 1.7-2.3 m as the clusters' threshold moves)."""
    from eidoblend.terrain.core.levels import plan_levels
    from eidoblend.terrain.core.fields import Fields
    lv = plan_levels(2000.0, 128, (0.0, 0.0), context=2, focus=(100.0, -200.0), hero=4.0)
    K._PLANS.clear()
    fields = []
    spreads = []
    for L in lv:
        f = fields[L.parent].inherit(L) if L.parent is not None else Fields(L, {'h': 0.0})
        K.op_karst(f, L, {'river_azimuth_deg': 30.0}, 9)
        for k in ('h', 'bed', 'deposit', 'talus', 'water', 'Sc'):
            assert k in f and f[k].shape == (L.n, L.n)
        wet = f['water'] > 0.01
        if wet.any():
            lvl = f['h'][wet].astype(np.float64) + f['water'][wet]
            spreads.append(float(np.ptp(lvl)))
        fields.append(f)
    assert len(K._PLANS) == 1, f'{len(K._PLANS)} plans for one terrain'
    assert spreads and max(spreads) < 0.01, f'the water is not one level: {spreads}'
    pairs = {}
    for L, f in zip(lv, fields):
        if L.parent is None:
            continue
        i0, j0, m = L.in_parent(lv)
        r = L.n // m
        down = f['h'].astype(np.float64).reshape(m, r, m, r).mean(axis=(1, 3))
        d = float(np.abs(down - fields[L.parent]['h'][j0:j0 + m, i0:i0 + m]).mean())
        lim = 2.5 if lv[L.parent].cell >= 25.0 else 1.0
        pairs[f'{lv[L.parent].cell:g}->{L.cell:g} m'] = round(d, 3)
        assert d <= lim, f'child {L} vs its parent: mean |dh| {d:.2f} m (limit {lim})'
    record('test_op_on_core_levels', levels=[repr(L) for L in lv], child_parent_mean_dh_m=pairs,
           water_level_spread_m=spreads)


def test_recipe():
    """tower_karst is registered, resolves (fengcong takes its preset for knobs left at their defaults), runs the
    karst op then a light threshold (no creep: it rounded the summits into domes), is JSON, names the nearest knob
    for a typo, and its op is found by the registry."""
    from eidoblend.terrain import recipes
    R = recipes.get('tower_karst')
    v, st = R.resolve({})
    assert st[0].op == 'karst' and st[0].params['spacing_m'] == K.DEFAULTS['spacing_m']
    assert [s.op for s in st] == ['karst', 'threshold'], [s.op for s in st]
    v, st = R.resolve({'kind': 'fengcong'})
    assert 'spacing_m' not in st[0].params and st[0].params['kind'] == 'fengcong'
    v, st = R.resolve({'kind': 'fengcong', 'spacing_m': 300.0})
    assert st[0].params['spacing_m'] == 300.0
    json.dumps(R.to_dict())
    try:
        R.resolve({'spacng_m': 1.0})
        raise AssertionError('a typo passed')
    except KeyError as e:
        assert 'spacing_m' in str(e)
    assert recipes.get_op('karst') is K.op_karst
    try:
        K.params_for({'spacng_m': 1.0})
        raise AssertionError('a typo passed the solver')
    except ValueError as e:
        assert 'spacing_m' in str(e)


def test_performance():
    """Timings (recorded; generous bounds): the plan of a 32 km domain, a 1024^2 main level at 7.8 m and a 1024^2
    hero level at 0.49 m."""
    t = time.time()
    plan = K.plan_karst(7, DOMAIN, {}, via=(0, 0), main=MAIN)
    tp = time.time() - t
    t = time.time()
    K.evaluate(plan, -4000.0, -4000.0, 7.8125, 1024)
    te = time.time() - t
    t = time.time()
    K.evaluate(plan, -250.0, -250.0, 0.48828125, 1024)
    th = time.time() - t
    assert tp < 20 and te < 40 and th < 30, f'plan {tp:.1f} s, main level {te:.1f} s, hero level {th:.1f} s'
    record('test_performance', plan_32km_s=round(tp, 2), main_level_1024sq_s=round(te, 2),
           hero_level_1024sq_s=round(th, 2), towers=plan.count)


def test_guilin_judge():
    """The official judge (judge/) on the default fenglin at the reference's extent (h and the river's water): every
    band passes (relief, hypsometry, slope p50, p90 and p99, the flat fraction, the spectrum slope, closed depressions
    with flat floors, anisotropy, texel cliffs, summit spacing, plain fraction), through the judge's radar chain, on
    seeds 1, 2 and 7 at 8 m cells, and on seed 1 at the draft's 15.625 m cells (a terrain with water coarser than the
    reference's stored 8 m pixel: its lake mask takes the radar chain too)."""
    from judge import judging
    rows = {}
    for seed, cell in ((1, 8.0), (2, 8.0), (7, 8.0), (1, 15.625)):
        n = int(round(8000.0 / cell))
        plan = K.plan_karst(seed, DOMAIN, {}, via=(0, 0), main=MAIN)
        out = K.evaluate(plan, -4000.0, -4000.0, cell, n)
        v = judging.judge(dict(h=out['h'].astype(np.float64), cell=cell, frame='south_up', water=out['water']),
                          'guilin_karst')
        key = f'seed{seed}_{cell:g}m'
        rows[key] = {r['metric']: (round(float(r['gen']), 3), r['passed']) for r in v.rows
                     if r.get('passed') is not None}
        record('test_guilin_judge', rows=rows)
        assert v.passed, f'{key}: {v.failures}'
    record('test_guilin_judge', rows=rows, asserted='every band')


TESTS = [test_blue_noise_spacing, test_plan_spacing_and_clusters, test_profile_functions, test_tower_walls_and_summits,
         test_plan_kinds, test_tower_slopes, test_world_space_windows, test_window_shift, test_base_edge_continuous,
         test_no_terraces_on_hero_levels, test_no_lattice_creases_on_hero_levels,
         test_cockpit_floors_meet_their_ground, test_parent_child_levels,
         test_determinism,
         test_fenglin_composition, test_cluster_massifs, test_river, test_fengcong_composition,
         test_fluting_on_hero_levels,
         test_op_on_core_levels, test_recipe, test_performance, test_guilin_judge]


def main(argv):
    names = set(argv)
    failed = 0
    for t in TESTS:
        if names and t.__name__ not in names:
            continue
        t0 = time.time()
        try:
            t()
            ok, msg = True, ''
        except Exception as e:                                        # noqa: BLE001
            ok, msg = False, f'{type(e).__name__}: {e}'
            traceback.print_exc()
        dt = time.time() - t0
        failed += not ok
        RESULTS.setdefault(t.__name__, {}).update(passed=ok, seconds=round(dt, 2), error=msg)
        print(f'{"PASS" if ok else "FAIL"}  {t.__name__:34s} {dt:6.2f} s  {msg}', flush=True)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, 'test_results.json')
    old = {}
    if os.path.exists(path):
        with open(path) as f:
            old = json.load(f)
    for k in ('test_isolated_tower_walls', 'test_plan_wall_angles'):        # replaced by the tests above
        old.pop(k, None)
    old.update(RESULTS)
    with open(path, 'w') as f:
        json.dump(old, f, indent=1, default=float)
    print(f'{len([1 for t in TESTS if not names or t.__name__ in names]) - failed} passed, {failed} failed; '
          f'{path}', flush=True)
    return failed


if __name__ == '__main__':
    sys.exit(1 if main(sys.argv[1:]) else 0)
