"""Take stock of the wardrobe base before cutting the tuta: objects, bones, the shirt/pants/shoes boundaries (digi's
split seams), the face disc and the eye plate. Read-only on the library .blend; writes look renders to work/claude_suit_wardrobe_looks/.

    bash run_blender.sh eidoverse/assets/vrms/claude_suit_wardrobe_src/inspect_base.py
"""
import math
import os

import bmesh
import bpy
from mathutils import Vector

bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = HERE
while REPO != os.path.dirname(REPO) and not os.path.exists(os.path.join(REPO, 'eido.py')):
    REPO = os.path.dirname(REPO)
SRC = os.path.join(REPO, 'eidoverse', 'assets', 'vrms', 'claude_suit_wardrobe_src', 'claude_suit_wardrobe.blend')
bpy.ops.wm.open_mainfile(filepath=SRC)


def log(*a):
    print('[ins]', *a, flush=True)


arm = bpy.data.objects['Armature']
for o in sorted(bpy.data.objects, key=lambda o: o.name):
    if o.type != 'MESH':
        log('obj', o.name, o.type)
        continue
    me = o.data
    W = o.matrix_world
    pts = [W @ v.co for v in me.vertices]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    sk = len(me.shape_keys.key_blocks) if me.shape_keys else 0
    log(f'mesh {o.name:16s} v {len(me.vertices):6d} f {len(me.polygons):6d} mats {[m.name for m in me.materials if m]} uv {[u.name for u in me.uv_layers]} '
        f'sk {sk} vg {len(o.vertex_groups)} mods {[m.type for m in o.modifiers]} parent {o.parent.name if o.parent else None}/{o.parent_bone} '
        f'min {tuple(round(c, 3) for c in mn)} max {tuple(round(c, 3) for c in mx)} hidden {o.hide_get()} hr {o.hide_render}')

for bn in ('hips', 'spine', 'chest', 'neck', 'head', 'shoulder.L', 'upper_arm.L', 'forearm.L', 'hand.L', 'shoulder.R', 'upper_arm.R',
           'forearm.R', 'hand.R', 'upper_leg.L', 'lower_leg.L', 'foot.L', 'toe.L'):
    b = arm.data.bones.get(bn)
    if b:
        log(f'bone {bn:12s} head {tuple(round(c, 3) for c in (arm.matrix_world @ b.head_local))} tail {tuple(round(c, 3) for c in (arm.matrix_world @ b.tail_local))}')
    else:
        log('bone missing', bn)
log('all bones', ' '.join(b.name for b in arm.data.bones))


def boundary_loops(name):
    o = bpy.data.objects[name]
    W = o.matrix_world
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bnd = [e for e in bm.edges if e.is_boundary]
    seen, loops = set(), []
    adj = {}
    for e in bnd:
        for v in e.verts:
            adj.setdefault(v.index, []).append(e)
    for e0 in bnd:
        if e0.index in seen:
            continue
        stack, comp = [e0], []
        while stack:
            e = stack.pop()
            if e.index in seen:
                continue
            seen.add(e.index)
            comp.append(e)
            for v in e.verts:
                for e2 in adj[v.index]:
                    if e2.index not in seen:
                        stack.append(e2)
        loops.append(comp)
    log(f'{name}: verts {len(bm.verts)} faces {len(bm.faces)} boundary edges {len(bnd)} loops {len(loops)}')
    for comp in sorted(loops, key=lambda c: -len(c)):
        ps = [W @ ((e.verts[0].co + e.verts[1].co) / 2) for e in comp]
        c = sum(ps, Vector()) / len(ps)
        log(f'   loop {len(comp):4d} edges  centre {tuple(round(x, 3) for x in c)}  x {min(p.x for p in ps):.3f}..{max(p.x for p in ps):.3f}'
            f'  y {min(p.y for p in ps):.3f}..{max(p.y for p in ps):.3f}  z {min(p.z for p in ps):.3f}..{max(p.z for p in ps):.3f}')
    bm.free()


for n in ('shirt', 'pants', 'shoes', 'BodyActual', 'jacket'):
    boundary_loops(n)

# UV islands summary for shirt / pants
for n in ('shirt', 'pants', 'shoes'):
    me = bpy.data.objects[n].data
    uv = me.uv_layers.active.data
    us = [d.uv.x for d in uv]
    vs = [d.uv.y for d in uv]
    log(f'{n} uv range u {min(us):.3f}..{max(us):.3f} v {min(vs):.3f}..{max(vs):.3f} loops {len(uv)}')

# face disc + eye/mouth plate
for n in ('face', 'Body'):
    o = bpy.data.objects[n]
    W = o.matrix_world
    me = o.data
    for mi, m in enumerate(me.materials):
        vs = {v for p in me.polygons if p.material_index == mi for v in p.vertices}
        if not vs:
            continue
        pts = [W @ me.vertices[i].co for i in vs]
        log(f'{n} mat {m.name}: {len(vs)} verts x {min(p.x for p in pts):.3f}..{max(p.x for p in pts):.3f} '
            f'y {min(p.y for p in pts):.3f}..{max(p.y for p in pts):.3f} z {min(p.z for p in pts):.3f}..{max(p.z for p in pts):.3f}')
    log(f'{n} local->world', [list(map(lambda x: round(x, 4), r)) for r in W])
    if me.shape_keys:
        log(f'{n} shape keys', [k.name for k in me.shape_keys.key_blocks][:60])

# the black plate: cluster its 'Material' verts by connectivity (eyes, smile line, mouth plate)
o = bpy.data.objects['Body']
W = o.matrix_world
bm = bmesh.new()
bm.from_mesh(o.data)
bm.verts.ensure_lookup_table()
seen = set()
for f0 in bm.faces:
    if f0.index in seen:
        continue
    stack, comp = [f0], []
    while stack:
        f = stack.pop()
        if f.index in seen:
            continue
        seen.add(f.index)
        comp.append(f)
        for e in f.edges:
            for f2 in e.link_faces:
                if f2.index not in seen:
                    stack.append(f2)
    vs = {v for f in comp for v in f.verts}
    pts = [W @ v.co for v in vs]
    mats = sorted({o.data.materials[f.material_index].name for f in comp})
    c = sum(pts, Vector()) / len(pts)
    log(f'plate island faces {len(comp):5d} mats {mats} centre {tuple(round(x, 4) for x in c)} '
        f'x {min(p.x for p in pts):.4f}..{max(p.x for p in pts):.4f} y {min(p.y for p in pts):.4f}..{max(p.y for p in pts):.4f} z {min(p.z for p in pts):.4f}..{max(p.z for p in pts):.4f}')
bm.free()

# look renders of the base garments without the jacket/tie/era layers
sc = bpy.context.scene
eng = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in eng else 'BLENDER_EEVEE_NEXT'
sc.render.resolution_x, sc.render.resolution_y = 700, 1000
if not sc.world:
    sc.world = bpy.data.worlds.new('w')
sc.world.color = (0.09, 0.1, 0.12)
show = {'BodyActual', 'face', 'Body', 'flower', 'shirt', 'pants', 'shoes'}
for o in bpy.data.objects:
    if o.type == 'MESH':
        o.hide_render = o.name not in show
cam = bpy.data.objects.new('ins_cam', bpy.data.cameras.new('ins_cam'))
sc.collection.objects.link(cam)
sc.camera = cam
sun = bpy.data.objects.new('ins_sun', bpy.data.lights.new('ins_sun', 'SUN'))
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(50), 0, math.radians(30))
sc.collection.objects.link(sun)
for tag, ang, h, dist, look_z, lens in (('front', 0, 1.0, 5.0, 1.0, 50), ('side', 90, 1.0, 5.0, 1.0, 50), ('back', 180, 1.0, 5.0, 1.0, 50),
                                        ('neck', 20, 1.35, 1.6, 1.3, 50), ('feet', 25, 0.25, 1.6, 0.12, 50)):
    a = math.radians(ang)
    cam.location = (math.sin(a) * dist, -math.cos(a) * dist, h)
    d = Vector((0, 0, look_z)) - cam.location
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    sc.render.filepath = os.path.join(REPO, 'work', 'claude_suit_wardrobe_looks', f'wd_blender_base_{tag}.png')
    bpy.ops.render.render(write_still=True)
log('done')
