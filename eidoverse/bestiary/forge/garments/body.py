"""THE BODY as the garment builder reads it: the human glb (h4d/build/glb/human_<sex>.glb, the canonical base), never edited.

skin_BODY in the glb's rest (the VRM T-pose, metres), its four-influence weights on the skin's joints, the skeleton's rest
world frames and inverse binds, the ring records mapped onto skin_BODY's own vertex ids, and linear blend skinning exactly
as three's SkinningNode does (posed world x inverse bind, weighted). pose() takes local rotations at named joints on top
of the rest (every VRM rest rotation is the identity, so a local rotation IS the pose).

    B = Body(path); B.V (n, 3) T rest; B.F (t, 3); B.J4 / B.W4; B.UV; B.lbs(pose) -> posed V; B.apose(deg)
"""
import hashlib

import numpy as np
from scipy.spatial import cKDTree

from .. import gltf


def quat_mat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def rot(axis, deg):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = np.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(t) * K + (1 - np.cos(t)) * K @ K


class Body:
    def __init__(self, path, mesh='skin_BODY'):
        g = gltf.read(path)
        self.path, self.j, self.acc = path, g['json'], g['accessor']
        j = self.j
        self.nodes = j['nodes']
        self.names = [n.get('name', '') for n in self.nodes]
        self.nidx = {n: i for i, n in enumerate(self.names)}
        self.parent = {c: i for i, n in enumerate(self.nodes) for c in n.get('children', [])}
        self.local = []
        for n in self.nodes:
            L = np.eye(4)
            if 'rotation' in n:
                L[:3, :3] = quat_mat(n['rotation'])
            if 'translation' in n:
                L[:3, 3] = n['translation']
            if 'scale' in n:
                L[:3, :3] = L[:3, :3] * np.asarray(n['scale'])
            self.local.append(L)
        self.rest_world = self.world()
        sk = j['skins'][0]
        self.joints = list(sk['joints'])
        self.jnames = [self.names[k] for k in self.joints]
        self.jidx = {n: i for i, n in enumerate(self.jnames)}
        self.ibm = self.acc(sk['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1).astype(np.float64)
        m = next(m for m in j['meshes'] if m['name'] == mesh)
        p = m['primitives'][0]
        a = p['attributes']
        self.V = self.acc(a['POSITION']).astype(np.float64)
        self.N = self.acc(a['NORMAL']).astype(np.float64)
        uv = self.acc(a['TEXCOORD_0']).astype(np.float64)
        self.UV = np.column_stack([uv[:, 0], 1.0 - uv[:, 1]])           # the forge's v-up
        self.J4 = self.acc(a['JOINTS_0']).astype(np.int64)
        self.W4 = self.acc(a['WEIGHTS_0']).astype(np.float64)
        self.F = self.acc(p['indices']).reshape(-1, 3).astype(np.int64)
        self.material = j['materials'][p['material']]['name']
        self.extras = j.get('extras', {}).get('bestiary', {})
        self.sex = self.extras.get('human', {}).get('sex', '?')
        self._rings = None

    # ------------------------------------------------------------------------------------------- the skeleton
    def world(self, extra=None):
        """world matrices of every node with optional extra local rotations {node name: 3x3} (post-multiplied: the rest
        rotation is the identity for the VRM's joints)"""
        out = [None] * len(self.nodes)

        def w(i):
            if out[i] is None:
                L = self.local[i].copy()
                if extra and self.names[i] in extra:
                    L[:3, :3] = L[:3, :3] @ extra[self.names[i]]
                p = self.parent.get(i)
                out[i] = (w(p) if p is not None else np.eye(4)) @ L
            return out[i]
        for i in range(len(self.nodes)):
            w(i)
        return out

    def skin_mats(self, extra=None, world=None):
        W = world if world is not None else self.world(extra)
        return np.stack([W[k] @ self.ibm[i] for i, k in enumerate(self.joints)])

    def lbs(self, extra=None, V=None, J4=None, W4=None, mats=None, normals=None):
        """posed points (and optionally normals) by the skin's weights (the body's own, or a garment's)"""
        V = self.V if V is None else V
        J4 = self.J4 if J4 is None else J4
        W4 = self.W4 if W4 is None else W4
        M = self.skin_mats(extra) if mats is None else mats
        A = np.einsum('nk,nkij->nij', W4, M[J4])
        P = np.einsum('nij,nj->ni', A[:, :3, :3], V) + A[:, :3, 3]
        if normals is None:
            return P
        Nn = np.einsum('nij,nj->ni', np.linalg.inv(A[:, :3, :3]).transpose(0, 2, 1), normals)
        Nn /= np.linalg.norm(Nn, axis=1, keepdims=True) + 1e-12
        return P, Nn

    def unlbs(self, P, J4, W4, mats):
        """the inverse: rest points whose LBS under mats lands on P (per vertex, the blended matrix inverted)"""
        A = np.einsum('nk,nkij->nij', W4, mats[J4])
        Ai = np.linalg.inv(A)
        return np.einsum('nij,nj->ni', Ai[:, :3, :3], P) + Ai[:, :3, 3]

    def apose(self, deg=45.0):
        """THE DRAPE POSE: the T rest's upper arms lowered by deg about the body's front axis (+Z), nothing else"""
        return {'upperarm_L': rot([0, 0, 1], -deg), 'upperarm_R': rot([0, 0, 1], deg)}

    def joint_pos(self, name, world=None):
        W = world if world is not None else self.rest_world
        return W[self.nidx[name]][:3, 3].copy()

    # ------------------------------------------------------------------------------------------- the records
    def rings(self):
        """{ring name: skin_BODY vertex ids along its loop}: the records index the forge's welded LOW (head + body); each
        loop point is matched to skin_BODY by position (exact: the glb's positions are the low's)"""
        if self._rings is None:
            self._rings = {}
            tree = cKDTree(self.V)
            for r in self.extras.get('rings', []):
                P = np.asarray(r.get('verts') or [], float)
                if P.size == 0:
                    continue
                d, i = tree.query(P)
                if np.max(d) < 1e-4:
                    self._rings[r['name']] = i
        return self._rings

    def socket(self, name, world=None):
        W = world if world is not None else self.rest_world
        return W[self.nidx[name]].copy()

    def welded(self):
        """skin_BODY is several pieces sewn by position (the ports' plugs, the nail folds sit in holes of the main skin with
        their own copies of the hole's vertices): one vertex per position (rounded to 1 um). Returns (Vw, Fw, wid: skin_BODY
        vertex -> welded id, rep: welded id -> one skin_BODY vertex)"""
        key = np.round(self.V * 1e6).astype(np.int64)
        u, rep, wid = np.unique(key, axis=0, return_index=True, return_inverse=True)
        wid = wid.ravel()
        Fw = wid[self.F]
        Fw = Fw[(Fw[:, 0] != Fw[:, 1]) & (Fw[:, 1] != Fw[:, 2]) & (Fw[:, 2] != Fw[:, 0])]
        return self.V[rep], Fw, wid, rep

    def pheno_hash(self):
        """THE CACHE KEY's body half: the rest positions' bits (float32) and the skeleton's rest translations"""
        h = hashlib.sha1(np.asarray(self.V, np.float32).tobytes())
        h.update(np.asarray([W[:3, 3] for W in self.rest_world], np.float32).tobytes())
        return h.hexdigest()[:12]

    def texel_density(self, size):
        """px per metre of skin_BODY's UVs at a size x size texture (area-weighted median)"""
        return texel_density(self.V, self.F, self.UV, size)


def texel_density(V, F, UV, size):
    a3 = 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)
    e1, e2 = UV[F[:, 1]] - UV[F[:, 0]], UV[F[:, 2]] - UV[F[:, 0]]
    a2 = 0.5 * np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0])
    ok = a3 > 1e-10
    d = np.sqrt(a2[ok] / a3[ok]) * size
    w = a3[ok]
    o = np.argsort(d)
    c = np.cumsum(w[o]) / w.sum()
    return dict(p50=float(d[o][np.searchsorted(c, 0.5)]), p5=float(d[o][np.searchsorted(c, 0.05)]),
                p95=float(d[o][np.searchsorted(c, 0.95)]))


def tri_normals(V, F):
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    return n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-20)


def vertex_normals(V, F):
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    N = np.zeros_like(V)
    for k in range(3):
        np.add.at(N, F[:, k], n)
    return N / (np.linalg.norm(N, axis=1, keepdims=True) + 1e-20)
