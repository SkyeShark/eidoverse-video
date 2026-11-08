"""eidoblend.fabrication.cutting: material-aware 2.5D stock sampling and deterministic cutting debris (cutting.js, MIT).

    STOCK_MATERIALS / stock_materials       aluminum, brass, steel, wood (hardwood), plywood: label, kind, colour,
                                            roughness, metalness, rpm, feed, plunge, stepdown, cut_depth, chip_size
    stock_profile(name)                     one of them by id or alias (metal -> aluminum, aluminium, hardwood -> wood)
    finish_stock(material, profile, color)  the stock's surface in the material's node tree: 3D growth rings, fibre
                                            and plywood plies for wood; fine brushing and patina for metals; the fine
                                            patterns fade with their screen footprint (no moire). -> {tint, set_color}
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
                                            set_color, dispose}
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

def _pixel_angle_driver(node, camera=None, scene=None):
    """The world size of one pixel per metre of view distance: 2 tan(fov / 2) / resolution_y, driven by the camera
    and the render size so a lens change or a resolution change keeps the fine-pattern filter right."""
    import bpy
    scene = scene or bpy.context.scene
    cam = camera or scene.camera
    out = node.outputs[0]
    out.default_value = 2 * math.tan(math.radians(36) / 2) / 1080
    if cam is None or cam.type != 'CAMERA':
        return
    fc = out.driver_add('default_value')
    d = fc.driver
    d.type = 'SCRIPTED'
    a = d.variables.new()
    a.name, a.type = 'fov', 'SINGLE_PROP'
    a.targets[0].id_type = 'CAMERA'
    a.targets[0].id = cam.data
    a.targets[0].data_path = 'angle_y'
    r = d.variables.new()
    r.name, r.type = 'res', 'SINGLE_PROP'
    r.targets[0].id_type = 'SCENE'
    r.targets[0].id = scene
    r.targets[0].data_path = 'render.resolution_y'
    d.expression = '2*tan(fov/2)/max(res,1)'


def finish_stock(material, profile, color=None, camera=None):
    """Build profile's finish into material (a Blender material with a Principled BSDF): the colour and roughness
    from object-space position, as finishStock does from the stock's local position. -> {tint, set_color}"""
    from ._nodes import Builder
    nt = material.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    b = Builder(nt, x0=-1800, y0=600)
    tc = b.node('ShaderNodeTexCoord')
    bx, by, bz = b.sep(tc.outputs['Object'])
    px, py, pz = bx, bz, -by                                  # three's (x, y, z) of the stock's local position
    cam = b.node('ShaderNodeCameraData')
    pix = b.node('ShaderNodeValue')
    pix.name = pix.label = 'pixel_angle'
    _pixel_angle_driver(pix, camera)
    footprint = b.s(cam.outputs['View Distance']) * b.s(pix.outputs[0]) * 1.4

    def fwidth(k):
        return footprint * k

    tint = b.node('ShaderNodeRGB')
    tint.name = tint.label = 'stock_tint'
    tint.outputs[0].default_value = color_linear(color or profile.color) + (1.0,)

    def mx_noise(scale_xyz):
        """MaterialX noise_float (signed, about -1..1) of p * scale, through Blender's Perlin noise."""
        n = b.node('ShaderNodeTexNoise', noise_dimensions='3D', normalize=True)
        n.inputs['Scale'].default_value = 1.0
        n.inputs['Detail'].default_value = 0.0
        n.inputs['Roughness'].default_value = 0.5
        n.inputs['Distortion'].default_value = 0.0
        v = b.vec(px * scale_xyz[0], py * scale_xyz[1], pz * scale_xyz[2])
        b.link(v, n.inputs['Vector'])
        return (b.s(n.outputs['Fac']) - 0.5) * 2.0

    if profile.kind == 'wood':
        broad = mx_noise((38, 27, 19))
        warp = b.sin(pz * 38) * .004 + broad * .002
        radial = b.sqrt(b.pow(px + .049 + warp, 2.0) + b.pow((py + .024) * 1.18, 2.0))
        phase = radial * 4200 + broad * 2.8
        rings = b.pow(b.sin(phase) * .5 + .5, 5.0) * (1.0 - b.clamp(fwidth(4200) * .28))
        fiber_phase = (px + warp) * 18000
        fiber = b.sin(fiber_phase) * b.sin(pz * 420) * .035 * (1.0 - b.clamp(fwidth(18000) * .3))
        grain = (b.sin(py * (math.pi / .0013)) * .065 + rings * .07) if profile.get('plies') else rings * .22
        k = .92 + broad * .16 - grain + fiber
        rough = .69 + rings * .12
    else:
        phase = pz * 83000 + b.sin(px * 270) * .7
        brushing = b.sin(phase) * .017 * (1.0 - b.clamp(fwidth(83000) * .25))
        n = b.node('ShaderNodeTexNoise', noise_dimensions='3D', normalize=True)
        n.inputs['Scale'].default_value = 1.0
        n.inputs['Detail'].default_value = 0.0
        b.link(b.vec(px * 95, py * 95, pz * 95), n.inputs['Vector'])
        patina = (b.s(n.outputs['Fac']) - .5) * 2.0 * .008
        k = .98 + brushing + patina
        rough = profile.roughness + brushing * 1.4 + patina
    col = b.vscale(tint.outputs[0], k)
    b.link(col, bsdf.inputs['Base Color'])
    b.link(rough, bsdf.inputs['Roughness'])
    bsdf.inputs['Metallic'].default_value = float(profile.metalness)

    def set_color(value):
        tint.outputs[0].default_value = color_linear(value) + (1.0,)
    return Rec(tint=tint, set_color=set_color)


def stock_material(name, profile, color=None, camera=None):
    import bpy
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Roughness'].default_value = float(profile.roughness)
    bsdf.inputs['Metallic'].default_value = float(profile.metalness)
    finish = finish_stock(m, profile, color, camera)
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


def _template(name, pts, tris, collection):
    import bpy
    from ._axes import t2b
    me = bpy.data.meshes.new(name)
    me.from_pydata([t2b(p) for p in pts], [], tris)
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
    size = (rnd(4) * .8 + .4) * (profile.chip_size * (.16 if dust else 1.0))
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
        tmpl = _template(f'{label} | template', DUST if is_dust else CHIP, DUST_TRIS if is_dust else CHIP_TRIS, col)
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
    from ._nodes import modifier_input

    def set_time(t):
        for p in pools:
            modifier_input(p.modifier, 'Time').value = float(t)

    def set_color(c):
        for p in pools:
            for m in p.template.data.materials:
                m.node_tree.nodes['chip_color'].outputs[0].default_value = color_linear(c) + (1.0,)

    def dispose():
        for p in pools:
            for m in list(p.template.data.materials):
                bpy.data.materials.remove(m)
            ng = p.modifier.node_group
            bpy.data.objects.remove(p.object)
            bpy.data.objects.remove(p.template)
            bpy.data.node_groups.remove(ng)
        bpy.data.objects.remove(events_ob)
        bpy.data.objects.remove(group)

    api = Rec(group=group, events_object=events_ob, pools=pools, emission_events=len(removal.events),
              particle_count=sum(p.count for p in pools), set_time=set_time, set_color=set_color, dispose=dispose,
              children=[Rec(name=p.name) for p in pools])
    set_time(-1.0)
    return api
