"""THE HOOF'S SURFACE: the HIGH of a claw and of a dewclaw (DEER_PLAN §6.4; work/bestiary/deer/hooves/build_NOTES.md
step 4), as RELIEF ON THE GENERATOR'S OWN COORDINATES.

Why not voxel strokes (families/horn_surface.py, the antler's way): an antler's block-out is an sdf.Program, so its
relief is strokes on a voxel field. A claw (families/hoof.py, ClawForm) is a ruled surface with exact growth
coordinates at every point: which tubule (the column), how old the horn is (the distance from the coronet along the
tubule), where it stands round the bearing edge. Horn's relief is written in those coordinates: growth rings are
lines of equal age, striae run along tubules, the edge wears by its distance from the ground ring, the sole flakes
in plan. So the high is the generator's own grid, dense (about 0.1 mm), displaced along its normal: a TRIANGLE high
of 1.5 M vertices that forge/bake_mesh.py bakes, with every driver the material stage needs carried per vertex
(no id strokes to decode). The sizes are rows (species/hoof_presets.RELIEF), shares of the hoof's length.

    V, T, A = claw_high(F, HL, side=+1)        the displaced claw (metres, the foot's frame) + per-vertex drivers
    V, T, A = dewclaw_high(p, HL)              the dewclaw template, its own frame
    DRIVERS                                    the names of the per-vertex drivers (A[name]: one float per vertex)

What the photos show and each layer answers (refs i01 dorsal, i04 side and below, i02 sole; hooves/refs/SOURCES.txt):
  rings      faint growth bands parallel to the coronet, one or two stress rings (i04's wall)
  streaks    the tubules' long grain, seen as the sheen breaking into lines (i01)
  scratches  fine pale scores, mostly across the tubules, on the toe and the outer wall (i01)
  film       the periople: a soft matte skin of young horn under the hairline, its lower edge ragged (c03)
  edge       the bearing edge worn round, most at the toe, with chips broken out of it (i04)
  sole       chalky plates with frayed edges, some shed, fibres along the claw (i02); the white line a shallow groove
  bulb       soft horn with fine striations across it (i02)
"""
import numpy as np

from . import hoof as HF
from ..species import hoof_presets as HP

DRIVERS = ('vv', 'age', 'per', 'fa', 'axial', 'wb', 'tau', 'wl', 'film', 'scratch', 'shed', 'flake', 'crack', 'chip',
           'ring', 'disp')
_ss = HF._ss


# -------------------------------------------------------------------------------------------------- noise
def _h01(i, seed=0):
    """an integer lattice hash in [0, 1)"""
    x = (np.asarray(i, np.int64) * 374761393 + int(seed) * 668265263) & 0xFFFFFFFF
    x = ((x ^ (x >> 13)) * 1274126177) & 0xFFFFFFFF
    x = x ^ (x >> 16)
    return (x & 0xFFFFFF) / 16777216.0


def vnoise1(x, seed=0, period=0):
    """1-D value noise in [-1, 1]; period: lattice cells per wrap (0: none)"""
    x = np.asarray(x, np.float64)
    i = np.floor(x).astype(np.int64)
    t = x - i
    t = t * t * (3.0 - 2.0 * t)
    j = i + 1
    if period:
        i, j = i % period, j % period
    return (1.0 - t) * (2.0 * _h01(i, seed) - 1.0) + t * (2.0 * _h01(j, seed) - 1.0)


def vnoise2(x, y, seed=0, period_x=0):
    x, y = np.asarray(x, np.float64), np.asarray(y, np.float64)
    ix, iy = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    tx, ty = x - ix, y - iy
    tx, ty = tx * tx * (3.0 - 2.0 * tx), ty * ty * (3.0 - 2.0 * ty)

    def h(a, b):
        if period_x:
            a = a % period_x
        return 2.0 * _h01(a * 73856093 + b * 19349663, seed) - 1.0
    return ((1.0 - tx) * (1.0 - ty) * h(ix, iy) + tx * (1.0 - ty) * h(ix + 1, iy)
            + (1.0 - tx) * ty * h(ix, iy + 1) + tx * ty * h(ix + 1, iy + 1))


def vnoise3(x, y, z, seed=0):
    """3-D value noise in [-1, 1]: for relief written in a part's own space (no pole, no seam: a pattern keyed on
    an angle fans out where the columns meet, the streak audit's first failure)"""
    x, y, z = (np.asarray(v, np.float64) for v in (x, y, z))
    ix, iy, iz = (np.floor(v).astype(np.int64) for v in (x, y, z))
    tx, ty, tz = x - ix, y - iy, z - iz
    tx, ty, tz = (t * t * (3.0 - 2.0 * t) for t in (tx, ty, tz))
    out = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                h = 2.0 * _h01((ix + dx) * 73856093 + (iy + dy) * 19349663 + (iz + dz) * 83492791, seed) - 1.0
                out = out + h * (tx if dx else 1.0 - tx) * (ty if dy else 1.0 - ty) * (tz if dz else 1.0 - tz)
    return out


def fbm3(x, y, z, seed=0, octaves=3):
    out, amp, tot = 0.0, 1.0, 0.0
    for o in range(octaves):
        k = 2 ** o
        out = out + amp * vnoise3(np.asarray(x) * k, np.asarray(y) * k, np.asarray(z) * k, seed + 7 * o)
        tot += amp
        amp *= 0.5
    return out / tot


def fbm1(x, seed=0, octaves=3, period=0):
    out, amp, tot = 0.0, 1.0, 0.0
    for o in range(octaves):
        out = out + amp * vnoise1(np.asarray(x) * 2 ** o, seed + 7 * o, period * 2 ** o)
        tot += amp
        amp *= 0.5
    return out / tot


def fbm2(x, y, seed=0, octaves=3):
    out, amp, tot = 0.0, 1.0, 0.0
    for o in range(octaves):
        out = out + amp * vnoise2(np.asarray(x) * 2 ** o, np.asarray(y) * 2 ** o, seed + 7 * o)
        tot += amp
        amp *= 0.5
    return out / tot


def worley(x, y, seed=0):
    """cellular noise: F1, F2 (the two nearest feature points' distances, cell units) and the nearest cell's key"""
    x, y = np.asarray(x, np.float64), np.asarray(y, np.float64)
    ix, iy = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    F1 = np.full(x.shape, 1e9)
    F2 = np.full(x.shape, 1e9)
    cid = np.zeros(x.shape, np.int64)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            cx, cy = ix + dx, iy + dy
            key = cx * 73856093 + cy * 19349663
            d = np.hypot(x - (cx + _h01(key, seed)), y - (cy + _h01(key, seed + 17)))
            near = d < F1
            F2 = np.where(near, F1, np.minimum(F2, d))
            cid = np.where(near, key, cid)
            F1 = np.where(near, d, F1)
    return F1, F2, cid


def worley3(x, y, z, seed=0):
    """3-D cellular noise: F1, F2 (the two nearest feature points' distances, cell units) and the nearest cell's
    key: for patterns on a curved part in its own space (no seam: the cells are cut by the surface)"""
    x, y, z = (np.asarray(v, np.float64) for v in (x, y, z))
    ix, iy, iz = (np.floor(v).astype(np.int64) for v in (x, y, z))
    F1 = np.full(x.shape, 1e9)
    F2 = np.full(x.shape, 1e9)
    cid = np.zeros(x.shape, np.int64)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                cx, cy, cz = ix + dx, iy + dy, iz + dz
                key = cx * 73856093 + cy * 19349663 + cz * 83492791
                d = np.sqrt((x - (cx + _h01(key, seed))) ** 2 + (y - (cy + _h01(key, seed + 17))) ** 2
                            + (z - (cz + _h01(key, seed + 29))) ** 2)
                near = d < F1
                F2 = np.where(near, F1, np.minimum(F2, d))
                cid = np.where(near, key, cid)
                F1 = np.where(near, d, F1)
    return F1, F2, cid


def _ring_table(rng, rg, reach, seed):
    """growth rings as a height over the distance from the coronet (HL): a sequence of soft ridges at the rows'
    spacing, a few of them stress rings, on a slow swell. Returns (x, height)"""
    x = np.arange(0.0, reach, 1.0e-4)
    cs, ws, hs = [], [], []
    c = 0.03 + 0.02 * rng.random()
    while c < reach - 0.02:
        sp = rng.uniform(*rg['spacing'])
        cs.append(c)
        ws.append(0.22 * sp)
        hs.append(rg['height'] * rg['base'] * rng.uniform(0.45, 1.0))
        c += sp
    cs = np.array(cs)
    pick = np.nonzero((cs > 0.12 * reach / 0.8) & (cs < 0.6 * reach / 0.8))[0]
    for i in rng.choice(pick, min(rg.get('stress', 0), len(pick)), replace=False):
        hs[i] = rg['height'] * rng.uniform(0.85, 1.0)
        ws[i] *= 1.3
    tab = np.zeros_like(x)
    for c_, w_, h_ in zip(cs, ws, hs):
        tab += h_ * np.exp(-0.5 * ((x - c_) / w_) ** 2)
    tab += 0.25 * rg['height'] * rg['base'] * vnoise1(x / 0.07, seed)
    return x, tab


def _ring_field(rng, rg, rho, aa, A, seed):
    """THE CLAW'S GROWTH RINGS, each its own soft ridge at a growth age that COMES AND GOES ROUND THE CLAW (11-11, fix
    round 1). The first rings (_ring_table: every ridge whole round the claw, 2-5.7 mm apart, 0.05-0.2 mm high, 0.4-1.2
    mm wide) read in the engine at the 1 m view in daylight as evenly ruled stripes over the whole wall, a brushed or
    3-D-printed surface (check1_NOTES.md verdict 4); the photos show none at that scale. Now: fewer (rg spacing), each
    ridge wide and low (its slope a degree or two), and each one's strength drawn along the ring by its own slow
    periodic noise, so a ring is a short soft run here and there and never a whole stripe; the stress ring(s) the
    strongest and the longest. rho: the growth coordinate (HL), aa: each point's place round the ground ring (HL), A:
    the ring's length. Returns the height (HL)"""
    out = np.zeros_like(rho)
    reach = float(np.max(rho)) if rho.size else 0.8
    cs = []
    c = rg['spacing'][0] * (0.6 + 0.8 * rng.random())
    while c < reach - 0.02:
        cs.append(c)
        c += rng.uniform(*rg['spacing'])
    cs = np.array(cs)
    stress = set()
    pick = np.nonzero((cs > 0.15) & (cs < 0.55))[0]
    if len(pick):
        stress = set(rng.choice(pick, min(rg.get('stress', 0), len(pick)), replace=False).tolist())
    cells = max(3, int(round(A / rg.get('run', 0.25))))       # the length of a ring's run round the claw
    for i, c_ in enumerate(cs):
        sp = rg['spacing'][1]
        w_ = rg.get('width', 0.30) * sp * rng.uniform(0.7, 1.3)
        if i in stress:
            h_ = rg['height'] * rng.uniform(0.85, 1.0)
            keep = 0.75
        else:
            h_ = rg['height'] * rg['base'] * rng.uniform(0.35, 1.0)
            keep = rg.get('keep', 0.40)
        # where along the ring this one shows: a periodic value noise thresholded softly round `keep` of its length
        m = 0.5 + 0.5 * vnoise1(aa / A * cells, seed + 101 + 7 * i, cells)
        m = _ss(1.0 - keep - 0.18, 1.0 - keep + 0.18, m)
        # the ridge's centre wanders a little along the ring on its own (rings are not parallel to each other)
        dc = 0.25 * w_ * vnoise1(aa / A * cells * 2, seed + 211 + 5 * i, cells * 2)
        out += h_ * m * np.exp(-0.5 * ((rho - c_ - dc) / w_) ** 2)
    return out


# -------------------------------------------------------------------------------------------------- the claw
def claw_relief(F, g, seed=5):
    """the relief of a claw's grid (ClawForm.grid): disp (R, K) in HL along the outward normal, the drivers
    (DRIVERS, each (R, K)) the material stage reads, and the bearing edge's wear for worn_edge (row: the ground
    ring's row; chip (R, K): how far each point is broken back, HL; sigma (K,): each column's rounding)"""
    p = F.p
    rl = HP.RELIEF[F.preset]
    rng = np.random.default_rng(seed)
    P = g['P']
    R, K = P.shape[:2]
    n = g['n']
    f = F.ring_f(n)
    col = F.ring(f, f[1:-1][::-1])
    G = col['G']
    seg = np.linalg.norm(np.diff(np.vstack([G, G[:1]])[:, [0, 2]], axis=0), axis=1)
    a = np.concatenate([[0.0], np.cumsum(seg)[:-1]])            # each column's place round the ground ring, HL
    A = float(seg.sum())
    aa = np.broadcast_to(a[None, :], (R, K))
    vv, age, zone = g['vv'], g['age'], g['zone']
    wallz = (zone == HF.Z_PERIOPLE) | (zone == HF.Z_WALL) | (zone == HF.Z_BULB)
    under = vv > 1.0
    v01 = np.clip(vv, 0.0, 1.0)
    t = np.clip(vv - 1.0, 0.0, 1.0)
    x_pt, y_pt, s_pt = P[..., 0], P[..., 1], P[..., 2]
    wbk = np.broadcast_to(col['wb'][None, :], (R, K))
    # UNDER THE CLAW THE SOLE'S HORN ENDS AT A LINE, NOT IN A RAMP (11-11; the engine from below,
    # look/h80_c_matched_sole.png: sole and bulb met in a soft band 11 mm wide, straight across both claws at one
    # station: an airbrushed stripe. On i04 and i02 the sole's rear edge is a crisp ragged line and the bulb begins
    # under it). The FORM keeps its long blend (ClawForm.under: trough into rounded bulb); the TISSUE changes at
    # s_b, a line that wanders at two scales, over `width`
    bb = rl['bulb_border']
    # (the noises are in -1..1 and mostly within +-0.4: the first rows, 0.025 and 0.010, moved the line by a
    # millimetre: a ruled line across the UV sheet, look/h50_maps_n.png. `bow` is its slow sweep across the claw)
    s_b = p['bulb_from'] + bb['bow'] * vnoise2(x_pt / 0.16, s_pt / 0.16, seed + 80) \
        + bb['wander'] * fbm2(x_pt / 0.05, s_pt / 0.05, seed + 81, 2) \
        + bb['wander_fine'] * fbm2(x_pt / 0.012, s_pt / 0.012, seed + 82, 3)
    wbp = _ss(-0.5 * bb['width'], 0.5 * bb['width'], s_pt - s_b)
    Lk, dk = col['L'][None, :], col['dist'][None, :]
    t_r, t_wl = col['t_r'][None, :], col['t_wl'][None, :]
    # the WALL'S bearing border runs on back beside the bulb and thins out toward the heel (i02: the dark wall edge
    # wraps the bulb), so the rim's tissue ends later and more gently than the sole's: wbr; across the white line
    # the two meet
    wbr = _ss(0.02, 0.14, s_pt - s_b)
    wbu = wbr + (wbp - wbr) * _ss(0.0, 1.0, (t - t_r) / np.maximum(t_wl - t_r, 1e-6))
    wb = np.where(under, wbu, wbk)
    hard = 1.0 - wbk                                            # the hard wall's share of a column
    # ---- the periople's film (first: the other layers are softened under it)
    fm = rl['film']
    cw = max(4, int(round(A / fm['wander_cell'])))
    per = np.maximum(F.periople_len(col)[None, :] + fm['wander'] * vnoise1(aa / A * cw, seed + 11, cw), 0.03)
    film = np.where(under, 0.0, _ss(per + fm['edge'], per - fm['edge'], age)) * hard
    h_film = fm['height'] * film * (1.0 + 0.35 * vnoise2(aa / 0.010, age / 0.010, seed + 13))
    # ---- growth rings: lines of equal age (the distance from the coronet), drawn a little toward equal shares of
    # the wall so that they close up toward the heel, and wandering a little round the claw
    rg = rl['ring']
    rho = age * (1.0 - rg['follow']) + v01 * F.wall_len * rg['follow']
    c0 = max(4, int(round(A / 0.30)))
    rho_w = rho + rg['wobble'] * (vnoise1(aa / A * c0, seed + 1, c0) + 0.3 * vnoise1(aa / A * c0 * 4, seed + 2, c0 * 4))
    # (11-11, fix round 1: _ring_table drew every ring whole round the claw: ruled stripes at the 1 m view, check1)
    h_ring = _ring_field(rng, rg, np.maximum(rho_w, 0.0), aa, A, seed + 3) * hard * wallz * (1.0 - 0.45 * film)
    # ---- the tubules' grain
    st = rl['streak']
    c1, c3 = max(8, int(round(A / st['cell']))), max(8, int(round(A / st['fine_cell'])))
    h_str = (st['height'] * fbm1(aa / A * c1, seed + 5, 3, c1) + st['fine'] * vnoise1(aa / A * c3, seed + 9, c3)) \
        * hard * wallz * (1.0 - 0.6 * film) * (0.55 + 0.45 * vnoise2(aa / 0.05, age / 0.08, seed + 6))
    # ---- scratches: short straight scores, most of them across the tubules, most on the toe and the outer wall
    sc = rl['scratch']
    h_sc = np.zeros((R, K))
    m_sc = np.zeros((R, K))
    r0w, nw = g['n_tuck'], g['n_wall'] + 1
    Mk = col['L'] * (1.0 - rg['follow']) + F.wall_len * rg['follow']        # rho = v x Mk on a column
    vrow = np.linspace(0.0, 1.0, nw)
    for _ in range(sc['n']):
        if rng.random() < 0.8:
            k0 = int(np.searchsorted(f, rng.uniform(0.0, 0.8) ** 1.3))
        else:
            k0 = K - 1 - int(np.searchsorted(f[1:-1], rng.uniform(0.0, 0.5)))
        k0 = min(max(k0, 0), K - 1)
        rho0 = rng.uniform(0.25, 0.98) ** 0.7 * Mk[k0]
        th = rng.normal(0.0, np.radians(22.0)) if rng.random() < sc['across'] else rng.uniform(-0.5 * np.pi, 0.5 * np.pi)
        # the length drawn SKEWED (u ** 2: many short scores, a few long; an even draw reads as pick-up sticks)
        ell = 0.5 * (sc['length'][0] + (sc['length'][1] - sc['length'][0]) * rng.random() ** 2)
        sg, dp = rng.uniform(*sc['width']), rng.uniform(*sc['depth'])
        stg = 0.22 + 0.78 * rng.random() ** 2                   # most scores faint, a few strong (equal ones: confetti)
        ext = ell + 3.0 * sg
        da = (a - a[k0] + 0.5 * A) % A - 0.5 * A
        ks = np.nonzero(np.abs(da) <= ext)[0]
        rr = np.nonzero((vrow >= (rho0 - ext) / Mk[ks].max() - 1e-3) & (vrow <= (rho0 + ext) / Mk[ks].min() + 1e-3))[0]
        if not len(rr) or not len(ks):
            continue
        X = da[ks][None, :]
        Y = vrow[rr][:, None] * Mk[ks][None, :] - rho0
        ct, sn = np.cos(th), np.sin(th)
        along, across = X * ct + Y * sn, -X * sn + Y * ct
        prof = np.exp(-0.5 * (across / sg) ** 2) * np.maximum(1.0 - (along / ell) ** 2, 0.0) ** 1.5
        sub = np.ix_(rr + r0w, ks)
        h_sc[sub] -= dp * prof
        m_sc[sub] = np.maximum(m_sc[sub], stg * prof)
    keep = hard * (1.0 - 0.7 * film)
    h_sc *= keep
    m_sc *= keep
    # ---- the bulb's striations: fine grooves across it, wrapping up round the heel
    wr = rl['wrinkle']
    q = s_pt + 0.9 * y_pt
    ph = (q + wr['wobble'] * fbm2(x_pt / 0.08, q / 0.08, seed + 15, 2)) / wr['period']
    broken = 0.25 + 0.75 * _ss(-0.35, 0.45, vnoise2(x_pt / 0.035, q / 0.05, seed + 16))
    h_wr = (-wr['depth'] * (0.5 - 0.5 * np.cos(2.0 * np.pi * ph)) ** 1.5 * broken
            + wr['lump'] * fbm2(x_pt / 0.06, q / 0.06, seed + 17, 3)) * wb * (vv >= 0.0)
    # the bulb's GRAIN: soft horn pebbled like grained leather (i04): a dome per cell of a 3-D cellular pattern in
    # the claw's own space (no seam, no pole), the domes unequal, on the bulb's points only
    pb = rl['pebble']
    mb = (wb > 0.01) & (vv >= 0.0)
    h_pb = np.zeros((R, K))
    if mb.any():
        F1p, F2p, cidp = worley3(x_pt[mb] / pb['cell'], y_pt[mb] / pb['cell'], s_pt[mb] / pb['cell'], seed + 83)
        h_pb[mb] = pb['height'] * (np.clip(1.0 - (F1p / 0.62) ** 2, 0.0, 1.0) * (0.45 + 0.55 * _h01(cidp, seed + 84))
                                   - 0.35) * wb[mb]
    h_wr = h_wr + h_pb
    # ---- the sole: plates with frayed edges, some shed, fibres along the claw; the white line; the rim's scuffs.
    # The plates are cells of a WARPED plan (their borders wander), their cracks open only in places, their edges
    # curl up, and the fibres and lumps carry as much relief as the plates (a clean cell net reads as a pattern)
    fl = rl['flake']
    sole_w = under * _ss(0.0, 0.10, (t - t_wl) / np.maximum(1.0 - t_wl, 1e-6)) * (1.0 - wbp)
    wx = x_pt + fl['warp'] * fbm2(x_pt / 0.035, s_pt / 0.035, seed + 19, 3)
    ws = s_pt + 1.6 * fl['warp'] * fbm2(x_pt / 0.035 + 31.7, s_pt / 0.035 - 12.3, seed + 20, 3)
    F1, F2, cid = worley(wx / fl['cell'], ws / (fl['cell'] * 1.7), seed + 21)
    gap = F2 - F1
    op = fl.get('open', (-0.2, 0.5))
    # WHERE THE SOLE FLAKES (11-12, fix round 2; check 2: "one even net of pale cracks"). Every plate stood at its
    # own height and every border curled, all over the sole: a net. A live sole (i04) is whole smooth horn in soft
    # bands, flaking in patches and toward its ragged end over the bulb. `flaky`: a slow field (cells of 0.11 HL)
    # + the last tenth before the bulb's border; plates, curled edges, open cracks and shed plates live inside it
    flaky = np.clip(np.maximum(_ss(-0.15, 0.45, vnoise2(wx / 0.11, ws / 0.11, seed + 26)),
                               _ss(0.10, 0.0, s_b - s_pt)), 0.0, 1.0)
    open_ = _ss(op[0], op[1], vnoise2(wx / 0.03, ws / 0.03, seed + 22)) * flaky    # where the cracks stand open
    crack = np.exp(-(gap / 0.07) ** 2) * open_
    shed = (_h01(cid, seed + 25) < fl['shed']).astype(np.float64) * _ss(0.35, 0.65, flaky)
    step = np.exp(-(gap / 0.16) ** 2)                                       # near a plate's border
    plate = ((2.0 * _h01(cid, seed + 23) - 1.0) * fl['plate'] * flaky - shed * fl['shed_depth']) * (1.0 - 0.5 * step)
    curl = fl['curl'] * step * (1.0 - shed) * (0.5 + 0.5 * vnoise2(wx / 0.012, ws / 0.012, seed + 24)) * flaky
    # an even CRUMB (it was fbm2(x / 0.005, s / 0.035): 0.5 mm lines seven times longer than wide, ruled hatching
    # along the whole sole in the engine's picture from below)
    fibre = fl['fibre'] * fbm2(wx / 0.009, ws / 0.012, seed + 27, 3) * (1.0 - 0.5 * shed)
    lump = fl['lump'] * fbm2(x_pt / 0.03, s_pt / 0.045, seed + 28, 3)
    # the sole horn's rear edge: it swells a little toward its ragged end over the bulb (a flaking lip), then stops
    lip = bb['lip'] * _ss(bb['lip_reach'], 0.0, s_b - s_pt) * (0.55 + 0.45 * vnoise2(wx / 0.02, ws / 0.02, seed + 85))
    h_sole = sole_w * (plate + curl - fl['crack'] * crack + fibre + lump + lip)
    xi = np.clip((t - t_r) / np.maximum(t_wl - t_r, 1e-6), 0.0, 1.0)
    # the white line's groove is deeper in places and nearly shut in others (one even hairline all round the sole
    # read as a seam drawn with a ruler)
    wl = under * np.sin(np.pi * xi) * (1.0 - wbr)
    cq = max(8, int(round(A / 0.045)))
    h_wl = -rl['white_line']['depth'] * wl * (0.35 + 0.65 * _ss(-0.5, 0.5, vnoise1(aa / A * cq, seed + 86, cq)))
    rim = under * (t <= t_r) * (1.0 - wbr)
    h_rim = 0.00015 * vnoise2(x_pt / 0.004, s_pt / 0.004, seed + 29) * rim
    # ---- the bearing edge: worn round (most at the toe), chipped
    ed = rl['edge']
    d_edge = np.where(under, t * dk, (1.0 - v01) * Lk)          # the distance from the ground ring along the surface
    toe_k = 1.0 - _ss(0.02, 0.20, G[:, 2])
    ce = max(8, int(round(A / 0.05)))
    B = (ed['bevel'] + (ed['bevel_toe'] - ed['bevel']) * toe_k) * (1.0 + 0.4 * vnoise1(a / A * ce, seed + 31, ce))
    chip_k = np.zeros(K)
    for _ in range(ed['chips']):
        k0 = int(np.searchsorted(f, rng.uniform(0.02, 0.78))) if rng.random() < 0.85 else \
            K - 1 - int(np.searchsorted(f[1:-1], rng.uniform(0.02, 0.3)))
        w_, d_ = rng.uniform(*ed['chip_w']), rng.uniform(*ed['chip_depth'])
        da = (a - a[min(max(k0, 0), K - 1)] + 0.5 * A) % A - 0.5 * A
        ragged = 0.55 + 0.45 * vnoise1(a / 0.004, seed + 41 + _)             # a broken edge, not a scoop
        chip_k = np.maximum(chip_k, d_ * ragged * np.maximum(1.0 - (da / w_) ** 2, 0.0) ** 1.5)
    edge_w = hard * (vv >= 0.0)
    chip = chip_k[None, :] * np.exp(-(d_edge / ed['chip_reach']) ** 2) * edge_w
    # THE EDGE IS NOT RELIEF: a bevel or a chip written as a push along each vertex's own normal folds the surface
    # at a sharp edge (the wall's normal and the underside's are 80-130 degrees apart, so the edge vertex and its
    # neighbours move apart: the first high carried a crease 0.1 mm wide all round the ground ring, baked as a
    # black line: AO 0.19, cavity 0.20, curvature -840 / m where the worn edge should be the most open, convex place
    # on the hoof). The chips and the rounding are done on the FORM (worn_edge), before any normal is taken
    disp = h_film + h_ring + h_str + h_sc + h_wr + h_sole + h_wl + h_rim
    tau = np.where(under, np.where(t <= t_r, t / np.maximum(t_r, 1e-6) - 1.0,
                                   (t - t_r) / np.maximum(1.0 - t_r, 1e-6)), -1.0)
    # per: the horn's age in PERIOPLE LENGTHS down its own tubule (0 the coronet, 1 the film's edge on that column,
    # 4 under the claw): what a soft veil of young horn fades on (hoof_fields), where `film` is the edge itself
    drv = dict(vv=vv, age=age, per=np.where(under, 4.0, np.clip(age / per, -1.0, 4.0)),
               fa=np.abs(g['fs']), axial=(g['fs'] < 0).astype(np.float64), wb=wb, tau=tau, wl=wl,
               film=film, scratch=m_sc, shed=shed * sole_w, flake=_h01(cid, seed + 33) * sole_w, crack=crack * sole_w,
               chip=chip / max(ed['chip_depth'][1], 1e-9), ring=h_ring / (rg['height'] * rg['base']), disp=disp)
    edge = dict(row=int(g['n_tuck'] + g['n_wall']), chip=chip, sigma=0.9 * B * (1.0 - col['wb']))
    return disp, drv, edge


def worn_edge(W, edge, band=34, iters=60):
    """THE BEARING EDGE WORN ON THE FORM (W: the claw's (R, K, 3) grid, HL): the chips broken out along the sharp
    edge's own bisector (one direction for a whole column, so nothing folds), then the corner worn ROUND: each
    column's polyline smoothed across the ground ring within `band` rows, to a Gaussian of edge['sigma'] (HL) per
    column (a wedge of turning angle phi smoothed by sigma has a radius of about 2.5 sigma / phi: 0.25 mm on the
    sides, 0.47 mm at the toe of the stag's hoof). Returns the worn grid; normals are taken from it afterwards"""
    r = edge['row']
    b = grid_normals(W)[r]
    W = W - b[None] * edge['chip'][..., None]
    seg = np.linalg.norm(np.diff(W[r - band:r + band + 1], axis=0), axis=-1).mean(0)       # each column's row spacing
    lam = np.clip(edge['sigma'] ** 2 / (iters * np.maximum(seg, 1e-12) ** 2), 0.0, 0.5)[None, :, None]
    taper = _ss(float(band), 0.6 * band, np.abs(np.arange(-band, band + 1)).astype(np.float64))[:, None, None]
    for _ in range(iters):
        X = W[r - band - 1:r + band + 2]
        W[r - band:r + band + 1] += lam * taper * (0.5 * (X[:-2] + X[2:]) - X[1:-1])
    return W


def grid_normals(W, pole=(0.0, -1.0, 0.0)):
    """outward unit normals of a closed (R, K) grid of points (columns closed round); a degenerate point (a pole,
    the spine's ends) takes `pole`"""
    dk = np.roll(W, -1, axis=1) - np.roll(W, 1, axis=1)
    dr = np.empty_like(W)
    dr[1:-1] = W[2:] - W[:-2]
    dr[0], dr[-1] = W[1] - W[0], W[-1] - W[-2]
    N = np.cross(dr, dk)
    if np.einsum('rki,rki->', N, W - W.reshape(-1, 3).mean(0)) < 0.0:
        N = -N
    ln = np.linalg.norm(N, axis=-1, keepdims=True)
    bad = ln[..., 0] < 1e-12 * max(float(ln.max()), 1e-30)
    N = N / np.maximum(ln, 1e-30)
    N[bad] = np.asarray(pole, np.float64)
    return N


def claw_high(F, HL, side=1.0, n=1024, n_wall=512, n_under=192, seed=5, relief=True):
    """THE CLAW'S HIGH: the generator's grid at about 0.1 mm, displaced by its relief; closed (the two halves of
    the sole welded along the spine, the tuck's top a fan inside the leg). V (metres, the foot's frame), T, A:
    the drivers per vertex (DRIVERS) + 'zone' + 'shape'. side -1: the mirror claw (the same relief, mirrored)"""
    g = F.grid(n=n, n_wall=n_wall, n_under=n_under)
    P = g['P']
    R, K = P.shape[:2]
    W = HF.to_world(P, 1.0, 1.0)
    if relief:
        disp, drv, edge = claw_relief(F, g, seed)
        W = worn_edge(W, edge)                  # the chipped, rounded bearing edge: form first, then the normals
    else:
        disp = np.zeros((R, K))
        drv = dict(vv=g['vv'], age=g['age'], disp=disp)
    Nn = grid_normals(W)
    # the spine: the abaxial column j and the axial column 2 n - j end on the same point; one vertex for both, its
    # normal and relief the two sides' mean
    j = np.arange(1, n)
    for arr in [Nn, disp] + [v for v in drv.values() if isinstance(v, np.ndarray) and v.shape == (R, K)]:
        m = 0.5 * (arr[-1, j] + arr[-1, 2 * n - j])
        arr = arr if arr.flags.writeable else None
        if arr is not None:
            arr[-1, j] = m
            arr[-1, 2 * n - j] = m
    Nn[-1] /= np.maximum(np.linalg.norm(Nn[-1], axis=-1, keepdims=True), 1e-30)
    V = (W + Nn * disp[..., None]).reshape(-1, 3) * HL
    idx = np.arange(R * K)
    idx[(R - 1) * K + 2 * n - j] = (R - 1) * K + j
    T = idx[HF.grid_tris(R, K)]
    T = T[(T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 0] != T[:, 2])]
    top = len(V)
    V = np.vstack([V, V[:K].mean(0)])
    jj = np.arange(K)
    T = np.concatenate([T, np.stack([np.full(K, top), (jj + 1) % K, jj], -1)])
    T = HF._orient(V, T)
    A = {}
    for k_, v_ in drv.items():
        if isinstance(v_, np.ndarray) and v_.shape == (R, K):
            A[k_] = np.concatenate([np.asarray(v_, np.float32).reshape(-1), np.float32([v_[0, 0]])])
    A['zone'] = np.concatenate([g['zone'].reshape(-1), [HF.Z_TUCK]]).astype(np.int8)
    A['shape'] = (R, K)
    if side < 0:
        V = HF.pair_place(V, F, HL, -1.0)               # the partner: mirrored and scaled (hoof.pair)
        T = T[:, ::-1]
    return V, T.astype(np.int32), A


# -------------------------------------------------------------------------------------------------- the dewclaw
def dewclaw_high(p, HL, n_round=384, n_long=256, seed=9, preset='cervid'):
    """THE DEWCLAW'S HIGH (one template for all eight): its form at about 0.15 mm with growth rings round it, the
    soft film under the hairline, scuffs toward its worn end. Its own frame (metres): +z along it, +y outward.
    V, T, A (vv: 0 the hairline .. 1 the tip; film, ring, disp)"""
    rl = HP.RELIEF[preset]['dew']
    rng = np.random.default_rng(seed)
    P, vv = HF.dewclaw_form(p, n_round=n_round, n_long=n_long)
    R, K = P.shape[:2]
    Nn = grid_normals(P, pole=(0.0, 0.0, 1.0))
    L = p['dew_len']
    w = vv * L                                                      # the distance from the hairline, HL
    th = np.broadcast_to(np.arange(K)[None, :] / K, (R, K))
    xt, tab = _ring_table(rng, dict(height=rl['ring_h'], base=0.7, spacing=rl['ring_spacing'], stress=1), L + 0.05,
                          seed + 3)
    # every pattern in the pad's own space (x across, y outward, z along; HL): an angle would fan at the tip's pole
    X, Y, Z = P[..., 0], P[..., 1], P[..., 2]
    h_ring = np.interp(w + 0.003 * vnoise3(X / 0.06, Y / 0.06, Z / 0.06, seed + 1), xt, tab, left=0.0, right=0.0)
    film = _ss(p['dew_periople'] * L + 0.006, p['dew_periople'] * L - 0.006,
               w + 0.012 * vnoise3(X / 0.07, Y / 0.07, Z / 0.07, seed + 5))
    h_film = rl['film'] * film
    worn = _ss(0.45, 0.95, vv)
    h_scuff = rl['scuff'] * worn * fbm3(X / 0.006, Y / 0.006, Z / 0.006, seed + 7)
    h_lump = rl['lump'] * fbm3(X / 0.05, Y / 0.05, Z / 0.05, seed + 8, 3)
    disp = (h_ring * (1.0 - 0.45 * film) * (1.0 - 0.5 * worn) + h_film + h_scuff + h_lump) * (vv >= 0.0)
    disp[-1] = disp[-1].mean()
    V = (P + Nn * disp[..., None]).reshape(-1, 3) * HL
    idx = np.arange(R * K)
    idx[(R - 1) * K:] = (R - 1) * K                                 # the tip: one vertex
    T = idx[HF.grid_tris(R, K)]
    T = T[(T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 0] != T[:, 2])]
    top = len(V)
    V = np.vstack([V, V[:K].mean(0)])
    jj = np.arange(K)
    T = np.concatenate([T, np.stack([np.full(K, top), (jj + 1) % K, jj], -1)])
    T = HF._orient(V, T)
    f32 = lambda x: np.concatenate([np.asarray(x, np.float32).reshape(-1), np.float32([x[0, 0]])])
    A = dict(vv=f32(vv), film=f32(film), ring=f32(h_ring / rl['ring_h']), worn=f32(worn), disp=f32(disp), shape=(R, K))
    return V, T.astype(np.int32), A


# -------------------------------------------------------------------------------------------------- the material's fields
def hoof_fields(b, HL, seed=3, preset='cervid'):
    """THE FIELDS OF A HOOF for the one horn material stage (families/horn_skin.material's `fields`: what the part's
    generator knows about each texel). b: the bake's maps over the sheet (cov, piece 0 claw / 1 dewclaw, position in
    the stand frame, ao, cavity, curvature) and the high's drivers at each texel (d_<name>: DRIVERS, and the
    dewclaw's vv, film, ring, worn); HL the hoof's length. Every field is 0..1, image order. The stage's own rules
    read along, tip, young and dust; the rest are the weights of the recipe's LAYERS (species/hoof_presets.HORN_ROWS).

      along        0 the coronet .. 1 the bearing edge (and under the claw); the dewclaw: 0 its hairline .. 1 its tip
      tip          the WORN zone: toward the ground, most at the toe (thin brown horn); the dewclaw's scuffed end
      young        the periople: a dusty veil of young matte horn under the hairline, thinning down the tubules
      grain        a lacy mottle, 0..1 about 0.5: the `gain` of the soft tissues' layers (no zone is a flat fill)
      dust         the dust line by height above the sole, in the stand frame
      scuff        flakes of the old film and scuffed bloom lower on the wall (photo i01: pale flaky patches down
                   to mid-wall), and a fine speckle all over the hard wall
      matte        where the wall's skin is scuffed dull (roughness only)
      bulb_lace, sole_lace   a lace of smoother skin on the bulb, and on the sole and rim (roughness only)
      scratch      the sculpt's scores, narrowed (a score is a hairline: 0.2 mm on the photo)
      bulb         the soft heel bulb (both above and under its equator)
      rim          the bearing border seen from below (the wall's own section: brown horn)
      white_line   the junction between wall and sole (a shallow groove that holds dirt)
      sole         the sole inside the white line
      scurf        chalky flaking: fine flakes on the sole (fewer on shed plates), on the bulb's striation crests
      shed         where a sole plate is shed: fresh dark horn
      dirt         packed in the sole's cracks and where the trough is shut in (its own AO)
      edge         the bearing edge worn round: convex and near the ground
      chip         a fresh break in the edge
    """
    cov = np.asarray(b['cov'], bool)
    pc = np.asarray(b['piece'])[cov]
    claw, dew = pc == 0, pc == 1
    P = np.asarray(b['position'], np.float64)[cov] / HL                # the stand frame, in hoof lengths
    y = P[:, 1]
    ao, curv = (np.asarray(b[k], np.float64)[cov] for k in ('ao', 'curvature'))
    d = {k[2:]: np.asarray(b[k], np.float64)[cov] for k in b if k.startswith('d_')}
    c01 = lambda x: np.clip(x, 0.0, 1.0)                                # noqa: E731
    X, Y, Z = P[:, 0], P[:, 1], P[:, 2]
    n1 = fbm3(X / 0.05, Y / 0.05, Z / 0.05, seed, 3)                    # slow: 5 mm on the stag
    n2 = fbm3(X / 0.11, Y / 0.11, Z / 0.11, seed + 9, 2)                # slower: where flaking gathers
    under = _ss(1.0, 1.01, d['vv'])
    wall = 1.0 - under
    nb = fbm3(X / 0.035, Y / 0.035, Z / 0.035, seed + 63, 5)           # five octaves from 3.6 mm: lacy
    # THE BULB'S BORDER WANDERS. The high's driver wb is a smooth ramp along one tubule (and one station under the
    # claw): painted as it is, wall, periople and bulb met along dead straight lines, which the streak audit flagged
    # as bars and fans (out/audit: 8 clusters, 7.3 cm2). Inside the ramp the lacy noise moves the border by +-4 mm
    wb0 = c01(d['wb'])
    wb = _ss(0.2, 0.8, wb0 + 1.6 * nb * wb0 * (1.0 - wb0))
    hard = 1.0 - wb
    toe = 1.0 - _ss(0.05, 0.5, d['fa'])
    film = c01(c01(d['film']) / np.maximum(1.0 - wb0, 0.08))           # the film without the driver's own bulb fade
    fine = 0.5 + 0.5 * fbm3(X / 0.004, Y / 0.004, Z / 0.004, seed + 61, 2)     # 0.4 mm grain, 0..1
    nb2 = fbm3(X / 0.021, Y / 0.021, Z / 0.021, seed + 71, 4)                  # four octaves from 2.2 mm
    # the rim's inner border WANDERS by about a millimetre (11-11: at one even offset from the outline, with the
    # white line a hairline beside it, the rim read as a shoe's welt in the engine's picture from below)
    in_sole = _ss(-0.05, 0.10, d['tau'] + 0.06 * nb2 + 0.04 * (fine - 0.5))
    sole = under * in_sole * hard
    shed = c01(d['shed']) * sole
    plate = c01(d['flake'])

    bloom = _ss(-0.05, 0.60, nb) * (0.45 + 0.55 * fine)

    def flakes(cell, density, sd):
        """ANGULAR FLAKES: the cells of a 3-D cellular pattern, each kept whole when its own random number is
        under the local density (coverage follows the density; a flake is a plate with straight edges, where a
        thresholded noise gives round blobs that read as camouflage: the second paint, look/h60_board_b.png),
        its border ragged (the grain eats into it) and thin, most flakes faint and a few strong (equal flakes at
        one size read as terrazzo: the third paint, look/h60_board_c.png)"""
        F1, F2, cid = worley3(X / cell, Y / cell, Z / cell, sd)
        keep = _ss(0.0, 0.12, density - _h01(cid, sd + 3))
        return keep * _ss(0.03, 0.34, (F2 - F1) + 0.30 * (fine - 0.5)) * (0.30 + 0.70 * _h01(cid, sd + 5) ** 2)

    # the wall's scuffs: a soft bloom of the old film, gathered in patches from under the periople to mid-wall
    # (cell flakes here clustered like frog-spawn in the quarter view: look/h60_d_quarter.png; a bloom only)
    d_wall = wall * hard * (1.0 - film) * _ss(0.50, 0.14, d['age']) * _ss(0.02, 0.50, n2)
    scuff = 0.60 * d_wall * bloom
    # + SPECKS all over the hard wall (11-11; i01 at 3.5x: besides the scores the black horn is peppered with pale
    # flecks of 0.3-0.8 mm, denser in patches; the bloom alone left the wall between its clouds clean as glass)
    speck = flakes(0.007, (0.05 + 0.13 * _ss(-0.2, 0.5, n1)) * wall * hard * (1.0 - film), seed + 91)
    scuff = np.maximum(scuff, 0.85 * speck)
    # MATTE PATCHES: where the horn's skin is scuffed dull, by a slow field broken by the grain (roughness only; a
    # wall at one even gloss was a sheet of blue-grey sky in the engine)
    matte = wall * hard * _ss(-0.30, 0.45, fbm3(X / 0.085, Y / 0.085, Z / 0.085, seed + 93, 3)) * (0.55 + 0.45 * fine)
    # NO ZONE AT ONE ROUGHNESS (11-11 05:1x: the bulb painted at 0.82 from p5 to p95, the sole at 0.62, the rim at
    # 0.60; the streak audit flagged a 43 mm2 bar on the bulb, in the roughness alone: the dust line's faint ramp
    # was the only thing there). Each soft or worn tissue gets a lace of smoother skin: roughness only
    bulb_lace = wb * _ss(-0.40, 0.40, nb2) * (0.55 + 0.45 * fine)
    sole_lace = under * hard * _ss(-0.30, 0.45, nb) * (0.55 + 0.45 * fine)
    # THE PERIOPLE IS A DUSTY VEIL, NOT A BAND (11-11). The photos: i04 a pale tan-grey zone along the hairline,
    # soft and ragged, wider toward the heel; c03 fading into the slate over a third of the wall; i01 black rough
    # horn under the hair on the toe's front. The first paints cut it at the high's film edge: a pale skirt with a
    # torn-paper border, flat inside (look/h60_board_e.png, pair 1), and the streak audit flagged the faint ramps
    # left in it (a flat zone has no texture of its own, so any ramp reads as a streak). Now it is whole only at
    # the hairline and thins to nothing by 1.3 periople lengths down the tubule, thinner on the toe's front than on
    # the flank, broken by the lacy noise and the grain all the way; toward the heel it runs into the bulb's soft
    # horn (one tissue), whose layer paints over it (nb2: the four-octave noise from 2.2 mm, above)
    lace = (0.50 + 0.50 * _ss(-0.45, 0.35, nb2)) * (0.72 + 0.28 * fine)
    thin = 0.55 + 0.45 * _ss(0.10, 0.45, d['fa'])
    young_c = wall * _ss(1.30, 0.10, d['per'] + 0.55 * nb) ** 1.5 * thin * lace
    # the dewclaw's: the same veil on its own length (its hairline is its base ring)
    per_d = d['vv'] / HP.preset(preset)['dew_periople']
    young_d = 0.75 * _ss(1.40, 0.10, per_d + 0.55 * nb) ** 1.5 * lace
    # the sole's scurf: a soft chalky bloom with a few flakes on it, gathered by a slow field, less on shed plates;
    # the bulb's: a fainter bloom where it meets the ground
    # (11-11: a live summer sole, i04, is dark smooth horn with a few pale marks: the bloom at 0.60 and the bulb's
    # at 0.35 made a chalky sole and a cloud across the heel in the engine's picture from below)
    d_sole = sole * (1.0 - 0.8 * shed) * (0.18 + 0.62 * _ss(-0.35, 0.40, n2)) * (0.55 + 0.45 * plate)
    scurf = np.maximum(0.38 * d_sole * bloom, flakes(0.022, 0.20 * d_sole, seed + 47))
    scurf = np.maximum(scurf, np.maximum(0.10 * wb * under * bloom, 0.30 * flakes(0.013, 0.06 * wb * under, seed + 51)))
    z = np.zeros(len(y))
    worn = c01(d.get('worn', z))                                               # the dewclaw's scuffed end
    F = dict(
        along=c01(d['vv']),
        # (the worn zone reached 0.14 HL up: on i01 the toe's brown horn runs about 0.2 up the front)
        tip=np.where(claw, (1.0 - _ss(0.02, 0.20, y)) * (0.25 + 0.75 * toe) * wall * hard,
                     0.5 * _ss(0.15, 0.85, worn + 1.2 * nb * worn * (1.0 - worn))),
        young=np.where(claw, young_c, young_d),
        grain=c01(0.5 + 0.9 * nb2),
        dust=np.where(claw, 0.6 * (1.0 - _ss(0.0, 0.07, y)) * (0.55 + 0.45 * n1) * wall, 0.0),
        scuff=np.where(claw, scuff, 0.0),
        matte=np.where(claw, matte, 0.0),
        bulb_lace=np.where(claw, bulb_lace, 0.0),
        sole_lace=np.where(claw, sole_lace, 0.0),
        scratch=np.where(claw, c01(d['scratch']) ** 1.5 * wall, 0.0),
        bulb=np.where(claw, wb, 0.0),
        rim=np.where(claw, under * (1.0 - in_sole) * hard, 0.0),
        # THE WHITE LINE'S CREAM COMES AND GOES (11-12, fix round 2; i04 at 2.2x: a thin cream line where the wall
        # meets the sole, strongest round the toe, in runs along the flanks; one even pale ring all round would be
        # an insole's stitching): whole at the toe, elsewhere in runs of a slow 3-D noise, a faint trace between
        white_line=np.where(claw, c01(d['wl']) * under * c01(0.15 + 0.85 * np.maximum(
            1.0 - _ss(0.03, 0.22, d['fa']), _ss(-0.05, 0.40, fbm3(X / 0.085, Y / 0.085, Z / 0.085, seed + 95, 2)))), 0.0),
        sole=np.where(claw, sole, 0.0),
        scurf=np.where(claw, scurf, 0.0),
        shed=np.where(claw, shed, 0.0),
        dirt=np.where(claw, sole * c01(0.9 * c01(d['crack']) + 0.8 * _ss(0.92, 0.55, ao)), 0.0),
        edge=np.where(claw, _ss(150.0, 900.0, curv) * (1.0 - _ss(0.0, 0.06, y)) * hard, 0.0),
        chip=np.where(claw, c01(d['chip']), 0.0),
    )
    out = {}
    for k, v in F.items():
        a = np.zeros(cov.shape, np.float32)
        a[cov] = v
        out[k] = a
    return out
