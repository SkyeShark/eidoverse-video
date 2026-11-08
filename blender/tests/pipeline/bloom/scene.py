"""Test T12: the config's "render": {"bloom": ...} option. A small hot emitter in the dark: with bloom the light
spills into a halo around it; without, the dark stays dark. run_tests.py renders both configs and compares the
ring around the emitter.
"""
import bpy


def setup(ctx):
    scene = ctx.scene
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, location=(0, 0, 0))
    ball = bpy.context.object
    m = bpy.data.materials.new('hot')
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (1, 0.6, 0.3, 1)
    b.inputs['Emission Color'].default_value = (1, 0.6, 0.3, 1)
    b.inputs['Emission Strength'].default_value = 60.0
    ball.data.materials.append(m)
    w = bpy.data.worlds.new('night')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.0, 0.0, 0.0, 1)
    scene.world = w
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.location, cam.rotation_euler = (0, -3, 0), (1.5708, 0, 0)
    scene.collection.objects.link(cam)
    scene.camera = cam
