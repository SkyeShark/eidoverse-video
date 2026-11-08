"""Shared fixtures for the UNKNOWN FORCE corridor / news probes: the worktree on sys.path, the shared texture library,
a clean scene, probe render settings, PASS / FAIL lines and still renders from the sets' own cameras.

Every render goes through the shared GPU slot: from the main checkout,
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <this folder>/render_shots.py both
(the shot renders peak near 1 GB of RAM before rendering: a cap of 4 is enough and leaves the shared ledger room).
"""
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[2]
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
if str(WORKTREE / 'blender') not in sys.path:
    sys.path.insert(0, str(WORKTREE / 'blender'))

# the shared CC0 library: the sets' texture sets (Marble016, Asphalt025C ... all fetched once) sit in the main
# checkout's library, which is read, never written; this worktree's own library (when it has one) holds other sets'
_MAIN_CACHE = Path('C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01/eidoverse/assets/cache')
_NEEDED = ('Marble016_2k', 'Asphalt025C_2k', 'Cardboard002_1k', 'Fabric077_1k')
if not os.environ.get('EIDO_ASSET_CACHE'):
    _own = WORKTREE / 'eidoverse/assets/cache'
    if not all((_own / 'textures' / n / 'tex_urls.json').is_file() for n in _NEEDED) and \
            all((_MAIN_CACHE / 'textures' / n / 'tex_urls.json').is_file() for n in _NEEDED):
        os.environ['EIDO_ASSET_CACHE'] = str(_MAIN_CACHE)
os.environ.setdefault('EIDO_NO_FETCH', '1')

import bpy  # noqa: E402

RESULTS = []


def args():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok)))
    print(f'{"PASS" if ok else "FAIL"} {name}' + (f'  ({detail})' if detail else ''), flush=True)
    return ok


def summary():
    n = sum(1 for _, ok in RESULTS if ok)
    print(f'SUMMARY {n}/{len(RESULTS)} passed', flush=True)
    return n == len(RESULTS)


def clean_scene():
    sc = bpy.context.scene
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.images,
                 bpy.data.node_groups, bpy.data.worlds):
        for b in list(coll):
            if b.users == 0:
                coll.remove(b)
    for c in list(sc.collection.children):
        sc.collection.children.unlink(c)
    return sc


def render_settings(width=960, height=540, samples=16, fps=24):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = width, height
    sc.render.resolution_percentage = 100
    sc.render.fps = fps
    sc.render.film_transparent = False
    sc.eevee.taa_render_samples = samples
    sc.view_settings.view_transform = 'AgX'
    sc.render.image_settings.file_format = 'PNG'
    return sc


def render_still(path, scene=None):
    sc = scene or bpy.context.scene
    sc.render.filepath = str(path)
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    ok = os.path.isfile(str(path))
    print(f'[probe] {Path(path).name} {"written" if ok else "MISSING"} in {time.time() - t0:.1f}s', flush=True)
    return ok


def timer():
    t0 = time.time()
    return lambda: time.time() - t0
