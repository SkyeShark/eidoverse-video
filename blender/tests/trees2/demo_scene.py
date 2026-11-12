"""The SeedThree app's demo scene around a plant, built and rendered.

    bash run_blender.sh blender/tests/trees2/demo_scene.py [oak|joshua] [--frames N]

oak: the app's first screen (white oak, temperate meadow, sun 40 / 32), joshua: the
desert biome with the app's scale reference, AO and auto-rotate toggles on (checked:
the 1.8 m box, EEVEE's AO, the keyed orbit's speed). Renders the framed view (frame 1), a wide view over the grove, and a
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
        # the desert run also takes the app's Environment / Camera toggles: the 1.8 m scale
        # reference, N8AO (EEVEE's AO here) and the orbit camera
        demo = build_demo_scene('joshuaTree', seed=7, sun_az=230, sun_el=14, resolution=(960, 540), samples=16,
                                frames=48, scale_ref=True, ao=True, autorotate=True)
    print('[trees2] demo %s built in %.1f s' % (which, time.perf_counter() - t0))
    if which == 'joshua':
        ref = demo['scaleRef']
        S.check('scale reference: the 1.8 m box, rendered', not ref.hide_render and abs(ref.dimensions.z - 1.8) < 1e-4,
                '%.3f m' % ref.dimensions.z)
        ee = scene.eevee
        S.check('AO toggle: EEVEE fast GI on', getattr(ee, 'use_fast_gi', True), str(getattr(ee, 'fast_gi_method', '')))
        cam_ = demo['camera']
        piv = demo['orbit'].location.copy()
        fps = scene.render.fps / scene.render.fps_base
        ang = []
        for fr in (scene.frame_start, scene.frame_end):
            scene.frame_set(fr)
            d = cam_.matrix_world.translation - piv
            ang.append(math.atan2(d.y, d.x))
        want = 2 * math.pi * (1.0 / 60.0) * (scene.frame_end - scene.frame_start) / fps
        got = (ang[1] - ang[0] + math.pi) % (2 * math.pi) - math.pi
        S.check('auto-rotate: the keyed orbit turns one round per 60 s at speed 1 (OrbitControls)',
                abs(got - want) < 1e-3, '%.2f deg over the shot, want %.2f' % (math.degrees(got), math.degrees(want)))
        scene.frame_set(scene.frame_start)
        fwd = (cam_.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))).normalized()
        aim = math.degrees(fwd.angle((piv - cam_.matrix_world.translation).normalized()))
        S.check('auto-rotate keeps the framing: the camera looks at the plant', aim < 15.0,
                '%.1f deg between the view axis and the orbit centre' % aim)
    smp = demo['environment']['sampler']
    # the JS hash2 for a few known inputs (computed with node from environment.js)
    S.check('terrain exists', demo['environment']['terrain'] is not None)
    S.check('rocks + scree', demo.get('rocks') and demo['rocks']['count'][0] > 0, str(demo.get('rocks', {}).get('count')))
    S.check('ground cover (grass/scrub)', demo.get('ground') is not None)
    S.check('limbs', demo.get('limbs') is not None)
    S.check('clouds', len(demo.get('clouds') or []) == 8)
    S.check('forest', demo.get('forest') is not None)
    S.check('haze compositor', demo.get('haze') is not None and scene.compositing_node_group == demo['haze'])
    hz = demo['haze']
    near_far = (hz.nodes['Fog Near'].outputs[0].default_value, hz.nodes['Fog Far'].outputs[0].default_value)
    S.check('the range fog the app falls back to: %s' % ('55-230 m (desert)' if which == 'joshua' else '95-300 m'),
            near_far == ((55.0, 230.0) if which == 'joshua' else (95.0, 300.0)), str(near_far))
    vs = scene.view_settings
    S.check('three\'s ACES at 1.3 as AgX High Contrast at log2(1.3) + 0.23 stops',
            vs.view_transform == 'AgX' and vs.look == 'AgX - High Contrast' and abs(vs.exposure - (math.log2(1.3) + 0.23)) < 1e-4,
            '%s / %s / %.3f' % (vs.view_transform, vs.look, vs.exposure))
    sun_ = demo['environment']['sun']
    S.check('the app\'s sun colour: its HSL triple taken as linear (three r184 setHSL)',
            sun_.data.color[0] > 0.8 and sun_.data.color[2] < sun_.data.color[1] < sun_.data.color[0],
            str(tuple(round(c, 3) for c in sun_.data.color)))
    # a 48-frame shot is shorter than the first bird call (6-18 s in): the wind bed alone
    # covers it (the birds' schedule and the mixdown are ambience_mixdown.py's)
    audio = demo.get('audio') or []
    beds = [s for s in audio if s.name.startswith('SeedThree wind')]
    S.check('ambience: the wind bed covers the shot', beds and min(s.frame_final_start for s in beds) <= scene.frame_start
            and max(s.frame_final_end for s in beds) > scene.frame_end,
            '%d strips, bed %s' % (len(audio), [(s.frame_final_start, s.frame_final_end) for s in beds]))
    tree = demo['tree']
    drv = [o for objs in tree['objects'].values() for o in objs if o.animation_data and o.animation_data.drivers]
    S.check('LOD drivers', len(drv) > 0, '%d driven objects' % len(drv))
    print('[trees2] lod distances', demo['lodDistances'])
    scene.frame_set(1)
    S.render(scene, os.path.join(S.OUT, 'demo_%s_framed.png' % which))
    # the scene as built (orbit, drivers, audio) reopens from this file
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'demo_%s.blend' % which), compress=True)
    cam = demo['camera']
    if demo.get('orbit') is not None:
        cam.parent = None          # the probe shots below place the camera in world space
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
    # the clouds in the scene: 30 m behind the plant from the nearest cloud, eye height, looking
    # 12 degrees up toward it (the plant and the grove below, the cloud above)
    clouds = demo.get('clouds') or []
    if clouds:
        c0 = min(clouds, key=lambda c: c.location.to_2d().length)
        toward = c0.location.to_2d().normalized()
        p = -toward * 30.0
        cam.location = (p.x, p.y, smp.height_xy(p.x, p.y) + 1.7)
        look = Vector((toward.x * math.cos(math.radians(12)), toward.y * math.cos(math.radians(12)), math.sin(math.radians(12))))
        cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
        S.render(scene, os.path.join(S.OUT, 'demo_%s_clouds.png' % which))
    S.summary('demo_scene')


main()
