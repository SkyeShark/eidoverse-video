"""H4 (the rig builder, 11-01; HUMAN_PLAN §4.3): THE FACE RIG v1: jaw, eyes, lids, brows, lips and cheeks on joints, one
driver (§4.5 decision 18: the VRM expressions carry no binds; the runtime reads their values and this file's control
table drives the joints).

THE JOINTS (children of the head unless noted; their rest rotations the identity, like every joint of the VRM view):
  lids     lid_upper_L/R, lid_lower_L/R AT THE EYE'S CENTRE: a lid's skin turns about the globe's horizontal axis, so its
           margin rides the lid sphere (H2b's rule: the margin 1 mm off the globe) and never drags across the eye
  brows    brow_inner, brow_mid, brow_outer L/R: 6 mm under the skin of GNM's brow regions (inner third, middle, outer)
  cheeks   cheek_L/R under the zygoma (GNM's zygomatic + infraorbital regions), 8 mm in
  nose     nostril_L/R at the alar wings, 3 mm in
  lips     lip_upper_C / L / R (head), lip_lower_C / L / R (children of the JAW, so they ride its opening), lip_corner_L / R
           (head; the control table moves them with the jaw at 45 %): 3 mm under the vermilion (GNM's upper_lip /
           lower_lip groups) at the middle and at a third of the half-width; the corners at the inner lip line's ends
  + the skeleton's jaw, eyes and tongue: 28 face joints in all (the plan's "about 40" counts v2's squints and puffs:
  they wait for v2's correctives and wrinkle maps)
THE WEIGHTS split the body heat's HEAD weight (r05: the whole head one bone):
  * THE JAW by the lips' partition: geodesic distances over the head's skin from the UPPER lip (GNM's upper_lip +
    upper_lip_region) and from the LOWER (lower_lip + lower_lip_region + chin_region); jawness = smoothstep(dU / (dU + dL),
    0.38, 0.62), so the inner lip line is the boundary; faded to 0 over 12 mm above the plane through the mouth corners and
    the jaw joint, and within 18 mm of the temporomandibular joints (the cheeks and the ears stay on the head); and (v2,
    11-01) faded out 40 mm under the menton and behind a plane 8 mm behind the jaw joints: the neck stays off the jaw;
  * each face joint a geodesic falloff (smoothstep from its radius to 0) from its anchor vertices, inside its region
    masks; the lids from their MARGIN (1 within 1.5 mm, 0 at 9 mm upper / 7 mm lower, the lid tucks behind the margin all
    lid); shares normalised within the head part (or the jaw part, for the lower lips) so the head keeps the rest;
  * cut to four influences with the body's, the cut continuous (rig.limit_influences).
THE CONTROLS (control_table()): the ARKit names v1 needs (eyeBlink, eyeWide, eyeSquint, eyeLook*, jawOpen, mouthClose,
mouthSmile, mouthFrown, mouthPucker, mouthFunnel, mouthStretch, mouthUpperUp, mouthLowerDown, browInnerUp, browDown,
browOuterUp, cheekSquint, noseSneer) as linear driven keys on joint rotations (deg, about world axes at the joint: the
rest frames are the identity) and translations (mm); the house's visemes aa / ih / ou / ee / oh and the VRM presets
(blink, happy, angry, sad, relaxed, surprised, lookUp ...) as combinations of them. The lids follow the gaze (up 0.55 of
the eye's pitch for the upper lid, 0.35 for the lower: eye-lid coupling).
THE GATES (gates()): the lids clear the cornea (the eye part's own globe and cornea, posed with the gaze) at rest, at a
blink and at nine gaze extremes, by at least CLEAR mm over every vertex the lid carries; the lips seal at rest (the
inner lip lines' gap) and never cross in any control or viseme (the lower inner line under the upper, column by
column); the teeth inside the lips at rest (every tooth vertex behind the skin: a ray forward meets the lips or the face).

    joints(low, Q, head_v, masks, eye_c, commissure) -> {name: (parent, (3,) mm)}
    weights(...) -> per-vertex face shares           control_table() -> dict   pose(...) -> joint transforms
"""
import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import dijkstra

VERSION = 'h4b-face-4'           # 2: the jaw's reach bounded (under the chin, behind the ramus); 3 (H4b face, 11-02): the
                                 # tongue in the visemes (tongueDown / tongueBack / tongueUp), see control_table; 4 (H4b
                                 # face, session 2): tongueDown lowers the back and keeps the blade at the lower incisors
CLEAR = 0.15
# THE GAZE'S RANGE (the eye joints' extremes at a control of 1; the VRM view's lookAt range maps write the same, so the
# runtime never turns an eye past what the lid gate proved): 25 deg out and in, 22 up, 25 down. Saccades in conversation
# and walking stay well inside it (the oculomotor range is ~45 deg, but beyond ~20 deg people turn the head)
YAW_DEG, UP_DEG, DOWN_DEG = 25.0, 22.0, 25.0
CONJ_MM = 1.9                    # the conjunctiva's band: the tuck within this of the eye part rides the eye
JAW_UNDER_CHIN_MM = 40.0         # the jaw's weight fades out this far under the menton (the submental skin follows it;
                                 # over 22 mm the open jaw creased the skin along its lower border, face_F.png 08:1x)
JAW_BEHIND_TMJ_MM = 8.0          # ... and behind a plane this far behind the jaw joints (the ramus's back edge),
JAW_BEHIND_FADE_MM = 20.0        # eased over this
FACE_JOINTS = [('lid_upper_L', 'head'), ('lid_upper_R', 'head'), ('lid_lower_L', 'head'), ('lid_lower_R', 'head'),
               ('brow_inner_L', 'head'), ('brow_inner_R', 'head'), ('brow_mid_L', 'head'), ('brow_mid_R', 'head'),
               ('brow_outer_L', 'head'), ('brow_outer_R', 'head'), ('cheek_L', 'head'), ('cheek_R', 'head'),
               ('nostril_L', 'head'), ('nostril_R', 'head'), ('lip_upper_C', 'head'), ('lip_upper_L', 'head'),
               ('lip_upper_R', 'head'), ('lip_corner_L', 'head'), ('lip_corner_R', 'head'), ('lip_lower_C', 'jaw'),
               ('lip_lower_L', 'jaw'), ('lip_lower_R', 'jaw')]


def _smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def edge_graph(V, Q, verts):
    """the mesh's edge graph restricted to `verts` (lengths in mm): (csr over local ids, global -> local map)"""
    loc = -np.ones(len(V), np.int64)
    loc[verts] = np.arange(len(verts))
    e = np.concatenate([Q[:, [0, 1]], Q[:, [1, 2]], Q[:, [2, 3]], Q[:, [3, 0]]])
    e = np.unique(np.sort(e, axis=1), axis=0)
    e = e[(loc[e[:, 0]] >= 0) & (loc[e[:, 1]] >= 0)]
    w = np.linalg.norm(V[e[:, 0]] - V[e[:, 1]], axis=1)
    n = len(verts)
    G = sp.coo_matrix((np.concatenate([w, w]), (np.concatenate([loc[e[:, 0]], loc[e[:, 1]]]),
                                                 np.concatenate([loc[e[:, 1]], loc[e[:, 0]]]))), shape=(n, n)).tocsr()
    return G, loc


def geodesic(G, loc, seeds, limit=80.0):
    s = loc[np.asarray(seeds, np.int64)]
    s = s[s >= 0]
    d = dijkstra(G, directed=False, indices=s, min_only=True, limit=limit)
    return np.where(np.isfinite(d), d, limit)


def joints(V, head_v, masks, eye_c, commissure, inner_lip, N):
    """the face joints' rest positions (mm) on the A-pose bind (module docstring). masks: GNM's region groups over the
    LOW's vertices; eye_c {L, R} the globes' centres; commissure {L, R} vertex ids; inner_lip the inner lip line's ids;
    N the LOW's vertex normals"""
    J = {}
    for sd, sg in (('L', 1.0), ('R', -1.0)):
        J[f'lid_upper_{sd}'] = np.asarray(eye_c[sd], np.float64)
        J[f'lid_lower_{sd}'] = np.asarray(eye_c[sd], np.float64)
        side = 'left' if sd == 'L' else 'right'
        b = np.nonzero(masks[f'{side}_brow_region'] & head_v)[0]
        xs = V[b, 0] * sg
        lo, hi = np.percentile(xs, 5), np.percentile(xs, 95)
        for k, nm in enumerate(('inner', 'mid', 'outer')):
            sel = b[(xs >= lo + (hi - lo) * k / 3.0) & (xs <= lo + (hi - lo) * (k + 1) / 3.0)]
            p = V[sel].mean(0)
            n = N[sel].mean(0)
            J[f'brow_{nm}_{sd}'] = p - 6.0 * n / np.linalg.norm(n)
        zz = np.nonzero((masks[f'{side}_zygomatic_region'] | masks[f'{side}_infraorbital_region']) & head_v)[0]
        n = N[zz].mean(0)
        J[f'cheek_{sd}'] = V[zz].mean(0) - 8.0 * n / np.linalg.norm(n)
        nose = np.nonzero(masks['nose_region'] & head_v & (V[:, 0] * sg > 0))[0]
        # the alar wing: the nose region's most lateral vertices in its lower half
        ylo = np.percentile(V[nose, 1], 35)
        low_half = nose[V[nose, 1] < ylo]
        wing = low_half[np.argsort(-V[low_half, 0] * sg)[:12]]
        n = N[wing].mean(0)
        J[f'nostril_{sd}'] = V[wing].mean(0) - 3.0 * n / np.linalg.norm(n)
        J[f'lip_corner_{sd}'] = V[commissure[sd]].copy()
    for lip, grp in (('upper', 'upper_lip'), ('lower', 'lower_lip')):
        ids = np.nonzero(masks[grp] & head_v)[0]
        x = V[ids, 0]
        half = np.percentile(np.abs(x), 95)
        for nm, xc in (('C', 0.0), ('L', half / 1.6), ('R', -half / 1.6)):
            sel = ids[np.abs(x - xc) < max(half / 5.0, 3.0)]
            p = V[sel].mean(0)
            n = N[sel].mean(0)
            q = p - 3.0 * n / np.linalg.norm(n)
            if nm == 'C':
                q[0] = 0.0
            J[f'lip_{lip}_{nm}'] = q
    return J


def weights(V, Q, head_v, w_head, w_jaw_src, J, jaw_pos, masks, margin, eye_c, commissure, tmj, axis0=(0.0, 0.0, 1.0)):
    """the face's shares of the head bone's weight (module docstring). w_head: the body heat's head weight per vertex;
    axis0 the eyes' rest optical axis. Returns ({joint: per-vertex weight}, {'jawness': ...})"""
    axis0 = np.asarray(axis0, np.float64)
    hv = np.nonzero(head_v)[0]
    G, loc = edge_graph(V, Q, hv)
    up = np.nonzero((masks['upper_lip'] | masks['upper_lip_region']) & head_v)[0]
    lw = np.nonzero((masks['lower_lip'] | masks['lower_lip_region'] | masks['chin_region']) & head_v)[0]
    dU = np.full(len(V), 200.0)
    dL = np.full(len(V), 200.0)
    dU[hv] = geodesic(G, loc, up, 200.0)
    dL[hv] = geodesic(G, loc, lw, 200.0)
    raw = dU / np.maximum(dU + dL, 1e-9)
    jawness = _smooth((raw - 0.38) / 0.24)
    # the fade above the plane through the mouth corners and the jaw joint (its normal pointing up and forward)
    cL, cR = V[commissure['L']], V[commissure['R']]
    a = 0.5 * (cL + cR)
    n = np.cross(cL - cR, np.asarray(jaw_pos) - a)
    if n[1] < 0:
        n = -n
    n /= np.linalg.norm(n)
    h = (V - a) @ n
    jawness *= 1.0 - _smooth(h / 12.0)
    for t in tmj:
        jawness *= _smooth((np.linalg.norm(V - np.asarray(t), axis=1) - 6.0) / 12.0)
    # (H4 11-01, read by the ring records) THE JAW'S REACH: the partition alone sent every vertex nearer the lower lip
    # than the upper to the jaw, so the whole neck rode it (19-28 % of the mid-neck ring, round to the nape). The jaw's
    # skin is the lower face and the skin under the chin: jawness fades out by JAW_UNDER_CHIN_MM under the chin's lowest
    # point (the menton) and behind a plane JAW_BEHIND_TMJ_MM behind the jaw joints (the ramus's back edge: the neck's
    # side and back and the ear's lobe stay on the head)
    chin = np.nonzero(masks['chin_region'] & head_v)[0]
    y_men = float(V[chin, 1].min())
    jawness *= 1.0 - _smooth((y_men - V[:, 1]) / JAW_UNDER_CHIN_MM)
    z_back = float(np.mean([np.asarray(t)[2] for t in tmj])) - JAW_BEHIND_TMJ_MM
    jawness *= _smooth((V[:, 2] - z_back) / JAW_BEHIND_FADE_MM)
    jawness[~head_v] = 0.0
    # the lips' own sets are exact: the upper lip never on the jaw, the lower lip all jaw
    jawness[masks['upper_lip'] & head_v] = 0.0
    jawness[masks['lower_lip'] & head_v] = 1.0
    W = {}
    w_jaw = w_head * jawness + w_jaw_src
    w_top = w_head * (1.0 - jawness)

    def fall(seeds, r0, r1, region=None):
        d = np.full(len(V), 1e3)
        d[hv] = geodesic(G, loc, seeds, r1 + 1.0)
        f = 1.0 - _smooth((d - r0) / max(r1 - r0, 1e-6))
        if region is not None:
            f = f * region
        f[~head_v] = 0.0
        return f
    F = {}
    for sd, sg in (('L', 1.0), ('R', -1.0)):
        side = 'left' if sd == 'L' else 'right'
        c = np.asarray(eye_c[sd])
        ms = [v for v in margin if V[v, 0] * sg > 0]
        mu = [v for v in ms if V[v, 1] >= c[1] - 0.5]
        md = [v for v in ms if V[v, 1] < c[1] - 0.5]
        orb = (masks[f'{side}_orbital_region'] | masks['eye_sockets']) & head_v & (V[:, 0] * sg > 0)
        above = _smooth((V[:, 1] - (c[1] - 2.0)) / 3.0)
        F[f'lid_upper_{sd}'] = fall(mu, 1.5, 9.0, orb * above)
        F[f'lid_lower_{sd}'] = fall(md, 1.5, 7.0, orb * (1.0 - above))
        tuck = masks['eye_sockets'] & head_v & (V[:, 0] * sg > 0)
        F[f'lid_upper_{sd}'][tuck] = np.maximum(F[f'lid_upper_{sd}'][tuck], above[tuck])
        F[f'lid_lower_{sd}'][tuck] = np.maximum(F[f'lid_lower_{sd}'][tuck], 1.0 - above[tuck])
        # THE CONJUNCTIVA rides the globe: the lid's tuck behind the margin (GNM's eye sockets) within 1.05 mm of the eye
        # part's surface (the sphere AND the cornea's cap: human_eye's globe along the rest axis), in front of its equator,
        # goes with the EYE joint (1 within 0.15 mm, 0 at 1.05 mm), as the conjunctiva on the globe moves with the eye: the
        # cornea's 1.13 mm bulge then never sweeps through it when the eye turns (r06's first gates: -0.6 to -1.0 mm, all
        # on tuck vertices lying ON the cornea's edge under the upper lid, 0.07-0.6 mm off it at rest)
        dv = V - c
        rr = np.linalg.norm(dv, axis=1)
        cl = rr - globe_radius((dv @ axis0) / np.maximum(rr, 1e-9))
        front = (dv @ axis0) > -2.0
        lidreg = ((F[f'lid_upper_{sd}'] + F[f'lid_lower_{sd}']) > 0.0) & masks['eye_sockets']
        conj = np.where(lidreg & front & (cl < CONJ_MM), 1.0 - _smooth((cl - 0.15) / (CONJ_MM - 0.15)), 0.0)
        F[f'eye_{sd}'] = conj
        F[f'lid_upper_{sd}'] *= 1.0 - conj                 # the eye's share replaces the lid's there
        F[f'lid_lower_{sd}'] *= 1.0 - conj
        brow = (masks[f'{side}_brow_region'] | masks['forehead_region'] | masks['middle_brow_region']) & head_v
        for nm in ('inner', 'mid', 'outer'):
            seeds = np.argsort(np.linalg.norm(V - J[f'brow_{nm}_{sd}'], axis=1))[:6]
            F[f'brow_{nm}_{sd}'] = fall(seeds, 4.0, 18.0, brow * (V[:, 0] * sg > -2.0))
        chk = (masks[f'{side}_zygomatic_region'] | masks[f'{side}_infraorbital_region'] |
               masks[f'{side}_cheek_region']) & head_v
        seeds = np.argsort(np.linalg.norm(V - J[f'cheek_{sd}'], axis=1))[:8]
        F[f'cheek_{sd}'] = fall(seeds, 6.0, 26.0, chk * 1.0)
        seeds = np.argsort(np.linalg.norm(V - J[f'nostril_{sd}'], axis=1))[:6]
        F[f'nostril_{sd}'] = fall(seeds, 2.0, 9.0, masks['nose_region'] & head_v)
        # the corner by the mouth's own width, not the surface's: the same share on both lips at one x (a geodesic falloff
        # gave the upper lip's end 0.91 and the lower's 0.75 at one column, so a frown drew the upper lip through the
        # lower, r06's never-cross gate), over the lips and their regions near the mouth's line
        pc = V[commissure[sd]]
        lips = (masks['upper_lip'] | masks['upper_lip_region'] | masks['lower_lip'] | masks['lower_lip_region']) & head_v
        fx = 1.0 - _smooth((np.abs(V[:, 0] - pc[0]) - 2.0) / 9.0)
        fy = 1.0 - _smooth((np.abs(V[:, 1] - pc[1]) - 6.0) / 8.0)
        F[f'lip_corner_{sd}'] = np.where(lips & (V[:, 0] * sg > 0), fx * fy, 0.0)
    for nm in ('C', 'L', 'R'):
        for lip in ('upper', 'lower'):
            seeds = np.argsort(np.linalg.norm(V - J[f'lip_{lip}_{nm}'], axis=1))[:6]
            reg = (masks[f'{lip}_lip'] | masks[f'{lip}_lip_region']) & head_v
            F[f'lip_{lip}_{nm}'] = fall(seeds, 3.0, 13.0, reg * 1.0)
    # shares: the top part's joints share w_top, the lower lips share w_jaw, the corners take from both
    top = [k for k in F if not k.startswith('lip_lower') and not k.startswith('lip_corner')]
    low_ = [k for k in F if k.startswith('lip_lower')]
    corner = [k for k in F if k.startswith('lip_corner')]

    def share(keys, base):
        S = np.array([F[k] for k in keys])
        tot = S.sum(0)
        scale = np.where(tot > 1.0, 1.0 / np.maximum(tot, 1e-9), 1.0)
        out = {k: base * S[i] * scale for i, k in enumerate(keys)}
        rest = base * (1.0 - np.minimum(tot, 1.0))
        return out, rest
    o1, head_rest = share(top + corner, w_top)
    o2, jaw_rest = share(low_ + corner, w_jaw)
    for k in top:
        W[k] = o1[k]
    for k in low_:
        W[k] = o2[k]
    for k in corner:
        W[k] = o1[k] + o2[k]
    W['head'] = head_rest
    W['jaw'] = jaw_rest
    return W, dict(jawness=jawness)


def control_table(blink_deg):
    """the v1 controls as linear driven keys: {control: [(joint, 'rot', axis (world), deg) | (joint, 'trans', (mm))]}.
    blink_deg {L, R}: each upper lid's closure angle (its margin onto the lower's, about the globe's x axis)"""
    T = {}
    # THE LIDS' PUSH: as the cornea's bulge (1.13 mm proud of the sphere, the lid margin 1 mm off it) passes under a lid,
    # the lid rides out over it: the lid joints step forward along the gaze (mm), as a lid in life is lifted by the cornea
    P_BLINK, P_GAZE, P_YAW = 0.85, 0.60, 0.80          # (r06's runs: the yaw's cornea passes nearest the canthi)
    for sd, sg in (('L', 1.0), ('R', -1.0)):
        Lr = 'Left' if sd == 'L' else 'Right'
        b = blink_deg[sd]
        T[f'eyeBlink{Lr}'] = [(f'lid_upper_{sd}', 'rot', (1, 0, 0), 0.86 * b), (f'lid_lower_{sd}', 'rot', (1, 0, 0), -0.14 * b),
                              (f'lid_upper_{sd}', 'trans', (0.0, 0.0, P_BLINK)), (f'lid_lower_{sd}', 'trans', (0.0, 0.0, 0.15))]
        T[f'eyeWide{Lr}'] = [(f'lid_upper_{sd}', 'rot', (1, 0, 0), -9.0), (f'lid_lower_{sd}', 'rot', (1, 0, 0), 3.0)]
        T[f'eyeSquint{Lr}'] = [(f'lid_lower_{sd}', 'rot', (1, 0, 0), -10.0), (f'cheek_{sd}', 'trans', (0.0, 1.8, 0.6)),
                               (f'lid_upper_{sd}', 'rot', (1, 0, 0), 4.0), (f'lid_lower_{sd}', 'trans', (0.0, 0.0, 0.2))]
        T[f'eyeLookUp{Lr}'] = [(f'eye_{sd}', 'rot', (1, 0, 0), -UP_DEG), (f'lid_upper_{sd}', 'rot', (1, 0, 0), -0.55 * UP_DEG),
                               (f'lid_lower_{sd}', 'rot', (1, 0, 0), -0.35 * UP_DEG),
                               (f'lid_upper_{sd}', 'trans', (0.0, 0.0, P_GAZE)), (f'lid_lower_{sd}', 'trans', (0.0, 0.0, 0.2))]
        T[f'eyeLookDown{Lr}'] = [(f'eye_{sd}', 'rot', (1, 0, 0), DOWN_DEG), (f'lid_upper_{sd}', 'rot', (1, 0, 0), 0.55 * DOWN_DEG),
                                 (f'lid_lower_{sd}', 'rot', (1, 0, 0), 0.35 * DOWN_DEG),
                                 (f'lid_upper_{sd}', 'trans', (0.0, 0.0, P_GAZE)), (f'lid_lower_{sd}', 'trans', (0.0, 0.0, P_GAZE))]
        out_ = YAW_DEG * sg
        T[f'eyeLookOut{Lr}'] = [(f'eye_{sd}', 'rot', (0, 1, 0), out_), (f'lid_upper_{sd}', 'trans', (0.0, 0.0, P_YAW)),
                                (f'lid_lower_{sd}', 'trans', (0.0, 0.0, P_YAW))]
        T[f'eyeLookIn{Lr}'] = [(f'eye_{sd}', 'rot', (0, 1, 0), -out_), (f'lid_upper_{sd}', 'trans', (0.0, 0.0, P_YAW)),
                               (f'lid_lower_{sd}', 'trans', (0.0, 0.0, P_YAW))]
        # the smile lifts the upper lip's side with the corner (at 0.8 mm the woman's lower lip end rose 0.29 mm past it)
        T[f'mouthSmile{Lr}'] = [(f'lip_corner_{sd}', 'trans', (3.2 * sg, 3.0, -1.8)), (f'cheek_{sd}', 'trans', (0.4 * sg, 2.2, 0.8)),
                                (f'lip_upper_{sd}', 'trans', (0.8 * sg, 1.8, -0.4)), (f'lid_lower_{sd}', 'rot', (1, 0, 0), -3.0)]
        # the lower lip goes down with the corner (r06: with -0.8 the corner dragged the upper lip's end through it)
        T[f'mouthFrown{Lr}'] = [(f'lip_corner_{sd}', 'trans', (0.5 * sg, -3.0, -0.5)), (f'lip_lower_{sd}', 'trans', (0.0, -3.0, 0.2))]
        T[f'mouthStretch{Lr}'] = [(f'lip_corner_{sd}', 'trans', (3.5 * sg, -1.5, -1.0)), (f'lip_lower_{sd}', 'trans', (0.8 * sg, -0.8, 0.0))]
        T[f'browDown{Lr}'] = [(f'brow_inner_{sd}', 'trans', (-1.2 * sg, -3.0, 0.6)), (f'brow_mid_{sd}', 'trans', (0.0, -2.2, 0.4))]
        T[f'browOuterUp{Lr}'] = [(f'brow_outer_{sd}', 'trans', (0.0, 4.0, 0.0)), (f'brow_mid_{sd}', 'trans', (0.0, 1.5, 0.0))]
        T[f'cheekSquint{Lr}'] = [(f'cheek_{sd}', 'trans', (0.0, 2.5, 0.6)), (f'lid_lower_{sd}', 'rot', (1, 0, 0), -5.0)]
        T[f'noseSneer{Lr}'] = [(f'nostril_{sd}', 'trans', (0.4 * sg, 2.2, 0.0)), (f'lip_upper_{sd}', 'trans', (0.0, 1.2, 0.0))]
    T['browInnerUp'] = [(f'brow_inner_{sd}', 'trans', (0.0, 4.0, 0.3)) for sd in ('L', 'R')]
    T['jawOpen'] = [('jaw', 'rot', (1, 0, 0), 24.0), ('lip_corner_L', 'trans', (0.4, -3.2, -1.2)),
                    ('lip_corner_R', 'trans', (-0.4, -3.2, -1.2))]
    T['mouthClose'] = [('lip_upper_C', 'trans', (0.0, -1.6, 0.2)), ('lip_upper_L', 'trans', (0.0, -1.3, 0.2)),
                       ('lip_upper_R', 'trans', (0.0, -1.3, 0.2)), ('lip_lower_C', 'trans', (0.0, 2.2, 0.2)),
                       ('lip_lower_L', 'trans', (0.0, 1.8, 0.2)), ('lip_lower_R', 'trans', (0.0, 1.8, 0.2))]
    # the pucker parts the lips a little as they push out (r06's never-cross gate: pressed straight forward they met 1 mm
    # past their rest contact)
    T['mouthPucker'] = [('lip_upper_C', 'trans', (0.0, 0.8, 4.0)), ('lip_lower_C', 'trans', (0.0, -0.8, 4.0)),
                        ('lip_upper_L', 'trans', (-2.0, 0.7, 3.4)), ('lip_upper_R', 'trans', (2.0, 0.7, 3.4)),
                        ('lip_lower_L', 'trans', (-2.0, -0.7, 3.4)), ('lip_lower_R', 'trans', (2.0, -0.7, 3.4)),
                        ('lip_corner_L', 'trans', (-6.0, 0.0, 2.5)), ('lip_corner_R', 'trans', (6.0, 0.0, 2.5))]
    T['mouthFunnel'] = [('lip_upper_C', 'trans', (0.0, 1.2, 3.2)), ('lip_lower_C', 'trans', (0.0, -1.2, 3.2)),
                        ('lip_upper_L', 'trans', (-1.0, 1.0, 2.6)), ('lip_upper_R', 'trans', (1.0, 1.0, 2.6)),
                        ('lip_lower_L', 'trans', (-1.0, -1.0, 2.6)), ('lip_lower_R', 'trans', (1.0, -1.0, 2.6)),
                        ('lip_corner_L', 'trans', (-4.0, 0.0, 1.5)), ('lip_corner_R', 'trans', (4.0, 0.0, 1.5))]
    T['mouthUpperUp'] = [('lip_upper_C', 'trans', (0.0, 2.0, 0.0)), ('lip_upper_L', 'trans', (0.0, 2.4, 0.0)),
                         ('lip_upper_R', 'trans', (0.0, 2.4, 0.0))]
    T['mouthLowerDown'] = [('lip_lower_C', 'trans', (0.0, -2.0, 0.0)), ('lip_lower_L', 'trans', (0.0, -2.4, 0.0)),
                           ('lip_lower_R', 'trans', (0.0, -2.4, 0.0))]
    # (H4b face, 11-02) THE TONGUE IN SPEECH: GNM's tongue rides the jaw on tongue_01 -> 02 -> 03 (children of the jaw, each
    # its parent's child, so a key's translation carries every joint after it: each key below is its joint's LOCAL share of
    # the totals named), in the jaw's frame (it turns with the opening). The H4 tongue never moved against the jaw: its dorsum
    # stood 3-11 mm over the lower incisors' edge in every viseme and filled the open mouth (the H4 check's ID render: 68-76 %
    # of the opening). An open vowel lowers the tongue's body into the floor of the mouth and keeps the blade behind the
    # lower incisors; a rounded back vowel retracts it; the front vowels raise its front a little (behind the teeth)
    # tongueDown (session 2, h4b/face/probes/p08_sagittal.py + p09_tongue_pose.py variant v6): totals tongue_01 (0, -20,
    # -4), tongue_02 (0, -9, -1), tongue_03 (0, +2, +3.5). The first tongueDown (totals 01 -3, 02 -4, 03 -1.5) left the
    # dorsum riding the jaw's tilt, rising ~20 deg toward the back into every sight line through the opening (the camera
    # saw it 20-45 mm deep, black) and the blade 4-6 mm behind the lower incisors under the lower lip; an /a/ in section
    # has the dorsum low and flat and the tip against the lower incisors: the back down 20 (x0.68: 13.6 mm; it rides
    # 5-6 mm over the mouth's floor at aa 0.68), the middle 9, the blade up 2 and forward 3.5 (x0.68: the tip ~0.5 mm
    # behind the lower incisors)
    T['tongueDown'] = [('tongue_01', 'trans', (0.0, -20.0, -4.0)), ('tongue_02', 'trans', (0.0, 11.0, 3.0)),
                       ('tongue_03', 'trans', (0.0, 11.0, 4.5))]
    # tongueBack: totals tongue_01 (0, 0, -1.5), tongue_02 (0, -0.3, -2.5), tongue_03 (0, -0.5, -3)
    T['tongueBack'] = [('tongue_01', 'trans', (0.0, 0.0, -1.5)), ('tongue_02', 'trans', (0.0, -0.3, -1.0)),
                       ('tongue_03', 'trans', (0.0, -0.2, -0.5))]
    # tongueUp: totals tongue_02 (0, 1.5, 0.5), tongue_03 (0, 1, 0.8)
    T['tongueUp'] = [('tongue_02', 'trans', (0.0, 1.5, 0.5)), ('tongue_03', 'trans', (0.0, -0.5, 0.3))]
    return T


# the house's visemes (claudesona_face.js's aa / ih / ou / ee / oh) and the VRM presets, as weights of the controls
COMBOS = {
    # (H4b face) the tongue's keys added (control_table: tongueDown / tongueBack / tongueUp)
    'aa': {'jawOpen': 0.75, 'mouthLowerDown': 0.3, 'mouthStretchLeft': 0.1, 'mouthStretchRight': 0.1, 'tongueDown': 1.0},
    'ih': {'jawOpen': 0.3, 'mouthSmileLeft': 0.35, 'mouthSmileRight': 0.35, 'mouthUpperUp': 0.2, 'tongueUp': 0.4},
    'ou': {'jawOpen': 0.25, 'mouthPucker': 0.85, 'tongueBack': 0.8},
    'ee': {'jawOpen': 0.18, 'mouthSmileLeft': 0.45, 'mouthSmileRight': 0.45, 'mouthStretchLeft': 0.25,
           'mouthStretchRight': 0.25, 'tongueUp': 0.6},
    'oh': {'jawOpen': 0.5, 'mouthFunnel': 0.7, 'tongueDown': 0.6, 'tongueBack': 0.6},
    'blink': {'eyeBlinkLeft': 1.0, 'eyeBlinkRight': 1.0},
    'blinkLeft': {'eyeBlinkLeft': 1.0},
    'blinkRight': {'eyeBlinkRight': 1.0},
    'happy': {'mouthSmileLeft': 0.85, 'mouthSmileRight': 0.85, 'cheekSquintLeft': 0.6, 'cheekSquintRight': 0.6,
              'eyeSquintLeft': 0.3, 'eyeSquintRight': 0.3},
    'angry': {'browDownLeft': 0.9, 'browDownRight': 0.9, 'noseSneerLeft': 0.4, 'noseSneerRight': 0.4,
              'mouthFrownLeft': 0.4, 'mouthFrownRight': 0.4, 'eyeSquintLeft': 0.3, 'eyeSquintRight': 0.3},
    'sad': {'browInnerUp': 0.8, 'mouthFrownLeft': 0.7, 'mouthFrownRight': 0.7},
    'relaxed': {'mouthSmileLeft': 0.3, 'mouthSmileRight': 0.3, 'eyeBlinkLeft': 0.15, 'eyeBlinkRight': 0.15},
    'surprised': {'browInnerUp': 0.8, 'browOuterUpLeft': 0.8, 'browOuterUpRight': 0.8, 'eyeWideLeft': 0.7,
                  'eyeWideRight': 0.7, 'jawOpen': 0.45},
    'lookUp': {'eyeLookUpLeft': 1.0, 'eyeLookUpRight': 1.0},
    'lookDown': {'eyeLookDownLeft': 1.0, 'eyeLookDownRight': 1.0},
    'lookLeft': {'eyeLookOutLeft': 1.0, 'eyeLookInRight': 1.0},
    'lookRight': {'eyeLookInLeft': 1.0, 'eyeLookOutRight': 1.0},
}


def evaluate(controls, table):
    """the joints' (axis-angle sum (deg, world), translation (mm)) from control weights {name: w} (combos expanded)"""
    flat = {}
    for k, w in controls.items():
        if k in COMBOS:
            for c, cw in COMBOS[k].items():
                flat[c] = flat.get(c, 0.0) + w * cw
        else:
            flat[k] = flat.get(k, 0.0) + w
    rot, tr = {}, {}
    for c, w in flat.items():
        for e in table.get(c, []):
            if e[1] == 'rot':
                rot[e[0]] = rot.get(e[0], np.zeros(3)) + np.asarray(e[2], np.float64) * e[3] * w
            else:
                tr[e[0]] = tr.get(e[0], np.zeros(3)) + np.asarray(e[2], np.float64) * w
    return rot, tr


def axis_angle(v_deg):
    a = np.radians(np.linalg.norm(v_deg))
    if a < 1e-12:
        return np.eye(3)
    k = np.asarray(v_deg, np.float64) / np.linalg.norm(v_deg)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K


def globe_radius(cos_t):
    """the eye part's surface radius (mm) at the angle t from its optical axis (human_eye's globe: the sphere and the
    cornea's cap by its soft maximum)"""
    from . import human_eye as HE
    R = HE.GLOBE_D / 2.0
    zc, th_l, _ = HE.cornea_geom()
    t = np.arccos(np.clip(cos_t, -1.0, 1.0))
    s = np.sin(t)
    disc = HE.CORNEA_R ** 2 - (zc * s) ** 2
    rc = np.where(disc > 0, zc * np.cos(t) + np.sqrt(np.maximum(disc, 0.0)), 0.0)
    rc = np.where(np.cos(t) > 0, rc, 0.0)
    return 0.5 * (R + rc + np.sqrt((R - rc) ** 2 + HE.BLEND ** 2)) - 0.5 * HE.BLEND
