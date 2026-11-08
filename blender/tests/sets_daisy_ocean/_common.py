"""Helpers the ocean tests share (tests only): paths, PASS/FAIL lines, the WebGPU dump, the characters family's probe
stage (clean scene, EEVEE probe settings)."""

import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
BLENDER_DIR = os.path.join(REPO, 'blender')
if BLENDER_DIR not in sys.path:
    sys.path.insert(0, BLENDER_DIR)
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
MAIN = os.path.join(os.path.dirname(REPO), 'eidoverse-video-prealpha-0.01')
THREE_BUILD = os.path.join(MAIN, 'node_modules', 'three', 'build')
JS_DUMP = os.path.join(OUT, 'ocean_js.json')


def argv():
    return sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


class Checks:
    def __init__(self, tag):
        self.tag, self.rows = tag, []

    def check(self, name, ok, detail=''):
        self.rows.append({'check': name, 'pass': bool(ok), 'detail': detail})
        print(f'[{self.tag}] {"PASS" if ok else "FAIL"} {name} {detail}', flush=True)
        return ok

    def summary(self):
        n = sum(1 for r in self.rows if r['pass'])
        print(f'[{self.tag}] {n}/{len(self.rows)} checks pass', flush=True)
        return n == len(self.rows)


def save_blend(path):
    """Save the scene (compressed, no .blend1 backup: the out folder stays small)."""
    import bpy
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    print('[save]', path, flush=True)


def js_dump(refresh=False):
    """The WebGPU set's numbers (ocean_dump.mjs), made once with deno."""
    if refresh or not os.path.exists(JS_DUMP):
        subprocess.run(['deno', 'run', '--no-config', '--no-lock', '-A', os.path.join(HERE, 'ocean_dump.mjs'), THREE_BUILD,
                        JS_DUMP], cwd=REPO, check=True)
    with open(JS_DUMP, encoding='utf-8') as f:
        return json.load(f)


def characters_stage():
    spec = importlib.util.spec_from_file_location('characters_stage', os.path.join(BLENDER_DIR, 'tests', 'characters', '_stage.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
