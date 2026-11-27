"""eidoblend.props.hardsurface.bake_export: what the GPU baker (blender/tools/gpu_bake.py) reads, written from Blender.

    from eidoblend.props.hardsurface import bake_export
    # in the session that holds the HIGH (its parts with their bevels and normals as modifiers):
    bake_export.write_high(high_parts, 'work/my_prop/bake', 'my_prop')
    # in the session that holds the LOW (finished by lowpoly.prepare_low: triangulated, UVs packed):
    bake_export.write_low(low_parts, 'work/my_prop/bake', 'my_prop', size=4096, substrate={'body': 1, 'pin': 5})
    # then, outside Blender:   python blender/tools/gpu_bake.py --bake work/my_prop/bake --name my_prop

A low part bakes from the high part of the SAME NAME only (a texel's ray never lands on a neighbour), so the two lists
hold the same names. Every part is read in the asset's space (world space; keep the asset at the origin).

<name>_high.npz   p (H, 3, 3) the high's triangles (its modifiers applied), n (H, 3, 3) their corner normals (as they
                  shade), part (H); ar_p / ar_n / ar_part: the high's own sharp CONVEX edges BEFORE its bevels (its base
                  mesh), sampled every arris_mm, with each edge's outward direction (the baker keeps the samples its
                  rays find exposed: the edge-wear map); cc_p / cc_part: its sharp CONCAVE edges (the inside-corner map);
                  occ_p (K, 3, 3): triangles that only occlude (rigid neighbours that are not baked)
<name>_low.npz    per low triangle corner: p position, n shading normal, t MikkTSpace tangent and sign (Blender's, for
                  this frozen triangulation: the frame EEVEE's normal-map node builds), uv, cage (each vertex's
                  angle-weighted normal, one direction per position), part
<name>.json       names, substrate (part -> ID, 0..15: the ID map and a layered material's table row), size, uv_fill,
                  px_per_mm, the triangle counts, and the bake's options (ao_mm, cav_mm, edge_mm, corner_mm; cage_mm /
                  reach_mm per part to override the measured cage)
"""

from __future__ import annotations

import json
import math
import os

import bmesh
import bpy
import numpy as np

MM = 1e-3


def _edge_samples(o, step, sharp_deg):
    """The base mesh's sharp convex edges (sampled, with outward directions) and sharp concave edges (sampled)."""
    M = o.matrix_world.copy()
    b0 = bmesh.new()
    b0.from_mesh(o.data)
    b0.transform(M)
    b0.normal_update()
    conv_p, conv_n, conc_p = [], [], []
    lim = math.radians(sharp_deg)
    for e in b0.edges:
        if len(e.link_faces) != 2:
            continue
        a = e.calc_face_angle_signed(0.0)
        p0, p1 = e.verts[0].co, e.verts[1].co
        k = max(1, int((p1 - p0).length / step))
        if a >= lim:
            n_ = e.link_faces[0].normal + e.link_faces[1].normal
            if n_.length < 1e-6:
                continue
            n_.normalize()
            for i in range(k + 1):
                conv_p.append(tuple(p0.lerp(p1, i / k)))
                conv_n.append(tuple(n_))
        elif a <= -lim:
            for i in range(k + 1):
                conc_p.append(tuple(p0.lerp(p1, i / k)))
    b0.free()
    return conv_p, conv_n, conc_p


def _triangles(o, dg):
    """The evaluated mesh's triangles in world space: positions (T, 3, 3), corner normals (T, 3, 3)."""
    M = o.matrix_world.copy()
    N3 = M.to_3x3().inverted().transposed()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    me.calc_loop_triangles()
    nt = len(me.loop_triangles)
    tl = np.empty(nt * 3, np.int32)
    tv = np.empty(nt * 3, np.int32)
    me.loop_triangles.foreach_get('loops', tl)
    me.loop_triangles.foreach_get('vertices', tv)
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    cn = np.empty(len(me.loops) * 3, np.float32)
    me.corner_normals.foreach_get('vector', cn)
    co = co.reshape(-1, 3) @ np.array(M.to_3x3()).T.astype(np.float32) + np.array(M.translation, np.float32)
    cn = cn.reshape(-1, 3) @ np.array(N3).T.astype(np.float32)
    cn /= np.maximum(np.linalg.norm(cn, axis=1, keepdims=True), 1e-12)
    bpy.data.meshes.remove(me)
    return co[tv].reshape(nt, 3, 3), cn[tl].reshape(nt, 3, 3)


def write_high(parts, out_dir: str, name: str, arris_mm: float = 0.3, sharp_deg: float = 30.0, occluders=(),
               log=print) -> dict:
    """The highs' bake inputs (see the module doc). parts: the high's mesh objects, one per low part, by name.
    occluders: other objects that cast ambient occlusion on the asset but are not baked."""
    os.makedirs(out_dir, exist_ok=True)
    parts = sorted(parts, key=lambda o: o.name)
    dg = bpy.context.evaluated_depsgraph_get()
    hp, hn, hpart = [], [], []
    ar_p, ar_n, ar_part, cc_p, cc_part = [], [], [], [], []
    for pi, o in enumerate(parts):
        cp, cn_, kp = _edge_samples(o, arris_mm * MM, sharp_deg)
        ar_p += cp
        ar_n += cn_
        ar_part += [pi] * len(cp)
        cc_p += kp
        cc_part += [pi] * len(kp)
        p, n = _triangles(o, dg)
        hp.append(p)
        hn.append(n)
        hpart.append(np.full(len(p), pi, np.int32))
    occ = [_triangles(o, dg)[0] for o in occluders]
    hp, hn, hpart = np.concatenate(hp), np.concatenate(hn), np.concatenate(hpart)
    np.savez_compressed(os.path.join(out_dir, f'{name}_high.npz'), p=hp.astype(np.float32), n=hn.astype(np.float16),
                        part=hpart, ar_p=np.array(ar_p, np.float32).reshape(-1, 3), ar_n=np.array(ar_n, np.float16).reshape(-1, 3),
                        ar_part=np.array(ar_part, np.int32), cc_p=np.array(cc_p, np.float32).reshape(-1, 3),
                        cc_part=np.array(cc_part, np.int32),
                        occ_p=(np.concatenate(occ) if occ else np.zeros((0, 3, 3))).astype(np.float32))
    meta = {'names': [o.name for o in parts], 'high_triangles': int(len(hp)), 'arris_samples': len(ar_p),
            'corner_samples': len(cc_p), 'occluder_triangles': int(sum(len(o) for o in occ))}
    with open(os.path.join(out_dir, f'{name}_high.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(meta, f, indent=1)
    log(f'[bake_export] {name}: highs of {len(parts)} parts, {len(hp):,} triangles, {len(ar_p):,} arris samples')
    return meta


def write_low(parts, out_dir: str, name: str, size: int = 4096, substrate=None, ids=None, uv_name: str = 'UVMap',
              options=None, log=print) -> dict:
    """The lows' bake inputs and the bake's settings (see the module doc). parts: the low's mesh objects, finished
    (triangulated, UVs in [0, 1]); substrate: {part name: ID} or a function name -> ID (default 1); ids: {ID: label}
    for the record; options: the bake's settings to store (ao_mm, cav_mm, edge_mm, corner_mm, cage_mm, reach_mm)."""
    os.makedirs(out_dir, exist_ok=True)
    parts = sorted(parts, key=lambda o: o.name)
    names = [o.name for o in parts]
    hj = os.path.join(out_dir, f'{name}_high.json')
    high = json.load(open(hj, encoding='utf-8')) if os.path.exists(hj) else {}
    if high and high.get('names') != names:
        raise ValueError(f'write_low: the high and the low hold different parts: {set(names) ^ set(high["names"])}')
    sub = substrate if callable(substrate) else (lambda n, s=substrate or {}: int(s.get(n, 1)))
    lp, ln, lt, luv, lcage, lpart = [], [], [], [], [], []
    uv_area, area = 0.0, 0.0
    for pi, o in enumerate(parts):
        me = o.data
        me.calc_tangents(uvmap=uv_name)
        me.calc_loop_triangles()
        nt = len(me.loop_triangles)
        tl = np.empty(nt * 3, np.int32)
        tv = np.empty(nt * 3, np.int32)
        me.loop_triangles.foreach_get('loops', tl)
        me.loop_triangles.foreach_get('vertices', tv)
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        cn = np.empty(len(me.loops) * 3, np.float32)
        me.corner_normals.foreach_get('vector', cn)
        tg = np.empty(len(me.loops) * 3, np.float32)
        me.loops.foreach_get('tangent', tg)
        sg = np.empty(len(me.loops), np.float32)
        me.loops.foreach_get('bitangent_sign', sg)
        uv = np.empty(len(me.loops) * 2, np.float32)
        me.uv_layers[uv_name].uv.foreach_get('vector', uv)
        uv = uv.reshape(-1, 2)
        cg = np.zeros((len(me.vertices), 3))                    # the cage: each vertex's angle-weighted normal
        for p in me.polygons:
            vs = [co[i] for i in p.vertices]
            n_ = np.array(p.normal)
            for k, vi in enumerate(p.vertices):
                a_ = vs[k - 1] - vs[k]
                b_ = vs[(k + 1) % len(vs)] - vs[k]
                ang = math.acos(max(-1.0, min(1.0, float(np.dot(a_, b_) / max(np.linalg.norm(a_) * np.linalg.norm(b_), 1e-12)))))
                cg[vi] += n_ * ang
        cg /= np.maximum(np.linalg.norm(cg, axis=1, keepdims=True), 1e-12)
        lp.append(co[tv].reshape(nt, 3, 3))
        ln.append(cn.reshape(-1, 3)[tl].reshape(nt, 3, 3))
        lt.append(np.concatenate([tg.reshape(-1, 3)[tl], sg[tl][:, None]], 1).reshape(nt, 3, 4))
        luv.append(uv[tl].reshape(nt, 3, 2))
        lcage.append(cg[tv].reshape(nt, 3, 3))
        lpart.append(np.full(nt, pi, np.int32))
        u3 = uv[tl].reshape(nt, 3, 2)
        uv_area += float(np.sum(np.abs(np.cross(u3[:, 1] - u3[:, 0], u3[:, 2] - u3[:, 0])) / 2.0))
        area += sum(p.area for p in me.polygons) / (MM * MM)
    lp, ln, lt, luv, lcage, lpart = (np.concatenate(a) for a in (lp, ln, lt, luv, lcage, lpart))
    np.savez_compressed(os.path.join(out_dir, f'{name}_low.npz'), p=lp.astype(np.float32), n=ln.astype(np.float32),
                        t=lt.astype(np.float32), uv=luv.astype(np.float32), cage=lcage.astype(np.float32), part=lpart)
    dens = math.sqrt(uv_area * size * size / max(area, 1e-9))
    meta = {'names': names, 'substrate': {n: sub(n) for n in names}, 'ids': ids or {}, 'size': int(size),
            'uv_fill': uv_area, 'px_per_mm': dens, 'low_triangles': int(len(lp)),
            'high_triangles': high.get('high_triangles'), 'options': dict(options or {})}
    with open(os.path.join(out_dir, f'{name}.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(meta, f, indent=1)
    log(f'[bake_export] {name}: lows of {len(parts)} parts, {len(lp):,} triangles; UV fill {uv_area * 100:.1f} %; '
        f'{dens:.2f} px/mm at {size}')
    return meta
