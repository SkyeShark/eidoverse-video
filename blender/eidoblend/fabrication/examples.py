"""eidoblend.fabrication.examples: eidoverse/examples/robotics/{manufacturing,relief,mesh_fabrication}.scene.js in Blender.

    from eidoblend.fabrication.examples import EXAMPLES
    rec = EXAMPLES['manufacturing'](scene)     # studio, machines, jobs, camera; every frame keyed

Each builder sets the scene to its WebGPU config (eidoverse/examples/robotics/<name>.json: size, 24 fps, duration),
builds what setup() built and keys what renderFrame(t) did at every frame (job.play), so the scene plays and renders on
its own. The harness runs them as films through scenes/<name>.json (python eido_blender.py render
blender/eidoblend/fabrication/scenes/manufacturing.json). They light themselves with the robotics studio, as there.

    manufacturing     the G430 three ways over an 18 s time-lapse: the FDM printing a 40 mm lathe sleeve (25 % infill,
                      #218675), the CNC milling an aluminium pocket, the relief CNC carving the original flowing crest
                      in hardwood at 192 cells; one wide camera framed from three's (-.55, .75, 1.2), margin 1.12
    relief            a close study of three-axis carving: roughing then finishing in hardwood over 24 s, the camera
                      framed on the stock from three's (.8, 1.05, .8), margin 1.5
    mesh_fabrication  the stock-rotating CNC carving the handle sample (an ordinary two-mesh object) in wood over 28 s,
                      starting at 1 s; needs eidoblend.fabrication.rotary (the rotary machine's own package)
"""

from __future__ import annotations

import json
import math
import os

import bpy
from mathutils import Vector

from ..common import EIDOVERSE_DIR
from . import three_geometry as tg
from .manufacturing_samples import manufacturing_sample
from .processes import carve, mill, print as fab_print
from .relief import sample_relief

EXAMPLES_DIR = os.path.join(EIDOVERSE_DIR, 'examples', 'robotics')


def _three(x, y, z):
    return Vector((x, -z, y))


def config(name):
    with open(os.path.join(EXAMPLES_DIR, name + '.json'), encoding='utf-8') as f:
        return json.load(f)


def _stage(scene, name, width=None, height=None, fps=None, duration=None, grid=True):
    from eidoblend.characters.robotics.studio import studio
    cfg = config(name)
    sc = scene or bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = width or cfg['width'], height or cfg['height']
    fps = fps or cfg['fps']
    sc.render.fps, sc.render.fps_base = int(fps), 1.0
    sc.frame_start = sc.frame_start or 1
    sc.frame_end = sc.frame_start + int(math.ceil((duration or cfg['duration']) * fps)) - 1
    sc.render.engine = 'BLENDER_EEVEE'
    sc.view_settings.view_transform = 'AgX'
    return sc, studio(sc, grid=grid)


def manufacturing(scene=None, **cfg):
    from eidoblend.characters.robotics import make_robot
    from eidoblend.characters.robotics.studio import frame_camera, make_camera
    sc, st = _stage(scene, 'manufacturing', **cfg)
    cam = make_camera(36, 'manufacturing camera', sc)
    sc.camera = cam
    printer = make_robot('fdm', scene=sc, position=tuple(_three(-.78, 0, 0)), accent='#267c82', filament='#218675')
    cnc = make_robot('cnc', scene=sc, position=(0.0, 0.0, 0.0), accent='#b26c36')
    wood_cnc = make_robot('cnc_relief', scene=sc, position=tuple(_three(.78, 0, 0)), accent='#688050')
    sleeve = tg.lathe([[.014, 0], [.020, 0], [.020, .006], [.014, .006], [.014, 0]], 48)
    jobs = [fab_print(printer, sleeve, size=.04, infill=.25, duration=18, color='#218675'),
            mill(cnc, None, material='aluminum', duration=18),
            carve(wood_cnc, sample_relief, material='wood', duration=18, resolution=192)]
    frame_camera(cam, [printer.group, cnc.group, wood_cnc.group], direction=_three(-.55, .75, 1.2), margin=1.12)
    cam.data.clip_start = .05                  # depth precision for the 0.65 mm sheet over its bed, as there
    for j in jobs:
        j.play(scene=sc)
    return {'robots': [printer, cnc, wood_cnc], 'jobs': jobs, 'camera': cam, 'studio': st}


def relief(scene=None, **cfg):
    from eidoblend.characters.robotics import make_robot
    from eidoblend.characters.robotics.studio import frame_camera, make_camera
    sc, st = _stage(scene, 'relief', grid=False, **cfg)
    cam = make_camera(36, 'relief camera', sc)
    cam.data.clip_start = .0001
    sc.camera = cam
    machine = make_robot('cnc_relief', scene=sc, accent='#547b68')
    carving = carve(machine, sample_relief, material='wood', duration=24, resolution=192)
    frame_camera(cam, [carving.mesh], direction=_three(.8, 1.05, .8), margin=1.5)
    carving.play(scene=sc)
    return {'robots': [machine], 'jobs': [carving], 'camera': cam, 'studio': st}


def mesh_fabrication(scene=None, frames=None, cache_dir=None, resolution=(256, 96, 96), **cfg):
    """frames: key only these frames (the rotary stock writes one VDB file per keyed frame); cache_dir: where (an
    absolute folder, or '//...' beside a saved .blend)."""
    from eidoblend.characters.robotics import make_robot
    from eidoblend.characters.robotics.studio import make_camera
    from . import rotary                            # the stock-rotating machine's package (its own step)
    sc, st = _stage(scene, 'mesh_fabrication', grid=False, **cfg)
    cam = make_camera(36, 'mesh fabrication camera', sc)
    cam.data.clip_start = .035
    sc.camera = cam
    machine = make_robot('cnc_rotary', scene=sc, primary='#b9c7c8', accent='#235b68')
    # the WebGPU source is an Object3D outside the scene graph: here its exact parts, so nothing extra renders
    source = manufacturing_sample('handle', as_parts=True)
    job = rotary.rotary_carve(machine, source, material='wood', duration=28,
                              cache_dir=cache_dir or '//mesh_fabrication_stock_cache', resolution=resolution)
    cam.location = _three(-.31, .38, .48)
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (_three(.015, .16, 0) - cam.location).to_track_quat('-Z', 'Y')
    fps = sc.render.fps / sc.render.fps_base
    keyed = list(range(sc.frame_start, sc.frame_end + 1)) if frames is None else sorted(int(f) for f in frames)
    for f in keyed:                                 # renderFrame(t): job.seek(max(0, t - 1))
        job.seek(max(0.0, (f - sc.frame_start) / fps - 1))
        job.key(f)
    return {'robots': [machine], 'jobs': [job], 'camera': cam, 'studio': st, 'source': source, 'frames': keyed}


EXAMPLES = {'manufacturing': manufacturing, 'relief': relief, 'mesh_fabrication': mesh_fabrication}
