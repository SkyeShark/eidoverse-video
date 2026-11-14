"""The EUROPEAN LOBSTER's side of the streak audit (forge/audit_streaks.py): the X7 pilot bake's outputs
(work/bestiary/tests/x07_bake.py: work/bestiary/lobster/x7/page_LIMBS.npz, baked through x04's cages and X5b's UVs).
Written after the stag beetle's adapter (audit_streaks_beetle.py), whose method it follows.

The lobster's chelipeds are 13 PRIMARY shells on one 4096 page (LIMBS, 3,800 px/m at x4: the audit's millimetres are
x4 millimetres, 0.25 mm at life), the stacked right copies on their primary's texels. Each primary was baked against its
own X6 high (lobster_sculpt.build_high on its creased limit) and its MICRO layer composed per sub-sample at q = the
CLOSEST POINT ON ITS LIMIT to the low's point (x07_compose.k_compose_lob): granules at their sites (stag_beetle_sculpt
grain_granules, cell_mode 5), sparse setal pits, the membranes' vermiculate cells. So:
  * sets: 'LIMBS' (one page).
  * check 1, the coordinate: q(P) replicated exactly (Warp's mesh_query_point_no_sign on each primary's limit at
    lobster_sculpt.LEVEL; the right carpus and the cutter built on the left as x07 baked them, the carpus's low mirrored
    to the left with them), w = the micro layer's use there (micro_params' masks: the pits' density, the cells' amount);
    sref 1 (isometric); cell 1 mm at life (the granules' spacing, GRANULES).
  * check 2: no material pass has run (X9), so the one map is the RELIEF: the composed normal less the bake's macro
    normal (normal_macro: the high alone, its strokes, fillets and folds included): the micro layer's own output.
  * check 3: the GRANULES as the planted features (grain_sites on each primary's limit with micro_params' own settings:
    exactly the sites the relief draws), plantable where micro_params' cells mask reaches (no membrane, no polished
    molar face, no stroke's tip).
  * places: the primary's name."""
import json
import os

import numpy as np
import warp as wp

from . import audit_streaks as AS
from .species import lobster_sculpt as LS
from .species import lobster_uv as LU
from .species import stag_beetle_sculpt as SC

wp.set_module_options({'enable_backward': False})
SCM = LS.SC_M                    # metres at x4 per life mm: the audit's unit


@wp.kernel
def k_closest(meshes: wp.array(dtype=wp.uint64), mid: wp.array(dtype=wp.int32), P: wp.array(dtype=wp.vec3),
              maxd: float, out: wp.array(dtype=wp.vec3), ok: wp.array(dtype=wp.int32)):
    """(audit_streaks_beetle.k_closest, copied) per point (life mm) the closest point on its own primary's limit"""
    i = wp.tid()
    m = mid[i]
    out[i] = P[i]
    ok[i] = 0
    if m < 0:
        return
    q = wp.mesh_query_point_no_sign(meshes[m], P[i], maxd)
    if q.result:
        out[i] = wp.mesh_eval_position(meshes[m], q.face, q.u, q.v)
        ok[i] = 1


class LobsterAudit(AS.CreatureAudit):
    name = 'lobster'

    def __init__(self, root, label=None, tag=''):
        """root: the repository; tag: the bake's suffix (x07_bake.py --tag)"""
        out7 = os.path.join(root, 'work', 'bestiary', 'lobster', 'x7')
        super().__init__(out7, label or 'European lobster (X7 pilot bake)')
        self.tag = tag
        OL = os.path.join(root, 'work', 'bestiary', 'lobster')
        self.z = np.load(os.path.join(OL, 'cage_x04_crusher.npz'))
        meta = json.loads(str(self.z['meta']))
        self.cnames = [str(n) for n in self.z['names']]
        self.C = LU.load(self.z, meta, SCM)
        self.Z = np.load(os.path.join(OL, 'uv_x05.npz'), allow_pickle=False)
        self.CH = {}
        for k in range(int(self.Z['n_charts'])):
            self.CH.setdefault(str(self.Z[f'c{k}_shell']), []).append(k)
        self.prim = list(self.CH)                        # (x07's PRIMARY, its region ids)
        self.REC = json.load(open(os.path.join(OL, 'strokes_x04_crusher.json'), encoding='utf-8'))['strokes']
        self.size = int(json.load(open(os.path.join(OL, 'uv_x05_meta.json'), encoding='utf-8'))['size'])
        self._lim = {}
        self._G = {}
        self._tex = {}
        self._feat = None
        self.notes.append(f'{len(self.prim)} primary shells on one {self.size}^2 page (LIMBS) at 3,800 px/m x4; the audit\'s '
                          f'mm are x4 mm (0.25 mm at life)')
        self.notes.append('check 1: q = the closest point on each primary\'s own limit (lobster_sculpt.LEVEL) to the low\'s '
                          'point, as x07_compose.k_compose_lob evaluates the micro relief; the granules (cell_mode 5) are '
                          'drawn at q, each in its own site\'s tangent plane: q is their coordinate')
        self.notes.append('check 2: no material pass yet (X9): the one map is the RELIEF, the composed normal less the bake\'s '
                          'macro normal (the high alone: strokes, fillets, folds)')
        self.notes.append('check 3: the granules\' sites (grain_sites with micro_params\' settings) as the planted features')

    # ---- the shells: the high's limit, its micro masks, the strokes
    def _shell(self, nm):
        if nm in self._lim:
            return self._lim[nm]
        c = self.C[nm]
        i = self.cnames.index(nm)
        C_life = self.z[f'C_x4_{i}'] / SCM
        Q = c['Q']
        rec = self.REC.get(nm, [])
        on_left = nm in LU.CLAW_MIRRORS
        Vlow = c['V'].copy()
        if on_left:
            C_life = C_life * LU.M_X
            Q = Q[:, ::-1].copy()
            rec = self.REC.get(LU.CLAW_MIRRORS[nm], [])
            Vlow = Vlow * LU.M_X
        prims = LS.stroke_prims(rec)
        V, Ql, par = LS.limit(C_life, Q, c['sharp'])
        region = c['region']
        mp = LS.micro_params(V, Ql, par, region, prims)
        regq = np.array([str(region[p_]) for p_ in par])
        reg_v = np.full(len(V), 'chitin', object)
        for j in range(4):
            reg_v[Ql[:, j]] = regq
        w_cells = np.where(np.isin(reg_v, ('membrane', 'sleeve')), 0.0, mp['m4'][:, 3]).astype(np.float32)
        self._lim[nm] = dict(V=V, F=mp['tri'].astype(np.int32), N=mp['vn'], M4=mp['m4'].astype(np.float32), Q=Q,
                             Vlow=Vlow, on_left=on_left, w_cells=w_cells, prims=prims)
        return self._lim[nm]

    def _wp_mesh(self, nm):
        L = self._shell(nm)
        if 'mesh' not in L:
            L['mesh'] = wp.Mesh(points=wp.array(L['V'].astype(np.float32), dtype=wp.vec3),
                                indices=wp.array(L['F'].ravel(), dtype=wp.int32))
        return L['mesh']

    # ---- the run folder
    def low(self):
        """every primary's low under its charts, as x07 baked it (metres at x4; the carpus built on the left mirrored, each
        triangle's winding reversed)"""
        if self._low is None:
            Vs, Fs, UVs, Ns, rg = [], [], [], [], []
            off = 0
            for si, nm in enumerate(self.prim):
                L = self._shell(nm)
                VN = LS.vertex_normals(L['Vlow'], L['Q'])
                for k in self.CH[nm]:
                    orig = self.Z[f'c{k}_orig'].astype(np.int64)
                    F_ = self.Z[f'c{k}_F'].astype(np.int64)
                    if L['on_left']:
                        F_ = F_[:, ::-1]
                    Vs.append(L['Vlow'][orig] * SCM)
                    Ns.append(VN[orig])
                    UVs.append(self.Z[f'c{k}_uv'].astype(np.float64))
                    Fs.append(F_ + off)
                    rg.append(np.full(len(F_), si, np.int32))
                    off += len(orig)
            F = np.concatenate(Fs)
            self._low = dict(V=np.concatenate(Vs), F=F, UV=np.concatenate(UVs), N=np.concatenate(Ns),
                             face_set=np.full(len(F), 'LIMBS'), region=np.concatenate(rg))
        return self._low

    def sets(self):
        if getattr(self, '_sets', None) is None:
            self._sets = [dict(name='LIMBS', faces=np.ones(len(self.low()['F']), bool), size=self.size)]
        return self._sets

    def drivers(self, set_name):
        if set_name not in self._drv:
            z = np.load(os.path.join(self.run_dir, f'page_{set_name}{self.tag}.npz'))
            self._drv[set_name] = dict(normal=np.asarray(z['normal'], np.float32), region=np.asarray(z['region']),
                                       normal_macro=np.asarray(z['normal_macro'], np.float32),
                                       micro=np.asarray(z['micro'], np.float32))
        return self._drv[set_name]

    def load_map(self, set_name, key):
        if (set_name, key) in self.map_override:
            return self.map_override[(set_name, key)]
        d = self.drivers(set_name)
        n = {'N': d['normal_macro'], 'normal': d['normal']}.get(key)
        if n is None:
            return None
        return (np.clip(n[..., :3] * 0.5 + 0.5, 0, 1) * 255.0 + 0.5).astype(np.uint8)

    def groups(self, set_name):
        return [dict(name='relief', key='normal', kind='normal_delta', ref='N')]

    def high_group(self, set_name):
        return dict(name='high', key='N', kind='normal')

    def texel_masks(self, set_name, G):
        """per inside texel: its primary and the micro layer's use (micro_params' masks at the nearest limit vertex of
        its own primary to its low point)"""
        if set_name in self._tex:
            return self._tex[set_name]
        from scipy.spatial import cKDTree
        reg = self.drivers(set_name)['region'][G.ys, G.xs].astype(np.int32)
        m4 = np.zeros((G.n, 4), np.float32)
        wc = np.zeros(G.n, np.float32)
        for si in np.unique(reg):
            if si < 0:
                continue
            L = self._shell(self.prim[si])
            sel = np.nonzero(reg == si)[0]
            _, j = cKDTree(L['V']).query(G.P[sel] / SCM)
            m4[sel] = L['M4'][j]
            wc[sel] = L['w_cells'][j]
        self._tex[set_name] = dict(reg=reg, m4=m4, wc=wc)
        return self._tex[set_name]

    def zones(self, set_name, G):
        self._G[set_name] = G
        reg = self.drivers(set_name)['region'][G.ys, G.xs].astype(np.int16)
        return reg, {int(k): self.prim[int(k)] for k in np.unique(reg) if k >= 0}

    def places(self, set_name, P):
        G = self._G.get(set_name)
        if G is None:
            return None
        from scipy.spatial import cKDTree
        if not hasattr(G, '_tree'):
            G._tree = cKDTree(G.P)
        _, j = G._tree.query(P)
        z = G.zone[j]
        return np.array([self.prim[int(k)].replace('cheliped_', '') if k >= 0 else 'none' for k in z])

    def landmarks(self):
        if getattr(self, '_lm', None) is None:
            L = self.low()
            self._lm = {nm.replace('cheliped_', ''): L['V'][np.unique(L['F'][L['region'] == si])].mean(0)
                        for si, nm in enumerate(self.prim)}
        return self._lm

    # ---- check 1: the micro layer's coordinate
    def coordinates(self, set_name):
        G = self._G.get(set_name)
        if G is None:
            return []
        from scipy.spatial import cKDTree
        T = self.texel_masks(set_name, G)
        tree = cKDTree(G.P)
        w_tex = np.maximum(T['m4'][:, 0], T['wc'])               # the pits' density, the granules' amount
        ids = np.zeros(len(self.prim), np.uint64)
        for si in sorted(set(int(x) for x in np.unique(T['reg']) if x >= 0)):
            ids[si] = self._wp_mesh(self.prim[si]).id
        ids_d = wp.array(ids, dtype=wp.uint64)

        def fn(P, xp):
            Pn = P.get() if hasattr(P, 'get') else np.asarray(P)
            n5 = len(Pn)
            m = n5 // 5
            _, j = tree.query(Pn[:m])                    # (check_coord passes [pb, pb+dx, pb-dx, pb+dy, pb-dy])
            mid = np.tile(T['reg'][j].astype(np.int32), 5)
            out = wp.zeros(n5, dtype=wp.vec3)
            ok = wp.zeros(n5, dtype=wp.int32)
            wp.launch(k_closest, dim=n5, inputs=[ids_d, wp.array(mid, dtype=wp.int32),
                                                 wp.array((Pn / SCM).astype(np.float32), dtype=wp.vec3), 5.0, out, ok])
            q = out.numpy().astype(np.float64) * SCM
            return xp.asarray(q), xp.asarray(np.tile(w_tex[j], 5)), xp.asarray(np.ones(n5))
        return [dict(name='limit closest point (micro relief)', fn=fn, cell=LS.GRANULES['spacing'] * SCM,
                     note='the micro relief is a solid pattern at q = the closest limit point to the low\'s point; cell 1 '
                          'mm at life (the granules\' spacing)')]

    def coord_breakdown(self, set_name, G, idx):
        T = self.texel_masks(set_name, G)
        reg = T['reg'][idx]
        return {self.prim[int(k)].replace('cheliped_', ''): reg == k for k in np.unique(reg) if k >= 0}

    # ---- check 3: the granules
    def features(self, set_name):
        if self._feat is None:
            Ps, Ns, Rs, Ks = [], [], [], []
            d0 = LS.GRANULES['spacing']
            cfg = dict(density=2.0 / (np.sqrt(3.0) * d0 * d0), aniso=1.0, flow_rot=0.0, rot_jit=0.0, mod_amp=0.0,
                       kappa=LS.GRANULES['size'] / d0, **{k_: LS.GRANULES[k_] for k_ in ('size_jit', 'ht_jit', 'iters', 'step',
                                                                                          'seed')})
            for si, nm in enumerate(self.prim):            # (micro_params' own call: the same sites the relief draws)
                L = self._shell(nm)
                if not (L['w_cells'] > 0.005).any():
                    continue
                S_ = SC.grain_sites(L['V'], L['F'], L['N'], L['w_cells'], cfg=cfg)
                Ps.append(np.asarray(S_['P'], np.float64) * SCM)
                Ns.append(np.asarray(S_['n'], np.float64))
                Rs.append((0.5 * (np.asarray(S_['ra']) + np.asarray(S_['rb'])) * SCM).astype(np.float32))
                Ks.append(np.full(len(S_['P']), si, np.int32))
            self._feat = dict(p=np.concatenate(Ps), n=np.concatenate(Ns), rb=np.concatenate(Rs), kind=np.concatenate(Ks))
            self.notes.append(f'check 3: {len(self._feat["p"]):,} granules planted over {len(set(self._feat["kind"].tolist()))} '
                              f'primaries')
        return self._feat

    def plantable(self, set_name, P, N, zone):
        """the design's granule density at P: the cells' mask of P's own primary (its zone) at its nearest limit vertex"""
        from scipy.spatial import cKDTree
        out = np.zeros(len(P), np.float32)
        for zz in np.unique(zone):
            if zz < 0:
                continue
            L = self._shell(self.prim[int(zz)])
            if 'tree' not in L:
                L['tree'] = cKDTree(L['V'])
            sel = np.nonzero(zone == zz)[0]
            _, j = L['tree'].query(np.asarray(P)[sel] / SCM)
            out[sel] = L['w_cells'][j]
        return out
