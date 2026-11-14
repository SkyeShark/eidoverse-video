"""The particles port's probe: the corner set's campfire (eidoverse/sets/corner.js), its four makeParticles
layers verbatim (two 'fire' layers on flame_05 / flame_06, 'embers' on spark_01, 'smoke' on smoke_04), over
a small pit of logs and stones built here (the set's camp_fire.glb is not in the repo), lit by a fire light.

    bash run_blender.sh blender/tests/fx/test_particles_campfire.py [-- frames=12,30,60]
    (a GPU job: 4 GB VRAM, 8 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

No bake: the particles are a Geometry Nodes function of scene time. Writes out/particles_campfire_f####.png.
"""

import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.fx import particles as fxp          # noqa: E402
from eidoblend.fx._util import color, from_three    # noqa: E402

args = dict(a.split('=', 1) for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if '=' in a)
FRAMES = [int(x) for x in args.get('frames', '12,30,60').split(',')]
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 960, 540
sc.render.fps = 30
sc.frame_start, sc.frame_end = 1, 90
sc.eevee.taa_render_samples = 16
sc.view_settings.view_transform = 'AgX'
sc.view_settings.exposure = 0.0
world = bpy.data.worlds.new('night')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (*color(0x0a0d18), 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.6
sc.world = world

# ground, stones, logs
bpy.ops.mesh.primitive_plane_add(size=12)
ground = bpy.context.active_object
gm = bpy.data.materials.new('ground')
gm.use_nodes = True
gb = gm.node_tree.nodes['Principled BSDF']
gb.inputs['Base Color'].default_value = (*color('#3b3329'), 1)
gb.inputs['Roughness'].default_value = 0.95
ground.data.materials.append(gm)
stone = bpy.data.materials.new('stone')
stone.use_nodes = True
sb = stone.node_tree.nodes['Principled BSDF']
sb.inputs['Base Color'].default_value = (*color('#6b6660'), 1)
sb.inputs['Roughness'].default_value = 0.85
for k in range(9):
    a = k / 9 * 2 * math.pi
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.11, location=(math.cos(a) * 0.42, math.sin(a) * 0.42, 0.05))
    s = bpy.context.active_object
    s.scale = (1.0, 0.8, 0.6)
    s.data.materials.append(stone)
log = bpy.data.materials.new('charred_log')
log.use_nodes = True
lnt = log.node_tree
lb = lnt.nodes['Principled BSDF']
lb.inputs['Base Color'].default_value = (*color('#1a1410'), 1)        # char: near-black, dry, rough
lb.inputs['Roughness'].default_value = 0.95
lb.inputs['Emission Color'].default_value = (*color('#ff5a1a'), 1)
# embers only in the cracks: a fine noise thresholded to thin glowing seams, not a glowing log
ln = lnt.nodes.new('ShaderNodeTexNoise')
ln.inputs['Scale'].default_value = 24.0
ln.inputs['Detail'].default_value = 6.0
ln.inputs['Roughness'].default_value = 0.6
lm = lnt.nodes.new('ShaderNodeMapRange')
lm.interpolation_type = 'SMOOTHSTEP'
lm.inputs['From Min'].default_value = 0.6
lm.inputs['From Max'].default_value = 0.72
lm.inputs['To Max'].default_value = 4.0
lnt.links.new(ln.outputs['Fac'], lm.inputs['Value'])
lnt.links.new(lm.outputs['Result'], lb.inputs['Emission Strength'])
for k in range(4):
    a = k / 4 * 2 * math.pi + 0.3
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.045, depth=0.6,
                                        location=(math.cos(a) * 0.1, math.sin(a) * 0.1, 0.1),
                                        rotation=(0.0, math.radians(70), a))
    bpy.context.active_object.data.materials.append(log)

# the corner set's four layers (three origins -> Blender; area [x, y, z] -> Blender extents)
def P(**kw):
    o = kw.pop('origin3')
    return fxp.make_particles(origin=tuple(from_three(o)), **kw)


P(preset='fire', map='flame_05', origin3=(0, 0.10, 0), count=120, size=0.46, area=(0.18, 0.18, 0.05), name='campfire_flames_a')
P(preset='fire', map='flame_06', origin3=(0.04, 0.12, -0.03), count=70, size=0.34, area=(0.12, 0.12, 0.05), name='campfire_flames_b', seed=2)
P(preset='embers', map='spark_01', origin3=(0, 0.35, 0), count=90, size=0.035, area=0.25, name='campfire_embers', seed=3)
P(preset='smoke', map='smoke_04', origin3=(0, 1.1, 0), count=26, size=0.9, opacity=0.10, color=0x3a3a40,
  name='campfire_smoke', seed=4)

# the set's fire light: PointLight(0xff8a3c, 7, 14, 2) at (0, 0.7, 0) -> 4*pi*7 W, flickering
ld = bpy.data.lights.new('fire_light', 'POINT')
ld.color = color(0xff8a3c)
ld.shadow_soft_size = 0.15
fl = bpy.data.objects.new('fire_light', ld)
sc.collection.objects.link(fl)
fl.location = tuple(from_three((0, 0.7, 0)))
from eidoblend.fx._noise import ImprovedNoise    # noqa: E402
nz = ImprovedNoise()
for f in range(1, 91):
    t = f / 30
    ld.energy = 4 * math.pi * 7.0 * (0.85 + 0.15 * nz.noise(0, t * 6.0, 0.5))
    ld.keyframe_insert('energy', frame=f)

cd = bpy.data.cameras.new('cam')
cd.lens = 40
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
cam.location = (2.6, -2.4, 1.15)
tgt = bpy.data.objects.new('tgt', None)
sc.collection.objects.link(tgt)
tgt.location = (0, 0, 0.55)
c = cam.constraints.new('TRACK_TO')
c.target = tgt
c.track_axis = 'TRACK_NEGATIVE_Z'
c.up_axis = 'UP_Y'
sc.camera = cam

for f in FRAMES:
    sc.frame_set(f)
    sc.render.filepath = os.path.join(OUT, f'particles_campfire_f{f:04d}.png')
    bpy.ops.render.render(write_still=True)
    print('[test_particles] wrote', sc.render.filepath)
print('[test_particles] DONE')
