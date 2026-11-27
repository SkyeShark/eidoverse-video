"""export_room.py (Blender): one SAME SEED room, made by the Blender edition, written out as this edition's files.

    blender --background --factory-startup <made>/<room>.blend --python export_room.py -- \
        --room kitchen --made <made folder> --eidoblend <Blender edition>/blender --cache <eidoverse/assets/cache> \
        --out eidoverse/assets/sets/same_seed/kitchen --models eidoverse/assets/models [--steps rest,lows,light,meta]

The room is made on the Blender edition (branch blender: python blender/eidoblend/sets/same_seed/make.py <room>); this
script reads its made .blend and writes, in three's space (metres, +Y up: Blender's (x, y, z) is three's (x, z, -y)):

  rest    <models>/same_seed_<room>_rest.glb: every part that is not a low (walls, floors, trim, the small things),
          keeping each part's transform, its material slots by name and every UV map by name (vertex attributes
          _UV_<NAME>, Blender's own UVs) with the tangents of each UV a normal map reads (_TANGENT_<NAME>), the
          normals Blender shades with, and faces where two parts touch drawn apart (separate_touching); and
          <out>/materials.json: each of those materials' shader node graph (and the world's), which
          eidoverse/sets/same_seed/nodes.js rebuilds in TSL. The pictures they read: CC0 sets by ID (fetched into
          the shared library), the room's drawn prints copied to <out>/prints/.
  lows    <models>/same_seed_<room>_<atlas>.glb, one per atlas (the parts with UV 'atlas'): their look baked down by
          Cycles at the atlas's size to base colour, ORM (the GPU bake's ambient occlusion, roughness, metalness),
          a tangent-space normal and, where a part glows or is cut out, emission and alpha.
  light   <out>/room.json's lights (each Blender light as its three.js light), the bounce of the room's volume probe
          as a grid of L2 spherical harmonics (Cycles, at each grid point, lamps unseen) and the reflection probe's
          panorama (<out>/reflection.hdr, Cycles).
  meta    <out>/room.json: cameras, marks, render settings, the CC0 models placed (Poly Haven IDs, each mesh's
          matrix), the world.
Cycles runs on the GPU (OptiX, then CUDA) when it can. Nothing here is needed at run time.
"""

import argparse
import json
import math
import os
import re
import shutil
import sys
import time

sys.dont_write_bytecode = True

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from glb import GLB  # noqa: E402

T0 = time.time()
C = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))       # three -> Blender (C @ v3 = vb)
CI = C.transposed()                                                          # Blender -> three


def log(*a):
    print(f'[export {time.time() - T0:6.1f}s]', *a, flush=True)


def v3(v):
    """a Blender point or direction in three's space"""
    return [float(v[0]), float(v[2]), float(-v[1])]


def colmajor(m):
    return [m[r][c] for c in range(4) for r in range(4)]


def strip_suffix(s):
    return re.sub(r'\.\d{3}$', '', s)


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument('--room', required=True)
    p.add_argument('--made', required=True)
    p.add_argument('--eidoblend', required=True, help="the Blender edition's blender/ folder (its eidoblend package)")
    p.add_argument('--cache', required=True, help='the shared CC0 library, eidoverse/assets/cache')
    p.add_argument('--out', required=True)
    p.add_argument('--models', required=True)
    p.add_argument('--steps', default='rest,lows,light,meta')
    p.add_argument('--quality', type=int, default=88, help='JPEG quality of the baked maps')
    p.add_argument('--max-size', type=int, default=4096, help='the largest baked map')
    p.add_argument('--bake-samples', type=int, default=8)
    p.add_argument('--grid-max', type=int, default=1200, help='at most this many bounce probes')
    p.add_argument('--grid-scale', type=float, default=2.0, help="the bounce grid's cells per the volume probe's own")
    p.add_argument('--grid-bounces', type=int, default=4, help='diffuse bounces in the bounce capture (Cycles)')
    p.add_argument('--grid-samples', type=int, default=48)
    p.add_argument('--grid-res', type=int, default=48, help='each bounce probe panorama is this wide (half as high)')
    p.add_argument('--reflection', default='1024x512')
    return p.parse_args(a)


A = args()
ROOM = A.room
os.makedirs(A.out, exist_ok=True)
os.makedirs(A.models, exist_ok=True)
sys.path.insert(0, os.path.abspath(A.eidoblend))
import importlib  # noqa: E402

RM = importlib.import_module(f'eidoblend.sets.same_seed.{ROOM}')
SC = bpy.context.scene
COLL = bpy.data.collections[RM.COLLECTION]
BAKE_DIR = os.path.join(A.made, 'bake')
PRINTS_DIR = os.path.join(A.made, 'prints')
CACHE = os.path.abspath(A.cache)
OBJS = [o for o in COLL.all_objects]
DG = bpy.context.evaluated_depsgraph_get()


# ----------------------------------------------------------------------------------------- what each part is ---

def atlas_of(o):
    """the atlas a low belongs to (UV 'atlas'; its material reads <bake>/<atlas>_*.png), else None"""
    if o.type != 'MESH' or 'atlas' not in o.data.uv_layers:
        return None
    for s in o.material_slots:
        m = s.material
        if not (m and m.node_tree):
            continue
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image and n.image.filepath:
                p = os.path.abspath(bpy.path.abspath(n.image.filepath))
                if os.path.dirname(p).lower() == os.path.abspath(BAKE_DIR).lower():
                    return os.path.basename(p).rsplit('_', 1)[0]
    for f in os.listdir(BAKE_DIR) if os.path.isdir(BAKE_DIR) else []:
        if f.endswith('.json') and not f.endswith(('_high.json', '_report.json')) and f != 'atlases.json':
            try:
                d = json.load(open(os.path.join(BAKE_DIR, f), encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if o.name in d.get('names', []):
                return f[:-5]
    return '_atlas'


def cc0_models():
    """the room's CC0 models (its cc0.json, and the houseplants' when it grows them): [(id, res, gltf path, json)]"""
    out = []
    for man in (os.path.join(A.eidoblend, 'eidoblend', 'sets', 'same_seed', ROOM, 'cc0.json'),):
        spec = json.load(open(man, encoding='utf-8'))
        for m in spec.get('models', []):
            d = os.path.join(CACHE, 'models', f"{m['id']}_{m.get('res', '1k')}")
            g = next((os.path.join(d, f) for f in os.listdir(d) if f.endswith('.gltf')), None) if os.path.isdir(d) else None
            if g:
                out.append((m['id'], m.get('res', '1k'), g, json.load(open(g, encoding='utf-8'))))
    return out


MODELS = cc0_models()


def model_of(o):
    """(model id, res, glTF mesh index) of a loaded CC0 part, by its mesh's and materials' names"""
    mats = {strip_suffix(s.material.name) for s in o.material_slots if s.material}
    co = np.empty(len(o.data.vertices) * 3, np.float32)
    o.data.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    lo, hi = co.min(0), co.max(0)
    best = None
    for mid, res, path, js in MODELS:
        gm = {strip_suffix(m.get('name') or '') for m in js.get('materials', [])}
        for k, mesh in enumerate(js.get('meshes', [])):
            bl, bh = np.full(3, 1e9), np.full(3, -1e9)
            for pr in mesh['primitives']:
                acc = js['accessors'][pr['attributes']['POSITION']]
                a, b = np.array(acc['min']), np.array(acc['max'])
                a, b = np.array([a[0], -b[2], a[1]]), np.array([b[0], -a[2], b[1]])      # (glTF -> Blender: x, -z, y)
                bl, bh = np.minimum(bl, a), np.maximum(bh, b)
            err = float(np.abs(bl - lo).max() + np.abs(bh - hi).max())
            if err > 2e-3 * max(1.0, float((hi - lo).max())):
                continue                                # (the importer keeps a glTF mesh's vertices; the box tells it)
            score = (len(mats & gm), mesh.get('name') == o.data.name, -err)
            if best is None or score > best[0]:
                best = (score, mid, res, k)
    return best[1:] if best else None


def cc0_identity(o):
    """(model id, res, its glTF) of a part that came from a CC0 model (tagged by the look, or loaded as an asset), else
    None: by the tag's id, else by the model whose materials share the most names with the part's"""
    tag = o.get('cc0')
    if not (o.get('eido_loaded_asset') or isinstance(tag, str)):
        return None
    mats = {strip_suffix(s.material.name) for s in o.material_slots if s.material}
    best = None
    for mid, res, path, js in MODELS:
        if isinstance(tag, str) and tag != mid:
            continue
        gm = {strip_suffix(m.get('name') or '') for m in js.get('materials', [])}
        score = len(mats & gm)
        if best is None or score > best[0]:
            best = (score, mid, res, js)
    return best[1:] if best else None


def own_material(m, js):
    """the material is one the CC0 model ships with (by name)"""
    return m is not None and strip_suffix(m.name) in {strip_suffix(x.get('name') or '') for x in js.get('materials', [])}


KIND, CC0_OF = {}, {}
for o in OBJS:
    if o.type != 'MESH':
        continue
    ident = cc0_identity(o)
    if ident is not None:
        mid, res, js = ident
        CC0_OF[o.name] = (mid, res, js)
        hit = model_of(o)
        same = hit is not None and hit[0] == mid
        own = all(own_material(s.material, js) for s in o.material_slots)
        n_uv = 0
        if same:
            at = js['meshes'][hit[2]]['primitives'][0]['attributes']
            n_uv = sum(1 for k in at if k.startswith('TEXCOORD_'))
        extra_uv = len(o.data.uv_layers) > max(1, n_uv)
        if same and own and not extra_uv:
            KIND[o.name] = ('model', hit)                          # as it ships: loaded by ID and placed
        else:
            KIND[o.name] = ('rest', None)                          # changed here (its mesh or a material): its geometry
    elif atlas_of(o):                                              # ships, its own materials still by ID
        KIND[o.name] = ('low', atlas_of(o))
    else:
        KIND[o.name] = ('rest', None)


# ------------------------------------------------------------------------------------------- mesh arrays ---

def normal_map_uvs(mats):
    """the UV maps the materials' normal-map nodes read"""
    out = set()
    for m in mats:
        if m and m.node_tree:
            for n in walk_nodes(m.node_tree):
                if n.bl_idname == 'ShaderNodeNormalMap' and n.space == 'TANGENT':
                    out.add(n.uv_map or '')
    return out


def walk_nodes(tree):
    for n in tree.nodes:
        yield n
        if n.bl_idname == 'ShaderNodeGroup' and n.node_tree:
            yield from walk_nodes(n.node_tree)


def attribute_names(mats):
    """the mesh attributes the materials' Attribute nodes read"""
    out = set()
    for m in mats:
        if m and m.node_tree:
            for n in walk_nodes(m.node_tree):
                if n.bl_idname == 'ShaderNodeAttribute' and n.attribute_type == 'GEOMETRY' and n.attribute_name:
                    out.add(n.attribute_name)
    return out


def attribute_per_loop(me, name, lv):
    """a mesh attribute as (loops, 4) floats (colours linear, vectors padded with 0, alpha 1 where it has none)"""
    a = me.attributes.get(name) or (me.color_attributes.get(name) if hasattr(me, 'color_attributes') else None)
    if a is None:
        return None
    n = len(a.data)
    if a.data_type in ('FLOAT_COLOR', 'BYTE_COLOR'):
        v = np.empty(n * 4, np.float32)
        a.data.foreach_get('color', v)
        v = v.reshape(-1, 4)
    elif a.data_type in ('FLOAT_VECTOR',):
        v3_ = np.empty(n * 3, np.float32)
        a.data.foreach_get('vector', v3_)
        v = np.concatenate([v3_.reshape(-1, 3), np.ones((n, 1), np.float32)], 1)
    elif a.data_type == 'FLOAT2':
        v2 = np.empty(n * 2, np.float32)
        a.data.foreach_get('vector', v2)
        v = np.concatenate([v2.reshape(-1, 2), np.zeros((n, 1), np.float32), np.ones((n, 1), np.float32)], 1)
    elif a.data_type in ('FLOAT', 'INT', 'BOOLEAN', 'INT8'):
        s = np.empty(n, np.float32)
        a.data.foreach_get('value', s)
        v = np.stack([s, s, s, np.ones(n, np.float32)], 1)
    else:
        return None
    if a.domain == 'POINT':
        return v[lv]
    if a.domain == 'CORNER':
        return v
    if a.domain == 'FACE':
        pl = np.empty(len(me.loops), np.int32)
        starts = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get('loop_start', starts)
        counts = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get('loop_total', counts)
        pl = np.repeat(np.arange(len(me.polygons)), counts)
        return v[pl]
    return None


def mesh_arrays(o, tangent_uvs=(), texcoord0=None, orco=False, attrs=()):
    """the evaluated mesh as corner-deduplicated vertices (three's space) and triangles per material slot"""
    eo = o.evaluated_get(DG)
    me = eo.to_mesh()
    try:
        if tangent_uvs and any(len(p.vertices) > 4 for p in me.polygons):
            # calc_tangents wants triangles and quads, so the n-gons are cut; each corner keeps the normal it had (a
            # custom normal, a Weighted Normal's, is stored against its corner's fan of faces, and the cut moves it:
            # a wall's corner by a door turned 50 degrees, and a long triangle shaded dark across the wall)
            had = np.empty(len(me.loops) * 3, np.float32)
            me.corner_normals.foreach_get('vector', had)
            had = had.reshape(-1, 3)
            lv0 = np.empty(len(me.loops), np.int32)
            me.loops.foreach_get('vertex_index', lv0)
            normal_of = {}
            for p in me.polygons:
                for li in p.loop_indices:
                    normal_of[(p.index, int(lv0[li]))] = had[li]
            bm = bmesh.new()
            bm.from_mesh(me)
            face_was = bm.faces.layers.int.new('_face_was')
            bm.faces.index_update()
            for f in bm.faces:
                f[face_was] = f.index
            bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
            bm.to_mesh(me)
            bm.free()
            was = np.empty(len(me.polygons), np.int32)
            me.attributes['_face_was'].data.foreach_get('value', was)
            me.attributes.remove(me.attributes['_face_was'])
            lv0 = np.empty(len(me.loops), np.int32)
            me.loops.foreach_get('vertex_index', lv0)
            keep = np.empty((len(me.loops), 3), np.float32)
            for p in me.polygons:
                for li in p.loop_indices:
                    keep[li] = normal_of[(int(was[p.index]), int(lv0[li]))]
            me.normals_split_custom_set([tuple(n) for n in keep])
        me.calc_loop_triangles()
        nl, nv, nt = len(me.loops), len(me.vertices), len(me.loop_triangles)
        if nt == 0:
            return None
        lv = np.empty(nl, np.int32)
        me.loops.foreach_get('vertex_index', lv)
        co = np.empty(nv * 3, np.float32)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        nrm = np.empty(nl * 3, np.float32)
        me.corner_normals.foreach_get('vector', nrm)
        nrm = nrm.reshape(-1, 3)
        tl = np.empty(nt * 3, np.int32)
        me.loop_triangles.foreach_get('loops', tl)
        tm = np.empty(nt, np.int32)
        me.loop_triangles.foreach_get('material_index', tm)
        cols = {'P': co[lv], 'N': nrm}
        for uvl in me.uv_layers:
            a = np.empty(nl * 2, np.float32)
            uvl.uv.foreach_get('vector', a)
            cols['UV:' + uvl.name] = a.reshape(-1, 2)
        for name in tangent_uvs:
            uvn = name or (me.uv_layers.active.name if me.uv_layers.active else None)
            if not uvn or uvn not in me.uv_layers:
                continue
            me.calc_tangents(uvmap=uvn)
            t = np.empty(nl * 3, np.float32)
            me.loops.foreach_get('tangent', t)
            s = np.empty(nl, np.float32)
            me.loops.foreach_get('bitangent_sign', s)
            cols['T:' + uvn] = np.concatenate([t.reshape(-1, 3), s[:, None]], 1)
            me.free_tangents()
        for an in attrs:
            v = attribute_per_loop(me, an, lv)
            if v is not None and len(v) == nl:
                cols['A:' + an] = v.astype(np.float32)
            else:
                log('attribute', an, 'not found on', o.name)
        if orco:
            loc, size = Vector(me.texspace_location), Vector(me.texspace_size)
            lo = np.array(loc - size, np.float32)
            span = np.maximum(np.array(size * 2.0, np.float32), 1e-8)
            cols['ORCO'] = (co[lv] - lo) / span
        keys = list(cols)
        big = np.concatenate([cols[k] for k in keys], 1).astype(np.float32)
        big = np.ascontiguousarray(big)
        view = big.view(np.dtype((np.void, big.dtype.itemsize * big.shape[1]))).ravel()
        _, first, inv = np.unique(view, return_index=True, return_inverse=True)
        verts = big[first]
        tri = inv.ravel()[tl].reshape(-1, 3).astype(np.uint32)
        out, c = {}, 0
        for k in keys:
            w = cols[k].shape[1]
            out[k] = np.ascontiguousarray(verts[:, c:c + w])
            c += w
        p = out['P']
        out['P'] = np.stack([p[:, 0], p[:, 2], -p[:, 1]], 1)
        n = out['N']
        n = np.stack([n[:, 0], n[:, 2], -n[:, 1]], 1)
        out['N'] = (n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)).astype(np.float32)
        for k in list(out):
            if k.startswith('T:'):
                t = out[k]
                out[k] = np.ascontiguousarray(np.stack([t[:, 0], t[:, 2], -t[:, 1], t[:, 3]], 1))
        return {'verts': out, 'tri': tri, 'mat': tm, 'nslots': max(1, len(o.material_slots))}
    finally:
        eo.to_mesh_clear()


def snorm8(a):
    """unit vectors as normalized int8 (KHR_mesh_quantization)"""
    return np.clip(np.round(a * 127.0), -127, 127).astype(np.int8)


def glb_prims(g, arr, mat_index_of_slot, uv_names_for_custom=True, texcoord0=None, tangent0=None):
    """write a mesh's vertex arrays once and one primitive per used material slot (normals and tangents quantized to
    int8, KHR_mesh_quantization); the UV map written as TEXCOORD_0 is not written again under its name (the mesh's
    extras.uv0 names it)"""
    v = arr['verts']
    g.use('KHR_mesh_quantization', required=True)
    attrs = {'POSITION': g.accessor(v['P'].astype(np.float32), 'VEC3', target=34962, minmax=True),
             'NORMAL': g.accessor(snorm8(v['N']), 'VEC3', target=34962, normalized=True)}
    if texcoord0 and ('UV:' + texcoord0) in v:
        uv = v['UV:' + texcoord0].copy()
        uv[:, 1] = 1.0 - uv[:, 1]
        attrs['TEXCOORD_0'] = g.accessor(uv.astype(np.float32), 'VEC2', target=34962)
    if tangent0 and ('T:' + tangent0) in v:
        attrs['TANGENT'] = g.accessor(snorm8(v['T:' + tangent0]), 'VEC4', target=34962, normalized=True)
    if uv_names_for_custom:
        for k in v:
            if k.startswith('UV:') and k[3:] == texcoord0 and 'TEXCOORD_0' in attrs:
                continue
            if k.startswith('UV:'):
                attrs['_UV_' + re.sub(r'[^A-Za-z0-9]', '_', k[3:]).upper()] = g.accessor(v[k].astype(np.float32), 'VEC2', target=34962)
            elif k.startswith('T:'):
                attrs['_TANGENT_' + re.sub(r'[^A-Za-z0-9]', '_', k[2:]).upper()] = g.accessor(snorm8(v[k]), 'VEC4', target=34962, normalized=True)
            elif k == 'ORCO':
                attrs['_ORCO'] = g.accessor(v[k].astype(np.float32), 'VEC3', target=34962)
            elif k.startswith('A:'):
                attrs['_ATTR_' + re.sub(r'[^A-Za-z0-9]', '_', k[2:]).upper()] = g.accessor(v[k].astype(np.float32), 'VEC4', target=34962)
    nverts = len(v['P'])
    prims = []
    for slot in range(arr['nslots']):
        sel = arr['tri'][arr['mat'] == slot]
        if not len(sel):
            continue
        idx = sel.ravel().astype(np.uint16 if nverts < 65536 else np.uint32)
        pr = {'attributes': attrs, 'indices': g.accessor(idx, 'SCALAR', target=34963)}
        mi = mat_index_of_slot(slot)
        if mi is not None:
            pr['material'] = mi
        prims.append(pr)
    return prims


def mesh_matrix(o):
    return colmajor(CI @ o.matrix_world @ C)


# ------------------------------------------------------------------------------------- shader node graphs ---

SKIP_PROPS = {'rna_type', 'name', 'label', 'location', 'location_absolute', 'width', 'width_hidden', 'height',
              'dimensions', 'select', 'show_options', 'show_preview', 'hide', 'mute', 'show_texture', 'bl_idname',
              'bl_label', 'bl_description', 'bl_icon', 'bl_static_type', 'bl_width_default', 'bl_width_min',
              'bl_width_max', 'bl_height_default', 'bl_height_min', 'bl_height_max', 'type', 'use_custom_color',
              'color', 'parent', 'internal_links', 'inputs', 'outputs', 'is_active_output', 'target', 'warning_propagation',
              'color_tag'}
IMAGES = {}


def image_ref(img):
    """where a picture comes from: a CC0 set by ID, an HDRI by ID, one of the room's prints (copied), or packed"""
    if img is None:
        return None
    key = img.name
    if key in IMAGES:
        return IMAGES[key]
    p = os.path.abspath(bpy.path.abspath(img.filepath)) if img.filepath else ''
    cs = img.colorspace_settings.name
    ref = {'colorspace': 'srgb' if cs in ('sRGB', 'sRGB EOTF') else ('linear' if cs != 'Non-Color' else 'data'),
           'alpha': img.alpha_mode}
    tex = os.path.join(CACHE, 'textures')
    hdr = os.path.join(CACHE, 'hdris')
    low = p.lower()
    if p and low.startswith(os.path.abspath(tex).lower() + os.sep):
        folder = os.path.basename(os.path.dirname(p))
        sid, res = folder.rsplit('_', 1)
        ref.update({'kind': 'cc0', 'id': sid, 'res': res, 'file': os.path.basename(p)})
    elif p and low.startswith(os.path.abspath(hdr).lower() + os.sep):
        folder = os.path.basename(os.path.dirname(p))
        sid, res = folder.rsplit('_', 1)
        ref.update({'kind': 'hdri', 'id': sid, 'res': res, 'file': os.path.basename(p)})
    elif p and os.path.isfile(p) and low.startswith(os.path.abspath(A.made).lower() + os.sep):
        rel = os.path.relpath(p, A.made).replace(os.sep, '/')
        if rel.startswith('bake/'):
            ref.update({'kind': 'bake', 'file': rel})
        else:
            dst = os.path.join(A.out, 'prints', os.path.basename(p))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(p, dst)
            ref.update({'kind': 'print', 'file': 'prints/' + os.path.basename(p)})
    else:
        name = re.sub(r'[^A-Za-z0-9_.-]', '_', strip_suffix(img.name))
        name = os.path.splitext(name)[0] + '.png'
        dst = os.path.join(A.out, 'prints', name)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        w, h = img.size
        if w and h:
            px = np.empty(w * h * img.channels, np.float32)
            img.pixels.foreach_get(px)
            px = px.reshape(h, w, img.channels)[::-1]
            save_png(dst, px, srgb=False)
        ref.update({'kind': 'print', 'file': 'prints/' + name})
    IMAGES[key] = ref
    return ref


def value_of(v):
    if isinstance(v, (int, float, bool, str)):
        return v
    try:
        return [float(x) for x in v]
    except TypeError:
        return None


def node_props(n):
    out = {}
    for p in n.bl_rna.properties:
        k = p.identifier
        if k in SKIP_PROPS or p.type in ('POINTER', 'COLLECTION'):
            continue
        try:
            v = getattr(n, k)
        except AttributeError:
            continue
        vv = value_of(v)
        if vv is not None:
            out[k] = vv
    if getattr(n, 'image', None) is not None:
        out['image'] = image_ref(n.image)
    if n.bl_idname == 'ShaderNodeValToRGB':
        cr = n.color_ramp
        out['ramp'] = {'interpolation': cr.interpolation, 'color_mode': cr.color_mode,
                       'elements': [[e.position, list(e.color)] for e in cr.elements]}
    if n.bl_idname in ('ShaderNodeRGBCurve', 'ShaderNodeVectorCurve', 'ShaderNodeFloatCurve'):
        cm = n.mapping
        cm.initialize()
        out['curves'] = [[cm.evaluate(c, i / 255.0) for i in range(256)] for c in cm.curves]
    if n.bl_idname == 'ShaderNodeTexCoord' and n.object is not None:
        out['object'] = n.object.name
    if n.bl_idname in ('ShaderNodeRGB', 'ShaderNodeValue'):
        out['out'] = value_of(n.outputs[0].default_value)
    return out


def graph(tree, prefix='', group_inputs=None):
    """{'nodes': {name: {type, props, in: {identifier: default}}}, 'links': [[from, out id, to, in id]]}, groups
    flattened, reroutes and muted nodes passed through"""
    nodes, links = {}, []
    for n in tree.nodes:
        if n.bl_idname in ('NodeFrame', 'NodeReroute', 'NodeGroupInput', 'NodeGroupOutput'):
            continue
        name = prefix + n.name
        if n.bl_idname == 'ShaderNodeGroup' and n.node_tree:
            sub = graph(n.node_tree, prefix=name + '/')
            nodes.update(sub['nodes'])
            links.extend(sub['links'])
            continue
        ins = {}
        for s in n.inputs:
            if not s.enabled:
                continue
            if hasattr(s, 'default_value'):
                vv = value_of(s.default_value)
                if vv is not None:
                    ins[s.identifier] = vv
        nodes[name] = {'type': n.bl_idname, 'props': node_props(n), 'in': ins}
        if n.mute:
            nodes[name]['mute'] = [[l.from_socket.identifier, l.to_socket.identifier] for l in n.internal_links]
    for l in tree.links:
        if not l.is_valid or l.is_muted or not l.to_socket.enabled:
            continue
        src = resolve_from(l.from_node, l.from_socket, prefix)
        for dst in resolve_to(l.to_node, l.to_socket, prefix):
            if src and dst:
                links.append([src[0], src[1], dst[0], dst[1]])
    return {'nodes': nodes, 'links': links}


def resolve_from(node, sock, prefix):
    """the real output a link starts from, through reroutes and into groups' outputs"""
    if node.bl_idname == 'NodeReroute':
        ls = node.inputs[0].links
        return resolve_from(ls[0].from_node, ls[0].from_socket, prefix) if ls else None
    if node.bl_idname == 'ShaderNodeGroup' and node.node_tree:
        out = next((x for x in node.node_tree.nodes if x.bl_idname == 'NodeGroupOutput' and x.is_active_output), None)
        if out is None:
            return None
        s = next((x for x in out.inputs if x.identifier == sock.identifier), None)
        if s is None or not s.links:
            return None
        return resolve_from(s.links[0].from_node, s.links[0].from_socket, prefix + node.name + '/')
    if node.bl_idname == 'NodeGroupInput':
        return ('@group_input', sock.identifier) if not prefix else ('@in:' + prefix, sock.identifier)
    return (prefix + node.name, sock.identifier)


def resolve_to(node, sock, prefix):
    if node.bl_idname == 'NodeReroute':
        return [d for l in node.outputs[0].links for d in resolve_to(l.to_node, l.to_socket, prefix)]
    if node.bl_idname == 'ShaderNodeGroup' and node.node_tree:
        gi = [x for x in node.node_tree.nodes if x.bl_idname == 'NodeGroupInput']
        out = []
        for g in gi:
            s = next((x for x in g.outputs if x.identifier == sock.identifier), None)
            if s:
                for l in s.links:
                    out += resolve_to(l.to_node, l.to_socket, prefix + node.name + '/')
        return out
    if node.bl_idname == 'NodeGroupOutput':
        return []
    return [(prefix + node.name, sock.identifier)]


def material_graph(m):
    g = graph(m.node_tree)
    out = m.node_tree.get_output_node('EEVEE') or m.node_tree.get_output_node('ALL')
    g['output'] = out.name if out else None
    g['settings'] = {'blend_method': getattr(m, 'blend_method', 'OPAQUE'),
                     'surface_render_method': getattr(m, 'surface_render_method', 'DITHERED'),
                     'backface_culling': bool(getattr(m, 'use_backface_culling', False)),
                     'use_transparency_overlap': bool(getattr(m, 'use_transparency_overlap', True))}
    return g


# ------------------------------------------------------------------------------------------- pictures out ---

def to_srgb(x):
    x = np.clip(x, 0.0, None)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def encode(arr, fmt, quality=88):
    """an (h, w, c) float 0..1 picture (row 0 at the top) -> JPEG or PNG bytes (OpenImageIO, bundled with Blender)"""
    import tempfile
    import OpenImageIO as oiio
    a = (np.clip(arr, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    h, w, c = a.shape
    fd, tmp = tempfile.mkstemp(suffix='.' + fmt)
    os.close(fd)
    try:
        spec = oiio.ImageSpec(w, h, c, 'uint8')
        if fmt == 'jpg':
            spec.attribute('Compression', f'jpeg:{quality}')
        else:
            spec.attribute('png:compressionLevel', 9)
        o = oiio.ImageOutput.create(tmp)
        o.open(tmp, spec)
        o.write_image(np.ascontiguousarray(a))
        o.close()
        return open(tmp, 'rb').read()
    finally:
        os.remove(tmp)


def save_png(path, px, srgb=False):
    a = px[..., :4] if px.shape[-1] >= 3 else px
    with open(path, 'wb') as f:
        f.write(encode(to_srgb(a) if srgb else a, 'png'))


def read_png(path):
    """a picture as float (h, w, c), row 0 at the top"""
    import OpenImageIO as oiio
    i = oiio.ImageInput.open(path)
    a = i.read_image('float')
    i.close()
    return np.asarray(a, np.float32)


# ------------------------------------------------------------------------------------------- cycles setup ---

def cycles(samples, denoise=False):
    SC.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    dev = 'CPU'
    for kind in ('OPTIX', 'CUDA'):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type == kind]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == kind
                dev = 'GPU'
                break
        except TypeError:
            continue
    SC.cycles.device = dev
    SC.cycles.samples = samples
    SC.cycles.use_denoising = denoise
    SC.cycles.use_adaptive_sampling = False
    SC.render.use_persistent_data = True
    log('cycles', dev, prefs.compute_device_type, samples, 'samples')


# ------------------------------------------------------------------------------------------------ the rest ---

TOUCH_GAP = 0.00025          # metres each touching face is drawn back into its own part


def _overlap(a, b, n, margin=5e-5):
    """do two triangles in one plane (normal n) share area (more than `margin` metres deep)? (separating axes)"""
    u = a[1] - a[0]
    u = u / np.linalg.norm(u)
    v = np.cross(n, u)
    pa, pb = np.c_[a @ u, a @ v], np.c_[b @ u, b @ v]
    for poly in (pa, pb):
        for i in range(3):
            e = poly[(i + 1) % 3] - poly[i]
            ax = np.array([-e[1], e[0]])
            ax = ax / max(np.linalg.norm(ax), 1e-12)
            x, y = pa @ ax, pb @ ax
            if x.max() <= y.min() + margin or y.max() <= x.min() + margin:
                return False
    return True


def separate_touching(items):
    """Two parts that touch face to face (a gasket against its bead, a pane against its gasket) lie in one plane over
    the touch, and three's depth test fights along the edge where one face ends on the other: a serrated line where
    EEVEE's samples average to a clean one. Each face that touches another part's (in one plane, facing it, sharing
    area) is drawn back into its own part by TOUCH_GAP, every copy of its corners with it, so the touch becomes a gap of
    half a millimetre no lens resolves. items: [(object, mesh_arrays)]; their positions are changed in place."""
    tri_part, tri_idx, nrm, off, key = [], [], [], [], []
    world = []
    for pi, (o, arr) in enumerate(items):
        M = np.array(mesh_matrix(o), np.float64).reshape(4, 4).T
        P = arr['verts']['P'].astype(np.float64) @ M[:3, :3].T + M[:3, 3]
        world.append((M, P))
        T = arr['tri'].astype(np.int64)
        a, b, c = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
        n = np.cross(b - a, c - a)
        ar = np.linalg.norm(n, axis=1)
        keep = ar > 1e-10
        n = n[keep] / ar[keep, None]
        big = np.argmax(np.abs(n), axis=1)
        sgn = np.sign(n[np.arange(len(n)), big])
        ns = n * sgn[:, None]
        tri_part.append(np.full(len(n), pi))
        tri_idx.append(np.nonzero(keep)[0])
        nrm.append(n)
        off.append(np.einsum('ij,ij->i', ns, a[keep]))
        key.append(np.round(ns * 1000.0).astype(np.int64))
    if not items:
        return
    tri_part, tri_idx, nrm, off, key = (np.concatenate(x) for x in (tri_part, tri_idx, nrm, off, key))
    _, group = np.unique(key, axis=0, return_inverse=True)
    group = group.ravel()
    touching = {}                                          # part -> {position key: {normal key: unit normal}}
    pairs, same = 0, 0
    order = np.lexsort((off, group))
    g_sorted, o_sorted = group[order], off[order]
    starts = np.r_[0, np.nonzero(np.diff(g_sorted))[0] + 1, len(order)]
    for s0, s1 in zip(starts[:-1], starts[1:]):
        if s1 - s0 < 2:
            continue
        members = order[s0:s1]
        if len(set(tri_part[members].tolist())) < 2:
            continue
        cuts = np.r_[0, np.nonzero(np.diff(o_sorted[s0:s1]) > 5e-5)[0] + 1, s1 - s0]
        for c0, c1 in zip(cuts[:-1], cuts[1:]):
            plane = members[c0:c1]
            if len(plane) < 2 or len(set(tri_part[plane].tolist())) < 2:
                continue
            V = np.stack([world[tri_part[t]][1][items[tri_part[t]][1]['tri'][tri_idx[t]].astype(np.int64)] for t in plane])
            lo, hi = V.min(1) - 5e-5, V.max(1) + 5e-5
            for i in range(len(plane)):
                ti = plane[i]
                js = np.nonzero((tri_part[plane[i + 1:]] != tri_part[ti])
                                & np.all(lo[i + 1:] < hi[i], axis=1) & np.all(hi[i + 1:] > lo[i], axis=1))[0] + i + 1
                for j in js:
                    tj = plane[j]
                    A, B = V[i], V[j]
                    if not _overlap(A, B, nrm[ti]):
                        continue
                    if np.dot(nrm[ti], nrm[tj]) > 0.0:
                        same += 1
                        continue
                    pairs += 1
                    for t, X in ((ti, A), (tj, B)):
                        d = touching.setdefault(int(tri_part[t]), {})
                        nk = tuple(np.round(nrm[t] * 1000.0).astype(int))
                        for p in X:
                            d.setdefault(tuple(np.round(p * 1e5).astype(np.int64)), {})[nk] = nrm[t]
    for pi, d in touching.items():
        M, P = world[pi]
        local = items[pi][1]['verts']['P']
        inv = np.linalg.inv(M[:3, :3])
        pk = np.round(P * 1e5).astype(np.int64)
        index = {}
        for vi, k in enumerate(map(tuple, pk)):
            index.setdefault(k, []).append(vi)
        for k, normals in d.items():
            step = inv @ (-TOUCH_GAP * np.sum(list(normals.values()), axis=0))
            for vi in index.get(k, ()):
                local[vi] = local[vi] + step.astype(np.float32)
        log('rest', f'{items[pi][0].name}: {len(d)} corners drawn back from the parts it touches')
    log('rest', f'{pairs} face pairs touching across parts drawn {TOUCH_GAP * 2e3:.1f} mm apart'
        + (f'; {same} pairs in one plane facing the same way, left as they are' if same else ''))


def step_rest():
    g = GLB('eidoverse/assets/sets/same_seed_src/export_room.py')
    mats, matidx = {}, {}

    def mat_index(m, cc0=None):
        if m is None:
            return None
        if cc0 is not None and own_material(m, cc0[2]):            # a CC0 model's own material: read from the model
            key = ('cc0', cc0[0], strip_suffix(m.name))
            if key not in matidx:
                matidx[key] = g.material({'name': strip_suffix(m.name),
                                          'extras': {'cc0': {'id': cc0[0], 'res': cc0[1], 'material': strip_suffix(m.name)},
                                                     'override': cc0_override(m)}})
            return matidx[key]
        if m.name not in matidx:
            matidx[m.name] = g.material({'name': m.name, 'extras': {'graph': m.name}})
            mats[m.name] = material_graph(m)
        return matidx[m.name]

    parts, todo = [], []
    for o in sorted(OBJS, key=lambda o: o.name):
        if KIND.get(o.name, ('', ''))[0] != 'rest':
            continue
        if o.hide_render:
            continue
        cc0 = CC0_OF.get(o.name)
        slots = [s.material for s in o.material_slots]
        tuvs = normal_map_uvs(slots)
        orco = any(n.bl_idname == 'ShaderNodeTexCoord' and any(l.from_socket.name == 'Generated' for l in m.node_tree.links if l.from_node == n)
                   for m in slots if m and m.node_tree for n in m.node_tree.nodes)
        arr = mesh_arrays(o, tangent_uvs=tuvs, orco=orco, attrs=attribute_names(slots))
        if arr is not None:
            todo.append((o, slots, cc0, arr))
    separate_touching([(o, arr) for o, _, _, arr in todo])
    for o, slots, cc0, arr in todo:
        first_uv = o.data.uv_layers[0].name if len(o.data.uv_layers) else None
        prims = glb_prims(g, arr, lambda i: mat_index(slots[i], cc0) if i < len(slots) else None, texcoord0=first_uv)
        has_uv0 = bool(first_uv) and ('UV:' + first_uv) in arr['verts']
        mesh = g.mesh(o.data.name, prims, extras={'uv0': first_uv} if has_uv0 else None)
        extras = {'cc0': {'id': cc0[0], 'res': cc0[1]}} if cc0 else {}
        if not o.visible_camera:
            extras['camera'] = False
        if not o.visible_shadow:
            extras['shadow'] = False
        g.node(o.name, mesh=mesh, matrix=mesh_matrix(o), extras=extras or None)
        parts.append(o.name)
    path = os.path.join(A.models, f'same_seed_{ROOM}_rest.glb')
    n = g.write(path)
    w = bpy.data.worlds.get(getattr(RM, 'WORLD', '') or '') or SC.world
    out = {'materials': mats, 'world': material_graph(w) if w and w.node_tree else None,
           'images': IMAGES}
    with open(os.path.join(A.out, 'materials.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, separators=(',', ':'))
    log('rest', len(parts), 'parts,', len(mats), 'materials,', f'{n / 1e6:.2f} MB', path)
    return parts


# ------------------------------------------------------------------------------------------------ the lows ---

PASSES = ('base', 'rough', 'metal', 'emit', 'alpha')


def principled(m):
    out = m.node_tree.get_output_node('EEVEE') or m.node_tree.get_output_node('ALL')
    if not out or not out.inputs['Surface'].is_linked:
        return None, out
    n = out.inputs['Surface'].links[0].from_node
    return (n if n.bl_idname == 'ShaderNodeBsdfPrincipled' else None), out


def constant(m, sock):
    """the value of a Principled input when it is not linked, else None"""
    p, _ = principled(m)
    if p is None:
        return None
    s = p.inputs[sock]
    return None if s.is_linked else value_of(s.default_value)


def bake_pass(objs, mats, img, kind):
    """one Cycles bake of every material on `objs` into img: 'normal' (tangent space) or a Principled input through an
    emission swap"""
    saved = []
    for m in mats:
        nt = m.node_tree
        tn = nt.nodes.new('ShaderNodeTexImage')
        tn.image = img
        nt.nodes.active = tn
        rec = {'m': m, 'tn': tn}
        if kind != 'normal':
            p, out = principled(m)
            surf = out.inputs['Surface']
            rec['old'] = surf.links[0].from_socket if surf.is_linked else None
            em = nt.nodes.new('ShaderNodeEmission')
            rec['em'] = em
            em.inputs['Strength'].default_value = 1.0
            src = None
            if p is not None:
                key = {'base': 'Base Color', 'rough': 'Roughness', 'metal': 'Metallic', 'alpha': 'Alpha',
                       'emit': 'Emission Color'}[kind]
                s = p.inputs[key]
                if s.is_linked:
                    src = s.links[0].from_socket
                else:
                    v = s.default_value
                    em.inputs['Color'].default_value = (tuple(v)[:3] + (1.0,)) if hasattr(v, '__len__') else (v, v, v, 1.0)
                if kind == 'emit':
                    es = p.inputs['Emission Strength']
                    if es.is_linked:
                        nt.links.new(es.links[0].from_socket, em.inputs['Strength'])
                    else:
                        em.inputs['Strength'].default_value = es.default_value
            else:
                em.inputs['Color'].default_value = (0.5, 0.5, 0.5, 1.0) if kind == 'base' else ((0.5,) * 3 + (1,) if kind == 'rough' else (0, 0, 0, 1))
                if kind == 'alpha':
                    em.inputs['Color'].default_value = (1, 1, 1, 1)
            if src is not None:
                nt.links.new(src, em.inputs['Color'])
            nt.links.new(em.outputs[0], surf)
        saved.append(rec)
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
        o.data.uv_layers.active = o.data.uv_layers['atlas']
    render_uv = {}
    if kind == 'normal':                                        # (a normal bake's tangents come from the render UV)
        for o in objs:
            render_uv[o] = next((u.name for u in o.data.uv_layers if u.active_render), None)
            o.data.uv_layers['atlas'].active_render = True
    bpy.context.view_layer.objects.active = objs[0]
    bk = SC.render.bake
    bk.margin, bk.margin_type, bk.use_clear, bk.target = 16, 'EXTEND', True, 'IMAGE_TEXTURES'
    # (these passes see no light: only the atlas's parts are synced, so the rest of the room's pictures are not loaded)
    keep = set(objs)
    hidden = [(o, o.hide_render) for o in SC.objects if o not in keep]
    for o, _ in hidden:
        o.hide_render = True
    try:
        if kind == 'normal':
            bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', normal_r='POS_X', normal_g='POS_Y', normal_b='POS_Z',
                                margin=16, use_clear=True)
        else:
            bpy.ops.object.bake(type='EMIT', margin=16, use_clear=True)
    finally:
        for o, h in hidden:
            o.hide_render = h
        for o, n in render_uv.items():
            if n:
                o.data.uv_layers[n].active_render = True
    for rec in saved:
        nt = rec['m'].node_tree
        if 'em' in rec:
            p, out = principled(rec['m'])
            if rec['old'] is not None:
                nt.links.new(rec['old'], out.inputs['Surface'])
            nt.nodes.remove(rec['em'])
        nt.nodes.remove(rec['tn'])
    a = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(img.size[1], img.size[0], 4)[::-1]          # row 0 at the top


def atlas_size(name):
    p = os.path.join(BAKE_DIR, 'atlases.json')
    if os.path.isfile(p):
        for a in json.load(open(p, encoding='utf-8')):
            if a['name'] == name:
                return int(a['size'])
    for suffix in ('_normal.png', '_masks_a.png', '_ao.png'):
        f = os.path.join(BAKE_DIR, name + suffix)
        if os.path.isfile(f):
            return read_png(f).shape[1]
    return 2048


def ao_map(name, size):
    for suffix, ch in (('_masks_a.png', 0), ('_ao.png', 0)):
        f = os.path.join(BAKE_DIR, name + suffix)
        if os.path.isfile(f):
            a = read_png(f)
            a = a[..., ch] if a.ndim == 3 else a
            if a.shape[0] != size:
                ys = (np.arange(size) * a.shape[0] / size).astype(int)
                a = a[ys][:, ys]
            return a
    return np.ones((size, size), np.float32)


def step_lows():
    atlases = {}
    for o in OBJS:
        k = KIND.get(o.name)
        if k and k[0] == 'low' and not o.hide_render:
            atlases.setdefault(k[1], []).append(o)
    cycles(A.bake_samples)
    SC.cycles.bake_type = 'EMIT'
    rows = {}
    for name, objs in sorted(atlases.items()):
        size = min(atlas_size(name), A.max_size)
        mats = sorted({s.material for o in objs for s in o.material_slots if s.material}, key=lambda m: m.name)
        img = bpy.data.images.new(f'bake_{name}', size, size, alpha=True, float_buffer=True)
        img.colorspace_settings.name = 'Non-Color'
        t = time.time()
        maps = {'normal': bake_pass(objs, mats, img, 'normal')}
        for kind in ('base', 'rough', 'metal'):
            maps[kind] = bake_pass(objs, mats, img, kind)
        glow = [m for m in mats if (constant(m, 'Emission Strength') or 0.0) > 0.0 or
                (principled(m)[0] is not None and principled(m)[0].inputs['Emission Strength'].is_linked)]
        if glow:
            maps['emit'] = bake_pass(objs, mats, img, 'emit')
        cut = [m for m in mats if principled(m)[0] is not None and (principled(m)[0].inputs['Alpha'].is_linked or
                                                                    (constant(m, 'Alpha') or 1.0) < 0.999)]
        if cut:
            maps['alpha'] = bake_pass(objs, mats, img, 'alpha')
        bpy.data.images.remove(img)
        log('lows', name, size, f'{len(objs)} parts, {len(mats)} materials, baked in {time.time() - t:.1f} s')
        rows[name] = write_atlas(name, size, objs, mats, maps)
    return rows


def write_atlas(name, size, objs, mats, maps):
    g = GLB('eidoverse/assets/sets/same_seed_src/export_room.py')
    q = A.quality
    base = to_srgb(maps['base'][..., :3])
    if 'alpha' in maps:
        base = np.concatenate([base, maps['alpha'][..., :1]], 2)
    ao = ao_map(name, size)[..., None]
    orm = np.concatenate([ao, maps['rough'][..., :1], maps['metal'][..., :1]], 2)
    nrm = maps['normal'][..., :3]
    imgs = {'base': g.image(encode(base, 'png' if 'alpha' in maps else 'jpg', q), 'image/png' if 'alpha' in maps else 'image/jpeg', f'{name}_base'),
            'orm': g.image(encode(orm, 'jpg', q), 'image/jpeg', f'{name}_orm'),
            'normal': g.image(encode(nrm, 'jpg', min(95, q + 6)), 'image/jpeg', f'{name}_normal')}
    emit_k = 0.0
    if 'emit' in maps:
        e = maps['emit'][..., :3]
        emit_k = float(max(1e-6, e.max()))
        imgs['emit'] = g.image(encode(to_srgb(e / emit_k), 'jpg', q), 'image/jpeg', f'{name}_emit')
    tex = {k: g.texture(v) for k, v in imgs.items()}
    matidx = {}
    for m in mats:
        md = {'name': m.name,
              'pbrMetallicRoughness': {'baseColorTexture': {'index': tex['base']}, 'metallicRoughnessTexture': {'index': tex['orm']},
                                       'metallicFactor': 1.0, 'roughnessFactor': 1.0},
              'occlusionTexture': {'index': tex['orm']}, 'normalTexture': {'index': tex['normal']}}
        ext, extras = {}, {}
        if 'emit' in tex and ((constant(m, 'Emission Strength') or 0.0) > 0.0 or principled(m)[0] is not None and principled(m)[0].inputs['Emission Strength'].is_linked):
            md['emissiveTexture'] = {'index': tex['emit']}
            md['emissiveFactor'] = [1.0, 1.0, 1.0]
            ext['KHR_materials_emissive_strength'] = {'emissiveStrength': emit_k}
        if 'alpha' in maps and (principled(m)[0] is not None and (principled(m)[0].inputs['Alpha'].is_linked or (constant(m, 'Alpha') or 1.0) < 0.999)):
            md['alphaMode'] = 'BLEND' if getattr(m, 'surface_render_method', 'DITHERED') == 'BLENDED' else 'MASK'
            if md['alphaMode'] == 'MASK':
                md['alphaCutoff'] = 0.5
        cw = constant(m, 'Coat Weight') or 0.0
        if cw > 0.0:
            ext['KHR_materials_clearcoat'] = {'clearcoatFactor': cw, 'clearcoatRoughnessFactor': constant(m, 'Coat Roughness') or 0.0}
        tw = constant(m, 'Transmission Weight') or 0.0
        if tw > 0.0:
            ext['KHR_materials_transmission'] = {'transmissionFactor': tw}
            ext['KHR_materials_ior'] = {'ior': constant(m, 'IOR') or 1.5}
        for e in ext:
            g.use(e)
        if ext:
            md['extensions'] = ext
        extras['blender'] = m.name
        if m.use_backface_culling:
            extras['backfaceCulling'] = True
        else:
            md['doubleSided'] = True
        md['extras'] = extras
        matidx[m.name] = g.material(md)
    for o in sorted(objs, key=lambda o: o.name):
        slots = [s.material for s in o.material_slots]
        arr = mesh_arrays(o, tangent_uvs=('atlas',))
        if arr is None:
            continue
        prims = glb_prims(g, arr, lambda i: matidx.get(slots[i].name) if i < len(slots) and slots[i] else None,
                          uv_names_for_custom=False, texcoord0='atlas', tangent0='atlas')
        extras = {'camera': False} if not o.visible_camera else None
        g.node(o.name, mesh=g.mesh(o.data.name, prims), matrix=mesh_matrix(o), extras=extras)
    path = os.path.join(A.models, f'same_seed_{ROOM}_{name}.glb')
    n = g.write(path)
    log('lows', name, f'{n / 1e6:.2f} MB', path)
    return {'file': os.path.basename(path), 'size': size, 'parts': len(objs), 'bytes': n}


# ---------------------------------------------------------------------------------------------- the light ---

def light_rows():
    rows = []
    for o in OBJS:
        if o.type != 'LIGHT' or o.hide_render:
            continue
        L = o.data
        M = CI @ o.matrix_world
        pos = [M[0][3], M[1][3], M[2][3]]
        fwd = (M.to_3x3() @ Vector((0, 0, -1))).normalized()
        up = (M.to_3x3() @ Vector((0, 1, 0))).normalized()
        r = {'name': o.name, 'color': list(L.color), 'shadow': bool(L.use_shadow), 'position': pos,
             'direction': list(fwd), 'up': list(up), 'matrix': colmajor(M), 'blender': {'type': L.type, 'energy': L.energy}}
        if L.diffuse_factor != 1.0 or L.specular_factor != 1.0:
            r['factors'] = {'diffuse': L.diffuse_factor, 'specular': L.specular_factor}
        if L.type != 'SUN':
            # EEVEE ends a light's reach where its power falls under the scene's light threshold (its custom distance
            # when set), with Frostbite's window (1 - (d / r)^4)^2: the room's fill lights were set under that reach
            if getattr(L, 'use_custom_distance', False):
                r['influence'] = float(L.cutoff_distance)
            else:
                power = max(L.color) * abs(L.energy / 100.0) * max(L.diffuse_factor, L.specular_factor)
                r['influence'] = math.sqrt(power / max(1e-6, SC.eevee.light_threshold))
        if L.type == 'SUN':
            r.update({'type': 'directional', 'intensity': L.energy, 'angle': L.angle})
        elif L.type == 'AREA':
            w = L.size
            h = L.size_y if L.shape in ('RECTANGLE', 'ELLIPSE') else L.size
            if L.shape in ('DISK', 'ELLIPSE'):
                w, h = w * math.sqrt(math.pi) / 2.0, h * math.sqrt(math.pi) / 2.0     # (a rectangle of the same area)
            r.update({'type': 'rectArea', 'width': w, 'height': h, 'intensity': L.energy / (math.pi * w * h),
                      'spread': getattr(L, 'spread', math.pi)})
        elif L.type == 'SPOT':
            r.update({'type': 'spot', 'intensity': L.energy / (4.0 * math.pi), 'angle': L.spot_size / 2.0,
                      'penumbra': L.spot_blend, 'radius': L.shadow_soft_size})
        else:
            r.update({'type': 'point', 'intensity': L.energy / (4.0 * math.pi), 'radius': L.shadow_soft_size})
        rows.append(r)
    return rows


def as_probe_rays():
    """the world and materials as a probe's rays see them: every Light Path 'Is Camera Ray' read as 0 (the panoramas
    are camera rays to Cycles; EEVEE's probes are not); -> undo"""
    made = []
    trees = [m.node_tree for m in bpy.data.materials if m.use_nodes and m.node_tree]
    trees += [w.node_tree for w in bpy.data.worlds if w.use_nodes and w.node_tree]
    for nt in trees:
        for n in list(nt.nodes):
            if n.bl_idname != 'ShaderNodeLightPath':
                continue
            links = [l for l in nt.links if l.from_node == n and l.from_socket.name == 'Is Camera Ray']
            if not links:
                continue
            zero = nt.nodes.new('ShaderNodeValue')
            zero.outputs[0].default_value = 0.0
            for l in links:
                to = l.to_socket
                nt.links.remove(l)
                nt.links.new(zero.outputs[0], to)
                made.append((nt, n, zero, to))

    def undo():
        for nt, n, zero, to in made:
            for l in list(nt.links):
                if l.from_node == zero:
                    nt.links.remove(l)
            nt.links.new(n.outputs['Is Camera Ray'], to)
            if zero.name in nt.nodes:
                nt.nodes.remove(zero)
    return undo


def capture_visibility(kind):
    """objects as a probe sees them (kind 'volume' / 'sphere'): lamps unseen, the parts a probe hides hidden; -> undo"""
    saved = []
    for o in SC.objects:
        if not hasattr(o, 'visible_camera'):
            continue
        saved.append((o, o.visible_camera))
        if o.type == 'LIGHT':
            o.visible_camera = False
        elif o.type == 'MESH':
            hide = getattr(o, 'hide_probe_volume' if kind == 'volume' else 'hide_probe_sphere', False)
            o.visible_camera = not hide
    return lambda: [setattr(o, 'visible_camera', v) for o, v in saved]


def pano_camera():
    cd = bpy.data.cameras.new('export_pano')
    cd.type = 'PANO'
    cd.panorama_type = 'EQUIRECTANGULAR'
    cd.clip_start = 0.01
    cam = bpy.data.objects.new('export_pano', cd)
    SC.collection.objects.link(cam)
    cam.rotation_euler = Vector((1.0, 0.0, 0.0)).to_track_quat('-Z', 'Z').to_euler()   # (Blender's world equirect: +X in the middle, +Z up)
    SC.camera = cam
    return cam


def render_pano(cam, at, w, h, path):
    cam.location = at
    SC.render.resolution_x, SC.render.resolution_y, SC.render.resolution_percentage = w, h, 100
    SC.render.image_settings.file_format = 'OPEN_EXR'
    SC.render.image_settings.color_depth = '32'
    SC.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return read_png(path)[..., :3]                    # (OpenImageIO reads EXR too; row 0 at the top)


def sh9_of(pano):
    """L2 spherical harmonics of a Blender-convention equirect (row 0 at the top), three's basis and frame"""
    h, w, _ = pano.shape
    v = 1.0 - (np.arange(h) + 0.5) / h
    u = (np.arange(w) + 0.5) / w
    lat = (v - 0.5) * math.pi
    lon = (u - 0.5) * 2.0 * math.pi
    cl, sl = np.cos(lat)[:, None], np.sin(lat)[:, None]
    bx, by, bz = cl * np.cos(lon)[None, :], -cl * np.sin(lon)[None, :], sl * np.ones((1, w))
    x, y, z = bx, bz, -by                             # three's frame
    dw = (2.0 * math.pi / w) * (math.pi / h) * cl * np.ones((1, w))
    basis = [0.282095 * np.ones_like(x), 0.488603 * y, 0.488603 * z, 0.488603 * x, 1.092548 * x * y, 1.092548 * y * z,
             0.315392 * (3.0 * z * z - 1.0), 1.092548 * x * z, 0.546274 * (x * x - y * y)]
    return [[float((pano[..., c] * b * dw).sum()) for c in range(3)] for b in basis]


RAYS = [Vector(d).normalized() for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1),
                                         (1, 1, 1), (1, 1, -1), (1, -1, 1), (1, -1, -1), (-1, 1, 1), (-1, 1, -1),
                                         (-1, -1, 1), (-1, -1, -1))]


def inside_solid(p):
    """a point no probe should stand at: inside a solid part (half of 14 rays hit a back face first) or shut in a
    pocket (most of them hit something within 0.3 m: above a wall cupboard, behind a radiator); its cell is filled
    from its neighbours, as EEVEE leaves out the samples its validity rejects"""
    back = near = 0
    for d in RAYS:
        hit, loc, nrm, idx, ob, mat = SC.ray_cast(DG, Vector(p), d, distance=50.0)
        if hit and Vector(nrm).dot(d) > 0.0:
            back += 1
        if hit and (Vector(loc) - Vector(p)).length < 0.3:
            near += 1
    return back >= 7 or near >= 9


def step_light():
    rows = {'lights': light_rows()}
    probes = [o for o in OBJS if o.type == 'LIGHT_PROBE']
    vol = next((o for o in probes if o.data.type == 'VOLUME'), None)
    sph = next((o for o in probes if o.data.type == 'SPHERE'), None)
    tmp = os.path.join(A.out, '_tmp')
    os.makedirs(tmp, exist_ok=True)
    rays_undo = as_probe_rays()
    try:
        if vol is not None:
            # (the world is captured too, through the room's openings: EEVEE relights its volume probes from the
            #  world by a visibility it bakes, which this grid of Cycles' own bounce stands in for)
            cycles(A.grid_samples)
            SC.cycles.diffuse_bounces = A.grid_bounces
            SC.view_settings.view_transform = 'Standard'
            SC.view_settings.exposure = 0.0
            SC.view_settings.look = 'None'
            undo = capture_visibility('volume')
            cam = pano_camera()
            s = A.grid_scale
            nx, ny, nz = (max(2, round(r * s)) for r in (vol.data.resolution_x, vol.data.resolution_y, vol.data.resolution_z))
            k = 1.0
            while nx * ny * nz / (k ** 3) > A.grid_max:
                k += 0.25
            nx, ny, nz = max(2, round(nx / k)), max(2, round(ny / k)), max(2, round(nz / k))
            M = vol.matrix_world
            # three's grid: x = Blender x, y = Blender z, z = -Blender y; cell centres, x fastest, then y, then z
            tx, ty, tz = nx, nz, ny
            coeffs, valid = [], []
            t = time.time()
            for kz in range(tz):
                for ky in range(ty):
                    for kx in range(tx):
                        ix, iy, iz = kx, tz - 1 - kz, ky
                        p = M @ Vector(((ix + 0.5) / nx * 2 - 1, (iy + 0.5) / ny * 2 - 1, (iz + 0.5) / nz * 2 - 1))
                        if inside_solid(p):
                            coeffs.append(None)
                            valid.append(False)
                            continue
                        pano = render_pano(cam, p, A.grid_res, A.grid_res // 2, os.path.join(tmp, 'probe.exr'))
                        coeffs.append(sh9_of(pano))
                        valid.append(True)
            log('light', f'{nx} x {ny} x {nz} bounce probes in {time.time() - t:.1f} s ({sum(valid)} outside solids)')
            fill_invalid(coeffs, valid, tx, ty, tz)
            lo3, hi3 = v3(M @ Vector((-1, -1, -1))), v3(M @ Vector((1, 1, 1)))
            rows['grid'] = {'res': [tx, ty, tz], 'min': [min(a, b) for a, b in zip(lo3, hi3)],
                            'max': [max(a, b) for a, b in zip(lo3, hi3)],
                            'about': "L2 spherical harmonics of the radiance at each cell's centre (three's basis and "
                                     'frame), x fastest, then y, then z; the volume probe\'s box', 'sh': coeffs,
                            'blender_res': [vol.data.resolution_x, vol.data.resolution_y, vol.data.resolution_z]}
            undo()
            bpy.data.objects.remove(cam, do_unlink=True)
        if sph is not None:
            w, h = (int(x) for x in A.reflection.lower().split('x'))
            cycles(128, denoise=True)
            SC.view_settings.view_transform = 'Standard'
            undo = capture_visibility('sphere')
            cam = pano_camera()
            pano = render_pano(cam, sph.matrix_world.translation, w, h, os.path.join(tmp, 'reflection.exr'))
            write_hdr(os.path.join(A.out, 'reflection.hdr'), pano)
            undo()
            bpy.data.objects.remove(cam, do_unlink=True)
            rows['reflection'] = {'file': 'reflection.hdr', 'position': v3(sph.matrix_world.translation),
                                  'influence': sph.data.influence_distance, 'sh': sh9_of(pano)}
    finally:
        rays_undo()
        shutil.rmtree(tmp, ignore_errors=True)
    return rows


def fill_invalid(coeffs, valid, nx, ny, nz):
    """a probe inside a solid takes the mean of its valid neighbours (repeated until every probe has a value)"""
    def idx(x, y, z):
        return (z * ny + y) * nx + x
    for _ in range(nx + ny + nz):
        todo = [i for i, c in enumerate(coeffs) if c is None]
        if not todo:
            return
        for i in todo:
            z, r = divmod(i, nx * ny)
            y, x = divmod(r, nx)
            nb = [coeffs[idx(x + dx, y + dy, z + dz)] for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
                  if 0 <= x + dx < nx and 0 <= y + dy < ny and 0 <= z + dz < nz and coeffs[idx(x + dx, y + dy, z + dz)] is not None]
            if nb:
                coeffs[i] = [[sum(n[b][c] for n in nb) / len(nb) for c in range(3)] for b in range(9)]
    for i, c in enumerate(coeffs):
        if c is None:
            coeffs[i] = [[0.0, 0.0, 0.0] for _ in range(9)]


def write_hdr(path, rgb):
    """Radiance RGBE, flat (no run-length), row 0 at the top"""
    h, w, _ = rgb.shape
    a = np.maximum(rgb.astype(np.float64), 0.0)
    m = a.max(axis=2)
    e = np.zeros_like(m, dtype=np.int32)
    mant = np.zeros_like(m)
    nz = m > 1e-32
    mant[nz], e[nz] = np.frexp(m[nz])
    scale = np.zeros_like(m)
    scale[nz] = mant[nz] * 256.0 / m[nz]
    out = np.zeros((h, w, 4), np.uint8)
    for c in range(3):
        out[..., c] = np.clip(a[..., c] * scale, 0, 255).astype(np.uint8)
    out[..., 3] = np.where(nz, e + 128, 0).astype(np.uint8)
    with open(path, 'wb') as f:
        f.write(b'#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n')
        f.write(f'-Y {h} +X {w}\n'.encode('ascii'))
        f.write(out.tobytes())


# ------------------------------------------------------------------------------------------------ the rest of it ---

def cc0_override(m):
    """what the look changed on a CC0 material that this edition must change too: its emission (a lamp lit, another
    put out), as {'emissive': rgb or None (its texture kept), 'emissiveIntensity'}; None when it emits nothing"""
    if not (m and m.node_tree):
        return None
    p, _ = principled(m)
    if p is None:
        e = next((n for n in m.node_tree.nodes if n.type == 'EMISSION'), None)
        return {'emissive': None, 'emissiveIntensity': float(e.inputs['Strength'].default_value)} if e else None
    es, ec = p.inputs['Emission Strength'], p.inputs['Emission Color']
    if es.is_linked:
        return None
    col = None if ec.is_linked else list(ec.default_value)[:3]
    if es.default_value <= 0.0 or (col is not None and max(col) <= 0.0):
        return {'emissive': [0.0, 0.0, 0.0], 'emissiveIntensity': 0.0}
    return {'emissive': col, 'emissiveIntensity': float(es.default_value)}


def model_rows():
    rows = []
    over = {}
    for o in sorted(OBJS, key=lambda o: o.name):
        k = KIND.get(o.name)
        if not k or k[0] != 'model' or o.hide_render:
            continue
        mid, res, mesh = k[1]
        rows.append({'name': o.name, 'id': mid, 'res': res, 'mesh': mesh, 'matrix': mesh_matrix(o),
                     'camera': bool(o.visible_camera), 'shadow': bool(o.visible_shadow)})
        for s in o.material_slots:
            m = s.material
            if m and strip_suffix(m.name) not in over:
                over[strip_suffix(m.name)] = cc0_override(m)
    return rows, {k: v for k, v in over.items() if v is not None}


def cams_rows():
    out = {}
    for name, (pos, aim, lens) in RM.CAMS.items():
        out[name] = {'position': v3(pos), 'target': v3(aim), 'lens': lens, 'sensor': 36.0}
    return out


AXIS_TO_THREE = {'+x': '+x', '-x': '-x', '+y': '-z', '-y': '+z', '+z': '+y', '-z': '-y'}


def marks_rows():
    """the marks in three's frame: yaw about +Y in radians (0 faces +Z, Blender's -y), and a description's 'facing -y'
    said in three's axes"""
    out = {}
    for name, m in RM.MARKS.items():
        r = {'position': v3(m['pos'])}
        if 'yaw' in m:
            r['yaw'] = math.radians(m['yaw'])
        if 'size' in m:
            r['size'] = list(m['size'])
        if 'about' in m:
            r['about'] = re.sub(r'\bfacing ([+-]?)([xyz])\b',
                                lambda g: 'facing ' + AXIS_TO_THREE[(g.group(1) or '+') + g.group(2)], m['about'])
        out[name] = r
    return out


def step_meta(extra):
    room = {'room': ROOM, 'film': 'SAME SEED', 'about': RM.ABOUT, 'space': 'metres, +Y up (three); Blender (x, y, z) -> (x, z, -y)',
            'cameras': cams_rows(), 'marks': marks_rows(),
            'render': {'exposure': float(RM.RENDER.get('exposure', 0.0)), 'view': 'AgX', 'blender': RM.RENDER},
            'look': getattr(RM, 'LOOK', {})}
    room.update(extra)
    p = os.path.join(A.out, 'room.json')
    old = json.load(open(p, encoding='utf-8')) if os.path.isfile(p) else {}
    old.update(room)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(old, f, indent=1)
    log('meta', p)


steps = set(A.steps.split(','))
extra = {}
if 'rest' in steps:
    extra['rest'] = {'file': f'same_seed_{ROOM}_rest.glb', 'parts': step_rest()}
if 'lows' in steps:
    extra['lows'] = step_lows()
if 'meta' in steps:
    rows, over = model_rows()
    extra['models'] = rows
    extra['model_overrides'] = over
if 'light' in steps:
    extra.update(step_light())
step_meta(extra)
log('done')
