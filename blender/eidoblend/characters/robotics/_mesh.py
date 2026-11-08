"""eidoblend.characters.robotics._mesh: a subset of a mesh's faces as a new mesh, exactly as it shades.

The WebGPU edition isolates parts by giving a geometry a new index buffer over the same vertices (loadPart, the track
shoes). Blender meshes cannot share vertex data that way, so the subset is copied: positions, every face-corner and
face attribute (UV maps, colours, material_index ...), the materials, and the ORIGINAL corner normals as custom normals,
so the copy shades exactly like those faces did. Face order is kept.

    submesh(me, faces, name) -> bpy.types.Mesh
"""

from __future__ import annotations

import bpy
import numpy as np

_SKIP = {'position', 'sharp_face', 'sharp_edge', 'custom_normal'}


def _attr_array(a, n):
    kind = {'FLOAT': (np.float32, 1, 'value'), 'INT': (np.int32, 1, 'value'), 'FLOAT2': (np.float32, 2, 'vector'),
            'FLOAT_VECTOR': (np.float32, 3, 'vector'), 'FLOAT_COLOR': (np.float32, 4, 'color'),
            'BYTE_COLOR': (np.float32, 4, 'color'), 'BOOLEAN': (bool, 1, 'value'), 'INT8': (np.int32, 1, 'value'),
            'INT32_2D': (np.int32, 2, 'value'), 'QUATERNION': (np.float32, 4, 'value')}.get(a.data_type)
    if kind is None:
        return None, None
    dt, w, prop = kind
    arr = np.empty(n * w, dtype=dt)
    a.data.foreach_get(prop, arr)
    return arr.reshape(n, w) if w > 1 else arr, prop


def submesh(me, faces, name):
    faces = np.asarray(sorted(set(int(f) for f in faces)), dtype=np.int64)
    nP, nL, nV = len(me.polygons), len(me.loops), len(me.vertices)
    ls = np.empty(nP, np.int32)
    lt = np.empty(nP, np.int32)
    me.polygons.foreach_get('loop_start', ls)
    me.polygons.foreach_get('loop_total', lt)
    lv = np.empty(nL, np.int32)
    me.loops.foreach_get('vertex_index', lv)
    cnt = lt[faces]
    loop_idx = (np.repeat(ls[faces], cnt) + (np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt))).astype(np.int64)
    used = np.unique(lv[loop_idx])
    remap = np.full(nV, -1, np.int64)
    remap[used] = np.arange(len(used))
    co = np.empty(nV * 3, np.float32)
    me.vertices.foreach_get('co', co)
    cn = np.empty(nL * 3, np.float32)
    me.corner_normals.foreach_get('vector', cn)
    new = bpy.data.meshes.new(name)
    new.vertices.add(len(used))
    new.vertices.foreach_set('co', co.reshape(-1, 3)[used].ravel())
    new.loops.add(len(loop_idx))
    new.loops.foreach_set('vertex_index', remap[lv[loop_idx]].astype(np.int32))
    new.polygons.add(len(faces))
    new.polygons.foreach_set('loop_start', (np.cumsum(cnt) - cnt).astype(np.int32))
    new.polygons.foreach_set('loop_total', cnt.astype(np.int32))
    new.update(calc_edges=True)
    for m in me.materials:
        new.materials.append(m)
    for a in me.attributes:
        if a.name.startswith('.') or a.name in _SKIP or a.domain not in ('POINT', 'CORNER', 'FACE'):
            continue
        n = {'POINT': nV, 'CORNER': nL, 'FACE': nP}[a.domain]
        arr, prop = _attr_array(a, n)
        if arr is None:
            continue
        sel = {'POINT': used, 'CORNER': loop_idx, 'FACE': faces}[a.domain]
        b = new.attributes.get(a.name) or new.attributes.new(a.name, a.data_type, a.domain)
        b.data.foreach_set(prop, np.ascontiguousarray(arr[sel]).ravel())
    if me.uv_layers.active is not None and me.uv_layers.active.name in new.uv_layers:
        new.uv_layers.active = new.uv_layers[me.uv_layers.active.name]
    new.polygons.foreach_set('use_smooth', np.ones(len(faces), dtype=bool))
    new.normals_split_custom_set(cn.reshape(-1, 3)[loop_idx].tolist())
    return new                 # no validate(): it would drop degenerate triangles and break the part-per-face table
