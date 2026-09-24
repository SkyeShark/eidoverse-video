"""era_bkit.py — Blender 5.2 kit for DAISY's era-2 voice machines (headless).

Build scripts (build_<machine>.py) import this, model each machine as hard-surface masses (profile prisms / lofts,
exact booleans, angle-limited chamfers, weighted normals), give every face a bake-source material (AmbientCG PBR
box-projected at real scale, tinted; AO grime; pointiness edge wear; yellowing; dust; projected label decals),
bake the layered look down to per-atlas maps (colour, roughness, normal, AO) and export one GLB per machine.

Conventions: metres, Blender Z up, the machine's FRONT faces -Y (the glTF exporter turns that into three's +Z).
Object-name contract read by the JS modules:
    screen_*  display glass (the module drives it with makeScreen)      led_*   indicator lenses
    glow_*    surfaces lit by the machine's voice                        metal_* runtime metal (not baked)
    part_*    baked but movable parts                                     everything else: baked static meshes
Run:  bash run_blender.sh work/daisy/props/blender/build_<machine>.py   (from the repo root)
      The runner sandboxes BLENDER_USER_RESOURCES. Never call blender.exe --factory-startup against the real user
      folder: it syncs extensions to an empty set and deletes the installed extension packages.
"""
import bpy, bmesh, math, os, sys, time
from mathutils import Vector, Matrix, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
PROPS = os.path.dirname(HERE)
TEX = os.path.join(PROPS, 'tex')
ASSETS = os.path.join(PROPS, 'assets')
DECALS = os.path.join(HERE, 'decals')
BAKE = os.path.join(HERE, '_bake_era2')          # baked maps (build cache; the GLBs embed them)
os.makedirs(ASSETS, exist_ok=True); os.makedirs(DECALS, exist_ok=True)
FONTS = 'C:/Windows/Fonts/'
T0 = time.time()


def log(*a):
    print(f'[era_bkit {time.time() - T0:6.1f}s]', *a, flush=True)


# ════════════════════════════════════════════════════════════════════ scene
def reset(ao_distance=0.025, samples=24):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    sc.unit_settings.system = 'METRIC'
    w = bpy.data.worlds.new('World'); sc.world = w
    w.light_settings.distance = ao_distance
    return sc


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def activate(ob):
    if bpy.context.view_layer.objects.active is not None and bpy.context.view_layer.objects.active.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for o in list(bpy.context.view_layer.objects):
        if o is not None: o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def mesh_obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def apply_mods(ob):
    activate(ob)
    for m in list(ob.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def xform(ob, loc=(0, 0, 0), rot=(0, 0, 0), scl=(1, 1, 1)):
    """bake a transform into the mesh data"""
    m = Matrix.LocRotScale(Vector(loc), Euler(rot).to_quaternion(), Vector(scl))
    ob.data.transform(m)
    ob.data.update()
    return ob


def duplicate(ob, name=None):
    o2 = ob.copy(); o2.data = ob.data.copy()
    if name: o2.name = name
    return link(o2)


def join(objs, name=None):
    objs = [o for o in objs if o]
    activate(objs[0])
    for o in objs[1:]:
        o.select_set(True)
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    if name: ob.name = name; ob.data.name = name
    return ob


def delete(objs):
    for o in (objs if isinstance(objs, (list, tuple)) else [objs]):
        if o and o.name in bpy.data.objects:
            bpy.data.objects.remove(o, do_unlink=True)


# ════════════════════════════════════════════════════════════════════ 2-D outlines
def rrect(w, h, r, n=6, cx=0.0, cy=0.0):
    """rounded rectangle, CCW, n segments per corner (r = 0 → sharp)"""
    r = max(0.0, min(r, w / 2 - 1e-6, h / 2 - 1e-6))
    if r <= 1e-7:
        return [(cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2), (cx - w / 2, cy - h / 2)]
    pts = []
    for (x, y, a0) in [(w / 2 - r, -h / 2 + r, -0.5), (w / 2 - r, h / 2 - r, 0.0), (-w / 2 + r, h / 2 - r, 0.5), (-w / 2 + r, -h / 2 + r, 1.0)]:
        for i in range(n + 1):
            a = (a0 + 0.5 * i / n) * math.pi
            pts.append((cx + x + math.cos(a) * r, cy + y + math.sin(a) * r))
    return pts


def fillet_poly(pts, radius, n=5):
    """round every corner of a closed polygon (list of (x,y) with per-vertex radius override as 3rd item)"""
    out = []
    N = len(pts)
    for i in range(N):
        p = pts[i]; r = p[2] if len(p) > 2 else radius
        a, b, c = Vector(pts[i - 1][:2]), Vector(p[:2]), Vector(pts[(i + 1) % N][:2])
        if r <= 1e-7:
            out.append((b.x, b.y)); continue
        da, dc = (a - b), (c - b)
        la, lc = da.length, dc.length
        rr = min(r, la * 0.45, lc * 0.45)
        p0, p1 = b + da.normalized() * rr, b + dc.normalized() * rr
        for k in range(n + 1):
            t = k / n
            q = (1 - t) ** 2 * p0 + 2 * (1 - t) * t * b + t * t * p1
            out.append((q.x, q.y))
    return out


# ════════════════════════════════════════════════════════════════════ masses
def _plane_map(axis):
    # 2-D (u, v) + extrusion coordinate w → 3-D
    if axis == 'z': return lambda u, v, w: Vector((u, v, w))
    if axis == 'y': return lambda u, v, w: Vector((u, w, v))      # profile in XZ (front view), extruded along Y
    if axis == 'x': return lambda u, v, w: Vector((w, u, v))      # profile in YZ (side view), extruded along X
    raise ValueError(axis)


def prism(name, pts, depth, axis='z', w0=None):
    """closed 2-D outline extruded by depth along axis; centred on the axis unless w0 given (start coordinate)"""
    f = _plane_map(axis)
    s = -depth / 2 if w0 is None else w0
    bm = bmesh.new()
    bot = [bm.verts.new(f(u, v, s)) for (u, v) in pts]
    top = [bm.verts.new(f(u, v, s + depth)) for (u, v) in pts]
    bm.faces.new(bot[::-1]); bm.faces.new(top)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm)


def loft(name, rings, cap0=True, cap1=True):
    """skin closed rings (lists of 3-D points, equal count); caps optional"""
    bm = bmesh.new()
    R = [[bm.verts.new(Vector(p)) for p in ring] for ring in rings]
    n = len(rings[0])
    for a, b in zip(R[:-1], R[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if cap0: bm.faces.new(R[0][::-1])
    if cap1: bm.faces.new(R[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm)


def rbox(name, w, d, h, r=0.0, n=6, loc=(0, 0, 0), zbase=False):
    """box w (x) × d (y) × h (z) with its vertical edges rounded r (other edges: chamfer later)"""
    ob = prism(name, rrect(w, d, r, n), h, 'z')
    xform(ob, (loc[0], loc[1], loc[2] + (h / 2 if zbase else 0)))
    return ob


def cyl(name, r, h, n=32, loc=(0, 0, 0), rot=(0, 0, 0)):
    pts = [(math.cos(2 * math.pi * i / n) * r, math.sin(2 * math.pi * i / n) * r) for i in range(n)]
    ob = prism(name, pts, h, 'z')
    xform(ob, loc, rot)
    return ob


# ════════════════════════════════════════════════════════════════════ modelling ops
def boolean(target, cutters, op='DIFFERENCE', mat_from_cutter=False):
    cutters = [c for c in (cutters if isinstance(cutters, (list, tuple)) else [cutters]) if c]
    if not cutters: return target
    c = join(cutters, target.name + '_cut') if len(cutters) > 1 else cutters[0]
    if not mat_from_cutter:
        c.data.materials.clear()
    m = target.modifiers.new('bool', 'BOOLEAN')
    m.operation = op; m.object = c; m.solver = 'EXACT'
    if mat_from_cutter:
        try: m.material_mode = 'TRANSFER'
        except Exception: pass
    m.use_self = len(cutters) > 1          # joined cutters overlap each other
    m.use_hole_tolerant = True
    n0 = len(target.data.vertices)
    activate(target)
    bpy.ops.object.modifier_apply(modifier=m.name)
    delete(c)
    n1 = len(target.data.vertices)
    if n1 == 0 or (op != 'INTERSECT' and n1 < n0 * 0.5):
        log(f'⚠ boolean {op} on {target.name}: {n0} → {n1} verts ({len(cutters)} cutter(s))')
    return target


def _bbox(ob):
    co = [v.co for v in ob.data.vertices]
    return [min(c[k] for c in co) for k in range(3)], [max(c[k] for c in co) for k in range(3)]


def chamfer(ob, width=0.0008, segments=3, angle=30, profile=0.5, harden=False, _try=0):
    """angle-limited bevel; self-checking: if any vertex leaves the pre-bevel bounds (a degenerate explosion on
    dense boolean geometry) the mesh is restored and the bevel retried gentler, then skipped (logged)"""
    backup = ob.data.copy()
    mn, mx = _bbox(ob)
    m = ob.modifiers.new('bevel', 'BEVEL')
    m.width = width; m.segments = segments; m.limit_method = 'ANGLE'; m.angle_limit = math.radians(angle)
    m.profile = profile; m.use_clamp_overlap = True; m.harden_normals = harden
    m.miter_outer = 'MITER_ARC' if _try == 0 else 'MITER_SHARP'
    apply_mods(ob)
    mn2, mx2 = _bbox(ob)
    tol = 0.0005
    if any(mn2[k] < mn[k] - tol or mx2[k] > mx[k] + tol for k in range(3)):
        old = ob.data; ob.data = backup; bpy.data.meshes.remove(old)
        if _try < 2:
            log(f'⚠ chamfer on {ob.name} exploded (w={width}); retrying gentler')
            return chamfer(ob, width * 0.5, max(1, segments - 1), angle + 10, profile, harden, _try + 1)
        log(f'⚠ chamfer on {ob.name} skipped (unstable geometry)')
        return ob
    bpy.data.meshes.remove(backup)
    return ob


def finish(ob, angle=38, weighted=True, planar_area=0.0001):
    """smooth by angle, then HARDEN: every coplanar face region larger than planar_area (m²) gets exactly flat
    corner normals, so booleans' sliver triangles can't streak; rounds and chamfers keep smooth normals."""
    activate(ob)
    try: bpy.ops.mesh.customdata_custom_splitnormals_clear()
    except Exception as e: log('clear normals:', e)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle))
    if not weighted:
        return ob
    me = ob.data
    cn = [tuple(c.vector) for c in me.corner_normals]
    polys = me.polygons
    edge_faces = {}
    for p in polys:
        for ek in p.edge_keys: edge_faces.setdefault(ek, []).append(p.index)
    region = [-1] * len(polys)
    nflat = 0
    for p in polys:
        if region[p.index] >= 0: continue
        n0 = p.normal.copy(); stack = [p.index]; members = []; area = 0.0
        region[p.index] = p.index
        while stack:
            i = stack.pop(); members.append(i); area += polys[i].area
            for ek in polys[i].edge_keys:
                for j in edge_faces[ek]:
                    if region[j] < 0 and polys[j].normal.dot(n0) > 0.99985:
                        region[j] = p.index; stack.append(j)
        if area >= planar_area:
            nf = tuple(n0)
            for i in members:
                for li in polys[i].loop_indices: cn[li] = nf
            nflat += len(members)
    me.normals_split_custom_set(cn)
    return ob


def delete_faces(ob, pred):
    """delete faces where pred(centre: Vector, normal: Vector) is true (buried caps, hidden backs)"""
    bm = bmesh.new(); bm.from_mesh(ob.data)
    kill = [f for f in bm.faces if pred(f.calc_center_median(), f.normal)]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    bm.to_mesh(ob.data); bm.free()
    log(f'{ob.name}: deleted {len(kill)} hidden faces')
    return ob


def triangulate(ob):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(ob.data); bm.free()


def slots(name, n, pitch, w, h, depth, axis_along='x', r=None, loc=(0, 0, 0), rot=(0, 0, 0)):
    """a row of rounded slots (cutter): each w × h (in the XZ front plane), cut depth along Y"""
    objs = []
    r = min(w, h) / 2 * 0.98 if r is None else r
    for i in range(n):
        off = (i - (n - 1) / 2) * pitch
        o = prism(f'{name}{i}', rrect(w, h, r, 5), depth, 'y')
        xform(o, (off, 0, 0) if axis_along == 'x' else (0, 0, off))
        objs.append(o)
    ob = join(objs, name)
    xform(ob, loc, rot)
    return ob


def keycap(name, wB, dB, wT, dT, h, r=0.0012, dish=0.0006, n=4, sculpt=0.0, top_rings=4):
    """keycap: rounded-rect base → smaller rounded-rect top; the top is a real dish made of concentric scaled rings
    stepping down to a centre vertex (clean quads + one fan, no n-gons to fold). x = width, y = depth, z up.
    sculpt shifts the top toward -y (the typist) for sculpted rows."""
    bm = bmesh.new()
    steps = [(0.0, wB, dB, r), (0.6, wB - (wB - wT) * 0.72, dB - (dB - dT) * 0.72, r * 1.15), (1.0, wT, dT, r * 1.35)]
    rings = []
    for t, w, d, rr in steps:
        rings.append([bm.verts.new((x, y - sculpt * t, h * t)) for (x, y) in rrect(w, d, rr, n)])
    m = len(rings[0])
    def band(a, b):
        for i in range(m):
            j = (i + 1) % m
            bm.faces.new((a[i], a[j], b[j], b[i]))
    for a, b in zip(rings[:-1], rings[1:]):
        band(a, b)
    bm.faces.new(rings[0][::-1])
    cx, cy = 0.0, -sculpt
    prev = rings[-1]
    for k in range(1, top_rings + 1):
        sc = 1.0 - k / (top_rings + 0.6)
        z = h - dish * (1.0 - sc * sc)
        ring = [bm.verts.new((cx + (v.co.x - cx) * sc, cy + (v.co.y - cy) * sc, z)) for v in rings[-1]]
        band(prev, ring)
        prev = ring
    c = bm.verts.new((cx, cy, h - dish))
    for i in range(m):
        bm.faces.new((prev[i], prev[(i + 1) % m], c))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm)


def screw(name, r=0.0028, loc=(0, 0, 0), rot=(0, 0, 0), recess=True):
    """pan-head Phillips screw head (metal_*), axis +Z out of the surface"""
    head = loft(name, [[(math.cos(a) * r, math.sin(a) * r, 0) for a in [2 * math.pi * i / 24 for i in range(24)]],
                       [(math.cos(a) * r * 0.97, math.sin(a) * r * 0.97, r * 0.35) for a in [2 * math.pi * i / 24 for i in range(24)]],
                       [(math.cos(a) * r * 0.7, math.sin(a) * r * 0.7, r * 0.55) for a in [2 * math.pi * i / 24 for i in range(24)]]])
    c1 = rbox('x1', r * 1.3, r * 0.28, r * 0.8, 0, loc=(0, 0, r * 0.55))
    c2 = rbox('x2', r * 0.28, r * 1.3, r * 0.8, 0, loc=(0, 0, r * 0.55))
    boolean(head, [c1, c2])
    xform(head, loc, rot)
    return head


def cable(name, points, radius=0.0012, res=6):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'
    sp = cu.splines.new('POLY'); sp.points.add(len(points) - 1)
    for p, q in zip(sp.points, points): p.co = (q[0], q[1], q[2], 1)
    cu.bevel_depth = radius; cu.bevel_resolution = 2; cu.use_fill_caps = True
    ob = link(bpy.data.objects.new(name, cu))
    activate(ob)
    bpy.ops.object.convert(target='MESH')
    return bpy.context.view_layer.objects.active


def fillet_path(pts, radius, n=6):
    """open 3-D polyline with every interior corner rounded by a quadratic fillet"""
    P = [Vector(p) for p in pts]
    out = [tuple(P[0])]
    for i in range(1, len(P) - 1):
        a, b, c = P[i - 1], P[i], P[i + 1]
        ra = min(radius, (a - b).length * 0.45); rc = min(radius, (c - b).length * 0.45)
        p0 = b + (a - b).normalized() * ra; p1 = b + (c - b).normalized() * rc
        for k in range(n + 1):
            t = k / n
            out.append(tuple((1 - t) ** 2 * p0 + 2 * (1 - t) * t * b + t * t * p1))
    out.append(tuple(P[-1]))
    return out


def smooth_path(pts, n=12):
    """Catmull-Rom resample of a polyline"""
    P = [Vector(p) for p in pts]
    out = []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = P[max(i - 1, 0)], P[i], P[i + 1], P[min(i + 2, len(P) - 1)]
        for k in range(n):
            t = k / n
            q = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)
            out.append(tuple(q))
    out.append(tuple(P[-1]))
    return out


# ════════════════════════════════════════════════════════════════════ materials (bake sources)
_IMG = {}


def image(path, noncolor=False):
    key = (path, noncolor)
    if key not in _IMG:
        im = bpy.data.images.load(path, check_existing=True)
        if noncolor: im.colorspace_settings.name = 'Non-Color'
        _IMG[key] = im
    return _IMG[key]


_LUMA = {}


def mean_luma(path):
    if path not in _LUMA:
        from PIL import Image
        import numpy as np
        a = np.asarray(Image.open(path).convert('L').resize((128, 128)), dtype=np.float32) / 255.0
        _LUMA[path] = float(a.mean())
    return _LUMA[path]


def pbr(name):
    d = os.path.join(TEX, name)
    return {k: os.path.join(d, f'{name}_{v}.jpg') for k, v in
            [('color', 'Color'), ('rough', 'Roughness'), ('normal', 'NormalGL'), ('disp', 'Displacement')]}


class NT:
    """tiny node-tree builder"""
    def __init__(self, mat):
        self.nt = mat.node_tree; self.n = self.nt.nodes; self.l = self.nt.links
        self.x = -1400

    def node(self, kind, **props):
        nd = self.n.new(kind)
        nd.location = (self.x, 0); self.x += 40
        for k, v in props.items(): setattr(nd, k, v)
        return nd

    def link(self, a, b):
        self.l.new(a, b)

    def val(self, v):
        nd = self.node('ShaderNodeValue'); nd.outputs[0].default_value = v; return nd.outputs[0]

    def rgb(self, c):
        nd = self.node('ShaderNodeRGB'); nd.outputs[0].default_value = (*c, 1.0); return nd.outputs[0]

    def math(self, op, a, b=None, clamp=False):
        nd = self.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        for i, v in enumerate([a, b]):
            if v is None: continue
            if isinstance(v, (int, float)): nd.inputs[i].default_value = v
            else: self.link(v, nd.inputs[i])
        return nd.outputs[0]

    def mixc(self, fac, a, b):
        nd = self.node('ShaderNodeMix', data_type='RGBA', clamp_factor=True)
        for sock, v in [(nd.inputs[0], fac), (nd.inputs[6], a), (nd.inputs[7], b)]:
            if isinstance(v, (int, float)): sock.default_value = v
            elif isinstance(v, tuple): sock.default_value = (*v, 1.0) if len(v) == 3 else v
            else: self.link(v, sock)
        return nd.outputs[2]

    def mixf(self, fac, a, b):
        nd = self.node('ShaderNodeMix', data_type='FLOAT', clamp_factor=True)
        for sock, v in [(nd.inputs[0], fac), (nd.inputs[2], a), (nd.inputs[3], b)]:
            if isinstance(v, (int, float)): sock.default_value = v
            else: self.link(v, sock)
        return nd.outputs[0]

    def maprange(self, v, a0, a1, b0, b1, clamp=True):
        nd = self.node('ShaderNodeMapRange', clamp=clamp)
        self.link(v, nd.inputs[0])
        for i, x in zip(range(1, 5), [a0, a1, b0, b1]): nd.inputs[i].default_value = x
        return nd.outputs[0]

    def luma(self, col):
        nd = self.node('ShaderNodeRGBToBW'); self.link(col, nd.inputs[0]); return nd.outputs[0]

    def boxtex(self, path, scale, noncolor=False, blend=0.25):
        tc = self.node('ShaderNodeTexCoord')
        mp = self.node('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (scale, scale, scale)
        self.link(tc.outputs['Object'], mp.inputs['Vector'])
        tx = self.node('ShaderNodeTexImage', projection='BOX', projection_blend=blend, extension='REPEAT')
        tx.image = image(path, noncolor)
        self.link(mp.outputs['Vector'], tx.inputs['Vector'])
        return tx


def plastic(name, tint, *, pbrname='Plastic013B', tile=5.0, texmix=0.2, rough=(0.30, 0.62), aged=None, age=0.3,
            grime=(0.20, 0.17, 0.12), grime_amt=0.65, ao_dist=0.02, edge=0.22, dust=(0.62, 0.60, 0.55), dust_amt=0.10,
            bump=0.25, decals=(), scratch=0.5, metallic=0.0, emission=None):
    """a bake-source moulded-plastic material. tint is linear RGB (use lin()).
    decals: list of dict(img=path, proj=empty, rough=None|float, mode='mix'|'mul')"""
    lum = lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    if lum(grime) > lum(tint) * 0.6:                  # grime is always darker than the plastic it soils
        k = lum(tint) * 0.45 / max(lum(grime), 1e-4)
        grime = tuple(g * k for g in grime)
    if lum(dust) > lum(tint) * 3 and lum(tint) < 0.05:
        dust_amt = min(dust_amt, 0.05)                 # dark plastics: a whisper of dust, not speckle
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    t = NT(mat)
    bsdf = t.n['Principled BSDF']; bsdf.location = (400, 0)
    P = pbr(pbrname)
    col = t.boxtex(P['color'], tile)
    rgh = t.boxtex(P['rough'], tile, True)
    dsp = t.boxtex(P['disp'], tile, True)
    grm = t.boxtex(pbr('Plastic018B')['color'], tile * 0.45)
    # texture variation around the tint (the albedo's luminance, normalised around its mean)
    L = t.luma(col.outputs['Color'])
    var = t.math('ADD', t.math('MULTIPLY', t.math('SUBTRACT', L, mean_luma(P['color'])), texmix / max(mean_luma(P['color']), 0.05)), 1.0)
    var = t.math('MAXIMUM', t.math('MINIMUM', var, 1.5), 0.6)
    base = t.node('ShaderNodeVectorMath', operation='SCALE')
    t.link(t.rgb(tint), base.inputs[0]); t.link(var, base.inputs['Scale'])
    c = base.outputs[0]
    geo = t.node('ShaderNodeNewGeometry')
    nz = t.node('ShaderNodeSeparateXYZ'); t.link(geo.outputs['Normal'], nz.inputs[0])
    up = t.maprange(nz.outputs['Z'], 0.35, 1.0, 0.0, 1.0)
    # ageing / yellowing: broad noise + up-facing bias
    if aged is not None:
        nzs = t.node('ShaderNodeTexNoise'); nzs.inputs['Scale'].default_value = 6.0; nzs.inputs['Detail'].default_value = 3.0
        tc = t.node('ShaderNodeTexCoord'); t.link(tc.outputs['Object'], nzs.inputs['Vector'])
        m = t.math('ADD', t.maprange(nzs.outputs['Fac'], 0.35, 0.7, 0.0, 0.8), t.math('MULTIPLY', up, 0.45))
        c = t.mixc(t.math('MULTIPLY', m, age, clamp=True), c, aged)
    # grime in occluded places, broken up by a dirty-plastic scan
    ao = t.node('ShaderNodeAmbientOcclusion', samples=16); ao.inputs['Distance'].default_value = ao_dist
    occl = t.math('POWER', t.math('SUBTRACT', 1.0, ao.outputs['AO']), 1.4)
    brk = t.maprange(t.luma(grm.outputs['Color']), 0.25, 0.75, 0.35, 1.0)
    gmask = t.math('MULTIPLY', t.math('MULTIPLY', occl, brk), grime_amt * 1.6, clamp=True)
    c = t.mixc(gmask, c, grime)
    # convex edges: slightly paler, polished
    pnt = t.maprange(geo.outputs['Pointiness'], 0.5, 0.56, 0.0, 1.0)
    lighter = t.node('ShaderNodeVectorMath', operation='SCALE'); t.link(c, lighter.inputs[0]); lighter.inputs['Scale'].default_value = 1.18
    c = t.mixc(t.math('MULTIPLY', pnt, edge), c, lighter.outputs[0])
    # dust on up-facing surfaces
    if dust_amt > 0:
        dn = t.node('ShaderNodeTexNoise'); dn.inputs['Scale'].default_value = 60.0; dn.inputs['Detail'].default_value = 6.0
        tc2 = t.node('ShaderNodeTexCoord'); t.link(tc2.outputs['Object'], dn.inputs['Vector'])
        dm = t.math('MULTIPLY', t.math('MULTIPLY', up, t.maprange(dn.outputs['Fac'], 0.45, 0.7, 0.0, 1.0)), dust_amt, clamp=True)
        c = t.mixc(dm, c, dust)
    # roughness: scan roughness remapped, scratches read smoother/rougher, edges polished, grime/dust matte
    r = t.maprange(rgh.outputs['Color'], 0.0, 1.0, rough[0], rough[1])
    r = t.math('ADD', r, t.math('MULTIPLY', gmask, 0.25))
    r = t.math('SUBTRACT', r, t.math('MULTIPLY', pnt, 0.12 * edge / 0.22))
    # decals (printed/pad-printed labels), projected by empties
    for d in decals:
        c, r = _decal(t, d, c, r, geo)
    t.link(c, bsdf.inputs['Base Color'])
    t.link(t.math('MAXIMUM', t.math('MINIMUM', r, 1.0), 0.03), bsdf.inputs['Roughness'])
    bsdf.inputs['Metallic'].default_value = metallic
    bmp = t.node('ShaderNodeBump'); bmp.inputs['Strength'].default_value = bump; bmp.inputs['Distance'].default_value = 0.0004
    t.link(dsp.outputs['Color'], bmp.inputs['Height'])
    t.link(bmp.outputs['Normal'], bsdf.inputs['Normal'])
    mat['era_role'] = 'plastic'
    return mat


def _decal(t, d, c, r, geo):
    tc = t.node('ShaderNodeTexCoord'); tc.object = d['proj']
    sep = t.node('ShaderNodeSeparateXYZ'); t.link(tc.outputs['Object'], sep.inputs[0])
    u = t.maprange(sep.outputs['X'], -1.0, 1.0, 0.0, 1.0, clamp=False)
    v = t.maprange(sep.outputs['Y'], -1.0, 1.0, 0.0, 1.0, clamp=False)
    comb = t.node('ShaderNodeCombineXYZ'); t.link(u, comb.inputs[0]); t.link(v, comb.inputs[1])
    tx = t.node('ShaderNodeTexImage', extension='CLIP', interpolation='Cubic'); tx.image = image(d['img'])
    t.link(comb.outputs[0], tx.inputs['Vector'])
    # facing: only faces turned toward the projector's +Z (normal world · proj axis); depth: |z| < 1
    ax = d['proj'].matrix_world.to_3x3() @ Vector((0, 0, 1)); ax.normalize()
    dp = t.node('ShaderNodeVectorMath', operation='DOT_PRODUCT'); dp.inputs[1].default_value = ax
    t.link(geo.outputs['Normal'], dp.inputs[0])
    face = t.maprange(dp.outputs['Value'], d.get('face0', 0.35), d.get('face1', 0.6), 0.0, 1.0)
    depth = t.maprange(t.math('ABSOLUTE', sep.outputs['Z']), 0.95, 1.0, 1.0, 0.0)
    a = t.math('MULTIPLY', t.math('MULTIPLY', tx.outputs['Alpha'], face), depth)
    if d.get('opacity', 1.0) != 1.0: a = t.math('MULTIPLY', a, d['opacity'])
    if d.get('mode', 'mix') == 'mul':
        mul = t.node('ShaderNodeMix', data_type='RGBA', blend_type='MULTIPLY', clamp_factor=True)
        t.link(a, mul.inputs[0]); t.link(c, mul.inputs[6]); t.link(tx.outputs['Color'], mul.inputs[7])
        c = mul.outputs[2]
    else:
        c = t.mixc(a, c, tx.outputs['Color'])
    if d.get('rough') is not None:
        r = t.mixf(a, r, d['rough'])
    return c, r


def projector(name, center, size, normal=(0, -1, 0), up=(0, 0, 1), depth=0.01):
    """an empty whose local XY spans the decal (size w,h) on a surface facing `normal`; image u → local +X"""
    e = link(bpy.data.objects.new(name, None))
    n = Vector(normal).normalized(); upv = Vector(up).normalized()
    xax = upv.cross(n).normalized(); yax = n.cross(xax).normalized()
    m = Matrix((xax, yax, n)).transposed().to_4x4()
    e.matrix_world = Matrix.Translation(Vector(center)) @ m @ Matrix.Diagonal((size[0] / 2, size[1] / 2, depth, 1.0))
    bpy.context.view_layer.update()
    return e


def rubber(name, tint=(0.02, 0.02, 0.02)):
    return plastic(name, tint, pbrname='Rubber004', tile=12, texmix=0.3, rough=(0.7, 0.95), grime_amt=0.3, edge=0.1, dust_amt=0.25, bump=0.4)


def assign(ob, mat):
    ob.data.materials.clear(); ob.data.materials.append(mat)
    return ob


def lin(hexstr):
    """sRGB hex → linear tuple"""
    h = hexstr.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


# ════════════════════════════════════════════════════════════════════ decal images (PIL)
def decal_png(name, w, h, draw):
    """draw(img, drawer, font) on an RGBA canvas, transparent background; returns the path"""
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    def font(size, bold=True, face='arial'):
        f = {'arial': ('arialbd.ttf' if bold else 'arial.ttf'), 'tahoma': ('tahomabd.ttf' if bold else 'tahoma.ttf'),
             'segoe': ('segoeuib.ttf' if bold else 'segoeui.ttf'), 'consola': ('consolab.ttf' if bold else 'consola.ttf')}[face]
        return ImageFont.truetype(FONTS + f, max(4, int(size)))
    draw(im, dr, font)
    p = os.path.join(DECALS, name + '.png')
    im.save(p)
    return p


# ════════════════════════════════════════════════════════════════════ UV, bake, export
def uv_atlas(ob, angle=62, margin=0.004):
    activate(ob)
    while ob.data.uv_layers: ob.data.uv_layers.remove(ob.data.uv_layers[0])
    ob.data.uv_layers.new(name='atlas')
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode='OBJECT')


def uv_planar(ob, x0, y0, x1, y1, plane='xz'):
    """planar UV across a rectangle in the given plane (screens): u → +first axis, v → +second axis"""
    me = ob.data
    while me.uv_layers: me.uv_layers.remove(me.uv_layers[0])
    uvl = me.uv_layers.new(name='atlas')
    ia, ib = {'x': 0, 'y': 1, 'z': 2}[plane[0]], {'x': 0, 'y': 1, 'z': 2}[plane[1]]
    for loop in me.loops:
        co = me.vertices[loop.vertex_index].co
        uvl.data[loop.index].uv = ((co[ia] - x0) / (x1 - x0), (co[ib] - y0) / (y1 - y0))


QUICK = os.environ.get('ERA_QUICK') == '1'
# normal: 16 samples, never 1 -- the scan bump is finer than a texel; one sample per texel point-samples it into
# per-texel white noise (a 'granite' speckle under grazing light). Averaged, the map keeps texel-scale relief only.
PASS_SAMPLES = {'color': 48, 'rough': 16, 'normal': 16, 'ao': 48}


DATA_SCALE = {'color': 1.0, 'rough': 0.5, 'normal': 0.5, 'ao': 0.5}   # colour carries print + legends; data maps at half


def bake(ob, prefix, size=2048, passes=('color', 'rough', 'normal', 'ao'), margin=10, samples=None):
    sc = bpy.context.scene
    if QUICK: size = max(128, size // 4)
    base_size = size
    sc.render.bake.margin = margin
    sc.render.bake.use_clear = True
    activate(ob)
    out = {}
    for p in passes:
        imname = f'{prefix}_{p}'
        size = max(64, int(base_size * DATA_SCALE.get(p, 1.0)))
        im = bpy.data.images.new(imname, size, size, alpha=False)
        if p != 'color': im.colorspace_settings.name = 'Non-Color'
        nodes = []
        for slot in ob.material_slots:
            nt = slot.material.node_tree
            tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = im; tn.select = True; nt.nodes.active = tn
            nodes.append((nt, tn))
        t1 = time.time()
        sc.cycles.samples = 2 if QUICK else (samples or PASS_SAMPLES[p])
        if p == 'color': bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, margin=margin, use_clear=True)
        elif p == 'rough': bpy.ops.object.bake(type='ROUGHNESS', margin=margin, use_clear=True)
        elif p == 'normal': bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', margin=margin, use_clear=True)
        elif p == 'ao': bpy.ops.object.bake(type='AO', margin=margin, use_clear=True)
        ext = '.jpg' if p == 'color' else '.png'
        path = os.path.join(BAKE, f'{prefix}_{p}{ext}')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        im.filepath_raw = path
        im.file_format = 'JPEG' if ext == '.jpg' else 'PNG'
        if ext == '.jpg': sc.render.image_settings.quality = 92
        im.save()
        log(f'baked {prefix}_{p} {size}² in {time.time() - t1:.1f}s')
        for nt, tn in nodes: nt.nodes.remove(tn)
        out[p] = im
    return out


def _gltf_settings_group():
    g = bpy.data.node_groups.get('glTF Material Output')
    if g: return g
    g = bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
    g.interface.new_socket('Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
    g.interface.new_socket('Thickness', in_out='INPUT', socket_type='NodeSocketFloat')
    return g


def export_material(name, maps, metallic=0.0):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    nt = mat.node_tree; n = nt.nodes; l = nt.links
    b = n['Principled BSDF']
    tc = n.new('ShaderNodeTexImage'); tc.image = maps['color']; l.new(tc.outputs['Color'], b.inputs['Base Color'])
    if 'rough' in maps:
        tr = n.new('ShaderNodeTexImage'); tr.image = maps['rough']
        sep = n.new('ShaderNodeSeparateColor'); l.new(tr.outputs['Color'], sep.inputs[0]); l.new(sep.outputs['Red'], b.inputs['Roughness'])
    b.inputs['Metallic'].default_value = metallic
    if 'normal' in maps:
        tn = n.new('ShaderNodeTexImage'); tn.image = maps['normal']
        nm = n.new('ShaderNodeNormalMap'); l.new(tn.outputs['Color'], nm.inputs['Color']); l.new(nm.outputs['Normal'], b.inputs['Normal'])
    if 'ao' in maps:
        ta = n.new('ShaderNodeTexImage'); ta.image = maps['ao']
        sep2 = n.new('ShaderNodeSeparateColor'); l.new(ta.outputs['Color'], sep2.inputs[0])
        gg = n.new('ShaderNodeGroup'); gg.node_tree = _gltf_settings_group()
        l.new(sep2.outputs['Red'], gg.inputs['Occlusion'])
    return mat


def simple_material(name, color=(0.5, 0.5, 0.5), rough=0.5, metallic=0.0):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    b = mat.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1); b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metallic
    return mat


def export_glb(objs, name):
    for o in bpy.context.view_layer.objects: o.select_set(False)
    for o in objs: o.select_set(True)
    path = os.path.join(ASSETS, name + '.glb')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_apply=True,
                              export_texcoords=True, export_normals=True, export_materials='EXPORT',
                              export_image_format='AUTO', export_extras=False, export_yup=True)
    log(f'exported {path} ({os.path.getsize(path) / 1e6:.1f} MB)')
    return path


def sanity(objs, limit=2.0):
    """log each object's bbox; delete vertices that exploded far outside the model (bevel/solidify degeneracies)"""
    for o in objs:
        if o.type != 'MESH' or not o.data.vertices: continue
        co = [v.co for v in o.data.vertices]
        bad = [i for i, c in enumerate(co) if max(abs(c.x), abs(c.y), abs(c.z)) > limit or c.x != c.x]
        mn = [min(c[k] for c in co) for k in range(3)]; mx = [max(c[k] for c in co) for k in range(3)]
        log(f'{o.name}: {len(co)} verts bbox {[round(v, 3) for v in mn]} {[round(v, 3) for v in mx]}' + (f'  ⚠ {len(bad)} exploded verts removed' if bad else ''))
        if bad:
            bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[bm.verts[i] for i in bad], context='VERTS')
            bm.to_mesh(o.data); bm.free()


def stats(objs):
    tris = 0
    for o in objs:
        if o.type == 'MESH':
            tris += sum(len(p.vertices) - 2 for p in o.data.polygons)
    return tris
