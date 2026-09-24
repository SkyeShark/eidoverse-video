# build_robot_final.py — layered PBR for the robot, BAKED DOWN to one 2K atlas, then robot.glb.
# Opens wip/robot_clay.blend (from build_robot.py). Roles come from the clay material names.
#   body  = paint | trim | rubber | dark  -> joined into 'robot_body', one baked material 'robot_metal'
#   lamps = lens | light                  -> 'robot_lamps' (red glass lenses, amber domes; emission-ready)
# Layers (Cycles, CPU):
#   drivers : AO bake (the grime/dust driver) + Geometry.Pointiness (the edge-wear driver)
#   paint   : gunmetal enamel over AmbientCG Metal028 variation; edge wear to bare steel (Metal012);
#             grime in crevices + faint vertical streaks
#   trim    : bright steel (Metal012), scratched roughness, crevice grime
#   rubber  : Rubber004 bellows, pale dust settled in the grooves
#   dark    : gauge faces (painted dial texture: ticks + red zone = MATERIAL, not geometry)
#   normal  : box-projected height bumps (geometric, UV-independent) + a 3 mm Bevel-node edge round
# Bakes: AO, baseColor (EMIT), roughness (EMIT), metallic (EMIT), normal (tangent, OpenGL/+Y) -> ORM pack.
#
#   blender --background --factory-startup --python build_robot_final.py -- <figures_dir>
import bpy, bmesh, math, os, sys
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ROOT = os.path.abspath(argv[0] if argv else '.')
TEX = os.path.join(ROOT, 'tex'); OUTT = os.path.join(TEX, 'robot'); os.makedirs(OUTT, exist_ok=True)
RES = 2048
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'wip', 'robot_clay.blend'))
sc = bpy.context.scene
for o in list(bpy.data.objects):
    if o.name.startswith('cut'): bpy.data.objects.remove(o, do_unlink=True)

def role_of(o):
    m = o.data.materials[0].name if o.data.materials else 'clay_paint'
    return m.replace('clay_', '')

body = [o for o in bpy.data.objects if o.type == 'MESH' and role_of(o) in ('paint', 'trim', 'rubber', 'dark')]
lamps = [o for o in bpy.data.objects if o.type == 'MESH' and role_of(o) in ('lens', 'light')]

# gauge faces get their own dial UVs (planar, from their local disc coordinates) before the join
for o in body:
    me = o.data
    if not me.uv_layers: me.uv_layers.new(name='UVMap')
    dl = me.uv_layers.new(name='UVdial')
    if o.name.startswith('gauge_face'):
        r = max(abs(v.co.x) for v in me.vertices) or 1.0
        for loop in me.loops:
            co = me.vertices[loop.vertex_index].co
            dl.data[loop.index].uv = (co.x / (2 * r) + 0.5, co.y / (2 * r) + 0.5)

def join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active; ob.name = name; ob.data.name = name
    return ob
def lamp_mat(name, col, rough):
    m = bpy.data.materials.new(name); m.use_nodes = True; bb = m.node_tree.nodes['Principled BSDF']
    bb.inputs['Base Color'].default_value = (*col, 1); bb.inputs['Roughness'].default_value = rough
    bb.inputs['Emission Color'].default_value = (*col, 1); bb.inputs['Emission Strength'].default_value = 0.0
    bb.inputs['Coat Weight'].default_value = 0.6
    return m
lens_m = lamp_mat('robot_lens', (0.62, 0.035, 0.02), 0.08)
lamp_m = lamp_mat('robot_lamp', (0.92, 0.62, 0.18), 0.25)
for o in lamps:
    idx = 0 if role_of(o) == 'lens' else 1
    o.data.materials.clear(); o.data.materials.append(lens_m); o.data.materials.append(lamp_m)
    for p in o.data.polygons: p.material_index = idx; p.use_smooth = True
rb = join(body, 'robot_body')
rl = join(lamps, 'robot_lamps')
# origin between the feet: centre the feet in y as well (x is symmetric, z already on the ground)
feet_y = [(rb.matrix_world @ v.co).y for v in rb.data.vertices if (rb.matrix_world @ v.co).z < 0.02]
dy = -(min(feet_y) + max(feet_y)) / 2
for ob in (rb, rl):
    bpy.context.view_layer.objects.active = ob
    ob.location.y += dy
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
print('FEET dy', round(dy, 4))

# ---------------------------------------------------------------- atlas UVs (smart project, uniform density)
bpy.ops.object.select_all(action='DESELECT'); rb.select_set(True); bpy.context.view_layer.objects.active = rb
rb.data.uv_layers.active = rb.data.uv_layers['UVMap']
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(62), island_margin=0.004, area_weight=0.0, scale_to_bounds=False)
bpy.ops.object.mode_set(mode='OBJECT')
# weld the big shading seams: shade smooth by angle keeps bevel rounds soft and hard edges crisp
for p in rb.data.polygons: p.use_smooth = True
try:
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))
except Exception as e:
    print('shade_by_angle unavailable', e)

# ---------------------------------------------------------------- images
def new_img(name, noncolor):
    im = bpy.data.images.new(name, RES, RES, alpha=False, float_buffer=False)
    im.colorspace_settings.name = 'Non-Color' if noncolor else 'sRGB'
    return im
IMG = {k: new_img('robot_' + k, k != 'basecolor') for k in ('ao', 'basecolor', 'rough', 'metal', 'normal')}
def load(fn, noncolor=True):
    im = bpy.data.images.load(os.path.join(TEX, fn)); im.colorspace_settings.name = 'Non-Color' if noncolor else 'sRGB'
    return im
SRC = {'m28c': load('Metal028/Metal028_Color.jpg', False), 'm28r': load('Metal028/Metal028_Roughness.jpg'),
       'm28h': load('Metal028/Metal028_Displacement.jpg'),
       'm12c': load('Metal012/Metal012_Color.jpg', False), 'm12r': load('Metal012/Metal012_Roughness.jpg'),
       'm12h': load('Metal012/Metal012_Displacement.jpg'),
       'r4c': load('Rubber004/Rubber004_Color.jpg', False), 'r4r': load('Rubber004/Rubber004_Roughness.jpg'),
       'r4h': load('Rubber004/Rubber004_Displacement.jpg'), 'dial': load('robot/dial_face.png', False)}

# ---------------------------------------------------------------- layered materials (one per role, same slots)
def build_layered(mat, role):
    mat.use_nodes = True; nt = mat.node_tree; N = nt.nodes; L = nt.links
    N.clear()
    out = N.new('ShaderNodeOutputMaterial'); bsdf = N.new('ShaderNodeBsdfPrincipled'); emit = N.new('ShaderNodeEmission')
    tc = N.new('ShaderNodeTexCoord')
    sc_ = N.new('ShaderNodeMapping'); sc_.inputs['Scale'].default_value = (2.2, 2.2, 2.2)   # ~0.45 m per tile
    L.new(tc.outputs['Object'], sc_.inputs['Vector'])
    def tex(key, box=True, uvname=None):
        n = N.new('ShaderNodeTexImage'); n.image = SRC[key]
        if box:
            n.projection = 'BOX'; n.projection_blend = 0.25; L.new(sc_.outputs['Vector'], n.inputs['Vector'])
        elif uvname:
            u = N.new('ShaderNodeUVMap'); u.uv_map = uvname; L.new(u.outputs['UV'], n.inputs['Vector'])
        return n
    uvm = N.new('ShaderNodeUVMap'); uvm.uv_map = 'UVMap'
    ao = N.new('ShaderNodeTexImage'); ao.image = IMG['ao']; L.new(uvm.outputs['UV'], ao.inputs['Vector'])
    geo = N.new('ShaderNodeNewGeometry')
    def math_(op, a, b=None, clamp=False):
        n = N.new('ShaderNodeMath'); n.operation = op; n.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None: continue
            if isinstance(v, (int, float)): n.inputs[i].default_value = v
            else: L.new(v, n.inputs[i])
        return n.outputs[0]
    def mix(fac, a, b):
        n = N.new('ShaderNodeMix'); n.data_type = 'RGBA'; n.blend_type = 'MIX'
        for sock, v in ((n.inputs[0], fac), (n.inputs[6], a), (n.inputs[7], b)):
            if isinstance(v, (int, float)): sock.default_value = v
            elif isinstance(v, tuple): sock.default_value = v
            else: L.new(v, sock)
        return n.outputs[2]
    def mixf(fac, a, b):
        n = N.new('ShaderNodeMix'); n.data_type = 'FLOAT'
        for sock, v in ((n.inputs[0], fac), (n.inputs[2], a), (n.inputs[3], b)):
            if isinstance(v, (int, float)): sock.default_value = v
            else: L.new(v, sock)
        return n.outputs[0]
    def rgb2bw(c):
        n = N.new('ShaderNodeRGBToBW'); L.new(c, n.inputs[0]); return n.outputs[0]
    def noise(scale, detail=4.0, stretch=None):
        n = N.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = scale; n.inputs['Detail'].default_value = detail
        if stretch:
            mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = stretch
            L.new(tc.outputs['Object'], mp.inputs['Vector']); L.new(mp.outputs['Vector'], n.inputs['Vector'])
        else:
            L.new(tc.outputs['Object'], n.inputs['Vector'])
        return n.outputs['Fac']
    # drivers
    occl = rgb2bw(ao.outputs['Color'])                                      # 1 = open, 0 = occluded
    crev = math_('POWER', math_('SUBTRACT', 1.0, occl, clamp=True), 1.4)
    # hard-edge detector: where a 6 mm Bevel-node normal departs from the true normal (blind to smooth
    # curvature, so lathe/tube parts are not "all edge"); convexity gate from Pointiness keeps inner creases out
    bw = N.new('ShaderNodeBevel'); bw.inputs['Radius'].default_value = 0.006; bw.samples = 8
    dotn = N.new('ShaderNodeVectorMath'); dotn.operation = 'DOT_PRODUCT'
    L.new(bw.outputs['Normal'], dotn.inputs[0]); L.new(geo.outputs['Normal'], dotn.inputs[1])
    hard = math_('MULTIPLY', math_('SUBTRACT', 1.0, dotn.outputs['Value']), 22.0, clamp=True)
    convex = math_('MULTIPLY', math_('SUBTRACT', geo.outputs['Pointiness'], 0.49), 30.0, clamp=True)
    edge = math_('MULTIPLY', hard, convex, clamp=True)
    wear = math_('MULTIPLY', edge, math_('MULTIPLY', math_('SUBTRACT', noise(42.0, 6.0), 0.47), 4.0, clamp=True), clamp=True)
    streak = math_('MULTIPLY', math_('SUBTRACT', noise(9.0, 3.0, stretch=(9.0, 9.0, 0.9)), 0.55), 2.2, clamp=True)
    height = None
    if role == 'paint':
        m28 = tex('m28c'); var = rgb2bw(m28.outputs['Color'])
        base = mix(math_('MULTIPLY', var, 2.2, clamp=True), (0.055, 0.068, 0.088, 1), (0.105, 0.125, 0.155, 1))
        steel = tex('m12c').outputs['Color']
        col = mix(wear, base, steel)
        grime_col = (0.035, 0.03, 0.025, 1)
        col = mix(math_('MINIMUM', math_('ADD', math_('MULTIPLY', crev, 0.85), math_('MULTIPLY', streak, 0.18)), 0.9), col, grime_col)
        r_paint = math_('ADD', 0.46, math_('MULTIPLY', math_('SUBTRACT', rgb2bw(tex('m28r').outputs['Color']), 0.5), 0.35))
        rough = mixf(wear, r_paint, 0.32)
        rough = math_('ADD', rough, math_('MULTIPLY', crev, 0.2), clamp=True)
        metal = wear
        height = tex('m28h').outputs['Color']; hstr = 0.25
    elif role == 'trim':
        steel = tex('m12c').outputs['Color']
        col = mix(math_('MULTIPLY', crev, 0.75), mix(0.0, steel, steel), (0.05, 0.045, 0.04, 1))
        rough = math_('ADD', 0.18, math_('MULTIPLY', rgb2bw(tex('m12r').outputs['Color']), 0.35))
        rough = math_('ADD', rough, math_('MULTIPLY', crev, 0.3), clamp=True)
        metal = mixf(crev, 1.0, 0.6)
        height = tex('m12h').outputs['Color']; hstr = 0.15
    elif role == 'rubber':
        rc = tex('r4c').outputs['Color']
        dust = (0.30, 0.28, 0.25, 1)
        col = mix(math_('MULTIPLY', crev, 0.55), rc, dust)
        rough = math_('ADD', 0.62, math_('MULTIPLY', rgb2bw(tex('r4r').outputs['Color']), 0.3), clamp=True)
        metal = 0.0
        height = tex('r4h').outputs['Color']; hstr = 0.35
    else:   # dark: gauge faces (the dial texture on its own UVs)
        col = tex('dial', box=False, uvname='UVdial').outputs['Color']
        rough = 0.22; metal = 0.0
    # normal: bevel-rounded edges + box-projected height bump (geometric, UV-independent)
    bev = N.new('ShaderNodeBevel'); bev.inputs['Radius'].default_value = 0.003; bev.samples = 8
    nrm_out = bev.outputs['Normal']
    if height is not None:
        bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = hstr; bump.inputs['Distance'].default_value = 0.002
        L.new(rgb2bw(height), bump.inputs['Height']); L.new(bev.outputs['Normal'], bump.inputs['Normal'])
        nrm_out = bump.outputs['Normal']
    # wire the preview BSDF
    L.new(col, bsdf.inputs['Base Color'])
    for key, v in (('Roughness', rough), ('Metallic', metal)):
        if isinstance(v, (int, float)): bsdf.inputs[key].default_value = v
        else: L.new(v, bsdf.inputs[key])
    L.new(nrm_out, bsdf.inputs['Normal'])
    L.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    # bake target (active, unconnected)
    tgt = N.new('ShaderNodeTexImage'); tgt.name = 'BAKE'; tgt.image = IMG['ao']
    L.new(uvm.outputs['UV'], tgt.inputs['Vector'])
    N.active = tgt
    mat['chan'] = {}
    return {'out': out, 'bsdf': bsdf, 'emit': emit, 'col': col, 'rough': rough, 'metal': metal, 'tgt': tgt, 'nt': nt}

HOOK = {}
for slot in rb.material_slots:
    role = slot.material.name.replace('clay_', '')
    m = slot.material.copy(); m.name = 'bake_' + role; slot.material = m
    HOOK[m.name] = build_layered(m, role)

eng = sc.render
eng.engine = 'CYCLES'; sc.cycles.device = 'CPU'
if sc.world is None: sc.world = bpy.data.worlds.new('w')
sc.world.light_settings.distance = 0.18          # local (crevice) occlusion for a 2 m robot
sc.render.bake.margin = 8; sc.render.bake.use_clear = True
bpy.ops.object.select_all(action='DESELECT'); rb.select_set(True); bpy.context.view_layer.objects.active = rb

def set_target(img):
    for h in HOOK.values():
        h['tgt'].image = img; h['nt'].nodes.active = h['tgt']

def route_emit(key):
    for h in HOOK.values():
        nt = h['nt']; L = nt.links
        for l in list(h['out'].inputs['Surface'].links): L.remove(l)
        v = h[key]
        e = h['emit']
        for l in list(e.inputs['Color'].links): L.remove(l)
        if isinstance(v, (int, float)): e.inputs['Color'].default_value = (v, v, v, 1)
        else: L.new(v, e.inputs['Color'])
        e.inputs['Strength'].default_value = 1.0
        L.new(e.outputs['Emission'], h['out'].inputs['Surface'])

def route_bsdf():
    for h in HOOK.values():
        L = h['nt'].links
        for l in list(h['out'].inputs['Surface'].links): L.remove(l)
        L.new(h['bsdf'].outputs['BSDF'], h['out'].inputs['Surface'])

import time
t0 = time.time()
# 1) AO driver (the AO image is also sampled by the materials, so bake it with the BSDF connected)
set_target(IMG['ao']); route_bsdf()
sc.cycles.samples = 48
bpy.ops.object.bake(type='AO', margin=8, use_clear=True)
print('BAKED ao', round(time.time() - t0, 1)); t0 = time.time()
sc.cycles.samples = 16
for key, img in (('col', IMG['basecolor']), ('rough', IMG['rough']), ('metal', IMG['metal'])):
    set_target(img); route_emit(key)
    bpy.ops.object.bake(type='EMIT', margin=8, use_clear=True)
    print('BAKED', key, round(time.time() - t0, 1)); t0 = time.time()
set_target(IMG['normal']); route_bsdf(); sc.cycles.samples = 12
bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', margin=8, use_clear=True)
print('BAKED normal', round(time.time() - t0, 1))

# ---------------------------------------------------------------- save + pack ORM
def px(img):
    a = np.empty(RES * RES * 4, np.float32); img.pixels.foreach_get(a); return a.reshape(RES, RES, 4)
orm = np.ones((RES, RES, 4), np.float32)
orm[..., 0] = px(IMG['ao'])[..., 0]; orm[..., 1] = px(IMG['rough'])[..., 0]; orm[..., 2] = px(IMG['metal'])[..., 0]
orm_img = bpy.data.images.new('robot_orm', RES, RES, alpha=False); orm_img.colorspace_settings.name = 'Non-Color'
orm_img.pixels.foreach_set(orm.ravel())
for key, img, fn in (('base', IMG['basecolor'], 'robot_basecolor.png'), ('normal', IMG['normal'], 'robot_normal.png'),
                     ('orm', orm_img, 'robot_orm.png'), ('ao', IMG['ao'], 'robot_ao.png')):
    img.filepath_raw = os.path.join(OUTT, fn); img.file_format = 'PNG'; img.save()
    print('SAVED', fn)

# ---------------------------------------------------------------- final single material + lamp materials
fm = bpy.data.materials.new('robot_metal'); fm.use_nodes = True
nt = fm.node_tree; N = nt.nodes; L = nt.links
b = N['Principled BSDF']
uv = N.new('ShaderNodeUVMap'); uv.uv_map = 'UVMap'
def img_node(fn, noncolor):
    n = N.new('ShaderNodeTexImage'); n.image = bpy.data.images.load(os.path.join(OUTT, fn))
    n.image.colorspace_settings.name = 'Non-Color' if noncolor else 'sRGB'; L.new(uv.outputs['UV'], n.inputs['Vector']); return n
bc = img_node('robot_basecolor.png', False); L.new(bc.outputs['Color'], b.inputs['Base Color'])
om = img_node('robot_orm.png', True)
sep = N.new('ShaderNodeSeparateColor'); L.new(om.outputs['Color'], sep.inputs['Color'])
L.new(sep.outputs['Green'], b.inputs['Roughness']); L.new(sep.outputs['Blue'], b.inputs['Metallic'])
nm = img_node('robot_normal.png', True)
nmap = N.new('ShaderNodeNormalMap'); nmap.uv_map = 'UVMap'; L.new(nm.outputs['Color'], nmap.inputs['Color']); L.new(nmap.outputs['Normal'], b.inputs['Normal'])
# glTF occlusion: the exporter reads a 'glTF Material Output' group with an 'Occlusion' input
grp = bpy.data.node_groups.get('glTF Material Output') or bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
if not any(getattr(i, 'name', '') == 'Occlusion' for i in grp.interface.items_tree):
    grp.interface.new_socket('Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
g = N.new('ShaderNodeGroup'); g.node_tree = grp; L.new(sep.outputs['Red'], g.inputs['Occlusion'])
rb.data.materials.clear(); rb.data.materials.append(fm)
for p in rb.data.polygons: p.material_index = 0
rb.data.uv_layers.remove(rb.data.uv_layers['UVdial'])

from collections import Counter
print('LAMP slots', [m.name for m in rl.data.materials], Counter(p.material_index for p in rl.data.polygons))

root = bpy.data.objects.new('robot', None); sc.collection.objects.link(root)
rb.parent = root; rl.parent = root
tris = sum(len(p.vertices) - 2 for o in (rb, rl) for p in o.data.polygons)
pts = [o.matrix_world @ Vector(c) for o in (rb, rl) for c in o.bound_box]
print('FINAL tris', tris, 'bbox', [round(min(p[i] for p in pts), 4) for i in range(3)], [round(max(p[i] for p in pts), 4) for i in range(3)])
sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'robot.blend'))
bpy.ops.object.select_all(action='DESELECT')
for o in (root, rb, rl): o.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.join(ROOT, 'robot.glb'), export_format='GLB', use_selection=True,
                          export_yup=True, export_apply=True, export_normals=True, export_texcoords=True,
                          export_tangents=False, export_materials='EXPORT', export_image_format='AUTO')
print('EXPORTED robot.glb')
