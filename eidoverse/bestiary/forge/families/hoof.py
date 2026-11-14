"""HOOVES: the hoof generator (DEER_PLAN §6; work/bestiary/deer/hooves/build_NOTES.md). One generator for every
hoof: the deer's own and a grafted hoof at any leg end are the same code at different sizes (species/hoof_presets.py
holds the rows and the sizing law). HF1 builds the `cervid` preset: the red deer's cloven hoof.

THE FORM IS GROWN, NOT ASSEMBLED FROM PRIMITIVES (Skye, 11-10, on the lobster: "looks overly geometry, not organic
enough shapes"). Horn grows down from the coronet as straight tubules, so a claw's WALL is a RULED surface between
two measured closed curves:
    the CORONET RING   where the haired skin ends: its front point and heel height from the side photos, its plan
                       from the sole outline pulled in by the wall's lean
    the GROUND RING    the bearing border's outer edge: the red deer's sole outline, measured (hoof_presets)
joined column by column at equal shares of each half's length (front point to back point, abaxial and axial side
apart). That one rule gives the straight dorsal wall at its measured angle, the rounded dorsal ridge (the ring's
nose over the blunt toe), the convex abaxial wall, the upright axial wall, and columns that stand up toward the
heel, where the soft BULB takes over (its columns bulge, and its ground ring is its equator, not an edge).
Under the ground ring the same columns run on inward to a spine: the wall's bearing border flat on the ground, the
white line, the sole's trough between the rims, the bulb's rounded underside. Rings of constant v are parallel to
the coronet: they are the growth rings, the low's loops and the UV rows; columns are the tubules.

    F = ClawForm('cervid')                        every length a share of the hoof's length HL
    g = F.grid(n=96)                              the claw as a (rows, columns) grid with its coordinates and zones
    V, T, A = claw_mesh(F, HL, side=+1)           a dense closed mesh (the clay; the high's base) + per-vertex data
    V, T, A = dewclaw_mesh(p, HL)                 the dewclaw template (a blunt flat pad), in its own frame
    prog, info = stump_program(F, HL)             THE NEUTRAL STUMP as an sdf.Program: the two digits' haired skin
                                                  from the coronets up, the fetlock, the cannon's end (the deer's leg
                                                  does not exist yet; D6.4's cage replaces it)
    rows = rig_rows(F, HL)                        the joints and sockets of §8.4's hoof stage, as data

Frame: metres, +Y up, +Z forward (the toes), +X the creature's LEFT; the foot stands on y = 0 with its toe tips at
z = 0 and its midline at x = 0. Internally a point is (x across from the midline, y up, s behind the toe tip) in
shares of HL; the LEFT-side claw (+X) is the template, the other its mirror.
"""
import numpy as np

from ..species import hoof_presets as HP

ZONES = ('tuck', 'periople', 'wall', 'bulb', 'rim', 'white_line', 'sole', 'bulb_under')
Z_TUCK, Z_PERIOPLE, Z_WALL, Z_BULB, Z_RIM, Z_WHITE, Z_SOLE, Z_BULB_UNDER = range(8)


def _ss(a, b, x):
    t = np.clip((np.asarray(x, float) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class _Poly:
    """a polyline by its share of length: P(f), f in 0..1"""

    def __init__(self, P):
        self.P = np.asarray(P, float)
        d = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(self.P, axis=0), axis=1))])
        self.L = float(d[-1])
        self.u = d / d[-1]

    def __call__(self, f):
        f = np.asarray(f, float)
        return np.column_stack([np.interp(f, self.u, self.P[:, k]) for k in range(self.P.shape[1])])


class ClawForm:
    """one claw of a preset, in shares of HL: x across from the foot's midline (the claw on the + side), y up, s
    behind the toe tip. Columns are named by (half, f): half 'ab' (abaxial, the outer side) or 'ax' (axial, the
    cleft side), f the share of the half's length from the front point (f = 0: the dorsal ridge and the toe tip) to
    the back point (f = 1: the middle of the heel)."""

    def __init__(self, preset='cervid'):
        from scipy.interpolate import CubicSpline
        p = self.p = HP.preset(preset)
        self.preset = preset
        s, a, x = HP.outline(preset)
        # the closed plan outline through the measured knots: toe tip -> abaxial edge -> heel -> axial edge -> toe tip
        loop = np.concatenate([np.column_stack([s, a]), np.column_stack([s[-2:0:-1], x[-2:0:-1]])])
        loop = np.vstack([loop, loop[:1]])
        u = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(loop, axis=0), axis=1))])
        cs = CubicSpline(u, loop, bc_type='periodic')
        q = cs(np.linspace(0.0, u[-1], 6001)[:-1])
        i0, i1 = int(np.argmin(q[:, 0])), int(np.argmax(q[:, 0]))
        q = np.roll(q, -i0, axis=0)
        i1 = (i1 - i0) % len(q)
        up, dn = q[:i1 + 1], np.vstack([q[i1:], q[:1]])[::-1]
        if up[:, 1].mean() < dn[:, 1].mean():
            up, dn = dn, up
        self.s_min, self.s_max = float(q[0, 0]), float(q[i1, 0])
        self._ab = (np.maximum.accumulate(up[:, 0]), up[:, 1])
        self._ax = (np.maximum.accumulate(dn[:, 0]), dn[:, 1])
        self.plan = q
        self.g_ab, self.g_ax = _Poly(up), _Poly(dn)                # the ground ring's halves, toe -> heel: (s, x)
        # ---- the coronet ring (where the hair ends). In plan: its front point on the dorsal ridge; its abaxial
        # edge runs back obliquely across the claw to the outline pulled in by the wall's lean (the red deer's
        # hairline from the front, photo i01: a straight oblique line, nearest the toe at the cleft); its axial edge
        # straight back beside the cleft; a rounded back over the heel. In height: a plane sloping down to the heel
        # (the side photos), dipped toward the cleft on the axial side of the ridge (the front photo e01: each
        # claw's hairline is lower at the cleft)
        self.s_cf, self.h_cf = p['coronet_front_s'], p['coronet_front_h']
        self.s_cb, self.h_cb = p['coronet_back_s'], p['heel_h']
        # the dip toward the cleft: the hairline's two faces (the plane, and the face down to the midline) meet at a
        # right angle along the ridge line, so the fall per unit across is 1 / cos(the plane's slope): about 45 deg
        self.dip = float(np.hypot(1.0, (self.h_cb - self.h_cf) / (self.s_cb - self.s_cf)))
        th = np.linspace(0.0, np.pi, 1601)
        sc = self.s_cf + (self.s_cb - self.s_cf) * 0.5 * (1.0 - np.cos(th))
        t_ab = np.clip((sc - self.s_cf) / p['coronet_nose'][0], 0.0, 1.0)
        t_ax = np.clip((sc - self.s_cf) / p['coronet_nose'][1], 0.0, 1.0)
        tt = np.clip((self.s_cb - sc) / p['coronet_tail'], 0.0, 1.0)
        e_t = np.sqrt(np.maximum(1.0 - (1.0 - tt) ** 2, 0.0))
        e_ab = (1.0 - (1.0 - t_ab) ** 1.5) * e_t                   # a straight oblique run, eased onto the flank
        e_ax = np.sqrt(np.maximum(1.0 - (1.0 - t_ax) ** 2, 0.0)) * e_t
        h0 = self.coronet(sc)
        lean = np.radians(np.interp(sc, [0.45, 0.90], p['wall_lean']))
        xa = self.abaxial(sc) - h0 / np.tan(lean)
        xx = self.axial(sc) + p['axial_inset']
        a0, x0 = float(self.abaxial(self.s_cf)), float(self.axial(self.s_cf))
        xr = x0 + p['ridge_at'][1] * (a0 - x0)                     # the dorsal ridge's place at the coronet
        xb = 0.5 * (xa[-1] + xx[-1]) + p['coronet_back_x']
        xc = xr + (xb - xr) * _ss(0.0, 1.0, (sc - self.s_cf) / (self.s_cb - self.s_cf))
        self.x_ridge = xr
        # the coronet's FALL from the ridge toward the abaxial side (preset row coronet_fall, per unit across; 0 =
        # the plane of 11-10, level across). The plane's back is raised by the fall at the ring's back middle, so the
        # heel keeps its measured height
        self.fall = float(p.get('coronet_fall', 0.0))
        if self.fall > 0.0:
            self.h_cb = p['heel_h'] + self.fall * max(float(xb - xr), 0.0)
            self.dip = float(np.hypot(1.0, (self.h_cb - self.h_cf) / (self.s_cb - self.s_cf)))
        x_ab, x_ax = xc + (xa - xc) * e_ab, xc - (xc - xx) * e_ax
        # the ring's front corner rounded (the dorsal ridge is a rounded crest, not a crease): the closed plan
        # curve smoothed along its length by a few per cent of HL, only near the front; split again at its new
        # front point
        ring = np.vstack([np.column_stack([sc, x_ab]), np.column_stack([sc, x_ax])[-2:0:-1]])
        d = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(np.vstack([ring, ring[:1]]), axis=0), axis=1))])
        n_r = 4000
        uq = np.linspace(0.0, d[-1], n_r, endpoint=False)
        rq = np.column_stack([np.interp(uq, d, np.append(ring[:, k], ring[0, k])) for k in range(2)])
        sig = p['ridge_round'] / (d[-1] / n_r)
        kx = np.arange(-int(4 * sig), int(4 * sig) + 1)
        ker = np.exp(-0.5 * (kx / sig) ** 2)
        ker /= ker.sum()
        sm = np.column_stack([np.convolve(np.concatenate([rq[-len(kx):, k], rq[:, k], rq[:len(kx), k]]), ker,
                                          mode='same')[len(kx):-len(kx)] for k in range(2)])
        # full at the front point, none beyond (the zone was fixed at 0.06 / 0.16 HL for the 0.034 sigma of 11-10;
        # it scales with the sigma now, the same numbers at 0.034)
        rr = p['ridge_round']
        wgt = _ss(4.7 * rr, 1.8 * rr, np.minimum(uq, d[-1] - uq))[:, None]
        rq = rq * (1.0 - wgt) + sm * wgt
        i_f, i_b = int(np.argmin(rq[:, 0])), int(np.argmax(rq[:, 0]))
        rq = np.roll(rq, -i_f, axis=0)
        i_b = (i_b - i_f) % n_r
        ab, ax = rq[:i_b + 1], np.vstack([rq[i_b:], rq[:1]])[::-1]
        self.s_cf_ring = float(rq[0, 0])
        self.c_ab = _Poly(np.column_stack([ab, self.coronet(ab[:, 0], ab[:, 1])]))
        self.c_ax = _Poly(np.column_stack([ax, self.coronet(ax[:, 0], ax[:, 1])]))
        self.sp0, self.sp1 = p['spine']
        self.wall_len = float(np.hypot(self.s_cf - self.s_min, self.h_cf))     # the dorsal wall's length

    # ------------------------------------------------------------------------------------------ measured curves
    def abaxial(self, s):
        return np.interp(s, *self._ab)

    def axial(self, s):
        return np.interp(s, *self._ax)

    def coronet(self, s, x=None):
        """the coronet's height at station s (and place x across): a plane from its front point down to the heel,
        falling by `fall` per unit across on the abaxial side of the ridge (level when 0), dipping toward the cleft
        on its axial side. Over the claw it is a ridge roof: the hairline rises over the crest"""
        h = self.h_cf + (self.h_cb - self.h_cf) * (np.asarray(s, float) - self.s_cf) / (self.s_cb - self.s_cf)
        if x is None:
            return h
        x = np.asarray(x, float)
        return h - self.dip * np.maximum(self.x_ridge - x, 0.0) - self.fall * np.maximum(x - self.x_ridge, 0.0)

    def coronet_plane(self):
        """(point, unit normal pointing up-forward) of the coronet's plane, as (x, y, s) in HL"""
        m = (self.h_cb - self.h_cf) / (self.s_cb - self.s_cf)
        n = np.array([0.0, 1.0, -m])
        return np.array([0.0, self.h_cf, self.s_cf]), n / np.linalg.norm(n)

    # ------------------------------------------------------------------------------------------ columns
    def column(self, f, half):
        """the columns at shares f of a half: dict of C (coronet point), G (ground-ring point: on the ground along
        the wall, lifted to the bulb's equator at the heel), Sp (its spine point), wb (0 wall .. 1 bulb), n (the
        plan direction outward from the spine), L (the column's length coronet -> ground ring); points (n, 3) as
        (x, y, s)"""
        p = self.p
        f = np.atleast_1d(np.asarray(f, float))
        C, G, wb, eq, g = self._cg(f, half)
        # the ruled surface's tangent along the ring (for the wall's normal: the shell's bulge runs along it): the
        # two rings' own tangents at f, by a central difference (one-sided at the ends)
        dd = 1e-3
        Cm, Gm = self._cg(np.clip(f - dd, 0.0, 1.0), half)[:2]
        Cp, Gp = self._cg(np.clip(f + dd, 0.0, 1.0), half)[:2]
        s_sp = self.sp0 + (self.sp1 - self.sp0) * f
        Sp = np.column_stack([0.5 * (self.abaxial(s_sp) + self.axial(s_sp)), np.zeros_like(f), s_sp])
        d = G - Sp
        d[:, 1] = 0.0
        dist = np.maximum(np.linalg.norm(d, axis=1), 1e-9)
        # the wall's bearing border: its share of the way in to the spine, and the white line's inner edge
        toe = 1.0 - _ss(0.02, 0.14, g[:, 0])
        # (the cleft side's thinner border comes in over the first 0.12 of the axial half: at the toe tip the two
        # halves are one column and must agree; the factor used to jump there, 1.0 against 0.7)
        rim = (p['rim_w'] + (p['rim_w_toe'] - p['rim_w']) * toe) * \
            ((1.0 - (1.0 - p['rim_axial']) * _ss(0.0, 0.12, f)) if half == 'ax' else 1.0)
        # ... and never one width round the claw (11-12, fix round 2: an even band read as a shoe's welt): a slow
        # change by the column's place round the ring (fs: f on the abaxial half, -f on the axial; two waves whose
        # periods divide the ring, so the width is one curve through the toe and through the heel's middle)
        fs = f if half == 'ab' else -f
        rim = rim * (1.0 + p.get('rim_wander', 0.0) * (0.6 * np.sin(3.0 * np.pi * fs + 1.1)
                                                       + 0.4 * np.sin(5.0 * np.pi * fs + 4.0)))
        t_r = np.clip(rim / dist, 0.0, 0.6)
        n_out = d / dist[:, None]
        # the wall's outward normal at mid height decides the sign of the ruled surface's normal on this column
        # (the surface's own (f, v) orientation flips between the halves)
        Nm = np.cross(0.5 * (Cp - Cm + Gp - Gm), G - C)
        sgn = np.where(np.einsum('ij,ij->i', Nm, n_out + np.array([0.0, 0.25, 0.0])) < 0.0, -1.0, 1.0)
        return dict(C=C, G=G, Sp=Sp, wb=wb, n=n_out, dist=dist, L=np.linalg.norm(G - C, axis=1), f=f,
                    eq=eq, t_r=t_r, t_wl=t_r + p['white_line'] / dist, dC=Cp - Cm, dG=Gp - Gm, nsign=sgn,
                    half=np.full(len(f), 0 if half == 'ab' else 1), fs=(f if half == 'ab' else -f))

    def _cg(self, f, half):
        """a column's two ends at shares f of a half: C on the coronet ring, G on the ground ring (lifted to the
        bulb's equator at the heel); with wb (0 wall .. 1 bulb), eq (the equator's height) and the ground ring's
        (s, x)"""
        p = self.p
        g = (self.g_ab if half == 'ab' else self.g_ax)(f)
        c = (self.c_ab if half == 'ab' else self.c_ax)(f)
        wb = _ss(p['bulb_from'] - 0.08, p['bulb_from'] + 0.10, g[:, 0])
        C = np.column_stack([c[:, 1], c[:, 2], c[:, 0]])
        # the bulb's equator: low along the flank (the heel meets the ground on a small roll), higher round the back
        eq = p['bulb_eq_h'][0] + (p['bulb_eq_h'][1] - p['bulb_eq_h'][0]) * _ss(0.78, 1.0, f)
        G = np.column_stack([g[:, 1], eq * wb, g[:, 0]])
        return C, G, wb, eq, g

    def ring(self, f_ab, f_ax):
        """the columns round a claw as ONE closed ring (the order every grid and low uses): the abaxial half at
        shares f_ab from the dorsal ridge (0) to the heel's middle (1), both ends included, then the axial half at
        f_ax, strictly inside (0, 1), from the heel forward (descending). A dict of column() arrays, K long"""
        ca, cx = self.column(f_ab, 'ab'), self.column(f_ax, 'ax')
        return {k: np.concatenate([ca[k], cx[k]]) for k in ca}

    def wall(self, col, v):
        """points on the wall's columns at v (0 the coronet, 1 the ground ring; < 0 the tuck under the skin): the
        ruled line bowed OUT along the ruled surface's own normal into a shell (bulge(); 11-11, fix round 1: the
        straight rulings alone made a cone, read as flat-faced wedges), the axial wall hollowed a little, the bulb
        bulged. Under the skin (v < 0) the bow carries on along its own tangent: the tuck curls in under the
        coronet's band"""
        v = np.broadcast_to(np.asarray(v, float), col['f'].shape)
        P = col['C'] + v[..., None] * (col['G'] - col['C'])
        bump = np.sin(np.pi * np.clip(v, 0.0, 1.0))
        P = P + (self.wall_amp(col) * bump)[..., None] * col['n']
        A = self.bulge(col)
        if not np.any(A > 0.0):
            return P
        vc = np.clip(v, 0.0, 1.0)
        tf = col['dC'] * (1.0 - vc)[..., None] + col['dG'] * vc[..., None]
        N = np.cross(tf, col['G'] - col['C']) * col['nsign'][..., None]
        N = N / np.maximum(np.linalg.norm(N, axis=-1, keepdims=True), 1e-12)
        return P + (A * self.shell(v))[..., None] * N

    def shell(self, v):
        """the bow's profile down a column: 0 at the coronet (v 0) and at the ground ring (v 1), 1 at the preset's
        bulge_peak; under the skin (v < 0) its slope at the coronet carried on"""
        pk = float(self.p.get('bulge_peak', 0.5))
        k = (0.5 - pk) / (pk * (1.0 - pk))                    # w(v) = v + k v (1 - v): w(peak) = 0.5, w'(0) = 1 + k
        v = np.asarray(v, float)
        vc = np.clip(v, 0.0, 1.0)
        out = np.sin(np.pi * (vc + k * vc * (1.0 - vc)))
        return np.where(v < 0.0, np.pi * (1.0 + k) * v, out)

    def bulge(self, col):
        """how far each column's wall bows out of its ruled line at the bow's peak (HL), along the ruled surface's
        normal: the ridge's own (small: the dorsal profile is nearly straight), the toe's fan and the flank on the
        abaxial half, the toe's inner face on the axial half (rounding the toe; behind it the cleft's wall keeps its
        hollow, wall_amp's); none on the bulb, which has its own bulge. Each column's bow is BOUNDED so the wall
        stands no more than `bulge_overhang` outside its own bearing edge (from below, i02 / i03, the dark wall shows
        only a hair outside the rim): toward the heel, where the wall stands upright, the bound decides"""
        if 'bulge_ab' not in self.p:
            return np.zeros_like(col['f'])
        tab = self._bulge_table()
        f = np.asarray(col['f'], float)
        return np.where(col['half'] == 0, np.interp(f, *tab[0]), np.interp(f, *tab[1]))

    def _bulge_design(self, f, half, wb):
        p = self.p
        if half == 0:
            a = p['bulge_dorsal'] + (p['bulge_toe'] - p['bulge_dorsal']) * _ss(0.0, 0.14, f)
            a = a + (p['bulge_ab'] - p['bulge_toe']) * _ss(0.15, 0.40, f)
        else:
            a = (p['bulge_dorsal'] + (p['bulge_ax_toe'] - p['bulge_dorsal']) * _ss(0.0, 0.05, f)) * _ss(0.30, 0.12, f)
        return a * (1.0 - wb)

    def _bulge_table(self):
        """per half, the bow at shares f (201 of them): the design row, cut to the overhang bound (bisection on each
        column's own points; the bow is monotone in its amount)"""
        if getattr(self, '_btab', None) is not None:
            return self._btab
        p = self.p
        ov = float(p.get('bulge_overhang', 1.0))
        fq = np.linspace(0.0, 1.0, 201)
        vq = np.linspace(0.0, 1.0, 41)
        sh = self.shell(vq)
        tab = []
        for hi, half in enumerate(('ab', 'ax')):
            col = self.column(fq, half)
            A = self._bulge_design(fq, hi, col['wb'])
            n = col['n']
            vc = vq[None, :, None]
            tf = col['dC'][:, None] * (1.0 - vc) + col['dG'][:, None] * vc
            N = np.cross(tf, (col['G'] - col['C'])[:, None]) * col['nsign'][:, None, None]
            N = N / np.maximum(np.linalg.norm(N, axis=-1, keepdims=True), 1e-12)
            base = col['C'][:, None] + vq[None, :, None] * (col['G'] - col['C'])[:, None] - col['G'][:, None]
            b0 = np.einsum('kvi,ki->kv', base, n)                  # the ruled line's offset beyond the ground point
            dn = np.einsum('kvi,ki->kv', N, n) * sh[None]           # the bow's outward share per unit amount
            lo, hi_ = np.zeros_like(A), A.copy()
            for _ in range(24):
                mid = 0.5 * (lo + hi_)
                bad = (b0 + mid[:, None] * dn).max(1) > ov
                hi_ = np.where(bad, mid, hi_)
                lo = np.where(bad, lo, mid)
            ok = (b0 + A[:, None] * dn).max(1) <= ov
            tab.append((fq, np.where(ok, A, lo)))
        self._btab = tab
        return tab

    def wall_amp(self, col):
        """how far each column's wall stands off its straight line at mid height (HL; + outward): the bulb's
        bulge, the axial wall's hollow. Zero on the dorsal and abaxial wall: there the wall is the ruled line"""
        p = self.p
        return p['bulb_bulge'] * col['wb'] - (col['half'] == 1) * p['axial_hollow'] * (1.0 - col['wb']) * \
            _ss(0.02, 0.25, col['f']) * _ss(1.0, 0.75, col['f'])

    def under(self, col, t):
        """points under the ground ring at t (0 the ring, 1 the spine): the wall's bearing border flat on the ground,
        then the sole's trough; at the heel the bulb's rounded underside. Returns (points, the rim's share t_r)"""
        p = self.p
        t = np.broadcast_to(np.asarray(t, float), col['f'].shape)
        G, Sp, wb, dist, t_r = col['G'], col['Sp'], col['wb'], col['dist'], col['t_r']
        P = G + t[..., None] * (Sp - G)
        tau = np.clip((t - t_r) / np.maximum(1.0 - t_r, 1e-6), 0.0, 1.0)
        # the trough's depth by the point's own station (so the columns agree where they meet at the spine's ends)
        depth = p['sole_depth'] * _ss(0.04, 0.26, P[..., 2])
        y_sole = depth * (1.0 - (1.0 - tau) ** 2.5)
        A = p['bulb_under'] * dist                                 # the bulb's rounding: a quarter ellipse
        i = np.minimum(t * dist, A)
        y_bulb = col['eq'] * (1.0 - np.sqrt(np.maximum(1.0 - ((A - i) / np.maximum(A, 1e-9)) ** 2, 0.0)))
        # sole or bulb by the point's own station inside the claw (the column's own share on the ring itself), so
        # the two halves agree along the spine
        wbp = _ss(p['bulb_from'] - 0.08, p['bulb_from'] + 0.10, P[..., 2])
        w = wb + (wbp - wb) * _ss(0.0, 0.5, t)
        P[..., 1] = (1.0 - w) * y_sole + w * y_bulb
        return P, t_r

    def periople_len(self, col):
        """the periople's reach down each column from the coronet (HL): the preset's share of the dorsal wall's
        length, longer over the heel, where the young horn runs into the bulb"""
        return self.p['periople'] * self.wall_len * (1.0 + 0.6 * col['wb'])

    # ------------------------------------------------------------------------------------------ the grid
    def ring_f(self, n):
        """the 2 n columns round a claw: (half, f) pairs from the dorsal ridge back along the abaxial side to the
        heel's middle and forward again along the axial side; closer together round both ends"""
        u = np.linspace(0.0, 1.0, n + 1)
        f = 0.55 * u + 0.45 * 0.5 * (1.0 - np.cos(np.pi * u))
        return f

    def grid(self, n=96, n_tuck=3, n_wall=48, n_under=36, tuck=None):
        """the claw as a closed grid: P (R, K, 3) points (x, y, s) in HL, K = 2 n columns, rows from the tuck's top
        (under the skin) down the wall to the ground ring and in under the claw to the spine; with per-point data:
        zone, vv (the wall's v, 1 + t under the claw), age (the distance from the coronet along the tubule, HL),
        wb, fs (the column's f, negative on the axial half), col (column index), row"""
        p = self.p
        tuck = p['coronet_tuck'] if tuck is None else tuck
        f = self.ring_f(n)
        col = self.ring(f, f[1:-1][::-1])
        tr = np.linspace(1.0, 0.0, n_tuck + 1)[:-1]
        vw = np.linspace(0.0, 1.0, n_wall + 1)
        tu = np.linspace(0.0, 1.0, n_under + 1)[1:] ** 1.35
        rows, data = [], dict(zone=[], vv=[], age=[])
        fs, wbk, Lk = col['fs'], col['wb'], col['L']
        per = self.periople_len(col)
        for t in tr:                                               # the tuck: the wall continued up under the skin
            v = -t * tuck / Lk
            rows.append(self.wall(col, v))
            data['zone'].append(np.full(2 * n, Z_TUCK))
            data['vv'].append(v)
            data['age'].append(v * Lk)
        for v in vw:
            rows.append(self.wall(col, v))
            age = v * Lk
            data['zone'].append(np.where(wbk > 0.5, Z_BULB, np.where(age < per, Z_PERIOPLE, Z_WALL)))
            data['vv'].append(np.full(2 * n, v))
            data['age'].append(age)
        for t in tu:
            Pu, t_r = self.under(col, t)
            rows.append(Pu)
            data['zone'].append(np.where(wbk > 0.5, Z_BULB_UNDER, np.where(t <= t_r, Z_RIM,
                                                                           np.where(t <= col['t_wl'], Z_WHITE, Z_SOLE))))
            data['vv'].append(np.full(2 * n, 1.0 + t))
            data['age'].append(Lk.copy())
        P = np.stack(rows)
        R, K = P.shape[:2]
        out = dict(P=P, fs=np.tile(fs, (R, 1)), wb=np.tile(wbk, (R, 1)), L=np.tile(Lk, (R, 1)),
                   col=np.tile(np.arange(K), (R, 1)), row=np.repeat(np.arange(R)[:, None], K, 1),
                   n_tuck=n_tuck, n_wall=n_wall, n_under=n_under, n=n)
        for k_, v_ in data.items():
            out[k_] = np.stack(v_)
        return out

    # ------------------------------------------------------------------------------------------ what the rig needs
    def toe_point(self):
        return np.array([float(self.g_ab(0.0)[0, 1]), 0.0, self.s_min])

    def heel_point(self):
        g = self.g_ab(1.0)[0]
        return np.array([g[1], 0.0, self.sp1])


# -------------------------------------------------------------------------------------------------- meshes
def to_world(P, HL, side=1.0):
    """(x, y, s) shares of HL -> metres in the foot's frame; side +1 the left claw, -1 its mirror"""
    P = np.asarray(P, float)
    return np.stack([side * P[..., 0] * HL, P[..., 1] * HL, -P[..., 2] * HL], -1)


def pair(F, HL=1.0):
    """THE FOOT'S TWO CLAWS as [(side, scale, centre)]: the primary (+X, the template: digit IV of a left foot) as
    it is, its partner (-X, digit III) MIRRORED AND SCALED by the preset's medial_scale about a point on the midline
    on the ground under the claws' middle (pair_centre_s behind the toe tips): a similarity, so the partner still
    stacks on the primary's texels (11-11, fix round 1: an exact mirror was one more sign of a made thing; the two
    claws differ by about 5 % in width on i02). centre in metres"""
    p = F.p
    c = np.array([0.0, 0.0, -float(p.get('pair_centre_s', 0.5))]) * HL
    return [(1.0, 1.0, c), (-1.0, float(p.get('medial_scale', 1.0)), c)]


def pair_place(V, F, HL, side):
    """the template claw's points (metres, the foot's frame: the +X claw) placed as the claw on `side`"""
    V = np.asarray(V, float)
    if side > 0:
        return V
    _, s, c = pair(F, HL)[1]
    return c + s * (V * np.array([-1.0, 1.0, 1.0]) - c)


def grid_tris(R, K, closed=True):
    """the triangles of an (R, K) grid, columns closed round; quads split on the 0-2 diagonal"""
    i, j = np.meshgrid(np.arange(R - 1), np.arange(K if closed else K - 1), indexing='ij')
    a = (i * K + j).ravel()
    b = (i * K + (j + 1) % K).ravel()
    c, d = a + K, b + K
    return np.concatenate([np.stack([a, c, d], -1), np.stack([a, d, b], -1)])


def _orient(V, T):
    """triangles turned so that the closed mesh's volume is positive (normals outward)"""
    vol = np.einsum('ij,ij->i', V[T[:, 0]], np.cross(V[T[:, 1]], V[T[:, 2]])).sum()
    return T if vol > 0 else T[:, ::-1]


def claw_mesh(F, HL, side=1.0, **kw):
    """one claw as a dense closed mesh: V (metres), T, A (per-vertex data of ClawForm.grid, flattened; + 'shape':
    (R, K)). The tuck's top is closed by a fan (it lies inside the leg)"""
    g = F.grid(**kw)
    P = g['P']
    R, K = P.shape[:2]
    V = pair_place(to_world(P.reshape(-1, 3), HL, 1.0), F, HL, side)
    T = grid_tris(R, K)
    top = len(V)
    V = np.vstack([V, V[:K].mean(0)])
    j = np.arange(K)
    T = np.concatenate([T, np.stack([np.full(K, top), (j + 1) % K, j], -1)])
    T = _orient(V, T)
    A = {k: np.concatenate([np.asarray(v).reshape(-1), [np.asarray(v).reshape(-1)[0]]])
         for k, v in g.items() if isinstance(v, np.ndarray) and v.shape[:2] == (R, K) and v.ndim == 2}
    A['zone'][-1] = Z_TUCK
    A['shape'] = (R, K)
    return V, T.astype(np.int32), A


def dewclaw_sections(p, t):
    """THE PAD'S SECTION AT STATIONS t (0 the hairline .. 1 the tip; < 0 the tuck under the skin), from the preset's
    measured rows (hoof_presets `dew_sections`): a dict of arrays, shares of HL: half_p / half_m (the half widths
    toward +a and -a), out / inn (the thickness outside and inside the widest line), e_out (the outer face's
    exponent), skew (the crest's place off the middle, a share of the half width), ca / co (the axis' own lean
    across and its hook toward the leg). The two profiles are splined in sqrt(1 - t): a round nose at the tip"""
    from scipy.interpolate import PchipInterpolator
    S = p['dew_sections']
    t = np.asarray(t, float)
    tk = np.asarray(S['t'], float)
    tc = np.clip(t, 0.0, 1.0)
    u, uq = np.sqrt(1.0 - tk)[::-1], np.sqrt(1.0 - tc)                 # ascending: 0 the tip .. 1 the hairline
    nose = lambda key: PchipInterpolator(u, np.asarray(S[key], float)[::-1])(uq)       # noqa: E731
    along = lambda key: PchipInterpolator(tk, np.asarray(S[key], float))(tc)           # noqa: E731
    under = np.where(t < 0.0, 1.0 + 0.10 * (t / p['dew_tuck']), 1.0)   # the tuck narrows a little under the skin
    W, T = p['dew_w'] * nose('w') * under, p['dew_t'] * nose('thick') * under
    k_i, f = float(S['inner']), float(S['fuller'])
    return dict(half_p=0.5 * W * (1.0 + f), half_m=0.5 * W * (1.0 - f), out=(1.0 - k_i) * T, inn=k_i * T,
                e_out=along('e_out'), skew=along('skew'), ca=S['lean'] * p['dew_len'] * tc ** 2,
                co=-p['dew_hook'] * p['dew_len'] * tc ** 2.2)


def dewclaw_tip(p):
    """the template's tip in its own frame (a, o, w), shares of HL"""
    return np.array([p['dew_sections']['lean'] * p['dew_len'], -p['dew_hook'] * p['dew_len'], p['dew_len']])


def dewclaw_form(p, n_round=64, n_long=48, w=None, theta=None):
    """THE DEWCLAW TEMPLATE (digits II and V; one for all eight): a small hoof. Its own frame, shares of HL: +w along
    its length from the base ring (0: the hairline) to the tip (1 x dew_len), +o outward (away from the leg), +a
    across. Returns P (rows from the tuck's top to the tip, n_round, 3) as (a, o, w) and vv (0..1 along).
    w: the rows' own places (shares of its length, -dew_tuck at the tuck's top), for a low's rings.

    ITS SECTIONS CHANGE ALONG ITS LENGTH (11-12, fix round 2; check 2: "one fixed oval section along a straight line
    with an even taper and a domed end ... two capsules"). Each row is a D: an outer arc (the wall: a superellipse
    whose exponent falls under 2 along the middle of the pad, a soft crest, set off the middle by `skew`) on a FLAT
    inner face with a rim (the pad's own sole, against the leg). Face on the rows widen from a rounded apex to a
    shield, widest just under the hairline; on edge they thicken to 0.6 of the length and end blunt; the two sides
    are not equal and the axis leans a little (hoof_presets `dew_sections`, each row read on a photo)"""
    L = p['dew_len']
    tuck = p['dew_tuck']
    if w is None:
        w = np.concatenate([np.linspace(-tuck, 0.0, 3)[:-1], 1.0 - (1.0 - np.linspace(0.0, 1.0, n_long + 1)) ** 1.6])
    w = np.asarray(w, float)
    S = dewclaw_sections(p, w)
    e_in = float(p['dew_sections']['e_in'])
    th = np.linspace(0.0, 2.0 * np.pi, n_round, endpoint=False) if theta is None else np.asarray(theta, float)
    n_round = len(th)
    ct, st = np.cos(th)[None], np.sin(th)[None]
    outer = st >= 0.0
    ex = np.where(outer, S['e_out'][:, None], e_in)                    # each half's own exponent
    half = np.where(ct >= 0.0, S['half_p'][:, None], S['half_m'][:, None])
    a = half * np.sign(ct) * np.abs(ct) ** (2.0 / ex)
    o = np.where(outer, S['out'][:, None], -S['inn'][:, None]) * np.abs(st) ** (2.0 / ex)
    # the crest set off the middle: the outer half sheared across by its own height (the widest line stays)
    mean_half = 0.5 * (S['half_p'] + S['half_m'])[:, None]
    a = a + np.where(outer, S['skew'][:, None] * mean_half * o / np.maximum(S['out'][:, None], 1e-12), 0.0)
    P = np.zeros((len(w), n_round, 3))
    P[..., 0] = a + S['ca'][:, None]
    P[..., 1] = o + S['co'][:, None]
    P[..., 2] = (w * L)[:, None]
    vv = np.repeat(w[:, None], n_round, 1)
    return P, vv


def dewclaw_mesh(p, HL, **kw):
    """the dewclaw template as a closed mesh in its own frame (metres): V, T, A (vv, zone). Both ends closed by
    fans (the tip's is its rounded end; the tuck's lies inside the leg)"""
    P, vv = dewclaw_form(p, **kw)
    R, K = P.shape[:2]
    V = P.reshape(-1, 3) * HL
    T = grid_tris(R, K)
    j = np.arange(K)
    top, tip = len(V), len(V) + 1
    V = np.vstack([V, V[:K].mean(0), V[-K:].mean(0) + np.array([0.0, 0.0, 0.004 * HL])])
    T = np.concatenate([T, np.stack([np.full(K, top), (j + 1) % K, j], -1),
                        np.stack([np.full(K, tip), (R - 1) * K + j, (R - 1) * K + (j + 1) % K], -1)])
    T = _orient(V, T)
    v = np.concatenate([vv.reshape(-1), [vv[0, 0], 1.0]])
    zone = np.where(v < 0.0, Z_TUCK, np.where(v < p['dew_periople'], Z_PERIOPLE, Z_WALL))
    return V, T.astype(np.int32), dict(vv=v, zone=zone, shape=(R, K))


def dewclaw_frames(p, HL):
    """where the two dewclaws of a foot hang (under the fetlock's back corners, one each side): a list of (origin,
    R, side); R's columns are the template's axes (a across, o outward, w along its length) in the foot's frame.
    THE BASE IS DERIVED (11-12, fix round 2): the TIP is what the photos give (its height, how far behind the heel,
    the two tips apart), with the pad's own axis (dew_hang to the ground, its tip forward of its top when
    dew_tip_fwd is +1, splayed a little outward) and the way its outer face looks (dew_face); the base ring is the
    tip carried back up the template. (It was typed, dew_base_h / dew_base_s, with the axis 62 deg down and BACK:
    the pad pointed away from the leg and its base stood off the skin: check 2's "capsules on stalks")
    THE RIGHT PAD IS THE LEFT ONE'S MIRROR (11-12): its R is the left R mirrored in x, so det R = -1 and whoever
    places a template with it mirrors it AS DATA (hoof_low.moved: the winding turned, the tangent's w negated; the
    same texels). The template is no longer symmetric (its crest and its lean are to one side), and a turned copy
    would carry the crest on the other anatomical side"""
    hang = np.radians(p['dew_hang'])
    fwd = float(p.get('dew_tip_fwd', 1.0))
    wdir = np.array([p['dew_splay'], -np.sin(hang), fwd * np.cos(hang)])              # down, a little outward
    wdir /= np.linalg.norm(wdir)
    odir = np.asarray(p['dew_face'], float)                                           # outward and back
    odir = odir - wdir * (odir @ wdir)
    odir /= np.linalg.norm(odir)
    adir = np.cross(odir, wdir)
    R = np.column_stack([adir, odir, wdir])
    tip = np.array([0.5 * p['dew_apart'], p['dew_tip_h'], -(1.0 + p['dew_tip_behind_heel'])])
    base = (tip - R @ dewclaw_tip(p)) * HL
    M = np.diag([-1.0, 1.0, 1.0])
    return [(base, R, 1.0), (M @ base, M @ R, -1.0)]


# -------------------------------------------------------------------------------------------------- the stump
def stump_program(F, HL, top_cut=None, log=None):
    """THE NEUTRAL STUMP as an sdf.Program: what stands in for the deer's lower leg until D6.4's cage exists. Each
    digit's haired skin is a PSWEEP up the pastern's axis whose first key IS the claw's coronet ring pushed out by
    the coronet's step, so the skin lies proud of the horn by that step all round by construction (the modelled
    coronet step); the keys open into the measured pastern ovals; the two digits fuse in a ROUND union (the groove
    up the pastern's front is what is left between them); the fetlock and the cannon's end are one sweep of measured
    widths and depths; two soft mounts carry the dewclaws. The whole is kept above the coronets' plane, its lower
    edge rolled (the lip of hair lying on the wall). Returns (prog, info)"""
    from .. import sdf
    p = F.p
    top_cut = p['stump_top'] if top_cut is None else top_cut
    prog = sdf.Program()
    step = p['coronet_step']
    th = np.radians(p['pastern_axis'])
    t_ax = np.array([0.0, np.sin(th), -np.cos(th)])                    # up and back along the digit
    n_ax = np.array([0.0, np.cos(th), np.sin(th)])                     # the pastern's front
    M = 96
    fr = np.linspace(0.0, 1.0, M // 2 + 1)
    ring = np.vstack([F.c_ab(fr), F.c_ax(fr[1:-1][::-1])])            # (s, x, h) round the coronet
    Q = np.column_stack([ring[:, 1], ring[:, 2], -ring[:, 0]])         # (x, y, z) in HL
    O = Q.mean(0)
    k0 = np.column_stack([(Q - O) @ n_ax, Q[:, 0] - O[0]])             # (along the front normal, across)
    # the digit above the coronet: the ring's outline rounds into the pastern's measured oval (an egg: its front
    # narrower than its back), waisted above the coronet's band, and ends buried inside the fetlock
    from scipy.interpolate import PchipInterpolator
    ang = np.arctan2(k0[:, 1], k0[:, 0])
    half_d, half_w = 0.5 * p['pastern_d'] - step, 0.5 * p['digit_w'] - step
    egg = 1.0 - 0.10 * np.cos(ang)                                     # across: fuller behind than in front
    oval = np.column_stack([half_d * np.cos(ang), half_w * egg * np.sin(ang)])
    c1 = np.array([p['digit_fwd'], 0.0])
    L_p = p['pastern_len']
    d_tau = np.array([0.09, 0.30, 0.55, 0.80, 1.05]) * (L_p / 0.62)
    tau_k = np.concatenate([[-0.22], np.linspace(d_tau[0], d_tau[-1], 15)])
    tau = np.concatenate([np.linspace(-0.22, d_tau[0], 7)[:-1], np.linspace(d_tau[0], d_tau[-1], 29)])
    key = np.interp(tau, tau_k, np.arange(len(tau_k), dtype=float))
    info = dict(HL=HL, step=step * HL, members=[], axis=t_ax, front=n_ax)
    prog.begin_group(op=sdf.UNION, k=0.0)
    kr = p['web_blend'] * HL
    for (side, sc, cen), nm in zip(pair(F, 1.0), ('L', 'R')):
        # each digit's skin starts round ITS claw's coronet ring: the partner's ring is the primary's mirrored and
        # scaled about the pair's centre (pair()), so the first key and the start point scale with it
        d_keys = np.stack([sc * k0, 0.22 * sc * k0 + 0.78 * (oval * [0.97, 0.94] + c1), oval * [1.00, 0.98] + c1,
                           oval * [1.00, 1.00] + c1, oval * [0.70, 0.72] + c1])
        S = PchipInterpolator(d_tau, d_keys, axis=0)(np.clip(tau_k, d_tau[0], d_tau[-1])) * HL
        Os = cen + sc * (np.array([side * O[0], O[1], O[2]]) - cen)
        conv = p['digit_converge'] * _ss(0.05, 0.85, tau / d_tau[-1])
        Pc = (Os[None] + t_ax[None] * tau[:, None] - np.array([side, 0.0, 0.0])[None] * conv[:, None]) * HL
        Sk = S.copy()
        Sk[..., 1] *= side
        prog.psweep(Pc, Sk, rho=step * HL, key=key, normal=np.tile(n_ax, (len(tau), 1)), op=sdf.ROUND, k=kr,
                    name=f'digit_{nm}')
        info['members'].append(f'digit_{nm}')
    # the fetlock and the cannon's end: one sweep, measured widths (across) and depths (front to back), smooth
    fet = np.array([0.0, p['fetlock_h'], -p['fetlock_behind_toe']])
    thc = np.radians(p['cannon_angle'])
    dc = np.array([0.0, np.sin(thc), -np.cos(thc)])
    # its centreline is the limb's own: down the cannon, round the fetlock, on down the pastern between the two
    # digits (the common mass behind them), thinning to nothing by the middle of the pastern
    Lc = top_cut - p['fetlock_h'] + 0.45
    # (17 + 31 nodes, 3.6 mm apart, left a faint ring at every node: a sweep's profile is linear between its nodes,
    # and the rings showed as bands across the fetlock in every lit picture, look/h60_k_back.png. Three times denser)
    lv = np.concatenate([np.linspace(-0.50, -0.02, 49), np.linspace(0.02, Lc, 91)])
    bend = 0.16
    cu = np.where(lv[:, None] < 0.0, fet[None] + t_ax[None] * lv[:, None], fet[None] + dc[None] * lv[:, None])
    # the corner at the fetlock rounded: within `bend` of it the line is a parabola between the two axes
    m = np.abs(lv) < bend
    u = (lv[m] + bend) / (2.0 * bend)
    p0, p2 = fet - t_ax * bend, fet + dc * bend
    cu[m] = ((1.0 - u) ** 2)[:, None] * p0[None] + (2.0 * u * (1.0 - u))[:, None] * fet[None] + (u ** 2)[:, None] * p2[None]
    kn = [-0.50, -0.30, -0.12, 0.0, 0.15, 0.35, 0.60, 0.90]
    cw, cd = p['cannon_w'] / p['fetlock_w'], p['cannon_d'] / p['fetlock_d']
    w_half = PchipInterpolator(kn, np.array([0.30, 0.62, 0.92, 1.0, 0.95, cw * 1.10, cw, cw])
                               * 0.5 * p['fetlock_w'])(np.clip(lv, kn[0], kn[-1]))
    d_half = PchipInterpolator(kn, np.array([0.30, 0.60, 0.90, 1.0, 0.92, cd * 1.12, cd, cd])
                               * 0.5 * p['fetlock_d'])(np.clip(lv, kn[0], kn[-1]))
    prog.sweep(cu * HL, np.tile([1.0, 0.0, 0.0], (len(lv), 1)), w_half * HL, aspect=d_half / w_half, a3=0.035,
               phi3=np.pi / 2.0, op=sdf.ROUND, k=kr, name='fetlock_cannon')
    info['members'].append('fetlock_cannon')
    # the dewclaws' mounts: each vestigial digit's haired skin, a short lobe out of the back of the fetlock that ENDS
    # ROUND THE DEWCLAW'S BASE RING: its first section IS that ring pushed out by the coronet's step (rho), as each
    # claw's skin ends round its coronet, so the whole pad stands outside the skin and only its tuck is inside.
    # (11-11: the first mount was a ROUNDCONE whose end sphere reached 0.45 of the pad's length. The visible horn was
    # 0.17 HL long where the photos read 0.29-0.32, and wider than long where i04 reads 0.75: from behind the pads
    # were short teeth on knobs. work/bestiary/deer/hooves/scripts/h13_dewclaw_visible.py measures it.)
    # (11-12, fix round 2: THE MOUNT WAS A STALK. A dewclaw is a DIGIT (II and V) that hangs from the fetlock's back
    # corner, beside the pastern: on e01 from the front the leg's outline widens in one line from the cannon to the
    # lobe's top, on e02 the leg's back outline runs straight down into the nub, on i04 the pad lies on a haired
    # swelling. The stand-in's fetlock is an oval: its back corners are empty, so every mount to a pad that hangs
    # where the photos put it was a stalk or an arm (the 11-11 lobe; four tries on 11-12, work/bestiary/deer/hooves/
    # fix2/tmp/g20_{a..e}_row.png). Now the mount is the digit's haired root in two members: the CUFF (the skin that
    # ends round the base ring: straight up the pad's own axis, no thicker than the pad, its small end buried) and
    # the ROOT, a round cone from the cuff's middle up the CANNON'S BACK CORNER (`root`, from the fetlock's centre):
    # a ridge that fills the corner, so the leg flares to the pad and the cuff's top never shows as a knob. (One
    # sweep that turned from the pad's axis into the fetlock was refused: a PSWEEP's band cannot turn 60 degrees
    # inside a reach of 18 mm.) Rows: hoof_presets `dew_mount` (the stand-in's))
    Pb, _ = dewclaw_form(p, n_round=64, w=np.array([0.0]))
    ring_d = Pb[0][:, :2]                                              # the base ring: (a across, o outward), HL
    o_mid = 0.5 * (ring_d[:, 1].max() + ring_d[:, 1].min())
    core = np.column_stack([ring_d[:, 1] - o_mid, ring_d[:, 0]])       # a section: x outward (the frame normal), y across
    th_d = np.linspace(0.0, 2.0 * np.pi, len(core), endpoint=False)    # dewclaw_form's own angles: the same point order
    oval = lambda AB: np.column_stack([AB[1] * np.sin(th_d), AB[0] * np.cos(th_d)])      # noqa: E731  (across, outward)
    mt = p['dew_mount']
    d_keys5 = np.stack([core, 0.5 * 1.06 * core + 0.5 * oval(mt['ovals'][0]), oval(mt['ovals'][1]),
                        oval(mt['ovals'][2]), oval(mt['ovals'][3])]) * HL
    # the five design sections as 13 keys through a monotone spline (sections blend linearly between keys: five
    # keys alone left a ring at each one, as the fetlock's sweep did at its nodes)
    m_u = np.linspace(0.0, 1.0, 13)
    m_keys = PchipInterpolator([0.0, 0.22, 0.50, 0.78, 1.0], d_keys5, axis=0)(m_u)
    uu = np.linspace(0.0, 1.0, 49)
    for base, Rm, side in dewclaw_frames(p, HL):
        adir, odir, wdir = Rm[:, 0], Rm[:, 1], Rm[:, 2]
        c0 = base + odir * (o_mid * HL)
        root = (fet + np.array([side * mt['root'][0], mt['root'][1], mt['root'][2]])) * HL
        Cm = c0[None] - wdir[None] * (mt['rise'] * HL * uu[:, None])   # the hairline's plane IS the base ring's
        sk = m_keys.copy()
        if np.dot(np.cross(-wdir, odir), adir) < 0.0:                  # y runs along t x n: keep it the pad's `a`
            sk[..., 1] *= -1.0
        nm = 'dew_mount_' + ('L' if side > 0 else 'R')
        prog.psweep(Cm, sk, rho=step * HL, key=np.interp(uu, m_u, np.arange(len(m_u), dtype=float)),
                    normal=np.tile(odir, (len(uu), 1)), op=sdf.ROUND, k=kr, name=nm)
        info['members'].append(nm)
        # (a ROUND group is members of one radius throughout: the web's)
        prog.roundcone(c0 - wdir * (mt['cone_at'] * mt['rise'] * HL), root, mt['cone_r'][0] * HL, mt['cone_r'][1] * HL,
                       op=sdf.ROUND, k=kr, name='dew_root_' + ('L' if side > 0 else 'R'))
        info['members'].append('dew_root_' + ('L' if side > 0 else 'R'))
    prog.end_group()
    # kept above the coronets' surface, the lower edge rolled (the lip of hair on the wall): above the coronets'
    # plane, or inside the wedge that carries the hair lower between the claws (ClawForm.coronet's dip: the two
    # faces through the ridge lines x = +-x_ridge, sloping down to the midline)
    a_pl, n_pl = F.coronet_plane()
    a_w = np.array([0.0, a_pl[1], -a_pl[2]]) * HL
    n_w = np.array([0.0, n_pl[1], -n_pl[2]])
    X = np.array([1.0, 0.0, 0.0])
    e_w = np.cross(X, n_w)
    e_w = e_w if e_w[2] < 0 else -e_w                                  # along the coronet, backward
    big = 4.0 * HL
    # EACH CLAW'S OWN HEM (11-11, fix round 1): the partner claw is scaled (pair()), so its coronet's plane lies a
    # little lower than the primary's; each side of the midline is kept above its own claw's plane (a box corner:
    # the plane and x = 0). Between the claws the hair dips into the cleft (a wedge whose faces run down at 45 deg
    # from each claw's ridge line); on the abaxial side of each ridge it falls by the coronet's `fall` (a box corner
    # whose second face is square to the fall's)
    (_, _, cen), (_, s_m, _) = pair(F, HL)
    a_m = cen + s_m * (a_w * np.array([-1.0, 1.0, 1.0]) - cen)        # the partner's plane point (x stays 0)
    d_n = float((a_m - a_w) @ n_w) / HL                               # its plane's offset along n_w, HL
    x_r = F.x_ridge
    x_a = 0.5 * (d_n + x_r * (1.0 - s_m))                              # where the two 45 deg faces meet
    apex = a_w + (X * x_a + n_w * (x_a - x_r)) * HL                    # the wedge's lowest line
    u1 = (n_w + X) / np.sqrt(2.0)                                      # the wedge's two faces: a box's corner
    u2 = (n_w - X) / np.sqrt(2.0)
    Rw = np.column_stack([u1, u2, np.cross(u1, u2)])
    fall_n = F.fall / F.dip                                            # the fall per unit across, along n_w
    prog.begin_group(op=sdf.INTERSECT, k=p['coronet_lip'] * HL)
    for sd, a_s, nm in ((1.0, a_w, 'L'), (-1.0, a_m, 'R')):
        Rb = np.column_stack([sd * X, n_w, np.cross(sd * X, n_w)])
        prog.roundbox(a_s + (sd * X + n_w) * big, [big, big, big], r=0.0, axes=Rb, op=sdf.UNION, k=0.0,
                      name='above_coronet_' + nm)
    prog.roundbox(apex + (u1 + u2) * big, [big, big, big], r=0.0, axes=Rw, op=sdf.UNION, k=0.0,
                  name='between_claws')
    if fall_n > 0.0:
        for sd, a_s, xr_s, nm in ((1.0, a_w, x_r, 'L'), (-1.0, a_m, s_m * x_r, 'R')):
            m1 = n_w + sd * fall_n * X
            m1 /= np.linalg.norm(m1)
            m2 = sd * X - fall_n * n_w
            m2 /= np.linalg.norm(m2)
            r_s = a_s + sd * X * (xr_s * HL)
            prog.roundbox(r_s + (m1 + m2) * big, [big, big, big], r=0.0, axes=np.column_stack([m1, m2, np.cross(m1, m2)]),
                          op=sdf.UNION, k=0.0, name='abaxial_fall_' + nm)
    prog.end_group()
    # the stump's clean end, square to the cannon: where the deer's own leg will continue
    pc = (fet + dc * ((top_cut - fet[1]) / dc[1])) * HL
    Rc = np.column_stack([[1.0, 0.0, 0.0], dc, np.cross([1.0, 0.0, 0.0], dc)])
    prog.roundbox(pc - dc * big, [big, big, big], r=0.0, axes=Rc, op=sdf.INTERSECT, k=0.004 * HL, name='stump_cut')
    info['coronet_plane'] = dict(point=a_w, normal=n_w, along=e_w)
    info['stump_cut'] = dict(point=pc, normal=dc)
    info['fetlock'] = fet * HL
    info['bounds'] = (np.array([-0.52, 0.18, -1.75]) * HL, np.array([0.52, top_cut + 0.06, -0.20]) * HL)
    if log:
        log(f'[hoof] stump: HL {HL * 1e3:.1f} mm, coronet step {step * HL * 1e3:.2f} mm, {len(prog.kind)} primitives')
    return prog, info


# -------------------------------------------------------------------------------------------------- the rig rows
def rig_rows(F, HL, prefix='f'):
    """THE HOOF STAGE'S REST DATA (DEER_PLAN §8.4, §6.4, §6.6), as data for ONE LEFT FOOT of hoof length HL (the
    hind foot: prefix 'h' and its own HL = hind_scale x the fore's; `_R` mirrors x): metres in the foot's frame
    (+Y up, +Z forward, +X the creature's left; the toe tips at z = 0, the ground at y = 0).
      joints    the wolf's grammar (families/limbed.py): per main digit (III medial at -X, IV lateral at +X) `_0`
                the fetlock joint, `_1` the pastern joint (P1 | P2), `_2` the coffin joint (P2 | P3): it carries
                the capsule, RIGID, one influence; the dewclaws II (medial) and V (lateral) are rigid leaves
      sockets   per claw the toe and heel points on the ground (socket_hoof_toe_* / socket_hoof_heel_*: the sole's
                frame is the line between them, its normal down), per dewclaw its tip (the stage's ground clamp)
      capsules  which primary each of the foot's four pieces repeats, and how it is placed (mirror, frame)
      stage     the hoof stage's numbers that are the capsule's own (the breakover shares, the splay's range, the
                fetlock's range, the rest angles)
    THE CHAIN IS BUILT FROM THE GROUND UP, as the base's stand solve builds it (species/red_deer.py): the coffin
    joint is the capsule's own (its place inside the claw); P2 and P1 stand on it along the pastern's BONE axis
    (`bone_axis`, fore / hind) and end at the digit's fetlock joint; `fetlock` is the two digits' mean (the
    joint's centre, in the cannon's condyles). `fetlock_outline` is another thing: the middle of the fetlock's
    bulge on the photos' outline (with its sesamoids, lower and further back), which shaped the neutral stump.
    On a host the BASE's skeleton owns the fetlock and the phalanges' lengths, and reads from these rows what is
    the capsule's own: the coffin joint's height and place, the toe and heel points, the dewclaws. `phalanx_scale`
    keeps P1 and P2 at the FORE hoof's lengths when a hind foot's capsule is the scaled repeat (bones do not
    shrink with the capsule). The stage itself is a later round (HF5)"""
    p = F.p
    k = 0 if prefix == 'f' else 1
    HLb = HL / (p['hind_scale'] if k else 1.0)                         # the fore hoof's length: the bones' unit
    a = np.radians(p['bone_axis'][k])
    up_back = np.array([0.0, np.sin(a), -np.cos(a)])
    meta = 'metacarpus_L' if prefix == 'f' else 'metatarsus_L'
    deg = lambda v: float(np.degrees(np.arctan2(v[1], np.hypot(v[0], v[2]))))      # noqa: E731  over the ground
    fet_o = np.array([0.0, p['fetlock_h'], -p['fetlock_behind_toe']]) * HL
    cof0 = np.array([0.0, p['coffin_h'], -p['coffin_s']]) * HL
    fet = cof0 + up_back * (p['p1_len'] + p['p2_len']) * HLb
    rows = dict(units='m', frame='+Y up, +Z forward (toes), +X left; toe tips at z 0, ground y 0', HL=HL,
                preset=F.preset, prefix=prefix, fetlock=fet.tolist(), fetlock_outline=fet_o.tolist(),
                bone_axis_deg=float(p['bone_axis'][k]), p1=p['p1_len'] * HLb, p2=p['p2_len'] * HLb,
                joints=[], sockets=[], capsules=[],
                stage=dict(breakover=dict(walk=0.20, trot=0.12, gallop=0.15), toe_roll_max_deg=[20.0, 30.0],
                           fetlock_range_deg=[-15.0, 50.0], fetlock_sink_peak=0.55, splay_rest_deg=p['splay_rest'],
                           splay_max_deg=p['splay_max'], claw_roll_deg=8.0, wall_angle_deg=p['wall_angle'],
                           tags='breakover walk [P], trot and gallop [E]; toe roll, splay, claw roll [E] (HF5)'),
                weights=dict(capsule='rigid on its `_2` joint, one influence', tuck='100 % on that joint (the '
                             'coronet\'s lip stays on the wall in every pose)', dewclaw='rigid on its own joint',
                             pastern_skin='the host\'s: fetlock -> pastern -> claws, the cleft split between the claws'))
    toe, heel = F.toe_point(), F.heel_point()
    for side, d in ((1.0, 4), (-1.0, 3)):
        # the foot's two digits: IV on the outer side of a LEFT foot (+X), III on its inner side: the capsule's own
        # points (coffin joint, toe, heel) placed as the claw is (pair(): the partner mirrored and scaled)
        cof = pair_place(np.array([p['coffin_x'], p['coffin_h'], -p['coffin_s']]) * HL, F, HL, side)
        fj = fet + np.array([side * p['digit_x_fetlock'] * HLb, 0.0, 0.0])
        pj = cof + (fj - cof) * (p['p2_len'] / (p['p1_len'] + p['p2_len']))
        tp = pair_place(np.array([toe[0], 0.0, -toe[2]]) * HL, F, HL, side)
        hp = pair_place(np.array([heel[0], 0.0, -heel[2]]) * HL, F, HL, side)
        for k, pos, par, tail in ((0, fj, meta, pj), (1, pj, f'{prefix}_digit{d}_0_L', cof),
                                  (2, cof, f'{prefix}_digit{d}_1_L', tp)):
            rows['joints'].append(dict(name=f'{prefix}_digit{d}_{k}_L', parent=par, head=pos.tolist(),
                                       tail=tail.tolist(), rigid=(k == 2), carries=('capsule' if k == 2 else 'skin'),
                                       length=float(np.linalg.norm(tail - pos)),
                                       rest_pitch_deg=deg(pos - tail)))
        for nm, q in (('toe', tp), ('heel', hp)):
            rows['sockets'].append(dict(name=f'socket_hoof_{nm}_{prefix}{d}_L', joint=f'{prefix}_digit{d}_2_L',
                                        pos=q.tolist(), normal=[0.0, -1.0, 0.0], forward=[0.0, 0.0, 1.0]))
        _, sc_, cen_ = pair(F, HL)[0 if side > 0 else 1]
        rows['capsules'].append(dict(name=f'{prefix}_hoof{d}_L', joint=f'{prefix}_digit{d}_2_L', primary='claw',
                                     mirror_x=bool(side < 0), scale=float(sc_), scale_centre=cen_.tolist(),
                                     coffin=cof.tolist(), sole_length=float(np.linalg.norm(tp - hp))))
    for (base, Rm, side), d in zip(dewclaw_frames(p, HL), (5, 2)):
        tip = base + Rm @ (dewclaw_tip(p) * HL)                        # the template's own tip (its lean and hook)
        rows['joints'].append(dict(name=f'{prefix}_dewclaw{d}_L', parent=meta, head=base.tolist(),
                                   tail=tip.tolist(), rigid=True, carries='dewclaw',
                                   length=float(np.linalg.norm(tip - base)), rest_pitch_deg=deg(base - tip)))
        rows['sockets'].append(dict(name=f'socket_dew_tip_{prefix}{d}_L', joint=f'{prefix}_dewclaw{d}_L',
                                    pos=tip.tolist(), clamp='ground'))
        # R's determinant is -1 on the medial pad: the template mirrored as data (dewclaw_frames)
        rows['capsules'].append(dict(name=f'{prefix}_dewhoof{d}_L', joint=f'{prefix}_dewclaw{d}_L', primary='dewclaw',
                                     mirror_x=bool(np.linalg.det(Rm) < 0.0), origin=base.tolist(), R=Rm.tolist()))
    return rows


def skeleton(F, HL, c, prefix='f'):
    """the cloven foot's joints in families/limbed.py's names, for a foot whose fetlock centre is c (the base's
    `_hoof` asks this of the generator: DEER_PLAN §4.2 item 2): {name: (3,)} for {prefix}_digit{3,4}_{0,1,2}_L,
    _tip_L (the toe point on the ground), {prefix}_dewclaw{2,5}_L and _tip_L. The capsule's own points (coffin joint,
    toe, dewclaws) keep their place relative to the GROUND and to the toe line; the `_0` and `_1` joints lie on the
    line from the host's fetlock to the coffin joint"""
    rows = rig_rows(F, HL, prefix)
    c = np.asarray(c, float)
    shift = np.array([c[0], 0.0, c[2] - rows['fetlock'][2]])           # the foot's frame set under the host's fetlock
    P = {}
    for j in rows['joints']:
        P[j['name']] = np.asarray(j['head']) + shift
    for d in (3, 4):
        sx = -1.0 if d == 3 else 1.0
        cof = P[f'{prefix}_digit{d}_2_L']
        f0 = c + np.array([sx * F.p['digit_x_fetlock'] * HL, 0.0, 0.0])
        P[f'{prefix}_digit{d}_0_L'] = f0
        P[f'{prefix}_digit{d}_1_L'] = cof + (f0 - cof) * (F.p['p2_len'] / (F.p['p1_len'] + F.p['p2_len']))
    for s in rows['sockets']:
        if s['name'].startswith('socket_hoof_toe_'):
            P[f'{prefix}_digit{s["name"][-3]}_tip_L'] = np.asarray(s['pos']) + shift
        if s['name'].startswith('socket_dew_tip_'):
            P[f'{prefix}_dewclaw{s["name"][-3]}_tip_L'] = np.asarray(s['pos']) + shift
    return P
