# build_crowd.py — the mourners: four stylized, featureless figure variants for the
# DAISY funeral crowd (instanced ~200x in the engine). Built like a figure study:
# a skinned-armature mass for body + limbs, an ellipsoid head, and clothing masses
# (long coat / hoodie + hood / long hair + long skirt / puffer + beanie + backpack).
# The RIGHT arm (with its phone) is its own part pinned at the shoulder so the
# engine can raise it on the GPU. No faces, no features: non-identifiable by
# construction.
#   blender --background --python build_crowd.py [-- preview]
# COLOR_0: R = phone-arm mask (rotates about SHOULDER), G = phone screen,
#          B = head mask (rotates about NECK for the bowed/lifted posture).
import sys
import os
import math
import json
import bpy
import bmesh
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib
import fx_core
importlib.reload(fx_core)
from fx_core import reset_scene, ASSETS, T2B, material, preview, apply_modifiers

reset_scene()
col = bpy.context.scene.collection
SHOULDER = (-0.205, 1.425, -0.01)     # right shoulder pivot (three space)
NECK = (0.0, 1.52, -0.02)             # head pivot
B2T = Matrix(T2B).inverted()


def link(name, me):
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob


def skin_part(name, verts, edges, radii, subsurf=1, root=0):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(T2B @ Vector(v)) for v in verts], edges, [])
    ob = link(name, me)
    sk = ob.modifiers.new('skin', 'SKIN')
    sk.use_smooth_shade = True
    sk.branch_smoothing = 0.8
    for i, r in enumerate(radii):
        me.skin_vertices[0].data[i].radius = r
    me.skin_vertices[0].data[root].use_root = True
    ss = ob.modifiers.new('sub', 'SUBSURF')
    ss.levels = subsurf
    apply_modifiers(ob)
    return ob


def ellipsoid(name, c, r, segs=20, rings=14, cut_below=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * r[0], v.co.z * r[1], v.co.y * r[2]))      # built in three space: (x, y-up, z)
    if cut_below is not None:
        kill = [v for v in bm.verts if v.co.y < cut_below]
        bmesh.ops.delete(bm, geom=kill, context='VERTS')
    bmesh.ops.translate(bm, vec=Vector(c), verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.transform(T2B)
    ob = link(name, me)
    if cut_below is not None:
        s = ob.modifiers.new('sol', 'SOLIDIFY')
        s.thickness = 0.012
        apply_modifiers(ob)
    return ob


def lathe_shell(name, prof, segs, c, sz=0.7, zoff=None, thick=0.014):
    """a revolved clothing shell with an elliptical plan (sz squashes front-back);
    zoff(y) shifts the section centre in z along the height."""
    bm = bmesh.new()
    rings = []
    for r, y in prof:
        dz = zoff(y) if zoff else 0.0
        rings.append([bm.verts.new((c[0] + r * math.cos(2 * math.pi * i / segs), c[1] + y,
                                    c[2] + dz + r * sz * math.sin(2 * math.pi * i / segs))) for i in range(segs)])
    for k in range(len(rings) - 1):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new([rings[k][i], rings[k + 1][i], rings[k + 1][j], rings[k][j]])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.transform(T2B)
    ob = link(name, me)
    s = ob.modifiers.new('sol', 'SOLIDIFY')
    s.thickness = thick
    s.offset = 1.0
    ss = ob.modifiers.new('sub', 'SUBSURF')
    ss.levels = 1
    apply_modifiers(ob)
    return ob


def box_obj(name, c, s, bev=0.3):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * s[0], v.co.y * s[1], v.co.z * s[2]))
    bmesh.ops.translate(bm, vec=Vector(c), verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.transform(T2B)
    ob = link(name, me)
    b = ob.modifiers.new('bev', 'BEVEL')
    b.width = min(s) * bev
    b.segments = 3
    apply_modifiers(ob)
    return ob


def paint(ob, fn):
    me = ob.data
    ca = me.color_attributes.get('Col') or me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
    for i, v in enumerate(me.vertices):
        p = B2T @ v.co
        ca.data[i].color = (*fn(p), 1.0)
    return ob


def body(variant):
    """torso, neck, legs and the LEFT arm (static pose per variant)."""
    bulk = 1.12 if variant == 3 else 1.0          # puffer jacket
    V = [
        (0.0, 0.95, 0.0),        # 0 pelvis (root)
        (0.0, 1.1, 0.012),       # 1 waist
        (0.0, 1.29, 0.01),       # 2 chest
        (0.0, 1.41, -0.012),     # 3 upper chest
        (0.0, 1.5, -0.02),       # 4 neck base
        (0.0, 1.58, -0.012),     # 5 neck top
        (0.205, 1.425, -0.01),   # 6 L shoulder
        (-0.205, 1.425, -0.01),  # 7 R shoulder stub (the arm part covers it)
        (0.1, 0.92, 0.0),        # 8 L hip
        (0.105, 0.5, 0.022),     # 9 L knee
        (0.105, 0.085, -0.005),  # 10 L ankle
        (0.105, 0.035, 0.125),   # 11 L toe
        (-0.1, 0.92, 0.0),       # 12 R hip
        (-0.105, 0.5, 0.022),    # 13 R knee
        (-0.105, 0.085, -0.005), # 14 R ankle
        (-0.105, 0.035, 0.125),  # 15 R toe
    ]
    E = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (3, 6), (3, 7), (0, 8), (8, 9), (9, 10), (10, 11),
         (0, 12), (12, 13), (13, 14), (14, 15)]
    R = [(0.175 * bulk, 0.12 * bulk), (0.158 * bulk, 0.108 * bulk), (0.19 * bulk, 0.128 * bulk),
         (0.2 * bulk, 0.115 * bulk), (0.062, 0.06), (0.052, 0.052), (0.075 * bulk, 0.07 * bulk),
         (0.075 * bulk, 0.07 * bulk), (0.095, 0.095), (0.065, 0.068), (0.045, 0.048), (0.045, 0.035),
         (0.095, 0.095), (0.065, 0.068), (0.045, 0.048), (0.045, 0.035)]
    if variant == 1:      # hand in the hoodie pocket
        arm = [(0.24, 1.17, 0.03), (0.16, 1.04, 0.13), (0.07, 1.0, 0.14)]
    elif variant == 2:    # hands folded in front, holding the other wrist
        arm = [(0.235, 1.17, 0.05), (0.13, 1.03, 0.16), (0.01, 1.0, 0.17)]
    else:                 # hanging, relaxed
        arm = [(0.24, 1.15, 0.0), (0.25, 0.9, 0.035), (0.25, 0.8, 0.045)]
    b = len(V)
    V += arm
    E += [(6, b), (b, b + 1), (b + 1, b + 2)]
    R += [(0.058 * bulk, 0.058 * bulk), (0.042, 0.04), (0.046, 0.028)]
    ob = skin_part('body%d' % variant, V, E, R)
    return paint(ob, lambda p: (0, 0, 1 if p.y > 1.54 else 0))


def head(variant):
    h = ellipsoid('head', (0.0, 1.675, 0.012), (0.086, 0.112, 0.099))
    return paint(h, lambda p: (0, 0, 1))


def phone_arm(variant):
    bulk = 1.12 if variant == 3 else 1.0
    V = [SHOULDER, (-0.24, 1.15, 0.0), (-0.25, 0.9, 0.035), (-0.25, 0.8, 0.045)]
    arm = skin_part('parm', V, [(0, 1), (1, 2), (2, 3)],
                    [(0.068 * bulk, 0.064 * bulk), (0.056 * bulk, 0.056 * bulk), (0.042, 0.04), (0.046, 0.028)])
    paint(arm, lambda p: (1, 0, 0))
    # the phone: a slab in the hand, screen facing +y in the hanging pose (it faces the
    # owner's face once the engine swings the arm up to the hold angle)
    ph = box_obj('phone', (-0.25, 0.79, 0.075), (0.074, 0.011, 0.148), bev=0.25)
    paint(ph, lambda p: (1, 1 if p.y > 0.7945 else 0, 0))
    return [arm, ph]


def chain(name, pts, radii, fn=lambda p: (0, 0, 0), subsurf=1, cut_y=None):
    ob = skin_part(name, pts, [(i, i + 1) for i in range(len(pts) - 1)], radii, subsurf=subsurf)
    if cut_y is not None:        # a hem, not a sack: slice off the skin's rounded end cap
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, cut_y),
                               plane_no=(0, 0, 1), clear_inner=True)
        bm.to_mesh(ob.data)
        bm.free()
    return paint(ob, fn)


def clothes(variant):
    out = []
    headmask = lambda p: (0, 0, 1 if p.y > 1.54 else 0)
    if variant == 0:      # long wool coat, shoulders to below the knee, turned-up collar; short hair
        out.append(chain('coat', [(0, 1.5, -0.02), (0, 1.43, -0.012), (0, 1.27, 0.005), (0, 1.08, 0.01),
                                  (0, 0.9, 0.0), (0, 0.68, 0.0), (0, 0.46, 0.0)],
                         [(0.095, 0.085), (0.222, 0.128), (0.205, 0.138), (0.182, 0.128), (0.2, 0.132),
                          (0.218, 0.14), (0.232, 0.145)], headmask, cut_y=0.5))
        out.append(chain('collar', [(0, 1.47, -0.03), (0, 1.585, -0.035)], [(0.105, 0.095), (0.098, 0.09)],
                         headmask, subsurf=1))
        out.append(paint(ellipsoid('hair', (0.0, 1.705, -0.014), (0.094, 0.1, 0.104), cut_below=-0.025),
                         lambda p: (0, 0, 1)))
    elif variant == 1:    # hoodie with the hood UP, kangaroo pocket
        out.append(chain('hoodie', [(0, 1.5, -0.02), (0, 1.42, -0.012), (0, 1.25, 0.008), (0, 1.05, 0.012),
                                    (0, 0.86, 0.004)],
                         [(0.1, 0.09), (0.218, 0.13), (0.205, 0.14), (0.19, 0.135), (0.188, 0.128)], headmask,
                         cut_y=0.9))
        out.append(paint(ellipsoid('hood', (0.0, 1.692, -0.04), (0.118, 0.142, 0.132)), lambda p: (0, 0, 1)))
        out.append(paint(box_obj('pocket', (0.0, 1.0, 0.125), (0.22, 0.14, 0.03), bev=0.4), lambda p: (0, 0, 0)))
    elif variant == 2:    # long hair to the shoulder blades + a long A-line skirt
        out.append(paint(ellipsoid('hair', (0.0, 1.69, -0.02), (0.1, 0.122, 0.11)), lambda p: (0, 0, 1)))
        out.append(chain('hairfall', [(0, 1.62, -0.065), (0, 1.45, -0.105), (0, 1.3, -0.11)],
                         [(0.1, 0.05), (0.11, 0.045), (0.09, 0.03)], lambda p: (0, 0, 1 if p.y > 1.54 else 0.4)))
        out.append(chain('skirt', [(0, 1.08, 0.01), (0, 0.9, 0.0), (0, 0.6, 0.0), (0, 0.24, 0.0)],
                         [(0.162, 0.115), (0.205, 0.145), (0.24, 0.17), (0.27, 0.19)], cut_y=0.27))
    elif variant == 3:    # quilted puffer + beanie + backpack
        pts, rad = [], []
        for k in range(9):
            y = 1.45 - k * 0.075
            bump = 0.012 if k % 2 == 0 else -0.006
            pts.append((0, y, -0.004))
            w = 0.232 if k == 0 else (0.215 - 0.02 * math.sin(k / 8 * math.pi) + bump)
            rad.append((w, 0.14 + bump))
        out.append(chain("puffer", pts, rad, subsurf=1))
        out.append(chain('puffer_collar', [(0, 1.47, -0.03), (0, 1.56, -0.03)], [(0.1, 0.095), (0.092, 0.088)],
                         headmask, subsurf=1))
        out.append(paint(ellipsoid('beanie', (0.0, 1.715, -0.006), (0.095, 0.1, 0.105), cut_below=-0.035),
                         lambda p: (0, 0, 1)))
        out.append(paint(lathe_shell('beanie_band', [(0.098, 1.68), (0.099, 1.71)], 28, (0, 0, -0.006), sz=1.08,
                                     thick=0.012), lambda p: (0, 0, 1)))
        out.append(paint(box_obj('pack', (0.0, 1.2, -0.225), (0.3, 0.44, 0.17), bev=0.35), lambda p: (0, 0, 0)))
        for sg in (-1, 1):
            out.append(paint(box_obj('strap', (sg * 0.11, 1.33, -0.03), (0.045, 0.32, 0.29), bev=0.2),
                             lambda p: (0, 0, 0)))
    return out


rig = {'shoulder': list(SHOULDER), 'neck': list(NECK), 'hand': [-0.25, 0.79, 0.075], 'variants': []}
objs = []
for v in range(4):
    parts = [body(v), head(v)] + phone_arm(v) + clothes(v)
    for o in bpy.data.objects:
        o.select_set(False)
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = 'person_%d' % v
    ob.data.name = 'person_%d' % v
    ob.data.materials.clear()
    ob.data.materials.append(material('fabric'))
    ob.data.color_attributes.active_color = ob.data.color_attributes['Col']
    for p in ob.data.polygons:
        p.use_smooth = True
    objs.append(ob)
    rig['variants'].append({'name': ob.name, 'tris': sum(len(p.vertices) - 2 for p in ob.data.polygons)})
    ob.location.x = (v - 1.5) * 0.75

json.dump(rig, open(ASSETS + '/crowd_rig.json', 'w'), indent=1)
print('[crowd]', rig)
if 'preview' in sys.argv:
    preview(ASSETS + '/../probes/crowd_prev.png', [((0.0, 1.15, 3.5), (0.0, 1.0, 0.0), 38),
                                                   ((2.4, 1.4, -2.4), (0.0, 1.0, 0.0), 40),
                                                   ((-3.4, 1.0, 0.3), (0.0, 1.0, 0.0), 38)])
for ob in objs:
    ob.location.x = 0.0
bpy.ops.export_scene.gltf(filepath=ASSETS + '/crowd.glb', export_format='GLB', use_selection=False, export_apply=True,
                          export_yup=True, export_vertex_color='ACTIVE', export_all_vertex_colors=False,
                          export_materials='EXPORT', export_animations=False)
print('[fx] exported crowd.glb', os.path.getsize(ASSETS + '/crowd.glb') // 1024, 'KB')
sys.stdout.flush()
os._exit(0)      # hard exit: user add-ons hang Blender's background exit
