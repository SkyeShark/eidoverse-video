"""blender/tests/dlss5nr/make_film.py (Blender): the small two-shot film test_render_motion.py checks the motion tool on.

    bash run_blender.sh blender/tests/dlss5nr/make_film.py --out <dir> [--no-render]

16 frames at 320 x 180, 24 fps, frame_start 1: a checkered floor, a cube sliding 3 m along +x and a sphere rising, under
a sun. Shot 1 (frames 1-8) is a fixed camera; a camera marker at frame 9 cuts to shot 2, a camera dollying sideways.
Every key is LINEAR. Saves <out>/film.blend, and (unless --no-render) renders its beauty frames, 8 samples, to
<out>/beauty/####.png.
"""
import math
import os
import sys

import bpy

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.abspath(argv[argv.index('--out') + 1])
os.makedirs(OUT, exist_ok=True)


def keyed(ob, path, frames_values):
    for f, v in frames_values:
        setattr(ob, path, v)
        ob.keyframe_insert(path, frame=f)
    ad = ob.animation_data
    if ad and ad.action:
        # Blender 5.x keeps keys in layered actions: reach every F-curve through the action's channelbags
        curves = []
        if hasattr(ad.action, 'layers'):
            for layer in ad.action.layers:
                for strip in layer.strips:
                    for bag in strip.channelbags:
                        curves.extend(bag.fcurves)
        elif hasattr(ad.action, 'fcurves'):
            curves = list(ad.action.fcurves)
        for fc in curves:
            for k in fc.keyframe_points:
                k.interpolation = 'LINEAR'


bpy.ops.wm.read_homefile(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 320, 180, 100
sc.render.fps = 24
sc.frame_start, sc.frame_end = 1, 16
sc.eevee.taa_render_samples = 8
sc.view_settings.view_transform = 'AgX'
sc.render.image_settings.file_format = 'PNG'

world = bpy.data.worlds.new('grey')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.25, 0.27, 0.3, 1)
sc.world = world

floor_mat = bpy.data.materials.new('checker')
floor_mat.use_nodes = True
nt = floor_mat.node_tree
bsdf = nt.nodes['Principled BSDF']
checker = nt.nodes.new('ShaderNodeTexChecker')
checker.inputs['Scale'].default_value = 24.0
checker.inputs['Color1'].default_value = (0.8, 0.75, 0.6, 1)
checker.inputs['Color2'].default_value = (0.1, 0.12, 0.15, 1)
nt.links.new(checker.outputs['Color'], bsdf.inputs['Base Color'])
bpy.ops.mesh.primitive_plane_add(size=16)
floor = bpy.context.object
floor.data.materials.append(floor_mat)

cube_mat = bpy.data.materials.new('cube')
cube_mat.use_nodes = True
cn = cube_mat.node_tree
noise = cn.nodes.new('ShaderNodeTexNoise')
noise.inputs['Scale'].default_value = 6.0
ramp = cn.nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].color = (0.6, 0.1, 0.05, 1)
ramp.color_ramp.elements[1].color = (1.0, 0.8, 0.3, 1)
cn.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
cn.links.new(ramp.outputs['Color'], cn.nodes['Principled BSDF'].inputs['Base Color'])
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-1.5, 0.0, 0.5))
cube = bpy.context.object
cube.name = 'mover_cube'
cube.data.materials.append(cube_mat)
keyed(cube, 'location', [(1, (-1.5, 0.0, 0.5)), (16, (1.5, 0.0, 0.5))])
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, location=(1.2, 1.2, 0.4))
sphere = bpy.context.object
sphere.name = 'mover_sphere'
sphere.data.materials.append(cube_mat)
keyed(sphere, 'location', [(1, (1.2, 1.2, 0.4)), (16, (1.2, 1.2, 1.4))])

sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
sun.data.energy = 4.0
sun.rotation_euler = (math.radians(50), 0.0, math.radians(30))
sc.collection.objects.link(sun)


def camera(name, location, rotation):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    cam.location, cam.rotation_euler = location, rotation
    cam.data.lens = 35
    sc.collection.objects.link(cam)
    return cam


cam_a = camera('cam_fixed', (0.0, -7.0, 3.0), (math.radians(68), 0.0, 0.0))
cam_b = camera('cam_dolly', (-1.0, -5.0, 2.2), (math.radians(72), 0.0, math.radians(-12)))
keyed(cam_b, 'location', [(9, (-1.0, -5.0, 2.2)), (16, (1.2, -5.0, 2.2))])
sc.camera = cam_a
for f, cam in ((1, cam_a), (9, cam_b)):
    sc.timeline_markers.new(f'cut_{cam.name}', frame=f).camera = cam

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'film.blend'))
print(f'[make_film] saved {os.path.join(OUT, "film.blend")}', flush=True)
if '--no-render' not in argv:
    beauty = os.path.join(OUT, 'beauty')
    os.makedirs(beauty, exist_ok=True)
    sc.render.filepath = os.path.join(beauty, '')
    bpy.ops.render.render(animation=True)
    print(f'[make_film] rendered {len([n for n in os.listdir(beauty) if n.endswith(".png")])} frames to {beauty}',
          flush=True)
