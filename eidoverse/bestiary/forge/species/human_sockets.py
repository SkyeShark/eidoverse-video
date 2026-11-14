"""THE HUMAN'S SOCKETS, PORTS AND RING RECORDS (H4, the rig builder, 11-01; HUMAN_PLAN §4.4, §6.2, decision 2):
what makes the human a BASE the remix can use. Every site is measured on the shipped surface: the refined LOW's
welded vertices in the glb's T-POSE REST (h4/rig/weights/tpose_<sex>.npz, the positions the glb's split meshes carry,
through r05's skinning), the weights the glb carries (h4/rig/face/weights_full_<sex>.npz) and the H1 cage's ring loops
(h3/look/cage_<sex>_recs.pkl: the LOW is the cage at its level-0 limit, so a cage loop IS a low loop; H4's refinement
appended its new vertices after the cage's and the rings it touched are checked here, edge by edge).

  RING RECORD (forge/graft.py's ring_record, for a human ring): K vertices in the loop's order, vertex 0 the record's
  first; the FRAME (origin the loop's centroid, normal Z the loop plane's normal turned toward the NATIVE side, the
  tangent X toward vertex 0 made square to Z); the deviation of each vertex from the standard angle 2 pi k / K about Z;
  the planarity (max |z| / r_mean); r_mean; the collar's h (the mean distance off the ring's plane of the next row of
  vertices, both sides); the FROZEN positions, normals and (joint, weight) pairs as the glb's float32 buffers hold them
  (the bits too), with each vertex's split copies in the HEAD and BODY meshes; the texel density at the ring (its
  adjacent quads' UV area on their set, 4096); the ROOT joint k (it stays: decision 2), the NATIVE group (the faces
  beyond the ring: the smaller side of the surface cut along the loop; joint k's descendants, less the twist and helper
  leaves the ring's own weights hold, "a twist leaf straddling a ring is kept" [X R5]); ring_problems (graft.py's
  bars: K a multiple of 4, unit frozen normals, planar within 0.02 r_mean, no weight on a native joint, a density with
  a set, no unknown joint).
  SOCKETS: one node per §4.4 site, `socket_<slot>` on its joint, translation-only in the joint's frame (every joint's
  rest rotation is the identity in the VRM rest), extras.slot by remix/slots.py's slot_extras (the kind, side,
  interface, joint, the PORT frame from its outward normal, the interface's dims); the seats (seat_hat, seat_glasses)
  are r10's, hung under socket_head_top and socket_eyes.
  H4b (11-02, for HX0; the H4 check's list): THE FRAME is the socket's port frame (slots.port_frame: Z outward on a
  surface port, from the ring vertices' skin normals, never the plug's side; distal on a cut; X its port tangent), so
  ring and socket share one frame and pairs mirror; THE ORDER is CROSSBREED §2.2's (vertex 0 nearest X, right-handed on
  _L and unsided rings, left-handed on _R: vertex k of R the mirror of vertex k of L, checked by the LOW's mirror map);
  THE NATIVE GROUP is whole: the faces as lists (LOW quads, and per skin mesh the glb's triangle indices with its
  material: ASSEMBLE's prims), the joints exactly (the root's twist leaves kept only when they straddle the ring), the
  sockets and seats in the region or on its joints, the mesh nodes (eyes, mouth, eye parts) inside it.

    rings = ring_records(sex, data)        data: load(sex) (the low, the T-pose, the weights, the cage records, the UVs)
    socks = socket_table(sex, data, rings, SL)   SL: the slots module that knows the human's kinds (the staged patch)
"""
import json
import os
import pickle

import numpy as np

VERSION = 'h4b-sockets-2'
SET_SIZE = 4096
TWIST_LEAF = ('_twist_', 'helper_')


def _unit(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def load(sex, rig_dir, h3_dir, mesh_dir=None):
    """the arrays the records read, per sex (module docstring). mesh_dir (H4b): where the LOW (low/) and the skeleton
    (skel/) are read, when they are not rewritten beside the weights (rig_dir: weights/, face/); also the LOW's mirror
    map (mir: each vertex's twin) and the suprasternal notch's LOW vertex (hm08's landmark through the H3 cage's c2h and
    bmap: the cage records' landmarks are hm08 ids, not LOW ids)"""
    md = mesh_dir or rig_dir
    CZ = np.load(os.path.join(md, 'low', f'cage_{sex}.npz'))
    TP = np.load(os.path.join(rig_dir, 'weights', f'tpose_{sex}.npz'))
    WZ = np.load(os.path.join(rig_dir, 'face', f'weights_full_{sex}.npz'))
    UZ = np.load(os.path.join(md, 'low', f'uv_{sex}.npz'))
    sk = json.load(open(os.path.join(md, 'skel', f'skeleton_{sex}.json'), encoding='utf-8'))
    fj = json.load(open(os.path.join(rig_dir, 'face', f'face_{sex}.json'), encoding='utf-8'))
    recs = pickle.load(open(os.path.join(h3_dir, 'look', f'cage_{sex}_recs.pkl'), 'rb'))
    zc = np.load(os.path.join(h3_dir, 'look', f'cage_{sex}.npz'))
    lm_low = {}
    for k, h in recs['landmarks'].items():                 # hm08 id -> the body cage's id (c2h) -> the whole cage's (bmap)
        b = np.nonzero(zc['c2h'] == h)[0]
        if len(b):
            lm_low[k] = int(zc['bmap'][b[0]])
    names = [str(x) for x in WZ['names']]
    parents = {n: (str(p) or None) for n, p in zip(names, WZ['parents'])}
    PT = {k: np.asarray(v, np.float64) for k, v in sk['tpose_mm'].items()}
    for k, v in fj['joints'].items():
        PT[k] = PT[v['parent']] + (np.asarray(v['apose_mm']) - np.asarray(sk['apose_mm'][v['parent']]))
    return dict(sex=sex, Q=CZ['Q'].astype(np.int64), n_cage=int(CZ['n_cage']), V=TP['V'] * 1e-3, N=_unit(TP['N']),
                J4=WZ['J4'].astype(np.int64), W4=WZ['W4'].astype(np.float32), names=names, parents=parents,
                PT={k: v * 1e-3 for k, v in PT.items()}, recs=recs, UZ=UZ, sk=sk, mir=CZ['mir'].astype(np.int64),
                landmarks_low=lm_low)


def descendants(parents, k):
    kids = {}
    for c, p in parents.items():
        kids.setdefault(p, []).append(c)
    out, st = [], list(kids.get(k, []))
    while st:
        c = st.pop()
        out.append(c)
        st += kids.get(c, [])
    return sorted(out)


def _edges(Q):
    E = set()
    for q in Q.tolist():
        for a, b in zip(q, q[1:] + q[:1]):
            E.add((min(a, b), max(a, b)))
    return E


def _split_sides(Q, loop):
    """the quads on each side of a closed loop of edges: a flood over quads through edges not on the loop; returns
    the components (lists of quad ids), largest first"""
    on = {(min(a, b), max(a, b)) for a, b in zip(loop, loop[1:] + loop[:1])}
    e2q = {}
    for qi, q in enumerate(Q.tolist()):
        for a, b in zip(q, q[1:] + q[:1]):
            e2q.setdefault((min(a, b), max(a, b)), []).append(qi)
    seen = np.full(len(Q), -1)
    comps = []
    for s in range(len(Q)):
        if seen[s] >= 0:
            continue
        c = len(comps)
        stack, comp = [s], []
        seen[s] = c
        while stack:
            qi = stack.pop()
            comp.append(qi)
            q = Q[qi].tolist()
            for a, b in zip(q, q[1:] + q[:1]):
                e = (min(a, b), max(a, b))
                if e in on:
                    continue
                for qj in e2q[e]:
                    if seen[qj] < 0:
                        seen[qj] = c
                        stack.append(qj)
        comps.append(comp)
    return sorted(comps, key=len, reverse=True)


def native_of(D, root, loop=None):
    """a ring's NATIVE joints: the root's descendants, less the leaves of the root's OWN bone (its twists and helpers,
    children of the root: "a twist leaf straddling a ring is kept" [X R5]; the upper arm's twists stay with a shoulder
    ring, the thigh's are native to the waist ring, whose root is the pelvis)"""
    return [j for j in descendants(D['parents'], root)
            if not (any(t in j for t in TWIST_LEAF) and D['parents'].get(j) == root)]


def _native_side(D, comps, native_joints, loop):
    """the quads beyond the ring: the side carrying more weight on the native joints; with none (a port, a plug, a
    nail fold, an ear) the smaller side (the plug's own patch). The skin split along the loop has two sides, or one if
    the loop is not a cut (its edges missing: then nothing is native)"""
    if len(comps) < 2:
        return []
    if not native_joints:
        return comps[-1]
    cols = [D['names'].index(j) for j in native_joints if j in D['names']]
    Q = D['Q']
    ls = set(int(v) for v in loop)

    def wsum(c):
        vs = np.array(sorted(set(np.unique(Q[c]).tolist()) - ls), np.int64)
        return float((np.isin(D['J4'][vs], cols) * D['W4'][vs]).sum())
    return max(comps[:2], key=wsum)


def clean_ring_weights(V, Q, dense, names, rings, fade_rows=2.0):
    """THE RING'S WEIGHTS FROZEN CLEAN (graft.ring_problems' 'weights beyond the cut', the lead's decision 2: joint k
    stays the graft root and the ring keeps its shipped weights): per ring (name, loop, root, native joints), every
    weight a native joint holds on the ring and on the KEPT side goes to the root, and on the native side it eases in
    over `fade_rows` collar rows past the ring (a smoothstep along the ring's normal), so the field has no step. The
    bone heat let the thighs reach the waist ring (3-6 %) and the forearm the armpit (0.03-0.12 %). V the welded low
    (any units), Q its quads, dense (n, len(names)) edited in place; returns {ring: weight moved (sum, max per vertex)}"""
    rep = {}
    order = np.argsort(-dense, 1)[:, :4]
    D4 = dict(names=list(names), Q=Q, J4=order, W4=np.take_along_axis(dense, order, 1))
    for name, loop, root, native in rings:
        if not native:
            continue
        cols = [names.index(j) for j in native if j in names]
        k = names.index(root)
        comps = _split_sides(Q, [int(v) for v in loop])
        nq = _native_side(D4, comps, native, loop)
        ls = set(int(v) for v in loop)
        nat_v = np.array(sorted(set(np.unique(Q[nq]).tolist()) - ls), np.int64)
        kept = np.ones(len(V), bool)
        kept[nat_v] = False
        P = V[np.asarray(loop, np.int64)]
        O = P.mean(0)
        z = np.linalg.svd(P - O)[2][2]
        if len(nat_v) and np.dot(V[nat_v].mean(0) - O, z) < 0:
            z = -z
        # the collar's row height: the native-side neighbours' mean distance off the ring's plane
        nb = np.unique(Q[[qi for qi, q in enumerate(Q.tolist()) if any(v in ls for v in q)]])
        nb = np.array([v for v in nb if v not in ls and not kept[v]], np.int64)
        h = float(np.mean((V[nb] - O) @ z)) if len(nb) else 0.01
        f = np.ones(len(V))
        f[kept] = 0.0
        d = (V[nat_v] - O) @ z
        f[nat_v] = np.clip(d / max(fade_rows * h, 1e-9), 0.0, 1.0)
        f[nat_v] = f[nat_v] * f[nat_v] * (3.0 - 2.0 * f[nat_v])
        mv = dense[:, cols] * (1.0 - f)[:, None]
        dense[:, cols] -= mv
        dense[:, k] += mv.sum(1)
        rep[name] = dict(moved_sum=round(float(mv.sum()), 4), moved_max=round(float(mv.sum(1).max()), 5),
                         fade_mm=round(float(fade_rows * h * 1e3), 2))
    return rep


def _density(UZ, quads, V):
    """texels per metre on the quads' set (4096): sqrt(UV area / 3-D area) over their corners (V: welded positions)"""
    Q = UZ['Q'][quads]
    uv = UZ['quv'][quads] * SET_SIZE
    P = V[Q]
    a3 = 0.5 * (np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1)
                + np.linalg.norm(np.cross(P[:, 2] - P[:, 0], P[:, 3] - P[:, 0]), axis=1))
    cr = lambda a, b: a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
    a2 = 0.5 * (np.abs(cr(uv[:, 1] - uv[:, 0], uv[:, 2] - uv[:, 0])) + np.abs(cr(uv[:, 2] - uv[:, 0], uv[:, 3] - uv[:, 0])))
    sets = sorted(set(int(x) for x in UZ['qset'][quads]))
    return float(np.sqrt(a2.sum() / max(a3.sum(), 1e-20))), sets


def _copies(UZ, loop):
    """each loop vertex's split copies in the glb's two skin meshes"""
    out = []
    idx = {}
    for S in ('HEAD', 'BODY'):
        o = UZ[f'{S}_orig']
        m = {}
        for i, v in enumerate(o.tolist()):
            m.setdefault(v, []).append(i)
        idx[S] = m
    for v in loop:
        out.append({S: idx[S].get(int(v), []) for S in ('HEAD', 'BODY')})
    return out


def port_tangent(z, side=''):
    """slots.port_frame's TANGENT (CROSSBREED §2.2: the ring's frame IS the socket's port frame), in the creature's
    frame: the lateral axis made square to the normal z, +X on a left or unsided ring, -X on a right one (pairs are mirror
    images), -Z where z lies within 25.8 deg of the lateral axis (|z.x| > 0.9). Kept here so a ring record needs no
    slots module; h4b's g01 gate checks it against slots.port_frame"""
    z = _unit(z)
    ref = np.array([0.0, 0.0, -1.0]) if abs(z[0]) > 0.9 else np.array([-1.0 if side == 'R' else 1.0, 0.0, 0.0])
    return _unit(ref - np.dot(ref, z) * z)


def orient_loop(V, loop, z, side=''):
    """the loop in CROSSBREED §2.2's order (H4b): vertex 0 the loop vertex nearest the port tangent X about z, then
    vertex k at parametric angle 2 pi k / K about z RIGHT-handed on a left or unsided ring, LEFT-handed on an _R one (so
    vertex k of R is the mirror image of vertex k of L). Returns (loop, X, winding): winding +1 when the order runs
    right-handed about z (the signed area in the frame's (x, y) plane positive), -1 left-handed"""
    loop = [int(v) for v in loop]
    P = V[loop]
    O = P.mean(0)
    x = port_tangent(z, side)
    y = np.cross(z, x)
    loc = (P - O) @ np.column_stack([x, y])
    k0 = int(np.argmin(np.abs(np.arctan2(loc[:, 1], loc[:, 0]))))
    loop = loop[k0:] + loop[:k0]
    loc = np.roll(loc, -k0, axis=0)
    area = 0.5 * float(np.sum(loc[:, 0] * np.roll(loc[:, 1], -1) - np.roll(loc[:, 0], -1) * loc[:, 1]))
    want = -1.0 if side == 'R' else 1.0
    if np.sign(area) != want:
        loop = [loop[0]] + loop[1:][::-1]
        area = -area
    return loop, x, int(np.sign(area))


def winding(V, loop, z, x):
    """the measured sense of a loop about z in the frame (x, z x x): +1 right-handed, -1 left-handed (the gate's read)"""
    P = V[np.asarray(loop)]
    loc = (P - P.mean(0)) @ np.column_stack([x, np.cross(z, x)])
    return int(np.sign(np.sum(loc[:, 0] * np.roll(loc[:, 1], -1) - np.roll(loc[:, 0], -1) * loc[:, 1])))


def native_triangles(UZ, native_q):
    """the native LOW quads as the glb's TRIANGLES (H4b: ASSEMBLE drops faces per primitive, by its material's name):
    per skin mesh the sorted triangle indices of its index buffer (uv_<sex>.npz's <S>_quad: each triangle's LOW quad;
    the glb writes <S>_F in that order)"""
    nq = np.zeros(len(UZ['Q']), bool)
    nq[np.asarray(native_q, np.int64)] = True
    out = {}
    for S in ('HEAD', 'BODY'):
        tq = UZ[f'{S}_quad'].astype(np.int64)
        out[f'skin_{S}'] = dict(material=f'human_skin_{S}', triangles=np.nonzero(nq[tq])[0].astype(int).tolist(),
                                of=int(len(tq)))
    return out


def ring_record(D, name, loop, kind, root, native_joints=None, side='', normal_hint=None, cut=None, port=False):
    """one ring's record (module docstring). loop: welded low ids (any start, any sense: H4b orders them); root: joint
    k; port (H4b): a surface port (plugs, horns, scalp, gills, ears, nail folds): its normal Z is the OUTWARD skin
    normal (the mean of the ring vertices' normals), never the plug's side, which faces inward on a concave plug (H4's
    back_shell and gills pointed 176-180 deg into the body); a chain cut or a region's ring: Z toward the native side
    (distal). normal_hint: kept for the records' callers (unused when the side or the skin tells)"""
    V, N, Q = D['V'], D['N'], D['Q']
    loop = [int(x) for x in loop]
    K = len(loop)
    E = _edges(Q)
    P = V[loop]
    O = P.mean(0)
    _, _, vt = np.linalg.svd(P - O)
    z = vt[2]
    comps = _split_sides(Q, loop)
    if native_joints is None:
        native_joints = descendants(D['parents'], root)
    native_q = _native_side(D, comps, native_joints, loop)
    if port:
        if np.dot(N[loop].mean(0), z) < 0:
            z = -z
    elif native_q:
        cn = V[np.unique(Q[native_q])].mean(0)
        if np.dot(cn - O, z) < 0:
            z = -z
    elif normal_hint is not None and np.dot(normal_hint, z) < 0:
        z = -z
    loop, x, wind = orient_loop(V, loop, z, side)
    missing = [i for i, (a, b) in enumerate(zip(loop, loop[1:] + loop[:1])) if (min(a, b), max(a, b)) not in E]
    P = V[loop]
    y = np.cross(z, x)
    loc = (P - O) @ np.column_stack([x, y, z])
    rho = np.hypot(loc[:, 0], loc[:, 1])
    r_mean = float(rho.mean())
    th = np.arctan2(loc[:, 1], loc[:, 0])
    th_std = (-1.0 if side == 'R' else 1.0) * 2.0 * np.pi * np.arange(K) / K
    dth = (th - th_std + np.pi) % (2.0 * np.pi) - np.pi
    # the collar: the next row of vertices on each side (the loop's quad neighbours off the loop)
    ls = set(loop)
    nb = {}
    for q in Q.tolist():
        if any(v in ls for v in q):
            for v in q:
                if v not in ls:
                    nb[v] = q
    nbv = np.array(sorted(nb), np.int64)
    dz = (V[nbv] - O) @ z if len(nbv) else np.zeros(0)
    h_out = float(dz[dz > 0].mean()) if (dz > 0).any() else 0.0
    h_in = float(-dz[dz < 0].mean()) if (dz < 0).any() else 0.0
    names = D['names']
    wts = [[(names[int(D['J4'][v, q])], float(D['W4'][v, q])) for q in range(4) if D['W4'][v, q] > 0.0] for v in loop]
    adj_q = [qi for qi, q in enumerate(Q.tolist()) if sum(v in ls for v in q) >= 2]
    px, sets = _density(D['UZ'], adj_q, V)
    Pj = D['PT'][root]
    copies = _copies(D['UZ'], loop)
    keep_q = np.ones(len(Q), bool)
    keep_q[native_q] = False
    kept_v = np.unique(Q[keep_q])
    nat_v = np.array(sorted(set(np.unique(Q[native_q]).tolist()) - ls), np.int64) if len(native_q) else \
        np.zeros(0, np.int64)
    # (H4b) THE NATIVE JOINTS EXACTLY: the root's descendants, less the root's own twist / helper leaves that carry weight
    # on the ring or the kept side (a leaf straddling the ring is kept, CROSSBREED R5); a leaf whose skin is all beyond
    # the ring goes with it
    kept_leaves = []
    if native_joints:
        lw = set(loop) | set(kept_v.tolist())
        lv = np.array(sorted(lw), np.int64)
        for j in list(native_joints):
            if any(t in j for t in TWIST_LEAF) and D['parents'].get(j) == root and j in names:
                if (np.isin(D['J4'][lv], [names.index(j)]) & (D['W4'][lv] > 0)).any():
                    kept_leaves.append(j)
        native_joints = [j for j in native_joints if j not in kept_leaves]
    tri = native_triangles(D['UZ'], native_q)
    rec = dict(
        name=name, kind=kind, K=K, side=side, root=root, cut=cut,
        handedness=('left-handed about +Z: an _R ring, vertex k the mirror image of its _L twin\'s vertex k' if side == 'R'
                    else 'right-handed about +Z'), winding=wind, port=bool(port),
        loop=loop, loop_edges_missing=missing,
        frame=dict(joint=root, normal=z.round(6).tolist(), tangent=x.round(6).tolist(),
                   rule='slots.port_frame(normal, side): Z outward (a port) or distal (a cut), X its port tangent; '
                        'vertex 0 the loop vertex nearest X',
                   creature=dict(origin=O.round(6).tolist(), R=np.column_stack([x, y, z]).round(6).tolist())),
        origin=(O - Pj).round(6).tolist(),
        verts=P.round(6).tolist(), normals=N[loop].round(6).tolist(), weights=dict(per_vertex=wts),
        verts_f32=P.astype(np.float32).view(np.uint32).tolist(), normals_f32=N[loop].astype(np.float32).view(np.uint32).tolist(),
        theta_dev_deg=np.degrees(dth).round(3).tolist(), v0_off_tangent_deg=round(float(np.degrees(abs(dth[0]))), 3),
        planarity=float(np.abs(loc[:, 2] - loc[:, 2].mean()).max() / max(r_mean, 1e-12)), r_mean=r_mean,
        h=h_out, h_in=h_in, copies=copies, px_per_m=px, set=['HEAD', 'BODY'][sets[0]] if len(sets) == 1 else
        [['HEAD', 'BODY'][s] for s in sets], set_size=SET_SIZE, cls='dry_skin',
        native=dict(group=f'{name}>', faces_low=sorted(int(q) for q in native_q), joints=native_joints,
                    kept_twist_leaves=kept_leaves, sockets=[], nodes=[], fx=[], kept_weighted_beyond=0,
                    meshes=tri, prims={t['material']: t['triangles'] for t in tri.values() if t['triangles']},
                    vertices_low=nat_v.astype(int).tolist()))
    if native_joints:
        did = [names.index(j) for j in native_joints if j in names]
        rec['native']['kept_weighted_beyond'] = int((np.isin(D['J4'][kept_v], did) & (D['W4'][kept_v] > 0)).any(1).sum())
    rec['problems'] = ring_problems(rec, names)
    return rec


def ring_problems(rec, joint_names):
    """forge/graft.py ring_problems' bars on a human ring, plus the loop's own integrity (every loop edge a low edge)"""
    out = []
    if rec['K'] % 4:
        out.append(f'K {rec["K"]} is not 0 mod 4')
    if len(rec['normals']) != rec['K'] or not all(abs(np.linalg.norm(n) - 1.0) < 1e-5 for n in rec['normals']):
        out.append('a frozen normal is missing or not unit')
    if rec['planarity'] > 0.02:
        out.append(f'non-planar: {rec["planarity"]:.4f} r')
    bad = {nm for wv in rec['weights']['per_vertex'] for nm, _ in wv if nm in rec['native']['joints']}
    if bad:
        out.append(f'weights beyond the cut on the ring: {sorted(bad)}')
    if rec['native']['kept_weighted_beyond']:
        out.append(f'kept base vertices weighted on native joints: {rec["native"]["kept_weighted_beyond"]}')
    unknown = {nm for wv in rec['weights']['per_vertex'] for nm, _ in wv if nm not in joint_names}
    if unknown:
        out.append(f'weights on unknown joints {sorted(unknown)}')
    if not rec.get('set') or not rec.get('px_per_m'):
        out.append('a density with no set')
    if rec['loop_edges_missing']:
        out.append(f'loop edges not in the low: {rec["loop_edges_missing"]}')
    return out


# the §6.2 table: (record name, the cage record's place, kind, root joint per side, the cut's name)
LIMB_RINGS = (('shoulder', 'armscye', 'leg_fore', 'upperarm'), ('elbow', 'elbow', 'leg_fore', 'lowerarm'),
              ('wrist', 'wrist', 'leg_fore', 'hand'), ('hip', 'hip', 'leg_hind', 'thigh'),
              ('knee', 'knee', 'leg_hind', 'calf'), ('ankle', 'ankle', 'leg_hind', 'foot'))
PLUG_ROOTS = dict(back_upper='spine_05', back_lower='spine_02', back_shell='spine_04', sacral='pelvis')
NAIL_JOINTS = dict(thumb='thumb_03', index='index_03', middle='middle_03', ring='ring_03', little='pinky_03')


def _dominant_joint(D, loop):
    w = {}
    for v in loop:
        for q in range(4):
            if D['W4'][v, q] > 0:
                nm = D['names'][int(D['J4'][v, q])]
                w[nm] = w.get(nm, 0.0) + float(D['W4'][v, q])
    return max(w, key=w.get)


def ring_specs(recs, parents):
    """the rings whose native side holds joints (the neck, the limb rings, the waist): [(name, loop, root, native)],
    for clean_ring_weights. The NECK's root is the HEAD (HUMAN_PLAN §6.2: its native group is the head's jaw, tongue,
    eyes, lids and face joints; the donor's skull hangs from the head joint, which stays); the WAIST's is the pelvis
    (the legs native)"""
    D = dict(parents=parents)
    out = [('neck', recs['head']['neck']['loop'], 'head', native_of(D, 'head'))]
    for nm, src, kind, j in LIMB_RINGS:
        for s in 'LR':
            out.append((f'{nm}_{s}', recs['body_rings'][f'{src}_{s}'], f'{j}_{s}', native_of(D, f'{j}_{s}')))
    legs = [j for s in 'LR' for j in [f'thigh_{s}'] + descendants(parents, f'thigh_{s}')]
    out.append(('waist', recs['body_rings']['waist'], 'pelvis', legs))
    return out


def ring_records(D):
    """every §6.2 ring of one sex: the neck, the six limb rings a side, the waist, the back's four ports and its shell
    port, the sacral port, the horns, the scalp plugs, the gills, the ears and the nail folds"""
    R = D['recs']
    out = {}
    out['neck'] = ring_record(D, 'neck', R['head']['neck']['loop'], 'head_region', 'head', cut='neck')
    for nm, src, kind, j in LIMB_RINGS:
        for s in 'LR':
            out[f'{nm}_{s}'] = ring_record(D, f'{nm}_{s}', R['body_rings'][f'{src}_{s}'], kind, f'{j}_{s}', side=s, cut=nm)
    legs = [j for s in 'LR' for j in [f'thigh_{s}'] + descendants(D['parents'], f'thigh_{s}')]
    out['waist'] = ring_record(D, 'waist', R['body_rings']['waist'], 'body_region', 'pelvis', native_joints=legs,
                               cut='waist')
    for nm, p in R['plugs'].items():
        base = nm[:-2] if nm.endswith(('_L', '_R')) else nm
        side = nm[-1] if nm.endswith(('_L', '_R')) else ''
        kind = {'back_upper': 'back_limb', 'back_lower': 'back_limb', 'back_shell': 'back', 'sacral': 'tail_base'}[base]
        # the plugs' loops in the merged low's numbering are body_rings' (the plugs record holds the body cage's own)
        out[nm] = ring_record(D, nm, R['body_rings'][nm], kind, PLUG_ROOTS[base], native_joints=[], side=side,
                              normal_hint=np.asarray(p['normal']), cut='port', port=True)
    for nm, h in R['head'].items():
        if h.get('kind') in ('horn', 'scalp', 'gill', 'ear') and h.get('loop') is not None:
            side = nm[-1] if nm.endswith(('_L', '_R')) else ''              # (H4b) the side from the name, as the plugs
            root = 'head' if h['kind'] != 'gill' else _dominant_joint(D, h['loop'])
            out[nm] = ring_record(D, nm, h['loop'], h['kind'], root, native_joints=[], side=side,
                                  normal_hint=np.asarray(h['normal']), cut='port', port=True)
    for nm, h in R['nails'].items():
        digit, side = nm.split('_')[1], nm.split('_')[2]
        root = f'{NAIL_JOINTS[digit]}_{side}' if digit in NAIL_JOINTS else f'ball_{side}'
        out[nm] = ring_record(D, nm, h['loop'], 'claw', root, native_joints=[], side=side,
                              normal_hint=np.asarray(h['normal']), cut='nail_fold', port=True)
    mirror_pairs(D, out)
    return out


def mirror_pairs(D, rings):
    """(H4b) every _L / _R pair as TRUE MIRRORS (CROSSBREED §2.2): vertex k of R the mirror image of vertex k of L, by the
    LOW's mirror map (topology) and by position (the T-pose rest, x negated); the frames mirror too (normal and tangent
    with x negated, compared component by component: the records round them to 1e-6, so an arccos of their dot reads
    0.02-0.08 deg for identical frames). Each record gets mirror = {twin, ids_ok, max_mm, frame_d}; a mismatch is a ring
    problem"""
    mir = D['mir']
    Mx = np.array([-1.0, 1.0, 1.0])
    for nm, r in rings.items():
        if not nm.endswith('_R') or nm[:-2] + '_L' not in rings:
            continue
        L = rings[nm[:-2] + '_L']
        ids_ok = len(L['loop']) == len(r['loop']) and all(int(mir[a]) == int(b) for a, b in zip(L['loop'], r['loop']))
        dmax = float(np.abs(np.asarray(L['verts']) * Mx - np.asarray(r['verts'])).max()) if ids_ok else float('inf')
        fd = max(float(np.abs(np.asarray(L['frame'][k]) * Mx - np.asarray(r['frame'][k])).max())
                 for k in ('normal', 'tangent'))
        for rr, tw in ((L, nm), (r, nm[:-2] + '_L')):
            rr['mirror'] = dict(twin=tw, ids_ok=bool(ids_ok), max_mm=round(dmax * 1e3, 6), frame_d=round(fd, 9))
            if not ids_ok or dmax > 1e-6 or fd > 2e-6:
                rr['problems'] = rr['problems'] + [f'not the mirror of {tw}: ids {ids_ok}, {dmax * 1e3:.3g} mm, frame '
                                                   f'{fd:.3g}']


def native_members(D, rec, sockets, meshes):
    """(H4b) the NATIVE GROUP's nodes for one ring, so ASSEMBLE can drop it whole (its assert, assemble.py:117-121: every
    child of a dropped node is dropped too):
      * sockets (and their seats, every node under them): on a native joint; a PORT's own socket (it goes with its plug,
        H4's choice, kept); carrying a ring whose loop lies in the native region (the nails' in the hand, the scalp's in
        the head); or a mount whose origin's nearest skin vertex is native, unless it sits ON this ring (within half a
        collar row of its plane and 1.5 r of its axis: a cut's own socket, the neck collar, the wrist, the ankle);
      * meshes (the instances: eyes, teeth, gums, tongue, the eye's parts, any part outside the skin): those whose
        vertices' nearest skin vertices are native (99 % or more), and every mesh node under a native joint or socket.
    sockets: [dict(name, joint, origin (3,) m in the creature's T-pose frame, ring (name or None), ring_loop (its LOW ids
    or None), children [names])]; meshes: [dict(node, points (n, 3) m T-pose, under (the parent chain's node names))].
    Returns (sockets, nodes)"""
    from scipy.spatial import cKDTree
    V = D['V']
    nat = np.zeros(len(V), bool)
    nat[np.asarray(rec['native']['vertices_low'], np.int64)] = True
    if not nat.any():
        return [], []
    tree = cKDTree(V)
    O = np.asarray(rec['frame']['creature']['origin'])
    z = np.asarray(rec['frame']['normal'])
    njs = set(rec['native']['joints'])
    out_s = []
    for s in sockets:
        p = np.asarray(s['origin'])
        # ON the ring: a cut's own sockets at its centroid (a port has no such socket but its own, handled below: on a
        # shallow plug the test would also hold for a mount inside it, as g02 found for socket_back_0 in the sacral plug)
        on_ring = (not rec.get('port')) and abs(np.dot(p - O, z)) <= 0.5 * max(rec['h'], 1e-4) and \
            np.linalg.norm((p - O) - np.dot(p - O, z) * z) <= 1.5 * rec['r_mean']
        if s['joint'] in njs:
            take = True
        elif s.get('ring') == rec['name']:
            take = bool(rec.get('port'))
        elif s.get('ring_loop') is not None:
            take = bool(nat[np.asarray(s['ring_loop'], np.int64)].all())
        else:
            take = (not on_ring) and bool(nat[tree.query(p)[1]])
        if take:
            out_s += [s['name']] + list(s.get('children', []))
    dropped = set(out_s) | njs
    out_n = []
    for m in meshes:
        if any(u in dropped for u in m['under']):
            out_n.append(m['node'])
            continue
        if len(m['points']):
            frac = float(nat[tree.query(np.asarray(m['points']))[1]].mean())
            if frac >= 0.99:
                out_n.append(m['node'])
    return out_s, out_n
