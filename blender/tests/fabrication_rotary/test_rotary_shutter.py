"""Motion blur on the rotary films: what each frame's shutter sees, read from the scene data at the sub-frames the
renderer samples (no render). The examples are time lapses (the wood carving plays 38 minutes of program in 28 s; the
metal study jumps from setup to its first chip at 2 s, then plays hours in 18 s), so keys at whole frames alone made
the shutter sample the straight line between poses seconds of program apart. Checks, for both examples built at a
small stock resolution (and a short job played with START and END shutters):

  the machine     the cutter tip and the A axis inside a 1/2-frame and a 31/32-frame shutter are where the program
                  puts them at the physical moments of a real-time exposure (a time-lapse frame is crisp, a held frame
                  still); the straight line to the next frame is printed beside it for scale
  held            the spindle and the chips' clock do not change inside a shutter
  the camera      still inside every frame's shutter, the metal study's cuts at 2 s and 28 s included
  the stock       every sample within half a frame of a keyed frame shows that frame's VDB file
  the keys        the bracket keys are LINEAR and sit at the offsets shutter_offsets() gives

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/fabrication_rotary/test_rotary_shutter.py
"""

import math
import os
import shutil
import sys

import bpy
from mathutils import Vector

sys.dont_write_bytecode = True                  # no __pycache__ in the repository
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from bpy_extras import anim_utils  # noqa: E402

from eidoblend.characters.robotics import make_robot  # noqa: E402
from eidoblend.fabrication._nodes import modifier_input  # noqa: E402
from eidoblend.fabrication.rotary import rotary_carve, sample_rotary  # noqa: E402
from eidoblend.fabrication.rotary.carve import SHUTTER_SPAN, cut_offset, shutter_offsets  # noqa: E402
from eidoblend.fabrication.rotary.examples import EXAMPLES, metal_time  # noqa: E402

OUT = os.path.join(HERE, 'out', 'shutter')
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT, exist_ok=True)
RES = (64, 32, 32)
FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + detail) if detail else ''), flush=True)
    if not ok:
        FAILS.append(name)


def reset():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.node_groups, bpy.data.volumes, bpy.data.actions,
                 bpy.data.cameras, bpy.data.lights):
        for d in list(coll):
            if d.users == 0:
                coll.remove(d)


def at(sc, x):
    """jump to film frame x (a sub-frame too), as a motion-blur step does"""
    f = math.floor(x)
    sc.frame_set(int(f), subframe=x - f)


def chuck_angle(machine):
    rel = machine.roots['rotary_fixture'].matrix_world.inverted() @ machine.roots['rotary_chuck'].matrix_world
    return math.atan2(rel[2][1], rel[1][1])


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def stock_sig(job):
    me = job.stock.mesh.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
    n = len(me.vertices)
    if not n:
        return (0, 0.0)
    co = [0.0] * (3 * n)
    me.vertices.foreach_get('co', co)
    s = sum(co[i] * (1.3, 1.7, 2.9)[i % 3] for i in range(0, 3 * n, 7))
    return (n, round(s, 9))


def expected_tip(job, physical):
    s = job.settings
    st = job.path.sample(min(max(physical, 0.0), job.physical_duration))
    return Vector((st['position'][0] + s['axis_x'], st['position'][1], st['position'][2] + s['axis_height'])), \
        st['angle']


def shutter_report(name, rec, clock, frames, shutters=(0.5, 2 * SHUTTER_SPAN)):
    """for every keyed frame and shutter width: the tip and A axis at the shutter's ends against the program's
    physical exposure, the camera, the held channels and the stock file"""
    sc, job, machine, cam = rec.scene, rec.job, rec.machine, rec.camera
    fps = sc.render.fps / sc.render.fps_base
    rotor = machine.roots['spindle_rotor']
    pools = job.debris.pools
    worst_tip = worst_a = worst_cam = worst_spin = worst_chip = 0.0
    held_travel = 0.0
    stock_ok = True
    lines = []
    for f in frames:
        t = (f - sc.frame_start) / fps
        rate = min(1.0, job.clock_rate(clock, t))
        t_phys = min(max(clock(t), 0.0), job.duration) / job.duration * job.physical_duration
        at(sc, f)
        tip0, a0 = machine.tool_tip(), chuck_angle(machine)
        cam0 = cam.matrix_world.copy()
        rot0 = rotor.matrix_basis.to_quaternion()
        chip0 = [modifier_input(p.modifier, 'Time').value for p in pools]
        sig0 = stock_sig(job)
        for s in shutters:
            travel = 0.0
            for side in (-1, 1):
                x = f + side * s / 2
                at(sc, x)
                want, want_a = expected_tip(job, t_phys + side * s / 2 / fps * rate)
                tip = machine.tool_tip()
                worst_tip = max(worst_tip, (tip - want).length)
                worst_a = max(worst_a, abs(wrap(chuck_angle(machine) - want_a)))
                worst_cam = max(worst_cam, max(abs(cam.matrix_world[i][j] - cam0[i][j]) for i in range(4)
                                               for j in range(4)))
                worst_spin = max(worst_spin, rotor.matrix_basis.to_quaternion().rotation_difference(rot0).angle)
                worst_chip = max(worst_chip, max([abs(modifier_input(p.modifier, 'Time').value - c)
                                                  for p, c in zip(pools, chip0)] or [0.0]))
                travel = max(travel, (tip - tip0).length)
                if rate == 0:
                    held_travel = max(held_travel, (tip - tip0).length, abs(wrap(chuck_angle(machine) - a0)))
                if stock_sig(job) != sig0:
                    stock_ok = False
            if s == 0.5:
                # for scale: where the old whole-frame keys put the shutter's end, a straight line to the next frame
                t1 = (f + 1 - sc.frame_start) / fps
                nxt, _a = expected_tip(job, min(max(clock(t1), 0.0), job.duration) / job.duration *
                                       job.physical_duration)
                lines.append(f'f{f} (t {t:.2f} s, program {t_phys:.1f} s, rate {rate:.2f}): tip moves '
                             f'{travel * 1000:.3f} mm in a 1/2-frame shutter (the straight line to the next frame would '
                             f'give {(nxt - tip0).length * 1000 * .25:.2f} mm)')
    for ln in lines:
        print('   ', ln)
    check(f'{name}: inside every shutter (1/2 and 31/32 frame) the cutter tip is where the program is at the '
          'exposure\'s physical moments', worst_tip < 2e-4, f'worst {worst_tip * 1000:.4f} mm')
    check(f'{name}: and the chuck (and the stock on it) at the program\'s A angle', worst_a < 2e-3,
          f'worst {math.degrees(worst_a):.4f} deg')
    check(f'{name}: held frames do not move inside their shutter', held_travel < 1e-7, f'{held_travel:.2e}')
    check(f'{name}: the camera is still inside every frame\'s shutter', worst_cam < 1e-9, f'{worst_cam:.2e}')
    check(f'{name}: the spindle and the chips\' clock hold their frame\'s state inside the shutter',
          worst_spin < 1e-5 and worst_chip < 1e-9, f'spindle {worst_spin:.1e} rad, chips {worst_chip:.1e} s')
    check(f'{name}: every shutter sample shows its frame\'s stock file', stock_ok)


# --------------------------------------------------------------------------------------- the wood example ---
reset()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'shutter_rotary.blend'))
sc = bpy.context.scene
WOOD = [5, 25, 71, 72, 433, 434, 696, 720]
rec = EXAMPLES['rotary'](sc, frames=WOOD, cache_dir='//shutter_rotary_cache', resolution=RES)
print('wood: program', round(rec.job.physical_duration, 1), 's over', rec.job.duration, 's of film')
check('shutter_offsets: CENTER brackets each frame by 31/64 of a frame, a camera cut keys half a frame before',
      shutter_offsets(sc) == (-31 / 64, 31 / 64) and cut_offset(sc) == -0.5)
gx = rec.machine.roots['gantry_x']
cb = anim_utils.action_get_channelbag_for_slot(gx.animation_data.action, gx.animation_data.action_slot)
pts = [kp for fc in cb.fcurves for kp in fc.keyframe_points]
want_x = sorted({round(f + d, 6) for f in WOOD for d in (-31 / 64, 0.0, 31 / 64)})
got_x = sorted({round(kp.co.x, 6) for kp in pts})
check('the keys: each keyed frame has its bracket (f - 31/64, f, f + 31/64), all LINEAR',
      got_x == want_x and all(kp.interpolation == 'LINEAR' for kp in pts),
      f'{len(got_x)} key times')
shutter_report('rotary', rec, lambda t: max(0.0, t - 1), WOOD)
# the stock file at sub-frames between two consecutive keyed frames in mid-cut: the nearest frame's file
at(sc, 433)
s_a = stock_sig(rec.job)
at(sc, 434)
s_b = stock_sig(rec.job)
picks = []
for x in (432.6, 433.25, 433.49, 433.51, 433.75, 434.4):
    at(sc, x)
    picks.append({s_a: 433, s_b: 434}.get(stock_sig(rec.job), '?'))
check('the stock: frames 433 and 434 (mid-cut) hold different files, and sub-frames show the nearest one '
      '(432.6, 433.25, 433.49 -> 433; 433.51, 433.75, 434.4 -> 434; Blender alone shows floor(t))',
      s_a != s_b and picks == [433, 433, 433, 434, 434, 434], f'{picks}, {s_a[0]} / {s_b[0]} vertices')

# ---------------------------------------------------------------------------------------- the metal study ---
reset()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'shutter_rotary_metal.blend'))
sc = bpy.context.scene
METAL = [1, 48, 49, 50, 121, 241, 433, 672, 673, 700]
rec = EXAMPLES['rotary_metal'](sc, frames=METAL, cache_dir='//shutter_metal_cache', resolution=RES, log=lambda *a: None)
cs = rec.cutting_start


def mclock(t):
    return metal_time(t, cs, rec.job.duration)


shutter_report('rotary_metal', rec, mclock, METAL)
cam = rec.camera
views = {}
for f in (48, 49, 672, 673):
    at(sc, f)
    views[f] = cam.matrix_world.translation.copy()
wide = Vector((-.31, -.48, .38))
close = Vector((.22, -.30, .275))
check('rotary_metal: the camera cuts in at 2 s (frame 49) and back out at 28 s (frame 673), between two shutters',
      (views[48] - wide).length < 1e-6 and (views[49] - close).length < 1e-6 and (views[672] - close).length < 1e-6
      and (views[673] - wide).length < 1e-6)
fs = sc.frame_start
at(sc, 49 - .25)
a_before = chuck_angle(rec.machine)
at(sc, 49 + .25)
a_after = chuck_angle(rec.machine)
check('rotary_metal: across the clock jump at 2 s (setup -> the first chip) the chuck barely turns inside frame 49\'s '
      'shutter', abs(wrap(a_after - a_before)) < math.radians(1.0),
      f'{math.degrees(abs(wrap(a_after - a_before))):.4f} deg (whole-frame keys swung it 11 deg)')

# ----------------------------------------------------------------------- START and END shutters, play() ---
reset()
sc.frame_start, sc.frame_end = 1, 3
m = make_robot('cnc_rotary', textures=False)
job = rotary_carve(m, sample_rotary, duration=2.0, cache_dir=os.path.join(OUT, 'positions'), resolution=(48, 24, 24),
                   engagement_resolution=(48, 24, 24), angles=24, sample_step=.004)
fps = sc.render.fps / sc.render.fps_base
for pos, offs in (('START', (0.0, 31 / 32)), ('END', (-31 / 32, 0.0))):
    sc.render.motion_blur_position = pos
    job.play(frames=[1, 2, 3])
    gx = m.roots['gantry_x']
    cb = anim_utils.action_get_channelbag_for_slot(gx.animation_data.action, gx.animation_data.action_slot)
    times = sorted({round(kp.co.x, 6) for fc in cb.fcurves for kp in fc.keyframe_points})
    want = sorted({round(f + d, 6) for f in (1, 2, 3) for d in offs})
    worst = 0.0
    for f in (1, 2, 3):
        t = (f - 1) / fps
        rate = min(1.0, job.clock_rate(lambda x: max(0.0, x), t))
        tp = min(t, job.duration) / job.duration * job.physical_duration
        d = offs[1] if pos == 'START' else offs[0]
        at(sc, f + d / 2)
        w, _a = expected_tip(job, tp + d / 2 / fps * rate)
        worst = max(worst, (m.tool_tip() - w).length)
    check(f'play() with a {pos} shutter: keys at each frame and {offs[1] or offs[0]:+.5f} of a frame, the tip inside '
          'the shutter on the program', times == want and worst < 2e-4 and shutter_offsets(sc) == offs,
          f'{len(times)} key times, worst {worst * 1000:.4f} mm, cut offset {cut_offset(sc):+.6f}')
sc.render.motion_blur_position = 'CENTER'
err = None
try:
    job.key(5, rate=-1)
except ValueError as e:
    err = str(e)
check('key(): refuses a negative or non-finite rate', err is not None and 'rate' in err, err or '')
job.dispose(files=True)
print('\n%d FAIL' % len(FAILS) if FAILS else '\nALL PASS')
