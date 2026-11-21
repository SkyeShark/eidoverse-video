"""CROSSBREED, the graft pipeline's forge side (work/bestiary/research/CROSSBREED_DESIGN.md §2-§4, §8 M0 / M1a, and
THE LEAD'S DECISIONS 1-13 at its end). A graft site on a base is a RING; a part grafted there is GENERATED for that
ring, never cut from another creature:

  RING RECORD   ring_record(): K vertices at the standard angles of the socket's frame (vertex k at 2 pi k / K about
                Z from X; the octopus arms are rotational copies, so every arm's record is right-handed: R26), their
                FROZEN positions, normals and (joint name, weight) pairs bit for bit from the shipped glb, the UV seam
                vertex, the base's texel density there, the section in sdf.SWEEP's vocabulary with the per-vertex
                residual, the collar h, the native group it drops and the morph deltas it carries (§2.11).
  NATIVE GROUP  everything a graft removes (§2.1, decision 2 = R3 option (a)): the faces beyond the ring, joint k's
                DESCENDANTS (joint k itself stays as the graft root, so the ring keeps its shipped k-1 / k weights:
                no pin, no re-weight of the base), the geometric suckers rooted beyond the ring, the tip socket.
  BAND          the native continued past the ring for L_band = max(0.75 r, |dr| / 0.25, two ring steps) (§2.7):
                its loops are the base's own (its build cache: the shipped low), so nothing at z = 0 is new.
  PART          the donor family's generator in the socket's frame (FramedSDF: x_world = R x_donor + t; the octopus
                arm's generator is octopus.build_cage's arm loop, extracted: ring proxies at the arm's stations, the
                tip's quad-grid cap, projected and relaxed by retopo.fit) from the band's end; weights frozen over the
                ring and band, then the donor's own ramp (rig.hat_weights) smoothed with the band pinned; normals
                welded on the part, the ring's frozen (§2.5, §2.6).
  ISLANDS       the STRIP island (an APRON of the native's own loops BEHIND the ring, then the ring, the band and the
                donor's first length: the ring is an interior line of its island, so the part's texels across it
                are the base's surface continued, for the bake's and the material's neighbourhoods and the
                renderer's filtering and mips; the apron is baked and painted, never shipped), then the donor's own
                islands; LSCM + ARAP per island (octopus_uv's rule) packed at the RING'S density into the smallest
                atlas that holds them (decision 7: one parts atlas per crossbreed, the base's sets untouched).
  MATERIAL      the base's skin pass on the part's own bake with the BASE'S convexity normaliser (decision 13: a graft
                never re-measures the base), the GRAFT pack (§2.8: R w, G the dressing, B the harmonize weight,
                A z / L_band) on every WELD part.

M1a, the IDENTITY graft (§8): the octopus's own arm R1 (arm0) past cut 8 rebuilt by this pipeline from the octopus's
own generator, same spec and skin, w = 0 (the high is the native high): it must be indistinguishable from the
ungrafted octopus. M0, the NULL graft (R19): the native low, weights and suckers COPIED, only re-UV'd and re-baked: the
pipeline's noise floor. The gates are forge/graft_gates.py; ASSEMBLE is forge/assemble.py.
"""
import hashlib
import json
import math

import numpy as np

TAU = 2.0 * math.pi


# ============================================================================================ the base's arrays
def sha1_file(path):
    with open(path, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


def load_base(base_dir, glb_name='octopus.glb'):
    """the shipped octopus as the graft reads it: the glb's shared vertex set (POSITION, NORMAL, TANGENT, TEXCOORD_0
    in the forge's v-up convention, JOINTS_0 / WEIGHTS_0) and each primitive's triangles by material name, the
    sucker primitive's own set, the skin's joint names and bind worlds (cyborg_octopus.Rig: three's composition), the
    low.npz beside it (V, F, region, orig, face_set, order, the sets' densities), the glb's sha1 (the build hash)"""
    import os
    from . import cyborg_octopus as CO
    from . import gltf
    path = os.path.join(base_dir, glb_name)
    G = gltf.read(path)
    j = G['json']
    acc = G['accessor']
    prims = j['meshes'][0]['primitives']
    mats = [m['name'] for m in j['materials']]
    p0 = prims[0]['attributes']
    uv = acc(p0['TEXCOORD_0']).astype(np.float64)
    out = dict(path=path, sha1=sha1_file(path), json=j, G=G,
               V32=acc(p0['POSITION']).copy(), N32=acc(p0['NORMAL']).copy(), T32=acc(p0['TANGENT']).copy(),
               UV=np.column_stack([uv[:, 0], 1.0 - uv[:, 1]]), J=acc(p0['JOINTS_0']).astype(np.int64),
               W32=acc(p0['WEIGHTS_0']).copy(), prims={}, mats=mats)
    for k, p in enumerate(prims):
        out['prims'][mats[p['material']]] = dict(index=k, F=acc(p['indices']).reshape(-1, 3).astype(np.int64),
                                                 attrs=dict(p['attributes']), material=p['material'],
                                                 targets=len(p.get('targets', [])))
    rig = CO.Rig(path)
    out['rig'] = rig
    out['jnames'] = list(rig.jnames)
    out['world'] = rig.worlds()
    L = dict(np.load(os.path.join(base_dir, 'low.npz'), allow_pickle=True))
    out['low'] = L
    nL = len(L['V'])
    assert np.abs(out['V32'][:nL].astype(np.float64) - L['V']).max() < 1e-6, 'the glb is not this low'
    out['n_low'] = nL
    return out


def joint_world(base, name):
    return base['world'][base['rig'].index[name]]


# ============================================================================================ the arm frame
def arm_frame_at(arm, s):
    """an arm's centreline point and its rotation-minimising frame at share s (octopus.build_cage's arm_frame, without
    the radius): P, n (aboral: theta 0), b, t"""
    Pa, na, ba, ta = arm
    sa = np.linspace(0.0, 1.0, len(Pa))
    ip = lambda X: np.array([np.interp(s, sa, X[:, k]) for k in range(3)])
    return ip(Pa), ip(na), ip(ba), ip(ta)


def ring_frame(arm, s):
    """the socket frame of a ring at share s on an octopus arm (§2.2): origin the centreline point, Z the distal
    tangent, X the direction of vertex 0 (the cage's alpha -90 deg: -b), Y = Z x X (the aboral normal n): vertex k sits
    at parametric angle 2 pi k / 16 about Z from X, right-handed (the cage puts it at cos(a) n + sin(a) b with
    a = 2 pi k / 16 - pi / 2). Returns (origin, R with columns X, Y, Z)"""
    P, n, b, t = arm_frame_at(arm, s)
    t = t / np.linalg.norm(t)
    X = -b - t * np.dot(-b, t)
    X /= np.linalg.norm(X)
    Y = np.cross(t, X)
    return P, np.column_stack([X, Y, t])


# ============================================================================================ the ring record
def fit_section(rho, theta, aspects=np.arange(0.70, 1.3001, 0.0025)):
    """a ring's section in sdf.SWEEP's vocabulary, r(th) = r0 (1 + a2 cos 2(th - phi2) + a3 cos 3(th - phi3) +
    a4 cos 4 th) x asp / sqrt(asp^2 cos^2 th + sin^2 th), least squares (the aspect searched, the harmonics linear for
    each), with each vertex's residual (so the record stays exact). Returns (dict, residual (K,))"""
    best = None
    c, s = np.cos(theta), np.sin(theta)
    for asp in aspects:
        sq = asp / np.sqrt(asp * asp * c * c + s * s)
        A = np.column_stack([sq, sq * np.cos(2 * theta), sq * np.sin(2 * theta), sq * np.cos(3 * theta),
                             sq * np.sin(3 * theta), sq * np.cos(4 * theta)])
        x, *_ = np.linalg.lstsq(A, rho, rcond=None)
        res = rho - A @ x
        e = float((res ** 2).sum())
        if best is None or e < best[0]:
            best = (e, asp, x, res)
    _, asp, x, res = best
    r0 = float(x[0])
    sec = dict(r0=r0, a2=float(np.hypot(x[1], x[2]) / r0), phi2=float(0.5 * np.arctan2(x[2], x[1])),
               a3=float(np.hypot(x[3], x[4]) / r0), phi3=float(np.arctan2(x[4], x[3]) / 3.0),
               a4=float(x[5] / r0), aspect=float(asp))
    return sec, res


def ring_record(base, cage, arms, spec, chain_j=0, cut=8, ring_i=None, set_size=1280, apron=3):
    """THE RING RECORD of chain arm<chain_j> at its listed cut `cut` (§2.11), measured on the shipped glb (frozen bits)
    and the cage's structure (cage: work/.../out/p02_cage.npz's arrays: rings (cage ids, vertex k in order), ring_s,
    ic, i30, i62, cap_v, order). The ring is the low's ring nearest the cut's share (forge/cyborg_octopus.cut_arm's);
    its K = 16 vertices take their positions, normals and weights from the glb's float32 buffers, each split copy
    listed. Decision 2 (R3 option (a)): joint `cut` is the graft ROOT and stays; the native group is its descendants."""
    from . import cyborg_octopus as CO
    from .species import octopus as O
    from .species import octopus_rig as OR
    L = base['low']
    orig = L['orig']
    rings = cage['rings']
    ic = int(cage['ic']) if ring_i is None else int(ring_i)
    s_ring = float(cage['ring_s'][ic])
    K = len(rings[ic])
    copies = {}
    for i in range(base['n_low']):
        copies.setdefault(int(orig[i]), []).append(i)
    low_k = [copies[int(c)] for c in rings[ic]]
    seam = [k for k, cp in enumerate(low_k) if len(cp) > 1]
    first = np.array([cp[0] for cp in low_k])
    V = base['V32'][first].astype(np.float64)
    N = base['N32'][first].astype(np.float64)
    names = base['jnames']
    wts = []
    for v in first:
        wts.append([(names[int(base['J'][v, q])], float(base['W32'][v, q])) for q in range(4)
                    if base['W32'][v, q] > 0.0])
    for cp in low_k:                     # every split copy carries the same bits (the weld)
        for v in cp[1:]:
            assert np.array_equal(base['V32'][v], base['V32'][cp[0]]) and np.array_equal(base['N32'][v], base['N32'][cp[0]])
            assert np.array_equal(base['J'][v], base['J'][cp[0]]) and np.array_equal(base['W32'][v], base['W32'][cp[0]])
    arm = arms[cage['order'][chain_j]]
    O_, R_ = ring_frame(arm, s_ring)
    loc = (V - O_) @ R_
    theta_std = TAU * np.arange(K) / K
    theta_got = np.arctan2(loc[:, 1], loc[:, 0])
    dth = (theta_got - theta_std + math.pi) % TAU - math.pi
    rho = np.hypot(loc[:, 0], loc[:, 1])
    sec, res = fit_section(rho, theta_std)
    r_mean = float(rho.mean())
    # the next ring out and in: the collar h (one ring step: none is shorter than 0.15 r here), the section's slope
    nxt = base['V32'][[copies[int(c)][0] for c in rings[ic + 1]]].astype(np.float64)
    prv = base['V32'][[copies[int(c)][0] for c in rings[ic - 1]]].astype(np.float64)
    h = float(np.linalg.norm(nxt.mean(0) - V.mean(0)))
    h_in = float(np.linalg.norm(prv.mean(0) - V.mean(0)))
    O_n, R_n = ring_frame(arm, float(cage['ring_s'][ic + 1]))
    sec_n, _ = fit_section(np.hypot(*((nxt - O_n) @ R_n)[:, :2].T), theta_std)
    dz = float(np.dot(O_n - O_, R_[:, 2]))
    # the base's texel density at the ring: its proximal triangles (the ring and the ring before) in the arms set
    F = L['F']
    ring_low = set(np.concatenate(low_k).tolist())
    prev_low = set(np.concatenate([copies[int(c)] for c in rings[ic - 1]]).tolist())
    on = np.array([all((v in ring_low) or (v in prev_low) for v in f) for f in F.tolist()])
    Ft = F[on]
    P3, T2 = L['V'][Ft], L['UV'][Ft] * set_size
    a3 = 0.5 * np.linalg.norm(np.cross(P3[:, 1] - P3[:, 0], P3[:, 2] - P3[:, 0]), axis=1)
    d1, d2 = T2[:, 1] - T2[:, 0], T2[:, 2] - T2[:, 0]
    a2 = 0.5 * np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0])
    px_ring = float(np.sqrt(a2.sum() / a3.sum()))
    px_set = float(L['px_arms']) * set_size / float(L['px_at'])
    # the native group: the faces beyond the ring (cut_arm's distal triangles), joint `cut`'s descendants, the suckers
    # rooted beyond the ring, the tip socket
    oc = CO.Octopus(base['path'])
    c = CO.cut_arm(oc, chain_j, cut)
    assert set(c['ring'].tolist()) == ring_low, 'the cut ring is not the record\'s ring'
    jn = f'arm{chain_j}'
    desc = [f'{jn}_{k:02d}' for k in range(cut + 1, OR.N_ARM_JOINTS)]
    arm_pos = base['prims']['octopus_arms']
    tri_key = {tuple(sorted(t)): i for i, t in enumerate(arm_pos['F'].tolist())}
    distal_prim = np.array(sorted(tri_key[tuple(sorted(t))] for t in F[c['distal']].tolist()))
    # weights on a joint beyond the cut (the native group's) anywhere on the kept base: an export error (§2.11)
    keep_tris = np.ones(len(F), bool)
    keep_tris[c['distal']] = False
    kept_v = np.unique(F[keep_tris])
    did = [names.index(d) for d in desc]
    beyond = int((np.isin(base['J'][kept_v], did) & (base['W32'][kept_v] > 0)).any(1).sum())
    targets = {nm: p['targets'] for nm, p in base['prims'].items()}
    js = OR.arm_joint_s(spec)
    Wk = joint_world(base, f'{jn}_{cut:02d}')
    to_j = lambda p: (np.linalg.inv(Wk) @ np.append(p, 1.0))[:3]
    rec = dict(
        K=int(K), chain=jn, cut=int(cut), ring_index=ic, root=f'{jn}_{cut:02d}', handedness='right-handed about +Z',
        frame=dict(joint=f'{jn}_{cut:02d}', normal=(Wk[:3, :3].T @ R_[:, 2]).tolist(),
                   tangent=(Wk[:3, :3].T @ R_[:, 0]).tolist(), creature=dict(origin=O_.tolist(), R=R_.tolist())),
        origin=to_j(O_).tolist(), section=sec, section_residual=res.tolist(),
        slope=dict(dr0_dz=(sec_n['r0'] - sec['r0']) / dz, dz=dz),
        verts=V.tolist(), normals=N.tolist(), weights=dict(per_vertex=wts),
        verts_f32=base['V32'][first].view(np.uint32).tolist(), normals_f32=base['N32'][first].view(np.uint32).tolist(),
        theta_dev_deg=np.degrees(dth).tolist(), planarity=float(np.abs(loc[:, 2] - loc[:, 2].mean()).max() / r_mean),
        r_mean=r_mean, h=h, h_in=h_in, seam_k=seam, low_copies=[[int(v) for v in cp] for cp in low_k],
        px_per_m=px_ring, px_set=px_set, set='arms', set_size=int(set_size), cls='wet_skin', st_s=s_ring,
        cut_s=float(0.5 * (js[cut - 1] + js[cut])), apron_rings=int(apron),
        native=dict(group=f'{jn}>{cut}', faces_low=c['distal'].tolist(), faces_prim=distal_prim.tolist(),
                    primitive='octopus_arms', joints=desc, sockets=[f'socket_{jn}_tip'], fx=[],
                    kept_weighted_beyond=beyond),
        targets=dict(counts=targets, deltas={}, note='the base carries no morph targets (rest v3 parked, decision 13): '
                                                       'nothing to freeze; a rest pose re-runs these gates'),
        build=base['sha1'], radius_spec=float(O.arm_radius(np.array([s_ring]), spec)[0]))
    return rec


def ring_problems(rec, joint_names):
    """the export errors a ring record must not carry (§2.11; never fallbacks): a missing frozen normal, K not 0 mod 4,
    a non-planar ring (> 0.02 r), a weight on a joint beyond the cut, a density with no set, a weight on an unknown
    joint"""
    out = []
    if rec['K'] % 4:
        out.append(f'K {rec["K"]} is not 0 mod 4')
    if len(rec['normals']) != rec['K'] or not all(abs(np.linalg.norm(n) - 1.0) < 1e-5 for n in rec['normals']):
        out.append('a frozen normal is missing or not unit')
    if rec['planarity'] > 0.02:
        out.append(f'non-planar: {rec["planarity"]:.4f} r')
    bad = {nm for wv in rec['weights']['per_vertex'] for nm, _ in wv if nm in rec['native']['joints']}
    if bad or rec['native']['kept_weighted_beyond']:
        out.append(f'weights beyond the cut: {sorted(bad)} (kept base vertices {rec["native"]["kept_weighted_beyond"]})')
    unknown = {nm for wv in rec['weights']['per_vertex'] for nm, _ in wv if nm not in joint_names}
    if unknown:
        out.append(f'weights on unknown joints {sorted(unknown)}')
    if not rec.get('set') or not rec.get('px_per_m'):
        out.append('a density with no set')
    return out


def band_length(rec, dr=0.0):
    """L_band = max(0.75 r, |dr|max / 0.25, two ring steps) (§2.7); the identity donor's |dr| is 0 (REROOT: a re-rooted
    donor passes its own |dr|max, the radius step from the ring's section to its root section)"""
    return max(0.75 * rec['r_mean'], float(dr) / 0.25, 2.0 * rec['h'])


# ============================================================================================ REROOT: any host's ring
# (REMIX_LIBRARY §7 rank 1; remix-machinery-r1) The octopus arm ring above is ONE host. Any host whose glb CARRIES its
# ring records (extras.bestiary.rings: the axolotl's 21, the human's 57, each written by the host's own export with
# ring_record's frozen bits: ax11_glb.py, the human's x10) goes through load_host + host_ring_record, which complete
# the stored record into the schema the rest of this module reads (the socket frame in the creature's space, the
# section, the seam vertex, the ring steps, the loops either side, the native group's triangles). The part itself is
# graft_tube's (below): the host's loops round the ring, a DONOR generator run in the socket frame at the host's scale
# and texel density, so every cross is the same code; M1a is (the octopus's loops, the octopus arm on its own ring, the
# identity map).
def load_host(glb_path, welded=None):
    """ANY host's shipped glb as the graft reads it: load_base's arrays without the octopus's low.npz (the skin
    primitives' shared vertex set: POSITION, NORMAL, TANGENT, TEXCOORD_0 in the forge's v-up convention, JOINTS_0,
    WEIGHTS_0; each primitive's triangles by material name; the skin's joint names and bind worlds by
    cyborg_octopus.Rig, three's composition), its records (extras.bestiary) and, when given, its WELDED topology:
    welded = dict(Q (q, 4) the welded quads, orig (n,) each of the first n shipped vertices' welded id) so the loops
    round a ring can be walked (tube_loops). The octopus keeps load_base (its low.npz is its welded topology)"""
    from . import cyborg_octopus as CO
    from . import gltf
    G = gltf.read(glb_path)
    j = G['json']
    acc = G['accessor']
    prims = j['meshes'][0]['primitives']
    mats = [m['name'] for m in j['materials']]
    p0 = prims[0]['attributes']
    assert all(p['attributes']['POSITION'] == p0['POSITION'] for p in prims), 'the host\'s primitives share no vertex set'
    uv = acc(p0['TEXCOORD_0']).astype(np.float64)
    out = dict(path=glb_path, sha1=sha1_file(glb_path), json=j, G=G,
               V32=acc(p0['POSITION']).copy(), N32=acc(p0['NORMAL']).copy(), T32=acc(p0['TANGENT']).copy(),
               UV=np.column_stack([uv[:, 0], 1.0 - uv[:, 1]]), J=acc(p0['JOINTS_0']).astype(np.int64),
               W32=acc(p0['WEIGHTS_0']).copy(), prims={}, mats=mats, records=j.get('extras', {}).get('bestiary', {}))
    for k, p in enumerate(prims):
        out['prims'][mats[p['material']]] = dict(index=k, F=acc(p['indices']).reshape(-1, 3).astype(np.int64),
                                                 attrs=dict(p['attributes']), material=p['material'],
                                                 targets=len(p.get('targets', [])))
    rig = CO.Rig(glb_path)
    out['rig'] = rig
    out['jnames'] = list(rig.jnames)
    out['world'] = rig.worlds()
    if welded is not None:
        orig = np.asarray(welded['orig'], np.int64)
        n = len(orig)
        assert n <= len(out['V32'])
        copies = {}
        for i, w in enumerate(orig.tolist()):
            if w >= 0:
                copies.setdefault(int(w), []).append(i)
        out['welded'] = dict(Q=np.asarray(welded['Q'], np.int64), orig=orig, n=n, copies=copies,
                             V=np.asarray(welded['V'], np.float64) if 'V' in welded else None)
        # the low as strip_base_corners reads the octopus's low.npz: the skin primitive's triangles, every shipped
        # vertex's welded id (-1 past the welded set: the separate pieces), the UVs (v up)
        og = -np.ones(len(out['V32']), np.int64)
        og[:n] = orig
        out['low'] = dict(F=out['prims'][mats[prims[0]['material']]]['F'], orig=og, UV=out['UV'],
                          V=out['V32'].astype(np.float64))
    return out


def native_tags(host):
    """the host's NATIVE GROUP TAGS per shipped vertex (ax11_glb.py's: extras.bestiary.native_tags, run-length pairs of
    32-bit words, bit k set when the vertex lies beyond ring sites[k]). Returns (sites, words (n,) uint32)"""
    nt = host['records'].get('native_tags')
    if nt is None:
        return None, None
    words = np.concatenate([np.full(int(c), int(v), np.uint32) for v, c in nt['rle']])
    assert len(words) == len(host['V32']), 'the native tags do not cover the vertex set'
    return list(nt['sites']), words


def tube_loops(Q, ring, distal, n_out, n_in):
    """THE TUBE'S LOOPS round a ring on a welded quad mesh (any host): ring (K welded ids, k order), distal a
    callable(ids (K,)) -> +1 on the native's side, -1 on the base's. Each next loop's vertex k is the one across the
    quad from the current loop's vertex k, on the side away from the loop before. Returns (loops_out (m, K) from the
    first loop past the ring, m <= n_out; loops_in (p, K) from the first loop before it, p <= n_in): a walk stops where
    the strip ends (an edge without exactly one quad on its far side, or a loop that is not K distinct new vertices:
    a pole, a K change, a cap)"""
    Q = np.asarray(Q, np.int64)
    ring = [int(v) for v in ring]
    K = len(ring)
    e2q = {}
    for qi, q in enumerate(Q.tolist()):
        for m in range(4):
            a, b = q[m], q[(m + 1) % 4]
            e2q.setdefault((min(a, b), max(a, b)), []).append(qi)

    def opposite(q, a, b):
        """quad q holds the edge (a, b): the corners across from a and from b"""
        ia, ib = q.index(a), q.index(b)
        pa = q[(ia + 2) % 4] if q[(ia + 1) % 4] == b or q[(ia - 1) % 4] == b else None
        # across from a: a's other neighbour in the quad (not b); across from b likewise
        na_ = q[(ia - 1) % 4] if q[(ia + 1) % 4] == b else q[(ia + 1) % 4]
        nb_ = q[(ib - 1) % 4] if q[(ib + 1) % 4] == a else q[(ib + 1) % 4]
        assert pa is not None
        return na_, nb_

    def step(cur, prev):
        """the loop past cur away from prev (a set of welded ids): per edge the one quad holding none of prev"""
        nxt = [None] * K
        for k in range(K):
            a, b = cur[k], cur[(k + 1) % K]
            cand = [Q[qi].tolist() for qi in e2q.get((min(a, b), max(a, b)), [])]
            cand = [q for q in cand if not (set(q) & prev)]
            if len(cand) != 1:
                return None
            pa, pb = opposite(cand[0], a, b)
            for kk, v in ((k, pa), ((k + 1) % K, pb)):
                if nxt[kk] is None:
                    nxt[kk] = v
                elif nxt[kk] != v:
                    return None
        if len(set(nxt)) != K or set(nxt) & set(cur) or set(nxt) & prev:
            return None
        return nxt

    def first_loop(q0):
        """the loop on the side of quad q0 (at ring edge 0), propagated round the ring quad by quad"""
        nxt = [None] * K
        q = q0
        for k in range(K):
            a, b = ring[k], ring[(k + 1) % K]
            if k > 0:
                cand = [Q[qi].tolist() for qi in e2q.get((min(a, b), max(a, b)), [])]
                cand = [c for c in cand if nxt[k] in c]
                if len(cand) != 1:
                    return None
                q = cand[0]
            pa, pb = opposite(q, a, b)
            if nxt[k] is not None and nxt[k] != pa:
                return None
            nxt[k] = pa
            if k + 1 < K:
                nxt[k + 1] = pb
            elif nxt[0] != pb:
                return None
        return nxt if len(set(nxt)) == K and not set(nxt) & set(ring) else None

    a0, b0 = ring[0], ring[1]
    q_sides = [Q[qi].tolist() for qi in e2q.get((min(a0, b0), max(a0, b0)), [])]
    assert len(q_sides) == 2, 'a ring edge without two quads: the ring is not inside a tube'
    cand = [first_loop(q) for q in q_sides]
    assert all(c is not None for c in cand), 'the ring\'s two sides are not both quad strips'
    sgn = [distal(np.asarray(c)) for c in cand]
    assert sorted(sgn) == [-1, 1], f'the side test does not tell the ring\'s two sides apart: {sgn}'
    first_out, first_in = (cand[0], cand[1]) if sgn[0] > 0 else (cand[1], cand[0])

    def walk(first, n):
        loops, prev, cur = [], set(ring), first
        while cur is not None and len(loops) < n:
            loops.append(cur)
            nxt = step(cur, prev)
            prev, cur = set(cur), nxt
        return np.array(loops, np.int64).reshape(-1, K)
    return walk(first_out, n_out), walk(first_in, n_in)


def frame_of_ring(V):
    """the socket frame of a STORED ring (its K frozen vertices in k order, the creature's space): origin the centroid,
    Z the axis about which the vertices turn counter-clockwise (the record's 'right-handed about +Z': the sum of the
    consecutive radii's cross products), X vertex 0's direction made normal to Z, Y = Z x X. Returns (origin, R)"""
    V = np.asarray(V, np.float64)
    c = V.mean(0)
    r = V - c
    z = np.cross(r, np.roll(r, -1, axis=0)).sum(0)
    z /= np.linalg.norm(z)
    x = r[0] - z * float(r[0] @ z)
    x /= np.linalg.norm(x)
    return c, np.column_stack([x, np.cross(z, x), z])


def host_ring_record(host, name, apron=3, n_native=64):
    """THE RING RECORD of a host whose glb carries it (load_host's records['rings'][name]), completed into ring_record's
    schema: the socket frame in the creature's space (frame_of_ring: Z checked DISTAL, toward the native group, and
    against the record's own joint-frame normal and tangent through the root's bind world), the section (fit_section:
    sdf.SWEEP's vocabulary, the per-vertex residual), seam_k (the ring vertices on the host's UV LENGTH seam: more split
    copies than the ring's own), the loops either side (tube_loops on the welded quads: `apron` before the ring, up to
    n_native past it), h and h_in (the ring steps), the slope, the base's density at the ring (the stored px_per_m:
    the host's one density, its set and size), the ring's share along its chain (st_s), and the native group's
    triangles per primitive (by the host's native tags: every corner tagged beyond the ring or a copy of a ring vertex,
    at least one tagged). Returns (rec, side): rec the completed record (JSON data), side the arrays graft_tube reads
    (loops of welded ids, apron first, the ring at index `apron`; the ring's copies split by side)"""
    src = host['records']['rings'][name]
    rec = json.loads(json.dumps(src))
    W = host['welded']
    copies = W['copies']
    K = int(rec['K'])
    low_k = [[int(v) for v in cp] for cp in rec['low_copies']]
    first = np.array([cp[0] for cp in low_k])
    V = host['V32'][first].astype(np.float64)
    assert np.array_equal(host['V32'][first].view(np.uint32), np.asarray(rec['verts_f32'], np.uint32)), \
        'the record\'s frozen positions are not the glb\'s'
    assert np.array_equal(host['N32'][first].view(np.uint32), np.asarray(rec['normals_f32'], np.uint32)), \
        'the record\'s frozen normals are not the glb\'s'
    ring_w = [int(W['orig'][v]) for v in first]
    for k, cp in enumerate(low_k):
        assert all(int(W['orig'][v]) == ring_w[k] for v in cp), 'a ring copy on another welded vertex'
    sites, words = native_tags(host)
    bit = np.uint32(1 << sites.index(name))
    tagged = (words & bit) != 0
    O_, R_ = frame_of_ring(V)
    # Z distal: the native's tagged welded vertices lie on +Z
    tw = np.unique(W['orig'][:W['n']][tagged[:W['n']]])
    tw = tw[tw >= 0]
    Vw = W['V'] if W['V'] is not None else None
    if Vw is None:
        Vw = np.zeros((int(W['orig'].max()) + 1, 3))
        Vw[W['orig'][:W['n']]] = host['V32'][:W['n']].astype(np.float64)
    zt = (Vw[tw] - O_) @ R_[:, 2]
    hand = 'right-handed about +Z'
    if np.median(zt) < 0:
        # the record's vertices turn the other way about the distal axis (an R site: left-handed by the plan's rule)
        hand = 'left-handed about +Z'
        x = R_[:, 0]
        z = -R_[:, 2]
        R_ = np.column_stack([x, np.cross(z, x), z])
    # the stored frame (joint-local normal / tangent) against it
    Wr = host['world'][host['rig'].index[rec['root']]]
    n_st = Wr[:3, :3] @ np.asarray(rec['frame']['normal'], np.float64)
    t_st = Wr[:3, :3] @ np.asarray(rec['frame']['tangent'], np.float64)
    ang_n = float(np.degrees(np.arccos(min(1.0, abs(float(n_st @ R_[:, 2]) / np.linalg.norm(n_st))))))
    ang_t = float(np.degrees(np.arccos(np.clip(float(t_st @ R_[:, 0]) / np.linalg.norm(t_st), -1.0, 1.0))))
    o_st = (Wr @ np.append(np.asarray(rec['origin'], np.float64), 1.0))[:3]
    # the loops: the first loop past the ring is the one on the native's (tagged) side
    def side(ids):
        z = (Vw[np.asarray(ids)] - O_) @ R_[:, 2]
        return 1 if float(np.median(z)) > 0 else -1
    lo, li = tube_loops(W['Q'], ring_w, side, n_native, apron)
    assert len(li) == apron, f'{name}: {len(li)} loops before the ring, the apron asks {apron}'
    loops = np.concatenate([li[::-1], np.array([ring_w]), lo])
    pos = lambda ids: host['V32'][[copies[int(c)][0] for c in ids]].astype(np.float64)    # noqa: E731
    loc = (V - O_) @ R_
    theta_std = TAU * np.arange(K) / K
    theta_got = np.arctan2(loc[:, 1], loc[:, 0])
    if hand.startswith('left'):
        theta_got = -theta_got
    dth = (theta_got - theta_std + math.pi) % TAU - math.pi
    rho = np.hypot(loc[:, 0], loc[:, 1])
    sec, res = fit_section(rho, theta_std)
    nxt, prv = pos(lo[0]), pos(li[0])
    h = float(np.linalg.norm(nxt.mean(0) - V.mean(0)))
    h_in = float(np.linalg.norm(prv.mean(0) - V.mean(0)))
    On, _ = frame_of_ring(nxt)
    loc_n = (nxt - On) @ R_
    sec_n, _ = fit_section(np.hypot(loc_n[:, 0], loc_n[:, 1]), theta_std)
    dz = float(np.dot(On - O_, R_[:, 2]))
    # the length seam: ring vertices with more copies than the ring's own split (a ring on an island boundary has two)
    ncp = np.array([len(cp) for cp in low_k])
    seam = [int(k) for k in np.nonzero(ncp > np.median(ncp))[0]]
    # each ring vertex's copies by side: the native's (used by a native triangle) and the base's
    F0 = host['prims'][host['mats'][0]]['F']
    nat_tri = {}
    for mname, p in host['prims'].items():
        F = p['F']
        ring_copy = np.zeros(len(host['V32']), bool)
        ring_copy[np.concatenate(low_k)] = True
        on = (tagged[F] | ring_copy[F]).all(1) & tagged[F].any(1)
        nat_tri[mname] = np.nonzero(on)[0]
    distal_copies, base_copies = [], []
    used_nat = np.zeros(len(host['V32']), bool)
    used_nat[F0[nat_tri[host['mats'][0]]].ravel()] = True
    used_kept = np.zeros(len(host['V32']), bool)
    keep0 = np.ones(len(F0), bool)
    keep0[nat_tri[host['mats'][0]]] = False
    used_kept[F0[keep0].ravel()] = True
    for cp in low_k:
        distal_copies.append([v for v in cp if used_nat[v] and not used_kept[v]])
        base_copies.append([v for v in cp if used_kept[v]])
    # the chain and the cut this ring is listed at, and its share
    chain = next((c for c in host['records'].get('chains', []) for ct in c.get('cuts', []) if ct.get('ring') == name),
                 None)
    cut = next((ct for ct in (chain or {}).get('cuts', []) if ct.get('ring') == name), None)
    rec.update(handedness=hand, chain=chain['name'] if chain else None, cut=int(cut['joint']) if cut else None,
               ring_index=int(apron), apron_rings=int(apron),
               frame=dict(rec['frame'], creature=dict(origin=O_.tolist(), R=R_.tolist()),
                          check=dict(normal_deg=ang_n, tangent_deg=ang_t,
                                     origin_mm=float(np.linalg.norm(o_st - O_) * 1e3))),
               section=sec, section_residual=res.tolist(), slope=dict(dr0_dz=(sec_n['r0'] - sec['r0']) / dz, dz=dz),
               h=h, h_in=h_in, seam_k=seam, theta_dev_deg=np.degrees(dth).tolist(),
               st_s=float(cut['s']) if cut else None, cut_s=float(cut['s']) if cut else None,
               px_set=float(rec['px_per_m']), build=host['sha1'])
    rec['native'] = dict(rec['native'], faces_prim={m: t.tolist() for m, t in nat_tri.items()},
                         primitive=host['mats'][0])
    side_ = dict(loops=loops, rings={i: loops[i] for i in range(len(loops))}, ic=int(apron), i_last=len(loops) - 1,
                 copies=copies, distal_copies=distal_copies, base_copies=base_copies, tagged=tagged, ring_w=ring_w)
    return rec, side_


# ============================================================================================ the generator
class FramedSDF:
    """a donor's SDF program placed in the socket's frame, x_world = R x_donor + t (R orthonormal): eval, normals and
    project as retopo.fit calls them. R = I, t = 0 reproduces the program's own arithmetic bit for bit"""

    def __init__(self, prog, R=None, t=None):
        self.prog = prog
        self.R = np.eye(3) if R is None else np.asarray(R, np.float64)
        self.t = np.zeros(3) if t is None else np.asarray(t, np.float64)

    def _in(self, X):
        return (np.asarray(X, np.float64) - self.t) @ self.R

    def eval(self, X):
        return self.prog.eval(self._in(X))

    def normals(self, X):
        return self.prog.normals(self._in(X)) @ self.R.T

    def project(self, X, dirs, maxd=0.05):
        q, st = self.prog.project(self._in(X), np.asarray(dirs, np.float64) @ self.R, maxd=maxd)
        return np.asarray(q, np.float64) @ self.R.T + self.t, st


def socket_map(rec, donor_arm, donor_s):
    """the re-rooting (§3.4 step 4): the rigid map taking the donor's frame at its matching share onto the base's ring
    frame: (R, t) with x_world = R x_donor + t. On its own arm at its own cut (M1a) it is the identity"""
    O_b = np.asarray(rec['frame']['creature']['origin'])
    R_b = np.asarray(rec['frame']['creature']['R'])
    O_d, R_d = ring_frame(donor_arm, donor_s)
    R = R_b @ R_d.T
    return R, O_b - R @ O_d


def octopus_arm_rings(donor_arm, spec, stations, R=None, t=None, n_k=16, out=1.05, shift=0):
    """the octopus arm's ring PROXIES (octopus.build_cage's arm loop, extracted): at each station s the 16 vertices
    c + 1.05 r(s) (cos a n + sin a b), a = -90 deg + k 22.5 deg, carried into the socket frame. Returns (m, 16, 3).
    (REROOT) shift: the part's vertex k takes the arm's vertex (k + shift) mod 16, so the arm's oral midline (its
    vertex 12) lies on the host's hidden line; 0 on its own ring"""
    from .species import octopus as O
    R = np.eye(3) if R is None else R
    t = np.zeros(3) if t is None else t
    alphas = np.radians(-90.0 + ((np.arange(n_k) + int(shift)) % n_k) * (360.0 / n_k))
    rings = []
    for s in stations:
        P, n, b, _ = arm_frame_at(donor_arm, s)
        ra = O.arm_radius(np.array([s]), spec)[0]
        ring = np.array([P + out * ra * (np.cos(a) * n + np.sin(a) * b) for a in alphas])
        rings.append(ring @ R.T + t)
    return np.array(rings)


# the octopus arm's section law (octopus.build_sdf's arm SWEEP: "rounder aboral, flatter oral") and its cage's ring step
# in share (the canonical cage: 65 rings over s 0.3347 .. 0.9973, p02_cage.npz)
ARM_SECTION = dict(a2=0.06, phi2=0.0, a3=0.05, phi3=0.0, aspect=0.92)
ARM_RING_DS = 0.0103547
ARM_CUT8_S = 0.5003959804030899      # the canonical's cut-8 ring share (M1a's ring record st_s): where the part starts
ARM_CUT8_R = 0.017288115237625894    # its mean radius there (M1a's r_mean): the scale reference for a re-rooted arm


class OctopusArm:
    """THE OCTOPUS ARM AS A DONOR (CROSSBREED §0 item 2, R21: octopus.build_cage's arm loop and build_sdf's arm SWEEP,
    made standalone and re-rooted). Two ways to run it:
      own(arm, spec, prog_low, rec)   on ITS OWN RING (M1a): the canonical's arm (its centreline and rotation-minimising
                                      frame), the whole low program, the identity socket map; the part's rings are the
                                      native cage's own (native=True: its stations, its quads, its cap ids)
      rerooted(host, rec, side, ...)  at ANY HOST'S RING: one SWEEP of the arm's own section law (ARM_SECTION) and
                                      taper (octopus.arm_radius through _ARM_TAPER) along a centreline laid in the host's
                                      creature frame: straight behind the ring along -Z (the arm's proximal part, inside
                                      the host, only so the sweep and the fit's support rings have it), from the ring's
                                      origin along the native's own axis (the native loops' centroids past the ring,
                                      then the host chain's joints past the root, then on along the last direction);
                                      its sections by the RING (scale s_c: the ring's mean radius over the octopus's
                                      own at cut 8, ARM_CUT8_R) and its length by the HOST (the part from the ring to the
                                      tip `share` x the native's length past the ring: M2c's rule, R11), the arm's
                                      share s0 = ARM_CUT8_S at the ring; its aboral side on the host's side opposite the
                                      ring's hidden line (rec['seam_k']), so its oral midline (the suckers' rows, the
                                      arm's UV seam, its vertex 12) lies on the host's hidden line
    Members: arm (P, n, b, t over the donor's whole arm, sampled evenly in share), spec (its arm_radius law), prog (the
    field the low is fitted to), R / t (the socket map: identity for both, the re-rooted arm is built in place),
    s0, shift (octopus_arm_rings'), native, scale (s_c), length (the part's, m), L_arm (the whole donor arm's)"""

    def __init__(self, arm, spec, prog, R, t, s0, shift=0, native=False, scale=1.0, length=None, L_arm=None,
                 info=None):
        self.arm, self.spec, self.prog, self.R, self.t = arm, spec, prog, R, t
        self.s0, self.shift, self.native, self.scale = float(s0), int(shift), bool(native), float(scale)
        self.length, self.L_arm, self.info = length, L_arm, info or {}

    @classmethod
    def own(cls, arm, spec, prog_low, rec):
        R, t = socket_map(rec, arm, rec['st_s'])
        assert np.abs(R - np.eye(3)).max() < 1e-12 and np.abs(t).max() < 1e-12, \
            'M1a grafts the arm onto its own ring: the socket map must be the identity'
        return cls(arm, spec, prog_low, R, t, rec['st_s'], native=True)

    @classmethod
    def rerooted(cls, host, rec, side, spec, share=1.0, count=257, back=None, tip_axis=None, log=print, z0=0.0,
                 lam=None):
        """the re-rooted arm at the host's ring (the class docstring). side: host_ring_record's (its native loops);
        share: the part's length over the native's past the ring; back: the straight proximal run (m; default the arm's
        own length up to s0 at its section scale). z0: the arc past the ring where the arm's s0 (its cut-8 share) lies
        (0: at the ring, the WELD arm; the C5 mech tentacle's flesh: at the band's end, where its flange grips the
        octopus's own section). lam: the arm's length over the octopus's own at its section scale instead of `share`
        (a MACHINE on the arm keeps its proportions: C5's flange stack needs room between its ring and joint 8)"""
        from . import loft
        from . import sdf as SD
        from .species import octopus as O
        O_ = np.asarray(rec['frame']['creature']['origin'], np.float64)
        R_ = np.asarray(rec['frame']['creature']['R'], np.float64)
        X, Y, Z = R_[:, 0], R_[:, 1], R_[:, 2]
        K = int(rec['K'])
        s_c = float(rec['r_mean']) / ARM_CUT8_R
        # the native's axis past the ring: its loops' centroids, then the host chain's joints past the root and the tip
        W = host['welded']
        pos = lambda ids: host['V32'][[W['copies'][int(c)][0] for c in ids]].astype(np.float64)     # noqa: E731
        cents = [pos(l).mean(0) for l in side['loops'][side['ic'] + 1:]]
        ch = next(c for c in host['records']['chains'] if c['name'] == rec['chain'])
        jw = {nm: host['world'][host['rig'].index[nm]][:3, 3] for nm in ch['joints']}
        k_root = ch['joints'].index(rec['root'])
        tail = [jw[nm] for nm in ch['joints'][k_root + 1:]]
        tip_nm = ch.get('tip')
        if tip_nm and tip_nm in host['rig'].index:
            tail.append(host['world'][host['rig'].index[tip_nm]][:3, 3])
        z_last = float((cents[-1] - O_) @ Z)
        tail = [p for p in tail if float((p - O_) @ Z) > z_last + 1e-4]
        # (the chain's joints lie on the bone axis, off the skin loops' centroids: at the switch from the last loop's
        # centroid to the next joint the arm kinked, LOOKED in rr_ax2_clay 2.5; so past the loops only the chain's last
        # point, the tip, is kept, and the axis is smoothed, its first point and tangent held)
        tail = tail[-1:]
        nat = np.array([O_] + cents + tail)
        for _ in range(8):
            sm = nat.copy()
            sm[2:-1] = 0.25 * nat[1:-2] + 0.5 * nat[2:-1] + 0.25 * nat[3:]
            nat = sm
        L_nat = float(np.linalg.norm(np.diff(nat, axis=0), axis=1).sum())
        L_part = float(share) * L_nat
        if lam is not None:
            L_part = float(z0) + (1.0 - ARM_CUT8_S) * float(lam) * s_c * float(spec['arm_len'])
            share = L_part / L_nat
        # the donor's whole arm: L_d from s = 0 so the part s0 .. 1 is L_part (s0 at z0 past the ring); its proximal run
        # straight behind the ring
        L_d = (L_part - float(z0)) / (1.0 - ARM_CUT8_S)
        back = ARM_CUT8_S * L_d - float(z0) if back is None else float(back)
        path = nat.copy()
        if L_part > L_nat:                               # longer than the native: on along the native's last direction
            d_end = tip_axis if tip_axis is not None else _unit3(nat[-1] - nat[-2])
            path = np.vstack([path, nat[-1] + d_end * (L_part - L_nat)])
        seg = np.linalg.norm(np.diff(path, axis=0), axis=1)
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        if L_part < L_nat:                               # shorter: cut the native's axis at L_part
            k = int(np.searchsorted(cum, L_part))
            f = (L_part - cum[k - 1]) / max(seg[k - 1], 1e-12)
            path = np.vstack([path[:k], path[k - 1] + f * (path[k] - path[k - 1])])
        ctrl = np.vstack([O_ - Z * back, path])
        # (the control polyline made EVEN before the Catmull-Rom resample: through the 200 mm back run's one segment and
        # the native's 10 mm steps the uniform spline overshot past the ring by ~17 mm, so the arm's s0 sat behind it)
        cl = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(ctrl, axis=0), axis=1))])
        ue = np.linspace(0.0, cl[-1], max(int(cl[-1] / 0.002) + 1, 8))
        P = loft.resample(np.column_stack([np.interp(ue, cl, ctrl[:, k]) for k in range(3)]), count)
        # shares evenly along the arc: the ring's point at s0 (the resampling's arc share there is back / (back + L))
        arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
        sP = arc / L_d                                   # (the share even in arc: s0 at z0 past the ring, 1 at the tip)
        sa = np.linspace(0.0, 1.0, count)
        P = np.column_stack([np.interp(sa, sP, P[:, k]) for k in range(3)])
        # the aboral reference: opposite the ring's hidden line (the host's seam vertex's direction)
        seam = int(rec['seam_k'][0])
        th = TAU * seam / K
        hidden = np.cos(th) * X + np.sin(th) * Y
        n, b, t = loft.rmf(P, ref=-hidden)
        spec_d = dict(spec, arm_r0=spec['arm_r0'] * s_c, arm_tip_r=spec['arm_tip_r'] * s_c,
                      sucker_d=spec['sucker_d'] * s_c, arm_len=L_d, arm_pair_len=[1.0, 1.0, 1.0, 1.0])
        prog = SD.Program()
        prog.sweep(P, n, O.arm_radius(sa, spec_d), op=SD.UNION, name='octopus arm (re-rooted)', **ARM_SECTION)
        # the part's vertex k on the arm's alpha: the arm's oral midline (its vertex 12, a = +90 deg... the cage's
        # alpha -90 + 22.5 k: vertex 12 at 180 deg from n, the oral side) onto the host's seam vertex
        shift = (12 - seam) % K
        arm = (P, n, b, t)
        info = dict(s_c=s_c, L_native=L_nat, L_part=L_part, L_arm=L_d, back=back, share=float(share), seam_k=seam,
                    lam=L_d / (s_c * float(spec['arm_len'])), shift=shift, z0=float(z0))
        log(f'[graft reroot] the octopus arm at {rec.get("name", "?")}: sections x{s_c:.4f} by the ring (r mean '
            f'{rec["r_mean"] * 1e3:.2f} mm over the octopus\'s {ARM_CUT8_R * 1e3:.2f} at cut 8), the part '
            f'{L_part * 1e3:.1f} mm = {share:.2f} x the native\'s {L_nat * 1e3:.1f} mm (the whole donor arm '
            f'{L_d * 1e3:.1f} mm: lam {info["lam"]:.4f} of the octopus\'s at its section scale), its oral midline on '
            f'the host\'s seam vertex {seam} (shift {shift})')
        return cls(arm, spec_d, prog, np.eye(3), np.zeros(3), ARM_CUT8_S, shift=shift, native=False, scale=s_c,
                   length=L_part, L_arm=L_d, info=info)

    def s_at(self, z):
        """the arm's share at arc length z past the ring along its centreline (the re-rooted arm: linear; s0 at z0)"""
        z0 = float(self.info.get('z0', 0.0))
        return self.s0 + (np.asarray(z, np.float64) - z0) / self.L_arm if self.L_arm else \
            self.s0 + (1.0 - self.s0) * np.asarray(z, np.float64) / self.length

    def rings(self, stations, out=1.05):
        return octopus_arm_rings(self.arm, self.spec, stations, self.R, self.t, out=out, shift=self.shift)

    def field(self):
        return FramedSDF(self.prog, self.R, self.t)

    def tip_axis(self):
        _, _, _, ta = arm_frame_at(self.arm, 0.999)
        return self.R @ ta

    def section_radius(self, s, theta):
        """the arm's SWEEP radius at share s and the part's frame angle theta (the angle of the part's vertex index
        theta K / 2 pi: alpha = -90 deg + (theta K / 2 pi + shift) 22.5 deg from n toward b): sd_sweep's profile,
        r0 (1 + a2 cos 2 al + a3 cos 3 al) aspect / sqrt(aspect^2 cos^2 al + sin^2 al), al from n"""
        from .species import octopus as O
        al = np.asarray(theta, np.float64) - math.pi / 2.0 + TAU * self.shift / 16.0
        r = 1.0 + ARM_SECTION['a2'] * np.cos(2.0 * al) + ARM_SECTION['a3'] * np.cos(3.0 * al)
        a = ARM_SECTION['aspect']
        return O.arm_radius(np.asarray(s, np.float64), self.spec) * r * a / np.sqrt(a * a * np.cos(al) ** 2 +
                                                                                    np.sin(al) ** 2)


def _unit3(v):
    v = np.asarray(v, np.float64)
    return v / max(float(np.linalg.norm(v)), 1e-300)


# ============================================================================================ the part's cage
def octopus_side(base, cage, rec):
    """the OCTOPUS'S side of a ring for graft_tube (its cage is its welded topology): the arm's rings by cage ring
    number (cage['rings'], the ring at rec['ring_index']), the native's own quads (q_arm) and tip cap ids, its ring
    stations (ring_s), the anatomical coordinate st per cage id, every cage id's low copies"""
    L = base['low']
    copies = {}
    for i in range(base['n_low']):
        copies.setdefault(int(L['orig'][i]), []).append(i)
    return dict(rings={i: np.asarray(r) for i, r in enumerate(cage['rings'])}, ic=int(rec['ring_index']),
                i_last=len(cage['rings']) - 1, copies=copies, st=cage['st'], ring_k=np.asarray(cage['ring_k']),
                native=dict(Q=cage['q_arm'], cap_v=np.asarray(cage['cap_v']), ring_s=cage['ring_s']))


def part_cage(base, cage, rec, arms, spec, prog_low, mode='generate', fit_iters=6, log=print):
    """M1a / M0 on the octopus: graft_tube on the octopus's side of its own arm ring (octopus_side) with the octopus
    arm on its own ring (OctopusArm.own: the identity socket map, the native cage's stations, quads and cap)"""
    donor = OctopusArm.own(arms[cage['order'][int(rec['chain'][3:])]], spec, prog_low, rec)
    return graft_tube(base, octopus_side(base, cage, rec), rec, donor, mode=mode, fit_iters=fit_iters, log=log)


def band_ramp(z, z0, z1):
    """the BAND's donor weight w(z): 0 over the collar (z <= z0: the native's own first loop, §2.3), a C1 smoothstep to 1
    at z1 (zero slope at both ends: its steepest slope 1.5 x its mean, so the band's length is set by 1.5 |dr| / 0.25,
    graft_socket.collar's rule)"""
    u = np.clip((np.asarray(z, np.float64) - z0) / max(z1 - z0, 1e-12), 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


# (CROSS 11-10, the lead's call (e): AX-X2's skin change read as "an even, straight gradient about 10 mm wide": the band wore
# `morph`, the only dressing with code) CROSSBREED §2.10's DESIGNED BOUNDARY on a WELD band. `fold`: a transverse skin fold at
# z_f in [0.35, 0.6] of the band (as at a wrist or neck crease), relief 1-3 mm, the boundary on its crest; its line wanders
# round the limb (low harmonics, a crease is never a machined ring). `margin`: the boundary along the DONOR's own cell network
# (the octopus skin's patch cells: its masks pack's A, 'patch random'): w steps cell by cell, so the donor's skin starts as
# whole cells; structure places the edge, noise only shapes it. `fold+margin` (the default for a soft weld across species): the
# fold's crest line, the donor's whole cells starting along it. Metres at the creature's authored scale
DRESSING = dict(fold_share=0.45,        # z_f's share of the band, from the collar loop to the band's end (§2.10: 0.35-0.6)
                fold_wander=0.16,       # the crest line's wander along the axis round the limb (share of the band)
                fold_relief=0.0013,     # the fold's height (§2.10: 1-3 mm)
                fold_width=0.0019,      # its crest's half-width (the bulge's Gaussian sigma)
                crease=0.35,            # the groove on the crest's distal side, where the donor's skin tucks under (share of
                                        # the relief), its centre and width in fold widths
                crease_at=0.95, crease_w=0.42,
                cell_jitter=1.6,        # a cell's own offset from the crest line, in cell sizes (the dentate edge: at 0.55
                                        # the first look read a clean ring, the teeth a cell deep, too fine at the close-up)
                edge_px=0.8,            # the class edge's softness between whole cells (texels: a filtered step)
                seed=11)


def cells_from_pack(A, cov, min_size=6):
    """the donor's CELL NETWORK from a per-cell random pack channel (the octopus skin's masks A, 'patch random': one value per
    patch cell): each connected region of one value inside cov, labelled; the filtered SLIVERS along the cells' borders (on
    AX-X2's band: half the labels a single texel, 10 % of the texels, their values between two cells') joined to the nearest
    whole cell (regions of min_size texels and more). Returns (labels (-1 outside), n)"""
    from scipy import ndimage
    A = np.asarray(A)
    lab = -np.ones(A.shape, np.int64)
    n = 0
    for v in np.unique(A[cov]):
        l_, k_ = ndimage.label((A == v) & cov)
        m = l_ > 0
        lab[m] = l_[m] - 1 + n
        n += int(k_)
    cnt = np.bincount(lab[cov], minlength=n)
    big = cov & (cnt[np.maximum(lab, 0)] >= min_size)
    if big.any() and (cov & ~big).any():
        _, (iy, ix) = ndimage.distance_transform_edt(~big, return_indices=True)
        sl = cov & ~big
        lab[sl] = lab[iy[sl], ix[sl]]
    u_, inv = np.unique(lab[cov], return_inverse=True)        # (the kept cells numbered 0 .. n - 1)
    lab[cov] = inv
    return lab, int(len(u_))


def band_dressing(kind, z, theta, z0, L_band, cells=None, opts=None):
    """CROSSBREED §2.10's dressing on a WELD band (block comment above), per sample (texels or vertices): z its station along
    the ring's axis, theta its angle round it, z0 / L_band the collar loop's station and the band's end, cells the donor's cell
    labels there (cells_from_pack; -1: none). kind 'morph' (band_ramp, as before), 'fold', 'margin' or 'fold+margin'. Returns
    dict(w (the donor's class weight: the material's mix and the graft pack's R), h (the fold's relief, m: the high's / the
    normal map's), crease (0..1: the groove's depth share, for the AO and the albedo), mask (the dressing mask: the graft pack's
    G), z_f (the crest line's station at each sample))"""
    from .graft_socket import cuff_wave
    o = dict(DRESSING, **(opts or {}))
    z = np.asarray(z, np.float64)
    theta = np.asarray(theta, np.float64)
    if kind == 'morph':
        w = band_ramp(z, z0, L_band)
        return dict(w=w, h=np.zeros_like(z), crease=np.zeros_like(z), mask=np.zeros_like(z), z_f=np.full_like(z, np.nan))
    Lb = max(float(L_band) - float(z0), 1e-9)
    z_f = z0 + Lb * (o['fold_share'] + o['fold_wander'] * cuff_wave(theta, o['seed'], n=3))
    d = z - z_f
    h, crease, mask = np.zeros_like(z), np.zeros_like(z), np.zeros_like(z)
    if 'fold' in kind:
        s_ = o['fold_width']
        bulge = np.exp(-(d / s_) ** 2)
        groove = np.exp(-((d - o['crease_at'] * s_) / (o['crease_w'] * s_)) ** 2)
        h = o['fold_relief'] * (bulge - o['crease'] * groove)
        crease = groove
        mask = np.clip(bulge + groove, 0.0, 1.0)
    if 'margin' in kind and cells is not None:
        cells = np.asarray(cells, np.int64)
        on = cells >= 0
        w = (d > 0).astype(np.float64)
        if on.any():
            ids = cells[on]
            n = int(ids.max()) + 1
            cnt = np.bincount(ids, minlength=n).astype(np.float64)
            zc = np.bincount(ids, z[on], minlength=n) / np.maximum(cnt, 1)
            cz = np.bincount(ids, np.cos(theta[on]), minlength=n)
            sz = np.bincount(ids, np.sin(theta[on]), minlength=n)
            thc = np.arctan2(sz, cz)
            # a cell's size along the axis: its z extent's spread (a disc's sd is r / 2)
            zz = np.bincount(ids, z[on] ** 2, minlength=n) / np.maximum(cnt, 1)
            size = 4.0 * np.sqrt(np.maximum(zz - zc ** 2, 0.0))
            u_ = np.random.default_rng(o['seed']).uniform(-1.0, 1.0, n)
            zf_c = z0 + Lb * (o['fold_share'] + o['fold_wander'] * cuff_wave(thc, o['seed'], n=3))
            donor_c = (zc - zf_c) > o['cell_jitter'] * u_ * size
            w[on] = donor_c[ids].astype(np.float64)
        return dict(w=w, h=h, crease=crease, mask=np.maximum(mask, 0.0), z_f=z_f)
    # a fold alone: the boundary on its crest, a narrow C1 step there (a few texels at the band's density)
    w = band_ramp(d, -0.5 * o['fold_width'], 0.5 * o['fold_width'])
    return dict(w=w, h=h, crease=crease, mask=mask, z_f=z_f)


def graft_tube(host, side, rec, donor, mode='generate', fit_iters=6, log=print, band_only=False):
    """THE PART'S QUAD CAGE at ANY host's ring (CROSSBREED §2.7; REROOT's general path), from the apron to the tip cap:
      the APRON   the host's loops before the ring (baked and painted for context, never shipped)
      THE RING    frozen bits
      the BAND    the native continued past the ring MORPHED into the donor: the native loop at z (its own frozen
                  bits) and the donor's surface at the same z and angle (the donor's field, projected along the ring
                  plane's radii), mixed by band_ramp: w = 0 over the collar (the native's first loop, FIXED), 1 at
                  L_band = h + 1.5 |dr|max / 0.25 (|dr| the radius step from the ring's section to the donor's at the
                  ring); the vertex angles morph from the native's to the donor's own (each part vertex k at the
                  standard angle 2 pi k / K: octopus_arm_rings' shift), so the donor's rings past the band continue
                  them. The IDENTITY donor (donor.native: M1a) has w = 0 over the whole band: the band is the native's
                  loops, L_band / h of them, all fixed
      the DONOR   its rings past the band at its own stations (the identity donor: the native cage's ring_s, ring for
                  ring), then its tip cap (loft.cap over the last ring's proxies, dome 0.8 mm x the donor's scale along
                  its tip axis), fitted by retopo.fit to the donor's field in the socket frame from SUPPORT rings behind
                  the first one (the donor's own proxies, the farthest fixed; dropped after the fit)
    The quads: the native's own on the identity (the gates compare quad for quad), else ring to ring in the host's
    winding, the cap's grid. host: load_base / load_host's arrays; side: octopus_side / host_ring_record's (rings by
    ring number, copies, the native's topology on the octopus); donor: OctopusArm. Returns the part's dict (V, Q,
    cage_ids (host ids; -1 for designed or donor vertices), ring_no, is_cap, st, fixed, i0, ic, nb, i_last, base_pos
    (the host's position where the vertex is a host id, else nan), mode, fit, copies, rings (each ring's part
    vertices, k order), z (each ring's station along Z), w (each ring's donor weight), L_band)"""
    from . import loft, retopo
    from .mesh import QuadMesh
    rings = side['rings']
    ic, apron = int(rec['ring_index']), int(rec['apron_rings'])
    i0 = ic - apron
    copies = side['copies']
    K = int(rec['K'])
    O_ = np.asarray(rec['frame']['creature']['origin'], np.float64)
    R_ = np.asarray(rec['frame']['creature']['R'], np.float64)
    pos_of = lambda ids: np.array([host['V32'][copies[int(c)][0]] for c in ids]).astype(np.float64)   # noqa: E731
    fit_stats = None
    if donor.native:
        # ---------------------------------------------------------- the identity: the native's rings, quads and cap
        nat = side['native']
        nb = int(round(band_length(rec) / rec['h']))
        i_last = int(side['i_last'])
        cage_ids = np.concatenate([np.asarray(rings[i]) for i in range(i0, i_last + 1)] + [np.asarray(nat['cap_v'])])
        local = {int(c): k for k, c in enumerate(cage_ids)}
        Q = np.array([[local[int(v)] for v in q] for q in nat['Q'] if all(int(v) in local for v in q)])
        ring_no = np.full(len(cage_ids), -1)
        for i in range(i0, i_last + 1):
            for c in rings[i]:
                ring_no[local[int(c)]] = i
        is_cap = ring_no < 0
        base_pos = np.array([host['V32'][copies[int(c)][0]] for c in cage_ids]).astype(np.float64)
        st = side['st'][cage_ids]
        fixed = (ring_no >= 0) & (ring_no <= ic + nb)
        V = base_pos.copy()
        if mode == 'generate':
            gen = [i for i in range(ic + nb + 1, i_last + 1)]
            # the generator runs from SUPPORT rings behind its root (the donor's own proxies, the farthest one fixed),
            # so retopo.fit's relaxation, which reaches one ring per round, meets the donor's first kept ring in its
            # native context: fixed at the band's final bits instead, the ring beside it took a different relaxation
            # target (153 um off the native on the CPU dry run); the support rings are dropped after the fit
            n_sup = fit_iters + 1
            sup = list(range(gen[0] - n_sup, gen[0]))
            allr = sup + gen
            stations = [float(nat['ring_s'][i]) for i in allr]
            P = donor.rings(stations)
            ids = np.concatenate([np.asarray(rings[i]) for i in allr] + [np.asarray(nat['cap_v'])])
            lf = {int(c): k for k, c in enumerate(ids)}
            Vf = np.zeros((len(ids), 3))
            for i, ring in zip(allr, P):
                for k, c in enumerate(rings[i]):
                    Vf[lf[int(c)]] = ring[k]
            Qf = np.array([[lf[int(v)] for v in q] for q in nat['Q'] if all(int(v) in lf for v in q)])
            # the tip cap over the last ring's PROXIES (build_cage caps before the fit), its axis the tip's tangent
            nr = len(ids) - len(nat['cap_v'])
            tmp = QuadMesh(Vf[:nr].copy(), Qf[:0], {})
            last = np.array([lf[int(c)] for c in rings[i_last]])
            capped, grid = loft.cap(tmp, last, donor.tip_axis(), dome=0.0008 * donor.scale)
            new = capped.V[nr:]
            assert len(new) == len(nat['cap_v']), (len(new), len(nat['cap_v']))
            Vf[nr:] = new                        # (creation order = the cage's cap ids' order: sorted ascending)
            fx = np.zeros(len(ids), bool)
            fx[[lf[int(c)] for c in rings[sup[0]]]] = True
            mesh = QuadMesh(Vf, Qf, {})
            stat, acc = retopo.fit(mesh, donor.field(), iters=fit_iters, relax=0.5, fixed=fx)
            for c in np.concatenate([np.asarray(rings[i]) for i in gen] + [np.asarray(nat['cap_v'])]):
                V[local[int(c)]] = mesh.V[lf[int(c)]]
            fit_stats = dict(status=stat.tolist(), accepted=[round(a, 4) for a in acc], support=[sup[0], sup[-1]])
            d = np.linalg.norm(V - base_pos, axis=1)
            gm = ~fixed
            log(f'[graft] generated {len(gen)} rings + the cap by the octopus arm generator (identity socket map; '
                f'support rings {sup[0]}..{sup[-1]}), fitted: {fit_stats}; against the native low: max '
                f'{d[gm].max() * 1e6:.2f} um, p99 {np.percentile(d[gm], 99) * 1e6:.2f} um, median '
                f'{np.median(d[gm]) * 1e6:.3f} um')
        ring_list = [np.nonzero(ring_no == i)[0] for i in range(i0, i_last + 1)]     # (cage_ids holds each ring in k order)
        z_r = np.array([float((pos_of(rings[i]).mean(0) - O_) @ R_[:, 2]) for i in range(i0, i_last + 1)])
        return dict(V=V, Q=Q, cage_ids=cage_ids, ring_no=ring_no, is_cap=is_cap, st=st, fixed=fixed, i0=i0, ic=ic,
                    nb=nb, i_last=i_last, base_pos=base_pos, mode=mode, fit=fit_stats, copies=copies, rings=ring_list,
                    z=z_r, w=np.zeros(len(z_r)), L_band=float(band_length(rec)), K=K)
    # -------------------------------------------------------------- a re-rooted donor on a host's ring
    assert mode == 'generate', 'a re-rooted donor is generated (the copy graft is the identity\'s noise floor)'
    X, Y, Z = R_[:, 0], R_[:, 1], R_[:, 2]
    th_std = TAU * np.arange(K) / K
    n_nat = max(i for i in rings) - ic                           # the native loops past the ring the side carries
    nat_pos = {i: pos_of(rings[i]) for i in range(i0, ic + n_nat + 1)}
    z_nat = {i: float((nat_pos[i].mean(0) - O_) @ Z) for i in nat_pos}
    # |dr|max: the ring's own radii against the donor's section at the ring, at the ring vertices' own angles
    loc0 = (nat_pos[ic] - O_) @ R_
    th0 = np.arctan2(loc0[:, 1], loc0[:, 0])
    r_nat0 = np.hypot(loc0[:, 0], loc0[:, 1])
    r_don0 = donor.section_radius(np.full(K, float(donor.s_at(0.0))), th0)
    dr = float(np.abs(r_nat0 - r_don0).max())
    z_collar = z_nat[ic + 1]
    L_band = max(band_length(rec, 0.0), z_collar + 1.5 * dr / 0.25)
    band_i = [i for i in range(ic + 1, ic + n_nat + 1) if z_nat[i] <= L_band + 0.5 * rec['h']]
    assert len(band_i) >= 2 and band_i == list(range(ic + 1, band_i[-1] + 1)), \
        f'the native continues only {n_nat} loops past the ring: the band needs to z {L_band * 1e3:.1f} mm'
    L_band = max(L_band, z_nat[band_i[-1]])                  # the band ends on a native loop's station: w = 1 there
    # the donor's surface at a station and angles: along each angle's radius in the ring plane of its centreline point
    P_c, n_c, b_c, t_c = donor.arm
    sa = np.linspace(0.0, 1.0, len(P_c))
    fld = donor.field()

    def donor_at(s, theta, guess_r):
        c = np.array([np.interp(s, sa, P_c[:, k]) for k in range(3)])
        tz = np.array([np.interp(s, sa, t_c[:, k]) for k in range(3)])
        tz /= np.linalg.norm(tz)
        # the part's frame at the centreline point: the ring frame carried by the minimal rotation Z -> tz
        ax = np.cross(Z, tz)
        sn, cs = float(np.linalg.norm(ax)), float(Z @ tz)
        if sn > 1e-12:
            ax /= sn
            Kx = np.array([[0.0, -ax[2], ax[1]], [ax[2], 0.0, -ax[0]], [-ax[1], ax[0], 0.0]])
            Rm = np.eye(3) + sn * Kx + (1.0 - cs) * (Kx @ Kx)
        else:
            Rm = np.eye(3)
        Xs, Ys = Rm @ X, Rm @ Y
        d = np.cos(theta)[:, None] * Xs[None] + np.sin(theta)[:, None] * Ys[None]
        p0 = c[None] + guess_r[:, None] * d
        q, st_ = fld.project(p0, d, maxd=0.05)
        return np.asarray(q, np.float64), st_, c

    # the band's designed rings: the native loop at its station morphed into the donor there
    s_of = lambda z: float(donor.s_at(z))                                                       # noqa: E731
    band_V, band_w, band_z = [], [], []
    for i in band_i:
        z = z_nat[i]
        w = float(band_ramp(z, z_collar, L_band))
        Pn = nat_pos[i]
        if w <= 0.0:
            band_V.append(Pn)
        else:
            cn = Pn.mean(0)
            loc = (Pn - cn) @ R_
            th_n = np.arctan2(loc[:, 1], loc[:, 0])
            dth = (th_std - th_n + math.pi) % TAU - math.pi
            th_m = th_n + w * dth
            Pd, st_, _ = donor_at(s_of(z), th_m, donor.section_radius(np.full(K, s_of(z)), th_m) * 1.05)
            assert (np.asarray(st_) == 0).all(), f'the donor\'s surface missed at band station z {z * 1e3:.1f} mm'
            band_V.append((1.0 - w) * Pn + w * Pd)
        band_w.append(w)
        band_z.append(z)
    # the donor's rings past the band at its own ring step (the octopus cage's share step at the part's length)
    ds = ARM_RING_DS
    s_band = s_of(L_band)
    if band_only:
        # (the band alone: a machine part grips its end ring, the C5 flange on the octopus's own section; no donor
        # rings, no cap, the tube open there as C5b's cut arm is under its flange)
        st_gen = []
    else:
        st_gen = list(np.arange(s_band + ds, 0.9973 + 0.5 * ds, ds))
        st_gen[-1] = min(st_gen[-1], 0.9973)
    n_sup = fit_iters + 1
    st_sup = [s_band + ds * (k - n_sup + 1) for k in range(n_sup)]          # behind the first generated ring, the
    allst = st_sup + st_gen                                                 # band's last station among them
    if band_only:
        allst = st_sup[-2:]                                  # (a token donor tube, never kept: the cap code needs a ring)
    Pr = donor.rings(allst)
    Vf = Pr.reshape(-1, 3)
    nr = len(Vf)
    ring_ids_f = np.arange(nr).reshape(len(allst), K)
    Qf = []
    for a_, b_ in zip(ring_ids_f[:-1], ring_ids_f[1:]):
        for m in range(K):
            Qf.append((a_[m], a_[(m + 1) % K], b_[(m + 1) % K], b_[m]))
    Qf = np.array(Qf, np.int64)
    # outward winding (the quads' normals against the radial)
    c_ = Vf[Qf].mean(1)
    radv = c_ - (Pr.mean(1)[np.repeat(np.arange(len(allst) - 1), K)])
    fn = np.cross(Vf[Qf[:, 2]] - Vf[Qf[:, 0]], Vf[Qf[:, 3]] - Vf[Qf[:, 1]])
    if float(np.einsum('ij,ij->i', fn, radv).sum()) < 0:
        Qf = Qf[:, ::-1].copy()
    tmp = QuadMesh(Vf.copy(), Qf, {})
    capped, grid = loft.cap(tmp, ring_ids_f[-1], donor.tip_axis(), dome=0.0008 * donor.scale)
    Vf = np.asarray(capped.V, np.float64)
    Qf = np.asarray(capped.Q, np.int64)
    fx = np.zeros(len(Vf), bool)
    fx[ring_ids_f[0]] = True
    mesh = QuadMesh(Vf, Qf, {})
    if band_only:
        Vg = np.zeros((0, 3))
        gen_rings = np.zeros((0, K), np.int64)
        cap_v = np.zeros(0, np.int64)
        fit_stats = dict(band_only=True)
    else:
        stat, acc = retopo.fit(mesh, fld, iters=fit_iters, relax=0.5, fixed=fx)
        fit_stats = dict(status=np.asarray(stat).tolist(), accepted=[round(a, 4) for a in acc], support=n_sup)
        Vg = np.asarray(mesh.V, np.float64)
        gen_rings = ring_ids_f[n_sup:]
        cap_v = np.arange(nr, len(Vg))
    # ------------------------------------------------------------- the part: host rings, band, donor rings, cap
    fixed_i = list(range(i0, ic + 2))                       # the apron, the ring, the collar loop (w = 0, the native's)
    blocks, ring_no_l, cids, fixed_l = [], [], [], []
    for i in fixed_i:
        blocks.append(nat_pos[i])
        ring_no_l.append(np.full(K, i))
        cids.append(np.asarray(rings[i]))
        fixed_l.append(np.ones(K, bool))
    nids = list(cids)
    for j, i in enumerate(band_i[1:]):
        blocks.append(band_V[j + 1])
        ring_no_l.append(np.full(K, i))
        cids.append(np.full(K, -1))
        nids.append(np.asarray(rings[i]))                    # the native vertex each band vertex was morphed from
        fixed_l.append(np.zeros(K, bool))
    n0 = band_i[-1]
    for j, g in enumerate(gen_rings):
        blocks.append(Vg[g])
        ring_no_l.append(np.full(K, n0 + 1 + j))
        cids.append(np.full(K, -1))
        nids.append(np.full(K, -1))
        fixed_l.append(np.zeros(K, bool))
    nring = len(blocks)
    V = np.concatenate(blocks + [Vg[cap_v]])
    ring_no = np.concatenate(ring_no_l + [np.full(len(cap_v), -1)])
    cage_ids = np.concatenate(cids + [np.full(len(cap_v), -1)])
    nat_ids = np.concatenate(nids + [np.full(len(cap_v), -1)])
    fixed = np.concatenate(fixed_l + [np.zeros(len(cap_v), bool)])
    is_cap = ring_no < 0
    i_last = n0 + len(gen_rings)
    Q = []
    for j in range(nring - 1):
        a_, b_ = j * K, (j + 1) * K
        for m in range(K):
            Q.append((a_ + m, a_ + (m + 1) % K, b_ + (m + 1) % K, b_ + m))
    Q = np.array(Q, np.int64)
    c_ = V[Q].mean(1)
    cent = np.repeat(V[:nring * K].reshape(nring, K, 3).mean(1)[:-1], K, axis=0)
    fn = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
    if float(np.einsum('ij,ij->i', fn, c_ - cent).sum()) < 0:
        Q = Q[:, ::-1].copy()
    # the cap's quads, remapped from the donor mesh's numbering (its last ring = the part's last ring)
    if len(cap_v):
        remap = -np.ones(len(Vg), np.int64)
        remap[gen_rings[-1]] = np.arange((nring - 1) * K, nring * K)
        remap[cap_v] = np.arange(nring * K, nring * K + len(cap_v))
        cap_q = [q for q in Qf.tolist() if all(remap[v] >= 0 for v in q) and any(v in set(cap_v.tolist()) for v in q)]
        Qc = remap[np.array(cap_q, np.int64)]
        # the cap's winding agrees with the tube's at their shared edges (the donor mesh's own winding was outward)
        Q = np.vstack([Q, Qc])
    base_pos = np.full((len(V), 3), np.nan)
    has = cage_ids >= 0
    base_pos[has] = V[has]
    z_r = np.array([float((V[j * K:(j + 1) * K].mean(0) - O_) @ Z) for j in range(nring)])
    w_r = np.concatenate([np.zeros(len(fixed_i)), np.array(band_w[1:]), np.ones(len(gen_rings))])
    # each vertex's anatomical coordinate: (s along the donor arm, cos theta, sin theta, 0): the band's s by its z
    loc = (V - O_) @ R_
    s_v = np.concatenate([np.repeat([s_of(max(z, 0.0)) for z in z_r], K), np.full(len(cap_v), 1.0)])
    th_v = np.arctan2(loc[:, 1], loc[:, 0])
    st = np.column_stack([s_v, np.cos(th_v), np.sin(th_v), np.zeros(len(V))])
    ring_list = [np.arange(j * K, (j + 1) * K) for j in range(nring)]
    nb = len(band_i)
    log(f'[graft reroot] the part: {len(fixed_i)} host loops fixed (apron {apron}, the ring, the collar loop at z '
        f'{z_collar * 1e3:.1f} mm), the band to z {L_band * 1e3:.1f} mm (|dr|max {dr * 1e3:.2f} mm: {nb - 1} designed '
        f'rings, w {np.round(band_w[1:], 3).tolist()}), {len(gen_rings)} donor rings'
        + (f' (share {st_gen[0]:.4f} .. {st_gen[-1]:.4f}) + the cap ({len(cap_v)} vertices)' if len(gen_rings) else
           ' (the band alone)') + f'; fit {fit_stats}')
    return dict(V=V, Q=Q, cage_ids=cage_ids, ring_no=ring_no, is_cap=is_cap, st=st, fixed=fixed, i0=i0, ic=ic, nb=nb,
                i_last=i_last, base_pos=base_pos, mode=mode, fit=fit_stats, copies=copies, rings=ring_list, z=z_r,
                w=w_r, L_band=float(L_band), K=K, dr=dr, z_collar=z_collar, nat_ids=nat_ids)


def part_weights(base, part, rec, arms, cage, spec, mode='generate', smooth_iters=4, donor=None, cols=None):
    """weights on the chain's 24 joints (columns 0..23: arm<j>_00..arm<j>_cut are the base's, past the cut the graft's
    own joints at the donor's bind; M1a: the native positions). 'copy': the base's per vertex. 'generate': the apron,
    ring and band FROZEN (the base's bits: §2.6's Dirichlet boundary), the rest octopus_rig.weights' arm-tube rule
    (its share on the arm's centreline, rig.hat_weights over the joints' shares), smoothed over the part's cage with
    the frozen vertices pinned (rig.smooth_field), cut to 4 influences (rig.limit_influences). Returns (n, 24).
    (REROOT) On a host's ring: donor the re-rooted OctopusArm (its centreline: the shares the hat ramp reads; its joint
    shares the octopus's own, octopus_rig.arm_joint_s) and cols the 24 columns' joint NAMES (graft_joint_names: 7 the
    root's parent, 8 the root, 9.. the graft's own); the frozen vertices' host joints off those columns get columns of
    their own after the 24. Returns (W (n, 24 + extra), the column names)"""
    from . import rig as RG
    from .species import octopus_rig as OR
    names = base['jnames']
    jn = rec['chain']
    n = len(part['V'])
    if cols is None:
        col = {names.index(f'{jn}_{k:02d}'): k for k in range(OR.N_ARM_JOINTS)}
        ncol = OR.N_ARM_JOINTS
    else:
        cn = list(cols)
        for i, c in enumerate(part['cage_ids']):
            if c >= 0 and part['fixed'][i]:
                v = part['copies'][int(c)][0]
                for q in range(4):
                    nm = names[int(base['J'][v, q])]
                    if base['W32'][v, q] > 0.0 and nm not in cn:
                        cn.append(nm)
        col = {names.index(nm): k for k, nm in enumerate(cn) if nm in names}
        ncol = len(cn)
    Wb = np.zeros((n, ncol))
    for i, c in enumerate(part['cage_ids']):
        if c < 0:
            continue                                             # (a designed or donor vertex: no host bits)
        v = part['copies'][int(c)][0]
        for q in range(4):
            w = float(base['W32'][v, q])
            if w > 0.0:
                Wb[i, col[int(base['J'][v, q])]] += w           # (a weight off the chain would raise: none here)
    if mode == 'copy':
        return Wb
    if cols is not None:
        # (REROOT) the collar loop past the ring is the native's own (w = 0) but its host weights may name the native
        # group's joints, which the graft drops: their weight moves to the ROOT (graft_socket.collar_weights' rule)
        nat_j = [cn.index(nm) for nm in rec['native']['joints'] if nm in cn]
        past = part['fixed'] & (part['ring_no'] > part['ic'])
        if nat_j:
            k_root = cn.index(rec['root'])
            Wb[past, k_root] += Wb[np.ix_(past, nat_j)].sum(1)
            Wb[np.ix_(past, nat_j)] = 0.0
    js = OR.arm_joint_s(spec)
    Pa = (arms[cage['order'][int(jn[3:])]] if donor is None else donor.arm)[0]
    seg = Pa[1:] - Pa[:-1]
    V = part['V']
    q = V[:, None, :] - Pa[None, :-1, :]
    tseg = np.clip((q * seg[None]).sum(2) / (seg * seg).sum(1)[None], 0.0, 1.0)
    dist = np.linalg.norm(q - tseg[..., None] * seg[None], axis=2)
    ib = dist.argmin(1)
    s_on = (ib + tseg[np.arange(n), ib]) / (len(Pa) - 1)
    a, b, t = RG.hat_weights(s_on, js)
    W = np.zeros((n, ncol))
    np.add.at(W, (np.arange(n), a), 1.0 - t)
    np.add.at(W, (np.arange(n), b), t)
    W /= np.maximum(W.sum(1, keepdims=True), 1e-12)
    fr = part['fixed']
    if cols is not None:
        # (REROOT) the ring side of the donor's own joints: a share before its joint 7 never occurs past the ring (s0
        # is the cut-8 ring's share, between joints 7 and 8): every free vertex's weight lands on columns 7 .. 23 (the
        # apron, behind the ring, is frozen: its host weights replace its ramp below)
        assert not W[~fr, :7].any(), 'a free part vertex before the donor\'s joint 7'
    W[fr] = Wb[fr]
    W = RG.smooth_field(W, part['Q'], iters=smooth_iters, alpha=0.5, pinned=np.nonzero(fr)[0])
    J4, W4 = RG.limit_influences(W, 4)
    Wd = np.zeros_like(W)
    np.put_along_axis(Wd, J4.astype(np.int64), W4.astype(np.float64), axis=1)
    Wd[fr] = Wb[fr]                                       # the frozen bits exactly (the cut renormalises)
    return Wd if cols is None else (Wd, cn)


def graft_joint_names(host, rec, stem=None, n=24, cut=8):
    """(REROOT) the 24 donor columns' joint names on a host's ring: k < 8 the root's parent (the host's joint before
    the ring: only column 7 is ever reached), 8 the ROOT (the host's kept joint just past the ring, decision 2), k > 8
    the graft's own joints <stem>_g<kk> (§4.2's names; stem the host chain's name)"""
    rig = host['rig']
    root = rec['root']
    par = rig.names[int(rig.parent[rig.index[root]])]
    stem = stem or rec['chain']
    return [par if k < cut else (root if k == cut else f'{stem}_g{k:02d}') for k in range(n)]


def graft_joints(host, rec, donor, names, cut=8):
    """(REROOT) the graft's own joints on a host's ring: k > cut at the donor's joint shares (octopus_rig.arm_joint_s)
    on its centreline, each frame as octopus_rig.build lays an arm joint (x along the arm, y its aboral normal, z = x
    cross y). Returns [dict(name, parent, world)] parent-first"""
    from . import rig as RG
    from .species import octopus_rig as OR
    js = OR.arm_joint_s(donor.spec)
    Pa, na, ba, ta = donor.arm
    sa = np.linspace(0.0, 1.0, len(Pa))
    ip = lambda X, s: np.array([np.interp(s, sa, X[:, k]) for k in range(3)])            # noqa: E731
    out = []
    for k in range(cut + 1, len(names)):
        x = ip(ta, js[k])
        W = np.eye(4)
        W[:3, :3] = RG.frame_from(x, ip(na, js[k]))
        W[:3, 3] = ip(Pa, js[k])
        out.append(dict(name=names[k], parent=names[k - 1], world=W, share=float(js[k])))
    return out


def part_normals(base, part, rec, mode='generate'):
    """vertex normals on the part's WELDED cage (mesh.vertex_normals, as t10's N_w), the apron, ring and band the
    base's frozen bits (the ring by §2.5; the apron and band are the base's own loops, whose welded normals the base
    computed with their whole neighbourhood); 'copy': every vertex the base's"""
    from .mesh import QuadMesh
    Nb = np.array([base['N32'][part['copies'][int(c)][0]] if c >= 0 else (np.nan, np.nan, np.nan)
                   for c in part['cage_ids']]).astype(np.float64)
    if mode == 'copy':
        return Nb
    N = QuadMesh(part['V'], part['Q']).vertex_normals()
    fr = part['fixed']
    N[fr] = Nb[fr]
    return N


# ============================================================================================ islands and atlas
def part_islands(part, cage, seam_k=12, cut_rings=None):
    """the part's seams: the arm's oral midline (vertex seam_k of every ring), and loops at the native's own island
    cuts past the ring (octopus_uv: rings int(0.30 n), int(0.62 n), the tip's ring) so the donor keeps its native
    island shapes; the apron, ring and band share the STRIP island with the donor's first length.
    (REROOT) part['rings'] (each ring's part vertices in k order, graft_tube's) carries the rings, so a part on any host
    reads them there; cut_rings: the island cuts by ring number on a host's ring (donor_island_cuts), None: the
    octopus cage's (i30, i62, the tip)"""
    rings = part['rings']
    i0 = part['i0']
    S = []
    for i in range(part['i0'], part['i_last']):
        S.append((int(rings[i - i0][seam_k]), int(rings[i + 1 - i0][seam_k])))
    cuts = [int(cage['i30']), int(cage['i62']), part['i_last']] if cut_rings is None else list(cut_rings)
    for i in cuts:
        if part['i0'] < i <= part['i_last']:
            r = [int(c) for c in rings[i - i0]]
            S += [(r[m], r[(m + 1) % len(r)]) for m in range(len(r))]
    return S, [i for i in cuts if part['i0'] < i <= part['i_last']]


def donor_island_cuts(part, donor, shares=(0.7489, )):
    """(REROOT) the island cuts of a re-rooted octopus arm part: the band's last ring (w = 1: the STRIP island holds the
    ring, the collar and the morph, on the base's lattice where the native is), the octopus cage's own cut past it at
    i62's share (0.7489: octopus_uv's int(0.62 n)), and the tip's ring. Returns ring numbers"""
    i0 = part['i0']
    end = int(part['i0'] + int(np.nonzero(part['w'] >= 1.0 - 1e-12)[0][0]))
    out = [int(part['ic']), end]                     # (the ring: an island boundary on the host, as the host's own)
    zs = part['z']
    for s in shares:
        z = (s - donor.s0) / (1.0 - donor.s0) * donor.length
        j = int(np.argmin(np.abs(zs - z)))
        if i0 + j > end:
            out.append(i0 + j)
    out.append(int(part['i_last']))
    return out


def strip_base_corners(base, part, Qn, orig, strip, partial=False):
    """THE BASE LOW'S OWN VERTEX for every split vertex of the STRIP island (its quads `strip` in Qn), corner by
    corner: each part quad is a native quad (the same cage ids), whose base-low corners (the split copy on the same side
    of the oral seam: the one sharing a base triangle with the quad's other corners) carry the base set's UVs and the
    base's shipped frames. Returns {split vertex: base low vertex}; raises where a corner has no native counterpart (a
    donor's ring past the band: the conformal continuation is M1b's).
    (REROOT) partial: the quads with no native counterpart (a re-rooted donor's band rings, cage id -1) are skipped, so
    only the native's own corners come back (unwrap_part's lattice strip continues the rest conformally)"""
    L = base['low']
    # each split vertex's native cage id (REROOT: nat_ids, the native vertex a band vertex was morphed from, so the band
    # takes the native's own UVs there; the identity's are its cage ids)
    cid = part.get('nat_ids', part['cage_ids'])[orig]
    F = L['F']
    tri_of = {}
    for t, f in enumerate(F.tolist()):
        tri_of.setdefault(tuple(sorted(L['orig'][f].tolist())), []).append(t)
    out = {}
    for q in strip:
        corners = Qn[q]
        cc = [int(cid[v]) for v in corners]
        if partial and min(cc) < 0:
            continue
        # the base triangles on this quad (either diagonal): their corner low ids by cage id
        cand = [t for tri in ((cc[0], cc[1], cc[2]), (cc[0], cc[2], cc[3]), (cc[0], cc[1], cc[3]), (cc[1], cc[2], cc[3]))
                for t in tri_of.get(tuple(sorted(tri)), [])]
        if not cand:
            if partial:
                continue
            raise NotImplementedError(f'strip quad {q}: no native quad (a donor ring): the continuation is M1b\'s')
        ts = set(cand)
        low_of = {}
        for t in ts:
            for v in F[t]:
                low_of.setdefault(int(L['orig'][v]), set()).add(int(v))
        for v, c in zip(corners, cc):
            cps = low_of[c]
            if len(cps) > 1:                         # (never within one quad: a seam copy is per side)
                raise ValueError(f'strip quad {q}: two base copies of cage vertex {c} on one quad')
            lv = int(next(iter(cps)))
            if out.setdefault(int(v), lv) != lv:     # (a split vertex is one corner of the base on every quad)
                raise ValueError(f'strip vertex {int(v)}: two base corners {out[int(v)]} and {lv}')
    return out


def raster_mask(T, F, shape):
    """the texels (kernel rows: y = v * size) whose centre lies in any triangle (T: texel coordinates per vertex)"""
    m = np.zeros(shape, bool)
    for a, b, c in T[np.asarray(F)]:
        x0, y0 = np.floor(np.minimum(np.minimum(a, b), c)).astype(int)
        x1, y1 = np.ceil(np.maximum(np.maximum(a, b), c)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, shape[1] - 1), min(y1, shape[0] - 1)
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if x1 < x0 or y1 < y0 or abs(den) < 1e-12:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l0 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / den
        l1 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / den
        inside = (l0 >= -1e-9) & (l1 >= -1e-9) & (1.0 - l0 - l1 >= -1e-9)
        m[gy[inside].astype(int), gx[inside].astype(int)] = True
    return m


def skyline_pack(boxes, size, pad):
    """uv.pack's skyline (tallest first, rotated 0 / 90 to lay islands flat), returning the placements and the skyline
    itself (so a pre-placed island's slot can be searched above it). boxes: [(index, T (n, 2) texels from 0)]"""
    bx = []
    for i, T in boxes:
        w, h = T.max(0) + 2 * pad
        rot = w > h
        if rot:
            T = np.column_stack([T[:, 1], T.max(0)[0] - T[:, 0]])
            w, h = h, w
        bx.append((i, T, int(np.ceil(w)), int(np.ceil(h))))
    sky = np.zeros(size, np.int64)
    out = {}
    for i, T, w, h in sorted(bx, key=lambda b: -b[3]):
        best = None
        for x in range(0, size - w + 1, 4):
            y = int(sky[x:x + w].max())
            if best is None or y < best[1]:
                best = (x, y)
        if best is None or best[1] + h > size:
            return None, None
        x, y = best
        sky[x:x + w] = y + h
        out[i] = T + np.array([x + pad, y + pad])
    return out, sky


def unwrap_lattice_all(part, seams, lattice, pad=8, sizes=range(256, 4097, 64), log=print):
    """THE DONOR FAMILY'S OWN ISLANDS on the base's lattice (M1a: the donor is the octopus arm generator, whose own UV
    rule, octopus_uv, gives the native's islands): every island of the part takes the base's own UVs
    (strip_base_corners) and is placed by a whole number of `align` texels into the smallest square atlas that holds
    them all `pad` texels apart, so every texel of the part is one of the base's own sample points, as the strip's are
    (unwrap_part's lattice). Raises where an island has no native counterpart (a real donor: its own unwrap). Returns
    unwrap_part's dict, its strip covering every island: verts, quads, base_uv, base_v; offs {island: [dx, dy]},
    island_quads {island: quads}; off and island the ring's island's"""
    from scipy import ndimage
    from . import uv as U
    lab = U.islands(part['Q'], seams)
    Vn, Qn, orig = U.split(part['V'], part['Q'], lab, seams)
    n_isl = int(lab.max()) + 1
    base, S, al = lattice['base'], int(lattice['base_size']), int(lattice['align'])
    rq = (part['ring_no'][part['Q']] == lattice['ring']).any(1)
    strip_isl = int(np.bincount(lab[rq]).argmax())
    isl = []
    for i in range(n_isl):
        q = np.nonzero(lab == i)[0]
        bc = strip_base_corners(base, part, Qn, orig, q)
        sv = np.array(sorted(bc))
        bv = np.array([bc[v] for v in sv])
        Tb = base['low']['UV'][bv] * S
        idx = -np.ones(len(Vn), np.int64)
        idx[sv] = np.arange(len(sv))
        loc0 = np.floor(Tb.min(0)).astype(int)
        hi = np.ceil(Tb.max(0)).astype(int)
        lw, lh = int(hi[0] - loc0[0] + 1), int(hi[1] - loc0[1] + 1)
        m = raster_mask(Tb - loc0, idx[U._tri(Qn[q])], (lh, lw))
        isl.append(dict(i=i, q=q, sv=sv, bv=bv, Tb=Tb, loc0=loc0, lw=lw, lh=lh, m=m))
    order = sorted(range(n_isl), key=lambda k: -int(isl[k]['m'].sum()))
    for size in sizes:
        if size % al:
            continue
        occ = np.zeros((size, size), bool)
        offs, top = {}, 0
        for k in order:
            d = isl[k]
            sy, sx = np.nonzero(d['m'])
            (x0, y0), best = d['loc0'], None
            for jy in range(int(np.ceil((pad - y0) / al)), int(np.floor((size - pad - y0 - d['lh']) / al)) + 1):
                for jx in range(int(np.ceil((pad - x0) / al)), int(np.floor((size - pad - x0 - d['lw']) / al)) + 1):
                    if not occ[y0 + jy * al + sy, x0 + jx * al + sx].any():
                        best = (jx, jy)
                        break
                if best is not None:
                    break
            if best is None:
                break
            ox, oy = x0 + best[0] * al, y0 + best[1] * al
            mk = np.zeros((size, size), bool)
            mk[oy + sy, ox + sx] = True
            occ |= ndimage.binary_dilation(mk, structure=np.ones((3, 3), bool), iterations=pad)
            offs[d['i']] = np.array(best, np.float64) * al
            top = max(top, oy + d['lh'] + pad)
        if len(offs) == n_isl:
            break
    else:
        raise ValueError('no atlas up to 4096 holds the part\'s islands on the base\'s lattice')
    UVn = np.zeros((len(Vn), 2))
    for d in isl:
        UVn[d['sv']] = (d['Tb'] + offs[d['i']]) / size
    strip = dict(island=strip_isl, off=offs[strip_isl].tolist(), base_size=S, align=al,
                 verts=np.concatenate([d['sv'] for d in isl]), quads=np.concatenate([d['q'] for d in isl]),
                 base_uv=np.concatenate([d['Tb'] for d in isl]) / S, base_v=np.concatenate([d['bv'] for d in isl]),
                 offs={d['i']: offs[d['i']].tolist() for d in isl}, island_quads={d['i']: d['q'] for d in isl})
    log(f'[graft uv] EVERY island ({n_isl}: the donor family\'s own, the native\'s) on the BASE\'S LATTICE in {size}^2, '
        f'offsets {[[int(v) for v in offs[i]] for i in range(n_isl)]} texels (multiples of {al}), height used '
        f'{top / size * 100:.1f} %')
    return dict(Vn=Vn, Qn=Qn, orig=orig, UV=UVn, label=lab, size=int(size), used=float(top / size), dens={},
                strip=strip)


def lattice_canvas_map(strip, low, canvas_mask):
    """for every texel of canvas_mask (image rows on the CANVAS: the base set's size, the lattice islands at the base's
    own UVs) the part-atlas texel it composites to, by its island's own whole-texel offset (strip['offs'], or the one
    strip island's 'off'). A texel is its island's when its centre lies on one of the island's triangles at the base's
    UVs, else the nearest such texel's (an edge texel only a sub-sample reached). Returns (r_c, x_c, r_p, x_p)"""
    from scipy import ndimage
    Sc, size = int(strip['base_size']), int(low['size'])
    offs = strip.get('offs') or {strip['island']: strip['off']}
    iq = strip.get('island_quads') or {strip['island']: strip['quads']}
    UVc = np.asarray(low['UV'], np.float64).copy()
    UVc[strip['verts']] = strip['base_uv']
    lab_img = -np.ones((Sc, Sc), np.int64)
    for i, q in iq.items():
        m = raster_mask(UVc * Sc, low['F'][np.isin(low['fq'], q)], (Sc, Sc))[::-1]
        lab_img[m] = i
    _, (iy, ix) = ndimage.distance_transform_edt(lab_img < 0, return_indices=True)
    lab_img = lab_img[iy, ix]
    r_c, x_c = np.nonzero(canvas_mask)
    li = lab_img[r_c, x_c]
    ox = np.array([offs[int(i)][0] for i in li], np.float64)
    oy = np.array([offs[int(i)][1] for i in li], np.float64)
    r_p = r_c + (size - Sc) - np.round(oy).astype(np.int64)
    x_p = x_c + np.round(ox).astype(np.int64)
    return r_c, x_c, r_p, x_p


def unwrap_part(part, seams, px_per_m, pad=8, arap_iters=8, sizes=range(256, 4097, 64), log=print, lattice=None):
    """per island LSCM + ARAP (octopus_uv's rule: the ARAP depth whose worst-direction footprint is smallest among
    those that do not fold), counter-clockwise, then packed at the RING'S density px_per_m into the smallest square
    atlas (a multiple of 64) whose skyline holds every island with `pad` texels round it.
    lattice = dict(base=..., ring=<the ring's ring number>, base_size, align): the STRIP island (the one holding the
    ring) is laid on THE BASE'S OWN TEXEL LATTICE instead: its UVs the base set's (strip_base_corners) shifted by a whole
    number of `align` texels into a free slot above the other islands' skyline, so its texel centres are the base's
    own sample points at the same surface points (the bake reads the same points, and on a canvas of the base's size
    at the base's positions the same AO rays: m1_gpu.py), and with align a power of two the mip levels up to log2(align)
    are aligned too. lattice['all'] True: EVERY island on the base's lattice (unwrap_lattice_all: the donor family's own
    islands, where the donor is the native). Returns dict(Vn, Qn, orig, UV, label, size, used, dens, strip)"""
    from . import uv as U
    if lattice is not None and lattice.get('all'):
        return unwrap_lattice_all(part, seams, lattice, pad=pad, sizes=sizes, log=log)
    lab = U.islands(part['Q'], seams)
    Vn, Qn, orig = U.split(part['V'], part['Q'], lab, seams)
    n_isl = int(lab.max()) + 1
    UVn = np.zeros((len(Vn), 2))
    dens, vsets = {}, {}
    strip_isl = None
    if lattice is not None:
        rq = (part['ring_no'][part['Q']] == lattice['ring']).any(1)
        if lattice.get('distal'):
            # (REROOT) a host whose ring is an island boundary of its own (the axolotl's): the strip is the island past
            # the ring (the native's distal chart continued), the apron's an island of its own
            rq &= (part['ring_no'][part['Q']] >= lattice['ring']).all(1)
        strip_isl = int(np.bincount(lab[rq]).argmax())
    for i in range(n_isl):
        if i == strip_isl:
            continue
        fq = np.nonzero(lab == i)[0]
        F = U._tri(Qn[fq])
        vs = np.unique(F)
        lk = -np.ones(len(Vn), np.int64)
        lk[vs] = np.arange(len(vs))
        Fl = lk[F]
        P = Vn[vs]
        uv = U.lscm(P, Fl)
        best, cand, done = None, uv, 0
        for it in (0, 2, max(arap_iters // 2, 3), arap_iters):
            if it > done:
                cand, done = U.arap(P, Fl, cand, it - done), it
            if U.self_overlap(cand, Fl):
                continue
            fp = U.footprint(P, Fl, cand)
            if best is None or fp < best[0]:
                best = (fp, it, cand)
        if best is None:
            log(f'[graft uv] island {i}: every ARAP depth folded it, LSCM kept')
            best = (U.footprint(P, Fl, uv), 0, uv)
        uv = best[2]
        d1, d2 = uv[Fl[:, 1]] - uv[Fl[:, 0]], uv[Fl[:, 2]] - uv[Fl[:, 0]]
        if (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum() < 0:
            uv[:, 0] = -uv[:, 0]
        # turned to its smallest bounding box (LSCM leaves an island at any angle and the packer boxes it: a strip at
        # 45 deg took twice its texels); a rotation in the plane keeps the density and the winding
        best_a, best_area = 0.0, None
        for a in np.radians(np.arange(0.0, 90.0, 0.25)):
            c_, s_ = np.cos(a), np.sin(a)
            rt = uv @ np.array([[c_, -s_], [s_, c_]])
            ar = float(np.ptp(rt[:, 0]) * np.ptp(rt[:, 1]))
            if best_area is None or ar < best_area - 1e-15:
                best_a, best_area = a, ar
        c_, s_ = np.cos(best_a), np.sin(best_a)
        uv = uv @ np.array([[c_, -s_], [s_, c_]])
        UVn[vs] = uv
        dens[i] = U.island_density(P, Fl, uv)
        vsets[i] = vs
        log(f'[graft uv] island {i}: {len(fq)} quads, ARAP {best[1]}, footprint p95 {best[0]:.3f}')
    ids = [i for i in range(n_isl) if i != strip_isl]
    strip = None
    if strip_isl is None:
        for size in sizes:
            try:
                packed, used = U.pack([UVn[vsets[i]] for i in ids], [px_per_m / dens[i] for i in ids], size, pad)
            except ValueError:
                continue
            if used <= 1.0:
                break
        else:
            raise ValueError('no atlas up to 4096 holds the part at the ring\'s density')
        for i, pk in zip(ids, packed):
            UVn[vsets[i]] = pk
    else:
        # the strip island on the base's lattice: its base UVs in the base set's texels (kernel rows, v up)
        sq = np.nonzero(lab == strip_isl)[0]
        if lattice.get('pin') == 'fixed':
            # (REROOT, M1b's conformal continuation) a re-rooted donor's band: the strip's FIXED vertices (the ring and
            # the collar loop: the native's own) pinned at the base's UVs, the morphed band rings continued by the
            # conformal map with every pin held (graft_socket.lscm_pinned, M2's collar_uv): the native's UVs on the
            # morphed rings stretched them past G-R5's bar (anisotropy p95 1.23 on tail_mid)
            from .graft_socket import lscm_pinned
            bc_all = strip_base_corners(lattice['base'], part, Qn, orig, sq, partial=True)
            bcor = {v: b for v, b in bc_all.items() if part['fixed'][orig[v]]}
            sv = np.unique(Qn[sq])
            pin_l = np.array([i for i, v in enumerate(sv) if int(v) in bcor])
            base_v = np.array([bcor.get(int(v), -1) for v in sv])
            lk = -np.ones(len(Vn), np.int64)
            lk[sv] = np.arange(len(sv))
            Fl_s = lk[U._tri(Qn[sq])]
            Tb = lscm_pinned(Vn[sv], Fl_s, pin_l,
                             lattice['base']['low']['UV'][base_v[pin_l]] * lattice['base_size'])
            # each strip vertex's NATIVE uv (the native vertex it was morphed from: nat_ids), for the material's
            # native side on the band (a sample of the base's maps there)
            uv_nat = np.full((len(sv), 2), np.nan)
            for i, v in enumerate(sv):
                if int(v) in bc_all:
                    uv_nat[i] = lattice['base']['low']['UV'][bc_all[int(v)]]
        else:
            bcor = strip_base_corners(lattice['base'], part, Qn, orig, sq)
            sv = np.array(sorted(bcor))
            base_v = np.array([bcor[v] for v in sv])
            Tb = lattice['base']['low']['UV'][base_v] * lattice['base_size']
            uv_nat = None
        t0, t1 = Tb.min(0), Tb.max(0)
        al = int(lattice['align'])
        boxes = []
        for i in ids:
            T = UVn[vsets[i]] * (px_per_m / dens[i])
            boxes.append((i, T - T.min(0)))
        # the strip's own texels on its lattice, in a local grid from its box's corner (whole texels, so a shift by
        # whole texels moves the mask unchanged)
        from scipy import ndimage
        loc0 = np.floor(t0).astype(int)
        lw, lh = int(np.ceil(t1[0])) - loc0[0] + 1, int(np.ceil(t1[1])) - loc0[1] + 1
        idx = -np.ones(len(Vn), np.int64)
        idx[sv] = np.arange(len(sv))
        Fs = idx[U._tri(Qn[sq])]
        m_strip = raster_mask(Tb - loc0, Fs, (lh, lw))
        sy, sx = np.nonzero(m_strip)
        for size in sizes:
            if size % al:
                continue
            placed, sky = skyline_pack(boxes, size, pad)
            if placed is None:
                continue
            # the other islands' texels, padded; then the lowest slot whose offset from the base's texels is a whole
            # number of al texels and whose strip texels stay pad clear of them and of the sheet's edges
            occ = np.zeros((size, size), bool)
            for i in ids:
                fq_i = np.nonzero(lab == i)[0]
                li = -np.ones(len(Vn), np.int64)
                li[vsets[i]] = np.arange(len(vsets[i]))
                occ |= raster_mask(placed[i], li[U._tri(Qn[fq_i])], (size, size))
            occ = ndimage.binary_dilation(occ, structure=np.ones((3, 3), bool), iterations=pad)
            best = None
            for jy in range(int(np.ceil((pad - loc0[1]) / al)), int(np.floor((size - pad - loc0[1] - lh) / al)) + 1):
                for jx in range(int(np.ceil((pad - loc0[0]) / al)), int(np.floor((size - pad - loc0[0] - lw) / al)) + 1):
                    ox, oy = loc0[0] + jx * al, loc0[1] + jy * al
                    if not occ[oy + sy, ox + sx].any():
                        best = (jx, jy)
                        break
                if best is not None:
                    break
            if best is not None:
                break
        else:
            raise ValueError('no atlas up to 4096 holds the part with its strip on the base\'s lattice')
        off = np.array(best, np.float64) * al
        for i in ids:
            UVn[vsets[i]] = placed[i] / size
        UVn[sv] = (Tb + off) / size
        used = float(max(sky.max(), t1[1] + off[1] + pad) / size)
        strip = dict(island=strip_isl, off=off.tolist(), base_size=int(lattice['base_size']), align=al,
                     verts=sv, quads=sq, base_uv=Tb / lattice['base_size'], base_v=base_v)
        if uv_nat is not None:
            strip['uv_nat'] = uv_nat                     # (REROOT: the band's native uv per strip vertex, base frame)
        log(f'[graft uv] the strip island {strip_isl} ({len(sq)} quads) on the BASE\'S LATTICE: its UVs the base set\'s '
            f'shifted by {off.astype(int).tolist()} texels (multiples of {al}: mips aligned to level {int(np.log2(al))})')
    log(f'[graft uv] {n_isl} islands packed at {px_per_m:.2f} px/m (the ring\'s) into {size}^2, height used '
        f'{used * 100:.1f} %')
    return dict(Vn=Vn, Qn=Qn, orig=orig, UV=UVn, label=lab, size=int(size), used=float(used), dens=dens, strip=strip)


def triangulate(Vn, Qn):
    """two triangles per quad along the SHORTER diagonal in 3D (t10's rule, the export's), all first triangles then all
    second ones (t10's order); returns (F, quad of each triangle)"""
    d02 = np.linalg.norm(Vn[Qn[:, 0]] - Vn[Qn[:, 2]], axis=1)
    d13 = np.linalg.norm(Vn[Qn[:, 1]] - Vn[Qn[:, 3]], axis=1)
    short = d02 <= d13
    Fa = np.where(short[:, None], Qn[:, [0, 1, 2]], Qn[:, [0, 1, 3]])
    Fb = np.where(short[:, None], Qn[:, [0, 2, 3]], Qn[:, [1, 2, 3]])
    return np.concatenate([Fa, Fb]), np.concatenate([np.arange(len(Qn)), np.arange(len(Qn))])


def part_low(base, part, rec, uvres, N_cage, W24):
    """the part's LOW as the bake and the material pass take it (the apron included) and the mask of the triangles it
    SHIPS (the apron's left out): V, F, UV (forge v-up, in the atlas), N (the cage's per vertex: the frozen bits on the
    ring), TAN (bake.low_frames: the same tangents the export writes), W24 per vertex, ring vertices.
    The FIXED loops (the apron, the ring, the band: the base's own vertices, positions and normals already the base's
    bits) take the BASE'S SHIPPED TANGENTS too, where the strip lies on the base's lattice: their own UVs are the base's
    shifted by whole texels, so low_frames gives the base's tangents but for its summation order (1 ulp on about half
    of them) and, on the apron's first ring, its missing proximal triangles. With the frame frozen, the strip's bake
    inputs (position, normal, tangent, UV on the base's lattice) are the canonical's own, bit for bit"""
    from . import bake as BK
    Vn, Qn, orig = uvres['Vn'], uvres['Qn'], uvres['orig']
    F, fq = triangulate(Vn, Qn)
    N = N_cage[orig]
    _, TAN = BK.low_frames(Vn, F, uvres['UV'], N)
    st = uvres.get('strip')
    if st is not None and 'base_v' in st:
        sv, bv = np.asarray(st['verts']), np.asarray(st['base_v'])
        fx = part['fixed'][orig[sv]]
        n32 = lambda a: np.ascontiguousarray(np.asarray(a, np.float32)).view(np.uint32)
        assert (n32(N[sv[fx]]) == n32(base['N32'][bv[fx]])).all(), 'a fixed strip vertex\'s normal is not the base\'s'
        assert (n32(Vn[sv[fx]]) == n32(base['V32'][bv[fx]])).all(), 'a fixed strip vertex is not the base\'s'
        TAN[sv[fx]] = base['T32'][bv[fx]].astype(np.float64)
    rn = part['ring_no'][orig]
    q_ring = np.minimum.reduce([part['ring_no'][part['Q'][:, k]] for k in range(4)])
    q_ring = np.where(part['is_cap'][part['Q']].any(1), 10 ** 6, q_ring)
    ship_q = q_ring >= part['ic']
    return dict(V=Vn, F=F, UV=uvres['UV'], N=N, TAN=TAN, W24=W24[orig], fq=fq, ship=ship_q[fq],
                ring_v=np.nonzero(rn == part['ic'])[0], orig=orig, ring_no=rn, size=uvres['size'])


# ============================================================================================ the material
def frozen_normaliser(drivers_npz, px_per_m, fine_sigma_mm=0.6, mid_sigma_mm=3.0):
    """the BASE'S convexity normaliser (decision 13: frozen per base, never re-measured by a graft): calib's p95 of the
    masked-blurred curvature over the base set's coverage, at the base set's density, exactly as the canonical's t11
    took it (calib.relief_drivers on the drivers it saved). Returns dict(conv, conv_mid)"""
    from . import calib
    D = np.load(drivers_npz)
    cov = np.asarray(D['normal'])[..., 3] > 0
    m = cov.astype(np.float32)
    mm = lambda s: s / 1000.0 * px_per_m
    cu = np.asarray(D['curvature'], np.float32)
    p = {}
    for k, sg in (('conv', fine_sigma_mm), ('conv_mid', mid_sigma_mm)):
        b = calib.mblur(cu, m, mm(sg))
        p[k] = float(np.percentile(np.abs(b[cov]), 95))
    return p


def relief_drivers_frozen(p95, ctx=None):
    """calib.relief_drivers with the convexity normalised by the BASE'S p95 (frozen_normaliser) in place of the set's
    own: the part's set is a part of the base's surface, so its own p95 would re-measure the base.
    ctx (a part whose STRIP island lies on the base's lattice): dict(ao, cu, cov: the canonical's own drivers on the
    base set's image; px: the base set's px/m; rp, xp: the strip's texels in the part atlas (image rows); rc, xc: the
    same texels on the base set's image; ship: those whose centre lies on a triangle the part ships). The strip's
    relief is taken IN THE BASE'S OWN CONTEXT: on the canonical's drivers with the part's shipped strip texels in place
    of the base's, at the base set's density, so every masked blur round the ring reads on the base's side what the
    canonical's own blur read (its UV neighbours included) and past the ring the part's own surface"""
    from . import calib

    def fields(ao, cu, cov, px_per_m, ao_sigma_mm, fine_sigma_mm, mid_sigma_mm):
        m = cov.astype(np.float32)
        mm = lambda s: s / 1000.0 * px_per_m
        ao_local = (ao - calib.mblur(ao, m, mm(ao_sigma_mm))) * m
        conv = np.clip(calib.mblur(cu, m, mm(fine_sigma_mm)) / max(p95['conv'], 1e-12), -3.0, 3.0) * m
        conv_mid = np.clip(calib.mblur(cu, m, mm(mid_sigma_mm)) / max(p95['conv_mid'], 1e-12), -3.0, 3.0) * m
        return dict(ao_local=ao_local.astype(np.float32), conv=conv.astype(np.float32),
                    conv_mid=conv_mid.astype(np.float32))

    def relief(drivers, px_per_m, ao_sigma_mm=6.0, fine_sigma_mm=0.6, mid_sigma_mm=3.0, **_kw):
        cov = np.asarray(drivers['normal'])[..., 3] > 0
        ao = np.asarray(drivers['ao'], np.float32)
        cu = np.asarray(drivers['curvature'], np.float32)
        sg = (ao_sigma_mm, fine_sigma_mm, mid_sigma_mm)
        out = fields(ao, cu, cov, px_per_m, *sg)
        if ctx is not None:
            rp, xp, rc, xc, sh = (np.asarray(ctx[k]) for k in ('rp', 'xp', 'rc', 'xc', 'ship'))
            ao_c = np.asarray(ctx['ao'], np.float32).copy()
            cu_c = np.asarray(ctx['cu'], np.float32).copy()
            cov_c = np.asarray(ctx['cov'], bool).copy()
            ao_c[rc[sh], xc[sh]] = ao[rp[sh], xp[sh]]
            cu_c[rc[sh], xc[sh]] = cu[rp[sh], xp[sh]]
            cov_c[rc[sh], xc[sh]] = cov[rp[sh], xp[sh]]
            oc = fields(ao_c, cu_c, cov_c, float(ctx['px']), *sg)
            cy = ctx.get('cyl')
            if cy is None:
                for k in out:
                    out[k][rp, xp] = oc[k][rc, xc] * cov[rp, xp]
            else:
                # (M2b) near the part's UV SEAM the masked texture-space blurs saw one side of it only (the M2 seam
                # check: a roughness step along the collar's seam, 0.032 against the arm's own 0.006, where the kept
                # sucker 51's shade lay on one side); there the fields come from the tube's own (theta, z) grid, which
                # wraps across the seam (cyl_fields), blended in by each field's seam window and faded in from the ring
                cf = cyl_fields(np.asarray(drivers['position'])[rp, xp, :3], ao_c[rc, xc], cu_c[rc, xc],
                                cov_c[rc, xc], float(ctx['px']), sg, p95, cy)
                for k in out:
                    w = cf['w'][k]
                    out[k][rp, xp] = ((1.0 - w) * oc[k][rc, xc] + w * cf[k]) * cov[rp, xp]
        return out
    return relief


def cyl_fields(P, ao, cu, ok, px_per_m, sg, p95, cy):
    """relief_drivers_frozen's three fields for a TUBE's texels, seam-free (M2b, the collar's seam): the texels'
    positions P (n, 3) in the socket's frame (cy: O, R the frame's origin and axes, X / Y across, Z along) give (theta,
    z); their values (ao, curvature: the context's) are splatted onto a (theta, z) grid at the texel density, whose theta
    WRAPS, the masked Gaussians run there (theta's sigma per row by its radius, so each is sigma_mm of arc), and each
    texel reads its blur back bilinearly. Returns the fields and per field the BLEND WEIGHT: the seam window (1 within
    3 sigma of arc from cy['theta_seam'], 0 past 4 sigma) x the ring fade (smoothstep from cy['z_ring'] to cy['z_full']:
    at the ring the fields stay the base's own context's)"""
    from scipy import ndimage
    ao_sigma_mm, fine_sigma_mm, mid_sigma_mm = sg[:3]
    O, R = np.asarray(cy['O'], np.float64), np.asarray(cy['R'], np.float64)
    q = (np.asarray(P, np.float64) - O) @ R
    th = np.mod(np.arctan2(q[:, 1], q[:, 0]), TAU)
    z, r = q[:, 2], np.hypot(q[:, 0], q[:, 1])
    ok = np.asarray(ok, bool) & np.isfinite(z)
    rmean = float(np.median(r[ok]))
    nth = int(np.ceil(TAU * rmean * px_per_m))
    z0 = float(z[ok].min())
    nz = int(np.ceil((float(z[ok].max()) - z0) * px_per_m)) + 1
    it = np.clip((th / TAU * nth).astype(np.int64), 0, nth - 1)
    iz = np.clip(((z - z0) * px_per_m).astype(np.int64), 0, nz - 1)
    S = np.zeros((nz, nth, 3))
    C = np.zeros((nz, nth))
    np.add.at(S, (iz[ok], it[ok]), np.column_stack([ao[ok], cu[ok], r[ok]]))
    np.add.at(C, (iz[ok], it[ok]), 1.0)
    m = (C > 0).astype(np.float64)
    S[C > 0] /= C[C > 0][:, None]
    rows = m.sum(1) > 0
    rz = np.where(rows, (S[..., 2] * m).sum(1) / np.maximum(m.sum(1), 1.0), np.nan)
    rz = np.interp(np.arange(nz), np.nonzero(rows)[0], rz[rows])          # (an empty row: its neighbours' radius)

    def mblur(v, sig_mm):
        num, den = v * m, m.copy()
        for i in range(nz):
            s = sig_mm / 1000.0 * px_per_m * rmean / max(rz[i], 1e-4)       # sigma_mm of ARC at this row's radius
            num[i] = ndimage.gaussian_filter1d(num[i], s, mode='wrap')
            den[i] = ndimage.gaussian_filter1d(den[i], s, mode='wrap')
        s = sig_mm / 1000.0 * px_per_m
        num = ndimage.gaussian_filter1d(num, s, axis=0, mode='constant')
        den = ndimage.gaussian_filter1d(den, s, axis=0, mode='constant')
        return num / np.maximum(den, 1e-6)

    def sample(G):
        fz = np.clip((z - z0) * px_per_m - 0.5, 0.0, nz - 1.0)
        ft = th / TAU * nth - 0.5
        z_i = np.minimum(np.floor(fz).astype(np.int64), nz - 2) if nz > 1 else np.zeros(len(z), np.int64)
        t_i = np.floor(ft).astype(np.int64)
        a, b = fz - z_i, ft - t_i
        t0, t1 = np.mod(t_i, nth), np.mod(t_i + 1, nth)
        z1_ = np.minimum(z_i + 1, nz - 1)
        return ((1 - a) * ((1 - b) * G[z_i, t0] + b * G[z_i, t1]) + a * ((1 - b) * G[z1_, t0] + b * G[z1_, t1]))

    b_ao = sample(mblur(S[..., 0], ao_sigma_mm))
    out = dict(ao_local=(ao - b_ao).astype(np.float32),
               conv=np.clip(sample(mblur(S[..., 1], fine_sigma_mm)) / max(p95['conv'], 1e-12), -3.0, 3.0).astype(np.float32),
               conv_mid=np.clip(sample(mblur(S[..., 1], mid_sigma_mm)) / max(p95['conv_mid'], 1e-12), -3.0,
                                3.0).astype(np.float32))
    d_arc = r * np.abs(np.mod(th - float(cy['theta_seam']) + math.pi, TAU) - math.pi)
    ring = np.clip((z - float(cy['z_ring'])) / max(float(cy['z_full']) - float(cy['z_ring']), 1e-9), 0.0, 1.0)
    ring = ring * ring * (3.0 - 2.0 * ring)
    out['w'] = {}
    for k, sig in (('ao_local', ao_sigma_mm), ('conv', fine_sigma_mm), ('conv_mid', mid_sigma_mm)):
        s = sig / 1000.0
        u = np.clip((d_arc - 3.0 * s) / s, 0.0, 1.0)
        out['w'][k] = ((1.0 - u * u * (3.0 - 2.0 * u)) * ring * ok).astype(np.float32)
    return out


def strip_context(base_drivers_npz, strip_npz, px_set):
    """relief_drivers_frozen's ctx from the canonical's drivers (the base set's image) and a part's strip.npz
    (m1_gpu.py's: the strip's texels in the part atlas and on the base set's canvas, and which of them ship)"""
    D = np.load(base_drivers_npz)
    S = np.load(strip_npz)
    return dict(ao=np.asarray(D['ao'], np.float32), cu=np.asarray(D['curvature'], np.float32),
                cov=np.asarray(D['normal'])[..., 3] > 0, px=float(px_set),
                rp=S['rp'], xp=S['xp'], rc=S['rc'], xc=S['xc'], ship=S['ship'].astype(bool))


def part_material(low, drivers, size, px_per_m, p95, spec, arms, order, inst, prog, log=print, ctx=None):
    """the octopus skin pass (species/octopus_skin.run, the arms set's kind: the part is arm order[0]'s own surface)
    over the part's own bake, with the BASE'S convexity normaliser (calib.relief_drivers swapped for the frozen one
    for this call only; ctx: the strip's relief in the base's own context, relief_drivers_frozen). Returns the
    image-order uint8 maps"""
    from . import calib
    from .species import octopus_sculpt as SC
    from .species import octopus_skin
    from .species import octopus_suckers as OS
    keep = calib.relief_drivers
    calib.relief_drivers = relief_drivers_frozen(p95, ctx)
    try:
        recipe = dict(octopus_skin.SKIN_RECIPE, vein=None)
        out = octopus_skin.run(dict(V=low['V'], F=low['F'], UV=low['UV'], N=low['N'], TAN=low['TAN'],
                                    ATTR=np.zeros((len(low['V']), 4))), drivers, 1, size, spec, arms, order,
                               OS.baked_only(inst), SC.arm_tables(spec), 1.0 / px_per_m, prog, recipe=recipe, log=log)
    finally:
        calib.relief_drivers = keep
    return out


def strip_canvas_material(maps, low, drivers, strip, strip_npz, material, ctx):
    """the STRIP's material pass in the frame its bake ran in: the strip's triangles on the CANVAS (the base set's size,
    the base's own UVs) over its own drivers placed back on the canvas, then its texels composited into the part
    atlas's maps (from the atlas pass, every island) and the atlas's gutters re-dilated from them. In the atlas frame
    (the base's UVs shifted by whole texels) a sub-sample on an island edge can round to the other side of the edge
    test, so an edge texel the canonical shaded from one sub-sample came out black there; on the canvas every
    sub-sample test is the canonical's own. material(low, drivers, size, ctx) -> maps; strip_npz: m1_gpu.py's (the
    strip's texels in the atlas, rp / xp, and on the canvas, rc / xc). Returns (maps, report)"""
    rp, xp, rc, xc = (np.asarray(strip_npz[k]) for k in ('rp', 'xp', 'rc', 'xc'))
    Sc = int(strip['base_size'])
    ts = np.isin(low['fq'], strip['quads'])
    UVc = np.asarray(low['UV'], np.float64).copy()
    UVc[strip['verts']] = strip['base_uv']
    low_c = dict(V=low['V'], F=low['F'][ts], UV=UVc, N=low['N'], TAN=low['TAN'])
    Dc = {}
    for k, a in drivers.items():
        a = np.asarray(a)
        if a.ndim >= 2 and a.shape[:2] == drivers['normal'].shape[:2]:
            b = np.full((Sc, Sc) + a.shape[2:], -1 if k == 'region' else 0, a.dtype)
            b[rc, xc] = a[rp, xp]
            Dc[k] = b
        else:
            Dc[k] = a
    ctx_c = dict(ctx, rp=rc, xp=xc) if ctx is not None else None      # (the canvas IS the base set's frame)
    maps_c = material(low_c, Dc, Sc, ctx_c)
    cov = np.asarray(drivers['normal'])[..., 3] > 0
    out, changed = {}, {}
    for k, a in maps.items():
        b = a.copy()
        changed[k] = int((np.asarray(b[rp, xp]) != np.asarray(maps_c[k][rc, xc])).reshape(len(rp), -1).any(1).sum())
        b[rp, xp] = maps_c[k][rc, xc]
        out[k] = b
    return redilate(out, cov), dict(changed=changed, texels=len(rp))


def redilate(maps, cov, steps=24):
    """the skin pass's gutter dilation (octopus_skin.run's bake.dilate_all, 24 texels: each gutter texel takes its
    nearest covered texel's value) re-applied to finished uint8 maps after covered texels were replaced; texels
    farther out keep what they hold (the pass's defaults)"""
    from scipy import ndimage
    d, idx = ndimage.distance_transform_edt(~np.asarray(cov, bool), return_indices=True)
    fill = (d <= steps) & ~np.asarray(cov, bool)
    out = {}
    for k, a in maps.items():
        b = np.asarray(a).copy()
        b[fill] = np.asarray(a)[idx[0][fill], idx[1][fill]]
        out[k] = b
    return out


def arm_share_length(points, arm):
    """each point's arc length along the arm's centreline (m from its root) at its nearest centreline point"""
    Pa = arm[0]
    seg = Pa[1:] - Pa[:-1]
    sl = np.concatenate([[0.0], np.cumsum(np.linalg.norm(seg, axis=1))])
    p = np.asarray(points, np.float64).reshape(-1, 3)
    z = np.zeros(len(p))
    for c in range(0, len(p), 16384):
        q = p[c:c + 16384, None, :] - Pa[None, :-1, :]
        tt = np.clip((q * seg[None]).sum(2) / (seg * seg).sum(1)[None], 0.0, 1.0)
        d = np.linalg.norm(q - tt[..., None] * seg[None], axis=2)
        ib = d.argmin(1)
        z[c:c + 16384] = sl[ib] + tt[np.arange(len(ib)), ib] * np.linalg.norm(seg[ib], axis=1)
    return z


def graft_pack(drivers, rec, arm, size, w=0.0, dressing=0.0, harmonize=0.0):
    """the GRAFT pack (§2.8), RGBA uint8 in image order: R w (the donor class weight), G the dressing mask, B the
    harmonize weight the runtime palette uses, A z / L_band (0 at the ring, 1 at the band's end and beyond; the texel's
    block-out point's arc length along the arm against the ring's). w, dressing, harmonize are constants for M1a (0:
    identity). Texels the low does not cover take 0 (the runtime samples covered texels only)"""
    base = np.asarray(drivers['base'], np.float64)
    cov = (np.asarray(drivers['normal'])[..., 3] > 0) & (base[..., 3] > 0.5)
    z = arm_share_length(base[..., :3][cov], arm)
    z_ring = arm_share_length(np.asarray(rec['frame']['creature']['origin'])[None], arm)[0]
    A = np.clip((z - z_ring) / band_length(rec), 0.0, 1.0)
    out = np.zeros((size, size, 4), np.float64)
    out[..., 0], out[..., 1], out[..., 2] = w, dressing, harmonize
    out[..., :3] *= cov[..., None]
    out[..., 3][cov] = A
    return np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)


# ============================================================================================ the suckers
def native_suckers(base_dir, base, rec, spec, order, log=print):
    """the geometric suckers the graft drops (§2.1: rooted beyond the ring) and the base primitive's triangles and
    vertices that are theirs: octopus_suckers.part_mesh's instances and per-vertex instance ids (topological: the
    base glb's sucker primitive is part_mesh's arrays in order). Returns dict(I, S (part_mesh's mesh), ids (instances
    dropped), tri (the base primitive's triangles), verts)"""
    from .species import octopus_suckers as OS
    L = base['low']
    low = dict(V=L['V'], F=L['F'])
    I, S = OS.part_mesh(low, order, spec, base_dir, log=lambda *a: None)
    sp = base['prims']['octopus_suckers']
    Fs = sp['F']
    # the glb's vertices are part_mesh's, in order (positions to float32); its TRIANGLES are the glb's own: the
    # template's near-symmetric quads split along the shorter diagonal, a float tie the device decides (the canonical
    # was exported on the GPU; 28 % of its sucker quads split the other way on the CPU)
    Vg = base['G']['accessor'](sp['attrs']['POSITION']).astype(np.float64)
    assert len(S['V']) == len(Vg) and np.abs(S['V'] - Vg).max() < 1e-6, 'part_mesh\'s suckers are not the glb\'s'
    jn = int(rec['chain'][3:])
    # rooted beyond the ring, or referencing a joint the graft removes (the review's R5: the native group by
    # influence; a sucker rooted just before the ring whose footprint reaches over the band takes weight from the
    # band's triangles: kept, it would name a joint the crossbreed no longer has)
    beyond = (I['arm'] == jn) & (I['s'] > rec['st_s'])
    Jb = base['G']['accessor'](sp['attrs']['JOINTS_0']).astype(np.int64)
    Wb = base['G']['accessor'](sp['attrs']['WEIGHTS_0'])
    nat = [base['jnames'].index(n) for n in rec['native']['joints']]
    refs = np.zeros(len(I['d']), bool)
    refs[np.unique(S['inst'][(np.isin(Jb, nat) & (Wb > 0)).any(1)])] = True
    ids = np.nonzero(beyond | refs)[0]
    vin = np.isin(S['inst'], ids)
    tri = np.nonzero(vin[Fs].all(1))[0]
    assert (vin[Fs].any(1) == vin[Fs].all(1)).all(), 'a sucker triangle straddles two instances'
    log(f'[graft] native suckers: {len(ids)} instances ({int(beyond.sum())} rooted beyond the ring, '
        f'{int((refs & ~beyond).sum())} before it referencing {rec["native"]["joints"][0]}..: ids '
        f'{np.nonzero(refs & ~beyond)[0].tolist()}), {int(vin.sum())} vertices, {len(tri)} triangles')
    return dict(I=I, S=S, ids=ids, tri=tri, verts=np.nonzero(vin)[0], beyond=int(beyond.sum()),
                by_influence=np.nonzero(refs & ~beyond)[0].tolist())


def part_suckers(base, ns, plow, maps, joint_names, mode='generate', log=print):
    """the PART'S OWN geometric suckers (the native group's instances), its own primitive on the base's sucker
    material (one stacked template set: no new texels). 'copy' (M0): the base primitive's vertices (positions,
    normals, tangents, UVs, weights) copied; 'generate' (M1a): octopus_suckers.build_mesh on the part's low (its base
    rings conformed onto the part, its weights interpolated from the part's), the native draws of every instance kept
    (build_mesh runs on all instances so its seeded draws are the native's). Both take COLOR_0 from the PART'S own maps
    (skin_colours on the part's low and atlas). Returns dict(V, N, TAN, UV (forge v-up), F, J (names), W, COLOR)"""
    from .species import octopus_suckers as OS
    I, ids = ns['I'], ns['ids']
    sub = {k: (v[ids] if isinstance(v, np.ndarray) and len(v) == len(I['d']) else v) for k, v in I.items()}
    low_ray = dict(V=plow['V'], F=plow['F'], UV=plow['UV'], face_set=np.array(['part'] * len(plow['F'])))
    colours = OS.skin_colours(sub, low_ray, {'part': maps['albedo']}, {'part': maps['display']}, log=log)
    if mode == 'copy':
        sp = base['prims']['octopus_suckers']['attrs']
        acc = base['G']['accessor']
        v = ns['verts']
        remap = -np.ones(len(ns['S']['V']), np.int64)
        remap[v] = np.arange(len(v))
        F = remap[base['prims']['octopus_suckers']['F'][ns['tri']]]
        J = acc(sp['JOINTS_0'])[v].astype(np.int64)
        uv = acc(sp['TEXCOORD_0'])[v].astype(np.float64)
        inst_of = {int(x): k for k, x in enumerate(ids)}
        col = colours[[inst_of[int(x)] for x in ns['S']['inst'][v]]]
        return dict(V=acc(sp['POSITION'])[v].astype(np.float64), N=acc(sp['NORMAL'])[v].astype(np.float64),
                    TAN=acc(sp['TANGENT'])[v].astype(np.float64), UV=np.column_stack([uv[:, 0], 1.0 - uv[:, 1]]),
                    F=F, J=np.array([[base['jnames'][int(x)] for x in row] for row in J]),
                    W=acc(sp['WEIGHTS_0'])[v].astype(np.float64), COLOR=col.astype(np.float32))
    # generate: the template's own build on the part's low, skinned by the part's weights (chain columns)
    W24 = plow['W24']
    from . import rig as RG
    J4, W4 = RG.limit_influences(W24, 4)
    low_s = dict(V=plow['V'], F=plow['F'], J=J4, W=W4)
    S = OS.build_mesh(I, low_s, log=lambda *a: None)
    vin = np.isin(S['inst'], ids)
    v = np.nonzero(vin)[0]
    remap = -np.ones(len(S['V']), np.int64)
    remap[v] = np.arange(len(v))
    tri = np.nonzero(vin[S['F']].all(1))[0]
    inst_of = {int(x): k for k, x in enumerate(ids)}
    col = colours[[inst_of[int(x)] for x in S['inst'][v]]]
    log(f'[graft] the part\'s own suckers rebuilt on its low: {len(ids)} instances, {len(v)} vertices, {len(tri)} '
        f'triangles (ray misses in the conform on these: {int((~np.isfinite(S["burial"])).sum())} of all)')
    return dict(V=S['V'][v], N=S['N'][v], TAN=S['TAN'][v], UV=S['UV'][v], F=remap[S['F'][tri]],
                J=np.array([[joint_names[int(x)] for x in row] for row in S['J'][v]]), W=S['W'][v].astype(np.float64),
                COLOR=col.astype(np.float32))


# ------------------------------------------------------------------ G-R13, SIZE MATCH (CROSS r1c loop 2, 11-12)
# Skye, 11-11: "also we need to do something about stize matching" / "like when limbs and heads and stuff are remixed, they
# should match the size of the animal". A donor part is sized to the HOST'S SLOT, never to the donor's own body: its LENGTH
# is the host's own part past the ring (the native limb, tail or head the graft drops), its ROOT sits in the host's ring,
# and it gets there by GENERATION on a re-proportioned chain (CROSSBREED §3: "never squashed"), so each visible segment
# keeps the donor's own slenderness within the bar. Three numbers, each with the miss that set its bar:
#   length  part / host's own past the ring, 0.85 .. 1.20. REROOT's first bug leg took its scale from the ring's girth alone
#           (the tibia's root 0.88 of the ring): 222 mm on a 92 mm limb slot, 2.42 x.
#   root    the part's girth where it leaves the host (a socket's lip, a weld's band end) / the ring's diameter, 0.50 .. 1.05.
#           r1b's leg at the host's length kept the beetle's girth: 0.19, the check's "toothpick in a sausage".
#   squash  per visible segment, (length / width) / the donor's own, 0.50 .. 2.00. r1c's leg filled the ring at the host's
#           length by one factor on its length alone: femur and tibia 0.18 of the beetle's slenderness, the check's "hoof".
SIZE_MATCH = dict(length=(0.85, 1.20), root=(0.50, 1.05), squash=(0.50, 2.00))


def slot_measure(chain, ring_name, joint_pos, tip_pos, ring_origin, ring_r=None):
    """THE HOST'S OWN PART PAST A RING, what a donor part at that ring is sized to. chain: the host's chain record (extras.
    bestiary.chains: joints, s, radius, cuts); ring_name: one of its cuts' rings; joint_pos {joint name: (3,) world};
    tip_pos (3,) the chain's tip (its socket), or None (a chain with no tip record: the last joint ends it); ring_origin (3,)
    the ring record's origin; ring_r (m) the ring record's own mean radius when the caller has it (else the chain's radius
    interpolated at the cut's arc share: the axolotl's axilla reads 9.19 mm that way, its ring measures 9.80). Returns
    dict(length (m: the ring's origin, then the chain's joints from the cut's joint on, to the tip), joints [names past the
    ring], share [each one's arc share of that length, 0 at the ring .. 1 at the tip], radius [the chain's own radius at
    each: the host's girth along what the part replaces], ring_d (m))"""
    cut = next(c for c in chain['cuts'] if c.get('ring') == ring_name)
    k = int(cut['joint'])
    names = list(chain['joints'][k:])
    pts = [np.asarray(ring_origin, np.float64)] + [np.asarray(joint_pos[n], np.float64) for n in names]
    if tip_pos is not None:
        pts.append(np.asarray(tip_pos, np.float64))
    seg = np.linalg.norm(np.diff(np.array(pts), axis=0), axis=1)
    L = float(seg.sum())
    arc = np.cumsum(seg)[:len(names)] / max(L, 1e-12)
    rad = [float(r) for r in chain['radius'][k:]]
    if ring_r is None:
        s, r = chain['s'], chain['radius']
        t = (float(cut['s']) - s[k - 1]) / max(s[k] - s[k - 1], 1e-12) if k > 0 else 0.0
        ring_r = (1.0 - t) * r[max(k - 1, 0)] + t * r[k]
    return dict(length=L, joints=names, share=[float(a) for a in arc], radius=rad, ring_d=2.0 * float(ring_r))


def slenderness(V, a, b):
    """a segment's length / width as the quality check measured it (remix_r1/check_quality_r1c_1/tools/p_seg_proportions.py):
    joint to joint (a -> b) over the largest extent of its vertices V across that axis"""
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    L = float(np.linalg.norm(b - a))
    u = (b - a) / max(L, 1e-12)
    p = np.asarray(V, np.float64) - a
    perp = p - np.outer(p @ u, u)
    e1 = np.cross(u, [0.0, 0.0, 1.0] if abs(u[2]) < 0.9 else [1.0, 0.0, 0.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(u, e1)
    W = max(float(np.ptp(perp @ (np.cos(t) * e1 + np.sin(t) * e2))) for t in np.linspace(0.0, np.pi, 36, endpoint=False))
    return L / max(W, 1e-12)


def size_match(L_part, L_host, d_root, d_ring, seg=None, seg_donor=None, bars=None):
    """G-R13. L_part, L_host (m): the part from the ring to its tip, the host's own part past the ring (slot_measure);
    d_root, d_ring (m): the part's girth where it leaves the host, the ring's diameter; seg / seg_donor {segment: length /
    width} of the part's VISIBLE segments and of the donor's own (slenderness; both or neither). Returns dict(ok, length,
    root, squash {segment: ratio}, fails [str])"""
    b = dict(SIZE_MATCH, **(bars or {}))
    out = dict(length=float(L_part / L_host), root=float(d_root / d_ring), squash={}, fails=[])
    if not b['length'][0] <= out['length'] <= b['length'][1]:
        out['fails'].append(f'length {out["length"]:.2f} x the host\'s own part (bar {b["length"][0]} .. {b["length"][1]})')
    if not b['root'][0] <= out['root'] <= b['root'][1]:
        out['fails'].append(f'root {out["root"]:.2f} of the ring\'s diameter (bar {b["root"][0]} .. {b["root"][1]})')
    for nm in (seg or {}):
        if seg_donor and nm in seg_donor:
            r = float(seg[nm] / seg_donor[nm])
            out['squash'][nm] = r
            if not b['squash'][0] <= r <= b['squash'][1]:
                out['fails'].append(f'{nm} {r:.2f} of the donor\'s own slenderness ({seg[nm]:.2f} against '
                                    f'{seg_donor[nm]:.2f}; bar {b["squash"][0]} .. {b["squash"][1]})')
    out['ok'] = not out['fails']
    return out
