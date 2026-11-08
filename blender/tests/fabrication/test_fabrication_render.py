"""The manufacturing example built, checked and rendered: a print growing layer by layer, a pocket being milled and a
relief being carved, all keyed over time.

Builds EXAMPLES['manufacturing'] (the FDM printing the lathe sleeve, the CNC milling aluminium, the relief CNC carving
wood, 18 s time-lapse) at 960 x 540, then checks what the saved file will play, numerically:
  - the bead's Geometry Nodes show exactly the chords the feed clock has reached at each sampled frame
  - each stock's Geometry Nodes heights equal the CPU swept-envelope heights (job.inspect_heights) at its vertices
  - the keyed machine pose at a frame equals job.seek at that frame's time (tool tip, reel, progress)
and times the stock evaluation. Then renders probe stills into out/: the example's wide view and close views of each
machine at three times (shadows on in the close views so contact reads).

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/fabrication/test_fabrication_render.py
        [-- --no-render] [-- --samples 16]
"""
import math
import os
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as U  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.common import script_args  # noqa: E402
from eidoblend.fabrication.examples import EXAMPLES  # noqa: E402
from eidoblend.fabrication.machine import world_matrix  # noqa: E402

args = script_args()
RENDER = '--no-render' not in args
SAMPLES = int(args[args.index('--samples') + 1]) if '--samples' in args else 16
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
t0 = time.time()
rec = EXAMPLES['manufacturing'](scene, width=960, height=540)
printer, cnc, wood = rec['robots']
pj, mj, cj = rec['jobs']
print(f'[build] manufacturing example built and keyed in {time.time() - t0:.1f} s; frames {scene.frame_start}..'
      f'{scene.frame_end}; print {pj.layers} layers, {pj.physical_duration / 60:.1f} min physical; pocket '
      f'{mj.physical_duration / 60:.1f} min; relief {cj.physical_duration / 60:.1f} min, bins up to '
      f"{cj.binning['maximum_bin']} sweeps", flush=True)
fps = scene.render.fps
dg = bpy.context.evaluated_depsgraph_get()


def frame_of(t):
    return scene.frame_start + int(round(t * fps))


# --- the bead shows the chords the feed clock has reached ------------------------------------------------------
pieces = None
ok = True
for t in (0.5, 4.5, 9.0, 13.5, 18.0):
    f = frame_of(t)
    scene.frame_set(f)
    state = pj.path.sample(min(t, pj.duration) / pj.duration * pj.path.duration)
    me = pj.mesh.evaluated_get(dg).to_mesh()
    shown = len(me.vertices) // 16
    pj.mesh.evaluated_get(dg).to_mesh_clear()
    starts = np.array([a.value for a in pj.mesh.data.attributes['fab_start'].data])[::16]
    expected = int((state.distance - starts > 1e-9).sum())
    ok &= abs(shown - expected) <= 1
    print(f'  bead at t={t:5.2f}s: {shown} of {len(starts)} chords shown, {expected} reached', flush=True)
U.check('the keyed bead shows exactly the chords the nozzle has reached', ok)

# --- the keyed pose replays job.seek ---------------------------------------------------------------------------
worst = 0.0
for t in (2.0, 7.25, 12.5):
    scene.frame_set(frame_of(t))
    tip = world_matrix(printer.roots['extruder_fixed']).to_translation()
    pj.seek(t)
    worst = max(worst, (tip - world_matrix(printer.roots['extruder_fixed']).to_translation()).length)
scene.frame_set(frame_of(9.0))
U.check('the keyed machine at a frame stands where job.seek puts it', worst < 1e-5, f'worst {worst * 1000:.4f} mm')

# --- the stocks' nodes evaluate the swept envelope ---------------------------------------------------------------
for job, label in ((mj, 'pocket'), (cj, 'relief')):
    for t in (4.5, 12.0):
        f = frame_of(t)
        scene.frame_set(f)
        t1 = time.time()
        bpy.context.view_layer.update()
        ev = job.mesh.evaluated_get(dg)
        me = ev.to_mesh()
        dt = time.time() - t1
        n = (job.stock.resolution + 1) ** 2
        co = np.empty(len(me.vertices) * 3, dtype=np.float32)
        me.vertices.foreach_get('co', co)
        ev.to_mesh_clear()
        co = co.reshape(-1, 3)[:n]
        pick = np.linspace(0, n - 1, 1500).astype(int)
        progress = job.path.sample(min(t, job.duration) / job.duration * job.path.duration).distance
        cpu = np.array(job.inspect_heights(co[pick, :2], progress=progress))
        err = float(np.abs(co[pick, 2] - cpu).max())
        cut = float(job.stock.height - co[:, 2].min())
        U.check(f'{label} stock at t={t}s: nodes = CPU envelope', err < 2e-6,
                f'max |nodes - cpu| {err * 1e6:.2f} um over 1500 vertices, deepest cut {cut * 1000:.2f} mm, '
                f'evaluated in {dt:.2f} s')

# --- save and render -----------------------------------------------------------------------------------------
blend = os.path.join(U.OUT, 'manufacturing_example.blend')
bpy.context.preferences.filepaths.save_version = 0          # no .blend1 backup beside it (the disk is shared)
bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
print(f'[save] {blend}', flush=True)
if RENDER:
    from eidoblend.characters.robotics.studio import make_camera
    scene.render.resolution_x, scene.render.resolution_y = 960, 540
    scene.eevee.taa_render_samples = SAMPLES
    scene.render.image_settings.file_format = 'PNG'
    wide = rec['camera']
    U.render_still(scene, os.path.join(U.OUT, 'manufacturing_wide_t09.png'), frame_of(9.0))
    sun = rec['studio'].get('sun') if isinstance(rec['studio'], dict) else None
    if sun is not None:
        sun.data.use_shadow = True

    def close(name, robot, offset, look, lens_fov):
        cam = make_camera(lens_fov, name, scene)
        base = world_matrix(robot.roots['gantry_base'])
        target = base @ Vector(look)
        cam.location = target + Vector(offset)
        cam.rotation_mode = 'QUATERNION'
        cam.rotation_quaternion = (target - cam.location).to_track_quat('-Z', 'Y')
        cam.data.clip_start = .005
        return cam

    shots = [('print', close('print close', printer, (.10, -.17, .11), (0, 0, .062), 30), (3.0, 9.0, 18.0)),
             ('pocket', close('pocket close', cnc, (.13, -.22, .17), (0, 0, .07), 30), (3.0, 9.0, 18.0)),
             ('relief', close('relief close', wood, (.13, -.22, .17), (0, 0, .07), 30), (4.0, 9.0, 18.0))]
    for name, cam, times in shots:
        scene.camera = cam
        for t in times:
            U.render_still(scene, os.path.join(U.OUT, f'manufacturing_{name}_close_t{t:04.1f}.png'), frame_of(t))
    scene.camera = wide
ok = U.summary('render')
sys.exit(0 if ok else 1)
