"""RECIPE: the 2010 Eurovision saxophonist (the "Epic Sax Guy" look) for digi's claudesona — a sleeveless open
pinstripe vest over a sleeveless tee, white wayfarers, a red fingerless glove on the right hand, a cord necklace.
Read README.md in this folder first.

    bash run_blender.sh eidoverse/assets/vrms/claude_suit_wardrobe_src/build_sax.py

Opens claude_suit_wardrobe.blend, adds the layers and SAVES it (the library VRM is then exported by build_tuta.py):

  sax_vest       material `vest`   digi's jacket, sleeves cut at the shoulder, opened down the front; double-sided
                                   (the open front and the armholes show its inside). Skinned (the jacket's weights).
  sax_tee        material `tee`    digi's shirt, sleeves cut at the shoulder. Skinned.
  acc_wayfarers  `wayfarer`, `lens_dark`   thick trapezoid frames following the face dome, filled dark lenses. Head bone.
  acc_glove_r    material `glove_red`      the right hand's own skin (palm, back, the first finger joints, the thumb,
                                   the wrist) pushed out 2.5 mm: it keeps the hand's weights. Skinned.
  acc_cord       material `cord_black`     a cord round the neck, dipping in front. Chest bone.

The runtime preset (eidoverse/claudesona_wardrobe.js, `sax_guy_2010`) paints the vest's pinstripes, the tee, the
trousers and the shoes. Re-running replaces the layers it made.
"""
import math
import os

import bmesh
import bpy
from mathutils import Vector

bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'claude_suit_wardrobe.blend')
bpy.ops.wm.open_mainfile(filepath=SRC)
LAYERS = ['sax_vest', 'sax_tee', 'acc_wayfarers', 'acc_glove_r', 'acc_cord']


def log(*a):
    print('[sax]', *a, flush=True)


def mat(name, rgb, outline=0.004, double_sided=False, base=None):
    """an MToon material (a copy of `base` if given, keeping its textures), flat colour otherwise"""
    m = bpy.data.materials.get(name)
    if m is None:
        m = base.copy() if base else bpy.data.materials.new(name)
        m.name = name
    ext = m.vrm_addon_extension.mtoon1
    ext.enabled = True
    ext.pbr_metallic_roughness.base_color_factor = (*rgb, 1.0)
    mt = ext.extensions.vrmc_materials_mtoon
    mt.shade_color_factor = tuple(c * 0.58 for c in rgb)
    mt.outline_width_mode = 'worldCoordinates' if outline > 0 else 'none'
    mt.outline_width_factor = outline
    mt.outline_color_factor = tuple(c * 0.25 for c in rgb)
    mt.outline_lighting_mix_factor = 0.0
    mt.parametric_rim_color_factor = (0.0, 0.0, 0.0)
    ext.double_sided = double_sided
    return m


def dup(name, newname):
    src = bpy.data.objects[name]
    o = src.copy()
    o.data = src.data.copy()
    o.name = newname
    o.data.name = newname
    for c in src.users_collection:
        c.objects.link(o)
    return o


def bone_parent(o, arm, bone):
    mw = o.matrix_world.copy()
    o.parent = arm
    o.parent_type = 'BONE'
    o.parent_bone = bone
    bpy.context.view_layer.update()
    o.matrix_world = mw


def new_object(name, bm, materials, smooth=True):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    o = bpy.data.objects.new(name, me)
    bpy.data.objects['shirt'].users_collection[0].objects.link(o)
    for m in materials:
        me.materials.append(m)
    return o


def ring_sweep(bm, pts, sides, normals, w, th, mat_index=0):
    rings = []
    for p, s, n in zip(pts, sides, normals):
        s, n = s.normalized(), n.normalized()
        rings.append([bm.verts.new(p + s * sx * w / 2 + n * nx * th / 2) for sx, nx in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    for a, b in zip(rings, rings[1:]):
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((a[i], a[j], b[j], b[i])).material_index = mat_index
    return rings


def tube(bm, pts, r, seg=10, mat_index=0, closed=False):
    rings = []
    n = len(pts)
    for i, p in enumerate(pts):
        if closed:
            t = (pts[(i + 1) % n] - pts[(i - 1) % n]).normalized()
        else:
            t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        a = t.orthogonal().normalized()
        b = t.cross(a).normalized()
        rings.append([bm.verts.new(p + (a * math.cos(2 * math.pi * k / seg) + b * math.sin(2 * math.pi * k / seg)) * r) for k in range(seg)])
    pairs = list(zip(rings, rings[1:])) + ([(rings[-1], rings[0])] if closed else [])
    for ra, rb in pairs:
        for k in range(seg):
            bm.faces.new((ra[k], ra[(k + 1) % seg], rb[(k + 1) % seg], rb[k])).material_index = mat_index


def dominant(o):
    names = {g.index: g.name for g in o.vertex_groups}
    out = []
    for v in o.data.vertices:
        g = max(v.groups, key=lambda g: g.weight, default=None)
        out.append(names.get(g.group, '') if g else '')
    return out


arm = bpy.data.objects['Armature']
for n in LAYERS:                                                   # re-runnable: drop what an earlier run made
    o = bpy.data.objects.get(n)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)
bone = lambda n: arm.matrix_world @ arm.data.bones[n].head_local
sh_x = max(abs(bone('upper_arm.L').x), abs(bone('upper_arm.R').x))
log('upper_arm heads x', round(bone('upper_arm.L').x, 3), round(bone('upper_arm.R').x, 3), 'neck', tuple(round(c, 3) for c in bone('neck')))


def sleeveless(o, cut):
    """remove every face reaching past the shoulder line (T-pose: the arms run along x)"""
    W = o.matrix_world
    bm = bmesh.new()
    bm.from_mesh(o.data)
    kill = [f for f in bm.faces if any(abs((W @ v.co).x) > cut for v in f.verts)]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    return bm, W


# ---- the tee: digi's shirt without sleeves (cut a little inside the shoulder joint, like a tank top's armhole)
tee = dup('shirt', 'sax_tee')
bm, W = sleeveless(tee, sh_x + 0.012)
bm.to_mesh(tee.data)
bm.free()
tee.data.materials.clear()
tee.data.materials.append(mat('tee', (0.95, 0.76, 0.1), base=bpy.data.materials['shirt']))
log('sax_tee verts', len(tee.data.vertices))

# ---- the vest: digi's jacket, sleeveless, open in front (a gap that widens toward the hem, the lapels kept above)
vest = dup('jacket', 'sax_vest')
bm, W = sleeveless(vest, sh_x + 0.022)
cy = sum((W @ v.co).y for v in bm.verts) / max(1, len(bm.verts))
neck_z = bone('neck').z
hip_z = bone('hips').z


def in_gap(p):
    if p.y > cy:                                                    # the back stays whole
        return False
    if p.z > neck_z - 0.06:                                         # the collar stays
        return False
    t = max(0.0, min(1.0, (neck_z - 0.06 - p.z) / max(0.05, neck_z - 0.06 - (hip_z - 0.15))))
    half = 0.03 + 0.05 * t                                          # 3 cm each side at the chest, 8 cm at the hem
    return abs(p.x) < half


kill = [f for f in bm.faces if sum(1 for v in f.verts if in_gap(W @ v.co)) >= 2]
bmesh.ops.delete(bm, geom=kill, context='FACES')
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
bm.to_mesh(vest.data)
bm.free()
vest.data.materials.clear()
vest.data.materials.append(mat('vest', (0.94, 0.94, 0.92), double_sided=True, base=bpy.data.materials['Jacket']))
log('sax_vest verts', len(vest.data.vertices))

# ---- the glove: the right hand's skin, pushed out (palm + back + first finger joints + thumb + the wrist)
glove = dup('BodyActual', 'acc_glove_r')
for k in list(glove.data.shape_keys.key_blocks) if glove.data.shape_keys else []:
    pass
if glove.data.shape_keys:                                          # the body's blend shapes don't belong on a glove
    glove.shape_key_clear()
dom = dominant(glove)
wrist = bone('hand.R')
keep_groups = {'hand.R', 'f_index.01.R', 'f_middle.01.R', 'f_ring.01.R', 'f_pinky.01.R', 'thumb.01.R', 'thumb.02.R'}
Wg = glove.matrix_world
bm = bmesh.new()
bm.from_mesh(glove.data)
bm.verts.ensure_lookup_table()


def keep_v(v):
    g = dom[v.index]
    if g in keep_groups:
        return True
    return g == 'forearm.R' and ((Wg @ v.co) - wrist).length < 0.045   # a short cuff over the wrist


kill = [f for f in bm.faces if not all(keep_v(v) for v in f.verts)]
bmesh.ops.delete(bm, geom=kill, context='FACES')
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
bm.normal_update()
for v in bm.verts:
    v.co = v.co + v.normal * 0.0025
bm.to_mesh(glove.data)
bm.free()
glove.data.materials.clear()
glove.data.materials.append(mat('glove_red', (0.82, 0.07, 0.06), outline=0.0025, double_sided=True))
log('acc_glove_r verts', len(glove.data.vertices))

# ---- the wayfarers: trapezoid frames (wider at the brow), thick, white; dark lenses filled inside
face = bpy.data.objects['face']
body = bpy.data.objects['Body']
fpts = [face.matrix_world @ v.co for v in face.data.vertices] + [body.matrix_world @ v.co for v in body.data.vertices]


def face_y_at(x, z):
    near = [p for p in fpts if abs(p.x - x) < 0.02 and abs(p.z - z) < 0.02]
    return min(p.y for p in near) if near else -0.12


bm = bmesh.new()
for sx in (-1, 1):
    cx, cz, w, h = sx * 0.052, 1.553, 0.096, 0.064
    n = 48
    pts, sides, nrm, inner = [], [], [], []
    for i in range(n + 1):
        a = 2 * math.pi * i / n
        ca, sa = math.cos(a), math.sin(a)
        zt = (h / 2) * math.copysign(abs(sa) ** 0.55, sa)
        # wider along the brow, narrower at the cheek: the wayfarer's trapezoid; the outer top corner lifted
        widen = 1.0 + 0.16 * (zt / (h / 2))
        x = cx + (w / 2) * widen * math.copysign(abs(ca) ** 0.5, ca)
        z = cz + zt + (0.006 if (sa > 0.5 and ca * sx > 0.3) else 0.0)
        y = face_y_at(x, z) - 0.011
        pts.append(Vector((x, y, z)))
        sides.append(Vector((x - cx, 0, z - cz)))
        nrm.append(Vector((0, -1, 0)))
        inner.append(Vector((cx + (x - cx) * 0.9, y + 0.001, cz + (z - cz) * 0.88)))
    ring_sweep(bm, pts, sides, nrm, 0.012, 0.009, mat_index=0)
    # the lens: a fan inside the rim, a hair behind the frame's front
    c = bm.verts.new(Vector((cx, face_y_at(cx, cz) - 0.010, cz)))
    ring = [bm.verts.new(p) for p in inner[:-1]]
    for i in range(len(ring)):
        bm.faces.new((c, ring[i], ring[(i + 1) % len(ring)])).material_index = 1
# the bridge: a thick bar between the two brow lines
br = [Vector((x, face_y_at(x, 1.575) - 0.013, 1.575)) for x in (-0.012, -0.004, 0.004, 0.012)]
tube(bm, br, 0.0045, seg=10)
wf = new_object('acc_wayfarers', bm, [mat('wayfarer', (0.95, 0.95, 0.95), outline=0.003), mat('lens_dark', (0.03, 0.035, 0.04), outline=0.0, double_sided=True)])
bone_parent(wf, arm, 'head')
log('acc_wayfarers verts', len(wf.data.vertices))

# ---- the cord necklace: a loop round the base of the neck, dipping into the open collar
ba = bpy.data.objects['BodyActual']
Wb = ba.matrix_world
nz = bone('neck').z - 0.02
ring_pts = [Wb @ v.co for v in ba.data.vertices if abs((Wb @ v.co).z - nz) < 0.012 and (Wb @ v.co).length < 3]
cxy = Vector((sum(p.x for p in ring_pts) / len(ring_pts), sum(p.y for p in ring_pts) / len(ring_pts), nz)) if ring_pts else Vector((0, 0, nz))
R = (max((Vector((p.x - cxy.x, p.y - cxy.y, 0)).length for p in ring_pts), default=0.06)) + 0.008
R = min(R, 0.09)
pts = []
for i in range(48):
    a = 2 * math.pi * i / 48
    front = max(0.0, -math.sin(a))                                   # -y is the front
    pts.append(Vector((cxy.x + R * math.cos(a) * (1 + 0.15 * front), cxy.y + R * math.sin(a) - 0.01 * front, nz - 0.07 * front ** 3)))
bm = bmesh.new()
tube(bm, pts, 0.0022, seg=8, closed=True)
cord = new_object('acc_cord', bm, [mat('cord_black', (0.05, 0.05, 0.05), outline=0.0)])
bone_parent(cord, arm, 'chest')
log('acc_cord radius', round(R, 3), 'at z', round(nz, 3))

for n in LAYERS:
    bpy.data.objects[n].hide_set(False)
bpy.ops.wm.save_mainfile(filepath=SRC)
log('saved', SRC)
