"""tests/xr/_inputs.py: the films the xr tests take from the other families. Where the toolkit makes one in seconds the
test builds its own, in the open (empty) file; a film that needs another family's bake or render is read from that
family's test output when it is there, and skipped with the reason when it is not:

    robot_walk()     my robot body (claude_robot.vrm, its 4096 px maps) walking 7 m across a level floor with the
                     characters family's walk (load_clip 'walk', walk_path), two suns, a plain world, no camera
    meadow()         a meadow: vegetation.md's MEADOW recipe (fine grass under white and orange daisies, the wind on)
                     under a sun
    BUILT            the other families' films, by name: (their .blend under blender/tests/, the test that builds it)
    built(name)      (path, None) when that .blend is there, else (None, the reason it is not)
"""
import math
import os

import bpy

TESTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

BUILT = {
    'example': ('pipeline/out/example.blend', 'blender/tests/pipeline/run_tests.py (the example scene through '
                                              'eido_blender.py)'),
    'crows': ('pipeline/out/crows.blend', 'blender/tests/pipeline/run_tests.py (the crows scene through '
                                          'eido_blender.py)'),
    'fire_teapot': ('fx/out/fire_teapot.blend', 'blender/tests/fx/test_fire_teapot.py (a fire bake on the GPU)'),
    'stage': ('look/out/stage/stage.blend', 'blender/tests/look/test_stage.py --stage build'),
}


def built(name):
    rel, by = BUILT[name]
    path = os.path.join(TESTS, rel)
    if os.path.exists(path):
        return path, None
    return None, f'{rel} is not built in this checkout (it is the output of {by}); run that first to check it here'


def _empty(fps=24):
    bpy.ops.wm.read_homefile(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = fps, 1.0
    w = bpy.data.worlds.new('plain')
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (0.05, 0.055, 0.065, 1.0)
    bg.inputs['Strength'].default_value = 1.0
    sc.world = w
    return sc


def _sun(name, direction, energy, colour=(1.0, 1.0, 1.0)):
    """a sun shining along `direction`"""
    from mathutils import Vector
    ld = bpy.data.lights.new(name, 'SUN')
    ld.energy, ld.color, ld.angle = energy, colour, math.radians(3.0)
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = Vector(direction).normalized().to_track_quat('-Z', 'Y')
    return ob


def _floor(size_x, size_y, centre=(0.0, 0.0)):
    me = bpy.data.meshes.new('floor')
    x0, x1 = centre[0] - size_x / 2, centre[0] + size_x / 2
    y0, y1 = centre[1] - size_y / 2, centre[1] + size_y / 2
    me.from_pydata([(x0, y0, 0.0), (x1, y0, 0.0), (x1, y1, 0.0), (x0, y1, 0.0)], [], [(0, 1, 2, 3)])
    mat = bpy.data.materials.new('floor')
    mat.use_nodes = True
    b = mat.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.18, 0.18, 0.19, 1.0)
    b.inputs['Roughness'].default_value = 0.8
    me.materials.append(mat)
    ob = bpy.data.objects.new('floor', me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def robot_walk(log=print):
    """my robot body walking 7 m across a level floor (the characters family's walk), two suns, no camera"""
    from eidoblend.characters import Ground, load_clip, load_vrm, walk_path
    sc = _empty(24)
    _sun('key', (2.2, -3.0, -3.2), 2.6, (1.0, 0.91, 0.81))
    _sun('rim', (-2.5, -3.0, 2.0), 1.2, (0.74, 0.8, 1.0))
    _floor(12.0, 4.0, (3.5, 0.0))
    me = load_vrm('claude_robot', name='claude', location=(0.0, 0.0, 0.0), rotation=90.0)   # facing +X, the path
    walk = load_clip(me, 'walk')
    rep = walk_path(me, walk, [(0.0, 0.0), (7.0, 0.0)], Ground(fn=lambda x, y: 0.0 * x), f0=1, log=log)
    sc.frame_start, sc.frame_end = rep['frames']
    sc.frame_set(sc.frame_start)
    return sc


def meadow():
    """a meadow: vegetation.md's MEADOW recipe (fine grass under white and orange daisies, the wind on), under a sun"""
    from eidoblend.flora import create_flora, reset_flora_occupancy
    sc = _empty(24)
    sc.frame_start, sc.frame_end = 1, 48
    _sun('sun', (-0.4, 0.7, -0.6), 4.5)
    _floor(30.0, 30.0)
    reset_flora_occupancy()
    create_flora('grass', size=26, seed=3, height=0.42, blades='fine')
    create_flora('grass', size=18, seed=17, center=(1.5, 3.0), density=0.55, height=0.55, blades='fine')
    create_flora('daisy', size=13, seed=5, center=(0.4, 2.2), density=0.45, color='white')
    create_flora('daisy', size=10, seed=29, center=(-1.6, 3.6), density=0.35, color='orange')
    create_flora('daisy', size=8, seed=41, center=(1.8, 0.8), density=0.3, color={'white': 1, 'orange': 1})
    return sc
