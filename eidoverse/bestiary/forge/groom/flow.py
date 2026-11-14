"""THE FLOW FIELD: the direction the coat lies in, a unit tangent vector per welded vertex of the base's low.

Built from the spec's sources (HAIR_STUDY §9.2 step 2, WOLF_PLAN §5.2 step 1, CG 16.35-16.37), each a soft mask (a
fields.py expression) times a unit direction rule:
  {"dir": "chain", "chains": "^arm", "sign": 1}   along the matching joint chains toward their tips: the skin-weighted
                                                   sum of the joints' directions (base.joint_dir), so a web between two
                                                   arms takes their mean
  {"dir": "joints", "joints": "^mantle_", "sign": -1}   the same over any joints (sign -1: from the chain's end back)
  {"dir": "away", "from": "^socket_mantle_apex$"}  radially away from a node (a source, a crown whorl's centre);
                                                   "toward" the opposite (a sink)
  {"dir": "axis", "axis": [0, -1, 0]}              a fixed world direction (gravity's comb)
plus singularities {"type": "whorl", "at": "<node regex>", "radius_mm": r, "spin": 1, "strength": k}: a vortex term
N x (p - c) with a Gaussian falloff. (coat G6, 11-01) A source's "from" / "to" and a whorl's "at" may also name a point
between two sockets, {"between": ["^socket_eyes$", "^socket_head_top$"], "t": 0.4} (each regex's first match; optional
"offset_mm": [x, y, z]), so a whorl can sit where an animal's would (a crown behind the eyes) though no socket stands
there (node_points). The sum is projected to the tangent plane, then smoothed by parallel-transport
Laplacian iterations (Warp, k_smooth): each vertex takes its neighbours' vectors projected into its own tangent plane,
plus its source held at `hold` x its source strength, so strong sources stay put and weak regions interpolate.

(B3, HAIR_FUR H1) THE PARTING, a singularity of its own kind:
  {"type": "part", "center": c, "curve": [[az, el], ...], "band_mm": 14, "strength": 1.5, "side_bias": 0.0}
a line on the scalp where the flow SPLITS: the curve is written in the head's spherical frame (fields.py's: centre c,
azimuth about +Y from the front, signed: + toward the base's +X; elevation), each row carried out from the centre to the
skin, the polyline densified on the surface. Every welded vertex within band_mm of it takes a source pointing AWAY from
the line on its own side (n x t, signed by the side; Gaussian in the distance; side_bias > 0 favours the + side), and the
smoothing's neighbour lists are CUT across the line (no edge joins two vertices on opposite sides within the band), so
the two sides never average into a cross-flow: the split stays a crisp line, as a combed part does. The part's band is a
designed zone for the index gate (its ends are where a part's half-turn singularities sit).

GATES (printed per run):
  zero   no vertex whose smoothed vector is shorter than 1e-6 before normalising (CG 16.35's fallback case);
  tangency  max |v . n| below 1e-4 after the last projection;
  index  the field's winding around every welded face: a face with |index| >= 1/2 holds a singularity; each is listed
         with its position and whether it lies in the bare zone, near a designed singularity, or ELSEWHERE (flagged).
"""
import numpy as np
import warp as wp

from .fields import Pts, smoothstep

wp.set_module_options({'enable_backward': False})


@wp.kernel
def k_smooth(V: wp.array(dtype=wp.vec3), N: wp.array(dtype=wp.vec3), src: wp.array(dtype=wp.vec3),
             hold: wp.array(dtype=wp.float32), nb_ptr: wp.array(dtype=wp.int32), nb_idx: wp.array(dtype=wp.int32),
             vin: wp.array(dtype=wp.vec3), vout: wp.array(dtype=wp.vec3)):
    i = wp.tid()
    n = N[i]
    acc = src[i] * hold[i]
    for e in range(nb_ptr[i], nb_ptr[i + 1]):
        j = nb_idx[e]
        vj = vin[j]
        # transport: project into this vertex's tangent plane, keep the length (a rotation for small normal changes)
        lj = wp.length(vj)
        pj = vj - n * wp.dot(vj, n)
        lp = wp.length(pj)
        if lp > 1.0e-12:
            acc = acc + pj * (lj / lp)
    acc = acc - n * wp.dot(acc, n)
    la = wp.length(acc)
    if la > 1.0e-12:
        vout[i] = acc / la
    else:
        vout[i] = acc


def _unit(a):
    return a / np.maximum(np.linalg.norm(a, axis=-1, keepdims=True), 1e-30)


def node_points(base, at):
    """(coat G6) the points (n, 3) a flow term names, bind pose: a node regex (every match, as before), or a point between
    two sockets, {"between": [regex_a, regex_b], "t": 0.4} (each regex's first match: a + t (b - a)), or {"node": regex};
    "offset_mm": [x, y, z] moves the dict forms. A whorl on a mask's edge (the octopus's mantle apex sits on the
    underside's) fans the coat out round a bald spot; a crown whorl wants a point no socket marks"""
    if isinstance(at, str):
        return base.node_world[base.node_ids(at)][:, :3, 3]
    if 'between' in at:
        a, c = at['between']
        ia, ic = base.node_ids(a), base.node_ids(c)
        assert ia and ic, f'no node matches {at["between"]!r}'
        pa, pc = base.node_world[ia[0]][:3, 3], base.node_world[ic[0]][:3, 3]
        P = (pa + (pc - pa) * float(at.get('t', 0.5)))[None, :]
    else:
        P = base.node_world[base.node_ids(at['node'])][:, :3, 3]
    if 'offset_mm' in at:
        P = P + np.asarray(at['offset_mm'], np.float64)[None, :] * 1e-3
    return P


class Flow:
    """the coat's flow on a base: build(spec_flow, fields, bare) then .at(pts) for unit tangents at surface points"""

    def __init__(self, base, fields):
        self.base = base
        self.fields = fields
        self.log = []

    def _sources(self, spec):
        b = self.base
        pv = Pts.vertices(b)                         # one point per unwelded vertex
        nv = len(b.V)
        src = np.zeros((nv, 3))
        strength = np.zeros(nv)
        for s in spec['sources']:
            m = self.fields.eval(s.get('mask', 1.0), pv) * float(s.get('weight', 1.0))
            kind = s['dir']
            if kind in ('chain', 'joints'):
                if kind == 'chain':
                    import re
                    rx = re.compile(s['chains'])
                    ids = np.array(sorted({j for c in b.chains if rx.search(c['name']) for j in c['joints']}), np.int64)
                else:
                    ids = b.joint_ids(s['joints'])
                Wm = np.where(np.isin(b.J, ids), b.W, 0.0)
                d = np.einsum('nk,nkd->nd', Wm, b.joint_dir[b.J]) * float(s.get('sign', 1.0))
                wsum = Wm.sum(1)
                d = _unit(d) * (wsum > 1e-6)[:, None]
                m = m * np.clip(wsum, 0.0, 1.0)
            elif kind in ('away', 'toward'):
                C = node_points(b, s['from'] if kind == 'away' else s['to'])
                dd = pv.P[:, None, :] - C[None, :, :]
                k = np.argmin(np.linalg.norm(dd, axis=2), axis=1)
                d = _unit(dd[np.arange(nv), k]) * (1.0 if kind == 'away' else -1.0)
            elif kind == 'axis':
                d = np.broadcast_to(_unit(np.asarray(s['axis'], np.float64)), (nv, 3)).copy()
            else:
                raise ValueError(kind)
            # tangential part only: a direction along the normal says nothing about how the coat lies
            d = d - pv.N * np.sum(d * pv.N, axis=1, keepdims=True)
            src += d * m[:, None]
            strength += m * np.linalg.norm(d, axis=1)
        # (B3) the partings: a source away from each line on its own side (per welded vertex, spread to the copies)
        self.parts = []
        for w in spec.get('singularities', []):
            if w.get('type') != 'part':
                continue
            pr = self.part_line(w)
            self.parts.append(pr)
            g = pr['weight'][b.wid]
            d = pr['away'][b.wid]
            d = d - pv.N * np.sum(d * pv.N, axis=1, keepdims=True)
            src += _unit(d) * g[:, None]
            strength += g
        for w in spec.get('singularities', []):
            if w.get('type') != 'whorl':
                continue
            C = node_points(b, w['at'])
            for c in C:
                rel = pv.P - c
                d2 = np.sum(rel * rel, axis=1)
                r = w['radius_mm'] * 1e-3
                g = np.exp(-d2 / (r * r)) * float(w.get('strength', 1.0))
                t = np.cross(pv.N, rel) * float(w.get('spin', 1.0))
                src += _unit(t) * g[:, None]
                strength += g
        return src, strength

    def part_line(self, w):
        """(B3) a parting's line on the welded low and, per welded vertex: the distance to it (m), its side (+1 / -1),
        the direction away from it (unit, tangent), the source weight; the polyline (n, 3)"""
        b = self.base
        from .fields import Fields
        f = self.fields if isinstance(self.fields, Fields) else Fields(b)
        c = f._node_pos(w['center'])[0]
        U = _unit(b.Vw - c)
        pts = []
        for az, el in w['curve']:
            a, e = np.radians(az), np.radians(el)
            dvec = np.array([np.cos(e) * np.sin(a), np.sin(e), np.cos(e) * np.cos(a)])
            pts.append(b.Vw[int(np.argmax(U @ dvec))])
        pts = np.array(pts)
        # densify every 2 mm and snap each sample to the skin (its welded vertex nearest along the centre's ray)
        dense = [pts[0]]
        for p0, p1 in zip(pts[:-1], pts[1:]):
            n = max(int(np.ceil(np.linalg.norm(p1 - p0) / 2e-3)), 1)
            for k in range(1, n + 1):
                q = p0 + (p1 - p0) * (k / n)
                dense.append(b.Vw[int(np.argmax(U @ _unit(q - c)))])
        L = np.array(dense)
        keep = np.concatenate([[True], np.linalg.norm(np.diff(L, axis=0), axis=1) > 1e-9])
        L = L[keep]
        # each welded vertex's closest point on the polyline, the segment's tangent there
        A, B = L[:-1], L[1:]
        AB = B - A
        best = np.full(len(b.Vw), np.inf)
        foot = np.zeros((len(b.Vw), 3))
        tang = np.zeros((len(b.Vw), 3))
        for k in range(len(A)):
            t = np.clip(np.sum((b.Vw - A[k]) * AB[k], 1) / max(float(AB[k] @ AB[k]), 1e-18), 0.0, 1.0)
            q = A[k] + t[:, None] * AB[k]
            dd = np.linalg.norm(b.Vw - q, axis=1)
            m = dd < best
            best[m] = dd[m]
            foot[m] = q[m]
            tang[m] = AB[k] / max(np.linalg.norm(AB[k]), 1e-12)
        side_dir = _unit(np.cross(b.Nw, tang))
        side = np.sign(np.sum((b.Vw - foot) * side_dir, 1))
        side[side == 0] = 1.0
        band = float(w.get('band_mm', 14.0)) * 1e-3
        bias = float(w.get('side_bias', 0.0))
        weight = float(w.get('strength', 1.5)) * np.exp(-(best / band) ** 2) * (1.0 + bias * side)
        return dict(line=L, dist=best, side=side, away=side_dir * side[:, None], weight=weight, band=band,
                    name=w.get('name', 'part'))

    def build(self, spec, bare_v=None, designed=(), designed_w=None):
        """spec: the style's "flow" block; bare_v: the bare mask per welded vertex (gates ignore singularities there);
        designed: [(name, position, radius_m)] designed singularity zones; designed_w: [(name, welded-vertex mask)]"""
        b = self.base
        src, strength = self._sources(spec)
        nw = len(b.Vw)
        # weld: sum the unwelded vertices' sources onto their welded vertex
        S = np.zeros((nw, 3))
        np.add.at(S, b.wid, src)
        St = np.zeros(nw)
        np.add.at(St, b.wid, strength)
        cnt = np.bincount(b.wid, minlength=nw)
        S /= cnt[:, None]
        St /= cnt
        S = S - b.Nw * np.sum(S * b.Nw, axis=1, keepdims=True)
        n_zero_src = int((np.linalg.norm(S, axis=1) < 1e-6).sum())
        hold = float(spec.get('hold', 2.0)) * np.clip(St, 0.0, 1.0)
        dev = wp.get_preferred_device() if spec.get('device') is None else spec['device']
        Vd = wp.array(b.Vw.astype(np.float32), dtype=wp.vec3, device=dev)
        Nd = wp.array(b.Nw.astype(np.float32), dtype=wp.vec3, device=dev)
        Sd = wp.array(_unit(S).astype(np.float32) * (np.linalg.norm(S, axis=1, keepdims=True) > 1e-9),
                      dtype=wp.vec3, device=dev)
        Hd = wp.array(hold.astype(np.float32), dtype=wp.float32, device=dev)
        nb_ptr, nb_idx = b.nb_ptr, b.nb_idx
        self.part_cut_edges = 0
        if self.parts:
            # (B3) the smoothing cut across every parting: no neighbour on the other side within the part's band
            row = np.repeat(np.arange(nw), np.diff(nb_ptr))
            ok = np.ones(len(nb_idx), bool)
            for pr in self.parts:
                near = pr['dist'] < pr['band']
                ok &= ~(near[row] & near[nb_idx] & (pr['side'][row] != pr['side'][nb_idx]))
            self.part_cut_edges = int((~ok).sum())
            nb_idx = nb_idx[ok]
            nb_ptr = np.concatenate([[0], np.cumsum(np.bincount(row[ok], minlength=nw))]).astype(np.int32)
            designed_w = list(designed_w or []) + [(pr['name'], (pr['dist'] < pr['band']).astype(np.float64))
                                                   for pr in self.parts]
        P_ = wp.array(nb_ptr.astype(np.int32), dtype=wp.int32, device=dev)
        I_ = wp.array(nb_idx.astype(np.int32), dtype=wp.int32, device=dev)
        v0 = wp.array(_unit(S + 1e-9 * np.cross(b.Nw, [0.3, 0.7, 0.1])).astype(np.float32), dtype=wp.vec3, device=dev)
        v1 = wp.zeros_like(v0)
        for _ in range(int(spec.get('smooth_iters', 40))):
            wp.launch(k_smooth, dim=nw, inputs=[Vd, Nd, Sd, Hd, P_, I_, v0], outputs=[v1], device=dev)
            v0, v1 = v1, v0
        v = v0.numpy().astype(np.float64)
        lens = np.linalg.norm(v, axis=1)
        n_zero = int((lens < 1e-6).sum())
        v = _unit(v)
        v = _unit(v - b.Nw * np.sum(v * b.Nw, axis=1, keepdims=True))
        self.v = v
        self.src = S
        self.strength = St
        tang = float(np.abs(np.sum(v * b.Nw, axis=1)).max())
        sing = self.singularities(bare_v, designed, designed_w)
        self.gates = dict(zero_source_vertices=n_zero_src, zero_vertices=n_zero, tangency_max=tang,
                          singular_faces=len(sing), flagged=[s for s in sing if s['zone'] == 'ELSEWHERE'],
                          by_zone={z: sum(1 for s in sing if s['zone'] == z) for z in ('bare', 'designed', 'ELSEWHERE')},
                          index_sum=float(sum(s['index'] for s in sing)))
        if self.parts:
            # (B3) the part as designed: its line's length, the edges cut, and the split measured across it (the flows
            # 3 mm either side of the line's middle half point apart: the dot of the two sides' mean flows, -1 = opposite)
            splits = []
            for pr in self.parts:
                L = pr['line']
                mid = (pr['dist'] < 4e-3) & (pr['dist'] > 1e-3)
                a = v[mid & (pr['side'] > 0)].mean(0) if (mid & (pr['side'] > 0)).any() else np.zeros(3)
                c_ = v[mid & (pr['side'] < 0)].mean(0) if (mid & (pr['side'] < 0)).any() else np.zeros(3)
                splits.append(dict(name=pr['name'], length_mm=round(float(np.linalg.norm(np.diff(L, axis=0), axis=1).sum()) * 1e3, 1),
                                   split_dot=round(float(_unit(a) @ _unit(c_)), 3)))
            self.gates['parts'] = dict(edges_cut=self.part_cut_edges, lines=splits)
        self.singular = sing
        return self

    def singularities(self, bare_v=None, designed=(), designed_w=None):
        """faces whose field winding is at least half a turn: (face, index, position, zone). designed: socket zones
        [(name, position, radius)]; designed_w: [(name, mask per welded vertex)] zones written as field masks"""
        b = self.base
        F = b.Fw
        out = []
        P = b.Vw[F]                                   # (m, 3, 3)
        n = _unit(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]))
        e1 = _unit(P[:, 1] - P[:, 0])
        e2 = np.cross(n, e1)
        ang = []
        for c in range(3):
            vc = self.v[F[:, c]]
            ang.append(np.arctan2(np.sum(vc * e2, axis=1), np.sum(vc * e1, axis=1)))
        tot = np.zeros(len(F))
        for c in range(3):
            d = ang[(c + 1) % 3] - ang[c]
            d = (d + np.pi) % (2 * np.pi) - np.pi
            tot += d
        idx = tot / (2 * np.pi)
        for f in np.nonzero(np.abs(idx) >= 0.5)[0]:
            c = P[f].mean(0)
            zone = 'ELSEWHERE'
            if bare_v is not None and bare_v[F[f]].max() >= 0.5:
                zone = 'bare'
            why = None
            for name, pos, rad in designed:
                if np.linalg.norm(c - pos) <= rad:
                    zone, why = 'designed', name
            for name, mw in (designed_w or []):
                if mw[F[f]].max() >= 0.5:
                    zone, why = 'designed', name
            out.append(dict(face=int(f), index=float(np.round(idx[f])), pos=c.round(4).tolist(), zone=zone,
                            why=why))
        return out

    def at(self, pts):
        """unit flow tangents at surface points: the welded corners' vectors blended, projected to the point's normal"""
        Fw = self.base.Fw[pts.tri]
        v = np.einsum('nk,nkd->nd', pts.bary, self.v[Fw])
        v = v - pts.N * np.sum(v * pts.N, axis=1, keepdims=True)
        bad = np.linalg.norm(v, axis=1) < 1e-9
        if bad.any():                                  # a root at a singularity: take its strongest corner
            k = np.argmax(pts.bary[bad], axis=1)
            v[bad] = self.v[Fw[bad, k]]
            v[bad] -= pts.N[bad] * np.sum(v[bad] * pts.N[bad], axis=1, keepdims=True)
        return _unit(v)
