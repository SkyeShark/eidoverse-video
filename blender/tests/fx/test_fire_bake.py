"""The fire's bake (fx/fire.py): the same grids every time, and played so that the session that baked it renders it.

Checks (no render: the bakes run on the GPU through Blender's gpu module, as every fire bake does):
    repeat  the example's teapot fire (test_fire_teapot.py's scene: TeapotGeometry(0.8, 28) burning from its 26,912 raw
            vertices, several to a voxel) baked three times: every frame's grids byte-identical across the bakes, both
            as the GPU hands them to the .vdb writer (density, temperature, age) and as read back from the .vdb files
            (whose bytes differ only by the random file id OpenVDB writes into each). The engine's emission kernel let
            the points that share a voxel race for it (three bakes gave frame 1 a peak density of 3.26, 3.38 and
            3.38); fx.fire emits in two passes, a hash of the point's index and the substep drawing the point that
            stores.
    look    the first bake's total density and temperature over frames 1..12 against the engine's one-pass kernel on
            the same scene (RACY_*: the mean of six of its bakes, measured with fx/fire.py as it was before the two
            passes): within 15 %. Those six bakes spread from 0.95 to 1.03 of their mean over these frames; the store
            of the last point in buffer order measured 0.75 (a quarter less smoke), the first point's about twice.
    attach  in the session that baked: the Volume datablock carries no load error; the evaluated Volume (what a
            render's own copy of it starts from) loads its frame's grids and reports their bounds; a bake that starts
            after frame 1 asks for no file before its first frame or after its last, and leaves no error there.
    rebake  Blender keeps the grids of every .vdb it reads for the rest of the session, by path, so each bake above
            wrote its own stem (bakefire, bakefire_bake2, bakefire_bake3); one more bake, emitting nothing, and the
            Volume evaluated at a frame the session has played reads the new stem's frame and holds no voxels (over
            the first stem's files it went on playing the first bake's gas).
Renders: test_fire_shadows.py's fire case (baked and rendered in one session, the gas checked in its still),
test_fire_teapot.py (rendered from the saved .blend).

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/fx/test_fire_bake.py [-- frames=12 bakes=3]
"""

import hashlib
import math
import os
import sys
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
sys.path.insert(0, HERE)
from eidoblend.fx import fire as fxfire          # noqa: E402
from eidoblend.fx._util import from_three, frame_file  # noqa: E402
import _teapot                                     # noqa: E402

args = dict(a.split('=', 1) for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if '=' in a)
FRAMES = int(args.get('frames', 12))
BAKES = int(args.get('bakes', 3))
OUT = os.path.join(HERE, 'out', 'fire_bake')
os.makedirs(OUT, exist_ok=True)
FAILS = []
# the engine's one-pass emission on this scene, frames 1..12: the totals of the density and temperature grids (as the
# GPU hands them to the .vdb writer), the mean of six bakes
RACY_DENSITY = [26153, 26386, 26683, 26982, 27291, 27529, 27780, 28115, 28633, 29170, 29636, 30102]
RACY_TEMPERATURE = [11694, 11726, 11798, 11865, 11940, 11965, 11998, 12087, 12294, 12505, 12667, 12833]


def check(ok, what):
    print(f"[test_fire_bake] {'PASS' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILS.append(what)


# ---- the example's scene: floor height, teapot spinning on `frame`, key spot ----------------------------------------
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.render.fps = 24
sc.frame_start, sc.frame_end = 1, FRAMES
floor_z = 0.8
teapot, min_y = _teapot.teapot_object('teapot', 0.8, 28)
teapot.location = (0, 0, floor_z - min_y)
drv = teapot.driver_add('rotation_euler', 2).driver
drv.type = 'SCRIPTED'
drv.expression = '(4.0 + frame / 24 * 1.2) * 0.25'
kd = bpy.data.lights.new('key', 'SPOT')
kd.energy = 4 * math.pi * 1000.0
key = bpy.data.objects.new('key', kd)
sc.collection.objects.link(key)
key.location = tuple(from_three((-4.5, 15.4, 9.0)))
bpy.context.view_layer.update()

fire = fxfire.create_volume_fire(teapot, key_light=key, cache_dir=os.path.join(OUT, 'cache'), name='bakefire')
GX, GY, GZ = fire.G3
write_vdb = fire._write_vdb
raw = {}                                         # frame -> sha1 of the grids the GPU handed to the .vdb writer


def hashing_write(vdb, frame, arr):
    raw[frame] = hashlib.sha1(np.ascontiguousarray(arr[..., :3]).tobytes()).hexdigest()
    raw[('peak', frame)] = float(arr[..., 0].max())
    raw[('totals', frame)] = (float(arr[..., 0].astype(np.float64).sum()), float(arr[..., 1].astype(np.float64).sum()))
    return write_vdb(vdb, frame, arr)


fire._write_vdb = hashing_write


def read_back(frame):
    """sha1 of the frame's grids as read from its .vdb (each grid copied out dense, in Blender's x, y, z), and the
    sha1 of the file's bytes"""
    import openvdb as vdb
    path = frame_file(fire.cache_dir, fire.stem, frame, 'vdb')
    h = hashlib.sha1()
    for g in sorted(vdb.readAll(path)[0], key=lambda g: g.name):
        a = np.zeros((GX, GZ, GY), np.float32)
        g.copyToArray(a, ijk=(0, 0, 0))
        h.update(g.name.encode())
        h.update(a.tobytes())
    with open(path, 'rb') as f:
        return h.hexdigest(), hashlib.sha1(f.read()).hexdigest()


runs = []
for k in range(BAKES):
    raw.clear()
    t0 = time.time()
    fire.bake(1, FRAMES, log=(print if k == 0 else (lambda *_a, **_k: None)))
    files = {f: read_back(f) for f in range(1, FRAMES + 1)}
    runs.append(({f: raw[f] for f in range(1, FRAMES + 1)}, {f: files[f][0] for f in files},
                 {f: files[f][1] for f in files}, raw[('peak', 1)]))
    print(f'[test_fire_bake] bake {k + 1}: {FRAMES} frames in {time.time() - t0:.1f} s, frame 1 peak density '
          f'{raw[("peak", 1)]:.4f}, frame {FRAMES} grids {runs[-1][0][FRAMES][:12]}', flush=True)
    if k == 0:
        # ---- look: the bake against the engine's racy kernel -----------------------------------------------------------
        fr = range(1, min(FRAMES, len(RACY_DENSITY)) + 1)
        rd = [raw[('totals', f)][0] / RACY_DENSITY[f - 1] for f in fr]
        rt = [raw[('totals', f)][1] / RACY_TEMPERATURE[f - 1] for f in fr]
        check(abs(np.mean(rd) - 1) < 0.15 and abs(np.mean(rt) - 1) < 0.15,
              f'the look of the engine\'s racy kernel kept over frames 1..{fr[-1]}: total density {np.mean(rd):.3f} and '
              f'temperature {np.mean(rt):.3f} of its six bakes\' mean (frame by frame {min(rd):.3f} .. {max(rd):.3f} '
              f'and {min(rt):.3f} .. {max(rt):.3f})')
        # ---- attach: the session that baked renders what it baked -----------------------------------------------------
        vol = fire.volume_object.data
        check(vol.grids.error_message == '' and not vol.grids.is_loaded,
              f'the Volume datablock holds no grids and no load error after the bake '
              f'(error {vol.grids.error_message!r})')
        sc.frame_set(FRAMES)
        dg = bpy.context.evaluated_depsgraph_get()
        ev = fire.volume_object.evaluated_get(dg)
        ok = ev.data.grids.load()
        names = sorted(g.name for g in ev.data.grids)
        bb = np.array([tuple(v) for v in ev.bound_box])
        lo, hi = fire._domain_box()
        leaf = 8 * fire.W3[0] / fire.G3[0]       # Blender bounds a volume by its grids' leaf nodes, 8 voxels a side
        size = bb.max(axis=0) - bb.min(axis=0)
        check(ok and names == ['age', 'density', 'temperature'] and (size > 0.5).all()
              and (bb.min(axis=0) >= lo - leaf).all() and (bb.max(axis=0) <= hi + leaf).all(),
              f'the evaluated Volume (a render\'s copy starts from it) loads frame {FRAMES}: load() {ok}, grids {names}, '
              f'bounds {np.round(bb.min(axis=0), 2).tolist()} .. {np.round(bb.max(axis=0), 2).tolist()} in the domain '
              f'{np.round(lo, 2).tolist()} .. {np.round(hi, 2).tolist()} (to the leaf nodes, {leaf:.2f} m)')

check(all(r[0] == runs[0][0] for r in runs[1:]),
      f'{BAKES} bakes, the grids the GPU hands to the .vdb writer byte-identical in all {FRAMES} frames '
      f'(frame 1 peak density {", ".join(f"{r[3]:.4f}" for r in runs)})')
check(all(r[1] == runs[0][1] for r in runs[1:]),
      f'{BAKES} bakes, the grids read back from the .vdb files byte-identical in all {FRAMES} frames')
same_files = sum(r[2][f] == runs[0][2][f] for r in runs[1:] for f in r[2])
print(f'[test_fire_bake] the .vdb files\' bytes: {same_files} of {(BAKES - 1) * FRAMES} identical to the first bake\'s '
      '(OpenVDB writes a random id into every file)', flush=True)
print('[test_fire_bake] frame grids sha1: ' + ' '.join(f'{f}:{runs[0][0][f][:10]}' for f in (1, FRAMES)), flush=True)

# ---- a bake from frame 3 (the same files): no file is asked for outside 3..FRAMES --------------------------------------
fs = 3
fire._attach_sequence(fs, FRAMES)
seen = {}
for f in (1, fs - 1, fs, FRAMES, FRAMES + 1):
    sc.frame_set(f)
    ev = fire.volume_object.evaluated_get(bpy.context.evaluated_depsgraph_get())
    g = ev.data.grids
    ok = g.load()
    seen[f] = (ok, len(g), os.path.basename(g.frame_filepath) if len(g) else '', g.error_message)
inside = all(seen[f][0] and seen[f][1] == 3 and seen[f][2] == f'{fire.stem}_{f:04d}.vdb' and not seen[f][3]
             for f in (fs, FRAMES))
outside = all(seen[f][0] and seen[f][1] == 0 and not seen[f][3] for f in (1, fs - 1, FRAMES + 1))
check(inside and outside and fire.volume_object.data.grids.error_message == '',
      f'a bake of frames {fs}..{FRAMES}: frames {fs} and {FRAMES} play their own files, frames 1, {fs - 1} and '
      f'{FRAMES + 1} ask for none and leave no error: ' + ', '.join(f'{f}: {s[1]} grids {s[2] or "-"}'
                                                                   f'{" " + repr(s[3]) if s[3] else ""}'
                                                                   for f, s in seen.items()))

# ---- rebake: a fire baked again in the session plays its new frames ----------------------------------------------------
stems = [fire._stem_of_bake(k) for k in range(1, BAKES + 1)]
fire.bake(1, FRAMES, log=lambda *_a, **_k: None,
          controls=lambda f, t: {'emit_density': 0.0, 'emit_temperature': 0.0, 'warmup_seconds': 0.0})
sc.frame_set(FRAMES)
ev = fire.volume_object.evaluated_get(bpy.context.evaluated_depsgraph_get())
ok = ev.data.grids.load()
played = os.path.basename(ev.data.grids.frame_filepath)
extent = np.ptp(np.array([tuple(v) for v in ev.bound_box]), axis=0)
wrote = {p.rsplit('_', 1)[0] for p in os.listdir(fire.cache_dir) if p.endswith('.vdb')}
check(ok and extent.max() < 1e-6 and fire.stem == fire._stem_of_bake(BAKES + 1)
      and played == f'{fire.stem}_{FRAMES:04d}.vdb' and set(stems) <= wrote,
      f'a fire baked again in the session plays its new frames: the bakes wrote {", ".join(stems)}, then {fire.stem} '
      f'(nothing emitted); at frame {FRAMES} the Volume reads {played} (load {ok}) and holds '
      + ('no voxels' if extent.max() < 1e-6 else
         f'voxels over {np.round(extent, 2).tolist()} m (grids an earlier bake wrote, played again)'))
print(f'[test_fire_bake] {"FAIL" if FAILS else "PASS"}: {len(FAILS)} failed check(s)')
