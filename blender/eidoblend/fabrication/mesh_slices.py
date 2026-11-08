"""eidoblend.fabrication.mesh_slices: closed cross-sections with holes, and the union of overlapping input meshes
(mesh_slices.js, MIT).

    slice_at = mesh_slicer(geometry, polygons=False)    # geometry: a SourceGeometry (source_geometry / fit_...)
    rings = slice_at(z)                                 # closed rings [(x, y), ..., first again] at height z
    polys = mesh_slicer(geometry, polygons=True)(z)     # [[outer, hole, ...], ...]

Each mesh of the snapshot (its manufacturing_source ranges) is sliced on its own: the plane's segments are chained into
rings by shared points (a point not shared by exactly two segments raises: open or non-manifold source), the surface's
winding makes inner walls holes rather than filled islands, every hole goes to the smallest solid that contains it, and
the solids are unioned (polygon_union.union), first per mesh and then all together: overlapping parts merge, a
separate solid inside another's hole survives. Heights are visited upward cheaply (the active triangle set is kept);
asking for a lower height starts over.
"""

from __future__ import annotations

import math

import numpy as np

from .polygon_union import union


def _area(r):
    a = 0.0
    for i in range(len(r) - 1):
        a += r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1]
    return a / 2


def _contains(r, p):
    inside = False
    for i in range(1, len(r)):
        a, b = r[i - 1], r[i]
        if (a[1] > p[1]) != (b[1] > p[1]) and p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0]:
            inside = not inside
    return inside


def mesh_slicer(geometry, polygons=False):
    tris = geometry.triangles
    n = len(tris)
    info = getattr(geometry, 'manufacturing_source', None) or {}
    ranges = info.get('ranges') or [{'first_triangle': 0, 'triangles': n, 'name': 'source'}]
    owners = np.zeros(n, dtype=np.int64)
    for i, r in enumerate(ranges):
        owners[r['first_triangle']:r['first_triangle'] + r['triangles']] = i
    lo_b, hi_b = geometry.bounding_box
    extent = float(np.linalg.norm(np.asarray(hi_b) - np.asarray(lo_b)))
    epsilon = max(1e-11, extent * 1e-8)

    def key(p):
        return (math.floor(p[0] / epsilon + .5), math.floor(p[1] / epsilon + .5))

    z = tris[:, :, 2]
    lo = z.min(axis=1)
    hi = z.max(axis=1)
    order = np.argsort(lo, kind='stable')
    tris_s, owners_s, lo_s, hi_s = tris[order], owners[order], lo[order], hi[order]
    # face normals (Blender axes) for the winding rule
    u = tris_s[:, 1] - tris_s[:, 0]
    v = tris_s[:, 2] - tris_s[:, 0]
    nx = u[:, 1] * v[:, 2] - u[:, 2] * v[:, 1]
    ny = u[:, 2] * v[:, 0] - u[:, 0] * v[:, 2]

    def slice_at(height):
        count = int(np.searchsorted(lo_s, height, side='right'))
        cand = np.nonzero(hi_s[:count] > height)[0]
        groups = {}
        if len(cand):
            T = tris_s[cand]
            hits = []
            crossing = []
            for j in range(3):
                a, b = T[:, j], T[:, (j + 1) % 3]
                c = ((a[:, 2] <= height) & (b[:, 2] > height)) | ((b[:, 2] <= height) & (a[:, 2] > height))
                with np.errstate(divide='ignore', invalid='ignore'):     # level edges never cross: masked by c
                    w = (height - a[:, 2]) / (b[:, 2] - a[:, 2])
                    hits.append(np.stack([a[:, 0] + w * (b[:, 0] - a[:, 0]), a[:, 1] + w * (b[:, 1] - a[:, 1])],
                                         axis=1))
                crossing.append(c)
            crossing = np.stack(crossing, axis=1)
            hits = np.stack(hits, axis=1)                    # (m, 3 edges, 2)
            for k in range(len(cand)):
                cs = crossing[k]
                if cs.sum() != 2:
                    continue
                idx = np.nonzero(cs)[0]
                h0, h1 = tuple(hits[k, idx[0]].tolist()), tuple(hits[k, idx[1]].tolist())
                if key(h0) == key(h1):
                    continue
                ti = cand[k]
                # preserve the surface winding so inner walls are holes, not filled islands
                if (h1[0] - h0[0]) * ny[ti] - (h1[1] - h0[1]) * nx[ti] < 0:
                    h0, h1 = h1, h0
                groups.setdefault(int(owners_s[ti]), []).append((h0, h1))
        solids = []
        for owner, segs in groups.items():
            graph = {}
            for i, s in enumerate(segs):
                for p in s:
                    graph.setdefault(key(p), []).append(i)
            for k_, edges in graph.items():
                if len(edges) != 2:
                    raise ValueError(f"Open or nonmanifold slice at height {height} in {ranges[owner]['name']}, {k_}. "
                                     'Repair the source mesh.')
            used = set()
            rings = []
            for i in range(len(segs)):
                if i in used:
                    continue
                ring = [segs[i][0], segs[i][1]]
                used.add(i)
                while key(ring[-1]) != key(ring[0]):
                    j = next((j for j in graph[key(ring[-1])] if j not in used), None)
                    if j is None:
                        raise ValueError('Source cross-section has an unclosed perimeter')
                    if key(segs[j][0]) != key(ring[-1]):
                        raise ValueError('Source cross-section has inconsistent face winding')
                    used.add(j)
                    ring.append(segs[j][1])
                ring[-1] = ring[0]
                if abs(_area(ring)) > epsilon * epsilon:
                    rings.append(ring)
            if not rings:
                continue
            largest = max(rings, key=lambda r: abs(_area(r)))
            orientation = math.copysign(1.0, _area(largest))
            outers = [[r] for r in rings if _area(r) * orientation > 0]
            holes = [r for r in rings if _area(r) * orientation < 0]
            for hole in holes:
                parents = [p for p in outers if abs(_area(p[0])) > abs(_area(hole)) and _contains(p[0], hole[0])]
                if not parents:
                    raise ValueError('Source cross-section has a hole without a containing solid')
                parents.sort(key=lambda p: abs(_area(p[0])))
                parents[0].append(hole)
            solid = union(*outers)
            if solid:
                solids.append(solid)
        if not solids:
            return []
        result = union(*[p for s in solids for p in s]) if len(solids) > 1 else solids[0]
        return result if polygons else [r for poly in result for r in poly]

    return slice_at
