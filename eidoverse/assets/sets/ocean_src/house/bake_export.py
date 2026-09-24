# bake_export.py — bake the layered source materials of house_src.blend down to per-object maps
# (baseColor, tangent normal, ORM = occlusion/roughness/metallic), swap in glTF-ready materials,
# and export house.glb.
#
#   blender --background --factory-startup --python bake_export.py -- [--samples 24] [--scale 1.0] [--only name]
#
# Cycles on the CPU (the GPU stays free for the film). The AO pass sees every object including the
# look-dev ground plane, so contact occlusion at grade is baked in (the house sits on sand in the set).

import bpy, os, sys, math, json, time
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

def arg(name, default=None):
    if name in ARGV:
        i = ARGV.index(name)
        return ARGV[i + 1]
    return default

SAMPLES = int(arg('--samples', 24))
SCALE = float(arg('--scale', 1.0))
ONLY = arg('--only')
OUT_TEX = os.path.join(ROOT, 'textures')
os.makedirs(OUT_TEX, exist_ok=True)

BAKE = {
    'house_body': 2048, 'roof': 2048, 'porch': 2048,
    'window_frame': 1024, 'window_curtain': 1024, 'door': 1024, 'screen_door': 1024,
    'steps': 1024, 'chimney': 512, 'lamp_fixture': 1024,
}
KEEP = ['window_glass', 'screen_mesh', 'lamp_glass', 'lamp_bulb']

bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'house_src.blend'))
sc = bpy.context.scene
try:
    sc.render.engine = 'CYCLES'
except TypeError:
    bpy.ops.preferences.addon_enable(module='cycles')
    sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = False
sc.render.bake.margin = 8
sc.render.bake.margin_type = 'EXTEND'
sc.render.bake.use_clear = True
if sc.world is None:
    sc.world = bpy.data.worlds.new('bake_world')
sc.world.use_nodes = True
sc.world.node_tree.nodes['Background'].inputs['Color'].default_value = (1, 1, 1, 1)
sc.world.light_settings.distance = 0.6          # AO pass reach (m)

def select_only(ob):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob

def make_bake_uv(ob):
    me = ob.data
    if 'bake' in me.uv_layers:
        me.uv_layers.remove(me.uv_layers['bake'])
    uv = me.uv_layers.new(name='bake')
    me.uv_layers.active = uv
    select_only(ob)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(58), island_margin=0.0025, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    try:
        bpy.ops.uv.pack_islands(rotate=True, margin=0.004)
    except TypeError:
        bpy.ops.uv.pack_islands(margin=0.004)
    bpy.ops.object.mode_set(mode='OBJECT')
    uv.active_render = True
    return uv

def new_img(name, size, color):
    if name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[name])
    im = bpy.data.images.new(name, size, size, alpha=False, float_buffer=not color)
    im.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
    return im

def set_target(ob, im):
    for slot in ob.material_slots:
        m = slot.material
        nt = m.node_tree
        nd = nt.nodes.get('__bake_target')
        if nd is None:
            nd = nt.nodes.new('ShaderNodeTexImage')
            nd.name = '__bake_target'
        nd.image = im
        for n in nt.nodes:
            n.select = False
        nd.select = True
        nt.nodes.active = nd

def bake(ob, kind, im, **kw):
    set_target(ob, im)
    select_only(ob)
    t0 = time.time()
    bpy.ops.object.bake(type=kind, **kw)
    print(f'[bake] {ob.name:15s} {kind:9s} {im.size[0]}px {time.time() - t0:5.1f}s', flush=True)

def principled(m):
    for n in m.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            return n
    return None

def metal_emit_swap(ob):
    """Route each material's Metallic into an Emission shader (EMIT bake), remembering the output."""
    saved = []
    for slot in ob.material_slots:
        m = slot.material
        nt = m.node_tree
        out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output)
        prev = out.inputs['Surface'].links[0].from_socket if out.inputs['Surface'].links else None
        em = nt.nodes.new('ShaderNodeEmission')
        em.name = '__metal_emit'
        b = principled(m)
        if b and b.inputs['Metallic'].links:
            nt.links.new(b.inputs['Metallic'].links[0].from_socket, em.inputs['Color'])
        else:
            v = b.inputs['Metallic'].default_value if b else 0.0
            em.inputs['Color'].default_value = (v, v, v, 1)
        nt.links.new(em.outputs[0], out.inputs['Surface'])
        saved.append((m, out, prev, em))
    return saved

def metal_emit_restore(saved):
    for (m, out, prev, em) in saved:
        nt = m.node_tree
        if prev is not None:
            nt.links.new(prev, out.inputs['Surface'])
        nt.nodes.remove(em)

def pixels(im):
    a = np.empty(im.size[0] * im.size[1] * 4, dtype=np.float32)
    im.pixels.foreach_get(a)
    return a.reshape(im.size[1], im.size[0], 4)

def save(im, path, fmt, quality=92):
    im.filepath_raw = path
    im.file_format = fmt
    if fmt == 'JPEG':
        sc.render.image_settings.quality = quality
    im.save()

def gltf_output_group():
    ng = bpy.data.node_groups.get('glTF Material Output')
    if ng:
        return ng
    ng = bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
    ng.interface.new_socket('Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
    ng.interface.new_socket('Thickness', in_out='INPUT', socket_type='NodeSocketFloat')
    ng.nodes.new('NodeGroupInput')
    return ng

def export_material(name, col_im, orm_im, nrm_im):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs[0], out.inputs['Surface'])
    uv = nt.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'UVMap'
    def tex(im):
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = im
        nt.links.new(uv.outputs[0], t.inputs['Vector'])
        return t
    tc = tex(col_im)
    nt.links.new(tc.outputs['Color'], b.inputs['Base Color'])
    to = tex(orm_im)
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(to.outputs['Color'], sep.inputs[0])
    nt.links.new(sep.outputs['Green'], b.inputs['Roughness'])
    nt.links.new(sep.outputs['Blue'], b.inputs['Metallic'])
    grp = nt.nodes.new('ShaderNodeGroup')
    grp.node_tree = gltf_output_group()
    nt.links.new(sep.outputs['Red'], grp.inputs['Occlusion'])
    tn = tex(nrm_im)
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nm.uv_map = 'UVMap'
    nt.links.new(tn.outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    return m

report = {}
REDO = arg('--redo')          # comma list: re-bake only these; reuse the saved maps of the rest
REDO = set(REDO.split(',')) if REDO else None
names = [n for n in BAKE if (ONLY is None or n == ONLY)]
for name in names:
    ob = bpy.data.objects[name]
    size = max(256, int(BAKE[name] * SCALE))
    t0 = time.time()
    make_bake_uv(ob)
    p_col = os.path.join(OUT_TEX, f'{name}_color.jpg')
    p_orm = os.path.join(OUT_TEX, f'{name}_orm.jpg')
    p_nrm = os.path.join(OUT_TEX, f'{name}_normal.jpg')
    if REDO is not None and name not in REDO and all(os.path.exists(p) for p in (p_col, p_orm, p_nrm)):
        # Smart UV Project is deterministic for an unchanged mesh, so the saved atlas still fits
        ci = bpy.data.images.load(p_col); ci.colorspace_settings.name = 'sRGB'
        oi = bpy.data.images.load(p_orm); oi.colorspace_settings.name = 'Non-Color'
        ni = bpy.data.images.load(p_nrm); ni.colorspace_settings.name = 'Non-Color'
        em = export_material(f'{name}_mat', ci, oi, ni)
        em.use_backface_culling = name != 'window_curtain'
        me = ob.data
        me.materials.clear()
        me.materials.append(em)
        for p in me.polygons:
            p.material_index = 0
        for uvl in [u for u in me.uv_layers if u.name != 'bake']:
            me.uv_layers.remove(uvl)
        me.uv_layers['bake'].name = 'UVMap'
        report[name] = dict(size=size, reused=True)
        print('[reuse]', name, flush=True)
        continue
    col = new_img(f'{name}_color', size, True)
    rough = new_img(f'{name}_rough', size, False)
    nrm = new_img(f'{name}_normal', size, False)
    ao = new_img(f'{name}_ao', size, False)
    met = new_img(f'{name}_metal', size, False)
    bake(ob, 'DIFFUSE', col, pass_filter={'COLOR'})
    bake(ob, 'ROUGHNESS', rough)
    bake(ob, 'NORMAL', nrm, normal_space='TANGENT')
    sc.cycles.samples = max(SAMPLES, 48)
    bake(ob, 'AO', ao)
    sc.cycles.samples = SAMPLES
    saved = metal_emit_swap(ob)
    bake(ob, 'EMIT', met)
    metal_emit_restore(saved)
    # pack ORM (R occlusion, G roughness, B metallic) — occlusion softened toward 1 so the engine's
    # own AO doesn't double-darken: keep ~70% of the baked contrast
    A = pixels(ao)[..., 0]
    Rg = pixels(rough)[..., 0]
    Mt = pixels(met)[..., 0]
    orm = np.stack([1.0 - (1.0 - A) * 0.7, Rg, Mt, np.ones_like(A)], -1).astype(np.float32)
    orm_im = new_img(f'{name}_orm', size, False)
    orm_im.pixels.foreach_set(orm.ravel())
    p_col = os.path.join(OUT_TEX, f'{name}_color.jpg')
    p_orm = os.path.join(OUT_TEX, f'{name}_orm.jpg')
    p_nrm = os.path.join(OUT_TEX, f'{name}_normal.jpg')
    save(col, p_col, 'JPEG', 92)
    # 8-bit copies for the non-colour maps
    for im, p in ((orm_im, p_orm), (nrm, p_nrm)):
        im8 = bpy.data.images.new(im.name + '_8', size, size, alpha=False, float_buffer=False)
        im8.colorspace_settings.name = 'Non-Color'
        im8.pixels.foreach_set(pixels(im).ravel())
        save(im8, p, 'JPEG', 95)
    # reload the saved files as the export images (file-backed, so the GLB embeds them)
    ci = bpy.data.images.load(p_col); ci.colorspace_settings.name = 'sRGB'
    oi = bpy.data.images.load(p_orm); oi.colorspace_settings.name = 'Non-Color'
    ni = bpy.data.images.load(p_nrm); ni.colorspace_settings.name = 'Non-Color'
    em = export_material(f'{name}_mat', ci, oi, ni)
    em.use_backface_culling = name != 'window_curtain'
    me = ob.data
    me.materials.clear()
    me.materials.append(em)
    for p in me.polygons:
        p.material_index = 0
    # UVs: keep only the bake atlas, as TEXCOORD_0
    for uvl in [u for u in me.uv_layers if u.name != 'bake']:
        me.uv_layers.remove(uvl)
    me.uv_layers['bake'].name = 'UVMap'
    report[name] = dict(size=size, seconds=round(time.time() - t0, 1))
    print('[done]', name, report[name], flush=True)

# un-baked parts keep their simple materials; their tile UVs become UVMap
for name in KEEP:
    ob = bpy.data.objects.get(name)
    if ob is None:
        continue
    me = ob.data
    if 'tile' in me.uv_layers:
        me.uv_layers['tile'].name = 'UVMap'
# lamp and window materials ship dark: the set turns them on
for mn in ('filament',):
    m = bpy.data.materials.get(mn)
    if m:
        b = principled(m)
        b.inputs['Emission Strength'].default_value = 0.0

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'house_baked.blend'))

if ONLY is None:
    # export: the house hierarchy only
    for o in list(bpy.data.objects):
        if o.name in ('ground',) or o.type in ('LIGHT', 'CAMERA'):
            bpy.data.objects.remove(o)
    for o in bpy.context.view_layer.objects:
        o.select_set(o.name == 'house' or (o.parent is not None and o.parent.name == 'house'))
    glb = os.path.join(ROOT, 'house.glb')
    kw = dict(filepath=glb, export_format='GLB', use_selection=True, export_apply=True, export_yup=True,
              export_texcoords=True, export_normals=True, export_materials='EXPORT', export_cameras=False,
              export_lights=False, export_extras=False, export_animations=False)
    try:
        bpy.ops.export_scene.gltf(export_image_format='AUTO', **kw)
    except TypeError as e:
        print('[export] retry without image format:', e)
        bpy.ops.export_scene.gltf(**kw)
    print('[export]', glb, os.path.getsize(glb) // 1024, 'KB')
    json.dump(report, open(os.path.join(ROOT, 'bake_report.json'), 'w'), indent=1)
