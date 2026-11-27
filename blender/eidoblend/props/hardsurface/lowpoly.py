"""eidoblend.props.hardsurface.lowpoly: a built low finished for its bake: its normals, its seams, its UVs, its pack.

    from eidoblend.props.hardsurface import lowpoly
    rep = lowpoly.prepare_low(parts, sharp_deg=40.0, hide_dir=(0.0, -0.45, -0.89), cells=1024)
    # rep: {'triangles', 'islands', 'hidden_islands', 'uv_fill', 'area_m2', 'parts': [(name, triangles, cuts, mm2)]}

The low is the same construction as the high at lower resolution (masses.start(low=True)): nothing decimated, nothing
remeshed. prepare_low finishes it in place, every part at identity in the asset's space:
  * coplanar runs merged and the fewest triangles a flat's outline needs (BEAUTY); a closed part turned right side out
    by its signed volume; custom normals weighted by the area of each face's COPLANAR REGION, so a big flat panel,
    however its fill is triangulated, shades dead flat and its neighbours carry the bending (region_weighted_normals)
  * hard edges (over sharp_deg) split in the normals, and every one is a UV seam; an island that would not flatten (a
    tube, a closed skin) is cut once more along the cheapest line of its own edges, cheapest where the surface faces
    hide_dir (the side the asset is seen least from)
  * unwrapped (angle-based), every island scaled to ONE texel density by its own surface area; an island inside
    another part (a tube inside a stock) gets hidden_scale of that density
  * packed by uv_pack (cells x cells, a gutter of `gutter` cells)
The triangulation is frozen here: the bake's tangents come from it (bake_export.write_low), and the same mesh is what
renders.
"""

from __future__ import annotations

import math
from collections import defaultdict
from heapq import heappop, heappush

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from . import uv_pack

MM = 1e-3


def region_weighted_normals(me, sharp_deg):
    """Custom normals weighted by the area of each face's coplanar region: a big flat panel dominates every vertex
    it touches, so it shades dead flat."""
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    region, areas = {}, []
    cos_flat = math.cos(math.radians(0.5))
    for f in bm.faces:
        if f.index in region:
            continue
        rid = len(areas)
        region[f.index] = rid
        stack, area = [f], 0.0
        while stack:
            g = stack.pop()
            area += g.calc_area()
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in region and h.normal.dot(g.normal) > cos_flat:
                        region[h.index] = rid
                        stack.append(h)
        areas.append(area)
    cos_sharp = math.cos(math.radians(sharp_deg))
    per_face = {}
    for f in bm.faces:
        ns = []
        for lp in f.loops:
            acc = Vector()
            for h in lp.vert.link_faces:
                if h.normal.dot(f.normal) >= cos_sharp:
                    acc += h.normal * areas[region[h.index]]
            ns.append(acc.normalized() if acc.length > 1e-12 else f.normal.copy())
        per_face[f.index] = ns
    bm.free()
    loops = [None] * len(me.loops)
    for p in me.polygons:
        for k, li in enumerate(p.loop_indices):
            loops[li] = per_face[p.index][k]
    me.normals_split_custom_set(loops)


def islands_of(bm):
    """Face islands: faces joined across edges that are not seams."""
    seen, out = {}, []
    for f in bm.faces:
        if f.index in seen:
            continue
        isl, stack = [], [f]
        seen[f.index] = len(out)
        while stack:
            g = stack.pop()
            isl.append(g)
            for e in g.edges:
                if e.seam or len(e.link_faces) != 2:
                    continue
                for h in e.link_faces:
                    if h.index not in seen:
                        seen[h.index] = len(out)
                        stack.append(h)
        out.append(isl)
    return out


def chi_and_borders(isl):
    """The island's Euler characteristic once it is cut along its seams (1 for a disk), and its border edges."""
    fs = set(f.index for f in isl)
    E = 0
    border = []
    for e in {e for f in isl for e in f.edges}:
        k = sum(1 for f in e.link_faces if f.index in fs)
        if e.seam or k == 1:
            E += k
            border.append(e)
        else:
            E += 1
    V = 0
    for v in {v for f in isl for v in f.verts}:
        fan = [f for f in v.link_faces if f.index in fs]
        grp = {f.index: f.index for f in fan}

        def find(a):
            while grp[a] != a:
                grp[a] = grp[grp[a]]
                a = grp[a]
            return a
        for e in v.link_edges:
            if e.seam:
                continue
            lf = [f for f in e.link_faces if f.index in fs]
            if len(lf) == 2:
                ra, rb = find(lf[0].index), find(lf[1].index)
                if ra != rb:
                    grp[ra] = rb
        V += len({find(f.index) for f in fan})
    return V - E + len(isl), border


def cut_path(isl, border, hide_dir, sharp_deg):
    """One seam line that opens the island: from one border loop to another (a tube), or along a closed skin from its
    lowest-x vertex to its highest; it runs on the island's own edges, cheapest where the surface faces hide_dir.
    Returns the number of edges cut."""
    fs = set(f.index for f in isl)
    verts = {v for f in isl for v in f.verts}
    inner = [e for e in {e for f in isl for e in f.edges} if not e.seam and sum(1 for f in e.link_faces if f.index in fs) == 2]
    adj = defaultdict(list)
    for e in inner:
        n_ = (e.link_faces[0].normal + e.link_faces[1].normal).normalized()
        w = e.calc_length() * (2.0 - n_.dot(hide_dir)) * (1.0 - 0.5 * min(1.0, e.calc_face_angle(0.0) / math.radians(sharp_deg)))
        a, b = e.verts
        adj[a.index].append((b.index, w, e))
        adj[b.index].append((a.index, w, e))
    bv = defaultdict(set)
    for e in border:
        bv[e.verts[0].index].add(e.verts[1].index)
        bv[e.verts[1].index].add(e.verts[0].index)
    comp = {}
    for s in bv:
        if s in comp:
            continue
        stack = [s]
        comp[s] = s
        while stack:
            a = stack.pop()
            for b in bv[a]:
                if b not in comp:
                    comp[b] = s
                    stack.append(b)
    loops = defaultdict(set)
    for v, c in comp.items():
        loops[c].add(v)
    loops = list(loops.values())
    if len(loops) >= 2:
        src, dst = loops[0], set().union(*loops[1:])
    else:
        vs = sorted(verts, key=lambda v: v.co.x)
        src = {vs[0].index} if not loops else loops[0]
        dst = {vs[-1].index}
    dist = {s: 0.0 for s in src}
    prev = {}
    heap = [(0.0, s) for s in src]
    end = None
    while heap:
        d, a = heappop(heap)
        if d > dist.get(a, 1e18):
            continue
        if a in dst and a not in src:
            end = a
            break
        for b, w, e in adj[a]:
            nd = d + w
            if nd < dist.get(b, 1e18):
                dist[b] = nd
                prev[b] = (a, e)
                heappush(heap, (nd, b))
    if end is None:
        return 0
    k = 0
    while end in prev:
        a, e = prev[end]
        e.seam = True
        k += 1
        end = a
    return k


def _finish_part(o, sharp_deg, hide_dir, uv_name):
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-6)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=2e-6)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.5), verts=bm.verts, edges=bm.edges)
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method='BEAUTY', ngon_method='BEAUTY')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if all(e.is_manifold for e in bm.edges) and bm.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.normal_update()
    for e in bm.edges:
        hard = len(e.link_faces) != 2 or e.calc_face_angle(0.0) > math.radians(sharp_deg)
        e.smooth = not hard
        e.seam = hard
    for f in bm.faces:
        f.smooth = True
    cuts = 0
    for _ in range(12):                                          # cut until every island is a disk
        bad = 0
        for isl in islands_of(bm):
            chi, border = chi_and_borders(isl)
            if chi != 1:
                bad += 1
                cuts += cut_path(isl, border, hide_dir, sharp_deg)
        if not bad:
            break
    bm.to_mesh(me)
    bm.free()
    me.update()
    region_weighted_normals(me, sharp_deg)
    if uv_name not in me.uv_layers:
        me.uv_layers.new(name=uv_name)
    me.uv_layers.active = me.uv_layers[uv_name]
    return len(me.polygons), cuts, sum(p.area for p in me.polygons) / (MM * MM)


def prepare_low(parts, sharp_deg: float = 40.0, hide_dir=(0.0, -0.45, -0.89), hidden_scale: float = 0.2,
                cells: int = 1024, gutter: int = 2, uv_name: str = 'UVMap', log=print) -> dict:
    """Finish the low's parts for their bake, in place (see the module doc). parts: mesh objects (their transforms are
    applied and their modifiers dropped). Returns a report dict."""
    parts = list(parts)
    bpy.context.view_layer.update()
    for o in parts:
        if o.matrix_world != Matrix.Identity(4):
            o.data.transform(o.matrix_world)
            o.matrix_world = Matrix.Identity(4)
        o.modifiers.clear()
    hide = Vector(hide_dir).normalized()
    rep = {'parts': []}
    total_area = 0.0
    for o in parts:
        tris, cuts, area = _finish_part(o, sharp_deg, hide, uv_name)
        total_area += area
        rep['parts'].append((o.name, tris, cuts, round(area)))
    # the unwrap: every part in one edit session
    for o in bpy.context.scene.objects:
        o.select_set(o in parts)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.context.scene.tool_settings.use_uv_select_sync = True
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.unwrap(method='ANGLE_BASED', fill_holes=True, correct_aspect=True, margin=0.0)
    bpy.ops.object.mode_set(mode='OBJECT')
    # one density: each island by its own area. Hidden: a face whose centre, lifted 0.3 mm, is inside ANOTHER part
    dg = bpy.context.evaluated_depsgraph_get()
    trees = {o.name: BVHTree.FromObject(o, dg) for o in parts}
    bbs = {o.name: (np.min(np.array([v.co for v in o.data.vertices]), 0), np.max(np.array([v.co for v in o.data.vertices]), 0))
           for o in parts}

    def inside_other(p, own):
        for nm, (lo, hi) in bbs.items():
            if nm == own or np.any(np.array(p) < lo - 1e-4) or np.any(np.array(p) > hi + 1e-4):
                continue
            t, q, hits = trees[nm], Vector(p), 0
            d = Vector((0.0, 0.0, 1.0))
            for _ in range(24):
                h = t.ray_cast(q, d, 1.0)
                if h[0] is None:
                    break
                hits += 1
                q = h[0] + d * 1e-6
            if hits % 2 == 1:
                return True
        return False

    hidden_islands, n_isl, weights = 0, 0, {}
    for o in parts:
        me = o.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        uvl = bm.loops.layers.uv[uv_name]
        fw = [1.0] * len(bm.faces)
        for isl in islands_of(bm):
            n_isl += 1
            a3 = sum(f.calc_area() for f in isl) / (MM * MM)
            auv = 0.0
            for f in isl:
                u = [lp[uvl].uv for lp in f.loops]
                auv += abs((u[1] - u[0]).cross(u[2] - u[0])) / 2.0
            hid = sum(f.calc_area() for f in isl if inside_other(tuple(f.calc_center_median() + f.normal * 0.0003), o.name)) / (MM * MM)
            if hid > 0.9 * a3:
                hidden_islands += 1
                for f in isl:
                    fw[f.index] = hidden_scale
            if auv < 1e-12 or a3 < 1e-9:
                continue
            s = math.sqrt(a3 / auv) * 1e-3                       # one density (the packer applies the weights)
            c = sum((lp[uvl].uv for f in isl for lp in f.loops), Vector((0.0, 0.0))) / sum(len(f.loops) for f in isl)
            for f in isl:
                for lp in f.loops:
                    lp[uvl].uv = c + (lp[uvl].uv - c) * s
        bm.to_mesh(me)
        bm.free()
        weights[o.name] = fw
    fill = uv_pack.pack(parts, weights, N=cells, gutter=gutter, log=log)
    rep.update(triangles=sum(r[1] for r in rep['parts']), islands=n_isl, hidden_islands=hidden_islands, uv_fill=fill,
               area_m2=total_area * 1e-6)
    log(f'[lowpoly] {len(parts)} parts, {rep["triangles"]:,} triangles, {n_isl} islands ({hidden_islands} inside other '
        f'parts), {fill * 100:.1f} % of the square')
    return rep
