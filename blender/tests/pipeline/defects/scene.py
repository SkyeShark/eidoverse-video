"""Planted defects (test T3): every one must be NAMED in the digest. run_tests.py checks the list below against
<out>/defects_probe.audit.json. Not a film: grey boxes on a floor, so the defects are the only thing in it.

    defect                                  the record that must warn
    a wheel spun about an off-axis origin   motion.envelope (wrong pivot)
    a crate keyed down through the floor    motion.envelope (below ground)
    a box that jumps 6 m in one frame       motion.envelope (teleport)
    a ball whose scale grows x3             motion.envelope (scale drift)
    a bus driven along its short side       motion.sideways
    a camera dollying in and out at 6 Hz    motion.camera
    a humanoid rig never posed              motion.rig_pose
    an image file that does not exist       preflight.images
    the Standard view transform             preflight.colour
    no world                                preflight.world
    a declared asset never read             assets.reads
    one flag covering two bodies            coverage.no_clipping_check (group blanket)
    a sun dimmed per frame without a key    build.unkeyed (the film would show its last value throughout)
    a global disable                        motion.locomotion SKIPPED (declared exception)
"""
import math

import bpy

_no_locomotion_check = True          # a scene-wide flag, read from the script's namespace


def box(name, size, location, colour=(0.5, 0.5, 0.5, 1)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    ob = bpy.context.object
    ob.name = name
    ob.scale = size
    m = bpy.data.materials.new(name)
    m.diffuse_color = colour
    m.use_nodes = True
    m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = colour
    ob.data.materials.append(m)
    return ob


def setup(ctx):
    scene = ctx.scene
    scene.view_settings.view_transform = 'Standard'
    floor = box('floor', (20, 20, 0.02), (0, 0, -0.01))

    # a wheel whose origin is 0.8 m off its centre, spun about that origin
    wheel = box('wheel', (0.6, 0.1, 0.6), (-3, 2, 1.2))
    wheel.data.transform(__import__('mathutils').Matrix.Translation((0.8 / 0.6, 0, 0)))
    for f, a in ((ctx.frame_start, 0.0), (ctx.frame_end, 4 * math.pi)):
        wheel.rotation_euler.y = a
        ctx.key(wheel, 'rotation_euler', frame=f)

    crate = box('crate', (0.5, 0.5, 0.5), (0, 3, 0.25))
    for f, z in ((ctx.frame_start, 0.25), (ctx.frame_end, -1.0)):
        crate.location.z = z
        ctx.key(crate, 'location', frame=f)

    jumper = box('jumper', (0.4, 0.4, 0.4), (2, 1, 0.2))
    mid = ctx.frame_at(2.0)
    for f, x in ((ctx.frame_start, 2.0), (mid, 2.4), (mid + 1, 8.4), (ctx.frame_end, 8.8)):
        jumper.location.x = x
        ctx.key(jumper, 'location', frame=f)

    ball = box('ball', (0.3, 0.3, 0.3), (-1, 0, 0.15))
    for f, s in ((ctx.frame_start, 0.3), (ctx.frame_end, 0.9)):
        ball.scale = (s, s, s)
        ctx.key(ball, 'scale', frame=f)

    bus = box('bus', (4.0, 1.2, 1.5), (-4, -3, 0.75))          # long along X, driven along Y
    for f, y in ((ctx.frame_start, -6.0), (ctx.frame_end, 2.0)):
        bus.location.y = y
        ctx.key(bus, 'location', frame=f)

    pair_a = box('pair_a', (0.3, 0.3, 0.3), (3, -1, 0.15))
    pair_b = box('pair_b', (0.3, 0.3, 0.3), (3.6, -1, 0.15))
    group = bpy.data.objects.new('pair', None)
    scene.collection.objects.link(group)
    pair_a.parent = pair_b.parent = group
    ctx.flag(group, 'no_clipping_check')

    arm = bpy.data.armatures.new('rig')
    rig = bpy.data.objects.new('statue_rig', arm)
    scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    names = ['hips', 'spine', 'chest', 'neck', 'head'] + [f'{s}_{p}' for s in ('l', 'r')
                                                          for p in ('shoulder', 'arm', 'forearm', 'hand', 'thigh', 'shin')]
    for i, n in enumerate(names):
        b = arm.edit_bones.new(n)
        b.head, b.tail = (0.1 * (i % 4), 0, 0.5 + 0.1 * i), (0.1 * (i % 4), 0, 0.6 + 0.1 * i)
    bpy.ops.object.mode_set(mode='OBJECT')
    rig.location = (1, -2, 0)

    m = bpy.data.materials['crate']
    tex = m.node_tree.nodes.new('ShaderNodeTexImage')
    img = bpy.data.images.new('missing_scan', 4, 4)
    img.source = 'FILE'
    img.filepath = '//this_file_does_not_exist.png'
    tex.image = img

    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    scene.collection.objects.link(cam)
    scene.camera = cam
    light = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    light.rotation_euler = (0.7, 0.2, 0.5)
    scene.collection.objects.link(light)


def render_frame(ctx, t, i):
    cam = ctx.scene.camera
    cam.location = (0, -12 + 0.6 * math.sin(2 * math.pi * 6 * t), 4)
    cam.rotation_euler = (math.radians(75), 0, 0)
    ctx.key(cam, 'location')
    ctx.key(cam, 'rotation_euler')
    # the literal port of a WebGPU renderFrame's `sun.intensity = ...`: set, never keyed
    bpy.data.lights['sun'].energy = 1.0 + 2.0 * t
