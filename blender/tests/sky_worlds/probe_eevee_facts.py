"""The EEVEE facts the sky worlds rest on, measured in one small render.

F1  light linking works in EEVEE: a sun whose receiver collection INCLUDEs only object A lights A alone; a sun whose
    receiver collection holds only an EXCLUDEd object B lights everything except B. (The ringworld's band lamps light
    only the band; the scene's sun lights everything but the band, as WebGPU's per-material lightsNode does.)
F2  Light Path 'Is Camera Ray' is 1 in a material seen by the camera (the sky-element materials composite the
    clouds over themselves only for camera rays).
F3  a Blended material Add(Transparent(1 - a), Emission(rgb)) is a premultiplied 'over': rgb + (1 - a) * behind.
F4  EEVEE draws Blended objects in the order of their ORIGINS along the view axis, farthest first, whatever their
    geometry: a plane whose origin sits far in front of the camera draws before (under) one whose origin is near,
    even when its surface is nearer. (The cloud dome keeps its origin far ahead so it draws first.)
F5  shadow linking works in EEVEE: a sun whose blocker collection INCLUDEs only plate P1 is shadowed by P1 alone;
    plate P2 beside it, outside the collection, casts nothing. (The ringworld's band sun is shadowed by the ring's
    eclipse proxy and cloud sheet alone, never by the local scene or its cloud-shadow caster.)
F6  no input in Blender 5.2 scales a surface's indirect light alone (no render): no BSDF takes an occlusion input,
    the Ambient Occlusion node only returns a value, and the World takes no light linking, so no object can take the
    world's light on its own. (The ringworld band's baked AO, WebGPU's aoNode on indirect light only, stays in its
    albedo; EEVEE's horizon scan occludes the indirect light of the real relief.) The day this fails, port the aoNode.

    bash run_blender.sh blender/tests/sky_worlds/probe_eevee_facts.py
Prints one PASS/FAIL line per fact; writes out/probe_eevee_facts.png.
"""
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 160, 90
sc.eevee.taa_render_samples = 4
sc.view_settings.view_transform = 'Standard'
sc.render.image_settings.file_format = 'OPEN_EXR'
world = bpy.data.worlds.new('w')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.0
sc.world = world


def mat_diffuse(name, col):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*col, 1)
    b.inputs['Roughness'].default_value = 1.0
    b.inputs['Specular IOR Level'].default_value = 0.0
    return m


def cube(name, x, mat, size=1.0):
    bpy.ops.mesh.primitive_cube_add(size=size, location=(x, 0, size / 2))
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    return ob


white = mat_diffuse('white', (0.8, 0.8, 0.8))
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
plane = bpy.context.object
plane.data.materials.append(white)
A = cube('A', -3, white)
B = cube('B', 0, white)

# F2 + F3: an emissive card that shows Is Camera Ray, behind a blended 'over' card
cam_card_mat = bpy.data.materials.new('is_camera')
cam_card_mat.use_nodes = True
nt = cam_card_mat.node_tree
nt.nodes.clear()
lp = nt.nodes.new('ShaderNodeLightPath')
em = nt.nodes.new('ShaderNodeEmission')
mx = nt.nodes.new('ShaderNodeMix')
mx.data_type = 'RGBA'
mx.inputs['A'].default_value = (0, 0, 1, 1)
mx.inputs['B'].default_value = (1, 0, 0, 1)
nt.links.new(lp.outputs['Is Camera Ray'], mx.inputs['Factor'])
nt.links.new(mx.outputs['Result'], em.inputs['Color'])
o = nt.nodes.new('ShaderNodeOutputMaterial')
nt.links.new(em.outputs[0], o.inputs['Surface'])
bpy.ops.mesh.primitive_plane_add(size=1.6, location=(3, 0, 1.0), rotation=(0, 0, 0))
card = bpy.context.object
card.name = 'card_is_camera'
card.data.materials.append(cam_card_mat)

over = bpy.data.materials.new('over')
over.use_nodes = True
over.surface_render_method = 'BLENDED'
nt = over.node_tree
nt.nodes.clear()
tr = nt.nodes.new('ShaderNodeBsdfTransparent')
tr.inputs['Color'].default_value = (0.5, 0.5, 0.5, 1)      # 1 - a, a = 0.5
em2 = nt.nodes.new('ShaderNodeEmission')
em2.inputs['Color'].default_value = (0.0, 0.25, 0.0, 1)    # premultiplied green 0.5 * 0.5
add = nt.nodes.new('ShaderNodeAddShader')
nt.links.new(tr.outputs[0], add.inputs[0])
nt.links.new(em2.outputs[0], add.inputs[1])
o2 = nt.nodes.new('ShaderNodeOutputMaterial')
nt.links.new(add.outputs[0], o2.inputs['Surface'])
bpy.ops.mesh.primitive_plane_add(size=0.6, location=(3, 0, 1.0 + 0.3), rotation=(0, 0, 0))
ov = bpy.context.object
ov.name = 'over_card'
ov.data.materials.append(over)
ov.visible_shadow = False

# F4: two half-transparent blended cards over the same spot; the RED one is nearer the camera but its origin sits
# far down the view axis (the camera looks down -Z from z = 20), the BLUE one is farther but its origin is near
def blended_card(name, col, z_surface, origin_z, x):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.surface_render_method = 'BLENDED'
    t = m.node_tree
    t.nodes.clear()
    tr = t.nodes.new('ShaderNodeBsdfTransparent')
    tr.inputs['Color'].default_value = (0.5, 0.5, 0.5, 1)
    e = t.nodes.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = (col[0] * 0.5, col[1] * 0.5, col[2] * 0.5, 1)
    a = t.nodes.new('ShaderNodeAddShader')
    t.links.new(tr.outputs[0], a.inputs[0])
    t.links.new(e.outputs[0], a.inputs[1])
    o = t.nodes.new('ShaderNodeOutputMaterial')
    t.links.new(a.outputs[0], o.inputs['Surface'])
    me = bpy.data.meshes.new(name)
    d = z_surface - origin_z
    me.from_pydata([(-0.5, -0.5, d), (0.5, -0.5, d), (0.5, 0.5, d), (-0.5, 0.5, d)], [], [(0, 1, 2, 3)])
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    ob.location = (x, -2.0, origin_z)
    ob.visible_shadow = False
    sc.collection.objects.link(ob)
    return ob


blended_card('red_near_surface_far_origin', (1, 0, 0), 6.0, -500.0, 0.0)
blended_card('blue_far_surface_near_origin', (0, 0, 1), 5.0, 19.0, 0.0)

# F1: two suns with light linking
inc = bpy.data.collections.new('recv_include_A')
inc.objects.link(A)
exc = bpy.data.collections.new('recv_exclude_B')
exc.objects.link(B)
for name, col, coll, state in (('sun_red_onlyA', (1, 0, 0), inc, 'INCLUDE'), ('sun_green_notB', (0, 1, 0), exc, 'EXCLUDE')):
    ld = bpy.data.lights.new(name, 'SUN')
    ld.energy = 3.0
    ld.color = col
    ld.use_shadow = False
    ob = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(ob)
    ob.rotation_euler = (0, 0, 0)               # straight down
    ob.light_linking.receiver_collection = coll
    for co in coll.collection_objects:
        co.light_linking.link_state = state

# F5: a blue sun from +y at 45 deg with shadows that lights only a floor patch (x 0.5..4.5, y 1.2..2.8, so it leaves
# the F1-F4 readings alone), its blocker collection INCLUDE only plate P1; two plates 1 m up at y = 2.6 throw their
# shadows (if any) 1 m toward -y, onto the patch at y = 1.6
bpy.ops.mesh.primitive_plane_add(size=1.0, location=(2.5, 2.0, 0.01))
patch = bpy.context.object
patch.name = 'F5_patch'
patch.scale = (4.0, 1.6, 1.0)
patch.data.materials.append(white)
blk = bpy.data.collections.new('blockers_P1_only')
plates = []
for name, x in (('P1', 1.5), ('P2', 3.5)):
    bpy.ops.mesh.primitive_plane_add(size=0.8, location=(x, 2.6, 1.0))
    pl = bpy.context.object
    pl.name = name
    pl.data.materials.append(white)
    plates.append(pl)
blk.objects.link(plates[0])
for co in blk.collection_objects:
    co.light_linking.link_state = 'INCLUDE'
rcv = bpy.data.collections.new('receivers_patch_only')
rcv.objects.link(patch)
for co in rcv.collection_objects:
    co.light_linking.link_state = 'INCLUDE'
ld = bpy.data.lights.new('sun_blue_blockP1', 'SUN')
ld.energy = 3.0
ld.color = (0, 0, 1)
ld.use_shadow = True
ld.angle = 0.0
sun_b = bpy.data.objects.new('sun_blue_blockP1', ld)
sc.collection.objects.link(sun_b)
sun_b.rotation_euler = (-0.7853982, 0, 0)          # light travelling toward -y and down: from +y above
sun_b.light_linking.blocker_collection = blk
sun_b.light_linking.receiver_collection = rcv

cd = bpy.data.cameras.new('cam')
cd.type = 'ORTHO'
cd.ortho_scale = 10.0
camob = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(camob)
camob.location = (0, 0, 20)
sc.camera = camob

path = os.path.join(OUT, 'probe_eevee_facts.exr')
sc.render.filepath = path
bpy.ops.render.render(write_still=True)
img = bpy.data.images.load(path)
w, h = img.size
px = np.array(img.pixels[:], np.float32).reshape(h, w, 4)


def at(x, y):
    """pixel at world (x, y) under the ortho top camera"""
    u = (x / 10.0 + 0.5) * w
    v = (y / (10.0 * h / w) + 0.5) * h
    return px[int(v), int(u), :3]


a, b, p = at(-3, 0), at(0, 0), at(-1.5, 2.5)
print('A', a, 'B', b, 'plane', p)
f1 = a[0] > 0.2 and a[1] > 0.2 and b[0] < 0.02 and b[1] < 0.02 and p[0] < 0.02 and p[1] > 0.2
print('F1 light linking (include A only; exclude B):', 'PASS' if f1 else 'FAIL')
c_lo = at(3, 0.6)        # the is-camera card outside the over card (which spans y in [-0.3, 0.3])
c_hi = at(3, 0.0)        # under the over card: red * 0.5 + premult green 0.25
print('card', c_lo, 'card under over', c_hi)
f2 = c_lo[0] > 0.9 and c_lo[2] < 0.05
print('F2 Is Camera Ray = 1 in a material seen by the camera:', 'PASS' if f2 else 'FAIL')
f3 = abs(c_hi[0] - 0.5) < 0.05 and abs(c_hi[1] - 0.25) < 0.05
print('F3 blended Add(Transparent(1-a), Emission(premult)) is an over:', 'PASS' if f3 else 'FAIL')
# both cards over the plane (lit green 0.76): red drawn first then blue over it gives blue 0.5 > red 0.25
s = at(0.0, -2.0)
print('stacked cards', s)
red_first = s[2] > s[0] + 0.05
print('F4 blended objects draw farthest ORIGIN first (red origin far ahead drew under blue):',
      'PASS' if red_first else 'FAIL (blue drew first: the order follows something else)')
s1, s2, s0 = at(1.5, 1.6), at(3.5, 1.6), at(2.5, 1.6)
print('floor under P1 shadow', s1, 'under P2 shadow', s2, 'open floor', s0)
f5 = s0[2] > 0.2 and s1[2] < 0.25 * s0[2] and s2[2] > 0.8 * s0[2]
print('F5 shadow linking (blocker collection INCLUDE P1 only):', 'PASS' if f5 else 'FAIL')
# F6: what a surface could use to darken its indirect light alone
probe = bpy.data.materials.new('f6_inputs')
probe.use_nodes = True
bsdfs = [t for t in dir(bpy.types) if t.startswith('ShaderNodeBsdf')]
occl = {}
for t in bsdfs:
    try:
        n = probe.node_tree.nodes.new(t)
    except RuntimeError:                      # a node type a material tree does not take
        continue
    occl[t] = [i.name for i in n.inputs if 'occlu' in i.name.lower() or i.name.upper() == 'AO']
ao = probe.node_tree.nodes.new('ShaderNodeAmbientOcclusion')
world_ll = 'light_linking' in [p.identifier for p in bpy.types.World.bl_rna.properties]
f6 = not any(occl.values()) and [o.name for o in ao.outputs] == ['Color', 'AO'] and not world_ll
print('F6 nothing scales indirect light alone (%d BSDF nodes, none with an occlusion input; the AO node outputs %s; '
      'World light linking %s):' % (len(bsdfs), [o.name for o in ao.outputs], world_ll),
      'PASS' if f6 else 'FAIL (an indirect-only occlusion exists now: port the band\'s aoNode)')
bpy.data.materials.remove(probe)
bpy.data.images.remove(img)
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = os.path.join(OUT, 'probe_eevee_facts.png')
bpy.ops.render.render(write_still=True)
