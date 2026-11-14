"""THE PATTERNS: each garment as a region of the body's own surface (HUMAN_PLAN §6.8: garments built from the real
underbody, junctions on the base's own rings) and a REST SHAPE with its ease, both on the T rest of the glb.

The region: the welded skin_BODY, subdivided once (the new points projected back onto the skin), the parts away from the
garment dropped by the ring components (legs for a top, the arms and the feet for trousers), then CUT by continuous
fields (meshops.cut: each opening an exact boundary): the hem's height (a shirt tail curves: lower front and back than at
the side seams), the sleeve's length along the arm, the neckline (an elliptic cylinder round the neck under a plane
tilted front-down), the waistband's height.

The rest shape (what the cloth is cut to): every point moved off the skin by the fabric's stand-off plus the EASE, and
the BRIDGES a cloth makes over hollows: across each section its convex hull (the cleavage, the spine's groove); DOWN
the body (B2b, the lead's call 11-08: sewn darts, not the pinch pleats a straight hang gathered under the bust) the
taut line from the bust (behind: the blades) to the waist and hip, per angle round the trunk, of which the DARTS take
a share back toward the waist (the cloth between is the cone a dart sews, so the drape has no excess to pleat); a
straight-leg trouser hangs as the taut line down each leg from the seat to the ankle (the calf inside the tube, not
moulded by it); the sleeve's opening a little wider than the arm. The displacement is smoothed over the surface so no
bridge leaves a crease. The trouser leg is then EXTENDED past the ankle ring as a straight tube to the hem height (it
falls onto the shoe in the drape: the break).
  darts  shirts: 'dart_take' of the hang taken in at the waist, the front's (F) from 3 cm under the bust point, the
         back's from 5 cm under the blades; the sewn line is drawn by the bake (outfit._pattern_lines). The tee is
         SIDE-SHAPED (a knit has no darts: the same take, smaller, its line the side seam it already has).

SPECS (lengths in metres; F and M read the same spec, the body gives the sizes):
    tee        crew neck, short sleeve, straight hem at the high hip, jersey
    shirt_ss   collared shirt, short sleeve, shirt-tail hem, poplin
    shirt_ls   collared shirt, long sleeve to the wrist (a 6 cm cuff), shirt-tail hem, poplin
    trousers   mid rise, straight leg, full length (a half break on the shoe), cotton twill
"""
import numpy as np

from . import meshops as mo

RINGS = ['neck', 'shoulder_L', 'shoulder_R', 'elbow_L', 'elbow_R', 'wrist_L', 'wrist_R', 'hip_L', 'hip_R', 'knee_L',
         'knee_R', 'ankle_L', 'ankle_R', 'waist']

SPECS = {
    # the tee (side-shaped, no lines). Tried 0.15 / 0.10 (11-09): the fold round the waist sides stayed: it is the
    # trousers' waistband's open top edge under the tee (y 1.01 F), where the drape's fastest vertices sit too
    'tee': dict(kind='top', fabric='jersey', sleeve_s=0.33, hem_up=0.075, tail=0.0, neck='crew', ease_chest=0.016,
                dart_take=(0.45, 0.35), dart_lines=False, ease_sleeve=(0.010, 0.020), standoff=0.0025, hem_w=0.022,
                sleeve_hem_w=0.020),
    'shirt_ss': dict(kind='top', fabric='poplin', sleeve_s=0.36, hem_up=0.045, tail=0.045, neck='collar',
                     ease_chest=0.018, dart_take=(0.75, 0.6), dart_lines=True, ease_sleeve=(0.012, 0.022),
                     standoff=0.002, hem_w=0.007, sleeve_hem_w=0.025),
    'shirt_ls': dict(kind='top', fabric='poplin', sleeve_s=0.955, hem_up=0.045, tail=0.045, neck='collar',
                     ease_chest=0.018, dart_take=(0.75, 0.6), dart_lines=True, ease_sleeve=(0.012, 0.016),
                     standoff=0.002, hem_w=0.007, cuff=0.060, cuff_ease=0.009),
    # (B2b) the leg hangs as a taut tube (the calf inside it), so the ease is the chino's own: ~7 cm round the knee
    'trousers': dict(kind='bottom', fabric='twill', rise=0.065, hem_y=0.032, ease_seat=0.008, ease_thigh=0.011,
                     ease_knee=0.011, standoff=0.0025, hem_w=0.035, waistband=0.038),
}


class Frame:
    """the body's garment frames on the T rest: the torso axis, arm and leg axes, landmark heights"""

    def __init__(self, B):
        self.B = B
        Vw, Fw, wid, rep = B.welded()
        self.Vw, self.Fw, self.wid, self.rep = Vw, Fw, wid, rep
        rings = B.rings()
        self.ring_w = {k: np.unique(wid[rings[k]]) for k in RINGS if k in rings}
        bar = np.concatenate(list(self.ring_w.values()))
        lab = mo.components(Fw, len(Vw), bar)
        J = {n: B.joint_pos(n) for n in ['pelvis', 'spine_05', 'neck_01', 'upperarm_L', 'hand_L', 'thigh_L', 'calf_L',
                                          'foot_L', 'ball_L', 'lowerarm_L']}
        self.J = J
        # name the components by a joint inside each
        parts = {}
        for name, p in [('hand_L', J['hand_L'] + [0.05, 0, 0]), ('hand_R', (J['hand_L'] + [0.05, 0, 0]) * [-1, 1, 1]),
                        ('foot_L', J['ball_L']), ('foot_R', J['ball_L'] * [-1, 1, 1]),
                        ('shin_L', 0.5 * (J['calf_L'] + J['foot_L'])), ('shin_R', 0.5 * (J['calf_L'] + J['foot_L']) * [-1, 1, 1]),
                        ('torso_up', J['spine_05'] + [0, 0, 0.08]), ('torso_low', J['pelvis'] + [0, 0, 0.09])]:
            k = lab[np.argmin(np.linalg.norm(Vw - p, axis=1) + 10.0 * np.isin(np.arange(len(Vw)), bar))]
            parts[name] = k
        self.part_of = lab
        self.parts = parts
        self.bar = bar
        # landmarks
        tor = np.isin(lab, [parts['torso_up'], parts['torso_low']])
        mid = tor & (np.abs(Vw[:, 0]) < 0.012)
        self.crotch_y = float(Vw[mid, 1].min())
        self.neck = Vw[self.ring_w['neck']]
        self.waist_y = float(Vw[self.ring_w['waist'], 1].mean())
        self.x_sh = float(J['upperarm_L'][0])
        self.arm_len = float(J['hand_L'][0] - J['upperarm_L'][0])
        self.arm_axis = (J['upperarm_L'][1], J['upperarm_L'][2])
        self.leg_axis = (float(J['thigh_L'][0]), float(J['thigh_L'][2]))
        self.knee_y = float(J['calf_L'][1])
        self.ankle_y = float(Vw[self.ring_w['ankle_L'], 1].mean())
        # the torso's centre line z(y) and the chest band
        ys = np.linspace(self.crotch_y, self.neck[:, 1].min(), 40)
        zc = []
        for y in ys:
            m = tor & (np.abs(Vw[:, 1] - y) < 0.02)
            zc.append(0.5 * (Vw[m, 2].min() + Vw[m, 2].max()) if m.sum() > 4 else np.nan)
        zc = np.array(zc)
        ok = ~np.isnan(zc)
        # ONE vertical axis for the trunk (the sections' mid-depth averaged from the crotch to the neck): a centre that
        # followed each section would ride forward with the bust and read the bust as narrower than the belly
        self._zc = (ys[ok], np.full(ok.sum(), float(np.mean(zc[ok]))))
        front = tor & (np.abs(Vw[:, 0]) < 0.10) & (Vw[:, 1] > self.waist_y) & (Vw[:, 1] < self.neck[:, 1].min() - 0.08)
        self.bust_y = float(Vw[front][np.argmax(Vw[front, 2]), 1])
        back = tor & (Vw[:, 1] > self.waist_y) & (Vw[:, 1] < self.neck[:, 1].min() - 0.05)
        self.blade_y = float(Vw[back][np.argmin(Vw[back, 2]), 1])
        self.tor_mask = tor
        # (B2b) the darts' places (the left side's; the right mirrors): the bust point (the front's most forward point
        # off the centre line) and the blade's (the back's rearmost)
        fl = tor & (Vw[:, 0] > 0.03) & (Vw[:, 0] < 0.16) & (Vw[:, 1] > self.waist_y) & (Vw[:, 1] < self.neck[:, 1].min() - 0.08)
        self.bust_pt = Vw[fl][np.argmax(Vw[fl, 2])].copy()
        bl = tor & (Vw[:, 0] > 0.03) & (Vw[:, 0] < 0.16) & (Vw[:, 1] > self.waist_y) & (Vw[:, 1] < self.neck[:, 1].min() - 0.05)
        self.blade_pt = Vw[bl][np.argmin(Vw[bl, 2])].copy()

    def zc(self, y):
        return np.interp(y, *self._zc)

    def torso_cyl(self, P):
        dz = P[:, 2] - self.zc(P[:, 1])
        return np.arctan2(P[:, 0], dz), np.hypot(P[:, 0], dz)

    def arm_s(self, P):
        return (np.abs(P[:, 0]) - self.x_sh) / self.arm_len

    def arm_cyl(self, P):
        dy, dz = P[:, 1] - self.arm_axis[0], P[:, 2] - self.arm_axis[1]
        return np.arctan2(dz, dy), np.hypot(dy, dz)

    def leg_cyl(self, P):
        sx = np.sign(P[:, 0])
        dx, dz = P[:, 0] - sx * self.leg_axis[0], P[:, 2] - self.leg_axis[1]
        return np.arctan2(sx * dx, dz), np.hypot(dx, dz)


def region(fr, spec):
    """the garment's region on the body surface (T rest): (V, F, attrs{part}, boundary tags) before the rest shape"""
    p = fr.parts
    if spec['kind'] == 'top':
        drop = [p['hand_L'], p['hand_R'], p['foot_L'], p['foot_R'], p['shin_L'], p['shin_R']]
        lab = fr.part_of
        legs = ~np.isin(lab, [p['torso_up'], p['torso_low']]) & (fr.Vw[:, 1] < fr.crotch_y + 0.02) & ~np.isin(
            np.arange(len(lab)), fr.bar)
        bad = np.isin(lab, drop) | legs
    else:
        drop = [p['hand_L'], p['hand_R'], p['foot_L'], p['foot_R']]
        bad = np.isin(fr.part_of, drop) | ((fr.Vw[:, 1] > fr.waist_y + 0.02) & ~fr.tor_mask &
                                            ~np.isin(np.arange(len(fr.Vw)), fr.bar))
        bad |= (np.abs(fr.Vw[:, 0]) > 0.24) & (fr.Vw[:, 1] > 1.0)          # the arms
    keepF = ~bad[fr.Fw].all(axis=1)
    if spec['kind'] == 'bottom':
        keepF &= ~bad[fr.Fw].any(axis=1)
    F0 = fr.Fw[keepF]
    V, F, A, used = mo.compact(fr.Vw, F0, {'bad': bad.astype(float)})
    # subdivide once, the new points back on the skin
    V, F, A = mo.subdivide(V, F, A)
    q, _, _, _ = mo.closest_on_mesh(fr.Vw, fr.Fw, V)
    V = q
    return V, F, A


def fields(fr, spec, V):
    """the opening fields (keep >= 0), each continuous over the region"""
    out = {}
    y = V[:, 1]
    th, _ = fr.torso_cyl(V)
    if spec['kind'] == 'top':
        hem = fr.crotch_y + spec['hem_up'] + spec['tail'] * np.abs(np.sin(th)) ** 1.5
        out['hem'] = y - hem
        out['sleeve'] = spec['sleeve_s'] - fr.arm_s(V)
        nk = fr.neck
        cx = 0.5 * (nk[:, 0].max() - nk[:, 0].min())
        cz = 0.5 * (nk[:, 2].max() + nk[:, 2].min())
        dz = 0.5 * (nk[:, 2].max() - nk[:, 2].min())
        yb = nk[np.argmin(nk[:, 2]), 1]
        sup = fr.B.socket('socket_chest')[:3, 3]
        if spec['neck'] == 'crew':
            a, b, y_front, y_back = cx + 0.012, dz + 0.020, sup[1] - 0.012, yb - 0.012
        else:
            a, b, y_front, y_back = cx + 0.004, dz + 0.008, sup[1] + 0.006, yb - 0.004
        ell = np.sqrt((V[:, 0] / a) ** 2 + ((V[:, 2] - cz) / b) ** 2) - 1.0
        zf, zb = nk[:, 2].max() + 0.02, nk[:, 2].min()
        plane = y_back + (V[:, 2] - zb) / (zf - zb) * (y_front - y_back)
        out['neck'] = np.maximum(ell * 0.1, plane - y)
    else:
        top = fr.waist_y - spec['rise']
        out['waist'] = top - y
    return out


SLEEVE_SPLIT = 0.06          # the armscye on the arm's s (x 0.18 m on the baseline woman: the shoulder point)


def leg_zax(fr, y):
    """the trousers' front / back split's depth: the leg's axis under the crotch, the trunk's centre over it, blended
    over 10 cm (B2b: round 1 switched at the crotch, a step in the outseam)"""
    u = np.clip((y - (fr.crotch_y - 0.05)) / 0.10, 0.0, 1.0)
    return fr.leg_axis[1] * (1 - u) + fr.zc(y) * u


def dart_span(fr, front):
    """(B2b) a dart's point and its lower end, front (under the bust point) or back (under the blade)"""
    y_pt = np.where(front, fr.bust_pt[1] - 0.03, fr.blade_pt[1] - 0.06)
    y_end = np.where(front, fr.waist_y - 0.09, fr.waist_y - 0.13)
    return y_pt, y_end


def seam_fields(fr, spec, V):
    """(B2b) the panel borders as fields, in the order they are inserted: [(name, field, edge restriction or None)].
    Tops: the armscye (s = SLEEVE_SPLIT), the side and shoulder seams (cos th = 0 on the trunk), the centre lines (x = 0:
    a UV cut on a tee, the placket's line on a shirt), the sleeve's top / under split (a UV cut). Trousers: the out- and
    inseams (z = leg_zax), the centre seams (x = 0)"""
    if spec['kind'] == 'top':
        s = fr.arm_s(V)
        th, _ = fr.torso_cyl(V)
        return [('armscye', s - SLEEVE_SPLIT, None),
                ('side', np.cos(th), 'trunk'),
                ('centre', V[:, 0], None),
                ('sleeve', V[:, 1] - fr.arm_axis[0], 'sleeve')]
    return [('side', V[:, 2] - leg_zax(fr, V[:, 1]), None), ('centre', V[:, 0], None)]


def build_region(fr, spec):
    V, F, A = region(fr, spec)
    for k in list(fields(fr, spec, V)):
        f = fields(fr, spec, V)[k]                  # each field evaluated on the mesh as the earlier cuts left it
        V, F, A, fv = mo.cut(V, F, f, A)
        A['open_' + k] = (np.abs(fv) < 1e-9).astype(float)
    # the region's own largest connected piece
    lab = mo.components(F, len(V))
    big = np.bincount(lab[F[:, 0]]).argmax()
    F = F[lab[F[:, 0]] == big]
    V, F, A, _ = mo.compact(V, F, A)
    # (B2b) THE SEAMS as edge chains (each field re-read on the mesh the earlier lines left; the openings' rims and the
    # earlier lines' vertices fixed, so a junction never drags a line off its field)
    on_line = np.zeros(len(V), bool)
    for i in range(4 if spec['kind'] == 'top' else 2):
        name, f, restrict = seam_fields(fr, spec, V)[i]
        fixed = on_line.copy()
        for lp in mo.boundary_loops(F):
            fixed[lp] = True
        ok = None
        if restrict is not None:
            s = fr.arm_s(V)
            m = (s <= SLEEVE_SPLIT + 1e-6) if restrict == 'trunk' else (s >= SLEEVE_SPLIT - 1e-6)
            ok = (lambda m_: (lambda a, b: m_[a] & m_[b]))(m)
        V, F, A, fv = mo.split_line(V, F, f, A, edge_ok=ok, fixed=fixed)
        on_line = np.concatenate([on_line, np.zeros(len(V) - len(on_line), bool)]) | (np.abs(fv) < 1e-12)
    return V, F, A


def rest_shape(fr, spec, V, F):
    """the cloth's rest positions (T rest): the stand-off + ease along the skin's normal, the bridges, smoothed"""
    Nb = _normals_on_body(fr, V)
    y = V[:, 1]
    disp = np.zeros_like(V)
    if spec['kind'] == 'top':
        th, r = fr.torso_cyl(V)
        s = fr.arm_s(V)
        torso = s < -0.05
        # cloth spans a section's hollows (the cleavage, the spine's groove): the radius at each point >= its own
        # section's CONVEX HULL
        zc = fr.zc(y)
        Q = np.column_stack([V[:, 0], V[:, 2] - zc])
        rown = r.copy()
        for y0 in np.arange(y[torso].min(), y[torso].max(), 0.01):
            m = torso & (np.abs(y - y0) < 0.006)
            if m.sum() > 8:
                rown[m] = np.maximum(r[m], _hull_r(_hull(Q[m]), th[m]))
        # (B2b) THE HANG AND THE DARTS. Down the body, per angle, the taut line from the bust (behind: the blades) over
        # the section profile to the waist and the hip: the cloth a straight cut hangs as (round 1's gathered into pinch
        # pleats under the bust in the drape: the hang's excess with nowhere to go). The darts take 'dart_take' of that
        # bridge back in, growing from the dart's point (3 cm under the bust point, 5 cm under the blades) to all of it
        # at the waist: the cone a sewn dart makes, continuous with the section hull above the bust line
        front = np.cos(th) > 0
        yref = np.where(front, fr.bust_pt[1], fr.blade_pt[1])
        # under the waist the cloth also hangs PLUMB from the widest section (the belly, the seat): it never follows
        # the body back in toward the crotch (the hem's notch at the front, d01 b2b)
        hang = _taut(th, y, rown, torso, yref, straight_below=fr.waist_y)
        tk_f, tk_b = spec.get('dart_take', (0.0, 0.0))
        if fr.B.sex != 'F':
            tk_f = 0.0          # (B2b) no bust: a front take pinched the man's tee under the pecs (the engine's close view)
        y_pt, y_end = dart_span(fr, front)
        u = np.clip((y_pt - y) / np.maximum(1e-3, y_pt - fr.waist_y), 0.0, 1.0)
        v = np.clip((y - y_end) / np.maximum(1e-3, fr.waist_y - y_end), 0.0, 1.0)
        # the intake grows from the dart's point to the waist and closes again by the dart's lower end (the hip is
        # wider than the waist: under it the cloth hangs plumb, d01 b2b's crotch notch was the take reaching the hem)
        bump = np.where(y >= fr.waist_y, u * u * (3 - 2 * u), v * v * (3 - 2 * v))
        take = np.where(front, tk_f, tk_b) * bump
        # the darts take in the HANG only: the section hull (a navel, the spine's groove) stays bridged
        renv = rown + (hang - rown) * (1.0 - take)
        grow = np.where(torso, np.maximum(0.0, renv - r), 0.0)
        rad = np.column_stack([np.sin(th), np.zeros_like(th), np.cos(th)])
        disp += rad * grow[:, None]
        env_mask, env_r = torso, renv
        # the ease: the chest's on the torso, the sleeve's (wider toward its opening) on the arm
        e0, e1 = spec['ease_sleeve']
        u = np.clip(s / max(spec['sleeve_s'], 0.05), 0.0, 1.0)
        ease = np.where(s < 0.0, spec['ease_chest'] * 0.55, e0 + (e1 - e0) * u)
        if 'cuff' in spec:
            cuff0 = spec['sleeve_s'] - spec['cuff'] / fr.arm_len
            ease = np.where(s > cuff0, spec['cuff_ease'], ease)
        disp += Nb * (spec['standoff'] + ease)[:, None]
    else:
        th, r = fr.leg_cyl(V)
        leg = (y < fr.crotch_y + 0.005) & (np.abs(V[:, 0]) > 0.012)
        # (B2b) each leg hangs as the taut line down its profile from the seat, and straight down from the widest
        # section under the knee (round 1 hung from the knee's section only: the calf bulged it, lumps in the back view)
        renv = r.copy()
        for sg in (1.0, -1.0):
            m = leg & (np.sign(V[:, 0]) == sg)
            renv[m] = _taut(th, y, r, m, np.full(len(V), fr.crotch_y + 0.005), straight_below=fr.knee_y)[m]
        grow = np.where(leg, np.maximum(0.0, renv - r), 0.0)
        sx = np.sign(V[:, 0])
        rad = np.column_stack([sx * np.sin(th), np.zeros_like(th), np.cos(th)])
        disp += rad * grow[:, None]
        ease = np.where(leg, np.interp(y, [fr.knee_y, fr.crotch_y], [spec['ease_knee'], spec['ease_thigh']]),
                        np.interp(y, [fr.crotch_y, fr.waist_y - spec['rise']], [spec['ease_seat'], 0.003]))
        disp += Nb * (spec['standoff'] + ease)[:, None]
        env_mask, env_r = leg, renv
    # smooth the displacement over the surface (no bridge leaves a crease)
    L = mo.laplacian(V, F)
    for _ in range(30):
        disp = disp + 0.5 * (L @ disp)
    X = V + disp
    # (B2b) and the bridges re-imposed after it: the smoothing had eroded the narrow ones (the navel showed through
    # the shirt, the fold under the bust half bridged): each point out to its envelope + its stand-off and ease
    ease_n = spec['standoff'] + (ease if np.ndim(ease) else np.full(len(V), ease))
    if spec['kind'] == 'top':
        thX, rX = fr.torso_cyl(X)
        radX = np.column_stack([np.sin(thX), np.zeros_like(thX), np.cos(thX)])
    else:
        thX, rX = fr.leg_cyl(X)
        sxX = np.sign(X[:, 0])
        radX = np.column_stack([sxX * np.sin(thX), np.zeros_like(thX), np.cos(thX)])
    # (where the skin faces sideways, or where the envelope bridges: under the bust, over the crotch the cloth hangs at
    # its radius whichever way the skin there faces; on the shoulders' tops the radius is not the stand-off's direction)
    side = (np.abs(Nb[:, 1]) < 0.5) | (grow > 0.002)
    deficit = np.where(env_mask & side, np.maximum(0.0, env_r + ease_n - rX), 0.0)
    X = X + radX * deficit[:, None]
    # cloth does not follow the skin's small relief (the navel, the abdominals, the ribs, the nipples): the rest shape
    # is Taubin-smoothed (no shrink) and pushed back out to its stand-off wherever the smoothing took it closer
    bd = np.zeros(len(V), bool)
    for lp in mo.boundary_loops(F):
        bd[lp] = True
    # smoothing and the stand-off alternate, so a small convex bump (a nipple) is TENTED over rather than restored
    need = spec['standoff'] + 0.003
    its = spec.get('smooth_iters', 160)
    for it in range(its):
        for lam in (0.6, -0.63):
            d = L @ X
            d[bd] = 0.0
            X = X + lam * d
        if it % 4 == 3 or it == its - 1:
            q, _, _, sd = mo.closest_on_mesh(fr.Vw, fr.Fw, X)
            low = sd < need
            if low.any():
                X[low] = q[low] + _normals_on_body(fr, X[low]) * need
    return X


def _hull(Q):
    """a 2D convex hull as (outward unit normals (e, 2), offsets (e,)), the axis at the origin"""
    from scipy.spatial import ConvexHull
    h = ConvexHull(Q)
    return h.equations[:, :2], -h.equations[:, 2]


def _hull_r(h, th):
    """the hull's radius along each angle th (the direction (sin th, cos th) in (x, z))"""
    n, d = h
    u = np.column_stack([np.sin(th), np.cos(th)])
    c = u @ n.T
    with np.errstate(divide='ignore', invalid='ignore'):
        t = np.where(c > 1e-9, d[None, :] / c, np.inf)
    return t.min(axis=1)


def _taut(th, y, R, mask, yref, nb=72, dy=0.005, straight_below=None):
    """(B2b) the cloth's radius DOWN the body per angle: in each of nb angle bins the profile R(y) (the max per dy slab
    of the masked points) under the bin's yref is replaced by its upper hull (a string pulled taut over it: the cloth
    bridges the hollow under the bust, the blades, the knee's back); with straight_below, under that height the radius
    is also >= the widest section between there and the point (a straight leg hangs from the calf, it is not moulded by
    it). Above yref, and outside the mask, R itself."""
    out = R.copy()
    idx = np.nonzero(mask)[0]
    if len(idx) < 10:
        return out
    Yg = np.arange(y[idx].min() - dy, y[idx].max() + 2 * dy, dy)          # slab centres
    G = np.full((nb, len(Yg)), np.nan)
    tb = (th + np.pi) / (2 * np.pi) * nb
    b = np.floor(tb).astype(int) % nb
    for k in range(nb):
        m = idx[b[idx] == k]
        if len(m) < 6:
            continue
        yr = float(np.median(yref[m]))
        j = np.clip(np.round((y[m] - Yg[0]) / dy).astype(int), 0, len(Yg) - 1)
        P = np.full(len(Yg), -np.inf)
        np.maximum.at(P, j, R[m])
        have = np.isfinite(P)
        Yk, Pk = Yg[have], P[have]
        env = Pk.copy()
        low = Yk <= yr
        if low.sum() >= 2:
            Yl, Pl = Yk[low], Pk[low]
            hull = []                                    # the upper hull (monotone chain over y ascending)
            for q in zip(Yl, Pl):
                while len(hull) >= 2:
                    (y1, p1), (y2, p2) = hull[-2], hull[-1]
                    if (y2 - y1) * (q[1] - p1) - (p2 - p1) * (q[0] - y1) >= 0:
                        hull.pop()
                    else:
                        break
                hull.append(q)
            H = np.array(hull)
            el = np.interp(Yl, H[:, 0], H[:, 1])
            if straight_below is not None:
                # the widest slab between each slab and straight_below (a running max from there down)
                run = Pl.copy()
                k0 = np.searchsorted(Yl, straight_below)
                for i in range(min(k0, len(run)) - 2, -1, -1):
                    run[i] = max(run[i], run[i + 1])
                el = np.maximum(el, np.where(Yl < straight_below, run, -np.inf))
            # (B2b) blurred down the body (16 [1 2 1] passes, sigma ~1.4 cm): the plumb starting at the waist was a kink
            # the drape kept as a crease round the waist (the engine's b2still / b2close of the F tee)
            for _ in range(16):
                el = np.concatenate([el[:1], 0.25 * el[:-2] + 0.5 * el[1:-1] + 0.25 * el[2:], el[-1:]]) if len(el) > 2 else el
            env[low] = np.maximum(Pl, el)
        G[k, have] = env
        # the bin's empty slabs inside its own range: interpolated (so a point between two filled slabs reads both)
        if have.sum() >= 2:
            inside = (Yg >= Yk.min()) & (Yg <= Yk.max())
            G[k, inside] = np.interp(Yg[inside], Yk, env)
    # (B2b) across the bins: a [1 2 1] pass (nan-aware, round the trunk), then each point reads the grid BILINEARLY:
    # nearest-bin strings stepped 15 mm between neighbours at the breast's flank (a ledge in d01's render)
    W = np.isfinite(G).astype(float)
    G0 = np.nan_to_num(G)
    num = 2 * G0 + np.roll(G0, 1, 0) + np.roll(G0, -1, 0)
    den = 2 * W + np.roll(W, 1, 0) + np.roll(W, -1, 0)
    Gs = np.where(den > 0, num / np.maximum(den, 1e-9), np.nan)
    kf = tb[idx] - 0.5
    k0 = np.floor(kf).astype(int)
    wk = kf - k0
    jf = (y[idx] - Yg[0]) / dy
    j0 = np.clip(np.floor(jf).astype(int), 0, len(Yg) - 2)
    wj = np.clip(jf - j0, 0, 1)
    acc = np.zeros(len(idx))
    wsum = np.zeros(len(idx))
    for dk, wa in ((0, 1 - wk), (1, wk)):
        for dj, wb in ((0, 1 - wj), (1, wj)):
            v = Gs[(k0 + dk) % nb, j0 + dj]
            ok = np.isfinite(v)
            acc += np.where(ok, v, 0.0) * wa * wb
            wsum += ok * wa * wb
    env_p = np.where(wsum > 1e-6, acc / np.maximum(wsum, 1e-9), R[idx])
    out[idx] = np.where(y[idx] <= yref[idx], np.maximum(R[idx], env_p), R[idx])
    return out


def _normals_on_body(fr, P):
    from .body import vertex_normals
    q, t, bc, _ = mo.closest_on_mesh(fr.Vw, fr.Fw, P)
    Nw = vertex_normals(fr.Vw, fr.Fw)
    n = np.einsum('nk,nkj->nj', bc, Nw[fr.Fw[t]])
    return n / np.linalg.norm(n, axis=1, keepdims=True)


def extend_legs(fr, spec, V, F, Vrest):
    """the trouser legs past the ankle ring: each leg's open loop continued as a straight tube down to the hem height
    (rows ~ the loop's spacing), the rest shape the loop's own rest ring carried straight down"""
    loops = mo.boundary_loops(F)
    V, Vrest, F = V.copy(), Vrest.copy(), F.copy()
    leg_loops = [l for l in loops if V[l, 1].mean() < fr.knee_y]
    for lp in leg_loops:
        y0 = Vrest[lp, 1].mean()
        rows = max(2, int(np.ceil((y0 - spec['hem_y']) / 0.014)))
        prev = lp
        for k in range(1, rows + 1):
            t = k / rows
            Rr = Vrest[lp].copy()
            Rr[:, 1] = Vrest[lp, 1] + (spec['hem_y'] - y0) * t
            ids = np.arange(len(V), len(V) + len(lp))
            V = np.concatenate([V, Rr])
            Vrest = np.concatenate([Vrest, Rr])
            n = len(lp)
            for i in range(n):
                a, b = prev[i], prev[(i + 1) % n]
                c, d = ids[i], ids[(i + 1) % n]
                F = np.concatenate([F, [[b, a, c], [b, c, d]]])
            prev = ids
    return V, F, Vrest


def build(fr, garment):
    spec = SPECS[garment]
    V, F, A = build_region(fr, spec)
    Vr = rest_shape(fr, spec, V, F)
    if spec['kind'] == 'bottom':
        V, F, Vr = extend_legs(fr, spec, V, F, Vr)
    return dict(garment=garment, spec=spec, V_skin=V, F=F, V_rest=Vr)
