"""RECIPE (as run for the DAISY music video, 2026-09). Its stage inputs were working files that are not kept
here; claude_suit_wardrobe.blend is the finished, editable result. Read README.md in this folder first.

Era accessories for digi's claudesona, bone-parented into the same VRM as both outfits.

    bash run_blender.sh eidoverse/assets/vrms/claude_suit_wardrobe_src/build_accessories.py [--export]

acc_glasses (1961 horn-rims) · acc_headset (1939 operator) · acc_pocket (1961 pocket protector + pens)
acc_bowtie (1984, green silk) · acc_headband (1982 terry, pink/teal) · acc_ribbons (2007 teal bows + tails)
Loads cyclist_tex.blend (suit + cyclist), adds these and saves cyclist_acc.blend (build_era_garments.py builds on
it and exports the VRM; --export writes a stage check to work/claude_suit_accessories_stage.vrm). Review them in the engine with vrm_turntable.py (repo root) —
MToon in eidoverse is the truth, not EEVEE. The film shows each accessory only in its era.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')
REPO = os.path.dirname(os.path.abspath(__file__))
while REPO != os.path.dirname(REPO) and not os.path.exists(os.path.join(REPO, 'eido.py')):
    REPO = os.path.dirname(REPO)
BL = os.path.dirname(os.path.abspath(__file__))


def log(*a):
    print('[acc]', *a, flush=True)


def mat(name, rgb, outline=0.004, double_sided=False):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    ext = m.vrm_addon_extension.mtoon1
    ext.enabled = True
    ext.pbr_metallic_roughness.base_color_factor = (*rgb, 1.0)
    mt = ext.extensions.vrmc_materials_mtoon
    mt.shade_color_factor = tuple(c * 0.58 for c in rgb)
    mt.outline_width_mode = 'worldCoordinates'
    mt.outline_width_factor = outline
    mt.outline_color_factor = tuple(c * 0.25 for c in rgb)
    mt.outline_lighting_mix_factor = 0.0
    mt.parametric_rim_color_factor = (0.0, 0.0, 0.0)        # a grey rim washed small pieces out (pale bow tie, silver rims)
    ext.double_sided = double_sided
    return m


def obj_from_bm(bm, name, material, bone, arm, smooth=True):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    bpy.data.objects['shirt'].users_collection[0].objects.link(o)
    if isinstance(material, list):
        for m in material:
            me.materials.append(m)
    else:
        me.materials.append(material)
    mw = o.matrix_world.copy()
    o.parent = arm
    o.parent_type = 'BONE'
    o.parent_bone = bone
    bpy.context.view_layer.update()
    o.matrix_world = mw
    return o


def ring_sweep(bm, pts, sides, normals, w, th, mat_index=0, cap=True):
    """a rectangular section swept along pts; sides/normals give the width and thickness directions"""
    rings = []
    for p, s, n in zip(pts, sides, normals):
        s, n = s.normalized(), n.normalized()
        rings.append([bm.verts.new(p + s * sx * w / 2 + n * nx * th / 2) for sx, nx in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    for a, b in zip(rings, rings[1:]):
        for i in range(4):
            j = (i + 1) % 4
            f = bm.faces.new((a[i], a[j], b[j], b[i]))
            f.material_index = mat_index
    if cap:
        bm.faces.new(rings[0][::-1]).material_index = mat_index
        bm.faces.new(rings[-1]).material_index = mat_index
    return rings


def tube(bm, pts, r, seg=12, mat_index=0):
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = t.orthogonal().normalized()
        b = t.cross(a).normalized()
        rings.append([bm.verts.new(p + (a * math.cos(2 * math.pi * k / seg) + b * math.sin(2 * math.pi * k / seg)) * r) for k in range(seg)])
    for ra, rb in zip(rings, rings[1:]):
        for k in range(seg):
            bm.faces.new((ra[k], ra[(k + 1) % seg], rb[(k + 1) % seg], rb[k])).material_index = mat_index
    bm.faces.new(rings[0][::-1]).material_index = mat_index
    bm.faces.new(rings[-1]).material_index = mat_index


def cylinder(bm, c, axis, r, length, seg=24, r2=None, mat_index=0):
    axis = axis.normalized()
    a = axis.orthogonal().normalized()
    b = axis.cross(a).normalized()
    r2 = r if r2 is None else r2
    lo = [bm.verts.new(c - axis * length / 2 + (a * math.cos(2 * math.pi * k / seg) + b * math.sin(2 * math.pi * k / seg)) * r) for k in range(seg)]
    hi = [bm.verts.new(c + axis * length / 2 + (a * math.cos(2 * math.pi * k / seg) + b * math.sin(2 * math.pi * k / seg)) * r2) for k in range(seg)]
    for k in range(seg):
        bm.faces.new((lo[k], lo[(k + 1) % seg], hi[(k + 1) % seg], hi[k])).material_index = mat_index
    bm.faces.new(lo[::-1]).material_index = mat_index
    bm.faces.new(hi).material_index = mat_index


def ellipsoid(bm, c, radii, seg=16, rings=10, shape=None, mat_index=0):
    """shape(x_norm, v) -> scale on (y,z) for pinched forms (bow wings)"""
    verts = []
    for i in range(rings + 1):
        th = math.pi * i / rings
        row = []
        for k in range(seg):
            ph = 2 * math.pi * k / seg
            x, y, z = math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)
            s = shape(x) if shape else 1.0
            row.append(bm.verts.new(c + Vector((x * radii[0], y * radii[1] * s, z * radii[2] * s))))
        verts.append(row)
    for i in range(rings):
        for k in range(seg):
            a, b = verts[i][k], verts[i][(k + 1) % seg]
            cc, d = verts[i + 1][(k + 1) % seg], verts[i + 1][k]
            if i == 0:
                bm.faces.new((a, cc, d)).material_index = mat_index if a != b else mat_index
            else:
                bm.faces.new((a, b, cc, d)).material_index = mat_index
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)


def ribbon(bm, pts, widths, twist, notch=0.012, mat_index=0):
    """a flat satin strip along pts: three columns (left, middle, right), the width direction twisting about the
    path by `twist` radians per point, the end cut as a swallowtail (the middle pulled back by `notch`)"""
    n = len(pts)
    rows = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        side = Matrix.Rotation(twist[i], 3, t) @ t.cross(Vector((0, -1, 0))).normalized()
        w = widths[i]
        mid = p - t * notch if i == n - 1 else p
        rows.append([bm.verts.new(p - side * w / 2), bm.verts.new(mid), bm.verts.new(p + side * w / 2)])
    for a, b in zip(rows, rows[1:]):
        bm.faces.new((a[0], a[1], b[1], b[0])).material_index = mat_index
        bm.faces.new((a[1], a[2], b[2], b[1])).material_index = mat_index


def face_y_at(x, z, face_pts):
    """front surface of the face dome near (x, z)"""
    near = [p for p in face_pts if abs(p.x - x) < 0.02 and abs(p.z - z) < 0.02]
    return min(p.y for p in near) if near else -0.12


def build(arm):
    face = bpy.data.objects['face']
    fpts = [face.matrix_world @ v.co for v in face.data.vertices]
    body = bpy.data.objects['Body']
    bpts = [body.matrix_world @ v.co for v in body.data.vertices]
    front_y = min(p.y for p in bpts) - 0.007
    out = {}

    # ---- 1961 horn-rims: two rounded frames following the face dome, a keyhole bridge
    bm = bmesh.new()
    for sx in (-1, 1):
        cx, cz, w, h, r = sx * 0.048, 1.553, 0.09, 0.065, 0.022
        n = 40
        pts, sides, nrm = [], [], []
        for i in range(n + 1):
            a = 2 * math.pi * i / n
            # superellipse: a rounded rectangle
            ca, sa = math.cos(a), math.sin(a)
            x = cx + (w / 2) * math.copysign(abs(ca) ** 0.45, ca)
            z = cz + (h / 2) * math.copysign(abs(sa) ** 0.45, sa)
            y = face_y_at(x, z, bpts + fpts) - 0.009
            pts.append(Vector((x, y, z)))
            sides.append(Vector((x - cx, 0, z - cz)))
            nrm.append(Vector((0, -1, 0)))
        ring_sweep(bm, pts, sides, nrm, 0.0085, 0.0065, cap=False)
    br = [Vector((sx * 0.009, front_y - 0.008, 1.566 + 0.004 * (1 - abs(sx) / 0.009) ** 2)) for sx in (-0.009, -0.004, 0.0, 0.004, 0.009)]
    tube(bm, br, 0.0032, seg=10)
    out['acc_glasses'] = obj_from_bm(bm, 'acc_glasses', mat('acetate', (0.05, 0.04, 0.045)), 'head', arm)

    # ---- 1939 operator headset: band over the disc, receiver at the right, arm + horn to the mouth
    bm = bmesh.new()
    cz, R, y0 = 1.53, 0.176, -0.07
    pts, sides, nrm = [], [], []
    for i in range(41):
        a = math.radians(12 + 156 * i / 40)
        pts.append(Vector((R * math.cos(a), y0, cz + R * math.sin(a))))
        sides.append(Vector((0, 1, 0)))
        nrm.append(Vector((math.cos(a), 0, math.sin(a))))
    ring_sweep(bm, pts, sides, nrm, 0.02, 0.006, mat_index=0)
    rc = Vector((R + 0.012, y0, cz - 0.01))
    cylinder(bm, rc, Vector((1, 0, 0)), 0.036, 0.024, seg=32, r2=0.03, mat_index=1)
    cylinder(bm, rc + Vector((0.016, 0, 0)), Vector((1, 0, 0)), 0.018, 0.012, seg=24, mat_index=2)
    arm_pts = [rc + Vector((-0.004, -0.03, -0.03)), Vector((0.16, -0.125, 1.475)), Vector((0.11, -0.16, 1.462)), Vector((0.055, -0.172, 1.458))]
    fine = []
    for i in range(len(arm_pts) - 1):
        for k in range(8):
            fine.append(arm_pts[i].lerp(arm_pts[i + 1], k / 8))
    fine.append(arm_pts[-1])
    tube(bm, fine, 0.0042, seg=10, mat_index=2)
    mouth = Vector((0.0, -0.13, 1.476))
    hc = arm_pts[-1]
    cylinder(bm, hc + (mouth - hc).normalized() * 0.015, (mouth - hc), 0.007, 0.03, seg=24, r2=0.022, mat_index=1)
    out['acc_headset'] = obj_from_bm(bm, 'acc_headset', [mat('leather_black', (0.08, 0.06, 0.05)),
                                                          mat('bakelite', (0.035, 0.03, 0.035)),
                                                          mat('nickel', (0.72, 0.72, 0.74))], 'head', arm)

    # ---- 1961 pocket protector with three pens, on the jacket's left chest
    bm = bmesh.new()
    pc = Vector((0.078, -0.101, 1.205))
    cylinder(bm, pc, Vector((0, 1, 0)), 0.001, 0.001)          # (cheap anchor, removed by the box below)
    bmesh.ops.delete(bm, geom=bm.verts[:], context='VERTS')
    box = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(0.052, 0.005, 0.08), verts=box['verts'])
    bmesh.ops.translate(bm, vec=pc, verts=box['verts'])
    flap = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(0.054, 0.004, 0.018), verts=flap['verts'])
    bmesh.ops.rotate(bm, cent=Vector((0, 0, 0)), matrix=Matrix.Rotation(math.radians(-25), 3, 'X'), verts=flap['verts'])
    bmesh.ops.translate(bm, vec=pc + Vector((0, -0.006, 0.044)), verts=flap['verts'])
    for f in bm.faces:
        f.material_index = 0
    for i, (dx, mi) in enumerate(((-0.015, 1), (0.0, 2), (0.015, 3))):
        cylinder(bm, pc + Vector((dx, -0.004, 0.048)), Vector((0, 0, 1)), 0.0048, 0.05, seg=16, mat_index=mi)
        cylinder(bm, pc + Vector((dx, -0.004, 0.075)), Vector((0, 0, 1)), 0.0048, 0.004, seg=16, r2=0.0015, mat_index=4)
        clip = bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(0.0025, 0.0015, 0.026), verts=clip['verts'])
        bmesh.ops.translate(bm, vec=pc + Vector((dx, -0.0095, 0.052)), verts=clip['verts'])
        for v in clip['verts']:
            for f in v.link_faces:
                f.material_index = 4
    out['acc_pocket'] = obj_from_bm(bm, 'acc_pocket', [mat('vinyl', (0.93, 0.93, 0.95)), mat('pen_red', (0.75, 0.08, 0.07)),
                                                        mat('pen_blue', (0.09, 0.18, 0.62)), mat('pen_black', (0.04, 0.04, 0.05)),
                                                        mat('chrome', (0.8, 0.8, 0.82))], 'chest', arm, smooth=False)

    # ---- 1984 green silk bow tie at the collar
    bm = bmesh.new()
    kc = Vector((0.0, -0.104, 1.333))
    for sx in (-1, 1):
        ellipsoid(bm, kc + Vector((sx * 0.034, 0, 0)), (0.034, 0.011, 0.026), seg=24, rings=12,
                  shape=lambda x, sx=sx: 0.35 + 0.65 * min(1.0, abs(x * sx + 1) / 1.6))
    ellipsoid(bm, kc + Vector((0, -0.003, 0)), (0.011, 0.01, 0.013), seg=16, rings=8)
    out['acc_bowtie'] = obj_from_bm(bm, 'acc_bowtie', mat('silk_green', (0.012, 0.15, 0.045)), 'chest', arm)

    # ---- 1982 terry sweatband across the forehead (pink, teal stripe)
    bm = bmesh.new()
    zb = 1.64
    xs = [x / 100 for x in range(-13, 14)]
    pts = [Vector((x, face_y_at(x, zb, fpts + bpts) - 0.006, zb)) for x in xs]
    ring_sweep(bm, pts, [Vector((0, 0, 1))] * len(pts), [Vector((0, -1, 0))] * len(pts), 0.032, 0.007, mat_index=0)
    pts2 = [p + Vector((0, -0.0045, 0)) for p in pts]
    ring_sweep(bm, pts2, [Vector((0, 0, 1))] * len(pts), [Vector((0, -1, 0))] * len(pts), 0.008, 0.002, mat_index=1)
    out['acc_headband'] = obj_from_bm(bm, 'acc_headband', [mat('terry_pink', (1.0, 0.33, 0.62)), mat('terry_teal', (0.1, 0.8, 0.78))], 'head', arm)

    # ---- 2007 teal ribbon bows in the petals, with tails
    bm = bmesh.new()
    teal = mat('satin_teal', (0.22, 0.77, 0.73), double_sided=True)
    for sx in (-1, 1):
        bc = Vector((sx * 0.25, -0.078, 1.74))                    # clipped onto the front of the petals
        for lx in (-1, 1):
            ellipsoid(bm, bc + Vector((lx * 0.036, 0, 0.005)), (0.036, 0.012, 0.024), seg=20, rings=10,
                      shape=lambda x, lx=lx: 0.4 + 0.6 * min(1.0, abs(x * lx + 1) / 1.6))
        ellipsoid(bm, bc, (0.012, 0.012, 0.014), seg=12, rings=8)
        for j, (dx, spread, ph) in enumerate(((-0.006, 1.0, 0.0), (0.007, 0.55, 1.9))):
            n, L = 18, 0.2
            pts, wid, tw = [], [], []
            for i in range(n + 1):
                k = i / n
                pts.append(bc + Vector((dx + sx * spread * (0.01 + 0.05 * k ** 1.3),
                                        -0.004 - 0.012 * math.sin(k * math.pi * 1.5 + ph),
                                        -0.012 - L * k)))
                wid.append(0.027 - 0.005 * k)
                tw.append((0.35 + 0.95 * k) * (1 if j == 0 else -1) * sx + 0.18 * math.sin(3.0 * k + ph))
            ribbon(bm, pts, wid, tw, notch=0.013)
    out['acc_ribbons'] = obj_from_bm(bm, 'acc_ribbons', teal, 'head', arm)
    return out


def looks(objs):
    sc = bpy.context.scene
    eng = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in eng else 'BLENDER_EEVEE_NEXT'
    sc.render.resolution_x, sc.render.resolution_y = 700, 700
    if not sc.world:
        sc.world = bpy.data.worlds.new('w')
    sc.world.color = (0.09, 0.1, 0.12)
    cam = bpy.data.objects.new('acc_cam', bpy.data.cameras.new('acc_cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    sun = bpy.data.objects.new('acc_sun', bpy.data.lights.new('acc_sun', 'SUN'))
    sun.data.energy = 3.2
    sun.rotation_euler = (math.radians(55), 0, math.radians(25))
    sc.collection.objects.link(sun)
    for n in ('jersey', 'knickers', 'socks', 'boater', 'boater_band'):
        bpy.data.objects[n].hide_render = True
    looks_ = {'1939_headset': ['acc_headset'], '1961_glasses_pocket': ['acc_glasses', 'acc_pocket'],
              '1982_headband': ['acc_headband'], '1984_bowtie': ['acc_bowtie'], '2007_ribbons': ['acc_ribbons']}
    for tag, show in looks_.items():
        for n in objs:
            bpy.data.objects[n].hide_render = n not in show
        for ang in (-25, 20):
            a = math.radians(ang)
            cam.location = (math.sin(a) * 1.35, -math.cos(a) * 1.35, 1.46)
            cam.rotation_euler = (math.radians(92), 0, a)
            cam.data.lens = 50
            sc.render.filepath = os.path.join(BL, f'acc_{tag}_{ang}.png')
            bpy.ops.render.render(write_still=True)
    for n in objs:
        bpy.data.objects[n].hide_render = False
    for n in ('jersey', 'knickers', 'socks', 'boater', 'boater_band'):
        bpy.data.objects[n].hide_render = False
    bpy.data.objects.remove(cam, do_unlink=True)
    bpy.data.objects.remove(sun, do_unlink=True)


bpy.ops.wm.open_mainfile(filepath=os.path.join(BL, 'cyclist_tex.blend'))
for n in list(bpy.data.objects.keys()):
    if n.startswith('acc_') or n in ('look_cam', 'look_sun'):
        bpy.data.objects.remove(bpy.data.objects[n], do_unlink=True)
arm = bpy.data.objects['Armature']
objs = build(arm)
log('built', list(objs))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BL, 'cyclist_acc.blend'))
if '--export' in sys.argv:
    out = os.path.join(REPO, 'work', 'claude_suit_accessories_stage.vrm')   # never the library VRM: a subset
    os.makedirs(os.path.dirname(out), exist_ok=True)
    res = bpy.ops.export_scene.vrm(filepath=out, export_invisibles=True, export_only_selections=False)
    log('export', res, os.path.getsize(out))
