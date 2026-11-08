"""Probe-scene helpers for the trees2 tests: round one's trees/_scene.py (the neutral
sky + sun + SeedThree ground stage), with this folder's out/ and a few more helpers."""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
_spec = importlib.util.spec_from_file_location('_trees_scene', os.path.join(HERE, '..', 'trees', '_scene.py'))
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)

args = _base.args
reset = _base.reset
render_settings = _base.render_settings
sky_and_sun = _base.sky_and_sun
ground = _base.ground
camera = _base.camera
render = _base.render
BLENDER_DIR = _base.BLENDER_DIR

import bpy  # noqa: E402

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok)))
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, (': ' + detail) if detail else ''))
    return ok


def summary(tag):
    bad = [n for n, ok in RESULTS if not ok]
    print('[%s] %d/%d PASS%s' % (tag, len(RESULTS) - len(bad), len(RESULTS), ('; FAIL: ' + ', '.join(bad)) if bad else ''))


def show_only(tree, level):
    for name, objs in tree['objects'].items():
        for o in objs:
            o.hide_render = name != level


def clear_lights_cameras(scene):
    for o in [o for o in scene.objects if o.type in ('LIGHT', 'CAMERA')]:
        data = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Light):
                bpy.data.lights.remove(data)
            elif isinstance(data, bpy.types.Camera):
                bpy.data.cameras.remove(data)


def save_image(img, path):
    """Write a (packed or generated) bpy image to a PNG for looking at."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(filepath=path)
    return path
