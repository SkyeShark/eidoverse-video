"""THE BASE a coat grows on: any forge glb, read once into what the groom needs (no species code).

    b = Base.from_glb('work/bestiary/octopus/octopus.glb')

The skin is every primitive whose material's extras say bestiary 'skin' (the forge's own tag); their triangles,
concatenated in primitive order, are THE LOW the coat's roots key on: a root is (triangle index, barycentrics), so it
rides any refit that keeps the low's topology (the vertices move, the root moves with its triangle) and a crossbreed
graft that carries a donor's triangles. On the octopus these triangles are exactly low.npz's faces, per set, in order
(verified 10-29 by (position, uv) to 1e-8), so nothing here needs a forge file.

What it holds:
  V, N, TAN, UV (glTF convention, v down the image), UVf (the forge's, v up), J (uint16, 4), W (float32, 4): the skin
    primitives' shared vertex set, compacted to the vertices the skin uses (`vmap` maps back to the glb's indices);
  F (m, 3) and face_set (m,) the texture set of each face (index into `sets`: the material name minus its species
    prefix, 'octopus_head' -> 'head');
  weld: wid (n,) the welded vertex of each vertex (seams duplicate positions), Vw, Nw (area-weighted), Fw (m, 3) the
    faces on welded vertices, and the welded one-ring adjacency (CSR: nb_ptr, nb_idx) for the flow field's smoothing;
  the skeleton: node names, parents, bind-pose world matrices, the skin's joint order and inverse bind matrices;
  sockets: every node whose name starts with 'socket_' or 'seat_', with its bind-pose world position and frame;
  chains: the glb's extras chains (bestiary.chains: joints, s, radius) or, without them, every run of single-child
    joints of length >= 3 in the skeleton;
  textures: the materials' maps, decoded lazily (tex(set, slot) -> float32 (h, w, c) in 0..1), slots by the forge's
    extras: 'base', 'normal', 'orm', 'masks' (KHR_materials_volume's thickness texture), 'display' (the emissive
    texture), 'growth' (the iridescence texture).
"""
import io
import json
import os
import re
import struct
import hashlib

import numpy as np

_NP = {5126: np.float32, 5123: np.uint16, 5125: np.uint32, 5121: np.uint8, 5122: np.int16, 5120: np.int8}
_NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def read_glb(path):
    """parse a .glb into (json, bin bytes, accessor reader); the reader honours byteStride (interleaved views, which the
    forge's gltf.read does not), sparse accessors and normalized integer components"""
    with open(path, 'rb') as f:
        data = f.read()
    magic, ver, total = struct.unpack_from('<III', data, 0)
    assert magic == 0x46546C67 and ver == 2 and total == len(data), path
    jl, _ = struct.unpack_from('<II', data, 12)
    j = json.loads(data[20:20 + jl])
    bl, _ = struct.unpack_from('<II', data, 20 + jl)
    b = data[28 + jl:28 + jl + bl]

    def acc(i):
        a = j['accessors'][i]
        n = _NCOMP[a['type']]
        dt = np.dtype(_NP[a['componentType']])
        cnt = a['count']
        if 'bufferView' in a:
            v = j['bufferViews'][a['bufferView']]
            off = v.get('byteOffset', 0) + a.get('byteOffset', 0)
            stride = v.get('byteStride', 0)
            if stride and stride != n * dt.itemsize:
                rows = np.frombuffer(b, np.uint8, count=(cnt - 1) * stride + n * dt.itemsize, offset=off)
                rows = np.lib.stride_tricks.as_strided(rows, (cnt, n * dt.itemsize), (stride, 1))
                arr = np.ascontiguousarray(rows).view(dt).reshape(cnt, n)
            else:
                arr = np.frombuffer(b, dtype=dt, count=cnt * n, offset=off).reshape(cnt, n).copy()
        else:
            arr = np.zeros((cnt, n), dt)
        if 'sparse' in a:
            s = a['sparse']
            vi, vv = j['bufferViews'][s['indices']['bufferView']], j['bufferViews'][s['values']['bufferView']]
            idx = np.frombuffer(b, dtype=_NP[s['indices']['componentType']], count=s['count'],
                                offset=vi.get('byteOffset', 0) + s['indices'].get('byteOffset', 0))
            val = np.frombuffer(b, dtype=dt, count=s['count'] * n,
                                offset=vv.get('byteOffset', 0) + s['values'].get('byteOffset', 0))
            arr = arr.copy()
            arr[idx] = val.reshape(-1, n)
        if a.get('normalized') and dt.kind in 'iu':
            arr = arr.astype(np.float32) / float(np.iinfo(dt).max)
        return arr if n > 1 else arr[:, 0]
    return j, b, acc


def cross2(a, b):
    """the z of the 2-D cross product (numpy 2 dropped 2-D vectors from np.cross)"""
    return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]


def _quat_to_mat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def _local(n):
    M = np.eye(4)
    if 'matrix' in n:
        return np.array(n['matrix'], np.float64).reshape(4, 4).T
    if 'rotation' in n:
        M[:3, :3] = _quat_to_mat(n['rotation'])
    if 'scale' in n:
        M[:3, :3] = M[:3, :3] * np.asarray(n['scale'])[None, :]
    if 'translation' in n:
        M[:3, 3] = n['translation']
    return M


class Base:
    """a forge glb's skin, skeleton, sockets, chains and maps (see the module docstring)"""

    @classmethod
    def from_glb(cls, path, skin_tag='skin'):
        self = cls()
        self.path = os.path.abspath(path)
        with open(path, 'rb') as f:
            self.sha1 = hashlib.sha1(f.read()).hexdigest()
        j, b, acc = read_glb(path)
        self.json, self._bin, self._acc = j, b, acc
        ex = j.get('extras', {}).get('bestiary', {})
        self.extras = ex
        self.species = ex.get('species', os.path.splitext(os.path.basename(path))[0])
        # ------------------------------------------------------------------ the skin primitives
        mats = j.get('materials', [])
        # (B3) the skin tag may be a list (the human's skin says 'human_skin'), and the skin may span SEVERAL meshes
        # (the human's skin_HEAD and skin_BODY, each with its own vertex set): their vertex sets are concatenated in mesh
        # order (each primitive's indices offset by its mesh's start), so (triangle, barycentrics) stays one index space
        # over every skin face. A single-mesh base (the octopus) reads exactly as before: one vertex set, offset 0
        tags = (skin_tag,) if isinstance(skin_tag, str) else tuple(skin_tag)
        prims = []                                            # (mesh, primitive index, primitive)
        for mi, m in enumerate(j['meshes']):
            for pi, p in enumerate(m['primitives']):
                mat = mats[p['material']] if 'material' in p else {}
                if mat.get('extras', {}).get('bestiary') in tags:
                    prims.append((mi, pi, p))
        assert prims, f'no primitive whose material says bestiary {tags!r} in {path}'
        meshes = sorted({mi for mi, _, _ in prims})
        skin_mesh = meshes[0]
        for mi in meshes:
            pos = {p['attributes']['POSITION'] for m2, _, p in prims if m2 == mi}
            assert len(pos) == 1, 'skin primitives of one mesh must share a vertex set'
        vsrc, voff, n0 = {}, {}, 0
        for mi in meshes:
            a_ = next(p for m2, _, p in prims if m2 == mi)['attributes']
            vsrc[mi] = a_
            voff[mi] = n0
            n0 += j['accessors'][a_['POSITION']]['count']

        def cat(key, dt):
            if not all(key in vsrc[mi] for mi in meshes):
                return None
            return np.concatenate([acc(vsrc[mi][key]).astype(dt) for mi in meshes])
        Vall = cat('POSITION', np.float64)
        Fs, sets, fset, set_mat = [], [], [], []
        for k, (mi, pi, p) in enumerate(prims):
            T = acc(p['indices']).reshape(-1, 3).astype(np.int64) + voff[mi]
            Fs.append(T)
            mname = mats[p['material']].get('name', f'mat{p["material"]}')
            sname = re.sub(r'^' + re.escape(self.species) + r'_', '', mname)
            sets.append(sname)
            set_mat.append(p['material'])
            fset.append(np.full(len(T), k, np.int32))
        Fglb = np.concatenate(Fs)
        used = np.unique(Fglb)
        remap = -np.ones(len(Vall), np.int64)
        remap[used] = np.arange(len(used))
        self.vmap = used
        self.F = remap[Fglb]
        self.face_set = np.concatenate(fset)
        self.sets = sets
        self.set_material = set_mat
        self.skin_mesh = skin_mesh
        self.skin_meshes = meshes
        self.skin_prims = [pi for _, pi, _ in prims]
        self.V = Vall[used]
        self.N = cat('NORMAL', np.float64)[used]
        TAN = cat('TANGENT', np.float64)
        self.TAN = TAN[used] if TAN is not None else None
        self.UV = cat('TEXCOORD_0', np.float64)[used]
        self.UVf = np.column_stack([self.UV[:, 0], 1.0 - self.UV[:, 1]])
        J = cat('JOINTS_0', np.int64)
        self.J = J[used] if J is not None else None
        W = cat('WEIGHTS_0', np.float64)
        self.W = W[used] if W is not None else None
        # ------------------------------------------------------------------ geometry
        e1 = self.V[self.F[:, 1]] - self.V[self.F[:, 0]]
        e2 = self.V[self.F[:, 2]] - self.V[self.F[:, 0]]
        cr = np.cross(e1, e2)
        self.area2 = np.linalg.norm(cr, axis=1)
        self.area = 0.5 * self.area2
        self.FN = cr / np.maximum(self.area2[:, None], 1e-30)
        self._weld()
        # ------------------------------------------------------------------ skeleton, sockets, chains
        self._skeleton(j, acc)
        self._chains(ex)
        self._tex_cache = {}
        return self

    # ---------------------------------------------------------------------------------------------- topology
    def _weld(self, tol=1e-7):
        q = np.round(self.V / tol).astype(np.int64)
        _, wid, inv_counts = np.unique(q, axis=0, return_inverse=True, return_counts=True)
        wid = wid.reshape(-1)
        self.wid = wid
        nw = int(wid.max()) + 1
        Vw = np.zeros((nw, 3))
        np.add.at(Vw, wid, self.V)
        Vw /= np.bincount(wid, minlength=nw)[:, None]
        self.Vw = Vw
        self.Fw = wid[self.F]
        Nw = np.zeros((nw, 3))
        for c in range(3):
            np.add.at(Nw, self.Fw[:, c], self.FN * self.area[:, None])
        self.Nw = Nw / np.maximum(np.linalg.norm(Nw, axis=1, keepdims=True), 1e-30)
        E = np.concatenate([self.Fw[:, [0, 1]], self.Fw[:, [1, 2]], self.Fw[:, [2, 0]]])
        E = np.concatenate([E, E[:, ::-1]])
        E = np.unique(E, axis=0)
        E = E[E[:, 0] != E[:, 1]]
        self.nb_ptr = np.concatenate([[0], np.cumsum(np.bincount(E[:, 0], minlength=nw))]).astype(np.int32)
        self.nb_idx = E[:, 1].astype(np.int32)
        # boundary edges (an edge on one welded face only): the base's open borders
        Eu = np.sort(np.concatenate([self.Fw[:, [0, 1]], self.Fw[:, [1, 2]], self.Fw[:, [2, 0]]]), axis=1)
        _, cnt = np.unique(Eu, axis=0, return_counts=True)
        self.n_border_edges = int((cnt == 1).sum())
        self.n_nonmanifold_edges = int((cnt > 2).sum())

    # ---------------------------------------------------------------------------------------------- skeleton
    def _skeleton(self, j, acc):
        nodes = j['nodes']
        n = len(nodes)
        self.node_names = [nd.get('name', f'node{i}') for i, nd in enumerate(nodes)]
        parent = -np.ones(n, np.int64)
        for i, nd in enumerate(nodes):
            for c in nd.get('children', []):
                parent[c] = i
        self.node_parent = parent
        world = [None] * n

        def W(i):
            if world[i] is None:
                L = _local(nodes[i])
                world[i] = L if parent[i] < 0 else W(parent[i]) @ L
            return world[i]
        for i in range(n):
            W(i)
        self.node_world = np.stack(world)
        self.node_children = [nd.get('children', []) for nd in nodes]
        skins = j.get('skins', [])
        self.skin = skins[0] if skins else None
        if self.skin:
            self.joint_nodes = list(self.skin['joints'])
            self.joint_names = [self.node_names[i] for i in self.joint_nodes]
            self.ibm = acc(self.skin['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1).astype(np.float64)
            self.joint_world = np.stack([self.node_world[i] for i in self.joint_nodes])
            jset = {nd: k for k, nd in enumerate(self.joint_nodes)}
            # a joint's direction: toward its only child joint; else from its parent joint to it (a branch or a leaf)
            P = self.joint_world[:, :3, 3]
            D = np.zeros_like(P)
            for k, nd in enumerate(self.joint_nodes):
                kids = [jset[c] for c in self.node_children[nd] if c in jset]
                if len(kids) == 1:
                    d = P[kids[0]] - P[k]
                elif parent[nd] in jset:
                    d = P[k] - P[jset[parent[nd]]]
                else:
                    d = np.zeros(3)
                ln = np.linalg.norm(d)
                D[k] = d / ln if ln > 1e-9 else 0.0
            self.joint_dir = D
            self.joint_pos = P
        self.sockets = {}
        for i, nm in enumerate(self.node_names):
            if nm.startswith('socket_') or nm.startswith('seat_'):
                self.sockets[nm] = self.node_world[i]

    def _chains(self, ex):
        self.chains = []
        if ex.get('chains'):
            for c in ex['chains']:
                ids = [self.joint_names.index(nm) for nm in c['joints'] if nm in self.joint_names]
                self.chains.append(dict(name=c['name'], joints=ids, s=np.asarray(c.get('s', np.linspace(0, 1, len(ids)))),
                                        radius=np.asarray(c['radius']) if 'radius' in c else None,
                                        kind=c.get('kind', '')))
            return
        if self.skin is None:
            return
        jset = {nd: k for k, nd in enumerate(self.joint_nodes)}
        kids = {k: [jset[c] for c in self.node_children[nd] if c in jset] for k, nd in enumerate(self.joint_nodes)}
        starts = [k for k in kids if self.node_parent[self.joint_nodes[k]] not in jset
                  or len(kids[jset[self.node_parent[self.joint_nodes[k]]]]) != 1]
        for s0 in starts:
            run = [s0]
            while len(kids[run[-1]]) == 1:
                run.append(kids[run[-1]][0])
            if len(run) >= 3:
                L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(self.joint_pos[run], axis=0), axis=1))])
                self.chains.append(dict(name=self.joint_names[s0], joints=run, s=L / max(L[-1], 1e-9), radius=None,
                                        kind='derived'))

    # ---------------------------------------------------------------------------------------------- queries
    def joint_ids(self, pattern):
        rx = re.compile(pattern)
        return np.array([k for k, nm in enumerate(self.joint_names) if rx.search(nm)], np.int64)

    def node_ids(self, pattern):
        rx = re.compile(pattern)
        return [i for i, nm in enumerate(self.node_names) if rx.search(nm)]

    def tri_points(self, tri, bary):
        """surface points at (triangle, barycentrics): position, interpolated (renormalised) normal, glTF uv, set"""
        tri = np.asarray(tri, np.int64)
        b = np.asarray(bary, np.float64)
        Fv = self.F[tri]
        P = np.einsum('nk,nkd->nd', b, self.V[Fv])
        N = np.einsum('nk,nkd->nd', b, self.N[Fv])
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-30)
        UV = np.einsum('nk,nkd->nd', b, self.UV[Fv])
        return P, N, UV, self.face_set[tri]

    def tri_weights(self, tri, bary, k=4):
        """the root's skin weights: the three corners' joint weights blended by barycentrics, the top k kept and
        renormalised (one vector per root: CG 16.36)"""
        tri = np.asarray(tri, np.int64)
        b = np.asarray(bary, np.float64)
        n = len(tri)
        Fv = self.F[tri]
        nj = len(self.joint_names)
        acc = np.zeros((n, nj))
        rows = np.arange(n)[:, None]
        for c in range(3):
            Jc = self.J[Fv[:, c]]
            Wc = self.W[Fv[:, c]] * b[:, c:c + 1]
            for s in range(Jc.shape[1]):
                np.add.at(acc, (rows[:, 0], Jc[:, s]), Wc[:, s])
        top = np.argsort(-acc, axis=1)[:, :k]
        w = np.take_along_axis(acc, top, axis=1)
        w = w / np.maximum(w.sum(1, keepdims=True), 1e-30)
        return top.astype(np.uint16), w.astype(np.float32)

    def joint_weight_field(self, ids, verts=None):
        """sum of the skin weights of the joints `ids`, per vertex (or per given vertex indices)"""
        J = self.J if verts is None else self.J[verts]
        Wt = self.W if verts is None else self.W[verts]
        return np.where(np.isin(J, ids), Wt, 0.0).sum(1)

    def px_per_m(self):
        """texels per metre of each set at its base colour map's resolution (the median over its faces)"""
        out = {}
        for k, s in enumerate(self.sets):
            m = self.face_set == k
            img = self.tex(s, 'base')
            res = img.shape[0] if img is not None else 1024
            Fv = self.F[m]
            uva = 0.5 * np.abs(cross2(self.UV[Fv[:, 1]] - self.UV[Fv[:, 0]], self.UV[Fv[:, 2]] - self.UV[Fv[:, 0]]))
            r = np.sqrt(uva / np.maximum(self.area[m], 1e-30)) * res
            out[s] = float(np.median(r[np.isfinite(r)]))
        return out

    # ---------------------------------------------------------------------------------------------- textures
    def tex_index(self, set_name, slot):
        m = self.json['materials'][self.set_material[self.sets.index(set_name)]]
        pbr = m.get('pbrMetallicRoughness', {})
        ext = m.get('extensions', {})
        if slot == 'base':
            return pbr.get('baseColorTexture', {}).get('index')
        if slot == 'orm':
            return pbr.get('metallicRoughnessTexture', {}).get('index')
        if slot == 'normal':
            return m.get('normalTexture', {}).get('index')
        if slot == 'masks':
            return ext.get('KHR_materials_volume', {}).get('thicknessTexture', {}).get('index')
        if slot == 'display':
            return m.get('emissiveTexture', {}).get('index')
        if slot == 'growth':
            return ext.get('KHR_materials_iridescence', {}).get('iridescenceTexture', {}).get('index')
        raise KeyError(slot)

    def tex(self, set_name, slot):
        """the map as float32 (h, w, c) in 0..1 (sRGB values as stored: no conversion), or None"""
        key = (set_name, slot)
        if key in self._tex_cache:
            return self._tex_cache[key]
        ti = self.tex_index(set_name, slot)
        img = None
        if ti is not None:
            from PIL import Image
            t = self.json['textures'][ti]
            src = t.get('source', t.get('extensions', {}).get('EXT_texture_webp', {}).get('source'))
            im = self.json['images'][src]
            v = self.json['bufferViews'][im['bufferView']]
            data = self._bin[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']]
            pil = Image.open(io.BytesIO(data))
            img = np.asarray(pil, np.float32) / 255.0
            if img.ndim == 2:
                img = img[:, :, None]
        self._tex_cache[key] = img
        return img

    def sample(self, set_name, slot, uv):
        """bilinear sample of a map at glTF uvs (n, 2) (clamped), returns (n, c)"""
        img = self.tex(set_name, slot)
        h, w, c = img.shape
        x = np.clip(uv[:, 0] * w - 0.5, 0, w - 1)
        y = np.clip(uv[:, 1] * h - 0.5, 0, h - 1)
        x0 = np.floor(x).astype(np.int64)
        y0 = np.floor(y).astype(np.int64)
        x1 = np.minimum(x0 + 1, w - 1)
        y1 = np.minimum(y0 + 1, h - 1)
        fx = (x - x0)[:, None]
        fy = (y - y0)[:, None]
        return ((img[y0, x0] * (1 - fx) + img[y0, x1] * fx) * (1 - fy)
                + (img[y1, x0] * (1 - fx) + img[y1, x1] * fx) * fy)

    def props(self):
        """the skin mesh's other primitives (eyes, beak, suckers: what the coat must not cover but the review renders
        must show): [(name, V (n, 3), F (m, 3), mean albedo (linear rgb))]"""
        j, acc = self.json, self._acc
        out = []
        for pi, p in enumerate(j['meshes'][self.skin_mesh]['primitives']):
            if pi in self.skin_prims or len(getattr(self, 'skin_meshes', [0])) > 1:   # (B3) multi-mesh skin: none
                continue
            V = acc(p['attributes']['POSITION']).astype(np.float64)
            F = acc(p['indices']).reshape(-1, 3).astype(np.int64)
            used = np.unique(F)
            remap = -np.ones(len(V), np.int64)
            remap[used] = np.arange(len(used))
            mat = j['materials'][p['material']] if 'material' in p else {}
            col = np.array([0.5, 0.5, 0.5])
            ti = mat.get('pbrMetallicRoughness', {}).get('baseColorTexture', {}).get('index')
            if ti is not None:
                from PIL import Image
                t = j['textures'][ti]
                src = t.get('source', t.get('extensions', {}).get('EXT_texture_webp', {}).get('source'))
                v = j['bufferViews'][j['images'][src]['bufferView']]
                img = np.asarray(Image.open(io.BytesIO(self._bin[v.get('byteOffset', 0):v.get('byteOffset', 0)
                                                                   + v['byteLength']])).convert('RGB'), np.float32)
                col = ((img / 255.0) ** 2.2).reshape(-1, 3).mean(0)
            out.append((mat.get('name', f'prim{pi}'), V[used], remap[F], col))
        return out

    def summary(self):
        return dict(path=self.path, sha1=self.sha1, species=self.species, verts=len(self.V), tris=len(self.F),
                    welded=len(self.Vw), border_edges=self.n_border_edges, nonmanifold_edges=self.n_nonmanifold_edges,
                    sets={s: int((self.face_set == k).sum()) for k, s in enumerate(self.sets)},
                    area_m2=float(self.area.sum()), joints=len(self.joint_names) if self.skin else 0,
                    chains=[c['name'] for c in self.chains], sockets=sorted(self.sockets))
