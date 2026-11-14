"""THE HORN GENERATOR: antlers, bovid horns, rhino horns, tusks and ossicones as parts for any head's horn port
(work/bestiary/research/DEER_PLAN.md §5 with DEER_CRITIC.md §1b; the build's notes
work/bestiary/deer/horns/build_NOTES.md; the presets in species/horn_presets.py).

A horn is a SKELETON: branches, each a dense centreline with a frame and a SECTION per node that is measured and
changes along the form (never a tube of one radius), each on its parent at a station. Everything else reads it:

    skel = antler(PRESETS['red_deer'])            the red deer's branching grammar on Bils' measured table
    prog = program(skel)                          the block-out: one SWEEP per branch in ONE n-ary ROUND union, so a
                                                  fork is one form flowing into the next; the signet cut flat
    measures(skel)                                the built antler in the paper's own measures (the HN0 gate's table)
    low = cage(skel, prog, lod)                   OUR OWN low: a tube of fair rings per branch drawn from the SAME
                                                  section function, ports at the forks, quad-grid caps (no fans); the
                                                  LODs from the same ring and K tables
    horn_surface.build(skel, prog, ...)           the high: voxel strokes on the block-out (pearls, gutters, the burr)
    horn_skin.material(...)                       the one horn material stage

THE SECTION is the SWEEP's own rule (forge/sdf.py sd_sweep), so the clay, the low and the strokes agree to the bit:
    r(theta) = r0 (1 + a2 cos 2(theta - phi2) + a3 cos 3(theta - phi3) + a4 cos 4 theta) * asp / sqrt(asp^2 cos^2 + sin^2)
theta from the frame normal n toward b = t x n. r0 is the half WIDTH along n (the fork plane), asp the thickness /
width, a3 the egg toward a crotch, a2 / a4 the burr's low lobes.

FRAMES. A part is built in its PART frame (z the root axis, x the tines' front, y = z cross x: outward on the left
part) and placed in the host's head axes at rest by the preset's `launch` (+Y up, +Z forward, +X the host's left), so
the bake's world position and normal are the host's own and the material's world-space wear means something. The right
part is the left mirrored (x -> -x in the head frame), as data.

FAMILIES ARE DATA: `build(preset)` picks the builder by preset['family']: 'antler' (the branching grammar), 'spiral'
(the bovid's natural 3D spiral: radius of curvature and of torsion linear in arc length; the horns study's check),
'cone' (rhino horn, tusk, ossicone: a bent cone with an optional helix phase). Only the antler goes past its skeleton
in this round (HN0-HN1); the others' sections are measured first at HN3 (DEER_CRITIC §1b).
"""
import numpy as np
from scipy.interpolate import PchipInterpolator

MM = 1.0e-3
ROOT_HIDE = 0.70          # a tine's root inside the beam: its half width as a share of the beam's least half axis
FORK_REACH = 60.0         # mm along the prime beam: how far a fork's widening reaches in the girth table (`aged`)


# ------------------------------------------------------------------------------------------------------ helpers
def unit(v):
    v = np.asarray(v, np.float64)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-30)


def rot(axis, ang):
    """the rotation matrix about a unit axis by ang radians (Rodrigues)"""
    a = unit(axis)
    K = np.array([[0.0, -a[2], a[1]], [a[2], 0.0, -a[0]], [-a[1], a[0], 0.0]])
    return np.eye(3) + np.sin(ang) * K + (1.0 - np.cos(ang)) * (K @ K)


def sstep(x):
    x = np.clip(np.asarray(x, np.float64), 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def ellipse_half_width(girth, aspect):
    """the half width r0 of the ellipse of perimeter `girth` whose other half axis is aspect * r0 (Ramanujan II)"""
    aspect = np.asarray(aspect, np.float64)
    h = ((1.0 - aspect) / (1.0 + aspect)) ** 2
    return np.asarray(girth, np.float64) / (np.pi * (1.0 + aspect) * (1.0 + 3.0 * h / (10.0 + np.sqrt(4.0 - 3.0 * h))))


def section_radius(r0, asp, a2, phi2, a3, phi3, a4, theta):
    """the SWEEP's section rule (sdf.sd_sweep), vectorised: the radius at theta"""
    r = r0 * (1.0 + a2 * np.cos(2.0 * (theta - phi2)) + a3 * np.cos(3.0 * (theta - phi3)) + a4 * np.cos(4.0 * theta))
    cs, sn = np.cos(theta), np.sin(theta)
    return r * asp / np.sqrt(asp * asp * cs * cs + sn * sn)


class Branch:
    """one branch: nodes P (N, 3) metres, frame normal n (N, 3), the section arrays (N,), its parent and station"""
    FIELDS = ('r0', 'asp', 'a2', 'phi2', 'a3', 'phi3', 'a4')

    def __init__(self, name, kind, P, n, r0, asp=1.0, a2=0.0, phi2=0.0, a3=0.0, phi3=0.0, a4=0.0, parent=-1,
                 s_parent=0.0, cls=None, meta=None):
        self.name, self.kind, self.parent, self.s_parent, self.cls = name, kind, parent, float(s_parent), cls
        self.P = np.asarray(P, np.float64)
        N = len(self.P)
        bc = lambda v: np.broadcast_to(np.asarray(v, np.float64), (N,)).copy()      # noqa: E731
        self.r0, self.asp, self.a2, self.phi2, self.a3, self.phi3, self.a4 = (bc(v) for v in (r0, asp, a2, phi2, a3,
                                                                                               phi3, a4))
        seg = np.linalg.norm(np.diff(self.P, axis=0), axis=1)
        self.s = np.concatenate([[0.0], np.cumsum(seg)])
        self.length = float(self.s[-1])
        # the node tangents by the SWEEP's own rule (sdf.node_tangent: the chord through the neighbours)
        T = np.zeros_like(self.P)
        T[1:-1] = self.P[2:] - self.P[:-2]
        T[0], T[-1] = self.P[1] - self.P[0], self.P[-1] - self.P[-2]
        self.T = unit(T)
        n = np.asarray(n, np.float64)
        self.n = unit(n - self.T * np.sum(n * self.T, axis=1, keepdims=True))
        self.b = np.cross(self.T, self.n)
        self.meta = dict(meta or {})

    def frac(self, s):
        """node index and fraction at arc length s (clamped)"""
        s = np.clip(np.asarray(s, np.float64), 0.0, self.length)
        j = np.clip(np.searchsorted(self.s, s, side='right') - 1, 0, len(self.s) - 2)
        u = (s - self.s[j]) / np.maximum(self.s[j + 1] - self.s[j], 1e-30)
        return j, u

    def lerp(self, arr, s):
        j, u = self.frac(s)
        a = np.asarray(arr)
        if a.ndim == 1:
            return a[j] * (1.0 - u) + a[j + 1] * u
        return a[j] * (1.0 - u)[..., None] + a[j + 1] * u[..., None]

    def frame(self, s):
        """(point, n, b, t) at arc length s, interpolated as the SWEEP interpolates them"""
        p = self.lerp(self.P, s)
        t = unit(self.lerp(self.T, s))
        n = self.lerp(self.n, s)
        n = unit(n - t * np.sum(n * t, axis=-1, keepdims=True))
        return p, n, np.cross(t, n), t

    def radius(self, s, theta):
        """the section's radius at arc length s (scalar or (M,)) and theta (broadcast)"""
        v = [self.lerp(getattr(self, k), s) for k in self.FIELDS]
        return section_radius(v[0], v[1], v[2], v[3], v[4], v[5], v[6], theta)

    def surface(self, s, theta):
        """points of the branch's own section at (s, theta) (before any blend)"""
        p, n, b, _ = self.frame(s)
        r = self.radius(s, theta)
        return p + np.asarray(r)[..., None] * (np.cos(theta)[..., None] * n + np.sin(theta)[..., None] * b)

    def girth(self, s, m=256):
        th = np.linspace(0.0, 2.0 * np.pi, m, endpoint=False)
        r = self.radius(float(s), th)
        x, y = r * np.cos(th), r * np.sin(th)
        return float(np.hypot(np.roll(x, -1) - x, np.roll(y, -1) - y).sum())


class Skeleton:
    def __init__(self, family, branches, frame, blend, preset, scale=1.0, side='L', meta=None):
        self.family, self.branches, self.blend, self.preset, self.scale, self.side = family, branches, blend, preset, \
            scale, side
        self.origin, self.x, self.y, self.z = frame          # the part frame in the head axes (metres, unit vectors)
        self.meta = dict(meta or {})

    def __getitem__(self, name):
        return next(b for b in self.branches if b.name == name)

    def index(self, name):
        return next(i for i, b in enumerate(self.branches) if b.name == name)

    def bounds(self, pad=0.004):
        lo = np.min([np.min(b.P - (b.r0 * 1.6)[:, None], axis=0) for b in self.branches], axis=0) - pad
        hi = np.max([np.max(b.P + (b.r0 * 1.6)[:, None], axis=0) for b in self.branches], axis=0) + pad
        return lo, hi


def part_frame(launch):
    """the part frame (x front, y, z axis) in the head axes from a preset's launch: z the axis, x the front made
    square to it, y = z cross x"""
    z = unit(launch['axis'])
    x = np.asarray(launch['front'], np.float64)
    x = unit(x - z * float(x @ z))
    return x, np.cross(z, x), z


# ------------------------------------------------------------------------------------------------- the antler
def _beam_curve(B, ds=0.002, s_end=None):
    """the beam's centreline in the PART frame (mm in, mm out): nodes every ds metres... here in mm: stations s (N,),
    points (N, 3), tangents, the in-plane front normal, tilt and lateral angles (rad)"""
    L = float(B['length']) if s_end is None else float(s_end)
    # dense near the base (the burr's rim is 11 mm long), then every 2 mm
    s = np.unique(np.concatenate([np.arange(0.0, 30.0, 0.5), np.arange(30.0, L, ds * 1000.0), [L]]))
    tilt = np.zeros_like(s)
    for (sk, deg, w) in B['turns']:
        tilt += np.radians(deg) * sstep((s - (sk - w)) / (2.0 * w))
    bow = np.asarray(B['bow'], np.float64)
    tilt += np.radians(PchipInterpolator(bow[:, 0], bow[:, 1], extrapolate=True)(s))
    lat_k = np.asarray(B['lateral'], np.float64)
    lat = np.radians(PchipInterpolator(lat_k[:, 0], lat_k[:, 1], extrapolate=True)(s))
    T = np.column_stack([-np.sin(tilt) * np.cos(lat), np.sin(lat), np.cos(tilt) * np.cos(lat)])
    P = np.zeros_like(T)
    P[1:] = np.cumsum(0.5 * (T[1:] + T[:-1]) * np.diff(s)[:, None], axis=0)
    e = np.column_stack([np.cos(tilt), np.zeros_like(tilt), np.sin(tilt)])       # the front, in the tines' plane
    n = unit(e - T * np.sum(e * T, axis=1, keepdims=True))
    return s, P, T, n


def _interp_rows(s, P, T, n, at):
    j = int(np.clip(np.searchsorted(s, at, side='right') - 1, 0, len(s) - 2))
    u = (at - s[j]) / (s[j + 1] - s[j])
    p = P[j] * (1 - u) + P[j + 1] * u
    t = unit(T[j] * (1 - u) + T[j + 1] * u)
    nn = n[j] * (1 - u) + n[j + 1] * u
    nn = unit(nn - t * float(nn @ t))
    return p, t, nn


def _tine_curve(row, base, T_ref, T_dist, front, kind, ds=2.0):
    """a tine's centreline in the part frame (mm). kind 'main': the launch at 180 - out from T_ref (the beam BELOW
    the fork); 'crown': at `fork` from T_ref (the beam ABOVE the fork). az turns the launch about T_ref from the front
    toward out (out = T_ref x front). bend: (degrees, direction) pairs, the direction turning about the launch from
    'toward the beam's distal side' (0) toward out (90). Returns stations u (N,), P, T, n (the frame normal: toward
    the distal side, the crotch)"""
    out = np.cross(T_ref, front)
    az = np.radians(row.get('az', 0.0))
    rho = np.cos(az) * front + np.sin(az) * out
    a = np.radians(180.0 - row['out']) if kind == 'main' else np.radians(row['fork'])
    u0 = unit(np.cos(a) * T_ref + np.sin(a) * rho)
    d = T_dist - u0 * float(T_dist @ u0)
    d = unit(d) if np.linalg.norm(d) > 1e-6 else unit(front - u0 * float(front @ u0))
    e = np.cross(u0, d)
    if float(e @ out) < 0.0:
        e = -e
    L = float(row['arc'])
    r_tip = row['girth'] / (2.0 * np.pi) * row['taper'][-1]
    Lc = L - r_tip                                   # the SWEEP ends in a hemisphere of the end radius
    N = max(int(np.ceil(Lc / ds)) + 1, 8)
    u = np.linspace(0.0, 1.0, N)
    Tt = np.zeros((N, 3))
    nn = np.zeros((N, 3))
    prof = row.get('bend_profile', (1.0, 1.0))       # the turning's share along the tine: (weight at 0, at 1)
    wts = prof[0] + (prof[1] - prof[0]) * u
    f = np.concatenate([[0.0], np.cumsum(0.5 * (wts[1:] + wts[:-1]) * np.diff(u))])
    f /= f[-1]
    for i in range(N):
        R = np.eye(3)
        for (deg, dr) in row['bend']:
            w = np.cos(np.radians(dr)) * d + np.sin(np.radians(dr)) * e
            R = rot(np.cross(u0, w), np.radians(deg) * f[i]) @ R
        Tt[i] = R @ u0
        nn[i] = R @ d
    P = np.zeros((N, 3))
    P[1:] = np.cumsum(0.5 * (Tt[1:] + Tt[:-1]) * (np.diff(u) * Lc)[:, None], axis=0)
    return u, base + P, Tt, nn, r_tip


def _taper(row, u):
    tp = np.asarray(row['taper'], np.float64)
    return PchipInterpolator(np.array([0.0, 0.25, 0.5, 0.75, 0.9, 1.0]), tp)(u)


def aged(preset, age):
    """A YOUNGER HEAD OF THE SAME STAG, as data: the row `age` of the preset's `age_table` applied to the preset
    (the table's own comment in species/horn_presets.py says what each number is and where it was read). Preset in,
    preset out: the builder below never knows an age. What a row does:
      - THE STATION AXIS IS WARPED, tine to tine: the prime antler's keys (0, each tine's station, the crown's base,
        the end) go to this head's keys, and EVERY table written against the station (girth, turns, bow, lateral)
        is read through that warp, so a section or a bend stays at its own tine. The first tine's station scales
        with the GIRTH (the brow sits on the burr; so does the burr itself);
      - a tine the row does not name is dropped AND THE BEAM NEITHER TURNS NOR WIDENS AT IT (the beam turns and
        flattens into a fork where a tine leaves: a first head is a plain tapering bow; with the crown's girth keys
        left in, the first head's spike had a knot at 0.59 of its length, build/tmp/now/h13_board_a.png); a short
        tine turns the beam by its share;
      - arcs by the row's share; girths by the row's girth, a short tine thinner again; the fork's blend with them;
      - A SHORT TINE BENDS LESS THAN ITS LENGTH SAYS (the turn by share ** 1.5): the first head's brow at 0.42 of
        its full length with the full 118 degrees was a fish hook; on c06 it is a nearly straight prong, and the
        brow is strongly hooked from the second head on."""
    import copy
    row = (preset.get('age_table') or {}).get(age)
    pr = copy.deepcopy(preset)
    pr.pop('age_table', None)
    if row is None:
        return pr
    B, crown, bu = pr['beam'], pr['crown'], pr['burr']
    L0 = float(B['length'])
    fb, fg = float(row.get('beam', 1.0)), float(row.get('girth', 1.0))
    grow = dict(row.get('tines', {}))
    at = dict(row.get('at', {}))
    L1 = L0 * fb
    c0 = float(crown['base'])
    c1 = float(at['crown']) * L1 if 'crown' in at else c0 * fb
    first = min(pr['tines'], key=lambda t: t['station'])['name']

    def station(name, s):
        if name in at:
            return float(at[name]) * L1
        if name == first:
            return s * fg
        if s >= c0:
            return c1 + (s - c0) / (L0 - c0) * (L1 - c1)
        return s * fb
    rows = list(pr['tines']) + list(crown['tines'])
    k0 = np.array([0.0] + [t['station'] for t in rows] + [c0, L0])
    k1 = np.array([0.0] + [station(t['name'], t['station']) for t in rows] + [c1, L1])
    k0, i = np.unique(k0, return_index=True)
    k1 = np.maximum.accumulate(k1[i] + 1.0e-6 * np.arange(len(i)))

    def warp(s):
        return float(np.interp(s, k0, k1))

    def slope(s):
        j = int(np.clip(np.searchsorted(k0, s, side='right') - 1, 0, len(k0) - 2))
        return float((k1[j + 1] - k1[j]) / (k0[j + 1] - k0[j]))
    share = {t['name']: float(grow.get(t['name'], 0.0)) for t in rows}
    by_station = {float(t['station']): t['name'] for t in rows}
    gone = [float(t['station']) for t in rows if share[t['name']] <= 0.0]
    B['length'] = L1
    # the girth keys within FORK_REACH of a tine that does not exist are the widening into ITS fork: they go with it
    B['girth'] = tuple((warp(s), g * fg, a) for (s, g, a) in B['girth']
                       if not any(abs(float(s) - st) <= FORK_REACH for st in gone))
    B['turns'] = tuple((warp(s), deg * float(sstep(share.get(by_station.get(float(s)), 1.0) / 0.5)), w * slope(s))
                       for (s, deg, w) in B['turns'])
    B['bow'] = tuple((warp(s), deg) for (s, deg) in B['bow'])
    B['lateral'] = tuple((warp(s), deg) for (s, deg) in B['lateral'])
    for key in ('station', 'length', 'low_proud', 'seal_dome'):
        if key in bu:
            bu[key] = bu[key] * fg
    # a thinner burr carries fewer lumps of the same size (the crust's rows, its furrows and its small nodules)
    if 'nodules' in bu:
        bu['nodules'] = tuple((max(10, int(round(n * fg))),) + tuple(rest) for (n, *rest) in bu['nodules'])
    for key in ('notches', 'crust'):
        if key in bu:
            bu[key] = int(round(bu[key] * fg))
    if bu.get('rim'):
        bu['rim'] = dict(bu['rim'], r=bu['rim']['r'] * fg, wander=tuple(v * fg for v in bu['rim']['wander']),
                         blend=bu['rim']['blend'] * fg)

    def grown(t):
        f = share[t['name']]
        t = dict(t, station=warp(t['station']), arc=t['arc'] * f, girth=t['girth'] * fg * (0.55 + 0.45 * f),
                 bend=tuple((deg * min(f, 1.0) ** 1.5, dr) for (deg, dr) in t['bend']))
        for key in ('secant', 'sagitta'):
            if key in t:
                t[key] = t[key] * f
        return t
    pr['tines'] = tuple(grown(t) for t in pr['tines'] if share[t['name']] > 0.0)
    crown['tines'] = tuple(grown(t) for t in crown['tines'] if share[t['name']] > 0.0)
    crown['base'] = c1
    crown['top'] = dict(crown['top'], girth=crown['top']['girth'] * fg)
    pr['blend'] = pr['blend'] * max(fg, 0.5)
    pr['age'] = age
    return pr


def antler(preset, age=None, side='L', scale=None, U_host=None, only=None):
    """the red deer family's skeleton from a preset (mm, degrees) -> Skeleton in metres, in the host's head axes.
    age: a head number of the preset's age table (None: the prime antler as the preset stands; `aged` above makes
    the younger head's preset); only: a tuple of branch names to keep (a class template's own build). scale: a
    number, or from U_host / U_native (isometric)"""
    import copy
    pr = copy.deepcopy(preset) if age is None else aged(preset, age)
    pr.pop('age_table', None)
    sc = float(scale) if scale is not None else (float(U_host) / pr['U_native'] * 1000.0 if U_host else 1.0)
    B = pr['beam']
    crown = pr['crown']
    s, P, T, n = _beam_curve(B)
    girth = np.asarray(B['girth'], np.float64)
    s_last = crown['tines'][-1]['station'] if crown['tines'] else crown['base']
    top = crown['top']
    # the beam's girth and thickness / width: the measured keys up to the last fork, then the top as a tine
    Ltop = B['length'] - s_last
    r_tip = top['girth'] / (2.0 * np.pi) * top['taper'][-1]
    keep = s <= B['length'] - r_tip + 1e-9
    s, P, T, n = s[keep], P[keep], T[keep], n[keep]
    g_fork = float(PchipInterpolator(girth[:, 0], girth[:, 1])(s_last))
    ut = np.clip((s - s_last) / Ltop, 0.0, 1.0)
    g_top = PchipInterpolator(np.array([0.0, 0.25, 0.5, 0.75, 0.9, 1.0]),
                              np.array([g_fork] + [top['girth'] * t for t in top['taper'][1:]]))(ut)
    g = np.where(s <= s_last, PchipInterpolator(girth[:, 0], girth[:, 1])(np.minimum(s, s_last)), g_top)
    # the top starts from the section AT the last fork. The prime antler's last fork is the table's last key (kept
    # as written: its low and bake are keyed to these bytes); a younger head's last fork lies between keys
    asp_fork = float(girth[-1, 2]) if pr.get('age') is None else \
        float(PchipInterpolator(girth[:, 0], girth[:, 2])(s_last))
    asp = np.where(s <= s_last, PchipInterpolator(girth[:, 0], girth[:, 2])(np.minimum(s, s_last)),
                   asp_fork + (1.0 - asp_fork) * sstep(ut / 0.55))
    r0 = ellipse_half_width(g, asp)
    # the egg toward the front where a tine leaves (the beam widens toward its fork), and the burr's low lobes
    a3 = np.zeros_like(s)
    forks = [(t['station'], 0.07) for t in pr['tines']] + [(t['station'], 0.05) for t in crown['tines']]
    for (sk, amp) in forks:
        a3 += amp * np.exp(-0.5 * ((s - sk) / 22.0) ** 2)
    bu = pr['burr']
    wb = np.exp(-0.5 * ((s - bu['station']) / (0.45 * bu['length'])) ** 2)
    a2 = bu['lobes'][0] * wb
    a4 = bu['lobes'][1] * wb
    branches = [Branch('beam', 'beam', P, n, r0, asp, a2=a2, phi2=0.6, a3=a3, phi3=0.0, a4=a4, cls=None,
                       meta=dict(stations={t['name']: t['station'] for t in list(pr['tines']) + list(crown['tines'])},
                                 crown_base=crown['base'], r_tip=r_tip, length=B['length']))]
    turn_w = {sk: w for (sk, _, w) in B['turns']}
    rows = [('main', t) for t in pr['tines']] + [('crown', t) for t in crown['tines']]
    for kind, row in rows:
        st = row['station']
        w = turn_w.get(st, 20.0)
        base, _, _ = _interp_rows(s, P, T, n, st)
        _, T_below, n_below = _interp_rows(s, P, T, n, max(st - w, 0.0))
        _, T_above, n_above = _interp_rows(s, P, T, n, min(st + w, s[-1]))
        T_ref, front = (T_below, n_below) if kind == 'main' else (T_above, n_above)
        u, Pt, Tt, nt, rt = _tine_curve(row, base, T_ref, T_above, front, kind)
        gt = row['girth'] * _taper(row, u)
        aspt = row['flat'] + (1.0 - row['flat']) * sstep(u / 0.55)
        a3t = 0.06 * (1.0 - sstep(u / 0.30))
        r0t = ellipse_half_width(gt, aspt)
        # THE ROOT HIDES IN THE BEAM: a tine's centreline starts ON the beam's centreline, and its base section is
        # about as wide as the beam is thick, so its round end cap stood through the beam's far side as a bump (the
        # first clay, build/look/h04_clay_a.png). Inside the beam the root narrows to ROOT_HIDE of the beam's least
        # half axis, back to its own width by the time it leaves the beam's surface
        j_b = int(np.clip(np.searchsorted(s, st), 0, len(s) - 1))
        rb_min = float(r0[j_b] * min(asp[j_b], 1.0))
        s_t = u * (row['arc'] - rt)
        root = np.minimum(1.0, ROOT_HIDE * rb_min / r0t[0] + (1.0 - ROOT_HIDE * rb_min / r0t[0]) *
                          sstep(s_t / (1.25 * float(r0[j_b]))))
        branches.append(Branch(row['name'], 'tine', Pt, nt, r0t * root, aspt, a3=a3t, phi3=0.0,
                               parent=0, s_parent=st, meta=dict(arc=row['arc'], r_tip=rt, kind=kind)))
    # THE BURR'S RIM: a low irregular ring round the base (never a torus: DEER_CRITIC 1b), its own branch: a closed
    # sweep that follows the beam's OWN section at the crest station, wandering along the beam and in and out, its
    # thickness changing round it. The beads are the high's strokes (horn_surface); this is the form under them,
    # the step the low models
    rim = pr['burr'].get('rim')
    if rim and (only is None or 'burr' in only):
        rng = np.random.default_rng(int(rim.get('seed', 7)))
        m = 96
        ph = np.linspace(0.0, 2.0 * np.pi, m, endpoint=False)

        def wander(amp, lobes):
            out_ = np.zeros(m)
            for kq in lobes:
                out_ += rng.normal() * np.cos(kq * ph + rng.uniform(0.0, 2.0 * np.pi)) / np.sqrt(len(lobes))
            return amp * out_
        # the lobe counts of the three wanders are the preset's (`rim.lobes`; absent: the first drawing's)
        lz, lr, lt = rim.get('lobes', ((1, 2, 3), (2, 3, 5), (2, 3, 4, 7)))
        dz = wander(rim['wander'][0], lz)
        dr = wander(rim['wander'][1], lr)
        tr = rim['r'] * (1.0 + wander(rim['r_var'], lt))
        Pr = np.zeros((m, 3))
        for i in range(m):
            p_c, t_c, n_c = _interp_rows(s, P, T, n, bu['station'] + dz[i])
            b_c = np.cross(t_c, n_c)
            g_c = float(np.interp(bu['station'] + dz[i], s, g))
            a_c = float(np.interp(bu['station'] + dz[i], s, asp))
            rr = float(section_radius(ellipse_half_width(g_c, a_c), a_c, 0.0, 0.0, 0.0, 0.0, 0.0, ph[i]))
            Pr[i] = p_c + (rr + dr[i] + rim['proud'] * tr[i]) * (np.cos(ph[i]) * n_c + np.sin(ph[i]) * b_c)
        Pr = np.vstack([Pr, Pr[:1]])
        tr = np.concatenate([tr, tr[:1]])
        _, t_c, _ = _interp_rows(s, P, T, n, bu['station'])
        branches.append(Branch('burr', 'rim', Pr, np.tile(t_c, (m + 1, 1)), tr, rim.get('tall', 1.0), parent=0,
                               s_parent=bu['station'], meta=dict(r_tip=0.0, kind='rim', closed=True)))
    for cname, members in pr.get('classes', {}).items():
        for b in branches:
            if b.name in members:
                b.cls = cname
    if only is not None:
        branches = [b for b in branches if b.name in only]
    # into the head axes, metres; the right part mirrored
    x, y, z = part_frame(pr['launch'])
    M = np.column_stack([x, y, z])                    # part -> head
    k = sc * MM
    for b in branches:
        b.P = (b.P @ M.T) * k
        b.T, b.n, b.b = b.T @ M.T, b.n @ M.T, b.b @ M.T
        b.s, b.length, b.r0, b.s_parent = b.s * k, b.length * k, b.r0 * k, b.s_parent * k
        for key in ('arc', 'r_tip', 'length', 'crown_base'):
            if key in b.meta:
                b.meta[key] *= k
        if 'stations' in b.meta:
            b.meta['stations'] = {nm: v * k for nm, v in b.meta['stations'].items()}
    if side == 'R':
        mir = np.array([-1.0, 1.0, 1.0])
        for b in branches:
            b.P, b.T, b.n = b.P * mir, b.T * mir, b.n * mir
            b.b = np.cross(b.T, b.n)
            b.phi2, b.phi3 = -b.phi2, -b.phi3
        x, y, z = x * mir, -y * mir, z * mir
    return Skeleton('antler', branches, (np.zeros(3), x, y, z), pr['blend'] * k, pr, scale=sc, side=side,
                    meta=dict(burr=dict(station=bu['station'] * k, length=bu['length'] * k),
                              rim_blend=(rim or {}).get('blend', 2.5) * k, seal_dome=bu.get('seal_dome', 0.0) * k))


# ------------------------------------------------------------------------------- the other families: skeletons
def natural_spiral(length, excursion, turn, curl_ratio, hand=1.0, n=400):
    """the bovid's centreline (mm, its own frame: z the curl's axis): radius of curvature and of torsion linear in
    arc length with kappa / tau constant, so the tangent keeps one angle beta to the curl's axis and the projection
    is a planar log-like spiral (the horns study §5.2; W/deer/horns/scripts/natural_spiral_check.py, re-derived).
    From the BASE (sigma = length) to the tip (0). Returns P (n, 3), T, the principal normal"""
    beta = np.arccos(excursion / length)                     # the tangent's angle to the axis
    Lp = length * np.sin(beta)                               # the projected length
    # projected radius rho = a sig + b over the projected arc sig in [0, Lp]: tip rho_t, base curl_ratio * rho_t,
    # turning the given number of turns: integral dsig / rho = 2 pi turn
    k = np.log(curl_ratio) / (2.0 * np.pi * turn)            # a = k
    rho_t = k * Lp / (curl_ratio - 1.0)
    sig = np.linspace(Lp, 0.0, n)                            # base -> tip
    rho = k * sig + rho_t
    ang = np.log(rho / rho[0]) / k * hand                    # the projected tangent's angle
    tx, ty = np.cos(ang), np.sin(ang)
    T = np.column_stack([np.sin(beta) * tx, np.sin(beta) * ty, np.full(n, np.cos(beta))])
    ds = np.abs(np.diff(sig)) / np.sin(beta)
    P = np.zeros((n, 3))
    P[1:] = np.cumsum(0.5 * (T[1:] + T[:-1]) * ds[:, None], axis=0)
    Nn = np.column_stack([-ty, tx, np.zeros(n)]) * hand * -1.0      # toward the centre of curvature
    return P, T, Nn


def spiral(preset, side='L', scale=None, U_host=None):
    """a bovid horn's skeleton: one branch on the natural 3D spiral, its section from the preset's keys (u from the
    base, half width mm, thickness / width, third harmonic). Sections are [E] until HN3 measures them"""
    sp = preset['spiral']
    sc = float(scale) if scale is not None else (float(U_host) / preset['U_native'] * 1000.0 if U_host else 1.0)
    P, T, Nn = natural_spiral(sp['length'], sp['excursion'], sp['turn'], sp['curl_ratio'], sp.get('hand', 1.0))
    keys = np.asarray(preset['section']['keys'], np.float64)
    seg = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    u = seg / seg[-1]
    r0 = PchipInterpolator(keys[:, 0], keys[:, 1])(u)
    asp = PchipInterpolator(keys[:, 0], keys[:, 2])(u)
    a3 = PchipInterpolator(keys[:, 0], keys[:, 3])(u)
    keep = seg <= seg[-1] - r0[-1]
    # the horn's own frame onto the part frame: its first tangent is the root axis z, its first normal the front x
    z0, x0 = T[0], unit(Nn[0] - T[0] * float(Nn[0] @ T[0]))
    R0 = np.column_stack([x0, np.cross(z0, x0), z0])         # horn -> part
    x, y, z = part_frame(preset['launch'])
    M = np.column_stack([x, y, z]) @ R0.T
    k = sc * MM
    b = Branch('horn', 'sheath', (P[keep] @ M.T) * k, Nn[keep] @ M.T, r0[keep] * k, asp[keep], a3=a3[keep],
               meta=dict(bands=preset.get('bands')))
    if side == 'R':
        mir = np.array([-1.0, 1.0, 1.0])
        b = Branch('horn', 'sheath', b.P * mir, b.n * mir, b.r0, b.asp, a3=b.a3, phi3=-b.phi3, meta=b.meta)
        x, y, z = x * mir, -y * mir, z * mir
    return Skeleton('spiral', [b], (np.zeros(3), x, y, z), 0.0, preset, scale=sc, side=side)


def cone(preset, side='L', scale=None, U_host=None, n=200):
    """a bent cone's skeleton (rhino horn, tusk, ossicone): length, base and tip diameters, a bend (degrees, toward
    -x: back), thickness / width, an optional helix (starts, angle, hand, amp: the third harmonic's phase advancing
    2 pi / P per unit length with P = pi D tan(angle), the tusk's rule). Sections are [E] until HN3 measures them"""
    c = preset['cone']
    sc = float(scale) if scale is not None else (float(U_host) / preset['U_native'] * 1000.0 if U_host else 1.0)
    L = float(c['length'])
    u = np.linspace(0.0, 1.0, n)
    r = 0.5 * (c['base_d'] + (c['tip_d'] - c['base_d']) * u)
    if c.get('knob'):
        r = r * (1.0 + (c['knob'] - 1.0) * np.exp(-0.5 * ((u - 0.9) / 0.08) ** 2))
    tilt = np.radians(c.get('bend', 0.0)) * u
    T = np.column_stack([-np.sin(tilt), np.zeros(n), np.cos(tilt)])
    keep = u * L <= L - r[-1]
    P = np.zeros((n, 3))
    P[1:] = np.cumsum(0.5 * (T[1:] + T[:-1]) * (np.diff(u) * L)[:, None], axis=0)
    nn = np.column_stack([np.cos(tilt), np.zeros(n), np.sin(tilt)])
    a3 = np.zeros(n)
    phi3 = np.zeros(n)
    hx = c.get('helix')
    if hx:
        pitch = np.pi * 2.0 * r * np.tan(np.radians(hx['angle']))
        dphi = 2.0 * np.pi / np.maximum(pitch, 1e-9) * (np.diff(u, prepend=0.0) * L)
        phi3 = np.cumsum(dphi) * hx['hand'] / hx['starts']
        a3 = np.full(n, hx['amp'])
    x, y, z = part_frame(preset['launch'])
    M = np.column_stack([x, y, z])
    k = sc * MM
    b = Branch('horn', 'cone', (P[keep] @ M.T) * k, nn[keep] @ M.T, r[keep] * k, c.get('aspect', 1.0), a3=a3[keep],
               phi3=phi3[keep])
    if side == 'R':
        mir = np.array([-1.0, 1.0, 1.0])
        b = Branch('horn', 'cone', b.P * mir, b.n * mir, b.r0, b.asp, a3=b.a3, phi3=-b.phi3)
        x, y, z = x * mir, -y * mir, z * mir
    return Skeleton('cone', [b], (np.zeros(3), x, y, z), 0.0, preset, scale=sc, side=side)


BUILDERS = dict(antler=antler, spiral=spiral, cone=cone)


def build(preset, **kw):
    """the skeleton of any preset: the family is data"""
    return BUILDERS[preset['family']](preset, **kw)


# --------------------------------------------------------------------------------------------- the block-out
def program(skel, blend=None, seal=True, only=None):
    """the block-out as an sdf.Program: every branch a SWEEP with its own measured section, all in ONE n-ary ROUND
    union (radius = the preset's blend: a crotch is a saddle, not a seam), then the SIGNET cut flat through the root
    (a SWEEP's own end is a hemisphere; a cast antler's is its seal). only: branch names (a template's own high)"""
    from .. import sdf as S
    prog = S.Program()
    k = float(skel.blend if blend is None else blend)
    allb = [b for b in skel.branches if only is None or b.name in only]
    brs = [b for b in allb if b.kind != 'rim']
    if k > 0.0 and len(brs) > 1:
        prog.begin_group(S.UNION, 0.0)
        for b in brs:
            prog.sweep(b.P, b.n, b.r0, a2=b.a2, phi2=b.phi2, a3=b.a3, phi3=b.phi3, a4=b.a4, aspect=b.asp,
                       op=S.ROUND, k=k, name=b.name)
        prog.end_group()
    else:
        for b in brs:
            prog.sweep(b.P, b.n, b.r0, a2=b.a2, phi2=b.phi2, a3=b.a3, phi3=b.phi3, a4=b.a4, aspect=b.asp, name=b.name)
    # the burr's rim keeps its ledge: a small smooth union of its own, never the crotches' wide round one
    for b in allb:
        if b.kind == 'rim':
            prog.sweep(b.P, b.n, b.r0, aspect=b.asp, op=S.UNION, k=float(skel.meta.get('rim_blend', 0.0025)),
                       name=b.name)
    if seal and skel.branches[0] in brs:
        root = skel.branches[0]
        R = 2.5 * float(root.r0[:8].max())
        axes = np.column_stack([skel.x, skel.y, skel.z])
        prog.roundbox(skel.origin - skel.z * R, [R, R, R], r=0.0, axes=axes, op=S.SUBTRACT, k=0.0012, name='signet')
        dome = float(skel.meta.get('seal_dome', 0.0))
        if dome > 0.0:
            # a cast antler's seal is a low convex face, not a sawn flat: a flat dome on the cut
            rs = float(root.r0[0])
            prog.ellipsoid(skel.origin, [0.93 * rs, 0.93 * rs * float(root.asp[0]), dome], axes=axes, op=S.UNION,
                           k=0.0015, name='seal')
    return prog


# ----------------------------------------------------------------------------------------------- the measures
def _sagitta(P):
    """the greatest distance of a polyline from its chord"""
    c = P[-1] - P[0]
    L = np.linalg.norm(c)
    q = P - P[0]
    d = q - np.outer(q @ c / (L * L), c)
    return float(np.linalg.norm(d, axis=1).max()), float(L)


def measures(skel):
    """the built antler in Bils' own measures (mm, degrees): the gate's table. Angles between centrelines as the
    paper takes them: the tine's outgoing angle to the beam below its base, the beam's angle at each tine"""
    out = {}
    k = 1.0 / (skel.scale * MM)
    beam = skel.branches[0]
    out['beam_length'] = (beam.length + beam.meta.get('r_tip', 0.0)) * k
    cb = beam.meta.get('crown_base')
    if cb is not None:
        j = int(np.searchsorted(beam.s, cb))
        out['beam_sagitta'] = _sagitta(beam.P[:j + 1])[0] * k
        out['crown_base'] = cb * k
    for nm, st in beam.meta.get('stations', {}).items():
        out[f'station_{nm}'] = st * k
    for s_mm, name in ((3.0, 'signet'), (8.0, 'burr'), (22.0, 'base_brow'), (66.0, 'brow_bay'), (185.0, 'lower_beam'),
                       (420.0, 'upper_beam')):
        out[f'girth_{name}'] = beam.girth(s_mm * skel.scale * MM) * k
    rims = [b for b in skel.branches if b.kind == 'rim']
    if rims:
        # the burr's girth is the tape round the rim's outside: its nodes pushed out by the rim's own depth, in the
        # plane square to the beam at the crest
        rm = rims[0]
        p_c, _, _, t_c = beam.frame(rm.s_parent)
        q = rm.P[:-1] - p_c
        q = q - np.outer(q @ t_c, t_c)
        rad = np.linalg.norm(q, axis=1)
        q = q * ((rad + rm.r0[:-1] * rm.asp[:-1]) / rad)[:, None]
        out['girth_burr'] = float(np.linalg.norm(np.roll(q, -1, axis=0) - q, axis=1).sum()) * k
    tips = {}
    for b in skel.branches[1:]:
        if b.kind == 'rim':
            continue
        tip = b.P[-1] + b.T[-1] * b.meta['r_tip']
        tips[b.name] = tip
        sag, chord = _sagitta(np.vstack([b.P, tip]))
        out[f'{b.name}_arc'] = (b.length + b.meta['r_tip']) * k
        out[f'{b.name}_secant'] = chord * k
        out[f'{b.name}_sagitta'] = sag * k
        out[f'{b.name}_girth_mid'] = b.girth(0.5 * (b.length + b.meta['r_tip'])) * k
        w = 0.022 * skel.scale
        _, _, _, t_below = beam.frame(max(b.s_parent - w, 0.0))
        _, _, _, t_above = beam.frame(min(b.s_parent + w, beam.length))
        out[f'{b.name}_out'] = float(np.degrees(np.arccos(np.clip(-t_below @ b.T[0], -1, 1))))
        out[f'{b.name}_beam_angle'] = float(180.0 - np.degrees(np.arccos(np.clip(t_below @ t_above, -1, 1))))
        out[f'{b.name}_to_distal'] = float(np.degrees(np.arccos(np.clip(t_above @ b.T[0], -1, 1))))
    d = lambda a, b_: float(np.linalg.norm(a - b_)) * k                           # noqa: E731
    if cb is not None:
        pc = beam.frame(cb)[0]
        for a, b_ in (('brow', 'bay'), ('brow', 'tray'), ('bay', 'tray')):
            if a in tips and b_ in tips:
                out[f'tip_{a}_{b_}'] = d(tips[a], tips[b_])
        for a in ('brow', 'tray'):
            if a in tips:
                out[f'tip_{a}_crown_base'] = d(tips[a], pc)
        # the crown's box in the beam's frame at its base: height along the beam, length in the tines' plane, width
        _, n_, b_, t_ = beam.frame(cb)
        pts = [beam.P[-1] + beam.T[-1] * beam.meta['r_tip']] + [tips[b.name] for b in skel.branches[1:]
                                                                 if b.meta.get('kind') == 'crown']
        pts = np.array(pts + [pc])
        q = (pts - pc)
        out['crown_height'] = float((q @ t_).max() - (q @ t_).min()) * k
        out['crown_length'] = float((q @ n_).max() - (q @ n_).min()) * k
        out['crown_width'] = float((q @ b_).max() - (q @ b_).min()) * k
    out['tips'] = {nm: (v * k).round(1).tolist() for nm, v in tips.items()}
    return out


# Bils, Willems & Reiner 2023, mean and sd (mm, degrees): what measures() is read against
BILS = dict(beam_length=(967.5, 101.1), beam_sagitta=(55.1, 17.0), girth_signet=(184.8, 18.8),
            girth_burr=(245.9, 21.0), girth_base_brow=(215.2, 23.9), girth_brow_bay=(189.4, 26.9),
            girth_lower_beam=(145.6, 13.9), girth_upper_beam=(134.7, 15.4),
            brow_arc=(351.1, 46.7), brow_secant=(293.9, 33.5), brow_sagitta=(79.3, 19.0), brow_girth_mid=(92.7, 9.9),
            brow_out=(108.8, 10.0), brow_beam_angle=(138.5, 11.3),
            bay_arc=(294.2, 92.8), bay_secant=(264.6, 76.2), bay_sagitta=(55.4, 24.5), bay_girth_mid=(80.2, 11.0),
            bay_out=(98.8, 9.1), bay_beam_angle=(173.7, 6.4),
            tray_arc=(352.1, 71.4), tray_secant=(300.7, 55.0), tray_sagitta=(80.7, 22.9), tray_girth_mid=(88.9, 12.0),
            tray_out=(116.9, 8.0), tray_beam_angle=(159.1, 6.7),
            tip_brow_bay=(176.6, 45.0), tip_brow_tray=(336.7, 92.5), tip_bay_tray=(260.4, 65.3),
            tip_brow_crown_base=(512.8, 84.4), tip_tray_crown_base=(262.8, 39.7),
            crown_a_arc=(261.2, 57.8), crown_c_arc=(196.4, 68.8),
            crown_height=(333.3, 61.4), crown_length=(336.1, 82.1), crown_width=(210.3, 74.6))


def gate_table(skel, log=print):
    """measures() beside Bils' means: value, mean +- sd, z. Returns (rows, worst |z|)"""
    m = measures(skel)
    rows, worst = [], 0.0
    for key, (mu, sd) in BILS.items():
        if key not in m:
            continue
        z = (m[key] - mu) / sd
        worst = max(worst, abs(z))
        rows.append((key, m[key], mu, sd, z))
        log(f'  {key:24s} {m[key]:8.1f}   Bils {mu:7.1f} +- {sd:5.1f}   z {z:+5.2f}' + ('   <-- over 1 sd' if
                                                                                         abs(z) > 1.0 else ''))
    return rows, worst
