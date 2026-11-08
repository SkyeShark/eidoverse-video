"""test_bin.py: builds THE BIN (eidoblend.sets.unknown_force.bin) headless, keys the film's bridge (its state on the
song clock and its four cameras with the film's pushes) at probe frames, checks what it keyed after jumping to each
frame, and renders the probes into out/bin_<n>_<shot>.png.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sets_uf_race_bin/test_bin.py -- [--build-only] [--res 960x540] [--samples 16]
        [--atlas 1] [--shots a,b] [--blend] [--singer [--vrm path]]

--singer puts the claudesona on the mark at the film's scale (claude_suit by default, --vrm for the film's own suit)
and tags the probes _singer.

Prints PASS / FAIL lines; exits 1 on a FAIL.
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend import common  # noqa: E402
from eidoblend.sets.unknown_force import bin as B  # noqa: E402

args = common.script_args()
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)


def arg(name, default=None):
    if name in args:
        i = args.index(name)
        return args[i + 1] if i + 1 < len(args) and not args[i + 1].startswith('--') else True
    return default


fails = []


def check(name, ok, info=''):
    print(('PASS' if ok else 'FAIL'), name, info, flush=True)
    if not ok:
        fails.append(name)


film_state = B.film_state      # the film's bin state on the song clock (scene.js setState('bin'))


# (song time, cam, push, shot start, shot end): the film's bin shots (B.FILM_SHOTS), the bridge and break 2's return
# ("the trash can's name is ideology"); the 'face' shot (243.5) frames her, so binWide stands in for it here
SHOTS = [(223.4, 'binWide', 2.0, 222.6, 227.8), (226.9, 'binWide', 2.0, 222.6, 227.8), (229.5, 'paperClose', 0, 227.8, 233.0),
         (234.6, 'climb', 0, 233.0, 238.1), (237.2, 'climb', 0, 233.0, 238.1), (239.2, 'topDown', 0, 238.1, 240.9),
         (242.0, 'climb', 0.3, 240.9, 243.5), (249.0, 'binWide', -3.0, 248.15, 258.6), (245.0, 'binWide', 0, 243.5, 248.15),
         (268.0, 'binWide', 4.0, 265.1, 272.0)]
only = arg('--shots')
if only and only is not True:
    SHOTS = [s for s in SHOTS if s[1] in only.split(',')]
scene = bpy.context.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
W, H = (int(v) for v in arg('--res', '960x540').split('x'))
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = W, H, 100
scene.render.fps = 24
t0 = time.time()
b = B.build(scene, atlas_scale=float(arg('--atlas', 1.0)), cache_dir=os.path.join(OUT, 'cache'))
print(f'[test_bin] build {time.time() - t0:.1f} s, objects {len(b.objects)}', flush=True)
check('build: can radius 1.88 m', abs(b.R - 1.8768) < 0.002, f'{b.R:.4f}')
check('build: can rim at 6.2 m', abs(b.parts['can'].dimensions.z - B.H) < 0.01, f'{b.parts["can"].dimensions.z:.3f}')
pj = os.path.join(OUT, 'parity', 'bin.json')
if os.path.isfile(pj):      # the placed pieces against bin.js (bin_parity_dump.mjs): lid, toppled can, lamp, lights
    import json
    J = json.load(open(pj))
    t3 = lambda v: Vector(B.to_blender(v))
    err = max((b.parts['toppled'].location - t3(J['toppled']['pos'])).length,
              (b.parts['lamp'].location - t3(J['lampPos'])).length)
    qj = J['lid']['q']
    ql = b.parts['lid'].rotation_quaternion
    qe = min(sum(abs(a - c) for a, c in zip(ql, B.quat_to_blender(qj))), sum(abs(a + c) for a, c in zip(ql, B.quat_to_blender(qj))))
    check('toppled can and lamp where bin.js puts them; the lid at its angle', err < 1e-3 and qe < 1e-3,
          f'pos {err:.1e}, lid rotation {qe:.1e}')
    # bin.js reads the lid's radius from a bounding box its scale() already scaled, then scales it again: its lid sits
    # about 12 m up, out of every shot. The port leans it against the can's front left, as BIN.md describes.
    lid_z = b.parts['lid'].location.z
    check('the lid leans against the can (BIN.md), not 12 m up (bin.js)', 0.5 < lid_z < 3.0 and J['lid']['pos'][1] > 10,
          f'port z {lid_z:.2f} m; bin.js y {J["lid"]["pos"][1]:.2f} m')
    b.update(230, {'climb': 1})                     # the dump's last update
    le = 0.0
    for k, v in J['lights'].items():
        if k == 'hemi':
            continue
        o = b.lights[k]
        le = max(le, (o.location - t3(v['pos'])).length)
        W = B.cd(v['i']) if o.data.type != 'SUN' else v['i']
        le = max(le, abs(o.data.energy - W) / max(1.0, W))
    check('lights at bin.js positions and intensities (4 pi I W)', le < 1e-3, f'max err {le:.1e}')
n_tri = sum(len(o.data.polygons) for o in b.objects if o.type == 'MESH')
print(f'[test_bin] triangles {n_tri}', flush=True)
if arg('--singer'):          # the claudesona riding the mark, at the film's scale (the cameras are framed for her)
    try:
        from eidoblend.characters import load_vrm, play_vrma_default
        h = load_vrm(arg('--vrm', 'claude_suit'), scene=scene)      # --vrm <path>: the film's own suit
        h.arm.parent = b.parts['mark']
        h.arm.matrix_parent_inverse.identity()
        h.arm.location, h.arm.scale = (0.0, 0.0, 0.0), (0.87, 0.87, 0.87)
        play_vrma_default(h, 'sing_low', t=0.0)
        print(f"[test_bin] singer on the mark ({os.path.basename(str(arg('--vrm', 'claude_suit')))} x 0.87, sing_low)", flush=True)
    except Exception as e:                      # a probe aid: the set renders without her
        print('[test_bin] singer not loaded:', e, flush=True)
cam = bpy.data.objects.new('probe_cam', bpy.data.cameras.new('probe_cam'))
scene.collection.objects.link(cam)
scene.camera = cam
frames = []
for i, (t, name, push, a, z) in enumerate(SHOTS):
    f = i + 1
    st = film_state(t)
    b.update(t, st, frame=f)
    b.key_camera(cam, name, frame=f, push=push, u=(t - a) / (z - a))
    frames.append((f, t, name, st))
b.finish()
scene.frame_start, scene.frame_end = 1, len(SHOTS)
print('[test_bin] render settings:', b.apply_render_settings(scene), flush=True)
scene.eevee.taa_render_samples = int(arg('--samples', 16))
worst = 0.0
for f, t, name, st in reversed(frames):
    scene.frame_set(f)
    c = st['climb']
    zt = B.lerp(b.Z_IN, b.Z_OUT, B.smooth(0, 1, c))
    want = Vector(B.to_blender((0, b._fill_y3(0, zt) + 0.03, zt)))
    worst = max(worst, (Vector(b.mark.location) - want).length)
check('keyed mark on the climb at its frame', worst < 1e-4, f'max err {worst:.2e}')
dg = bpy.context.evaluated_depsgraph_get()
scene.frame_set(1)
ev = b.falling.evaluated_get(bpy.context.evaluated_depsgraph_get())
zs = [v.co.z for v in ev.data.vertices]
check('falling paper GN: sheets between the floor and 23 m', min(zs) > -1 and max(zs) < 24.5 and max(zs) - min(zs) > 5,
      f'z {min(zs):.1f}..{max(zs):.1f}')
if arg('--blend'):
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'bin_probe.blend'), compress=True)
if not arg('--build-only'):
    scene.render.image_settings.file_format = 'PNG'
    tag = '_singer' if arg('--singer') else ''
    for f, t, name, st in frames:
        scene.frame_set(f)
        path = os.path.join(OUT, f'bin_{f:02d}_{name}_{t:.1f}{tag}.png')
        scene.render.filepath = path
        t2 = time.time()
        bpy.ops.render.render(write_still=True)
        check(f'render {name} @ {t}', os.path.isfile(path), f'{time.time() - t2:.1f} s')
print('[test_bin]', 'ALL PASS' if not fails else f'{len(fails)} FAIL: {fails}', flush=True)
sys.exit(1 if fails else 0)
