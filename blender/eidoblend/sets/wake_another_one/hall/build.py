"""eidoblend.sets.wake_another_one.hall.build: the hall's layout, from layout.json. Blender.

    from eidoblend.sets.wake_another_one.hall.build import Layout
    lay = Layout(layout_dict, small=False).run()       # every part, rigged, in flat colours; lay.report says what it made

Called by hall.build(); the look (hall.look) turns the layout into the finished place afterwards. Every dimension is in
layout.json. What the layout makes (collections):
  hall_shell      the floor (the tracks' pits cut out), walls, roof, strip lights, the frosted office window
  racks           the rack rows' frames;  boxes_stock: the stock on them (closed cartons, instanced)
  line_module     ONE line's fixed parts: the roller track, the hood stack's base, the lectern, the crane runway, the
                  pendant's mast, the floor lines. Instanced at every line, the hero included; the trays, hoods,
                  dressing and moving crane parts are separate sets (under `assets`), so the hero line's can be real
                  driven objects
  lines           per line NN: line_NN (its root), line_NN_unit_K (K 0..9: a tray's frame), line_NN_lead (the station's
                  mark), the line's instancers
  line_hero       the hero line's own driven parts: its ten hoods, the two cartons that swap at unit_0, the stack's slots
  machinery       the hero crane (gantry_ctl: run), its pendant (press), the main track and its stream of cartons
                  (track_ctl: travel, swap), every other line's crane (crowd_ctl: crowd_run)
  meter_cabinet   the cabinet and its counter's drums (meter_cabinet_ctl: meter);  returns_cage;  dock;  cameras;
  layout_lights;  marks;  assets  (excluded from the view layer: what the instancers show)
THE MACHINES are driven by custom properties on their control empties, through simple-expression drivers (they evaluate
without Python): key the properties (hall.animate) and the machines move in the saved file, with no handler.
FRAMES: an empty line_NN_unit_K or line_NN_lead has local -Y as the way a body there faces and +X as its left; a unit's
empty IS the tray's frame (a body stands at the carton's body_mark in it).
"""

import math
import time

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from .... import common
from . import carton as CARTON

PI = math.pi
RAD = math.radians


# ======================================================================================================== helpers
def srgb(h):
    """'#rrggbb' -> linear rgb"""
    v = [int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in v)


class MB:
    """a mesh from boxes, cylinders and quads; mi = material slot"""

    def __init__(self):
        self.v, self.f, self.mi, self.sm = [], [], [], []

    def box(self, c, s, mi=0, rz=0.0, rx=0.0):
        hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
        pts = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
               (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
        if rz or rx:
            m = Matrix.Rotation(rz, 3, 'Z') @ Matrix.Rotation(rx, 3, 'X')
            pts = [tuple(m @ Vector(p)) for p in pts]
        n = len(self.v)
        self.v += [(p[0] + c[0], p[1] + c[1], p[2] + c[2]) for p in pts]
        for q in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self.f.append(tuple(n + i for i in q))
            self.mi.append(mi)
            self.sm.append(False)
        return self

    def span(self, lo, hi, mi=0):
        """a box from its two corners"""
        return self.box([(lo[i] + hi[i]) / 2 for i in range(3)], [abs(hi[i] - lo[i]) for i in range(3)], mi)

    def cyl(self, c, r, length, axis='x', n=14, mi=0, caps=True):
        n0 = len(self.v)
        for side in (-1, 1):
            d = side * length / 2
            for i in range(n):
                a, b = math.cos(2 * PI * i / n) * r, math.sin(2 * PI * i / n) * r
                p = (d, a, b) if axis == 'x' else (b, d, a) if axis == 'y' else (a, b, d)
                self.v.append((c[0] + p[0], c[1] + p[1], c[2] + p[2]))
        for i in range(n):
            j = (i + 1) % n
            self.f.append((n0 + i, n0 + j, n0 + n + j, n0 + n + i))
            self.mi.append(mi)
            self.sm.append(True)
        if caps:
            self.f.append(tuple(n0 + i for i in reversed(range(n))))
            self.f.append(tuple(n0 + n + i for i in range(n)))
            self.mi += [mi, mi]
            self.sm += [False, False]
        return self

    def quad(self, pts, mi=0):
        n = len(self.v)
        self.v += [tuple(p) for p in pts]
        self.f.append((n, n + 1, n + 2, n + 3))
        self.mi.append(mi)
        self.sm.append(False)
        return self

    def mesh(self, name, mats, recalc=True):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        for m in mats:
            me.materials.append(m)
        me.polygons.foreach_set('material_index', self.mi)
        me.polygons.foreach_set('use_smooth', self.sm)
        if recalc:
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            bm.to_mesh(me)
            bm.free()
        me.update()
        return me


def new_ob(name, data, collection, loc=(0, 0, 0), rz=0.0, parent=None):
    o = bpy.data.objects.new(name, data)
    collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (0, 0, rz)
    if parent is not None:
        o.parent = parent
    return o


def empty(name, loc, collection, rz=0.0, parent=None, kind='PLAIN_AXES', size=0.15):
    o = new_ob(name, None, collection, loc, rz, parent)
    o.empty_display_type, o.empty_display_size = kind, size
    return o


def inst(name, what, loc, collection, rz=0.0, parent=None):
    o = empty(name, loc, collection, rz, parent, size=0.1)
    o.instance_type = 'COLLECTION'
    o.instance_collection = what
    return o


def add_prop(ob, name, value, lo=None, hi=None, desc=''):
    ob[name] = value
    kw = {}
    if lo is not None:
        kw.update(min=lo, max=hi, soft_min=lo, soft_max=hi)
    if desc:
        kw['description'] = desc
    if kw:
        ob.id_properties_ui(name).update(**kw)
    ob.property_overridable_library_set(f'["{name}"]', True)


def num(x):
    s = f'{x:.6f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def drv(target, path, expr, variables, index=-1):
    """a SIMPLE-EXPRESSION driver (it evaluates with Python auto-run off, without Python); variables: [(name, object,
    data_path)]"""
    if len(expr) > 255:
        raise RuntimeError(f'driver expression too long ({len(expr)}): {expr}')
    fc = target.driver_add(path, index) if index >= 0 else target.driver_add(path)
    d = fc.driver
    d.type = 'SCRIPTED'
    for old in list(d.variables):
        d.variables.remove(old)
    for vn, vid, vpath in variables:
        v = d.variables.new()
        v.name, v.type = vn, 'SINGLE_PROP'
        v.targets[0].id = vid
        v.targets[0].data_path = vpath
    d.expression = expr
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)
    if not d.is_simple_expression:
        raise RuntimeError(f'not a simple expression: {expr}')
    return fc


def lookup(fc, pts):
    """keys on a driver's curve: the driver's value is looked up on them (linear between keys)"""
    for x, y in pts:
        k = fc.keyframe_points.insert(x, y)
        k.interpolation = 'LINEAR'
    return fc


def ramp(a, b, y0=0.0, y1=1.0, n=10):
    out = []
    for i in range(n + 1):
        t = i / n
        s = t * t * (3 - 2 * t)
        out.append((a + (b - a) * t, y0 + (y1 - y0) * s))
    return out


def tri_count(me):
    n = len(me.polygons)
    if not n:
        return 0
    a = np.empty(n, dtype=np.int32)
    me.polygons.foreach_get('loop_total', a)
    return int(a.sum()) - 2 * n


def track_mesh(mb, T, x0, x1, y0, y1, axis, gap=None):
    """a flush roller track in its pit: rollers across `axis`' travel, tops at z 0; curbs along the two long sides (gap: a
    (lo, hi) stretch of the low-coordinate side's curb left open). T: layout['line']['track']"""
    d, r = T['pit_depth'], T['roller_d'] / 2
    mb.quad([(x0, y0, -d), (x1, y0, -d), (x1, y1, -d), (x0, y1, -d)], 1)
    mb.quad([(x0, y0, 0), (x1, y0, 0), (x1, y0, -d), (x0, y0, -d)], 1)
    mb.quad([(x1, y0, 0), (x1, y1, 0), (x1, y1, -d), (x1, y0, -d)], 1)
    mb.quad([(x1, y1, 0), (x0, y1, 0), (x0, y1, -d), (x1, y1, -d)], 1)
    mb.quad([(x0, y1, 0), (x0, y0, 0), (x0, y0, -d), (x0, y1, -d)], 1)
    p = T['roller_pitch']
    cw, ch = T['curb_w'], T['curb_h']
    if axis == 'y':                                   # cartons travel along y: rollers lie along x
        k = math.floor((y0 + r) / p - 0.5) + 1
        while (k + 0.5) * p <= y1 - r - 0.004:
            mb.cyl(((x0 + x1) / 2, (k + 0.5) * p, -r), r, (x1 - x0) - 0.08, 'x', 10, 0)
            k += 1
        for xs, side in ((x0 - cw / 2, 0), (x1 + cw / 2, 1)):
            segs = [(y0, y1)]
            if gap and side == 0:
                segs = [(y0, gap[0]), (gap[1], y1)]
            for a, b in segs:
                if b - a > 0.01:
                    mb.span((xs - cw / 2, a, 0), (xs + cw / 2, b, ch), 0)
    else:                                             # cartons travel along x: rollers lie along y
        k = math.floor((x0 + r) / p - 0.5) + 1
        while (k + 0.5) * p <= x1 - r - 0.004:
            mb.cyl(((k + 0.5) * p, (y0 + y1) / 2, -r), r, (y1 - y0) - 0.08, 'y', 10, 0)
            k += 1
        for ys in (y0 - cw / 2, y1 + cw / 2):
            mb.span((x0, ys - cw / 2, 0), (x1, ys + cw / 2, ch), 0)


def floor_with_holes(name, x0, x1, y0, y1, holes, collection, material, z=0.0):
    """a floor of quads with rectangular holes (x0, x1, y0, y1) left out"""
    xs = sorted({x0, x1} | {h[0] for h in holes if x0 < h[0] < x1} | {h[1] for h in holes if x0 < h[1] < x1})
    ys = sorted({y0, y1} | {h[2] for h in holes if y0 < h[2] < y1} | {h[3] for h in holes if y0 < h[3] < y1})
    mb = MB()
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            if any(h[0] < cx < h[1] and h[2] < cy < h[3] for h in holes):
                continue
            mb.quad([(xs[i], ys[j], z), (xs[i + 1], ys[j], z), (xs[i + 1], ys[j + 1], z), (xs[i], ys[j + 1], z)])
    me = mb.mesh(name, [material], recalc=False)
    return new_ob(name, me, collection)


def look_at(name, collection, pos, aim, lens=50.0, up=(0, 0, 1), ortho=None):
    """a camera at pos aimed at aim (its frame's top toward `up`), focused on aim"""
    cd = bpy.data.cameras.new(name)
    cd.sensor_width = 36.0
    cd.clip_start, cd.clip_end = 0.1, 800.0
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    else:
        cd.lens = lens
    o = new_ob(name, cd, collection, pos)
    f = (Vector(aim) - Vector(pos)).normalized()
    z = -f
    x = Vector(up).cross(z)
    if x.length < 1e-6:
        x = Vector((1, 0, 0))
    x.normalize()
    y = z.cross(x)
    o.rotation_euler = Matrix((x, y, z)).transposed().to_euler()
    cd.dof.focus_distance = (Vector(aim) - Vector(pos)).length
    return o


# ======================================================================================================== the layout
class Layout:
    """the hall's layout in the current scene. L: layout.json as a dict; small: two rows of two lanes and a short hall
    (layout['hall']['small']); log: print-like. run() -> self; then .C (collections by name), .M (materials by name),
    .controls (the control empties by name), .cams, .report"""

    def __init__(self, L, small=False, scene=None, log=print):
        self.L, self.small, self.log = L, bool(small), log
        self.SC = scene or bpy.context.scene
        self.T0 = time.time()
        self.report = {'small': self.small, 'steps': []}
        self.C, self.M, self.controls, self.cams = {}, {}, {}, {}
        H = L['hall']
        sm = H.get('small', {})
        self.ROWS = sm.get('rows', 2) if small else H['rows']
        self.LANES = H['lanes_x'][:sm.get('lanes', 2)] if small else H['lanes_x']
        self.HX0, self.HX1 = H['x']
        self.HY0, self.HY1 = (sm.get('y0', -45.0) if small else H['y'][0]), H['y'][1]
        self.LN = L['line']
        self.PITCH = self.LN['pitch']
        self.YAW = RAD(self.LN['tray_yaw'])
        self.G = L['gantry']
        self.ST = self.LN['stack']

    def say(self, *a):
        self.log('[hall %6.1f s] ' % (time.time() - self.T0) + ' '.join(str(x) for x in a))

    def step(self, what):
        self.say(what)
        self.report['steps'].append([round(time.time() - self.T0, 1), what])

    def run(self):
        self.collections()
        self.materials()
        self.step('1. the carton')
        self.carton()
        self.step('2. the line module')
        self.module()
        self.step('3. the controls and the other lines\' moving copies')
        self.control_empties()
        self.step('4. the shell: floor, walls, roof, lights, the office window')
        self.lines_plan()
        self.shell()
        self.step('5. racks and stock')
        self.racks()
        self.step('6. the lines: %d of them' % len(self.LINES))
        self.lines()
        self.step('7. the hero line: its hoods, the two cartons at unit_0, its crane')
        self.hero()
        self.step('8. the main track, its stream, the spurs')
        self.main_track()
        self.step('9. the meter cabinet and its drums')
        self.meter()
        self.step('10. the returns cage and its cartons')
        self.cage()
        self.step('11. the dock door and the apron')
        self.dock()
        self.step('12. the cameras')
        self.cameras()
        self.step('13. the layout\'s light and world')
        self.light()
        self.step('14. counting')
        self.count()
        return self

    # ------------------------------------------------------------------------------------------------ collections
    def coll(self, name, parent=None):
        c = bpy.data.collections.new(name)
        (parent or self.SC.collection).children.link(c)
        self.C[name] = c
        return c

    def collections(self):
        root = bpy.data.collections.new('hall')
        self.SC.collection.children.link(root)
        self.C['hall'] = root
        for n in ('hall_shell', 'racks', 'boxes_stock', 'line_module', 'lines', 'line_hero', 'machinery', 'meter_cabinet',
                  'returns_cage', 'dock', 'cameras', 'layout_lights', 'marks', 'assets'):
            self.coll(n, root)

    def mat(self, name, rgb, rough=0.5, metal=0.0, emit=None, strength=0.0):
        if name in self.M:
            return self.M[name]
        m = bpy.data.materials.new(name)
        if not m.node_tree:
            m.use_nodes = True
        b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        b.inputs['Base Color'].default_value = (*rgb, 1.0)
        b.inputs['Roughness'].default_value = rough
        b.inputs['Metallic'].default_value = metal
        if emit is not None:
            b.inputs['Emission Color'].default_value = (*emit, 1.0)
            b.inputs['Emission Strength'].default_value = strength
        m.diffuse_color = (*rgb, 1.0)
        m.roughness, m.metallic = rough, metal
        self.M[name] = m
        return m

    def materials(self):
        """flat colours for the layout, under the names the look rebuilds in place"""
        mat = self.mat
        mat('hall_concrete', (0.42, 0.43, 0.43), 0.62)
        mat('hall_wall_panel', (0.70, 0.72, 0.73), 0.6)
        mat('hall_roof', (0.55, 0.57, 0.59), 0.7)
        mat('steel_galv', (0.55, 0.57, 0.58), 0.38, 0.85)
        mat('steel_dark', (0.06, 0.065, 0.07), 0.5, 0.6)
        mat('machine_white', srgb('#d9e0df'), 0.42)
        mat('machine_teal', srgb('#398b91'), 0.42)
        mat('rubber_black', (0.02, 0.02, 0.02), 0.8)
        mat('rack_upright', (0.62, 0.65, 0.67), 0.45, 0.3)
        mat('rack_beam', (0.36, 0.40, 0.43), 0.45, 0.3)
        mat('floor_line_paint', (0.78, 0.80, 0.80), 0.55)
        mat('strip_light_glow', (0.9, 0.93, 1.0), 0.4, 0.0, (0.82, 0.90, 1.0), 6.0)
        mat('office_frosted_glow', (0.9, 0.86, 0.78), 0.6, 0.0, (1.0, 0.86, 0.66), 4.0)
        mat('paper_placeholder', (0.80, 0.78, 0.72), 0.7)
        mat('glass_placeholder', (0.25, 0.30, 0.33), 0.05)
        mat('cabinet_grey', (0.33, 0.36, 0.37), 0.5, 0.4)
        mat('drum_white', (0.82, 0.82, 0.80), 0.5)
        mat('drum_ink', (0.015, 0.015, 0.015), 0.6)
        mat('dock_apron', (0.50, 0.48, 0.45), 0.7)
        mat('carton_board', (0.80, 0.78, 0.72), 0.65)
        mat('carton_insert', (0.52, 0.48, 0.41), 0.85)

    # ------------------------------------------------------------------------------------------------ 1. the carton
    def carton(self):
        CT = CARTON.build(self.L['carton'], self.M['carton_board'], self.M['carton_insert'], self.C['assets'])
        self.CT = CT
        meas = CT['meas']
        self.report['carton'] = meas
        self.SEAM, self.HOOD_H = meas['seam_z'], meas['hood_height']
        self.RING_TO_ORIGIN = self.G['ring_to_hood_bottom'] + self.SEAM    # the ring over a hood set's origin (the tray's floor)
        self.Z_TOP = self.G['ring_top']
        self.Z_TRAY = self.RING_TO_ORIGIN                                   # the ring's height gripping a hood on a tray
        self.N_SLOTS = self.ST['cols'] * self.ST['levels']

    def slot_xyz(self, j):
        """the origin of a hood set standing in the stack's slot j (its hood's foot is SEAM above it)"""
        ST = self.ST
        return (ST['x'], ST['y0'] - ST['col_pitch'] * (j // ST['levels']),
                ST['base_h'] + self.HOOD_H * (j % ST['levels']) - self.SEAM)

    # ------------------------------------------------------------------------------------------------ 2. the line module
    def module(self):
        L, LN, G, ST, M = self.L, self.LN, self.G, self.ST, self.M
        CM = self.C['line_module']
        T = LN['track']
        hw = T['half_width']
        mb = MB()
        track_mesh(mb, T, -hw, hw, T['y0'], T['y1'], 'y', gap=(-hw, hw))
        new_ob('line_track', mb.mesh('line_track', [M['steel_galv'], M['steel_dark']]), CM)
        # the hood stack's base: a low steel deck beside the head of the line
        mb = MB()
        ya = ST['y0'] + ST['col_pitch'] / 2
        yb = ST['y0'] - ST['col_pitch'] * (ST['cols'] - 0.5)
        mb.span((ST['x'] - 0.475, yb, 0), (ST['x'] + 0.475, ya, ST['base_h']))
        for c in range(ST['cols'] + 1):                       # low locating ribs between the columns
            y = ya - ST['col_pitch'] * c
            mb.span((ST['x'] - 0.475, y - 0.012, ST['base_h']), (ST['x'] + 0.475, y + 0.012, ST['base_h'] + 0.02))
        new_ob('line_hood_stack_base', mb.mesh('line_hood_stack_base', [M['steel_galv']]), CM)
        # the lectern: a foot plate, a column, a shelf; its sloped top is a separate object (it carries things)
        LE = LN['lectern']
        lx, ly = LE['x'], LE['y']
        mb = MB()
        mb.span((lx - 0.24, ly - 0.20, 0), (lx + 0.24, ly + 0.20, 0.012))
        mb.span((lx - 0.04, ly - 0.04, 0.012), (lx + 0.04, ly + 0.04, LE['top_h'] - 0.06))
        mb.span((lx - 0.26, ly - 0.15, 0.54), (lx + 0.26, ly + 0.15, 0.552))
        mb.span((lx - 0.26, ly + 0.138, 0.552), (lx + 0.26, ly + 0.15, 0.60))
        new_ob('line_lectern', mb.mesh('line_lectern', [M['steel_galv']]), CM)
        mb = MB()
        w, d = LE['top_w'], LE['top_d']
        mb.span((-w / 2, -d / 2, -0.012), (w / 2, d / 2, 0))
        mb.span((-w / 2, -d / 2, 0), (w / 2, -d / 2 + 0.012, 0.022))               # the lip at the reader's edge
        mb.span((-w / 2, d / 2 - 0.05, 0), (w / 2, d / 2 - 0.045, 0.010))          # the pencil groove's rail
        top = new_ob('line_lectern_top', mb.mesh('line_lectern_top', [M['steel_galv']]), CM, (lx, ly, LE['top_h']))
        top.rotation_euler = (RAD(LE['tilt']), 0, 0)                               # low toward -Y, where the station stands
        # the crane's runway: posts, rails, end ties, drop tubes from the roof
        mb = MB()
        zt = G['rail_top']
        for rx, posts in zip(G['rail_x'], (G['post_y_west'], G['post_y_east'])):
            mb.span((rx - 0.07, G['rail_y'][0], zt - 0.26), (rx + 0.07, G['rail_y'][1], zt))
            mb.span((rx - 0.035, G['rail_y'][0], zt), (rx + 0.035, G['rail_y'][1], zt + 0.03), 1)      # the wheels' rail
            for py in posts:
                mb.span((rx - 0.07, py - 0.07, 0), (rx + 0.07, py + 0.07, zt - 0.26))
                mb.span((rx - 0.16, py - 0.16, 0), (rx + 0.16, py + 0.16, 0.016))
            hwt = G['hang_w'] / 2
            for py in G['hang_y']:
                mb.span((rx - hwt, py - hwt, zt), (rx + hwt, py + hwt, L['hall']['roof_z']))
                mb.span((rx - 0.12, py - 0.12, zt), (rx + 0.12, py + 0.12, zt + 0.02))
                mb.span((rx - 0.14, py - 0.14, L['hall']['roof_z'] - 0.02), (rx + 0.14, py + 0.14, L['hall']['roof_z']))
        for ty in G['rail_y']:
            mb.span((G['rail_x'][0], ty - 0.06, zt - 0.22), (G['rail_x'][1], ty + 0.06, zt - 0.04))
        new_ob('line_crane_runway', mb.mesh('line_crane_runway', [M['machine_white'], M['steel_galv']]), CM)
        # the pendant's mast: a slim post behind the lectern with an arm; the control hangs from the arm's end
        P = G['pendant']
        mb = MB()
        mb.cyl((P['mast_x'], P['y'], (P['hang_z'] + 0.05) / 2), 0.03, P['hang_z'] + 0.05, 'z', 12, 0)
        mb.cyl((P['mast_x'], P['y'], 0.008), 0.11, 0.016, 'z', 16, 0)
        mb.span((P['mast_x'], P['y'] - 0.02, P['hang_z']), (P['x'] + 0.03, P['y'] + 0.02, P['hang_z'] + 0.04), 0)
        new_ob('line_pendant_mast', mb.mesh('line_pendant_mast', [M['machine_white']]), CM)
        # floor lines
        mb = MB()
        MK = LN['marks']
        for x in (MK['x_a'], MK['x_b'], G['rail_x'][0] - 0.25):
            mb.quad([(x - MK['line_w'] / 2, G['rail_y'][0], 0.002), (x + MK['line_w'] / 2, G['rail_y'][0], 0.002),
                     (x + MK['line_w'] / 2, G['rail_y'][1], 0.002), (x - MK['line_w'] / 2, G['rail_y'][1], 0.002)])
        sx, sy = lx, ly - LE['stand_back']
        for a, b in (((sx - 0.35, sy - 0.30), (sx + 0.35, sy - 0.26)), ((sx - 0.35, sy + 0.26), (sx + 0.35, sy + 0.30)),
                     ((sx - 0.35, sy - 0.30), (sx - 0.31, sy + 0.30)), ((sx + 0.31, sy - 0.30), (sx + 0.35, sy + 0.30))):
            mb.quad([(a[0], a[1], 0.002), (b[0], a[1], 0.002), (b[0], b[1], 0.002), (a[0], b[1], 0.002)])
        new_ob('line_floor_lines', mb.mesh('line_floor_lines', [M['floor_line_paint']], recalc=False), CM)
        # what stands on a line, as instanced sets
        A = self.C['assets']
        self.C_TRAYS = self.coll('line_trays', A)          # units 0..9's trays
        self.C_TRAYS_HERO = self.coll('line_trays_hero', A)  # units 1..9's (unit_0's swap on the hero line)
        for K in range(LN['units']):
            inst('tray_%d' % K, self.CT['tray'], (0, K * self.PITCH, 0), self.C_TRAYS, self.YAW)
            if K >= 1:
                inst('tray_hero_%d' % K, self.CT['tray'], (0, K * self.PITCH, 0), self.C_TRAYS_HERO, self.YAW)
        self.C_PROPS = self.coll('line_props_placeholders', A)
        self.lectern_dressing(self.C_PROPS, top)
        self.C_DRESS = self.coll('line_dressing', A)       # every other line's: the placeholders, a pendant that does not move
        inst('dressing_props', self.C_PROPS, (0, 0, 0), self.C_DRESS)
        self.pendant(self.C_DRESS, None, 'pendant_static')

    def pendant(self, collection, parent, name):
        """the crane's hanging control: a cable from its arm, a body at hand height, a button facing -Y"""
        P, M = self.G['pendant'], self.M
        mb = MB()
        mb.cyl((0, 0, (P['hang_z'] + P['z'] + 0.12) / 2 - P['z']), 0.006, P['hang_z'] - P['z'] - 0.12, 'z', 8, 1)
        mb.span((-0.035, -0.0275, -0.12), (0.035, 0.0275, 0.12), 0)
        mb.cyl((0, 0, 0.13), 0.016, 0.03, 'z', 24, 1)
        mb.cyl((0, -0.030, -0.03), 0.011, 0.006, 'y', 32, 1)                       # the lower, smaller button (fixed)
        mb.cyl((0, -0.0285, P['button_z'] - P['z']), 0.023, 0.003, 'y', 40, 1)     # a collar round the big button
        body = new_ob(name, mb.mesh('pendant_body', [M['machine_teal'], M['steel_dark']]), collection,
                      (P['x'], P['y'], P['z']), 0.0, parent)
        mb = MB()
        mb.cyl((0, -0.006, 0), 0.018, 0.012, 'y', 40, 0)
        button = new_ob(name + '_button', mb.mesh('pendant_button', [M['machine_white']]), collection,
                        (0, -0.0275, P['button_z'] - P['z']), 0.0, body)
        return body, button

    def lectern_dressing(self, collection, top):
        """blank stand-ins on the lectern's top (a clipboard, a stack of cards, pencils, a closed notebook), and empties
        where real ones go (place_*)"""
        M = self.M
        par = empty('lectern_top_frame', tuple(top.location), collection, size=0.1)
        par.rotation_euler = tuple(top.rotation_euler)
        mb = MB()
        mb.span((-0.285, -0.19, 0), (-0.045, 0.14, 0.006), 0)                      # the clipboard's board
        mb.span((-0.280, -0.185, 0.006), (-0.050, 0.11, 0.009), 1)                 # its paper
        mb.span((-0.215, 0.105, 0.006), (-0.115, 0.14, 0.020), 2)                  # its clip
        new_ob('ph_clipboard', mb.mesh('ph_clipboard', [M['steel_dark'], M['paper_placeholder'], M['steel_galv']]),
               collection, (0, 0, 0), 0, par)
        mb = MB()
        mb.span((0.16, 0.0, 0), (0.265, 0.148, 0.022), 0)
        new_ob('ph_cards', mb.mesh('ph_cards', [M['paper_placeholder']]), collection, (0, 0, 0), 0, par)
        mb = MB()
        for i in range(3):
            mb.cyl((0.05, 0.195 + 0.009 * i, 0.0045), 0.0037, 0.175, 'x', 6, 0)
        new_ob('ph_pencils', mb.mesh('ph_pencils', [M['steel_dark']]), collection, (0, 0, 0), 0, par)
        mb = MB()
        mb.span((-0.02, -0.17, 0), (0.13, 0.04, 0.012), 0)
        new_ob('ph_notebook', mb.mesh('ph_notebook', [M['steel_dark']]), collection, (0, 0, 0), 0, par)
        for nm, loc in (('place_clipboard', (-0.165, -0.025, 0.006)), ('place_notebook', (0.055, -0.065, 0.0)),
                        ('place_cards', (0.2125, 0.074, 0.0)), ('place_pencils', (0.05, 0.204, 0.0))):
            empty(nm, loc, collection, 0, par, size=0.05)
        return par

    # ------------------------------------------------------------------------------------------------ the crane
    def gantry_meshes(self):
        """the crane's moving parts as shared meshes: a double-girder bridge, a trolley that is an open frame (a camera
        above looks through it), four belts, a ring that comes down round a hood, four pads that grip its sides"""
        if getattr(self, '_gm', None):
            return self._gm
        G, M = self.G, self.M
        x0, x1 = G['rail_x']
        dy, gw = G['girder_dy'], G['girder_w']
        z0, z1 = G['girder_z']
        zt = G['rail_top']
        WTS = [M['machine_white'], M['machine_teal'], M['steel_galv']]
        out = {}
        mb = MB()
        for s in (-1, 1):
            mb.span((x0 - 0.22, s * dy - gw / 2, z0), (x1 + 0.22, s * dy + gw / 2, z1), 0)
            mb.span((x0 - 0.22, s * dy - 0.02, z1), (x1 + 0.22, s * dy + 0.02, z1 + 0.02), 2)             # the trolley's rail
        for rx in (x0, x1):
            mb.span((rx - 0.12, -0.92, zt + 0.03), (rx + 0.12, 0.92, zt + 0.22), 1)                        # the end truck
            for wy in (-0.78, 0.78):
                mb.cyl((rx, wy, zt + 0.03 + 0.075), 0.075, 0.26, 'x', 14, 2)
        mb.cyl((x0 - 0.20, 0.45, zt + 0.14), 0.07, 0.22, 'x', 14, 2)                                       # the travel motor
        out['bridge'] = mb.mesh('crane_bridge', WTS)
        mb = MB()
        ty, tx, tw = dy + 0.14, 0.62, 0.12
        for s in (-1, 1):
            mb.span((-tx, s * ty - tw / 2 * s - tw / 2, z1 + 0.02), (tx, s * ty - tw / 2 * s + tw / 2, z1 + 0.14), 0)
            mb.span((s * tx - tw / 2 * s - tw / 2, -ty, z1 + 0.02), (s * tx - tw / 2 * s + tw / 2, ty, z1 + 0.14), 0)
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.cyl((sx * 0.52, sy * 0.52, z1 + 0.20), 0.06, 0.10, 'x', 14, 2)                          # the belt drums
        mb.span((tx + 0.02, -0.26, z1 + 0.04), (tx + 0.22, 0.26, z1 + 0.30), 1)                           # the hoist's drive
        out['trolley'] = mb.mesh('crane_trolley', WTS)
        mb = MB()
        mb.span((-0.025, -0.003, -1.0), (0.025, 0.003, 0.0), 0)
        out['belt'] = mb.mesh('crane_belt', [M['steel_dark']])
        ro, ri = G['ring_half_out'], G['ring_half_in']
        mb = MB()
        for s in (-1, 1):
            mb.span((-ro, s * (ro + ri) / 2 - (ro - ri) / 2, -0.04), (ro, s * (ro + ri) / 2 + (ro - ri) / 2, 0.04), 0)
            mb.span((s * (ro + ri) / 2 - (ro - ri) / 2, -ri, -0.04), (s * (ro + ri) / 2 + (ro - ri) / 2, ri, 0.04), 0)
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.span((sx * 0.52 - 0.035, sy * 0.52 - 0.035, 0.04), (sx * 0.52 + 0.035, sy * 0.52 + 0.035, 0.08), 2)
        for a in range(4):                                                                                 # the pads' hangers
            m = Matrix.Rotation(a * PI / 2, 3, 'Z')
            c = m @ Vector(((ro + ri) / 2, 0, -0.105))
            mb.box(c, (0.06, 0.20, 0.13) if a % 2 == 0 else (0.20, 0.06, 0.13), 1)
        out['ring'] = mb.mesh('crane_ring', WTS)
        mb = MB()
        mb.span((0.0, -0.12, -0.05), (0.02, 0.12, 0.05), 0)
        mb.cyl((0.065, 0, 0), 0.014, 0.09, 'x', 10, 1)
        out['pad'] = mb.mesh('crane_pad', [M['rubber_black'], M['steel_galv']])
        self._gm = out
        return out

    def make_gantry(self, prefix, collection, parent=None):
        """the moving parts as objects: bridge (moves along y) > trolley (x) > ring (z) > pads; belts hang from the
        trolley"""
        ms = self.gantry_meshes()
        G = self.G
        z1 = G['girder_z'][1]
        bridge = new_ob(prefix + 'bridge', ms['bridge'], collection, (0, G['park_y'], 0), 0, parent)
        trolley = new_ob(prefix + 'trolley', ms['trolley'], collection, (G['trolley_x'][0], 0, 0), 0, bridge)
        ring = new_ob(prefix + 'ring', ms['ring'], collection, (0, 0, self.Z_TOP), 0, trolley)
        pads = [new_ob(prefix + 'pad_%d' % a, ms['pad'], collection, (0, 0, -0.105), a * PI / 2, ring) for a in range(4)]
        belts = [new_ob(prefix + 'belt_%d' % i, ms['belt'], collection, (sx * 0.52, sy * 0.52, z1 + 0.14), 0, trolley)
                 for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)))]
        socket = empty(prefix + 'hood_socket', (0, 0, -self.RING_TO_ORIGIN), collection, self.YAW, ring, size=0.2)
        socket['note'] = 'a hood set held by the ring has its origin here'
        return {'bridge': bridge, 'trolley': trolley, 'ring': ring, 'pads': pads, 'belts': belts, 'socket': socket}

    def rig_gantry(self, Gp, calc, run_ob, run_path, jmax, unit_expr, hoods, offs=None):
        """THE CRANE'S ONE PROPERTY, run (q): cycle J = min(floor(q), jmax) works on unit unit_expr(J); f = q - J is the
        move. hoods: [(hood object, cycle index k, slot empty)]: on its tray until k + hood_rides[0], on the ring until
        k + hood_rides[1], then in its slot. offs: (object, 'along_offset' path, 'hoist_offset' path) added on top (m)"""
        G, ST = self.G, self.ST
        C = G['cycle']
        q = [('q', run_ob, run_path)]
        J = f'min(floor(q),{jmax})'
        F = f'min(q-{J},1)'
        y0s, cp, xs = num(ST['y0']), num(ST['col_pitch']), num(ST['x'])
        lv = ST['levels']
        props = {
            'yu': f'{num(self.PITCH)}*({unit_expr(J)})',
            'ys': f'{y0s}-{cp}*floor({J}/{lv})',
            'yp': f'{num(G["park_y"])} if q<1 else {y0s}-{cp}*floor(({J}-1)/{lv})',
            'zs': f'{num(ST["base_h"] - self.SEAM + self.RING_TO_ORIGIN)}+{num(self.HOOD_H)}*({J}-{lv}*floor({J}/{lv}))',
        }
        for k, e in props.items():
            calc[k] = 0.0
            drv(calc, f'["{k}"]', e, q)
        looks = {
            'ta': ramp(*C['travel_a']) + [(1.0, 1.0)],
            'tb': [(0.0, 0.0)] + ramp(*C['travel_b']) + [(1.0, 1.0)],
            'da': [(0.0, 0.0)] + ramp(*C['lower_a']) + ramp(*C['raise_a'], 1.0, 0.0) + [(1.0, 0.0)],
            'db': [(0.0, 0.0)] + ramp(*C['lower_b']) + ramp(*C['raise_b'], 1.0, 0.0),
            'gr': [(0.0, 0.0)] + ramp(*C['grip']) + ramp(*C['release'], 1.0, 0.0) + [(1.0, 0.0)],
        }
        for k, pts in looks.items():
            calc[k] = 0.0
            lookup(drv(calc, f'["{k}"]', F, q), pts)
        cv = [(k, calc, f'["{k}"]') for k in ('yu', 'ys', 'yp', 'zs', 'ta', 'tb', 'da', 'db', 'gr')]
        ov = [('ao', offs[0], offs[1]), ('ho', offs[0], offs[2])] if offs else []
        drv(Gp['bridge'], 'location', 'yp+(yu-yp)*ta+(ys-yu)*tb' + ('+ao' if offs else ''), cv + ov, 1)
        drv(Gp['trolley'], 'location', f'{xs}*(1-ta+tb)', cv, 0)
        zexpr = f'{num(self.Z_TOP)}-({num(self.Z_TOP - self.Z_TRAY)})*da-({num(self.Z_TOP)}-zs)*db' + ('+ho' if offs else '')
        drv(Gp['ring'], 'location', zexpr, cv + ov, 2)
        half = self.L['carton']['size'][0] / 2 + 0.001
        for a, p in enumerate(Gp['pads']):
            sgn = 1 if a in (0, 1) else -1
            drv(p, 'location', f'{num(sgn)}*({num(half)}+{num(G["pad_stroke"])}*(1-gr))', cv, a % 2)
        z1 = G['girder_z'][1]
        for b in Gp['belts']:
            drv(b, 'scale', f'{num(z1 + 0.14 - 0.08)}-({zexpr})', cv + ov, 2)
        a0, a1 = C['hood_rides']
        for hood, k, slot in hoods:
            c1 = hood.constraints.new('COPY_TRANSFORMS')
            c1.name, c1.target = 'in_its_slot', slot
            drv(c1, 'influence', f'1 if q>={num(k + a1)} else 0', q)
            c2 = hood.constraints.new('COPY_TRANSFORMS')
            c2.name, c2.target = 'on_the_ring', Gp['socket']
            drv(c2, 'influence', f'1 if (q>={num(k + a0)} and q<{num(k + a1)}) else 0', q)

    # ------------------------------------------------------------------------------------------------ 3. the controls
    def control_empties(self):
        G, L, LN = self.G, self.L, self.LN
        CMch = self.C['machinery']
        g = empty('gantry_ctl', (G['rail_x'][1] + 0.3, -1.6, 2.2), CMch, kind='CUBE', size=0.12)
        add_prop(g, 'run', 10.0, 0.0, 11.0,
                 'THE HERO CRANE. Whole part: the unit it works on (0..9; 10 = the fresh carton at unit_0). Fraction: the move: '
                 'travel to the unit, lower, grip, raise, carry to the hood stack, set down. 0 = ten closed cartons; 10 = units '
                 '1..9 open.')
        add_prop(g, 'along_offset', 0.0, -8.0, 14.0, 'metres added to the bridge\'s place along the line')
        add_prop(g, 'hoist_offset', 0.0, -2.0, 0.5, 'metres added to the ring\'s height')
        t = empty('track_ctl', (L['main_track']['x'], -1.6, 2.2), CMch, kind='CUBE', size=0.12)
        add_prop(t, 'travel', 0.0, -1.0e6, 1.0e6, 'THE MAIN TRACK: metres its stream of closed cartons has rolled toward the dock')
        add_prop(t, 'swap', 1.0, 0.0, 1.0,
                 'THE HEAD OF THE HERO LINE: 0 = the first carton stands open at unit_0; 0..1 its tray rolls out along the spur '
                 'and away through the dock while a fresh closed carton rolls in along the inbound track; 1 = the fresh one stands there')
        c = empty('crowd_ctl', (self.LANES[-1], -1.6, 2.2), CMch, kind='CUBE', size=0.12)
        self.CROWD_MAX = 9.0 + (L['crowd']['variants'] - 1) * L['crowd']['phase_step']
        add_prop(c, 'crowd_run', self.CROWD_MAX, 0.0, self.CROWD_MAX,
                 'EVERY OTHER LINE\'S CRANE: as run, for units 1..9 (unit_0 stays closed); each row runs a little after the one '
                 'before. 0 = every line closed; at its highest value every line has its nine open')
        self.controls.update(gantry_ctl=g, track_ctl=t, crowd_ctl=c)
        self.report['crowd_run_max'] = self.CROWD_MAX
        self.CROWD = []
        NV = L['crowd']['variants']
        for v in range(NV):
            col = self.coll('crowd_moving_%d' % v, self.C['assets'])
            ctl = empty('cm%d_run' % v, (0, 0, 0), col)
            ctl['run'] = 9.0
            drv(ctl, '["run"]', f'clamp(q-{num(v * L["crowd"]["phase_step"])},0,9)', [('q', c, '["crowd_run"]')])
            calc = empty('cm%d_calc' % v, (0, 0, 0), col)
            Gp = self.make_gantry('cm%d_' % v, col)
            inst('cm%d_hood_0' % v, self.CT['hood'], (0, 0, 0), col, self.YAW)                  # unit_0 stays closed
            hoods = []
            for K in range(1, LN['units']):
                h = inst('cm%d_hood_%d' % (v, K), self.CT['hood'], (0, K * self.PITCH, 0), col, self.YAW)
                s = empty('cm%d_slot_%d' % (v, K - 1), self.slot_xyz(K - 1), col, self.YAW)
                hoods.append((h, K - 1, s))
            self.rig_gantry(Gp, calc, ctl, '["run"]', 8, lambda J: f'{J}+1', hoods)
            self.CROWD.append(col)

    # ------------------------------------------------------------------------------------------------ 4. the shell
    def lines_plan(self):
        """(nn, lane, row, X0, Y0) for every line: the hero aisle (lane 0) holds the hero line alone"""
        self.LINES = []
        for lane, X0 in enumerate(self.LANES):
            for row in range(1 if lane == 0 else self.ROWS):
                self.LINES.append((len(self.LINES), lane, row, X0, -row * self.L['hall']['row_pitch']))
        MT = self.L['main_track']
        self.MX, self.MHW = MT['x'], MT['half_width']
        self.MY0 = max(MT['y0'], self.HY0 + 4.0)

    def shell(self):
        L, M, H = self.L, self.M, self.L['hall']
        CS = self.C['hall_shell']
        T = self.LN['track']
        HX0, HX1, HY0, HY1 = self.HX0, self.HX1, self.HY0, self.HY1
        MX, MHW, MY0 = self.MX, self.MHW, self.MY0
        holes = [(X0 - T['half_width'], X0 + T['half_width'], Y0 + T['y0'], Y0 + T['y1']) for _n, _l, _r, X0, Y0 in self.LINES]
        holes += [(MX + MHW, -T['half_width'], Y0 - T['half_width'], Y0 + T['half_width'])
                  for _n, lane, _r, _x, Y0 in self.LINES if lane == 0]
        holes.append((MX - MHW, MX + MHW, MY0, HY1 + 1.0))
        holes.append((-T['half_width'], T['half_width'], MY0, T['y0']))                    # the inbound track
        floor_with_holes('hall_floor', HX0, HX1, HY0, HY1, holes, CS, M['hall_concrete'])
        D = L['dock']
        wt, rz_ = H['wall_t'], H['roof_z']
        mb = MB()
        mb.span((HX1, HY0 - wt, 0), (HX1 + wt, HY1 + wt, rz_))                                      # east: the side wall
        mb.span((HX0 - wt, HY0 - wt, 0), (HX0, HY1 + wt, rz_))                                      # west
        mb.span((HX0, HY0 - wt, 0), (HX1, HY0, rz_))                                                # the far end
        mb.span((HX0, HY1, 0), (D['door_x'][0], HY1 + wt, rz_))                                     # the dock wall, west of the door
        mb.span((D['door_x'][1], HY1, 0), (HX1, HY1 + wt, rz_))
        mb.span((D['door_x'][0], HY1, D['door_h']), (D['door_x'][1], HY1 + wt, rz_))
        new_ob('hall_walls', mb.mesh('hall_walls', [M['hall_wall_panel']]), CS)
        mb = MB()
        mb.span((HX0 - wt, HY0 - wt, rz_), (HX1 + wt, HY1 + wt, rz_ + 0.25))
        for k in range(int((HY1 - HY0) // 12) + 1):                                                  # roof beams across the hall
            y = HY1 - 6.0 - 12.0 * k
            if y > HY0:
                mb.span((HX0, y - 0.12, rz_ - 0.5), (HX1, y + 0.12, rz_))
        new_ob('hall_roof', mb.mesh('hall_roof', [M['hall_roof']]), CS)
        mb = MB()
        lz, ll, lp = H['lights_z'], H['light_len'], H['light_pitch']
        for x in H['light_rows_x']:
            if x < HX0 or (self.small and x < self.LANES[-1] - 4):
                continue
            y = HY1 - 1.0 - ll / 2
            while y - ll / 2 > HY0:
                mb.span((x - 0.07, y - ll / 2, lz), (x + 0.07, y + ll / 2, lz + 0.07), 0)
                mb.span((x - 0.055, y - ll / 2 + 0.03, lz - 0.012), (x + 0.055, y + ll / 2 - 0.03, lz), 1)
                mb.span((x - 0.01, y - 0.01, lz + 0.07), (x + 0.01, y + 0.01, rz_ - 0.25), 0)
                y -= lp
        new_ob('strip_lights', mb.mesh('strip_lights', [M['machine_white'], M['strip_light_glow']]), CS)
        OW = L['office_window']
        mb = MB()
        ox = OW['wall_x']
        mb.span((ox - 0.10, OW['y'][0] - 0.12, OW['z'][0] - 0.12), (ox, OW['y'][1] + 0.12, OW['z'][0]), 0)        # the frame
        mb.span((ox - 0.10, OW['y'][0] - 0.12, OW['z'][1]), (ox, OW['y'][1] + 0.12, OW['z'][1] + 0.12), 0)
        for i in range(5):
            y = OW['y'][0] + (OW['y'][1] - OW['y'][0]) * i / 4
            mb.span((ox - 0.10, y - 0.05, OW['z'][0]), (ox, y + 0.05, OW['z'][1]), 0)
        mb.span((ox - 0.05, OW['y'][0], OW['z'][0]), (ox - 0.03, OW['y'][1], OW['z'][1]), 1)                      # the frosted pane
        new_ob('office_window', mb.mesh('office_window', [M['machine_white'], M['office_frosted_glow']]), CS)

    # ------------------------------------------------------------------------------------------------ 5. racks and stock
    def racks(self):
        M, RK = self.M, self.L['racks']
        HX0, HY0 = self.HX0, self.HY0
        count = {'near': 0, 'far': 0}
        frame_mb = MB()
        for row in RK['rows']:
            y_lo, y_hi = max(row['y'][0], HY0 + 1.0), row['y'][1]
            if row['face_x'] < HX0:
                continue
            sgn = 1 if row['faces'] == '+x' else -1                    # the aisle is on this side of the row
            fx = row['face_x']
            bx = fx - sgn * RK['depth']
            bay = RK['bay']
            m0, m1 = math.ceil((y_lo + 0.6) / bay), math.floor((y_hi + 0.6) / bay)
            for m in range(m0, m1 + 1):
                y = -0.6 + bay * m
                for x in (fx - sgn * 0.045, bx + sgn * 0.045):
                    frame_mb.span((x - 0.045, y - 0.035, 0), (x + 0.045, y + 0.035, RK['post_h']), 0)
                for z in (0.35, 1.3, 2.9, 4.5):
                    frame_mb.span((min(fx, bx) + 0.09, y - 0.02, z - 0.02), (max(fx, bx) - 0.09, y + 0.02, z + 0.02), 0)
                if m < m1:
                    for zt_ in RK['levels_z']:
                        for x in (fx - sgn * 0.03, bx + sgn * 0.03):
                            frame_mb.span((x - 0.025, y + 0.035, zt_ - 0.10), (x + 0.025, y + bay - 0.035, zt_), 1)
            near, far = [], []
            ya, yb = -0.6 + bay * m0, -0.6 + bay * m1
            n0, n1 = math.ceil((ya + 0.3) / RK['stock_pitch']), math.floor((yb - 0.3) / RK['stock_pitch'])
            aisle = row['name'] in ('r1_east', 'east_wall')
            for n in range(n0, n1 + 1):
                y = n * RK['stock_pitch']
                for zt_ in RK['levels_z']:
                    (near if aisle and RK['near_y'][0] <= y <= RK['near_y'][1] else far).append((fx - sgn * RK['depth'] / 2, y, zt_))
            for pts, key in ((near, 'near'), (far, 'far')):
                if not pts:
                    continue
                me = bpy.data.meshes.new('stock_%s_%s_points' % (row['name'], key))
                me.from_pydata(pts, [], [])
                o = new_ob('stock_%s_%s' % (row['name'], key), me, self.C['boxes_stock'])
                mod = o.modifiers.new('stock', 'NODES')
                mod.node_group = self.gn_instancer('stock_%s_%s' % (row['name'], key), self.CT['closed'],
                                                   self.YAW if sgn > 0 else -self.YAW)
                o['note'] = 'each point is a closed carton'
                count[key] += len(pts)
        new_ob('rack_frames', frame_mb.mesh('rack_frames', [M['rack_upright'], M['rack_beam']]), self.C['racks'])
        self.report['stock_cartons'] = count
        self.say('stock cartons on the racks:', count)

    @staticmethod
    def gn_instancer(name, what, rz):
        ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
        ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        n_in, n_out = ng.nodes.new('NodeGroupInput'), ng.nodes.new('NodeGroupOutput')
        ci = ng.nodes.new('GeometryNodeCollectionInfo')
        ci.inputs[0].default_value = what
        ci.transform_space = 'ORIGINAL'
        iop = ng.nodes.new('GeometryNodeInstanceOnPoints')
        iop.inputs['Rotation'].default_value = (0.0, 0.0, rz)
        ng.links.new(n_in.outputs[0], iop.inputs['Points'])
        ng.links.new(ci.outputs[0], iop.inputs['Instance'])
        ng.links.new(iop.outputs[0], n_out.inputs[0])
        return ng

    # ------------------------------------------------------------------------------------------------ 6. the lines
    def lines(self):
        LN, L = self.LN, self.L
        CL = self.C['lines']
        LE = LN['lectern']
        NV = L['crowd']['variants']
        if len(self.LINES) > 100:
            raise RuntimeError('more than 100 lines: line_NN would need three digits')
        self.HERO_ROOT = None
        for nn, lane, row, X0, Y0 in self.LINES:
            hero = nn == 0
            tag = 'line_%02d' % nn
            root = empty(tag, (X0, Y0, 0), CL, kind='ARROWS', size=0.6)
            root['lane'], root['row'], root['hero'] = lane, row, int(hero)
            root['crowd_copy'] = -1 if hero else row % NV
            root['delay'] = 0.0 if hero else (row % NV) * L['crowd']['phase_step']
            inst(tag + '_module', self.C['line_module'], (0, 0, 0), CL, 0, root)
            for K in range(LN['units']):
                empty('%s_unit_%d' % (tag, K), (0, K * self.PITCH, 0), CL, self.YAW, root, size=0.25)
            lead = empty(tag + '_lead', (LE['x'], LE['y'] - LE['stand_back'], 0), CL, PI, root, kind='SINGLE_ARROW', size=0.4)
            lead['note'] = 'the station\'s mark at the lectern; local -Y is the way a body there faces (down the line)'
            if hero:
                self.HERO_ROOT = root
                inst(tag + '_trays', self.C_TRAYS_HERO, (0, 0, 0), CL, 0, root)
                inst(tag + '_props_placeholders', self.C_PROPS, (0, 0, 0), CL, 0, root)
            else:
                inst(tag + '_trays', self.C_TRAYS, (0, 0, 0), CL, 0, root)
                inst(tag + '_dressing', self.C_DRESS, (0, 0, 0), CL, 0, root)
                inst(tag + '_moving', self.CROWD[row % NV], (0, 0, 0), CL, 0, root)
        self.report['lines'] = {'lines': len(self.LINES), 'lanes': len(self.LANES), 'rows': self.ROWS,
                                'units': len(self.LINES) * LN['units']}

    # ------------------------------------------------------------------------------------------------ 7. the hero line
    def hero(self):
        L, LN, G = self.L, self.LN, self.G
        MT = L['main_track']
        CH, CM = self.C['line_hero'], self.C['machinery']
        HR = self.HERO_ROOT
        HTAG = HR.name
        MX = self.MX
        track_ctl, gantry_ctl = self.controls['track_ctl'], self.controls['gantry_ctl']
        sw = [('q', track_ctl, '["swap"]')]
        tray_a = inst(HTAG + '_tray_a', self.CT['tray'], (0, 0, 0), CH, self.YAW, HR)
        tray_a['note'] = 'the first carton at unit_0: swap rolls it away'
        drv(tray_a, 'location', f'{num(MX)}*clamp(q/0.3,0,1)+{num(MT["x_end"] - MX)}*clamp((q-0.9)/0.1,0,1)', sw, 0)
        drv(tray_a, 'location', f'{num(MT["y_turn"])}*clamp((q-0.3)/0.6,0,1)', sw, 1)
        tray_b = inst(HTAG + '_tray_b', self.CT['tray'], (0, 0, 0), CH, self.YAW, HR)
        tray_b['note'] = 'the fresh carton that swap rolls in to unit_0 along the inbound track'
        drv(tray_b, 'location', f'{num(MT["swap"]["b_start_y"])}-({num(MT["swap"]["b_start_y"])})*clamp((q-0.25)/0.75,0,1)', sw, 1)
        for nm, par in (('_unit_0a', tray_a), ('_unit_0b', tray_b)):
            e = empty(HTAG + nm, (0, 0, 0), CH, 0, par, size=0.25)
            e['note'] = 'the tray frame of this carton as it rolls (a body in it rides here)'
        slots = [empty('%s_stack_slot_%d' % (HTAG, j), self.slot_xyz(j), CH, self.YAW, HR, size=0.1) for j in range(self.N_SLOTS)]
        hoods = []
        for K in range(LN['units']):
            par = tray_a if K == 0 else bpy.data.objects['%s_unit_%d' % (HTAG, K)]
            h = inst('%s_hood_%d' % (HTAG, K), self.CT['hood'], (0, 0, 0), CH, 0, par)
            hoods.append((h, K, slots[K]))
        h = inst(HTAG + '_hood_0b', self.CT['hood'], (0, 0, 0), CH, 0, tray_b)
        hoods.append((h, 10, slots[10]))
        gcalc = empty('gantry_calc', (G['rail_x'][1] + 0.3, -1.6, 2.0), CM, size=0.05)
        self.HG = self.make_gantry('gantry_', CM, HR)
        self.rig_gantry(self.HG, gcalc, gantry_ctl, '["run"]', 10, lambda J: f'({J} if q<10 else 0)', hoods,
                        (gantry_ctl, '["along_offset"]', '["hoist_offset"]'))
        pbody, pbutton = self.pendant(CM, HR, 'gantry_pendant')
        add_prop(pbody, 'press', 0.0, 0.0, 1.0, 'the pendant\'s button: 0 out, 1 pressed in')
        drv(pbutton, 'location', f'{num(-0.0275)}+{num(G["pendant"]["button_travel"])}*q', [('q', pbody, '["press"]')], 1)
        e = empty('gantry_pendant_button_face', (0, -0.012, 0), CM, 0, pbutton, size=0.03)
        e['note'] = 'the centre of the button\'s face (a thumb presses it along +Y)'
        self.controls['gantry_pendant'] = pbody
        CT = L['carton']
        for K in range(LN['units']):                                       # tray (x, y) -> the line's (-y, x)
            e = empty('%s_mark_%d' % (HTAG, K), (-CT['body_mark'][1], K * self.PITCH + CT['body_mark'][0], CT['body_mark'][2]),
                      self.C['marks'], self.YAW, HR, kind='CIRCLE', size=0.2)
            e['note'] = 'where a body stands in unit %d\'s tray (the carton\'s body_mark); local -Y is the way it faces' % K

    # ------------------------------------------------------------------------------------------------ 8. the main track
    def main_track(self):
        L, LN = self.L, self.LN
        MT = L['main_track']
        T = LN['track']
        MX, MHW, MY0 = self.MX, self.MHW, self.MY0
        CM = self.C['machinery']
        M = self.M
        mb = MB()
        track_mesh(mb, T, MX - MHW, MX + MHW, MY0, MT['y_turn'] + MHW, 'y')
        track_mesh(mb, T, MT['x_end'] - 0.6, MX - MHW, MT['y_turn'] - MHW, MT['y_turn'] + MHW, 'x')
        for _n, lane, _r, _x, Y0 in self.LINES:
            if lane == 0:
                track_mesh(mb, T, MX + MHW, -T['half_width'], Y0 - T['half_width'], Y0 + T['half_width'], 'x')
        new_ob('main_track', mb.mesh('main_track', [M['steel_galv'], M['steel_dark']]), CM)
        mb = MB()
        track_mesh(mb, T, -T['half_width'], T['half_width'], MY0, T['y0'], 'y')
        new_ob('inbound_track', mb.mesh('inbound_track', [M['steel_galv'], M['steel_dark']]), CM)
        CSt = self.coll('boxes_stream', CM)
        SPI = MT['stream']['pitch']
        SPH = MT['stream'].get('phase', 0.0)
        leg_y = MT['y_turn'] - MY0
        path_len = leg_y + (MX - MT['x_end'])
        n_stream = int(math.ceil(path_len / SPI))
        loop = n_stream * SPI
        tv = [('q', self.controls['track_ctl'], '["travel"]')]
        for i in range(n_stream):
            b = inst('stream_box_%02d' % i, self.CT['closed'], (MX, MY0, 0), CSt, self.YAW)
            w = f'(q+{num(i * SPI + SPH)}-{num(loop)}*floor((q+{num(i * SPI + SPH)})/{num(loop)}))'
            drv(b, 'location', f'{num(MY0)}+min({w},{num(leg_y)})', tv, 1)
            drv(b, 'location', f'{num(MX)}-max(0,{w}-{num(leg_y)})', tv, 0)
        self.report['stream'] = {'cartons': n_stream, 'pitch': SPI, 'phase': SPH, 'loop_m': round(loop, 3), 'y_start': MY0,
                                 'carton_i_at_y': 'y = y_start + ((travel + phase + i * pitch) mod loop_m), up to the turn outside the door'}

    # ------------------------------------------------------------------------------------------------ 9. the meter
    def meter(self):
        L, M = self.L, self.M
        MC = L['meter_cabinet']
        CC = self.C['meter_cabinet']
        cx0, cx1 = MC['x']
        cy0, cy1 = MC['y']
        cxm = (cx0 + cx1) / 2
        wz, (ww, wh) = MC['window_z'], MC['window']
        mb = MB()
        mb.span((cx0 - 0.03, cy0 - 0.03, 0), (cx1 + 0.03, cy1 + 0.03, MC['plinth']), 1)
        zt = MC['plinth'] + MC['h']
        t = 0.02
        mb.span((cx0, cy0, MC['plinth']), (cx1, cy0 + t, zt), 0)                                   # the back
        mb.span((cx0, cy0, MC['plinth']), (cx0 + t, cy1, zt), 0)
        mb.span((cx1 - t, cy0, MC['plinth']), (cx1, cy1, zt), 0)
        mb.span((cx0, cy0, zt - t), (cx1, cy1, zt), 0)
        mb.span((cx0, cy0, MC['plinth']), (cx1, cy1, MC['plinth'] + t), 0)
        dy = cy1                                                                                    # the door, on +Y, with its window
        mb.span((cx0 + 0.015, dy, MC['plinth'] + 0.015), (cx1 - 0.015, dy + 0.018, wz - wh / 2), 0)
        mb.span((cx0 + 0.015, dy, wz + wh / 2), (cx1 - 0.015, dy + 0.018, zt - 0.015), 0)
        mb.span((cx0 + 0.015, dy, wz - wh / 2), (cxm - ww / 2, dy + 0.018, wz + wh / 2), 0)
        mb.span((cxm + ww / 2, dy, wz - wh / 2), (cx1 - 0.015, dy + 0.018, wz + wh / 2), 0)
        new_ob('meter_cabinet', mb.mesh('meter_cabinet', [M['cabinet_grey'], M['steel_galv'], M['steel_dark']]), CC)
        mb = MB()
        mb.quad([(cxm - ww / 2, dy + 0.004, wz - wh / 2), (cxm + ww / 2, dy + 0.004, wz - wh / 2),
                 (cxm + ww / 2, dy + 0.004, wz + wh / 2), (cxm - ww / 2, dy + 0.004, wz + wh / 2)])
        glass = new_ob('meter_window_glass', mb.mesh('meter_window_glass', [M['glass_placeholder']], recalc=False), CC)
        glass.hide_render = True                                                                   # (the look glazes it)
        e = empty('meter_label_place', (cxm, dy + 0.0205, wz + 0.105), CC, size=0.05)
        e.rotation_euler = (PI / 2, 0, PI)
        e['note'] = 'a label plate 0.26 x 0.07 m on the door; local +Z out of the door, +Y up'
        ctl = empty('meter_cabinet_ctl', (cxm, cy1 + 0.4, 2.3), CC, kind='CUBE', size=0.12)
        add_prop(ctl, 'meter', float(MC['default']), 0.0, 9999.0, 'THE METER: the number its four drums show (0..9999); it rolls like an odometer')
        self.controls['meter_cabinet_ctl'] = ctl
        font = bpy.data.fonts.load(common.asset_path('fonts', 'Rajdhani-Bold.ttf'), check_existing=True)
        R = MC['drum_d'] / 2
        DW = MC['drum_w']
        digit_meshes = []
        tmpc = bpy.data.collections.new('tmp_digits')
        self.SC.collection.children.link(tmpc)
        for n in range(10):
            cu = bpy.data.curves.new('digit', 'FONT')
            cu.body, cu.font, cu.size = str(n), font, 0.36 * MC['drum_d']
            cu.align_x, cu.align_y = 'CENTER', 'CENTER'
            o = new_ob('digit', cu, tmpc)
            bpy.context.view_layer.update()
            me = bpy.data.meshes.new_from_object(o.evaluated_get(bpy.context.evaluated_depsgraph_get()))
            digit_meshes.append(me)
            bpy.data.objects.remove(o)
            bpy.data.curves.remove(cu)
        bpy.data.collections.remove(tmpc)
        face = Matrix(((-1, 0, 0), (0, 0, 1), (0, 1, 0)))                 # a glyph in its XY plane -> on the drum's front, upright
        mv = [('q', ctl, '["meter"]')]
        for k in range(MC['digits']):
            mb = MB()
            mb.cyl((0, 0, 0), R, DW - 0.004, 'x', 40, 0)
            for s in (-1, 1):                                               # a dark flange at each side of the drum
                mb.cyl((s * (DW / 2 - 0.0015), 0, 0), R + 0.003, 0.003, 'x', 40, 1)
            me = mb.mesh('meter_drum_%d' % k, [M['drum_white'], M['drum_ink']])
            bm = bmesh.new()
            bm.from_mesh(me)
            for n in range(10):
                rot = Matrix.Rotation(-n * RAD(36), 3, 'X')
                a, nf = len(bm.verts), len(bm.faces)
                bm.from_mesh(digit_meshes[n])
                bm.verts.ensure_lookup_table()
                bm.faces.ensure_lookup_table()
                for v in bm.verts[a:]:
                    p = face @ v.co
                    v.co = rot @ Vector((p.x, R + 0.0007, p.z))            # laid on the rim: a flat glyph 0.7 mm off the drum
                for f in bm.faces[nf:]:
                    f.material_index = 1
            bm.to_mesh(me)
            bm.free()
            x = cxm - (MC['digits'] / 2 - 0.5 - k) * (DW + 0.006)          # k 0 = the units' drum, on the reader's right (-X)
            drum = new_ob('meter_drum_%d' % k, me, CC, (x, dy - R - 0.012, wz))
            p10 = 10 ** k
            ex = 'q' if k == 0 else f'floor(q/{p10})+clamp(q-{p10}*floor(q/{p10})-{p10 - 1},0,1)'
            drv(drum, 'rotation_euler', f'0.6283185*({ex})', mv, 0)
        for me in digit_meshes:
            bpy.data.meshes.remove(me)
        mb = MB()                                                           # the drums' housing behind the window (dark)
        mb.span((cxm - ww / 2 - 0.03, dy - 2 * R - 0.03, wz - R - 0.02), (cxm + ww / 2 + 0.03, dy - 2 * R - 0.025, wz + R + 0.02), 0)
        new_ob('meter_drum_housing', mb.mesh('meter_drum_housing', [M['steel_dark']]), CC)
        self.cab = (cxm, cy1, wz)

    # ------------------------------------------------------------------------------------------------ 10. the cage
    def cage(self):
        RC = self.L['returns_cage']
        CG = self.C['returns_cage']
        M = self.M
        gx0, gx1 = RC['x']
        gy0, gy1 = RC['y']
        gh = RC['h']
        corners = [(gx0, gy0), (gx1, gy0), (gx1, gy1), (gx0, gy1)]
        pm = MB()
        for px, py in corners + [((gx0 + gx1) / 2, gy0), (gx0, gy0 + 1.6), (gx0, gy0 + 3.0)]:
            pm.cyl((px, py, gh / 2), 0.03, gh, 'z', 10, 0)
        for a, b in ((corners[0], corners[1]), (corners[0], corners[3])):
            cxm_, cym_ = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            ln = math.hypot(b[0] - a[0], b[1] - a[1])
            pm.cyl((cxm_, cym_, gh), 0.022, ln, 'x' if abs(b[0] - a[0]) > 0.1 else 'y', 8, 0)
        for z in (0.05, gh):
            pm.box((gx0 + 0.9, gy0 + 2.085, z), (0.03, 1.6, 0.03), 0, math.atan2(0.93, 1.3) - PI / 2)
        new_ob('cage_posts', pm.mesh('cage_posts', [M['steel_galv']]), CG)
        # the woven chain link comes with the look; the layout's is a thin sheet on each side
        mb = MB()
        for a, b in ((corners[0], corners[1]), (corners[0], (gx0, gy0 + 1.6)), ((gx0, gy0 + 3.0), corners[3]),
                     ((gx0 + 0.25, gy0 + 1.62), (gx0 + 1.55, gy0 + 2.55))):
            mb.quad([(a[0], a[1], 0.05), (b[0], b[1], 0.05), (b[0], b[1], gh), (a[0], a[1], gh)])
        new_ob('cage_chain_link', mb.mesh('cage_chain_link', [M['steel_galv']], recalc=False), CG)
        cr = 0
        for i in range(3):
            for j in range(2):
                x, y = gx0 + 0.75 + 1.0 * i, gy1 - 0.65 - 1.05 * j
                for lvl in range(2):
                    if cr >= RC['cartons'] or (lvl == 1 and j == 1):
                        continue
                    yaw = -PI / 2 + RAD((7, -4, 3, -9, 5, -2, 8, -6, 2)[cr % 9])
                    inst('cage_carton_%d' % cr, self.CT['closed'], (x, y, self.L['carton']['size'][2] * lvl), CG, yaw)
                    cr += 1
        self.report['returns_cage'] = {'cartons': cr}

    # ------------------------------------------------------------------------------------------------ 11. the dock
    def dock(self):
        L, M, H = self.L, self.M, self.L['hall']
        D = L['dock']
        MT = L['main_track']
        CD = self.C['dock']
        HY1, wt = self.HY1, H['wall_t']
        MX, MHW = self.MX, self.MHW
        dx0, dx1 = D['door_x']
        dh = D['door_h']
        mb = MB()
        for x in (dx0 - 0.12, dx1 + 0.12):
            mb.span((x - 0.12, HY1 - 0.06, 0), (x + 0.12, HY1 + wt + 0.06, dh + 0.25), 0)             # the jambs
        mb.span((dx0 - 0.24, HY1 - 0.06, dh), (dx1 + 0.24, HY1 + wt + 0.06, dh + 0.25), 0)
        mb.cyl(((dx0 + dx1) / 2, HY1 - 0.32, dh + 0.42), 0.26, dx1 - dx0 + 0.3, 'x', 20, 1)          # the rolled-up door
        mb.span((dx0 - 0.2, HY1 - 0.62, dh + 0.12), (dx1 + 0.2, HY1 - 0.02, dh + 0.18), 1)
        for x in (dx0 - 0.5, dx1 + 0.5):
            mb.cyl((x, HY1 - 1.2, 0.55), 0.085, 1.1, 'z', 14, 2)                                     # bollards
        new_ob('dock_door', mb.mesh('dock_door', [M['steel_galv'], M['machine_white'], M['machine_teal']]), CD)
        yo = HY1 + wt
        out_holes = [(MX - MHW, MX + MHW, yo - 1.0, MT['y_turn'] + MHW),
                     (MT['x_end'] - 0.6, MX - MHW, MT['y_turn'] - MHW, MT['y_turn'] + MHW)]
        floor_with_holes('dock_apron', -90.0, 60.0, yo, 220.0, out_holes, CD, M['dock_apron'])
        mb = MB()                                                                                    # the threshold: two steel plates
        mb.span((dx0, HY1, -0.02), (MX - MHW, yo, 0.0), 0)
        mb.span((MX + MHW, HY1, -0.02), (dx1, yo, 0.0), 0)
        new_ob('dock_threshold', mb.mesh('dock_threshold', [M['steel_galv']]), CD)

    # ------------------------------------------------------------------------------------------------ 12. the cameras
    def cameras(self):
        CAM = self.L['cameras']
        CC = self.C['cameras']
        rim = self.L['carton']['rim_z']
        cams = {}
        for name in ('cam_top_unit0', 'cam_top_unit1'):
            c = CAM[name]
            px, py = -c['centre'][1], c['unit'] * self.PITCH + c['centre'][0]           # the tray's (x, y) -> the line's (-y, x)
            lens = 36.0 * (c['z'] - rim) / c['frame_width_at_rim']
            cams[name] = look_at(name, CC, (px, py, c['z']), (px, py, 0), lens, up=(-1, 0, 0))
        c = CAM['cam_line_top']
        cams['cam_line_top'] = look_at('cam_line_top', CC, c['pos'], (c['pos'][0], c['pos'][1], 0), up=(-1, 0, 0), ortho=c['ortho'])
        for name, c in CAM.items():
            if name in cams or not isinstance(c, dict) or 'pos' not in c:
                continue
            cams[name] = look_at(name, CC, c['pos'], c['aim'], c['lens'])
        c = CAM['cam_drums']
        cxm, cy1, wz = self.cab
        cams['cam_drums'] = look_at('cam_drums', CC, (cxm, cy1 + c['back'], wz + 0.03), (cxm, cy1, wz + 0.03), c['lens'])
        self.SC.camera = cams['cam_aisle_out']
        self.cams = cams
        self.report['cameras'] = sorted(cams)

    # ------------------------------------------------------------------------------------------------ 13. the light
    def light(self):
        """the layout's own light (the look replaces it): a pale sky for the lens through the door, the dock sun, two
        shadowless fills from above"""
        L, H = self.L, self.L['hall']
        D = L['dock']
        SC = self.SC
        w = bpy.data.worlds.new('layout_world')
        if not w.node_tree:
            w.use_nodes = True
        bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
        bg.inputs['Color'].default_value = (0.74, 0.82, 0.92, 1.0)
        bg.inputs['Strength'].default_value = 0.38
        wo = next(n for n in w.node_tree.nodes if n.type == 'OUTPUT_WORLD')
        bg2 = w.node_tree.nodes.new('ShaderNodeBackground')
        bg2.inputs['Color'].default_value = (0.80, 0.86, 0.95, 1.0)
        bg2.inputs['Strength'].default_value = 2.2
        lp = w.node_tree.nodes.new('ShaderNodeLightPath')
        mx = w.node_tree.nodes.new('ShaderNodeMixShader')
        w.node_tree.links.new(lp.outputs['Is Camera Ray'], mx.inputs[0])
        w.node_tree.links.new(bg.outputs[0], mx.inputs[1])
        w.node_tree.links.new(bg2.outputs[0], mx.inputs[2])
        w.node_tree.links.new(mx.outputs[0], wo.inputs['Surface'])
        SC.world = w
        SC.eevee.use_raytracing = True
        SC.eevee.use_fast_gi = True
        SC.eevee.fast_gi_method = 'AMBIENT_OCCLUSION_ONLY'
        S = D['sun']
        az = RAD(S['azimuth_off_axis'])
        head_y = self.HY1 + H['wall_t'] + 0.06                 # the outer foot of the door's head: its shadow ends the patch
        el = math.atan(D['door_h'] * math.cos(az) / (head_y - S['patch_end_y']))
        self.SUN_DIR = Vector((-math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), -math.sin(el)))   # the way it travels
        self.report['dock_sun'] = {'elevation_deg': round(math.degrees(el), 3), 'azimuth_off_axis_deg': S['azimuth_off_axis'],
                                   'patch_end_y': S['patch_end_y']}
        ld = bpy.data.lights.new('sun_dock', 'SUN')
        ld.energy, ld.color, ld.angle = 9.0, (1.0, 0.80, 0.58), RAD(0.53)
        o = new_ob('sun_dock', ld, self.C['layout_lights'], (0, 40, 12))
        o.rotation_euler = self.SUN_DIR.to_track_quat('-Z', 'Y').to_euler()
        o['note'] = 'the afternoon sun through the dock door, at layout.json\'s dock.sun angles: its patch reaches unit_9\'s tray'
        for nm, energy, dv in (('fill_a', 1.7, (-0.42, 0.30, -0.86)), ('fill_b', 0.9, (0.50, -0.36, -0.79))):
            ld = bpy.data.lights.new(nm, 'SUN')
            ld.energy, ld.color, ld.use_shadow = energy, (0.86, 0.92, 1.0), False
            o = new_ob(nm, ld, self.C['layout_lights'], (0, 0, 20))
            o.rotation_euler = Vector(dv).normalized().to_track_quat('-Z', 'Y').to_euler()
        SC.eevee.taa_render_samples = 32

    # ------------------------------------------------------------------------------------------------ 14. count
    def count(self):
        for lc in bpy.context.view_layer.layer_collection.children:
            for sub in lc.children:
                if sub.name == 'assets':
                    sub.exclude = True
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        tri_cache, tris, n_inst = {}, 0, 0
        for i in dg.object_instances:
            o = i.object
            if o.type != 'MESH':
                continue
            key = o.data.name if o.data else o.name
            if key not in tri_cache:
                try:
                    tri_cache[key] = tri_count(o.data)
                except (AttributeError, RuntimeError):
                    tri_cache[key] = 0
            tris += tri_cache[key]
            n_inst += 1
        self.report['scene'] = {'objects': len(bpy.data.objects), 'mesh_instances_drawn': n_inst, 'triangles_drawn': tris,
                                'meshes': len(bpy.data.meshes), 'collections': len(bpy.data.collections)}
        self.report['seconds'] = round(time.time() - self.T0, 1)
        self.say('the layout:', self.report['scene'])
