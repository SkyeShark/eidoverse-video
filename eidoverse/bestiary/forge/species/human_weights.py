"""H4 (the rig builder, 11-01; HUMAN_PLAN §4.2): THE HUMAN'S SKIN WEIGHTS on the LOW (welded: weights live on the welded
mesh and are scattered to the split copies, rig.py's invariants).

BONE HEAT (Baran & Popovic 2007, "Automatic Rigging and Animation of 3D Characters", §4; the plan's "heat diffusion on
the cotangent Laplacian"): each bone is a segment (a joint to its child; a leaf to its tip on the skin); every vertex
finds its nearest VISIBLE bone (the straight path from the vertex to the bone's nearest point inside the body: a ray
that meets no other skin), and the weights of bone j solve
    (-L + M H) w_j = M H p_j,      H_vv = 1 / d_v^2,  p_j(v) = 1 where j is v's nearest visible bone
with L the cotangent Laplacian (the stiffness, cot weights clamped at 0 for the obtuse corners) and M the lumped
(barycentric) areas: one factorisation, one solve per bone; the weights sum to one by construction (L 1 = 0).
THEN: the TWISTS take their bone's weight IN FULL by a level along it (H4b: TWIST_BONES below; H4's partial shares
are TWISTS_H4, kept for the gate's plant); the whole field is smoothed (rig.smooth_field), cut to four influences
continuously (rig.limit_influences) and renormalised; coincident split copies take identical weights (one welded
vertex each). H4b: the CLAVICLES are then bounded below the neck (bound_clavicles: nothing on the neck's upper part,
the neck ring or the HEAD) and the THIGHS under the iliac crest and to their own side (bound_legs).
WHICH BONES: the body's (the spine and neck chain, the head as one bone over the whole head: the face rig splits it,
the clavicles, the arms with each finger's three phalanges and the four metacarpals, the legs to the toes' tips). Not
here: the eyes, the jaw, the tongue and the face joints (the face rig's), the helpers (records for a runtime driver;
they weight nothing until one exists).

    cot_laplacian(V, F) -> (L, M)       bones(J, table, low) -> list of (joint, a, b)
    bone_heat(V, F, bones, ...) -> (n, len(bones)) weights
    split_twists(W, names, J, V, rest) -> W   finish(W, F, k=4) -> (joints (n, 4), weights (n, 4))
    bound_clavicles(J4, W4, names, V, ring origin, ring normal, s0, s1) -> (J4, W4, report)
    bound_legs(J4, W4, names, V, y_lo, y_hi) -> (J4, W4, report)
    lbs(V, joints, weights, M) / skin_matrices(...)     the posing for the sweeps and the T-pose
"""
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

try:
    import warp as wp

    @wp.kernel
    def _k_ray(m: wp.uint64, o: wp.array(dtype=wp.vec3), d: wp.array(dtype=wp.vec3), mt: wp.array(dtype=float),
               out: wp.array(dtype=float)):
        i = wp.tid()
        q = wp.mesh_query_ray(m, o[i], d[i], mt[i] + 1.0)
        if q.result:
            out[i] = q.t
        else:
            out[i] = -1.0
except ImportError:                  # the module's other functions need no warp
    wp = None

VERSION = 'h4d-weights-1'   # H4c: the back ports on the trunk (PORT_BLEND); H4d: back_shell too, the fold, PORT_POSES
# THE TWISTS (H4b, 11-02: the check's candy-wrap plant showed H4's shares were PARTIAL: near the wrist the forearm kept
# 0.33-0.48 of its weight at 0 deg beside the first twist's 0.6 x the roll, so a 150 deg roll pinched the forearm to
# 0.56 even with the drivers run). Now every long bone's skin weight is split in FULL between the bone and its two twists
# by a LEVEL a(t), the fraction of the bone's roll the vertex at parameter t (0 at the joint, 1 at the next) should turn:
# hat weights over the three columns' levels, so a vertex blends at most two neighbouring levels and the largest step
# between levels is a third of the roll (the pinch at 150 deg: cos(25 deg) = 0.906 at its worst, against cos(75 deg) =
# 0.26 for a bone with no twists). Per bone: (the columns at their levels, low to high), the level a(t), the DRIVER
# source and each twist's gain (the record the runtime reads: the twist joint turns about its bone's rest axis by
# gain x the source's twist about that axis, swing-twist):
#   * the FOREARM and the SHIN carry their DISTAL joint's roll up the bone (VRM clips roll the hand; the foot's yaw about
#     the shin): levels 0, 1/3, 2/3 on the bone and its twists, the hand / foot at 1; a(t) rises from the elbow / knee to
#     2/3 by t = 0.9, where the hand's / foot's own weight starts (r05's bone heat: the hand holds 0.04 at t 0.8-0.9,
#     0.19 at 0.9-1.0);
#   * the UPPER ARM and the THIGH carry their OWN roll down the bone with COUNTER-ROLLS: the twists turn back -2/3 and
#     -1/3 of it (levels 1/3, 2/3), the bone itself at 1 near the elbow / knee (where the children turn fully with it),
#     so the shoulder's and the hip's crease blend the trunk's 0 with 1/3, not with the whole roll; a(t) holds 1/3 to
#     t = 0.3, where the trunk's own weight (pelvis, clavicle, chest) still reaches along the bone (the crotch, the
#     armpit), then rises to 1 by t = 0.85. (A rise from t = 0 put the trunk's 0, 1/3 and 2/3 on the same crotch and
#     armpit vertices: three levels in one blend, g04's thigh at 150 deg 0.78-0.80 where a two-level blend allows 0.906.)
_ramp = lambda t, lo, hi: np.clip((t - lo) / max(hi - lo, 1e-9), 0.0, 1.0)  # noqa: E731
TWIST_BONES = {
    'lowerarm': dict(cols=(('lowerarm', 0.0), ('lowerarm_twist_02', 1 / 3), ('lowerarm_twist_01', 2 / 3)),
                     level=lambda t: (2 / 3) * _ramp(t, 0.0, 0.9), source='hand'),
    'calf': dict(cols=(('calf', 0.0), ('calf_twist_01', 1 / 3), ('calf_twist_02', 2 / 3)),
                 level=lambda t: (2 / 3) * _ramp(t, 0.0, 0.9), source='foot'),
    'upperarm': dict(cols=(('upperarm_twist_01', 1 / 3), ('upperarm_twist_02', 2 / 3), ('upperarm', 1.0)),
                     level=lambda t: 1 / 3 + (2 / 3) * _ramp(t, 0.3, 0.85), source='upperarm'),
    'thigh': dict(cols=(('thigh_twist_01', 1 / 3), ('thigh_twist_02', 2 / 3), ('thigh', 1.0)),
                  level=lambda t: 1 / 3 + (2 / 3) * _ramp(t, 0.3, 0.85), source='thigh'),
}


def _twist_gain(bone, col, level):
    """a twist column's driver gain: its level for a distal source (the hand's roll, the foot's), level - 1 for the
    bone's own roll (the counter-roll: the twist is the bone's child and already carries the whole roll)"""
    return level if TWIST_BONES[bone]['source'] != bone else level - 1.0


# the H4 table as it was (kept for the plant: a rig with H4's shares and drivers, h4b's g04 gate)
TWISTS_H4 = {
    'upperarm_twist_01': ('upperarm', lambda t: 0.5 * (1.0 - _ramp(t, 0.0, 0.5)), ('upperarm', -0.5)),
    'upperarm_twist_02': ('upperarm', lambda t: 0.4 * _ramp(t, 0.5, 1.0), ('lowerarm', 0.25)),
    'lowerarm_twist_01': ('lowerarm', lambda t: 0.6 * _ramp(t, 0.4, 1.0), ('hand', 0.6)),
    'lowerarm_twist_02': ('lowerarm', lambda t: 0.3 * _ramp(t, 0.15, 0.5) * (1.0 - _ramp(t, 0.6, 1.0)), ('hand', 0.3)),
    'thigh_twist_01': ('thigh', lambda t: 0.5 * (1.0 - _ramp(t, 0.0, 0.5)), ('thigh', -0.5)),
    'thigh_twist_02': ('thigh', lambda t: 0.4 * _ramp(t, 0.5, 1.0), ('calf', 0.25)),
    'calf_twist_01': ('calf', lambda t: 0.3 * _ramp(t, 0.1, 0.5) * (1.0 - _ramp(t, 0.5, 0.9)), ('foot', 0.25)),
    'calf_twist_02': ('calf', lambda t: 0.5 * _ramp(t, 0.5, 1.0), ('foot', 0.5)),
}
NEXT = dict(upperarm='lowerarm', lowerarm='hand', thigh='calf', calf='foot')


def cot_laplacian(V, F):
    """the cotangent stiffness L (n x n, L_ij = (cot a + cot b) / 2 off the diagonal, clamped >= 0; rows sum to 0) and the
    lumped mass M (diagonal: a third of each incident triangle's area)"""
    V = np.asarray(V, np.float64)
    F = np.asarray(F, np.int64)
    n = len(V)
    rows, cols, vals = [], [], []
    for k in range(3):
        i, j, o = F[:, k], F[:, (k + 1) % 3], F[:, (k + 2) % 3]
        u, w = V[i] - V[o], V[j] - V[o]
        c = (u * w).sum(1) / np.maximum(np.linalg.norm(np.cross(u, w), axis=1), 1e-20)
        c = np.maximum(c, 0.0) * 0.5
        rows += [i, j]
        cols += [j, i]
        vals += [c, c]
    W = sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsr()
    L = W - sp.diags(np.asarray(W.sum(1)).ravel())
    A = 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)
    m = np.zeros(n)
    for k in range(3):
        np.add.at(m, F[:, k], A / 3.0)
    return L, sp.diags(m)


def bones(J, table, low, tips):
    """the heat's bones: (joint, a, b) segments. A joint with a body child gets a segment to it (the hand to the middle
    metacarpal's base; the pelvis to spine_01; spine_05 to neck_01); a leaf to its tip on the skin (tips: {joint: (3,)})"""
    kids = {}
    for t in table:
        if t['parent']:
            kids.setdefault(t['parent'], []).append(t)
    out = []
    pick = dict(pelvis='spine_01', spine_05='neck_01', neck_01='neck_02', neck_02='head')
    for t in table:
        nm = t['name']
        if t['kind'] not in ('body',) or nm in ('root',):
            continue
        body_kids = [c['name'] for c in kids.get(nm, []) if c['kind'] == 'body']
        if nm in pick:
            out.append((nm, J[nm], J[pick[nm]]))
        elif nm.startswith('hand_'):
            sd = nm[-1]
            out.append((nm, J[nm], 0.5 * (J[f'index_metacarpal_{sd}'] + J[f'pinky_metacarpal_{sd}'])))
        elif nm.startswith('clavicle_'):
            out.append((nm, J[nm], J[f'upperarm_{nm[-1]}']))
        elif nm.startswith('upperarm_') or nm.startswith('lowerarm_') or nm.startswith('thigh_') or nm.startswith('calf_'):
            nxt = dict(upperarm='lowerarm', lowerarm='hand', thigh='calf', calf='foot')[nm.split('_')[0]]
            out.append((nm, J[nm], J[f'{nxt}_{nm[-1]}']))
        elif nm.startswith('foot_'):
            out.append((nm, J[nm], J[f'ball_{nm[-1]}']))
        elif len(body_kids) == 1:
            out.append((nm, J[nm], J[body_kids[0]]))
        elif nm in tips:
            out.append((nm, J[nm], tips[nm]))
    return out


def _seg_dist(P, a, b):
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(ab @ ab, 1e-20), 0.0, 1.0)
    Q = a + t[:, None] * ab
    return np.linalg.norm(P - Q, axis=1), Q, t


def bone_heat(V, F, bone_list, N=None, k_vis=6, log=print):
    """Baran & Popovic's bone heat (module docstring) on the welded LOW (V mm, F triangles); N the vertex normals (for the
    visibility rays' start, 0.05 mm inside). Returns W (n, len(bone_list)) and the per-vertex diagnostics"""
    wp.config.quiet = True
    V = np.asarray(V, np.float64)
    n, nb = len(V), len(bone_list)
    D = np.zeros((n, nb))
    for j, (_, a, b) in enumerate(bone_list):
        D[:, j], _, _ = _seg_dist(V, np.asarray(a), np.asarray(b))
    order = np.argsort(D, axis=1)[:, :k_vis]
    if N is None:
        fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
        N = np.zeros_like(V)
        for k in range(3):
            np.add.at(N, F[:, k], fn)
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-20)
    mesh = wp.Mesh(points=wp.array(V.astype(np.float32), dtype=wp.vec3),
                   indices=wp.array(np.asarray(F, np.int32).ravel(), dtype=wp.int32))
    visible = np.zeros((n, k_vis), bool)
    for c in range(k_vis):
        js = order[:, c]
        Q = np.zeros((n, 3))
        for j in np.unique(js):
            m = js == j
            _, Q[m], _ = _seg_dist(V[m], np.asarray(bone_list[j][1]), np.asarray(bone_list[j][2]))
        O = V - N * 0.05
        Dv = Q - O
        L_ = np.linalg.norm(Dv, axis=1)
        Dn = Dv / np.maximum(L_[:, None], 1e-12)
        t_ = _rays(mesh, O, Dn, L_)
        visible[:, c] = (t_ < 0) | (t_ >= L_ * 0.999)
    first = np.argmax(visible, axis=1)
    none = ~visible.any(1)
    jbest = np.where(none, order[:, 0], order[np.arange(n), first])
    dbest = D[np.arange(n), jbest]
    H = 1.0 / np.maximum(dbest, 1.0) ** 2
    H[none] = 0.0
    L, Mm = cot_laplacian(V, F)
    A = (-L + Mm @ sp.diags(H)).tocsc()
    lu = spla.splu(A)
    rhs = np.zeros((n, nb))
    rhs[np.arange(n), jbest] = Mm.diagonal() * H
    W = lu.solve(rhs)
    W = np.maximum(W, 0.0)
    s = W.sum(1, keepdims=True)
    W = W / np.maximum(s, 1e-12)
    log(f'[weights] bone heat: {n} vertices, {nb} bones; nearest bone visible for {int((~none).sum())} '
        f'({int(none.sum())} saw none of their {k_vis} nearest: heat 0 there, the diffusion fills them); row sums before '
        f'the clip p1 {np.percentile(s, 1):.4f} / p99 {np.percentile(s, 99):.4f}')
    return W, dict(nearest=jbest, dist=dbest, unseen=none)


def _rays(mesh, O, D, maxt):
    out = wp.zeros(len(O), dtype=float)
    wp.launch(_k_ray, dim=len(O), inputs=[mesh.id, wp.array(O.astype(np.float32), dtype=wp.vec3),
                                           wp.array(D.astype(np.float32), dtype=wp.vec3),
                                           wp.array(np.asarray(maxt, np.float32), dtype=float), out])
    return out.numpy().astype(np.float64)


def split_twists_h4(W, cols, J, V):
    """H4's split, as it was (each long bone's weight shared with its two twists by TWISTS_H4's partial shares): kept
    for the candy-wrap gate's plant. Returns W over cols + the twist columns, and the drivers"""
    cols = list(cols)
    W = W.copy()
    extra, new_cols, drivers = [], [], {}
    for tw, (b, share, (src, gain)) in TWISTS_H4.items():
        for sd in ('L', 'R'):
            nm = f'{b}_{sd}'
            if nm not in cols:
                continue
            j = cols.index(nm)
            _, _, t = _seg_dist(V, J[nm], J[f'{NEXT[b]}_{sd}'])
            take = W[:, j] * share(t)
            W[:, j] -= take
            extra.append(take[:, None])
            new_cols.append(f'{tw}_{sd}')
            drivers[f'{tw}_{sd}'] = dict(source=f'{src}_{sd}', gain=gain, axis_bone=nm,
                                         axis_to=f'{NEXT[b]}_{sd}')
    return np.hstack([W] + extra), cols + new_cols, drivers


def split_twists(W, cols, J, V, rest=None):
    """each long bone's weight split IN FULL between the bone and its two twists by the level a(t) (TWIST_BONES: hat
    weights over the columns' levels, the vertex's t from its projection on the bone, A-pose J and V). Returns W over
    cols + the twist columns, and the drivers {twist joint: dict(source, gain, axis_bone, axis_to, level, axis_local)}:
    axis_local is the bone's rest direction (axis_bone -> axis_to) in `rest` (the T-pose positions the glb's rest
    carries, every rest rotation the identity: the axis in the twist's parent's frame AND the source's parent's)"""
    cols = list(cols)
    W = W.copy()
    extra, new_cols, drivers = {}, [], {}
    for b, spec in TWIST_BONES.items():
        for sd in ('L', 'R'):
            nm = f'{b}_{sd}'
            if nm not in cols:
                continue
            j = cols.index(nm)
            _, _, t = _seg_dist(V, J[nm], J[f'{NEXT[b]}_{sd}'])
            a = spec['level'](t)
            lv = np.array([x[1] for x in spec['cols']])
            # hat weights over the levels: the two levels round a, linearly
            k = np.clip(np.searchsorted(lv, a, side='right') - 1, 0, len(lv) - 2)
            u = np.clip((a - lv[k]) / (lv[k + 1] - lv[k]), 0.0, 1.0)
            share = np.zeros((len(V), len(lv)))
            share[np.arange(len(V)), k] = 1.0 - u
            share[np.arange(len(V)), k + 1] = u
            wb = W[:, j].copy()
            for ci, (cn, level) in enumerate(spec['cols']):
                full = f'{cn}_{sd}'
                if cn == b:
                    W[:, j] = wb * share[:, ci]
                    continue
                extra[full] = (wb * share[:, ci])[:, None]
                new_cols.append(full)
                ax = None
                if rest is not None:
                    d = np.asarray(rest[f'{NEXT[b]}_{sd}'], np.float64) - np.asarray(rest[nm], np.float64)
                    ax = (d / np.linalg.norm(d)).round(9).tolist()
                drivers[full] = dict(source=f'{spec["source"]}_{sd}', gain=round(_twist_gain(b, cn, level), 9),
                                     axis_bone=nm, axis_to=f'{NEXT[b]}_{sd}', level=round(level, 9), axis_local=ax)
    return np.hstack([W] + [extra[c] for c in new_cols]), cols + new_cols, drivers


def bound_clavicles(J4, W4, names, V, origin, normal, s0, s1):
    """THE CLAVICLES BOUNDED BELOW THE NECK (H4b; the check: H4's bone heat let them weight 10,200 of the HEAD's 10,409
    vertices, 0.4-0.9 % round the eyes, so a shrug moved the lids' skin against the eyeball): each clavicle's weight
    times f(s), s the height along the neck ring's normal from its centroid (mm), f = 1 under s0 (the suprasternal
    notch's level: the neck's base), 0 over s1, a smoothstep between; the weight taken goes to the vertex's other
    influences in proportion (four influences kept). Returns (J4, W4, report)"""
    s = (np.asarray(V, np.float64) - np.asarray(origin)) @ np.asarray(normal)
    u = np.clip((s - s0) / (s1 - s0), 0.0, 1.0)
    f = 1.0 - u * u * (3.0 - 2.0 * u)
    cl = np.isin(J4, [names.index('clavicle_L'), names.index('clavicle_R')])
    W4, take, lonely = _scale_slots(W4, cl, np.repeat(f[:, None], cl.shape[1], 1))
    after = (W4 * cl).sum(1)
    rep = dict(s0_mm=float(s0), s1_mm=float(s1), vertices_changed=int((take > 1e-9).sum()),
               weight_moved=float(take.sum()), clavicle_left_over_s1=float(after[s >= s1].max()) if (s >= s1).any() else 0.0,
               lonely=int(lonely.sum()))
    return J4, W4.astype(np.float32), rep


def _scale_slots(W4, on, fac):
    """multiply the weights in the slots `on` (n, 4) by fac (n, 4) in ONE pass, the weight taken going to the vertex's
    other slots (not `on`) in proportion, so a bound applied to both sides at once stays mirror-symmetric; returns
    (W4 float64, taken per vertex, vertices left with nothing else)"""
    W4 = np.asarray(W4, np.float64).copy()
    before = (W4 * on).sum(1)
    W4 = np.where(on, W4 * fac, W4)
    after = (W4 * on).sum(1)
    rest_ = (W4 * ~on).sum(1)
    take = before - after
    scale = np.where(rest_ > 1e-12, 1.0 + take / np.maximum(rest_, 1e-12), 1.0)
    W4 = np.where(on, W4, W4 * scale[:, None])
    W4 /= np.maximum(W4.sum(1, keepdims=True), 1e-12)
    return np.where(np.abs(W4) < 1e-12, 0.0, W4), take, (rest_ <= 1e-12) & (take > 0)


def bound_legs(J4, W4, names, V, y_lo, y_hi, mid_w=8.0):
    """THE THIGHS BOUNDED UNDER THE ILIAC CREST AND TO THEIR OWN SIDE (H4b; found while splitting the twists: the bone
    heat let the thigh reach the waist ring, 70-90 mm over the iliac crest, at 0.16-0.31, and the left thigh the right
    side of the lower belly, so a 30 deg stride moved the flank skin 28-52 mm and the other side up to 12 mm; H4's
    halves hid part of it under the four-influence cut). Each thigh column (the thigh and its twists, per side) times
    f(y) g(x): f = 1 under y_lo (the trochanterion's height: the hip joint), 0 over y_hi (the iliac crest's, by ANSUR
    II's iliocristale - trochanterion difference), a smoothstep between; g = 0 past mid_w mm over the midline on the
    other side, 1 past mid_w on its own, a smoothstep between (at the midline each thigh keeps half). The weight taken
    goes to the vertex's other influences in proportion. Returns (J4, W4, report)"""
    V = np.asarray(V, np.float64)
    u = np.clip((V[:, 1] - y_lo) / (y_hi - y_lo), 0.0, 1.0)
    f = 1.0 - u * u * (3.0 - 2.0 * u)
    on = np.zeros(np.shape(J4), bool)
    fac = np.ones(np.shape(J4))
    cols = {}
    for sd, sg in (('L', 1.0), ('R', -1.0)):
        cols[sd] = [i for i, nm in enumerate(names) if nm.startswith('thigh') and nm.endswith('_' + sd)]
        w = np.clip((V[:, 0] * sg + mid_w) / (2.0 * mid_w), 0.0, 1.0)
        g = w * w * (3.0 - 2.0 * w)
        m = np.isin(J4, cols[sd])
        on |= m
        fac = np.where(m, (f * g)[:, None], fac)
    W4, take, lonely = _scale_slots(W4, on, fac)
    rep = dict(vertices_changed=int((take > 1e-9).sum()), weight_moved=round(float(take.sum()), 2), lonely=int(lonely.sum()),
               y_lo_mm=float(y_lo), y_hi_mm=float(y_hi), mid_w_mm=float(mid_w))
    for sd, sg in (('L', 1.0), ('R', -1.0)):
        left = (W4 * np.isin(J4, cols[sd])).sum(1)
        rep[sd] = dict(left_over_crest=float(left[V[:, 1] >= y_hi].max()) if (V[:, 1] >= y_hi).any() else 0.0,
                       left_other_side=float(left[V[:, 0] * sg <= -mid_w].max()))
    return J4, W4.astype(np.float32), rep


# H4c (11-07): THE BACK PORTS ON THE TRUNK. HX0's check found the four back-limb port rings moving against their root
# joints (the scapular rings carried clavicle (mean 0.29) and upper-arm twist (to 0.42) weight: 16-31 mm against spine_05
# in the arm's swing and raise, 57 mm in the controller's walk, which protracts the clavicles; the lumbar rings 9-18 mm
# with the thigh), so a SOCKET's rigid flange could not stay seated (CROSSBREED §2.6). Now each port's CORE (its ring, its
# plug and the collar row: the ring's quad neighbours outside it) rides its root ALONE, and in a transition region round
# it (to `rmax` mm over the cage's edges) each vertex blends W = (1 - b) e_root + b W_before with a share b SOLVED, not
# guessed: b minimises the skin's distortion over a motion set (the controller's walk and the poses: arm swing, raise,
# shrug, the T-pose down, hip flex, spine turn) as the symmetric Dirichlet energy of each triangle against the A-pose
# (|F|^2 + |F^-1|^2 - 4: it blows up as a triangle collapses), plus a smoothness term on b (no hard line at the band's
# edge). Exact for linear blend skinning: a vertex's T rest is linear in its b, its posed position quadratic. One b per
# mirror pair (the weights stay symmetric); beyond the region, and on the other rings' loops and far sides, the weights
# before stand. (A smoothstep from the core instead, any width 60-140 mm, moved the walk's distortion out to the posterior
# shoulder and collapsed triangles there: the study in work/bestiary/human/h4c/build/probes, p02-p09.)
# (H4d) back_shell on spine_04 too: kept on the weights before (spine_04 0.74-0.92 with spine_03 / spine_05 and a few % of
# the arm), its loop's top edge sat one quad row under the scapular cores (spine_05 alone) and strained there in the walk,
# the shrug and the raise (H4c's check); on its root alone the rows between turn only with spine_05 against spine_04
# (the controller's walk holds spine_05 3.4-5.4 deg off spine_04), and the ring rides its root (g06: 11-12 mm before).
# Its collar row is SOLVED, not pinned (PORT_NOROW: one more row to spread that turn over), and a core vertex belongs to
# the first port listed that holds it (3 of back_shell's row are the scapular rows' and stay on spine_05)
PORT_ROOTS = {'back_upper_L': 'spine_05', 'back_upper_R': 'spine_05', 'back_lower_L': 'spine_02', 'back_lower_R': 'spine_02',
              'back_shell': 'spine_04'}
# the rings whose loops keep the weights before (their far side too, where `far` names it)
PORT_KEEP = ('waist', 'sacral', 'armscye_L', 'armscye_R')
PORT_FAR = ('armscye_L', 'armscye_R', 'neck', 'sacral')
PORT_TOWARD = {'neck': 'head', 'armscye_L': 'hand_L', 'armscye_R': 'hand_R', 'waist': 'foot_L'}
# area 'floor': each triangle weighs max(its area, the mean) (tried against a sliver pair at F's posterior armpit, 30 mm
# from the armscye ring, that collapses to s2 0.05 in two walk frames; it did not remove it: walk max 18.7 -> 18.5)
# rom_w: the weight of the ROM's poses (r12's arms_down 75, arms_up 80, arms_forward, squat, sit, neck turn / nod) beside
# pose_w for the gait's poses: at 4 they doubled F's collapsed triangle-frames in the walk (221 -> 403)
# (H4d) THE FOLD. H4c's solve left F's posterior armpit with b 0 -> 0.95 across two edges and 8 triangles turned over in
# the standing pose (10 in r12's arms_down 75): the symmetric Dirichlet energy reads a triangle's 3D Gram matrix, which
# cannot tell a triangle turned over from one the right way round, and its barrier at zero area holds a turned triangle
# turned (one from the smoothstep start stays so). Now (a) the area ratio's barrier is capped at jfloor (a triangle can
# pass back through zero area) and (b) each triangle's ORIENTED area ratio r (its posed normal against the same
# triangle's posed normal under the weights before, per frame) pays flip_mu (r0 - r)^2 below r0 = min(flip_r0, 0.8 r_before)
# (no harder than the weights before could do), at the largest frame weight in EVERY frame (flip_wmax: weighted per
# frame, the squat / sit at rom_w 1 kept 10-16 turned triangles at the flank); (c) the scene's standing pose and the
# 30 deg shrug join the gait's poses (shrug30_w 12 changed nothing: 4). The study: h4d/build/probes q01-q04, NOTES.
# Result (H4d q03 tag e, against H4b's posed normals): 0 triangles turned in the walk and the arm / shrug / raise poses
# (H4c 846 in the walk F), 2-4 at the flank in squat / sit (H4c 10-18)
PORT_BLEND = dict(rmax=140.0, lam=2.0, pose_w=4.0, rom_w=1.0, iters=800, area='floor', start_mm=100.0,
                  jfloor=0.02, flip_mu=150.0, flip_r0=0.35, shrug30_w=4.0, stand_w=4.0, flip_wmax=1.0, cof_outer=3)
PORT_NOROW = ('back_shell',)


def port_poses(arm_open):
    """(H4d) THE MOTION SET'S POSES, here so every script that runs port_blend poses the same: a list of (name, weight
    key in PORT_BLEND, {joint: (axis, deg)}), local rotation deltas from the T rest (+X the creature's left, +Y up, +Z
    forward; the twists driven by the caller as the runtime drives them). arm_open: the gait record's arm opening (deg;
    5 F, 2.5 M). The gait's (pose_w): T rest, arms down, swing +-25, shrug 15 / 30, raise 90, hip +-30, spine turn 20,
    the scene's standing pose (upper arms 1.20 rad down, forearms 0.15: human_walk_scene's 'backpose'); r12's ROM poses
    that reach the back (rom_w): arms_down 75 (+ clavicle -5), arms_up 80 (+ clavicle 15), arms_forward 90, squat, sit,
    neck_turn, neck_nod (H4c run 3's set, in its order, then H4d's two). A joint's list composes later on the left:
    [(a1, d1), (a2, d2)] is R(a2, d2) @ R(a1, d1) (port_pose_mats)"""
    sg = {'L': 1.0, 'R': -1.0}
    Z, X, Y = (0, 0, 1), (1, 0, 0), (0, 1, 0)
    dn = 70.0 - arm_open
    down = {f'upperarm_{k}': [(Z, -dn * sg[k])] for k in 'LR'}
    P = [('T rest', 'pose_w', {}), ('arms down', 'pose_w', down)]
    P += [(f'swing {s:+d}', 'pose_w', {k: [(Z, -dn * sg[k[-1]]), (X, -s)] for k in down}) for s in (25, -25)]
    P += [('shrug 15', 'pose_w', dict(down, **{f'clavicle_{k}': [(Z, 15 * sg[k])] for k in 'LR'})),
          ('raise 90', 'pose_w', {f'upperarm_{k}': [(Z, 90 * sg[k])] for k in 'LR'})]
    P += [(f'hip {s:+d}', 'pose_w', dict(down, **{f'thigh_{k}': [(X, -s)] for k in 'LR'})) for s in (30, -30)]
    P += [('spine turn 20', 'pose_w', dict(down, spine_03=[(Y, 10)], spine_04=[(Y, 10)]))]
    P += [('arms_down 75', 'rom_w', dict({f'upperarm_{k}': [(Z, -75 * sg[k])] for k in 'LR'},
                                        **{f'clavicle_{k}': [(Z, -5 * sg[k])] for k in 'LR'})),
          ('arms_up 80', 'rom_w', dict({f'upperarm_{k}': [(Z, 80 * sg[k])] for k in 'LR'},
                                      **{f'clavicle_{k}': [(Z, 15 * sg[k])] for k in 'LR'})),
          ('arms_forward 90', 'rom_w', {f'upperarm_{k}': [(Y, -90 * sg[k])] for k in 'LR'}),
          ('squat', 'rom_w', dict({f'thigh_{k}': [(X, -105)] for k in 'LR'}, **{f'calf_{k}': [(X, 120)] for k in 'LR'},
                                  **{f'foot_{k}': [(X, -25)] for k in 'LR'})),
          ('sit', 'rom_w', dict({f'thigh_{k}': [(X, -90)] for k in 'LR'}, **{f'calf_{k}': [(X, 90)] for k in 'LR'})),
          ('neck_turn', 'rom_w', {'neck_01': [(Y, 24)], 'head': [(Y, 36)]}),
          ('neck_nod', 'rom_w', {'neck_01': [(X, 15)], 'head': [(X, 25)]})]
    P += [('shrug 30', 'shrug30_w', dict(down, **{f'clavicle_{k}': [(Z, 30 * sg[k])] for k in 'LR'})),
          ('standing', 'stand_w', dict({f'upperarm_{k}': [(Z, -68.755 * sg[k])] for k in 'LR'},
                                      **{f'lowerarm_{k}': [(Z, -8.594 * sg[k])] for k in 'LR'}))]
    return P


def _edge_graph(V, Q):
    e = np.unique(np.sort(np.concatenate([Q[:, [0, 1]], Q[:, [1, 2]], Q[:, [2, 3]], Q[:, [3, 0]], Q[:, [0, 2]],
                                          Q[:, [1, 3]]]), 1), axis=0)
    w = np.linalg.norm(V[e[:, 0]] - V[e[:, 1]], axis=1)
    return sp.coo_matrix((np.r_[w, w], (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])),
                         shape=(len(V), len(V))).tocsr()


def port_regions(V, Q, rings, neck_loop, joints_a, ports=PORT_ROOTS, rmax=PORT_BLEND['rmax']):
    """the re-weight's sets on the welded LOW (A-pose, mm): rings {name: loop} (the cage records' body_rings), the neck's
    loop, joints_a the A-pose joints (head, hands, foot_L: which side of a ring is its far side). Returns dict(roots: the
    root names, owner (n,) index into roots (the nearer core), dmin (n,) mm from the nearest core, core, region, fixed1
    (bool (n,)): core = the ports' rings + plugs + collar rows; fixed1 = the other rings' loops and far sides (weights
    before); region = within rmax of a core, off both, the lumbar regions under the waist ring, the scapular over it"""
    from scipy.sparse.csgraph import dijkstra
    from .human_sockets import _split_sides
    V = np.asarray(V, np.float64)
    Q = np.asarray(Q, np.int64)
    n = len(V)
    G = _edge_graph(V, Q)

    def loop_of(nm):
        return [int(v) for v in (neck_loop if nm == 'neck' else rings[nm])]

    def side_of(nm, small=True):
        lp = loop_of(nm)
        comps = _split_sides(Q, lp)
        if nm in PORT_TOWARD:
            ref = int(np.argmin(np.linalg.norm(V - np.asarray(joints_a[PORT_TOWARD[nm]]), axis=1)))
            far = next(c for c in comps if ref in set(np.unique(Q[c]).tolist()))
            c = far if small else next(c for c in comps if c is not far)
        else:
            c = comps[-1] if small else comps[0]
        return np.array(sorted(set(np.unique(Q[c]).tolist()) - set(lp)), np.int64)

    core = np.zeros(n, bool)
    dc_root = {}
    claim = -np.ones(n, np.int64)                  # (H4d) the root (index into roots) holding each core vertex
    for nm, root in ports.items():
        lp = loop_of(nm)
        ls = set(lp)
        plug_v = np.array(sorted(set(np.unique(Q[_split_sides(Q, lp)[-1]]).tolist()) - ls), np.int64)
        pv = set(plug_v.tolist())
        row = np.array(sorted({v for q in Q.tolist() if any(x in ls for x in q) for v in q
                               if v not in ls and v not in pv and not core[v]}), np.int64)   # (H4d) not another's core
        if nm in PORT_NOROW:                       # (H4d) its collar row solved, not pinned
            row = row[:0]
        dc = dijkstra(G, directed=False, indices=np.r_[lp, row], min_only=True, limit=600.0)
        dc = np.where(np.isfinite(dc), dc, 600.0)
        dc[plug_v] = 0.0
        mine = np.r_[lp, row, plug_v].astype(np.int64)
        core[mine] = True
        if root not in dc_root:
            dc_root[root] = np.full(n, 600.0)
        claim[mine[claim[mine] < 0]] = list(dc_root).index(root)
        dc_root[root] = np.minimum(dc_root[root], dc)
    fixed1 = np.zeros(n, bool)
    for nm in PORT_KEEP + ('neck',):
        fixed1[loop_of(nm)] = True
    for nm in PORT_FAR:
        fixed1[side_of(nm)] = True
    lower = np.zeros(n, bool)
    lower[side_of('waist', small=True)] = True
    some_lumbar = next(nm for nm, r in ports.items() if r == 'spine_02')
    if lower[loop_of(some_lumbar)].mean() < 0.5:
        lower = ~lower
        lower[loop_of('waist')] = False
    roots = list(dc_root)
    dstack = np.stack([dc_root[r] for r in roots])
    owner = np.argmin(dstack, 0)
    owner[claim >= 0] = claim[claim >= 0]          # (H4d) a core vertex rides the port that holds it
    dmin = dstack.min(0)
    region = (dmin < rmax) & ~core & ~fixed1
    lum = roots.index('spine_02')
    region &= ~((owner == lum) & ~lower)
    region &= ~((owner != lum) & lower)
    return dict(roots=roots, owner=owner, dmin=dmin, core=core, region=region, fixed1=fixed1)


def port_blend_solve(V, F, J4, W4, names, sets, Ms_at, mats, mats_w, mir, lam=PORT_BLEND['lam'],
                     area_mode=PORT_BLEND['area'], iters=PORT_BLEND['iters'], start_mm=PORT_BLEND['start_mm'],
                     jfloor=PORT_BLEND['jfloor'], flip_mu=PORT_BLEND['flip_mu'], flip_r0=PORT_BLEND['flip_r0'], log=print):
    """the share b (n,): 0 on the cores, 1 outside the regions, solved in them (the PORT_BLEND comment). V the welded
    LOW (A-pose, mm), F its triangles, J4 / W4 the weights before (indices into names), sets port_regions', Ms_at per
    name the A -> T skinning matrix (the glb's rest is the T-pose re-posed by these weights), mats a list of (len(names),
    4, 4) skinning matrices from the T rest (the motion set), mats_w their weights, mir the mirror map. L-BFGS-B, b in
    [0, 1], from a smoothstep over start_mm"""
    from scipy.optimize import minimize
    V = np.asarray(V, np.float64)
    F = np.asarray(F, np.int64)
    J4 = np.asarray(J4, np.int64)
    W4 = np.asarray(W4, np.float64)
    roots, owner, core, region = sets['roots'], sets['owner'], sets['core'], sets['region']
    n = len(V)
    rep = np.where(V[:, 0] >= 0, np.arange(n), mir)
    var_v = np.unique(rep[region])
    vid = -np.ones(n, np.int64)
    vid[var_v] = np.arange(len(var_v))
    vid[region] = vid[rep[region]]
    trs = np.nonzero(region[F].any(1))[0]
    tv = np.unique(F[trs])
    # the posed position of each touched vertex, P0 + b P1 + b^2 P2 per frame
    VA = np.c_[V[tv], np.ones(len(tv))]
    rk = np.array([names.index(roots[o]) for o in owner[tv]])
    Ob = np.einsum('nk,nkij->nij', W4[tv], Ms_at[J4[tv]])
    a0 = np.einsum('nij,nj->ni', Ms_at[rk], VA)
    da = np.einsum('nij,nj->ni', Ob, VA) - a0
    da[:, 3] = 0.0
    P0, P1, P2 = [], [], []
    for S in mats:
        Rm = S[rk]
        Om = np.einsum('nk,nkij->nij', W4[tv], S[J4[tv]])
        c00 = np.einsum('nij,nj->ni', Rm, a0)[:, :3]
        c01 = np.einsum('nij,nj->ni', Rm, da)[:, :3]
        c10 = np.einsum('nij,nj->ni', Om, a0)[:, :3]
        c11 = np.einsum('nij,nj->ni', Om, da)[:, :3]
        P0.append(c00)
        P1.append(c10 + c01 - c00)
        P2.append(c11 - c01)
    P0, P1, P2 = np.stack(P0), np.stack(P1), np.stack(P2)
    wf = np.asarray(mats_w, np.float64)
    loc = -np.ones(n, np.int64)
    loc[tv] = np.arange(len(tv))
    bfix = np.where(core[tv], 0.0, 1.0)
    tvid = vid[tv]
    Ft = loc[F[trs]]
    e1, e2 = V[F[trs, 1]] - V[F[trs, 0]], V[F[trs, 2]] - V[F[trs, 0]]
    area = 0.5 * np.linalg.norm(np.cross(e1, e2), axis=1)
    area_true = area.copy()
    # (H4d) the orientation reference: each triangle's posed normal under the weights before (b = 1), per frame
    pb = P0 + P1 + P2
    nb = np.cross(pb[:, Ft[:, 1]] - pb[:, Ft[:, 0]], pb[:, Ft[:, 2]] - pb[:, Ft[:, 0]])
    nbl = np.linalg.norm(nb, axis=2)
    cref = nb / np.maximum(nbl, 1e-12)[..., None]
    r_before = nbl / (2.0 * area_true[None])
    r0 = np.minimum(flip_r0, 0.8 * r_before)
    refs = [(cref, r0)]
    # (H4d) the SECOND orientation reference, r12's: the T-rest triangle's normal carried by the cofactor of its three
    # vertices' mean T -> pose blend (what the renderer's skinned normal does). M's axilla at r12's arms_down 75 turned
    # 12 quads against it while it agreed with the weights-before normal. It depends on b: held fixed through one
    # L-BFGS-B solve, refreshed from the solution, up to PORT_BLEND['cof_outer'] solves (a fixed point)
    S3 = [(S[rk][:, :3, :3], np.einsum('nk,nkij->nij', W4[tv], S[J4[tv]])[:, :3, :3]) for S in mats]
    Rm3 = np.stack([s[0] for s in S3])
    Om3 = np.stack([s[1] for s in S3])
    del S3

    def cof_ref(b):
        VT = a0[:, :3] + b[:, None] * da[:, :3]
        nT = np.cross(VT[Ft[:, 1]] - VT[Ft[:, 0]], VT[Ft[:, 2]] - VT[Ft[:, 0]])
        Mv = (1.0 - b)[None, :, None, None] * Rm3 + b[None, :, None, None] * Om3
        Mf = Mv[:, Ft].mean(2)
        c0, c1, c2 = Mf[..., :, 0], Mf[..., :, 1], Mf[..., :, 2]
        cof = np.stack([np.cross(c1, c2), np.cross(c2, c0), np.cross(c0, c1)], axis=3)
        nr = np.einsum('ftij,tj->fti', cof, nT)
        return nr / np.maximum(np.linalg.norm(nr, axis=2), 1e-12)[..., None]

    def r_of(b, ref):
        p = P0 + b[None, :, None] * P1 + (b * b)[None, :, None] * P2
        n_ = np.cross(p[:, Ft[:, 1]] - p[:, Ft[:, 0]], p[:, Ft[:, 2]] - p[:, Ft[:, 0]])
        return (n_ * ref).sum(2) / (2.0 * area_true[None])

    b1 = np.ones(len(tv))
    r2_before = r_of(b1, cof_ref(b1))
    r02 = np.minimum(flip_r0, 0.8 * r2_before)
    if area_mode == 'floor':
        area = np.maximum(area, area.mean())
    u = e1 / np.linalg.norm(e1, axis=1, keepdims=True)
    w = np.cross(np.cross(e1, e2), u)
    w /= np.linalg.norm(w, axis=1, keepdims=True)
    A2 = np.stack([np.stack([(u * e1).sum(1), (u * e2).sum(1)], 1), np.stack([(w * e1).sum(1), (w * e2).sum(1)], 1)], 1)
    A2i = np.linalg.inv(A2)
    K = A2i @ np.transpose(A2i, (0, 2, 1))
    detK = np.linalg.det(K)
    E = np.unique(np.sort(np.concatenate([F[trs][:, [0, 1]], F[trs][:, [1, 2]], F[trs][:, [2, 0]]]), 1), axis=0)
    le = np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1)
    El = loc[E]
    wsm = 1.0 / le ** 2 * area.mean() * len(mats)
    m = tvid >= 0

    def b_of(x):
        b = bfix.copy()
        b[m] = x[tvid[m]]
        return b

    def energy(x):
        b = b_of(x)
        p = P0 + b[None, :, None] * P1 + (b * b)[None, :, None] * P2
        dp = P1 + 2.0 * b[None, :, None] * P2
        Ep = np.stack([p[:, Ft[:, 1]] - p[:, Ft[:, 0]], p[:, Ft[:, 2]] - p[:, Ft[:, 0]]], 3)
        X = np.einsum('ftki,ftkj->ftij', Ep, Ep)
        detX = np.maximum(X[..., 0, 0] * X[..., 1, 1] - X[..., 0, 1] * X[..., 1, 0], 1e-12)
        J = detX * detK[None]
        Jc = np.maximum(J, jfloor)                  # (H4d) the barrier capped: a turned triangle can come back
        act = (J >= jfloor).astype(np.float64)
        I1 = np.einsum('tij,ftji->ft', K, X)
        tot = float((wf[:, None] * area[None] * (I1 * (1.0 + 1.0 / Jc) - 4.0)).sum())
        Xi = np.stack([np.stack([X[..., 1, 1], -X[..., 0, 1]], -1), np.stack([-X[..., 1, 0], X[..., 0, 0]], -1)], -2) \
            / detX[..., None, None]
        g_E = 2.0 * (1.0 + 1.0 / Jc)[..., None, None] * np.einsum('ftki,tij->ftkj', Ep, K) \
            - 2.0 * (act * I1 / Jc)[..., None, None] * np.einsum('ftki,ftij->ftkj', Ep, Xi)
        g_E *= (wf[:, None] * area[None])[..., None, None]
        # (H4d) the oriented area ratio below r0 pays flip_mu (r0 - r)^2
        if flip_mu > 0:
            a1, a2 = Ep[..., 0], Ep[..., 1]
            cw = flip_mu * (wf.max() if PORT_BLEND['flip_wmax'] else wf)[..., None] * area[None]
            for cr, rr in refs:
                r = (np.cross(a1, a2) * cr).sum(2) / (2.0 * area_true[None])
                vio = np.maximum(rr - r, 0.0)
                tot += float((cw * vio * vio).sum())
                k = (-2.0 * cw * vio / (2.0 * area_true[None]))[..., None]
                g_E[..., 0] += k * np.cross(a2, cr)
                g_E[..., 1] += k * np.cross(cr, a1)
        gp = np.zeros_like(p)
        np.add.at(gp, (slice(None), Ft[:, 1]), g_E[..., 0])
        np.add.at(gp, (slice(None), Ft[:, 2]), g_E[..., 1])
        np.add.at(gp, (slice(None), Ft[:, 0]), -(g_E[..., 0] + g_E[..., 1]))
        gb = (gp * dp).sum((0, 2))
        db = b[El[:, 0]] - b[El[:, 1]]
        tot += lam * float((wsm * db * db).sum())
        gs = np.zeros_like(b)
        np.add.at(gs, El[:, 0], 2 * lam * wsm * db)
        np.add.at(gs, El[:, 1], -2 * lam * wsm * db)
        gb = gb + gs
        gx = np.zeros(len(var_v))
        np.add.at(gx, tvid[m], gb[m])
        return tot, gx

    uu = np.clip(sets['dmin'][var_v] / start_mm, 0.0, 1.0)
    x0 = uu * uu * (3.0 - 2.0 * uu)
    e_before, _ = energy(np.ones(len(var_v)))
    res = minimize(energy, x0, jac=True, method='L-BFGS-B', bounds=[(0.0, 1.0)] * len(var_v),
                   options=dict(maxiter=int(iters), maxfun=4000))
    for it in range(int(PORT_BLEND.get('cof_outer', 0))):
        bt = b_of(res.x)
        r2 = r_of(bt, cof_ref(bt))
        bad = (r2 < 0) & (r2_before >= 0)                # turned against r12's reference where the weights before were not
        log(f'[weights] port blend: outer {it}: {int(bad.any(0).sum())} triangles turned against the blended transform '
            f'({int(bad.sum())} triangle-frames)')
        if not bad.any():
            break
        refs[1:] = [(cof_ref(bt), r02)]
        res = minimize(energy, res.x, jac=True, method='L-BFGS-B', bounds=[(0.0, 1.0)] * len(var_v),
                       options=dict(maxiter=int(iters), maxfun=4000))
    b = np.ones(n)
    b[core] = 0.0
    b[region] = res.x[vid[region]]
    log(f'[weights] port blend: {len(var_v)} unknowns ({int(region.sum())} vertices), {len(trs)} triangles, {len(mats)} '
        f'frames; energy with the weights before in the region {e_before:.4g} -> solved {res.fun:.4g} ({res.nit} '
        f'iterations, {res.message})')
    return b


def port_blend_apply(J4, W4, names, sets, b):
    """W = (1 - b) e_root + b W on the vertices with b < 1 (the root the vertex's owner's), cut to four influences
    (rig.limit_influences); the other vertices' weights untouched, bit for bit. Returns (J4, W4)"""
    from .. import rig as RG
    J4 = np.asarray(J4).copy()
    W4 = np.asarray(W4, np.float64).copy()
    ch = np.nonzero(b < 1.0)[0]
    d = np.zeros((len(ch), len(names)))
    np.add.at(d, (np.repeat(np.arange(len(ch)), J4.shape[1]), J4[ch].ravel()), W4[ch].ravel())
    d *= b[ch, None]
    rk = np.array([names.index(sets['roots'][o]) for o in sets['owner'][ch]], np.int64)
    d[np.arange(len(ch)), rk] += 1.0 - b[ch]
    j, w = RG.limit_influences(d, J4.shape[1])
    J4[ch] = j
    W4[ch] = w
    return J4, W4


def port_pose_mats(arm_open, rot, skin):
    """(H4d) port_poses as skinning matrices: rot(axis, deg) -> 3x3, skin(local {joint: 3x3}) -> (len(names), 4, 4) from
    the T rest (the caller's: its skeleton and its twist drivers). Returns (names, mats, weight keys)"""
    out = []
    for nm, wk, P in port_poses(arm_open):
        loc = {}
        for j, seq in P.items():
            R = np.eye(3)
            for ax, deg in seq:
                R = rot(ax, deg) @ R
            loc[j] = R
        out.append((nm, skin(loc), wk))
    return [o[0] for o in out], [o[1] for o in out], [o[2] for o in out]


def port_blend(V, Q, F, rings, neck_loop, joints_a, names, J4, W4, Ms_at, walk_mats, pose_mats, pose_keys, mir,
               log=print):
    """(H4d) THE BACK PORTS ON THE TRUNK in one call (the integration's r06 and the builders' copies call this): the sets
    (port_regions), the share b solved over the motion set (the gait record's frames at weight 1, then the poses at
    PORT_BLEND[key]), the weights applied. V / Q / F the welded LOW (A-pose, mm) and its triangles, rings the cage
    records' body_rings, joints_a the A-pose joints, J4 / W4 the final field before (after the rings' clean), Ms_at per
    name the A -> T skinning matrix. Returns (J4, W4, b, sets); the T rest must be re-posed where b < 1"""
    sets = port_regions(V, Q, rings, neck_loop, joints_a, rmax=PORT_BLEND['rmax'])
    mats = list(walk_mats) + list(pose_mats)
    wts = np.r_[np.ones(len(walk_mats)), [PORT_BLEND[k] for k in pose_keys]]
    P = PORT_BLEND                                 # read now (a default argument is bound when the module loads)
    b = port_blend_solve(V, F, J4, W4, names, sets, Ms_at, mats, wts, mir, lam=P['lam'], area_mode=P['area'],
                         iters=P['iters'], start_mm=P['start_mm'], jfloor=P['jfloor'], flip_mu=P['flip_mu'],
                         flip_r0=P['flip_r0'], log=log)
    J4n, W4n = port_blend_apply(J4, W4, names, sets, b)
    return J4n, W4n, b, sets


def finish(W, Q, k=4, smooth=2, pinned=None):
    """the field smoothed over the quads' edges, cut to k influences continuously, renormalised (rig.py)"""
    from .. import rig as RG
    if smooth:
        W = RG.smooth_field(W, np.asarray(Q), iters=smooth, alpha=0.5, pinned=pinned)
    return RG.limit_influences(W, k)


def skin_matrices(rest_world, posed_world):
    """per joint the 4x4 skinning matrix posed @ inverse(rest)"""
    return np.stack([P @ np.linalg.inv(R) for R, P in zip(rest_world, posed_world)])


def lbs(V, joints, weights, Ms, normals=None, tangents=None):
    """linear blend skinning of positions (and normals, tangents by the blended linear part, renormalised)"""
    Vh = np.concatenate([V, np.ones((len(V), 1))], 1)
    Mb = np.einsum('nk,nkij->nij', weights, Ms[joints])
    P = np.einsum('nij,nj->ni', Mb, Vh)[:, :3]
    out = [P]
    for X in (normals, tangents):
        if X is None:
            out.append(None)
            continue
        Y = np.einsum('nij,nj->ni', Mb[:, :3, :3], X[:, :3])
        Y /= np.maximum(np.linalg.norm(Y, axis=1, keepdims=True), 1e-20)
        out.append(np.column_stack([Y, X[:, 3]]) if X.shape[1] == 4 else Y)
    return out
