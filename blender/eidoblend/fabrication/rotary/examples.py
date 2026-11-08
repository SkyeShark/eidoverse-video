"""eidoverse/examples/robotics/rotary.scene.js and rotary_metal.scene.js in Blender.

    from eidoblend.fabrication.rotary.examples import EXAMPLES
    rec = EXAMPLES['rotary'](scene, cache_dir='//rotary_cache')      # studio, machine, job, camera, every frame keyed
    rec = EXAMPLES['rotary_metal'](scene, frames=[1, 49, 241, 721])   # or only the frames a probe renders

Each builder sets the scene to its example's config (eidoverse/examples/robotics/<name>.json: 1280 x 900, 24 fps, 31
or 32 s), builds what setup() built (the robotics studio without its grid, the cnc_rotary machine in #b9c7c8 /
#235b68, the rotary job, the 36-degree camera) and keys what renderFrame(t) did at every frame (or at `frames`; a
frame left out has no stock file, so render only keyed frames then). The harness runs them as films through
scenes/<name>.json (python eido_blender.py render blender/eidoblend/fabrication/rotary/scenes/rotary.json).

    rotary        an indexed rotary carving study in hardwood: the sample sculpture (change the radius function to
                  design the shape), the whole program played over 28 s after a one-second hold
    rotary_metal  aluminium at physical cutting speed: two seconds of setup, eight seconds of real cutting from the
                  first chip, then a time lapse to the finished part; the camera moves in close for the cutting
                  (a cut at 2 s and back at 28 s). Change material to 'brass' for its look and rates.
"""

from __future__ import annotations

import json
import math
import os

from .._axes import Rec
from .carve import rotary_carve
from .path import sample_rotary

EXAMPLES_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..',
                                             'eidoverse', 'examples', 'robotics'))
PRIMARY, ACCENT = '#b9c7c8', '#235b68'


def config(name):
    """the WebGPU example's own config (width, height, fps, duration, outputVideo)"""
    with open(os.path.join(EXAMPLES_DIR, name + '.json'), encoding='utf-8') as f:
        return json.load(f)


def _three(x, y, z):
    from mathutils import Vector
    return Vector((x, -z, y))


def _stage(scene, name, width=None, height=None, fps=None, duration=None):
    import bpy
    from eidoblend.characters.robotics import studio
    cfg = config(name)
    sc = scene or bpy.context.scene
    width, height = width or cfg['width'], height or cfg['height']
    fps, duration = fps or cfg['fps'], duration or cfg['duration']
    sc.render.resolution_x, sc.render.resolution_y = width, height
    sc.render.fps, sc.render.fps_base = int(fps), 1.0
    sc.frame_start = sc.frame_start or 1
    sc.frame_end = sc.frame_start + int(math.ceil(duration * fps)) - 1
    sc.render.engine = 'BLENDER_EEVEE'
    return sc, studio(sc, grid=False)


def _camera(sc, name):
    from eidoblend.characters.robotics.studio import make_camera
    cam = make_camera(36, name, sc)
    cam.data.clip_start, cam.data.clip_end = .035, 10.0
    sc.camera = cam
    return cam


def _aim(cam, eye, target):
    cam.location = _three(*eye)
    cam.rotation_quaternion = (_three(*target) - cam.location).to_track_quat('-Z', 'Y')


def _frames(sc, frames):
    return list(range(sc.frame_start, sc.frame_end + 1)) if frames is None else sorted(int(f) for f in frames)


def rotary(scene=None, frames=None, cache_dir=None, resolution=(256, 96, 96), **cfg):
    """rotary.scene.js: job.seek(max(0, t - 1)) at every frame of a 28 s wood carving."""
    from eidoblend.characters.robotics import make_robot
    sc, st = _stage(scene, 'rotary', **cfg)
    cam = _camera(sc, 'rotary camera')
    machine = make_robot('cnc_rotary', scene=sc, primary=PRIMARY, accent=ACCENT)
    job = rotary_carve(machine, sample_rotary, material='wood', duration=28,
                       cache_dir=cache_dir or '//rotary_stock_cache', resolution=resolution)
    _aim(cam, (-.31, .38, .48), (.015, .16, 0))
    fps = sc.render.fps / sc.render.fps_base
    for f in _frames(sc, frames):
        job.seek(max(0.0, (f - sc.frame_start) / fps - 1))
        job.key(f)
    return Rec(scene=sc, machine=machine, job=job, camera=cam, studio=st)


def metal_time(t, cutting_start, duration):
    """rotary_metal's renderFrame(t) clock: setup, eight seconds at physical speed from the first chip, a time lapse"""
    if t < 2:
        return t
    if t < 10:
        return cutting_start + t - 2
    return cutting_start + 8 + min(1.0, (t - 10) / 18) * (duration - cutting_start - 8)


def rotary_metal(scene=None, frames=None, cache_dir=None, material='aluminum', resolution=(256, 96, 96), log=print,
                 **cfg):
    """rotary_metal.scene.js: aluminium at physical cutting speed, then a time lapse; the camera cuts close at 2 s."""
    from eidoblend.characters.robotics import make_robot
    sc, st = _stage(scene, 'rotary_metal', **cfg)
    cam = _camera(sc, 'rotary metal camera')
    machine = make_robot('cnc_rotary', scene=sc, primary=PRIMARY, accent=ACCENT)
    job = rotary_carve(machine, sample_rotary, material=material, cache_dir=cache_dir or '//rotary_metal_cache',
                       resolution=resolution)
    cutting_start = job.removal.events[0]['time']
    log('METAL_STUDY', json.dumps({'physical_duration': job.physical_duration, 'cutting_start': cutting_start,
                                   'settings': {k: v for k, v in job.settings.items() if k != 'centre_seat'},
                                   'stages': len(job.program.stages)}))
    fps = sc.render.fps / sc.render.fps_base
    for f in _frames(sc, frames):
        t = (f - sc.frame_start) / fps
        job.seek(metal_time(t, cutting_start, job.duration))
        if t < 2 or t >= 28:
            _aim(cam, (-.31, .38, .48), (.015, .16, 0))
        else:
            _aim(cam, (.22, .275, .30), (.025, .153, 0))
        for path in ('location', 'rotation_quaternion'):
            cam.keyframe_insert(path, frame=f)
        job.key(f)
    _constant(cam)                                       # the camera cuts between its two views; it never travels
    return Rec(scene=sc, machine=machine, job=job, camera=cam, studio=st, cutting_start=cutting_start)


def _constant(ob):
    from bpy_extras import anim_utils
    ad = ob.animation_data
    if ad and ad.action:
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        for fc in cb.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'


EXAMPLES = {'rotary': rotary, 'rotary_metal': rotary_metal}
