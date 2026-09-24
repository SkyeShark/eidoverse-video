# build_robot.py — the classic science-fiction movie robot ARCHETYPE for DAISY verse 3 (robot.glb).
# Generic by construction (no specific film/toy design): rounded box head with a recessed visor, two round
# lenses, a slotted mouth grille, ear discs and twin antennae; a chunky tapered box torso with a recessed
# chest panel carrying three gauges, four indicator domes and a slotted speaker; shoulder balls; ribbed
# bellows arms ending in pincer claws; a ribbed waist; lathe legs with bellows knees; heavy soled feet.
# Face-modelled masses (inset / extrude / bevel / boolean on ONE mass per part); separate objects only for
# genuinely separate hardware (lenses, gauge glass + needles, domes, antennae, bolts).
# 2.2 m to the antenna tips, origin between the feet on the ground, faces glTF +Z (Blender -Y).
#
#   blender --background --factory-startup --python build_robot.py -- <out_dir> [clay|final]
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else '.')
STAGE = argv[1] if len(argv) > 1 else 'clay'
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
COL = bpy.data.collections.new('robot'); bpy.context.scene.collection.children.link(COL)
PARTS = {}          # name -> (object, role) ; role: paint | trim | rubber | lens | light | dark

def link(ob, role):
    COL.objects.link(ob); PARTS[ob.name] = (ob, role); return ob

def mesh_from_bm(name, bm, role, smooth=True):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = smooth
    return link(bpy.data.objects.new(name, me), role)

def faces_facing(bm, d, tol=0.9):
    return [f for f in bm.faces if f.normal.dot(d) > tol]

def bevel_all(bm, width, segs, angle_deg=30.0, prof=0.5):
    bm.normal_update()
    edges = [e for e in bm.edges if e.is_manifold and e.calc_face_angle(0) > math.radians(angle_deg)]
    if edges:
        bmesh.ops.bevel(bm, geom=edges, offset=width, offset_type='OFFSET', segments=segs, profile=prof,
                        affect='EDGES', clamp_overlap=True)

def box_bm(size, center=(0, 0, 0), taper_bottom=1.0):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
        if v.co.z < 0 and taper_bottom != 1.0: v.co.x *= taper_bottom
        v.co += Vector(center)
    return bm

def recess(bm, face, inset, depth, frame=0.0):
    """Face-model a recessed panel: inset the face (optionally twice for a frame lip), push the centre in."""
    r = bmesh.ops.inset_region(bm, faces=[face], thickness=inset, depth=0.0, use_even_offset=True)
    core = [face]
    if frame:
        r2 = bmesh.ops.inset_region(bm, faces=core, thickness=frame, depth=0.0, use_even_offset=True)
    n = face.normal.copy()
    bmesh.ops.translate(bm, verts=list(face.verts), vec=-n * depth)
    return face

def lathe_bm(profile, segs=40, center=(0, 0, 0), axis='Z', cap=True):
    """profile: list of (radius, height). Returns a closed bmesh solid of revolution."""
    bm = bmesh.new(); rings = []
    for (r, h) in profile:
        ring = []
        for k in range(segs):
            a = 2 * math.pi * k / segs
            p = Vector((r * math.cos(a), r * math.sin(a), h))
            if axis == 'X': p = Vector((p.z, p.x, p.y))
            ring.append(bm.verts.new(p + Vector(center)))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(segs):
            a, b = rings[i][k], rings[i][(k + 1) % segs]
            c, d = rings[i + 1][(k + 1) % segs], rings[i + 1][k]
            bm.faces.new((a, b, c, d))
    if cap:
        bm.faces.new(list(reversed(rings[0]))); bm.faces.new(rings[-1])
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-6)
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return bm

def tube_bm(path_pts, radius_fn, segs=28, cap=True):
    """Sweep a circle along a polyline with rotation-minimising frames; radius_fn(s_metres)."""
    pts = [Vector(p) for p in path_pts]
    L = [0.0]
    for i in range(1, len(pts)): L.append(L[-1] + (pts[i] - pts[i - 1]).length)
    bm = bmesh.new(); rings = []
    t0 = (pts[1] - pts[0]).normalized()
    ref = Vector((0, 0, 1)) if abs(t0.z) < 0.9 else Vector((1, 0, 0))
    nrm = (ref - t0 * ref.dot(t0)).normalized()
    prev_t = t0
    for i, p in enumerate(pts):
        if i == 0: t = t0
        elif i == len(pts) - 1: t = (pts[i] - pts[i - 1]).normalized()
        else: t = (pts[i + 1] - pts[i - 1]).normalized()
        # rotation-minimising: rotate the previous normal by the rotation prev_t -> t
        q = prev_t.rotation_difference(t); nrm = (q @ nrm).normalized(); prev_t = t
        bin_ = t.cross(nrm)
        r = radius_fn(L[i])
        ring = [bm.verts.new(p + (nrm * math.cos(2 * math.pi * k / segs) + bin_ * math.sin(2 * math.pi * k / segs)) * r)
                for k in range(segs)]
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(segs):
            bm.faces.new((rings[i][k], rings[i][(k + 1) % segs], rings[i + 1][(k + 1) % segs], rings[i + 1][k]))
    if cap:
        bm.faces.new(list(reversed(rings[0]))); bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return bm

def bezier_path(p0, p1, p2, p3, n):
    out = []
    for i in range(n + 1):
        t = i / n; u = 1 - t
        out.append(p0 * u ** 3 + p1 * 3 * u * u * t + p2 * 3 * u * t * t + p3 * t ** 3)
    return out

def boolean(target, cutters, op='DIFFERENCE'):
    for c in cutters:
        n0 = len(target.data.polygons)
        m = target.modifiers.new('b', 'BOOLEAN'); m.operation = op; m.solver = 'EXACT'; m.object = c
        bpy.context.view_layer.objects.active = target
        bpy.ops.object.modifier_apply(modifier=m.name)
        if len(target.data.polygons) == n0:
            print('BOOL-NOOP', target.name, tuple(round(x, 3) for x in c.location))
        bpy.data.objects.remove(c, do_unlink=True)

def cutter_cyl(r, depth, loc, rot=(math.pi / 2, 0, 0), segs=40):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=depth)
    me = bpy.data.meshes.new('cut'); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new('cut', me); bpy.context.scene.collection.objects.link(ob)
    ob.location = loc; ob.rotation_euler = rot; ob.hide_render = True
    return ob

def cutter_box(size, loc):
    bm = box_bm(size); me = bpy.data.meshes.new('cutb'); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new('cutb', me); bpy.context.scene.collection.objects.link(ob)
    ob.location = loc; ob.hide_render = True
    return ob

FRONT = Vector((0, -1, 0))

# ======================================================================= TORSO (one mass)
TZ0, TZ1 = 1.07, 1.73
tw, td, th = 0.66, 0.42, TZ1 - TZ0
bm = box_bm((tw, td, th), (0, 0, (TZ0 + TZ1) / 2), taper_bottom=0.86)
bevel_all(bm, 0.045, 5, angle_deg=60)          # the big silhouette rounding FIRST
bm.normal_update()
front = max(faces_facing(bm, FRONT, 0.99), key=lambda f: f.calc_area())
# chest panel: inset (frame lip) + recess
bmesh.ops.inset_region(bm, faces=[front], thickness=0.045, depth=0.0, use_even_offset=True)
bmesh.ops.inset_region(bm, faces=[front], thickness=0.014, depth=0.0, use_even_offset=True)
bmesh.ops.translate(bm, verts=list(front.verts), vec=Vector((0, 0.028, 0)))
PANEL = (min(v.co.x for v in front.verts), max(v.co.x for v in front.verts), min(v.co.z for v in front.verts), max(v.co.z for v in front.verts))
# back: a hatch plate recess
back = max(faces_facing(bm, -FRONT, 0.99), key=lambda f: f.calc_area())
bmesh.ops.inset_region(bm, faces=[back], thickness=0.08, depth=0.0, use_even_offset=True)
bmesh.ops.translate(bm, verts=list(back.verts), vec=Vector((0, -0.012, 0)))
HATCH = (min(v.co.x for v in back.verts), max(v.co.x for v in back.verts), min(v.co.z for v in back.verts), max(v.co.z for v in back.verts), back.verts[0].co.y)
# side plates: inset the side faces and push in slightly (the shoulder balls sit on them)
for sgn in (-1, 1):
    side = max(faces_facing(bm, Vector((sgn, 0, 0)), 0.8), key=lambda f: f.calc_area())
    bmesh.ops.inset_region(bm, faces=[side], thickness=0.05, depth=0.0, use_even_offset=True)
    bmesh.ops.translate(bm, verts=list(side.verts), vec=Vector((-sgn * 0.012, 0, 0)))
bevel_all(bm, 0.006, 2, angle_deg=35)          # machining on the recess walls
torso = mesh_from_bm('torso', bm, 'paint')
# gauges: three round recesses in the chest panel, and four light sockets, and a speaker grille
py = -td / 2 + 0.028                          # panel plane y (recessed)
cuts = []
for i, x in enumerate((-0.14, 0.0, 0.14)):
    cuts.append(cutter_cyl(0.052 if i == 1 else 0.044, 0.05, (x, py, 1.53 if i != 1 else 1.55)))
for i in range(4):
    cuts.append(cutter_cyl(0.017, 0.04, (-0.105 + i * 0.07, py, 1.415)))
for k in range(4):
    cuts.append(cutter_box((0.22, 0.05, 0.011), (0, py, 1.315 - k * 0.026)))
boolean(torso, cuts)                           # gauges, light sockets, speaker grille
hx0, hx1, hz0, hz1, hy = HATCH
cuts = [cutter_box((hx1 - hx0 - 0.09, 0.05, 0.014), (0, hy, hz1 - 0.07 - k * 0.036)) for k in range(5)]
boolean(torso, cuts)
# hardware: rivets on the chest-panel frame, bolts at the hatch corners (seated measured, not typed)
def dome(name, r, loc, face_dir, flat=0.45, role='trim', segs=16):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=max(6, segs // 2), radius=r)
    for v in bm.verts:
        d = v.co.dot(face_dir)
        if d < 0: v.co -= face_dir * d                 # flat back (sits on the surface)
        else: v.co -= face_dir * (d * (1 - flat))      # a low dome
    ob = mesh_from_bm(name, bm, role); ob.location = loc; return ob
px0, px1, pz0, pz1 = PANEL
off = 0.014 + 0.045 / 2
xs = (px0 - off, (px0 + px1) / 2, px1 + off); zs = (pz0 - off, (pz0 + pz1) / 2, pz1 + off)
k = 0
for x in xs:
    for z in zs:
        if x == xs[1] and z == zs[1]: continue
        dome(f'rivet_{k}', 0.0095, (x, -td / 2 + 0.0005, z), FRONT); k += 1
for x in (hx0 + 0.028, hx1 - 0.028):
    for z in (hz0 + 0.028, hz1 - 0.028):
        bm = lathe_bm([(0.0, 0.0), (0.016, 0.0), (0.016, 0.006), (0.012, 0.011), (0.0, 0.012)], segs=6, cap=False)
        b = mesh_from_bm(f'bolt_{x:+.2f}_{z:.2f}', bm, 'trim')
        b.rotation_euler = (-math.pi / 2, 0, 0); b.location = (x, hy - 0.0005, z)

# gauge hardware (separate: bezel rings + glass + needles), light domes
def gauge(x, z, r):
    bm = lathe_bm([(r * 0.78, 0.0), (r * 1.02, 0.0), (r * 1.06, 0.008), (r * 1.02, 0.016), (r * 0.86, 0.016),
                   (r * 0.80, 0.006), (r * 0.78, 0.0)], segs=40, center=(0, 0, 0), cap=False)
    ob = mesh_from_bm(f'gauge_bezel_{x:+.2f}', bm, 'trim')
    ob.rotation_euler = (math.pi / 2, 0, 0); ob.location = (x, py - 0.006, z)
    bmf = bmesh.new(); bmesh.ops.create_circle(bmf, cap_ends=True, segments=40, radius=r * 0.8)
    face = mesh_from_bm(f'gauge_face_{x:+.2f}', bmf, 'dark')
    face.rotation_euler = (math.pi / 2, 0, 0); face.location = (x, py + 0.004, z)
    bmn = box_bm((0.006, 0.004, r * 0.7), (0, 0, r * 0.3))
    needle = mesh_from_bm(f'gauge_needle_{x:+.2f}', bmn, 'light')
    needle.location = (x, py - 0.001, z); needle.rotation_euler = (0, math.radians(35 + 40 * x * 10), 0)
for i, x in enumerate((-0.14, 0.0, 0.14)):
    gauge(x, 1.53 if i != 1 else 1.55, 0.052 if i == 1 else 0.044)
for i in range(4):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=0.016)
    for v in bm.verts:
        if v.co.y > 0.004: v.co.y = 0.004
    ob = mesh_from_bm(f'light_{i}', bm, 'light'); ob.location = (-0.105 + i * 0.07, py - 0.002, 1.415)

# ======================================================================= NECK + HEAD
neck_prof = [(0.080, 1.715), (0.082, 1.73), (0.090, 1.742), (0.078, 1.754), (0.090, 1.766), (0.078, 1.778), (0.086, 1.79)]
link_neck = mesh_from_bm('neck', lathe_bm(neck_prof, segs=40), 'rubber')
HZ0, HZ1 = 1.785, 2.095
hw, hd, hh = 0.44, 0.36, HZ1 - HZ0
bm = box_bm((hw, hd, hh), (0, 0, (HZ0 + HZ1) / 2))
bevel_all(bm, 0.05, 6, angle_deg=60)
bm.normal_update()
htop = max(faces_facing(bm, Vector((0, 0, 1)), 0.99), key=lambda f: f.calc_area())
# a crown: the top face insets and rises a little (a lid)
bmesh.ops.inset_region(bm, faces=[htop], thickness=0.03, depth=0.0, use_even_offset=True)
bmesh.ops.translate(bm, verts=list(htop.verts), vec=Vector((0, 0, 0.016)))
bevel_all(bm, 0.005, 2, angle_deg=30)
head = mesh_from_bm('head', bm, 'paint')
# visor band + eye sockets + mouth grille, all boolean recesses into the one head mass
fy = -hd / 2
cuts = [cutter_box((0.37, 0.04, 0.128), (0, fy, 1.975))]
boolean(head, cuts)
cuts = [cutter_cyl(0.047, 0.07, (sx * 0.098, fy + 0.01, 1.975)) for sx in (-1, 1)]
cuts += [cutter_box((0.18, 0.05, 0.011), (0, fy, 1.878 - k * 0.022)) for k in range(4)]
boolean(head, cuts)
# lenses (separate): convex red glass caps, with trim bezel rings
for sx in (-1, 1):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=0.05)
    for v in bm.verts: v.co.y = min(v.co.y, 0.0) * 0.55
    lens = mesh_from_bm(f'lens_{"L" if sx > 0 else "R"}', bm, 'lens'); lens.location = (sx * 0.098, fy + 0.03, 1.975)
    bmr = lathe_bm([(0.046, 0.0), (0.054, 0.0), (0.057, 0.010), (0.053, 0.019), (0.047, 0.019), (0.046, 0.0)],
                   segs=40, cap=False)
    ring = mesh_from_bm(f'lens_bezel_{"L" if sx > 0 else "R"}', bmr, 'trim')
    ring.rotation_euler = (math.pi / 2, 0, 0); ring.location = (sx * 0.098, fy + 0.017, 1.975)
# ear discs (one lathe mass each) + antennae (rod + ball, separate hardware)
for sx in (-1, 1):
    prof = [(0.0, 0.0), (0.078, 0.0), (0.083, 0.013), (0.083, 0.034), (0.068, 0.048), (0.035, 0.057), (0.0, 0.06)]
    bm = lathe_bm(prof, segs=40, axis='X', cap=False)
    if sx < 0:
        for v in bm.verts: v.co.x = -v.co.x
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    ear = mesh_from_bm(f'ear_{"L" if sx > 0 else "R"}', bm, 'trim'); ear.location = (sx * (hw / 2 - 0.006), 0.0, 1.95)
    base = Vector((sx * 0.125, 0.03, HZ1 + 0.012)); tip = Vector((sx * 0.165, 0.05, 2.235))
    rod = tube_bm([base, base.lerp(tip, 0.5), tip], lambda s: 0.0105, segs=12)
    link_rod = mesh_from_bm(f'antenna_{"L" if sx > 0 else "R"}', rod, 'trim')
    bmb = bmesh.new(); bmesh.ops.create_uvsphere(bmb, u_segments=20, v_segments=12, radius=0.026)
    ball = mesh_from_bm(f'antenna_ball_{"L" if sx > 0 else "R"}', bmb, 'light'); ball.location = tip + (tip - base).normalized() * 0.012
    bmc = lathe_bm([(0.0, 0.0), (0.022, 0.0), (0.024, 0.01), (0.016, 0.022), (0.0, 0.024)], segs=24, cap=False)
    collar = mesh_from_bm(f'antenna_base_{"L" if sx > 0 else "R"}', bmc, 'trim'); collar.location = base - Vector((0, 0, 0.006))

# ======================================================================= SHOULDERS + ARMS + CLAWS
for sx in (-1, 1):
    S = Vector((sx * 0.365, 0.0, 1.635))
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=36, v_segments=20, radius=0.098)
    # a machined seam band around the ball: inset the equator faces, push in
    bm.normal_update()
    band = [f for f in bm.faces if abs(f.calc_center_median().z) < 0.012]
    if band:
        bmesh.ops.inset_region(bm, faces=band, thickness=0.003, depth=-0.004, use_even_offset=True)
    sh = mesh_from_bm(f'shoulder_{"L" if sx > 0 else "R"}', bm, 'paint'); sh.location = S; sh.rotation_euler = (0, math.pi / 2, 0)
    # the arm: ONE continuous bellows hose, shoulder -> elbow -> wrist
    E = S + Vector((sx * 0.13, -0.03, -0.30))
    Wr = E + Vector((sx * 0.13, -0.16, -0.22))
    pts = bezier_path(S + Vector((sx * 0.05, 0, -0.03)), E + Vector((0, 0, 0.12)), E + Vector((sx * 0.02, -0.07, -0.06)), Wr, 120)
    pitch = 0.038
    def rad(s, pitch=pitch):
        ph = (s % pitch) / pitch
        return 0.068 + 0.013 * (0.5 + 0.5 * math.cos(2 * math.pi * ph)) ** 0.6
    arm = mesh_from_bm(f'arm_{"L" if sx > 0 else "R"}', tube_bm(pts, rad, segs=28), 'rubber')
    # wrist cuff (lathe) aligned to the last segment, then the claw
    tdir = (pts[-1] - pts[-2]).normalized()
    cuff_prof = [(0.0, 0.0), (0.086, 0.0), (0.09, 0.013), (0.09, 0.058), (0.08, 0.071), (0.06, 0.076), (0.0, 0.076)]
    bm = lathe_bm(cuff_prof, segs=36, cap=False)
    cuff = mesh_from_bm(f'cuff_{"L" if sx > 0 else "R"}', bm, 'paint')
    q = Vector((0, 0, 1)).rotation_difference(tdir)
    cuff.rotation_mode = 'QUATERNION'; cuff.rotation_quaternion = q; cuff.location = Wr - tdir * 0.02
    # claw: a palm block + two curved pincers (tapered tubes on arcs), opening ~34 deg
    Pc = Wr + tdir * 0.09
    side = Vector((sx, 0, 0)); side = (side - tdir * side.dot(tdir)).normalized()
    up = tdir.cross(side).normalized()
    bm = box_bm((0.14, 0.13, 0.10))
    bevel_all(bm, 0.028, 3, angle_deg=60)
    palm = mesh_from_bm(f'palm_{"L" if sx > 0 else "R"}', bm, 'paint')
    M = Matrix((side, up, tdir)).transposed()
    palm.rotation_mode = 'QUATERNION'; palm.rotation_quaternion = M.to_quaternion(); palm.location = Pc
    for fs in (-1, 1):
        base = Pc + tdir * 0.05
        pts_f = []
        for k in range(21):
            t = k / 20
            lat = 0.028 + 0.06 * math.sin(math.pi * t * 0.85) - 0.043 * t * t
            pts_f.append(base + tdir * (0.165 * t) + side * (fs * lat))
        fing = tube_bm(pts_f, lambda s: 0.027 - 0.085 * s, segs=16)
        for v in fing.verts:                           # flatten the finger across `up` (a blade, not a sausage)
            d = v.co - base; v.co = v.co - up * (d.dot(up) * 0.45)
        mesh_from_bm(f'claw_{"L" if sx > 0 else "R"}_{fs:+d}', fing, 'trim')

# ======================================================================= WAIST + PELVIS
waist_prof = [(0.19, 0.985), (0.205, 0.995), (0.18, 1.012), (0.205, 1.03), (0.18, 1.048), (0.205, 1.066), (0.19, 1.08)]
waist = mesh_from_bm('waist', lathe_bm(waist_prof, segs=48), 'rubber')
for v in waist.data.vertices: v.co.y *= 0.82                      # oval, fits the 0.42 m deep torso
bm = box_bm((0.58, 0.37, 0.15), (0, 0, 0.925))
bevel_all(bm, 0.035, 4, angle_deg=60)
bm.normal_update()
pf = max(faces_facing(bm, FRONT, 0.99), key=lambda f: f.calc_area())
bmesh.ops.inset_region(bm, faces=[pf], thickness=0.025, depth=0.0, use_even_offset=True)
bmesh.ops.translate(bm, verts=list(pf.verts), vec=Vector((0, 0.01, 0)))
bevel_all(bm, 0.005, 2, angle_deg=30)
pelvis = mesh_from_bm('pelvis', bm, 'paint')

# ======================================================================= LEGS + FEET
for sx in (-1, 1):
    x = sx * 0.16
    prof = [(0.0, 0.13), (0.12, 0.13), (0.124, 0.146), (0.124, 0.19), (0.11, 0.206), (0.102, 0.222),
            (0.102, 0.42)]
    z = 0.42
    for k in range(5):                                            # bellows knee
        prof += [(0.112, z + 0.017), (0.097, z + 0.034)]; z += 0.034
    prof += [(0.106, z + 0.02), (0.108, 0.83), (0.116, 0.848), (0.116, 0.88), (0.0, 0.886)]
    leg = mesh_from_bm(f'leg_{"L" if sx > 0 else "R"}', lathe_bm(prof, segs=40, center=(x, 0, 0), cap=False), 'paint')
    # foot: a heavy rounded box with a proud sole lip and a toe cap
    fc = Vector((sx * 0.17, -0.06, 0.075))
    bm = box_bm((0.28, 0.43, 0.135), fc)
    bevel_all(bm, 0.04, 5, angle_deg=60)
    bm.normal_update()
    bot = max(faces_facing(bm, Vector((0, 0, -1)), 0.99), key=lambda f: f.calc_area())
    top = max(faces_facing(bm, Vector((0, 0, 1)), 0.99), key=lambda f: f.calc_area())
    # proud sole: the flat underside extrudes down and flares out a touch
    ext = bmesh.ops.extrude_face_region(bm, geom=[bot])
    nv = [g for g in ext['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=nv, vec=Vector((0, 0, -0.014)))
    bmesh.ops.scale(bm, vec=Vector((1.07, 1.05, 1.0)), verts=nv, space=Matrix.Translation(-Vector((fc.x, fc.y, 0.0))))
    # instep plate on top: inset + raise
    bmesh.ops.inset_region(bm, faces=[top], thickness=0.028, depth=0.0, use_even_offset=True)
    bmesh.ops.translate(bm, verts=list(top.verts), vec=Vector((0, 0, 0.012)))
    bevel_all(bm, 0.005, 2, angle_deg=30)
    foot = mesh_from_bm(f'foot_{"L" if sx > 0 else "R"}', bm, 'paint')

# sit everything on the ground: lowest point -> z = 0
bpy.context.view_layer.update()
zmin = min((o.matrix_world @ Vector(c)).z for o, _ in PARTS.values() for c in o.bound_box)
for o, _ in PARTS.values(): o.location.z -= zmin
bpy.context.view_layer.update()
pts = [(o.matrix_world @ Vector(c)) for o, _ in PARTS.values() for c in o.bound_box]
print('ROBOT parts', len(PARTS), 'bbox', [round(min(p[i] for p in pts), 3) for i in range(3)], [round(max(p[i] for p in pts), 3) for i in range(3)])
tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o, _ in PARTS.values())
print('ROBOT tris', tris)

# clay material by role (for look-dev renders); the final stage replaces these with baked PBR
CLAY = {'paint': (0.32, 0.34, 0.38), 'trim': (0.75, 0.75, 0.78), 'rubber': (0.12, 0.12, 0.13), 'lens': (0.8, 0.08, 0.05),
        'light': (0.9, 0.7, 0.2), 'dark': (0.03, 0.03, 0.03)}
mats = {}
for role, c in CLAY.items():
    m = bpy.data.materials.new('clay_' + role); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = (*c, 1)
    b.inputs['Roughness'].default_value = 0.35 if role in ('trim', 'lens') else 0.55
    b.inputs['Metallic'].default_value = 1.0 if role == 'trim' else 0.0
    mats[role] = m
for o, role in PARTS.values():
    o.data.materials.clear(); o.data.materials.append(mats[role])
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'wip', 'robot_clay.blend'))
bpy.ops.object.select_all(action='DESELECT')
for o, _ in PARTS.values(): o.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, 'wip', 'robot_clay.glb'), export_format='GLB', use_selection=True,
                          export_yup=True, export_apply=True)
print('EXPORTED clay')
