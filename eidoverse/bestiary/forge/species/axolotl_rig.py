"""AX10 (work/bestiary/research/AXOLOTL_PLAN.md §9, §11's AX10 row): THE AXOLOTL'S RIG on the AX4 low (families/sprawl.py's
124-joint skeleton, the animation craft guide AG 05 / 06): the skin WEIGHTS (§9.1), the joint LIMITS as data (§4.1's
ranges, the SPEC's rig r_* rows), the local rotations of a pose by its anatomical angles, and the MOTION (§9.3: the
salamander walk, the anguilliform swim, the idles) as functions of time.

THE LOW, WELDED (load_low): AX5's vertex set, the whole animal (work/bestiary/axolotl/cage_ax04_animal.npz: the forelimbs
L / R, the hindlimbs L / R, the six rami, then the body, its copy rings welded to the limbs' and rami's rings), the fin
membranes (cage_ax04_fins.npz) and the eyeballs (cage_ax04_eyes.npz, the left then the right), in that order: uv_ax05.npz's
`orig` maps every split vertex onto it, so the weights live on the welded set and every split copy takes its vertex's
(AG 00.43: identical on welded seams). x4 metres throughout (the skeleton's).

THE WEIGHTS (weights): a piece label per welded vertex, then by piece:
  * the BODY (head, trunk, tail; the body cage's regions): the axial ramp by station (families/sprawl.body_owners' bones
    and spans through rig.hat_weights: each vertex blends the two bones whose spans' middles bracket it), then the
    head's leaves: the JAW owns the lower lip and everything under the mouth line ahead of the hinge (the chin, the
    pearls on the lower lip's rows, the lower bag), fading to nothing by HEAD['jaw_fade'] TL behind the hinge (before the
    poll ring's collar: §9.1). The lips go BY THEIR RUN, not by height (lip_sides: the loop's upper run and the bag's
    upper wall on the head, the lower run and wall on the jaw, half each at the corners; the face skin within
    HEAD['lip_reach'] by the nearer run over the skin); the TONGUE the bag's deep floor; the THROAT the gular region's
    underside (a share peaking under its joint); the two BREATHERS a share of the ventral flank round their stations;
    the GILL BASES' skin (the body cage's gill ports and their fillet rings) to neck_0, the rami's parent, so a neck bend
    never shears a ramus off its port
  * a LIMB (its cage's vertices): projected on its chain of bones (fore: scapula, humerus, radius, carpus, metacarpus
    and each finger's two bones from the metacarpus; hind: femur, tibia, tarsus, metatarsus, each toe's) and ramped
    along it with blend zones LIMB['blend'] x the shorter bone round each joint; the TWIST leaves take their bone's
    half (humerus_twist / femur_twist the proximal half: they counter-rotate half the bone's own twist; radius_twist /
    tibia_twist the distal half: they carry half the hand's / foot's twist); the ROOT (from the body's footprint ring to
    the axilla / groin ring) blends the body's weights into the limb's (§9.1: the trunk-to-limb share across the port)
  * a RAMUS: projected on its chain (gill_r_0 .. 3 and its tip), ramped, and blended into neck_0 over its first
    RAMUS['root'] of the stalk (§9.1: along its own s, blended into neck_0 over the port's fillets)
  * a FIN vertex: the body's axial weights at its own station (§9.1: the body's weights at its root point; a fin column
    stands at one station over its root)
  * an EYEBALL: rigid on eye_L / eye_R
  * a FILAMENT instance (uv_ax05's fil_*): rigid on its ramus's weights at its root (§9.1): the smoothed skin field at
    the closest point of the ramus's triangles to its root, barycentric (filament_weights)
then smoothed (rig.smooth_field: SMOOTH['iters'] passes, the eyes, the lips and the bag held) and cut to four influences
(rig.limit_influences, continuous).

POSES (local): a joint's rotation from its anatomical angles in its own frame (sprawl.py's: x along the bone, y the side
it folds toward, z = x cross y): FOLD about z (+ the anatomical way: flexion, ventral, the gill laid back, the elbow and
the knee closing), SPLAY about -y (sprawl.swing_angles' convention), TWIST about x; R = Rz(fold) Ry(-splay) Rx(twist).
"""
import math

import numpy as np

from .. import rig as RG

# ============================================================================================ the tables
LIMB = dict(blend=0.35, root_ring=('ring_footprint', 'ring_axilla'), twist_share=0.5, root_ext=11.0, root_past=3.0,
            girdle=1.0, root_ext_hind=12.5, diag_graph=('hind',))
# (AX13 restart, 11-02 15:4x: THE HIND ROOT'S blend by skin distances over the quads' DIAGONALS too (diag_graph names the
# limb kinds) and reaching root_ext_hind 12.5 mm (root_ext 11 the fore's, as AX10b shipped it). By the quads' sides
# alone a body vertex one diagonal (1.35 mm) ahead of another in front of the thigh read 3.1 mm further from the
# footprint ring (7.41 against 4.31: the path round two sides), so the limb's share fell 0.44 across that diagonal and
# gate 11 on every glb edge read x3.74 there at swim 5/12 (ax13_notes/try/hip_weights.py). Over the 69 motion poses with
# the AX13 correctives (edge_probe.py): diag_graph alone x3.18; + no hip corrective x3.05; root_ext 10 x3.29 (the knee
# x3.29), 12 x2.87, 12.5 x2.78, 13 x2.70 (the shoulder x0.28), 13.5 x2.60 (the knee x0.39): 12.5 is the plateau's middle.
# On the fore too it reached the third gill's socket beside the shoulder (its port 0.19 mm from that footprint, AX3): 4
# filament roots out of r3 at neck_0 fold -35 (gate 5) and their drift 1.017 mm life (gate 6))
# (AX10b continuation, 11-02: root_ext 6 -> 11 once the skin distances were true (weights()' graph had every inner edge
# at twice its length, so the 6 mm reach was ~3 mm of skin): over gates 9 and 11's 69 motion poses with the girdle on
# (ax10b_notes/try/c_girdle.py, logs/c_girdle4-5.log) 6 -> the hip x3.27, 9 -> x2.72 but a squash x0.14, 10 and 11 ->
# det 0.784 / 0.781, the edges x0.37..x2.68 (the worst a wrist in the walk, the hip's x2.67), 12 -> x0.29..x2.69,
# 14 -> the shoulder x3.41; the girdle off at 12: det 0.742. 11 is the plateau's middle)
# (AX10b continuation, 11-02: THE LIMB RIDES ITS GIRDLE. The root blend's body side is the axial hat ramp at each
# vertex's station, so the thigh's own root skin, between the pelvis (z 0) and spine_0's joint (9.1 mm ahead), carried
# spine_0 0.02-0.33 beside hip_pt and the pelvis; the swim's wave turns spine_0 +-15.5 deg against the pelvis, and that
# share swung the thigh's root ~5 mm x share sideways: gate 11's worst, three 0.52-0.68 mm edges on the thigh's front at
# x4.2 when spine_0 turned toward the leg, x2.2 when away (ax10b_notes/try/c_hip_root.py). `girdle`: the share of the
# body side's axial weight (every body owner but the girdle) moved onto the limb's girdle (its first bone's parent: the
# pelvis for the hindlimb, spine_6 for the forelimb) on the limb's own skin, fading to none over the body's root_ext ring
# by skin distance (no step at the footprint ring); 0 = off)
# (AX10b, 11-02: the trunk-to-limb blend by SKIN DISTANCE from the limb's footprint ring (Dijkstra over the quads): it
# reaches root_ext life mm out over the BODY's skin and runs down the limb to the axilla / groin ring plus root_past mm.
# By the station along the chain it spanned ~3 rows from the footprint ring (the port's copy / half / loop rings sit
# within 1 mm of each other) and differed round each slanted ring, so in the swim's thigh laid back 93 deg two
# neighbours met 0.4 of the blend apart: once the helpers stopped the collapse (det 0.42 -> 0.80) that step showed as
# x9.4 edges at the hip root. By skin distance: 4 / 1.5 mm x5.5, 6 / 3 x4.45, 8 / 3 x4.46 (the cage is coarse: 18
# body vertices lie within 4 mm of the hind footprint ring); the walk's hip zone x1.35-1.55 at all of them)
HELPER = dict(share=0.5)
# (AX10, 11-02: the elbow's and the knee's HALF-ANGLE HELPERS, sprawl.py's elbow_pt / knee_pt moved onto the hinge's axis
# (SPEC rig olecranon / knee_pt 0, 0) in the forearm's / shank's own frame, children of the humerus / femur: each turns
# `share` of its driver's local rotation about the hinge (drivers()) and carries the bend's blend zone (limb_weights), so
# the skin blends between transforms half the bend apart; with the bend alone LBS lost 13.8 % of the elbow's local volume
# at 152 deg and 16.0 % of the knee's at 145 (tests/ax10_rig.py --only hinge). The runtime drives them the same way:
# a helper's local rotation = slerp(I, its driver's local rotation, share), the glb's extras carry the rule (AX11))
HELPERS = dict(fore=(('shoulder_pt', None, ('humerus', 'humerus_twist')),
                     ('elbow_pt', ('humerus', 'humerus_twist'), ('radius', 'radius_twist')),
                     ('wrist_pt', ('radius', 'radius_twist'), ('carpus',))),
               hind=(('hip_pt', None, ('femur', 'femur_twist')),
                     ('knee_pt', ('femur', 'femur_twist'), ('tibia', 'tibia_twist')),
                     ('ankle_pt', ('tibia', 'tibia_twist'), ('tarsus',))))
# (AX10b, 11-02: EVERY LIMB JOINT THE SWIM FOLDS gets its half-angle helper (SPEC rig helpers_x10b; families/
# sprawl.skeleton): per limb (helper, the upper group, the lower group) as resplit() reads them, the twist leaves in
# their bone's group; None = the ROOT's upper group, every influence that is not the limb's own past the root (the
# body's axial bones, the scapula at the shoulder). The check measured the swim's folded limbs per vertex (det of the
# blended rotation): the hip root 0.39-0.48 (the body's spine_0 / pelvis and the femur 93-108 deg apart), the wrist 0.61
# (radius_twist and carpus 78 deg apart). A helper only holds if a vertex's influences stay half the bend apart after
# the smoothing too: resplit() runs in limb_weights and again after it (weights(); the check's helper_trial.py: the
# knee's v2221 carried tibia 0.558 / femur 0.230 / knee_pt 0.211 after the smoothing, 80 deg apart at 165)
RAMUS = dict(root=0.14)
HEAD = dict(jaw_fade=(-0.008, 0.015), jaw_y=0.25, tongue_depth=(2.0, 3.0), tongue=0.6, throat_s=(0.100, 0.140, 0.185),
            throat=0.65, throat_y=(0.55, 0.20), breath=0.35, breath_w=0.045, breath_y=(0.50, 0.15),
            lip_corner=1.2, lip_reach=(1.0, 2.0), lip_blend=0.5)
# (AX13, 11-02: lip_reach (2.0, 4.0) -> (1.0, 2.0) and lip_blend 1.0 -> 0.5 with lip_sides' skin graph deduplicated: the
# old graph listed every shared edge twice and coo_matrix summed them, so its distances ran 2x the skin's and these were
# tuned on them; halved, they cover the same skin as shipped, now on the honest metric; gate 8 re-run)
# (AX10 successor, 11-02: THE LIPS BY THEIR RUN (lip_sides), mm life: lip_corner the arc from each corner along a run over
# which the pair's shares blend to half each at the corner; lip_reach the skin distance from the loop inside which the
# face follows the nearer run, fading to the height rule by the second; lip_blend the run distances' difference over which
# that side blends. By height against the slit's station-binned middle (AX7b-AX10's first runs) the upper lip's front read
# 0.55-1.0 jaw (the U's front: one bin held the upper lip alone), six lower-lip vertices 0 and 21-43 upper-wall vertices
# a bag ring the jaw's: the jaw at 40 tore the mouth into shards (tests/out/axolotl/ax10_sweeps_worst.png, rig13))
SMOOTH = dict(iters=3, alpha=0.5)
FORE = ('scapula', 'humerus', 'radius', 'carpus', 'metacarpus')
HIND = ('femur', 'tibia', 'tarsus', 'metatarsus')


# ============================================================================================ rotations
def rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def local(fold=0.0, splay=0.0, twist=0.0):
    """a joint's local rotation from its anatomical angles in degrees (the module docstring)"""
    return rz(math.radians(fold)) @ ry(-math.radians(splay)) @ rx(math.radians(twist))


def compose(*poses):
    """local rotation dicts multiplied joint by joint (a later pose's rotation applied after the earlier one's)"""
    out = {}
    for p in poses:
        for k, R in p.items():
            out[k] = out[k] @ R if k in out else R
    return out


# ============================================================================================ the limits (§4.1)
def limits(spec):
    """§4.1's ranges as data, degrees, in the local() angles: {joint pattern: {angle: (lo, hi)}} (a pattern with '{s}'
    is per side). The elbow and the knee are given as INCLUDED angles in the SPEC; ranges_for() turns them into folds
    about the bind's own included angle"""
    rg = spec['rig']
    sp, nk, tl = rg['r_spine'], rg['r_neck'], rg['r_tail']
    hu, fe = rg['r_humerus'], rg['r_femur']
    L = {
        'spine_{k}': dict(splay=(-sp[0], sp[0]), fold=(-sp[1], sp[1]), twist=(-sp[2], sp[2])),
        'neck_0': dict(splay=(-nk[0], nk[0]), fold=(-nk[2], -nk[1])),          # pitch +35 = raised = fold -35
        'jaw': dict(fold=(rg['r_jaw'][0], rg['r_jaw'][1])),
        'eye_{s}': dict(fold=(-rg['r_gaze'], rg['r_gaze']), splay=(-rg['r_gaze'], rg['r_gaze'])),
        # (the gills' as sums over a stalk's four joints; the splay toward the neighbours r_gill_splay_in, AX10's sweep)
        'gill_{r}_{j}_{s}': dict(fold=tuple(rg['r_gill_fold']), splay=(-rg['r_gill_splay_in'], rg['r_gill_splay'])),
        'humerus_{s}': dict(fold=(-hu[0], hu[0]), splay=(-hu[2], -hu[1]), twist=(-hu[3], hu[3])),   # splay + = down
        'radius_{s}': dict(included=tuple(rg['r_elbow'])),
        # (the swim's adpressed limbs past the walk's: the wrist and the ankle straightened, the thigh laid back)
        'carpus_{s}': dict(fold=(-rg['r_wrist'], rg['r_wrist_ext'])),
        'f_digit{d}_{j}_{s}': dict(fold=tuple(rg['r_digit_curl']), splay=(-rg['r_digit_splay'], rg['r_digit_splay'])),
        'femur_{s}': dict(fold=(-rg['r_femur_back'], fe[0]), splay=(-fe[2], -fe[1]), twist=(-fe[3], fe[3])),
        'tibia_{s}': dict(included=tuple(rg['r_knee'])),
        'tarsus_{s}': dict(fold=(-rg['r_ankle'], rg['r_ankle_ext'])),
        'h_digit{d}_{j}_{s}': dict(fold=tuple(rg['r_digit_curl']), splay=(-rg['r_digit_splay'], rg['r_digit_splay'])),
        'tail_{k}': dict(splay=(-tl[0], tl[0]), fold=(-tl[1], tl[1]), twist=(-tl[2], tl[2])),
    }
    return L


def included_angle(sk, name):
    """the bind's included angle (deg) at a hinge joint: between its parent's start and its child (or tip)"""
    i = sk.index(name)
    p = sk.parent[i]
    pj = sk.world[p][:3, 3]
    jj = sk.world[i][:3, 3]
    kids = [k for k, q in enumerate(sk.parent) if q == i and sk.meta[sk.names[k]]['role'] not in ('twist', 'helper')]
    cj = sk.world[kids[0]][:3, 3] if kids else sk.meta[name]['tip']
    a, b = pj - jj, cj - jj
    return float(np.degrees(np.arccos(np.clip(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)), -1.0, 1.0))))


def fold_for_included(sk, name, inc):
    """the fold (deg) that sets a hinge's included angle to inc: a positive fold closes it"""
    return included_angle(sk, name) - inc


# ============================================================================================ the low
def load_low(out_a):
    """the welded low (the module docstring) with its pieces: dict(V (N, 3) x4 m, Q (q, 4), piece (N,) labels, side,
    idx ranges, the body cage's records, the fins', the eyes', uv (uv_ax05's arrays))"""
    import os
    A = np.load(os.path.join(out_a, 'cage_ax04_animal.npz'))
    B = np.load(os.path.join(out_a, 'cage_ax04_body.npz'))
    FN = np.load(os.path.join(out_a, 'cage_ax04_fins.npz'))
    EY = np.load(os.path.join(out_a, 'cage_ax04_eyes.npz'))
    FL = np.load(os.path.join(out_a, 'cage_ax04_forelimb.npz'))
    HL = np.load(os.path.join(out_a, 'cage_ax04_hindlimb.npz'))
    RA = np.load(os.path.join(out_a, 'cage_ax04_rami.npz'))
    UVZ = dict(np.load(os.path.join(out_a, 'uv_ax05.npz'), allow_pickle=False))
    Va = A['V_x4']
    na, nf, ne = len(Va), len(FN['V_x4']), len(EY['V_x4'])
    V = np.vstack([Va, FN['V_x4'], EY['V_x4']])
    Q = np.vstack([A['Q'], FN['Q'] + na, EY['Q'] + na + nf])
    n_fl, n_hl, n_ra = len(FL['V_x4']), len(HL['V_x4']), len(RA['V_x4'])
    nr = n_ra // 6
    piece = np.full(len(V), 'body', dtype=object)
    side = np.full(len(V), '', dtype=object)
    piece[:n_fl] = 'fore'
    side[:n_fl // 2], side[n_fl // 2:n_fl] = 'L', 'R'
    piece[n_fl:n_fl + n_hl] = 'hind'
    side[n_fl:n_fl + n_hl // 2], side[n_fl + n_hl // 2:n_fl + n_hl] = 'L', 'R'
    ramus = np.full(len(V), 0, int)
    for r in (1, 2, 3):
        for s_ in 'LR':
            o = n_fl + n_hl + nr * (2 * (r - 1) + (s_ == 'R'))
            piece[o:o + nr] = 'ramus'
            side[o:o + nr] = s_
            ramus[o:o + nr] = r
    piece[na:na + nf] = 'fin'
    piece[na + nf:] = 'eye'
    ns = int(EY['n_side'])
    side[na + nf:na + nf + ns], side[na + nf + ns:] = 'L', 'R'
    assert len(UVZ['orig']) == len(UVZ['V_x4']) and UVZ['orig'].max() < len(V), 'uv_ax05 is not this low'
    assert np.abs(V[UVZ['orig']] - UVZ['V_x4']).max() < 1e-9, 'uv_ax05\'s vertices are not this welded low\'s'
    # the body cage's vertices in the animal (body_ids) and its regions
    bid = A['body_ids']
    breg = np.array([str(r) for r in B['regions']])[B['part'].argmax(1)]
    body_region = np.full(len(V), '', dtype=object)
    body_region[bid] = breg
    rings = {k: (bid[B[k]] if k.startswith(('port_', 'ring_', 'mouth_loop', 'gular')) else B[k])
             for k in B.files if k.startswith(('port_', 'ring_')) or k in ('mouth_loop',)}
    limb_rings = {}
    for nm, Z, off in (('fore', FL, 0), ('hind', HL, n_fl)):
        for k in Z.files:
            if k.startswith('ring_'):
                limb_rings[k] = Z[k] + off
    rami_rings = {k: RA[k] + n_fl + n_hl for k in RA.files if k.startswith('ring_gill_')}
    # the mouth's bag (families/sprawl_body.mouth: its rings appended in order, each in the lip loop's order, the loop's
    # first half the upper lip's run; the upper wall's vertex k half_j above the lower wall's K - 1 - k): (rings, K)
    m_bag = np.nonzero(breg == 'mouth')[0]
    K_ = len(B['mouth_loop'])
    assert len(m_bag) % K_ == 0 and (np.diff(m_bag) == 1).all(), 'the bag is not whole rings in order'
    bag = bid[m_bag].reshape(-1, K_)
    k_up = np.arange(K_ // 2)
    dy = V[bag[:, k_up], 1] - V[bag[:, K_ - 1 - k_up], 1]
    assert (dy > 0).all() and (np.ptp(dy, axis=1) < 1e-3 * dy.mean(1)).all(), 'the bag\'s rings are not upper / lower pairs'
    return dict(V=V, Q=Q, piece=piece, side=side, ramus=ramus, na=na, nf=nf, ne=ne, n_fl=n_fl, n_hl=n_hl, nr=nr,
                body_ids=bid, body_region=body_region, body_rings=rings, limb_rings=limb_rings, rami_rings=rami_rings,
                mouth_bag=bag, fin_roots=FN['roots'] + na, fin_seg=dict(name=FN['seg_name'], v=FN['seg_v']), uv=UVZ)


# THE RINGS' CONTRACT (graft.ring_problems, AX11's gate 6; plan §6.1): each ring record's native group is its ROOT
# joint's descendants; no vertex on the ring or on the base's side of it may carry weight on them (a graft swaps the
# native group and keeps the base: the base's vertices must be expressible without it). The roots as tests/ax11_glb.py
# writes the records
RING_ROOT = dict(poll='head', tail_root='tail_2', tail_mid='tail_7')
for _sd in 'LR':
    RING_ROOT.update({f'axilla_{_sd}': f'radius_{_sd}', f'forearm_{_sd}': f'carpus_{_sd}',
                      f'hand_{_sd}': f'metacarpus_{_sd}', f'groin_{_sd}': f'tibia_{_sd}',
                      f'shank_{_sd}': f'tarsus_{_sd}', f'foot_{_sd}': f'metatarsus_{_sd}'})
    for _r in (1, 2, 3):
        RING_ROOT[f'gill_{_r}_{_sd}'] = f'gill_{_r}_1_{_sd}'


def ring_ids(low):
    """the welded low's ring records' vertices: {ring name: ids}"""
    out = {}
    for sd in 'LR':
        for k in ('axilla', 'forearm', 'hand', 'groin', 'shank', 'foot'):
            out[f'{k}_{sd}'] = np.asarray(low['limb_rings'][f'ring_{k}_{sd}'])
        for r in (1, 2, 3):
            out[f'gill_{r}_{sd}'] = np.asarray(low['rami_rings'][f'ring_gill_{r}_{sd}'])
    for k in ('poll', 'tail_root', 'tail_mid'):
        out[k] = np.asarray(low['body_rings'][f'ring_{k}'])
    return out


def ring_contract(sk, low, W):
    """the rings' contract (RING_ROOT's note) laid on the dense weights W (N, J): on each ring and its base's side (a
    flood from the trunk that may not cross the ring; the separate pieces, the fins and the eyes, by their weights: half
    or more native counts beyond), every weight on the ring root's descendants moved onto the root. Returns (W, the
    weight moved per ring)"""
    V, Q, na = low['V'], low['Q'], low['na']
    adj = [[] for _ in range(na)]
    for q in Q:
        if q.max() < na:
            for k in range(4):
                a, b = int(q[k]), int(q[(k + 1) % 4])
                adj[a].append(b)
                adj[b].append(a)
    seed = int(np.argmin(np.linalg.norm(V[:na] - sk.world[sk.index('spine_3')][:3, 3], axis=1)))
    kids = {}
    for i, p in enumerate(sk.parent):
        kids.setdefault(p, []).append(i)
    sep = np.arange(na, len(V))
    moved = {}
    for nm, ids in ring_ids(low).items():
        root = sk.index(RING_ROOT[nm])
        desc, st_ = [], [root]
        while st_:
            for c in kids.get(st_.pop(), []):
                desc.append(c)
                st_.append(c)
        ring = set(int(v) for v in ids)
        seen, st_ = {seed}, [seed]
        while st_:
            v = st_.pop()
            for w in adj[v]:
                if w not in seen and w not in ring:
                    seen.add(w)
                    st_.append(w)
        base = np.array(sorted(seen | ring), int)
        sep_base = sep[W[np.ix_(sep, desc)].sum(1) + W[sep, root] < 0.5]
        cl = np.concatenate([base, sep_base])
        m = W[np.ix_(cl, desc)].sum(1)
        W[cl, root] += m
        W[np.ix_(cl, desc)] = 0.0
        moved[nm] = float(m.sum())
    return W, moved


# ============================================================================================ chains
def project_polyline(P, J):
    """each point's nearest point on the polyline J (m, 3): (station along it, distance, segment index, t on it)"""
    P = np.asarray(P, np.float64)
    J = np.asarray(J, np.float64)
    seg_a, seg_b = J[:-1], J[1:]
    d = seg_b - seg_a
    L = np.linalg.norm(d, axis=1)
    cum = np.concatenate([[0.0], np.cumsum(L)])
    best_d = np.full(len(P), np.inf)
    best_s = np.zeros(len(P))
    best_k = np.zeros(len(P), int)
    best_t = np.zeros(len(P))
    for k in range(len(seg_a)):
        t = np.clip(((P - seg_a[k]) @ d[k]) / max(L[k] ** 2, 1e-30), 0.0, 1.0)
        q = seg_a[k] + t[:, None] * d[k]
        dist = np.linalg.norm(P - q, axis=1)
        m = dist < best_d
        best_d[m], best_s[m], best_k[m], best_t[m] = dist[m], cum[k] + t[m] * L[k], k, t[m]
    return best_s, best_d, best_k, best_t


def ramp(s, J_s, blend):
    """weights over the bones of a chain at stations s: bone k owns [J_s[k], J_s[k + 1]]; round each inner joint a
    blend zone of half-width blend x the shorter of its two bones, a smoothstep between them. Returns (n, m) weights"""
    J_s = np.asarray(J_s, np.float64)
    m = len(J_s) - 1
    lens = np.diff(J_s)
    W = np.zeros((len(s), m))
    k = np.clip(np.searchsorted(J_s, s, side='right') - 1, 0, m - 1)
    W[np.arange(len(s)), k] = 1.0
    for j in range(1, m):
        h = blend * min(lens[j - 1], lens[j])
        u = np.clip((s - (J_s[j] - h)) / (2.0 * h), 0.0, 1.0)
        zone = (s > J_s[j] - h) & (s < J_s[j] + h)
        w1 = u * u * (3.0 - 2.0 * u)
        W[zone] = 0.0
        W[zone, j - 1] = 1.0 - w1[zone]
        W[zone, j] = w1[zone]
    return W


# ============================================================================================ the weights
def body_axial(spec, chain, sk, P):
    """the body's axial weights at points P (x4 m): (n, J) dense, the owners' hat ramp by station"""
    from ..families import sprawl as SP
    owners, edges = SP.body_owners(spec, chain)
    TL = spec['a1']['TL']
    s = spec['stations']['hip'] - (np.asarray(P)[:, 2] / chain['k']) / TL
    k0, k1, t = RG.hat_weights(s, edges)
    W = np.zeros((len(P), len(sk.names)))
    ow = np.array([sk.index(n) for n in owners])
    k0, k1 = np.minimum(k0, len(owners) - 1), np.minimum(k1, len(owners) - 1)
    np.add.at(W, (np.arange(len(P)), ow[k0]), 1.0 - t)
    np.add.at(W, (np.arange(len(P)), ow[k1]), t)
    return W, s


def root_ext(kind):
    """the limb kind's root blend reach over the body's skin (life mm; LIMB's AX13 note)"""
    return float(LIMB.get(f'root_ext_{kind}', LIMB['root_ext']))


def limb_weights(spec, chain, sk, low, kind, side, idx, ext=None, geo=None):
    """a limb's vertices' weights (the module docstring), (len(idx), J) dense, plus each vertex's share of the limb.
    ext: (body vertex ids, their skin distance to the limb's footprint ring in life mm, their body weights (n, J)), the
    root's blend reaching onto the body by LIMB['root_ext'] (AX10b): their rows come back as the fourth value.
    geo: (the limb vertices' skin distance from the footprint ring, life mm (n,), the zone's length on the limb, life
    mm): the root's blend by those distances (the rings) instead of the station along the chain (AX10b)"""
    n_l = len(idx)
    if ext is not None:
        idx = np.concatenate([np.asarray(idx), np.asarray(ext[0])])
    V = low['V'][idx]
    pos = lambda n: sk.world[sk.index(n)][:3, 3]                                   # noqa: E731
    sx = f'_{side}'
    if kind == 'fore':
        main = list(FORE)
        pts = [pos(n + sx) for n in main] + [sk.meta['metacarpus' + sx]['tip']]
        digits = [(f'f_digit{d}', d) for d in range(1, 5)]
        root_bone = 'scapula' + sx
    else:
        main = list(HIND)
        pts = [pos(n + sx) for n in main] + [sk.meta['metatarsus' + sx]['tip']]
        digits = [(f'h_digit{d}', d) for d in range(1, 6)]
        root_bone = 'femur' + sx
    J = len(sk.names)
    W = np.zeros((len(V), J))
    s_m, d_m, k_m, t_m = project_polyline(V, pts)
    J_m = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(np.array(pts), axis=0), axis=1))])
    best = d_m.copy()
    owner = np.full(len(V), -1)
    dig = {}
    meta_pos = pos(main[-1] + sx)
    for nm, d in digits:
        dp = [meta_pos, pos(f'{nm}_0{sx}'), pos(f'{nm}_1{sx}'), sk.meta[f'{nm}_1{sx}']['tip']]
        s_d, d_d, k_d, t_d = project_polyline(V, dp)
        # a digit takes the vertex past its own base (k >= 1: the digit's two bones), nearer than the main chain
        m = (k_d >= 1) & (d_d < best)
        best[m], owner[m] = d_d[m], d
        dig[d] = (dp, s_d)
    Wm = ramp(s_m, J_m, LIMB['blend'])
    bones_m = [sk.index(n + sx) for n in main]
    sel = owner < 0
    W[np.ix_(sel, bones_m)] = Wm[sel]
    for nm, d in digits:
        sel = owner == d
        if not sel.any():
            continue
        dp, s_d = dig[d]
        J_d = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(np.array(dp), axis=0), axis=1))])
        Wd = ramp(s_d[sel], J_d, LIMB['blend'])
        bones_d = [sk.index(main[-1] + sx), sk.index(f'{nm}_0{sx}'), sk.index(f'{nm}_1{sx}')]
        W[np.ix_(sel, bones_d)] = Wd
    up, lo = (('humerus', 'radius') if kind == 'fore' else ('femur', 'tibia'))
    # the twist leaves (the module docstring): the upper bone's proximal half, the lower bone's distal half
    for bone, k_seg, prox in ((up, main.index(up), True), (lo, main.index(lo), False)):
        b, tw = sk.index(bone + sx), sk.index(bone + '_twist' + sx)
        on = (owner < 0) & (k_m == k_seg)
        u = t_m[on]
        share = (1.0 - np.clip((u - 0.15) / 0.5, 0.0, 1.0)) if prox else np.clip((u - 0.35) / 0.5, 0.0, 1.0)
        share = share * share * (3.0 - 2.0 * share) * LIMB['twist_share'] * 2.0
        share = np.minimum(share, 1.0)
        rows = np.nonzero(on)[0]
        moved = W[rows, b] * share
        W[rows, b] -= moved
        W[rows, tw] += moved
    # the root: the body's axial weights blending into the limb's, from the footprint ring to the axilla / groin ring
    lr = low['limb_rings']
    ring0 = lr.get(f'ring_footprint_{kind}_{side}')
    ring1 = lr.get(f'ring_axilla_{side}' if kind == 'fore' else f'ring_groin_{side}')
    s0 = float(np.mean(project_polyline(low['V'][ring0], pts)[0])) if ring0 is not None else J_m[1]
    s1 = float(np.mean(project_polyline(low['V'][ring1], pts)[0])) if ring1 is not None else J_m[1] + 0.3 * (J_m[2] - J_m[1])
    # (AX10b: the blend begins LIMB['root_ext'] out on the body's skin, so the footprint ring itself is part way; with
    # geo, the limb's side by its skin distance from the footprint ring over the zone's length: a ring is one share all
    # round, where the station along the chain differed round the slanted rings and two neighbours met 0.4 of t apart)
    re_ = root_ext(kind)
    e_m = re_ * chain['k']
    if geo is not None:
        z_m = float(geo[1]) * chain['k']
        u = np.zeros(len(V))
        u[:n_l] = (np.asarray(geo[0]) * chain['k'] + e_m) / max(z_m + e_m, 1e-9)
    else:
        z_m = s1 - s0
        u = (s_m - s0 + e_m) / max(z_m + e_m, 1e-9)
    if ext is not None:
        u[n_l:] = (e_m - np.asarray(ext[1]) * chain['k']) / max(z_m + e_m, 1e-9)
    u = np.clip(u, 0.0, 1.0)
    share = np.where(owner < 0, u * u * (3.0 - 2.0 * u), 1.0)
    Wb, _ = body_axial(spec, chain, sk, V)
    if ext is not None:
        Wb[n_l:] = ext[2]
    if LIMB.get('girdle', 0.0) > 0.0:
        # THE LIMB RIDES ITS GIRDLE (LIMB's note): the body side's axial weight onto the girdle, all of `girdle` on the
        # limb's own skin, fading over the body's root_ext ring by skin distance from the footprint ring
        from ..families import sprawl as SP
        gi = int(sk.parent[sk.index(main[0] + sx)])
        ax_i = [sk.index(n) for n in SP.body_owners(spec, chain)[0] if sk.index(n) != gi]
        g = np.full(len(V), float(LIMB['girdle']))
        if ext is not None:
            f_ = np.clip(1.0 - np.asarray(ext[1]) / re_, 0.0, 1.0)
            g[n_l:] *= f_ * f_ * (3.0 - 2.0 * f_)
        moved = Wb[:, ax_i] * g[:, None]
        Wb[:, ax_i] -= moved
        Wb[:, gi] += moved.sum(1)
        info_g = dict(girdle=sk.names[gi], moved_limb=float(moved[:n_l].sum(1).max()) if n_l else 0.0)
    else:
        info_g = {}
    W = share[:, None] * W + (1.0 - share)[:, None] * Wb
    # THE HALF-ANGLE HELPERS (HELPER's and HELPERS' notes; AX10's elbow / knee, AX10b's root and wrist / ankle): each
    # joint's blend re-split onto its helper, which turns half the bend, so no vertex blends across the whole bend
    for h_, ug, lg in limb_groups(sk, kind, side):
        W, _ = resplit(W, ug, h_, lg)
    info = dict(s0=s0, s1=s1, root_bone=root_bone, **info_g)
    if ext is not None:
        return W[:n_l], share[:n_l], info, W[n_l:]
    return W, share, info


def _descendants(sk, i):
    kids = {}
    for k, p in enumerate(sk.parent):
        kids.setdefault(p, []).append(k)
    out, st = [], [i]
    while st:
        for c in kids.get(st.pop(), []):
            out.append(c)
            st.append(c)
    return out


def limb_groups(sk, kind, side):
    """a limb's half-angle helpers with their upper and lower groups as joint indices (HELPERS' note): [(helper,
    upper (n,), lower (m,))]; a helper the skeleton lacks is left out (a skeleton built before AX10b)"""
    sx = f'_{side}'
    out = []
    for h, up, lo in HELPERS[kind]:
        if h + sx not in sk.names:
            continue
        lo_i = np.array([sk.index(n + sx) for n in lo])
        if up is None:
            # the root: every influence but the limb's own past it (the lower bone's subtree and the helper)
            past = set(_descendants(sk, int(lo_i[0]))) | set(int(j) for j in lo_i) | {sk.index(h + sx)}
            up_i = np.array([j for j in range(len(sk.names)) if j not in past])
        else:
            up_i = np.array([sk.index(n + sx) for n in up])
        out.append((sk.index(h + sx), up_i, lo_i))
    return out


def resplit(W, up, h, lo):
    """THE HALF-ANGLE PROJECTION (HELPER's note) on dense weights W (N, J), in place: every vertex carrying both the
    upper group's weight u and the lower group's l keeps the trio's total u + h + l and its mean bend position
    t = (h / 2 + l) / (u + h + l), re-split so its influences sit half the bend apart: t <= 1/2 -> (1 - 2t) upper + 2t
    helper, else (2 - 2t) helper + (2t - 1) lower, each group's bones keeping their proportions. A vertex with one side
    and the helper already keeps the rule and is left as it is. Returns (W, how many vertices were re-split)"""
    wu = W[:, up].sum(1)
    wl = W[:, lo].sum(1)
    r = np.nonzero((wu > 1e-9) & (wl > 1e-9))[0]
    if not len(r):
        return W, 0
    u_, l_, h_ = wu[r], wl[r], W[r, h]
    tot = u_ + l_ + h_
    t = (0.5 * h_ + l_) / tot
    nu = np.where(t <= 0.5, (1.0 - 2.0 * t) * tot, 0.0)
    nl = np.where(t > 0.5, (2.0 * t - 1.0) * tot, 0.0)
    W[np.ix_(r, up)] *= (nu / u_)[:, None]
    W[np.ix_(r, lo)] *= (nl / l_)[:, None]
    W[r, h] = tot - nu - nl
    return W, len(r)


def ramus_weights(spec, chain, sk, P, r, side):
    """a ramus's weights at points P (its cage's vertices, or the filaments' roots): the chain ramp blended into neck_0
    over its stalk's first RAMUS['root']"""
    pos = lambda n: sk.world[sk.index(n)][:3, 3]                                   # noqa: E731
    names = [f'gill_{r}_{j}_{side}' for j in range(4)]
    pts = [pos(n) for n in names] + [sk.meta[names[-1]]['tip']]
    s, d, k, t = project_polyline(P, pts)
    J_s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(np.array(pts), axis=0), axis=1))])
    Wr = ramp(s, J_s, LIMB['blend'])
    W = np.zeros((len(P), len(sk.names)))
    W[:, [sk.index(n) for n in names]] = Wr
    u = np.clip(s / (RAMUS['root'] * J_s[-1]), 0.0, 1.0)
    share = u * u * (3.0 - 2.0 * u)
    W *= share[:, None]
    W[:, sk.index('neck_0')] += 1.0 - share
    return W


def lip_sides(low, k_m):
    """THE LIPS BY THEIR RUN (HEAD lip_*'s note): the jaw's share by the side of the slit each mouth vertex lies on in
    the cage, not by its height. The lip loop's upper run (its first K / 2) and the bag's upper wall take 0, the lower run
    and wall 1, both blending to half each over HEAD['lip_corner'] mm of arc from each corner (a pair shares one value
    for its arc); the other body vertices within HEAD['lip_reach'] of the loop OVER THE SKIN (Dijkstra on the body's
    quad edges with the bag left out, so no path crosses the slit) take the nearer run's side, blended over
    HEAD['lip_blend'] of the two distances' difference. Returns (the share (N,), how much it rules (N,): 1 on the loop,
    the bag and within the reach's first value, 0 past its second; the lower wall (N,) bool, notes)"""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra
    V, Q = low['V'], low['Q']
    N = len(V)
    loop = np.asarray(low['body_rings']['mouth_loop'])
    bag = np.asarray(low['mouth_bag'])
    K = len(loop)
    n_up = K // 2
    Pu = V[loop[:n_up]]
    arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Pu, axis=0), axis=1))]) / k_m
    g = np.clip(np.minimum(arc, arc[-1] - arc) / HEAD['lip_corner'], 0.0, 1.0)
    g = g * g * (3.0 - 2.0 * g)
    w_up = 0.5 * (1.0 - g)
    w_k = np.concatenate([w_up, (1.0 - w_up)[::-1]])         # the loop's K: the lower run's k' pairs with K - 1 - k'
    w = np.zeros(N)
    rule = np.zeros(N)
    # the face: each run's distance over the skin
    skin = low['piece'] == 'body'
    skin[bag.ravel()] = False
    E = np.concatenate([Q[:, [0, 1]], Q[:, [1, 2]], Q[:, [2, 3]], Q[:, [3, 0]]])
    E = E[skin[E[:, 0]] & skin[E[:, 1]]]
    # (AX13, 11-02: each edge ONCE. AX10b's continuation found that an edge two quads share was listed twice here and
    # coo_matrix SUMS duplicates, so an inner edge weighed twice its length and these distances ran ~2x the skin's;
    # HEAD lip_reach / lip_blend are halved with it (their note), and gate 8 re-run)
    E = np.unique(np.sort(E, axis=1), axis=0)
    Lg = np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1) / k_m
    G = coo_matrix((np.concatenate([Lg, Lg]), (np.concatenate([E[:, 0], E[:, 1]]), np.concatenate([E[:, 1], E[:, 0]]))),
                   shape=(N, N)).tocsr()
    lim = 2.0 * HEAD['lip_reach'][1]
    d_up = dijkstra(G, indices=loop[:n_up], min_only=True, limit=lim)
    d_lo = dijkstra(G, indices=loop[n_up:], min_only=True, limit=lim)
    d = np.minimum(d_up, d_lo)
    with np.errstate(invalid='ignore'):                      # (both unreached: inf - inf, ruled out by d below)
        dd = np.nan_to_num(d_up - d_lo, nan=0.0, posinf=1e9, neginf=-1e9)
    t = np.clip(0.5 + 0.5 * dd / HEAD['lip_blend'], 0.0, 1.0)
    face = skin & np.isfinite(d)
    w[face] = (t * t * (3.0 - 2.0 * t))[face]
    a, b = HEAD['lip_reach']
    u = np.clip((d - a) / (b - a), 0.0, 1.0)
    rule[face] = (1.0 - u * u * (3.0 - 2.0 * u))[face]
    # the loop and the bag: exact, by their pairs
    w[loop], rule[loop] = w_k, 1.0
    w[bag] = w_k[None, :]
    rule[bag.ravel()] = 1.0
    lower = np.zeros(N, bool)
    lower[bag[:, n_up:].ravel()] = True
    up_side = face & (rule > 0.5) & (w < 0.5)
    note = (f'the loop {K} ({n_up} a run, {arc[-1]:.1f} mm of upper lip, the corners blended over {HEAD["lip_corner"]:g} '
            f'mm), the bag {bag.shape[0]} rings; {int((face & (rule > 0)).sum())} face vertices by the nearer run '
            f'({int(up_side.sum())} the upper lip\'s, {int((face & (rule > 0.5) & (w >= 0.5)).sum())} the lower\'s)')
    return w, rule, lower, note


def weights(spec, chain, sk, low, log=print):
    """the skin weights on the welded low (the module docstring): (joints (N, 4) int32, weights (N, 4) float32, the
    dense field before the cut (N, J), notes)"""
    V, piece, side = low['V'], low['piece'], low['side']
    N, J = len(V), len(sk.names)
    W = np.zeros((N, J))
    notes = {}
    # ---- the body and the fins: the axial ramp
    on = np.isin(piece, ('body', 'fin'))
    Wb, s_b = body_axial(spec, chain, sk, V[on])
    W[on] = Wb
    s_all = np.zeros(N)
    s_all[on] = s_b
    # ---- the head's leaves (body vertices only)
    body = piece == 'body'
    breg = low['body_region']
    k_m = chain['k']
    st = spec['stations']
    s_h = st['jaw_hinge']
    ml = low['body_rings']['mouth_loop']
    Pm = V[ml]
    sm = st['hip'] - (Pm[:, 2] / k_m) / spec['a1']['TL']
    o = np.argsort(sm)
    sm, ym = sm[o], Pm[o, 1]
    # the slit's middle height by station (the loop's upper and lower runs averaged per station bin)
    bins = np.linspace(sm.min(), sm.max(), 40)
    yb = np.array([ym[(sm >= a) & (sm <= b)].mean() if ((sm >= a) & (sm <= b)).any() else np.nan
                   for a, b in zip(bins[:-1], bins[1:])])
    cb = 0.5 * (bins[:-1] + bins[1:])
    ok = ~np.isnan(yb)
    y_line = lambda s: np.interp(s, cb[ok], yb[ok])                                 # noqa: E731
    s_c = float(sm.max())
    jaw, head, tongue = sk.index('jaw'), sk.index('head'), sk.index('tongue')
    sb = s_all
    fade = 1.0 - np.clip((sb - (s_h + HEAD['jaw_fade'][0])) / (HEAD['jaw_fade'][1] - HEAD['jaw_fade'][0]), 0.0, 1.0)
    fade = fade * fade * (3.0 - 2.0 * fade)
    yl = y_line(np.minimum(sb, s_c))
    below = np.clip((yl - V[:, 1]) / (HEAD['jaw_y'] * k_m) + 0.5, 0.0, 1.0)
    # the lips by their run near the mouth (lip_sides), the height rule past HEAD['lip_reach']; the loop and the bag
    # exactly their pairs' shares (the mouth's own: no hinge fade, it opens as one)
    w_lip, rule, lower, notes['lips'] = lip_sides(low, k_m)
    w_jaw = np.where(body, fade * (rule * w_lip + (1.0 - rule) * below), 0.0)
    bag = body & (breg == 'mouth')
    own = bag.copy()
    own[ml] = True
    w_jaw[own] = w_lip[own]
    # the bag's deep floor to the tongue
    from scipy.spatial import cKDTree
    d_lip = cKDTree(Pm).query(V[bag])[0] / k_m
    w_tg = np.zeros(N)
    w_tg[bag] = lower[bag] * HEAD['tongue'] * np.clip((d_lip - HEAD['tongue_depth'][0]) /
                                                      (HEAD['tongue_depth'][1] - HEAD['tongue_depth'][0]), 0, 1)
    ax = W.sum(1)
    W[:, :] *= (1.0 - w_jaw)[:, None]
    W[:, jaw] += w_jaw * (1.0 - w_tg)
    W[:, tongue] += w_jaw * w_tg
    notes['jaw'] = f'{int((w_jaw > 0.5).sum())} vertices mostly on the jaw, {int((w_tg > 0.3).sum())} on the tongue'
    # the throat: the gular region's underside
    a, pk, b = HEAD['throat_s']
    bump = np.where(sb < pk, np.clip((sb - a) / (pk - a), 0, 1), np.clip((b - sb) / (b - pk), 0, 1))
    bump = bump * bump * (3.0 - 2.0 * bump)
    sec = chain['sec']
    yc = np.array([sec['belly'] + 0.5 * sec['D'](float(s)) for s in sb]) * k_m
    yb_ = sec['belly'] * k_m
    vt = np.clip((yc - V[:, 1]) / np.maximum(yc - yb_, 1e-9), 0.0, 1.0)             # 0 at mid-height, 1 at the belly
    ven = np.clip((vt - (1.0 - HEAD['throat_y'][0])) / HEAD['throat_y'][0], 0.0, 1.0)
    w_th = np.where(body & (breg != 'mouth'), HEAD['throat'] * bump * ven * (1.0 - w_jaw), 0.0)
    thr = sk.index('throat')
    W *= (1.0 - w_th)[:, None]
    W[:, thr] += w_th
    notes['throat'] = f'{int((w_th > 0.3).sum())} vertices over 0.3 on the throat'
    # the breathers: a share of the ventral flank round each one's station
    for nm in ('breath_chest', 'breath_belly'):
        bj = sk.index(nm)
        s_j = st['hip'] - (sk.world[bj][2, 3] / k_m) / spec['a1']['TL']
        g = np.exp(-0.5 * ((sb - s_j) / HEAD['breath_w']) ** 2)
        venb = np.clip((vt - (1.0 - HEAD['breath_y'][0])) / HEAD['breath_y'][0], 0.0, 1.0)
        w_b = np.where(body, HEAD['breath'] * g * venb, 0.0)
        W *= (1.0 - w_b)[:, None]
        W[:, bj] += w_b
    # the gill bases' skin to neck_0 (the ports, their fillets and the copy rings the rami weld to)
    neck = sk.index('neck_0')
    gp = np.unique(np.concatenate([v for k, v in low['body_rings'].items() if k.startswith('port_gill_')]))
    Pg = V[gp]
    dg = cKDTree(Pg).query(V)[0] / k_m
    w_gp = np.where(body, np.clip(1.0 - (dg - 0.0) / 1.6, 0.0, 1.0), 0.0)
    w_gp = w_gp * w_gp * (3.0 - 2.0 * w_gp)
    W *= (1.0 - w_gp)[:, None]
    W[:, neck] += w_gp
    notes['gill ports'] = f'{len(gp)} port vertices, {int((w_gp > 0.5).sum())} vertices mostly on neck_0'
    # ---- the limbs, each root's blend reaching LIMB['root_ext'] out over the body's skin from its footprint ring (the
    # body's own weights so far, the head's leaves and the breathers in them, are the blend's body side there)
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra
    Eq = np.concatenate([low['Q'][:, [0, 1]], low['Q'][:, [1, 2]], low['Q'][:, [2, 3]], low['Q'][:, [3, 0]]])
    roots = {}
    for kind in ('fore', 'hind'):
        for sd in 'LR':
            idx = np.nonzero((piece == kind) & (side == sd))[0]
            ring0 = np.asarray(low['limb_rings'][f'ring_footprint_{kind}_{sd}'])
            ring1 = np.asarray(low['limb_rings'][f'ring_axilla_{sd}' if kind == 'fore' else f'ring_groin_{sd}'])
            # the skin distances from the footprint ring: out over the body (its mouth left out) and down the limb
            limb_v = (piece == kind) & (side == sd)
            okv = body | limb_v
            okv[np.nonzero(breg == 'mouth')[0]] = False
            Ee = Eq[okv[Eq[:, 0]] & okv[Eq[:, 1]]]
            if kind in LIMB.get('diag_graph', ()):
                # (AX13: the quads' diagonals in the graph too (LIMB's AX13 note))
                Ed = np.concatenate([low['Q'][:, [0, 2]], low['Q'][:, [1, 3]]])
                Ed = Ed[(Ed[:, 0] != Ed[:, 1]) & okv[Ed[:, 0]] & okv[Ed[:, 1]]]
                Ee = np.vstack([Ee, Ed])
            # (AX10b continuation: each edge ONCE. Two quads list a shared edge twice and coo_matrix sums duplicates, so
            # every inner edge weighed twice its length: the root's body ring reached ~3 mm of skin, not root_ext's 6,
            # and its blend crossed the port's 0.5-0.7 mm fillet rows twice as steeply (c_hip_dbg.py: two body vertices
            # 0.72 mm apart read 1.47 and 2.92 mm from the footprint ring))
            Ee = np.unique(np.sort(Ee, axis=1), axis=0)
            Lg = np.linalg.norm(V[Ee[:, 0]] - V[Ee[:, 1]], axis=1) / k_m
            G = coo_matrix((np.concatenate([Lg, Lg]), (np.concatenate([Ee[:, 0], Ee[:, 1]]),
                                                        np.concatenate([Ee[:, 1], Ee[:, 0]]))), shape=(N, N)).tocsr()
            d_fp = dijkstra(G, indices=ring0, min_only=True, limit=40.0)
            z_len = float(np.mean(d_fp[ring1])) + LIMB['root_past']
            ext_i = np.nonzero(body & np.isfinite(d_fp) & (d_fp < root_ext(kind)))[0]
            Wl, share, info, We = limb_weights(spec, chain, sk, low, kind, sd, idx, ext=(ext_i, d_fp[ext_i], W[ext_i]),
                                               geo=(d_fp[idx], z_len))
            W[idx] = Wl
            W[ext_i] = We
            info['ext'], info['z'] = len(ext_i), z_len
            roots[f'{kind}_{sd}'] = info
    notes['limb roots'] = '; '.join(f'{k} over {v["z"]:.2f} mm of the limb\'s skin from its footprint ring (+ {v["ext"]} '
                                    f'body vertices within {root_ext(k.split("_")[0]):g} mm)' for k, v in roots.items())
    # ---- the rami
    for r in (1, 2, 3):
        for sd in 'LR':
            idx = np.nonzero((piece == 'ramus') & (side == sd) & (low['ramus'] == r))[0]
            W[idx] = ramus_weights(spec, chain, sk, V[idx], r, sd)
    # ---- the eyes: rigid
    for sd in 'LR':
        idx = np.nonzero((piece == 'eye') & (side == sd))[0]
        W[idx] = 0.0
        W[idx, sk.index(f'eye_{sd}')] = 1.0
    # ---- smooth (the eyes, the lips and the bag held), cut to four
    held = (piece == 'eye') | bag
    held[ml] = True
    W = RG.smooth_field(W, low['Q'], iters=SMOOTH['iters'], alpha=SMOOTH['alpha'], pinned=np.nonzero(held)[0])
    W = np.maximum(W, 0.0)
    W /= np.maximum(W.sum(1, keepdims=True), 1e-12)
    # ---- the half-angle helpers AGAIN after the smoothing (HELPERS' note; AX10b, 11-02): the three passes mix the
    # upper bone, the helper and the lower bone across a crease's folds, so a vertex blended across the whole bend again
    # (the check's helper_trial.py at the elbows and knees: gate 1's worst -7.6 -> -2.8 %, the swim's knee -24.6 ->
    # -9.8 % on its worst vertex); before the fins copy the skin's weights
    n_rs = {}
    for kind in ('fore', 'hind'):
        for sd in 'LR':
            for h_, ug, lg in limb_groups(sk, kind, sd):
                W, n_rs[sk.names[h_]] = resplit(W, ug, h_, lg)
    notes['helpers'] = 're-split after the smoothing: ' + ', '.join(f'{k} {v}' for k, v in n_rs.items())
    # ---- the fins (§9.1: the body's weights at each root point; AX10, 11-02): every fin vertex takes the SMOOTHED
    # body skin's weights at its column's root (the column stands at one station over its root: the root at its station
    # nearest it; the body vertex nearest that root). The axial ramp at the fin's own station, smoothed along the fin
    # apart from the body's skin, left the blade tip's buried roots 0.03 off the skin's tail_11 share: a 30 deg bend
    # there lifted five roots 0.01-0.23 mm x4 out of the skin (tests/ax10_rig.py gate 4)
    fins_v = np.nonzero(piece == 'fin')[0]
    if len(fins_v):
        roots = np.asarray(low['fin_roots'])
        bod = np.nonzero(piece == 'body')[0]
        tb = cKDTree(V[bod])
        _, jb = tb.query(V[roots])
        root_body = bod[jb]
        zr = V[roots, 2]
        for v in fins_v:
            same = np.nonzero(np.abs(zr - V[v, 2]) < 1e-7)[0]
            cand = same if len(same) else np.arange(len(roots))
            k = cand[np.argmin(np.linalg.norm(V[roots[cand]] - V[v], axis=1))]
            W[v] = W[root_body[k]]
        notes['fins'] = f'{len(fins_v)} fin vertices on their columns\' roots\' skin weights ({len(roots)} roots)'
    # ---- the rings' contract (RING_ROOT's note; AX11's first run: the digits' weights on the hand / foot rings, the
    # jaw's on the poll ring, the smoothing's tail_3+ / tail_8+ leaking onto 65 / 14 base vertices before the tail rings)
    W, mv = ring_contract(sk, low, W)
    notes['rings'] = 'native weight moved onto the ring roots: ' + ', '.join(f'{k} {v:.2f}' for k, v in mv.items()
                                                                              if v > 1e-9)
    Jw, Ww = RG.limit_influences(W, 4)
    log('[rig] weights: ' + '; '.join(f'{k}: {v}' for k, v in notes.items()))
    return Jw, Ww, W, notes


def closest_on_triangles(P, A, B, C):
    """each point's closest point on its triangle (A[i], B[i], C[i]): (points, barycentrics (n, 3)) (Ericson's regions)"""
    P, A, B, C = (np.asarray(x, np.float64) for x in (P, A, B, C))
    ab, ac, ap = B - A, C - A, P - A
    d1, d2 = (ab * ap).sum(1), (ac * ap).sum(1)
    bp = P - B
    d3, d4 = (ab * bp).sum(1), (ac * bp).sum(1)
    cp = P - C
    d5, d6 = (ab * cp).sum(1), (ac * cp).sum(1)
    va = d3 * d6 - d5 * d4
    vb = d5 * d2 - d1 * d6
    vc = d1 * d4 - d3 * d2
    den = np.maximum(va + vb + vc, 1e-30)
    v = vb / den
    w = vc / den
    bc = np.column_stack([1.0 - v - w, v, w])
    # the edge and vertex regions: clamp by projecting onto the nearest of the three edges when outside
    out = (bc < 0.0).any(1)
    if out.any():
        best = np.full(len(P), np.inf)
        res = bc.copy()
        for (i0, i1), (X, Y) in (((0, 1), (A, B)), ((1, 2), (B, C)), ((0, 2), (A, C))):
            e = Y - X
            t = np.clip(((P - X) * e).sum(1) / np.maximum((e * e).sum(1), 1e-30), 0.0, 1.0)
            q = X + t[:, None] * e
            d = np.linalg.norm(P - q, axis=1)
            m = out & (d < best)
            best[m] = d[m]
            r_ = np.zeros((int(m.sum()), 3))
            r_[:, i0] = 1.0 - t[m]
            r_[:, i1] = t[m]
            res[m] = r_
        bc = res
    Q = bc[:, :1] * A + bc[:, 1:2] * B + bc[:, 2:] * C
    return Q, bc


def root_on_ramus(low, P, k=24, labels=None):
    """each point's closest point on the welded low's RAMUS triangles (with labels, 'gill_<r>_<side>' per point: on its
    OWN ramus's triangles and its socket's in the body only; AX10, 11-02: any ramus let a root near a stalk's junction
    take a neighbour's skin weights): (triangle (n, 3) vertex ids, barycentrics, distances)"""
    from scipy.spatial import cKDTree
    Q = low['Q']
    F = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
    F = F[low['piece'][F[:, 0]] == 'ramus']
    V = low['V']
    P = np.asarray(P, np.float64)
    best_d = np.full(len(P), np.inf)
    tri = np.zeros((len(P), 3), int)
    bcs = np.zeros((len(P), 3))
    groups = [(np.arange(len(P)), F)]
    if labels is not None:
        # the ramus's own piece AND its socket in the body (the gill port's loop, its two fillet rings and the copy
        # ring the ramus welds to): the comb's first filaments root below the graft ring, 3.5-14 mm x4 off the ramus
        # piece, in the socket's skin
        Fa = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
        labels = np.asarray([str(x) for x in labels])
        groups = []
        for lab in np.unique(labels):
            _, r_, sd = lab.split('_')
            Fl = F[(low['ramus'][F[:, 0]] == int(r_)) & (low['side'][F[:, 0]] == sd)]
            sock = np.unique(np.concatenate([np.asarray(v) for k, v in low['body_rings'].items()
                                             if k.startswith(f'port_gill_{r_}_{sd}_')]))
            Fs = Fa[np.isin(Fa, sock).all(1) & (low['piece'][Fa[:, 0]] == 'body')]
            groups.append((np.nonzero(labels == lab)[0], np.vstack([Fl, Fs])))
    for ids, Fg in groups:
        cen = V[Fg].mean(1)
        kk = min(k, len(Fg))
        _, cand = cKDTree(cen).query(P[ids], k=kk)
        cand = cand.reshape(len(ids), kk)
        for c in range(kk):
            f = Fg[cand[:, c]]
            q, bc = closest_on_triangles(P[ids], V[f[:, 0]], V[f[:, 1]], V[f[:, 2]])
            d = np.linalg.norm(P[ids] - q, axis=1)
            m = d < best_d[ids]
            best_d[ids[m]], tri[ids[m]], bcs[ids[m]] = d[m], f[m], bc[m]
    return tri, bcs, best_d


def filament_weights(low, Wd):
    """each filament instance's four influences (§9.1: rigid on its ramus's weights at its root): the SKIN's own weights
    at its root (the smoothed field Wd at the closest point of the ramus's triangles, barycentric), so the instance's
    root moves as the skin point it is rooted on (to the barycentric blend's linearity). Returns (joints (n, 4),
    weights, the root triangles, their barycentrics, the roots' distances to them (x4 m))"""
    P = np.asarray(low['uv']['fil_origin'], np.float64)
    tri, bc, d = root_on_ramus(low, P, labels=low['uv']['fil_ramus'])
    W = (bc[:, :, None] * Wd[tri]).sum(1)
    j, w = RG.limit_influences(W, 4)
    return j, w, tri, bc, d


def pearl_weights(low, Wd, contacts, k=24):
    """AX13: each glass droplet's four influences (species/axolotl_pearls.py: RIGID on the lower lip, the eyes' way):
    the skin's own weights (the smoothed field Wd) at its contact point's closest point on the BODY's outer skin (the
    mouth's bag left out), barycentric, so the droplet rides the lower lip skin it rests on (the jaw's, by lip_sides).
    contacts (n, 3) in the low's units (x4 m). Returns (joints (n, 4), weights, the triangles, barycentrics, distances)"""
    from scipy.spatial import cKDTree
    Q, V = low['Q'], low['V']
    F = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
    bag = np.zeros(len(V), bool)
    bag[np.asarray(low['mouth_bag']).ravel()] = True
    F = F[(low['piece'][F] == 'body').all(1) & ~bag[F].all(1)]
    P = np.asarray(contacts, np.float64)
    cen = V[F].mean(1)
    kk = min(k, len(F))
    _, cand = cKDTree(cen).query(P, k=kk)
    cand = cand.reshape(len(P), kk)
    best_d = np.full(len(P), np.inf)
    tri = np.zeros((len(P), 3), int)
    bcs = np.zeros((len(P), 3))
    for c in range(kk):
        f = F[cand[:, c]]
        q, bc = closest_on_triangles(P, V[f[:, 0]], V[f[:, 1]], V[f[:, 2]])
        d = np.linalg.norm(P - q, axis=1)
        m = d < best_d
        best_d[m], tri[m], bcs[m] = d[m], f[m], bc[m]
    W = (bcs[:, :, None] * Wd[tri]).sum(1)
    j, w = RG.limit_influences(W, 4)
    return j, w, tri, bcs, best_d


def skin_crossings(P, E, F):
    """AX13 (gate 13 on the whole skin): the edges E (vertex pairs of positions P) whose interior crosses the interior
    of a triangle of F sharing no vertex with them (Moller-Trumbore, both ends strict): (edge ids, triangle ids, depth),
    the depth how far the edge pokes through the triangle's plane on its shorter side (P's units). Candidates by a
    k-d tree of the edges' midpoints queried from the triangles' centres, in size classes of the triangles (a ball as
    wide as the largest triangle round every small one would pair the head's thousands)"""
    from scipy.spatial import cKDTree
    P = np.asarray(P, np.float64)
    E = np.asarray(E)
    F = np.asarray(F)
    if len(E) == 0 or len(F) == 0:
        return np.zeros(0, int), np.zeros(0, int), np.zeros(0)
    A, B, C = P[F[:, 0]], P[F[:, 1]], P[F[:, 2]]
    cen = (A + B + C) / 3.0
    rad = np.max(np.stack([np.linalg.norm(A - cen, axis=1), np.linalg.norm(B - cen, axis=1),
                           np.linalg.norm(C - cen, axis=1)]), axis=0)
    P0, P1 = P[E[:, 0]], P[E[:, 1]]
    mid = 0.5 * (P0 + P1)
    hl = 0.5 * np.linalg.norm(P1 - P0, axis=1)
    tree = cKDTree(mid)
    hmax = float(hl.max())
    order = np.argsort(rad)
    cuts = [0] + [int(q * len(order)) for q in (0.5, 0.9, 0.99)] + [len(order)]
    EI, TI = [], []
    for a_, b_ in zip(cuts[:-1], cuts[1:]):
        ts = order[a_:b_]
        if len(ts) == 0:
            continue
        R = float(rad[ts].max()) + hmax + 1e-12
        lists = tree.query_ball_point(cen[ts], R)
        ti = np.repeat(ts, [len(l) for l in lists])
        if len(ti) == 0:
            continue
        ei = np.concatenate([np.asarray(l, int) for l in lists])
        keep = np.linalg.norm(mid[ei] - cen[ti], axis=1) <= hl[ei] + rad[ti] + 1e-12
        EI.append(ei[keep])
        TI.append(ti[keep])
    if not EI:
        return np.zeros(0, int), np.zeros(0, int), np.zeros(0)
    ei, ti = np.concatenate(EI), np.concatenate(TI)
    Fe = F[ti]
    share = (Fe == E[ei, 0][:, None]).any(1) | (Fe == E[ei, 1][:, None]).any(1)
    ei, ti = ei[~share], ti[~share]
    hit = np.zeros(len(ei), bool)
    eps = 1e-9
    for s0 in range(0, len(ei), 2_000_000):
        sl = slice(s0, s0 + 2_000_000)
        p0, p1 = P0[ei[sl]], P1[ei[sl]]
        a, b, c = A[ti[sl]], B[ti[sl]], C[ti[sl]]
        d = p1 - p0
        e1, e2 = b - a, c - a
        h = np.cross(d, e2)
        det = (e1 * h).sum(1)
        ok = np.abs(det) > 1e-30
        f = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        s = p0 - a
        u = f * (s * h).sum(1)
        q = np.cross(s, e1)
        v = f * (d * q).sum(1)
        t = f * (e2 * q).sum(1)
        hit[sl] = ok & (u > eps) & (v > eps) & (u + v < 1 - eps) & (t > eps) & (t < 1 - eps)
    ei, ti = ei[hit], ti[hit]
    n = np.cross(B[ti] - A[ti], C[ti] - A[ti])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-30)
    d0 = np.abs(((P0[ei] - A[ti]) * n).sum(1))
    d1 = np.abs(((P1[ei] - A[ti]) * n).sum(1))
    return ei, ti, np.minimum(d0, d1)


# ============================================================================================ the pose drivers
def half_turn(R, share):
    """the rotation R's turn scaled by share (the same axis, share x the angle)"""
    c = np.clip(0.5 * (np.trace(R) - 1.0), -1.0, 1.0)
    ang = math.acos(c)
    if ang < 1e-9:
        return np.eye(3)
    ax = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
    if np.linalg.norm(ax) < 1e-9:                          # (a half turn: the axis from the symmetric part)
        w, v = np.linalg.eigh(0.5 * (R + R.T))
        ax = v[:, np.argmax(w)]
    return _rodrigues(ax, share * ang)


def drivers(sk, rot):
    """the leaves driven by their bones (sprawl.py's meta driver): each twist leaf counter-rotates (the upper bones'
    twist leaves, proximal) or carries (the lower bones', distal) half of the axial twist of its driver's rotation, so
    the skin twists along the bone instead of wrapping at one ring (AG 06.21); each HALF-ANGLE HELPER (elbow_pt /
    knee_pt, on the hinge's axis in its driver's frame) turns HELPER['share'] of its driver's rotation (HELPER's note);
    returns the rotations with the leaves'"""
    out = dict(rot)
    for nm in sk.names:
        m = sk.meta[nm]
        if m['role'] == 'helper':
            R = rot.get(sk.index(m['driver']))
            if R is not None:
                out[sk.index(nm)] = half_turn(R, HELPER['share'])
            continue
        if m['role'] != 'twist':
            continue
        drv = m['driver']
        if nm.startswith(('humerus_twist', 'femur_twist')):
            R = rot.get(sk.index(drv))
            if R is None:
                continue
            tw = math.atan2(R[2, 1] - R[1, 2], R[1, 1] + R[2, 2])         # the swing-twist split's twist about x
            out[sk.index(nm)] = rx(-LIMB['twist_share'] * tw)
        else:
            # radius_twist / tibia_twist: half of the hand's / foot's axial twist (the carpus / tarsus, its child)
            child = drv.replace('radius', 'carpus').replace('tibia', 'tarsus')
            R = rot.get(sk.index(child))
            if R is None:
                continue
            tw = math.atan2(R[2, 1] - R[1, 2], R[1, 1] + R[2, 2])
            out[sk.index(nm)] = rx(LIMB['twist_share'] * tw)
    return out


# ============================================================================================ the correctives (AX10b)
_CORR = dict(ring=2, iters=600, step=0.5, project=25, squash=0.35, diag=True)
CORRECTIVES = dict(
    knee_ext=dict(_CORR, measure=('included', ('femur', 'tibia', 'tarsus')), bone='tibia', piece='hind',
                  helper='knee_pt', up=('femur', 'femur_twist'), lo=('tibia', 'tibia_twist'), ramp=(117.0, 155.0)),
    elbow_ext=dict(_CORR, measure=('included', ('humerus', 'radius', 'carpus')), bone='radius', piece='fore',
                   helper='elbow_pt', up=('humerus', 'humerus_twist'), lo=('radius', 'radius_twist'),
                   ramp=(120.0, 151.0)),
    ankle_ext=dict(_CORR, measure=('fold', 'tarsus'), bone='tarsus', piece='hind', helper='ankle_pt',
                   up=('tibia', 'tibia_twist'), lo=('tarsus',), ramp=(25.0, 79.0)),
    wrist_ext=dict(_CORR, measure=('fold', 'carpus'), bone='carpus', piece='fore', helper='wrist_pt',
                   up=('radius', 'radius_twist'), lo=('carpus',), ramp=(25.0, 78.0), ring=3))
# (AX13 restart, 11-02 15:4x: GATE 11 ON EVERY GLB TRIANGLE EDGE (the lead's AX13 call; tests/ax10_rig.py _EG;
# ax13_notes/try/edge_probe.py, every corrective / weight variant over the 69 motion poses). The relaxation held only the
# quads' SIDES, so a zone's quads sheared freely: the swim's wrist diagonal went to x0.11 (swim 8/12), the elbow's to
# x0.16 (2/12), the ankle's x0.22. `diag`: each quad's two diagonals relaxed beside its sides (x0.36 / x0.56 / x0.44 now),
# the wrist's zone one ring wider (ring 3: its diagonal-held zone pulled a 0.25 mm crease edge to x3.06 at ring 2, x2.74
# at 3). HIP_FOLD IS GONE: at its own swim pose its relaxation took the hip root's edges from x0.32..x2.39 to x0.28..x2.57
# (> x2: 5 -> 9), and the swim's x3.74 at 5/12 was the BLEND across one body ring in front of the thigh (spine_0 0.51 ->
# 0.13, hip_pt 0.23 -> 0.67 over a 1.35 mm diagonal while spine_0 turns with the wave and hip_pt half the femur's fold:
# try/hip_weights.py), which no static morph at the fold undoes (off x3.60, with diagonals x3.63, ring 7 x3.51, built at
# the full 5/12 pose x3.63). That blend is LIMB's (diag_graph, root_ext 12.5: the hip x2.78 with no hip corrective))
# (AX10b continuation: the ramps' ends moved with ADPRESS's opened upper bones to the swim's new angles, the knee 158 ->
# 155, the elbow 160 -> 151, the femur's fold -93 -> -88 (the ankle's 79.9 and the wrist's 79.5 already past their ends),
# so each corrective is whole in the swim it was built at: at the old ends the elbow's read 0.9 there)
# (AX10b gate 10: THE WALK'S ELBOW, flexed to 63-65 deg in the swing (the bind 88), read -8.6 % of its closed volume,
# as AX10's rig did (-8.5 %: ax10b_notes/try/probe_walk_elbow.py), and flexion correctives were tried. AX10b
# continuation: NO LOSS TO CORRECT. The radius alone from 88 to 60 deg moves the whole forelimb's volume +0.19..+0.26 %
# of the hinge region's (its faces about a fixed point, the root ring still), while the test's closed volume fell to
# -8.5 % at 65 and rose to -6.9 % at 60: its caps took in the forearm's segments past the lower plane. With each cap
# clipped by the other's plane (tests/ax10_rig.py _section_area) it reads +0.16..+0.24 %, as the whole limb does
# (ax10b_notes/try/c_elbow_vol2.py, logs/c_elbow_vol2.log))
# (AX10b, the five joints the swim's adpressed limbs open or fold past the walk (tests/ax10_rig.py's kinematics: the
# walk and the stand reach the knee 68-117 deg included, the elbow 63-120, the tarsus's fold -1..55, the carpus's 0..25,
# the femur's -23..21; the swim 158 / 160 / 79 / 78 / -93): each its ramp from the walk's reach to the swim's. The ankle's
# and the wrist's start inside the walk's push-off (the heel lifted: the ankle's L opened to a fold of 55 stretched its
# crease x3.4), so they work there too. `measure`: ('included', joints) the hinge's included angle from the posed joints,
# ('fold', bone) the bone's local fold (local()'s angle about z: atan2(R10, R00)))
# (AX10b, 11-02: THE KNEE-EXTENSION CORRECTIVE, a morph target per knee driven by its INCLUDED ANGLE (the posed hip, knee
# and ankle joints), weight smoothstep over `ramp` deg. The swim's adpressed hindlimb opens the knee to ~158 deg, where
# the crease bound at the bind's 85 deg tears: its edges stretch x3.9 and carry the baked relief (the AX10 check's
# knee160_shipped_trial.png). Capping the swim's knee where the edges stay under x2 (~110-116 deg) hung the shank below
# the belly, the hindlimb no longer tucked against the body (ax10b_notes/try/swim_cap115.png; no axolotl swim footage
# exists, the literature's "limbs tucked against the body" and plan §9.3's [C] fold-back decide), so the brief's
# alternative: the knee's blend zone (the vertices on its helper or on both its groups, grown by `ring` rings) RELAXED at
# the ramp's end toward its bind edge lengths, sliding in the posed surface (tangential steps, a projection onto the
# posed triangles every `project` iterations; the zone's outer ring fixed), so the crease's stretch spreads over the
# zone; the deltas carried back into the bind (each vertex's blended linear part inverted: LBS(V + D) = the relaxed
# point at the ramp's end), the runtime adding w D before skinning (the glb's morph targets knee_ext_L / _R; the rule in
# extras.bestiary.correctives))


def corrective_names():
    return [f'{k}_{sd}' for k in CORRECTIVES for sd in 'LR']


def hinge_included(Wp, sk, side, joints):
    """a hinge's included angle (deg) from the posed joints (joints: the upper bone, the hinge, the lower bone's end)"""
    pa, pb, pc = (Wp[sk.index(f'{n}_{side}')][:3, 3] for n in joints)
    u, v = pa - pb, pc - pb
    return float(np.degrees(np.arccos(np.clip(u @ v / max(np.linalg.norm(u) * np.linalg.norm(v), 1e-30), -1.0, 1.0))))


def corrective_measure(Wp, rot, sk, side, c):
    """a corrective's driving angle (deg) at a pose (CORRECTIVES' measure)"""
    kind, arg = c['measure']
    if kind == 'included':
        return hinge_included(Wp, sk, side, arg)
    R = rot.get(sk.index(f'{arg}_{side}'), np.eye(3))
    return float(math.degrees(math.atan2(R[1, 0], R[0, 0])))


def corrective_weights(sk, rot, root=None):
    """each corrective's weight at a pose (CORRECTIVES' note): {name: w in 0 .. 1}"""
    from ..families import sprawl as SP
    Wp = SP.posed(sk, rot, root)
    out = {}
    for key, c in CORRECTIVES.items():
        a, b = c['ramp']
        for sd in 'LR':
            u = min(max((corrective_measure(Wp, rot, sk, sd, c) - a) / (b - a), 0.0), 1.0)
            out[f'{key}_{sd}'] = u * u * (3.0 - 2.0 * u)
    return out


def corrective_pose(sk, c, side, swim=None):
    """the pose a corrective is built at: its bone alone at the ramp's end; given the swim's rotations, the bone alone
    at its SWIM rotation (the ramps end at the swim's angles; the swim's femur, carpus and tarsus also splay, which a
    pure fold left out: the hip's zone read x3.86 in the swim against x2.82 at the pure fold)"""
    nm = f'{c["bone"]}_{side}'
    if swim is not None and sk.index(nm) in swim:
        return {sk.index(nm): swim[sk.index(nm)]}
    if c['measure'][0] == 'included':
        return {sk.index(nm): local(fold_for_included(sk, nm, c['ramp'][1]))}
    return {sk.index(nm): local(fold=c['ramp'][1])}


def corrective_rest(V0, deltas, rot, sk, root=None):
    """the bind positions with the correctives added at the pose's weights: V0 + sum w D"""
    if not deltas:
        return V0
    w = corrective_weights(sk, rot, root)
    V = V0.copy()
    for nm, D in deltas.items():
        if w.get(nm, 0.0) > 0.0:
            V = V + w[nm] * D
    return V


def corrective_deltas(spec, chain, sk, low, Jw, Ww, log=print):
    """THE CORRECTIVES' DELTAS (CORRECTIVES' note) on the welded low: ({name: (N, 3) x4 m}, notes)"""
    from scipy.spatial import cKDTree
    from ..families import sprawl as SP
    V0, Q = low['V'], low['Q']
    N, NJ = len(V0), len(sk.names)
    E_all = np.unique(np.sort(np.concatenate([Q[:, [0, 1]], Q[:, [1, 2]], Q[:, [2, 3]], Q[:, [3, 0]]]), axis=1), axis=0)
    # (AX13: each quad's TWO DIAGONALS, relaxed beside its sides where a corrective says `diag` (CORRECTIVES' AX13 note);
    # a quad closed on a repeated vertex has one, the other a point)
    E_dg = np.unique(np.sort(np.concatenate([Q[:, [0, 2]], Q[:, [1, 3]]]), axis=1), axis=0)
    E_dg = E_dg[E_dg[:, 0] != E_dg[:, 1]]
    F_all = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
    nbr = [[] for _ in range(N)]
    for a, b in E_all:
        nbr[a].append(b)
        nbr[b].append(a)
    Wd = np.zeros((N, NJ))
    for c_ in range(Jw.shape[1]):
        np.add.at(Wd, (np.arange(N), Jw[:, c_]), Ww[:, c_])
    out, notes = {}, {}
    # every corrective's CORE first (the limb's vertices, and the body's at a root, on its helper or on both its
    # groups): a vertex in another's core stays fixed in this one, so no two morph targets move one vertex
    cores, ons = {}, {}
    for key, c in CORRECTIVES.items():
        for sd in 'LR':
            sx = f'_{sd}'
            h_w = Wd[:, sk.index(c['helper'] + sx)]
            # (a root's zone may grow over the body's skin round it: the fold's stretch spreads onto the flank)
            on = ((low['piece'] == c['piece']) & (low['side'] == sd)) | ((low['piece'] == 'body') & (
                (h_w > 1e-3) | (c['up'] is None)))
            core = h_w > 0.01
            if c['up'] is not None:
                wu = Wd[:, [sk.index(n + sx) for n in c['up']]].sum(1)
                wl = Wd[:, [sk.index(n + sx) for n in c['lo']]].sum(1)
                core |= (wu > 0.01) & (wl > 0.01)
            cores[f'{key}_{sd}'], ons[f'{key}_{sd}'] = core & on, on
    swim = swim_pose(spec, sk, chain, 0.0, 0.6)
    for key, c in CORRECTIVES.items():
        for sd in 'LR':
            nm = f'{key}_{sd}'
            rot = corrective_pose(sk, c, sd, swim if c.get('build', 'swim') == 'swim' else None)
            Wp = SP.posed(sk, drivers(sk, rot))
            M = np.stack([Wp[i] @ np.linalg.inv(sk.world[i]) for i in range(NJ)])
            Vp = RG.lbs(V0, Jw, Ww, M)
            B = np.zeros((N, 3, 3))
            for c_ in range(Jw.shape[1]):
                B += Ww[:, c_, None, None] * M[Jw[:, c_], :3, :3]
            # the zone: the core grown by `ring` rings (the last one fixed, and any other corrective's core)
            on, core = ons[nm], cores[nm]
            others = np.zeros(N, bool)
            for k_, v_ in cores.items():
                # (another joint's core stays fixed; the same helper's other corrective never acts at once)
                if k_ != nm and not (CORRECTIVES[k_[:-2]]['helper'] == c['helper'] and k_[-1] == sd):
                    others |= v_
            zone = core.copy()
            for _ in range(c['ring']):
                grow = zone.copy()
                for v in np.nonzero(zone)[0]:
                    grow[nbr[v]] = True
                zone = grow & on
            edge = np.zeros(N, bool)
            for v in np.nonzero(zone)[0]:
                if any(not zone[w_] for w_ in nbr[v]):
                    edge[v] = True
            free = zone & ~edge & ~others
            E = E_all[zone[E_all[:, 0]] & zone[E_all[:, 1]]]
            if c.get('diag'):
                E = np.vstack([E, E_dg[zone[E_dg[:, 0]] & zone[E_dg[:, 1]]]])
            L0 = np.linalg.norm(V0[E[:, 0]] - V0[E[:, 1]], axis=1)
            Fz = F_all[zone[F_all].any(1)]
            fn = np.cross(Vp[Fz[:, 1]] - Vp[Fz[:, 0]], Vp[Fz[:, 2]] - Vp[Fz[:, 0]])
            nv = np.zeros((N, 3))
            for k in range(3):
                np.add.at(nv, Fz[:, k], fn)
            nv /= np.maximum(np.linalg.norm(nv, axis=1, keepdims=True), 1e-30)
            tree = cKDTree(Vp[Fz].mean(1))
            p = Vp.copy()
            r0 = np.linalg.norm(Vp[E[:, 0]] - Vp[E[:, 1]], axis=1) / L0
            fi = np.nonzero(free)[0]
            for it in range(c['iters']):
                d = p[E[:, 1]] - p[E[:, 0]]
                L = np.maximum(np.linalg.norm(d, axis=1), 1e-30)
                corr = (0.5 * (L - L0) / L)[:, None] * d
                acc = np.zeros((N, 3))
                cnt = np.zeros(N)
                np.add.at(acc, E[:, 0], corr)
                np.add.at(acc, E[:, 1], -corr)
                np.add.at(cnt, E[:, 0], 1.0)
                np.add.at(cnt, E[:, 1], 1.0)
                step = c['step'] * acc[fi] / np.maximum(cnt[fi], 1.0)[:, None]
                step -= (step * nv[fi]).sum(1, keepdims=True) * nv[fi]
                p[fi] += step
                if (it + 1) % c['project'] == 0 or it + 1 == c['iters']:
                    _, cand = tree.query(p[fi], k=min(12, len(Fz)))
                    best = np.full(len(fi), np.inf)
                    q_best = p[fi].copy()
                    for k in range(cand.shape[1]):
                        f = Fz[cand[:, k]]
                        q, _ = closest_on_triangles(p[fi], Vp[f[:, 0]], Vp[f[:, 1]], Vp[f[:, 2]])
                        dd = np.linalg.norm(p[fi] - q, axis=1)
                        m = dd < best
                        best[m], q_best[m] = dd[m], q[m]
                    p[fi] = q_best
            # THE FLIP GUARD: a free vertex on a triangle turned against its bind normal carried by the pose (that was
            # not turned in the plain pose already) takes half its displacement back, up to eight times. AX10b
            # continuation: and on an edge the relaxation squashed under c['squash'] of its bind length that the plain
            # pose kept over it (the right knee's relaxation slid one end of a 1.07 mm edge 1.23 mm onto the other:
            # x0.08 against the plain pose's x0.88; the left knee, its quads split on the other diagonal, x0.41)
            n0 = np.cross(V0[Fz[:, 1]] - V0[Fz[:, 0]], V0[Fz[:, 2]] - V0[Fz[:, 0]])
            ref = np.einsum('fij,fj->fi', B[Fz].mean(1), n0)
            ok0 = (fn * ref).sum(1) > 0
            sq = c.get('squash', 0.0)
            n_back = 0
            for _ in range(8):
                nq = np.cross(p[Fz[:, 1]] - p[Fz[:, 0]], p[Fz[:, 2]] - p[Fz[:, 0]])
                bad = ok0 & ((nq * ref).sum(1) <= 0)
                rq = np.linalg.norm(p[E[:, 0]] - p[E[:, 1]], axis=1) / L0
                short = (rq < sq) & (r0 >= sq)
                if not bad.any() and not short.any():
                    break
                bv = np.unique(np.concatenate([Fz[bad].ravel(), E[short].ravel()]))
                bv = bv[free[bv]]
                p[bv] = Vp[bv] + 0.5 * (p[bv] - Vp[bv])
                n_back += len(bv)
            # THE VOLUME KEPT: the zone's skin slid along itself but its new triangles chord the curved surface (the
            # knee's closed volume at 165 deg -5.1 % plain, -7.8 % relaxed): the zone's signed volume change (its outer
            # ring fixed, so it is well defined) taken back by one offset of the free vertices along their normals
            cz = Vp[Fz].mean((0, 1))

            def zone_vol(X):
                a_, b_, c_ = X[Fz[:, 0]] - cz, X[Fz[:, 1]] - cz, X[Fz[:, 2]] - cz
                return float((a_ * np.cross(b_, c_)).sum() / 6.0)
            dv_ = zone_vol(p) - zone_vol(Vp)
            area_v = np.zeros(N)
            for k in range(3):
                np.add.at(area_v, Fz[:, k], 0.5 * np.linalg.norm(fn, axis=1) / 3.0)
            h_ = -dv_ / max(float(area_v[fi].sum()), 1e-30)
            p[fi] += h_ * nv[fi]
            r1 = np.linalg.norm(p[E[:, 0]] - p[E[:, 1]], axis=1) / L0
            D = np.zeros((N, 3))
            D[fi] = np.linalg.solve(B[fi], (p[fi] - Vp[fi])[:, :, None])[:, :, 0]
            out[nm] = D
            notes[nm] = (f'{int(zone.sum())} zone vertices ({len(fi)} free), at the swim\'s {c["bone"]} the edges '
                         f'x{r0.min():.2f}..x{r0.max():.2f} -> x{r1.min():.2f}..x{r1.max():.2f} (> x2: {int((r0 > 2).sum())} '
                         f'-> {int((r1 > 2).sum())}), {n_back} vertex halvings against flips, the volume kept by a '
                         f'{h_ * 1e3:+.3f} mm x4 normal offset, the largest delta '
                         f'{np.linalg.norm(D, axis=1).max() * 1e3:.2f} mm x4')
    log('[rig] correctives: ' + '; '.join(f'{k}: {v}' for k, v in notes.items()))
    return out, notes


# ============================================================================================ the motion (§9.3)
def swim_pose(spec, sk, chain, t, speed_TL_s=1.0, phase=0.0):
    """the anguilliform swim (plan §9.3, D'Aout & Aerts): a wave y(s, t) = A(s) sin(2 pi (s / lam - f t)) along the
    spine and the tail, A(s) = 0.097 (0.15 + 0.85 s^2) TL rising to the tip, lam 0.60 TL, f = speed / 0.345 TL; each
    axial joint's yaw the wave's slope change between its neighbours; the limbs folded back along the body, the gills
    laid back. Returns the local rotations"""
    mo = spec['motion']
    lam, A_tip = mo['swim_wavelength'], mo['swim_amp']
    f = speed_TL_s / mo['swim_stride']
    TL = spec['a1']['TL']
    names = ['neck_0'] + [f'spine_{k}' for k in range(6, -1, -1)] + [f'tail_{k}' for k in range(12)]
    st = spec['stations']
    ss = [st['hip'] - (sk.world[sk.index(n)][2, 3] / chain['k']) / TL for n in names]
    ss.append(1.0)

    def y(s):
        return A_tip * (0.15 + 0.85 * s * s) * math.sin(2.0 * math.pi * (s / lam - f * t) + phase)
    rot = {}
    # the heading of each axial segment from the wave; a joint turns by the difference of its segments' headings
    head = []
    for a, b in zip(ss[:-1], ss[1:]):
        head.append(math.atan2(y(b) - y(a), (b - a)))
    prev = 0.0
    for k, nm in enumerate(names):
        turn = head[k] - prev
        prev = head[k]
        if nm == 'neck_0':
            turn *= SWIM['neck_share']                 # AX13: the head yaws least (SWIM's note)
        # the axial joints' x runs toward the head on the spine (pelvis -> spine_0 .. neck_0) and toward the tip on the
        # tail: a lateral turn is a rotation about the local y (ventral) axis, its sign by the bone's direction
        sgn = -1.0 if nm.startswith(('spine', 'neck')) else 1.0
        rot[sk.index(nm)] = ry(sgn * turn)
    # the gills laid back, the limbs ADPRESSED along the body (adpressed())
    for sd in 'LR':
        for r in (1, 2, 3):
            for j in range(4):
                rot[sk.index(f'gill_{r}_{j}_{sd}')] = local(fold=6.0 + 1.5 * math.sin(2 * math.pi * 1.3 * t + r + j))
    return adpressed(sk, rot, None)


ADPRESS = dict(fore=((0.65, -0.18, -1.0), (0.08, -0.50, -1.0), (0.10, -0.30, -1.0)),
               hind=((0.42, -0.10, -1.0), (0.10, -0.45, -1.0), (0.30, -0.25, -1.0)))
SWIM = dict(neck_share=0.5)
# (AX13, 11-02, GATE 13 ON THE WHOLE SKIN (the lead's AX13 call; ax13_notes/try/swim_cross.py, every animal edge against
# every animal triangle over the swim's 12 phases): three things crossed that the roots' sites could not see. THE OUTER
# HIND TOE through the tail base at swim 1-2 / 7-8 of 12 (h_digit5_1 x tail_2 / tail_3, <= 0.55 mm life): the foot laid
# back 6 deg off the axis met the tail bending toward it; the foot now 16 deg out (hind's third 0.10 -> 0.30, in the
# body's plane; laid down instead, 0.25 -> 0.45, cleared it too), 0 crossings. THE UPPER ARM grazing the flank at swim
# 0-1 / 6-7 (humerus x spine_4, <= 0.25 mm): the humerus opened 0.55 -> 0.65 (~33 deg off the axis), 0. THE NECK'S
# CONCAVE SIDE folding into itself and onto the third gill's stalk base at swim 2-4 / 8-10 (neck_0 x neck_0, spine_6 x
# neck_0, gill_3_0 x spine_6, <= 0.45 mm): the wave's full turn at neck_0; SWIM neck_share halves it (plan §9.3: "the
# head yawing least but not zero"), 0; r3's first joint laid back less (a third of its fold) only removed some)
# (AX10b continuation, 11-02: the upper bones opened, the humerus 0.30 -> 0.55 out and the femur 0.32 -> 0.42 (~17 / 18
# -> 29 / 23 deg off the body's axis; the forearms, shanks, hands and feet still laid back as before): at 0.30 / 0.32
# every rig pressed the limb roots INTO the flank in the swim (ax10b_notes/try/c_cross.py: each limb's root edges through
# the body's triangles, 10-16 in the worst phase, none in the walk, the stand or the idle; the three-quarter close-up's
# wedge at the thigh's front). With the weights' girdle and true root_ext: 0.42 / 0.48 left the hips clear and 2 at the
# shoulders, 0.60 / 0.55 none; the AX10b weights kept ~150 at the hips even opened: their narrow root folded the
# thigh's own skin into the flank)
# (AX10 successor, 11-02: the swim's limbs ADPRESSED, laid back along the flank, the plan §9.3's "folded back along the
# body" and §2.8's adpressed limbs: each limb's upper bone, lower bone and hand / foot (carpus + metacarpus, tarsus +
# metatarsus) aimed along these directions in its girdle's own frame (x out, y up, z forward on the left; the scapula's /
# pelvis's posed turn carried, so the limbs ride the body's wave); the elbows ~157 deg and the knees ~160 deg included.
# The first draft's local folds (the humerus +50, the radius -30) swung the arms back but left the forearms hanging
# down and the hands out: tests/out/axolotl/ax10_swim_sheet.png, its first run)


def adpressed(sk, rot, root):
    """the four limbs laid back along the body (ADPRESS's note), over the rotations rot (the spine's wave): each
    segment aimed by the minimal swing at its ADPRESS direction carried by its girdle's posed turn. Returns the
    rotations"""
    from ..families import sprawl as SP
    out = dict(rot)
    for kind in ('fore', 'hind'):
        for sd in 'LR':
            j0, j1, j2, j3 = _limb(kind, sd)
            mir = np.array([1.0 if sd == 'L' else -1.0, 1.0, 1.0])
            par = sk.parent[sk.index(j0)]
            Wb = SP.posed(sk, out, root)
            R_par = Wb[par][:3, :3] @ sk.world[par][:3, :3].T
            for jn, d in zip((j0, j1, j2), ADPRESS[kind]):
                out = SP.aim(sk, out, jn, R_par @ (np.asarray(d) * mir), root)
            out = SP.aim(sk, out, j3, R_par @ (np.asarray(ADPRESS[kind][2]) * mir), root)
    return out


WALK = dict(speed=0.08, stride=0.18, duty=(0.36, 0.51), phase=dict(hind_L=0.0, fore_L=0.25, hind_R=0.5, fore_R=0.75),
            lift=(2.2, 2.6), yaw=4.0, jitter=0.03)
# (speed TL/s: plan §9.3's range 0.05-0.30, the probe's slow amble (v01's cycle of 2-2.5 s: 0.18 / 0.08 = 2.25 s);
# stride TL per cycle, from the limbs' reach: the stance travel stride x duty, 13.9 mm life fore and 19.8 hind, the hands
# and feet +-7 / +-10 mm about the stand (0.25 asked +-11 / +-15 of 26-27 mm limbs: the knees past 160 deg); duty: the
# fore / hind contact shares (plan §2.11, Gamel 2024, used as the cycle's duty); the lateral sequence LH LF RH RF; lift:
# the swing's peak over the floor, life mm (fore, hind); yaw: the trunk's lateral sway, deg (plan: <= 5); jitter: the
# seeded phase jitter (the measured footfalls show no fixed pattern). The elbows and knees bend on the bind's own side
# (limb_ik's pole))


STAND = dict(wrist_lift=2.0, ankle_lift=3.5)
# (THE ANKLE'S L, the lead's AX8 call for this round: life mm the wrist / the ankle rises over the bind while the digits
# stay planted flat where they are: the hand / foot turns up about the line of the digits' bases, so the palm / sole
# and the carpus / tarsus slope down to the flat digits and the forearm / shank leans over them, p23's hand, p04's
# hindlimb and p06's walking animal (ax10_notes/ref/feet_photos.png); the bind keeps AX8's limbs (a lifted, leaning bind
# put AX4's knee wedge across its V crease: species/axolotl.py's ax10 note). The successor (11-02): the digits planted,
# not the metapodial joint (1.0 / 2.0 mm with the palm kept flat read as the bind's L, ax10_stand_vs_bind.png).
# Every pose the rig makes starts here: the stand itself, the walk (the digits planted, the heel up), the idle; the
# swim folds the limbs back from the bind)


def _limb(kind, sd):
    return ((f'humerus_{sd}', f'radius_{sd}', f'carpus_{sd}', f'metacarpus_{sd}') if kind == 'fore' else
            (f'femur_{sd}', f'tibia_{sd}', f'tarsus_{sd}', f'metatarsus_{sd}'))


def stand_targets(sk, chain):
    """each limb's stand at the bind (x4 m): {(kind, side): (the wrist's / ankle's new point, the metapodial joint's,
    the digits' bases (the metapodial's tip, planted))}: the hand / foot turned up about the horizontal line across it
    through the digits' bases until the wrist / ankle stands STAND's lift higher"""
    km = chain['k']
    up = np.array([0.0, 1.0, 0.0])
    out = {}
    for kind in ('fore', 'hind'):
        for sd in 'LR':
            j0, j1, j2, j3 = _limb(kind, sd)
            A = sk.world[sk.index(j2)][:3, 3]
            M = sk.world[sk.index(j3)][:3, 3]
            tip = np.asarray(sk.meta[j3]['tip'], np.float64)
            fwd = tip - A
            fwd[1] = 0.0
            axis = np.cross(up, fwd / np.linalg.norm(fwd))        # horizontal, across the foot
            lift = STAND['wrist_lift' if kind == 'fore' else 'ankle_lift'] * km
            # the turn that lifts the wrist / ankle by `lift` (bisection on the turn's sign that raises it)
            sgn = 1.0 if (_rodrigues(axis, 0.01) @ (A - tip))[1] > (A - tip)[1] else -1.0
            lo, hi = 0.0, math.radians(80.0)
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                if (_rodrigues(axis, sgn * mid) @ (A - tip))[1] - (A - tip)[1] < lift:
                    lo = mid
                else:
                    hi = mid
            R = _rodrigues(axis, sgn * 0.5 * (lo + hi))
            out[(kind, sd)] = (tip + R @ (A - tip), tip + R @ (M - tip), tip.copy())
    return out


def _rodrigues(axis, ang):
    a = np.asarray(axis, np.float64)
    a = a / max(np.linalg.norm(a), 1e-30)
    K = np.array([[0.0, -a[2], a[1]], [a[2], 0.0, -a[0]], [-a[1], a[0], 0.0]])
    return np.eye(3) + math.sin(ang) * K + (1.0 - math.cos(ang)) * (K @ K)


def _basis(x, n):
    """the frame (columns x, n x x, n) of a bone direction x and a plane normal n"""
    x = x / np.linalg.norm(x)
    n = n - x * float(n @ x)
    n = n / np.linalg.norm(n)
    return np.column_stack([x, np.cross(n, x), n])


def limb_ik(sk, rot, root, kind, sd, T, M, tip=None):
    """one limb onto its targets (x4 m, the world), the hinges kept hinges (AX10 successor, 11-02: the minimal-swing aims
    of the first draft bent the elbows and knees sideways, up to 74 deg of splay, and flipped the hind knee to the wrong
    side in the stand: tests/out/axolotl/ax10_stand_vs_bind.png, its first run):
      * the elbow / knee E solved by two bones from the shoulder / hip to the wrist / ankle at T, on the BIND's own bend
        side (the pole: the bind's elbow / knee off its shoulder-wrist line, carried by the limb's posed parent);
      * the upper bone (humerus / femur) turned as the limb's plane turns: the bind's (bone, plane normal) frame onto the
        posed one, so the elbow's / knee's hinge axis stays normal to the limb's plane (no splay at the hinge);
      * the lower bone (radius / tibia) a pure turn about that normal onto T;
      * the carpus / tarsus aimed at the metapodial joint's spot M (the minimal swing);
      * the metapodial at its bind's world orientation (the hand / foot flat and square, as planted in the bind), or,
        given `tip` (the digits' bases, planted: STAND), aimed at it SQUARE (its lateral axis the bind's: no roll) with
        each digit at its bind's world orientation (the digits flat on the floor under the raised palm / sole).
    Returns the rotations"""
    from ..families import sprawl as SP
    j0, j1, j2, j3 = _limb(kind, sd)
    i0, i1, i2, i3 = (sk.index(n) for n in (j0, j1, j2, j3))
    W0 = sk.world
    S0, E0, A0 = W0[i0][:3, 3], W0[i1][:3, 3], W0[i2][:3, 3]
    L1, L2 = float(np.linalg.norm(E0 - S0)), float(np.linalg.norm(A0 - E0))
    par = sk.parent[i0]
    Wb = SP.posed(sk, rot, root)
    S = Wb[i0][:3, 3]
    R_par = Wb[par][:3, :3] @ W0[par][:3, :3].T
    u0 = (A0 - S0) / np.linalg.norm(A0 - S0)
    pole0 = (E0 - S0) - u0 * float((E0 - S0) @ u0)
    E = two_bone(S, T, L1, L2, R_par @ pole0)
    # the upper bone: the bind's (bone, plane) frame onto the posed one
    n0 = np.cross(E0 - S0, A0 - E0)
    n1 = np.cross(E - S, T - E)
    if np.linalg.norm(n1) < 1e-12:                       # (a straight limb: keep the bind's plane, carried)
        n1 = R_par @ n0
    Rw = _basis(E - S, n1) @ _basis(E0 - S0, n0).T @ W0[i0][:3, :3]
    Fp = Wb[par][:3, :3] @ sk.local(i0)[:3, :3]
    out = dict(rot)
    out[i0] = Fp.T @ Rw
    # the lower bone: a pure turn about the plane's normal onto T
    Wb = SP.posed(sk, out, root)
    Fp1 = Wb[i0][:3, :3] @ sk.local(i1)[:3, :3]
    x_now = Fp1 @ np.array([1.0, 0.0, 0.0])
    want = (T - E) / np.linalg.norm(T - E)
    nn = n1 / np.linalg.norm(n1)
    ang = math.atan2(float(np.cross(x_now, want) @ nn), float(x_now @ want))
    out[i1] = _rodrigues(Fp1.T @ nn, ang)
    # the carpus / tarsus at the metapodial's spot, the metapodial at its bind world orientation (or at the planted tip,
    # the digits flat)
    out = SP.aim(sk, out, j2, M - T, root)
    if tip is None:
        Wb = SP.posed(sk, out, root)
        Fp3 = Wb[i2][:3, :3] @ sk.local(i3)[:3, :3]
        out[i3] = Fp3.T @ W0[i3][:3, :3]
        return out
    # (the metapodial SQUARE, the AX10 / AX11 check, 11-02: x along the line to the planted digits as before, its lateral
    # axis the bind's made orthogonal to it, so the palm / sole never rolls. sprawl.aim's minimal swing took its roll from
    # the carpus's / tarsus's frame, which turns as the limb sweeps through the stance: the fore palm rolled -15.5..+19.9
    # deg in one stance with every target met exactly, the digit bases -0.25..+1.25 mm life, digit 1 0.85 mm into the
    # floor, the bases drifting 0.31 mm, the digits folded to -25 deg against r_digit_curl's -20:
    # work/bestiary/axolotl/ax10_check/feet_probe.py, palm_trial.py)
    Wb = SP.posed(sk, out, root)
    Fp3 = Wb[i2][:3, :3] @ sk.local(i3)[:3, :3]
    x_ = (tip - M) / np.linalg.norm(tip - M)
    z_ = W0[i3][:3, 2] - x_ * float(W0[i3][:3, 2] @ x_)
    z_ /= np.linalg.norm(z_)
    out[i3] = Fp3.T @ np.column_stack([x_, np.cross(z_, x_), z_])
    Wb = SP.posed(sk, out, root)
    for k, p in enumerate(sk.parent):
        if p == i3 and sk.meta[sk.names[k]]['role'] == 'digit':
            Fpd = Wb[i3][:3, :3] @ sk.local(k)[:3, :3]
            out[k] = Fpd.T @ W0[k][:3, :3]
    return out


def stand_pose(spec, sk, chain):
    """the stand (STAND's note): the four limbs onto stand_targets. Returns the local rotations"""
    rot = {}
    for (kind, sd), (T, M, tip) in stand_targets(sk, chain).items():
        rot = limb_ik(sk, rot, None, kind, sd, T, M, tip)
    return rot


def two_bone(S, T, L1, L2, pole):
    """the middle joint of a two-bone chain from S toward T (lengths L1, L2), bent toward `pole` (a direction)"""
    d = T - S
    D = float(np.linalg.norm(d))
    D = min(max(D, abs(L1 - L2) + 1e-9), L1 + L2 - 1e-9)
    u = d / max(np.linalg.norm(d), 1e-12)
    a = (L1 * L1 - L2 * L2 + D * D) / (2.0 * D)
    h = math.sqrt(max(L1 * L1 - a * a, 0.0))
    p = np.asarray(pole, np.float64) - u * float(np.dot(pole, u))
    p /= max(np.linalg.norm(p), 1e-12)
    return S + a * u + h * p


def walk_pose(spec, sk, chain, t, speed=None, seed=11):
    """the underwater walk (plan §9.3, Gamel 2024): a lateral-sequence walk at `speed` TL/s, each limb planted for its
    duty share of the cycle and swung forward in an arc the rest, the hand / foot flat on the floor with STAND's heel
    lift; the trunk swaying a few degrees with the gait; two-bone IK per limb (limb_ik: the elbows and knees on the
    bind's own bend side, hinges kept hinges). Returns (local rotations, the root's world shift (x4 m))"""
    W_ = WALK
    v = (speed or W_['speed']) * spec['a1']['TL'] * chain['k']                  # x4 m / s
    stride = W_['stride'] * spec['a1']['TL'] * chain['k']
    f = v / stride
    rng = np.random.default_rng(seed)
    jit = {k: rng.uniform(-W_['jitter'], W_['jitter']) for k in W_['phase']}
    root = np.array([0.0, 0.0, v * t])
    rot = {}
    # the trunk's sway: a yaw wave along the spine at the stride's frequency (the hind pair's lead)
    for k in range(7):
        rot[sk.index(f'spine_{k}')] = ry(math.radians(W_['yaw'] / 7.0 * math.sin(2.0 * math.pi * f * t - 0.4 * k)))
    for k in range(12):
        rot[sk.index(f'tail_{k}')] = ry(math.radians(1.5 * math.sin(2.0 * math.pi * f * t - 0.5 - 0.35 * k)))
    km = chain['k']
    stand = stand_targets(sk, chain)
    for limb in ('hind_L', 'fore_L', 'hind_R', 'fore_R'):
        kind, sd = limb.split('_')
        duty, lift = (W_['duty'][0], W_['lift'][0] * km) if kind == 'fore' else (W_['duty'][1], W_['lift'][1] * km)
        A_st, M_st, tip_st = stand[(kind, sd)]          # the stand's wrist / ankle, metapodial joint, planted digits
        ph = (f * t + W_['phase'][limb] + jit[limb]) % 1.0
        # the foot's travel relative to the bind spot, which rides the body: planted it slides back (the body moves on),
        # swinging it arcs forward
        if ph < duty:
            u = ph / duty
            dz = stride * (0.5 - u) * duty
            dy = 0.0
        else:
            u = (ph - duty) / (1.0 - duty)
            dz = stride * duty * (-0.5 + u)
            dy = lift * math.sin(math.pi * u)
        # the stand's heel lift carried through the stride: the metapodial's spot travels and lifts, the wrist / ankle
        # rides STAND's lift over it, the hand / foot flat (limb_ik)
        d = root + np.array([0.0, dy, dz])
        rot = limb_ik(sk, rot, root, kind, sd, A_st + d, M_st + d, tip_st + d)
    return rot, root


def idle_pose(spec, sk, t, seed=7):
    """the idles (plan §9.3): the gill sway (each ramus its own phase, 0.3-1 Hz [E]) and an occasional flare, the
    throat's buccal pulse (~1 Hz [E]), a slow tail sway, rare eye drifts. Returns the local rotations"""
    rng = np.random.default_rng(seed)
    ph = rng.uniform(0.0, 2.0 * math.pi, (3, 2, 4))
    fr = rng.uniform(0.35, 0.75, (3, 2))
    rot = {}
    flare = 0.5 + 0.5 * math.sin(2.0 * math.pi * t / 7.0)
    flare = flare ** 6
    # within the SPEC's ranges summed over the stalk's four joints (rig r_gill_sway 5-15 deg, r_gill_fold -30 / +40):
    # the sway 1.5 + 2.3 + 3.1 + 3.9 = 10.8 deg at the tip, the flare -6 a joint (-24) less the sway's 0.4 left of it
    # (the first draft swayed 19 deg and flared -36 to -48 over the four, past the fold's -30)
    for i, r in enumerate((1, 2, 3)):
        for k, sd in enumerate('LR'):
            for j in range(4):
                amp = (1.5 + 0.8 * j) * (1.0 - 0.6 * flare)
                fold = amp * math.sin(2.0 * math.pi * fr[i, k] * t - 0.55 * j + ph[i, k, 0]) - 6.0 * flare
                splay = 1.5 * math.sin(2.0 * math.pi * 0.5 * fr[i, k] * t + ph[i, k, 1]) + (3.0 * flare if j == 0 else 0.0)
                rot[sk.index(f'gill_{r}_{j}_{sd}')] = local(fold=fold, splay=splay)
    pulse = 0.5 - 0.5 * math.cos(2.0 * math.pi * 1.0 * t)
    rot[sk.index('throat')] = local(fold=9.0 * pulse)
    rot[sk.index('jaw')] = local(fold=0.8 * pulse)
    for k in range(12):
        rot[sk.index(f'tail_{k}')] = local(splay=1.2 * (k + 1) / 12.0 * math.sin(2.0 * math.pi * 0.18 * t - 0.25 * k))
    drift = math.sin(2.0 * math.pi * 0.07 * t)
    for sd in 'LR':
        rot[sk.index(f'eye_{sd}')] = local(splay=3.0 * drift)
    return rot
