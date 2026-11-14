"""FIELDS: the small expression language a coat spec writes its masks and maps in, evaluated on any base.

Every term reads only what any forge glb carries (base.py), so a style is data and a second base needs only its own
spec. An expression is a number, a named reference, a leaf or a combinator (JSON):

  leaves
    {"tex": "masks.g"}                     the base's map (slot.channel: base / normal / orm / masks / display /
                                           growth, channel r g b a) at the point's uv in its own set; 0 in a set
                                           without that map. "sets": [...] limits it to some sets
    {"joints": "^funnel_"}                 the sum of the skin weights of the joints whose names match
    {"near": "^socket_eye_[LR]$", "r0_mm": 20, "r1_mm": 35}
                                           1 within r0 of the nearest matching node (bind pose), 0 beyond r1, smooth;
                                           (coat G6) "near" may also be a point between two nodes, {"between": [a, b],
                                           "t": 0.4} (+ "offset_mm"), as flow's sources and whorls take it
    {"chain_s": "^arm"}                    the position along the matching joint chains, 0 at the chain's root, 1 at its
                                           tip (the skin-weighted mean of the joints' s); 0 off every chain
    {"chain_r_mm": "^arm"}                 the chains' radius table (glb extras) at that s, in mm; "off" (default 0)
                                           elsewhere
    {"normal": [0, 1, 0]}                  dot(the surface normal, the axis), bind pose
    {"set": "arms"}                        1 on the faces of that texture set
    {"height_mm": [0, 1, 0]}               the point's height along the axis above the base's lowest point, mm
    {"edge_mm": <expr>, "cut": 0.12}       (coat round 3) the distance over the skin, in mm, from the point to where
                                           <expr> falls under cut (0 inside that zone): a coat's distance from its
                                           bare edge, so a style can thin and shorten its pelt toward a bare patch
                                           the way a real pelt does (Dijkstra over the welded low's edges, seeded at
                                           each edge's crossing of the cut, blended at the point)
    (B3, the hair forge core) THE HEAD'S SPHERICAL FRAME: a centre (a node regex or {"between": [a, b], "t"} with
    "offset_mm", as "near" takes it), +Y up, the base's +Z the front; azimuth about +Y from the front (0 front, +90 the
    base's +X side, 180 the back: written for |az| when the style says "mirror": true, the default), elevation from the
    centre's horizontal plane:
    {"sph": "az" | "el" | "r_mm", "center": c}   the point's azimuth / elevation (degrees) / distance (mm)
    {"hairline": {"center": c, "curve": [[az, el], ...], "fade_mm": [lo, hi], "mirror": true}}
                                           the SCALP: 1 above the hairline, 0 below, smooth over fade_mm measured along
                                           the head (the elevation over the curve x the radius): the curve is the
                                           hairline's elevation per azimuth (piecewise linear, |az| when mirrored), so a
                                           frontal M, recessed temples, sideburns growing down and the nape are table rows
                                           (HAIR_FUR H1; HS §2.2's root maps)
    {"band": {"center": c, "az": [a0, a1], "el": [e0, e1], "soft_deg": s, "mirror": true}}
                                           1 inside an azimuth x elevation window of the head frame (soft by s degrees):
                                           a group's domain (the fringe's front patch, the hang group's sides and back)
  combinators
    {"max": [...]}, {"min": [...]}, {"add": [...]}, {"mul": [...]}, {"sub": [a, b]}, {"not": e} (1 - e)
    {"smooth": [lo, hi], "of": e}          smoothstep (lo > hi gives the falling edge)
    {"clamp": [lo, hi], "of": e}, {"lerp": [a, b], "by": e}, {"pow": p, "of": e}, {"scale": k, "of": e}
    {"ref": "name"}                        a field named in the spec's "fields"

Points are evaluated as (triangle, barycentrics) on the base's low (Pts below); vertex fields are blended by
barycentrics, maps are sampled at the point's own uv (so a 2 mm sucker rim survives, which the 6 mm low cannot hold).
"""
import re

import numpy as np

_CH = {'r': 0, 'g': 1, 'b': 2, 'a': 3}


def smoothstep(lo, hi, x):
    if hi == lo:
        return (x >= lo).astype(np.float64)
    t = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class Pts:
    """surface points on a base: (tri, bary) and what the fields read there"""

    def __init__(self, base, tri, bary):
        self.base = base
        self.tri = np.asarray(tri, np.int64)
        self.bary = np.asarray(bary, np.float64)
        self.P, self.N, self.UV, self.set = base.tri_points(self.tri, self.bary)
        self.n = len(self.tri)

    @classmethod
    def vertices(cls, base):
        """one point per (unwelded) vertex: the first face that uses it, its corner's one-hot barycentrics"""
        nv = len(base.V)
        tri = np.full(nv, -1, np.int64)
        corner = np.zeros(nv, np.int64)
        for c in range(3):
            v = base.F[:, c]
            unset = tri[v] < 0
            tri[v[unset]] = np.nonzero(unset)[0]
            corner[v[unset]] = c
        bary = np.zeros((nv, 3))
        bary[np.arange(nv), corner] = 1.0
        return cls(base, tri, bary)

    def vblend(self, per_vertex):
        """a per-vertex quantity (nv,) or (nv, k) blended at the points by barycentrics"""
        a = np.asarray(per_vertex, np.float64)
        Fv = self.base.F[self.tri]
        if a.ndim == 1:
            return np.einsum('nk,nk->n', self.bary, a[Fv])
        return np.einsum('nk,nkd->nd', self.bary, a[Fv])


class Fields:
    """evaluates spec expressions on a base (with per-base caches of the vertex quantities)"""

    def __init__(self, base, named=None):
        self.base = base
        self.named = dict(named or {})
        self._cache = {}

    # -------------------------------------------------------------------------------------------- vertex caches
    def _joint_w(self, pattern):
        key = ('jw', pattern)
        if key not in self._cache:
            ids = self.base.joint_ids(pattern)
            self._cache[key] = self.base.joint_weight_field(ids)
        return self._cache[key]

    def _chain_sr(self, pattern):
        """per vertex: (s, radius_mm, weight on the chains) from the skin weights of the matching chains' joints"""
        key = ('chain', pattern)
        if key in self._cache:
            return self._cache[key]
        b = self.base
        rx = re.compile(pattern)
        nj = len(b.joint_names)
        js = np.zeros(nj)
        jr = np.zeros(nj)
        jm = np.zeros(nj, bool)
        for c in b.chains:
            if not rx.search(c['name']):
                continue
            for k, jid in enumerate(c['joints']):
                js[jid] = c['s'][k]
                jr[jid] = (c['radius'][k] * 1000.0) if c['radius'] is not None else 0.0
                jm[jid] = True
        W = np.where(jm[b.J], b.W, 0.0)
        wsum = W.sum(1)
        s = (W * js[b.J]).sum(1) / np.maximum(wsum, 1e-12)
        r = (W * jr[b.J]).sum(1) / np.maximum(wsum, 1e-12)
        self._cache[key] = (s, r, wsum)
        return self._cache[key]

    def _node_pos(self, pattern):
        b = self.base
        if isinstance(pattern, dict):        # (coat G6) a point between two nodes, as flow.node_points reads it
            from .flow import node_points
            return node_points(b, pattern)
        ids = b.node_ids(pattern)
        assert ids, f'no node matches {pattern!r}'
        return b.node_world[ids][:, :3, 3]

    def edge_distance_w(self, expr, cut=0.12):
        """(coat round 3) per WELDED vertex: the surface distance (metres) to where expr falls under cut, and expr itself
        (the minimum over a welded vertex's copies). Seeds: every vertex under the cut at 0, every vertex above it on an
        edge that crosses the cut at the crossing's distance along that edge; then Dijkstra over the welded edges"""
        import json
        key = ('edge', json.dumps(expr, sort_keys=True), float(cut))
        if key in self._cache:
            return self._cache[key]
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import dijkstra
        b = self.base
        pv = Pts.vertices(b)
        mv = np.clip(self.eval(expr, pv), 0.0, 1.0)
        nw = len(b.Vw)
        mw = np.ones(nw)
        np.minimum.at(mw, b.wid, mv)
        E = np.concatenate([b.Fw[:, [0, 1]], b.Fw[:, [1, 2]], b.Fw[:, [2, 0]]])
        E = np.unique(np.sort(E, axis=1), axis=0)
        L = np.linalg.norm(b.Vw[E[:, 0]] - b.Vw[E[:, 1]], axis=1)
        seed = np.full(nw, np.inf)
        seed[mw < cut] = 0.0
        a, c = mw[E[:, 0]], mw[E[:, 1]]
        cross = (a >= cut) != (c >= cut)
        for i, j, li, ai, cj in zip(E[cross, 0], E[cross, 1], L[cross], a[cross], c[cross]):
            if ai >= cut:                                   # i is the coat side: its distance to the crossing
                seed[i] = min(seed[i], li * (ai - cut) / max(ai - cj, 1e-9))
            else:
                seed[j] = min(seed[j], li * (cj - cut) / max(cj - ai, 1e-9))
        src = np.nonzero(np.isfinite(seed))[0]
        if len(src) == 0:
            out = (np.full(nw, np.inf), mw)
            self._cache[key] = out
            return out
        # a virtual source (node nw) joined to every seed by its seed distance (a tiny floor: csgraph drops zero weights)
        rows = np.concatenate([E[:, 0], E[:, 1], np.full(len(src), nw)])
        cols = np.concatenate([E[:, 1], E[:, 0], src])
        w = np.concatenate([L, L, np.maximum(seed[src], 1e-12)])
        G = coo_matrix((w, (rows, cols)), shape=(nw + 1, nw + 1)).tocsr()
        d = dijkstra(G, directed=True, indices=nw)[:nw]
        out = (d, mw)
        self._cache[key] = out
        return out

    # -------------------------------------------------------------------------------------------- evaluation
    def eval(self, e, pts):
        if isinstance(e, (int, float)):
            return np.full(pts.n, float(e))
        if isinstance(e, str):
            return self.eval({'ref': e}, pts)
        assert isinstance(e, dict), e
        if 'ref' in e:
            return self.eval(self.named[e['ref']], pts)
        if 'tex' in e:
            slot, ch = e['tex'].split('.')
            out = np.zeros(pts.n)
            for k, s in enumerate(self.base.sets):
                if 'sets' in e and s not in e['sets']:
                    continue
                m = pts.set == k
                if not m.any() or self.base.tex_index(s, slot) is None:
                    continue
                v = self.base.sample(s, slot, pts.UV[m])
                out[m] = v[:, min(_CH[ch], v.shape[1] - 1)]
            return out
        if 'joints' in e:
            return np.clip(pts.vblend(self._joint_w(e['joints'])), 0.0, 1.0)
        if 'near' in e:
            C = self._node_pos(e['near'])
            d = np.min(np.linalg.norm(pts.P[:, None, :] - C[None, :, :], axis=2), axis=1) * 1000.0
            return 1.0 - smoothstep(e.get('r0_mm', 0.0), e['r1_mm'], d)
        if 'chain_s' in e:
            s, _, w = self._chain_sr(e['chain_s'])
            return pts.vblend(np.where(w > 1e-6, s, e.get('off', 0.0)))
        if 'chain_r_mm' in e:
            _, r, w = self._chain_sr(e['chain_r_mm'])
            return pts.vblend(np.where(w > 1e-6, r, e.get('off', 0.0)))
        if 'normal' in e:
            a = np.asarray(e['normal'], np.float64)
            return pts.N @ (a / np.linalg.norm(a))
        if 'set' in e:
            return (pts.set == self.base.sets.index(e['set'])).astype(np.float64)
        if 'height_mm' in e:
            a = np.asarray(e['height_mm'], np.float64)
            a = a / np.linalg.norm(a)
            return (pts.P @ a - (self.base.V @ a).min()) * 1000.0
        if 'edge_mm' in e:
            d, _ = self.edge_distance_w(e['edge_mm'], e.get('cut', 0.12))
            dv = d[self.base.wid]                            # per unwelded vertex
            return np.minimum(pts.vblend(np.where(np.isfinite(dv), dv, 1.0)), 1.0) * 1000.0
        if 'sph' in e or 'hairline' in e or 'band' in e:
            return self._head_frame(e, pts)
        if 'max' in e:
            return np.max([self.eval(x, pts) for x in e['max']], axis=0)
        if 'min' in e:
            return np.min([self.eval(x, pts) for x in e['min']], axis=0)
        if 'add' in e:
            return np.sum([self.eval(x, pts) for x in e['add']], axis=0)
        if 'mul' in e:
            return np.prod([self.eval(x, pts) for x in e['mul']], axis=0)
        if 'sub' in e:
            a, b = e['sub']
            return self.eval(a, pts) - self.eval(b, pts)
        if 'not' in e:
            return 1.0 - self.eval(e['not'], pts)
        if 'smooth' in e:
            lo, hi = e['smooth']
            x = self.eval(e['of'], pts)
            return smoothstep(lo, hi, x) if lo <= hi else 1.0 - smoothstep(hi, lo, x)
        if 'clamp' in e:
            lo, hi = e['clamp']
            return np.clip(self.eval(e['of'], pts), lo, hi)
        if 'lerp' in e:
            a, b = e['lerp']
            t = self.eval(e['by'], pts)
            return self.eval(a, pts) * (1.0 - t) + self.eval(b, pts) * t
        if 'pow' in e:
            return np.maximum(self.eval(e['of'], pts), 0.0) ** float(e['pow'])
        if 'scale' in e:
            return self.eval(e['of'], pts) * float(e['scale'])
        raise ValueError(f'unknown field expression {e}')

    # -------------------------------------------------------------------------------------------- (B3) the head frame
    def head_angles(self, center, P, mirror=True):
        """(B3) azimuth (deg, |az| when mirror), elevation (deg) and radius (m) of points P about a head centre"""
        c = self._node_pos(center)[0]
        d = np.asarray(P, np.float64) - c
        r = np.linalg.norm(d, axis=1)
        az = np.degrees(np.arctan2(d[:, 0], d[:, 2]))
        el = np.degrees(np.arcsin(np.clip(d[:, 1] / np.maximum(r, 1e-12), -1.0, 1.0)))
        return (np.abs(az) if mirror else az), el, r

    def _head_frame(self, e, pts):
        if 'sph' in e:
            az, el, r = self.head_angles(e['center'], pts.P, e.get('mirror', False))
            return {'az': az, 'el': el, 'r_mm': r * 1e3}[e['sph']]
        if 'hairline' in e:
            h = e['hairline']
            az, el, r = self.head_angles(h['center'], pts.P, h.get('mirror', True))
            cv = np.asarray(h['curve'], np.float64)
            el0 = np.interp(az, cv[:, 0], cv[:, 1])
            above_mm = np.radians(el - el0) * r * 1e3
            lo, hi = h.get('fade_mm', [0.0, 8.0])
            return smoothstep(lo, hi, above_mm)
        b = e['band']
        az, el, _ = self.head_angles(b['center'], pts.P, b.get('mirror', True))
        s = float(b.get('soft_deg', 6.0))
        a0, a1 = b.get('az', [-360.0, 360.0])
        e0, e1 = b.get('el', [-90.0, 90.0])
        return (smoothstep(a0 - s, a0 + s, az) * (1.0 - smoothstep(a1 - s, a1 + s, az))
                * smoothstep(e0 - s, e0 + s, el) * (1.0 - smoothstep(e1 - s, e1 + s, el)))
