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


def material_attr_misses(collection):
    """(object, material, name) for every mesh whose material reads a named uv map or a geometry attribute that the
    mesh (as evaluated, its Geometry Nodes applied) does not carry: the texture then samples a single texel and the
    surface comes out one flat colour, as the corridor's pedestal once did (its marble read the walls' UVBook)."""
    dg = bpy.context.evaluated_depsgraph_get()
    miss = []
    for ob in collection.all_objects:
        if ob.type != 'MESH':
            continue
        names = set(ob.data.attributes.keys()) | set(ob.data.uv_layers.keys())
        ev = ob.evaluated_get(dg)
        if getattr(ev, 'data', None) is not None and hasattr(ev.data, 'attributes'):
            names |= set(ev.data.attributes.keys())
        for m in ob.data.materials:                     # (a material a Geometry Nodes tree sets on its output is not here)
            if m is None or m.node_tree is None:
                continue
            for n in m.node_tree.nodes:
                want = None
                if n.bl_idname == 'ShaderNodeUVMap' and n.uv_map:
                    want = n.uv_map
                elif n.bl_idname == 'ShaderNodeAttribute' and n.attribute_type == 'GEOMETRY':
                    want = n.attribute_name
                if want and want not in names:
                    miss.append((ob.name, m.name, want))
    return miss
