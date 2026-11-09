"""eidoblend.characters.maneuvers.targets: what a move is aimed at, measured from the scene's own geometry.

    from eidoblend.characters.maneuvers import measure_obstacle, measure_ladder
    ob = measure_obstacle(cover, from_xy=(0, -3))     # its near face (point, normal), the heading that faces it square,
                                                      # its top, rise, depth and what lies beyond
    lad = measure_ladder(rungs, wall)                 # first rung, spacing, the rungs' line, the wall's top

The WebGPU controller scans the path ahead along its heading for a step it can vault, mount or scramble (and the
parkour calls act "on whatever obstacle is ahead along the heading"); a ladder's rungs are passed as numbers
(climbLadder({firstRung, rungSpacing, height})). Here an object in the scene is measured the same way the controller's
probes see it (rays against its visible meshes), so a move can be aimed at it from anywhere and a ladder of any build is
climbed rung for rung. Blender's axes: Z up, metres; a heading is the controller's (rad about +Z, 0 faces -Y).
"""

import math

import numpy as np
from mathutils import Vector


def _meshes(objs):
    from ...placement import _world as W
    out = []
    for ob in (objs if isinstance(objs, (list, tuple, set)) else [objs]):
        for o in [ob] + list(ob.children_recursive):
            if o.type == 'MESH' and W.visible(o) and o not in out:
                out.append(o)
    return out


def _rays(objs):
    from ...placement import _world as W
    W.update()
    return W.Rays(_meshes(objs))


def _box(objs):
    from ...placement import _world as W
    dg = W.depsgraph()
    lo, hi = Vector((1e30,) * 3), Vector((-1e30,) * 3)
    for o in _meshes(objs):
        a, b = W.box_of_object(o, dg)
        lo = Vector((min(lo.x, a.x), min(lo.y, a.y), min(lo.z, a.z)))
        hi = Vector((max(hi.x, b.x), max(hi.y, b.y), max(hi.z, b.z)))
    return lo, hi


def _others(obj):
    """every visible mesh in the scene but obj's and a skinned VRM's: what the body stands on and lands on"""
    import bpy
    from ...placement import _world as W
    mine = set(_meshes(obj))
    out = []
    for o in bpy.context.scene.objects:
        if o.type != 'MESH' or o in mine or not W.visible(o):
            continue
        if any(m.type == 'ARMATURE' for m in o.modifiers) or (o.parent is not None and o.parent.type == 'ARMATURE'):
            continue
        out.append(o)
    return out


def heading_of(dx, dy):
    """the heading (the controller's: 0 faces -Y) of a direction"""
    return math.atan2(dx, -dy)


def forward(th):
    return Vector((math.sin(th), -math.cos(th), 0.0))


def measure_obstacle(obj, from_xy, ground_z=None, heights=(0.12, 0.25, 0.4), ground=None):
    """an obstacle as seen from from_xy: horizontal rays from there toward its centre at a few heights over the ground
    find its near face (the nearest hit; its normal flattened, pointing back at the viewer), then a ray down just inside
    the face finds its top, a ray back out through it from far beyond finds its far face (its depth), and a ray down
    beyond that what lies past it (the landing). -> {'point', 'normal' (Vectors, the face's), 'heading' (that faces it
    square), 'distance' (from from_xy), 'top_z', 'rise' (over the ground at from_xy), 'depth', 'landing_z' (None: no
    ground within 2 m beyond)} or None when nothing is hit. ground: objects to read the ground from (default the floor
    under from_xy among every visible mesh but obj)"""
    rays = _rays(obj)
    lo, hi = _box(obj)
    c = (lo + hi) / 2
    others = _rays(ground if ground is not None else _others(obj))
    if ground_z is None:
        hit = others.cast((from_xy[0], from_xy[1], hi.z + 2.0), (0, 0, -1), 50.0)
        ground_z = hit[0].z if hit else 0.0
    best = None
    for hz in heights:
        o = Vector((from_xy[0], from_xy[1], ground_z + hz))
        d = Vector((c.x - o.x, c.y - o.y, 0.0))
        if d.length < 1e-6:
            return None
        hit = rays.cast(o, d.normalized(), 100.0)
        if hit and (best is None or hit[3] < best[3]):
            best = hit
    if best is None:
        return None
    p, n = best[0], Vector((best[1].x, best[1].y, 0.0))
    if n.length < 1e-6:
        return None
    n.normalize()
    th = heading_of(-n.x, -n.y)
    f = forward(th)
    top = rays.cast((p.x + f.x * 0.04, p.y + f.y * 0.04, hi.z + 1.0), (0, 0, -1), hi.z - lo.z + 2.0)
    top_z = top[0].z if top else hi.z
    far_o = Vector((p.x, p.y, ground_z + heights[0])) + f * 20.0
    far = rays.cast(far_o, -f, 20.0)
    depth = (far[0] - p).dot(f) if far else (hi - lo).length
    beyond = p + f * (depth + 0.4)
    lh = others.cast((beyond.x, beyond.y, top_z + 0.5), (0, 0, -1), top_z + 3.0)
    land = lh[0].z if lh else None
    return {'point': p.copy(), 'normal': n, 'heading': th, 'distance': (Vector((p.x - from_xy[0], p.y - from_xy[1]))
                                                                        ).length,
            'top_z': top_z, 'rise': top_z - ground_z, 'depth': depth, 'landing_z': land, 'ground_z': ground_z}


def _is_rung(o):
    """a thin horizontal bar: long in one horizontal axis, short (under 8 cm) in the other two"""
    from ...placement import _world as W
    a, b = W.box_of_object(o, W.depsgraph())
    s = sorted([b.x - a.x, b.y - a.y])
    return s[1] > 0.2 and s[0] < 0.08 and (b.z - a.z) < 0.08


def measure_ladder(objs, wall=None, ground_z=0.0):
    """a ladder's rungs measured from its geometry: the thin horizontal bars among objs (or all of objs when they are the
    rungs), sorted up -> {'rungs': [z...], 'first_rung' (over ground_z), 'rung_spacing' (the median step), 'line' (a
    Vector on the rungs' axis line at ground height), 'along' (the rungs' horizontal axis), 'normal' (from the wall out
    through the rungs: the climber faces -normal), 'heading', 'width', 'height' (the wall's top over ground_z, else the
    top rung's + one spacing), 'wall_gap' (the rungs' line to the wall's face)} for the controller's climb_ladder"""
    from ...placement import _world as W
    dg = W.depsgraph()
    obs = _meshes(objs)
    rungs = [o for o in obs if _is_rung(o)] or obs
    cs, axes, widths = [], [], []
    for o in rungs:
        a, b = W.box_of_object(o, dg)
        cs.append((a + b) / 2)
        ax = Vector((1.0, 0.0, 0.0)) if (b.x - a.x) >= (b.y - a.y) else Vector((0.0, 1.0, 0.0))
        co = W.world_verts(o, dg)
        if len(co) >= 2:                               # the bar's own long axis (a turned ladder's rungs are diagonal)
            xy = co[:, :2] - co[:, :2].mean(axis=0)
            _u, _s, vt = np.linalg.svd(xy, full_matrices=False)
            ax = Vector((float(vt[0, 0]), float(vt[0, 1]), 0.0)).normalized()
        axes.append(ax)
        widths.append(float(np.ptp(co[:, :2] @ np.array([ax.x, ax.y])) if len(co) else (b - a).length))
    order = np.argsort([c.z for c in cs])
    zs = [float(cs[i].z) for i in order]
    along = axes[int(order[0])]
    if along.dot(axes[int(order[-1])]) < 0:
        along = -along
    mid = sum(cs, Vector()) / len(cs)
    spacing = float(np.median(np.diff(zs))) if len(zs) > 1 else 0.28
    out = {'rungs': zs, 'first_rung': zs[0] - ground_z, 'rung_spacing': spacing, 'along': along,
           'line': Vector((mid.x, mid.y, ground_z)), 'width': float(np.median(widths))}
    # the wall behind the rungs: the side of the rungs' line the wall is on
    nrm = Vector((-along.y, along.x, 0.0))
    if wall is not None:
        wl, wh = _box(wall)
        wc = (wl + wh) / 2
        if (Vector((wc.x, wc.y, 0.0)) - Vector((mid.x, mid.y, 0.0))).dot(nrm) > 0:
            nrm = -nrm
        hit = _rays(wall).cast((mid.x, mid.y, ground_z + zs[0]), -nrm, 5.0)
        out['wall_gap'] = hit[3] if hit else None
        top = _rays(wall).cast((mid.x - nrm.x * ((hit[3] if hit else 0.1) + 0.05),
                                mid.y - nrm.y * ((hit[3] if hit else 0.1) + 0.05), wh.z + 1.0), (0, 0, -1), 50.0)
        out['height'] = (top[0].z if top else wh.z) - ground_z
    else:
        out['wall_gap'] = None
        out['height'] = zs[-1] + spacing - ground_z
    out['normal'] = nrm
    out['heading'] = heading_of(-nrm.x, -nrm.y)
    return out
