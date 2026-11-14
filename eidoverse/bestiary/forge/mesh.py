"""The forge's quad mesh (numpy). Every cage the forge builds is pure quads by construction: ring lofts, quad-grid
caps and port bridges, so Catmull-Clark subdivision stays all-quad and the low's edge flow is the one designed.

Conventions: metres, +Y up, a creature faces +Z, +X is its left. Quads wind counter-clockwise seen from outside, so
normals point out.
"""
import numpy as np


class QuadMesh:
    def __init__(self, V, Q, attrs=None):
        self.V = np.ascontiguousarray(V, np.float64)
        self.Q = np.ascontiguousarray(Q, np.int64).reshape(-1, 4)
        # per-vertex attributes carried through subdivision linearly (anatomical coordinates, region ids as one-hot
        # weights): name -> (n, k) float64
        self.attrs = {k: np.asarray(v, np.float64).reshape(len(self.V), -1) for k, v in (attrs or {}).items()}

    # ------------------------------------------------------------------ topology
    def edges(self):
        """unique undirected edges (E, 2) and each quad's four edge ids (m, 4): edge k of quad f joins corner k to k+1"""
        d = np.stack([self.Q, np.roll(self.Q, -1, axis=1)], -1).reshape(-1, 2)
        key = np.sort(d, axis=1)
        E, inv = np.unique(key, axis=0, return_inverse=True)
        return E, inv.reshape(-1, 4)

    def edge_faces(self, E=None, QE=None):
        """per edge, its (up to two) faces; -1 where a boundary edge has only one"""
        if E is None:
            E, QE = self.edges()
        ef = np.full((len(E), 2), -1, np.int64)
        flat = QE.ravel()
        fid = np.repeat(np.arange(len(self.Q)), 4)
        order = np.argsort(flat, kind='stable')
        fe, ff = flat[order], fid[order]
        first = np.ones(len(fe), bool)
        first[1:] = fe[1:] != fe[:-1]
        ef[fe[first], 0] = ff[first]
        second = ~first
        ef[fe[second], 1] = ff[second]
        return ef

    def check(self):
        """manifold and orientation: every edge in at most two quads, every directed edge at most once, no degenerate
        quads; returns a dict of counts (all zero = clean)"""
        d = np.stack([self.Q, np.roll(self.Q, -1, axis=1)], -1).reshape(-1, 2)
        E, QE = self.edges()
        cnt = np.bincount(QE.ravel(), minlength=len(E))
        _, dcnt = np.unique(d, axis=0, return_counts=True)
        degenerate = int((np.array([len(set(q)) for q in self.Q]) < 4).sum())
        return {'nonmanifold_edges': int((cnt > 2).sum()), 'flipped_or_dup_directed': int((dcnt > 1).sum()),
                'boundary_edges': int((cnt == 1).sum()), 'degenerate_quads': degenerate,
                'unused_verts': int(len(self.V) - len(np.unique(self.Q)))}

    # ------------------------------------------------------------------ geometry
    def tris(self):
        """two triangles per quad, split along the shorter diagonal (the split the exporter writes)"""
        q = self.Q
        V = self.V
        d02 = np.linalg.norm(V[q[:, 0]] - V[q[:, 2]], axis=1)
        d13 = np.linalg.norm(V[q[:, 1]] - V[q[:, 3]], axis=1)
        a = np.where((d02 <= d13)[:, None], q[:, [0, 1, 2]], q[:, [0, 1, 3]])
        b = np.where((d02 <= d13)[:, None], q[:, [0, 2, 3]], q[:, [1, 2, 3]])
        return np.concatenate([a, b])

    def face_normals(self):
        q = self.Q
        V = self.V
        n = np.cross(V[q[:, 2]] - V[q[:, 0]], V[q[:, 3]] - V[q[:, 1]])     # the quad's diagonal cross: robust
        return n

    def vertex_normals(self):
        fn = self.face_normals()                      # area-weighted (length = 2 x area for a planar quad)
        vn = np.zeros_like(self.V)
        for k in range(4):
            np.add.at(vn, self.Q[:, k], fn)
        ln = np.linalg.norm(vn, axis=1)
        return vn / np.maximum(ln, 1e-20)[:, None]

    def area(self):
        return float(0.5 * np.linalg.norm(self.face_normals(), axis=1).sum())

    def bbox(self):
        return self.V.min(0), self.V.max(0)

    # ------------------------------------------------------------------ assembly
    @staticmethod
    def merge(meshes):
        V, Q, off = [], [], 0
        keys = set(meshes[0].attrs) if meshes else set()
        for m in meshes[1:]:
            keys &= set(m.attrs)
        A = {k: [] for k in keys}
        for m in meshes:
            V.append(m.V)
            Q.append(m.Q + off)
            for k in keys:
                A[k].append(m.attrs[k])
            off += len(m.V)
        return QuadMesh(np.concatenate(V), np.concatenate(Q), {k: np.concatenate(v) for k, v in A.items()})

    def weld(self, tol=1e-9):
        """merge coincident vertices (seam rings built bit-identical on both sides weld exactly); attributes keep the
        first copy's values"""
        key = np.round(self.V / tol).astype(np.int64)
        _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
        inv = inv.ravel()
        V = self.V[first]
        Q = inv[self.Q]
        attrs = {k: v[first] for k, v in self.attrs.items()}
        return QuadMesh(V, Q, attrs)

    def compact(self):
        used = np.unique(self.Q)
        remap = np.full(len(self.V), -1, np.int64)
        remap[used] = np.arange(len(used))
        return QuadMesh(self.V[used], remap[self.Q], {k: v[used] for k, v in self.attrs.items()})

    def save_npz(self, path):
        np.savez(path, V=self.V, F=self.tris(), Q=self.Q, **{f'attr_{k}': v for k, v in self.attrs.items()})
