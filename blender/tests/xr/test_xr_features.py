"""tests/xr/test_xr_features.py: a small lit, animated film set through the whole XR export, checked number by number.

    cd <main checkout> && HEAVY_VRAM_GB=6 bash work/claude_body/work/tmp/heavy.sh 16 bash run_blender.sh \\
        <worktree>/blender/tests/xr/test_xr_features.py

The set (5 s at 24 fps, AgX) holds one of each thing an eidoblend film animates or shades in a way glTF must be taught:
  robot      claude_robot_2k.vrm (characters.load_vrm) dancing a VRMA clip (an NLA strip)  -> skin + sampled joints
  ball       keyed location (a bounce)                                                    -> TRS keys
  spinner    rotation driven by a driver (frame x 0.1)                                    -> sampled
  drone      Follow Path on a circle, offset keyed                                        -> sampled constraint
  cam_film   keyed dolly + Track To                                                       -> an animated glTF camera
  blob       a shape key keyed 0 -> 1 -> 0                                                -> morph weights
  flag       a Geometry Nodes wave (scene time)                                           -> deform_to_shape_keys
  orbiters   8 Geometry Nodes instances orbiting                                          -> instances_to_objects
  rocks      a still Geometry Nodes scatter                                               -> EXT_mesh_gpu_instancing
  ground     noise / bump / ramp procedural material                                      -> bake: base, ORM, normal
  neon       emission strength keyed (a flicker)                                          -> emissive + a track
  lamp       a point light, energy keyed                                                  -> a light track
  popper     hide_render keyed (appears at 2 s)                                           -> a visibility track
  sun / spot / key (area)                                                                 -> punctual + RectAreaLight
  world      a sky gradient with a warm glow toward the sun                               -> world.hdr, oriented
EEVEE stills from cam_film at t = 1.0, 2.5, 4.0 go to out/features/; the bundle to out/features/vr/ for the page test.
"""
import json
import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(WORKTREE, 'blender'))
# --no-render: an API run (no EEVEE still, no Cycles bake or world image) into out/features_norender/: the motion,
# lights, tracks and conversions are checked; what needs a render is left to the GPU run
NO_RENDER = '--no-render' in sys.argv
OUT = os.path.join(HERE, 'out', 'features_norender' if NO_RENDER else 'features')
os.makedirs(OUT, exist_ok=True)

from eidoblend.xr import _bl                    # noqa: E402
from eidoblend.xr import export as X            # noqa: E402
from eidoblend.xr import glb as G               # noqa: E402
from eidoblend.xr import world as W             # noqa: E402
from eidoblend.xr._bl import Tree               # noqa: E402

RESULTS = []
FPS, SECONDS = 24, 5.0
TIMES = (1.0, 2.5, 4.0)
SUN_ELEV, SUN_AZ = 32.0, -35.0          # degrees; azimuth from +Y toward +X


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print(f"[check] {'PASS' if ok else 'FAIL'} {name}{': ' + str(detail) if detail else ''}", flush=True)


def frame_of(t):
    return 1 + int(round(t * FPS))


def principled(name, base=(0.5, 0.5, 0.5), rough=0.5, metal=0.0, emit=None, strength=0.0):
    m = _bl.new_material(name)
    T = Tree(m.node_tree)
    b = T.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': tuple(base) + (1,), 'Roughness': rough,
                                                    'Metallic': metal})
    if emit is not None:
        b.inputs['Emission Color'].default_value = tuple(emit) + (1,)
        b.inputs['Emission Strength'].default_value = strength
    o = T.node('ShaderNodeOutputMaterial')
    T.link(b.outputs[0], o.inputs['Surface'])
    m.diffuse_color = tuple(base) + (1,)
    return m


def key_linear(idb):
    _bl.set_interpolation(idb, 'LINEAR')


def mesh_object(name, me, col, loc=(0, 0, 0), mat=None):
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    ob.location = loc
    if mat is not None:
        ob.data.materials.append(mat)
    return ob


def prim(kind, **kw):
    getattr(bpy.ops.mesh, f'primitive_{kind}_add')(**kw)
    return bpy.context.object


# ------------------------------------------------------------------------------------------------- the set ---
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene
sc.render.fps, sc.render.fps_base = FPS, 1.0
sc.frame_start, sc.frame_end = 1, 1 + int(SECONDS * FPS)
sc.render.resolution_x, sc.render.resolution_y = 960, 540
sc.render.engine = 'BLENDER_EEVEE'
sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = 'AgX - Base Contrast'
sc.view_settings.exposure = 0.0
ee = sc.eevee
ee.taa_render_samples = 16
ee.use_shadows = True
ee.use_raytracing = True
col = sc.collection

# world: zenith / horizon / ground gradient + a warm glow toward the sun (an asymmetric marker for the equirect)
sun_dir = Vector((math.sin(math.radians(SUN_AZ)) * math.cos(math.radians(SUN_ELEV)),
                  math.cos(math.radians(SUN_AZ)) * math.cos(math.radians(SUN_ELEV)), math.sin(math.radians(SUN_ELEV))))
wd = bpy.data.worlds.new('xr_features_sky')
wd.use_nodes = True
sc.world = wd
T = Tree(wd.node_tree)
tc = T.node('ShaderNodeTexCoord')
dz = T.node('ShaderNodeSeparateXYZ', inputs={0: tc.outputs['Generated']}).outputs['Z']
up = T.math('POWER', T.math('MAXIMUM', dz, 0.0), 0.6)
c_sky = T.mix_rgb(up, (0.50, 0.58, 0.72, 1), (0.10, 0.20, 0.50, 1))
c_all = T.mix_rgb(T.math('LESS_THAN', dz, 0.0), c_sky, (0.10, 0.085, 0.07, 1))
glow = T.math('POWER', T.math('MAXIMUM', T.vmath('DOT_PRODUCT', tc.outputs['Generated'], tuple(sun_dir)), 0.0), 48.0)
gk = T.node('ShaderNodeCombineColor', inputs={0: T.math('MULTIPLY', glow, 6.0), 1: T.math('MULTIPLY', glow, 4.5),
                                              2: T.math('MULTIPLY', glow, 2.8)})
c = T.mix_rgb(1.0, c_all, gk.outputs[0], blend='ADD')
bg = T.node('ShaderNodeBackground', inputs={'Color': c, 'Strength': 0.9})
wo = T.node('ShaderNodeOutputWorld')
T.link(bg.outputs[0], wo.inputs['Surface'])

# ground: procedural (noise -> ramp base, noise roughness, bump) -> needs the bake
gm = _bl.new_material('ground_procedural')
T = Tree(gm.node_tree)
tco = T.node('ShaderNodeTexCoord')
nz = T.node('ShaderNodeTexNoise', inputs={'Vector': tco.outputs['Object'], 'Scale': 0.9, 'Detail': 6.0, 'Roughness': 0.6})
ramp = T.node('ShaderNodeValToRGB', inputs={'Fac': nz.outputs['Fac']})
ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[0].color = 0.35, (0.09, 0.07, 0.05, 1)
ramp.color_ramp.elements[1].position, ramp.color_ramp.elements[1].color = 0.7, (0.42, 0.33, 0.22, 1)
vor = T.node('ShaderNodeTexVoronoi', inputs={'Vector': tco.outputs['Object'], 'Scale': 6.0})
rough = T.node('ShaderNodeMapRange', inputs={'Value': nz.outputs['Fac'], 'From Min': 0.3, 'From Max': 0.7,
                                             'To Min': 0.55, 'To Max': 0.9})
bump = T.node('ShaderNodeBump', inputs={'Height': vor.outputs['Distance'], 'Strength': 0.35, 'Distance': 0.05})
b = T.node('ShaderNodeBsdfPrincipled')
T.link(ramp.outputs['Color'], b.inputs['Base Color'])
T.link(rough.outputs['Result'], b.inputs['Roughness'])
T.link(bump.outputs['Normal'], b.inputs['Normal'])
o = T.node('ShaderNodeOutputMaterial')
T.link(b.outputs[0], o.inputs['Surface'])
me = bpy.data.meshes.new('ground')
s = 12.0
me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
ground = mesh_object('ground', me, col, mat=gm)

# the robot, dancing
from eidoblend.characters import load_vrm, play_vrma_default     # noqa: E402
robot = load_vrm('claude_robot_2k', location=(0, 0, 0), rotation=0.0)
play_vrma_default(robot, 'dance')
her = load_vrm('aletheia', location=(-1.5, 0.9, 0), rotation=20.0)       # the cast's MToon: converted, not baked
play_vrma_default(her, 'cheer')

# ball: keyed bounce
ball = prim('uv_sphere', radius=0.25, location=(-2.0, -1.2, 0.25), segments=32, ring_count=16)
ball.name = 'ball'
bpy.ops.object.shade_smooth()
ball.data.materials.append(principled('ball_metal', (0.85, 0.75, 0.55), 0.25, 1.0))
for k in range(0, 11):
    f = 1 + k * 12
    ball.location = (-2.0 + 0.15 * k, -1.2, 0.25 + (1.2 if k % 2 else 0.0))
    ball.keyframe_insert('location', frame=f)
key_linear(ball)

# spinner: a driver on rotation Z
spinner = prim('cube', size=0.5, location=(-2.6, 1.6, 0.25))
spinner.name = 'spinner'
spinner.data.materials.append(principled('spinner_red', (0.7, 0.08, 0.06), 0.4))
drv = spinner.driver_add('rotation_euler', 2).driver
drv.type = 'SCRIPTED'
drv.use_self = False
drv.expression = 'frame * 0.1'

# drone: Follow Path on a circle, the offset keyed
bpy.ops.curve.primitive_bezier_circle_add(radius=3.0, location=(0, 0.5, 2.6))
path = bpy.context.object
path.name = 'drone_path'
path.hide_render = True
drone = prim('cone', radius1=0.18, depth=0.3, location=(0, 0, 0))
drone.name = 'drone'
drone.data.materials.append(principled('drone_white', (0.85, 0.85, 0.88), 0.3))
fp = drone.constraints.new('FOLLOW_PATH')
fp.target = path
fp.use_fixed_location = True
fp.use_curve_follow = True
fp.offset_factor = 0.0
drone.keyframe_insert('constraints["Follow Path"].offset_factor', frame=sc.frame_start)
fp.offset_factor = 0.8
drone.keyframe_insert('constraints["Follow Path"].offset_factor', frame=sc.frame_end)
key_linear(drone)

# blob: a shape key keyed 0 -> 1 -> 0
blob = prim('ico_sphere', radius=0.35, subdivisions=3, location=(2.2, -1.0, 0.45))
blob.name = 'blob'
bpy.ops.object.shade_smooth()
blob.data.materials.append(principled('blob_green', (0.1, 0.5, 0.2), 0.35))
blob.shape_key_add(name='Basis')
kb = blob.shape_key_add(name='puff')
for v in kb.data:
    v.co = v.co * 1.0 + Vector((0, 0, max(0.0, v.co.z) * 0.9))
for f, val in ((1, 0.0), (61, 1.0), (121, 0.0)):
    kb.value = val
    kb.keyframe_insert('value', frame=f)
key_linear(blob.data.shape_keys)

# flag: a Geometry Nodes wave
fl = prim('grid', x_subdivisions=24, y_subdivisions=12, size=1.0, location=(0, 0, 0))
fl.name = 'flag'
fl.scale = (1.6, 1.0, 1.0)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
fl.rotation_euler = (math.pi / 2, 0, 0)
fl.location = (2.6, 1.8, 2.0)
wav = _bl.new_material('flag_stripes')
T = Tree(wav.node_tree)
wv = T.node('ShaderNodeTexWave', inputs={'Scale': 2.5, 'Distortion': 0.0})
st = T.math('GREATER_THAN', wv.outputs['Fac'], 0.5)
fc = T.mix_rgb(st, (0.75, 0.08, 0.1, 1), (0.92, 0.88, 0.8, 1))
bb = T.node('ShaderNodeBsdfPrincipled', inputs={'Roughness': 0.7})
T.link(fc, bb.inputs['Base Color'])
oo = T.node('ShaderNodeOutputMaterial')
T.link(bb.outputs[0], oo.inputs['Surface'])
fl.data.materials.append(wav)
ng = bpy.data.node_groups.new('flag_wave', 'GeometryNodeTree')
ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
T = Tree(ng)
gi = T.node('NodeGroupInput')
go = T.node('NodeGroupOutput')
pos = T.node('GeometryNodeInputPosition')
sx = T.node('ShaderNodeSeparateXYZ', inputs={0: pos.outputs[0]}).outputs['X']
stime = T.node('GeometryNodeInputSceneTime').outputs['Seconds']
amp = T.math('MULTIPLY', T.math('ADD', sx, 0.8), 0.12)
wave = T.math('MULTIPLY', T.math('SINE', T.math('SUBTRACT', T.math('MULTIPLY', sx, 3.5), T.math('MULTIPLY', stime, 4.0))), amp)
off = T.node('ShaderNodeCombineXYZ', inputs={2: wave})
sp = T.node('GeometryNodeSetPosition', inputs={'Geometry': gi.outputs[0], 'Offset': off.outputs[0]})
T.link(sp.outputs[0], go.inputs[0])
fl.modifiers.new('wave', 'NODES').node_group = ng

# orbiters: 8 moving Geometry Nodes instances; rocks: a still scatter
def instancer(name, count, moving):
    me = bpy.data.meshes.new(name)
    ob = mesh_object(name, me, col)
    ng = bpy.data.node_groups.new(name + '_gn', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    T = Tree(ng)
    T.node('NodeGroupInput')
    go = T.node('NodeGroupOutput')
    idx = T.node('GeometryNodeInputIndex').outputs[0]
    if moving:
        tt = T.node('GeometryNodeInputSceneTime').outputs['Seconds']
        ang = T.math('ADD', T.math('MULTIPLY', idx, 2 * math.pi / count), T.math('MULTIPLY', tt, 0.7))
        px = T.math('MULTIPLY', T.math('COSINE', ang), 1.6)
        py = T.math('ADD', T.math('MULTIPLY', T.math('SINE', ang), 1.6), 2.2)
        pz = T.math('ADD', 0.9, T.math('MULTIPLY', T.math('SINE', T.math('ADD', T.math('MULTIPLY', tt, 3.0), idx)), 0.25))
        geo = T.node('GeometryNodeMeshCube', inputs={'Size': (0.22, 0.22, 0.22)}).outputs['Mesh']
        mat = principled('orbiter_cyan', (0.02, 0.05, 0.06), 0.3, emit=(0.1, 0.8, 1.0), strength=4.0)
    else:
        rnd = T.node('FunctionNodeRandomValue', data_type='FLOAT_VECTOR',
                     inputs={'Min': (-6.0, -2.0, 0.0), 'Max': (6.0, 8.0, 0.0)})
        T.link(idx, rnd.inputs['ID'])
        sep = T.node('ShaderNodeSeparateXYZ', inputs={0: rnd.outputs[0]})
        px, py, pz = sep.outputs['X'], sep.outputs['Y'], 0.05
        geo = T.node('GeometryNodeMeshIcoSphere', inputs={'Radius': 0.12, 'Subdivisions': 1}).outputs['Mesh']
        mat = principled('rock_grey', (0.25, 0.24, 0.22), 0.85)
    p3 = T.node('ShaderNodeCombineXYZ', inputs={0: px, 1: py, 2: pz})
    pts = T.node('GeometryNodePoints', inputs={'Count': count, 'Position': p3.outputs[0]})
    sm = T.node('GeometryNodeSetMaterial', inputs={'Geometry': geo})
    sm.inputs['Material'].default_value = mat
    inst = T.node('GeometryNodeInstanceOnPoints', inputs={'Points': pts.outputs[0], 'Instance': sm.outputs[0]})
    T.link(inst.outputs['Instances'], go.inputs[0])
    ob.modifiers.new('gn', 'NODES').node_group = ng
    return ob


orbiters = instancer('orbiters', 8, True)
rocks = instancer('rocks', 40, False)

# neon: emission strength keyed (a flicker) on an exportable material
neon_m = principled('neon', (0.02, 0.02, 0.02), 0.4, emit=(1.0, 0.12, 0.6), strength=2.0)
neon = prim('cube', size=1.0, location=(-1.2, 3.0, 2.1))
neon.name = 'neon'
neon.scale = (0.9, 0.06, 0.18)
neon.data.materials.append(neon_m)
es = next(n for n in neon_m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED').inputs['Emission Strength']
for f, v in ((1, 2.0), (31, 12.0), (61, 3.0), (91, 10.0), (121, 2.0)):
    es.default_value = v
    es.keyframe_insert('default_value', frame=f)
key_linear(neon_m.node_tree)

# popper: appears at t = 2 s
popper = prim('torus', major_radius=0.3, minor_radius=0.08, location=(1.2, -2.0, 0.6))
popper.name = 'popper'
popper.data.materials.append(principled('popper_gold', (0.9, 0.6, 0.15), 0.3, 1.0))
for f, hidden in ((1, True), (48, True), (49, False)):
    popper.hide_render = hidden
    popper.hide_viewport = hidden
    popper.keyframe_insert('hide_render', frame=f)
    popper.keyframe_insert('hide_viewport', frame=f)
sc.timeline_markers.new('cue_pop', frame=49)

# a metaball (the exporter skips metaballs: export_xr makes it a mesh), a text with depth (the exporter's own mesh
# conversion), and an empty volume (not glTF: named in the warnings)
mb = bpy.data.metaballs.new('blobby')
mb.resolution = mb.render_resolution = 0.06
for x in (-0.16, 0.16):
    el = mb.elements.new()
    el.co, el.radius = (x, 0.0, 0.0), 0.28
blobby = bpy.data.objects.new('blobby', mb)
col.objects.link(blobby)
blobby.location = (1.9, 2.7, 0.4)
blobby.data.materials.append(principled('blobby_blue', (0.1, 0.25, 0.8), 0.3))
td = bpy.data.curves.new('sign_text', 'FONT')
td.body, td.extrude, td.size, td.align_x = 'XR', 0.04, 0.7, 'CENTER'
sign = bpy.data.objects.new('sign_text', td)
col.objects.link(sign)
sign.location = (-2.9, 3.0, 1.0)
sign.rotation_euler = (math.pi / 2, 0.0, 0.0)
sign.data.materials.append(principled('sign_white', (0.9, 0.88, 0.85), 0.4))
smoke = bpy.data.objects.new('smoke_volume', bpy.data.volumes.new('smoke_volume'))
col.objects.link(smoke)


def light(name, kind, loc, rot=None, **kw):
    ld = bpy.data.lights.new(name, kind)
    for k, v in kw.items():
        setattr(ld, k, v)
    ob = bpy.data.objects.new(name, ld)
    col.objects.link(ob)
    ob.location = loc
    if rot is not None:
        ob.rotation_euler = rot
    return ob


sun = light('sun', 'SUN', (0, 0, 10), energy=3.0, angle=math.radians(1.0))
sun.data.use_temperature = True
sun.data.temperature = 5200.0
sun.rotation_euler = (-sun_dir).to_track_quat('-Z', 'Y').to_euler()
lamp = light('lamp', 'POINT', (-1.2, 2.6, 1.4), energy=60.0, shadow_soft_size=0.05, color=(1.0, 0.55, 0.3))
for f, v in ((1, 60.0), (40, 160.0), (80, 30.0), (121, 60.0)):
    lamp.data.energy = v
    lamp.data.keyframe_insert('energy', frame=f)
key_linear(lamp.data)
spot = light('spot', 'SPOT', (3.0, -2.5, 3.2), energy=400.0, spot_size=math.radians(40), spot_blend=0.3,
             shadow_soft_size=0.1)
spot.rotation_euler = (Vector((0, 0, 1.0)) - spot.location).to_track_quat('-Z', 'Y').to_euler()
key = light('key', 'AREA', (-2.4, -2.6, 2.4), energy=250.0, size=1.0, shape='SQUARE')
key.rotation_euler = (Vector((0, 0, 1.1)) - key.location).to_track_quat('-Z', 'Y').to_euler()

# cam_film: keyed dolly + Track To an empty at the robot's chest
aim = bpy.data.objects.new('cam_aim', None)
col.objects.link(aim)
aim.location = (0, 0, 1.15)
cd = bpy.data.cameras.new('cam_film')
cd.lens = 32.0
cd.clip_start, cd.clip_end = 0.05, 200.0
cam = bpy.data.objects.new('cam_film', cd)
col.objects.link(cam)
for f, p in ((1, (3.2, -6.2, 1.5)), (121, (-2.4, -6.0, 2.1))):
    cam.location = p
    cam.keyframe_insert('location', frame=f)
key_linear(cam)
tt = cam.constraints.new('TRACK_TO')
tt.target = aim
tt.track_axis, tt.up_axis = 'TRACK_NEGATIVE_Z', 'UP_Y'
sc.camera = cam
X.set_xr(sc, street=1.0, table=0.04, start=(0.0, -4.0, 0.0), facing=(0.0, 1.0, 0.0), table_centre=(0, 0.5, 0),
         name='features', shadows=True)

if '--dry' in sys.argv:                  # build only (no GPU): the scene, what the export would see, then stop
    from eidoblend.xr import materials as M, motion as MO          # noqa: E402
    print('[dry] survey', json.dumps(M.survey(), indent=None))
    det = MO.detect(sc)
    print('[dry] detect', {k: [getattr(x, 'name', x) if not isinstance(x, tuple) else (x[0].name, x[1]) for x in v]
                           for k, v in det.items()})
    print('[dry] animated', [(k, getattr(o, 'name', '?'), p) for k, o, p in MO.animated_properties(sc)])
    print('[dry] humanoid hand/head', robot.humanoid.get('rightHand'), robot.humanoid.get('head'))
    sys.exit(0)

# ------------------------------------------------------------------------------------------ EEVEE stills ---
sc.render.image_settings.media_type = 'IMAGE'
sc.render.image_settings.file_format = 'PNG'
sc.render.use_file_extension = False
for t in (() if NO_RENDER else TIMES):
    p = os.path.join(OUT, f'eevee_cam_film_t{t:g}.png')
    sc.frame_set(frame_of(t))
    sc.render.filepath = p
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    check(f'EEVEE still t = {t:g} s', os.path.exists(p), f'{time.time() - t0:.1f} s')

# ------------------------------------------------- what Blender says at the check times (before the export)
truth = {}
hum = robot.humanoid
hand = hum.get('rightHand')
head = hum.get('head')
for t in TIMES:
    sc.frame_set(frame_of(t))
    dg = bpy.context.evaluated_depsgraph_get()
    d = {}
    for n in ('ball', 'spinner', 'drone', 'cam_film'):
        d[n] = bpy.data.objects[n].matrix_world.copy()
    d['puff'] = blob.data.shape_keys.key_blocks['puff'].value
    arm = robot.arm
    d['hand'] = arm.matrix_world @ arm.pose.bones[hand].head if hand else None
    d['head'] = arm.matrix_world @ arm.pose.bones[head].head if head else None
    her_head = her.humanoid.get('head')
    d['her_head'] = (her_head, her.arm.matrix_world @ her.arm.pose.bones[her_head].head) if her_head else None
    ev = fl.evaluated_get(dg)
    d['flag'] = [ev.matrix_world @ v.co for v in ev.data.vertices]
    d['orbiters'] = sorted((tuple(i.persistent_id), i.matrix_world.translation.copy()) for i in dg.object_instances
                           if i.is_instance and i.parent and i.parent.original == orbiters)
    d['lamp'] = lamp.data.energy
    d['neon'] = es.default_value
    truth[t] = d
sc.frame_set(sc.frame_start)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'features.blend'), check_existing=False)

# ----------------------------------------------------------------------------------------------- export ---
vr = os.path.join(OUT, 'vr')
man = X.export_xr(vr, sc, name='scene', world_width=1024, texel_density=40, choreo_names=('ball', 'drone'),
                  bake_materials=not NO_RENDER, world=not NO_RENDER)
rep, s_ = man['report'], man['summary']
check('no GLB animation problem (every channel on its own node, every mover has one)', not rep.get('channel_problems'),
      rep.get('channel_problems'))
g = G.read(os.path.join(vr, 'scene.glb'))
check('one clip of the whole 5 s', len(s_['animations']) == 1 and abs(s_['duration'] - SECONDS) < 0.05,
      [(a['name'], round(a['duration'], 3), a['channels'], a['paths']) for a in s_['animations']])


def gltf_world(name, t):
    i = g.node_by_name(name)
    m = G.world_matrices(g, t)[i]
    # glTF (Y-up) -> Blender: B = C @ M @ C^-1 with C = Rx(+90)
    C = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    return C @ Matrix(m) @ C.inverted()


for t in TIMES:
    d = truth[t]
    for n in ('ball', 'spinner', 'drone'):
        gm_ = gltf_world(n, t)
        dp = (gm_.translation - d[n].translation).length
        da = math.degrees(gm_.to_quaternion().rotation_difference(d[n].to_quaternion()).angle)
        check(f'{n} at t = {t:g}: the GLB has it where Blender does', dp < 2e-3 and da < 0.5, f'{dp * 1000:.2f} mm, {da:.2f} deg')
    # the node that holds the camera (the exporter may hang it under a corrected child): its -Z is the view in glTF
    ci = g.node_by_name('cam_film')
    if 'camera' not in g.json['nodes'][ci]:
        ci = next(c for c in g.json['nodes'][ci].get('children', []) if 'camera' in g.json['nodes'][c])
    mg = Matrix(G.world_matrices(g, t)[ci])
    fx, fy, fz = mg.to_3x3() @ Vector((0, 0, -1))
    fw_g = Vector((fx, -fz, fy))
    gx, gy, gz = mg.translation
    dp = (Vector((gx, -gz, gy)) - d['cam_film'].translation).length
    fw_b = -(d['cam_film'].to_3x3() @ Vector((0, 0, 1)))
    check(f'cam_film at t = {t:g} (keys + Track To): position and aim', dp < 2e-3 and math.degrees(fw_g.angle(fw_b)) < 0.5,
          f'{dp * 1000:.2f} mm, {math.degrees(fw_g.angle(fw_b)):.2f} deg')
    w = G.morph_weights(g, 'blob', t)
    check(f'blob morph weight at t = {t:g}', w and abs(w[0] - d['puff']) < 2e-3, f'{w[:1]} vs {d["puff"]:.3f}')
    for jn, want in (('hand', d['hand']), ('head', d['head'])):
        bone = hand if jn == 'hand' else head
        try:
            got = Vector(G.node_position(g, bone, t=t, blender_axes=True))
            err = (got - want).length
        except KeyError:
            err = 1e9
        check(f'robot {jn} joint at t = {t:g} (VRMA through NLA, sampled)', err < 0.01, f'{err * 1000:.1f} mm')
    if d['her_head']:
        bone, want = d['her_head']
        try:
            err = (Vector(G.node_position(g, bone, t=t, blender_axes=True)) - want).length
        except KeyError:
            err = 1e9
        check(f"aletheia's head joint at t = {t:g}", err < 0.01, f'{bone}: {err * 1000:.1f} mm')
    fp_ = G.morphed_positions(g, 'flag', t)
    worst = 0.0
    for v in d['flag'][::7]:
        worst = max(worst, min((Vector(p) - v).length for p in fp_))
    check(f'flag surface at t = {t:g} (Geometry Nodes wave -> morph targets)', worst < 0.012, f'max {worst * 1000:.1f} mm')
    worst, n_ = 0.0, 0
    for k, (_pid, want) in enumerate(d['orbiters']):
        try:
            got = Vector(G.node_position(g, f'orbiters_{k:03d}', t=t, blender_axes=True))
        except KeyError:
            continue
        worst = max(worst, (got - want).length)
        n_ += 1
    check(f'orbiters at t = {t:g} (instances -> keyed objects)', n_ == 8 and worst < 2e-3, f'{n_} found, {worst * 1000:.2f} mm')

check('rocks: a still scatter -> one EXT_mesh_gpu_instancing node', s_['gpu_instanced_nodes'] >= 1
      and 'EXT_mesh_gpu_instancing' in s_['extensions_used'], s_['gpu_instanced_nodes'])
by_name = {n.get('name'): n for n in g.json['nodes']}
check('blobby: the metaball became a mesh in the GLB (the exporter skips metaballs)',
      rep.get('metaballs') == ['blobby_mesh'] and 'mesh' in by_name.get('blobby_mesh', {}), rep.get('metaballs'))
check("sign_text: a text object is a mesh in the GLB (the exporter's own conversion)", 'mesh' in by_name.get('sign_text', {}),
      sorted(by_name.get('sign_text', {}).keys()))
check('smoke_volume: a volume is named in the warnings (not glTF)', any(w.startswith('smoke_volume: a volume')
                                                                        for w in man['warnings']),
      [w for w in man['warnings'] if 'volume' in w])
mats = {m['name']: m for m in s_['materials']}
if not NO_RENDER:
    gmat = next((m for n, m in mats.items() if n and n.startswith('gltf_ground')), None)
    check('ground: the procedural material baked to base colour + ORM + normal', gmat and gmat['baseColorTexture']
          and gmat['metallicRoughnessTexture'] and gmat['normalTexture'], gmat)
    fmat = next((m for n, m in mats.items() if n and n.startswith('gltf_flag')), None)
    check('flag: its procedural stripes baked (on the morph-target mesh)', fmat and fmat['baseColorTexture'], fmat)
mt = rep.get('mtoon', {})
conv = [m for n, m in mats.items() if n and n in set(mt.values())]
check("aletheia's MToon materials converted (base colour textures kept), none baked",
      len(mt) >= 3 and all(m['baseColorTexture'] or m['unlit'] for m in conv)
      and not any(k.startswith('aletheia') or 'Body' in k for k in rep['materials'].get('baked', {})),
      f'{len(mt)} converted: {sorted(mt)[:6]}')
nm = mats.get('neon')
check('neon: kept as is (exportable), emissive strength carried', nm and (nm['emissiveStrength'] or 0) >= 1.9, nm)
lights = {li['name']: li for li in s_['lights']}
check('sun: a directional light, W/m2 as lux (COMPAT), temperature in its colour',
      'sun' in lights and abs(lights['sun']['intensity'] - 3.0) < 1e-3 and lights['sun']['color'][2] < 1.0,
      lights.get('sun'))
check('lamp: a point light, W / 4 pi as candela', 'lamp' in lights and abs(lights['lamp']['intensity'] - 60 / (4 * math.pi)) < 1e-3,
      lights.get('lamp'))
sp_ = lights.get('spot', {})
check('spot: outer cone half of spot_size, blend inside', sp_ and abs(sp_['spot']['outerConeAngle'] - math.radians(20)) < 1e-4,
      sp_.get('spot'))
rect = {r['name']: r for r in man['rect_lights']}
check('key: the area light -> a RectAreaLight, radiance P / (pi A)', 'key' in rect
      and abs(rect['key']['intensity'] - 250 / math.pi) < 1e-3 and abs(rect['key']['width'] - 1.0) < 1e-6, rect.get('key'))
with open(os.path.join(vr, 'choreo.json')) as f:
    ch = json.load(f)
pr = ch['props']
for t in TIMES:
    i = int(round(t * FPS))
    check(f'lamp track at t = {t:g}: energy / 4 pi', abs(pr['lights']['lamp']['intensity'][i] - truth[t]['lamp'] / (4 * math.pi)) < 1e-3,
          pr['lights']['lamp']['intensity'][i])
    check(f'neon emission track at t = {t:g}', abs(pr['emission']['neon']['strength'][i] - truth[t]['neon']) < 1e-3,
          pr['emission']['neon']['strength'][i])
vis = pr['visible'].get('popper')
check('popper: hidden before 2 s, shown from 2 s; exported (the page hides it in time)',
      vis and vis['v'][0] == 0 and vis['v'][int(2.0 * FPS)] == 1 and 'popper' in [n.get('name') for n in g.json['nodes']],
      vis and (vis['v'][0], vis['v'][int(2.0 * FPS)]))
check('markers: cue_pop at 2 s', ch['markers'] and ch['markers'][0]['name'] == 'cue_pop' and abs(ch['markers'][0]['t'] - 2.0) < 1e-6,
      ch['markers'])
for t in TIMES:                                    # the guide's recipe: world tracks in three's axes, every 2 frames
    row = next((r for r in ch['track']['drone'] if abs(r[0] - t) < 1e-4), None)
    want = truth[t]['drone'].translation
    check(f'choreo track: the drone at t = {t:g}, three axes (x, z, -y)', row is not None
          and max(abs(row[1] - want.x), abs(row[2] - want.z), abs(row[3] + want.y)) < 1e-4, row and row[:4])
# the world image: its brightest pixel looks toward the sun
if not NO_RENDER:
    img = bpy.data.images.load(os.path.join(vr, 'world.hdr'), check_existing=False)
    import numpy as np                                   # noqa: E402
    a = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(a)
    a = a.reshape(img.size[1], img.size[0], 4)
    lum = a[..., :3].sum(-1)
    yy, xx = np.unravel_index(int(lum.argmax()), lum.shape)
    d_ = Vector(W.equirect_direction((xx + 0.5) / img.size[0], (yy + 0.5) / img.size[1]))
    check("world.hdr: the sun's glow sits where three's equirect looks toward the sun",
          math.degrees(d_.angle(sun_dir)) < 3.0, f'{math.degrees(d_.angle(sun_dir)):.2f} deg off')
check('Quest budgets', all(v in ('ok', 'heavy') for v in s_['quest'].values()),
      f"{s_['triangles']} triangles, {s_['draws']} draws, {s_['texture_mb_gpu']} MB textures: {s_['quest']}")
with open(os.path.join(OUT, 'export_report.json'), 'w') as f:
    json.dump(man, f, indent=1, default=str)
n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
print(f'[check] {len(RESULTS) - n_fail} passed, {n_fail} failed', flush=True)
sys.exit(1 if n_fail else 0)
