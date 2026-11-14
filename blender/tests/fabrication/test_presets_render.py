"""The presets and samples rendered: every stock material milled, every manufacturing sample printed, a free PTFE tube.

  materials   the CNC milling the default pocket in aluminum, brass, steel, hardwood and birch plywood, each seen
              mid-cut (chips in the air, the finish on the cut walls and floor) at 55 % of its job
  samples     the FDM printing the three manufacturing samples side by side on the PEI sheet (the offset handle, the
              fork bracket with its bore, the torus-knot ring): one frame finished, one with the ring half printed
  tube        the guide's free PTFE tube (create_ptfe_tube) with a filament core through it, on its own

Checks (numeric): each material's removed volume, chip count alive at the probe time, and the slicer's contours for
each sample. Renders land in out/presets_*.png (960 x 540, shadows on).

    bash run_blender.sh blender/tests/fabrication/test_presets_render.py [-- --no-render]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)
"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as U  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend import fabrication as fab  # noqa: E402
from eidoblend.characters.robotics import make_robot  # noqa: E402
from eidoblend.characters.robotics.studio import make_camera, studio  # noqa: E402
from eidoblend.common import script_args  # noqa: E402
from eidoblend.fabrication.machine import world_matrix  # noqa: E402

RENDER = '--no-render' not in script_args()
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 24
st = studio(scene, grid=False, shadows=True)
U.render_settings(scene, 960, 540, 16)
scene.view_settings.view_transform = 'AgX'


def aim(cam, robot, offset, look):
    target = world_matrix(robot.roots['gantry_base']) @ Vector(look)
    cam.location = target + Vector(offset)
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (target - cam.location).to_track_quat('-Z', 'Y')
    cam.data.clip_start = .005
    scene.camera = cam


# --- materials ---------------------------------------------------------------------------------------------------
cnc = make_robot('cnc', scene=scene)
cam = make_camera(28, 'material camera', scene)
aim(cam, cnc, (.11, -.16, .12), (0, 0, .07))
for material in fab.STOCK_MATERIALS:
    job = fab.mill(cnc, None, material=material, duration=18, resolution=160)
    t = 18 * .55
    job.seek(t)
    bpy.context.view_layer.update()
    alive = sum(len(p.object.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh().vertices) > 0
                for p in job.effects.pools)
    U.check(f'{material}: pocket cut and debris live at 55 %', job.stock.removed_volume > 0,
            f'{job.stock.removed_volume * 1e6:.2f} cm3 removed in all, {job.physical_duration / 60:.1f} min, '
            f"{job.settings.chip_load * 1e6:.1f} um chip load, pools {[p.name for p in job.effects.pools]}")
    if RENDER:
        U.render_still(scene, os.path.join(U.OUT, f'presets_material_{material}.png'))
    job.dispose()
for o in list(cnc.collection.all_objects):
    o.hide_render = True

# --- samples -----------------------------------------------------------------------------------------------------
printer = make_robot('fdm', scene=scene, position=(1.5, 0, 0), filament='#d9822b')
jobs = []
for name, center in (('handle', (-.055, .02)), ('bracket', (.0, -.03)), ('ring', (.06, .02))):
    src = fab.manufacturing_sample(name, as_parts=True)
    job = fab.print(printer, src, size=.04, center=center, infill=.2, duration=12)
    U.check(f'sample {name}: sliced and printable', job.layers > 0,
            f"{job.layers} layers, {len(job.spec['contours'])} contours, {job.filament_length:.2f} m of filament, "
            f'{job.physical_duration / 60:.1f} min')
    jobs.append(job)
for j in jobs:
    j.seek(12)
cam2 = make_camera(30, 'samples camera', scene)
aim(cam2, printer, (.09, -.20, .15), (0, 0, .062))
if RENDER:
    U.render_still(scene, os.path.join(U.OUT, 'presets_samples_printed.png'))
jobs[2].seek(6)
if RENDER:
    U.render_still(scene, os.path.join(U.OUT, 'presets_samples_ring_half.png'))
for o in list(printer.collection.all_objects):
    o.hide_render = True

# --- a free PTFE tube --------------------------------------------------------------------------------------------
tube = fab.create_ptfe_tube(points=[(0, 0, 0), (0, 0, .20), (.12, 0, .20), (.12, 0, 0)], outer_diameter=.004,
                            inner_diameter=.002, segments=48, color='#e7eee5')
core = fab.create_ptfe_tube(points=[(0, 0, 0), (0, 0, .20), (.12, 0, .20), (.12, 0, 0)], outer_diameter=.00175,
                            inner_diameter=0, segments=48, color='#218675')
for t_ in (tube, core):
    t_.mesh.location = (3.0, 0, 0)
U.check('free tube: length of its cubic', abs(tube.length - fab.bezier_length(tube.points)) < 1e-12,
        f'{tube.length * 1000:.1f} mm')
cam3 = make_camera(30, 'tube camera', scene)
cam3.location = Vector((3.06, -.36, .16))
cam3.rotation_mode = 'QUATERNION'
cam3.rotation_quaternion = (Vector((3.06, 0, .11)) - cam3.location).to_track_quat('-Z', 'Y')
scene.camera = cam3
if RENDER:
    U.render_still(scene, os.path.join(U.OUT, 'presets_ptfe_tube.png'))
ok = U.summary('presets')
sys.exit(0 if ok else 1)
