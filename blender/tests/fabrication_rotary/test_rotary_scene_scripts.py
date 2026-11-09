"""The harness scene scripts blender/eidoblend/fabrication/rotary/scenes/rotary.py and rotary_metal.py, run the way the
runner runs them (setup(ctx)), with a short duration and the outputs in out/scene_scripts/ (the real runner writes
beside its outputVideo). Checks every frame is keyed and has its stock file, and that the build plays from a saved
.blend reopened from disk, its motion-blur sub-frames showing their nearest frame's stock file. Nothing renders.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/fabrication_rotary/test_rotary_scene_scripts.py
"""

import importlib.util
import math
import os
import sys

import bpy

sys.dont_write_bytecode = True                  # no __pycache__ in the repository
bpy.context.preferences.filepaths.save_version = 0   # no .blend1 backups beside the saved builds
HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, BLENDER_DIR)
OUT = os.path.join(HERE, 'out', 'scene_scripts')
os.makedirs(OUT, exist_ok=True)
FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + detail) if detail else ''), flush=True)
    if not ok:
        FAILS.append(name)


class Ctx:
    """the parts of eidoblend.harness.context.Ctx the scene scripts use"""

    def __init__(self, scene, duration):
        self.scene, self.width, self.height, self.fps, self.duration = scene, 640, 450, 24, duration
        self.out_dir = OUT

    def log(self, *msg):
        print('[ctx]', *msg, flush=True)


for name in ('rotary', 'rotary_metal'):
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    path = os.path.join(BLENDER_DIR, 'eidoblend', 'fabrication', 'rotary', 'scenes', name + '.py')
    spec = importlib.util.spec_from_file_location('scene_' + name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sc = bpy.context.scene
    sc.frame_start = 1
    ctx = Ctx(sc, 1.5)
    mod.setup(ctx)
    frames = list(range(sc.frame_start, sc.frame_end + 1))
    cache = os.path.join(OUT, {'rotary': 'rotary_stock_cache', 'rotary_metal': 'rotary_metal_cache'}[name])
    files = [f for f in os.listdir(cache) if f.endswith('.vdb') and 'hold' not in f]
    check(f'scenes/{name}.py: setup(ctx) keys all {len(frames)} frames of a {ctx.duration} s film, one stock file each',
          len(frames) == 36 and len(files) == 36 and getattr(mod, '_no_auto_enhance', False))
    blend = os.path.join(OUT, name + '.blend')
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    stock = bpy.data.objects['Rotary volumetric stock']
    counts = []
    for f in (1, 18, 36):
        sc.frame_set(f)
        counts.append(len(stock.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices))
    vol = bpy.data.volumes[stock.modifiers['stock surface'].object.data.name]
    check(f'scenes/{name}.py: reopened from disk, the stock meshes at frames 1, 18, 36 ({counts} vertices) from '
          f'its file sequence ({vol.frame_duration} files, path {vol.filepath[:22]}...)',
          all(c > 1000 for c in counts) and vol.frame_duration == 36 and vol.filepath.startswith('//'))
    sub = []
    for x in (17.6, 18.0, 18.4):
        sc.frame_set(int(math.floor(x)), subframe=x - math.floor(x))
        me = stock.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
        co = [0.0] * (3 * len(me.vertices))
        me.vertices.foreach_get('co', co)
        sub.append((len(me.vertices), round(sum(co), 6)))
    drv = vol.animation_data.drivers.find('frame_offset') if vol.animation_data else None
    check(f'scenes/{name}.py: reopened, the motion-blur sub-frames 17.6 and 18.4 show frame 18\'s file (the sequence\'s '
          'nearest-frame driver, a simple expression, survives the save)',
          len(set(sub)) == 1 and drv is not None and drv.driver.is_simple_expression, f'{[s[0] for s in sub]}')
print('\n%d FAIL' % len(FAILS) if FAILS else '\nALL PASS')
