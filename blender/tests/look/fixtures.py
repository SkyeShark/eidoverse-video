"""tests/look/fixtures.py: the sets the look family's tests photograph. Test dressing, not ports: the sky, terrain and
flora of a film come from their own families' ports (make_sky, make_terrain, create_flora). Here:

  - outdoor_world: a neutral uniform world (a flat pale-blue fill, no sky model: the sky is the sky family's) and a
    SUN light (look.lighting.sun) for the sun and its shadows. Exposure numbers measured under it are this fixture's,
    not a film's: a film meters under its own make_sky.
  - ground: Poly Haven's leafy_grass set when the main checkout has it, else the ambientCG Ground103 soil set, else a
    plain soil colour.
  - meadow_dressing: Poly Haven scanned grasses and flowers (CC0, fetched for the Blender meadow into the main
    checkout's work/claude_body/film/tools/dlss5nr/bmeadow/assets) scattered by a Geometry Nodes tree either side of
    the walk; skipped when the folder is not there.
  - robot: claude_robot.vrm (the VRM add-on), walking the stock walk.vrma in place, carried forward at 1.44 m/s
    (meadow.js's measured MW_SPEED), facing +Y.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
ASSETS = os.path.join(WORKTREE, 'eidoverse', 'assets')
MAIN = os.path.abspath(os.path.join(WORKTREE, '..', 'eidoverse-video-prealpha-0.01'))
BMEADOW = os.path.join(MAIN, 'work', 'claude_body', 'film', 'tools', 'dlss5nr', 'bmeadow', 'assets')
OUT = os.path.join(HERE, 'out')

sys.path.insert(0, os.path.join(WORKTREE, 'blender'))


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    return a


def arg(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


def new_scene(fps=24, frames=(1, 240)):
    """An empty scene (the factory cube, light and camera removed)."""
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = fps, 1.0
    sc.frame_start, sc.frame_end = frames
    return sc


def outdoor_world(scene, elevation_deg=18.0, azimuth_deg=-70.0, sun_w_m2=4.5, sun_kelvin=4800,
                  colour=(0.42, 0.56, 0.85), strength=0.25):
    """A neutral uniform world (camera-lighting.md: a test with no sky of its own uses one, not a stock sky standing
    in for ours) and a SUN light (look.lighting.sun; azimuth from +Y toward +X). The world is a flat fill: about a
    third of the low sun's horizontal irradiance at the defaults, blue, as a clear sky's. Returns (world, sun)."""
    from eidoblend.look import lighting as L
    w = bpy.data.worlds.new('test_neutral')
    scene.world = w
    if w.node_tree is None:
        w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = (*colour, 1.0)
    bg.inputs['Strength'].default_value = strength
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    w.sun_threshold = 0.0                      # nothing to extract: the sun is a light
    sun = L.sun(scene, elevation_deg=elevation_deg, azimuth_deg=azimuth_deg, strength=sun_w_m2, kelvin_k=sun_kelvin)
    return w, sun


def _texture_set(folder):
    """A Poly Haven texture set's maps in a folder: {diff, rough, nor_gl, ...} -> paths."""
    out = {}
    if not os.path.isdir(folder):
        return out
    for f in os.listdir(folder):
        for k in ('diff', 'rough', 'nor_gl', 'ao', 'disp'):
            if f'_{k}_' in f:
                out[k] = os.path.join(folder, f)
    return out


def ground(scene, size=400.0, repeat_m=2.0):
    """A ground plane: Poly Haven's leafy_grass set (fetched for the Blender meadow) when the main checkout has it,
    else the Ground103 soil set from the main checkout's root, else a plain soil colour."""
    leafy = _texture_set(os.path.join(BMEADOW, 'leafy_grass'))
    if leafy.get('diff'):
        return _ground_textured(scene, size, repeat_m, leafy['diff'], leafy.get('rough'), leafy.get('nor_gl'))
    return _ground_soil(scene, size, repeat_m)


def _plane(scene, name, size, repeat_m):
    me = bpy.data.meshes.new(name)
    h = size / 2
    me.from_pydata([(-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for i, (u, v) in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[i].uv = (u * size / repeat_m, v * size / repeat_m)
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob


def _ground_textured(scene, size, repeat_m, diff, rough=None, nor=None):
    ob = _plane(scene, 'ground', size, repeat_m)
    m = bpy.data.materials.new('ground')
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexImage')
    tc.image = bpy.data.images.load(diff)
    nt.links.new(tc.outputs['Color'], bsdf.inputs['Base Color'])
    if rough:
        tr = nt.nodes.new('ShaderNodeTexImage')
        tr.image = bpy.data.images.load(rough)
        tr.image.colorspace_settings.name = 'Non-Color'
        nt.links.new(tr.outputs['Color'], bsdf.inputs['Roughness'])
    if nor:
        tn = nt.nodes.new('ShaderNodeTexImage')
        tn.image = bpy.data.images.load(nor)
        tn.image.colorspace_settings.name = 'Non-Color'
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nt.links.new(tn.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    ob.data.materials.append(m)
    return ob


def _ground_soil(scene, size=400.0, repeat_m=2.0):
    """A ground plane; the Ground103 soil set from the main checkout's root when present."""
    me = bpy.data.meshes.new('ground')
    h = size / 2
    me.from_pydata([(-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for i, (u, v) in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[i].uv = (u * size / repeat_m, v * size / repeat_m)
    ob = bpy.data.objects.new('ground', me)
    scene.collection.objects.link(ob)
    m = bpy.data.materials.new('ground')
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    col = os.path.join(MAIN, 'Ground103_Color.jpg')
    if os.path.exists(col):
        tc = nt.nodes.new('ShaderNodeTexImage')
        tc.image = bpy.data.images.load(col)
        nt.links.new(tc.outputs['Color'], bsdf.inputs['Base Color'])
        rough = os.path.join(MAIN, 'Ground103_Roughness.jpg')
        if os.path.exists(rough):
            tr = nt.nodes.new('ShaderNodeTexImage')
            tr.image = bpy.data.images.load(rough)
            tr.image.colorspace_settings.name = 'Non-Color'
            nt.links.new(tr.outputs['Color'], bsdf.inputs['Roughness'])
        nor = os.path.join(MAIN, 'Ground103_NormalGL.jpg')
        if os.path.exists(nor):
            tn = nt.nodes.new('ShaderNodeTexImage')
            tn.image = bpy.data.images.load(nor)
            tn.image.colorspace_settings.name = 'Non-Color'
            nm = nt.nodes.new('ShaderNodeNormalMap')
            nt.links.new(tn.outputs['Color'], nm.inputs['Color'])
            nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    else:
        bsdf.inputs['Base Color'].default_value = (0.13, 0.1, 0.07, 1)
        bsdf.inputs['Roughness'].default_value = 0.95
    me.materials.append(m)
    return ob


def _append_collection(blend, name):
    with bpy.data.libraries.load(blend, link=False) as (src, dst):
        dst.collections = [name] if name in src.collections else []
    return dst.collections[0] if dst.collections else None


def meadow_dressing(scene, path_x=0.0, half_gap=0.55, area=(30.0, 60.0), centre_y=0.0, density=9.0, seed=3):
    """Scanned grass and flowers either side of a walk along +Y at x = path_x (a 2 x half_gap strip kept short).
    Returns the scatter objects (exclude them from camera sightlines), or [] without the assets."""
    if not os.path.isdir(BMEADOW):
        print('[fixtures] no bmeadow assets: the meadow is bare soil', flush=True)
        return []
    src = bpy.data.collections.new('meadow_sources')
    scene.collection.children.link(src)
    picks = [('grass_medium_01', 'grass_medium_01_LOD0', 2), ('grass_medium_02', 'grass_medium_02_static', 3),
             ('dandelion_01', 'dandelion_01_LOD0', 1), ('celandine_01', 'celandine_01_LOD0', 1),
             ('weed_plant_02', 'weed_plant_02_LOD0', 1)]
    weights = []
    for folder, coll, wgt in picks:
        blends = [f for f in os.listdir(os.path.join(BMEADOW, folder)) if f.endswith('.blend')] \
            if os.path.isdir(os.path.join(BMEADOW, folder)) else []
        if not blends:
            continue
        c = _append_collection(os.path.join(BMEADOW, folder, blends[0]), coll)
        if c is None:
            continue
        for o in list(c.all_objects):
            if o.type == 'MESH':
                o.parent = None
                o.location = (0, 0, 0)
                o.rotation_euler = (0, 0, 0)
                for k in range(wgt):            # linked copies weight the random pick (grass over flowers)
                    src.objects.link(o if k == 0 else o.copy())
                weights.append(o.name)
    # the sources render only through the scatter
    vl = bpy.context.view_layer.layer_collection.children[src.name]
    vl.exclude = True
    W, L = area
    out = []
    for side in (-1, 1):
        me = bpy.data.meshes.new(f'meadow_{side}')
        x0 = path_x + side * half_gap
        x1 = path_x + side * (half_gap + W / 2)
        y0, y1 = centre_y - L / 2, centre_y + L / 2
        me.from_pydata([(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)], [], [(0, 1, 2, 3)])
        ob = bpy.data.objects.new(f'meadow_scatter_{"L" if side < 0 else "R"}', me)
        scene.collection.objects.link(ob)
        mod = ob.modifiers.new('scatter', 'NODES')
        mod.node_group = _scatter_tree(src, density, seed + (side > 0))
        out.append(ob)
    print(f'[fixtures] meadow: {len(src.objects)} scanned plant meshes scattered at {density}/m2 either side of the walk',
          flush=True)
    return out


def _scatter_tree(src, density, seed):
    ng = bpy.data.node_groups.new('meadow_scatter', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    dist = N.new('GeometryNodeDistributePointsOnFaces')
    dist.inputs['Density'].default_value = density
    dist.inputs['Seed'].default_value = seed
    ci = N.new('GeometryNodeCollectionInfo')
    ci.inputs['Collection'].default_value = src
    ci.inputs['Separate Children'].default_value = True
    ci.inputs['Reset Children'].default_value = True
    iop = N.new('GeometryNodeInstanceOnPoints')
    iop.inputs['Pick Instance'].default_value = True
    def rnd(dtype, sock, lo, hi, s):
        n = N.new('FunctionNodeRandomValue')
        n.data_type = dtype
        ins = [i for i in n.inputs if i.type == sock and i.name in ('Min', 'Max')]
        ins[0].default_value, ins[1].default_value = lo, hi
        n.inputs['Seed'].default_value = s
        return n, next(o for o in n.outputs if o.type == sock)
    _r, rot_out = rnd('FLOAT_VECTOR', 'VECTOR', (0, 0, 0), (0, 0, 2 * math.pi), seed)
    _s, sca_out = rnd('FLOAT', 'VALUE', 0.75, 1.25, seed + 11)
    _p, pick_out = rnd('INT', 'INT', 0, 10000, seed + 23)
    L = ng.links
    L.new(gi.outputs[0], dist.inputs['Mesh'])
    L.new(dist.outputs['Points'], iop.inputs['Points'])
    L.new(ci.outputs[0], iop.inputs['Instance'])
    L.new(rot_out, iop.inputs['Rotation'])
    L.new(sca_out, iop.inputs['Scale'])
    L.new(pick_out, iop.inputs['Instance Index'])
    L.new(iop.outputs[0], go.inputs[0])
    return ng


def robot(scene, walk=True, start=(0.0, -7.5, 0.0), speed=1.44, frames=None, clip=None):
    """claude_robot.vrm, facing +Y; walking (walk.vrma cycled in place, carried at `speed` m/s) when walk=True;
    otherwise standing in `clip` (a stock .vrma name, e.g. 'idle', cycled), or its rest pose."""
    bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')
    view0 = (scene.view_settings.view_transform, scene.view_settings.look, scene.view_settings.exposure)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.vrm(filepath=os.path.join(ASSETS, 'vrms', 'claude_robot.vrm'),
                             set_view_transform_to_standard_on_import=False,
                             set_shading_type_to_material_on_import=False, enable_mtoon_outline_preview=False)
    new = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in new if o.type == 'ARMATURE')
    arm.name = 'claude'
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    vs = scene.view_settings
    vs.view_transform, vs.look, vs.exposure = view0
    arm.rotation_mode = 'XYZ'
    arm.rotation_euler = (0, 0, math.pi)         # the VRM faces -Y in Blender (glTF +Z forward): turn it to +Y
    arm.location = start
    for o in new:
        if o.type == 'MESH':
            o.visible_shadow = True
    if walk or clip:
        bpy.context.view_layer.objects.active = arm
        bpy.ops.import_scene.vrma(filepath=os.path.join(ASSETS, 'animations', f"{clip or 'walk'}.vrma"),
                                  armature_object_name=arm.name)
        from bpy_extras import anim_utils
        ad = arm.animation_data
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        for fc in cb.fcurves:
            if not any(m.type == 'CYCLES' for m in fc.modifiers):
                fc.modifiers.new('CYCLES')
    if walk:
        fa, fb = frames or (scene.frame_start, scene.frame_end)
        fps = scene.render.fps / scene.render.fps_base
        arm.location = start
        arm.keyframe_insert('location', frame=fa)
        arm.location = Vector(start) + Vector((0.0, speed * (fb - fa) / fps, 0.0))
        arm.keyframe_insert('location', frame=fb)
        for fc in cb.fcurves:
            if fc.data_path == 'location':
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
    return arm, [o for o in new if o.type == 'MESH']
