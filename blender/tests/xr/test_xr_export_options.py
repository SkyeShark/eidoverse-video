"""tests/xr/test_xr_export_options.py: the export's options the other xr tests leave at their defaults, on a small set.

    bash run_blender.sh blender/tests/xr/test_xr_export_options.py
    # a GPU job; on a shared machine queue it with EIDO_GPU_WRAP (blender/tests/_where.py)

  export_xr  motion_step=2 (keys every second frame), max_shape_keys=6 (a Geometry Nodes wave over 49 frames: 6
             morph targets at most), cameras=False (no camera in the GLB), page=False (no index.html),
             world_width=64 + world_samples=2 (a small world.hdr)
  motion     instances_to_objects(max_instances=5): 12 moving instances, 5 exported, 7 counted as dropped
  materials  convert_mtoon(unlit=True): a VRM cast's MToon as unlit materials (KHR_materials_unlit in the GLB);
             bake_for_gltf(bake_all=True, device='CPU'): two exportable materials, kept without it, baked into one
  instances  a kit piece placed by two collection-instance empties, one keyed to move: both in the GLB where Blender
             places them at the first, middle and last frames
Small and quick (a 64 px world, one CPU bake at 256 px): out/export_options/.
"""
import json
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(WORKTREE, 'blender'))
OUT = os.path.join(HERE, 'out', 'export_options')
os.makedirs(OUT, exist_ok=True)

from eidoblend.xr import _bl                    # noqa: E402
from eidoblend.xr import export as X            # noqa: E402
from eidoblend.xr import glb as G               # noqa: E402
from eidoblend.xr import materials as M         # noqa: E402
from eidoblend.xr import motion as MO           # noqa: E402
from eidoblend.xr._bl import Tree               # noqa: E402

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print(f"[check] {'PASS' if ok else 'FAIL'} {name}{': ' + str(detail) if detail else ''}", flush=True)


def fresh(name):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    sc = bpy.context.scene
    sc.name = name
    sc.render.fps, sc.render.fps_base = 24, 1.0
    sc.frame_start, sc.frame_end = 1, 49
    return sc


def plain(name, base=(0.6, 0.6, 0.6)):
    m = _bl.new_material(name)
    T = Tree(m.node_tree)
    b = T.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': tuple(base) + (1,), 'Roughness': 0.5})
    T.link(b.outputs[0], T.node('ShaderNodeOutputMaterial').inputs['Surface'])
    return m


def gn_tree(name, build):
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    T = Tree(ng)
    gi, go = T.node('NodeGroupInput'), T.node('NodeGroupOutput')
    T.link(build(T, gi.outputs[0]), go.inputs[0])
    return ng


# ----------------------------------------------------------------- 1. export_xr's options on a small animated set ---
sc = fresh('export_options')
w = bpy.data.worlds.new('options_sky')
w.use_nodes = True
T = Tree(w.node_tree)
tc = T.node('ShaderNodeTexCoord')
z = T.node('ShaderNodeSeparateXYZ', inputs={0: tc.outputs['Generated']}).outputs['Z']
T.link(T.node('ShaderNodeBackground', inputs={'Color': T.mix_rgb(z, (0.3, 0.3, 0.3, 1), (0.2, 0.4, 0.9, 1)),
                                              'Strength': 1.0}).outputs[0],
       T.node('ShaderNodeOutputWorld').inputs['Surface'])
sc.world = w
bpy.ops.mesh.primitive_cube_add(size=0.5, location=(0, 0, 0.25))
cube = bpy.context.object
cube.name = 'keyed_cube'
cube.data.materials.append(plain('cube_grey'))
for f, x in ((1, -2.0), (49, 2.0)):
    cube.location.x = x
    cube.keyframe_insert('location', frame=f)
_bl.set_interpolation(cube, 'LINEAR')
bpy.ops.mesh.primitive_grid_add(x_subdivisions=16, y_subdivisions=4, size=1.0, location=(0, 2, 1))
wave = bpy.context.object
wave.name = 'wave_sheet'
wave.data.materials.append(plain('wave_red', (0.7, 0.1, 0.1)))


def wave_build(T, geo):
    p = T.node('GeometryNodeInputPosition').outputs[0]
    sx = T.node('ShaderNodeSeparateXYZ', inputs={0: p}).outputs['X']
    st = T.node('GeometryNodeInputSceneTime').outputs['Seconds']
    dz = T.math('MULTIPLY', T.math('SINE', T.math('SUBTRACT', T.math('MULTIPLY', sx, 6.0), T.math('MULTIPLY', st, 5.0))), 0.1)
    return T.node('GeometryNodeSetPosition', inputs={'Geometry': geo,
                                                     'Offset': T.node('ShaderNodeCombineXYZ', inputs={2: dz}).outputs[0]}).outputs[0]


wave.modifiers.new('wave', 'NODES').node_group = gn_tree('options_wave', wave_build)
cd = bpy.data.cameras.new('cam_options')
cam = bpy.data.objects.new('cam_options', cd)
sc.collection.objects.link(cam)
cam.location = (0, -6, 2)
cam.rotation_euler = _bl.look_at_rotation(cam.location, (0, 0, 0.5))
sc.camera = cam
X.set_xr(sc, landmarks=False)
out = os.path.join(OUT, 'vr')
man = X.export_xr(out, sc, bake_materials=False, motion_step=2, max_shape_keys=6, cameras=False, page=False,
                  world_width=64, world_samples=2)
g = G.read(os.path.join(out, 'scene.glb'))
s = G.summary(g)
check('cameras=False: no camera in the GLB', not s['cameras'] and not man['cameras'], man['cameras'])
check('page=False: no index.html beside the manifest', not os.path.exists(os.path.join(out, 'index.html'))
      and os.path.exists(os.path.join(out, 'scene.xr.json')))
ci = g.node_by_name('keyed_cube')
ch = next(c for a in g.json['animations'] for c in a['channels'] if c['target'].get('node') == ci
          and c['target']['path'] == 'translation')
smp = g.json['animations'][0]['samplers'][ch['sampler']]
ts = g.accessor(smp['input'])
dts = sorted({round(b - a, 5) for a, b in zip(ts, ts[1:])})
check('motion_step=2: the clip sampled every second frame (1/12 s at 24 fps)', dts and abs(dts[0] - 2 / 24) < 1e-4,
      f'{len(ts)} keys, steps {dts[:3]}')
mt = man['report']['motion'].get('wave_sheet', {})
check('max_shape_keys=6: the wave over 49 frames as 6 morph targets at most (the step grows to fit)',
      mt and mt['morph_targets'] <= 6 and mt['step'] >= 9 and s['morph_targets'] == mt['morph_targets'], mt)
wsz = None
with open(os.path.join(out, 'world.hdr'), 'rb') as f:
    for line in f.read(4096).split(b'\n'):
        if line.startswith(b'-Y '):
            wsz = (int(line.split()[3]), int(line.split()[1]))
check('world_width=64 (world_samples=2): world.hdr is 64 x 32', wsz == (64, 32), wsz)

# --------------------------------------------------- 2. instances_to_objects(max_instances=5): the cap and its count
sc = fresh('instance_cap')


def crowd_build(T, geo):
    idx = T.node('GeometryNodeInputIndex').outputs[0]
    st = T.node('GeometryNodeInputSceneTime').outputs['Seconds']
    ang = T.math('ADD', T.math('MULTIPLY', idx, 2 * math.pi / 12), st)
    pos = T.node('ShaderNodeCombineXYZ', inputs={0: T.math('COSINE', ang), 1: T.math('SINE', ang)})
    pts = T.node('GeometryNodePoints', inputs={'Count': 12, 'Position': pos.outputs[0]})
    cube_ = T.node('GeometryNodeMeshCube', inputs={'Size': (0.1, 0.1, 0.1)})
    return T.node('GeometryNodeInstanceOnPoints', inputs={'Points': pts.outputs[0],
                                                          'Instance': cube_.outputs['Mesh']}).outputs['Instances']


crowd = bpy.data.objects.new('crowd', bpy.data.meshes.new('crowd'))
sc.collection.objects.link(crowd)
crowd.modifiers.new('gn', 'NODES').node_group = gn_tree('options_crowd', crowd_build)
r = MO.instances_to_objects(crowd, sc, step=8, max_instances=5)
made = [o for o in bpy.data.objects if o.name.startswith('crowd_')]
check('instances_to_objects(max_instances=5): 5 keyed objects made, the other 7 counted as dropped',
      r['instances'] == 5 and r['dropped'] == 7 and len(made) == 5 and r['moving'], {k: v for k, v in r.items()
                                                                                       if k != 'objects'})
# an instance that appears late grows where it appears (not from the origin): appear at frame 25
sc2 = fresh('late_instance')


def late_build(T, geo):
    st = T.node('GeometryNodeInputSceneTime').outputs['Frame']
    n = T.math('GREATER_THAN', st, 24.5)
    pts = T.node('GeometryNodePoints', inputs={'Count': n, 'Position': (3.0, 1.0, 0.5)})
    cube_ = T.node('GeometryNodeMeshCube', inputs={'Size': (0.2, 0.2, 0.2)})
    return T.node('GeometryNodeInstanceOnPoints', inputs={'Points': pts.outputs[0],
                                                          'Instance': cube_.outputs['Mesh']}).outputs['Instances']


late = bpy.data.objects.new('late', bpy.data.meshes.new('late'))
sc2.collection.objects.link(late)
late.modifiers.new('gn', 'NODES').node_group = gn_tree('options_late', late_build)
r = MO.instances_to_objects(late, sc2, step=1)
lo = next(o for o in bpy.data.objects if o.name.startswith('late_'))
sc2.frame_set(10)
early = lo.matrix_world.translation.copy()
sc2.frame_set(30)
there = lo.matrix_world.translation.copy()
check('an instance that appears late waits, collapsed, where it will appear (it grows in place, not from the origin)',
      (early - there).length < 1e-4 and max(lo.scale) > 0.5 and there.x > 2.9, (tuple(round(x, 3) for x in early),
                                                                              tuple(round(x, 3) for x in there)))

# ------------------------------------- 3. materials: convert_mtoon(unlit=True), bake_for_gltf(bake_all=True, CPU)
sc = fresh('materials_options')
from eidoblend.characters import load_vrm      # noqa: E402
her = load_vrm('aletheia', location=(0, 0, 0), rotation=0.0)
M.ensure_vrm_addon()
objs = X.export_objects(sc)
conv = M.convert_mtoon(objs, unlit=True)
new = [bpy.data.materials[n] for n in conv.values()]


def unlit_hookup(m):
    out_ = next(n for n in m.node_tree.nodes if n.type == 'OUTPUT_MATERIAL')
    return out_.inputs['Surface'].is_linked and out_.inputs['Surface'].links[0].from_socket.type == 'RGBA'


check('convert_mtoon(unlit=True): the cast\'s MToon materials become unlit (a colour into the output)',
      len(conv) >= 3 and all(unlit_hookup(m) or m.get('xr_mtoon_outline') for m in new), f'{len(conv)} converted')
out = os.path.join(OUT, 'vr_unlit_cast')
man = X.export_xr(out, sc, bake_materials=False, world=False, page=False)
s = G.summary(G.read(os.path.join(out, 'scene.glb')))
ul = [m for m in s['materials'] if m['name'] in set(conv.values())]
check('... and go into the GLB as KHR_materials_unlit', ul and all(m['unlit'] for m in ul),
      f"{sum(1 for m in ul if m['unlit'])} of {len(ul)} unlit")
sc = fresh('bake_all')
bpy.ops.mesh.primitive_cube_add(size=1.0)
box = bpy.context.object
box.name = 'two_colour_box'
box.data.materials.append(plain('plain_green', (0.1, 0.6, 0.2)))
box.data.materials.append(plain('plain_blue', (0.1, 0.2, 0.7)))
for i, p in enumerate(box.data.polygons):
    p.material_index = 0 if i < 3 else 1
kept = M.bake_for_gltf([box], os.path.join(OUT, 'bake_all_textures'), device='CPU', log=None)
r = M.bake_for_gltf([box], os.path.join(OUT, 'bake_all_textures'), device='CPU', bake_all=True, log=None)
b = r['baked'].get('two_colour_box', {})
check("bake_for_gltf(bake_all=True, device='CPU'): two exportable materials (kept as they are without it) baked into "
      'one texture, on the CPU', 'two_colour_box' in kept['kept'] and b.get('device') == 'CPU'
      and os.path.exists(b.get('images', {}).get('base', '')) and len(box.data.materials) == 1,
      {k: v for k, v in b.items() if k != 'images'})
# an image texture read through Object coordinates and a Mapping node: the exporter would lay it on the UVs, so the
# survey must count it lost (to bake); the same image on the UVs through a Mapping node goes as it is
img = bpy.data.images.new('options_checker', 32, 32)
for coords, want_lost in (('Object', True), ('UV', False)):
    m = _bl.new_material(f'image_by_{coords.lower()}')
    T = Tree(m.node_tree)
    tc_ = T.node('ShaderNodeTexCoord')
    mp = T.node('ShaderNodeMapping', inputs={'Vector': tc_.outputs[coords]})
    tx = T.node('ShaderNodeTexImage', inputs={'Vector': mp.outputs[0]})
    tx.image = img
    b_ = T.node('ShaderNodeBsdfPrincipled')
    T.link(tx.outputs['Color'], b_.inputs['Base Color'])
    T.link(b_.outputs[0], T.node('ShaderNodeOutputMaterial').inputs['Surface'])
    lost = M.classify(m)['lost']
    check(f'an image through {coords} coordinates and a Mapping node: '
          + ('lost (to bake: the exporter would lay it on the UVs)' if want_lost else 'written as it is'),
          ('Base Color' in lost) == want_lost, lost)

# ------------------------------- 4. collection instances (a kit piece placed by empties), one of them keyed to move
sc = fresh('collection_instances')
kit = bpy.data.collections.new('kit_cone')
bpy.ops.mesh.primitive_cone_add(radius1=0.3, depth=0.8, location=(0, 0, 0.4))
cone = bpy.context.object
cone.name = 'kit_cone_piece'
for c in list(cone.users_collection):
    c.objects.unlink(cone)
kit.objects.link(cone)
cone.data.materials.append(plain('cone_orange', (0.8, 0.35, 0.1)))
placed = []
for name, loc in (('cone_still', (-1.5, 0.0, 0.0)), ('cone_moving', (1.5, 0.0, 0.0))):
    e = bpy.data.objects.new(name, None)
    e.instance_type, e.instance_collection = 'COLLECTION', kit
    e.location = loc
    sc.collection.objects.link(e)
    placed.append(e)
mv = placed[1]
for f, y in ((1, 0.0), (49, 3.0)):
    mv.location.y = y
    mv.keyframe_insert('location', frame=f)
_bl.set_interpolation(mv, 'LINEAR')
truth = {}
for f in (1, 25, 49):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    truth[f] = sorted(tuple(round(v, 4) for v in i.matrix_world.translation) for i in dg.object_instances
                      if i.is_instance and i.parent and i.parent.original in placed)
sc.frame_set(1)
out = os.path.join(OUT, 'vr_collection_instances')
man = X.export_xr(out, sc, bake_materials=False, world=False, page=False)
g = G.read(os.path.join(out, 'scene.glb'))
worst = 0.0
for f in (1, 25, 49):
    t = (f - 1) / 24
    mats_ = G.world_matrices(g, t)
    got = []
    for i, nd in enumerate(g.json['nodes']):
        if 'mesh' not in nd:
            continue
        ext = nd.get('extensions', {}).get('EXT_mesh_gpu_instancing')
        m = mats_[i]
        if ext:                                       # (instanced: each translation of the instancing attribute)
            for tr in g.accessor(ext['attributes']['TRANSLATION']):
                x, y, z = (m[0][0] * tr[0] + m[0][1] * tr[1] + m[0][2] * tr[2] + m[0][3],
                           m[1][0] * tr[0] + m[1][1] * tr[1] + m[1][2] * tr[2] + m[1][3],
                           m[2][0] * tr[0] + m[2][1] * tr[1] + m[2][2] * tr[2] + m[2][3])
                got.append((x, -z, y))
        else:
            got.append((m[0][3], -m[2][3], m[1][3]))
    want = truth[f]
    if len(got) != len(want):
        worst = 1e9
        break
    for w_ in want:
        worst = max(worst, min(math.dist(w_, g_) for g_ in got))
check('collection instances: the still one and the keyed one stand in the GLB where Blender places them at the '
      'first, middle and last frames', worst < 2e-3 and len(truth[1]) == 2,
      f"{len(truth[1])} instances, worst {worst * 1000:.2f} mm; motion: {sorted(k for k in man['report']['motion'])}")

with open(os.path.join(OUT, 'report.json'), 'w') as f:
    json.dump([(n, ok, str(d)) for n, ok, d in RESULTS], f, indent=1)
n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
print(f'[check] {len(RESULTS) - n_fail} passed, {n_fail} failed', flush=True)
sys.exit(1 if n_fail else 0)
