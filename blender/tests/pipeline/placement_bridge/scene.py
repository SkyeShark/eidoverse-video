"""Test T8: the runner runs the placement family's audits when a scene uses that family. A crate seated with place_on,
and a box left hanging a metre above the floor: the digest must name the floating box under placement.*.
"""
import bpy

from eidoblend.placement import place_on


def box(name, size, location):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    ob = bpy.context.object
    ob.name = name
    ob.scale = size
    return ob


def setup(ctx):
    scene = ctx.scene
    floor = box('floor', (8, 8, 0.1), (0, 0, -0.05))
    crate = box('crate', (0.5, 0.5, 0.5), (0, 0, 2.0))
    place_on(crate, floor)
    box('floater_box', (0.4, 0.4, 0.4), (1.2, 0.5, 1.2))
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.location, cam.rotation_euler = (0, -6, 2.0), (1.35, 0, 0)
    scene.collection.objects.link(cam)
    scene.camera = cam
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    scene.collection.objects.link(sun)
