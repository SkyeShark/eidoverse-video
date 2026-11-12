"""eidoblend.fabrication.cutting: material-aware 2.5D stock sampling and deterministic cutting debris (cutting.js, MIT).

    STOCK_MATERIALS / stock_materials       aluminum, brass, steel, wood (hardwood), plywood: label, kind, colour,
                                            roughness, metalness, rpm, feed, plunge, stepdown, cut_depth, chip_size
    stock_profile(name)                     one of them by id or alias (metal -> aluminum, aluminium, hardwood -> wood)
    finish_stock(material, profile, color, axes='bed', scene=None)
                                            the stock's surface in the material's node tree: 3D growth rings, fibre
                                            and plywood plies for wood; fine brushing and patina for metals; the fine
                                            patterns fade by their exact screen footprint, fwidth(phase) (no moire),
                                            whichever camera renders; axes 'rotary' reads the rotary stock's point.
                                            -> {tint, set_color}
    stock_material(name, profile, color, axes='bed', scene=None)   a new material with that finish -> (material, finish)
    distance_time(segment, distance)        the inverse trapezoid: physical time at a distance along a FeedPath segment
    sample_removal(path, width, depth, height, radius, resolution, flute_length=.018, cutter='flat')
                                            the swept cutter against a heightfield of resolution x resolution cells
                                            (stock coordinates: x across width, y across depth, Blender's axes):
                                            {events [{time, position, volume, total_volume, distance, floor}],
                                            intervals [{start, end, engaged}], removed_volume, cell_size,
                                            final_heights (float32, row j along +y), nx, nz}. A rapid move through
                                            uncut stock and a cut below the flutes raise.
    cutting_debris(removal, profile, stock, max_particles=1200, seed=7319, dust=True, parent=None, collection=None)
                                            chips (metal swarf / wood shavings) and, for wood, fine dust, as a
                                            Geometry Nodes pool on the removal events: each chip's arc is a function
                                            of physical time, so a frame shows the same chips however it is reached.
                                            -> {group (the object), emission_events, particle_count, set_time(t),
                                            set_color, dispose, bounds (a hidden box of where chips can fly, which
                                            framing counts, as the WebGPU geometry bounds)}
"""

from __future__ import annotations

import math

import numpy as np

from ._axes import Rec, color_linear
from .cutter_sweep import swept_cutter_height_moves

_P = dict
STOCK_MATERIALS = {
    'aluminum': _P(label='Aluminum', kind='metal', color='#bec7cd', roughness=.29, metalness=1, rpm=16000, feed=.005,
                   plunge=.0008, stepdown=.001, cut_depth=.004, chip_size=.0012),
    'brass': _P(label='Brass', kind='metal', color='#ba9250', roughness=.3, metalness=1, rpm=12000, feed=.004,
                plunge=.0007, stepdown=.001, cut_depth=.004, chip_size=.0008),
    'steel': _P(label='Steel', kind='metal', color='#929ca6', roughness=.34, metalness=1, rpm=4800, feed=.0016,
                plunge=.00025, stepdown=.0005, cut_depth=.002, chip_size=.0007),
    'wood': _P(label='Hardwood', kind='wood', color='#bc884e', roughness=.73, metalness=0, rpm=18000, feed=.035,
               plunge=.006, stepdown=.003, cut_depth=.01, chip_size=.0021),
    'plywood': _P(label='Birch plywood', kind='wood', color='#d3b37e', roughness=.75, metalness=0, rpm=18000,
                  feed=.03, plunge=.005, stepdown=.003, cut_depth=.01, chip_size=.0018, plies=True),
}
stock_materials = STOCK_MATERIALS
_ALIASES = {'metal': 'aluminum', 'aluminium': 'aluminum', 'hardwood': 'wood'}


def stock_profile(name='aluminum'):
    pid = _ALIASES.get(name, name)
    if pid not in STOCK_MATERIALS:
        raise ValueError(f"Unknown stock material {name}; choose {', '.join(STOCK_MATERIALS)}")
    return Rec(dict(STOCK_MATERIALS[pid], id=pid))


# ------------------------------------------------------------------------------------------------ the surface ---

# The stock point finishStock reads, three's (x, y, z), from the stock surface's object coordinates o (Blender's axes):
# each row picks one axis of o, signed. 'bed': the 2.5D stock's local position, (ox, oz, -oy). 'rotary': the rotary
# stock's, which the WebGPU edition handed over as its (z, y, x) in three's axes, (-oy, oz, ox), so the long grain and
# the growth rings run along the rotary axis (a reflection: it lives in the material, not in the object's transform).
STOCK_AXES = {'bed': ((1, 0, 0), (0, 0, 1), (0, -1, 0)), 'rotary': ((0, -1, 0), (0, 0, 1), (1, 0, 0))}


def finish_stock(material, profile, color=None, axes='bed', scene=None):
    """Build profile's finish into material (a Blender material with a Principled BSDF): the colour and roughness
    from object-space position, as finishStock does from the stock's local position (`axes`: STOCK_AXES' 'bed' or
    'rotary', or three rows of a signed axis permutation). -> {tint, set_color}

    The fine patterns (growth rings, wood fibre, metal brushing) fade by fwidth(phase), as in the WebGPU edition: the
    phase's change from one pixel to the next. Blender's shader nodes have no screen derivatives, so it is computed
    exactly from the pattern's 3D gradient g (the broad noise's by finite differences) taken through the pixel's
    footprint on the surface, dP/dx = f (e_x - (e_x . N) / (I . N) I) for the screen axes e_x, e_y (N the normal, I
    the direction to the eye, f the metres one pixel spans across the view at the point: its depth times the
    camera's pixel pitch, measured in the shader by eidoblend.props.voice_machines.pixel_footprint, so it holds for
    whichever camera renders the frame, a cut, an animated lens, any sensor fit, an orthographic camera, and a stock
    made before its camera): fwidth = |g . dP/dx| + |g . dP/dy|. `scene` (the context scene by default) gives the
    render size the footprint reads. The nodes giving each pattern's phase and its fwidth are named
    'phase <pattern>' and 'fwidth <pattern>'."""
    import bpy
    from ..props.voice_machines import Nodes, pixel_footprint
    from ._nodes import V, Builder
    rows = STOCK_AXES[axes] if isinstance(axes, str) else tuple(tuple(r) for r in axes)
    nt = material.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    b = Builder(nt, x0=-1800, y0=600)
    tc = b.node('ShaderNodeTexCoord')
    o = b.sep(tc.outputs['Object'])
    point = o[0].v.node                                       # the stock point, labelled with the axes it is read by
    point.name = point.label = 'stock point ' + (axes if isinstance(axes, str) else 'axes ' + str(rows))

    def pick(row):
        j = next(i for i in range(3) if row[i])
        return o[j] if row[j] > 0 else -o[j]
    px, py, pz = (pick(r) for r in rows)                     # three's (x, y, z) of the stock's local position
    metres_per_pixel = b.s(pixel_footprint(Nodes(nt, x=-2400, y=600), scene or bpy.context.scene))
    metres_per_pixel.v.node.name = metres_per_pixel.v.node.label = 'pixel footprint'
    geo = b.node('ShaderNodeNewGeometry')
    normal, eye = V(b, geo.outputs['Normal']), V(b, geo.outputs['Incoming'])

    def screen_axis(v):
        n = b.node('ShaderNodeVectorTransform', vector_type='VECTOR', convert_from='CAMERA', convert_to='WORLD')
        n.inputs[0].default_value = v
        return V(b, n.outputs[0])
    ex, ey = screen_axis((1.0, 0.0, 0.0)), screen_axis((0.0, 1.0, 0.0))
    i_n = b.dot(eye, normal)
    inv_i_n = i_n / b.max(i_n * i_n, 1e-6)                    # 1 / (I . N), bounded at the silhouette
    rx, ry = b.dot(ex, normal) * inv_i_n, b.dot(ey, normal) * inv_i_n

    def name(sock, label):
        nd = sock.v.node
        nd.name = nd.label = label
        return sock

    def fwidth(g_three, pattern):
        """the exact fwidth of a phase whose gradient in three's axes is g_three"""
        g3 = b.sep(g_three)
        src = [next(i for i in range(3) if rows[i][j]) for j in range(3)]      # the gradient back to object space:
        g_object = b.vec(*[g3[i] if rows[i][j] > 0 else -g3[i] for j, i in enumerate(src)])   # the rows transposed
        tw = b.node('ShaderNodeVectorTransform', vector_type='VECTOR', convert_from='OBJECT', convert_to='WORLD')
        b.link(g_object, tw.inputs[0])
        g = V(b, tw.outputs[0])
        gi = b.dot(g, eye)
        return name((b.abs(b.dot(g, ex) - gi * rx) + b.abs(b.dot(g, ey) - gi * ry)) * metres_per_pixel,
                    'fwidth ' + pattern)

    tint = b.node('ShaderNodeRGB')
    tint.name = tint.label = 'stock_tint'
    tint.outputs[0].default_value = color_linear(color or profile.color) + (1.0,)

    def mx_noise(scale_xyz, d=(0.0, 0.0, 0.0)):
        """MaterialX noise_float of p * scale (at p + d): Blender's Noise Texture at Detail 0 is that same Perlin
        noise (OSL's: the lookup3 hash, the 12 gradients, the quintic fade, x 0.982), as 0.5 + 0.5 x it
        (test_finish_noise_materialx.py measures it)"""
        n = b.node('ShaderNodeTexNoise', noise_dimensions='3D', normalize=True)
        n.inputs['Scale'].default_value = 1.0
        n.inputs['Detail'].default_value = 0.0
        n.inputs['Roughness'].default_value = 0.5
        n.inputs['Distortion'].default_value = 0.0
        v = b.vec(*[(c + dc) * k if dc else c * k for c, k, dc in zip((px, py, pz), scale_xyz, d)])
        b.link(v, n.inputs['Vector'])
        return (b.s(n.outputs['Fac']) - 0.5) * 2.0

    if profile.kind == 'wood':
        broad = mx_noise((38, 27, 19))
        h = 5e-5
        gb = b.vec(*[(mx_noise((38, 27, 19), tuple(h if j == k else 0.0 for j in range(3))) - broad) * (1.0 / h)
                     for k in range(3)])
        warp = b.sin(pz * 38) * .004 + broad * .002
        u = px + .049 + warp
        w = (py + .024) * 1.18
        radial = b.sqrt(b.pow(u, 2.0) + b.pow(w, 2.0))
        phase = name(radial * 4200 + broad * 2.8, 'phase growth rings')
        gu = b.vec(1.0, 0.0, b.cos(pz * 38.0) * .152) + b.vscale(gb, .002)      # d(px + .049 + warp) / dp
        g_rings = b.vscale(b.vscale(gu, u) + b.vec(0.0, w * 1.18, 0.0), 4200.0 / b.max(radial, 1e-6)) + \
            b.vscale(gb, 2.8)
        rings = b.pow(b.sin(phase) * .5 + .5, 5.0) * (1.0 - b.clamp(fwidth(g_rings, 'growth rings') * .28))
        fiber_phase = name((px + warp) * 18000, 'phase wood fibre')
        fiber = b.sin(fiber_phase) * b.sin(pz * 420) * .035 * \
            (1.0 - b.clamp(fwidth(b.vscale(gu, 18000.0), 'wood fibre') * .3))
        grain = (b.sin(py * (math.pi / .0013)) * .065 + rings * .07) if profile.get('plies') else rings * .22
        k = .92 + broad * .16 - grain + fiber
        rough = .69 + rings * .12
    else:
        phase = name(pz * 83000 + b.sin(px * 270) * .7, 'phase metal brushing')
        g_brush = b.vec(b.cos(px * 270.0) * 189.0, 0.0, 83000.0)
        brushing = b.sin(phase) * .017 * (1.0 - b.clamp(fwidth(g_brush, 'metal brushing') * .25))
        patina = mx_noise((95, 95, 95)) * .008
        k = .98 + brushing + patina
        rough = profile.roughness + brushing * 1.4 + patina
    col = b.vscale(tint.outputs[0], k)
    b.link(col, bsdf.inputs['Base Color'])
    b.link(rough, bsdf.inputs['Roughness'])
    bsdf.inputs['Metallic'].default_value = float(profile.metalness)

    def set_color(value):
        tint.outputs[0].default_value = color_linear(value) + (1.0,)
    return Rec(tint=tint, set_color=set_color)


def stock_material(name, profile, color=None, axes='bed', scene=None):
    """A material with profile's finish (finish_stock), reading the stock point by `axes`. -> (material, finish)"""
    import bpy
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Roughness'].default_value = float(profile.roughness)
    bsdf.inputs['Metallic'].default_value = float(profile.metalness)
    finish = finish_stock(m, profile, color, axes, scene)
    return m, finish


# -------------------------------------------------------------------------------------------- removal events ---

def distance_time(segment, distance):
    """Inverse trapezoid timing: emission stays locked to the physical feed acceleration."""
    s = max(0.0, min(segment.length, distance))
    a = segment.acceleration
    if s <= segment.da:
        return segment.t0 + (math.sqrt(segment.v0 ** 2 + 2 * a * s) - segment.v0) / a
    cruise = segment.da + segment.peak * segment.tc
    if s < cruise:
        return segment.t0 + segment.ta + (s - segment.da) / segment.peak
    return segment.t1 - (math.sqrt(segment.v1 ** 2 + 2 * a * (segment.length - s)) - segment.v1) / a


def sample_removal(path, width, depth, height, radius, resolution, flute_length=.018, cutter='flat'):
    if not (isinstance(flute_length, (int, float)) and math.isfinite(flute_length) and flute_length > 0):
        raise ValueError('fluteLength must be positive')
    nx = nz = int(resolution)
    dx, dz = width / nx, depth / nz
    cell_area = dx * dz
    levels = np.full(nx * nz, height, dtype=np.float32)
    events, intervals = [], []
    removed = 0.0
    xs = (np.arange(nx) + .5) * dx - width / 2
    # rows run along +y; each cell centre is exactly the mirror of the WebGPU cell centre (three's z = -y), so
    # every envelope test, knife-edge cases included, comes out the same
    ys = -(((nz - 1 - np.arange(nz)) + .5) * dz - depth / 2)

    def at(x, y):
        if abs(x) >= width / 2 or abs(y) >= depth / 2:
            return 0.0
        i = max(0, min(nx - 1, math.floor((x + width / 2) / dx)))
        j = nz - 1 - max(0, min(nz - 1, math.floor((-y + depth / 2) / dz)))
        return float(levels[j * nx + i])

    for segment in path.segments:
        if segment.kind != 'line':
            raise ValueError('Stock removal expects straight cutter segments')
        steps = max(1, math.ceil(segment.length / min(radius / 3, dx * .65, dz * .65)))
        a = np.asarray(segment.a, dtype=np.float64)
        b = np.asarray(segment.b, dtype=np.float64)
        f = np.arange(steps + 1) / steps
        P = a[None, :] + (b - a)[None, :] * f[:, None]
        prev_f = np.maximum(0, (np.arange(steps + 1) - 1) / steps)
        Q = a[None, :] + (b - a)[None, :] * prev_f[:, None]
        engaged = False
        active = np.minimum(P[:, 2], Q[:, 2]) < height - 1e-7
        if active.any():
            ks = np.nonzero(active)[0]
            deep = (P[ks, 2] < height - flute_length) & (np.abs(P[ks, 0]) < width / 2 + radius) & \
                (np.abs(P[ks, 1]) < depth / 2 + radius)
            if deep.any():
                raise ValueError('Cut exceeds the visible cutter flute length; the shank would enter stock')
            lo_x = min(P[ks, 0].min(), Q[ks, 0].min()) - radius
            hi_x = max(P[ks, 0].max(), Q[ks, 0].max()) + radius
            lo_y = min(P[ks, 1].min(), Q[ks, 1].min()) - radius
            hi_y = max(P[ks, 1].max(), Q[ks, 1].max()) + radius
            x0 = max(0, math.floor((lo_x + width / 2) / dx))
            x1 = min(nx - 1, math.ceil((hi_x + width / 2) / dx))
            y0 = max(0, nz - 1 - math.ceil((-lo_y + depth / 2) / dz))
            y1 = min(nz - 1, nz - 1 - math.floor((-hi_y + depth / 2) / dz))
            if x0 <= x1 and y0 <= y1:
                gx, gy = np.meshgrid(xs[x0:x1 + 1], ys[y0:y1 + 1])
                cells = (np.arange(y0, y1 + 1)[:, None] * nx + np.arange(x0, x1 + 1)[None, :]).ravel()
                cx, cy = gx.ravel(), gy.ravel()
                # each step k sweeps Q[k] -> P[k]
                env = swept_cutter_height_moves(cx, cy, Q[ks], P[ks], radius, cutter)
                lv = levels[cells]
                for n_, k in enumerate(ks.tolist()):
                    e = env[n_]
                    delta = lv.astype(np.float64) - e
                    mask = delta > 2e-7
                    if not mask.any():
                        continue
                    if segment.type == 'rapid':
                        raise ValueError('Rapid move intersects uncut stock; retract above it before traversing')
                    volume = float(delta[mask].sum()) * cell_area
                    lv[mask] = e[mask]
                    levels[cells[mask]] = lv[mask]
                    if volume > 1e-13:
                        fk = k / steps
                        removed += volume
                        engaged = True
                        p = tuple(float(v) for v in P[k])
                        events.append(Rec(time=distance_time(segment, segment.length * fk), position=p, volume=volume,
                                          total_volume=removed, distance=segment.distance0 + segment.length * fk,
                                          floor=at(p[0], p[1])))
        intervals.append(Rec(start=segment.t0, end=segment.t1, engaged=engaged))
    return Rec(events=events, intervals=intervals, removed_volume=removed, cell_size=(dx, dz), final_heights=levels,
               nx=nx, nz=nz)


# ---------------------------------------------------------------------------------------------- the debris ---

CHIP = [(-.5, 0, -.4), (.5, 0, -.4), (-.5, .3, 0), (.5, .3, 0), (-.5, 0, .4), (.5, 0, .4)]   # three's axes
CHIP_TRIS = [(0, 2, 1), (1, 2, 3), (2, 4, 3), (3, 4, 5)]
DUST = [(-.5, 0, -.5), (.5, 0, -.5), (.5, 0, .5), (-.5, 0, .5)]
DUST_TRIS = [(0, 2, 1), (0, 3, 2)]


def _template(name, pts, tris, collection, size):
    """The chip (or dust flake) at its nominal size in metres: the pool scales each instance by its random factor
    only. (A unit-sized template would be a hidden 1 m mesh in the robot's hierarchy, and every framing box that
    counts hidden meshes, as three's expandByObject does, would grow by it.)"""
    import bpy
    from ._axes import t2b
    me = bpy.data.meshes.new(name)
    me.from_pydata([t2b(tuple(c * size for c in p)) for p in pts], [], tris)
    me.update()
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    ob.hide_render = ob.hide_viewport = True
    return ob


def _bounds_object(name, stock, collection):
    """cutting.js sets the chips' geometry bounds to where chips can fly (stock +- .22 m across, -.04 .. height + .09 m
    up) so that framing and placement tools count them: here a hidden mesh of that box's eight corners in the chips'
    frame, which world boxes count the same way."""
    import bpy
    w, d, h = stock['width'] / 2 + .22, stock['depth'] / 2 + .22, stock['height']
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x, y, z) for x in (-w, w) for y in (-d, d) for z in (-.04, h + .09)], [], [])
    me.update()
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    ob.hide_render = ob.hide_viewport = True
    return ob


def _chip_material(name, profile, dust):
    import bpy
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Roughness'].default_value = 1.0 if dust else float(profile.roughness)
    bsdf.inputs['Metallic'].default_value = float(profile.metalness)
    base = nt.nodes.new('ShaderNodeRGB')
    base.name = base.label = 'chip_color'
    base.outputs[0].default_value = color_linear(profile.color) + (1.0,)
    tint = nt.nodes.new('ShaderNodeAttribute')
    tint.attribute_type = 'INSTANCER'
    tint.attribute_name = 'chip_tint'
    mul = nt.nodes.new('ShaderNodeVectorMath')
    mul.operation = 'SCALE'
    nt.links.new(base.outputs[0], mul.inputs[0])
    nt.links.new(tint.outputs['Fac'], mul.inputs['Scale'])
    nt.links.new(mul.outputs[0], bsdf.inputs['Base Color'])
    if dust:
        alpha = nt.nodes.new('ShaderNodeAttribute')
        alpha.attribute_type = 'INSTANCER'
        alpha.attribute_name = 'chip_opacity'
        nt.links.new(alpha.outputs['Fac'], bsdf.inputs['Alpha'])
        m.surface_render_method = 'BLENDED'
        m.use_transparency_overlap = False
    m.use_backface_culling = False
    return m


def _events_object(name, removal, collection):
    import bpy
    ev = removal.events
    me = bpy.data.meshes.new(name)
    n = len(ev)
    me.vertices.add(n)
    if n:
        me.vertices.foreach_set('co', np.asarray([e.position for e in ev], dtype=np.float32).ravel())
        for attr, key in (('event_time', 'time'), ('event_volume', 'volume'), ('event_floor', 'floor')):
            a = me.attributes.new(attr, 'FLOAT', 'POINT')
            a.data.foreach_set('value', np.asarray([e[key] for e in ev], dtype=np.float32))
    me.update()
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    ob.hide_render = ob.hide_viewport = True
    return ob


def _debris_tree(name, events_ob, template, profile, stock, count, per_event, seed, dust):
    """The pool: point i of `count` shows event (cursor - floor(i / per_event)), chip k = i % per_event; its arc,
    spin, size and tint are functions of the event's identity and (time - event time), cutting.js's TSL as nodes."""
    from ._nodes import Builder, new_tree
    tree, gi, go = new_tree(name, inputs=[('Geometry', 'NodeSocketGeometry'), ('Time', 'NodeSocketFloat')],
                            outputs=[('Geometry', 'NodeSocketGeometry')])
    b = Builder(tree)
    time = b.s(gi.outputs['Time'])
    events = b.object_geometry(events_ob)
    # cursor: the index of the last event at or before time (events are in time order)
    stat = b.node('GeometryNodeAttributeStatistic', data_type='FLOAT', domain='POINT')
    b.link(events, stat.inputs['Geometry'])
    b.link(b.le(b.named('event_time'), time), stat.inputs['Selection'])
    b.link(1.0, stat.inputs['Attribute'])
    cursor = b.s(stat.outputs['Sum']) - 1.0
    pts = b.node('GeometryNodePoints')
    b.link(float(count), pts.inputs['Count'])
    i = b.index()
    idx = b.floor(i / float(per_event))
    k = i - idx * float(per_event)
    event = cursor - idx
    safe = b.max(event, 0.0)
    pos = b.sample_index(events, b.position(), safe, 'FLOAT_VECTOR')
    etime = b.sample_index(events, b.named('event_time'), safe)

    def rnd(j):
        return b.fract(b.sin(event * 12.9898 + k * 78.233 + float(j + seed)) * 43758.5453)

    theta = rnd(1) * (math.pi * 2)
    speed = rnd(2) * (.11 if dust else .65) + (.03 if dust else .25)
    vy = rnd(3) * (.13 if dust else .6) + (.12 if dust else .25)
    ct, st = b.cos(theta), b.sin(theta)
    velocity = b.vec(ct * speed, -(st * speed), vy)                       # three (cos, vy, sin) -> Blender
    origin = pos + b.vec(ct * (stock['radius'] * .55), -(st * (stock['radius'] * .55)), .0015)
    ttl = b.s(.16) if dust else b.min((vy + b.sqrt(vy * vy + 2 * 9.81 * .0015)) / 9.81, .22)
    age = time - etime
    a = b.clamp(age, 0.0, ttl)
    spin = theta + a * (5.0 if dust else 27.0)
    size = rnd(4) * .8 + .4                     # times the template's nominal chip_size (* .16 for dust)
    if dust:
        travel = (1.0 - b.exp(a * -14.0)) / 14.0
        drop = (a - travel) * (9.81 / 14)
    else:
        travel = a
        drop = a * a * (9.81 / 2)
    position = origin + velocity * travel - b.vec(0.0, 0.0, drop)
    alive = b.ge(event, 0.0) & b.ge(age, 0.0) & b.lt(age, ttl)
    setp = b.node('GeometryNodeSetPosition')
    b.link(pts.outputs['Points'], setp.inputs['Geometry'])
    b.link(position, setp.inputs['Position'])
    # per-chip tint and (dust) fading opacity on the points; instancing carries them to the instances, where the
    # material reads them through the instancer
    store = b.node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='POINT')
    b.link(setp.outputs['Geometry'], store.inputs['Geometry'])
    store.inputs['Name'].default_value = 'chip_tint'
    b.link(rnd(5) * .35 + .8, store.inputs['Value'])
    last = store.outputs['Geometry']
    op = b.node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='POINT')
    b.link(last, op.inputs['Geometry'])
    op.inputs['Name'].default_value = 'chip_opacity'
    b.link((1.0 - a / ttl) * .28 if dust else 1.0, op.inputs['Value'])
    last = op.outputs['Geometry']
    # the chip's persistent id (event x per_event + k): Blender's instancing takes a point attribute 'id' as the
    # instances' id, so a chip keeps its identity across motion-blur steps while the pool's points are renumbered as
    # chips are born and die
    pid = b.node('GeometryNodeStoreNamedAttribute', data_type='INT', domain='POINT')
    b.link(last, pid.inputs['Geometry'])
    pid.inputs['Name'].default_value = 'id'
    b.link(event * float(per_event) + k, pid.inputs['Value'])
    last = pid.outputs['Geometry']
    inst = b.node('GeometryNodeInstanceOnPoints')
    b.link(last, inst.inputs['Points'])
    b.link(alive, inst.inputs['Selection'])
    tobj = b.node('GeometryNodeObjectInfo', transform_space='ORIGINAL')
    tobj.inputs['Object'].default_value = template
    tobj.inputs['As Instance'].default_value = False
    b.link(tobj.outputs['Geometry'], inst.inputs['Instance'])
    rot = b.node('FunctionNodeEulerToRotation')
    b.link(b.vec(0.0, 0.0, -spin), rot.inputs[0])                       # turned = Rz(-spin) p (three's Ry(-spin))
    b.link(rot.outputs[0], inst.inputs['Rotation'])
    b.link(b.vec(size, size, size), inst.inputs['Scale'])
    b.link(inst.outputs['Instances'], go.inputs['Geometry'])
    return tree


def cutting_debris(removal, profile, stock, max_particles=1200, seed=7319, dust=True, parent=None, collection=None,
                   name='Material removal chips and dust'):
    import bpy
    if not (isinstance(max_particles, int) and 0 <= max_particles <= 50000):
        raise ValueError('maxParticles must be 0..50000')
    col = collection or bpy.context.scene.collection
    events_ob = _events_object(f'{name} | removal events', removal, col)
    group = bpy.data.objects.new(name, None)
    col.objects.link(group)
    if parent is not None:
        group.parent = parent
    events_ob.parent = group
    pools = []

    def make(is_dust):
        per = 8 if is_dust else 6
        count = min(max_particles, len(removal.events) * per)
        if not count:
            return
        label = 'Wood fines' if is_dust else ('Wood shavings' if profile.kind == 'wood' else 'Metal swarf')
        tmpl = _template(f'{label} | template', DUST if is_dust else CHIP, DUST_TRIS if is_dust else CHIP_TRIS, col,
                         profile.chip_size * (.16 if is_dust else 1.0))
        tmpl.parent = group
        tmpl.data.materials.append(_chip_material(f'{label} | {name}', profile, is_dust))
        me = bpy.data.meshes.new(label)
        ob = bpy.data.objects.new(label, me)
        col.objects.link(ob)
        ob.parent = group
        mod = ob.modifiers.new('debris', 'NODES')
        mod.node_group = _debris_tree(f'{label} | debris', events_ob, tmpl, profile, stock, count, per, seed, is_dust)
        pools.append(Rec(object=ob, modifier=mod, count=count, name=label, template=tmpl))

    make(False)
    if profile.kind == 'wood' and dust:
        make(True)
    bounds = None
    if pools:
        bounds = _bounds_object(f'{name} | trajectory bounds', stock, col)
        bounds.parent = group
    from ._nodes import modifier_input

    def set_time(t):
        for p in pools:
            modifier_input(p.modifier, 'Time').value = float(t)
            p.object.update_tag()                # (a Python-set modifier input does not tag its object in 5.2)

    def set_color(c):
        for p in pools:
            for m in p.template.data.materials:
                m.node_tree.nodes['chip_color'].outputs[0].default_value = color_linear(c) + (1.0,)

    def remove_object(ob):
        """The object and its mesh (when nothing else uses it); nothing when it is already gone (its robot's
        dispose may have taken it first)."""
        try:
            me = ob.data
            bpy.data.objects.remove(ob)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
        except ReferenceError:
            pass

    def dispose():
        for p in pools:
            try:
                mats = list(p.template.data.materials)
                ng = p.modifier.node_group
            except ReferenceError:
                mats, ng = [], None
            remove_object(p.object)
            remove_object(p.template)
            for m in mats:
                if m is not None and m.users == 0:
                    bpy.data.materials.remove(m)
            if ng is not None and ng.users == 0:
                bpy.data.node_groups.remove(ng)
        pools.clear()
        for ob in (bounds, events_ob, group):
            if ob is not None:
                remove_object(ob)

    api = Rec(group=group, events_object=events_ob, pools=pools, bounds=bounds, emission_events=len(removal.events),
              particle_count=sum(p.count for p in pools), set_time=set_time, set_color=set_color, dispose=dispose,
              children=[Rec(name=p.name) for p in pools])
    set_time(-1.0)
    return api
