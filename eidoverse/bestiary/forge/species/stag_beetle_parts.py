"""THE BEETLE'S PARTS for B5-B8 (the Bestiary lead's round 10-28: the beetle to MATERIAL): every rigid piece of *L. cervus*
B1 as ONE record, gathered from the rounds that built them, in one frame (WORLD, life mm: y = h + the venter's clearance,
+z forward, +x the animal's left; exported x10 in metres).

  head         heads/insect_cage.py (B3h b3h-1): the creased subdivision cage cached in cache_hull/beetle_subd_head_<key>.npz
               (its controls, quads, creases and targets), in the plan frame: + clearance
  mandible     heads/insect_mcage.py (B3h b3h-m7n): build_cage + limit() as mandible_grids does (world, the closed cage at
               the bind: mandible_grids applies g['R'] of the CLOSED geometry, the identity, so the clay's mandibles are
               this cage as built; b04 checks it against the clay); R = the mirror
  eye          NOT CAGED by B4: built here (eye_cage): the clay's REVOLVE (insect.eye_descs: the spherical cap on the head
               margin's outward normal, a fillet, the base plane inside the capsule) as a K 24 revolve cage, 8 ring bands
               and two 6 x 6 quad caps (apex and base), the limit fitted through targets ON the exact revolve
  body         B4 body (species/stag_beetle_cage.py b4-3): scratch_b4_body/cage_<part>_f2.npz (controls, quads, creases,
               the low), plan frame: + clearance; pronotum, venter, scutellum unique; elytron, scape, funicle, lamellae,
               palps L mastered, R the mirror; sleeves_b4_f2.npz: the neck (K 48) and the antennal sleeve (K 12)
  legs         B4 legs (families/arthropod_cage.py b4l-2): build_legs' cache (world); per pair the left segments mastered,
               claw b = claw a turned (the stored copy transform), R = the mirror; 10 sleeves per leg

A MASTER is a piece whose geometry is built (its control cage, quads, creases, its low = the limit at the cage's own
vertices); an INSTANCE is a placed copy V = M (low) + t with M a rotation or the mirror (det < 0: quads reversed, the
vertex numbering kept, so its UVs stack on the master's through the tangent sign: the house budget rule).
Sleeves are OPEN tubes (membranes): their high is the house SHELL (a half thickness about the sleeve's own surface).
"""
import json
import os

import numpy as np

from ..mesh import QuadMesh
from .. import subdiv_sharp as SS
from . import stag_beetle as SB

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
B4_BODY = os.path.join(REPO, 'work', 'bestiary', 'beetle', 'scratch_b4_body')
B4_TAG = '_f2'
MIRROR = np.diag([-1.0, 1.0, 1.0])
LEG_PAIRS = ('fore', 'mid', 'hind')
LEG_SEGS = ('coxa', 'trochanter', 'femur', 'tibia', 'tarsus_1', 'tarsus_2', 'tarsus_3', 'tarsus_4', 'tarsus_5', 'claw_a')
BODY_UNIQUE = ('pronotum', 'venter', 'scutellum')
BODY_PAIRED = ('elytron', 'scape', 'funicle', 'lamella_0', 'lamella_1', 'lamella_2', 'lamella_3', 'palp_max', 'palp_lab')
REGION_OF = dict(head='head', eye='eye', mandible='mandible', scape='antenna', funicle='antenna', lamella_0='antenna',
                 lamella_1='antenna', lamella_2='antenna', lamella_3='antenna', palp_max='mouthparts',
                 palp_lab='mouthparts', pronotum='pronotum', venter='venter', scutellum='scutellum', elytron='elytron',
                 coxa='coxa', trochanter='trochanter', femur='femur', tibia='tibia', tarsus_1='tarsus',
                 tarsus_2='tarsus', tarsus_3='tarsus', tarsus_4='tarsus', tarsus_5='tarsus', claw_a='claw')
# the eye cage (K = 24: four sides of 6 for the quad caps); ring bands from the base rim to the dome's last ring
EYE_CAGE = dict(K=24, cap=6, fillet_rings=2, dome_rings=6, cap_angle=0.36, levels_fit=5)
SLEEVE_HALF = 0.012                  # mm at life: the sleeves' membrane half thickness for their SHELL high [E] (0.24 mm
#                                      at x10, 2.2 texels: a membrane far thinner than the shells' 0.27 mm plate)


def _sharp_dict(pairs, vals):
    return {(int(a), int(b)): float(v) for (a, b), v in zip(np.asarray(pairs).reshape(-1, 2), np.asarray(vals))}


def master(name, region, Q, ctrl, low, sharp, levels_fit, kind='shell', src='', instances=()):
    Q = np.asarray(Q, np.int64)
    used = np.zeros(len(ctrl), bool)
    used[Q.ravel()] = True
    if not used.all():                         # (the mandible: a feature's replaced patch) the unused vertices out
        new = -np.ones(len(ctrl), np.int64)
        new[used] = np.arange(int(used.sum()))
        Q = new[Q]
        sharp = {(int(new[a]), int(new[b])): s for (a, b), s in sharp.items() if used[a] and used[b]}
        ctrl, low = np.asarray(ctrl)[used], np.asarray(low)[used]
    return dict(name=name, region=region, region_id=SB.REGION_ID[region], kind=kind, Q=Q,
                ctrl=np.asarray(ctrl, np.float64), low=np.asarray(low, np.float64), sharp=dict(sharp),
                levels_fit=int(levels_fit), src=src, instances=list(instances))


def inst(name, side, M=None, t=None):
    M = np.eye(3) if M is None else np.asarray(M, np.float64)
    t = np.zeros(3) if t is None else np.asarray(t, np.float64)
    return dict(name=name, side=side, M=M, t=t, flip=bool(np.linalg.det(M) < 0))


def place(V, it):
    return np.asarray(V, np.float64) @ it['M'].T + it['t']


def place_Q(Q, it):
    return np.asarray(Q)[:, ::-1].copy() if it['flip'] else np.asarray(Q)


# ============================================================================================ the eye (not caged by B4)
def eye_cage(spec, clear):
    """the left compound eye as a closed K 24 revolve cage on the clay's own REVOLVE (insect.eye_descs: centre C, axis a,
    profile(0) = base plane, fillet, dome to the apex). Rings: the base rim, EYE_CAGE fillet_rings through the fillet, the
    dome's rings at equal angle to cap_angle (radians from the axis), then a 6 x 6 quad cap at the apex and one on the base
    disk; every target ON the exact surface (a concentric square-to-disk map for the caps). Returns (V targets (n, 3), Q,
    info) in world life mm"""
    from ..heads import insect as HD
    descs, info = HD.eye_descs(spec, clear)
    C, a, R = np.asarray(info['center'], np.float64), np.asarray(info['axis'], np.float64), float(info['radius'])
    yb = float(info['y_base'])
    rf = HD.EYE_FILLET
    e1 = np.cross(a, [0.0, 1.0, 0.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(a, e1)
    ec = EYE_CAGE
    K, nc = ec['K'], ec['cap']
    th = 2.0 * np.pi * np.arange(K) / K
    # the profile (r, y): the fillet circle (centre (cx, yb + rf), radius rf) meets the dome where the line from C does
    cy = yb + rf
    cx = np.sqrt(max((R - rf) ** 2 - cy ** 2, 1e-12))
    a_s = np.arctan2(cx, cy)                         # the dome angle where the fillet ends
    prof = [(cx, yb)]                                # the base rim (the fillet's start, on the base plane)
    for k in range(1, ec['fillet_rings'] + 1):
        q = -0.5 * np.pi + (0.5 * np.pi - a_s + 0.5 * np.pi) * k / (ec['fillet_rings'] + 1)
        prof.append((cx + rf * np.cos(q), cy + rf * np.sin(q)))
    for k in range(ec['dome_rings']):
        ph = a_s + (ec['cap_angle'] - a_s) * k / (ec['dome_rings'] - 1)
        prof.append((R * np.sin(ph), R * np.cos(ph)))
    pt = lambda r, y, t_: C + a * y + r * (np.cos(t_) * e1 + np.sin(t_) * e2)   # noqa: E731
    V = np.concatenate([np.array([pt(r, y, t_) for t_ in th]) for r, y in prof])
    nr = len(prof)
    rid = lambda i, k: i * K + (k % K)                 # noqa: E731
    Q = [[rid(i, k), rid(i, k + 1), rid(i + 1, k + 1), rid(i + 1, k)] for i in range(nr - 1) for k in range(K)]

    def cap(ring, top):
        """a (nc+1)^2 grid whose boundary is the ring (K = 4 nc points, counter-clockwise seen from outside along the
        axis for the top); interior targets on the surface by the concentric square-to-disk map"""
        nonlocal V
        g = -np.ones((nc + 1, nc + 1), np.int64)
        # the boundary walk counter-clockwise about the axis from (u, v) = (1, 0), the ring's vertex 0 at angle 0 (e1):
        # under the concentric map the boundary points sit at 360 / K degree steps, as the ring's
        h = nc // 2
        side = [(nc, j) for j in range(h, nc)] + [(i, nc) for i in range(nc, 0, -1)] + [(0, j) for j in range(nc, 0, -1)] \
            + [(i, 0) for i in range(0, nc)] + [(nc, j) for j in range(0, h)]
        assert len(side) == K, (len(side), K)
        for k, (i, j) in enumerate(side):
            g[i, j] = ring[k]
        new = []
        for i in range(1, nc):
            for j in range(1, nc):
                u, v = 2.0 * i / nc - 1.0, 2.0 * j / nc - 1.0        # [-1, 1]^2, (u, v) ~ (cos, sin) directions
                if abs(u) >= abs(v):
                    rr, ang = abs(u), (np.pi / 4) * (v / u) if u != 0 else 0.0
                    ang = ang if u > 0 else ang + np.pi
                else:
                    rr, ang = abs(v), np.pi / 2 - (np.pi / 4) * (u / v)
                    ang = ang if v > 0 else ang + np.pi
                new.append((i, j, rr, ang))
        pts = []
        for i, j, rr, ang in new:
            if top:
                ph = ec['cap_angle'] * rr
                pts.append(pt(R * np.sin(ph), R * np.cos(ph), ang))
            else:
                pts.append(pt(cx * rr, yb, ang))
            g[i, j] = len(V) + len(pts) - 1
        V = np.concatenate([V, np.array(pts)])
        out = []
        for i in range(nc):
            for j in range(nc):
                q = [g[i, j], g[i + 1, j], g[i + 1, j + 1], g[i, j + 1]]
                out.append(q if top else q[::-1])
        return out
    Q += cap([rid(nr - 1, k) for k in range(K)], True)
    Q += cap([rid(0, k) for k in range(K)], False)
    Q = np.array(Q, np.int64)
    # outward: the signed volume positive
    vol = np.sum(np.einsum('ij,ij->i', V[Q[:, 0]], np.cross(V[Q[:, 1]] - V[Q[:, 0]], V[Q[:, 2]] - V[Q[:, 0]])))
    if vol < 0:
        Q = Q[:, ::-1].copy()
    return V, Q, dict(C=C, a=a, R=R, y_base=yb, rf=rf, cx=cx, a_s=a_s)


def eye_surface_error(V, info):
    """|distance to the exact revolve| per point: the dome sphere, the fillet torus, the base disk (the nearest)"""
    C, a, R = info['C'], info['a'], info['R']
    d = V - C
    y = d @ a
    r = np.linalg.norm(d - np.outer(y, a), axis=1)
    e_dome = np.abs(np.sqrt(r * r + y * y) - R)
    ang = np.arctan2(r, y)
    e_dome = np.where(ang <= info['a_s'] + 1e-6, e_dome, np.inf)
    fc = np.array([info['cx'], info['y_base'] + info['rf']])
    e_fil = np.abs(np.hypot(r - fc[0], y - fc[1]) - info['rf'])
    e_base = np.where(r <= info['cx'] + 1e-6, np.abs(y - info['y_base']), np.inf)
    return np.minimum(np.minimum(e_dome, e_fil), e_base)


# ============================================================================================ gather
def gather(spec=None, log=print, with_mandible=True):
    """every master with its instances (module docstring). Returns dict(masters, clear, sources)"""
    from ..families import arthropod as AR
    from ..families import arthropod_cage as AC
    from ..heads import insect_cage as IC
    from ..heads import insect_mcage as MC
    spec = SB.SPEC if spec is None else spec
    chain = AR.rest_chain(spec)
    clear = float(chain['clearance'])
    up = np.array([0.0, clear, 0.0])
    masters, sources = [], {}
    # ---- the head (B3h)
    hk = IC.head_key(spec)
    hp = os.path.join(IC.CACHE, f'beetle_subd_head_{hk}.npz')
    assert os.path.exists(hp), f'the B3h head cache {hp} is missing (insect_cage.head_volume builds it)'
    Z = np.load(hp, allow_pickle=False)
    masters.append(master('head', 'head', Z['cage_Q'], Z['cage_V'] + up, Z['targets'] + up,
                          _sharp_dict(Z['sharp_pairs'], Z['sharp_vals']), IC.LEVELS['fit'], src=os.path.relpath(hp, REPO),
                          instances=[inst('head', 'M')]))
    sources['head'] = dict(file=os.path.relpath(hp, REPO), version=IC.VERSION)
    log(f'[parts] head: {len(Z["cage_Q"])} quads, {len(Z["sharp_pairs"])} creases (insect_cage {IC.VERSION}, {hk})')
    # ---- the mandible (B3h m7n): the cage as mandible_grids builds it (world, the closed cage; bind = closed, R = I)
    if with_mandible:
        mesh, arm, sharp, recs, g = MC.build_cage(spec, clear, log=lambda s: None)
        lim, V0, res = MC.limit(mesh, sharp, MC.MCAGE['levels'])
        Rb, hinge = g['R'], g['hinge']
        tf = lambda P: hinge + (np.asarray(P) - hinge) @ Rb.T     # noqa: E731
        masters.append(master('mandible', 'mandible', mesh.Q, tf(V0), tf(mesh.V), sharp, MC.MCAGE['levels'] + 1,
                              src=f'insect_mcage {MC.VERSION}',
                              instances=[inst('mandible_L', 'L'), inst('mandible_R', 'R', MIRROR)]))
        sources['mandible'] = dict(version=MC.VERSION, fit_residual=float(res), R_is_identity=bool(np.allclose(Rb, np.eye(3))))
        log(f'[parts] mandible: {len(mesh.Q)} quads, {len(sharp)} creases, fit residual {res:.1e} (insect_mcage '
            f'{MC.VERSION}; the bind rotation {"the identity" if np.allclose(Rb, np.eye(3)) else "applied"})')
    # ---- the eye (built here)
    eV, eQ, einfo = eye_cage(spec, clear)
    em = QuadMesh(eV, eQ)
    ectrl, eres = SS.fit_controls(em, {}, eV, EYE_CAGE['levels_fit'])
    masters.append(master('eye', 'eye', eQ, ectrl, eV, {}, EYE_CAGE['levels_fit'], src='stag_beetle_parts.eye_cage',
                          instances=[inst('eye_L', 'L'), inst('eye_R', 'R', MIRROR)]))
    sources['eye'] = dict(K=EYE_CAGE['K'], quads=int(len(eQ)), fit_residual=float(eres), info={k: (v.tolist() if isinstance(
        v, np.ndarray) else float(v)) for k, v in einfo.items()})
    log(f'[parts] eye: built here, {len(eQ)} quads (K {EYE_CAGE["K"]}), fit residual {eres:.1e}')
    # ---- the body (B4 body, f2)
    for nm in BODY_UNIQUE + BODY_PAIRED:
        side = '' if nm in BODY_UNIQUE else '_L'
        p = os.path.join(B4_BODY, f'cage_{nm}{side}{B4_TAG}.npz')
        Z = np.load(p, allow_pickle=False)
        ins = [inst(nm, 'M')] if nm in BODY_UNIQUE else [inst(f'{nm}_L', 'L'), inst(f'{nm}_R', 'R', MIRROR)]
        masters.append(master(nm, REGION_OF[nm], Z['quads'], Z['controls'] + up, Z['low_V'] + up,
                              _sharp_dict(Z['sharp_pairs'], Z['sharp_vals']), 5, src=os.path.relpath(p, REPO),
                              instances=ins))
    log(f'[parts] body: {len(BODY_UNIQUE) + len(BODY_PAIRED)} masters from B4 body {B4_TAG}')
    S = np.load(os.path.join(B4_BODY, f'sleeves_b4{B4_TAG}.npz'), allow_pickle=False)
    for nm, ins in (('neck', [inst('sleeve_neck', 'M')]),
                    ('antenna_L', [inst('sleeve_antenna_L', 'L'), inst('sleeve_antenna_R', 'R', MIRROR)])):
        V = S[f'{nm}__V'] + up
        masters.append(master(f'sleeve_{nm.split("_")[0]}', 'membrane', S[f'{nm}__Q'], V, V, {}, 0, kind='sleeve',
                              src=f'sleeves_b4{B4_TAG}.npz', instances=ins))
        masters[-1]['graft'] = True                 # the neck's and the antenna's graft rings (B4 body: their records)
    # ---- the legs (B4 legs b4l-2)
    legs = AC.build_legs(spec, chain, log=lambda s: None)
    sources['legs'] = dict(key=legs['key'], path=os.path.relpath(legs['path'], REPO), version=AC.VERSION)
    for pair in LEG_PAIRS:
        segs = legs['pairs'][pair]
        c = pair[0]
        for nm in LEG_SEGS:
            s_ = segs[nm]
            ins = [inst(f'{nm}_{c}_L', 'L'), inst(f'{nm}_{c}_R', 'R', MIRROR)]
            if nm == 'claw_a':
                b = segs['claw_b']
                Rb, Ob = np.asarray(b['copy_R'], np.float64), np.asarray(b['copy_origin'], np.float64)
                tb = Ob - Ob @ Rb.T                       # V_b = O + (V_a - O) R^T
                ins += [inst(f'claw_b_{c}_L', 'L', Rb, tb), inst(f'claw_b_{c}_R', 'R', MIRROR @ Rb, tb @ MIRROR.T)]
            masters.append(master(f'{nm}_{c}', REGION_OF[nm], s_['Q'], s_['ctrl'], s_['V'], s_['sharp'], AC.LEVELS['fit'],
                                  src=f'b4_legs {legs["key"]}', instances=ins))
        for i, sl in enumerate(legs['sleeves'][pair]):
            masters.append(master(f'sleeve_{c}{i}', 'membrane', sl['Q'], sl['V'], sl['V'], {}, 0, kind='sleeve',
                                  src=f'b4_legs {legs["key"]} sleeve {i} ({sl.get("name", "")})',
                                  instances=[inst(f'sleeve_{c}{i}_L', 'L'), inst(f'sleeve_{c}{i}_R', 'R', MIRROR)]))
            masters[-1]['graft'] = bool(sl.get('graft', False))
            masters[-1]['axis'] = np.asarray(sl['axis'], np.float64)
    log(f'[parts] legs: {3 * len(LEG_SEGS)} segment masters + {sum(len(legs["sleeves"][p]) for p in LEG_PAIRS)} sleeves '
        f'(b4l-2 {legs["key"]})')
    return dict(masters=masters, clear=clear, sources=sources, legs_claw_b={p: legs['pairs'][p]['claw_b']['V']
                                                                             for p in LEG_PAIRS})


# ============================================================================================ limits and lows
def limit_mesh(m, levels):
    """the master's HIGH limit surface at `levels` (QuadMesh, world life mm); a sleeve is its own quads (no subdivision)"""
    if m['kind'] == 'sleeve':
        return QuadMesh(m['ctrl'], m['Q'])
    lim, _, _, _ = SS.subdivide(QuadMesh(m['ctrl'], m['Q']), m['sharp'], levels)
    return lim


def limit_level(m, b04_masters):
    """the HIGH's level for a master (b07's rule): L6 where an L5 edge passes 0.5 mm at x10 (b04's report), else L5
    (a sleeve carries 5 in its name and key but is never subdivided: its high is its own quads)"""
    return 6 if (m['kind'] == 'shell' and b04_masters[m['name']]['L5_edge_mm_x10'][1] > 0.5) else 5


def limit_key(m, lv):
    """the limit cache's key: the master's cage, creases, level and kind (b07 wrote its cache with this key)"""
    import hashlib
    return hashlib.sha1(m['ctrl'].tobytes() + m['Q'].tobytes() + repr(sorted(m['sharp'].items())).encode() +
                        str(lv).encode() + m['kind'].encode()).hexdigest()[:16]


def cached_limit(m, lv, out_dir, write=True):
    """the master's limit at level lv (life mm) from out_dir/limits/<name>_L<lv>_<key>.npz (b07's cache: the exact
    surface the bake baked), computed and cached when missing (write=False: computed, not written)"""
    p = os.path.join(out_dir, 'limits', f'{m["name"]}_L{lv}_{limit_key(m, lv)}.npz')
    if os.path.exists(p):
        Z = np.load(p)
        return QuadMesh(Z['V'], Z['Q'])
    lim = limit_mesh(m, lv) if m['kind'] == 'shell' else limit_mesh(m, 0)
    if write:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        np.savez(p, V=lim.V, Q=lim.Q)
    return lim


def low_check(m):
    """|A ctrl - low| max: the stored low against the limit at the cage's own vertices (A = the fit's limit operator)"""
    if m['kind'] == 'sleeve':
        return 0.0
    A, _ = SS.limit_operator(QuadMesh(m['ctrl'], m['Q']), m['sharp'], m['levels_fit'])
    return float(np.abs(A @ m['ctrl'] - m['low']).max())


def sleeve_meta(spec=None):
    """{sleeve master name: (graft, axis or None)} from the B4 legs cache (its meta's graft flags) and the body's two graft
    sleeves (the neck, the antenna): for a parts.npz written before the masters carried them"""
    from ..families import arthropod as AR
    from ..families import arthropod_cage as AC
    spec = SB.SPEC if spec is None else spec
    legs = AC.build_legs(spec, AR.rest_chain(spec), log=lambda s: None)
    out = {'sleeve_neck': (True, None), 'sleeve_antenna': (True, None)}
    for pair in LEG_PAIRS:
        for i, sl in enumerate(legs['sleeves'][pair]):
            out[f'sleeve_{pair[0]}{i}'] = (bool(sl.get('graft', False)), np.asarray(sl['axis'], np.float64))
    return out


def save(path, G):
    """the gathered masters as one npz (arrays) + json (the rest)"""
    Z, meta = {}, dict(clear=G['clear'], sources=G['sources'], masters=[])
    for i, m in enumerate(G['masters']):
        p = f'm{i:03d}_'
        Z[p + 'Q'], Z[p + 'ctrl'], Z[p + 'low'] = m['Q'], m['ctrl'], m['low']
        Z[p + 'sp'] = np.array(list(m['sharp'].keys()), np.int64).reshape(-1, 2)
        Z[p + 'sv'] = np.array(list(m['sharp'].values()), np.float64)
        for j, it in enumerate(m['instances']):
            Z[p + f'i{j}_M'], Z[p + f'i{j}_t'] = it['M'], it['t']
        if m.get('axis') is not None:
            Z[p + 'axis'] = m['axis']
        meta['masters'].append({k: m[k] for k in ('name', 'region', 'region_id', 'kind', 'levels_fit', 'src')} |
                               dict(graft=bool(m.get('graft', False)),
                                    instances=[dict(name=it['name'], side=it['side'], flip=it['flip'])
                                               for it in m['instances']]))
    Z['meta'] = np.array(json.dumps(meta))
    np.savez_compressed(path, **Z)


def load(path):
    Z = np.load(path, allow_pickle=False)
    meta = json.loads(str(Z['meta']))
    out = []
    for i, mm in enumerate(meta['masters']):
        p = f'm{i:03d}_'
        ins = [dict(it, M=Z[p + f'i{j}_M'], t=Z[p + f'i{j}_t']) for j, it in enumerate(mm['instances'])]
        out.append(dict(mm, Q=Z[p + 'Q'], ctrl=Z[p + 'ctrl'], low=Z[p + 'low'],
                        sharp=_sharp_dict(Z[p + 'sp'], Z[p + 'sv']), instances=ins,
                        axis=Z[p + 'axis'] if (p + 'axis') in Z.files else None))
    return dict(masters=out, clear=meta['clear'], sources=meta['sources'])
