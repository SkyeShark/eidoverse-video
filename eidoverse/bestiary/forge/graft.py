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


def band_length(rec):
    """L_band = max(0.75 r, |dr|max / 0.25, two ring steps) (§2.7); the identity donor's |dr| is 0"""
    return max(0.75 * rec['r_mean'], 0.0 / 0.25, 2.0 * rec['h'])


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


def octopus_arm_rings(donor_arm, spec, stations, R=None, t=None, n_k=16, out=1.05):
    """the octopus arm's ring PROXIES (octopus.build_cage's arm loop, extracted): at each station s the 16 vertices
    c + 1.05 r(s) (cos a n + sin a b), a = -90 deg + k 22.5 deg, carried into the socket frame. Returns (m, 16, 3)"""
    from .species import octopus as O
    R = np.eye(3) if R is None else R
    t = np.zeros(3) if t is None else t
    alphas = np.radians(-90.0 + np.arange(n_k) * (360.0 / n_k))
    rings = []
    for s in stations:
        P, n, b, _ = arm_frame_at(donor_arm, s)
        ra = O.arm_radius(np.array([s]), spec)[0]
        ring = np.array([P + out * ra * (np.cos(a) * n + np.sin(a) * b) for a in alphas])
        rings.append(ring @ R.T + t)
    return np.array(rings)


# ============================================================================================ the part's cage
def part_cage(base, cage, rec, arms, spec, prog_low, mode='generate', fit_iters=6, log=print):
    """the part's QUAD cage from the apron's first ring to the tip cap, in the native cage's topology (the octopus
    arm's: so the part's quads correspond one for one with the native's, which the gates use):
      rings ic - apron .. ic - 1   the APRON (the base's own, baked and painted, never shipped)
      ring  ic                     THE RING (frozen bits)
      rings ic + 1 .. ic + nb      the BAND (the base's own loops: L_band / h of them)
      rings ic + nb + 1 ..         'generate' (M1a): the donor's generator in the socket frame, projected and relaxed
                                   by retopo.fit with the apron, ring and band FIXED; 'copy' (M0): the base's own
      the tip cap                  loft.cap over the last ring's proxies (dome 0.0008 along the tip's tangent), as the
                                   native cage was built, then fitted with the rings
    Positions of copied vertices come from the glb's float32 (the low's vertex for each cage id). Returns a dict"""
    from . import loft, retopo
    from .mesh import QuadMesh
    rings = cage['rings']
    ic, apron = int(rec['ring_index']), int(rec['apron_rings'])
    nb = int(round(band_length(rec) / rec['h']))
    i0, i_last = ic - apron, len(rings) - 1
    L = base['low']
    copies = {}
    for i in range(base['n_low']):
        copies.setdefault(int(L['orig'][i]), []).append(i)
    cage_ids = np.concatenate([np.asarray(rings[i]) for i in range(i0, i_last + 1)] + [np.asarray(cage['cap_v'])])
    local = {int(c): k for k, c in enumerate(cage_ids)}
    Q = np.array([[local[int(v)] for v in q] for q in cage['q_arm'] if all(int(v) in local for v in q)])
    ring_no = np.full(len(cage_ids), -1)
    for i in range(i0, i_last + 1):
        for c in rings[i]:
            ring_no[local[int(c)]] = i
    is_cap = ring_no < 0
    base_pos = np.array([base['V32'][copies[int(c)][0]] for c in cage_ids]).astype(np.float64)
    st = cage['st'][cage_ids]
    fixed = (ring_no >= 0) & (ring_no <= ic + nb)
    V = base_pos.copy()
    fit_stats = None
    if mode == 'generate':
        donor = arms[cage['order'][int(rec['chain'][3:])]]
        R, t = socket_map(rec, donor, rec['st_s'])
        assert np.abs(R - np.eye(3)).max() < 1e-12 and np.abs(t).max() < 1e-12, \
            'M1a grafts the arm onto its own ring: the socket map must be the identity'
        gen = [i for i in range(ic + nb + 1, i_last + 1)]
        # the generator runs from SUPPORT rings behind its root (the donor's own proxies, the farthest one fixed), so
        # retopo.fit's relaxation, which reaches one ring per round, meets the donor's first kept ring in its native
        # context: fixed at the band's final bits instead, the ring beside it took a different relaxation target
        # (153 um off the native on the CPU dry run); the support rings are dropped after the fit
        n_sup = fit_iters + 1
        sup = list(range(gen[0] - n_sup, gen[0]))
        allr = sup + gen
        stations = [float(cage['ring_s'][i]) for i in allr]
        P = octopus_arm_rings(donor, spec, stations, R, t)
        ids = np.concatenate([np.asarray(rings[i]) for i in allr] + [np.asarray(cage['cap_v'])])
        lf = {int(c): k for k, c in enumerate(ids)}
        Vf = np.zeros((len(ids), 3))
        for i, ring in zip(allr, P):
            for k, c in enumerate(rings[i]):
                Vf[lf[int(c)]] = ring[k]
        Qf = np.array([[lf[int(v)] for v in q] for q in cage['q_arm'] if all(int(v) in lf for v in q)])
        # the tip cap over the last ring's PROXIES (build_cage caps before the fit), its axis the tip's tangent
        nr = len(ids) - len(cage['cap_v'])
        tmp = QuadMesh(Vf[:nr].copy(), Qf[:0], {})
        last = np.array([lf[int(c)] for c in rings[i_last]])
        _, _, _, ta = arm_frame_at(donor, 0.999)
        capped, grid = loft.cap(tmp, last, R @ ta, dome=0.0008)
        new = capped.V[nr:]
        assert len(new) == len(cage['cap_v']), (len(new), len(cage['cap_v']))
        Vf[nr:] = new                            # (creation order = the cage's cap ids' order: sorted ascending)
        fx = np.zeros(len(ids), bool)
        fx[[lf[int(c)] for c in rings[sup[0]]]] = True
        mesh = QuadMesh(Vf, Qf, {})
        sdf = FramedSDF(prog_low, R, t)
        stat, acc = retopo.fit(mesh, sdf, iters=fit_iters, relax=0.5, fixed=fx)
        for c in np.concatenate([np.asarray(rings[i]) for i in gen] + [np.asarray(cage['cap_v'])]):
            V[local[int(c)]] = mesh.V[lf[int(c)]]
        fit_stats = dict(status=stat.tolist(), accepted=[round(a, 4) for a in acc], support=[sup[0], sup[-1]])
        d = np.linalg.norm(V - base_pos, axis=1)
        gm = ~fixed
        log(f'[graft] generated {len(gen)} rings + the cap by the octopus arm generator (identity socket map; support '
            f'rings {sup[0]}..{sup[-1]}), fitted: {fit_stats}; against the native low: max {d[gm].max() * 1e6:.2f} um, '
            f'p99 {np.percentile(d[gm], 99) * 1e6:.2f} um, median {np.median(d[gm]) * 1e6:.3f} um')
    return dict(V=V, Q=Q, cage_ids=cage_ids, ring_no=ring_no, is_cap=is_cap, st=st, fixed=fixed, i0=i0, ic=ic, nb=nb,
                i_last=i_last, base_pos=base_pos, mode=mode, fit=fit_stats, copies=copies)


def part_weights(base, part, rec, arms, cage, spec, mode='generate', smooth_iters=4):
    """weights on the chain's 24 joints (columns 0..23: arm<j>_00..arm<j>_cut are the base's, past the cut the graft's
    own joints at the donor's bind; M1a: the native positions). 'copy': the base's per vertex. 'generate': the apron,
    ring and band FROZEN (the base's bits: §2.6's Dirichlet boundary), the rest octopus_rig.weights' arm-tube rule
    (its share on the arm's centreline, rig.hat_weights over the joints' shares), smoothed over the part's cage with
    the frozen vertices pinned (rig.smooth_field), cut to 4 influences (rig.limit_influences). Returns (n, 24)"""
    from . import rig as RG
    from .species import octopus_rig as OR
    names = base['jnames']
    jn = rec['chain']
    col = {names.index(f'{jn}_{k:02d}'): k for k in range(OR.N_ARM_JOINTS)}
    n = len(part['V'])
    Wb = np.zeros((n, OR.N_ARM_JOINTS))
    for i, c in enumerate(part['cage_ids']):
        v = part['copies'][int(c)][0]
        for q in range(4):
            w = float(base['W32'][v, q])
            if w > 0.0:
                Wb[i, col[int(base['J'][v, q])]] += w           # (a weight off the chain would raise: none here)
    if mode == 'copy':
        return Wb
    js = OR.arm_joint_s(spec)
    Pa = arms[cage['order'][int(jn[3:])]][0]
    seg = Pa[1:] - Pa[:-1]
    V = part['V']
    q = V[:, None, :] - Pa[None, :-1, :]
    tseg = np.clip((q * seg[None]).sum(2) / (seg * seg).sum(1)[None], 0.0, 1.0)
    dist = np.linalg.norm(q - tseg[..., None] * seg[None], axis=2)
    ib = dist.argmin(1)
    s_on = (ib + tseg[np.arange(n), ib]) / (len(Pa) - 1)
    a, b, t = RG.hat_weights(s_on, js)
    W = np.zeros((n, OR.N_ARM_JOINTS))
    np.add.at(W, (np.arange(n), a), 1.0 - t)
    np.add.at(W, (np.arange(n), b), t)
    W /= np.maximum(W.sum(1, keepdims=True), 1e-12)
    fr = part['fixed']
    W[fr] = Wb[fr]
    W = RG.smooth_field(W, part['Q'], iters=smooth_iters, alpha=0.5, pinned=np.nonzero(fr)[0])
    J4, W4 = RG.limit_influences(W, 4)
    Wd = np.zeros_like(W)
    np.put_along_axis(Wd, J4.astype(np.int64), W4.astype(np.float64), axis=1)
    Wd[fr] = Wb[fr]                                       # the frozen bits exactly (the cut renormalises)
    return Wd


def part_normals(base, part, rec, mode='generate'):
    """vertex normals on the part's WELDED cage (mesh.vertex_normals, as t10's N_w), the apron, ring and band the
    base's frozen bits (the ring by §2.5; the apron and band are the base's own loops, whose welded normals the base
    computed with their whole neighbourhood); 'copy': every vertex the base's"""
    from .mesh import QuadMesh
    Nb = np.array([base['N32'][part['copies'][int(c)][0]] for c in part['cage_ids']]).astype(np.float64)
    if mode == 'copy':
        return Nb
    N = QuadMesh(part['V'], part['Q']).vertex_normals()
    fr = part['fixed']
    N[fr] = Nb[fr]
    return N


# ============================================================================================ islands and atlas
def part_islands(part, cage, seam_k=12):
    """the part's seams: the arm's oral midline (vertex seam_k of every ring), and loops at the native's own island
    cuts past the ring (octopus_uv: rings int(0.30 n), int(0.62 n), the tip's ring) so the donor keeps its native
    island shapes; the apron, ring and band share the STRIP island with the donor's first length"""
    rings = cage['rings']
    loc = {int(c): k for k, c in enumerate(part['cage_ids'])}
    S = []
    for i in range(part['i0'], part['i_last']):
        S.append((loc[int(rings[i][seam_k])], loc[int(rings[i + 1][seam_k])]))
    cuts = [int(cage['i30']), int(cage['i62']), part['i_last']]
    for i in cuts:
        if part['i0'] < i <= part['i_last']:
            r = [loc[int(c)] for c in rings[i]]
            S += [(r[m], r[(m + 1) % len(r)]) for m in range(len(r))]
    return S, [i for i in cuts if part['i0'] < i <= part['i_last']]


def strip_base_corners(base, part, Qn, orig, strip):
    """THE BASE LOW'S OWN VERTEX for every split vertex of the STRIP island (its quads `strip` in Qn), corner by
    corner: each part quad is a native quad (the same cage ids), whose base-low corners (the split copy on the same side
    of the oral seam: the one sharing a base triangle with the quad's other corners) carry the base set's UVs and the
    base's shipped frames. Returns {split vertex: base low vertex}; raises where a corner has no native counterpart (a
    donor's ring past the band: the conformal continuation is M1b's)"""
    L = base['low']
    cid = part['cage_ids'][orig]                     # each split vertex's native cage id
    F = L['F']
    tri_of = {}
    for t, f in enumerate(F.tolist()):
        tri_of.setdefault(tuple(sorted(L['orig'][f].tolist())), []).append(t)
    out = {}
    for q in strip:
        corners = Qn[q]
        cc = [int(cid[v]) for v in corners]
        # the base triangles on this quad (either diagonal): their corner low ids by cage id
        cand = [t for tri in ((cc[0], cc[1], cc[2]), (cc[0], cc[2], cc[3]), (cc[0], cc[1], cc[3]), (cc[1], cc[2], cc[3]))
                for t in tri_of.get(tuple(sorted(tri)), [])]
        if not cand:
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
        bcor = strip_base_corners(lattice['base'], part, Qn, orig, sq)
        sv = np.array(sorted(bcor))
        base_v = np.array([bcor[v] for v in sv])
        Tb = lattice['base']['low']['UV'][base_v] * lattice['base_size']
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
