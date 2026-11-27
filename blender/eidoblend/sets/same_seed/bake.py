"""eidoblend.sets.same_seed.bake: a room's atlases written for the GPU baker (Blender), through the hard-surface kit's
exporter (eidoblend.props.hardsurface.bake_export), then baked by blender/tools/gpu_bake.py outside Blender.

    from eidoblend.sets.same_seed import bake
    bake.export_atlas('door', lows, claims, '<out>/bake', size=2048, occluders=[wall, floor],
                      cages={'door_leaf_low': (1.5, 4.6)}, ao_mm=200.0)
    # then: python blender/tools/gpu_bake.py --bake <out>/bake --name door --ao 96 --cav 48

A room's part is either built as one mass with one bevel (its low is the same construction without the bevel) or drawn
twice, a high and a low (the sealed room's bench). Either way a low CLAIMS the highs it bakes from: its own high, and
for a drawn part the welds or beads that lie on it, so a weld bakes into both pieces it joins. A texel's ray meets
only the highs its low claims. What the kit's exporter is given, per low:
  * the high: the claimed object itself (its modifiers live: the bevel as it renders), or the claimed highs joined,
    as they render, in the room's space;
  * the low: a copy in the room's space (a low may carry a transform), its UV 'atlas', triangulated;
  * the arrises: the LOW's own hard edges (past 30 degrees, convex and concave), where wear and grime are measured
    from, on every kind of part alike.
The bake's settings travel in <atlas>.json: the AO reach, the cavity reach (CAV_MM), the arris and corner ranges
(look.ARRIS_MM, look.CORNER_MM) and each part's cage (mm out from the low, mm reach in).
"""

from __future__ import annotations

import json
import math
import os

import bpy
import numpy as np

from ...props.hardsurface import bake_export
from .look import ARRIS_MM, CORNER_MM, log

CAV_MM = 6.0
ARRIS_STEP_MM = 1.0
SHARP_DEG = 30.0


def _identity(M):
    return all(abs(M[i][j] - (1.0 if i == j else 0.0)) < 1e-9 for i in range(4) for j in range(4))


def _evaluated_copy(o, name, coll):
    """a new object holding o as it renders (modifiers applied), with o's transform"""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    t = bpy.data.objects.new(name, me)
    t.matrix_world = o.matrix_world.copy()
    coll.objects.link(t)
    return t


def _joined(name, highs, coll):
    """one object holding every high as it renders, in the room's space"""
    parts = [_evaluated_copy(h, f'{name}~{i}', coll) for i, h in enumerate(highs)]
    with bpy.context.temp_override(active_object=parts[0], selected_editable_objects=parts, object=parts[0]):
        bpy.ops.object.join()
    parts[0].name = name
    return parts[0]


def _world_low(o, name, coll):
    """the low as a new object at identity: its mesh in the room's space (normals and UVs kept)"""
    me = o.data.copy()
    t = bpy.data.objects.new(name, me)
    coll.objects.link(t)
    if not _identity(o.matrix_world):
        me.transform(o.matrix_world)
        if o.matrix_world.determinant() < 0:
            me.flip_normals()
        me.update()
    return t


def export_atlas(atlas, lows, claims, bake_dir, size, occluders=(), cages=None, ao_mm=150.0, cav_mm=CAV_MM,
                 substrate=None, uv_name='atlas'):
    """Write <atlas>_high.npz, <atlas>_low.npz and <atlas>.json into bake_dir for gpu_bake.py. lows: the low objects
    (each with UV uv_name, triangulated); claims: {low name: [high object names]}; occluders: objects that cast AO on the
    atlas and are not baked; cages: {low name: (cage_mm, reach_mm)} (else the baker measures them); ao_mm: the AO reach.
    Returns the exporter's record (names, texel density, triangle counts)."""
    os.makedirs(bake_dir, exist_ok=True)
    lows = sorted(lows, key=lambda o: o.name)
    names = [o.name for o in lows]
    tmp = bpy.data.collections.new(f'bake_{atlas}_tmp')
    bpy.context.scene.collection.children.link(tmp)
    real = {}
    try:
        for o in lows:                                         # the lows step aside: the bake's parts take their names
            real[o.name] = o
            o.name = o.name + '~real'
        highs = []
        for n in names:
            hs = [bpy.data.objects[h] for h in claims[n]]
            if len(hs) == 1 and hs[0].modifiers:
                t = hs[0].copy()                               # its mesh and its modifiers: the bevel as it renders
                t.name = n
                tmp.objects.link(t)
            elif len(hs) == 1:
                t = _evaluated_copy(hs[0], n, tmp)
            else:
                t = _joined(n, hs, tmp)
            highs.append(t)
        bpy.context.view_layer.update()
        bake_export.write_high(highs, bake_dir, atlas, arris_mm=ARRIS_STEP_MM, sharp_deg=SHARP_DEG,
                               occluders=list(occluders), log=lambda *a: log('bake', *a))
        for t in highs:
            bpy.data.objects.remove(t, do_unlink=True)
        wl = [_world_low(real[n], n, tmp) for n in names]
        bpy.context.view_layer.update()
        cages = cages or {}
        opts = {'ao_mm': float(ao_mm), 'cav_mm': float(cav_mm), 'edge_mm': ARRIS_MM, 'corner_mm': CORNER_MM,
                'cage_mm': {n: float(c[0]) for n, c in cages.items() if n in names},
                'reach_mm': {n: float(c[1]) for n, c in cages.items() if n in names}}
        meta = bake_export.write_low(wl, bake_dir, atlas, size=size, substrate=substrate, uv_name=uv_name,
                                     options=opts, log=lambda *a: log('bake', *a))
        # the arrises from the lows' own hard edges (see the module doc)
        ar_p, ar_n, ar_part, cc_p, cc_part = [], [], [], [], []
        for pi, t in enumerate(wl):
            cp, cn, kp = bake_export._edge_samples(t, ARRIS_STEP_MM * 1e-3, SHARP_DEG)
            ar_p += cp
            ar_n += cn
            ar_part += [pi] * len(cp)
            cc_p += kp
            cc_part += [pi] * len(kp)
        hz = os.path.join(bake_dir, f'{atlas}_high.npz')
        H = dict(np.load(hz))
        H.update(ar_p=np.array(ar_p, np.float32).reshape(-1, 3), ar_n=np.array(ar_n, np.float16).reshape(-1, 3),
                 ar_part=np.array(ar_part, np.int32), cc_p=np.array(cc_p, np.float32).reshape(-1, 3),
                 cc_part=np.array(cc_part, np.int32))
        np.savez_compressed(hz, **H)
        for t in wl:
            bpy.data.objects.remove(t, do_unlink=True)
        meta['arris_samples'], meta['corner_samples'] = len(ar_p), len(cc_p)
        log('bake', f'{atlas}: {len(names)} lows, {len(ar_p):,} arris and {len(cc_p):,} corner samples from the lows')
        return meta
    finally:
        for n, o in real.items():
            o.name = n
        for o in list(tmp.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(tmp)


# ---------------------------------------------------------------------------------- the lows, drawn on a part ---

def make_low(h, coll, sharp_deg=30.0, hard=True, keep_slots=False, smooth_soft=False):
    """A part made as one mass with one bevel: its low is its own construction without the bevel (the base mesh the
    bevel rounds), triangulated once, hard where its faces turn more than sharp_deg (hard=False: a moulded skin, smooth
    all over: it keeps the shading its mesh has, or with smooth_soft every edge is made smooth). keep_slots: the low
    keeps the part's material slots (a look that gives each slot its own material). The low is named <part>_low, stands
    where the part stands, and records its part ('bake_from') and the bevel's width ('bevel_mm')."""
    import bmesh
    me = h.data.copy()
    me.name = h.name + '_low'
    if not keep_slots:
        me.materials.clear()
    o = bpy.data.objects.new(h.name + '_low', me)
    o.matrix_world = h.matrix_world.copy()
    coll.objects.link(o)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    if hard:
        lim = math.radians(sharp_deg)
        for e in bm.edges:
            e.smooth = not (len(e.link_faces) != 2 or e.calc_face_angle(0.0) > lim)
    elif smooth_soft:
        for e in bm.edges:
            e.smooth = True
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    b = h.modifiers.get('edge_group')
    o['bake_from'] = h.name
    o['bevel_mm'] = b.width * 1e3 if b else 0.0
    return o


def edit(objs, fn):
    """fn() run in Edit Mode over objs with every face selected (the UV operators)"""
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    fn()
    bpy.ops.object.mode_set(mode='OBJECT')


def unwrap(lows, uv_name='atlas'):
    """each low unwrapped by planes (smart project, 60 degrees), islands at their own scale"""
    for o in lows:
        if uv_name not in o.data.uv_layers:
            o.data.uv_layers.new(name=uv_name)
        o.data.uv_layers.active = o.data.uv_layers[uv_name]
        edit([o], lambda: bpy.ops.uv.smart_project(angle_limit=math.radians(60.0), island_margin=0.0, area_weight=0.0,
                                                   correct_aspect=True, scale_to_bounds=False))


def islands(bm, uv):
    """the UV islands of a bmesh: lists of face indices joined by shared UV corners"""
    bm.faces.ensure_lookup_table()
    parent = list(range(len(bm.faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in bm.edges:
        lf = e.link_faces
        if len(lf) != 2:
            continue
        a, b = lf[0], lf[1]
        same = True
        for v in e.verts:
            ua = next(lp[uv].uv for lp in a.loops if lp.vert == v)
            ub = next(lp[uv].uv for lp in b.loops if lp.vert == v)
            if (ua - ub).length > 1e-6:
                same = False
                break
        if same:
            ra, rb = find(a.index), find(b.index)
            if ra != rb:
                parent[ra] = rb
    groups = {}
    for f in bm.faces:
        groups.setdefault(find(f.index), []).append(f.index)
    return list(groups.values())


def true_size_weighted(o, weight, uv_name='atlas'):
    """Every UV island of o at its own size in metres, times the square root of its faces' mean weight (texels go
    where the lens looks). weight(name, centre, normal) -> 0..1, in the room's space."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.faces.ensure_lookup_table()
    bm.transform(o.matrix_world)
    bm.normal_update()
    uv = bm.loops.layers.uv[uv_name]
    for faces in islands(bm, uv):
        a3 = sum(bm.faces[i].calc_area() for i in faces)
        a2 = 0.0
        for i in faces:
            ls = [lp[uv].uv for lp in bm.faces[i].loops]
            for j in range(1, len(ls) - 1):
                a2 += abs((ls[j].x - ls[0].x) * (ls[j + 1].y - ls[0].y) - (ls[j].y - ls[0].y) * (ls[j + 1].x - ls[0].x)) * 0.5
        wsum = sum(bm.faces[i].calc_area() * weight(o.name, bm.faces[i].calc_center_median(), bm.faces[i].normal) for i in faces)
        w = wsum / max(a3, 1e-12)
        s = math.sqrt(a3 / max(a2, 1e-12)) * math.sqrt(max(w, 0.01))
        for i in faces:
            for lp in bm.faces[i].loops:
                lp[uv].uv = lp[uv].uv * s
    bm.transform(o.matrix_world.inverted())
    bm.to_mesh(o.data)
    bm.free()


def pack(lows, size, gutter_px=8.0, uv_name='atlas', rotate_method='CARDINAL'):
    """the lows' islands packed into one square (rotate_method: 'CARDINAL' quarter turns only, 'ANY' any turn), with a
    gutter of gutter_px at 4096 scaled to size"""
    for o in lows:
        o.data.uv_layers.active = o.data.uv_layers[uv_name]
    gutter = gutter_px * size / 4096.0
    edit(lows, lambda: bpy.ops.uv.pack_islands(rotate=True, rotate_method=rotate_method, scale=True,
                                               margin_method='FRACTION', margin=gutter / size, shape_method='CONCAVE'))


def density(lows, size, uv_name='atlas'):
    """{low name: (densest, median) texels a metre}"""
    from mathutils import Vector
    out = {}
    for o in lows:
        me = o.data
        uvd = me.uv_layers[uv_name].data
        vals = []
        for p in me.polygons:
            if p.area < 1e-7:
                continue
            l_ = list(p.loop_indices)
            a, b, c = (Vector(uvd[i].uv) for i in l_[:3])
            vals.append(math.sqrt(abs((b - a).cross(c - a)) * 0.5 * size * size / p.area))
        if vals:
            out[o.name] = (round(float(np.max(vals))), round(float(np.median(vals))))
    return out


def write_atlases(path, atlases):
    """the room's atlases and their bake settings, for make.py's bake step: [{name, size, ao, cav}]"""
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(atlases, f, indent=1)
