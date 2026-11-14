"""The AXOLOTL's side of the streak audit (forge/audit_streaks.py): the pilot bake's run folder (work/bestiary/axolotl/
ax07[_tag]: low.npz, drivers_BODY.npz / drivers_EYE.npz, the maps T_<set>_<key>.png the material pass wrote).

  * sets: BODY (the 2048 pilot page; its faces the baked primaries and the four filament templates at D_REF) and EYE
    (256). The audit's millimetres are x4 millimetres (0.25 mm at life): its scales were set on the octopus's skin
    patches of 2-4 mm, and the axolotl's mottle at x4 is 16 mm apart (spots ~5 mm), so its filters see the pattern.
  * check 1: the generator's coordinate is the texel's BASE point (forge/species/axolotl_skin.py: every pattern is a
    solid function of the block-out's surface point), i.e. the point itself on the surface: q = P, isometric (sref 1),
    the mottle's cell its spacing at x4. What can still collapse is the BASE map itself (the bake's block-out point
    along the low's normal: a concave crease could send a band of texels to one line), which no function of P shows:
    base_collapse() measures it on the drivers directly (the base map's differential across each texel against the hit
    position's), and the runner reports it beside the audit.
  * check 2: every map the material pass wrote: the ground (base colour, log luminance), the ORM's AO and roughness,
    the normal, and each channel of the packs (BODY: MASKS thin / ventral / cover, DISPLAY irid / xantho / speckle;
    not DISPLAY A, the mottle's per-blob id: groups() says why; EYE: its ring / pupil / outer masks); the high that
    explains a streak is the bake's own normal (T_<set>_N.png before the material pass: the pass adds no relief).
    Zones: the material pass's (body, head, mouth, limb, palm, digit, ramus, filament, fin).
  * check 3: none (the axolotl's skin has no planted instance detail: its pores are a texture term to come; the gill
    filaments are a stacked part with their own islands).
"""
import json
import os

import numpy as np

from . import audit_streaks as AS

ZONES = ('body', 'head', 'mouth', 'limb', 'palm', 'digit', 'ramus', 'filament', 'fin', 'hidden')
REGION_ZONE = dict(body_head='head', body_eye='head', body_cap='head', body_mouth='mouth', root='limb', arm='limb',
                   palm='palm', digit='digit', web='digit', ramus='ramus', cap='ramus', filament='filament', fin='fin',
                   eyeball='hidden')


class AxolotlAudit(AS.CreatureAudit):
    name = 'axolotl'

    def __init__(self, run_dir, label=None):
        super().__init__(run_dir, label or f'axolotl AX7 pilot ({os.path.basename(os.path.normpath(run_dir))})')
        L = self.low()
        self.rn = {int(k): v for k, v in json.loads(str(L['region_names'])).items()}
        self.size = [int(v) for v in np.asarray(L['size']).ravel()]
        self.notes.append('the axolotl\'s mm are x4 mm (0.25 mm at life); BODY at ' + str(self.size[0]) + '^2, EYE at '
                          + str(self.size[1]) + '^2')
        self.notes.append('check 1: q = the surface point (axolotl_skin reads the bake\'s base point: its own collapse is '
                          'measured on the drivers, base_collapse, in the runner\'s report)')
        self.notes.append('check 2: the ground, the melanophore cover, the xanthophore and iridophore masks, the '
                          'roughness and the normal; the high = the bake\'s normal')

    def sets(self):
        fs = self.low()['face_set']
        return [dict(name='BODY', faces=fs == 'BODY', size=self.size[0]),
                dict(name='EYE', faces=fs == 'EYE', size=self.size[1])]

    def groups(self, set_name):
        # every map the material pass writes (the AX7 brief, 10-29: "the streak audit on every map"): the base colour,
        # the ORM's AO and roughness, the normal, and each channel of the two mask packs but DISPLAY A, the mottle's
        # per-blob random: an id constant over each cell of the spots' jittered lattice, its borders straight Voronoi
        # edges by construction, which check 2 reads as bars and fans (AX7's one run with it: 718.7 cm2, all borders);
        # nothing renders it today
        g = [dict(name='ground', key='C', kind='loglum'), dict(name='roughness', key='ORM', kind='channel', ch=1),
             dict(name='ao', key='ORM', kind='channel', ch=0), dict(name='normal', key='N', kind='normal')]
        if set_name == 'BODY':
            g += [dict(name='cover', key='M', kind='channel', ch=3), dict(name='thin', key='M', kind='channel', ch=0),
                  dict(name='ventral', key='M', kind='channel', ch=1), dict(name='xantho', key='D', kind='channel', ch=1),
                  dict(name='irid', key='D', kind='channel', ch=0), dict(name='speckle', key='D', kind='channel', ch=2)]
        else:
            g += [dict(name='ring', key='M', kind='channel', ch=0), dict(name='pupil', key='M', kind='channel', ch=1),
                  dict(name='outer', key='M', kind='channel', ch=2)]
        return g

    def high_group(self, set_name):
        return dict(name='high', key='N', kind='normal')

    def zones(self, set_name, G):
        reg = self.drivers(set_name).get('region')
        names = {i: z for i, z in enumerate(ZONES)}
        if reg is None:
            return np.zeros(G.n, np.int16), {0: 'body'}
        r = reg[G.ys, G.xs]
        z = np.array([ZONES.index(REGION_ZONE.get(self.rn.get(int(k), ''), 'body')) for k in range(max(self.rn) + 2)],
                     np.int16)
        return z[np.where(r >= 0, r, len(z) - 1)], names

    def coordinates(self, set_name):
        if set_name != 'BODY':
            return []

        def fn(P, xp):
            n = P.shape[0]
            return P, xp.ones(n), xp.ones(n)
        return [dict(name='the surface point (x4 m)', fn=fn, cell=0.0164,
                     note='axolotl_skin: every pattern a solid function of the block-out point (the mottle 4.1 mm life '
                          'apart = 16.4 mm x4)')]

    def places(self, set_name, P):
        if getattr(self, '_tree', None) is None:
            from scipy.spatial import cKDTree
            L = self.low()
            self._tree = (cKDTree(L['V'][L['F']].mean(1)), L['region'])
        _, ti = self._tree[0].query(P)
        return np.array([self.rn.get(int(r), 'region') for r in self._tree[1][ti]])

    def landmarks(self):
        return dict(snout=(0.0, 0.06, 0.449), eye_L=(0.040, 0.083, 0.410), gills_L=(0.09, 0.12, 0.245),
                    hand_L=(0.13, 0.002, 0.20), foot_L=(0.14, 0.002, 0.05), vent=(0.0, 0.015, -0.085),
                    dorsal_fin=(0.0, 0.12, -0.10), tail_tip=(0.0, 0.04, -0.50))

    def renders(self):
        return [dict(tag='whole', views=('threeq', 'top', 'side'), center=None, span=None),
                dict(tag='head', views=('threeq', 'front'), center=(0.0, 0.08, 0.34), span=0.32)]


def base_collapse(drivers, region_names, step=1):
    """the base map's own collapse (module docstring): per covered texel with covered right and lower neighbours in the
    same region, the base point's differences across the texel (dx, dy) against the hit position's; their singular
    values' ratio (1 round, 0 a collapse) and the smaller's scale against the position's. Returns a dict per region:
    texels, p1 / p50 of the roundness, the share under 0.4 (the audit's coord_aniso), the share magnified 3x"""
    B = np.asarray(drivers['base'], np.float64)
    Pp = np.asarray(drivers['position'], np.float64)
    cov = (drivers['normal'][..., 3] > 0.99) & (B[..., 3] > 0.5)
    reg = drivers['region']
    ok = cov[:-step, :-step] & cov[step:, :-step] & cov[:-step, step:]
    ok &= (reg[:-step, :-step] == reg[step:, :-step]) & (reg[:-step, :-step] == reg[:-step, step:])
    dbx = (B[:-step, step:, :3] - B[:-step, :-step, :3])[ok]
    dby = (B[step:, :-step, :3] - B[:-step, :-step, :3])[ok]
    dpx = (Pp[:-step, step:, :3] - Pp[:-step, :-step, :3])[ok]
    dpy = (Pp[step:, :-step, :3] - Pp[:-step, :-step, :3])[ok]
    # the base's 2 x 2 metric in the position's frame (Gram matrices), its generalised singular values
    Gb = np.stack([np.stack([(dbx * dbx).sum(1), (dbx * dby).sum(1)], -1),
                   np.stack([(dbx * dby).sum(1), (dby * dby).sum(1)], -1)], -2)
    Gp = np.stack([np.stack([(dpx * dpx).sum(1), (dpx * dpy).sum(1)], -1),
                   np.stack([(dpx * dpy).sum(1), (dpy * dpy).sum(1)], -1)], -2)
    det = np.linalg.det(Gp)
    good = det > 1e-24
    Gb, Gp = Gb[good], Gp[good]
    M = np.linalg.solve(Gp, Gb)
    ev = np.sort(np.clip(np.real(np.linalg.eigvals(M)), 0.0, None), axis=1)
    s1, s2 = np.sqrt(ev[:, 1]), np.sqrt(ev[:, 0])
    rnd = s2 / np.maximum(s1, 1e-12)
    r_ = reg[:-step, :-step][ok][good]
    out = {}
    names = {int(k): v for k, v in region_names.items()}
    for rid in np.unique(r_):
        m = r_ == rid
        if m.sum() < 50:
            continue
        out[names.get(int(rid), str(rid))] = dict(texels=int(m.sum()), p1=float(np.percentile(rnd[m], 1)),
                                                  p50=float(np.median(rnd[m])),
                                                  under_0_4=float((rnd[m] < 0.4).mean()),
                                                  magnified_3x=float((s2[m] < 1.0 / 3.0).mean()))
    return out
