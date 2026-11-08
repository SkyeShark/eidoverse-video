"""eidoblend.fabrication.processes: G430 additive printing, pocket milling and 3-axis relief machining
(fabrication.js, MIT).

    from eidoblend.characters.robotics import make_robot
    from eidoblend import fabrication as fab
    printer = make_robot('fdm', location=(-.78, 0, 0), accent='#267c82', filament='#218675')
    job = fab.print(printer, source, size=.04, layer_height=.0004, bead_width=.0008, infill=.25, base=.00065,
                    feed=.025, duration=18, color='#278b79')
    job.seek(4)                 # seconds of playback (0 .. duration): pose the machine, the bead front, reel, tubes
    job.play()                  # key every frame of the scene's range (start=, speed=): the saved .blend plays alone
    job.set_color('#da642c')    # deposited bead, spool, live strand and guided cores

    cnc = make_robot('cnc')
    milling = fab.mill(cnc, None, material='aluminum', stock_width=.078, stock_depth=.128, stock_height=.020,
                       resolution=192, duration=18, effects={'max_particles': 1200, 'seed': 7319, 'dust': True})
    carving = fab.carve(make_robot('cnc_relief'), fab.sample_relief, material='wood', stepover=.0008,
                        sample_step=.001, resolution=192, duration=24)

Toolpaths are lists of {'position': (x, y, height), 'type': 'rapid' | 'cut' | 'extrude', 'feed': m/s (optional)} in
the machine's bed frame (Blender's axes, metres, height above the bed). Options are the WebGPU options in snake_case.

How the WebGPU GPU work lands in Blender, keyed:
  print  the deposited bead is one mesh of eight-sided bead sections, one per path chord, carrying the chord's ends,
         its section offset and its [start, end] path distance; a Geometry Nodes modifier moves each section's front
         end to the nozzle's progress and deletes sections not yet started (the WebGPU vertex shader and alpha test).
         The modifier's Progress input is keyed per frame from the job's feed clock.
  mill   the stock is a heightfield mesh (resolution x resolution top cells, a skirt to the bed and a floor); a Geometry
         Nodes modifier evaluates, per top vertex, the exact swept flat / ball envelope (cutter_nodes) of every cut
         sweep in its spatial bin up to the keyed Progress, as the TSL heightAt does. Ball-nose stock gets the
         WebGPU's filtered normals as custom normals.
  the machine's axes, lead screws, spindle rotor or fan, the reel and the PTFE feed are keyed object transforms and
  modifier inputs; chips are cutting.cutting_debris on the keyed physical time.
"""

from __future__ import annotations

import math

import numpy as np
from mathutils import Matrix

from . import _keys
from ._axes import Rec, color_linear, positive, t2b
from ._nodes import Builder, modifier_input, new_tree
from .cutter_nodes import cutter_height_node
from .cutter_sweep import index_cutter_sweeps, swept_cutter_height_np
from .cutting import cutting_debris, sample_removal, stock_material, stock_profile
from .feed_path import FeedPath
from .filament_path import FilamentPath
from .machine import g430, spin
from .mesh_slices import mesh_slicer
from .relief import relief_program
from .source_geometry import fit_source_geometry

TAU = math.pi * 2


# --------------------------------------------------------------------------------------------- the slicer ---

def _intersect_spans(a, b):
    out, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        lo, hi = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if hi - lo > 1e-10:
            out.append([lo, hi])
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def _subtract_spans(a, b):
    out = []
    for lo, hi in a:
        cursor = lo
        for x, z in b:
            if z <= cursor or x >= hi:
                continue
            if x - cursor > 1e-10:
                out.append([cursor, min(x, hi)])
            cursor = max(cursor, z)
            if cursor >= hi:
                break
        if hi - cursor > 1e-10:
            out.append([cursor, hi])
    return out


def _three_rings(polys):
    """A slice's polygons in three's (x, z) as polygon-clipping hands them to fabrication.js: outer rings
    counter-clockwise and holes clockwise in (x, z), each from its lowest-x (then lowest-z) point, the polygons in the
    order of those points and each polygon's holes after it in theirs. The perimeters then run, and the head travels,
    as in the WebGPU edition."""
    out = []
    for poly in polys:
        rs = []
        for k, r in enumerate(poly):
            pts = [(p[0], -p[1]) for p in r[:-1]]
            area = sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))
            if (area > 0) != (k == 0):
                pts.reverse()
            i0 = min(range(len(pts)), key=lambda i: pts[i])
            pts = pts[i0:] + pts[:i0]
            rs.append(pts + [pts[0]])
        out.append(rs)
    out.sort(key=lambda rs: rs[0][0])
    return [r for rs in out for r in [rs[0]] + sorted(rs[1:], key=lambda h: h[0])]


def slice_geometry(source, size=.04, layer_height=.0004, bead_width=.0008, base=.00065, infill=.25, solid_layers=3,
                   center=(0.0, 0.0), travel_lift=.0012, matrix=None, space='world', visible_only=True,
                   max_triangles=2000000, **_ignored):
    """Contours and alternating infill for an FDM print: {points, layers, contours [{layer, points}], layer_height,
    bead_width, base, source}. The source is fitted uniformly to `size`, centred on `center` (x, y) and stood on
    `base`; perimeters follow every closed contour (holes included), and infill alternates X / Y rows with `infill`
    of them sparse, solid for `solid_layers` layers above and below any change of cross-section."""
    for v, n in ((size, 'size'), (layer_height, 'layerHeight'), (bead_width, 'beadWidth'), (travel_lift, 'travelLift')):
        positive(v, n)
    if not (isinstance(infill, (int, float)) and math.isfinite(infill) and 0 <= infill <= 1):
        raise ValueError('Infill must be 0..1')
    if not (isinstance(solid_layers, int) and solid_layers >= 0):
        raise ValueError('solidLayers must be a nonnegative integer')
    g = fit_source_geometry(source, size=size, base=base, center=center, matrix=matrix, space=space,
                            visible_only=visible_only, max_triangles=max_triangles)
    slice_at = mesh_slicer(g, polygons=True)
    top = float(g.bounding_box[1][2])
    # the planner below reads like fabrication.js, in three's axes: rings in (x, z) with z = -y, heights along y
    lo_b, hi_b = g.bounding_box
    bb_min = (lo_b[0], lo_b[2], -hi_b[1])
    bb_max = (hi_b[0], hi_b[2], -lo_b[1])
    slices, heights = [], []
    y = base + layer_height / 2
    while y < top - 1e-10:
        heights.append(y)
        slices.append(_three_rings(slice_at(y)))
        y += layer_height
    points, contours = [], []
    cursor = [None]
    layers = 0

    def add(v, typ):
        c = cursor[0]
        if c is None or (c[0] - v[0]) ** 2 + (c[1] - v[1]) ** 2 + (c[2] - v[2]) ** 2 > 1e-16:
            points.append({'position': t2b(v), 'type': typ})
            cursor[0] = tuple(v)

    def travel(v):
        c = cursor[0]
        if c is not None:
            h = max(c[1], v[1]) + travel_lift
            add((c[0], h, c[2]), 'rapid')
            add((v[0], h, v[2]), 'rapid')
        add(v, 'rapid')

    def ring_segments(rings):
        return [((r[i][0], r[i][1]), (r[i + 1][0], r[i + 1][1])) for r in rings for i in range(len(r) - 1)]

    for index in range(len(slices)):
        y = heights[index]
        rings = slices[index]
        if not rings:
            continue
        loops = [[(x, y, z) for x, z in r] for r in rings]
        segs = ring_segments(rings)
        layers += 1
        for loop in loops:
            contours.append({'layer': layers, 'points': [t2b(v) for v in loop]})
            path = [(v[0], y + layer_height / 2, v[2]) for v in loop]
            travel(path[0])
            for v in path[1:]:
                add(v, 'extrude')
        continuing = []
        if solid_layers:
            for offset in range(-solid_layers, solid_layers + 1):
                k = index + offset
                continuing.append(ring_segments(slices[k]) if 0 <= k < len(slices) else [])
        if infill > 0 or solid_layers:
            along_x = layers % 2 == 0
            lo = bb_min[2] if along_x else bb_min[0]
            hi = bb_max[2] if along_x else bb_max[0]

            def intervals(segments, s, inset=0.0):
                hits = []
                for a, b in segments:
                    u = a[1] if along_x else a[0]
                    v = b[1] if along_x else b[0]
                    if (u <= s < v) or (v <= s < u):
                        pa = a[0] if along_x else a[1]
                        pb = b[0] if along_x else b[1]
                        hits.append(pa + (pb - pa) * (s - u) / (v - u))
                hits.sort()
                if len(hits) % 2:
                    raise ValueError('Odd infill intersections')
                spans = []
                for j in range(0, len(hits), 2):
                    if hits[j + 1] - hits[j] > max(1e-10, inset * 2):
                        spans.append([hits[j] + inset, hits[j + 1] - inset])
                return spans

            row = 0
            s = lo + bead_width
            while s < hi:
                full = intervals(segs, s, bead_width * .75)
                sparse_row = math.floor((row + 1) * infill + 1e-8) > math.floor(row * infill + 1e-8)
                spans = full
                if not sparse_row:
                    if not solid_layers:
                        spans = []
                    else:
                        core = full
                        for neighbour in continuing:
                            core = _intersect_spans(core, intervals(neighbour, s))
                            if not core:
                                break
                        spans = _subtract_spans(full, core)
                if row % 2:
                    spans = [sp[::-1] for sp in spans[::-1]]
                for a, b in spans:
                    v = (a, y + layer_height / 2, s) if along_x else (s, y + layer_height / 2, a)
                    w = (b, y + layer_height / 2, s) if along_x else (s, y + layer_height / 2, b)
                    travel(v)
                    add(w, 'extrude')
                s += bead_width
                row += 1
    if not layers:
        raise ValueError('Geometry is shorter than half a layer')
    if cursor[0] is not None:
        c = cursor[0]
        add((c[0], c[1] + travel_lift, c[2]), 'rapid')
    return {'points': points, 'layers': layers, 'contours': contours, 'layer_height': layer_height,
            'bead_width': bead_width, 'base': base, 'source': g.manufacturing_source}


def chords(path, max_length=.001):
    """Straight pieces of a FeedPath (arcs split by length and angle), each with its [start, end] path distance;
    a / b are (x, y, height) tuples in double precision."""
    from .feed_path import _add, _rotate, _sub
    pieces = []
    for s in path.segments:
        count = max(2, math.ceil(s.length / max_length), math.ceil(s.angle / .1)) if s.kind == 'arc' else 1
        a = tuple(s.a)
        for j in range(1, count + 1):
            f = j / count
            b = tuple(s.b) if s.kind == 'line' else _add(_rotate(_sub(s.a, s.center), s.normal, s.angle * f), s.center)
            pieces.append(Rec(a=a, b=b, start=s.distance0 + s.length * (j - 1) / count, end=s.distance0 + s.length * f,
                              type=s.type))
            a = b
    return pieces


def validate_machine(robot, points, kind, radius=0.0):
    m = getattr(robot, '_fabrication_g430', None) or g430(robot)
    if not m.tool or not callable(getattr(robot, 'move_tool', None)):
        raise ValueError('Fabrication needs the assembled G430 FDM or CNC machine')
    required = 'extruder_fixed' if kind == 'print' else 'spindle_fixed'
    if m.tool != required:
        raise ValueError('Wrong process head: expected ' + required)
    bb = m.bed_bounds
    for p in points:
        pos, typ = p['position'], p.get('type')
        q = m.to_axes(pos)
        for i, v in enumerate(q):
            lim = m.axis_limits[i]
            if not math.isfinite(v) or v < lim[0] - 1e-7 or v > lim[1] + 1e-7:
                raise ValueError(f"Toolpath exceeds G430 {'XYZ'[i]} travel at {tuple(pos)}")
        if typ != 'rapid' and (pos[0] - radius < bb[0] or pos[0] + radius > bb[1] or pos[1] - radius < bb[2]
                               or pos[1] + radius > bb[3]):
            raise ValueError('Process path exceeds the physical bed')
    return m


# ---------------------------------------------------------------------------------------------------- jobs ---

class Job:
    """A fabrication job: machine, path, mesh (the bead or stock object), duration (playback seconds),
    physical_duration, time, done, state; seek / play / stop / key / set_color / dispose."""

    def __init__(self, robot, path, mesh, options):
        self.machine = robot
        self.path = path
        self.mesh = mesh
        duration = options.get('duration') if options.get('duration') is not None else path.duration
        positive(duration, 'duration')
        self.duration = duration
        self.physical_duration = path.duration
        self.time = 0.0
        self.done = False
        self.state = None
        self.options = options
        self.effects = None
        self._on_done = options.get('on_done')
        self._callback_done = False
        self._keyed = []
        self._objects = set()

    # the WebGPU job.seek: pose everything for playback second `seconds`
    def seek(self, seconds):
        if not math.isfinite(seconds):
            raise ValueError('Job time must be finite')
        robot = self.machine
        t = min(max(seconds, 0.0), self.duration)
        state = self.path.sample(t / self.duration * self.path.duration)
        robot.move_tool(state.position)
        modifier_input(self.mesh.modifiers['fabrication'], 'Progress').value = float(state.distance)
        self.time = t
        self.done = t >= self.duration
        self.state = Rec(state, playback_time=t, physical_time=state.time)
        if 'filament_length' in state:
            fil = getattr(robot, 'filament', None)
            if fil is not None:
                fil.seek(state.filament_length, state.filament_retraction)
                fil.update()
            if callable(getattr(robot, 'cooling_fan', None)):
                robot.cooling_fan(state.time, rpm=self.options.get('fan_rpm', 4800))
        if self.effects is not None:
            self.effects.set_time(state.time)
        if 'spindle_rotor' in robot.roots:
            spin(robot, 'spindle_rotor', state.time * self.options.get('rpm', 1800) / 60 * TAU)
        if t < self.duration:
            self._callback_done = False
        if self.done and not self._callback_done:
            self._callback_done = True
            if callable(self._on_done):
                self._on_done(self)
        return self.state

    # ------------------------------------------------------------------------------------------- keying ---
    def _moving_objects(self):
        r = self.machine
        names = [n for n in r.roots if n.startswith('gantry_') and n != 'gantry_base']
        for n in ('spindle_rotor', 'filament_reel', 'extruder_fan'):
            if n in r.roots:
                names.append(n)
        names += [n for n in r.roots if n.split(' / ')[-1] == 'extruder_fan' and n not in names]
        return [r.roots[n] for n in names]

    def _slots(self):
        out = [modifier_input(self.mesh.modifiers['fabrication'], 'Progress')]
        if self.effects is not None:
            out += [modifier_input(p.modifier, 'Time') for p in self.effects.pools]
        fil = getattr(self.machine, 'filament', None)
        if fil is not None and 'filament_length' in (self.state or {}):
            for c in fil.curves:
                out += [modifier_input(c.modifier, n) for n in ('P0', 'P1', 'P2', 'P3', 'N0')]
        return out

    def key(self, frame_start=None, frame_end=None, fps=None, start=0.0, speed=1.0, scene=None):
        """Key every frame frame_start .. frame_end (the scene's range by default) at playback time
        (seconds since frame_start - start) * speed: the machine joints, reel and rotors as object keys, the
        progress, chip clock and feed-tube controls as modifier-input keys, all LINEAR."""
        import bpy
        scene = scene or bpy.context.scene
        f0 = scene.frame_start if frame_start is None else int(frame_start)
        f1 = scene.frame_end if frame_end is None else int(frame_end)
        fps = (scene.render.fps / scene.render.fps_base) if fps is None else fps
        frames = list(range(f0, f1 + 1))
        objs = self._moving_objects()
        for o in objs:
            o.rotation_mode = 'QUATERNION'
        loc = {o.name: [] for o in objs}
        rot = {o.name: [] for o in objs}
        slots = None
        vals = None
        for f in frames:
            self.seek(max(0.0, ((f - f0) / fps - start) * speed))
            if slots is None:
                slots = self._slots()
                vals = [[] for _ in slots]
            for o in objs:
                loc[o.name].append(tuple(o.location))
                rot[o.name].append(tuple(o.rotation_quaternion))
            for i, s in enumerate(slots):
                v = s.value
                vals[i].append(tuple(v) if hasattr(v, '__len__') else float(v))
        for o in objs:
            _keys.write(o, 'location', frames, loc[o.name])
            _keys.write(o, 'rotation_quaternion', frames, _keys.quaternions_continuous(rot[o.name]))
            self._keyed.append((o, ('location', 'rotation_quaternion')))
        for s, v in zip(slots, vals):
            _keys.write(s, 'value', frames, v)
            self._keyed.append((s.id_data, (s.path_from_id('value'),)))
        return self

    def play(self, start=0.0, speed=1.0, frame_start=None, frame_end=None, scene=None):
        """The WebGPU play(): here, key the scene's frames (playback time = (t - start) * speed)."""
        self.stop()
        return self.key(frame_start, frame_end, start=start, speed=speed, scene=scene)

    def stop(self):
        """Remove the keys play() / key() wrote; the current pose stays."""
        for idb, paths in self._keyed:
            _keys.clear(idb, paths)
        self._keyed = []
        return self

    def dispose(self):
        import bpy
        self.stop()
        mod = self.mesh.modifiers.get('fabrication')
        ng = mod.node_group if mod else None
        mats = list(self.mesh.data.materials)
        me = self.mesh.data
        bpy.data.objects.remove(self.mesh)
        bpy.data.meshes.remove(me)
        for m in mats:
            if m is not None and m.users == 0:
                bpy.data.materials.remove(m)
        if ng is not None and ng.users == 0:
            bpy.data.node_groups.remove(ng)
        for ob in getattr(self, '_data_objects', []):
            d = ob.data
            bpy.data.objects.remove(ob)
            bpy.data.meshes.remove(d)
        if self.effects is not None:
            self.effects.dispose()


def _place_on_bed(robot, ob, m):
    base = robot.roots['gantry_base']
    ob.parent = base
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.location = (0.0, 0.0, m.bed_top)


def _collection(robot):
    return robot.collection


# --------------------------------------------------------------------------------------------- the bead ---

def _bead_tree(name):
    tree, gi, go = new_tree(name, inputs=[('Geometry', 'NodeSocketGeometry'), ('Progress', 'NodeSocketFloat')],
                            outputs=[('Geometry', 'NodeSocketGeometry')])
    b = Builder(tree)
    p = b.s(gi.outputs['Progress'])
    start, end = b.named('fab_start'), b.named('fab_end_distance')
    f = b.clamp((p - start) / (end - start))
    pos = b.vmix(b.named('fab_a', 'FLOAT_VECTOR'), b.named('fab_b', 'FLOAT_VECTOR'), f * b.named('fab_end')) + \
        b.named('fab_offset', 'FLOAT_VECTOR')
    sp = b.node('GeometryNodeSetPosition')
    b.link(gi.outputs['Geometry'], sp.inputs['Geometry'])
    b.link(pos, sp.inputs['Position'])
    dl = b.node('GeometryNodeDeleteGeometry', domain='POINT')
    b.link(sp.outputs['Geometry'], dl.inputs['Geometry'])
    b.link(b.le(p - start, 1e-9), dl.inputs['Selection'])
    nm = b.node('GeometryNodeSetMeshNormal', mode='FREE', domain='POINT')
    b.link(dl.outputs['Geometry'], nm.inputs['Mesh'])
    b.link(b.named('fab_normal', 'FLOAT_VECTOR'), nm.inputs['Custom Normal'])
    b.link(nm.outputs['Mesh'], go.inputs['Geometry'])
    return tree


def _bead_mesh(name, pieces, bead_width, layer_height):
    import bpy
    n = len(pieces)
    A = np.array([tuple(s.a) for s in pieces], dtype=np.float64).reshape(-1, 3)
    B = np.array([tuple(s.b) for s in pieces], dtype=np.float64).reshape(-1, 3)
    S0 = np.array([s.start for s in pieces], dtype=np.float64)
    S1 = np.array([s.end for s in pieces], dtype=np.float64)
    d = B - A
    d /= np.linalg.norm(d, axis=1)[:, None]
    side = np.stack([d[:, 1], -d[:, 0], np.zeros(n)], axis=1)       # three's (-d.z, 0, d.x) in Blender's axes
    up = np.array([0.0, 0.0, 1.0])
    ang = np.arange(8) * math.pi / 4
    c, s = np.cos(ang), np.sin(ang)
    off = side[:, None, :] * (c[None, :, None] * bead_width / 2) + up[None, None, :] * \
        (s * layer_height / 2 - layer_height / 2)[None, :, None]                     # (n, 8, 3)
    nrm = side[:, None, :] * (c[None, :, None] / bead_width) + up[None, None, :] * (s / layer_height)[None, :, None]
    nrm /= np.linalg.norm(nrm, axis=2)[:, :, None]
    pos = np.concatenate([A[:, None, :] + off, B[:, None, :] + off], axis=1)           # (n, 16, 3)
    fab_a = np.repeat(A[:, None, :], 16, axis=1)
    fab_b = np.repeat(B[:, None, :], 16, axis=1)
    fab_off = np.concatenate([off, off], axis=1)
    fab_nrm = np.concatenate([nrm, nrm], axis=1)
    fab_end = np.concatenate([np.zeros((n, 8)), np.ones((n, 8))], axis=1)
    tri = []
    for j in range(8):
        k = (j + 1) % 8
        tri += [(j, k, 8 + k), (j, 8 + k, 8 + j)]
    for j in range(1, 7):
        tri += [(0, j + 1, j), (8, 8 + j, 8 + j + 1)]
    tri = np.array([(t[0], t[2], t[1]) for t in tri], dtype=np.int64)        # clockwise section: flip to face out
    faces = (np.arange(n)[:, None, None] * 16 + tri[None, :, :]).reshape(-1, 3)
    me = bpy.data.meshes.new(name)
    me.vertices.add(n * 16)
    me.vertices.foreach_set('co', pos.astype(np.float32).ravel())
    me.loops.add(len(faces) * 3)
    me.loops.foreach_set('vertex_index', faces.astype(np.int32).ravel())
    me.polygons.add(len(faces))
    me.polygons.foreach_set('loop_start', np.arange(0, len(faces) * 3, 3, dtype=np.int32))
    me.update(calc_edges=True)
    for nm, arr, kind in (('fab_a', fab_a, 'FLOAT_VECTOR'), ('fab_b', fab_b, 'FLOAT_VECTOR'),
                          ('fab_offset', fab_off, 'FLOAT_VECTOR'), ('fab_normal', fab_nrm, 'FLOAT_VECTOR'),
                          ('fab_start', np.repeat(S0, 16), 'FLOAT'), ('fab_end_distance', np.repeat(S1, 16), 'FLOAT'),
                          ('fab_end', fab_end, 'FLOAT')):
        at = me.attributes.new(nm, kind, 'POINT')
        at.data.foreach_set('vector' if kind == 'FLOAT_VECTOR' else 'value', np.asarray(arr, dtype=np.float32).ravel())
    me.polygons.foreach_set('use_smooth', np.ones(len(faces), dtype=bool))
    return me


def print(robot, source, **options):  # noqa: A001 - the WebGPU name
    """FDM print of a mesh source (or a slice_geometry spec) on the G430 FDM assembly; see the module notes."""
    import bpy
    o = dict(options)
    if o.get('fan_rpm') is not None and not (math.isfinite(o['fan_rpm']) and o['fan_rpm'] >= 0):
        raise ValueError('fanRpm must be finite and nonnegative')
    m = g430(robot)
    surface = robot.roots.get('fdm_build_plate')
    spec_given = isinstance(source, dict) and 'points' in source
    base = (source.get('base') if spec_given else None)
    if base is None:
        base = o.get('base', .00065)
    if o.get('build_plate', True) is not False:
        if surface is None:
            raise ValueError('The FDM assembly needs its authored build surface')
        if abs(base - .00065) > 1e-7 or (o.get('plate_width') is not None and abs(o['plate_width'] - .458) > 1e-7) \
                or (o.get('plate_depth') is not None and abs(o['plate_depth'] - .528) > 1e-7):
            raise ValueError('The removable PEI sheet is 458 x 528 x 0.65 mm on the original 450 x 520 mm bed; use '
                             'build_plate=False for a custom fixture')
    from .filament import ensure_filament
    fil = ensure_filament(robot)
    if fil is not None and o.get('filament_diameter') is not None and abs(o['filament_diameter'] - fil.diameter) > 1e-9:
        raise ValueError("filamentDiameter must match the loaded reel's 1.75 mm filament")
    spec = source if spec_given else slice_geometry(source, **o)
    layer_height = o.get('layer_height') or spec.get('layer_height') or .0004
    bead_width = o.get('bead_width') or spec.get('bead_width') or .0008
    validate_machine(robot, spec['points'], 'print', radius=bead_width / 2)
    if o.get('build_plate', True) is not False:
        for p in spec['points']:
            q = p['position']
            if p['type'] == 'extrude' and (abs(q[0]) + bead_width / 2 > .224 or q[1] + bead_width / 2 > .245
                                           or q[1] - bead_width / 2 < -.273):
                raise ValueError('Print exceeds the unobstructed area of the PEI sheet')
    geometric = FeedPath(spec['points'], feed=o.get('feed', .025), rapid=o.get('rapid', .10),
                         acceleration=o.get('acceleration', .5), bead_area=math.pi * bead_width * layer_height / 4,
                         blend_tolerance=o.get('blend_tolerance', .000015))
    path = FilamentPath(geometric, **{k: o[k] for k in ('filament_diameter', 'retract_length', 'retract_speed') if k in o})
    if fil is not None and path.filament_length > fil.capacity:
        raise ValueError('The reel has insufficient filament for this print')
    pieces = [s for s in chords(path, bead_width * .4) if s.type == 'extrude']
    for s in pieces:
        if abs(s.a[2] - s.b[2]) > 1e-6:
            raise ValueError('FDM extrusion must lie within a layer; use rapid for Z travel')
    me = _bead_mesh('FDM deposited bead', pieces, bead_width, layer_height)
    mat = bpy.data.materials.new('FDM deposited bead')
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Roughness'].default_value = .4
    bsdf.inputs['Metallic'].default_value = 0.0
    me.materials.append(mat)
    ob = bpy.data.objects.new('FDM deposited bead', me)
    _collection(robot).objects.link(ob)
    _place_on_bed(robot, ob, m)
    mod = ob.modifiers.new('fabrication', 'NODES')
    mod.node_group = _bead_tree('FDM deposited bead | progress')
    job = Job(robot, path, ob, o)
    job.kind = 'print'
    job.layers = spec['layers']
    job.extruded_volume = path.volume
    job.filament_length = path.filament_length
    job.spec = spec
    job.material = mat

    def set_color(color):
        bsdf.inputs['Base Color'].default_value = color_linear(color) + (1.0,)
        if fil is not None:
            fil.set_color(color)
        return job
    job.set_color = set_color
    unbind = fil.bind_material(mat) if fil is not None else None     # the bead takes the reel's colour ...
    if o.get('color') is not None or fil is None:
        set_color(o.get('color') or '#278b79')                         # ... unless a colour is given
    print_dispose = job.dispose

    def dispose_print():
        if unbind is not None:
            unbind()
        print_dispose()
    job.dispose = dispose_print
    job.base = spec.get('base', base)
    if surface is not None:
        _set_visible(surface, o.get('build_plate', True) is not False)
    if o.get('build_plate', True) is not False:
        job.plate = surface
    job.seek(0.0)
    if o.get('auto_play'):
        job.play(start=o.get('start', 0.0))
    return job


def _set_visible(root, visible):
    stack = [root]
    while stack:
        ob = stack.pop()
        ob.hide_render = ob.hide_viewport = not visible
        stack.extend(ob.children)


# --------------------------------------------------------------------------------------------- milling ---

def pocket_program(width=.048, depth=.080, stock_height=.020, cut_depth=.010, stepdown=.002, stepover=.0025,
                   radius=.003, clearance=.012, plunge=.001, **_ignored):
    """A raster pocket in layers of stepdown down to cut_depth: plunge at the corner, zig-zag rows stepover apart,
    retract to clearance above the stock between layers. Bed-frame points (Blender's axes)."""
    for i, v in enumerate((width, depth, stock_height, cut_depth, stepdown, stepover, radius, clearance, plunge)):
        positive(v, f'pocket parameter {i}')
    if width <= 2 * radius or depth <= 2 * radius or cut_depth >= stock_height:
        raise ValueError('Invalid pocket dimensions')
    pts = [[0.0, stock_height + clearance, 0.0, 'rapid', None]]          # three's [x, height, z]
    x0, x1 = -width / 2 + radius, width / 2 - radius
    z0, z1 = -depth / 2 + radius, depth / 2 - radius
    cut = min(stepdown, cut_depth)
    while True:
        y = stock_height - cut
        prev = pts[-1]
        pts += [[prev[0], stock_height + clearance, prev[2], 'rapid', None],
                [x0, stock_height + clearance, z0, 'rapid', None],
                [x0, y, z0, 'cut', plunge]]
        row = 0
        z = z0
        while True:
            a, b = (x1, x0) if row % 2 else (x0, x1)
            pts += [[a, y, z, 'cut', None], [b, y, z, 'cut', None]]
            row += 1
            if z >= z1 - 1e-9:
                break
            z = min(z + stepover, z1)
        if cut >= cut_depth - 1e-9:
            break
        cut = min(cut + stepdown, cut_depth)
    last = pts[-1]
    pts.append([last[0], stock_height + clearance, last[2], 'rapid', None])
    out = []
    for x, h, z, typ, feed in pts:
        p = {'position': (x, -z, h), 'type': typ}
        if feed is not None:
            p['feed'] = feed
        out.append(p)
    return out


def _stock_mesh(name, width, depth, height, resolution):
    import bpy
    R = resolution
    n = R + 1
    i, j = np.meshgrid(np.arange(n), np.arange(n))
    top = np.stack([(i / R - .5) * width, (j / R - .5) * depth, np.full(i.shape, height)], axis=-1).reshape(-1, 3)
    a = (np.arange(R)[:, None] * n + np.arange(R)[None, :]).ravel()
    tris = np.concatenate([np.stack([a, a + 1, a + n], axis=1), np.stack([a + 1, a + n + 1, a + n], axis=1)])
    border = list(range(n)) + [jj * n + R for jj in range(1, n)] + [R * n + ii for ii in range(R - 1, -1, -1)] + \
        [jj * n for jj in range(R - 1, 0, -1)]
    nb = len(border)
    bottom = np.arange(len(top), len(top) + nb)
    bot_pos = top[border].copy()
    bot_pos[:, 2] = 0.0
    border = np.array(border)
    side = []
    for k in range(nb):
        l = (k + 1) % nb
        side += [(border[k], bottom[k], bottom[l]), (border[k], bottom[l], border[l])]
    fan = [(bottom[0], bottom[k + 1], bottom[k]) for k in range(1, nb - 1)]
    faces = np.concatenate([tris, np.array(side), np.array(fan)])
    pos = np.concatenate([top, bot_pos])
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(pos))
    me.vertices.foreach_set('co', pos.astype(np.float32).ravel())
    me.loops.add(len(faces) * 3)
    me.loops.foreach_set('vertex_index', faces.astype(np.int32).ravel())
    me.polygons.add(len(faces))
    me.polygons.foreach_set('loop_start', np.arange(0, len(faces) * 3, 3, dtype=np.int32))
    me.update(calc_edges=True)
    at = me.attributes.new('fab_top', 'FLOAT', 'POINT')
    at.data.foreach_set('value', np.concatenate([np.ones(len(top)), np.zeros(nb)]).astype(np.float32))
    return me


def _data_object(name, count, attrs, collection, parent):
    """A hidden mesh of `count` points carrying the stock nodes' tables (the WebGPU's data textures)."""
    import bpy
    me = bpy.data.meshes.new(name)
    me.vertices.add(max(count, 1))
    for nm, (kind, arr) in attrs.items():
        at = me.attributes.new(nm, kind, 'POINT')
        a = np.asarray(arr, dtype=np.float32).ravel()
        if count == 0:
            a = np.zeros(3 if kind == 'FLOAT_VECTOR' else 1, dtype=np.float32)
        at.data.foreach_set('vector' if kind == 'FLOAT_VECTOR' else 'value', a)
    me.update()
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    ob.parent = parent
    ob.hide_render = ob.hide_viewport = True
    return ob


def _stock_tree(name, cuts_ob, bins_ob, index_ob, width, depth, height, resolution, radius, cutter, tiles,
                iterations):
    tree, gi, go = new_tree(name, inputs=[('Geometry', 'NodeSocketGeometry'), ('Progress', 'NodeSocketFloat')],
                            outputs=[('Geometry', 'NodeSocketGeometry')])
    b = Builder(tree)
    progress = b.s(gi.outputs['Progress'])
    cuts = b.object_geometry(cuts_ob)
    bins = b.object_geometry(bins_ob)
    indices = b.object_geometry(index_ob)
    x, y, _ = b.sep(b.position())
    bx = b.clamp(b.floor((x / width + .5) * tiles), 0.0, float(tiles - 1))
    by = b.clamp(b.floor((y / depth + .5) * tiles), 0.0, float(tiles - 1))
    bin_ = by * float(tiles) + bx
    store = []
    geo = gi.outputs['Geometry']
    for nm, val in (('cut_bin_start', b.sample_index(bins, b.named('bin_start'), bin_)),
                    ('cut_bin_count', b.sample_index(bins, b.named('bin_count'), bin_)), ('cut_h', float(height))):
        st = b.node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='POINT')
        b.link(geo, st.inputs['Geometry'])
        st.inputs['Name'].default_value = nm
        b.link(val, st.inputs['Value'])
        geo = st.outputs['Geometry']
        store.append(st)
    ri = b.node('GeometryNodeRepeatInput')
    ro = b.node('GeometryNodeRepeatOutput')
    ri.pair_with_output(ro)
    ri.inputs['Iterations'].default_value = int(iterations)
    b.link(geo, ri.inputs['Geometry'])
    it = b.s(ri.outputs['Iteration'])
    valid = b.lt(it, b.named('cut_bin_count'))
    seg = b.sample_index(indices, b.named('seg_index'), b.named('cut_bin_start') + it)
    a = b.sample_index(cuts, b.named('seg_a', 'FLOAT_VECTOR'), seg, 'FLOAT_VECTOR')
    e0 = b.sample_index(cuts, b.named('seg_b', 'FLOAT_VECTOR'), seg, 'FLOAT_VECTOR')
    s0 = b.sample_index(cuts, b.named('seg_start'), seg)
    s1 = b.sample_index(cuts, b.named('seg_end'), seg)
    active = valid & b.gt(progress, s0)
    f = b.clamp((progress - s0) / (s1 - s0))
    end = b.vmix(a, e0, f)
    env = b.node('GeometryNodeGroup')
    env.node_tree = cutter_height_node(radius, cutter)
    b.link(b.position(), env.inputs['XY'])
    b.link(a, env.inputs['A'])
    b.link(end, env.inputs['B'])
    h = b.named('cut_h')
    h_new = b.switch(active, h, b.min(h, b.s(env.outputs['Height'])))
    st = b.node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='POINT')
    b.link(ri.outputs['Geometry'], st.inputs['Geometry'])
    st.inputs['Name'].default_value = 'cut_h'
    b.link(b.gt(b.named('fab_top'), .5), st.inputs['Selection'])
    b.link(h_new, st.inputs['Value'])
    b.link(st.outputs['Geometry'], ro.inputs['Geometry'])
    sp = b.node('GeometryNodeSetPosition')
    b.link(ro.outputs['Geometry'], sp.inputs['Geometry'])
    px, py, _ = b.sep(b.position())
    b.link(b.vec(px, py, b.named('cut_h') * b.named('fab_top')), sp.inputs['Position'])
    out = sp.outputs['Geometry']
    if cutter == 'ball':
        # filter normals at the stock grid's sampling scale (two cells either side), as the WebGPU stock does: a
        # sub-grid scallop's instantaneous normal aliases into broad false stripes. Walls stay faceted.
        n = resolution + 1
        idx = b.index()
        jj = b.floor(idx / float(n))
        ii = idx - jj * float(n)
        il, ir = b.max(ii - 2.0, 0.0), b.min(ii + 2.0, float(resolution))
        jd, ju = b.max(jj - 2.0, 0.0), b.min(jj + 2.0, float(resolution))
        hz = b.sep(b.position())[2]

        def h_at(i_, j_):
            return b.sample_index(out, hz, j_ * float(n) + i_)
        cell_x, cell_y = width / resolution, depth / resolution
        sx = (h_at(il, jj) - h_at(ir, jj)) / b.max((ir - il) * cell_x, 1e-9)
        sy = (h_at(ii, jd) - h_at(ii, ju)) / b.max((ju - jd) * cell_y, 1e-9)
        curved = b.normalize(b.vec(sx, sy, 1.0))
        st2 = b.node('GeometryNodeStoreNamedAttribute', data_type='FLOAT_VECTOR', domain='POINT')
        b.link(out, st2.inputs['Geometry'])
        st2.inputs['Name'].default_value = 'cutter_surface_normal'
        b.link(curved, st2.inputs['Value'])
        on_face = b.node('GeometryNodeFieldOnDomain', data_type='FLOAT', domain='FACE')
        b.link(b.named('fab_top'), on_face.inputs[0])
        face_n = b.node('GeometryNodeFieldOnDomain', data_type='FLOAT_VECTOR', domain='FACE')
        b.link(b.node('GeometryNodeInputNormal').outputs[0], face_n.inputs[0])
        cn = b.named('cutter_surface_normal', 'FLOAT_VECTOR')
        use = b.gt(b.s(on_face.outputs[0]), .9999) & b.gt(b.dot(cn, b.vec(face_n.outputs[0])), .65)
        nrm = b.switch(use, b.vec(face_n.outputs[0]), cn, 'VECTOR')
        smn = b.node('GeometryNodeSetMeshNormal', mode='FREE', domain='CORNER')
        b.link(st2.outputs['Geometry'], smn.inputs['Mesh'])
        b.link(nrm, smn.inputs['Custom Normal'])
        out = smn.outputs['Mesh']
    b.link(out, go.inputs['Geometry'])
    return tree


def mill(robot, points=None, **options):
    """Pocket (points=None) or explicit-path milling on the G430 CNC; see the module notes."""
    import bpy
    m = g430(robot)
    fitted = m.cutter or Rec(kind='flat', radius=.003, flute_length=.018)
    cutter = options.get('cutter') or fitted.kind or 'flat'
    if cutter not in ('flat', 'ball'):
        raise ValueError('Cutter must be flat or ball')
    if cutter != (fitted.kind or 'flat'):
        raise ValueError('The requested cutter profile does not match the fitted tool; load the CNC relief assembly '
                         'for a ball nose')
    profile = stock_profile(options.get('material', 'aluminum'))
    o = dict(feed=profile.feed, plunge=profile.plunge, rpm=profile.rpm, stepdown=profile.stepdown,
             cut_depth=profile.cut_depth)
    o.update({k: v for k, v in options.items() if v is not None})
    positive(o['rpm'], 'spindle rpm')
    flutes = o.get('flutes', 2)
    if not (isinstance(flutes, int) and flutes >= 1):
        raise ValueError('flutes must be a positive integer')
    radius = o.get('radius', .003)
    width = o.get('stock_width', .078)
    depth = o.get('stock_depth', .128)
    height = o.get('stock_height', .020)
    resolution = o.get('resolution', 128)
    for i, v in enumerate((radius, width, depth, height)):
        positive(v, f'stock parameter {i}')
    if abs(radius - (fitted.radius or .003)) > 1e-8:
        raise ValueError('The installed G430 end mill has a 3 mm radius; cutter geometry and removal radius must match')
    fitted_flute = fitted.flute_length or .018
    flute = o.get('flute_length', fitted_flute)
    positive(flute, 'flute length')
    if flute > fitted_flute + 1e-8:
        raise ValueError('Flute length exceeds the exposed length of the fitted cutter')
    bed = m.bed_bounds
    if bed and (-width / 2 < bed[0] or width / 2 > bed[1] or -depth / 2 < bed[2] or depth / 2 > bed[3]):
        raise ValueError('Stock extends beyond the physical bed')
    clamps = [(n, r) for n, r in robot.roots.items() if n.startswith('cnc_clamp_')]
    if clamps:
        ok = abs(width - .078) < 1e-7 and .108 <= depth <= .148 and height >= .015
        if o.get('workholding', True) is not False and not ok:
            raise ValueError('The fitted toe clamps seat a 78 mm wide stock, 108..148 mm deep and at least 15 mm '
                             'high; use workholding=False with your own fixture')
    if not (isinstance(resolution, int) and 16 <= resolution <= 512):
        raise ValueError('Stock resolution must be 16..512')
    if points is None:
        points = pocket_program(**dict(o, stock_height=height, radius=radius))
    validate_machine(robot, points, 'mill', radius=radius)
    path = FeedPath(points, feed=o.get('feed', .012), rapid=o.get('rapid', .08), acceleration=o.get('acceleration', .25),
                    blend_tolerance=0)
    cuts = [s for s in chords(path) if s.type == 'cut']
    if not cuts:
        raise ValueError('Milling path has no cutting moves')
    for s in cuts:
        if min(s.a[2], s.b[2]) < 0:
            raise ValueError('Cutter would enter the machine bed')
    removal = sample_removal(path, width=width, depth=depth, height=height, radius=radius, resolution=resolution,
                             flute_length=flute, cutter=cutter)
    col = _collection(robot)
    me = _stock_mesh('CNC swept ball-nose relief stock' if cutter == 'ball' else 'CNC swept flat-end stock', width,
                     depth, height, resolution)
    mat, finish = stock_material(f'stock | {profile.id}', profile, o.get('color'))
    me.materials.append(mat)
    ob = bpy.data.objects.new(me.name, me)
    col.objects.link(ob)
    _place_on_bed(robot, ob, m)
    tiles = o.get('tiles', 24)
    binning = index_cutter_sweeps(cuts, width, depth, radius, tiles)
    hdr = binning['headers'].reshape(-1, 4)
    cuts_ob = _data_object('eidoverse/data/cutter-path', len(cuts), {
        'seg_a': ('FLOAT_VECTOR', [tuple(s.a) for s in cuts]), 'seg_b': ('FLOAT_VECTOR', [tuple(s.b) for s in cuts]),
        'seg_start': ('FLOAT', [s.start for s in cuts]), 'seg_end': ('FLOAT', [s.end for s in cuts])}, col, ob)
    bins_ob = _data_object('eidoverse/data/cutter-spatial-bins', tiles * tiles, {
        'bin_start': ('FLOAT', hdr[:, 0]), 'bin_count': ('FLOAT', hdr[:, 1])}, col, ob)
    index_ob = _data_object('eidoverse/data/cutter-spatial-indices', len(binning['indices']), {
        'seg_index': ('FLOAT', binning['indices'])}, col, ob)
    mod = ob.modifiers.new('fabrication', 'NODES')
    mod.node_group = _stock_tree(f'{me.name} | swept envelope', cuts_ob, bins_ob, index_ob, width, depth, height,
                                 resolution, radius, cutter, tiles, binning['maximum_bin'])
    if cutter != 'ball':
        me.polygons.foreach_set('use_smooth', np.zeros(len(me.polygons), dtype=bool))
    job = Job(robot, path, ob, o)
    job.kind = 'mill'
    job._data_objects = [cuts_ob, bins_ob, index_ob]
    job.stock = Rec(width=width, depth=depth, height=height, resolution=resolution,
                    cell_size=(width / resolution, depth / resolution), radius=radius, cutter=cutter,
                    material=profile.id, removed_volume=removal.removed_volume, removal_cell_size=removal.cell_size)
    job.cut_segments = cuts
    job.binning = binning
    job.workholding = [r for _, r in clamps]
    job._clamp_visibility = [not r.hide_render for r in job.workholding]
    for r in job.workholding:
        _set_visible(r, o.get('workholding', True) is not False)
    job.settings = Rec(material=profile.id, rpm=o['rpm'], feed=o['feed'], plunge=o['plunge'], stepdown=o['stepdown'],
                       cutter_diameter=radius * 2, cutter=cutter, flutes=flutes,
                       chip_load=o['feed'] * 60 / (o['rpm'] * flutes))

    def set_color(color):
        finish.set_color(color)
        return job
    job.set_color = set_color
    job.removal = removal
    job.finish = finish
    if o.get('effects', True) is not False:
        eff = o.get('effects') if isinstance(o.get('effects'), dict) else {}
        job.effects = cutting_debris(removal, profile, job.stock, collection=col, parent=robot.roots['gantry_base'],
                                     **{k: eff[k] for k in ('max_particles', 'seed', 'dust') if k in eff})
        job.effects.group.location = (0.0, 0.0, m.bed_top)
        job.effects.set_time(0.0)

    def inspect_heights(points_xy, progress=None):
        """The stock height at bed points (x, y) for the current (or given) progress: the same swept envelope the
        stock's nodes evaluate, on the CPU (the WebGPU job.inspectHeights compute pass)."""
        prog = job.state.distance if progress is None and job.state is not None else (progress or 0.0)
        pts = np.asarray(points_xy, dtype=np.float64).reshape(-1, 2)
        h = np.full(len(pts), height, dtype=np.float64)
        for s in cuts:
            if not prog > s.start:
                break
            f = min(max((prog - s.start) / (s.end - s.start), 0.0), 1.0)
            end = tuple(s.a[k] + (s.b[k] - s.a[k]) * f for k in range(3))
            h = np.minimum(h, swept_cutter_height_np(pts[:, 0], pts[:, 1], s.a, end, radius, cutter))
        return h.tolist()
    job.inspect_heights = inspect_heights
    dispose = job.dispose

    def dispose_mill():
        dispose()
        for r, vis in zip(job.workholding, job._clamp_visibility):
            _set_visible(r, vis)
    job.dispose = dispose_mill
    job.seek(0.0)
    if o.get('auto_play'):
        job.play(start=o.get('start', 0.0))
    return job


def carve(robot, source, **options):
    """3-axis relief carving: source is a height function f(x, y), a sampled heightfield, a mesh source (in stock
    coordinates), or an explicit toolpath / None (then this is mill). Wood by default, always the ball nose."""
    if source is None or isinstance(source, (list, tuple)):
        return mill(robot, source, **options)
    material = options.get('material', 'wood')
    profile = stock_profile(material)
    m = g430(robot)
    o = dict(feed=profile.feed, plunge=profile.plunge, stepdown=profile.stepdown,
             flute_length=(m.cutter.flute_length if m.cutter else None))
    o.update({k: v for k, v in options.items() if v is not None})
    o['material'] = material
    o['cutter'] = 'ball'
    program = relief_program(source, **o)
    job = mill(robot, program['points'], **o)
    job.program = program
    seek = job.seek

    def seek_stage(time):
        state = seek(time)
        state.stage = next((s['name'] for s in program['stages'] if state.distance <= s['end_distance']), 'retract')
        return state
    job.seek = seek_stage
    job.seek(0.0)
    return job
