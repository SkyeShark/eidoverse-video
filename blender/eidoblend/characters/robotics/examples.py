"""eidoblend.characters.robotics.examples: eidoverse/examples/robotics/{assembly,mantis,motion}.scene.js in Blender.

    from eidoblend.characters.robotics.examples import EXAMPLES
    rec = EXAMPLES['assembly'](scene)        # builds the whole example: studio, robots, camera, every frame keyed

Each builder sets the scene to its config (eidoverse/examples/robotics/<name>.json: 1280 x 720, 24 fps, its duration),
builds what setup() built and keys what renderFrame(t) did at every frame, so the scene plays and renders on its own.
The harness runs them as films through scenes/<name>.json (python eido_blender.py render
blender/eidoblend/characters/robotics/scenes/assembly.json). Their own studio lighting is the point, as there: the
scene scripts declare _no_auto_enhance.

    assembly   a B-540 backbone with the stereo camera on sensor_0 and the pan/tilt face on sensor_1, both playing
               their 'joints' sample; the camera framed on the backbone from three's (1, .7, 1.5), fov 32
    mantis     MANTIS (primary #b4c6c3, accent #365e65) driving its 'drive-circle'; the camera framed at t = 0 from
               (.7, .65, 1) with margin 1.06, fov 36, then carried with the body root (same offset, same view)
    motion     the humanoid and the quadruped on 'run-circle', the drone with the hand on 'flight' (no support
               check: it hangs from the air), the tracked arm on 'drive'; a fixed camera at three's (5, 3.8, 7)
               looking at (-.8, .7, 0), fov 35
"""

from __future__ import annotations

import json
import math
import os

import bpy
from mathutils import Vector

from . import io as kio
from .kit import make_robot
from .studio import frame_camera, make_camera, studio

EXAMPLES_DIR = os.path.join(kio.REPO, 'eidoverse', 'examples', 'robotics')


def _three(x, y, z):
    return Vector((x, -z, y))


def config(name):
    """the WebGPU example's own config (width, height, fps, duration, outputVideo)"""
    with open(os.path.join(EXAMPLES_DIR, name + '.json'), encoding='utf-8') as f:
        return json.load(f)


def _stage(scene, name, width=None, height=None, fps=None, duration=None):
    cfg = config(name)
    sc = scene or bpy.context.scene
    width, height = width or cfg['width'], height or cfg['height']
    fps, duration = fps or cfg['fps'], duration or cfg['duration']
    sc.render.resolution_x, sc.render.resolution_y = width, height
    sc.render.fps, sc.render.fps_base = int(fps), 1.0
    sc.frame_start = sc.frame_start or 1
    sc.frame_end = sc.frame_start + int(math.ceil(duration * fps)) - 1
    return sc, studio(sc)


def assembly(scene=None, **cfg):
    sc, st = _stage(scene, 'assembly', **cfg)
    cam = make_camera(32, 'assembly camera', sc)
    cam.data.clip_start, cam.data.clip_end = 0.001, 20.0
    sc.camera = cam
    base = make_robot('mobility/body', scene=sc)
    camera = make_robot('camera', scene=sc)
    face = make_robot('face', scene=sc)
    base.attach(camera, port='body_base/sensor_0', child_port='camera_base/input')
    base.attach(face, port='body_base/sensor_1', child_port='display_base/input')
    frame_camera(cam, [base.group], direction=_three(1, 0.7, 1.5))
    for r in (camera, face):
        r.play('joints', scene=sc)
    return {'robots': [base, camera, face], 'camera': cam, 'studio': st}


def mantis(scene=None, **cfg):
    sc, st = _stage(scene, 'mantis', **cfg)
    cam = make_camera(36, 'mantis camera', sc)
    cam.data.clip_start, cam.data.clip_end = 0.001, 30.0
    sc.camera = cam
    m = make_robot('mantis', scene=sc, primary='#b4c6c3', accent='#365e65')
    m.sample('drive-circle', 0)
    target = frame_camera(cam, [m.group], direction=_three(0.7, 0.65, 1), margin=1.06)
    body = m.roots[m.report['novel']['body_root']]
    bpy.context.view_layer.update()
    anchor = body.matrix_world.translation.copy()
    cam_off, tgt_off = cam.location - anchor, target - anchor
    m.play('drive-circle', scene=sc)
    for f in range(sc.frame_start, sc.frame_end + 1):          # renderFrame: the camera carried with the body root
        sc.frame_set(f)
        a = body.matrix_world.translation.copy()
        cam.location = a + cam_off
        cam.rotation_quaternion = ((a + tgt_off) - cam.location).to_track_quat('-Z', 'Y')
        cam.keyframe_insert('location', frame=f)
        cam.keyframe_insert('rotation_quaternion', frame=f)
    _linear(cam)
    return {'robots': [m], 'camera': cam, 'studio': st, 'camera_offset': cam_off, 'target_offset': tgt_off}


def motion(scene=None, **cfg):
    sc, st = _stage(scene, 'motion', **cfg)
    cam = make_camera(35, 'motion camera', sc)
    cam.data.clip_start, cam.data.clip_end = 0.001, 30.0
    sc.camera = cam
    robots = []
    for rid, clip, pos in (('humanoid', 'run-circle', (-1.3, 0, 0)), ('quadruped', 'run-circle', (1.6, 0, 0)),
                           ('payloads/drone_hand', 'flight', (0, 1.1, -1.8)), ('payloads/rover_arm', 'drive', (0, 0, 1.8))):
        r = make_robot(rid, scene=sc, position=tuple(_three(*pos)))
        if clip == 'flight':
            r.group['no_support_check'] = True          # it hangs from the air, its hand payload below it
        r.play(clip, scene=sc)
        robots.append(r)
    cam.location = _three(5, 3.8, 7)
    cam.rotation_quaternion = (_three(-0.8, 0.7, 0) - cam.location).to_track_quat('-Z', 'Y')
    return {'robots': robots, 'camera': cam, 'studio': st}


def _linear(ob):
    from bpy_extras import anim_utils
    ad = ob.animation_data
    if ad and ad.action:
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        for fc in cb.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'


EXAMPLES = {'assembly': assembly, 'mantis': mantis, 'motion': motion}
