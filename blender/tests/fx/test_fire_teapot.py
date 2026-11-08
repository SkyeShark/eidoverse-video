"""The fire port's first probe: three.js webgpu_volume_fire's own scene (the engine's work/firetest), in EEVEE.

Teapot TeapotGeometry(0.8, 28) burning from its raw vertex buffer, 12 x 24 x 12 m domain at 100 x 200 x 100,
the example's spot key light, 80 x 80 floor (#111115, roughness .8) at 0.8 m, black world, camera (14, 5.5, 4.4)
looking at (0, 3.6, 0) in three's axes. Bakes on the GPU, renders a few stills at 960x540.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 \
        bash run_blender.sh <worktree>/blender/tests/fx/test_fire_teapot.py [-- frames=1,24,48 fps=24 end=48]

More args: preset=raw (the engine's own numbers, look=None), match=0|aces|aces_compose (display_match),
path=, emis=, spread=, endcolor=rrggbb, smoke=, clarity=, lights=, exposure=, look=AgX_-_Punchy, tag=_name.
The teapot spins through a driver on `frame`, so the warmup's pre-roll spins it too, as the engine's did.
Writes blender/tests/fx/out/fire_teapot<tag>_f####.png and the .vdb cache under out/fire_cache/.
Reference: E:/eidoverse-video-desktop-work-folder/firetest/fire.mp4 (WebGPU, 1600x900).
"""

import math
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
sys.path.insert(0, HERE)

from eidoblend.fx import fire as fxfire          # noqa: E402
from eidoblend.fx._util import color, from_three  # noqa: E402
import _teapot                                     # noqa: E402

args = dict(a.split('=', 1) for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if '=' in a)
FPS = int(args.get('fps', 24))
END = int(args.get('end', 48))
FRAMES = [int(x) for x in args.get('frames', '1,24,48').split(',')]
RES = [int(x) for x in args.get('res', '960x540').split('x')]
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)

# ---- a clean scene ----------------------------------------------------------------------------------
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = RES
sc.render.resolution_percentage = 100
sc.render.fps = FPS
sc.frame_start, sc.frame_end = 1, END
sc.eevee.taa_render_samples = 16
sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = 'None'
# the example renders ACES at exposure 2, which three applies as x 2/0.6 before the curve: +1.74 stops
sc.view_settings.exposure = float(args.get('exposure', 1.74))
if 'look' in args:
    sc.view_settings.look = args['look'].replace('_', ' ')         # e.g. look=AgX_-_Punchy
TAG = args.get('tag', '')
sc.render.film_transparent = False
world = bpy.data.worlds.new('black')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0, 0, 0, 1)
sc.world = world

# ---- floor, teapot, key light, camera (the example's, three -> Blender axes) -------------------------
VOL_Y = 12.0
floor_z = 0.8                                     # -VOLUME_Y/2 + 0.4 + VOLUME_Y/2 + 0.4
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, floor_z))
floor = bpy.context.active_object
fm = bpy.data.materials.new('floor')
fm.use_nodes = True
fb = fm.node_tree.nodes['Principled BSDF']
fb.inputs['Base Color'].default_value = (*color(0x111115), 1)
fb.inputs['Roughness'].default_value = 0.8
floor.data.materials.append(fm)

teapot, min_y = _teapot.teapot_object('teapot', 0.8, 28)
teapot.location = (0, 0, floor_z - min_y)
tm = bpy.data.materials.new('teapot')
tm.use_nodes = True
tb = tm.node_tree.nodes['Principled BSDF']
tb.inputs['Base Color'].default_value = (0, 0, 0, 1)
tb.inputs['Metallic'].default_value = 1.0
tb.inputs['Roughness'].default_value = 1.0
teapot.data.materials.append(tm)
# the example spins the teapot with simulation time: rotation.y = simTime * 0.25 (simTime runs 1.2x). A driver
# on `frame` gives that spin at every frame the bake asks for, the warmup's pre-roll frames included (frame f
# ends at simTime = warmup + f / fps * 1.2 with frame_start 1)
warm, speed = 4.0, 1.2
drv = teapot.driver_add('rotation_euler', 2).driver
drv.type = 'SCRIPTED'
drv.expression = f'({warm} + frame / {FPS} * {speed}) * 0.25'

key_pos3 = (-3 * (12 / 8), 6 * (12 / 8) + 12 / 2 + 0.4, 3 * (24 / 8))
kd = bpy.data.lights.new('key', 'SPOT')
kd.energy = 4 * math.pi * 1000.0                  # SpotLight(0xffffff, 1000) candela -> watts
kd.spot_size = 2 * math.pi / 5                    # angle PI/5 is the half-angle
kd.spot_blend = 1.0                               # penumbra 1
kd.shadow_soft_size = 0.25
kd.use_shadow = True
key = bpy.data.objects.new('key', kd)
sc.collection.objects.link(key)
key.location = tuple(from_three(key_pos3))
tgt = bpy.data.objects.new('key_target', None)
sc.collection.objects.link(tgt)
tgt.location = tuple(from_three((1, 0, 0)))
con = key.constraints.new('TRACK_TO')
con.target = tgt
con.track_axis = 'TRACK_NEGATIVE_Z'
con.up_axis = 'UP_Y'

cd = bpy.data.cameras.new('cam')
cd.sensor_fit = 'VERTICAL'
cd.angle = math.radians(60)
cd.clip_start, cd.clip_end = 0.1, 100
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
cam.location = tuple(from_three((14, 5.5, 4.4)))
look = bpy.data.objects.new('look', None)
sc.collection.objects.link(look)
look.location = tuple(from_three((0, 3.6, 0)))
cc = cam.constraints.new('TRACK_TO')
cc.target = look
cc.track_axis = 'TRACK_NEGATIVE_Z'
cc.up_axis = 'UP_Y'
sc.camera = cam
bpy.context.view_layer.update()

# ---- the fire ----------------------------------------------------------------------------------------
opts = {k: float(args[a]) for k, a in (('smoke_density', 'smoke'), ('emission_scale', 'emis'),
                                        ('light_scale', 'lights'), ('flame_clarity', 'clarity'),
                                        ('fire_glow_spread', 'spread'), ('display_path', 'path')) if a in args}
if 'endcolor' in args:
    opts['fire_end_color'] = '#' + args['endcolor']
if args.get('match', '1') == '0':
    opts['display_match'] = None                  # the raw ramp under AgX (match=0)
elif args.get('match') in ('aces', 'aces_compose'):
    opts['display_match'] = args['match']
# preset=raw: the engine's own numbers (look=None) instead of the engine's look under AgX (fire.ENGINE_LOOK)
fire = fxfire.create_volume_fire(teapot, key_light=key, cache_dir=os.path.join(OUT, 'fire_cache'),
                                 look=None if args.get('preset') == 'raw' else 'engine', **opts)
fire.make_lava_emissive(tm)
t0 = time.time()
fire.bake(1, END)
print(f'[test_fire] bake {time.time() - t0:.1f} s; sim time at frame {END}: {fire.sim_time:.3f} s'
      f' (warmup {fire.params["warmup_seconds"]} + {END} / {FPS} x {fire.params["sim_speed"]}'
      f' = {fire.params["warmup_seconds"] + END / FPS * fire.params["sim_speed"]:.3f})')
fxfire.configure_eevee_for_fire(sc, fire, cam, tile=args.get('tile', '1'), samples=int(args.get('vsamples', 128)))
print(f'[test_fire] volume range {sc.eevee.volumetric_start:.2f} .. {sc.eevee.volumetric_end:.2f} m')
fxfire.create_fire_compose(sc, fire)

BLEND = os.path.join(OUT, 'fire_teapot.blend')
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
# render from the saved file, as a film would (bake once, render many): a fresh load reads the .vdb sequence
bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene
for f in FRAMES:
    sc.frame_set(f)
    sc.render.filepath = os.path.join(OUT, f'fire_teapot{TAG}_f{f:04d}.png')
    t1 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f'[test_fire] frame {f} rendered in {time.time() - t1:.1f} s -> {sc.render.filepath}')
print('[test_fire] DONE')
