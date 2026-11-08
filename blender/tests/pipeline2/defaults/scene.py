"""What every build gets without asking (run_tests.py U5, a build: nothing renders).

The script never imports eidoblend.placement, places a crate by hand 0.8 m above the floor (the classic mid-air prop)
and has a coffee mug and a 16 s duration but no showpiece. The runner must still run the placement audits and name
the crate (they run on every build, as the WebGPU runner's did), give the palette's showpiece nudge naming the
liquid, and record the auto-enhance stack it applied.

    python eido_blender.py build blender/tests/pipeline2/defaults/scene.json
"""
import bpy
from mathutils import Vector


def box(name, size, loc):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.scale = size
    return ob


def setup(ctx):
    scene = ctx.scene
    box('floor', (6, 6, 0.1), (0, 0, -0.05))
    box('crate_by_hand', (0.5, 0.5, 0.5), (0.0, 0.4, 1.05))      # 0.8 m of air under it
    bpy.ops.mesh.primitive_cylinder_add(radius=0.045, depth=0.1, location=(0.8, 0.0, 0.05))
    bpy.context.object.name = 'coffee_mug'
    key = bpy.data.objects.new('key', bpy.data.lights.new('key', 'SUN'))
    key.rotation_euler = (0.7, 0.2, 0.5)
    scene.collection.objects.link(key)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.location = (2.5, -3.5, 1.8)
    cam.rotation_euler = (Vector((0, 0.3, 0.5)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(cam)
    scene.camera = cam
