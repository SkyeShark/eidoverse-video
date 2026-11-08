"""eidoblend.fabrication.filament: Bezier service tubing and physically metered filament delivery (filament.js, MIT).

    bezier_point(points, u), bezier_length(points, steps=128)        a cubic's point and arc length
    service_loop(start, end, length, up=(0, 0, 1))                    four control points of a loop of that length,
                                                                      handles raised along `up` (binary search)
    direct_feed_route(start, tip, start_direction)                    the FDM's exposed supply strand (two joined
                                                                      cubics) and its seated head entry
    tube = create_ptfe_tube(points=..., outer_diameter=.004, inner_diameter=.002, segments=72, radial_segments=8,
                            ends=(True, True), color='#e7eee5', opacity=.48 (1 for a solid core), name=...)
        a cubic Bezier tube: a Blender object whose Geometry Nodes modifier bends a fixed ring mesh along the curve
        (parallel-transport frames, 16 steps from the start normal, as the WebGPU vertex shader). tube.set_points(four
        local points) changes the modifier's inputs, never the mesh; tube.sample(u), tube.length, tube.points,
        tube.normal_at(u), tube.set_start_normal(n), tube.set_color(c), tube.dispose(). The bore shows only at the
        loose ends (short end throats), as in the original.
    install_filament(robot) / ensure_filament(robot)                  robot.filament for a G430 FDM or a dispenser:
        the live strand paying off the reel's winding, the carrier liner and guide, the short PTFE entries and cores
        at the head, the free supply span; seek(length, retraction) turns the reel by consumed volume and walks the
        payout point over the level-wound pack; update() re-routes the tubes after the head moves.

Points are Blender coordinates local to the tube's parent. The routing math runs in three's axes inside (it is the
original's, line for line) and converts at the edges.
"""

from __future__ import annotations

import math

import numpy as np

from ._axes import Rec, color_linear, matrix_b2t, t2b

K = .5522847498307936


def _v(p):
    return np.asarray(p, dtype=np.float64).reshape(3)


def bezier_point(points, u):
    v = 1 - u
    p = [_v(q) for q in points]
    return p[0] * (v * v * v) + p[1] * (3 * v * v * u) + p[2] * (3 * v * u * u) + p[3] * (u * u * u)


def _tangent(points, u):
    v = 1 - u
    p = [_v(q) for q in points]
    return (p[1] - p[0]) * (3 * v * v) + (p[2] - p[1]) * (6 * v * u) + (p[3] - p[2]) * (3 * u * u)


def bezier_length(points, steps=128):
    total = 0.0
    prev = _v(points[0])
    for i in range(1, steps + 1):
        p = bezier_point(points, i / steps)
        total += float(np.linalg.norm(p - prev))
        prev = p
    return total


def service_loop(start, end, length, up=(0.0, 0.0, 1.0)):
    a, b = _v(start), _v(end)
    n = _v(up) / np.linalg.norm(_v(up))
    if not (math.isfinite(length) and length > np.linalg.norm(a - b) * 1.005):
        raise ValueError('PTFE length is too short for these endpoints and seated tangents')
    lo, hi = 0.0, length * 2
    for _ in range(30):
        h = (lo + hi) / 2
        if bezier_length([a, a + n * h, b + n * h, b]) > length:
            hi = h
        else:
            lo = h
    h = (lo + hi) / 2
    return [tuple(a), tuple(a + n * h), tuple(b + n * h), tuple(b)]


def _straight(p, q):
    p, q = _v(p), _v(q)
    return [p, p + (q - p) / 3, p + (q - p) * 2 / 3, q]


def _direct_feed_route_t(start, tip, start_direction=(0.0, -1.0, 0.0)):
    """directFeedRoute in three's axes (y up)."""
    a, b = _v(start), _v(tip)
    sd = _v(start_direction)
    shoulder = b + np.array([0.0, .016, 0.0])
    unit = [np.array(p, dtype=np.float64) for p in ((0, 1, 1), (0, 1, 1 - K), (0, K, 0), (0, 0, 0))]
    radius = .080 / bezier_length(unit)
    heading = max(-.85, min(.85, math.atan2(a[0] - shoulder[0], a[2] - shoulder[2])))
    toward = np.array([math.sin(heading), 0.0, math.cos(heading)])
    entry = [shoulder + toward * (p[2] * radius) + np.array([0.0, p[1] * radius, 0.0]) for p in unit]
    drop = a[1] - entry[0][1]
    if drop <= .02:
        raise ValueError('Direct feed needs room above the seated inlet')
    span = float(np.linalg.norm(a - entry[0]))
    horizontal = math.hypot(a[0] - entry[0][0], a[2] - entry[0][2])
    lateral = max(span * .1, (entry[0][0] - a[0]) * .95 / sd[0]) if abs(sd[0]) > 1e-6 else span * .6
    departure = min(span * .6, lateral)
    arrival = min(span * .3, horizontal * .6)
    path = [a, a + sd * departure, entry[0] + toward * arrival, entry[0]]
    ab, bc, cd = (path[0] + path[1]) / 2, (path[1] + path[2]) / 2, (path[2] + path[3]) / 2
    left, right = (ab + bc) / 2, (bc + cd) / 2
    middle = (left + right) / 2
    return {'strands': [[path[0], ab, left, middle], [middle, right, cd, path[3]]],
            'entry': [entry, _straight(shoulder, b)]}


def _b2t3(p):
    p = _v(p)
    return np.array([p[0], p[2], -p[1]])


def _t2b3(p):
    p = _v(p)
    return np.array([p[0], -p[2], p[1]])


def direct_feed_route(start, tip, start_direction=(0.0, 0.0, -1.0)):
    """Blender axes in and out: {strands: [cubic, cubic], entry: [quarter-turn liner, straight insertion]}."""
    r = _direct_feed_route_t(_b2t3(start), _b2t3(tip), _b2t3(start_direction))
    conv = lambda c: [tuple(_t2b3(p)) for p in c]  # noqa: E731
    return {'strands': [conv(c) for c in r['strands']], 'entry': [conv(c) for c in r['entry']]}


# -------------------------------------------------------------------------------------------- the tube nodes ---

def _tube_group():
    import bpy
    from ._nodes import Builder, new_tree
    name = 'eido.ptfe_tube'
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    tree, gi, go = new_tree(name, inputs=[('Geometry', 'NodeSocketGeometry'), ('P0', 'NodeSocketVector'),
                                          ('P1', 'NodeSocketVector'), ('P2', 'NodeSocketVector'),
                                          ('P3', 'NodeSocketVector'), ('N0', 'NodeSocketVector')],
                            outputs=[('Geometry', 'NodeSocketGeometry')])
    b = Builder(tree)
    P = [b.vec(gi.outputs[f'P{i}']) for i in range(4)]
    u = b.named('tube_u')

    def curve(t):
        s = 1.0 - t
        return P[0] * (s * s * s) + P[1] * (s * s * t * 3.0) + P[2] * (s * t * t * 3.0) + P[3] * (t * t * t)

    def direction(t):
        s = 1.0 - t
        return b.normalize((P[1] - P[0]) * (s * s * 3.0) + (P[2] - P[1]) * (s * t * 6.0) + (P[3] - P[2]) * (t * t * 3.0))

    previous = direction(0.0)
    n = b.vec(gi.outputs['N0'])
    for i in range(1, 17):                                     # parallel transport: no twist at an inflection
        nxt = direction(u * (i / 16.0))
        axis = b.cross(previous, nxt)
        c = b.dot(previous, nxt)
        n = b.normalize(n + b.cross(axis, n) + b.cross(axis, b.cross(axis, n)) * (1.0 / b.max(c + 1.0, .00001)))
        previous = nxt
    binormal = b.normalize(b.cross(n, previous))
    rx, rz = b.named('tube_rx'), b.named('tube_rz')
    pos = curve(u) + n * rx + binormal * rz
    nl = b.named('tube_normal', 'FLOAT_VECTOR')
    lx, ly, lz = b.sep(nl)
    normal = b.normalize(n * lx + previous * ly + binormal * lz)
    sp = b.node('GeometryNodeSetPosition')
    b.link(gi.outputs['Geometry'], sp.inputs['Geometry'])
    b.link(pos, sp.inputs['Position'])
    nm = b.node('GeometryNodeSetMeshNormal', mode='FREE', domain='POINT')
    b.link(sp.outputs['Geometry'], nm.inputs['Mesh'])
    b.link(normal, nm.inputs['Custom Normal'])
    b.link(nm.outputs['Mesh'], go.inputs['Geometry'])
    return tree


def _tube_mesh(name, outer, inner, segments, radial, ends):
    import bpy
    pos_u, rx, rz, nrm, faces = [], [], [], [], []

    def ring(u, r, sign=1, axial=0):
        start = len(pos_u)
        for j in range(radial + 1):
            a = j / radial * math.pi * 2
            pos_u.append(u)
            rx.append(math.cos(a) * r)
            rz.append(math.sin(a) * r)
            nrm.append((0.0 if axial else math.cos(a) * sign, float(axial), 0.0 if axial else math.sin(a) * sign))
        return start

    def join(a, b, flip=False):
        for j in range(radial):
            q = [(a + j, b + j, a + j + 1), (a + j + 1, b + j, b + j + 1)]
            if flip:
                q = [(t[0], t[2], t[1]) for t in q]
            faces.extend(q)

    outer_rings = [ring(i / segments, outer / 2) for i in range(segments + 1)]
    for i in range(segments):
        join(outer_rings[i], outer_rings[i + 1])
    if inner > 0:
        for end in (0, 1):
            if not ends[end]:
                continue
            a = ring(end, inner / 2, -1)
            b = ring(.015 if end == 0 else .985, inner / 2, -1)
            join(a, b, end == 1)
            c = ring(end, outer / 2, 1, 1 if end else -1)
            d = ring(end, inner / 2, 1, 1 if end else -1)
            join(c, d, end == 0)
    me = bpy.data.meshes.new(name)
    n = len(pos_u)
    co = np.stack([np.asarray(rx), np.asarray(rz), np.asarray(pos_u)], axis=1).astype(np.float32)
    me.vertices.add(n)
    me.vertices.foreach_set('co', co.ravel())
    f = np.asarray(faces, dtype=np.int32)
    me.loops.add(len(f) * 3)
    me.loops.foreach_set('vertex_index', f.ravel())
    me.polygons.add(len(f))
    me.polygons.foreach_set('loop_start', np.arange(0, len(f) * 3, 3, dtype=np.int32))
    me.update(calc_edges=True)
    for nm_, arr, kind in (('tube_u', pos_u, 'FLOAT'), ('tube_rx', rx, 'FLOAT'), ('tube_rz', rz, 'FLOAT'),
                           ('tube_normal', nrm, 'FLOAT_VECTOR')):
        at = me.attributes.new(nm_, kind, 'POINT')
        at.data.foreach_set('vector' if kind == 'FLOAT_VECTOR' else 'value', np.asarray(arr, dtype=np.float32).ravel())
    me.polygons.foreach_set('use_smooth', np.ones(len(f), dtype=bool))
    return me


def _tube_material(name, color, opacity):
    import bpy
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = color_linear(color) + (1.0,)
    bsdf.inputs['Roughness'].default_value = .34
    bsdf.inputs['Metallic'].default_value = 0.0
    if opacity < 1:
        bsdf.inputs['Alpha'].default_value = float(opacity)
        m.surface_render_method = 'BLENDED'
        m.use_transparency_overlap = True
    return m


class PTFETube:
    """createPTFETube's api: mesh (the object), modifier, set_points, normal_at, set_start_normal, points, length,
    sample, set_color, dispose."""

    def __init__(self, points=((0, 0, 0), (0, 0, .6), (.4, 0, .6), (.4, 0, 0)), outer_diameter=.004,
                 inner_diameter=.002, segments=72, radial_segments=8, ends=(True, True), color='#e7eee5', opacity=None,
                 name='PTFE guide tube', collection=None, parent=None):
        import bpy
        if opacity is None:
            opacity = .48 if inner_diameter > 0 else 1.0
        if not (outer_diameter > 0 and inner_diameter >= 0 and inner_diameter < outer_diameter
                and all(math.isfinite(v) for v in (outer_diameter, inner_diameter))):
            raise ValueError('Invalid tube diameters')
        if not (isinstance(segments, int) and 1 <= segments <= 512 and isinstance(radial_segments, int)
                and 6 <= radial_segments <= 32):
            raise ValueError('Invalid tube tessellation')
        if not (math.isfinite(opacity) and 0 <= opacity <= 1):
            raise ValueError('Tube opacity must be 0..1')
        self.outer_diameter, self.inner_diameter = outer_diameter, inner_diameter
        self.segments = segments
        me = _tube_mesh(name, outer_diameter, inner_diameter, segments, radial_segments, tuple(ends))
        self.material = _tube_material(name, color, opacity)
        me.materials.append(self.material)
        ob = bpy.data.objects.new(name, me)
        (collection or bpy.context.scene.collection).objects.link(ob)
        if parent is not None:
            ob.parent = parent
        self.mesh = ob
        self.name = name
        self.modifier = ob.modifiers.new('tube', 'NODES')
        self.modifier.node_group = _tube_group()
        self._initial = np.array([1.0, 0.0, 0.0])
        self._path = None
        self.set_points(points)

    def _slot(self, name):
        from ._nodes import modifier_input
        return modifier_input(self.modifier, name)

    def set_points(self, value):
        if len(value) != 4:
            raise ValueError('A cubic Bezier tube needs four control points')
        nxt = [_v(p) for p in value]
        if any(not np.isfinite(p).all() for p in nxt) or np.sum((nxt[1] - nxt[0]) ** 2) < 1e-12 \
                or np.sum((nxt[3] - nxt[2]) ** 2) < 1e-12:
            raise ValueError('Degenerate Bezier endpoint tangent')
        t = _tangent(nxt, 0)
        t = t / np.linalg.norm(t)
        ref = np.array([1.0, 0.0, 0.0]) if abs(t[0]) < .8 else np.array([0.0, -1.0, 0.0])   # three's (1,0,0) / (0,0,1)
        n0 = ref - t * float(ref @ t)
        self._initial = n0 / np.linalg.norm(n0)
        self._path = nxt
        for i, p in enumerate(nxt):
            self._slot(f'P{i}').value = tuple(float(x) for x in p)
        self._slot('N0').value = tuple(float(x) for x in self._initial)
        return self

    def normal_at(self, u):
        prev = _tangent(self._path, 0)
        prev = prev / np.linalg.norm(prev)
        n = self._initial.copy()
        for i in range(1, 17):
            nxt = _tangent(self._path, u * i / 16)
            nxt = nxt / np.linalg.norm(nxt)
            axis = np.cross(prev, nxt)
            c = float(prev @ nxt)
            first = np.cross(axis, n)
            second = np.cross(axis, first)
            n = n + first + second * (1 / max(.00001, 1 + c))
            n = n / np.linalg.norm(n)
            prev = nxt
        return n

    def set_start_normal(self, value):
        t = _tangent(self._path, 0)
        t = t / np.linalg.norm(t)
        n = _v(value)
        n = n - t * float(n @ t)
        self._initial = n / np.linalg.norm(n)
        self._slot('N0').value = tuple(float(x) for x in self._initial)

    @property
    def points(self):
        return [p.copy() for p in self._path]

    @property
    def length(self):
        return bezier_length(self._path)

    def sample(self, u):
        return bezier_point(self._path, u)

    def set_color(self, c):
        bsdf = next(n for n in self.material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs['Base Color'].default_value = color_linear(c) + (1.0,)

    def dispose(self):
        """Remove the tube's object, mesh and (unused) material; a second call does nothing."""
        import bpy
        ob, mat = self.mesh, self.material
        self.mesh = self.material = None
        try:
            if ob is not None and ob.name in bpy.data.objects:
                me = ob.data
                bpy.data.objects.remove(ob)
                if me is not None and me.users == 0:
                    bpy.data.meshes.remove(me)
        except ReferenceError:                  # already removed with its robot
            pass
        try:
            if mat is not None and mat.users == 0:
                bpy.data.materials.remove(mat)
        except ReferenceError:
            pass


def create_ptfe_tube(**options):
    return PTFETube(**options)


# ----------------------------------------------------------------------------------------- the installation ---

def ensure_filament(robot):
    """robot.filament, installed on first use for a robot with a filament stand and reel (None otherwise)."""
    fil = getattr(robot, 'filament', None)
    if fil is not None:
        return fil
    if 'filament_stand' in robot.roots and 'filament_reel' in robot.roots:
        return install_filament(robot)
    return None


def _world_t(ob):
    from .machine import world_matrix
    return matrix_b2t(world_matrix(ob))


def _apply(m, p):
    p = _v(p)
    return m[:3, :3] @ p + m[:3, 3]


def _direction(m, d):
    v = m[:3, :3] @ _v(d)
    return v / np.linalg.norm(v)


class Filament:
    """robot.filament: color (the palette's live linear colour), diameter, capacity, consumed_length, retraction,
    rotation, remaining_radius, payout, curves / tubes / cores / supplies / supply / guide_tube / strand,
    tube_length, free_span_length; seek, update, set_color, bind_material, dispose."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def install_filament(robot, register_part=None):
    """index.js's installFilament(robot, registerPart): the robotics kit runs it at load through its INSTALLERS hook
    (registered when eidoblend.fabrication is imported); ensure_filament runs it on first use otherwise."""
    from mathutils import Matrix, Quaternion
    from .machine import rest_matrix
    stand, reel = robot.roots.get('filament_stand'), robot.roots.get('filament_reel')
    if stand is None or reel is None:
        return None
    col = robot.collection
    spec = robot.specs.get('filament_stand', {})
    local_out = spec.get('filament_out') or [.041, -.041, .320]
    out = np.array([local_out[0], local_out[2], -local_out[1]], dtype=np.float64)        # three, stand-local
    overhead = spec.get('feed_layout') == 'overhead_direct'
    radius = .0827
    gy, gz = -.041, .298 - .15
    d2 = gy * gy + gz * gz
    py = radius * radius / d2 * gy - radius * math.sqrt(d2 - radius * radius) / d2 * gz
    pz = radius * radius / d2 * gz + radius * math.sqrt(d2 - radius * radius) / d2 * gy
    end = [.041, .298, .041]
    point = [0.0, .15 + pz, -py]
    lead = [point, [.012, point[1] + .059, point[2] - .018], [.041, .273, .041], end]
    if overhead:
        y, z = -.006, .155
        d = y * y + z * z
        r = radius + .001
        qy = r * r / d * y + r * math.sqrt(d - r * r) / d * z
        qz = r * r / d * z - r * math.sqrt(d - r * r) / d * y
        point = [0.0, .280 + qy, qz]
        lead = [point, [.003, point[1] - qz / r * .060, point[2] + qy / r * .060], [.0415, .315, .155], [.0415, .284, .155]]
    lead = [np.array(p, dtype=np.float64) for p in lead]
    group = getattr(robot, 'palette', None) or robot.materials.palette
    palette = group.nodes['filament'].outputs[0]
    color_hex = [None]                                  # the kit's palette holds the loaded colour (linear)
    bindings = []
    curves = []

    def tube(name, parent, part=None, **kw):
        if kw.get('color') is None:
            kw.pop('color', None)
        t = PTFETube(name=name, collection=col, parent=parent, **kw)
        if register_part is not None:
            register_part(t.mesh, part or name, parent)
        curves.append(t)
        return t

    def tl(c):
        return [tuple(t2b(p)) for p in c]

    strand = tube('FP live filament strand', stand, outer_diameter=.00175, inner_diameter=0, segments=36,
                  color=color_hex[0], points=tl(lead))
    bindings.append(strand.material)
    guide = None
    if overhead:
        guide = tube('FP carrier PTFE liner', stand, segments=3, radial_segments=10,
                     points=tl(_straight(lead[3], [.0415, .250, .155])))
        bore = tube('FP filament through guide', stand, segments=3, radial_segments=6, outer_diameter=.00175,
                    inner_diameter=0, color=color_hex[0], points=tl(_straight(lead[3], out)))
        bindings.append(bore.material)
    inlet, base = robot.roots.get('extruder_fixed'), robot.roots.get('gantry_base')
    tubes, cores, supplies = [], [], []
    if inlet is not None and base is not None:
        for i in range(4):
            segs = [1, 12, 18, 1][i]
            tubes.append(tube(f'FP short PTFE entry {i}', base, 'FP short PTFE entries', segments=segs,
                              radial_segments=10, ends=(i in (0, 2), i in (1, 3))))
            c = tube(f'FP guided filament core {i}', base, 'FP guided filament core', segments=segs, radial_segments=6,
                     outer_diameter=.00175, inner_diameter=0, color=color_hex[0])
            c.mesh.visible_shadow = False
            cores.append(c)
            bindings.append(c.material)
        for i in range(2):
            s = tube(f'FP free supply filament {i}', base, 'FP free supply filament', segments=36, radial_segments=8,
                     outer_diameter=.00175, inner_diameter=0, color=color_hex[0])
            supplies.append(s)
            bindings.append(s.material)
    rest_loc, rest_rot, rest_scale = rest_matrix(robot, 'filament_reel').decompose()
    state = {'initial': None, 'last': ''}
    api = Filament(color=palette.default_value, diameter=.00175, tube_length=0.0, supply=supplies[0] if supplies else None,
                   supplies=supplies, consumed_length=0.0, retraction=0.0, curves=curves, tubes=tubes, cores=cores,
                   guide_tube=guide, capacity=math.pi * (.083 ** 2 - .033 ** 2) * .05075 * .9 / (math.pi * .00175 ** 2 / 4),
                   rotation=0.0, remaining_radius=.083, free_span_length=0.0, payout=None, strand=strand)

    def payout(rotation=0.0):
        sw, rw = _world_t(stand), _world_t(reel)
        rel = np.linalg.inv(sw) @ rw
        inverse = np.linalg.inv(rel)
        local = _apply(inverse, lead[0])
        if state['initial'] is None:
            state['initial'] = (math.atan2(-local[2], local[0]) % (2 * math.pi))
        theta = state['initial'] + rotation
        pitch = .00175
        raw = 10 + theta / (2 * math.pi)
        span = 28
        q = (raw - .5) % (2 * span)
        turns = .5 + (q if q <= span else 2 * span - q)
        sign = 1.0 if q <= span else -1.0
        edge = .25
        if turns < .5 + edge:
            dd = turns - .5
            turns = .5 + edge / 2 + dd * dd / (2 * edge)
            sign *= dd / edge
        if turns > 28.5 - edge:
            dd = 28.5 - turns
            turns = 28.5 - edge / 2 - dd * dd / (2 * edge)
            sign *= dd / edge
        axial = -.025375 + pitch * turns
        sector = 2 * math.pi / 64
        phase = (theta % sector) - sector / 2
        shell = .0833 * math.cos(math.pi / 64) / math.cos(phase)
        r = shell - .00010
        p = _apply(rel, [r * math.cos(theta), axial, -r * math.sin(theta)])
        direction = _direction(rel, [-r * math.sin(theta), sign * pitch / (2 * math.pi), -r * math.cos(theta)])
        e = lead[3]
        chord = float(np.linalg.norm(e - p))
        approach = 1.0 if overhead else -1.0
        if float(direction @ (e - p)) < 0:
            direction = -direction
        strand.set_points(tl([p, p + direction * chord * (.50 if overhead else .72),
                              e + np.array([0.0, approach * min(chord * .23, abs(p[1] - e[1]) * .5), 0.0]), e]))
        api.payout = Rec(angle=theta, row=turns, shell_radius=shell, embedded_depth=shell - r, point=tuple(t2b(p)),
                         tangent=tuple(t2b(direction)))

    def set_color(value):
        color_hex[0] = value
        lin = color_linear(value) + (1.0,)
        palette.default_value = lin
        for m in bindings:
            bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
            bsdf.inputs['Base Color'].default_value = lin
        api.color_hex = value
        return api

    def bind_material(m):
        bindings.append(m)
        bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs['Base Color'].default_value = tuple(palette.default_value)

        def unbind():
            if m in bindings:
                bindings.remove(m)
        return unbind

    def seek(length, retraction=0.0):
        if not (math.isfinite(length) and length >= 0 and math.isfinite(retraction) and retraction >= 0):
            raise ValueError('Invalid filament feed')
        area = math.pi * api.diameter ** 2 / 4
        outer, core, width, packing = .083, .033, .05075, .9
        r2 = outer * outer - length * area / (math.pi * width * packing)
        if r2 < core * core:
            raise ValueError('The reel has insufficient filament for this print')
        r = math.sqrt(r2)
        angle = 2 * math.pi * width * packing / area * (outer - r)
        # three's local +Y is the kit's local +Z
        reel.matrix_basis = Matrix.LocRotScale(rest_loc, rest_rot @ Quaternion((0.0, 0.0, 1.0), angle), rest_scale)
        api.consumed_length = length
        api.retraction = retraction
        api.rotation = angle
        api.remaining_radius = r
        payout(-angle)
        return api

    def update():
        if not tubes:
            return
        bw = _world_t(base)
        inverse = np.linalg.inv(bw)
        sw = _world_t(stand)
        a = _apply(inverse, _apply(sw, out))
        b = _apply(inverse, _apply(_world_t(inlet), [0.0, .115, 0.0]))
        key = ','.join(f'{v:.12g}' for v in (*a, *b))
        if key == state['last']:
            return
        state['last'] = key
        down = _direction(inverse, _direction(sw, [0.0, -1.0 if overhead else 1.0, 0.0]))
        direction = np.array([1.0, 0.0, 0.0])
        theta = 1.25
        end_tangent = down * math.cos(theta) + direction * math.sin(theta)
        h = 4 / 3 * math.tan(theta / 4)
        p = down * math.sin(theta) + direction * (1 - math.cos(theta))
        unit = [np.zeros(3), down * h, p - end_tangent * h, p]
        seat = a + down * .006
        rad = .038 / bezier_length(unit)
        guide_c = [u * rad + seat for u in unit]
        feed = _direct_feed_route_t(guide_c[3], b, end_tangent)
        route = [_straight(a, seat), guide_c] + feed['entry']
        for i, c in enumerate(supplies):
            c.set_points(tl(feed['strands'][i]))
        supplies[1].set_start_normal(supplies[0].normal_at(1))
        for i, t in enumerate(tubes):
            t.set_points(tl(route[i]))
            cores[i].set_points(tl(route[i]))
        chain = tubes[:2] + supplies + tubes[2:]
        for i in range(1, len(chain)):
            chain[i].set_start_normal(chain[i - 1].normal_at(1))
        for i, c in enumerate(cores):
            c.set_start_normal(tubes[i].normal_at(0))
        api.tube_length = sum(t.length for t in tubes) + (guide.length if guide is not None else 0.0)
        api.free_span_length = sum(c.length for c in supplies)

    def dispose():
        # the kit lists the registered tubes among the robot's extra objects and materials and removes what is left
        # after this (Robot.dispose): take them off those lists first, so no list holds a removed datablock
        def ptr(d):
            try:
                return d.as_pointer()
            except ReferenceError:
                return None
        mine = {ptr(c.mesh) for c in curves if c.mesh is not None}
        mats = {ptr(c.material) for c in curves if c.material is not None}
        extra = getattr(robot, 'extra_objects', None)
        if isinstance(extra, list):
            extra[:] = [o for o in extra if ptr(o) is not None and ptr(o) not in mine]
        kit_mats = getattr(getattr(robot, 'materials', None), 'materials', None)
        if isinstance(kit_mats, list):
            kit_mats[:] = [m for m in kit_mats if ptr(m) is not None and ptr(m) not in mats]
        for c in curves:
            c.dispose()
        bindings.clear()
        cbs = getattr(robot, 'pose_callbacks', None)
        if cbs is not None and update in cbs:
            cbs.remove(update)

    api.set_color, api.bind_material, api.seek, api.update, api.dispose = set_color, bind_material, seek, update, dispose
    api.color_hex = None
    api._payout = payout
    for m in bindings:                                  # the live strand and cores take the palette's filament colour
        bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs['Base Color'].default_value = tuple(palette.default_value)
    robot.filament = api
    callbacks = getattr(robot, 'pose_callbacks', None)  # joint changes re-route the feed, as robot.poseCallbacks
    if isinstance(callbacks, list):
        callbacks.append(update)
    elif callbacks is not None:
        callbacks.add(update)
    payout()
    update()
    return api


def kit_installer(robot, register_part):
    """The robotics kit's INSTALLERS entry: live filament for every loaded robot with a stand and a reel."""
    if 'filament_stand' in robot.roots and 'filament_reel' in robot.roots and getattr(robot, 'filament', None) is None:
        install_filament(robot, register_part)


def register_with_kit():
    """The robotics kit's two hooks for filament.js: its loader's INSTALLERS (the live filament at load, as index.js
    runs installFilament) and facade.FABRICATION (RoboticsKit.create_ptfe_tube / service_loop, which index.js
    re-exports from filament.js)."""
    try:
        from eidoblend.characters.robotics import facade, kit
    except ImportError:
        return False
    if not any(getattr(f, '__name__', '') == 'kit_installer' and getattr(f, '__module__', '') == __name__
               for f in kit.INSTALLERS):
        kit.INSTALLERS.append(kit_installer)
    hooks = getattr(facade, 'FABRICATION', None)
    if isinstance(hooks, dict):
        hooks['create_ptfe_tube'] = create_ptfe_tube
        hooks['service_loop'] = service_loop
    return True
