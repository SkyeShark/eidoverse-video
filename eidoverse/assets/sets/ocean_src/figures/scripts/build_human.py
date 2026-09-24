# build_human.py — the "digital human" for DAISY verse 3 (a human figure made of light).
# Source: Blender Studio "Human Base Meshes" v1.4.1 (CC0), realistic body multires CAGE (level 0).
# Neutralised into a sculptural, gender-neutral mannequin:
#   - face: eyes/lips/ears smoothed away; a soft nose and brow remain
#   - chest flattened, crotch smoothed, shoulders/hips/waist eased toward the middle
#   - gentle whole-body Taubin smoothing (hands/feet kept crisp) -> sculptural, not anatomical-chart
#   - arms: armature + bone-heat weights, A-pose -> relaxed hang (landmarks MEASURED by slicing)
#   - 1.75 m, origin between the feet on the ground, faces +Z in glTF (Blender -Y)
#
#   blender --background --factory-startup <bundle.blend> --python build_human.py -- <out_dir> [female|male] [tag]
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else '.')
BASE = argv[1] if len(argv) > 1 else 'female'
TAG = argv[2] if len(argv) > 2 else ''
os.makedirs(OUT, exist_ok=True)

def smoothstep(a, b, x):
    if a == b: return 1.0 if x >= b else 0.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)

src = bpy.data.objects[f'GEO-body_{BASE}_realistic']
bm = bmesh.new(); bm.from_mesh(src.data)
bm.verts.ensure_lookup_table()
N = len(bm.verts)
nbr = [[e.other_vert(v).index for e in v.link_edges] for v in bm.verts]

def smooth(weights, iters, lam=0.55, mu=-0.58, taubin=True):
    idx = [i for i, w in enumerate(weights) if w > 1e-4]
    for _ in range(iters):
        for k in ((lam, mu) if taubin else (lam,)):
            new = {}
            for i in idx:
                ns = nbr[i]
                avg = sum((bm.verts[j].co for j in ns), Vector()) / len(ns)
                new[i] = bm.verts[i].co + (avg - bm.verts[i].co) * (k * weights[i])
            for i, c in new.items(): bm.verts[i].co = c

# ---------------------------------------------------------------- landmarks (measured)
zs0 = [v.co.z for v in bm.verts]; H0 = max(zs0) - min(zs0)
face_c = [v for v in bm.verts if 0.89 * H0 < v.co.z < 0.98 * H0 and abs(v.co.x) < 0.012]
nose = min(face_c, key=lambda v: v.co.y).co.copy()
head = [v.co for v in bm.verts if v.co.z > nose.z - 0.13]
head_c = sum(head, Vector()) / len(head)
print('LANDMARK', BASE, 'H', round(H0, 3), 'nose', tuple(round(c, 3) for c in nose), 'headc', tuple(round(c, 3) for c in head_c))
orig = [v.co.copy() for v in bm.verts]
kz = H0 / 1.684                                                # landmark heights below were read on the male (1.684)

# ---------------------------------------------------------------- chest flat, crotch smooth (Laplacian: removes volume)
wc = [0.0] * N
for i, v in enumerate(bm.verts):
    p = v.co
    front = smoothstep(0.02, -0.07, p.y)
    zc = 1.30 * kz
    breast = max(math.exp(-(((p.x - s * 0.095) / 0.085) ** 2 + ((p.z - zc) / 0.085) ** 2)) for s in (-1, 1))
    crotch = math.exp(-((p.x / 0.07) ** 2 + ((p.z - 0.86 * kz) / 0.07) ** 2)) * smoothstep(0.03, -0.06, p.y)
    wc[i] = max(breast * front, crotch)
smooth(wc, 70 if BASE == 'female' else 25, lam=0.5, taubin=False)
smooth(wc, 10)

# ---------------------------------------------------------------- proportions toward the middle
for v in bm.verts:
    p = v.co
    sh = smoothstep(1.18 * kz, 1.34 * kz, p.z) * (1 - smoothstep(1.46 * kz, 1.52 * kz, p.z))
    hip = math.exp(-((p.z - 0.93 * kz) / 0.10) ** 2)
    waist = math.exp(-((p.z - 1.07 * kz) / 0.07) ** 2)
    if BASE == 'female':
        if abs(p.x) > 0.06: p.x *= 1.0 + 0.035 * sh
        if abs(p.x) < 0.24: p.x *= 1.0 - 0.035 * hip
        if abs(p.x) < 0.20: p.x *= 1.0 + 0.03 * waist
    else:
        if abs(p.x) > 0.06: p.x *= 1.0 - 0.06 * sh
        if abs(p.x) < 0.23: p.x *= 1.0 + 0.035 * hip
        if abs(p.x) < 0.20: p.x *= 1.0 - 0.02 * waist

# ---------------------------------------------------------------- sculptural simplification (not hands/feet/face)
wg = [0.0] * N
for i, v in enumerate(bm.verts):
    p = v.co
    hands = 1.0 - smoothstep(0.93 * kz, 1.0 * kz, p.z) if abs(p.x) > 0.26 else 0.0
    feet = 1.0 - smoothstep(0.07, 0.12, p.z)
    wg[i] = 0.45 * (1.0 - max(hands, feet)) * (1.0 - smoothstep(nose.z - 0.16, nose.z - 0.12, p.z))
smooth(wg, 12)

# ---------------------------------------------------------------- arms: armature + bone heat, A-pose -> relaxed hang
def slice_arm(side, z):
    sl = [v.co for v in bm.verts if abs(v.co.z - z) < 0.01 and side * v.co.x > 0]
    xs = sorted(side * p.x for p in sl)
    gaps = [(xs[i + 1] - xs[i], xs[i + 1]) for i in range(len(xs) - 1)]
    if not gaps: return None
    g, x0 = max(gaps)
    if g < 0.015: return None
    arm = [p for p in sl if side * p.x >= x0]
    return sum(arm, Vector()) / len(arm) if arm else None

def first_slice(side, zs):
    for z in zs:
        c = slice_arm(side, z)
        if c is not None: return c
    return None

LM = {}
for side in (-1, 1):
    top = max((v.co for v in bm.verts if 1.28 * kz < v.co.z < 1.40 * kz and side * v.co.x > 0), key=lambda p: side * p.x)
    S = Vector((top.x - side * 0.042, 0.0, 1.372 * kz))
    E = first_slice(side, [1.10 * kz, 1.08 * kz, 1.12 * kz])
    W = first_slice(side, [0.905 * kz, 0.92 * kz, 0.89 * kz])
    T = first_slice(side, [0.76 * kz, 0.78 * kz, 0.80 * kz])
    LM[side] = (S, E, W, T)
    print(f'ARMLM side={side} S={tuple(round(c,3) for c in S)} E={tuple(round(c,3) for c in E)} '
          f'W={tuple(round(c,3) for c in W)} T={tuple(round(c,3) for c in T)} '
          f'upper_from_vertical={math.degrees(math.atan2(abs(E.x-S.x), abs(E.z-S.z))):.1f}')

mesh0 = bpy.data.meshes.new('human_pre'); bm.to_mesh(mesh0)
edited = [v.co.copy() for v in mesh0.vertices]
for v, c in zip(mesh0.vertices, orig): v.co = c        # weights are solved on the UNTOUCHED cage (heat solve is robust there)
for p in mesh0.polygons: p.use_smooth = True
hum = bpy.data.objects.new('human_pre', mesh0); bpy.context.scene.collection.objects.link(hum)
arm_data = bpy.data.armatures.new('rig'); rig = bpy.data.objects.new('rig', arm_data)
bpy.context.scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
eb = arm_data.edit_bones
def bone(name, h, t, parent=None):
    b = eb.new(name); b.head = h; b.tail = t; b.roll = 0.0
    if parent: b.parent = eb[parent]
    return b
ztop = max(v.co.z for v in bm.verts)
bone('hips', Vector((0, 0, 0.86 * kz)), Vector((0, 0, 1.02 * kz)))
bone('spine', Vector((0, 0, 1.02 * kz)), Vector((0, 0, 1.40 * kz)), 'hips')
bone('head', Vector((0, 0, 1.44 * kz)), Vector((0, 0, ztop)), 'spine')
for side, sn in ((1, 'L'), (-1, 'R')):
    S, E, W, T = LM[side]
    bone('clav.' + sn, Vector((side * 0.03, 0, 1.40 * kz)), S, 'spine')
    bone('upper.' + sn, S, E, 'clav.' + sn)
    bone('fore.' + sn, E, W, 'upper.' + sn)
    bone('hand.' + sn, W, T, 'fore.' + sn)
    hip = Vector((side * 0.088, 0, 0.90 * kz)); knee = Vector((side * 0.095, -0.01, 0.48 * kz))
    ank = Vector((side * 0.10, 0.02, 0.08 * kz))
    bone('thigh.' + sn, hip, knee, 'hips'); bone('shin.' + sn, knee, ank, 'thigh.' + sn)
    bone('foot.' + sn, ank, Vector((side * 0.11, -0.12, 0.02)), 'shin.' + sn)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
hum.select_set(True); rig.select_set(True); bpy.context.view_layer.objects.active = rig
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
wstat = {g.name: 0 for g in hum.vertex_groups}
for v in hum.data.vertices:
    for ge in v.groups:
        if ge.weight > 0.1: wstat[hum.vertex_groups[ge.group].name] += 1
print('WSTAT', wstat)
for v, c in zip(hum.data.vertices, edited): v.co = c    # then the neutralised shape is what gets posed
hum.data.update()

bpy.ops.object.mode_set(mode='POSE')
def pose_world(pb, Rw):
    Rr = pb.bone.matrix_local.to_3x3()
    pb.rotation_mode = 'QUATERNION'
    pb.rotation_quaternion = (Rr.inverted() @ Rw @ Rr).to_quaternion()
for side, sn in ((1, 'L'), (-1, 'R')):
    S, E, W, T = LM[side]
    whole = (T - S)
    ang_now = math.degrees(math.atan2(abs(whole.x), abs(whole.z)))       # shoulder -> fingertip, from vertical
    Rup = Matrix.Rotation(math.radians(ang_now - 13.0) * side, 3, 'Y')      # toward the body, in the frontal plane
    pose_world(rig.pose.bones['upper.' + sn], Rup)
    # elbow: a small natural bend forward (toward -Y) + remove part of the A-pose carrying angle
    fdir = (Rup @ (W - E)).normalized()
    hinge = fdir.cross(Vector((0, 1, 0))).normalized()
    Rf = Matrix.Rotation(math.radians(-8.0), 3, hinge)
    if (Rf @ fdir).y > fdir.y: Rf = Matrix.Rotation(math.radians(8.0), 3, hinge)
    Rf = Matrix.Rotation(math.radians(5.0) * side, 3, 'Y') @ Rf
    pose_world(rig.pose.bones['fore.' + sn], Rf)
    # hand: hang (cancel most of the forward reach) and turn the fingers down toward the thigh line
    hdir = (T - W).normalized()
    cur = math.degrees(math.atan2(-hdir.y, -hdir.z))
    Rh = Matrix.Rotation(math.radians(cur - 4.0), 3, Vector((1, 0, 0)))
    if (Rh @ hdir).y < hdir.y: Rh = Matrix.Rotation(math.radians(-(cur - 4.0)), 3, Vector((1, 0, 0)))
    Rh = Matrix.Rotation(math.radians(8.0) * side, 3, 'Y') @ Rh
    pose_world(rig.pose.bones['hand.' + sn], Rh)
    print(f'POSE side={side} whole_arm={ang_now:.1f}->13 hand_reach={cur:.1f}->4')
bpy.ops.object.mode_set(mode='OBJECT')
dg = bpy.context.evaluated_depsgraph_get()
posed = bpy.data.meshes.new_from_object(hum.evaluated_get(dg))
HANDW = {}
for side, sn in ((1, 'L'), (-1, 'R')):
    gi = hum.vertex_groups['hand.' + sn].index
    arr = [0.0] * len(hum.data.vertices)
    for v in hum.data.vertices:
        for ge in v.groups:
            if ge.group == gi: arr[v.index] = ge.weight
    HANDW[side] = arr
bpy.data.objects.remove(hum, do_unlink=True); bpy.data.objects.remove(rig, do_unlink=True)
bm.free(); bm = bmesh.new(); bm.from_mesh(posed); bm.verts.ensure_lookup_table()
N = len(bm.verts); nbr = [[e.other_vert(v).index for e in v.link_edges] for v in bm.verts]
# ---------------------------------------------------------------- hands: gather the A-pose finger fan, slight curl
for side in (-1, 1):
    hw = HANDW[side]
    hv = [i for i, w in enumerate(hw) if w > 0.02]
    wrist = [bm.verts[i].co for i in hv if 0.3 < hw[i] < 0.7]
    Wp = sum(wrist, Vector()) / len(wrist)
    far = sorted(hv, key=lambda i: (bm.verts[i].co - Wp).length)[-60:]
    tip = sum((bm.verts[i].co for i in far), Vector()) / len(far)
    a = (tip - Wp).normalized(); L = (tip - Wp).length
    # width axis: principal spread of the hand perpendicular to a
    pts = [bm.verts[i].co - Wp for i in hv if hw[i] > 0.6]
    pts = [q - a * q.dot(a) for q in pts]
    C = Matrix(((0, 0, 0), (0, 0, 0), (0, 0, 0)))
    for q in pts:
        for r in range(3):
            for c in range(3): C[r][c] += q[r] * q[c]
    b = Vector((0, 1, 0)); b = (b - a * b.dot(a)).normalized()
    for _ in range(50): b = (C @ b); b = (b - a * b.dot(a)).normalized()
    ctr = sum(pts, Vector()) / len(pts)
    thigh = Vector((side * 0.10, Wp.y, Wp.z))
    palm = (thigh - Wp); palm = (palm - a * palm.dot(a) - b * palm.dot(b)).normalized()
    for i in hv:
        v = bm.verts[i]; d = v.co - Wp
        t = d.dot(a) / L
        k = smoothstep(0.38, 1.0, t) * hw[i]
        if k <= 0: continue
        lat = (d - a * d.dot(a)).dot(b) - ctr.dot(b)
        v.co -= b * (lat * 0.42 * k)                     # fingers together
        v.co += palm * (0.018 * k * k)                   # a gentle curl toward the palm
    print(f'HAND side={side} L={L:.3f} axis={tuple(round(x,2) for x in a)} width={tuple(round(x,2) for x in b)}')

# ---------------------------------------------------------------- face surgery (post-pose): close the pockets
# The cage has real pocket topology (mouth bag, eye sockets, nostrils). Faces in the front of the head whose
# outward normal ray hits the mesh again within 5 cm are pocket interiors: delete them, fill the openings,
# triangulate, then smooth the face (nose ridge and brow protected) and fold the ears down.
from mathutils.bvhtree import BVHTree
bm.faces.ensure_lookup_table(); bm.normal_update()
bvh = BVHTree.FromBMesh(bm)
pocket = []
for f in bm.faces:
    c = f.calc_center_median()
    if c.z < nose.z - 0.125 or c.z > nose.z + 0.085 or abs(c.x) > 0.075 or c.y > head_c.y + 0.03: continue
    hit = bvh.ray_cast(c + f.normal * 2e-4, f.normal, 0.05)
    if hit[0] is not None: pocket.append(f)
print('POCKET faces', len(pocket))
bmesh.ops.delete(bm, geom=pocket, context='FACES')
loose = [v for v in bm.verts if not v.link_faces]
bmesh.ops.delete(bm, geom=loose, context='VERTS')
bnd = [e for e in bm.edges if e.is_boundary]
print('HOLE edges', len(bnd))
filled = bmesh.ops.holes_fill(bm, edges=bnd, sides=0)['faces']
bmesh.ops.triangulate(bm, faces=filled, quad_method='BEAUTY', ngon_method='BEAUTY')
print('AFTER fill boundary', sum(1 for e in bm.edges if e.is_boundary), 'nonmanifold', sum(1 for e in bm.edges if not e.is_manifold))
bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
N = len(bm.verts); nbr = [[e.other_vert(v).index for e in v.link_edges] for v in bm.verts]
zf = nose.z + 0.004
wf = [0.0] * N
for i, v in enumerate(bm.verts):
    p = v.co
    if p.z < nose.z - 0.13 or p.y > head_c.y + 0.035: continue
    m = math.exp(-((p.x / 0.066) ** 4 + ((p.z - zf) / 0.076) ** 4))
    ridge = math.exp(-((p.x / 0.014) ** 2 + ((p.z - (nose.z + 0.02)) / 0.035) ** 2))       # nose bridge + tip
    brow = math.exp(-((p.x / 0.05) ** 2 + ((p.z - (nose.z + 0.047)) / 0.011) ** 2))
    wf[i] = m * (1.0 - 0.8 * max(ridge, 0.7 * brow))
smooth(wf, 25, lam=0.5, taubin=False)
smooth(wf, 25)
we = [0.0] * N
for i, v in enumerate(bm.verts):
    p = v.co
    we[i] = math.exp(-(((abs(p.x) - 0.072) / 0.03) ** 2 + ((p.z - nose.z) / 0.055) ** 2 + ((p.y - head_c.y - 0.005) / 0.045) ** 2))
smooth(we, 45, lam=0.6, taubin=False)
smooth(we, 10)

# relax the shoulder/armpit seam
wa = [math.exp(-(((abs(v.co.x) - 0.17) / 0.05) ** 2 + ((v.co.z - 1.30 * kz) / 0.08) ** 2)) * 0.8 for v in bm.verts]
smooth(wa, 10)

# ---------------------------------------------------------------- scale to 1.75 m, origin between the feet
zs = [v.co.z for v in bm.verts]; s = 1.75 / (max(zs) - min(zs))
for v in bm.verts: v.co *= s
zmin = min(v.co.z for v in bm.verts)
feet = [v.co for v in bm.verts if v.co.z < zmin + 0.06]
fy = (min(p.y for p in feet) + max(p.y for p in feet)) / 2
fx = (min(p.x for p in feet) + max(p.x for p in feet)) / 2
for v in bm.verts:
    v.co.x -= fx; v.co.y -= fy; v.co.z -= zmin
print('SCALE', round(s, 4))

me = bpy.data.meshes.new('human'); bm.to_mesh(me); bm.free()
for p in me.polygons: p.use_smooth = True
obj = bpy.data.objects.new('human', me); bpy.context.scene.collection.objects.link(obj)
sub = obj.modifiers.new('sub', 'SUBSURF'); sub.levels = 1; sub.render_levels = 1
dg = bpy.context.evaluated_depsgraph_get()
me2 = bpy.data.meshes.new_from_object(obj.evaluated_get(dg)); obj.modifiers.clear(); obj.data = me2
tris = sum(len(p.vertices) - 2 for p in me2.polygons)
dec = obj.modifiers.new('dec', 'DECIMATE'); dec.ratio = min(1.0, 58000 / tris); dec.use_collapse_triangulate = True
dg = bpy.context.evaluated_depsgraph_get()
me3 = bpy.data.meshes.new_from_object(obj.evaluated_get(dg)); obj.modifiers.clear(); obj.data = me3
me3.name = 'human'
for p in me3.polygons: p.use_smooth = True
print('TRIS', sum(len(p.vertices) - 2 for p in me3.polygons), 'VERTS', len(me3.vertices))
mat = bpy.data.materials.new('human_light'); mat.use_nodes = True
bsdf = mat.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Base Color'].default_value = (0.82, 0.86, 0.92, 1); bsdf.inputs['Roughness'].default_value = 0.42
me3.materials.append(mat)
bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
print('BBOX', [round(min(p[i] for p in bb), 4) for i in range(3)], [round(max(p[i] for p in bb), 4) for i in range(3)])
for o in list(bpy.data.objects):
    if o is not obj: bpy.data.objects.remove(o, do_unlink=True)
name = 'human' + TAG
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, name + '.blend'))
bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True); bpy.context.view_layer.objects.active = obj
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, name + '.glb'), export_format='GLB', use_selection=True,
                          export_yup=True, export_apply=True, export_normals=True, export_texcoords=True,
                          export_materials='EXPORT')
print('EXPORTED', os.path.join(OUT, name + '.glb'))
