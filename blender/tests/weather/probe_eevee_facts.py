"""The Blender 5.2 facts the weather port rests on, measured in tiny renders. Prints FACT / PASS / FAIL lines.

    bash run_blender.sh blender/tests/weather/probe_eevee_facts.py        (through the GPU slot: it renders)

F1  a keyed Value node inside a shader node group changes an EEVEE render frame by frame (eido_wet keys its inputs)
F2  the Attribute node (Object) reads an object custom property; a missing one reads 0 (per-object wetness gates)
F3  a Geometry Nodes attribute stored on realized geometry reaches the shader (Attribute, Geometry)
F4  Add Shader(Transparent white, Emission) in BLENDED mode adds light over what is behind it (additive bolts)
F5  a point light of 4 pi I watts lights a diffuse plane like a three.js PointLight of I candela (Cycles + EEVEE)
F6  the Geometry Nodes Image Texture node samples a float EXR exactly (the weather map in the rain tree)
F7  Geometry Nodes Raycast finds a roof in a collection (rain shelter)
"""
import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out', 'facts')
os.makedirs(OUT, exist_ok=True)
fails = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + detail) if detail else ''), flush=True)
    if not ok:
        fails.append(name)


def fresh(engine='BLENDER_EEVEE', res=24):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = engine
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'OPEN_EXR'
    sc.render.image_settings.color_depth = '32'
    if engine == 'BLENDER_EEVEE':
        sc.eevee.taa_render_samples = 1
    else:
        sc.cycles.samples = 64
        sc.cycles.device = 'GPU'
    w = bpy.data.worlds.new('w')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0, 0, 0, 1)
    sc.world = w
    cam_d = bpy.data.cameras.new('c')
    cam_d.type = 'ORTHO'
    cam_d.ortho_scale = 2.0
    cam = bpy.data.objects.new('c', cam_d)
    sc.collection.objects.link(cam)
    cam.location = (0, 0, 5)
    sc.camera = cam
    return sc


def render(sc, name, frame=1):
    sc.frame_set(frame)
    p = os.path.join(OUT, f'{name}_{frame}.exr')
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(p)
    a = np.array(img.pixels[:], np.float32).reshape(img.size[1], img.size[0], 4)
    bpy.data.images.remove(img)
    return a


def plane(sc, name, size=2.0, z=0.0):
    me = bpy.data.meshes.new(name)
    s = size / 2
    me.from_pydata([(-s, -s, z), (s, -s, z), (s, s, z), (-s, s, z)], [], [(0, 1, 2, 3)])
    me.uv_layers.new(name='UVMap')
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    return ob


def emit_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(em.outputs[0], out.inputs[0])
    return m, nt, em


# ---- F1: keyed Value inside a node group ----
sc = fresh()
ob = plane(sc, 'p')
m, nt, em = emit_mat('m1')
g = bpy.data.node_groups.new('kv', 'ShaderNodeTree')
g.interface.new_socket('Out', in_out='OUTPUT', socket_type='NodeSocketFloat')
go = g.nodes.new('NodeGroupOutput')
val = g.nodes.new('ShaderNodeValue')
g.links.new(val.outputs[0], go.inputs[0])
val.outputs[0].default_value = 0.2
val.outputs[0].keyframe_insert('default_value', frame=1)
val.outputs[0].default_value = 0.8
val.outputs[0].keyframe_insert('default_value', frame=2)
gn = nt.nodes.new('ShaderNodeGroup')
gn.node_tree = g
nt.links.new(gn.outputs[0], em.inputs['Strength'])
ob.data.materials.append(m)
a1, a2 = render(sc, 'f1', 1)[12, 12, 0], render(sc, 'f1', 2)[12, 12, 0]
check('F1 keyed Value in a shader node group animates in EEVEE', abs(a1 - 0.2) < 0.01 and abs(a2 - 0.8) < 0.01,
      f'{a1:.3f} {a2:.3f}')

# ---- F2: Attribute (Object) reads custom properties, missing = 0, keyed animates ----
sc = fresh()
ob = plane(sc, 'p')
m, nt, em = emit_mat('m2')
at = nt.nodes.new('ShaderNodeAttribute')
at.attribute_type = 'OBJECT'
at.attribute_name = 'eido_probe'
nt.links.new(at.outputs['Fac'], em.inputs['Strength'])
ob.data.materials.append(m)
ob['eido_probe'] = 0.3
ob.keyframe_insert('["eido_probe"]', frame=1)
ob['eido_probe'] = 0.6
ob.keyframe_insert('["eido_probe"]', frame=2)
b1, b2 = render(sc, 'f2', 1)[12, 12, 0], render(sc, 'f2', 2)[12, 12, 0]
at.attribute_name = 'eido_missing'
b3 = render(sc, 'f2m', 1)[12, 12, 0]
check('F2 Attribute(Object) reads a keyed custom property; a missing one reads 0',
      abs(b1 - 0.3) < 0.01 and abs(b2 - 0.6) < 0.01 and b3 < 0.01, f'{b1:.3f} {b2:.3f} {b3:.3f}')

# ---- F3: a GN stored attribute reaches the shader ----
sc = fresh()
ob = plane(sc, 'p')
mod = ob.modifiers.new('gn', 'NODES')
tree = bpy.data.node_groups.new('gn3', 'GeometryNodeTree')
tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
gi, go = tree.nodes.new('NodeGroupInput'), tree.nodes.new('NodeGroupOutput')
st = tree.nodes.new('GeometryNodeStoreNamedAttribute')
st.data_type = 'FLOAT'
st.domain = 'FACE'
st.inputs['Name'].default_value = 'eido_a'
st.inputs['Value'].default_value = 0.45
tree.links.new(gi.outputs[0], st.inputs['Geometry'])
tree.links.new(st.outputs[0], go.inputs[0])
mod.node_group = tree
m, nt, em = emit_mat('m3')
at = nt.nodes.new('ShaderNodeAttribute')
at.attribute_type = 'GEOMETRY'
at.attribute_name = 'eido_a'
nt.links.new(at.outputs['Fac'], em.inputs['Strength'])
ob.data.materials.append(m)
c = render(sc, 'f3')[12, 12, 0]
check('F3 a GN-stored face attribute reaches the shader', abs(c - 0.45) < 0.01, f'{c:.3f}')

# ---- F4: additive blending ----
sc = fresh()
back = plane(sc, 'back', z=-1)
mb, ntb, emb = emit_mat('back')
emb.inputs['Color'].default_value = (0.25, 0.25, 0.25, 1)
back.data.materials.append(mb)
front = plane(sc, 'front', z=0)
mf = bpy.data.materials.new('add')
mf.use_nodes = True
nt = mf.node_tree
nt.nodes.clear()
o = nt.nodes.new('ShaderNodeOutputMaterial')
add = nt.nodes.new('ShaderNodeAddShader')
tr = nt.nodes.new('ShaderNodeBsdfTransparent')
em = nt.nodes.new('ShaderNodeEmission')
em.inputs['Color'].default_value = (0.3, 0.1, 0.0, 1)
nt.links.new(tr.outputs[0], add.inputs[0])
nt.links.new(em.outputs[0], add.inputs[1])
nt.links.new(add.outputs[0], o.inputs[0])
mf.surface_render_method = 'BLENDED'
front.data.materials.append(mf)
d = render(sc, 'f4')[12, 12, :3]
check('F4 Add(Transparent, Emission) BLENDED is additive', np.allclose(d, (0.55, 0.35, 0.25), atol=0.01), str(d))

# ---- F5: point light units against three.js candela (Cycles = ground truth, and EEVEE) ----
for eng in ('CYCLES', 'BLENDER_EEVEE'):
    sc = fresh(eng)
    p = plane(sc, 'ground', size=2.0, z=0.0)
    mat = bpy.data.materials.new('diffuse')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 1)
    bsdf.inputs['Roughness'].default_value = 1.0
    bsdf.inputs['Specular IOR Level'].default_value = 0.0
    p.data.materials.append(mat)
    I, dist = 100.0, 10.0
    ld = bpy.data.lights.new('pt', 'POINT')
    ld.energy = 4 * math.pi * I
    ld.shadow_soft_size = 0.0
    lo = bpy.data.objects.new('pt', ld)
    lo.location = (0, 0, dist)
    sc.collection.objects.link(lo)
    v = float(render(sc, 'f5_' + eng)[12, 12, 0])
    want = 0.5 / math.pi * I / dist ** 2
    print(f'FACT F5 {eng}: point light 4*pi*{I:.0f} W at {dist:.0f} m -> {v:.5f}; three PointLight {I:.0f} cd -> {want:.5f}')
    check(f'F5 {eng}: Blender point watts = 4 pi x three candela', abs(v / want - 1) < 0.06, f'ratio {v / want:.3f}')

# ---- F6: GN Image Texture samples a float EXR exactly (written the way the weather map is) ----
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.sky.bake.baker import write_exr  # noqa: E402


def gn_read(sc, img, u, v):
    """What a GN Image Texture (Closest) returns at (u, v), read back through a vertex position."""
    me = bpy.data.meshes.new('pts')
    me.from_pydata([(0, 0, 0)], [], [])
    ob = bpy.data.objects.new('pts', me)
    sc.collection.objects.link(ob)
    tree = bpy.data.node_groups.new('gn6', 'GeometryNodeTree')
    tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    gi, go = tree.nodes.new('NodeGroupInput'), tree.nodes.new('NodeGroupOutput')
    tx = tree.nodes.new('GeometryNodeImageTexture')
    tx.interpolation = 'Closest'
    tx.inputs['Image'].default_value = img
    vin = tree.nodes.new('ShaderNodeCombineXYZ')
    vin.inputs[0].default_value = u
    vin.inputs[1].default_value = v
    tree.links.new(vin.outputs[0], tx.inputs['Vector'])
    sep = tree.nodes.new('FunctionNodeSeparateColor')
    tree.links.new(tx.outputs['Color'], sep.inputs[0])
    sp = tree.nodes.new('GeometryNodeSetPosition')
    cx = tree.nodes.new('ShaderNodeCombineXYZ')
    tree.links.new(sep.outputs[0], cx.inputs[0])
    tree.links.new(gi.outputs[0], sp.inputs['Geometry'])
    tree.links.new(cx.outputs[0], sp.inputs['Position'])
    tree.links.new(sp.outputs[0], go.inputs[0])
    ob.modifiers.new('gn', 'NODES').node_group = tree
    dg = bpy.context.evaluated_depsgraph_get()
    return tx, ob.evaluated_get(dg).data.vertices[0].co.x


sc = fresh()
size = 8
arr = np.zeros((size, size, 4), np.float32)
arr[..., 0] = np.arange(size)[None, :] / 7.0 + 0.123456
arr[..., 3] = 1
want6 = 3 / 7.0 + 0.123456
path = os.path.join(OUT, 'wmap.exr')
write_exr(path, arr, half=False)                         # the sky baker's writer: how the weather map is written
img = bpy.data.images.load(path)
img.colorspace_settings.name = 'Non-Color'
tx, x = gn_read(sc, img, (3 + 0.5) / size, 0.5 / size)   # texel centres at (i + 0.5) / size
# The Vector input is an implicit field (hide_value): an unlinked default is ignored, so it must be linked.
print('FACT F6 the GN Image Texture Vector input is an implicit field (hide_value=%s): link it'
      % tx.inputs['Vector'].hide_value)
check('F6 GN Image Texture reads a float EXR (OpenImageIO, Non-Color) exactly', abs(x - want6) < 1e-6, f'{x:.7f}')
sc = fresh()
gen = bpy.data.images.new('wmap_saved', size, size, alpha=True, float_buffer=True)
gen.pixels.foreach_set(arr.ravel())
p2 = os.path.join(OUT, 'wmap_image_save.exr')
gen.filepath_raw = p2
gen.file_format = 'OPEN_EXR'
gen.save()
img2 = bpy.data.images.load(p2)
img2.colorspace_settings.name = 'Non-Color'
_tx, x2 = gn_read(sc, img2, (3 + 0.5) / size, 0.5 / size)
enc = 1.055 * want6 ** (1 / 2.4) - 0.055
print('FACT F6 bpy Image.save() of a generated float image wrote %.5f for %.5f: %s' % (
    x2, want6, 'the sRGB-encoded value (%.5f): write data maps with OpenImageIO, not Image.save' % enc
    if abs(x2 - enc) < 2e-3 else 'as stored'))

# ---- F7: GN Raycast against a collection ----
sc = fresh()
roof = plane(sc, 'roof', size=2.0, z=3.0)
col = bpy.data.collections.new('occ')
col.objects.link(roof)
me = bpy.data.meshes.new('q')
me.from_pydata([(0, 0, 0), (5, 0, 0)], [], [])
ob = bpy.data.objects.new('q', me)
sc.collection.objects.link(ob)
tree = bpy.data.node_groups.new('gn7', 'GeometryNodeTree')
tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
gi, go = tree.nodes.new('NodeGroupInput'), tree.nodes.new('NodeGroupOutput')
ci = tree.nodes.new('GeometryNodeCollectionInfo')
ci.inputs['Collection'].default_value = col
ci.transform_space = 'RELATIVE'
ri = tree.nodes.new('GeometryNodeRealizeInstances')
tree.links.new(ci.outputs[0], ri.inputs[0])
rc = tree.nodes.new('GeometryNodeRaycast')
tree.links.new(ri.outputs[0], rc.inputs['Target Geometry'])
rc.inputs['Ray Direction'].default_value = (0, 0, 1)
rc.inputs['Ray Length'].default_value = 100
sp = tree.nodes.new('GeometryNodeSetPosition')
cx = tree.nodes.new('ShaderNodeCombineXYZ')
sw = tree.nodes.new('GeometryNodeSwitch')
sw.input_type = 'FLOAT'
tree.links.new(rc.outputs['Is Hit'], sw.inputs['Switch'])
sw.inputs['True'].default_value = 1.0
sw.inputs['False'].default_value = 0.0
tree.links.new(sw.outputs[0], cx.inputs[2])
tree.links.new(gi.outputs[0], sp.inputs['Geometry'])
tree.links.new(cx.outputs[0], sp.inputs['Offset'])
tree.links.new(sp.outputs[0], go.inputs[0])
ob.modifiers.new('gn', 'NODES').node_group = tree
dg = bpy.context.evaluated_depsgraph_get()
vs = ob.evaluated_get(dg).data.vertices
check('F7 GN Raycast hits the roof above (0,0) and not (5,0)', abs(vs[0].co.z - 1) < 1e-6 and abs(vs[1].co.z) < 1e-6,
      f'{vs[0].co.z} {vs[1].co.z}')

# ---- F8: a GN-stored FLOAT2 corner attribute (the generators' 'UVMap') reaches the shader's Attribute node ----
sc = fresh()
ob = plane(sc, 'p')
tree = bpy.data.node_groups.new('gn8', 'GeometryNodeTree')
tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
gi, go = tree.nodes.new('NodeGroupInput'), tree.nodes.new('NodeGroupOutput')
grid = tree.nodes.new('GeometryNodeMeshGrid')
grid.inputs['Size X'].default_value = 2.0
grid.inputs['Size Y'].default_value = 2.0
grid.inputs['Vertices X'].default_value = 2
grid.inputs['Vertices Y'].default_value = 2
st = tree.nodes.new('GeometryNodeStoreNamedAttribute')
st.data_type = 'FLOAT2'
st.domain = 'CORNER'
st.inputs['Name'].default_value = 'UVMap'
tree.links.new(grid.outputs['Mesh'], st.inputs['Geometry'])
tree.links.new(grid.outputs['UV Map'], st.inputs['Value'])
tree.links.new(st.outputs[0], go.inputs[0])
ob.modifiers.new('gn', 'NODES').node_group = tree
m, nt, em = emit_mat('m8')
at = nt.nodes.new('ShaderNodeAttribute')
at.attribute_type = 'GEOMETRY'
at.attribute_name = 'UVMap'
nt.links.new(at.outputs['Vector'], em.inputs['Color'])
ob.data.materials.append(m)
st_mat = tree.nodes.new('GeometryNodeSetMaterial')
st_mat.inputs['Material'].default_value = m
tree.links.new(st.outputs[0], st_mat.inputs['Geometry'])
tree.links.new(st_mat.outputs[0], go.inputs[0])
px = render(sc, 'f8')
u_left, u_right = px[12, 3, 0], px[12, 20, 0]
v_bottom, v_top = px[3, 12, 1], px[20, 12, 1]
check('F8 a GN FLOAT2 corner attribute UVMap reads as the UV in the shader',
      u_left < 0.3 and u_right > 0.7 and v_bottom < 0.3 and v_top > 0.7,
      f'u {u_left:.2f}..{u_right:.2f} v {v_bottom:.2f}..{v_top:.2f}')
print('RESULT', 'PASS' if not fails else 'FAIL (%d)' % len(fails), flush=True)
