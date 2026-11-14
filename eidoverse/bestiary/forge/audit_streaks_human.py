"""The HUMAN's side of the streak audit (forge/audit_streaks.py): H3's bake run folder (work/bestiary/human/h3/bake/<sex>:
low.npz, drivers_HEAD.npz / drivers_BODY.npz, the maps T_<set>_<key>.png that h3_bake.py wrote). Step runner:
work/bestiary/human/h3/h3_audit.py.

  * sets: HEAD and BODY (4096 each; their faces the baked primaries: the right limbs share the left's texels).
  * check 1: the generator's coordinate is the texel's surface point. The T tier (human_sculpt: pores, the primary
    lines, the lip lines) is a solid function of the HIGH's hit point in millimetres, which h3_bake stores as the
    drivers' 'base' (the house bake's own block-out point means nothing on a mesh field): q = P, isometric (sref 1), the
    pores' lattice ~0.9 mm and the lines' 0.85 mm its cell. What could still collapse is the hit map itself (a band of
    texels sent to one line of the high): the runner measures it on the drivers (audit_streaks_axolotl.base_collapse
    against the position: identical here, so 1 by construction) and check 2 sees its effect in the maps.
  * check 2: every map the bake wrote: the composed normal N, the macro normal (the high alone: what explains a streak),
    AO, cavity, thickness, curvature and nlen; zoned by the islands' classes (face, scalp, ear, neck, mouth, lid,
    nostril; trunk, limb, hand, foot, nail).
  * check 3: none (no planted instances: the pores are a texture term on the HEAD, the body's are the runtime's).
"""
import json
import os

import numpy as np

from . import audit_streaks as AS

ZONES = ('face', 'scalp', 'ear', 'neck', 'mouth', 'lid', 'nostril', 'trunk', 'limb', 'hand', 'foot', 'nail', 'other')


class HumanAudit(AS.CreatureAudit):
    name = 'human'

    def __init__(self, run_dir, uv_json, label=None):
        super().__init__(run_dir, label or f'human H3 bake ({os.path.basename(os.path.normpath(run_dir))})')
        L = self.low()
        self.rn = {int(k): v for k, v in json.loads(str(L['region_names'])).items()}
        self.set_names = [str(s) for s in np.asarray(L['sets']).ravel()]
        self.size = dict(zip(self.set_names, [int(v) for v in np.asarray(L['size']).ravel()]))
        with open(uv_json, encoding='utf-8') as f:
            self.uvm = json.load(f)
        self.cls = {i: isl['cls'] for i, isl in enumerate(self.uvm['islands'])}
        self.notes.append(f'the human\'s mm are life mm; sets {self.size}')
        self.notes.append('check 1: q = the surface point (human_sculpt\'s T tier reads the high\'s hit, stored as the '
                          'drivers\' base)')
        self.notes.append('check 2: N, the macro normal, AO, cavity, thickness, curvature, nlen; the high = the macro bake')

    def sets(self):
        fs = self.low()['face_set']
        return [dict(name=s, faces=fs == s, size=self.size[s]) for s in self.set_names]

    def groups(self, set_name):
        out = [dict(name='normal', key='N', kind='normal'), dict(name='ao', key='ao', kind='channel', ch=0),
               dict(name='cavity', key='cavity', kind='channel', ch=0),
               dict(name='thickness', key='thickness', kind='channel', ch=0),
               dict(name='curvature', key='curvature', kind='channel', ch=0),
               dict(name='nlen', key='nlen', kind='channel', ch=0)]
        if os.path.exists(os.path.join(self.run_dir, f'T_{set_name}_pore.png')):        # (H3b) the pores' colour map, the HEAD's
            out.append(dict(name='pore', key='pore', kind='channel', ch=0))
        return out

    def high_group(self, set_name):
        return dict(name='high', key='Nmacro', kind='normal')

    def zones(self, set_name, G):
        reg = self.drivers(set_name).get('region')
        names = {i: z for i, z in enumerate(ZONES)}
        if reg is None:
            return np.zeros(G.n, np.int16), {0: 'face'}
        r = reg[G.ys, G.xs]
        lut = np.array([ZONES.index(self.cls.get(k, 'other')) if self.cls.get(k, 'other') in ZONES else len(ZONES) - 1
                        for k in range(max(self.cls) + 2)], np.int16)
        return lut[np.where(r >= 0, r, len(lut) - 1)], names

    def coordinates(self, set_name):
        def fn(P, xp):
            n = P.shape[0]
            return P, xp.ones(n), xp.ones(n)
        cell = 0.0009 if set_name == 'HEAD' else 0.003
        return [dict(name='the surface point (m)', fn=fn, cell=cell,
                     note='human_sculpt\'s T tier: a solid function of the high\'s hit point (the pores ~0.9 mm apart)')]

    def places(self, set_name, P):
        if getattr(self, '_tree', None) is None:
            from scipy.spatial import cKDTree
            L = self.low()
            self._tree = (cKDTree(L['V'][L['F']].mean(1)), L['region'])
        _, ti = self._tree[0].query(P)
        return np.array([self.rn.get(int(r), 'region').split('#')[0] for r in self._tree[1][ti]])

    def landmarks(self):
        L = self.low()
        V, F, reg = L['V'], L['F'], L['region']
        out = {}
        for nm in ('face', 'ear_L', 'ear_R', 'scalp_L', 'neck', 'trunk_up_F', 'trunk_up_B', 'hand_L', 'foot_L',
                   'thigh_L', 'uparm_L'):
            ids = [k for k, v in self.rn.items() if v == nm]
            if ids:
                m = np.isin(reg, ids)
                if m.any():
                    out[nm] = tuple(V[F[m]].reshape(-1, 3).mean(0).tolist())
        fm = np.isin(reg, [k for k, v in self.rn.items() if v == 'face'])
        if fm.any():
            P = V[F[fm]].reshape(-1, 3)
            out['nose_tip'] = tuple(P[np.argmax(P[:, 2])].tolist())
        return out

    def renders(self):
        L = self.low()
        V = L['V']
        hc = V[V[:, 1] > np.percentile(V[:, 1], 90)].mean(0)
        return [dict(tag='whole', views=('front', 'back', 'threeq'), center=None, span=None),
                dict(tag='head', views=('front', 'threeq', 'side'), center=tuple(hc.tolist()), span=0.30)]
