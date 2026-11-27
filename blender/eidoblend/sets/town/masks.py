"""eidoblend.sets.town.masks: the town's masks, from its geometry. Blender; the layout calls annotate(collection) once
the town stands.

Every mask has a physical cause and the geometric signal that encodes it, computed from the final geometry at physical
sizes and stored on each unique mesh (each placing then differs by its own random number in the materials). The
town's meshes are big flat faces (a wall bay between its openings is a handful of quads), so the masks are stored PER
FACE as the numbers a shader needs to draw the mask per pixel (eidoblend.sets.town.materials), not as values to be
interpolated between corners:

  tl_edge  (FLOAT)        on an upright face: the height of the nearest edge water runs off above it: the underside of
                          what juts out over it (a sill, a slab's band, a balcony, a hood) or the top of the wall it is
                          part of (a coping, an opening's sill), found by casting up from just outside and just inside the
                          face's top edge. Runs start at that edge and go straight down. (1e4 elsewhere: no runs.)
  tl_box   (FLOAT_COLOR)  on a face that looks up: its extent (x0, y0, x1, y1): dust and grit drift against whatever
                          stands at a roof's or a yard's edges.
  tl_corner (FLOAT_COLOR) on an upright face: its extent along the wall and which of its ends is an INSIDE corner
                          (something stands out in front of the face there): grime against the corner.
  tl_soot  (FLOAT_COLOR)  on the upright faces of a struck building: the opening under it whose room burned: (its
                          middle along the wall, its head's height, its half width, how hard it burned): soot above
                          fire. The openings are the house's own 'void' faces (a dark room behind a lost window).
  tl_lane  (FLOAT_COLOR)  on a road or a track: (its middle line, its half width): the lane frame its wheel paths, oil
                          line, gutters and ruts are drawn in.
"""
import hashlib

import bpy
import numpy as np
from mathutils.bvhtree import BVHTree

FAR = 1.0e4


def _faces(me):
    n = len(me.polygons)
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    nrm = np.empty(n * 3, np.float32)
    me.polygons.foreach_get('normal', nrm)
    ls, lt = np.empty(n, np.int64), np.empty(n, np.int64)
    me.polygons.foreach_get('loop_start', ls)
    me.polygons.foreach_get('loop_total', lt)
    mi = np.empty(n, np.int64)
    me.polygons.foreach_get('material_index', mi)
    lv = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get('vertex_index', lv)
    P = co[lv]
    f = {'n': n, 'co': co, 'nrm': nrm.reshape(-1, 3), 'ls': ls, 'lt': lt, 'mi': mi, 'P': P}
    for k, ax in (('x', 0), ('y', 1), ('z', 2)):
        f[k + '0'] = np.minimum.reduceat(P[:, ax], ls)
        f[k + '1'] = np.maximum.reduceat(P[:, ax], ls)
    top = P[:, 2] >= np.repeat(f['z1'], lt) - 0.01
    cnt = np.add.reduceat(top.astype(np.float64), ls)
    f['tx'] = np.add.reduceat(np.where(top, P[:, 0], 0.0), ls) / cnt
    f['ty'] = np.add.reduceat(np.where(top, P[:, 1], 0.0), ls) / cnt
    f['cx'] = np.add.reduceat(P[:, 0], ls) / lt
    f['cy'] = np.add.reduceat(P[:, 1], ls) / lt
    return f


def _bvh(me):
    return BVHTree.FromPolygons([tuple(v.co) for v in me.vertices], [tuple(p.vertices) for p in me.polygons], all_triangles=False, epsilon=0.0)


def _set(me, name, kind, values):
    a = me.attributes.get(name)
    if a is not None and (a.data_type != kind or a.domain != 'FACE'):
        me.attributes.remove(a)
        a = None
    if a is None:
        a = me.attributes.new(name, kind, 'FACE')
    a.data.foreach_set('value' if kind == 'FLOAT' else 'color', np.ascontiguousarray(values, np.float32).ravel())


def edges_and_boxes(me, f, bvh):
    """tl_edge on every upright face; tl_box on every face that looks up"""
    nz = f['nrm'][:, 2]
    wall = np.abs(nz) < 0.35
    edge = np.full(f['n'], FAR, np.float32)
    up = (0.0, 0.0, 1.0)
    for i in np.nonzero(wall)[0]:
        nx, ny = f['nrm'][i, 0], f['nrm'][i, 1]
        L = (nx * nx + ny * ny) ** 0.5
        if L < 1e-6:
            continue
        nx, ny = nx / L, ny / L
        z = f['z1'][i] - 0.02
        best = None
        for off in (0.03, -0.04):                                     # just outside the face, and just inside the wall
            hit = bvh.ray_cast((f['tx'][i] + nx * off, f['ty'][i] + ny * off, z), up, 8.0)
            if hit[0] is not None and hit[3] > 0.004:
                best = hit[0][2] if best is None else min(best, hit[0][2])
        edge[i] = best if best is not None else f['z1'][i]
    _set(me, 'tl_edge', 'FLOAT', edge)
    box = np.empty((f['n'], 4), np.float32)
    box[:] = (-FAR, -FAR, FAR, FAR)
    flat = nz > 0.7
    box[flat, 0], box[flat, 1], box[flat, 2], box[flat, 3] = f['x0'][flat], f['y0'][flat], f['x1'][flat], f['y1'][flat]
    _set(me, 'tl_box', 'FLOAT_COLOR', box)
    return int(wall.sum()), int(flat.sum())


def corners(me, f, bvh):
    """tl_corner on every upright face: (its extent along the wall, low end and high end, in the same coordinate the
    shader walks along a wall: x on a face that looks along y, y on one that looks along x; and whether each end is an
    INSIDE corner: a wall, a column, a stair head standing out in front of the face there). The grime against the
    junction is ramped over a few tens of centimetres; an opening's edge is an arris, not a corner, and stays clean."""
    nz = f['nrm'][:, 2]
    out = np.zeros((f['n'], 4), np.float32)
    out[:, 0], out[:, 1] = -FAR, FAR
    for i in np.nonzero(np.abs(nz) < 0.35)[0]:
        nx, ny = float(f['nrm'][i, 0]), float(f['nrm'][i, 1])
        alongx = abs(ny) > abs(nx)
        u0, u1 = (f['x0'][i], f['x1'][i]) if alongx else (f['y0'][i], f['y1'][i])
        if u1 - u0 < 0.05:
            continue
        L = (nx * nx + ny * ny) ** 0.5
        nx, ny = nx / L, ny / L
        zc = (f['z0'][i] + f['z1'][i]) / 2.0
        cx, cy = f['cx'][i], f['cy'][i]
        flags = []
        for end, sgn in ((u0, -1.0), (u1, 1.0)):
            px = (end - sgn * 0.02) if alongx else cx
            py = cy if alongx else (end - sgn * 0.02)
            o_ = (px + nx * 0.05, py + ny * 0.05, zc)               # just in front of the face, at its end
            d_ = (sgn, 0.0, 0.0) if alongx else (0.0, sgn, 0.0)
            hit = bvh.ray_cast(o_, d_, 0.3)
            flags.append(1.0 if hit[0] is not None else 0.0)
        out[i] = (u0, u1, flags[0], flags[1])
    _set(me, 'tl_corner', 'FLOAT_COLOR', out)
    return int((out[:, 2] + out[:, 3] > 0).sum())


def _h(*xs):
    return int(hashlib.md5(repr(xs).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def soot_sources(me, f):
    """tl_soot on the upright faces of a struck building, from the house's 'void' faces (a dark room behind a lost
    window): which of those rooms burned is the mesh's own chance (two in three)"""
    names = [m.name if m else '' for m in me.materials]
    void = [k for k, nm in enumerate(names) if nm == 'town.void']
    out = np.zeros((f['n'], 4), np.float32)
    if not void:
        _set(me, 'tl_soot', 'FLOAT_COLOR', out)
        return 0
    nrm = f['nrm']
    upright = np.abs(nrm[:, 2]) < 0.3
    src = np.nonzero(np.isin(f['mi'], void) & upright)[0]
    S = []
    for i in src:
        alongx = abs(nrm[i, 1]) > abs(nrm[i, 0])                     # the face looks along y: along it is x
        u0, u1 = (f['x0'][i], f['x1'][i]) if alongx else (f['y0'][i], f['y1'][i])
        plane = f['cy'][i] if alongx else f['cx'][i]
        k = _h(me.name, round(float(f['cx'][i]), 2), round(float(f['cy'][i]), 2), round(float(f['z1'][i]), 2))
        if k > 0.67 or (u1 - u0) < 0.3:
            continue
        S.append((alongx, float(np.sign(nrm[i, 1] if alongx else nrm[i, 0])), plane, (u0 + u1) / 2.0, float(f['z1'][i]), (u1 - u0) / 2.0, 0.55 + 0.45 * k / 0.67))
    if not S:
        _set(me, 'tl_soot', 'FLOAT_COLOR', out)
        return 0
    W = np.nonzero(upright)[0]
    for alongx, sgn, plane, su, sz, sw, sk in S:
        same = (np.abs(nrm[W, 1] if alongx else nrm[W, 0]) > 0.9) & (np.sign(nrm[W, 1] if alongx else nrm[W, 0]) == sgn)
        pl = f['cy'][W] if alongx else f['cx'][W]
        same &= np.abs(pl - plane) < 0.8
        uc = f['cx'][W] if alongx else f['cy'][W]
        dz = f['z0'][W] - sz
        wid = sw + 0.42 * np.maximum(dz, 0.0) + 0.3
        v = np.exp(-((uc - su) / wid) ** 2) * (dz > -0.4) * (dz < 3.2) * same * sk
        better = v > np.where(out[W, 3] > 0, np.exp(-((uc - out[W, 0]) / (out[W, 2] + 0.42 * np.maximum(f['z0'][W] - out[W, 1], 0.0) + 0.3)) ** 2) * out[W, 3], 0.0)
        pick = W[better & (v > 0.06)]
        out[pick] = (su, sz, sw, sk)
    _set(me, 'tl_soot', 'FLOAT_COLOR', out)
    return len(S)


def lanes(me, f):
    """tl_lane on the roads and tracks: each is a quad across its whole width, so its own extent is its lane frame"""
    names = [m.name if m else '' for m in me.materials]
    out = np.zeros((f['n'], 4), np.float32)
    n_ = 0
    for k, nm in enumerate(names):
        if nm not in ('town.road', 'town.road_y', 'town.track', 'town.track_y'):
            continue
        sel = f['mi'] == k
        if nm.endswith('_y'):
            out[sel, 0], out[sel, 1] = (f['x0'][sel] + f['x1'][sel]) / 2.0, (f['x1'][sel] - f['x0'][sel]) / 2.0
        else:
            out[sel, 0], out[sel, 1] = (f['y0'][sel] + f['y1'][sel]) / 2.0, (f['y1'][sel] - f['y0'][sel]) / 2.0
        n_ += int(sel.sum())
    _set(me, 'tl_lane', 'FLOAT_COLOR', out)
    return n_


SKIP = ('car_', 'palm', 'tree', 'bicycle')                       # (things whose materials read no mask)
STRUCK = ('town_HA', 'town_HC')                                  # the struck houses' meshes (soot over their openings)


def annotate(col, log=print):
    """every unique mesh of the town's collection, once (meshes without town materials, a SeedThree tree's or a CC0
    model's, are left alone)"""
    import time
    t0 = time.time()
    done, stats = set(), {'meshes': 0, 'walls': 0, 'flats': 0, 'corners': 0, 'soot': 0, 'lanes': 0}
    for o in col.all_objects:
        if o.type != 'MESH' or o.data in done:
            continue
        me = o.data
        done.add(me)
        if me.name.startswith(SKIP) or len(me.polygons) == 0:
            continue
        if not any(m is not None and m.name.startswith('town.') for m in me.materials):
            continue
        f = _faces(me)
        bvh = _bvh(me)
        w, fl = edges_and_boxes(me, f, bvh)
        stats['corners'] += corners(me, f, bvh)
        stats['meshes'] += 1
        stats['walls'] += w
        stats['flats'] += fl
        if me.name.startswith(STRUCK):
            stats['soot'] += soot_sources(me, f)
        if me.name in ('town_ground', 'town_streets'):
            stats['lanes'] += lanes(me, f)
            o['tn_space'] = 1.0
    log(f'MASKS {stats} in {time.time() - t0:.1f} s')
    return stats
