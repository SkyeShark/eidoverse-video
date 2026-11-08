"""Builds the two WebGPU rotary examples in Blender (eidoverse/examples/robotics/rotary.scene.js, rotary_metal.scene.js)
through EXAMPLES, keys a probe's frames, checks the build numerically and saves each as a .blend that plays on its own:
out/rotary_example.blend and out/rotary_metal_example.blend (the stock's VDB files beside them). Nothing renders here;
render_rotary_probes.py renders the saved files through the GPU slot.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/fabrication_rotary/test_rotary_examples.py \
        [-- examples=rotary,rotary_metal frames=all|1,25,121 res=256,96,96 suffix=_full material=brass]

Default frames: the WebGPU renderFrame times a reviewer looks at (the hold, the first passes, mid-roughing, the
finish, the end; for the metal study the setup, physical-speed cutting and the time lapse). material= builds the
metal study in another preset (the example's own suggestion: brass). Prints PASS / FAIL.
"""

import math
import os
import sys
import time

import bpy
from mathutils import Vector

sys.dont_write_bytecode = True                  # no __pycache__ in the repository
bpy.context.preferences.filepaths.save_version = 0   # no .blend1 backups beside the saved builds
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.fabrication.rotary.examples import EXAMPLES, metal_time      # noqa: E402

args = dict(a.split('=', 1) for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if '=' in a)
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
NAMES = args.get('examples', 'rotary,rotary_metal').split(',')
RES = tuple(int(v) for v in args.get('res', '256,96,96').split(','))
SUFFIX = args.get('suffix', '')                 # e.g. suffix=_full: out/rotary_full_example.blend, its own cache
MATERIAL = args.get('material')                 # rotary_metal only: 'brass', 'steel' ...
FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + detail) if detail else ''), flush=True)
    if not ok:
        FAILS.append(name)


def frames_for(name, fps=24):
    if args.get('frames') == 'all':
        return None
    if args.get('frames'):
        return [int(v) for v in args['frames'].split(',')]
    times = (0, 1.5, 3, 6, 10, 14, 18, 22, 26, 29, 30.9) if name == 'rotary' else (0, 1, 2.5, 5, 9.5, 12, 18, 24, 28.5, 31.9)
    return [1 + int(round(t * fps)) for t in times]


def reset():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.node_groups, bpy.data.volumes, bpy.data.actions,
                 bpy.data.lights, bpy.data.cameras, bpy.data.images, bpy.data.worlds):
        for d in list(coll):
            if d.users == 0:
                coll.remove(d)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)


for name in NAMES:
    reset()
    blend = os.path.join(OUT, f'{name}{SUFFIX}_example.blend')
    bpy.ops.wm.save_as_mainfile(filepath=blend)                     # the stock cache sits beside the .blend
    frames = frames_for(name)
    t0 = time.time()
    extra = {'material': MATERIAL} if MATERIAL and name == 'rotary_metal' else {}
    rec = EXAMPLES[name](bpy.context.scene, frames=frames, cache_dir=f'//{name}{SUFFIX}_stock_cache', resolution=RES,
                         **extra)
    dt = time.time() - t0
    sc, job, machine = rec.scene, rec.job, rec.machine
    keyed = frames or list(range(sc.frame_start, sc.frame_end + 1))
    check(f'{name}: built {len(keyed)} keyed frames in {dt:.1f} s ({job.program.path.duration:.0f} s physical, '
          f'{sum(1 for s in job.path.segments if s["type"] == "cut")} cutting strokes, {len(job.removal.events)} chip '
          f'events)', True)
    cfg = {'rotary': (1280, 900, 24, 31), 'rotary_metal': (1280, 900, 24, 32)}[name]
    check(f'{name}: the WebGPU config (1280 x 900, 24 fps, {cfg[3]} s)', (sc.render.resolution_x, sc.render.resolution_y,
          sc.render.fps, sc.frame_end - sc.frame_start + 1) == (cfg[0], cfg[1], cfg[2], cfg[3] * cfg[2]))
    # the build plays on its own: jump to each keyed frame and read the machine and the stock back from the scene
    fps = sc.render.fps
    worst_tip = worst_a = 0.0
    for f in keyed:
        sc.frame_set(f)
        t = (f - sc.frame_start) / fps
        want = max(0.0, t - 1) if name == 'rotary' else metal_time(t, rec.cutting_start, job.duration)
        st = job.path.sample(min(want, job.duration) / job.duration * job.path.duration)
        p = Vector((st['position'][0] + job.settings['axis_x'], st['position'][1],
                    st['position'][2] + job.settings['axis_height']))
        worst_tip = max(worst_tip, (machine.tool_tip() - p).length)
        chuck = machine.roots['rotary_chuck']
        rel = machine.roots['rotary_fixture'].matrix_world.inverted() @ chuck.matrix_world
        a = math.atan2(rel[2][1], rel[1][1])
        da = (a - st['angle'] + math.pi) % (2 * math.pi) - math.pi
        worst_a = max(worst_a, abs(da))
    check(f'{name}: jumping to each keyed frame, the tool tip is where the program says', worst_tip < 1e-5,
          f'worst {worst_tip * 1000:.4f} mm')
    check(f'{name}: and the chuck (and the stock on it) is at the program\'s A angle', worst_a < 1e-5,
          f'worst {worst_a:.2e} rad')
    # the stock surface at the last keyed frame is meshed from that frame's file
    sc.frame_set(keyed[-1])
    dg = bpy.context.evaluated_depsgraph_get()
    me = job.stock.mesh.evaluated_get(dg).data
    check(f'{name}: the stock surface meshes from the frame\'s VDB file ({len(me.vertices)} vertices)',
          len(me.vertices) > 1000 and os.path.exists(job.stock.frame_path(keyed[-1])))
    sc.frame_set(keyed[0])
    me0 = job.stock.mesh.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
    check(f'{name}: and the first frame shows the uncut blank (8 corners kept)', len(me0.vertices) > 100)
    size = sum(os.path.getsize(job.stock.frame_path(f)) for f in keyed) / len(keyed)
    check(f'{name}: {size / 1e6:.2f} MB of stock field per keyed frame', size < 6e6)
    if name == 'rotary_metal':
        check('rotary_metal: the physical-speed window starts at the first chip event '
              f'({rec.cutting_start:.2f} s) and the program takes {job.physical_duration / 3600:.2f} h',
              rec.cutting_start > 2 and job.physical_duration > 20000)
    sc.frame_set(sc.frame_start)
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
    print('saved', blend, flush=True)

print('\n%d FAIL' % len(FAILS) if FAILS else '\nALL PASS')
