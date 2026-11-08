"""The claudesona step's test helpers (tests only): the characters family's probe stage reused (a clean scene, EEVEE at
probe settings, the studio light, cameras), plus the bits these tests share: the out folder, PASS/FAIL lines, the
three-vrm reference run through deno, three <-> Blender axes, and name matching between three's sanitized node names
and Blender's bone names."""

import importlib.util
import json
import math
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
_spec = importlib.util.spec_from_file_location('characters_stage', os.path.join(REPO, 'blender', 'tests', 'characters', '_stage.py'))
CS = importlib.util.module_from_spec(_spec)       # the characters family's stage: clean_scene, probe_render, studio ...
_spec.loader.exec_module(CS)

OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
MAIN = os.path.join(os.path.dirname(REPO), 'eidoverse-video-prealpha-0.01')
VRMS = os.path.join(REPO, 'eidoverse', 'assets', 'vrms')

clean_scene, probe_render, studio_world, floor_disc, sun, camera, aim, still = (
    CS.clean_scene, CS.probe_render, CS.studio_world, CS.floor_disc, CS.sun, CS.camera, CS.aim, CS.still)


def argv():
    return sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


class Checks:
    def __init__(self, tag):
        self.tag, self.rows = tag, []

    def check(self, name, ok, detail=''):
        self.rows.append({'check': name, 'pass': bool(ok), 'detail': detail})
        print(f'[{self.tag}] {"PASS" if ok else "FAIL"} {name} {detail}', flush=True)
        return ok

    @property
    def all_pass(self):
        return all(r['pass'] for r in self.rows)


def to_three(v):
    return (v[0], v[2], -v[1])


def from_three(v):
    return (v[0], -v[2], v[1])


_RES = re.compile(r'[\[\]\.:/]')


def sanitize(name):
    """three's PropertyBinding.sanitizeNodeName (GLTFLoader names nodes with it)"""
    return _RES.sub('', re.sub(r'\s', '_', name))


def match_bone(three_name, blender_names):
    """the Blender bone for a three node name (Blender keeps spaces and dots, and cuts names at 63 bytes)"""
    want = sanitize(three_name)
    by = {sanitize(b): b for b in blender_names}
    if want in by:
        return by[want]
    for s, b in by.items():
        if len(b) >= 60 and want.startswith(s):
            return b
    return None


def import_map():
    """an import map for the engine's three / three-vrm in node_modules (this worktree's, else the main checkout's)"""
    for root in (REPO, MAIN):
        nm = os.path.join(root, 'node_modules')
        if os.path.isdir(os.path.join(nm, '@pixiv', 'three-vrm')):
            u = 'file:///' + nm.replace('\\', '/')
            m = {'imports': {'three': f'{u}/three/build/three.module.js', 'three/addons/': f'{u}/three/examples/jsm/',
                             '@pixiv/three-vrm': f'{u}/@pixiv/three-vrm/lib/three-vrm.module.js'}}
            p = os.path.join(OUT, 'import_map.json')
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(m, f)
            return p
    raise FileNotFoundError('no node_modules with @pixiv/three-vrm')


def three_vrm(job, tag):
    """run three_vrm_parity.mjs on a job dict; returns its result (cached by the job's content in out/)"""
    jp = os.path.join(OUT, f'{tag}_job.json')
    rp = os.path.join(OUT, f'{tag}_three.json')
    with open(jp, 'w', encoding='utf-8') as f:
        json.dump(job, f)
    cmd = ['deno', 'run', '--no-config', '--no-lock', '-A', f'--import-map={import_map()}',
           os.path.join(HERE, 'three_vrm_parity.mjs'), jp]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        raise RuntimeError(f'deno failed ({r.returncode}): {r.stderr[-2000:]}')
    line = [ln for ln in r.stdout.splitlines() if ln.startswith('{')][-1]
    with open(rp, 'w', encoding='utf-8') as f:
        f.write(line)
    return json.loads(line)


def turntable_studio(sc, light=0.7, background=0x2c3038, floor=True):
    """vrm_turntable_scene.js's neutral studio: key front-right, cool fill front-left, rim behind, a sky/ground
    hemisphere, the grey floor disc, the slate background (light scales it all)"""
    sys.path.insert(0, os.path.join(REPO, 'blender', 'tools'))
    import vrm_turntable as VT
    return VT.studio(sc, light=light, background=background, floor=floor)


def face_cam(h, lens=85.0, dist=0.62, height=None, name='facecam'):
    """a camera square on the face (the character faces -Y), aimed at the face's centre"""
    import bpy  # noqa: F401
    hb = h.arm.matrix_world @ h.arm.pose.bones[h.humanoid['head']].head
    z = hb.z + (0.07 * h.arm.scale[0] if height is None else height)
    cam = camera(name, lens=lens)
    aim(cam, (hb.x, hb.y - dist, z), (hb.x, hb.y, z))
    return cam


def run_mjs(script, job, tag, with_three=False):
    """run one of this folder's .mjs references on a job dict through deno; returns its JSON result"""
    jp = os.path.join(OUT, f'{tag}_job.json')
    with open(jp, 'w', encoding='utf-8') as f:
        json.dump(job, f)
    cmd = ['deno', 'run', '--no-config', '--no-lock', '-A']
    if with_three:
        cmd.append(f'--import-map={import_map()}')
    cmd += [os.path.join(HERE, script), jp]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        raise RuntimeError(f'deno {script} failed ({r.returncode}): {r.stderr[-2000:]}')
    line = [ln for ln in r.stdout.splitlines() if ln.startswith('{')][-1]
    with open(os.path.join(OUT, f'{tag}_ref.json'), 'w', encoding='utf-8') as f:
        f.write(line)
    return json.loads(line)


def lerp_keys(keys, t):
    if not keys:
        return 0.0
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return keys[-1][1]


def sheet(paths, out, cols=None, labels=None, scale=1.0):
    """tile PNG stills into one sheet (numpy + Blender's image API; Blender's Python has no PIL)"""
    import bpy
    import numpy as np
    ims = []
    for p in paths:
        im = bpy.data.images.load(p, check_existing=False)
        w, h = im.size
        a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
        ims.append(a)
        bpy.data.images.remove(im)
    cols = cols or len(ims)
    rows = math.ceil(len(ims) / cols)
    h, w = ims[0].shape[:2]
    big = np.zeros((rows * h, cols * w, 4), dtype=np.float32)
    big[..., 3] = 1
    for i, a in enumerate(ims):
        r, c = divmod(i, cols)
        big[(rows - 1 - r) * h:(rows - r) * h, c * w:(c + 1) * w] = a
    img = bpy.data.images.new('sheet', cols * w, rows * h, alpha=True)
    img.pixels.foreach_set(big.ravel())
    img.filepath_raw = out
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return out
