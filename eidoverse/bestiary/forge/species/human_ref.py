"""HUMAN H1: the REFERENCES the baseline cages are fitted to (HUMAN_PLAN §2.5; the lead's H1 decisions, 10-28).

HEAD: GNM Head v3 (Apache-2.0, work/bestiary/research/human_web/gnm_head_v3, read as data with numpy, allow_pickle=False;
never the gnm package) CONDITIONED PER SEX: the identity coefficients of least norm (GNM's 170 head components are unit
normal, so the norm is the Mahalanobis distance from GNM's mean) whose head hits the sex's measured head means (SPEC head,
B §4.1) and the baseline body's neck circumference (SPEC reg, the ANSUR regression at the baseline's stature and BMI 25),
by Gauss-Newton on the measures linearised at the current head (they are distances, a tape perimeter and an arc: not
linear in the coefficients). GNM's mesh is linear in its coefficients, so every point placed in GNM's chart is a FIXED
BARYCENTRIC point whatever the identity (plan §3.2).

BODY: the MakeHuman / MPFB2 base mesh hm08 (CC0, human_web/makehuman_mpfb2, data only) at the sex's young adult phenotype
(its own macro targets: race-gender-age, the three races at MakeHuman's default third each, average muscle and weight, whose
universal targets are empty at that point), then PINNED to ANSUR II's baseline body (plan §2.5's simpler route: the
reference deformed to the measures, then the cage fitted to it): the heights of the landmark loops, the arm's segment
lengths, the girths, breadths and depths at their stations. Its landmarks come from SURFACE rules (the H0 review: H0's
rules took the knee, hip, ankle and shoulder landmarks from the rig's joint cubes, so its 'heights as a share of stature'
measured MakeHuman's rig, not its body).

UNITS: millimetres; the forge's frame (+Y up, +Z forward, +X the creature's LEFT); MakeHuman's decimetres are scaled by
100 and its ground (joint-ground) put at y 0.
"""
import gzip
import json
import os
import site
import sys

sys.path.append(site.getusersitepackages())
import numpy as np
import scipy.sparse as sp

from . import human as HS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
WEB = os.path.join(ROOT, 'work', 'bestiary', 'research', 'human_web')
GNM_NPZ = os.path.join(WEB, 'gnm_head_v3', 'gnm_head.npz')
MH_DIR = os.path.join(WEB, 'makehuman_mpfb2', 'data')
H0_LANDMARKS = os.path.join(ROOT, 'work', 'bestiary', 'human', 'h0', 'landmarks')
VERSION = 'h1-ref-v1'
N_HEAD = 170                                   # GNM's head components (identity_names head_000 .. head_169)


# ============================================================================================ warp helpers
_W = {}


def warp():
    if 'wp' not in _W:
        import warp as wp
        wp.config.quiet = True
        wp.init()
        _W['wp'] = wp
        _W['dev'] = 'cuda:0' if wp.is_cuda_available() else 'cpu'

        @wp.kernel
        def k_closest(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), maxd: float, outp: wp.array(dtype=wp.vec3),
                      outf: wp.array(dtype=int), outb: wp.array(dtype=wp.vec3)):
            i = wp.tid()
            q = wp.mesh_query_point_no_sign(mesh, pts[i], maxd)
            if q.result:
                outp[i] = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
                outf[i] = q.face
                outb[i] = wp.vec3(q.u, q.v, 1.0 - q.u - q.v)
            else:
                outp[i] = wp.vec3(1.0e9, 1.0e9, 1.0e9)
                outf[i] = -1
                outb[i] = wp.vec3(0.0, 0.0, 0.0)

        @wp.kernel
        def k_ray(mesh: wp.uint64, org: wp.array(dtype=wp.vec3), dirs: wp.array(dtype=wp.vec3), maxt: float,
                  outt: wp.array(dtype=float), outf: wp.array(dtype=int), outb: wp.array(dtype=wp.vec3)):
            i = wp.tid()
            q = wp.mesh_query_ray(mesh, org[i], dirs[i], maxt)
            if q.result:
                outt[i] = q.t
                outf[i] = q.face
                outb[i] = wp.vec3(q.u, q.v, 1.0 - q.u - q.v)
            else:
                outt[i] = -1.0
                outf[i] = -1
                outb[i] = wp.vec3(0.0, 0.0, 0.0)
        _W['closest'] = k_closest
        _W['ray'] = k_ray
    return _W['wp'], _W['dev']


class TriMesh:
    """a triangle mesh on Warp's device (mm): closest points and rays, returning (point, face, barycentric)"""

    def __init__(self, V, F):
        wp, dev = warp()
        self.V = np.asarray(V, np.float64)
        self.F = np.asarray(F, np.int64)
        self.mesh = wp.Mesh(points=wp.array(self.V.astype(np.float32), dtype=wp.vec3, device=dev),
                            indices=wp.array(self.F.astype(np.int32).ravel(), dtype=wp.int32, device=dev))

    def closest(self, P, maxd=1.0e4):
        wp, dev = warp()
        P = np.atleast_2d(np.asarray(P, np.float64))
        n = len(P)
        if n == 0:
            return np.zeros((0, 3)), np.zeros(0, np.int64), np.zeros((0, 3))
        pts = wp.array(P.astype(np.float32), dtype=wp.vec3, device=dev)
        op = wp.zeros(n, dtype=wp.vec3, device=dev)
        of = wp.zeros(n, dtype=int, device=dev)
        ob = wp.zeros(n, dtype=wp.vec3, device=dev)
        wp.launch(_W['closest'], dim=n, inputs=[self.mesh.id, pts, float(maxd), op, of, ob], device=dev)
        b = ob.numpy().astype(np.float64)
        f = of.numpy().astype(np.int64)
        # the barycentric weights refer to the face's corners (u, v, w) = corners (0, 1, 2); re-evaluate the point in
        # double precision from them
        p = np.einsum('nk,nkd->nd', b, self.V[self.F[np.maximum(f, 0)]])
        return p, f, b

    def ray(self, O, D, maxt=1.0e4):
        wp, dev = warp()
        O = np.atleast_2d(np.asarray(O, np.float64))
        D = np.atleast_2d(np.asarray(D, np.float64))
        D = D / np.maximum(np.linalg.norm(D, axis=1, keepdims=True), 1e-12)
        n = len(O)
        ot = wp.zeros(n, dtype=float, device=dev)
        of = wp.zeros(n, dtype=int, device=dev)
        ob = wp.zeros(n, dtype=wp.vec3, device=dev)
        wp.launch(_W['ray'], dim=n, inputs=[self.mesh.id, wp.array(O.astype(np.float32), dtype=wp.vec3, device=dev),
                                             wp.array(D.astype(np.float32), dtype=wp.vec3, device=dev), float(maxt),
                                             ot, of, ob], device=dev)
        t = ot.numpy().astype(np.float64)
        return t, of.numpy().astype(np.int64), ob.numpy().astype(np.float64)

    def normals(self):
        if not hasattr(self, '_vn'):
            fn = np.cross(self.V[self.F[:, 1]] - self.V[self.F[:, 0]], self.V[self.F[:, 2]] - self.V[self.F[:, 0]])
            vn = np.zeros_like(self.V)
            for k in range(3):
                np.add.at(vn, self.F[:, k], fn)
            self._vn = vn / np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
            self._fn = fn / np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
        return self._vn

    def face_normals(self):
        self.normals()
        return self._fn

    def normal_at(self, f, b):
        N = np.einsum('nk,nkd->nd', b, self.normals()[self.F[np.maximum(f, 0)]])
        return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)


# ============================================================================================ geometry helpers
def plane_section(V, F, origin, normal, keep=None):
    """the segments where the triangle mesh (V, F) crosses the plane (origin, normal): (S, 2, 3) and their faces"""
    n = np.asarray(normal, np.float64)
    n = n / np.linalg.norm(n)
    d = (V - origin) @ n
    Fs = F if keep is None else F[keep]
    dd = d[Fs]
    cross = (dd.min(1) < 0) & (dd.max(1) > 0)
    Fc = Fs[cross]
    D = dd[cross]
    P = V[Fc]
    segs = []
    for k0, k1 in ((0, 1), (1, 2), (2, 0)):
        s = (D[:, k0] < 0) != (D[:, k1] < 0)
        t = np.where(s, D[:, k0] / np.where(s, D[:, k0] - D[:, k1], 1.0), 0.0)
        segs.append((s, P[:, k0] + t[:, None] * (P[:, k1] - P[:, k0])))
    S = []
    for i in range(len(Fc)):
        pts = [seg[1][i] for seg in segs if seg[0][i]]
        if len(pts) == 2:
            S.append(pts)
    return np.array(S).reshape(-1, 2, 3), Fc


def plane_basis(normal, ref=None):
    n = np.asarray(normal, np.float64)
    n = n / np.linalg.norm(n)
    r = np.array([0.0, 0.0, 1.0]) if ref is None else np.asarray(ref, np.float64)
    r = r - (r @ n) * n
    if np.linalg.norm(r) < 1e-9:
        r = np.array([1.0, 0.0, 0.0]) - n[0] * n
    r = r / np.linalg.norm(r)
    return r, np.cross(n, r), n


def hull_perimeter(P2):
    """the convex hull's perimeter of 2-D points (a tape measure's length round a section)"""
    from scipy.spatial import ConvexHull
    P2 = np.asarray(P2, np.float64)
    if len(P2) < 3:
        return 0.0
    h = ConvexHull(P2)
    H = P2[h.vertices]
    return float(np.linalg.norm(np.diff(np.vstack([H, H[:1]]), axis=0), axis=1).sum())


def section_loops(S, tol=1e-4):
    """chain section segments (S, 2, 3) into polylines (loops), longest first"""
    if len(S) == 0:
        return []
    P = S.reshape(-1, 3)
    key = np.round(P / tol).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1, 2)
    adj = {}
    for a, b in inv.tolist():
        if a == b:
            continue
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    pos = {}
    for (a, b), (pa, pb) in zip(inv.tolist(), S):
        pos[a] = pa
        pos[b] = pb
    seen, loops = set(), []
    for s in adj:
        if s in seen:
            continue
        loop, prev, cur = [s], None, s
        seen.add(s)
        while True:
            nx = [v for v in adj[cur] if v != prev and v not in seen]
            if not nx:
                break
            prev, cur = cur, nx[0]
            loop.append(cur)
            seen.add(cur)
        loops.append(np.array([pos[v] for v in loop]))
    loops.sort(key=lambda L: -len(L))
    return loops


def girth(V, F, origin, normal, near=None, radius=None, ref=None):
    """the TAPE perimeter (convex hull) of the mesh's section by a plane; near/radius keep the segments within radius of
    a point (one limb's section, not its neighbour's)"""
    S, _ = plane_section(V, F, origin, normal)
    if len(S) == 0:
        return 0.0, np.zeros((0, 2))
    if near is not None:
        m = np.linalg.norm(S.mean(1) - np.asarray(near), axis=1) < radius
        S = S[m]
    e1, e2, n = plane_basis(normal, ref)
    P = S.reshape(-1, 3) - origin
    P2 = np.column_stack([P @ e1, P @ e2])
    return hull_perimeter(P2), P2


def vertex_normals(V, F):
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    vn = np.zeros_like(V)
    for k in range(3):
        np.add.at(vn, F[:, k], fn)
    return vn / np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)


def chain(edges, multi=False):
    adj = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen, loops = set(), []
    for s in adj:
        if s in seen:
            continue
        loop, prev, cur = [s], None, s
        seen.add(s)
        while True:
            nx = [v for v in adj[cur] if v != prev and v not in seen]
            if not nx:
                break
            prev, cur = cur, nx[0]
            loop.append(cur)
            seen.add(cur)
        loops.append(loop)
    if multi:
        return loops
    return max(loops, key=len)


# ============================================================================================ GNM
_GNM_DATA = {}


def gnm_data():
    """GNM's arrays (read once): template, bases, topology, groups, chart"""
    if not _GNM_DATA:
        z = np.load(GNM_NPZ, allow_pickle=False)
        d = _GNM_DATA
        d['T'] = z['template_vertex_positions'].astype(np.float64) * 1000.0
        d['B'] = z['vertex_identity_basis'][:N_HEAD].astype(np.float64) * 1000.0
        d['TJ'] = z['template_joint_positions'].astype(np.float64) * 1000.0
        d['BJ'] = z['joint_identity_basis'][:N_HEAD].astype(np.float64) * 1000.0
        d['joint_names'] = [str(s) for s in z['joint_names']]
        Q = z['quads'].astype(np.int64)
        QUV = z['quad_uvs'].astype(np.float64)
        gn = [str(s) for s in z['vertex_group_names']]
        d['grp'] = {n: z['vertex_groups'][i] > 0.5 for i, n in enumerate(gn)}
        sk = d['grp']['skin'][Q].all(1)
        d['Q'], d['QUV'] = Q[sk], QUV[sk]
        d['F'] = np.concatenate([d['Q'][:, [0, 1, 2]], d['Q'][:, [0, 2, 3]]])
        d['FUV'] = np.concatenate([d['QUV'][:, [0, 1, 2]], d['QUV'][:, [0, 2, 3]]])
        d['mirror'] = z['mirror_indices'].astype(np.int64)
        # the chart's islands: triangles joined across edges whose corners carry the same uvs on both sides; the
        # largest component is the main island, the second the mouth sock's (gnm_ref.py's rule)
        emap = {}
        for t, (f, A) in enumerate(zip(d['F'].tolist(), d['FUV'])):
            for k in range(3):
                a, b = f[k], f[(k + 1) % 3]
                ua, ub = A[k], A[(k + 1) % 3]
                if a > b:
                    a, b, ua, ub = b, a, ub, ua
                emap.setdefault((a, b), []).append((t, round(ua[0], 6), round(ua[1], 6), round(ub[0], 6), round(ub[1], 6)))
        from scipy.sparse.csgraph import connected_components
        r, c = [], []
        for lst in emap.values():
            if len(lst) == 2 and lst[0][1:] == lst[1][1:]:
                r.append(lst[0][0])
                c.append(lst[1][0])
        nt = len(d['F'])
        A_ = sp.csr_matrix((np.ones(len(r)), (r, c)), shape=(nt, nt))
        _, lab = connected_components(A_ + A_.T, directed=False)
        ids, cnt = np.unique(lab, return_counts=True)
        order = ids[np.argsort(-cnt)]
        d['island'] = np.where(lab == order[0], 0, np.where(lab == order[1], 1, 2))
    return _GNM_DATA


class GNMRef:
    """GNM's skin at an identity (mm): its chart (identity independent) and its surface (the identity's positions)"""

    def __init__(self, coeffs=None):
        d = gnm_data()
        self.coeffs = np.zeros(N_HEAD) if coeffs is None else np.asarray(coeffs, np.float64)
        self.V = d['T'] + np.tensordot(self.coeffs, d['B'], 1)
        J = d['TJ'] + np.tensordot(self.coeffs, d['BJ'], 1)
        self.joints = dict(zip(d['joint_names'], J))
        self.Q, self.QUV, self.F, self.FUV = d['Q'], d['QUV'], d['F'], d['FUV']
        self.grp, self.mirror, self.island = d['grp'], d['mirror'], d['island']
        self.sock_tri = self.island == 1
        self._tm = None

    # ---------------------------------------------------------------------------------- the surface
    @property
    def tm(self):
        if self._tm is None:
            self._tm = TriMesh(self.V, self.F)
        return self._tm

    def closest(self, P, mesh=None):
        m = self.tm if mesh is None else mesh
        return m.closest(P)

    def normal_at(self, f, b):
        return self.tm.normal_at(f, b)

    def bary_to_3d(self, f, b, V=None):
        V = self.V if V is None else V
        return np.einsum('nk,nkd->nd', b, V[self.F[f]])

    # ---------------------------------------------------------------------------------- the chart
    def _uvmesh(self, island):
        key = 'uv_' + island
        if key not in _GNM_DATA:
            ids = np.nonzero(self.island == (0 if island == 'main' else 1))[0]
            P = self.FUV[ids].reshape(-1, 2)
            P3 = np.column_stack([P, np.zeros(len(P))])
            _GNM_DATA[key] = (TriMesh(P3, np.arange(len(P3)).reshape(-1, 3)), ids)
        return _GNM_DATA[key]

    def uv_locate(self, UV, island='main'):
        m, ids = self._uvmesh(island)
        UV = np.atleast_2d(np.asarray(UV, np.float64))
        _, f, b = m.closest(np.column_stack([UV, np.zeros(len(UV))]), maxd=10.0)
        return ids[f], b

    def uv_to_3d(self, UV, island='main'):
        f, b = self.uv_locate(UV, island)
        return np.einsum('nk,nkd->nd', b, self.V[self.F[f]]), f, b

    def bary_to_uv(self, f, b):
        return np.einsum('nk,nkd->nd', b, self.FUV[f])

    def jac(self, f):
        A = self.FUV[f]
        X = self.V[self.F[f]]
        D2 = np.stack([A[:, 1] - A[:, 0], A[:, 2] - A[:, 0]], 2)
        D3 = np.stack([X[:, 1] - X[:, 0], X[:, 2] - X[:, 0]], 2)
        return D3 @ np.linalg.inv(D2)

    def vertex_uv(self, island='main'):
        uv = np.full((len(self.V), 2), np.nan)
        sel = self.island == (0 if island == 'main' else 1)
        for Fv, A in zip(self.F[sel], self.FUV[sel]):
            for k in range(3):
                if np.isnan(uv[Fv[k], 0]):
                    uv[Fv[k]] = A[k]
        return uv

    def border_loop(self, inner):
        qin = inner[self.Q].all(1)
        emap = {}
        for qi, q in enumerate(self.Q.tolist()):
            for k in range(4):
                a, b = q[k], q[(k + 1) % 4]
                emap.setdefault((min(a, b), max(a, b)), []).append(qi)
        edges = [(a, b) for (a, b), lst in emap.items() if len(lst) == 2 and qin[lst[0]] != qin[lst[1]]]
        return chain(edges)

    def boundary_loops(self, quad_mask=None):
        Q = self.Q if quad_mask is None else self.Q[quad_mask]
        emap = {}
        for q in Q.tolist():
            for k in range(4):
                a, b = q[k], q[(k + 1) % 4]
                emap[(min(a, b), max(a, b))] = emap.get((min(a, b), max(a, b)), 0) + 1
        return chain([e for e, c in emap.items() if c == 1], multi=True)

    def vertex_normals(self):
        return self.tm.normals()


# ============================================================================================ GNM's head measures
def gnm_landmarks():
    """the head landmarks on GNM's template by vertex id (H0's rules, work/bestiary/human/h0/landmarks.py), with two of
    them re-found by tighter rules: ZY (the soft-tissue zygion) and EN (the inner canthus, from the lid shape)"""
    if 'lm' in _GNM_DATA:
        return _GNM_DATA['lm']
    js = json.load(open(os.path.join(H0_LANDMARKS, 'gnm_landmarks.json'), encoding='utf-8'))
    L = {k: int(v['vertex']) for k, v in js['head'].items()}
    d = gnm_data()
    V = d['T']
    grp = d['grp']
    mir = d['mirror']
    ext = grp['skin_exterior'] & ~grp['ears']
    # ZY: H0's rule (the most lateral point between the heights of prn and se, in front of the ear) lands at the temple
    # beside the ear's top (y 293.8, 12 mm in front of tragion): the pre-auricular bulge above the arch, which reads the
    # face 149 mm wide (ANSUR women 133.8, men 142.6). The bizygomatic breadth is taken on the ARCHES (spreading caliper,
    # ANSUR II's definition): the most lateral skin point in the band from 4 mm under tragion to 10 mm over it, and at
    # least 15 mm in front of tragion (the palpable arch, not the tragus' soft tissue)
    t = V[L['t_L']]
    band = ext & (V[:, 0] > 0) & (V[:, 1] > t[1] - 4.0) & (V[:, 1] < t[1] + 10.0) & (V[:, 2] > t[2] + 15.0)
    ii = np.nonzero(band)[0]
    zy = int(ii[np.argmax(V[ii, 0])])
    L['zy_L'] = zy
    L['zy_R'] = int(mir[zy])
    # EN_C: the ENDOCANTHION, the inner commissure of the eye fissure (Farkas's en), H2b. H0's en (vertex 555) is the lid
    # margin loop's medial end, where the lids meet the globe; medial of it GNM's skin folds into a tapered recess, the
    # place of the caruncle and the lacrimal lake, which the scans caught as skin: the rings outside the margin wrap
    # round it with their corners stepping medially (20.2, 19.8, 19.0, 18.5, 18.2 mm on the H2b woman) and the fold's
    # tip, the commissure, is ring 5's corner, vertex 633, the recess's deepest point (h2b/scratch/p09_canthus.py,
    # p11_wedge.py). en-ex read at 555 was 22.4 / 23.6 mm against Farkas's 27.6-30.7
    L['en_c_L'] = 633
    L['en_c_R'] = int(mir[633])
    _GNM_DATA['lm'] = L
    return L


def _section_perimeter(V, F, origin, normal, centre, radius):
    S, _ = plane_section(V, F, origin, normal)
    if len(S) == 0:
        return 0.0
    m = np.linalg.norm(S.mean(1) - centre, axis=1) < radius
    S = S[m]
    e1, e2, n = plane_basis(normal)
    P = S.reshape(-1, 3) - origin
    return hull_perimeter(np.column_stack([P @ e1, P @ e2]))


HEAD_MEASURES = ('head_length', 'head_breadth', 'head_circumference', 'tragion_top_of_head', 'face_width', 'jaw_width',
                 'face_length', 'nose_length', 'nose_breadth', 'nose_protrusion', 'mouth_width', 'interpupillary',
                 'ear_length', 'neck_circumference')
# measures a conditioning may add (condition_gnm's extra), with SPEC head's Farkas NAW means: the INTERCANTHAL width
# between the endocanthions (en_c; F 31.6 (2.4), M 32.9 (2.7)) and the BIOCULAR width between the exocanthions (F 86.8
# (4.0), M 89.4 (3.6)), each ex read where plan §3.3's lid rule puts it (moved radially onto the lid sphere fitted to
# its margin, human_head.lid_rule: it pulls the canthi ~0.5-0.8 mm in), so the fissure's two ends meet Farkas's two
# norms as the clay carries them. H2b conditions on both: at the 14 measures GNM's sex means put the commissures
# 36.3 / 38.2 mm apart, the fissures 24.8 / 26.2 mm long and 8.1 / 8.2 mm tall; the intercanthal alone gave 31.6 /
# 32.9 apart, 27.6 / 28.9 long, 10.3 / 10.6 tall, then the lid rule took the woman's en-ex to 27.2 (her biocular
# 86.7 -> 85.8; h2b/scratch/p12_intercanthal.py, logs/run_h2b_gates.txt of the first build)
HEAD_EXTRA = ('intercanthal', 'biocular')
# and what those two widths must NOT move (condition_gnm's hold): GNM's space lengthens a fissure by opening it (8.1 ->
# 11.0 mm tall) and flattening the lower lid's fold (2.2 -> 1.2 mm), and the eyes read large and tired on the clay
# (h2b/look/faces_clay.png of the second build; scratch/p15_fissure_hold.py). Held at the values the 14 measures leave
# (a first conditioning without the extras), the fissure only lengthens: the eyes keep the almond H1's heads had
#   fissure_height  the left lid margin's upper middle vertex over its lower middle vertex (GNM 1034, 1022: the margin
#                   loop's vertices nearest the mid-x of en and ex, above and below), in y
#   lid_fold        the infraorbital skin 4.2 mm under the lower margin's middle (GNM 1216: the most anterior exterior
#                   vertex 3.5-6.5 mm under 1022 within 1.5 mm of its x) ahead of that margin vertex, in z
#   groove_z        (the H2b review) the lid-cheek groove: the infraorbital skin 12 mm under 1022 (GNM 4751: the most
#                   anterior skin_exterior vertex of GNM's template within 1.5 mm of 1022's x and 1 mm of that height)
#                   ahead of 1022, in z
#   cheek_z         the cheek's front 24 mm under 1022 (GNM 676, the same rule), ahead of it, in z
# Without the last two the widths still hollowed the eyes: the groove under the chord from the lower lid's roll to the
# cheek's front 25 mm down (F / M, on the head as the clay carries it, after human_head.head_rules) went 3.2 / 3.4 mm
# (the 14 measures alone) -> 6.4 / 6.4, the cheek's front falling from 4.9 / 3.3 to 2.4 / 0.5 mm ahead of the margin: a
# proud lower lid over a dark hollow, tired eyes on the clay and in the turntable (scratch_h2b_review/p02_eyes.py,
# p06_eye_holds.py). GNM's own people never do that: over 2000 of the sampler's draws per sex the groove reads p50 2.6 /
# 2.8, MAX 5.2 / 5.5 mm (H1 2.5 / 3.3, the sex means 2.5 / 2.8), so 6.4 was deeper than every draw; held, it reads
# 3.6 / 4.1 (8.6 / 5.6 % of draws as deep) and the cheek's front 4.5 / 3.9 (p32 / p39) with every other measure still
# met (scratch_h2b_review/p07_groove_spread.py). The faces sit further out in the sex's spread (Mahalanobis F 17.5 ->
# 19.0, M 14.9 -> 16.3: p98 / p90 of the sampler's own draws) but nearer a real GNM face on the surface (the nearest
# of 4000 draws F 2.39 -> 2.27, M 2.13 -> 2.07 mm rms; p01_face_prior.py)
HEAD_HOLD = dict(fissure_height=0.8, lid_fold=0.8, groove_z=0.8, cheek_z=0.8)
EYE_V = dict(upper_mid=1034, lower_mid=1022, infraorbital=1216, groove=4751, cheek=676)
_MARGIN = {}


def _margin_v():
    """H0's lid margin loop (left eye, GNM vertex ids)"""
    if 'v' not in _MARGIN:
        _MARGIN['v'] = np.asarray(np.load(os.path.join(ROOT, 'work', 'bestiary', 'human', 'h0', 'probe1',
                                                       'gnm_features.npz'))['margin_v'], np.int64)
    return _MARGIN['v']


def ex_on_lid_sphere(V, side='L', globe=24.156, lid=1.0):
    """the exocanthion where the lid rule puts it: ex moved radially onto the lid sphere fitted to its eye's margin"""
    mv = _margin_v() if side == 'L' else gnm_data()['mirror'][_margin_v()]
    c, _ = fit_globe(V[mv], globe, lid)
    L = gnm_landmarks()
    ex = np.asarray(V[L['ex_' + side]], np.float64)
    return c + (ex - c) * ((globe / 2.0 + lid) / np.linalg.norm(ex - c))


def neck_plane(joints):
    """the mid-neck plane: through the midpoint of GNM's neck and head joints, normal along the neck's axis (the
    perpendicular cut ANSUR's neck circumference takes, below the laryngeal prominence)"""
    a, b = np.asarray(joints['neck']), np.asarray(joints['head'])
    n = (b - a) / np.linalg.norm(b - a)
    return 0.5 * (a + b), n


def head_measures(V, joints, F=None, L=None):
    """the 14 conditioning measures (mm) of a GNM head (V in GNM's topology): landmark distances by fixed vertex ids
    (gnm_landmarks), head circumference as the tape round the plane through glabella and opisthocranion (left-right
    horizontal), the neck's tape round the mid-neck plane, interpupillary from the eye joints; and HEAD_EXTRA's"""
    L = gnm_landmarks() if L is None else L
    F = gnm_data()['F'] if F is None else F
    p = lambda k: V[L[k]]                     # noqa: E731
    d = lambda a, b: float(np.linalg.norm(p(a) - p(b)))   # noqa: E731
    m = dict(head_length=d('g', 'op'), head_breadth=d('eu_L', 'eu_R'), face_width=d('zy_L', 'zy_R'),
             jaw_width=d('go_L', 'go_R'), face_length=d('se', 'me'), nose_length=d('se', 'sn'),
             nose_breadth=d('al_L', 'al_R'), nose_protrusion=d('prn', 'sn'), mouth_width=d('ch_L', 'ch_R'),
             ear_length=d('sa_L', 'sba_L'), tragion_top_of_head=float(V[L['v'], 1] - V[L['t_L'], 1]),
             interpupillary=float(np.linalg.norm(np.asarray(joints['left_eye']) - np.asarray(joints['right_eye']))),
             intercanthal=d('en_c_L', 'en_c_R'),
             biocular=float(np.linalg.norm(ex_on_lid_sphere(V, 'L') - ex_on_lid_sphere(V, 'R'))),
             fissure_height=float(V[EYE_V['upper_mid'], 1] - V[EYE_V['lower_mid'], 1]),
             lid_fold=float(V[EYE_V['infraorbital'], 2] - V[EYE_V['lower_mid'], 2]),
             groove_z=float(V[EYE_V['groove'], 2] - V[EYE_V['lower_mid'], 2]),
             cheek_z=float(V[EYE_V['cheek'], 2] - V[EYE_V['lower_mid'], 2]))
    g, op = p('g'), p('op')
    ax = (op - g) / np.linalg.norm(op - g)
    nrm = np.cross(ax, np.array([1.0, 0.0, 0.0]))
    m['head_circumference'] = _section_perimeter(V, F, 0.5 * (g + op), nrm, 0.5 * (g + op), 160.0)
    o, n = neck_plane(joints)
    m['neck_circumference'] = _section_perimeter(V, F, o, n, o, 95.0)
    return m


# the sex-dimorphic face measures (H2b, the lead's call 1) and their norms where a source gives them: Farkas 1994's North
# American White young adults via Chandra et al. 2012 (research/human_work/data/literature_values.json: farkas_naw_18_25;
# soft-tissue nasion read at our sellion, gnathion at our menton). The rest are read for their DIRECTION only (the men's
# brow ridge, chin, lower face and forehead slope larger, the gonial angle smaller), with no norm cited here
FACE_NORMS = dict(lower_face_height=dict(F=(65.5, 4.5), M=(71.9, 6.0)), upper_face_height=dict(F=(68.1, 3.4),
                                                                                              M=(74.0, 4.2)),
                  upper_lip_height=dict(F=(19.6, 2.4), M=(21.8, 2.0)), lower_vermilion=dict(F=(9.7, 1.6),
                                                                                          M=(10.4, 1.9)),
                  upper_vermilion=dict(M=(8.9, 1.5)), fissure_length=dict(F=(27.6, 30.7), M=(27.6, 30.7)))
FACE_DIRECTION = dict(brow_ridge=+1, brow_overhang=+1, chin_height=+1, lower_face_height=+1, forehead_slope=+1,
                      gonial_angle=-1)


def face_shape_measures(V, L=None):
    """the dimorphic shape of a head in GNM's topology (mm, degrees). The profile's frame: the horizontal h runs from the
    tragion to the sellion in the sagittal (y, z) plane, the vertical u perpendicular to it (up); a stand-in for the
    Frankfort plane, so the angles do not depend on how GNM poses the head.
      brow_ridge        the glabella in front of the sellion along h (the midline's soft-tissue prominence)
      brow_overhang     the left brow region's most anterior point in front of the left cornea's apex along h (the
                        supraorbital ridge over the eye: the deeper-set eye)
      forehead_slope    the angle back from u of the line from the glabella to the forehead's midline skin 40 mm up u
      chin_height       sublabiale to menton (Farkas's sl-gn); chin_projection the pogonion in front of the sublabiale
      lower_face_height subnasale to menton (sn-gn); upper_face_height sellion to stomion (n-sto)
      upper_lip_height  sn-sto; upper_vermilion ls-sto; lower_vermilion sto-li
      gonial_angle      the angle at the gonion between the tragion and the menton, in the sagittal projection (a
                        soft-tissue PROXY of the mandibular angle: the tragion is not on the ramus)
      fissure_length    en-ex (left), en at the commissure (en_c: gnm_landmarks' note)
      margin_length     H0's en (the lid margin's medial end, at the globe) to ex: the visible globe's span"""
    L = gnm_landmarks() if L is None else L
    p = lambda k: np.asarray(V[L[k]], np.float64)          # noqa: E731
    yz = lambda a: np.array([a[1], a[2]])                   # noqa: E731
    h = yz(p('se')) - yz(p('t_L'))
    h /= np.linalg.norm(h)
    u = np.array([h[1], -h[0]])
    if u[0] < 0:
        u = -u
    m = dict(brow_ridge=float((yz(p('g')) - yz(p('se'))) @ h),
             chin_height=float(np.linalg.norm(p('sl') - p('me'))),
             chin_projection=float((yz(p('pg')) - yz(p('sl'))) @ h),
             lower_face_height=float(np.linalg.norm(p('sn') - p('me'))),
             upper_face_height=float(np.linalg.norm(p('se') - p('sto'))),
             upper_lip_height=float(np.linalg.norm(p('sn') - p('sto'))),
             upper_vermilion=float(np.linalg.norm(p('ls') - p('sto'))),
             lower_vermilion=float(np.linalg.norm(p('sto') - p('li'))),
             fissure_length=float(np.linalg.norm(p('en_c_L') - p('ex_L'))),
             margin_length=float(np.linalg.norm(p('en_L') - p('ex_L'))))
    a, b = yz(p('t_L')) - yz(p('go_L')), yz(p('me')) - yz(p('go_L'))
    m['gonial_angle'] = float(np.degrees(np.arccos(a @ b / np.linalg.norm(a) / np.linalg.norm(b))))
    d = gnm_data()
    fwd = lambda ids: float((np.column_stack([V[ids, 1], V[ids, 2]]) @ h).max())     # noqa: E731
    m['brow_overhang'] = fwd(np.nonzero(d['grp']['left_brow_region'])[0]) - \
        fwd(np.nonzero(d['grp']['left_eye'] & d['grp']['eye_exteriors'])[0])
    # the forehead: GNM's midline exterior vertices in front of the ear, 40 mm up u from the glabella (+-4 mm), the most
    # anterior along h
    mid = (d['mirror'] == np.arange(len(V))) & d['grp']['skin_exterior']
    ii = np.nonzero(mid)[0]
    Y = np.column_stack([V[ii, 1], V[ii, 2]]) - yz(p('g'))
    up, fw = Y @ u, Y @ h
    sel = (np.abs(up - 40.0) < 4.0) & (fw > -40.0)
    k = ii[sel][np.argmax(fw[sel])]
    f = yz(np.asarray(V[k], np.float64)) - yz(p('g'))
    m['forehead_slope'] = float(np.degrees(np.arctan2(-(f @ h), f @ u)))
    return m


def face_distance(Va, Vb, regions=None):
    """two heads in GNM's topology: face b similarity-aligned (rotation, translation, scale; Umeyama) onto face a over
    GNM's hockey mask, then the rms distance (mm) over the mask and over each named region (vertex masks, GNM indices)"""
    d = gnm_data()
    mask = d['grp']['hockey_mask']
    A, B = np.asarray(Va, np.float64)[mask], np.asarray(Vb, np.float64)[mask]
    ma, mb = A.mean(0), B.mean(0)
    A0, B0 = A - ma, B - mb
    U, S, Vt = np.linalg.svd(A0.T @ B0)
    D = np.eye(3)
    D[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt
    s = float(np.trace(np.diag(S) @ D) / (B0 ** 2).sum())
    e = np.linalg.norm(s * B0 @ R.T + ma - A, axis=1)
    out = dict(rms=float(np.sqrt((e ** 2).mean())), scale=s)
    sub = np.nonzero(mask)[0]
    for k, m in (regions or {}).items():
        sel = np.asarray(m)[sub]
        if sel.any():
            out[k] = float(np.sqrt((e[sel] ** 2).mean()))
    return out


def head_targets(sex):
    """the conditioning targets (mm) and their sds: the sex's head means (SPEC head), the baseline body's neck"""
    H = HS.SPEC['head'][sex]
    t, s = {}, {}
    for k in HEAD_MEASURES + HEAD_EXTRA:
        if k == 'neck_circumference':
            b = HS.SPEC['baseline'][sex]
            r = HS.SPEC['reg'][sex]['neckcircumference']
            t[k] = HS.predict(sex, 'neckcircumference', b['stature'], b['bmi'])
            s[k] = r[6]                      # the residual sd at a given stature and BMI
        else:
            t[k], s[k] = H[k][0], H[k][1]
    return t, s


def condition_gnm(sex, iters=8, eps=0.25, tol=0.02, log=print, prior=None, ridge=1e-3, extra=(), hold=()):
    """the identity (GNM's 170 head components, unit normal) whose head hits head_targets(sex): Gauss-Newton, each step
    meeting the measures linearised at the current head (finite differences, eps), to tol sd on every measure.
    prior None (H1): each step the least-NORM coefficients, i.e. the nearest head to GNM's sex-neutral mean.
    prior (mean, cov) (H2b, the lead's call 1: the sex's statistics from GNM's IdentitySampler, human_idsampler.
    sex_stats): the walk starts at the sex's MEAN FACE and each step takes the coefficients of least Mahalanobis distance
    from it under the sex's covariance (its diagonal raised by ridge x its mean eigenvalue, so no direction is quite
    free), c = mean + C J^T (J C J^T)^-1 (J c_now - z - J mean): the Gaussian prior's posterior mean given the measures
    (plan §3.2), so the shape the measures don't name (brow, chin, jaw angle) stays the sex's.
    extra: names from HEAD_EXTRA conditioned too (H2b: HEAD_EXTRA); hold: names from HEAD_HOLD held at the values a
    first conditioning on the 14 measures alone leaves (H2b: the eye's opening and the lower lid's fold).
    Returns dict(coeffs, rows (the measures at GNM's mean, at the prior's mean and after), norm (from GNM's mean),
    mahalanobis (from the prior's mean under its covariance, or None), history)"""
    d = gnm_data()
    tgt, sd = head_targets(sex)
    keys = list(HEAD_MEASURES) + [k for k in extra if k in HEAD_EXTRA]
    hold = [k for k in hold if k in HEAD_HOLD]
    if hold:
        first = condition_gnm(sex, iters=iters, eps=eps, tol=tol, log=lambda *a: None, prior=prior, ridge=ridge)
        V1 = d['T'] + np.tensordot(first['coeffs'], d['B'], 1)
        m1 = head_measures(V1, dict(zip(d['joint_names'], d['TJ'] + np.tensordot(first['coeffs'], d['BJ'], 1))))
        for k in hold:
            tgt[k], sd[k] = m1[k], HEAD_HOLD[k]
        keys += hold
        log(f'[gnm] {sex}: held at the 14 measures\' values: ' + ', '.join(f'{k} {m1[k]:.2f}' for k in hold))
    T = np.array([tgt[k] for k in keys])
    S = np.array([sd[k] for k in keys])
    if prior is None:
        mu, Cp = np.zeros(N_HEAD), None
    else:
        mu = np.asarray(prior[0], np.float64)[:N_HEAD]
        Cp = np.asarray(prior[1], np.float64)[:N_HEAD, :N_HEAD]
        Cp = Cp + ridge * float(np.trace(Cp)) / N_HEAD * np.eye(N_HEAD)
    c = mu.copy()
    J0 = dict(zip(d['joint_names'], d['TJ']))
    before = head_measures(d['T'], J0)
    at_prior = head_measures(d['T'] + np.tensordot(mu, d['B'], 1),
                             dict(zip(d['joint_names'], d['TJ'] + np.tensordot(mu, d['BJ'], 1))))
    hist = []
    for it in range(iters):
        V = d['T'] + np.tensordot(c, d['B'], 1)
        Jt = dict(zip(d['joint_names'], d['TJ'] + np.tensordot(c, d['BJ'], 1)))
        m0 = head_measures(V, Jt)
        r = np.array([m0[k] for k in keys])
        z = (r - T) / S
        hist.append(dict(it=it, max_abs_z=float(np.abs(z).max()), norm=float(np.linalg.norm(c))))
        log(f'[gnm] {sex} step {it}: |z| max {np.abs(z).max():.3f} ({keys[int(np.argmax(np.abs(z)))]}), '
            f'|c| {np.linalg.norm(c):.3f}')
        if np.abs(z).max() < tol:
            break
        # the Jacobian (measures in sd units per unit coefficient)
        Jm = np.zeros((len(keys), N_HEAD))
        for k in range(N_HEAD):
            Vk = V + eps * d['B'][k]
            Jk = dict(zip(d['joint_names'], d['TJ'] + np.tensordot(c, d['BJ'], 1) + eps * d['BJ'][k]))
            mk = head_measures(Vk, Jk)
            Jm[:, k] = (np.array([mk[kk] for kk in keys]) - r) / eps / S
        # least norm of c (not of the step): Jm c_new = Jm c - z; with a prior, least Mahalanobis about its mean
        b = Jm @ c - z
        if Cp is None:
            c = Jm.T @ np.linalg.solve(Jm @ Jm.T, b)
        else:
            CJ = Cp @ Jm.T
            c = mu + CJ @ np.linalg.solve(Jm @ CJ, b - Jm @ mu)
    V = d['T'] + np.tensordot(c, d['B'], 1)
    Jt = dict(zip(d['joint_names'], d['TJ'] + np.tensordot(c, d['BJ'], 1)))
    after = head_measures(V, Jt)
    rows = {k: dict(target=float(tgt[k]), sd=float(sd[k]), gnm_mean=float(before[k]), conditioned=float(after[k]),
                    prior_mean=float(at_prior[k]), z_before=float((before[k] - tgt[k]) / sd[k]),
                    z_prior=float((at_prior[k] - tgt[k]) / sd[k]), z_after=float((after[k] - tgt[k]) / sd[k]))
            for k in keys}
    mahal = None if Cp is None else float(np.sqrt((c - mu) @ np.linalg.solve(Cp, c - mu)))
    return dict(sex=sex, coeffs=c, rows=rows, norm=float(np.linalg.norm(c)), mahalanobis=mahal, history=hist)


# ============================================================================================ MakeHuman hm08
# the standard rig's bones grouped into the body's parts (weights.default.json: the skin weights of 163 bones)
_HEAD_BONES = ('head', 'jaw', 'eye', 'levator', 'oculi', 'orbicularis', 'oris', 'risorius', 'special', 'temporalis',
               'tongue')
_PART_OF = (('neck', ('neck01', 'neck02', 'neck03')),
            ('trunk', ('root', 'spine', 'pelvis', 'breast', 'clavicle', 'shoulder01')),
            ('arm', ('upperarm', 'lowerarm')),
            ('hand', ('wrist', 'metacarpal', 'finger')),
            ('leg', ('upperleg', 'lowerleg')),
            ('foot', ('foot', 'toe')))
_MH = {}


def bone_part(b):
    stem = b.split('.')[0]
    side = b.split('.')[1] if '.' in b else ''
    if stem.startswith(_HEAD_BONES):
        return 'head'
    for part, stems in _PART_OF:
        if stem.startswith(stems):
            return part + ('_' + side if part in ('arm', 'hand', 'leg', 'foot') else '')
    raise KeyError(b)


def mh_data():
    """hm08's base mesh, groups, targets reader and skin weights (read once, as data)"""
    if _MH:
        return _MH
    V, Q, cur = [], [], None
    with open(os.path.join(MH_DIR, '3dobjs', 'base.obj'), encoding='utf-8') as fh:
        for ln in fh:
            if ln.startswith('v '):
                V.append([float(x) for x in ln.split()[1:4]])
            elif ln.startswith('g '):
                cur = ln.split(None, 1)[1].strip()
            elif ln.startswith('f ') and cur == 'body':
                Q.append([int(x.split('/')[0]) - 1 for x in ln.split()[1:]])
    _MH['V'] = np.array(V)
    _MH['Q'] = np.array(Q, np.int64)
    g = json.load(open(os.path.join(MH_DIR, 'mesh_metadata', 'basemesh_vertex_groups.json'), encoding='utf-8'))

    def ids(spec):
        out = []
        for r in spec:
            out += list(range(r[0], r[1] + 1)) if isinstance(r, list) else [r]
        return np.array(out, int)
    _MH['groups'] = {k: ids(v) for k, v in g.items()}
    _MH['nb'] = int(_MH['groups']['body'].max()) + 1            # 'body' = vertices 0 .. 13379
    w = json.load(open(os.path.join(MH_DIR, 'rigs', 'standard', 'weights.default.json'), encoding='utf-8'))['weights']
    bones = sorted(w)
    r, c, x = [], [], []
    for j, b in enumerate(bones):
        for vi, wt in w[b]:
            if vi < _MH['nb']:
                r.append(vi)
                c.append(j)
                x.append(wt)
    W = sp.csr_matrix((x, (r, c)), shape=(_MH['nb'], len(bones)))
    rs = np.asarray(W.sum(1)).ravel()
    _MH['W'] = sp.diags(1.0 / np.maximum(rs, 1e-12)) @ W
    _MH['bones'] = bones
    _MH['bone_part'] = [bone_part(b) for b in bones]
    return _MH


def mh_target(name):
    """a macro target (data/targets/macrodetails/<name>.target.gz): per-vertex offsets (decimetres) as a dense array"""
    D = np.zeros_like(mh_data()['V'])
    with gzip.open(os.path.join(MH_DIR, 'targets', 'macrodetails', name + '.target.gz'), 'rt') as fh:
        for ln in fh:
            p = ln.split()
            if len(p) >= 4:
                D[int(p[0])] = [float(p[1]), float(p[2]), float(p[3])]
    return D


class MHBody:
    """the hm08 body at the sex's young adult phenotype (mm, ground at y 0), or at given positions V (mm)"""
    SEXES = dict(F='female', M='male')

    def __init__(self, sex, V=None):
        d = mh_data()
        self.sex = sex
        if V is None:
            key = 'pheno_' + sex
            if key not in d:
                D = sum(mh_target(f'{r}-{self.SEXES[sex]}-young') for r in ('african', 'asian', 'caucasian')) / 3.0
                Vd = d['V'] + D
                ground = Vd[d['groups']['joint-ground']].mean(0)
                d[key] = (Vd - np.array([0.0, ground[1], 0.0])) * 100.0
            V = d[key]
        self.V = np.asarray(V, np.float64)
        self.nb = d['nb']
        self.Q = d['Q']
        self.F = np.concatenate([self.Q[:, [0, 1, 2]], self.Q[:, [0, 2, 3]]])
        self.joints = {k[6:]: self.V[v].mean(0) for k, v in d['groups'].items() if k.startswith('joint-')}
        W = d['W']
        parts = sorted(set(d['bone_part']))
        P = np.zeros((len(d['bone_part']), len(parts)))
        for j, p in enumerate(d['bone_part']):
            P[j, parts.index(p)] = 1.0
        self.part_w = np.asarray(W @ P)                       # (nb, parts): each part's share of the vertex's weight
        self.parts = parts
        self.part = np.array(parts, dtype=object)[np.argmax(self.part_w, 1)]
        self._tm = None

    @property
    def Vb(self):
        return self.V[:self.nb]

    @property
    def tm(self):
        if self._tm is None:
            self._tm = TriMesh(self.Vb, self.F)
        return self._tm

    def w(self, *names):
        """the summed weight share of the named parts per body vertex"""
        return sum(self.part_w[:, self.parts.index(n)] for n in names if n in self.parts)

    def bone_w(self, prefix, side=''):
        """the summed skin weight of the bones whose names start with prefix (and end with .side), per body vertex"""
        d = mh_data()
        js = [j for j, b in enumerate(d['bones']) if b.startswith(prefix) and (not side or b.endswith('.' + side))]
        return np.asarray(d['W'][:, js].sum(1)).ravel()

    def faces_of(self, mask):
        """the triangles whose three corners are in the vertex mask"""
        return self.F[mask[self.F].all(1)]


def _profile(V, F, front=True, step=1.0, x0=0.3):
    """the midline section's front (max z) or back (min z) profile, per height bin (y, z); the plane sits x0 mm off the
    midline, whose vertices lie exactly on x = 0 (no triangle crosses it there)"""
    S, _ = plane_section(V, F, np.array([x0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0]))
    # every section segment crossing each height: the front profile the largest z there, the back the smallest (the
    # segments are sparse in height on a coarse mesh, so each height is interpolated on the segments, not binned)
    A, Bp = S[:, 0], S[:, 1]
    lo, hi = np.minimum(A[:, 1], Bp[:, 1]), np.maximum(A[:, 1], Bp[:, 1])
    ys = np.arange(np.floor(lo.min()), np.ceil(hi.max()) + step, step)
    zs = np.full(len(ys), np.nan)
    for i, y in enumerate(ys):
        m = (lo <= y) & (hi >= y) & (hi > lo)
        if not m.any():
            continue
        t = (y - A[m, 1]) / (Bp[m, 1] - A[m, 1])
        z = A[m, 2] + t * (Bp[m, 2] - A[m, 2])
        zs[i] = z.max() if front else z.min()
    ok = ~np.isnan(zs)
    return ys[ok], zs[ok]


def _snap(V, p, mask=None):
    idx = np.arange(len(V)) if mask is None else np.nonzero(mask)[0]
    return int(idx[np.argmin(np.linalg.norm(V[idx] - p, axis=1))])


def mh_landmarks(B, log=print):
    """ANSUR II's landmarks on a MakeHuman body by SURFACE rules (vertex ids into B.V), left side (+x) and the midline.
    H0's rules took the trochanterion, the knee's two landmarks, the malleolus and the acromion within a few mm of the
    rig's joint cubes; here each is the extreme of the skin itself over a band wide enough to hold it:
      acromion        the shoulder's superolateral corner: the max of 0.54 x + 0.84 y (the bisector of the shoulder top's
                      ~20 deg slope and the A-posed arm's 45 deg) over the shoulder's skin (within 120 mm of the
                      shoulder joint, |z - z_joint| < 25)
      axilla          the armpit's apex: the highest down-facing (n_y < -0.25) skin point below the shoulder joint, within
                      35 mm of its z
      chest           the bust point: the most anterior point of the left chest (x 40-130 mm) between 150 mm under the
                      axilla and 30 mm over it (ANSUR's chest height: the nipple level)
      suprasternale   the jugular notch: the most posterior point of the front midline profile between 40 and 140 mm
                      under the menton... in practice the profile's minimum between the shoulder level and 70 mm above it
      cervicale       C7: the back profile's convex corner between the acromion's height and 130 mm above it
      omphalion       the navel: the front profile's minimum between the pelvis joint + 20 and + 220 mm (H0's rule)
      crotch          the lowest point of the midline section above the knees (H0's rule)
      buttock         the left buttock's (x 30-130, between the crotch and the omphalion, behind the hip joint) vertex
                      nearest its section's most posterior point at the height where that posterior reach, smoothed over
                      +-10 mm of height, peaks (H2b)
      trochanterion   the most lateral point from the thigh's axis (hip joint -> knee joint), hip joint height -70 .. +50
      mid_patella     the most anterior knee point within 70 mm of the knee joint's height and 70 mm of its x
      epicondyle      the most lateral point from the knee's axis within 8 mm of 10 mm over mid-patella (H2b: level
                      with the patella's upper half)
      malleolus       the most lateral point from the shank's axis (knee joint -> ankle joint), ankle joint +-40 mm,
                      within 35 mm of its z
      radiale         the elbow's outer point: the most lateral skin point (perpendicular to the upper arm's axis, in the
                      coronal plane, away from the body) within 15 mm (along the axis) of the elbow joint
      stylion         the radial styloid: the skin point at the wrist joint (within 12 mm along the forearm's axis) farthest
                      toward the thumb's base joint
      fingertip       the middle finger's tip: the farthest finger-3 skin point from the wrist joint
      heel, toe       the foot's most posterior and most anterior points"""
    V = B.Vb
    F = B.F
    J = B.joints
    L = {}
    part = B.part
    head = part == 'head'
    L['vertex'] = int(np.nonzero(head)[0][np.argmax(V[head, 1])])
    trunkish = np.isin(part, ('trunk', 'neck', 'head', 'leg_L', 'leg_R'))
    Ft = B.faces_of(trunkish)
    ys, zf = _profile(V, Ft, front=True)
    yb, zb = _profile(V, Ft, front=False)
    near_mid = np.abs(V[:, 0]) < 2.0
    # ---- acromion
    sh = J['l-shoulder']
    m = (np.linalg.norm(V - sh, axis=1) < 120.0) & (np.abs(V[:, 2] - sh[2]) < 25.0) & np.isin(part, ('trunk', 'arm_L')) & \
        (V[:, 0] > 0)
    ii = np.nonzero(m)[0]
    L['acromion'] = int(ii[np.argmax(0.54 * V[ii, 0] + 0.84 * V[ii, 1])])
    # ---- axilla
    vn = vertex_normals(V, F)
    m = (V[:, 1] < sh[1] - 10.0) & (np.abs(V[:, 2] - sh[2]) < 35.0) & (vn[:, 1] < -0.25) & \
        np.isin(part, ('trunk', 'arm_L')) & (V[:, 0] > 20.0) & (V[:, 1] > sh[1] - 200.0)
    ii = np.nonzero(m)[0]
    L['axilla'] = int(ii[np.argmax(V[ii, 1])])
    ya = V[L['axilla'], 1]
    # ---- chest (bust point)
    m = (V[:, 0] > 40.0) & (V[:, 0] < 130.0) & (V[:, 1] > ya - 150.0) & (V[:, 1] < ya + 30.0) & (part == 'trunk')
    ii = np.nonzero(m)[0]
    L['chest'] = int(ii[np.argmax(V[ii, 2])])
    # a PIT on a profile: how far the profile dips under its own running mean over +-w mm (the navel, the jugular notch)
    def pit(yv, zv, lo, hi, w, sign=1.0):
        k = int(round(w))
        zs_ = np.convolve(np.pad(zv, k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), mode='valid')
        depth = sign * (zs_ - zv)
        sel_ = np.nonzero((yv > lo) & (yv < hi))[0]
        return sel_[np.argmax(depth[sel_])], float(depth[sel_].max())
    # ---- suprasternale: the jugular notch, the front profile's deepest pit within 40 mm of the acromion's height
    ya_c = V[L['acromion'], 1]
    k, dep = pit(ys, zf, ya_c - 40.0, ya_c + 40.0, 25.0)
    L['suprasternale'] = _snap(V, np.array([0.0, ys[k], zf[k]]), near_mid)
    # ---- cervicale: C7, where the back of the neck's forward lean ends and the profile bends into the nape's hollow:
    # the most negative d2z/dy2 of the back profile (smoothed over 9 mm) between 20 mm over the acromion's height and
    # 10 mm under the nape's deepest point (the profile's most anterior point within 160 mm over the acromion). On both
    # phenotypes this lands within 3-5 mm of ANSUR's cervicale ratio (the slope there drops 0.49 -> 0.35 / 0.34 -> 0.22)
    zz = np.convolve(np.pad(zb, 4, mode='edge'), np.ones(9) / 9, mode='valid')
    d1 = np.gradient(zz, yb)
    d2 = np.convolve(np.pad(np.gradient(d1, yb), 3, mode='edge'), np.ones(7) / 7, mode='valid')
    band = np.nonzero((yb > ya_c) & (yb < ya_c + 160.0))[0]
    y_nape = yb[band[np.argmax(zz[band])]]
    sel = np.nonzero((yb > ya_c + 20.0) & (yb < y_nape - 10.0))[0]
    k = sel[np.argmin(d2[sel])]
    L['cervicale'] = _snap(V, np.array([0.0, yb[k], zb[k]]), near_mid)
    # ---- omphalion: the navel, the front profile's deepest pit between the pelvis joint + 40 and the chest - 60
    pel = J['pelvis'][1]
    k, dep = pit(ys, zf, pel + 40.0, V[L['chest'], 1] - 60.0, 20.0)
    L['omphalion'] = _snap(V, np.array([0.0, ys[k], zf[k]]), near_mid)
    # ---- crotch
    S, _ = plane_section(V, Ft, np.array([0.3, 0.0, 0.0]), np.array([1.0, 0.0, 0.0]))
    P = S.reshape(-1, 3)
    P = P[P[:, 1] > J['l-knee'][1] + 100.0]
    j = int(np.argmin(P[:, 1]))
    L['crotch'] = _snap(V, P[j], near_mid)
    yc = V[L['crotch'], 1]
    # ---- buttock: the peak of the buttock's posterior reach (the most posterior point of the left buttock's skin in
    # each horizontal SECTION, every 2 mm of height) SMOOTHED over +-10 mm of height, then the most posterior vertex
    # within 6 mm of that height (H2b). The bare extreme vertex was no landmark on MakeHuman's flat-topped bulge: the
    # woman's reach stays within 3 mm of its peak from y 834 to 860 and the extreme sat at the top of that span (the
    # reading +1.1 sd; h2b/scratch/p07_landmarks.py). The reach is read on the surface's sections, behind the hip
    # joints only: binned by VERTEX height, a 2 mm bin holding no back vertex took its minimum from the belly (reach
    # -145 mm), the smoothing sank and the peak fell on the thigh just above the crotch (h2b/scratch/p10_buttock.py)
    z_hip = float(J['l-upper-leg'][2])
    m = (V[:, 0] > 30.0) & (V[:, 0] < 130.0) & (V[:, 1] > yc) & (V[:, 1] < V[L['omphalion'], 1]) & \
        np.isin(part, ('trunk', 'leg_L')) & (V[:, 2] < z_hip)
    ii = np.nonzero(m)[0]
    Fb_ = B.faces_of(np.isin(part, ('trunk', 'leg_L')))
    yb_ = np.arange(yc + 2.0, V[L['omphalion'], 1] - 1.0, 2.0)
    reach = np.full(len(yb_), np.nan)
    rpt = np.full((len(yb_), 3), np.nan)
    for k_, yh_ in enumerate(yb_):
        S_, _ = plane_section(V, Fb_, np.array([0.0, yh_, 0.0]), np.array([0.0, 1.0, 0.0]))
        P_ = S_.reshape(-1, 3)
        P_ = P_[(P_[:, 0] > 30.0) & (P_[:, 0] < 130.0) & (P_[:, 2] < z_hip)]
        if len(P_):
            reach[k_] = -P_[:, 2].min()
            rpt[k_] = P_[np.argmin(P_[:, 2])]
    ok_ = np.isfinite(reach)
    reach = np.interp(yb_, yb_[ok_], reach[ok_])
    sm_ = np.convolve(np.pad(reach, 5, mode='edge'), np.ones(11) / 11.0, mode='valid')
    k_pk = int(np.argmax(np.where(ok_, sm_, -np.inf)))
    # the vertex nearest the section's most posterior point at that height (a 6 mm height window held no vertex on
    # the man's third H2b solve: hm08's rows there are ~13 mm apart)
    L['buttock'] = int(ii[np.argmin(np.linalg.norm(V[ii] - rpt[k_pk], axis=1))])
    # ---- the leg's landmarks
    hip, kn, an = J['l-upper-leg'], J['l-knee'], J['l-ankle']

    def lateral_from(a, b, mask):
        ax = (b - a) / np.linalg.norm(b - a)
        lat = np.array([1.0, 0.0, 0.0]) - ax[0] * ax
        lat /= np.linalg.norm(lat)
        ii = np.nonzero(mask)[0]
        D = V[ii] - a
        D = D - np.outer(D @ ax, ax)
        return int(ii[np.argmax(D @ lat)])
    legL = np.isin(part, ('trunk', 'leg_L')) & (V[:, 0] > 0)
    # the trochanter: the hip's lateral prominence, the most lateral skin point (horizontally: the A-posed thigh
    # diverges, so the distance from its axis favours points lower down the thigh) within 30 mm under and 40 mm over the
    # hip joint's height, within 60 mm of its z
    m = legL & (V[:, 1] > hip[1] - 30.0) & (V[:, 1] < hip[1] + 40.0) & (np.abs(V[:, 2] - hip[2]) < 60.0)
    ii = np.nonzero(m)[0]
    L['trochanterion'] = int(ii[np.argmax(V[ii, 0])])
    m = (part == 'leg_L') & (np.abs(V[:, 1] - kn[1]) < 70.0) & (np.abs(V[:, 0] - kn[0]) < 70.0)
    ii = np.nonzero(m)[0]
    L['mid_patella'] = int(ii[np.argmax(V[ii, 2])])
    ymp = V[L['mid_patella'], 1]
    # the epicondyle: the knee's lateral prominence from the KNEE's axis (the mean of the thigh's and the shank's
    # directions), read in a band 8 mm either side of 10 mm over mid-patella: the lateral femoral epicondyle is bone,
    # level with the patella's upper half in a standing knee, and MakeHuman's knee shows no lateral extreme for it (the
    # skin's lateral reach stays within ~2 mm of its peak over ~70 mm of height, so the old band's extreme, 10 mm under
    # to 35 mm over mid-patella, sat at its top and read +0.6 / +1.5 sd; h2b/scratch/p07_landmarks.py) [E: H2b]
    kax = (hip - kn) / np.linalg.norm(hip - kn) + (kn - an) / np.linalg.norm(kn - an)
    L['epicondyle'] = lateral_from(kn - kax * 50.0, kn + kax * 50.0,
                                   (part == 'leg_L') & (np.abs(V[:, 1] - (ymp + 10.0)) < 8.0))
    # (no further forward than 15 mm of the joint: the lateral malleolus sits at or behind it; the foot's lateral border
    # 26 mm forward and 25 mm low beat it by 1.3 mm on H2's grounded man and read his malleolus height -5 sd)
    L['malleolus'] = lateral_from(kn, an, np.isin(part, ('leg_L', 'foot_L')) & (np.abs(V[:, 1] - an[1]) < 25.0) &
                                  (V[:, 2] - an[2] > -30.0) & (V[:, 2] - an[2] < 15.0))
    foot = part == 'foot_L'
    ii = np.nonzero(foot)[0]
    L['heel'] = int(ii[np.argmin(V[ii, 2])])
    L['toe'] = int(ii[np.argmax(V[ii, 2])])
    # ---- the arm's landmarks
    el, wr = J['l-elbow'], J['l-hand']
    ax = (el - sh) / np.linalg.norm(el - sh)
    lat = np.cross(np.array([0.0, 0.0, 1.0]), ax)            # in the coronal plane, perpendicular to the arm
    if lat[1] < 0:
        lat = -lat                                           # away from the body: up and out for an A-posed arm
    m = np.isin(part, ('arm_L',)) & (np.abs((V - el) @ ax) < 15.0) & (np.linalg.norm(V - el, axis=1) < 70.0)
    ii = np.nonzero(m)[0]
    L['radiale'] = int(ii[np.argmax((V[ii] - el) @ lat)])
    axf = (wr - el) / np.linalg.norm(wr - el)
    th = J['l-finger-1-1'] - wr
    th = th - (th @ axf) * axf
    th /= np.linalg.norm(th)
    m = np.isin(part, ('arm_L', 'hand_L')) & (np.abs((V - wr) @ axf) < 12.0) & (np.linalg.norm(V - wr, axis=1) < 60.0)
    ii = np.nonzero(m)[0]
    L['stylion'] = int(ii[np.argmax((V[ii] - wr) @ th)])
    fing = B.bone_w('finger3', 'L') > 0.5
    ii = np.nonzero(fing)[0]
    L['fingertip'] = int(ii[np.argmax(np.linalg.norm(V[ii] - wr, axis=1))])
    return L


def _pchip(xs, ys):
    from scipy.interpolate import PchipInterpolator
    return PchipInterpolator(np.asarray(xs, np.float64), np.asarray(ys, np.float64), extrapolate=True)


def ansur_targets(sex):
    """the baseline body's ANSUR II values (the regression at the SPEC baseline's stature and BMI 25), mm"""
    b = HS.SPEC['baseline'][sex]
    out = {m: HS.predict(sex, m, b['stature'], b['bmi']) for m in HS.SPEC['reg'][sex] if m not in ('stature',
                                                                                                  'weight_kg')}
    out['stature'] = b['stature']
    return out


# the height anchors of the vertical remap (MakeHuman landmark -> ANSUR height); the acromion is set by the shoulders'
# own elevation (MakeHuman's woman has the jugular notch 24 mm over her acromion, ANSUR's women 5 mm under it: a height
# remap alone cannot reorder two heights); the rest are measured after
HEIGHT_ANCHORS = (('malleolus', 'lateralmalleolusheight'), ('mid_patella', 'kneeheightmidpatella'),
                  ('crotch', 'crotchheight'), ('trochanterion', 'trochanterionheight'),
                  ('omphalion', 'waistheightomphalion'), ('chest', 'chestheight'), ('axilla', 'axillaheight'),
                  ('suprasternale', 'suprasternaleheight'), ('vertex', 'stature'))
# ANSUR II measures the biceps and the forearm FLEXED; the reference arm is relaxed. The ratio relaxed / flexed [E]:
# NHANES 2021-23's relaxed mid-upper-arm circumference at 20-29 (F 31.9, M 34.3 cm; B §3.6) against ANSUR II's flexed
# biceps regression at NHANES 20-29's mean stature and BMI (F 163.5 cm, 28.0; M 176.3 cm, 27.8): F 319 / 325.1 = 0.981,
# M 343 / 359.6 = 0.954 (two populations, means against means); the forearm takes the same ratio, no relaxed source read
FLEX_RATIO = dict(F=0.981, M=0.954)


class PinnedBody:
    """MakeHuman's sex phenotype deformed to the ANSUR baseline (plan §2.5). EACH STATION IS GOVERNED BY ONE TRANSFORM
    (H1's first version blended every transform by the skin weights, so a station's measure moved with transforms it
    did not set, and the man's iteration ran away: chest sx 0.23, shoulders x4.5):
      TRUNK  (and neck, head) a vertical remap through the height anchors, then per height an x scale, a z scale about
             the section's centre and a DIAGONAL scale (1 + (sd - 1) sin^2 2phi: breadth and depth untouched), each a
             smooth (PCHIP) curve through its stations, solved in closed form on the original sections: the chest and
             the waist (breadth, depth, girth), the hip (breadth at the trochanterion), the buttock (depth, girth); the
             shoulder girdle's breadth and elevation from the acromion
      LEG    below the crotch (a 40 mm blend across it, by height): a radial scale about the leg's axis (a PCHIP curve
             through the thigh, lower thigh, calf and ankle stations: girth' = r girth, exactly), the remap, the foot's
             breadth and length about the ankle, the leg's root carried by the pelvis' x scale
      ARM    past the shoulder joint (a blend over its first 30 %, times the arm's skin weight): a radial scale about the
             chain, the three segments scaled along it, carried by the shoulder joint's trunk transform
    then a few multiplicative correction passes (each factor from its own station's measure)"""

    TRUNK_STATIONS = ('neck_base', 'chest', 'waist', 'hip', 'buttock')
    LEG_STATIONS = ('thigh', 'lowerthigh', 'calf', 'ankle')
    ARM_STATIONS = ('biceps', 'forearm', 'wrist', 'hand')

    def __init__(self, sex, iters=9, log=print, flex='nhanes'):
        self.sex = sex
        self.B0 = MHBody(sex)
        self.L = mh_landmarks(self.B0, log)
        self.T = ansur_targets(sex)
        self.log = log
        # ANSUR measures the biceps and the forearm FLEXED; the reference is relaxed. flex: the relaxed / flexed ratio
        # applied to those two targets [E] (FLEX_RATIO), or None: they are left free and reported
        if flex == 'nhanes':
            flex = {m: FLEX_RATIO[sex] for m in ('bicepscircumferenceflexed', 'forearmcircumferenceflexed')}
        self.flex = flex
        self._setup()
        self._solve_closed_form()
        self.history = []
        for it in range(iters):
            self.V = self.deform()
            rep = self.measure(self.V)
            self.history.append(rep)
            worst = max(abs(r['z']) for r in rep['pins'].values())
            wk = max(rep['pins'], key=lambda k: abs(rep['pins'][k]['z']))
            log(f'[pin] {sex} pass {it}: worst pinned measure {worst:.3f} residual sd ({wk}); k_sh {self.k_sh:.4f}, '
                f'd_sh {self.d_sh:.1f}, '
                f'chest sx/sz/sd {self.sx["chest"]:.3f}/{self.sz["chest"]:.3f}/{self.sd["chest"]:.3f}, biacromial '
                f'{rep["rows"]["biacromialbreadth"]["value"]:.1f}, chest breadth {rep["rows"]["chestbreadth"]["value"]:.1f}')
            if worst < 0.02 or it == iters - 1:
                break
            self.update(rep)
        self.B = MHBody(sex, self.V)
        self.report = self.measure(self.V)

    # ------------------------------------------------------------------------------ the parametrisation
    def _setup(self):
        B, L, T, J = self.B0, self.L, self.T, self.B0.joints
        V = B.Vb
        y = lambda k: V[L[k], 1]          # noqa: E731
        xs = [0.0] + [y(a) for a, _ in HEIGHT_ANCHORS]
        ts = [0.0] + [T[m] for _, m in HEIGHT_ANCHORS]
        o = np.argsort(xs)
        self.R = _pchip(np.array(xs)[o], np.array(ts)[o])
        # the trunk's stations (original heights): the neck base on its tilted plane is handled by its height at the
        # suprasternale; hip at the trochanterion; buttock at the buttock point
        self.st_y = dict(neck_base=y('suprasternale'), chest=y('chest'), waist=y('omphalion'), hip=y('trochanterion'),
                         buttock=y('buttock'))
        # the hip and the buttock are ONE station at the buttock's height, its breadth target ANSUR's hip breadth (the
        # maximum across the hips): two stations 2 mm apart (MakeHuman's man) made a cliff in the curves, 40 mm apart
        # (the woman, whose buttock sits ABOVE her trochanter, ANSUR's under) a ledge round her hips
        self.merged = True
        self.trunk_st = [k for k in self.TRUNK_STATIONS if k != 'hip']
        self.sx = {k: 1.0 for k in self.TRUNK_STATIONS}
        self.sz = {k: 1.0 for k in self.TRUNK_STATIONS}
        # the trunk section's centre z per height (the trunk-and-neck vertices' mean z in 10 mm bands, smoothed)
        tr = np.isin(B.part, ('trunk', 'neck'))
        yy = np.arange(0.0, 1800.0, 10.0)
        cz = np.array([V[tr & (np.abs(V[:, 1] - h) < 15.0), 2].mean() if (tr & (np.abs(V[:, 1] - h) < 15.0)).any()
                       else np.nan for h in yy])
        ok = ~np.isnan(cz)
        cz = np.interp(yy, yy[ok], cz[ok])
        self.cz = (yy, np.convolve(np.pad(cz, 5, mode='edge'), np.ones(11) / 11, mode='valid'))
        # the leg's axis (hip -> knee -> ankle joints) and its stations (arc parameter along it, mm from the hip joint);
        # the thigh's station 35 mm under the crotch, below the trunk-leg blend (crotch + 15 .. crotch - 25)
        self.leg_axis = np.array([J['l-upper-leg'], J['l-knee'], J['l-ankle']])
        hip, kn = J['l-upper-leg'], J['l-knee']
        ymp = y('mid_patella')
        self.y_crotch = y('crotch')
        self.leg_st = dict(thigh=self._leg_t(np.array([0.0, y('crotch') - 35.0, 0.0])),
                           lowerthigh=self._leg_t(np.array([0.0, ymp + 70.0, 0.0])),
                           calf=None, ankle=self._leg_t(np.array([0.0, y('malleolus') + 45.0, 0.0])))
        # the calf station at the shank's widest section
        self.leg_st['calf'] = self._calf_t()
        self.leg_r = {k: 1.0 for k in self.LEG_STATIONS}
        # the arm's chain (shoulder, elbow, wrist joints, middle fingertip) and segment scales
        tip = V[L['fingertip']]
        self.arm_axis = np.array([J['l-shoulder'], J['l-elbow'], J['l-hand'], tip])
        self.arm_k = [1.0, 1.0, 1.0]
        self.arm_st = dict(biceps=0.5, forearm=1.25, wrist=1.92)        # chain parameters (segment index + fraction)
        self.arm_r = {k: 1.0 for k in self.ARM_STATIONS}
        # the hand's circumference round the knuckles: the middle finger's MCP joint on the hand's segment
        wr, tip = self.arm_axis[2], self.arm_axis[3]
        mcp = J['l-finger-3-1']
        self.hand_t = 2.0 + float((mcp - wr) @ (tip - wr) / ((tip - wr) @ (tip - wr))) - 0.02
        self.arm_st['hand'] = self.hand_t
        self.arm_r['hand'] = 1.0
        self.foot_s = [1.0, 1.0]                                          # breadth (x), length (z) about the ankle
        # the shoulders' breadth: an x scale on the shoulder girdle (|x| past the neck, within 90 mm of the acromion's
        # height), on top of the stations' sx (the neck base and the acromion share a height, not a breadth)
        self.k_sh = 1.0
        self.y_sh = y('acromion')
        self.d_sh = 0.0                       # the shoulders' elevation (mm), for the acromion's height
        # the sections' DIAGONAL factor at the chest and the waist: a radial scale 1 + (sd - 1) sin^2(2 phi) about the
        # section's centre, which leaves the breadth (phi 0) and the depth (phi 90) alone: girth, breadth and depth are
        # three targets, and sx, sz alone left MakeHuman's man's chest too round (girth -2.3 sd with breadth +1.5)
        self.sd = {k: 1.0 for k in self.TRUNK_STATIONS}
        # the GEOMETRIC blend weights on the original body: legs below the crotch, arms past the shoulder joint
        self.w_leg = np.zeros(B.nb)
        self.w_arm = np.zeros(B.nb)
        yv = V[:, 1]
        s_leg = np.clip((self.y_crotch + 15.0 - yv) / 40.0, 0.0, 1.0)
        self.w_leg = s_leg * s_leg * (3 - 2 * s_leg)
        armv = np.isin(B.part, ('arm_L', 'arm_R', 'hand_L', 'hand_R'))
        for sg in (1.0, -1.0):
            A = self.arm_axis * np.array([sg, 1.0, 1.0])
            t, foot = self._chain_param(A, V)
            # along the chain: from 12 to 42 % of the upper arm (the armpit's apex lies at ~20 %, a trunk anchor)
            s_a = np.clip((t - 0.12) / 0.30, 0.0, 1.0)
            # across it: within the arm's own radius of its chain (the arm's vertices' median distance per chain
            # bin), out to 1.5 radii; the arm's skin weights alone took the man's chest wall under the armpit (the
            # A-posed arm runs down beside it), and the chest's breadth stopped answering the chest's scale
            d = np.linalg.norm(V - foot, axis=1)
            side = (V[:, 0] * sg) > 0
            bins = np.linspace(0.0, 3.0, 31)
            rad = np.full(len(bins) - 1, np.nan)
            for b in range(len(bins) - 1):
                mm = armv & side & (t >= bins[b]) & (t < bins[b + 1])
                if mm.sum() > 5:
                    rad[b] = np.median(d[mm])
            ok = ~np.isnan(rad)
            rt = np.interp(t, 0.5 * (bins[:-1] + bins[1:])[ok], rad[ok])
            s_d = np.clip((1.5 * rt - d) / (0.4 * rt), 0.0, 1.0)
            # (the distance test only beside the trunk: past 60-90 % of the upper arm everything of the arm's skin is
            # arm; the fingers stand off the hand's chain)
            s_d = np.maximum(s_d, np.clip((t - 0.6) / 0.3, 0.0, 1.0) * armv)
            w = (s_a * s_a * (3 - 2 * s_a)) * (s_d * s_d * (3 - 2 * s_d))
            self.w_arm[side] = w[side]
        self.w_leg = self.w_leg * (1.0 - self.w_arm)
        # the faces each transform governs alone (for the stations' sections)
        trunk_only = (self.w_leg < 0.02) & (self.w_arm < 0.02)
        self.F_trunk = B.F[trunk_only[B.F].all(1)]

    def _trunk_section(self, V, yh):
        """the trunk-only faces' horizontal section at height yh: the (x, z) points of the loop round the midline"""
        S, _ = plane_section(V, self.F_trunk, np.array([0.0, yh, 0.0]), np.array([0.0, 1.0, 0.0]))
        if len(S) == 0:
            return np.zeros((0, 2))
        loops = section_loops(S)
        from matplotlib.path import Path as MPath
        cz = float(np.interp(yh, *self.cz))
        for lp in loops:
            P2 = lp[:, [0, 2]]
            if len(P2) > 4 and MPath(P2).contains_point((0.0, cz)):
                return P2
        return S.reshape(-1, 3)[:, [0, 2]]

    @staticmethod
    def _bump(phi, ang):
        """the diagonal scale's weight at section angle phi (rad, from +x toward +z, the half x >= 0): zero at the
        section's back, side and front extremes (ang = (phi_back, phi_side, phi_front)), sin^2 bumps between them, zero
        past the front and back extremes toward the midline. So the breadth and the depth stay put whatever their
        angle (a fixed sin^2 2phi moved the man's side extreme at 20 deg, and sx and the diagonal fought)"""
        pb_, ps_, pf_ = ang
        w = np.zeros_like(phi)
        m1 = (phi >= ps_) & (phi <= pf_)
        w[m1] = np.sin(np.pi * (phi[m1] - ps_) / max(pf_ - ps_, 1e-6)) ** 2
        m2 = (phi >= pb_) & (phi < ps_)
        w[m2] = np.sin(np.pi * (phi[m2] - pb_) / max(ps_ - pb_, 1e-6)) ** 2
        return w

    @staticmethod
    def _extreme_angles(P2, cz):
        H = P2[P2[:, 0] >= 0]
        a = lambda p: float(np.arctan2(p[1] - cz, p[0]))      # noqa: E731
        return (a(H[np.argmin(H[:, 1])]), a(H[np.argmax(H[:, 0])]), a(H[np.argmax(H[:, 1])]))

    def _solve_section(self, P2, cz, ang, targets, sds, weights, sd_bounds=(0.85, 1.25), x0=None):
        """(sx, sz, sd) for a section with girth, breadth and depth targets (any may be None): least squares in residual
        sd, the girth weighted twice (the plan's primary pin: a tape), the diagonal bounded. A body's section cannot
        always take all three (MakeHuman's man's chest is rounder than ANSUR's box-like chest at the nipples: girth /
        (breadth + depth) 1.93 in ANSUR); unbounded, the diagonal ran to 1.7 and pinched the chest"""
        from scipy.optimize import minimize
        G, Bt, D = targets

        def resid(p):
            sx, sz, sd = p
            Q = self._diag_transform(P2, cz, sx, sz, sd, ang)
            r = []
            if G is not None:
                r.append(weights[0] * (hull_perimeter(Q) - G) / sds[0])
            if Bt is not None:
                r.append(weights[1] * (np.ptp(Q[:, 0]) - Bt) / sds[1])
            if D is not None:
                r.append(weights[2] * (np.ptp(Q[:, 1]) - D) / sds[2])
            return float(np.sum(np.square(r)))
        if x0 is None:
            x0 = [Bt / np.ptp(P2[:, 0]) if Bt else 1.0, D / np.ptp(P2[:, 1]) if D else 1.0, 1.0]
        res = minimize(resid, x0, method='L-BFGS-B', bounds=[(0.6, 1.6), (0.6, 1.6), sd_bounds])
        return [float(v) for v in res.x]

    def _diag_transform(self, P2, cz, sx, sz, sd, ang=None):
        ang = self._extreme_angles(P2, cz) if ang is None else ang
        phi = np.arctan2(P2[:, 1] - cz, np.abs(P2[:, 0]))
        rad = 1.0 + (sd - 1.0) * self._bump(phi, ang)
        return np.column_stack([P2[:, 0] * sx * rad, cz + (P2[:, 1] - cz) * sz * rad])

    def _solve_closed_form(self):
        """every factor from its station on the ORIGINAL body (the stations are governed by one transform each)"""
        B, L, T = self.B0, self.L, self.T
        V = B.Vb
        J = B.joints

        def tgt(m):
            v = T[m]
            if self.flex is not None and m in self.flex:
                v = v * self.flex[m]
            return v

        def bisect(fn, target, lo=0.6, hi=1.5, it=50):
            a, b = lo, hi
            fa = fn(a) - target
            for _ in range(it):
                m = 0.5 * (a + b)
                fm = fn(m) - target
                if (fm < 0) == (fa < 0):
                    a, fa = m, fm
                else:
                    b = m
            return 0.5 * (a + b)
        self.ang = {}
        self.sec = {}
        reg = HS.SPEC['reg'][self.sex]
        for st, gm, bm, dm in (('chest', 'chestcircumference', 'chestbreadth', 'chestdepth'),
                               ('waist', 'waistcircumference', 'waistbreadth', 'waistdepth')):
            yh = self.st_y[st]
            P2 = self._trunk_section(V, yh)
            cz = float(np.interp(yh, *self.cz))
            self.ang[st] = self._extreme_angles(P2, cz)
            self.sec[st] = dict(P2=P2, cz=cz, keys=(gm, bm, dm), eff=[tgt(gm), tgt(bm), tgt(dm)],
                                sds=[reg[gm][6], reg[bm][6], reg[dm][6]])
            self.sx[st], self.sz[st], self.sd[st] = self._solve_section(P2, cz, self.ang[st], self.sec[st]['eff'],
                                                                        self.sec[st]['sds'], (2.0, 1.0, 1.0))
        yh = self.st_y['buttock']
        P2 = self._trunk_section(V, yh)
        cz = float(np.interp(yh, *self.cz))
        self.ang['buttock'] = self._extreme_angles(P2, cz)
        self.sz['buttock'] = tgt('buttockdepth') / np.ptp(P2[:, 1])
        if self.merged:
            # the hip breadth (the maximum over the hip region, as ANSUR takes it) carried onto this section's breadth
            # by their ratio on the original body
            keys = ('buttockcircumference', 'hipbreadth', 'buttockdepth')
            hb0 = self._hip_breadth(V, original=True)
            eff = [tgt(keys[0]), tgt(keys[1]) * np.ptp(P2[:, 0]) / hb0, tgt(keys[2])]
            self.sec['buttock'] = dict(P2=P2, cz=cz, keys=keys, eff=eff, sds=[reg[k][6] for k in keys])
            self.sx['buttock'], self.sz['buttock'], self.sd['buttock'] = self._solve_section(
                P2, cz, self.ang['buttock'], self.sec['buttock']['eff'], self.sec['buttock']['sds'], (2.0, 1.0, 1.0))
        else:
            self.sx['buttock'] = bisect(lambda s: hull_perimeter(self._diag_transform(P2, cz, s, self.sz['buttock'],
                                                                                     1.0, self.ang['buttock'])),
                                        tgt('buttockcircumference'))
            P2 = self._trunk_section(V, self.st_y['hip'])
            self.sx['hip'] = tgt('hipbreadth') / np.ptp(P2[:, 0])
            self.sz['hip'] = 0.5 * (self.sz['waist'] + self.sz['buttock'])
        # the shoulders from the acromion (trunk governed): its x through sx at its height and k_sh; its height through
        # the remap and d_sh
        a = V[L['acromion']]
        sx_a = float(self._sx_curve(np.array([a[1]]), shoulder=True)[0])
        self.k_sh = (tgt('biacromialbreadth') / 2.0) / (a[0] * sx_a)
        self.d_sh = tgt('acromialheight') - float(self.R(a[1]))
        # the limbs' radial scales: girth' = r girth on the original perpendicular sections
        for st, m in (('thigh', 'thighcircumference'), ('lowerthigh', 'lowerthighcircumference'),
                      ('calf', 'calfcircumference'), ('ankle', 'anklecircumference')):
            self.leg_r[st] = tgt(m) / self._limb_girth(V, B, self.leg_axis, self.leg_st[st], 'leg_L')
        for st, m in (('biceps', 'bicepscircumferenceflexed'), ('forearm', 'forearmcircumferenceflexed'),
                      ('wrist', 'wristcircumference')):
            if m in ('bicepscircumferenceflexed', 'forearmcircumferenceflexed') and self.flex is None:
                continue
            self.arm_r[st] = tgt(m) / self._limb_girth(V, B, self.arm_axis, self.arm_st[st], 'arm_L')
        self.arm_r['hand'] = tgt('handcircumference') / self._hand_girth(V, B, J)
        # the arm's segments from their surface lengths (the ends move a little with the shoulder: corrected after)
        p = lambda k: V[L[k]]     # noqa: E731
        self.arm_k = [tgt('acromionradialelength') / np.linalg.norm(p('acromion') - p('radiale')),
                      tgt('radialestylionlength') / np.linalg.norm(p('radiale') - p('stylion')),
                      tgt('handlength') / np.linalg.norm(p('stylion') - p('fingertip'))]
        foot = B.part == 'foot_L'
        self.foot_s = [tgt('footbreadthhorizontal') / np.ptp(V[foot, 0]),
                       tgt('footlength') / np.linalg.norm((p('toe') - p('heel'))[[0, 2]])]

    def _hip_breadth(self, V, original=False):
        """ANSUR's hip breadth: the maximum breadth of the trunk's sections over the hip region (20 mm over the crotch
        to 40 mm under the navel), sampled every 5 mm (original heights, or carried by the remap)"""
        lo, hi = self.y_crotch + 20.0, self.st_y['waist'] - 40.0
        best = 0.0
        for yh in np.arange(lo, hi, 5.0):
            P2 = self._trunk_section(V, yh if original else float(self.R(yh)))
            if len(P2):
                best = max(best, float(np.ptp(P2[:, 0])))
        return best

    def _hand_girth(self, V, B, J):
        """round the knuckles, the thumb's bones left out: the plane across the palm's axis (wrist joint -> the middle
        finger's MCP joint) 5 mm short of that joint"""
        wrj, mcp = J['l-hand'], J['l-finger-3-1']
        ax = (mcp - wrj) / np.linalg.norm(mcp - wrj)
        c = mcp - 5.0 * ax
        thumb = (B.bone_w('finger1', 'L') + B.bone_w('metacarpal1', 'L')) > 0.5
        hm = ((B.part == 'hand_L') | (B.w('hand_L') > 0.3)) & ~thumb
        S, _ = plane_section(V, B.F[hm[B.F].all(1)], c, ax)
        S = S[np.linalg.norm(S.mean(1) - c, axis=1) < 80.0] if len(S) else S
        if not len(S):
            return 0.0
        e1, e2, _ = plane_basis(ax)
        Pp = S.reshape(-1, 3) - c
        return hull_perimeter(np.column_stack([Pp @ e1, Pp @ e2]))

    def _sx_curve(self, y, shoulder=False, which='sx'):
        """a trunk factor as a smooth curve of the original height (PCHIP through the stations, held past the ends);
        shoulder=True: the shoulder girdle's curve (without the neck's base station)"""
        vals = dict(sx=self.sx, sz=self.sz, sd=self.sd)[which]
        ks = [k for k in self.trunk_st if not (shoulder and k == 'neck_base')]
        ys = np.array([self.st_y[k] for k in ks])
        vs = np.array([vals[k] for k in ks])
        if shoulder:
            # the shoulder girdle returns to 1 at the acromion's height, where k_sh alone sets the breadth (held at the
            # chest's value, the shoulders moved with every chest correction and the woman's biacromial jumped 13 mm)
            ys = np.append(ys, self.y_sh)
            vs = np.append(vs, 1.0)
        o = np.argsort(ys)
        ys, vs = ys[o], vs[o]
        f = _pchip(ys, vs)
        yc = np.clip(y, ys[0], ys[-1])
        return f(yc)

    def _leg_t(self, p):
        """the chain parameter (segment index + fraction) of the leg axis point at p's height"""
        A = self.leg_axis
        for s in range(len(A) - 1):
            a, b = A[s], A[s + 1]
            if min(a[1], b[1]) <= p[1] <= max(a[1], b[1]):
                return s + (a[1] - p[1]) / (a[1] - b[1])
        return 0.0 if p[1] > A[0][1] else len(A) - 1.0

    def _calf_t(self):
        B = self.B0
        V = B.Vb
        best, bt = 0.0, 1.3
        for t in np.linspace(1.15, 1.6, 19):
            g = self._limb_girth(V, B, self.leg_axis, t, 'leg_L')
            if g > best:
                best, bt = g, t
        return bt

    @staticmethod
    def _chain_point(A, t):
        s = int(np.clip(np.floor(t), 0, len(A) - 2))
        f = t - s
        return A[s] * (1 - f) + A[s + 1] * f, (A[s + 1] - A[s]) / np.linalg.norm(A[s + 1] - A[s])

    def _limb_girth(self, V, B, A, t, partname, radius=None):
        """the tape round the limb's section perpendicular to its chain at t: the section LOOP that encloses the chain's
        point (a radius filter fed back on itself when a limb grew past it: H1's first runs), else the loop nearest it"""
        c, ax = self._chain_point(A, t)
        mask = (B.part == partname) | (B.w(partname) > 0.3)
        Fp = B.F[mask[B.F].any(1)]
        S, _ = plane_section(V, Fp, c, ax)
        if len(S) == 0:
            return 0.0
        e1, e2, n = plane_basis(ax)
        best, bd = None, np.inf
        for lp in section_loops(S):
            if len(lp) < 4:
                continue
            P2 = np.column_stack([(lp - c) @ e1, (lp - c) @ e2])
            from matplotlib.path import Path as MPath
            if MPath(P2).contains_point((0.0, 0.0)):
                return hull_perimeter(P2)
            d = np.linalg.norm(P2, axis=1).min()
            if d < bd:
                best, bd = P2, d
        return hull_perimeter(best) if best is not None else 0.0

    @staticmethod
    def _chain_param(A, P):
        """per point, the nearest chain parameter on the polyline A (segment index + fraction) and the foot point"""
        best_t = np.zeros(len(P))
        best_d = np.full(len(P), np.inf)
        foot = np.zeros_like(P)
        for s in range(len(A) - 1):
            a, b = A[s], A[s + 1]
            ab = b - a
            f = np.clip(((P - a) @ ab) / (ab @ ab), 0.0, 1.0)
            # extrapolate past the chain's ends
            if s == 0:
                f = np.minimum(((P - a) @ ab) / (ab @ ab), 1.0)
            if s == len(A) - 2:
                f = np.maximum(((P - a) @ ab) / (ab @ ab), 0.0) if s > 0 else ((P - a) @ ab) / (ab @ ab)
            q = a + f[:, None] * ab
            dd = np.linalg.norm(P - q, axis=1)
            better = dd < best_d
            best_d[better] = dd[better]
            best_t[better] = s + f[better]
            foot[better] = q[better]
        return best_t, foot

    @staticmethod
    def _interp_st(stations, values, t):
        """a limb factor along its chain: PCHIP through the stations, held past the end stations"""
        ks = sorted(stations, key=lambda k: stations[k])
        xs = np.array([stations[k] for k in ks])
        vs = np.array([values[k] for k in ks])
        return _pchip(xs, vs)(np.clip(t, xs[0], xs[-1]))

    # ------------------------------------------------------------------------------ the deformation
    def deform(self):
        B = self.B0
        V0 = B.V.copy()
        V = V0[:B.nb]
        J = B.joints
        # ---- TRUNK transform (also neck and head): height remap, then the section's scales about (0, cz); the
        # shoulder girdle (|x| past the neck) takes the curves without the neck's base station, and k_sh, d_sh

        def trunk_T(P):
            y = P[:, 1]
            ax_ = np.abs(P[:, 0])
            ramp_x = np.clip((ax_ - 55.0) / 75.0, 0.0, 1.0)
            ramp_x = ramp_x * ramp_x * (3 - 2 * ramp_x)
            sx = (1 - ramp_x) * self._sx_curve(y) + ramp_x * self._sx_curve(y, shoulder=True)
            sz = (1 - ramp_x) * self._sx_curve(y, which='sz') + ramp_x * self._sx_curve(y, True, 'sz')
            sdv = (1 - ramp_x) * self._sx_curve(y, which='sd') + ramp_x * self._sx_curve(y, True, 'sd')
            cz = np.interp(y, *self.cz)
            # (the shoulders' bump reaches 95 mm either side of the acromion: at 120 it lifted the woman's armpit 4 mm)
            bump_y = np.clip(1.0 - np.abs(y - self.y_sh) / 95.0, 0.0, 1.0)
            bump_y = bump_y * bump_y * (3 - 2 * bump_y)
            ksh = 1.0 + (self.k_sh - 1.0) * ramp_x * bump_y
            phi = np.arctan2(P[:, 2] - cz, np.abs(P[:, 0]))
            # the extremes' angles: linear in height between the stations that carry them
            ks_ = [k for k in ('chest', 'waist', 'buttock') if k in self.ang]
            ys_ = np.array([self.st_y[k] for k in ks_])
            o_ = np.argsort(ys_)
            angs = [np.interp(y, ys_[o_], np.array([self.ang[k][j] for k in ks_])[o_]) for j in range(3)]
            w_ = np.zeros(len(P))
            pbk, psd, pfr = angs
            m1 = (phi >= psd) & (phi <= pfr)
            w_[m1] = np.sin(np.pi * (phi[m1] - psd[m1]) / np.maximum(pfr[m1] - psd[m1], 1e-6)) ** 2
            m2 = (phi >= pbk) & (phi < psd)
            w_[m2] = np.sin(np.pi * (phi[m2] - pbk[m2]) / np.maximum(psd[m2] - pbk[m2], 1e-6)) ** 2
            rad = 1.0 + (sdv - 1.0) * w_
            out = P.copy()
            out[:, 0] = P[:, 0] * sx * ksh * rad
            out[:, 2] = cz + (P[:, 2] - cz) * sz * rad
            out[:, 1] = self.R(y) + self.d_sh * ramp_x * bump_y
            return out
        # the legs' root carried by the pelvis' x scale at the crotch (the middle of the trunk-leg blend)
        sx_h = float(self._sx_curve(np.array([self.y_crotch]))[0])

        def leg_T(P, sg, wf=None):
            """the leg's transform (side sign sg): radial scale about its axis, the foot's breadth and length about the
            ankle (weight wf: the foot's share), the remap, the hip joint's sideways move"""
            A = self.leg_axis * np.array([sg, 1.0, 1.0])
            t, foot = self._chain_param(A, P)
            r = self._interp_st(self.leg_st, self.leg_r, t)
            if wf is not None:
                r = 1.0 + (r - 1.0) * (1.0 - wf)        # the foot takes foot_s, not the ankle's radial scale
            Q = foot + (P - foot) * r[:, None]
            if wf is not None:
                an = A[2]
                Q[:, 0] = Q[:, 0] + wf * (Q[:, 0] - an[0]) * (self.foot_s[0] - 1.0)
                Q[:, 2] = Q[:, 2] + wf * (Q[:, 2] - an[2]) * (self.foot_s[1] - 1.0)
            Q[:, 1] = self.R(Q[:, 1])
            Q[:, 0] += A[0][0] * (sx_h - 1.0)
            return Q

        def arm_T(P, sg):
            """the arm's transform: radial scale about its chain, the segments scaled along it, carried by the shoulder
            joint's trunk transform"""
            A = self.arm_axis * np.array([sg, 1.0, 1.0])
            t, foot = self._chain_param(A, P)
            r = self._interp_st(self.arm_st, self.arm_r, t)
            off = (P - foot) * r[:, None]
            An = [trunk_T(A[:1])[0]]
            for s in range(3):
                An.append(An[-1] + (A[s + 1] - A[s]) * self.arm_k[s])
            An = np.array(An)
            s_i = np.clip(np.floor(t).astype(int), 0, 2)
            f = t - s_i
            out_ = An[s_i] * (1 - f)[:, None] + An[s_i + 1] * f[:, None] + off
            # the arm's root (the deltoid, the armpit) follows the trunk's height remap at its own height, fading out
            # by 80 % of the upper arm (the shoulder joint alone carried the axilla 20 mm off its anchor)
            fade = np.clip(1.0 - t / 0.8, 0.0, 1.0)
            ysh = A[0][1]
            out_[:, 1] += fade * ((self.R(P[:, 1]) - P[:, 1]) - (self.R(ysh) - ysh))
            return out_
        Tt = trunk_T(V)
        Tl, Ta = V.copy(), V.copy()
        mid = np.abs(V[:, 0]) < 1e-6
        TlL, TlR = leg_T(V, 1.0, B.w('foot_L')), leg_T(V, -1.0, B.w('foot_R'))
        for side, sg, TlS in (('L', 1.0, TlL), ('R', -1.0, TlR)):
            sidem = (V[:, 0] * sg) > 0
            Tl[sidem] = TlS[sidem]
            Ta[sidem] = arm_T(V, sg)[sidem]
        # the midline (the crotch between the legs): the mean of both legs' transforms (x cancels, the remap stays);
        # left untransformed it pulled the crotch 15 mm off its anchor through the blend
        Tl[mid] = 0.5 * (TlL[mid] + TlR[mid])
        Tl[mid, 0] = 0.0
        wl, wa = self.w_leg, self.w_arm
        wt = 1.0 - wl - wa
        Vn = Tt * wt[:, None] + Tl * wl[:, None] + Ta * wa[:, None]
        out = V0.copy()
        out[:B.nb] = Vn
        # the helpers follow the trunk; the JOINT CUBES follow their own limb's transform (the deformed joints are the
        # axes the limb stations are measured on, so they must move with the limb's skin)
        out[B.nb:] = trunk_T(V0[B.nb:])
        d = mh_data()
        for name, ids_ in d['groups'].items():
            if not name.startswith('joint-'):
                continue
            jn = name[6:]
            sg = -1.0 if jn.startswith('r-') else 1.0
            if any(k in jn for k in ('upper-leg', 'knee', 'ankle', 'foot', 'toe')):
                wf = np.ones(len(ids_)) if ('foot' in jn or 'toe' in jn) else np.zeros(len(ids_))
                out[ids_] = leg_T(V0[ids_], sg, wf)
            elif any(k in jn for k in ('elbow', 'hand', 'finger')):
                out[ids_] = arm_T(V0[ids_], sg)
        return out

    # ------------------------------------------------------------------------------ measuring
    def measure(self, Vall):
        B = MHBody(self.sex, Vall)
        V = B.Vb
        L, T = self.L, self.T
        p = lambda k: V[L[k]]     # noqa: E731
        rep = {}
        # heights
        for lm, m in (('acromion', 'acromialheight'), ('axilla', 'axillaheight'), ('chest', 'chestheight'),
                      ('suprasternale', 'suprasternaleheight'), ('cervicale', 'cervicaleheight'),
                      ('omphalion', 'waistheightomphalion'), ('trochanterion', 'trochanterionheight'),
                      ('crotch', 'crotchheight'), ('buttock', 'buttockheight'), ('mid_patella', 'kneeheightmidpatella'),
                      ('epicondyle', 'lateralfemoralepicondyleheight'), ('malleolus', 'lateralmalleolusheight')):
            rep[m] = float(p(lm)[1])
        rep['stature'] = float(V[:, 1].max())
        # lengths and breadths
        rep['biacromialbreadth'] = 2.0 * float(p('acromion')[0])
        rep['acromionradialelength'] = float(np.linalg.norm(p('acromion') - p('radiale')))
        rep['radialestylionlength'] = float(np.linalg.norm(p('radiale') - p('stylion')))
        rep['handlength'] = float(np.linalg.norm(p('stylion') - p('fingertip')))
        rep['footlength'] = float(np.linalg.norm((p('toe') - p('heel'))[[0, 2]]))
        foot = B.part == 'foot_L'
        rep['footbreadthhorizontal'] = float(np.ptp(V[foot, 0]))
        # the trunk's girths, breadths and depths: the trunk-only faces' horizontal sections (the loop round the
        # midline) at each station's height carried by the remap (the landmark vertices themselves may sit in a blend);
        # the hip breadth across the section at the trochanterion's
        for st, gm, bm, dm in (('chest', 'chestcircumference', 'chestbreadth', 'chestdepth'),
                               ('waist', 'waistcircumference', 'waistbreadth', 'waistdepth'),
                               ('buttock', 'buttockcircumference', None, 'buttockdepth')):
            P = self._trunk_section(V, float(self.R(self.st_y[st])))
            rep[gm] = hull_perimeter(P)
            if bm:
                rep[bm] = float(np.ptp(P[:, 0]))
            rep[dm] = float(np.ptp(P[:, 1]))
        rep['hipbreadth'] = self._hip_breadth(V)
        # the neck's base: the plane through the suprasternale and the cervicale, level left to right
        a, c = p('suprasternale'), p('cervicale')
        u = (c - a) / np.linalg.norm(c - a)
        nrm = np.cross(np.array([1.0, 0.0, 0.0]), u)
        nrm *= np.sign(nrm[1])
        Fn = B.faces_of(np.isin(B.part, ('trunk', 'neck', 'head')))
        S, _ = plane_section(V, Fn, 0.5 * (a + c), nrm)
        S = S[np.linalg.norm(S.mean(1) - 0.5 * (a + c), axis=1) < 110.0]
        e1, e2, _ = plane_basis(nrm)
        Pp = S.reshape(-1, 3) - 0.5 * (a + c)
        rep['neckcircumferencebase'] = hull_perimeter(np.column_stack([Pp @ e1, Pp @ e2]))
        # the limbs' girths, perpendicular to their axes on the deformed joints
        Jn = B.joints
        legA = np.array([Jn['l-upper-leg'], Jn['l-knee'], Jn['l-ankle']])
        for st, m in (('thigh', 'thighcircumference'), ('lowerthigh', 'lowerthighcircumference'),
                      ('calf', 'calfcircumference'), ('ankle', 'anklecircumference')):
            rep[m] = self._limb_girth(V, B, legA, self.leg_st[st], 'leg_L' if st != 'ankle' else 'leg_L')
        armA = np.array([Jn['l-shoulder'], Jn['l-elbow'], Jn['l-hand'], V[L['fingertip']]])
        for st, m in (('biceps', 'bicepscircumferenceflexed'), ('forearm', 'forearmcircumferenceflexed'),
                      ('wrist', 'wristcircumference')):
            rep[m] = self._limb_girth(V, B, armA, self.arm_st[st], 'arm_L', radius=80.0)
        rep['handcircumference'] = self._hand_girth(V, B, Jn)
        # compare with ANSUR in residual sd
        reg = HS.SPEC['reg'][self.sex]
        rows = {}
        for m, v in rep.items():
            if m == 'stature':
                # an input, not a regression measure: its population sd, and the remap pins it exactly
                rows[m] = dict(value=v, target=T['stature'], sd=reg['stature'][1],
                               z=(v - T['stature']) / reg['stature'][1])
                continue
            if m not in reg:
                continue
            tgt = T[m]
            if self.flex is not None and m in ('bicepscircumferenceflexed', 'forearmcircumferenceflexed'):
                tgt = tgt * self.flex[m]
            rows[m] = dict(value=v, target=tgt, sd=reg[m][6], z=(v - tgt) / reg[m][6])
        # (the neck's base is not pinned here: the cage's neck runs from GNM's neck at the mid-neck ring, conditioned to
        # ANSUR's neck circumference, down to this body's shoulders, and the base is measured on the clay)
        pinned = ('stature', 'acromialheight', 'axillaheight', 'chestheight', 'suprasternaleheight', 'waistheightomphalion',
                  'trochanterionheight', 'crotchheight', 'kneeheightmidpatella', 'lateralmalleolusheight',
                  'acromionradialelength', 'radialestylionlength', 'handlength', 'footlength',
                  'footbreadthhorizontal', 'chestcircumference', 'waistcircumference', 'buttockcircumference',
                  'thighcircumference', 'lowerthighcircumference', 'calfcircumference', 'handcircumference',
                  'anklecircumference', 'wristcircumference', 'chestbreadth', 'chestdepth', 'waistbreadth',
                  'waistdepth', 'hipbreadth', 'buttockdepth', 'biacromialbreadth')
        if self.flex is not None:
            pinned = pinned + ('bicepscircumferenceflexed', 'forearmcircumferenceflexed')
        return dict(rows=rows, pins={k: rows[k] for k in pinned if k in rows})

    # ------------------------------------------------------------------------------ the update
    def update(self, rep):
        """the corrections after the closed-form solve: each factor from its own station's measure (clipped to +-8 %
        a pass as a guard; the stations no longer share a transform)"""
        R = rep['rows']
        g = lambda m: float(np.clip(R[m]['target'] / max(R[m]['value'], 1e-9), 0.92, 1.08))   # noqa: E731
        # the three-target sections: their effective targets carried by the measured ratios, re-solved on the
        # original section (the bounded least squares)
        for st, sec in self.sec.items():
            sec['eff'] = [e * g(k) for e, k in zip(sec['eff'], sec['keys'])]
            # (warm-started at the current factors: with several optima, a cold start jumped between them)
            self.sx[st], self.sz[st], self.sd[st] = self._solve_section(sec['P2'], sec['cz'], self.ang[st], sec['eff'],
                                                                        sec['sds'], (2.0, 1.0, 1.0),
                                                                        x0=[self.sx[st], self.sz[st], self.sd[st]])
        gg, gd = g('buttockcircumference'), g('buttockdepth')
        if not self.merged:
            self.sz['buttock'] *= gd
            self.sx['buttock'] *= float(np.clip(2.0 * gg - gd, 0.92, 1.08))
            self.sx['hip'] *= g('hipbreadth')
            self.sz['hip'] = 0.5 * (self.sz['waist'] + self.sz['buttock'])
        self.d_sh += R['acromialheight']['target'] - R['acromialheight']['value']
        for st, m in (('thigh', 'thighcircumference'), ('lowerthigh', 'lowerthighcircumference'),
                      ('calf', 'calfcircumference'), ('ankle', 'anklecircumference')):
            self.leg_r[st] *= g(m)
        for st, m in (('wrist', 'wristcircumference'), ('hand', 'handcircumference')) + \
                ((('biceps', 'bicepscircumferenceflexed'), ('forearm', 'forearmcircumferenceflexed'))
                 if self.flex is not None else ()):
            self.arm_r[st] *= g(m)
        self.arm_k[0] *= g('acromionradialelength')
        self.arm_k[1] *= g('radialestylionlength')
        self.arm_k[2] *= g('handlength')
        self.foot_s[0] *= g('footbreadthhorizontal')
        self.foot_s[1] *= g('footlength')
        self.k_sh *= g('biacromialbreadth')


# ============================================================================================ the smooth body
def mh_smooth(sex, V_pinned=None, levels=2, cache=True):
    """the pinned hm08 body as the SMOOTH surface MakeHuman draws it (its base mesh is meant to be subdivided): the
    Catmull-Clark cage whose limit passes through every pinned vertex (subdiv_sharp.fit_controls, levels 0: the limit
    mask on the cage), subdivided `levels` levels to the limit. The landmarks and the pinned measures sit at vertices,
    so they are kept; the 17-22 mm facets of the trunk and legs are gone (a denser cage fitted to the faceted mesh
    printed them as striations: H1's first figure). Returns (V, F) of the limit, cached in h1/ref"""
    from ..mesh import QuadMesh
    from .. import subdiv_sharp as SS
    path = os.path.join(ROOT, 'work', 'bestiary', 'human', 'h1', 'ref', f'body_smooth_{sex}.npz')
    if cache and os.path.exists(path) and V_pinned is None:
        z = np.load(path)
        return z['V'], z['F']
    if V_pinned is None:
        V_pinned = np.load(os.path.join(ROOT, 'work', 'bestiary', 'human', 'h1', 'ref', f'body_pinned_{sex}.npz'))['V']
    d = mh_data()
    Vb = np.asarray(V_pinned, np.float64)[:d['nb']]
    cage = QuadMesh(Vb, d['Q'])
    V0, res = SS.fit_controls(cage, {}, Vb, 0)
    lim, _, _, _ = SS.subdivide(QuadMesh(V0, d['Q']), {}, levels)
    F = lim.tris()
    if cache:
        np.savez(path, V=lim.V, F=F, fit_residual=res)
    return lim.V, F


# ============================================================================================ the eye rule
def fit_globe(margin_pts, diameter, lid=1.0):
    """the centre of a globe of `diameter` whose lid sphere (the globe + lid mm) passes nearest the lid margin's points,
    least squares (Gauss-Newton from the points' centroid pushed back along their normal): returns centre, residuals"""
    P = np.asarray(margin_pts, np.float64)
    R = diameter / 2.0 + lid
    c = P.mean(0)
    # start behind the margin: the plane fit's normal pointing out of the face (+z)
    U, s, Vt = np.linalg.svd(P - c)
    n = Vt[2] * np.sign(Vt[2][2])
    c = c - n * R * 0.6
    for _ in range(50):
        D = P - c
        r = np.linalg.norm(D, axis=1)
        J = -D / r[:, None]
        res = r - R
        step = np.linalg.lstsq(J, -res, rcond=None)[0]
        c = c + step
        if np.linalg.norm(step) < 1e-7:
            break
    res = np.linalg.norm(P - c, axis=1) - R
    return c, res
