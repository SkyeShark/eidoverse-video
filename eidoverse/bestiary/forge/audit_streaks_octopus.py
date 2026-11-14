"""The OCTOPUS's side of the streak audit (forge/audit_streaks.py): a forge run folder of the octopus chain (t10's low,
drivers and instances, t11's maps: work/bestiary/octopus, or a staged round's t10 folder).

  * sets: 'head' (the 4096 head set: body, crown top, crown oral) and 'arms' (the stacked arms set, baked from the
    reference arm, region 3; drawn on all eight arms in the overlay).
  * check 1, the coordinate: octopus_skin.skin_at's ARM coordinate q_a, replicated term by term (the nearest arm by
    azimuth rotated onto the reference arm, the nearest centreline point among the segments round the best of every 4th
    node, s with t clamped, bd, r = arm_radius(s), alpha, armw = 1 - smoothstep(r, 1.6 r, bd)) in numpy or cupy, in
    the variant the run's skin source carries: 'clamped' (live 8801e4ab and before: q_a = (U(s), R cos a, R sin a), its
    use weight armw), 'continued' (crown v5's hunk, a875e2a3, landed in b1dd6aaf: U runs on behind the first node, the
    circle scales by bd past 1.15 r, and the network fades behind the node and at the sector bisector: armw_net) or
    'foot' (polish 1: on the head set the sweep's FOOT POINT, octopus_skin.foot_frame, for s, bd and alpha, and the
    circle scaled from the arm's SECTION radius, octopus_skin.section_k, not from 1.15 r). The head network's
    coordinate is the point itself (isometric: nothing to check). The replica proves itself on every run (fidelity):
    on the oral layer's lateral band the skin writes ventral = 1 - armw (clamped), 1 - w_tube (continued) or v_rim (1 -
    w_tube) ('foot': v_rim the web margin's ramp, octopus_skin.rim_map) into the masks' G, which the replica predicts
    texel by texel.
  * check 2: albedo, roughness (ORM G), normal, the patch random (masks A); the high = T_<set>_N.png (t10); zones by
    the bake's region (head) and by the arm frame's side (arms); the arms' baked suckers' grooves are designed.
  * check 3: the plan's head papillae and warts and the reference arm's papillae on all eight arms (octopus_sculpt's
    replicate: rot_y(az_j - az_0); a plan with arm_papillae_seated, polish 1's seat_papillae, those seated copies as
    planted; with band_papillae, crown v6b's band_sites off the tubes, those too); plantable by DESIGN, not by the
    planter's territories: the head set's body and crown
    top less the eyes' lid bowls and the funnel (eye_clear, funnel_mask: the plan's own exclusions), the arms' aboral and
    lateral skin weighted by the plan's taper toward the tip. (head_sites' arm_owner and arm_sites' s > 0 split the
    territory between two planters; the gap between them is exactly the kind of hole this check is for.)
  * places, for the report's totals: 'crown strip' (behind a first node), 'arm tube', 'tube rim' (1.0-1.15 r), 'web
    junction' (1.15-1.6 r), else the bake's region (body, crown top, crown oral); the arms set by the arm's side.
"""
import hashlib
import os

import numpy as np

from . import audit_streaks as AS

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE_SKIN = os.path.join(HERE, 'species', 'octopus_skin.py')
# the skin sources whose arm coordinate is known (sha1 -> variant); anything else: read from the source itself
KNOWN_SKIN = {'8801e4ab09adf0026a104c69e70e94259d8c282e': 'clamped',
              'a875e2a32e9e241b36173ff8a5dc770c74026927': 'continued',
              'b1dd6aaf7e979fe718a7b0bdd36392348e8fd438': 'continued',         # (stage 1's landed skin, 10-28)
              '1816a3ff72a92fb7432cc9f3804fd7a678ebd6cc': 'foot',              # (polish 1's, 10-28)
              '8cbbc340088ab9ca7795fc37820dcaffdcdf177a': 'foot'}              # (crown v6b's, 10-29)
ARM_NAMES = ['L1', 'L2', 'L3', 'L4', 'R1', 'R2', 'R3', 'R4']


def skin_variant(path):
    """the arm coordinate a skin source carries: by its sha1 when known, else by its text (crown v5's continuation
    defines rad_k and behind inside skin_at; polish 1's foot point calls foot_g and sec_k there)"""
    b = open(path, 'rb').read()
    h = hashlib.sha1(b).hexdigest()
    if h in KNOWN_SKIN:
        return KNOWN_SKIN[h], h, 'known sha1'
    src = b.decode('utf-8', 'replace')
    i = src.find('def skin_at')
    body = src[i:src.find('\n@wp.', i + 10)] if i >= 0 else ''
    v = 'continued' if ('rad_k' in body and 'behind' in body and 'armw_net' in body) else 'clamped'
    if v == 'continued' and 'foot_g(' in body and 'sec_k(' in body:
        v = 'foot'
    return v, h, 'read from the source (unknown sha1)'


def _wrap_pi(xp, a):
    return a - 2.0 * np.pi * xp.floor((a + np.pi) / (2.0 * np.pi))


def _table(xp, t, s):
    """octopus_skin.table: linear lookup on a uniform table over s in [0, 1]"""
    n = t.shape[0]
    x = xp.clip(s, 0.0, 1.0) * (n - 1)
    i = xp.minimum(xp.floor(x).astype(xp.int64), n - 2)
    f = x - i
    return t[i] * (1.0 - f) + t[i + 1] * f


def _norm(xp, v):
    return v / xp.maximum(xp.linalg.norm(v, axis=1, keepdims=True), 1e-20)


class OctopusAudit(AS.CreatureAudit):
    name = 'octopus'

    def __init__(self, run_dir, skin_src=None, variant=None, label=None):
        super().__init__(run_dir, label)
        from .species import octopus as OC
        from .species.octopus_sculpt import arm_tables
        self.OC = OC
        self.spec = OC.SPEC
        self.skin_src = skin_src or LIVE_SKIN
        v, h, how = skin_variant(self.skin_src)
        self.variant = variant or v
        self.notes.append(f'skin source {os.path.relpath(self.skin_src, os.path.join(HERE, "..", "..", ".."))} '
                          f'(sha1 {h[:8]}): arm coordinate "{self.variant}" ({"forced" if variant else how})')
        L = self.low()
        self.order = np.asarray(L['order'])
        self.az = OC.arm_azimuths()
        self.arms = [OC.arm_centreline(self.spec, a) for a in self.az]
        ref = self.arms[self.order[0]]
        st, U, R = arm_tables(self.spec)          # t11's tables (all arms one length: the reference's)
        rad = OC.arm_radius(st, self.spec)
        from .species.octopus_skin import node_tangents
        self._host = dict(az=self.az.astype(np.float64), az0=float(self.az[self.order[0]]), refP=ref[0], refN=ref[1],
                          refB=ref[2], refT=node_tangents(np.asarray(ref[0], np.float64)), nodes=np.arange(0, len(ref[0]), 4),
                          U=U, R=R, rad=rad, g=R / rad)
        self._dev = {}

    # ---- the run folder
    def sets(self):
        if getattr(self, '_sets', None) is None:
            L = self.low()
            fs, reg = L['face_set'], L['region']
            self._sets = [dict(name=name, faces=faces, size=int(self.drivers(name)['normal'].shape[0]), render_faces=rf)
                          for name, faces, rf in (('head', fs == 'head', fs == 'head'),
                                                  ('arms', (fs == 'arms') & (reg == 3), fs == 'arms'))]
        return self._sets

    def drivers(self, set_name):
        if set_name not in self._drv:
            z = np.load(os.path.join(self.run_dir, f'drivers_{set_name}.npz'))
            # (with the material ids and the hidden texels when the bake wrote them: AS.CreatureAudit.parts)
            self._drv[set_name] = {k: z[k] for k in AS.DRIVER_KEYS if k in z.files}
        return self._drv[set_name]

    # ---- the arm coordinate (skin_at's first block)
    def _C(self, xp):
        key = xp.__name__
        if key not in self._dev:
            self._dev[key] = {k: (v if np.isscalar(v) else xp.asarray(v)) for k, v in self._host.items()}
        return self._dev[key]

    def arm_coord(self, P, xp, set_kind, variant=None):
        """q_a, its use weight, its nominal scale (g = r0 / max(r, 0.3 r0): the coordinate is conformal at that scale on
        the tube) and the frame's terms (s, seg, bd, r, alpha, armw, behind, best), for points P (n, 3)"""
        C = self._C(xp)
        variant = variant or self.variant
        refP, refN, refB, az, nodes = C['refP'], C['refN'], C['refB'], C['az'], C['nodes']
        n_pts = refP.shape[0]
        P = xp.asarray(P, dtype=xp.float64)
        a_p = xp.arctan2(P[:, 0], P[:, 2])
        dd = xp.abs(_wrap_pi(xp, a_p[:, None] - az[None, :]))
        jb = xp.argmin(dd, axis=1)
        best = xp.min(dd, axis=1)
        phi = C['az0'] - az[jb]
        c, s_ = xp.cos(phi), xp.sin(phi)
        q0 = xp.stack([c * P[:, 0] + s_ * P[:, 2], P[:, 1], -s_ * P[:, 0] + c * P[:, 2]], 1)
        dn = xp.linalg.norm(q0[:, None, :] - refP[nodes][None], axis=2)
        bi = nodes[xp.argmin(dn, axis=1)]
        bd = xp.full(len(P), 1.0e9)
        s_best = xp.zeros(len(P))
        seg = xp.zeros(len(P), dtype=xp.int64)
        for off in range(-5, 6):
            i = bi + off
            valid = (i >= 0) & (i <= n_pts - 2)
            ic = xp.clip(i, 0, n_pts - 2)
            a = refP[ic]
            e = refP[ic + 1] - a
            t = xp.clip(((q0 - a) * e).sum(1) / xp.maximum((e * e).sum(1), 1e-12), 0.0, 1.0)
            d = xp.linalg.norm(q0 - (a + e * t[:, None]), axis=1)
            better = valid & (d < bd)
            bd = xp.where(better, d, bd)
            s_best = xp.where(better, (ic + t) / (n_pts - 1), s_best)
            seg = xp.where(better, ic, seg)
        s = s_best
        r = _table(xp, C['rad'], s)
        ta = _norm(xp, refP[seg + 1] - refP[seg])
        ft = xp.clip(s * (n_pts - 1) - seg, 0.0, 1.0)[:, None]
        na = _norm(xp, refN[seg] * (1.0 - ft) + refN[seg + 1] * ft)
        ba = _norm(xp, refB[seg] * (1.0 - ft) + refB[seg + 1] * ft)
        cc = refP[seg] + (refP[seg + 1] - refP[seg]) * ft
        v = q0 - cc
        v = v - ta * (v * ta).sum(1, keepdims=True)
        alpha = xp.arctan2((v * ba).sum(1), (v * na).sum(1))
        if variant == 'foot' and set_kind == 0:
            # (polish 1) the head set's frame by the sweep's foot point near that nearest point (skin_at's own terms)
            from .species.octopus_skin import foot_frame
            fr = foot_frame(q0, refP, refN, C['refT'], s, xp=xp)
            s, seg, bd, alpha = fr['s'], fr['seg'], fr['bd'], fr['alpha']
            r = _table(xp, C['rad'], s)
        armw = 1.0 - AS.smoothstep(xp, r, 1.6 * r, bd)
        if set_kind == 1:
            armw = xp.ones_like(armw)
        U = _table(xp, C['U'], s)
        R = _table(xp, C['R'], s)
        behind = xp.zeros_like(s)
        if variant in ('continued', 'foot') and set_kind == 0:
            t0a = refP[1] - refP[0]
            t0a = t0a / xp.linalg.norm(t0a)
            behind = xp.where(seg == 0, xp.maximum(-((q0 - refP[0]) * t0a[None]).sum(1), 0.0), 0.0)
            if variant == 'foot':
                from .species.octopus_skin import section_k
                rad_k = xp.maximum(bd / xp.maximum(1.01 * r * section_k(alpha, xp=xp), 1e-6), 1.0)
            else:
                rad_k = xp.maximum(bd / xp.maximum(1.15 * r, 1e-6), 1.0)
            q = xp.stack([U - behind * (R / xp.maximum(r, 1e-6)), R * rad_k * xp.cos(alpha), R * rad_k * xp.sin(alpha)], 1)
            d_bis = (0.39269908 - best) * xp.sqrt(P[:, 0] ** 2 + P[:, 2] ** 2)
            w = armw * (1.0 - AS.smoothstep(xp, 0.0, 0.010, behind)) * AS.smoothstep(xp, 0.004, 0.012, d_bis)
        else:
            q = xp.stack([U, R * xp.cos(alpha), R * xp.sin(alpha)], 1)
            w = armw
        sref = _table(xp, C['g'], s)
        return q, w, sref, dict(s=s, seg=seg, bd=bd, r=r, alpha=alpha, armw=armw, behind=behind, best=best, jb=jb)

    def coordinates(self, set_name):
        kind = 0 if set_name == 'head' else 1
        from .species.octopus_sculpt import PATCH

        def fn(P, xp):
            q, w, sref, _ = self.arm_coord(P, xp, kind)
            return q, w, sref
        return [dict(name='arm q_a', fn=fn, cell=PATCH['arm'],
                     note=f'octopus_skin.skin_at arm coordinate ({self.variant}), set_kind {kind}')]

    def _frame_at(self, P, set_kind, chunk=400000):
        """alpha, s, bd, r, armw at points P (host arrays), on the GPU when there"""
        xp, _, to_np, _ = AS.backend(True)
        out = {}
        for s0 in range(0, len(P), chunk):
            _, w, _, ex = self.arm_coord(xp.asarray(P[s0:s0 + chunk]), xp, set_kind)
            ex['w'] = w
            for k, v in ex.items():
                out.setdefault(k, []).append(to_np(v))
        return {k: np.concatenate(v) for k, v in out.items()}

    def frame(self, set_name, G):
        """the arm frame at every inside texel's base point, once per set"""
        key = (set_name, G.n)
        if getattr(self, '_frames', None) is None:
            self._frames = {}
        if key not in self._frames:
            self._frames[key] = self._frame_at(G.B, 0 if set_name == 'head' else 1)
        return self._frames[key]

    def _region_at(self, P):
        """the bake's region (0 body, 1 crown top, 2 crown oral) of the head face nearest each point"""
        if getattr(self, '_cen_tree', None) is None:
            from scipy.spatial import cKDTree
            L = self.low()
            hf = L['face_set'] == 'head'
            self._cen_tree = (cKDTree(L['V'][L['F'][hf]].mean(1)), L['region'][hf])
        _, ti = self._cen_tree[0].query(P)
        return self._cen_tree[1][ti]

    def places(self, set_name, P):
        """per point its category in the arm frame: 'crown strip' (behind a first node, s clamped to 0, within 1.6 r:
        the band Skye found), 'arm tube' (bd <= r), 'tube rim' (1.0-1.15 r: crown v5's continued q_a keeps rad_k 1 there),
        'web junction' (1.15-1.6 r: the clamped q_a ignores the distance from the axis there), else the bake's region
        (body, crown top, crown oral); on the arms set the arm frame's side"""
        P = np.asarray(P, np.float64)
        if set_name != 'head':
            ca = np.cos(self._frame_at(P, 1)['alpha'])
            return np.where(ca > 0.2, 'arm aboral', np.where(ca > -0.4, 'arm lateral', 'arm oral'))
        fr = self._frame_at(P, 0)
        rr = fr['bd'] / fr['r']
        behind = (fr['seg'] == 0) & (fr['s'] < 1e-9)
        out = np.array(['body', 'crown top', 'crown oral', 'arm'], dtype=object)[np.clip(self._region_at(P), 0, 3)]
        out[rr <= 1.6] = 'web junction (1.15-1.6 r)'
        out[rr <= 1.15] = 'tube rim (1.0-1.15 r)'
        out[rr <= 1.0] = 'arm tube'
        out[behind & (rr <= 1.6)] = 'crown strip (behind a first node)'
        return out.astype(str)

    def describe(self, P):
        """'behind R1's first node (1.12 r)', 'L3 s 0.142, oral, 1.31 r', 'body (R2 sector), y 201 mm'"""
        P = np.asarray(P, np.float64)
        fr = self._frame_at(P, 0)
        reg = self._region_at(P)
        out = []
        for i in range(len(P)):
            nm = ARM_NAMES[int(fr['jb'][i])]
            rr = fr['bd'][i] / fr['r'][i]
            ca = np.cos(fr['alpha'][i])
            side = 'aboral' if ca > 0.3 else ('oral' if ca < -0.3 else 'lateral')
            if fr['seg'][i] == 0 and fr['s'][i] < 1e-9 and rr < 1.6:
                out.append(f"behind {nm}'s first node ({rr:.2f} r, {side})")
            elif rr <= 1.6:
                out.append(f'{nm} s {fr["s"][i]:.3f}, {side}, {rr:.2f} r')
            else:
                out.append(f'{("body", "crown top", "crown oral")[int(reg[i])] if reg[i] < 3 else "arm"} ({nm} sector, '
                           f'{rr:.1f} r off the arm), y {P[i, 1] * 1000:.0f} mm')
        return out

    # ---- check 2
    def groups(self, set_name):
        # (relief: the shipped normal less t10's, the skin pass's own relief; patch: the runtime's patch random, latent)
        return [dict(name='albedo', key='albedo', kind='loglum'), dict(name='roughness', key='orm', kind='channel', ch=1),
                dict(name='relief', key='normal', kind='normal_delta', ref='N'),
                dict(name='patch', key='masks', kind='channel', ch=3, latent=True)]

    def zones(self, set_name, G):
        if set_name == 'head':
            reg = self.drivers('head')['region'][G.ys, G.xs].astype(np.int16)
            return reg, {0: 'body', 1: 'crown top', 2: 'crown oral'}
        ca = np.cos(self.frame(set_name, G)['alpha'])
        z = np.where(ca > 0.2, 0, np.where(ca > -0.4, 1, 2)).astype(np.int16)
        return z, {0: 'arm aboral', 1: 'arm lateral', 2: 'arm oral'}

    def _suckers(self, set_name):
        """every sucker's centre and diameter on this set (the head set: the reference arm's on all eight arms)"""
        I = np.load(os.path.join(self.run_dir, 'instances.npz'))
        from .species.octopus_sculpt import rot_y
        p, d = I['suckers_p'], I['suckers_d']
        if set_name == 'arms':
            return p, d
        a0 = self.az[self.order[0]]
        return (np.concatenate([p @ rot_y(self.az[self.order[j]] - a0).T for j in range(len(self.az))]),
                np.tile(d, len(self.az)))

    def designed(self, set_name, G):
        """the suckers (geometry or baked): their discs, rims and the occlusion rings round them are circles whose edges
        read as oriented texture; never streaks (0.9 d round each centre: the geometric suckers' occlusion rings in the
        skin's AO, roughness and colour reach ~0.85 d, the first audit's crescents; on the arms set also the baked
        suckers' masks)"""
        from scipy.spatial import cKDTree
        p, d = self._suckers(set_name)
        dist, j = cKDTree(p).query(G.B, distance_upper_bound=0.9 * float(d.max()))
        ok = np.isfinite(dist)
        out = np.zeros(G.n, bool)
        out[ok] = dist[ok] < 0.9 * d[j[ok]]
        if set_name == 'head':
            # the mouth: the lip's ring and radial folds, the dark lining inside the opening (1.8 lip radii round the
            # mouth point: octopus.mouth_point, mouth_dims)
            mo = self.OC.mouth_dims(self.spec)
            out |= np.linalg.norm(G.B - self.OC.mouth_point(self.spec), axis=1) < 1.8 * (mo['R'] + mo['r'])
        if set_name == 'arms':
            m = self.load_map('arms', 'masks')
            if m is not None:
                from scipy import ndimage as nd
                out |= nd.binary_dilation(m[..., 2] > 25, iterations=3)[G.ys, G.xs]
        return out

    def designed_dirs(self, set_name, G):
        """the skin's transverse arm WRINKLES (octopus_skin.skin_at: creases round the arm on its own tube, mostly
        aboral): designed streaks in the relief running round the arm, on the tube (s > 0, bd < 1.12 r)"""
        fr = self.frame(set_name, G)
        tube = (fr['s'] > 1e-9) & (fr['bd'] < 1.12 * fr['r'])
        T = np.zeros((G.n, 3))
        jb = fr['jb'].astype(np.int64)
        for j in np.unique(jb[tube]):
            m = tube & (jb == j)
            t = self.arms[int(j)][3]                     # the arm's own tangents (octopus.arm_centreline's rmf frame)
            sa = np.linspace(0.0, 1.0, len(t))
            T[m] = np.column_stack([np.interp(fr['s'][m], sa, t[:, k]) for k in range(3)])
        d = np.cross(G.N, T)
        return {'relief': (d / np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-20), tube)}

    # ---- check 3
    def features(self, set_name):
        I = np.load(os.path.join(self.run_dir, 'instances.npz'))
        from .species.octopus_sculpt import rot_y
        a0 = self.az[self.order[0]]
        if set_name == 'arms':
            p, n, rb = I['arm_papillae_p'], I['arm_papillae_n'], I['arm_papillae_rb']
            kind = np.zeros(len(p), np.int8)
        else:
            P, N, RB, K = [I['head_papillae_p'], I['warts_p']], [I['head_papillae_n'], I['warts_n']], \
                [I['head_papillae_rb'], I['warts_rb']], [np.zeros(len(I['head_papillae_p'])), np.ones(len(I['warts_p']))]
            if 'arm_papillae_seated_p' in I.files:
                # (polish 1: every arm's copies as planted, seated on its own skin: octopus_sculpt.seat_papillae)
                P.append(I['arm_papillae_seated_p'])
                N.append(I['arm_papillae_seated_n'])
                RB.append(I['arm_papillae_seated_rb'])
                K.append(np.full(len(I['arm_papillae_seated_p']), 2))
            else:
                for j in range(len(self.az)):
                    Rm = rot_y(self.az[self.order[j]] - a0)             # octopus_sculpt.replicate's rotation
                    P.append(I['arm_papillae_p'] @ Rm.T)
                    N.append(I['arm_papillae_n'] @ Rm.T)
                    RB.append(I['arm_papillae_rb'])
                    K.append(np.full(len(I['arm_papillae_p']), 2))
            if 'band_papillae_p' in I.files:
                # (crown v6b: the arms' papillae planted in the band off each tube, octopus_sculpt.band_sites)
                P.append(I['band_papillae_p'])
                N.append(I['band_papillae_n'])
                RB.append(I['band_papillae_rb'])
                K.append(np.full(len(I['band_papillae_p']), 2))
            p, n, rb, kind = np.concatenate(P), np.concatenate(N), np.concatenate(RB), np.concatenate(K).astype(np.int8)
        f = getattr(self, 'feature_filter', None)
        if f is not None:
            keep = f(set_name, p)
            p, n, rb, kind = p[keep], n[keep], rb[keep], kind[keep]
        return dict(p=p, n=n, rb=rb, kind=kind)

    def feature_zones(self, set_name, G):
        """check 3's zones: the head set's crown top split into the ARM ROOTS (past the first node, within 1.15 local
        radii: arm_sites' territory, 1.8 mm patches on the arm) and the rest (head_sites' territory, 2.8 mm patches at
        0.38: a third of the arm roots' density by design); the strip behind a first node is crown top by design"""
        if set_name != 'head':
            return np.zeros(G.n, np.int16), {0: 'arm'}
        reg = self.drivers('head')['region'][G.ys, G.xs].astype(np.int16)
        fr = self.frame(set_name, G)
        arm = (fr['s'] > 1e-9) & (fr['bd'] < 1.15 * fr['r'])
        z = np.where(reg == 0, 0, np.where(reg == 2, 3, np.where(arm, 1, 2))).astype(np.int16)
        return z, {0: 'body', 1: 'crown top arm roots', 2: 'crown top', 3: 'crown oral'}

    def plantable(self, set_name, P, N, zone):
        """the plan's DESIGN density, relative (0..1): on the head set's body and crown top the head papillae, less the
        eyes' lid bowls and the funnel (octopus_sculpt.eye_clear, funnel_mask); on the arm roots and the arms set the
        arm papillae: aboral and lateral, tapering toward the tip (plan_octopus's w(alpha) x its taper in s); none on the
        oral layer (0.04 by design)"""
        from .species.octopus_sculpt import eye_clear, funnel_mask
        P = np.asarray(P, np.float64)
        arm_w = lambda fr: np.clip((np.cos(fr['alpha']) + 0.25) / 0.6, 0.0, 1.0) * \
            np.clip(1.0 - (fr['s'] - 0.45) / 0.5, 0.1, 1.0) * (fr['s'] < 0.97)
        if set_name == 'head':
            w = np.isin(zone, (0, 2)).astype(np.float64)
            for side in (+1, -1):
                w *= eye_clear(P, self.spec, side)
            w *= 1.0 - funnel_mask(P, self.spec)
            ar = zone == 1
            if ar.any():
                w[ar] = arm_w(self._frame_at(P[ar], 0))
            return w.astype(np.float32)
        return arm_w(self._frame_at(P, 1)).astype(np.float32)

    # ---- labels, renders, proofs
    def landmarks(self):
        if getattr(self, '_lm', None) is not None:
            return self._lm
        L = self.low()
        V, F = L['V'], L['F'][(L['face_set'] == 'head') & (L['region'] == 1)]
        cen = V[F].mean(1)
        lm = {}
        for j, nm in enumerate(ARM_NAMES):
            p0 = self.arms[j][0][0]
            lm[f'{nm} first node'] = p0
            # the crown top's surface nearest the node, along the way back toward the head (the strip the clamped
            # coordinate paints)
            d = np.linalg.norm(cen - p0, axis=1)
            lm[f'{nm} root top'] = cen[int(np.argmin(d))]
        for side, nm in ((1, 'left eye'), (-1, 'right eye')):
            lm[nm] = self.OC.eye_geom(self.spec, side)[0]
        fa, fb, _, _ = self.OC.funnel_geom(self.spec)
        lm['funnel'] = 0.5 * (fa + fb)
        self._lm = lm
        return lm

    def renders(self):
        cy = self.spec['crown_y']
        return [dict(tag='whole', views=('threeq', 'top', 'front'), center=None, span=None),
                dict(tag='crown', views=('top', 'threeq', 'front'), center=(0.0, cy + 0.02, -0.01), span=0.26,
                     per_check=True)]

    def coord_breakdown(self, set_name, G, idx):
        """where check 1's texels lie in the arm frame: behind the first node (s clamped to 0), off the tube (bd > 1.15
        r: the clamped q_a ignores bd there), the tube's rim (1.0-1.15 r: the continued q_a keeps rad_k 1 there), on
        the tube (bd <= r)"""
        if set_name != 'head':
            return None
        fr = self._frame_at(G.B[idx], 0)
        rr = fr['bd'] / fr['r']
        behind = (fr['seg'] == 0) & (fr['s'] < 1e-9)
        P = G.B[idx]
        d_bis = (np.pi / 8 - fr['best']) * np.sqrt(P[:, 0] ** 2 + P[:, 2] ** 2)
        return {'behind the first node': behind, 'off the tube (bd > 1.15 r)': ~behind & (rr > 1.15),
                'tube rim (1.0-1.15 r)': ~behind & (rr > 1.0) & (rr <= 1.15), 'tube (bd <= r)': ~behind & (rr <= 1.0),
                '(overlapping) within 3 mm of a sector bisector, where the nearest arm switches': d_bis < 0.003}

    def fidelity(self, set_name, G):
        """the replica against the skin's own output: on the oral layer (region 2) where the arm frame's side is lateral
        (cos alpha > -0.2, v_arm = 0) the skin wrote ventral = 1 - armw (clamped) or 1 - w_tube (continued) into the
        masks' G; compare where the prediction is in its ramp (0.05-0.95)"""
        if set_name != 'head':
            return None
        m = self.load_map('head', 'masks')
        if m is None:
            return None
        reg = self.drivers('head')['region'][G.ys, G.xs]
        sel = np.nonzero(G.cov_c & (reg == 2))[0]
        fr = self._frame_at(G.B[sel], 0)
        lat = np.cos(fr['alpha']) > -0.2
        w_off = AS.smoothstep(np, 1.05 * fr['r'], 1.25 * fr['r'], fr['bd'])          # 1 - w_tube
        pred = {'clamped': 1.0 - fr['armw'], 'continued': w_off}
        if self.variant == 'foot':
            # (polish 1: the oral layer's own weight near a web margin, the section's ramp; 1 elsewhere)
            from .species.octopus_skin import rim_map
            if getattr(self, '_rim', None) is None:
                self._rim = rim_map(self.drivers('head'), self.spec, self.arms)
            a = self._rim[G.ys[sel], G.xs[sel]].astype(np.float64)
            v_rim = np.where(a < 0.5, AS.smoothstep(np, 0.0, 0.006, a), 1.0)
            pred['foot'] = v_rim * w_off
        meas = m[G.ys[sel], G.xs[sel], 1].astype(np.float64) / 255.0
        out = dict(variant=self.variant)
        for k, pv in pred.items():
            ramp = lat & (pv > 0.05) & (pv < 0.95)
            if ramp.sum() < 100:
                out[k] = dict(texels=int(ramp.sum()))
                continue
            err = np.abs(meas[ramp] - pv[ramp])
            out[k] = dict(texels=int(ramp.sum()), mae=round(float(err.mean()), 4),
                          p95=round(float(np.percentile(err, 95)), 4),
                          corr=round(float(np.corrcoef(meas[ramp], pv[ramp])[0, 1]), 4))
        good = [k for k in pred if 'mae' in out.get(k, {})]
        if good:
            out['best_match'] = min(good, key=lambda k: out[k]['mae'])
            out['agrees'] = out['best_match'] == self.variant
        return out
