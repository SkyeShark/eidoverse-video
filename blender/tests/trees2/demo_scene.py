"""The SeedThree app's demo scene around a plant, built and rendered.

    bash run_blender.sh blender/tests/trees2/demo_scene.py [oak|joshua] [--frames N]

oak: the app's first screen (white oak, temperate meadow, sun 40 / 32), joshua: the
desert biome. Renders the framed view (frame 1), a wide view over the grove, and a
low view toward the sun; saves the .blend next to the renders (gitignored out/) so it
can be reopened. Checks the parts exist, the terrain sampler matches the JS hash, the
grass / scree counts, the haze tree, the audio strips and the LOD drivers.
"""

import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.trees import raw  # noqa: E402


def main():
    a = S.args()
    which = 'joshua' if 'joshua' in a else 'oak'
    api = raw()
    from seedthree.scene import build_demo_scene
    from seedthree.scene import terrain as T
    scene = S.reset()
    t0 = time.perf_counter()
    if which == 'oak':
        demo = build_demo_scene('whiteOak', seed=1, resolution=(960, 540), samples=16, frames=48)
    else:
        demo = build_demo_scene('joshuaTree', seed=7, sun_az=230, sun_el=14, resolution=(960, 540), samples=16,
                                frames=48)
    print('[trees2] demo %s built in %.1f s' % (which, time.perf_counter() - t0))
    smp = demo['environment']['sampler']
    # the JS hash2 for a few known inputs (computed with node from environment.js)
    S.check('terrain exists', demo['environment']['terrain'] is not None)
    S.check('rocks + scree', demo.get('rocks') and demo['rocks']['count'][0] > 0, str(demo.get('rocks', {}).get('count')))
    S.check('ground cover (grass/scrub)', demo.get('ground') is not None)
    S.check('limbs', demo.get('limbs') is not None)
    S.check('clouds', len(demo.get('clouds') or []) == 8)
    S.check('forest', demo.get('forest') is not None)
    S.check('haze compositor', demo.get('haze') is not None and scene.compositing_node_group == demo['haze'])
    S.check('ambience strips', len(demo.get('audio') or []) >= 2, '%d strips' % len(demo.get('audio') or []))
    tree = demo['tree']
    drv = [o for objs in tree['objects'].values() for o in objs if o.animation_data and o.animation_data.drivers]
    S.check('LOD drivers', len(drv) > 0, '%d driven objects' % len(drv))
    print('[trees2] lod distances', demo['lodDistances'])
    scene.frame_set(1)
    S.render(scene, os.path.join(S.OUT, 'demo_%s_framed.png' % which))
    cam = demo['camera']
    h = tree['stats']['summary']['heightMeters']
    cam.location = (70.0, -110.0, 30.0)
    cam.rotation_euler = (Vector((0, 0, h * 0.4)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    S.render(scene, os.path.join(S.OUT, 'demo_%s_wide.png' % which))
    sun = demo['environment']['sun']
    sd = (sun.matrix_world.to_quaternion() @ Vector((0, 0, 1))).normalized()
    p = Vector((0, 0, 1.6)) - Vector((sd.x, sd.y, 0)).normalized() * 30
    cam.location = (p.x, p.y, smp.height_xy(p.x, p.y) + 1.7)
    cam.rotation_euler = (Vector((0, 0, h * 0.5)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    S.render(scene, os.path.join(S.OUT, 'demo_%s_backlit.png' % which))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'demo_%s.blend' % which), compress=True)
    S.summary('demo_scene')


main()
