"""PlantGeo: one plant's geometry as the generators emit it, in the WebGPU edition's three.js space (Y up), and its
one-time conversion into a Blender mesh (Z up: three (x, y, z) -> Blender (x, -z, y), a proper rotation, so triangle
winding and the generators' normals carry over).

The generators run verbatim in three space; nothing else in the package touches three coordinates.
"""
import numpy as np

# three -> Blender basis change (columns: where three's x, y, z land in Blender)
C3B = np.array([[1.0, 0.0, 0.0],
                [0.0, 0.0, -1.0],
                [0.0, 1.0, 0.0]])


def to_blender(v):
    """(..., 3) three-space vectors -> Blender."""
    v = np.asarray(v, dtype=np.float64)
    return v @ C3B.T


class PlantGeo:
    """pos (V,3), uv (V,2), aH (V,), tris (T,3) int, nrm (V,3) or None (= area-weighted vertex normals),
    extra: {name: (V,) or (V,3) arrays, per vertex}, mat (T,) int material slot per triangle, stats: dict."""

    def __init__(self, pos, uv, aH, tris, nrm=None, extra=None, mat=None, stats=None):
        self.pos = np.asarray(pos, dtype=np.float64).reshape(-1, 3)
        self.uv = np.asarray(uv, dtype=np.float64).reshape(-1, 2)
        self.aH = np.asarray(aH, dtype=np.float64).reshape(-1)
        self.tris = np.asarray(tris, dtype=np.int64).reshape(-1, 3)
        self.nrm = None if nrm is None else np.asarray(nrm, dtype=np.float64).reshape(-1, 3)
        self.extra = dict(extra or {})
        self.mat = None if mat is None else np.asarray(mat, dtype=np.int64).reshape(-1)
        self.stats = dict(stats or {})

    @property
    def nverts(self):
        return len(self.pos)

    @property
    def ntris(self):
        return len(self.tris)


def vertex_normals(pos, tris):
    """three's BufferGeometry.computeVertexNormals for indexed geometry: un-normalised face cross products
    (cb x ab, i.e. area-weighted) summed per vertex index, no welding across duplicated positions."""
    pos = np.asarray(pos, dtype=np.float64)
    a, b, c = pos[tris[:, 0]], pos[tris[:, 1]], pos[tris[:, 2]]
    fn = np.cross(c - b, a - b)
    n = np.zeros_like(pos)
    for k in range(3):
        np.add.at(n, tris[:, k], fn)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1.0
    return n / ln


def blend_normals_up(n, k):
    """vegetation.js blendNormalsUp: lean each normal toward +Y (three up) by k."""
    m = np.asarray(n, dtype=np.float64) * (1 - k)
    m[:, 1] += k
    ln = np.linalg.norm(m, axis=1, keepdims=True)
    ln[ln == 0] = 1.0
    return m / ln


def merge(geos):
    """Concatenate PlantGeos (same extra keys) into one; triangle indices offset."""
    pos, uv, aH, tris, nrm, mat = [], [], [], [], [], []
    keys = set()
    for g in geos:
        keys |= set(g.extra)
    extra = {k: [] for k in keys}
    off = 0
    for g in geos:
        pos.append(g.pos)
        uv.append(g.uv)
        aH.append(g.aH)
        tris.append(g.tris + off)
        nrm.append(g.nrm if g.nrm is not None else vertex_normals(g.pos, g.tris))
        mat.append(g.mat if g.mat is not None else np.zeros(g.ntris, np.int64))
        for k in keys:
            v = g.extra.get(k)
            if v is None:
                like = next(x.extra[k] for x in geos if k in x.extra)
                v = np.zeros((g.nverts,) + np.shape(like)[1:])
            extra[k].append(np.asarray(v))
        off += g.nverts
    return PlantGeo(np.concatenate(pos), np.concatenate(uv), np.concatenate(aH), np.concatenate(tris),
                    np.concatenate(nrm), {k: np.concatenate(v) for k, v in extra.items()}, np.concatenate(mat))


def to_blender_mesh(geo, name, materials=(), custom_normals=True, uv_name='UVMap'):
    """Build a bpy Mesh from a three-space PlantGeo: positions and normals through C3B, per-corner UVs from the
    per-vertex ones (seams stay as the generators emit them: coincident vertices are never merged), aH and every
    extra array as point attributes (vectors converted to Blender axes when their name ends in '_v')."""
    import bpy
    me = bpy.data.meshes.new(name)
    P = to_blender(geo.pos).astype(np.float32)
    nv, nt = geo.nverts, geo.ntris
    me.vertices.add(nv)
    me.vertices.foreach_set('co', P.ravel())
    me.loops.add(nt * 3)
    me.loops.foreach_set('vertex_index', geo.tris.astype(np.int32).ravel())
    me.polygons.add(nt)
    me.polygons.foreach_set('loop_start', (np.arange(nt, dtype=np.int32) * 3))
    me.update(calc_edges=True)
    me.polygons.foreach_set('use_smooth', np.ones(nt, dtype=bool))
    uvl = me.uv_layers.new(name=uv_name)
    uvl.data.foreach_set('uv', geo.uv[geo.tris.ravel()].astype(np.float32).ravel())
    a = me.attributes.new('aH', 'FLOAT', 'POINT')
    a.data.foreach_set('value', geo.aH.astype(np.float32))
    for k, v in geo.extra.items():
        v = np.asarray(v)
        if v.ndim == 2 and v.shape[1] == 3:
            vv = to_blender(v) if k.endswith('_v') else v
            at = me.attributes.new(k, 'FLOAT_VECTOR', 'POINT')
            at.data.foreach_set('vector', vv.astype(np.float32).ravel())
        else:
            at = me.attributes.new(k, 'FLOAT', 'POINT')
            at.data.foreach_set('value', v.astype(np.float32).ravel())
    for m in materials:
        me.materials.append(m)
    if geo.mat is not None and len(materials) > 1:
        me.polygons.foreach_set('material_index', geo.mat.astype(np.int32))
    if custom_normals:
        N = geo.nrm if geo.nrm is not None else vertex_normals(geo.pos, geo.tris)
        me.normals_split_custom_set_from_vertices([tuple(n) for n in to_blender(N)])
    me.update()
    return me
