"""The STAG BEETLE's side of the streak audit (forge/audit_streaks.py): the beetle-to-material round's outputs
(work/bestiary/beetle/out_b58: parts.npz, uv.npz, bake/page<k>.npz, maps/page<k>_<map>.png, limits/).

The beetle is not one skin: it is 42 PRIMARY masters (stag_beetle_parts; the stacked and mirrored copies take their
primary's texels), each baked against its OWN creased subdivision limit (b07). What can fail the way the octopus's crown
failed is the MICRO layer (species/stag_beetle_sculpt.relief): a solid pattern (Worley cells, punctures at jittered
lattice sites, setae streaks, the ventrites' grooves) evaluated at q = the CLOSEST POINT ON THE LIMIT to each sub-sample's
point on the low (b07's k_compose). That projection is the beetle's coordinate, and it can fail exactly as audit_streaks
fears: where the low's chord lies above a concave crease (a valley whose radius is under the chord's sag) every low point
of a band projects onto the same crease line (the pattern constant across the band: a COLLAPSE, a streak), and across the
crease's medial axis q jumps from one flank to the other (a TEAR: a seam through the pattern).

  * sets: 'page0', 'page1' (the two 4096 pages, 9,257 px/m at x10; the audit's millimetres are x10 millimetres, 0.1 mm
    at life: its scales were set on the octopus's skin patches of 2-4 mm, and the beetle's cells at x10 are 0.9-1.7 mm).
  * check 1, the coordinate: q(P) replicated exactly (Warp's mesh_query_point_no_sign on each primary's cached limit,
    the surface b07 baked), each texel against its own master's limit (the bake's region map names it; the texel's
    footprint points take their base texel's master, so no point projects onto a neighbouring part). The drivers carry
    no 'base', so the audit evaluates q at the LOW's point, where the generator does. w = the micro layer's use there
    (the per-vertex masks the generator reads, times whether its recipe draws that layer at all); sref 1 (isometric).
    (10-31, B9) EVERY COORDINATE A LAYER IS DRAWN ON: B8's elytral beads were drawn on a flowed 2D SHEET, d = (u, v) per limit
    vertex (stag_beetle_sculpt.grain_sheet, cell_mode 4), not at q, so this check, reading q alone, said "0 smears" while
    the sheet stretched the beads p50 1.62x (the B8 check's k04). A master whose cells are drawn on the sheet now adds that
    coordinate as its own check 1 entry ('grain sheet'): d interpolated at q on q's own limit triangle, as k_compose
    reads it (k_closest_d), its Jacobian against the surface measured by the core like any coordinate (sref 1: the sheet's
    millimetres are the surface's by design), w the cells' mask there; the cells leave q's weight on that master. The
    GRANULES (cell_mode 5, B9) are drawn at q, each in its own site's tangent plane (stag_beetle_sculpt.grain_granules):
    q is their coordinate, so they join q's weight (their recipe's cells amplitude is 0, their `grain` draws them), and
    the notes carry their sites' census (stag_beetle_sculpt.grain_sites).
  * check 2: the albedo, the COAT roughness (ORM B: the gloss that shows), the base roughness (ORM G), and the RELIEF =
    the shipped normal less the bake of the limit alone (b07's normal_macro): the micro layer's own output, the
    creases and folds cancelled by construction. The HIGH that explains a streak is the limit alone (normal_macro):
    creases, keels, sutures modelled as geometry. Designed anisotropy: the setae (their direction field, where the design
    plants them) and the ventrites' grooves.
  * check 3: the PUNCTURES as the planted features (every jittered lattice site within its radius of the limit and kept
    by the density mask: exactly the pits the relief draws), plantable by the design's density mask; the relief the bake
    carries (the shipped normal's high-passed RMS) cross-checks where the compose may have dropped the micro layer.
  * places: the master's region (head, pronotum, elytron, femur ...) for the report's per-place totals.
"""
import json
import os

import numpy as np
import warp as wp

from . import audit_streaks as AS
from . import proc as PR
from .mesh import QuadMesh
from .species import stag_beetle_parts as BP
from .species import stag_beetle_sculpt as SC

wp.set_module_options({'enable_backward': False})


@wp.kernel
def k_closest(meshes: wp.array(dtype=wp.uint64), mid: wp.array(dtype=wp.int32), P: wp.array(dtype=wp.vec3),
              maxd: float, out: wp.array(dtype=wp.vec3), ok: wp.array(dtype=wp.int32)):
    """per point (life mm) the closest point on its own master's limit (life mm)"""
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


@wp.kernel
def k_closest_d(mesh: wp.uint64, LF: wp.array(dtype=wp.int32), D: wp.array(dtype=wp.vec3), P: wp.array(dtype=wp.vec3),
                maxd: float, out: wp.array(dtype=wp.vec3), ok: wp.array(dtype=wp.int32)):
    """(10-31, B9) per point (life mm) the per-vertex coordinate D (micro_masks' d: the sheet a layer may be drawn on)
    interpolated at the closest point on the master's limit, on that point's own triangle (as b07's k_compose reads it)"""
    i = wp.tid()
    out[i] = wp.vec3(0.0, 0.0, 0.0)
    ok[i] = 0
    q = wp.mesh_query_point_no_sign(mesh, P[i], maxd)
    if q.result:
        f = q.face
        a0 = LF[3 * f]
        a1 = LF[3 * f + 1]
        a2 = LF[3 * f + 2]
        w = 1.0 - q.u - q.v
        out[i] = D[a0] * q.u + D[a1] * q.v + D[a2] * w
        ok[i] = 1


@wp.kernel
def k_pits(cells: wp.array(dtype=wp.vec3i), sp: float, r: float, seed: int, mesh: wp.uint64, LF: wp.array(dtype=wp.int32),
           LN: wp.array(dtype=wp.vec3), M4: wp.array(dtype=wp.vec4), out_p: wp.array(dtype=wp.vec3),
           out_n: wp.array(dtype=wp.vec3), keep: wp.array(dtype=wp.int32)):
    """per lattice cell the relief's puncture site (stag_beetle_sculpt.relief's pits: site_of(cell, 0.9, seed + 31) x sp,
    kept when u01(hash3i(cell, seed + 57)) < the density mask): kept when the site lies within r of the limit (its
    dimple reaches the surface; r = half the spacing for a region whose punctures are one layer, pit_mode 1) and the
    mask at its closest surface point keeps it"""
    i = wp.tid()
    c = cells[i]
    s = PR.site_of(c, 0.9, seed + 31) * sp
    h = PR.u01(PR.hash3i(c[0], c[1], c[2], seed + 57))
    keep[i] = 0
    q = wp.mesh_query_point_no_sign(mesh, s, r)
    if not q.result:
        return
    f = q.face
    a0 = LF[3 * f]
    a1 = LF[3 * f + 1]
    a2 = LF[3 * f + 2]
    w = 1.0 - q.u - q.v
    m = M4[a0] * q.u + M4[a1] * q.v + M4[a2] * w
    if h < m[0]:
        cp = wp.mesh_eval_position(mesh, f, q.u, q.v)
        out_p[i] = cp
        out_n[i] = wp.normalize(LN[a0] * q.u + LN[a1] * q.v + LN[a2] * w)
        keep[i] = 1


class BeetleAudit(AS.CreatureAudit):
    name = 'stag_beetle'

    def __init__(self, out_dir, label=None, tag=''):
        """out_dir: the round's out_b58 folder; tag: the bake's page suffix ('' for the full bake)"""
        super().__init__(out_dir, label or 'stag beetle (B58)')
        self.tag = tag
        P = BP.load(os.path.join(out_dir, 'parts.npz'))
        self.masters = P['masters']
        self.MD = {m['name']: m for m in self.masters}
        self.names = [m['name'] for m in self.masters]          # the bake's region id = the index here
        Z = np.load(os.path.join(out_dir, 'uv.npz'), allow_pickle=False)
        self.uvz = Z
        self.meta = json.loads(str(Z['meta']))
        self.prim = [nm for nm, mm in self.meta['masters'].items() if not mm.get('shared_from')]
        self.b04 = json.load(open(os.path.join(out_dir, 'b04_report.json'), encoding='utf-8'))['masters']
        self.sut = [(d['z_B1'], d['fwhm_B1']) for d in
                    json.load(open(os.path.join(out_dir, 'sutures.json'), encoding='utf-8'))['sutures']]
        self._lim = {}
        self._G = {}
        self._tex = {}
        self._feat = None
        self.notes.append(f'{len(self.prim)} primary masters on {self.meta["pages"]} pages of {self.meta["size"]}^2 at '
                          f'{self.meta["px_per_m"]:.0f} px/m (x10); the audit\'s mm are x10 mm (0.1 mm at life)')
        self.notes.append('check 1: q = the closest point on each master\'s own limit (the bake\'s cached L5/L6 surface) '
                          'to the low\'s point, as b07\'s k_compose evaluates the micro relief')
        self.notes.append('check 2: the high = the bake of the limit alone (normal_macro); relief = the shipped normal less '
                          'it; designed: the setae (along their direction) and the ventrites\' grooves')
        self.notes.append('check 3: the punctures (every relief pit site within its radius of the limit and kept by the '
                          'density mask) as the planted features, plantable by that mask')
        # (11-01, B9) the coordinate each region's cells are drawn on, said up front: run_audit copies the notes when it starts, so
        # limit()'s later census line (the granules' sites) never reached the report
        for reg in sorted({m['region'] for m in self.masters}):
            r = SC.RECIPE.get(reg, {})
            if r.get('grain') and r.get('cell_mode') == 5.0:
                self.notes.append(f'check 1: {reg}: GRANULES (cell_mode 5) drawn at q, each in its own site\'s tangent plane '
                                  f'(stag_beetle_sculpt.grain_granules): q is their coordinate, so the limit closest point '
                                  f'entry reads them; no sheet')
            elif r.get('cell_mode', 0.0) == 4.0 and r['cells'][1] != 0:
                self.notes.append(f'check 1: {reg}: cells drawn on micro_masks\' flowed SHEET d (cell_mode 4): read as its own '
                                  f'"grain sheet" entry')

    # ---- the run folder
    def low(self):
        if self._low is None:
            Vs, Fs, UVs, Ns, fs, rg = [], [], [], [], [], []
            off = 0
            for nm in self.prim:
                p = nm + '__'
                V = self.uvz[p + 'V'] * 0.01                       # life mm -> metres at x10
                F = self.uvz[p + 'F']
                Vs.append(V)
                Fs.append(F + off)
                UVs.append(self.uvz[p + 'UV'])
                Ns.append(self.uvz[p + 'N'])
                fs.append(np.array([f'page{int(k)}' for k in self.uvz[p + 'page']]))
                rg.append(np.full(len(F), self.names.index(nm), np.int32))
                off += len(V)
            self._low = dict(V=np.concatenate(Vs), F=np.concatenate(Fs), UV=np.concatenate(UVs), N=np.concatenate(Ns),
                             face_set=np.concatenate(fs), region=np.concatenate(rg))
        return self._low

    def sets(self):
        if getattr(self, '_sets', None) is None:
            fs = self.low()['face_set']
            self._sets = [dict(name=f'page{k}', faces=fs == f'page{k}', size=int(self.meta['size']))
                          for k in range(int(self.meta['pages']))]
        return self._sets

    def _page(self, set_name):
        return int(set_name.replace('page', ''))

    def drivers(self, set_name):
        """normal (the shipped, composed one; alpha = coverage) and region; NO base: the audit then evaluates check 1's
        coordinate at the low's point, where the generator evaluates it"""
        if set_name not in self._drv:
            z = np.load(os.path.join(self.run_dir, 'bake', f'page{self._page(set_name)}{self.tag}.npz'))
            self._drv[set_name] = dict(normal=np.asarray(z['normal'], np.float32), region=np.asarray(z['region']),
                                       normal_macro=np.asarray(z['normal_macro'], np.float32),
                                       micro=np.asarray(z['micro'], np.float32))
        return self._drv[set_name]

    def map_path(self, set_name, key):
        return os.path.join(self.run_dir, 'maps', f'{set_name}_{key}.png')

    def load_map(self, set_name, key):
        if (set_name, key) in self.map_override:
            return self.map_override[(set_name, key)]
        if key == 'N':                                   # the high: the bake of the limit alone, encoded as the maps are
            n = self.drivers(set_name)['normal_macro']
            return (np.clip(n[..., :3] * 0.5 + 0.5, 0, 1) * 255.0 + 0.5).astype(np.uint8)
        return super().load_map(set_name, key)

    # ---- the masters' limits and the micro layer's masks (per limit vertex, the generator's own numbers)
    def limit(self, nm):
        if nm not in self._lim:
            m = self.MD[nm]
            lv = BP.limit_level(m, self.b04)
            lim = BP.cached_limit(m, lv, self.run_dir, write=False)
            V = np.asarray(lim.V, np.float64)
            N = lim.vertex_normals()
            side = 1.0 if V[:, 0].mean() >= 0 else -1.0
            M4, D3 = SC.micro_masks(m['region'], nm, V, N, center=np.zeros(3), side_sign=side, sutures=self.sut)
            r = SC.RECIPE[m['region']]
            # (10-31, B9) the cells layer is drawn when its amplitude is set OR the recipe draws granules (cell_mode 5: the
            # cells' amplitude is 0 there and `grain` draws them, at q); on_sheet: the cells are drawn on micro_masks' d
            # (cell_mode 4, B8's flowed sheet), not at q (coordinates() adds that sheet as its own check 1 entry)
            grain = bool(r.get('grain')) and r.get('cell_mode') == 5.0
            draws = np.array([r['pits'][2] > 0, r['setae'][3] > 0, r['groove'] > 0, r['cells'][1] != 0 or grain],
                             np.float32)
            on_sheet = r.get('cell_mode', 0.0) == 4.0 and r['cells'][1] != 0
            F = lim.tris().astype(np.int32)
            self._lim[nm] = dict(V=V, F=F, N=N, M4=M4.astype(np.float32),
                                 D3=D3.astype(np.float32), draws=draws, level=lv,
                                 seed=7 + self.names.index(nm), recipe=r, on_sheet=on_sheet)
            if grain:
                SC.params_full(m['region'], 7 + self.names.index(nm), V, F, N, M4)
                cen = SC.grain_cached(V, F)['census']
                self.notes.append(f'check 1: {nm}\'s granules are drawn at q, each in its own site\'s tangent plane '
                                  f'(cell_mode 5; no sheet): {cen["sites"]:,} sites over {cen["area_mm2"]} mm2 (life), '
                                  f'nearest metric distance / spacing p5-p50-p95 {cen["nn_metric_over_d0_p5_p50_p95"]}, '
                                  f'semi-axes p50 {cen["semi_axes_mm_p50"]} mm, aniso {cen["aniso_p50"]}')
        return self._lim[nm]

    def _wp_mesh(self, nm):
        L = self.limit(nm)
        if 'mesh' not in L:
            L['mesh'] = wp.Mesh(points=wp.array(L['V'].astype(np.float32), dtype=wp.vec3),
                                indices=wp.array(L['F'].ravel(), dtype=wp.int32))
        return L['mesh']

    def texel_masks(self, set_name, G):
        """per inside texel: its master, the micro masks (4) and the setae direction (3) at the nearest limit vertex of
        its own master to its low point"""
        if set_name in self._tex:
            return self._tex[set_name]
        from scipy.spatial import cKDTree
        reg = self.drivers(set_name)['region'][G.ys, G.xs].astype(np.int32)
        m4 = np.zeros((G.n, 4), np.float32)
        d3 = np.zeros((G.n, 3), np.float32)
        for mi in np.unique(reg):
            if mi < 0:
                continue
            nm = self.names[mi]
            L = self.limit(nm)
            sel = np.nonzero(reg == mi)[0]
            _, j = cKDTree(L['V']).query(G.P[sel] * 100.0)
            m4[sel] = L['M4'][j] * L['draws'][None, :]
            d3[sel] = L['D3'][j]
        self._tex[set_name] = dict(reg=reg, m4=m4, d3=d3)
        return self._tex[set_name]

    # ---- zones, places, design
    def zones(self, set_name, G):
        self._G[set_name] = G
        reg = self.drivers(set_name)['region'][G.ys, G.xs].astype(np.int16)
        return reg, {int(k): self.names[int(k)] for k in np.unique(reg) if k >= 0}

    def groups(self, set_name):
        return [dict(name='albedo', key='albedo', kind='loglum'),
                dict(name='coat roughness', key='orm', kind='channel', ch=2),
                dict(name='base roughness', key='orm', kind='channel', ch=1),
                dict(name='relief', key='normal', kind='normal_delta', ref='N')]

    def high_group(self, set_name):
        return dict(name='high', key='N', kind='normal')

    def designed(self, set_name, G):
        """the ventrites' sutures and the metaventral groove: thin grooves along a line by design"""
        T = self.texel_masks(set_name, G)
        return T['m4'][:, 2] > 0.10

    def designed_dirs(self, set_name, G):
        """the setae lie along their direction field (micro_masks' d, projected on the surface) wherever the design plants
        them: a streak along it is the design. (10-28 restart) 'wherever the design plants them' is the relief's own rule,
        an amount over 0 (stag_beetle_sculpt.relief draws a seta at every site with u01 < m[1]; the skin paints its colour
        and roughness at full strength per hair), not over 0.1: the restart thinned the mandibles', femora's, funicles'
        and the venter's glabrous setae into (0, 0.1], and the live audit's first run flagged exactly those as 36 bars
        clusters, all in the albedo and base roughness, none in the relief (sparse hairs keep their colour per hair while
        their height scales with the amount). The core still flags any streak more than high_tol off d"""
        T = self.texel_masks(set_name, G)
        d = T['d3'] - G.N * (T['d3'] * G.N).sum(1, keepdims=True)
        d = AS._unit(d)
        mask = T['m4'][:, 1] > 0.0
        return {g['name']: (d, mask) for g in self.groups(set_name)}

    def places(self, set_name, P):
        G = self._G.get(set_name)
        if G is None:
            return None
        from scipy.spatial import cKDTree
        if not hasattr(G, '_tree'):
            G._tree = cKDTree(G.P)
        _, j = G._tree.query(P)
        z = G.zone[j]
        return np.array([self.MD[self.names[int(k)]]['region'] if k >= 0 else 'none' for k in z])

    def landmarks(self):
        if getattr(self, '_lm', None) is None:
            lm = {}
            for m in self.masters:
                if m['kind'] != 'shell':
                    continue
                for it in m['instances']:
                    V = BP.place(m['low'], it) * 0.01
                    lm[it['name']] = V.mean(0)
            self._lm = lm
        return self._lm

    def renders(self):
        # (10-28 restart) the venter's view by render.basis's own name: it takes named views only, and the direction
        # (0.30, -0.93, 0.20) stopped the first live run in its overlay renders (KeyError), after every check had run
        return [dict(tag='whole', views=('threeq', 'top', 'under'), center=None, span=None)]

    # ---- check 1: the micro layer's coordinate
    def coordinates(self, set_name):
        G = self._G.get(set_name)
        if G is None:
            return []
        from scipy.spatial import cKDTree
        T = self.texel_masks(set_name, G)
        tree = cKDTree(G.P)
        mids = sorted(set(int(x) for x in np.unique(T['reg']) if x >= 0))
        # (10-31, B9) the masters whose cells are drawn on micro_masks' sheet d (cell_mode 4), not at q
        sheet_m = np.zeros(len(self.names), bool)
        for mi in mids:
            sheet_m[mi] = self.limit(self.names[mi])['on_sheet']
        on_sheet = sheet_m[np.clip(T['reg'], 0, None)] & (T['reg'] >= 0)
        # pits, setae, cells: the layers drawn through q (the cells leave it where they are drawn on the sheet)
        w_tex = np.maximum(T['m4'][:, [0, 1]].max(1), T['m4'][:, 3] * (~on_sheet))
        ids = np.zeros(len(self.names), np.uint64)
        for mi in mids:
            ids[mi] = self._wp_mesh(self.names[mi]).id
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
                                                 wp.array((Pn * 100.0).astype(np.float32), dtype=wp.vec3), 5.0, out, ok])
            q = out.numpy().astype(np.float64) * 0.01
            w = np.tile(w_tex[j], 5)
            return xp.asarray(q), xp.asarray(w), xp.asarray(np.ones(n5))
        specs = [dict(name='limit closest point (micro relief)', fn=fn, cell=0.0009,
                      note='the micro relief is a solid pattern at q = the closest limit point to the low\'s point; cell '
                           '0.09 mm at life (the elytral cells, the median pattern scale)')]
        if on_sheet.any():
            w_sheet = T['m4'][:, 3] * on_sheet

            def fn_sheet(P, xp):
                """the sheet d = (u, v) (life mm) interpolated at q on q's own triangle of each sheet master's limit, as
                k_compose reads it; x0.01 into the audit's x10 metres (sref 1: the sheet is laid out in surface millimetres);
                points on other masters keep a constant coordinate with weight 0"""
                Pn = P.get() if hasattr(P, 'get') else np.asarray(P)
                n5 = len(Pn)
                m = n5 // 5
                _, j = tree.query(Pn[:m])
                reg = np.tile(T['reg'][j].astype(np.int32), 5)
                dd = np.zeros((n5, 3), np.float64)
                for mi in np.unique(reg):
                    if mi < 0 or not sheet_m[mi]:
                        continue
                    L = self.limit(self.names[mi])
                    sel = np.nonzero(reg == mi)[0]
                    out = wp.zeros(len(sel), dtype=wp.vec3)
                    ok = wp.zeros(len(sel), dtype=wp.int32)
                    wp.launch(k_closest_d, dim=len(sel), inputs=[self._wp_mesh(self.names[mi]).id,
                                                                 wp.array(L['F'].ravel(), dtype=wp.int32),
                                                                 wp.array(L['D3'], dtype=wp.vec3),
                                                                 wp.array((Pn[sel] * 100.0).astype(np.float32), dtype=wp.vec3),
                                                                 5.0, out, ok])
                    dd[sel] = out.numpy().astype(np.float64)
                return xp.asarray(dd * 0.01), xp.asarray(np.tile(w_sheet[j], 5)), xp.asarray(np.ones(n5))
            specs.append(dict(name='grain sheet (cells drawn on micro_masks d)', fn=fn_sheet, cell=0.0008,
                              note='the cells of cell_mode 4 (B8\'s packed beads) are drawn on the flowed 2D sheet d, not at '
                                   'q: the sheet\'s own differential is the beads\' stretch over their design (the B8 '
                                   'check\'s k04); cell 0.08 mm at life (the beads\' lattice)'))
        return specs

    def coord_breakdown(self, set_name, G, idx):
        T = self.texel_masks(set_name, G)
        reg = T['reg'][idx]
        out = {}
        for r_ in sorted(set(self.MD[self.names[int(k)]]['region'] for k in np.unique(reg) if k >= 0)):
            out[r_] = np.isin(reg, [i for i, nm in enumerate(self.names) if self.MD[nm]['region'] == r_])
        return out

    # ---- check 3: the punctures
    def features(self, set_name):
        if self._feat is None:
            Ps, Ns, Rs, Ks = [], [], [], []
            for nm in self.prim:
                L = self.limit(nm)
                sp, r, depth = L['recipe']['pits']
                if depth <= 0.0 or r <= 0.0 or L['M4'][:, 0].max() <= 0.0:
                    continue
                if L['recipe'].get('pit_mode', 0.0) > 0.5:
                    r = 0.5 * sp                          # one layer: every site within half a spacing makes a pit
                c = np.unique(np.floor(L['V'] / sp).astype(np.int64), axis=0)
                nb = np.array([[a, b, d] for a in (-1, 0, 1) for b in (-1, 0, 1) for d in (-1, 0, 1)], np.int64)
                c = np.unique((c[:, None, :] + nb[None]).reshape(-1, 3), axis=0).astype(np.int32)
                mesh = self._wp_mesh(nm)
                n = len(c)
                op, on, kp = wp.zeros(n, dtype=wp.vec3), wp.zeros(n, dtype=wp.vec3), wp.zeros(n, dtype=wp.int32)
                wp.launch(k_pits, dim=n, inputs=[wp.array(c, dtype=wp.vec3i), float(sp), float(r), int(L['seed']), mesh.id,
                                                 wp.array(L['F'].ravel(), dtype=wp.int32),
                                                 wp.array(L['N'].astype(np.float32), dtype=wp.vec3),
                                                 wp.array(L['M4'], dtype=wp.vec4), op, on, kp])
                k = kp.numpy() > 0
                Ps.append(op.numpy()[k] * 0.01)
                Ns.append(on.numpy()[k])
                Rs.append(np.full(int(k.sum()), r * 0.01, np.float32))
                Ks.append(np.full(int(k.sum()), self.names.index(nm), np.int32))
            self._feat = dict(p=np.concatenate(Ps), n=np.concatenate(Ns), rb=np.concatenate(Rs), kind=np.concatenate(Ks))
            self.notes.append(f'check 3: {len(self._feat["p"])} punctures planted by the relief over '
                              f'{len(set(self._feat["kind"].tolist()))} masters')
        return self._feat

    def plantable(self, set_name, P, N, zone):
        """the design's relative puncture density at P: the density mask of P's own master (the zone) at its nearest
        limit vertex, times whether that master's recipe draws punctures"""
        from scipy.spatial import cKDTree
        out = np.zeros(len(P), np.float32)
        for z in np.unique(zone):
            if z < 0:
                continue
            nm = self.names[int(z)]
            L = self.limit(nm)
            if 'tree' not in L:
                L['tree'] = cKDTree(L['V'])
            sel = np.nonzero(zone == z)[0]
            _, j = L['tree'].query(np.asarray(P)[sel] * 100.0)
            out[sel] = L['M4'][j, 0] * L['draws'][0]
        return out

    def fidelity(self, set_name, G):
        """the replica against what the bake wrote: b07 stored each covered texel's first sub-sample's limit point
        (page 'base'); the replica's q at the texel's centre must land within a texel or so of it on the same master"""
        z = np.load(os.path.join(self.run_dir, 'bake', f'page{self._page(set_name)}{self.tag}.npz'))
        base = np.asarray(z['base'], np.float64)[G.ys, G.xs]
        ok = (base[:, 3] > 0.5) & G.cov_c
        sel = np.nonzero(ok)[0]
        if len(sel) > 200000:
            sel = np.random.default_rng(5).choice(sel, 200000, replace=False)
        spec = self.coordinates(set_name)[0]
        P5 = np.concatenate([G.P[sel]] * 5)
        q, _, _ = spec['fn'](P5, np)
        q = np.asarray(q)[:len(sel)]
        d = np.linalg.norm(q - base[sel, :3], axis=1) * G.px_per_m          # texels
        return dict(texels=int(len(sel)), dist_texels_p50=round(float(np.median(d)), 3),
                    dist_texels_p99=round(float(np.percentile(d, 99)), 3), dist_texels_max=round(float(d.max()), 3),
                    agrees=bool(np.percentile(d, 99) < 1.5))
