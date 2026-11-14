"""H4 (the rig builder, 11-01; HUMAN_PLAN §4.1, §4.5): THE HUMAN'S SKELETON, regressed from the shape.

THE JOINTS (94 body + face basics, §4.1's table): root, pelvis, spine_01..05, neck_01..02, head; clavicle, upperarm,
lowerarm, hand; per hand 4 metacarpals and 15 phalanges; thigh, calf, foot, ball; two twist joints in each long bone;
eight volume helpers (shoulder, elbow, wrist, knee: their drivers are records the runtime reads, inert until it does);
eyes, jaw, three tongue joints. Names are the UE mannequin's stems with the house's side suffix (upperarm_L, thigh_R:
DESIGN.md's side rule), so the VRM map and later clip retargeting read them through one fixed table (VRM below).

WHERE THEY COME FROM (each sex its own skeleton, §4.1):
  * the BODY's joints are MakeHuman's own joint cubes (the MPFB2 core assets, CC0: data/rigs/standard/rig.*.json name
    the cube each bone's head sits on; the cubes are hm08 helper geometry that MakeHuman's phenotype targets carry, so
    on the sex's solved phenotype (h3/ref/pheno_<sex>.npz, the body's own reference) they sit where MakeHuman's artists
    put the joints inside that body). The spine's five from MakeHuman's four spine cubes (spine_02 midway); the
    metacarpals' bases from its hand-2 / hand-3 cubes, the phalanges from finger-n-1..3 (MCP, PIP, DIP), the thumb's
    finger-1-1..3 (CMC, MCP, IP);
  * the HEAD's are GNM's (Apache-2.0: its template joints plus the identity basis, at the sex's conditioned coefficients
    and H3's placement): neck_01 GNM's 'neck', head GNM's 'head', neck_02 two thirds of the way up between them (the K 48
    neck ring, the HEAD | BODY seam, lies at their midpoint: neck_01 under it, neck_02 over it, §6.2); the eyes at the
    globes' centres (the eye parts' own nodes: the eyeball sits there by rule, §3.3); the jaw at the temporomandibular
    joints, 11 mm in front of the tragions and 7 mm under them (the condyle), on the midline; the tongue's three on the
    tongue mesh's long axis at 20 / 50 / 80 % from its root;
  * twists at 1/3 and 2/3 of their bone (the lower arm's first twist at 3/4, near the wrist, where the forearm turns);
    helpers off their joint's outer side (the elbow's behind the olecranon, the knee's over the patella).
THE REGRESSOR (§4.1: "joints are regressed from cage vertices"; dV_low = M dV_cage makes it linear in identity): each
joint is an affine combination of the LOW's vertices round it (a shell: the vertices within 1.7x its distance to the
skin, 12 to 160 of the nearest), weights solved on BOTH sexes at once (least squares on the two positions, a light pull
toward the shell's uniform mean, sum 1: closed form), so H5's identities move their joints with their shape. Its
residual on the baselines is printed and gated (< 1 mm).
THE REST POSES: the bind is H3's A-pose (the LOW as built); the VRM view's rest is a T-pose (characters.md:19), the arms
along +-X, palms down, fingers straight, the legs plumb, every joint's rest rotation the identity (H0 probe 2's stub
convention, which three-vrm 3.5.2 loaded and the controller walked). tpose() gives each joint's world rotation A -> T;
the skinning of the A-pose weights carries the mesh, its normals and its tangents there (§4.5).

    joint_table() -> list of dict(name, parent, vrm, kind, side)
    reference(sex, ...) -> {name: (3,) mm} on the A-pose bind
    fit_regressor(lows, refs, names) -> (scipy CSR (J, n), residuals)
    tpose(J, table) -> {name: 3x3 world rotation A -> T}
"""
import json
import os

import numpy as np

VERSION = 'h4-skeleton-1'
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
MH = os.path.join(ROOT, 'work', 'bestiary', 'research', 'human_web', 'makehuman_mpfb2', 'data')
FINGERS = (('thumb', 1), ('index', 2), ('middle', 3), ('ring', 4), ('pinky', 5))
VRM_FINGER = dict(thumb='Thumb', index='Index', middle='Middle', ring='Ring', pinky='Little')


def joint_table():
    """the joints in parent-first order: dict(name, parent, vrm (VRM 1.0 humanBone or None), kind, side)"""
    T = []

    def add(name, parent, vrm=None, kind='body', side='M'):
        T.append(dict(name=name, parent=parent, vrm=vrm, kind=kind, side=side))
    add('root', None, None, 'root')
    add('pelvis', 'root', 'hips')
    add('spine_01', 'pelvis', 'spine')
    add('spine_02', 'spine_01')
    add('spine_03', 'spine_02', 'chest')
    add('spine_04', 'spine_03')
    add('spine_05', 'spine_04', 'upperChest')
    add('neck_01', 'spine_05', 'neck')
    add('neck_02', 'neck_01')
    add('head', 'neck_02', 'head')
    for sd in ('L', 'R'):
        side = 'left' if sd == 'L' else 'right'
        add(f'eye_{sd}', 'head', f'{side}Eye', 'face', sd)
    add('jaw', 'head', 'jaw', 'face')
    add('tongue_01', 'jaw', None, 'face')
    add('tongue_02', 'tongue_01', None, 'face')
    add('tongue_03', 'tongue_02', None, 'face')
    for sd in ('L', 'R'):
        side = 'left' if sd == 'L' else 'right'
        add(f'clavicle_{sd}', 'spine_05', f'{side}Shoulder', side=sd)
        add(f'upperarm_{sd}', f'clavicle_{sd}', f'{side}UpperArm', side=sd)
        add(f'upperarm_twist_01_{sd}', f'upperarm_{sd}', None, 'twist', sd)
        add(f'upperarm_twist_02_{sd}', f'upperarm_{sd}', None, 'twist', sd)
        add(f'lowerarm_{sd}', f'upperarm_{sd}', f'{side}LowerArm', side=sd)
        add(f'lowerarm_twist_01_{sd}', f'lowerarm_{sd}', None, 'twist', sd)
        add(f'lowerarm_twist_02_{sd}', f'lowerarm_{sd}', None, 'twist', sd)
        add(f'hand_{sd}', f'lowerarm_{sd}', f'{side}Hand', side=sd)
        for fn, k in FINGERS:
            if fn == 'thumb':
                add(f'thumb_01_{sd}', f'hand_{sd}', f'{side}ThumbMetacarpal', side=sd)
                add(f'thumb_02_{sd}', f'thumb_01_{sd}', f'{side}ThumbProximal', side=sd)
                add(f'thumb_03_{sd}', f'thumb_02_{sd}', f'{side}ThumbDistal', side=sd)
            else:
                add(f'{fn}_metacarpal_{sd}', f'hand_{sd}', None, side=sd)
                add(f'{fn}_01_{sd}', f'{fn}_metacarpal_{sd}', f'{side}{VRM_FINGER[fn]}Proximal', side=sd)
                add(f'{fn}_02_{sd}', f'{fn}_01_{sd}', f'{side}{VRM_FINGER[fn]}Intermediate', side=sd)
                add(f'{fn}_03_{sd}', f'{fn}_02_{sd}', f'{side}{VRM_FINGER[fn]}Distal', side=sd)
        add(f'helper_shoulder_{sd}', f'clavicle_{sd}', None, 'helper', sd)
        add(f'helper_elbow_{sd}', f'upperarm_{sd}', None, 'helper', sd)
        add(f'helper_wrist_{sd}', f'lowerarm_{sd}', None, 'helper', sd)
    for sd in ('L', 'R'):
        side = 'left' if sd == 'L' else 'right'
        add(f'thigh_{sd}', 'pelvis', f'{side}UpperLeg', side=sd)
        add(f'thigh_twist_01_{sd}', f'thigh_{sd}', None, 'twist', sd)
        add(f'thigh_twist_02_{sd}', f'thigh_{sd}', None, 'twist', sd)
        add(f'calf_{sd}', f'thigh_{sd}', f'{side}LowerLeg', side=sd)
        add(f'calf_twist_01_{sd}', f'calf_{sd}', None, 'twist', sd)
        add(f'calf_twist_02_{sd}', f'calf_{sd}', None, 'twist', sd)
        add(f'foot_{sd}', f'calf_{sd}', f'{side}Foot', side=sd)
        add(f'ball_{sd}', f'foot_{sd}', f'{side}Toes', side=sd)
        add(f'helper_knee_{sd}', f'thigh_{sd}', None, 'helper', sd)
    return T


def mh_cubes(Vref):
    """MakeHuman's joint cubes (vertex-group means) on all of hm08's vertices (the phenotype's 19,158, mm)"""
    g = json.load(open(os.path.join(MH, 'mesh_metadata', 'basemesh_vertex_groups.json'), encoding='utf-8'))
    out = {}
    for k, spec in g.items():
        if not k.startswith('joint-'):
            continue
        ids = []
        for r in spec:
            ids += list(range(r[0], r[1] + 1)) if isinstance(r, list) else [r]
        out[k[6:]] = np.asarray(Vref, np.float64)[ids].mean(0)
    return out


def section_centroid(V, F, y, xmin):
    """the centroid of the skin's section by the plane at height y, on the part with x > xmin (a leg's): the segments'
    midpoints weighted by their length"""
    d = V[:, 1] - y
    s = np.sign(d[F])
    m = ~((s[:, 0] == s[:, 1]) & (s[:, 1] == s[:, 2]))
    pts, wts = [], []
    for f in np.asarray(F)[m]:
        P = []
        for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            if (d[a] < 0) != (d[b] < 0):
                t = d[a] / (d[a] - d[b])
                P.append(V[a] + t * (V[b] - V[a]))
        if len(P) == 2 and min(P[0][0], P[1][0]) > xmin:
            pts.append(0.5 * (P[0] + P[1]))
            wts.append(np.linalg.norm(P[1] - P[0]))
    pts, wts = np.array(pts), np.array(wts)
    return (pts * wts[:, None]).sum(0) / wts.sum()


def reference(sex, Vref, gnm_joints, tvec, eye_centres, tragion, tongue_V, landmarks=None, skin=None):
    """the joints on the A-pose bind (mm): the body's from MakeHuman's cubes on the phenotype Vref, the head's from GNM's
    joints (gnm_joints in GNM's frame, tvec H3's placement), the eyes' at the globes, the jaw from the tragions, the tongue
    on its mesh's axis (module docstring). landmarks (the LOW's ANSUR landmarks, mm) and skin (V, F): THE HIP AND THE
    KNEE from the skin, because MakeHuman's cubes miss them on the measured body (r04's first run: its knee cube 80 / 66 mm
    under the femoral epicondyle, 0.241 of stature where a knee's axis is ~0.29; its hip cube 26 / 14 mm over the
    trochanterion): the hip joint at the trochanterion's height (the femoral head's centre is level with the greater
    trochanter's tip; ANSUR's ratio, the H0 gate), the cube's x and z; the knee joint at the lateral femoral epicondyle's
    height, the leg's section centroid there"""
    C = mh_cubes(Vref)
    if landmarks is not None:
        for ms, sg in (('l', 1.0), ('r', -1.0)):
            C[f'{ms}-upper-leg'] = np.array([C[f'{ms}-upper-leg'][0], landmarks['trochanterion'][1],
                                             C[f'{ms}-upper-leg'][2]])
            kc = section_centroid(skin[0] * np.array([sg, 1.0, 1.0]), skin[1], landmarks['epicondyle'][1], 40.0)
            C[f'{ms}-knee'] = kc * np.array([sg, 1.0, 1.0])
    J = {}
    J['pelvis'] = C['pelvis']
    J['root'] = np.array([0.0, 0.0, C['pelvis'][2]])
    sp = [C['spine-4'], 0.5 * (C['spine-4'] + C['spine-3']), C['spine-3'], C['spine-2'], C['spine-1']]
    for i, p in enumerate(sp):
        J[f'spine_{i + 1:02d}'] = p
    gn, gh = np.asarray(gnm_joints['neck']) + tvec, np.asarray(gnm_joints['head']) + tvec
    J['neck_01'] = gn
    J['neck_02'] = gn + (gh - gn) * (2.0 / 3.0)
    J['head'] = gh
    for sd in ('L', 'R'):
        J[f'eye_{sd}'] = np.asarray(eye_centres[sd], np.float64)
    tm = 0.5 * (np.asarray(tragion['L']) + np.asarray(tragion['R']))
    J['jaw'] = np.array([0.0, tm[1] - 7.0, tm[2] + 11.0])
    # the tongue: its mesh's long axis (the first principal direction, pointing forward), root at the back
    T_ = np.asarray(tongue_V, np.float64)
    c = T_.mean(0)
    U, S, Vt = np.linalg.svd(T_ - c, full_matrices=False)
    ax = Vt[0] if Vt[0][2] > 0 else -Vt[0]
    s = (T_ - c) @ ax
    lo, hi = np.percentile(s, 2), np.percentile(s, 98)
    for i, f in enumerate((0.2, 0.5, 0.8)):
        q = c + ax * (lo + f * (hi - lo))
        J[f'tongue_{i + 1:02d}'] = np.array([0.0, q[1], q[2]])
    for sd, ms in (('L', 'l'), ('R', 'r')):
        J[f'clavicle_{sd}'] = C[f'{ms}-clavicle']
        J[f'upperarm_{sd}'] = C[f'{ms}-shoulder']
        J[f'lowerarm_{sd}'] = C[f'{ms}-elbow']
        J[f'hand_{sd}'] = C[f'{ms}-hand']
        J[f'thumb_01_{sd}'] = C[f'{ms}-finger-1-1']
        J[f'thumb_02_{sd}'] = C[f'{ms}-finger-1-2']
        J[f'thumb_03_{sd}'] = C[f'{ms}-finger-1-3']
        for fn, k in FINGERS[1:]:
            J[f'{fn}_metacarpal_{sd}'] = C[f'{ms}-hand-3'] if k in (2, 3) else C[f'{ms}-hand-2']
            for j in (1, 2, 3):
                J[f'{fn}_0{j}_{sd}'] = C[f'{ms}-finger-{k}-{j}']
        J[f'thigh_{sd}'] = C[f'{ms}-upper-leg']
        J[f'calf_{sd}'] = C[f'{ms}-knee']
        J[f'foot_{sd}'] = C[f'{ms}-ankle']
        J[f'ball_{sd}'] = C[f'{ms}-foot-1']
        # the twists along their bones
        for b, nxt, fr in (('upperarm', 'lowerarm', (1 / 3, 2 / 3)), ('lowerarm', 'hand', (0.75, 0.4)),
                           ('thigh', 'calf', (1 / 3, 2 / 3)), ('calf', 'foot', (1 / 3, 2 / 3))):
            a, e = J[f'{b}_{sd}'], J[f'{nxt}_{sd}']
            J[f'{b}_twist_01_{sd}'] = a + fr[0] * (e - a)
            J[f'{b}_twist_02_{sd}'] = a + fr[1] * (e - a)
    # the helpers: off the joint on its outer side (set from the skin by place_helpers once the LOW is known)
    return J, C


def place_helpers(J, low, tm_closest):
    """the volume helpers on the skin's outer side of their joint, 40 % of the way from the joint to the skin: the
    shoulder's over the acromion (up and out), the elbow's behind the olecranon, the wrist's on the back of the wrist,
    the knee's over the patella (forward). tm_closest(points) -> closest skin points"""
    for sd in ('L', 'R'):
        sg = 1.0 if sd == 'L' else -1.0
        for h, j, d in (('shoulder', f'upperarm_{sd}', np.array([0.55 * sg, 0.83, 0.0])),
                        ('elbow', f'lowerarm_{sd}', np.array([0.0, 0.0, -1.0])),
                        ('wrist', f'hand_{sd}', None),
                        ('knee', f'calf_{sd}', np.array([0.0, 0.0, 1.0]))):
            p = J[j]
            if h == 'wrist':
                # the back of the wrist: the dorsal side, opposite the palm (the middle metacarpal's offset from the wrist
                # crossed with the thumb's, sides by the hand), square to the forearm's axis
                fa = J[f'hand_{sd}'] - J[f'lowerarm_{sd}']
                fa /= np.linalg.norm(fa)
                mc = J[f'middle_01_{sd}'] - J[f'hand_{sd}']
                th = J[f'thumb_01_{sd}'] - J[f'hand_{sd}']
                dorsal = np.cross(mc, th) * sg
                d = dorsal - fa * (dorsal @ fa)
            d = d / np.linalg.norm(d)
            q = tm_closest(np.vstack([p + d * 60.0]))[0]
            J[f'helper_{h}_{sd}'] = p + 0.4 * (q - p)
    return J


def fit_regressor(lows, refs, names, shell=1.7, kmin=12, kmax=160, lam=1e-3, tm_closest=None):
    """each joint an AFFINE combination of the LOW's vertices round it (a shell: within shell x its distance to the skin,
    at least kmin and at most kmax of the nearest), fitted on every sex at once: least squares on the sexes' positions plus
    lam x the pull toward the shell's uniform mean, the weights summing to one (closed form through the KKT system).
    lows: [(n, 3)] the sexes' LOWs (one topology); refs: [{name: (3,)}]; tm_closest[s](P) -> skin points of sex s.
    Returns (R scipy CSR (len(names), n), rows {name: dict(ids, w, res_mm per sex)})"""
    import scipy.sparse as sp
    n = len(lows[0])
    rows, cols, vals = [], [], []
    info = {}
    for ji, nm in enumerate(names):
        P0 = refs[0][nm]
        L0 = lows[0]
        d0 = np.linalg.norm(tm_closest[0](P0[None])[0] - P0)
        dist = np.linalg.norm(L0 - P0, axis=1)
        order = np.argsort(dist)
        k = int(np.clip(np.searchsorted(dist[order], shell * d0), kmin, kmax))
        ids = order[:k]
        A = np.vstack([L[ids].T for L in lows])                       # (3 s, k): each sex's x, y, z (mm)
        b = np.concatenate([refs[s][nm] for s in range(len(lows))])
        w0 = np.full(k, 1.0 / k)
        # min |A w - b|^2 + lam |w - w0|^2  s.t.  1'w = 1
        H = A.T @ A + lam * np.eye(k)
        g = A.T @ b + lam * w0
        K = np.block([[H, np.ones((k, 1))], [np.ones((1, k)), np.zeros((1, 1))]])
        sol = np.linalg.solve(K, np.concatenate([g, [1.0]]))
        w = sol[:k]
        res = [float(np.linalg.norm(w @ L[ids] - refs[s][nm])) for s, L in enumerate(lows)]
        keep = np.abs(w) > 1e-9
        rows += [ji] * int(keep.sum())
        cols += ids[keep].tolist()
        vals += w[keep].tolist()
        info[nm] = dict(ids=ids[keep].tolist(), w=w[keep].tolist(), res_mm=res)
    R = sp.csr_matrix((vals, (rows, cols)), shape=(len(names), n))
    return R, info


def _rot_between(a, b):
    """the smallest rotation taking direction a to direction b"""
    a = np.asarray(a, np.float64) / np.linalg.norm(a)
    b = np.asarray(b, np.float64) / np.linalg.norm(b)
    v = np.cross(a, b)
    c = float(a @ b)
    if np.linalg.norm(v) < 1e-12:
        if c > 0:
            return np.eye(3)
        p = np.cross(a, [1.0, 0.0, 0.0]) if abs(a[0]) < 0.9 else np.cross(a, [0.0, 1.0, 0.0])
        p /= np.linalg.norm(p)
        return 2.0 * np.outer(p, p) - np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * (1.0 / (1.0 + c))


def tpose(J, table):
    """each joint's WORLD rotation taking the A-pose bind to the VRM T-pose (module docstring), composed down the chains
    (a child inherits its parent's and adds its own): the upper arm along +-X, the lower arm on it, the hand along it with
    the palm facing down, each finger's three phalanges straight along the hand's axis in the palm's plane (the thumb
    keeps its spread from the index), the thigh and the calf plumb. Returns ({name: 3x3}, {name: T-pose position})"""
    par = {t['name']: t['parent'] for t in table}
    names = [t['name'] for t in table]
    kids = {nm: [t['name'] for t in table if t['parent'] == nm] for nm in names}
    Rw, Pt = {}, {}
    # each joint's own rule: 'dir' its bone (to the named child) along a fixed direction; 'hand' along +-X with the palm
    # down; 'continue' its bone (to its one child) along its parent's bone (parent -> it) as posed; else it inherits
    own = {}
    for sd in ('L', 'R'):
        sg = 1.0 if sd == 'L' else -1.0
        X = np.array([sg, 0.0, 0.0])
        own[f'upperarm_{sd}'] = ('dir', f'lowerarm_{sd}', X)
        own[f'lowerarm_{sd}'] = ('dir', f'hand_{sd}', X)
        own[f'hand_{sd}'] = ('hand', sd)
        for fn, k in FINGERS:
            if fn == 'thumb':
                own[f'thumb_02_{sd}'] = ('continue', f'thumb_03_{sd}')
            else:
                own[f'{fn}_01_{sd}'] = ('continue', f'{fn}_02_{sd}')
                own[f'{fn}_02_{sd}'] = ('continue', f'{fn}_03_{sd}')
        own[f'thigh_{sd}'] = ('dir', f'calf_{sd}', np.array([0.0, -1.0, 0.0]))
        own[f'calf_{sd}'] = ('dir', f'foot_{sd}', np.array([0.0, -1.0, 0.0]))
    for nm in names:
        p = par[nm]
        Rp = Rw[p] if p else np.eye(3)
        Pt[nm] = J[nm].copy() if p is None else Pt[p] + Rp @ (J[nm] - J[p])
        R = Rp
        rule = own.get(nm)
        if rule is not None and rule[0] == 'dir':
            R = _rot_between(Rp @ (J[rule[1]] - J[nm]), rule[2]) @ Rp
        elif rule is not None and rule[0] == 'hand':
            sd = rule[1]
            X = np.array([1.0 if sd == 'L' else -1.0, 0.0, 0.0])
            R1 = _rot_between(Rp @ (J[f'middle_01_{sd}'] - J[nm]), X)
            # the palm down: the knuckles' line (index MCP -> pinky MCP) horizontal, the index toward the front
            acr = R1 @ Rp @ (J[f'index_01_{sd}'] - J[f'pinky_01_{sd}'])
            acr -= X * (acr @ X)
            want = np.array([0.0, 0.0, 1.0])
            ang = np.arctan2(np.cross(acr, want) @ X, acr @ want)
            c, s_ = np.cos(ang), np.sin(ang)
            Kx = np.array([[0, -X[2], X[1]], [X[2], 0, -X[0]], [-X[1], X[0], 0]])
            R = (np.eye(3) + s_ * Kx + (1 - c) * Kx @ Kx) @ R1 @ Rp
        elif rule is not None and rule[0] == 'continue':
            pdir = Rp @ (J[nm] - J[p])                    # the parent's bone as posed
            R = _rot_between(Rp @ (J[rule[1]] - J[nm]), pdir) @ Rp
        Rw[nm] = R
    return Rw, Pt
