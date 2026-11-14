"""THE GROOM: a style (data) on a base -> roots, flow, guides, strands, the §9.2 gates; saved as groom.npz.

    g = Groom(base, style).build()          # style: a dict loaded from styles/<name>.json (spec.load)
    g.gates  -> the printed gates;  g.save(path);  Groom.load(path, base)

Stages (each recorded with its time):
  masks    the style's domain and bare expressions on the welded vertices (for the flow's gates) and at the roots
  flow     flow.Flow over the style's sources and singularities
  clumps   clump centres = Poisson roots at the style's card density (roots.py, priority dart throwing); the GUIDES
           grow from them (one per clump: a clump's mean curve is its card's spine later)
  strands  stable strand roots at the style's strand density (roots.py), each assigned its nearest clump centre,
           a class (the style's classes: share, length factor, lift, clump factor), its length (the length map x a
           bounded lognormal jitter, WOLF_PLAN §5.2: sigma 0.18 clipped 0.65-1.5x), lift and gravity, all from stable
           per-root hashes; grown by strands.grow, then the style's operators in order
Per-strand data kept: tri, bary, class, clump, rnd (the ABI's strandRandom), length, flex; the points (S, K, 3).

Coat round 3 (10-30): THE COAT'S EDGE, in the construction (round 2's shaggy hung 1,805 cards over bare skin: gravity
carried strands across the coat's lower edge while the flow ran along it; work/bestiary/coat/g5/g5_groom/NOTES.md):
  guard    (style "edge_guard": {"band_mm", "strength", "cut"}) a field per welded vertex: the direction into the bare
           zone (minus the surface gradient of the distance to it, fields.edge_distance_w) times a weight that is
           `strength` at the edge and falls to 0 `band_mm` inside it. Guides and strands grow with it (strands.k_grow:
           the part of a step heading into the bare zone turns along the edge)
  trim     (operator {"op": "trim", "cut", "margin_mm", "min_mm"}, last in the list) every strand and guide that still
           reaches skin whose coat mask is under the cut (a wave, a frizz or a clump pull past the guard) ends before
           it: cut at the crossing less the margin, resampled along its own path, its length recorded; gated
  feather  the styles thin and shorten the pelt toward its edge with the fields' edge_mm leaf (density and length)

B3 (11-07, HAIR_FUR H2 + H3): HAIR.
  groups   a style may list "groups": each a style overlay (its own domain, which multiplies the style's, its own flow,
           growth, length, lift, clumps, strands, operators, cards rules): grown as its own Groom on the same base (and
           the same SDF), then concatenated; every strand and clump keeps its group (saved as group / cgroup), every
           group's gates under gates.groups. The fringe and the hanging sides and back are two groups of one bob
  growth   a group's "growth": {"mode": "hang", "attach_mm": <field>, "offset_mm": <field>, "stiff": [s0, pow],
           "relax": {"iters", "gstep_mm", "bend"}}: strands.k_hang against the style's "sdf" (head + neck + shoulders,
           strands.SDF: {"lo": [x, y, z], "hi": [...], "h_mm": 2.5}), then k_hang_relax; "settle" becomes the SDF push
  operators (hang groups): "cut" (strands.cut_strands: a cut line per azimuth of the head frame, jittered per strand;
           strands and guides), "tuck" (the last tuck_mm bends toward the head's vertical axis by amp_mm x s^2: a bob's
           ends turning under), "anchor" (H3: every strand pulled to a point, or to a ring of radius ring_mm about it
           (axis "axis"), blended in over the last `blend` of its length: a tie or a bun's base; gated: the strand ends'
           distance to the anchor ring)
  gates    with an SDF, every point's SDF value: points inside (< 0), under the floor's margin, the minimum
"""
import json
import time

import numpy as np
import warp as wp

from . import strands as ST
from .fields import Fields, Pts
from .flow import Flow, node_points
from .roots import hkey, roots

DEG = np.pi / 180.0


def lognormal_jitter(u1, u2, sigma, clip):
    """a bounded lognormal factor from two uniforms (Box-Muller), clipped to [lo, hi]"""
    z = np.sqrt(-2.0 * np.log(np.maximum(u1, 1e-12))) * np.cos(2.0 * np.pi * u2)
    return np.clip(np.exp(sigma * z), clip[0], clip[1])


class Groom:
    def __init__(self, base, style, device=None, log=print, sdf=None, cache=None):
        self.base = base
        self.style = style
        self.device = device or wp.get_preferred_device()
        self.fields = Fields(base, style.get('fields', {}))
        self.seed = int(style.get('seed', 1))
        self.log = log
        self.times = {}
        self.gates = {}
        # (B3) the head + neck + shoulder SDF, built once per base (cached in `cache` by the base's sha1 and the box)
        self.cache = cache
        self.sdf = sdf
        if self.sdf is None and style.get('sdf'):
            sd = style['sdf']
            t0 = time.time()
            self.sdf = ST.SDF(base, sd['lo'], sd['hi'], sd.get('h_mm', 2.5) * 1e-3, self.device, cache=cache,
                              close_mm=float(sd.get('close_mm', 0.0)))
            self.times['sdf'] = round(time.time() - t0, 3)

    @staticmethod
    def group_style(style, gi, g):
        """(B3) a group's style: the style's keys with the group's over them (domain multiplied, fields merged, seed
        offset by the group's index)"""
        import copy
        sub = copy.deepcopy({k: v for k, v in style.items() if k not in ('groups',)})
        for k, v in g.items():
            if k == 'domain':
                sub['domain'] = {'mul': [style.get('domain', 1.0), v]}
            elif k == 'fields':
                sub['fields'] = dict(style.get('fields', {}), **v)
            else:
                sub[k] = copy.deepcopy(v)
        sub['seed'] = int(g.get('seed', int(style.get('seed', 1)) + 101 * (gi + 1)))
        sub['_group'] = g.get('name', f'group{gi}')
        return sub

    def _build_groups(self):
        """(B3) every group grown as its own Groom, then concatenated (strands, clumps, guides, per-strand data)"""
        st = self.style
        subs = []
        for gi, g in enumerate(st['groups']):
            t0 = time.time()
            sg = Groom(self.base, self.group_style(st, gi, g), self.device, self.log, sdf=self.sdf,
                       cache=self.cache).build()
            sg.strand_gates()
            subs.append(sg)
            self.times[f'group_{sg.style["_group"]}'] = round(time.time() - t0, 3)
        Ks = {s.K for s in subs}
        assert len(Ks) == 1, f'groups must share strands.points: {Ks}'
        self.K = Ks.pop()
        self.groups = [s.style['_group'] for s in subs]
        self.subs = subs
        b = self.base

        def cat_pts(lst):
            out = Pts(b, np.concatenate([p.tri for p in lst]), np.concatenate([p.bary for p in lst]))
            out.slot = np.concatenate([p.slot for p in lst])
            out.density = np.concatenate([p.density for p in lst])
            return out
        self.roots = cat_pts([s.roots for s in subs])
        self.clumps = cat_pts([s.clumps for s in subs])
        P = np.concatenate([s.points() for s in subs])
        G = np.concatenate([s.guides() for s in subs])
        d = self.device
        self.P = wp.array(P.reshape(-1, 3).astype(np.float32), dtype=wp.vec3, device=d)
        self.G = wp.array(G.reshape(-1, 3).astype(np.float32), dtype=wp.vec3, device=d)
        coff = np.cumsum([0] + [s.clumps.n for s in subs])
        self.clump_id = np.concatenate([np.where(s.clump_id >= 0, s.clump_id + coff[i], -1)
                                        for i, s in enumerate(subs)]).astype(np.int32)
        self.group = np.concatenate([np.full(s.roots.n, i, np.int8) for i, s in enumerate(subs)])
        self.cgroup = np.concatenate([np.full(s.clumps.n, i, np.int8) for i, s in enumerate(subs)])
        # classes: each group's own class list; the class id offset per group so by_class stays per group
        cls_names, coffs = [], []
        for s in subs:
            coffs.append(len(cls_names))
            cls_names += [f'{s.style["_group"]}:{c["name"]}' for c in s.style.get('classes', [{'name': 'all'}])]
        self.class_names = cls_names
        self.par = {k: np.concatenate([s.par[k] + (coffs[i] if k == 'cls' else 0) for i, s in enumerate(subs)])
                    for k in subs[0].par}
        self.guide_par = {k: np.concatenate([s.guide_par[k] for s in subs]) for k in subs[0].guide_par}
        self.flow = subs[0].flow
        self.surf = subs[0].surf
        self.bare_w = np.minimum.reduce([s.bare_w for s in subs])
        self.gates['groups'] = {s.style['_group']: s.gates for s in subs}
        self.gates['flow'] = subs[0].gates.get('flow')
        return self

    # ---------------------------------------------------------------------------------------------- stages
    def _t(self, name, t0):
        self.times[name] = round(time.time() - t0, 3)

    def mask_expr(self):
        st = self.style
        return {'mul': [st.get('domain', 1.0), {'not': st.get('bare', 0.0)}]}

    def build(self):
        st = self.style
        b = self.base
        if st.get('groups'):
            return self._build_groups()
        t0 = time.time()
        pv = Pts.vertices(b)
        bare_v = np.clip(self.fields.eval(st.get('bare', 0.0), pv), 0.0, 1.0)
        dom_v = np.clip(self.fields.eval(st.get('domain', 1.0), pv), 0.0, 1.0)
        nw = len(b.Vw)
        bw = np.zeros(nw)
        np.maximum.at(bw, b.wid, np.maximum(bare_v, 1.0 - dom_v))
        self.bare_w = bw
        self._t('masks', t0)
        # ------------------------------------------------------------------ flow
        t0 = time.time()
        designed, designed_w = [], []
        for z in st['flow'].get('designed', []):
            if 'mask' in z:                       # a zone written as a field mask (max over a welded vertex's copies)
                mv = np.clip(self.fields.eval(z['mask'], pv), 0.0, 1.0)
                mw = np.zeros(nw)
                np.maximum.at(mw, b.wid, mv)
                designed_w.append((z.get('name', 'mask'), mw))
                continue
            # (coat G6) 'at' may name a point between two sockets (flow.node_points): a crown whorl where no socket stands
            for p in node_points(b, z['at']):
                designed.append((z.get('name', z['at']), p, z['radius_mm'] * 1e-3))
        self.flow = Flow(b, self.fields).build(st['flow'], bare_v=bw, designed=designed, designed_w=designed_w)
        self.gates['flow'] = self.flow.gates
        self._t('flow', t0)
        self.surf = ST.Surface(b, self.flow.v, self.device)
        # ------------------------------------------------------------------ the coat's edge guard (coat round 3)
        t0 = time.time()
        self.guard = self._edge_guard()
        self._t('guard', t0)
        # ------------------------------------------------------------------ clumps (guides)
        t0 = time.time()
        cs = st['clumps']
        mexp = self.mask_expr()
        self.clumps = roots(b, self.fields, cs['density_cm2'], mexp, cs['d_max_cm2'], self.seed * 7 + 1,
                            oversample=cs.get('oversample', 3.0), poisson_alpha=cs.get('alpha', 0.75))
        cm = np.clip(self.fields.eval(mexp, self.clumps), 0, 1)
        keep = cm >= st.get('mask_cut', 0.1)
        self.clumps = _subset(self.clumps, keep)
        self._t('clumps', t0)
        # ------------------------------------------------------------------ strands
        t0 = time.time()
        sd = st['strands']
        self.roots = roots(b, self.fields, sd['density_cm2'], mexp, sd['d_max_cm2'], self.seed * 7 + 2,
                           oversample=1.0)
        rm = np.clip(self.fields.eval(mexp, self.roots), 0, 1)
        self.roots = _subset(self.roots, rm >= st.get('mask_cut', 0.1))
        self._t('roots', t0)
        t0 = time.time()
        self._grow()
        self._t('grow', t0)
        return self

    def _edge_guard(self):
        """(coat round 3) the coat-edge guard per welded vertex (strands.k_grow): the unit direction into the bare zone
        (minus the surface gradient of the distance to it, per face, area-weighted onto the vertices, in their tangent
        planes) x strength x smoothstep(band, 0, distance); None when the style asks for none"""
        eg = self.style.get('edge_guard')
        if not eg:
            self.gates['edge_guard'] = None
            return None
        b = self.base
        cut = float(eg.get('cut', self.style.get('mask_cut', 0.12)))
        d, mw = self.fields.edge_distance_w(self.mask_expr(), cut)
        dd = np.where(np.isfinite(d), d, 1.0)
        P = b.Vw[b.Fw]
        fn = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
        a2 = np.linalg.norm(fn, axis=1, keepdims=True)
        fn = fn / np.maximum(a2, 1e-30)
        f = dd[b.Fw]
        grad = np.zeros((len(P), 3))
        for i in range(3):
            e = P[:, (i + 2) % 3] - P[:, (i + 1) % 3]          # the edge opposite corner i
            grad += f[:, i:i + 1] * np.cross(fn, e)
        grad /= np.maximum(a2, 1e-30)                           # the distance's surface gradient (away from bare)
        acc = np.zeros((len(b.Vw), 3))
        for c in range(3):
            np.add.at(acc, b.Fw[:, c], -grad * (0.5 * a2))       # toward the bare zone, area-weighted
        acc -= b.Nw * np.sum(acc * b.Nw, axis=1, keepdims=True)
        ln = np.linalg.norm(acc, axis=1, keepdims=True)
        u = np.where(ln > 1e-12, acc / np.maximum(ln, 1e-30), 0.0)
        band = float(eg.get('band_mm', 8.0)) * 1e-3
        x = np.clip(dd / max(band, 1e-9), 0.0, 1.0)
        w = float(eg.get('strength', 1.0)) * (1.0 - x * x * (3.0 - 2.0 * x))
        w[mw < cut] = 0.0                                        # inside the bare zone nothing is grown anyway
        # (coat G6) "flow_parallel": p: the guard turns hairs along an edge the coat RUNS ALONG (an arm's flank, where the
        # flow is parallel to the edge and only gravity leans into the bare zone); where the coat FLOWS INTO its edge (the
        # mantle's back, combed down to its fur line) turning every arriving hair sideways laid them in a horizontal band
        # along the edge, the hard line and its straw fringe (the G5 check); there the style shortens the coat instead, so it
        # ends before the edge. w x (1 - max(u . flow, 0))^p; without the key, as before
        fp = eg.get('flow_parallel')
        into = None
        if fp is not None:
            into = np.clip(np.sum(u * self.flow.v, axis=1), 0.0, 1.0)
            w = w * (1.0 - into) ** float(fp)
        self.edge_dist_w = dd
        self.gates['edge_guard'] = dict(band_mm=band * 1e3, strength=float(eg.get('strength', 1.0)), cut=cut,
                                        vertices_in_band=int(((w > 1e-3)).sum()),
                                        bare_vertices=int((mw < cut).sum()))
        if into is not None:
            self.gates['edge_guard']['flow_parallel'] = float(fp)
        return (u * w[:, None]).astype(np.float32)

    def _trim_mask(self, P):
        """the coat mask at the closest skin point of every point of strands P (S, K, 3)"""
        S, K = P.shape[:2]
        face, bary, _ = ST.query(self.surf, P.reshape(-1, 3))
        return np.clip(self.fields.eval(self.mask_expr(), Pts(self.base, face, bary)), 0, 1).reshape(S, K)

    def _trim(self, Pw, L, K, op, label):
        """(coat round 3) the trim operator on a device array of strands (S * K): a strand reaching skin whose coat mask
        is under op.cut ends before it (at the crossing, interpolated between its two points' masks, less margin_mm,
        never under min_mm), resampled along its own path at equal arc length, then settled (the resample's chords can
        dip into a fold); op.rounds rounds (a settled tip can cross again); L (metres) is updated in place"""
        cut = float(op.get('cut', self.style.get('mask_cut', 0.12)))
        margin = float(op.get('margin_mm', 0.3)) * 1e-3
        min_len = float(op.get('min_mm', 0.6)) * 1e-3
        smargin = float(self.style.get('margin_mm', 0.2)) * 1e-3
        P = Pw.numpy().reshape(-1, K, 3).astype(np.float64)
        S = len(P)
        if S == 0:
            return Pw
        L0 = np.array(L, np.float64, copy=True)
        trimmed = np.zeros(S, bool)
        floor = np.zeros(S, bool)
        tq = np.linspace(0.0, 1.0, K)
        for _round in range(int(op.get('rounds', 3))):
            m = self._trim_mask(P)
            bad = m[:, 1:] < cut
            hit = np.nonzero(bad.any(1) & ~floor)[0]
            if len(hit) == 0:
                break
            seg = np.linalg.norm(np.diff(P[hit], axis=1), axis=2)
            arc = np.concatenate([np.zeros((len(hit), 1)), np.cumsum(seg, 1)], 1)
            k1 = np.argmax(bad[hit], axis=1) + 1
            rows = np.arange(len(hit))
            # the crossing on the segment (k1 - 1 -> k1): 24 sub-samples (the mask's edge is a few mm wide, a segment up
            # to ~5 mm: interpolating its two ends' masks puts the cut past the edge)
            nsub = 24
            fs = np.linspace(0.0, 1.0, nsub + 1)[1:]
            A, B = P[hit, k1 - 1], P[hit, k1]
            sub = (A[:, None, :] + (B - A)[:, None, :] * fs[None, :, None]).reshape(1, -1, 3)
            msub = self._trim_mask(sub).reshape(len(hit), nsub) < cut
            ks = np.where(msub.any(1), np.argmax(msub, axis=1), nsub - 1)
            fr = np.where(ks > 0, fs[np.maximum(ks - 1, 0)], 0.0)
            Lx = arc[rows, k1 - 1] + fr * seg[rows, k1 - 1] - margin
            Lnew = np.clip(Lx, min_len, arc[:, -1])
            for j, s in enumerate(hit):
                P[s] = np.stack([np.interp(tq * Lnew[j], arc[j], P[s, :, dd]) for dd in range(3)], 1)
            L[hit] = Lnew
            trimmed[hit] = True
            floor[hit[Lx <= min_len]] = True
            Pw = wp.array(P.reshape(-1, 3).astype(np.float32), dtype=wp.vec3, device=Pw.device)
            ST.settle(self.surf, Pw, L, K, smargin, 1)
            P = Pw.numpy().reshape(-1, K, 3).astype(np.float64)
        m = self._trim_mask(P)
        left = int((m[:, 1:] < cut).any(1).sum())
        self.gates.setdefault('trim', {})[label] = dict(
            cut=cut, strands=int(S), trimmed=int(trimmed.sum()), trimmed_pct=round(100.0 * trimmed.mean(), 2),
            removed_mm_p50_90=np.round(np.percentile((L0[trimmed] - L[trimmed]) * 1e3, [50, 90]), 2).tolist()
            if trimmed.any() else None,
            at_min_length=int(floor.sum()), rounds=_round + 1, still_reaching_bare=left)
        return wp.array(P.reshape(-1, 3).astype(np.float32), dtype=wp.vec3, device=Pw.device)

    def _params(self, pts, seed_ch, forced_class=None):
        """per-root class, length, lift, gravity, rnd from the style and stable hashes"""
        st = self.style
        n = pts.n
        key = (pts.tri, pts.slot)
        rnd = hkey(self.seed + seed_ch, *key, ch=10)
        classes = st.get('classes', [{'name': 'all', 'share': 1.0}])
        shares = np.cumsum([c['share'] for c in classes])
        shares /= shares[-1]
        u = hkey(self.seed + seed_ch, *key, ch=11)
        cls = np.searchsorted(shares, u, side='right') if forced_class is None else np.full(n, forced_class)
        cls = np.minimum(cls, len(classes) - 1)
        L = np.clip(self.fields.eval(st['length_mm'], pts), 0.0, None)
        jit = st.get('length_jitter', {'sigma': 0.18, 'clip': [0.65, 1.5]})
        L = L * lognormal_jitter(hkey(self.seed + seed_ch, *key, ch=12), hkey(self.seed + seed_ch, *key, ch=13),
                                 jit['sigma'], jit['clip'])
        lift = st.get('lift', {})
        th0 = np.full(n, float(lift.get('root_deg', 50.0)))
        th1 = np.full(n, float(lift.get('tip_deg', 80.0)))
        thp = np.full(n, float(lift.get('pow', 1.0)))
        grav = np.full(n, float(st.get('gravity', 0.0)))
        flex = np.full(n, 1.0)
        for ci, c in enumerate(classes):
            m = cls == ci
            L[m] *= c.get('length', 1.0)
            th0[m] += c.get('lift_root_deg', 0.0)
            th1[m] += c.get('lift_tip_deg', 0.0)
            grav[m] *= c.get('gravity', 1.0)
            flex[m] = c.get('flex', 1.0)
        # (coat G6) THE FUR LINE LIES DOWN (style "lift": {"edge": {"by": <field 0..1>, "root_deg", "tip_deg"}}): where the
        # field rises toward a bare edge the elevation (from the normal) runs to these, so a pelt's last hairs lie against
        # the skin the way they do at a real belly line, instead of standing out from it as a straw fringe (the G5 check:
        # the mantle seen from low behind). A style without it grows exactly as before
        edge = lift.get('edge')
        if edge:
            w = np.clip(self.fields.eval(edge['by'], pts), 0.0, 1.0)
            th0 = th0 + (float(edge.get('root_deg', 84.0)) - th0) * w
            th1 = th1 + (float(edge.get('tip_deg', 88.0)) - th1) * w
        # (coat G6) "gravity_edge": {"by": <field 0..1>, "scale": s}: gravity x lerp(1, s) by the field. Where a body curves
        # under toward a bare underside (the mantle's back below its tip) gravity's pull points OUT of the skin and stood
        # the fur line off it as a brim; near such a line the coat lies against the body instead
        ge = st.get('gravity_edge')
        if ge:
            w = np.clip(self.fields.eval(ge['by'], pts), 0.0, 1.0)
            grav = grav * (1.0 + (float(ge.get('scale', 0.2)) - 1.0) * w)
        jd = lift.get('jitter_deg', 0.0)
        th0 += (hkey(self.seed + seed_ch, *key, ch=14) - 0.5) * 2 * jd
        th1 += (hkey(self.seed + seed_ch, *key, ch=15) - 0.5) * 2 * jd
        th1 = np.minimum(th1, 89.0)
        return dict(rnd=rnd, cls=cls, L=L * 1e-3, th0=th0 * DEG, th1=th1 * DEG, thp=thp, grav=grav, flex=flex)

    # ---------------------------------------------------------------------------------------------- (B3) hang growth
    def _hang_par(self, pts, par):
        """(B3) a hang group's per-root attach length, offset (m) and root stiffness, from the growth block's fields"""
        gr = self.style['growth']
        att = np.clip(self.fields.eval(gr.get('attach_mm', 40.0), pts), 0.0, None) * 1e-3
        off = np.clip(self.fields.eval(gr.get('offset_mm', 3.0), pts), 0.0, None) * 1e-3
        s0, _sp = gr.get('stiff', [0.9, 1.5])
        stiff = np.full(pts.n, float(s0))
        return att.astype(np.float64), off.astype(np.float64), stiff

    def _hang(self, pts, par, K, gdir, margin):
        gr = self.style['growth']
        att, off, stiff = self._hang_par(pts, par)
        P = ST.hang(self.surf, self.sdf, pts.P, par['L'], att, off, par['th0'], stiff, gr.get('stiff', [0.9, 1.5])[1], K,
                    gdir, margin)
        rl = gr.get('relax', {})
        if rl.get('iters', 40) > 0:
            ST.hang_relax(self.sdf, P, par['L'], att, off, K, gdir, rl.get('gstep_mm', 1.0) * 1e-3, margin,
                          int(rl.get('iters', 40)), float(rl.get('bend', 0.15)))
        return P, att, off

    def _cut(self, Pw, L, K, op, att, off, margin, label, jitter=True, key=None):
        """(B3) the cut line (strands.cut_strands), resampled along each path, pushed back over the SDF floor"""
        P = Pw.numpy().reshape(-1, K, 3).astype(np.float64)
        S = len(P)
        if S == 0:
            return Pw
        c = self.fields._node_pos(op['center'])[0]
        jm = float(op.get('jitter_mm', 0.0)) * 1e-3
        if jitter and key is not None:
            jit = (hkey(self.seed + 700, *key, ch=1) - 0.5) * 2.0 * jm
        else:
            jit = np.full(S, -jm)                        # guides reach the lowest jittered line: never short of it
        L0 = np.array(L, np.float64, copy=True)
        Lnew, hit = ST.cut_strands(P, c, op['curve'], jit, op.get('mirror', True))
        Lnew = np.maximum(Lnew, float(op.get('min_mm', 5.0)) * 1e-3)
        P = ST.resample_paths(P, Lnew)
        L[:] = np.minimum(Lnew, L0)
        Pw = wp.array(P.reshape(-1, 3).astype(np.float32), dtype=wp.vec3, device=Pw.device)
        self._push(Pw, L, att, off, K, margin)
        self.gates.setdefault('cut', {})[label] = dict(
            strands=int(S), cut=int(hit.sum()), removed_mm_p50_90=np.round(np.percentile((L0[hit] - L[hit]) * 1e3, [50, 90]), 1).tolist()
            if hit.any() else None, length_mm_p10_50_90=np.round(np.percentile(L * 1e3, [10, 50, 90]), 1).tolist())
        return Pw

    def _tuck(self, Pw, L, K, op, att, off, margin):
        """(B3) the ends turn under: the last tuck_mm of each strand bends toward the head's vertical axis (through the
        op's centre) by amp_mm x s^2 (s 0 -> 1 over the tuck), then the SDF floor and the lengths"""
        P = Pw.numpy().reshape(-1, K, 3).astype(np.float64)
        if len(P) == 0:
            return Pw
        c = self.fields._node_pos(op['center'])[0]
        tuck = float(op.get('tuck_mm', 30.0)) * 1e-3
        amp = float(op.get('amp_mm', 8.0)) * 1e-3
        arc = np.linspace(0.0, 1.0, K)[None, :] * L[:, None]
        s = np.clip((arc - (L[:, None] - tuck)) / max(tuck, 1e-9), 0.0, 1.0)
        toward = c[None, None, :] - P
        toward[..., 1] = 0.0
        toward /= np.maximum(np.linalg.norm(toward, axis=2, keepdims=True), 1e-9)
        P = P + toward * (amp * s * s)[..., None]
        Pw = wp.array(P.reshape(-1, 3).astype(np.float32), dtype=wp.vec3, device=Pw.device)
        self._push(Pw, L, att, off, K, margin)
        return Pw

    def _fscale_of(self, off, n):
        """(B3c) the per-point floor scale of a strand set (keyed by its offset array: strands and guides each have
        one), ones until an op scales it"""
        tab = self.__dict__.setdefault('_fscale', {})
        if id(off) not in tab or len(tab[id(off)][1]) != n:
            tab[id(off)] = (off, np.ones(n, np.float64))
        return tab[id(off)][1]

    def _push(self, Pw, L, att, off, K, margin):
        """(B3c) ST.sdf_push with the strand set's per-point floor scale (none: as before)"""
        ent = self.__dict__.get('_fscale', {}).get(id(off))
        ST.sdf_push(self.sdf, Pw, L, att, off, K, margin, fscale=ent[1] if ent is not None else None)

    def _hug(self, Pw, L, K, op, att, off, margin):
        """(B3b) THE SIDES COMBED IN TO THE JAW: B3's hang strands left the skull at its widest (over the ears) and fell
        straight, standing 1-1.5 cm off the cheeks like a helmet (the lead's read of e03). Past each strand's attach
        length, every point's distance d to the head + neck SDF goes to gap + (d - gap) x (1 - strength x w): w ramps
        in below y_mm[0] to full at y_mm[1] (metres over the op centre's height, so the cheek and jaw take it, the skull
        keeps its volume) and over the first 25 mm past the attach; strength is per |azimuth| (by_az [[deg, s], ...],
        front 0, sides 90, nape 180). Monotone in d, so the layers keep their order (an outer strand stays outer). The
        point moves along the SDF gradient (central differences on the grid); three passes, then the SDF floor and the
        lengths (sdf_push).
        (B3c) op y_fade_mm [y2, y3]: the weight fades out again below y2 to none at y3 (an op over the ear only: the hang
        under the lobe keeps its fall and the tuck). op offset_scale: THE FLOOR UNDER IT. sdf_push holds every point of a
        strand at its offset (1.5 -> 13 mm) over the true SDF, along its whole length; over an ear standing 15 mm proud
        of the skull that floor alone put the side 15-17 mm out (the earmuffs), and any hug was undone by the push after
        it (c01 / c02 moved nothing over the ear). Each POINT's floor is scaled by 1 - (1 - offset_scale) x its weight
        there (the op's y and azimuth weights at the point; a per-point scale kept per strand set, self._fscale, that
        every later push reads), so the floor changes along the strand: over the ear, not over the temple the same
        strands cross first (c03 scaled the whole strand). Monotone in the offset, the layers keep their order"""
        P = Pw.numpy().reshape(-1, K, 3).astype(np.float64)
        if len(P) == 0:
            return Pw
        c = self.fields._node_pos(op['center'])[0]
        gap = float(op.get('gap_mm', 3.0)) * 1e-3
        y0, y1 = [float(v) * 1e-3 for v in op.get('y_mm', [-40.0, -75.0])]
        tab = np.asarray(op.get('by_az', [[0, 0.3], [60, 0.85], [120, 0.85], [180, 0.5]]), np.float64)
        arc = np.linspace(0.0, 1.0, K)[None, :] * L[:, None]
        past = np.clip((arc - np.asarray(att, np.float64)[:, None]) / 0.025, 0.0, 1.0)
        yf = [float(v) * 1e-3 for v in op['y_fade_mm']] if op.get('y_fade_mm') else None
        S = P.shape[0]
        sdf = self.sdf

        def zone_w(X):
            rel = X - c[None, :]
            az = np.degrees(np.abs(np.arctan2(rel[:, 0], rel[:, 2])))
            t = np.clip((rel[:, 1] - y0) / (y1 - y0), 0.0, 1.0)
            wy = t * t * (3 - 2 * t)
            if yf is not None:
                tf = np.clip((rel[:, 1] - yf[0]) / (yf[1] - yf[0]), 0.0, 1.0)
                wy = wy * (1.0 - tf * tf * (3 - 2 * tf))
            return wy * np.interp(az, tab[:, 0], tab[:, 1])
        if op.get('offset_scale') is not None:
            wpt = np.clip(zone_w(P.reshape(-1, 3)), 0.0, 1.0)
            fs = self._fscale_of(off, S * K)
            fs *= 1.0 - (1.0 - float(op['offset_scale'])) * wpt
        eps = sdf.h
        for _ in range(3):
            X = P.reshape(-1, 3)
            d = sdf.sample(X)
            g = np.stack([(sdf.sample(X + e) - sdf.sample(X - e)) / (2 * eps)
                          for e in np.eye(3) * eps], 1)
            g /= np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-9)
            w = zone_w(X) * past.reshape(-1)
            dn = np.where(d > gap, gap + (d - gap) * (1.0 - w), d)
            P = (X - g * (d - dn)[:, None]).reshape(S, K, 3)
        Pw = wp.array(P.reshape(-1, 3).astype(np.float32), dtype=wp.vec3, device=Pw.device)
        self._push(Pw, L, att, off, K, margin)
        return Pw

    def _clear(self, Pw, L, K, op, att, off, margin):
        """(B3b) THE FACE KEPT CLEAR: a strand that enters a box (op box_lo / box_hi, metres, world, grown by margin_mm
        sideways and forward; the build's face_clear gate box: the eyes, nose and mouth) is TRIMMED to end margin_mm before
        its first point in it, resampled along its own path (as the cut). B3 left 4 strays there (6 in B3b's first
        regrow): hang strands rooted at the part just behind the fringe that fall forward over it. A sideways push did not
        hold (the settle's length restore pulled them back) and moved the fringe's own ends; a trim of a handful of strands
        among ~18k is invisible, and the guides are trimmed alike so no card runs there"""
        P = Pw.numpy().reshape(-1, K, 3).astype(np.float64)
        S = len(P)
        if S == 0:
            return Pw
        lo = np.asarray(op['box_lo'], np.float64)
        hi = np.asarray(op['box_hi'], np.float64)
        mg = float(op.get('margin_mm', 6.0)) * 1e-3
        xw = max(abs(lo[0]), abs(hi[0])) + mg
        bad = (np.abs(P[..., 0]) < xw) & (P[..., 1] > lo[1]) & (P[..., 1] < hi[1]) & (P[..., 2] > lo[2] - mg)
        hit = bad.any(1)
        if hit.any():
            seg = np.linalg.norm(np.diff(P, axis=1), axis=2)
            arc = np.concatenate([np.zeros((S, 1)), np.cumsum(seg, 1)], 1)
            first = np.argmax(bad, axis=1)
            L0 = np.array(L, np.float64, copy=True)
            Lnew = L0.copy()
            Lnew[hit] = np.maximum(arc[hit, first[hit]] - mg, float(op.get('min_mm', 20.0)) * 1e-3)
            P = ST.resample_paths(P, Lnew)
            L[:] = np.minimum(Lnew, L0)
        self.gates.setdefault('clear', {})[op.get('name', 'face')] = int(hit.sum())
        Pw = wp.array(P.reshape(-1, 3).astype(np.float32), dtype=wp.vec3, device=Pw.device)
        self._push(Pw, L, att, off, K, margin)
        return Pw

    def _anchor(self, Pw, L, K, op, label):
        """(B3, H3) the anchor: every strand's last `blend` of its length pulled to a point (or the nearest point of a
        ring of radius ring_mm about it, in the plane normal to `axis`), smooth in; returns the strands and records the
        ends' distance to the ring"""
        P = Pw.numpy().reshape(-1, K, 3).astype(np.float64)
        if len(P) == 0:
            return Pw
        c = node_points(self.base, op['at'])[0]
        ax = np.asarray(op.get('axis', [0.0, 0.0, -1.0]), np.float64)
        ax /= np.linalg.norm(ax)
        ring = float(op.get('ring_mm', 0.0)) * 1e-3
        blend = float(op.get('blend', 0.3))
        tip = P[:, -1]
        rel = tip - c
        rel -= ax[None, :] * (rel @ ax)[:, None]
        rn = np.linalg.norm(rel, axis=1, keepdims=True)
        target = c[None, :] + np.where(rn > 1e-9, rel / np.maximum(rn, 1e-12), 0.0) * ring
        t = np.linspace(0.0, 1.0, K)
        w = np.clip((t - (1.0 - blend)) / max(blend, 1e-6), 0.0, 1.0)
        w = w * w * (3.0 - 2.0 * w)
        P = P + (target - tip)[:, None, :] * w[None, :, None]
        seg = np.linalg.norm(np.diff(P, axis=1), axis=2)
        L[:] = seg.sum(1)
        end = np.linalg.norm(P[:, -1] - target, axis=1)
        self.gates.setdefault('anchor', {})[label] = dict(strands=int(len(P)), ring_mm=ring * 1e3,
                                                          end_off_ring_mm_max=round(float(end.max()) * 1e3, 3))
        return wp.array(P.reshape(-1, 3).astype(np.float32), dtype=wp.vec3, device=Pw.device)

    def _grow(self):
        st = self.style
        if st.get('growth', {}).get('mode') == 'hang':
            return self._grow_hang()
        K = int(st['strands']['points'])
        gdir = st.get('gravity_dir', [0.0, -1.0, 0.0])
        margin = st.get('margin_mm', 0.2) * 1e-3
        # guides: one per clump centre, class forced to the style's guide class (default: the first)
        gp = self._params(self.clumps, 100, forced_class=st['clumps'].get('guide_class', 0))
        self.guide_par = gp
        guard = getattr(self, 'guard', None)
        G = ST.grow(self.surf, self.clumps.P, gp['L'], gp['th0'], gp['th1'], gp['thp'], gp['grav'], K, gdir, margin,
                    guard=guard)
        ST.settle(self.surf, G, gp['L'], K, margin)
        trim_op = next((o for o in st.get('operators', []) if o['op'] == 'trim'), None)
        sp = self._params(self.roots, 200)
        self.par = sp
        from scipy.spatial import cKDTree
        if self.clumps.n:
            _, cid = cKDTree(self.clumps.P).query(self.roots.P)
        else:
            cid = -np.ones(self.roots.n, np.int64)
        self.clump_id = cid.astype(np.int32)
        P = ST.grow(self.surf, self.roots.P, sp['L'], sp['th0'], sp['th1'], sp['thp'], sp['grav'], K, gdir, margin,
                    guard=guard)
        classes = st.get('classes', [{'name': 'all', 'share': 1.0}])
        cls_clump = np.array([c.get('clump', 1.0) for c in classes])[sp['cls']]
        key = (self.roots.tri, self.roots.slot)
        for op in st.get('operators', []):
            kind = op['op']
            if kind == 'clump' and self.clumps.n:
                s0, s1 = op.get('strength', [0.3, 0.7])
                ckey = (self.clumps.tri, self.clumps.slot)
                cstr = s0 + (s1 - s0) * hkey(self.seed + 300, *ckey, ch=1)
                strength = cstr[self.clump_id] * cls_clump
                ST.clump(P, G, self.clump_id, strength, op.get('profile', 1.5), K)
            elif kind == 'wave':
                a0, a1 = op.get('amp_mm', [0.5, 1.0])
                f0, f1 = op.get('freq', [0.5, 1.5])
                amp = (a0 + (a1 - a0) * hkey(self.seed + 400, *key, ch=1)) * 1e-3
                amp = amp * np.array([c.get('wave', 1.0) for c in classes])[sp['cls']]
                fr = f0 + (f1 - f0) * hkey(self.seed + 400, *key, ch=2)
                ph = 2 * np.pi * hkey(self.seed + 400, *key, ch=3)
                P = ST.wave(self.surf, P, amp, fr, ph, K)
            elif kind == 'frizz':
                amp = np.full(self.roots.n, op.get('amp_mm', 0.2) * 1e-3)
                ST.frizz(P, amp, self.seed + 500, K)
            elif kind == 'settle':
                ST.settle(self.surf, P, sp['L'], K, op.get('margin_mm', st.get('margin_mm', 0.2)) * 1e-3,
                          op.get('iters', 2))
            elif kind == 'trim':
                P = self._trim(P, sp['L'], K, op, 'strands')
            else:
                raise ValueError(f'unknown operator {kind}')
        # (coat round 3) the guides end before bare skin too (a card's spine is its guide), trimmed only now: the clump
        # pull above wants each guide whole (a strand pulled toward a guide cut short would crumple onto its root)
        if trim_op is not None:
            G = self._trim(G, gp['L'], K, trim_op, 'guides')
        self.G = G
        self.P = P
        self.K = K

    def _grow_hang(self):
        """(B3) a hang group: guides and strands by strands.k_hang + relax against the SDF, then the operators (clump,
        wave, frizz, settle = the SDF push, cut, tuck, anchor)"""
        st = self.style
        assert self.sdf is not None, 'a hang group needs the style\'s "sdf" block'
        K = int(st['strands']['points'])
        gdir = st.get('gravity_dir', [0.0, -1.0, 0.0])
        margin = st.get('margin_mm', 1.0) * 1e-3
        gp = self._params(self.clumps, 100, forced_class=st['clumps'].get('guide_class', 0))
        self.guide_par = gp
        G, gatt, goff = self._hang(self.clumps, gp, K, gdir, margin)
        sp = self._params(self.roots, 200)
        self.par = sp
        from scipy.spatial import cKDTree
        if self.clumps.n:
            _, cid = cKDTree(self.clumps.P).query(self.roots.P)
        else:
            cid = -np.ones(self.roots.n, np.int64)
        self.clump_id = cid.astype(np.int32)
        P, att, off = self._hang(self.roots, sp, K, gdir, margin)
        self.hang_att, self.hang_off = att, off
        classes = st.get('classes', [{'name': 'all', 'share': 1.0}])
        cls_clump = np.array([c.get('clump', 1.0) for c in classes])[sp['cls']]
        key = (self.roots.tri, self.roots.slot)
        gkey = (self.clumps.tri, self.clumps.slot)
        for op in st.get('operators', []):
            kind = op['op']
            if kind == 'clump' and self.clumps.n:
                s0, s1 = op.get('strength', [0.3, 0.7])
                cstr = s0 + (s1 - s0) * hkey(self.seed + 300, *gkey, ch=1)
                ST.clump(P, G, self.clump_id, cstr[self.clump_id] * cls_clump, op.get('profile', 1.5), K)
                self._push(P, sp['L'], att, off, K, margin)
            elif kind == 'wave':
                a0, a1 = op.get('amp_mm', [0.5, 1.0])
                f0, f1 = op.get('freq', [0.5, 1.5])
                amp = (a0 + (a1 - a0) * hkey(self.seed + 400, *key, ch=1)) * 1e-3
                amp = amp * np.array([c.get('wave', 1.0) for c in classes])[sp['cls']]
                fr = f0 + (f1 - f0) * hkey(self.seed + 400, *key, ch=2)
                ph = 2 * np.pi * hkey(self.seed + 400, *key, ch=3)
                P = ST.wave(self.surf, P, amp, fr, ph, K)
                self._push(P, sp['L'], att, off, K, margin)
            elif kind == 'frizz':
                ST.frizz(P, np.full(self.roots.n, op.get('amp_mm', 0.2) * 1e-3), self.seed + 500, K)
                self._push(P, sp['L'], att, off, K, margin)
            elif kind == 'settle':
                self._push(P, sp['L'], att, off, K, margin)
            elif kind == 'cut':
                P = self._cut(P, sp['L'], K, op, att, off, margin, 'strands', key=key)
                G = self._cut(G, gp['L'], K, op, gatt, goff, margin, 'guides', jitter=False)
            elif kind == 'tuck':
                P = self._tuck(P, sp['L'], K, op, att, off, margin)
                G = self._tuck(G, gp['L'], K, op, gatt, goff, margin)
            elif kind == 'hug':
                P = self._hug(P, sp['L'], K, op, att, off, margin)
                G = self._hug(G, gp['L'], K, op, gatt, goff, margin)
            elif kind == 'clear':
                P = self._clear(P, sp['L'], K, op, att, off, margin)
                G = self._clear(G, gp['L'], K, op, gatt, goff, margin)
            elif kind == 'anchor':
                P = self._anchor(P, sp['L'], K, op, 'strands')
                G = self._anchor(G, gp['L'], K, op, 'guides')
            else:
                raise ValueError(f'unknown operator {kind} (hang group)')
        self.G = G
        self.P = P
        self.K = K

    # ---------------------------------------------------------------------------------------------- arrays
    def points(self):
        return self.P.numpy().reshape(-1, self.K, 3).astype(np.float64)

    def guides(self):
        return self.G.numpy().reshape(-1, self.K, 3).astype(np.float64)

    # ---------------------------------------------------------------------------------------------- gates
    def strand_gates(self):
        st = self.style
        if getattr(self, 'subs', None):
            return self._group_gates()
        P = self.points()
        seg = np.linalg.norm(np.diff(P, axis=1), axis=2)
        arc = seg.sum(1)
        chord = np.linalg.norm(P[:, -1] - P[:, 0], axis=1)
        curl = arc / np.maximum(chord, 1e-9)
        H, _ = ST.heights(self.surf, self.P)
        H = H.reshape(-1, self.K)
        b = self.base
        rm = np.clip(self.fields.eval(self.mask_expr(), self.roots), 0, 1)
        coated = self._coated_area()
        classes = st.get('classes', [{'name': 'all', 'share': 1.0}])
        out = dict(strands=int(self.roots.n), clumps=int(self.clumps.n), points_per_strand=self.K,
                   coated_area_m2=round(coated, 4),
                   strands_per_cm2=round(self.roots.n / max(coated * 1e4, 1e-9), 2),
                   clumps_per_cm2=round(self.clumps.n / max(coated * 1e4, 1e-9), 3),
                   roots_outside_domain=int((rm < st.get('mask_cut', 0.1)).sum()),
                   points_inside=int((H[:, 1:] < -1e-6).sum()), min_height_mm=round(float(H[:, 1:].min()) * 1e3, 4),
                   tip_height_mm_p10_50_90=np.round(np.percentile(H[:, -1], [10, 50, 90]) * 1e3, 2).tolist(),
                   by_class={})
        for ci, c in enumerate(classes):
            m = self.par['cls'] == ci
            if not m.any():
                continue
            out['by_class'][c['name']] = dict(
                n=int(m.sum()), length_mm_p10_50_90=np.round(np.percentile(arc[m] * 1e3, [10, 50, 90]), 2).tolist(),
                curl_p50_p90=np.round(np.percentile(curl[m], [50, 90]), 3).tolist(),
                tip_elev_deg_p50=round(float(np.degrees(np.arcsin(np.clip(np.median(H[m, -1] / np.maximum(arc[m], 1e-9)), -1, 1)))), 1))
        tg = st.get('targets', {})
        checks = []
        for cname, t in tg.get('by_class', {}).items():
            got = out['by_class'].get(cname)
            if not got:
                continue
            if 'length_mm_p50' in t:
                lo, hi = t['length_mm_p50']
                checks.append((f'{cname} length p50 in [{lo}, {hi}] mm', lo <= got['length_mm_p10_50_90'][1] <= hi))
            if 'curl_p50_max' in t:
                checks.append((f'{cname} curl p50 <= {t["curl_p50_max"]}', got['curl_p50_p90'][0] <= t['curl_p50_max']))
        checks.append(('no root outside the domain', out['roots_outside_domain'] == 0))
        if self.sdf is not None and st.get('growth', {}).get('mode') == 'hang':
            # (B3) a hang group is gated against the SDF (the closest-face height reads a strand beside the jaw or an
            # ear against the wrong face): no point inside, and the floor's margin
            out.update(self.sdf_gate(P))
            checks.append(('no point inside the head + neck + shoulder SDF', out['sdf']['points_inside'] == 0))
        else:
            checks.append(('no point inside the base', out['points_inside'] == 0))
        if 'strands_per_cm2' in tg:
            lo, hi = tg['strands_per_cm2']
            checks.append((f'strand density in [{lo}, {hi}] / cm2', lo <= out['strands_per_cm2'] <= hi))
        out['checks'] = [dict(gate=g, ok=bool(ok)) for g, ok in checks]
        self.gates['strands'] = out
        return out

    def sdf_gate(self, P):
        """(B3) every point past the root against the SDF: inside (< 0), under 0.5 mm, the minimum (mm)"""
        ph = self.sdf.sample(P[:, 1:].reshape(-1, 3))
        return dict(sdf=dict(points=int(ph.size), points_inside=int((ph < 0).sum()),
                             under_0p5mm=int((ph < 0.5e-3).sum()), min_mm=round(float(ph.min()) * 1e3, 3)))

    def _group_gates(self):
        """(B3) a grouped style's gates: each group's own (grown and gated as a groom), plus the union's"""
        out = dict(groups={}, strands=int(self.roots.n), clumps=int(self.clumps.n), points_per_strand=self.K)
        ok = True
        for s in self.subs:
            g = s.gates.get('strands') or s.strand_gates()
            out['groups'][s.style['_group']] = g
            ok &= all(c['ok'] for c in g.get('checks', []))
        if self.sdf is not None:
            out.update(self.sdf_gate(self.points()))
        out['checks'] = [dict(gate='every group\'s checks', ok=bool(ok))]
        if self.sdf is not None:
            out['checks'].append(dict(gate='no point inside the SDF (all groups)', ok=out['sdf']['points_inside'] == 0))
        self.gates['strands'] = out
        return out

    def _coated_area(self):
        """the skin area where the mask (domain x not bare) is at least 1/2, from the welded vertex masks"""
        b = self.base
        m = (1.0 - self.bare_w[b.Fw]).mean(1) >= 0.5
        return float(b.area[m].sum())

    # ---------------------------------------------------------------------------------------------- io
    def save(self, path):
        P = self.points().astype(np.float32)
        np.savez_compressed(
            path, style=json.dumps(self.style), base_sha1=self.base.sha1, K=self.K,
            tri=self.roots.tri.astype(np.int32), bary=self.roots.bary.astype(np.float32),
            slot=self.roots.slot.astype(np.int32), points=P, cls=self.par['cls'].astype(np.int8),
            clump=self.clump_id, rnd=self.par['rnd'].astype(np.float32), length=self.par['L'].astype(np.float32),
            flex=self.par['flex'].astype(np.float32),
            ctri=self.clumps.tri.astype(np.int32), cbary=self.clumps.bary.astype(np.float32),
            cslot=self.clumps.slot.astype(np.int32), guides=self.guides().astype(np.float32),
            glength=self.guide_par['L'].astype(np.float32), grnd=self.guide_par['rnd'].astype(np.float32),
            flow=self.flow.v.astype(np.float32), bare_w=self.bare_w.astype(np.float32),
            gates=json.dumps(self.gates, default=float), times=json.dumps(self.times),
            # (B3) each strand's and clump's group (0 for a style without groups), the group names, the SDF's key
            group=getattr(self, 'group', np.zeros(self.roots.n, np.int8)),
            cgroup=getattr(self, 'cgroup', np.zeros(self.clumps.n, np.int8)),
            groups=json.dumps(getattr(self, 'groups', [self.style.get('name', 'coat')])),
            sdf_key=self.sdf.key if self.sdf is not None else '')


def _subset(pts, keep):
    out = Pts(pts.base, pts.tri[keep], pts.bary[keep])
    out.slot = pts.slot[keep]
    out.density = pts.density[keep]
    return out
