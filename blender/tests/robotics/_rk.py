"""The robotics tests' shared helpers (tests only): paths, PASS/FAIL lines, a clean scene, EEVEE probe settings, stills,
the three -> Blender matrix conversion the JS parity dumps need, and a contact sheet."""

import json
import math
import os
import sys
import time

import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
sys.dont_write_bytecode = True
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
DUMP = os.path.join(OUT, 'js_parity')
RESULTS = {'checks': [], 'fails': 0}
T0 = time.time()

C = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))      # Blender -> three: (x, y, z) -> (x, z, -y)
CI = C.inverted()


def argv():
    return sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def log(tag, *a):
    print(f'[{tag}]', *a, flush=True)


def check(name, ok, detail=''):
    line = ('PASS ' if ok else 'FAIL ') + name + (f'  ({detail})' if detail else '')
    print(line, flush=True)
    RESULTS['checks'].append(line)
    if not ok:
        RESULTS['fails'] += 1
    return ok


def three_matrix(e):
    """three's Matrix4.elements (column-major) -> a Blender Matrix in three's axes"""
    return Matrix([[e[j * 4 + i] for j in range(4)] for i in range(4)])


def world_from_three(e):
    """a three world matrix -> the same object's world matrix in Blender's axes: C^-1 W C"""
    return CI @ three_matrix(e) @ C


def frame_from_three(e):
    """a three port frame (local to its owner) -> Blender's: C^-1 M"""
    return CI @ three_matrix(e)


def mdiff(a, b):
    return max(abs(a[i][j] - b[i][j]) for i in range(4) for j in range(4))


def clean_scene(fps=24):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for blocks in (bpy.data.meshes, bpy.data.materials, bpy.data.actions, bpy.data.node_groups, bpy.data.lights,
                   bpy.data.cameras):
        for b in list(blocks):
            if b.users == 0:
                blocks.remove(b)
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = fps, 1.0
    return sc


def probe_render(sc, res=(960, 540), samples=16):
    r, ee = sc.render, sc.eevee
    r.engine = 'BLENDER_EEVEE'
    r.resolution_x, r.resolution_y, r.resolution_percentage = res[0], res[1], 100
    r.filter_size = 1.5
    ee.taa_render_samples = samples
    ee.use_raytracing = True
    ee.ray_tracing_method = 'SCREEN'
    o = ee.ray_tracing_options
    o.resolution_scale = '1'
    o.trace_max_roughness = 0.5
    o.use_denoise = True
    ee.use_fast_gi = True
    ee.fast_gi_method = 'GLOBAL_ILLUMINATION'
    ee.fast_gi_distance = 0.6
    ee.use_shadows = True
    ee.shadow_ray_count = 2
    ee.shadow_step_count = 12
    ee.use_overscan = True
    ee.overscan_size = 3.0
    vs = sc.view_settings
    vs.view_transform = 'AgX'
    vs.look = 'AgX - Base Contrast'
    vs.exposure = 0.0
    r.image_settings.media_type = 'IMAGE'
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_mode = 'RGB'
    r.use_motion_blur = False


NO_RENDER = '--no-render' in sys.argv


def still(sc, cam, frame, path):
    """render one still (with --no-render: build-only runs set the frame and skip the render)"""
    sc.camera = cam
    sc.frame_set(frame)
    if NO_RENDER:
        return True
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return os.path.exists(path)


def save_results(name, extra=None):
    """<name>.json in out/ (a --no-render run writes <name>.norender.json and says so: its 'still' checks only built
    and posed the frame, they rendered nothing)"""
    RESULTS['seconds'] = round(time.time() - T0, 1)
    RESULTS['no_render'] = NO_RENDER
    if extra:
        RESULTS.update(extra)
    with open(os.path.join(OUT, name + ('.norender' if NO_RENDER else '') + '.json'), 'w', encoding='utf-8') as f:
        json.dump(RESULTS, f, indent=1, default=str)
    tail = ' (no render: built and posed, nothing rendered)' if NO_RENDER else ''
    print((f"{RESULTS['fails']} failed of {len(RESULTS['checks'])}" if RESULTS['fails'] else
           f"ALL PASS ({len(RESULTS['checks'])} checks)") + tail, flush=True)


def safe(rid):
    return rid.replace('/', '__').replace('\\', '__')


def angle_deg(u, v):
    return math.degrees(math.acos(max(-1.0, min(1.0, u.normalized().dot(v.normalized())))))
