"""test_sections.py: the race's and the bin's whole-section keyers on a clock and a cut of your own (animate,
make_cameras), their build(ctx) entry, dict-style access and dispose, headless and CPU only (nothing renders): every
frame keyed through a harness-style ctx.key, the moving parts on their own time controls (race.sequence, bin's
ease_in), the cut coming out as cameras bound to timeline markers at the cut frames, each camera keyed where
key_camera puts it, and dispose() leaving no datablock of the set behind (every type, the keys' actions included).

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_race_bin/test_sections.py

Prints PASS / FAIL lines; exits 1 on a FAIL.
"""
import math
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))

import bpy  # noqa: E402

from eidoblend.sets.unknown_force import bin as B  # noqa: E402
from eidoblend.sets.unknown_force import race as R  # noqa: E402

fails = []


def check(name, ok, info=''):
    print(('PASS' if ok else 'FAIL'), name, info, flush=True)
    if not ok:
        fails.append(name)


KINDS = ('objects', 'meshes', 'materials', 'images', 'node_groups', 'lights', 'lightprobes', 'worlds', 'collections',
         'actions', 'cameras')


def names():
    return {k: {d.name for d in getattr(bpy.data, k)} for k in KINDS}


def leftovers(before):
    now = names()
    # the scene's compositor trees (apply_render_settings' fog and bloom: look.post's chain) and the render's images
    scene_level = {'eido_sky_fog', 'look_post', 'Render Result', 'Viewer Node'}
    return {k: sorted(n for n in now[k] - before[k] if n not in scene_level) for k in KINDS if now[k] - before[k] - scene_level}


for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
bpy.data.orphans_purge(do_recursive=True)
scene = bpy.context.scene
FPS = 12
scene.render.fps = FPS
keys = []
from eidoblend.harness.keying import KeyLog, make_linear  # noqa: E402
key_log = KeyLog()


def ctx_key(target, path, index=-1, frame=None, interpolation='LINEAR'):
    """The harness's ctx.key (context.py): insert, and log the interpolation asked for; make_linear applies it."""
    keys.append((path, frame))
    ok = target.keyframe_insert(path, index=index, frame=frame)
    if ok:
        key_log.add(target, path, index, frame, interpolation)
    return ok


ctx = types.SimpleNamespace(scene=scene, key=ctx_key)

# ---- the race: 4 s on my clock; the car reaches the broken edge at 3.2 s, the march comes up from 3.5 s, the boot
# strikes at 3.9 s; my cut: carPass, carTrack from 1.5 s, crashLow from 3.0 s
before = names()
race = R.build(ctx, rain=False)
check('race build(ctx): the ctx keyer is used', race.key.fn is not None)
check("race dict-style access (s['group'], s['update'])", race['group'] is race.group and callable(race['update']))
EV = dict(bill_a_on=(0.0, 0.5), glance_from=0.5, car_edge=3.2, march_on=(3.5, 3.8), heel_strike=3.9)
state_fn = lambda t: R.sequence(t, **EV)
f0, f1 = 1, 4 * FPS + 1
race.animate((f0, f1), t0=0.0, state_fn=state_fn)
check('race animate: every frame keyed through ctx.key', len({f for _, f in keys}) == f1 - f0 + 1, f'{len(keys)} keys')
scene.frame_set(f0 + round(2.0 * FPS))
rs = R.race_state(2.0, state_fn(2.0), race.path, race.debris)
check('race animate: the car keyed on its run (car_drive) at 2.0 s',
      (race.car['group'].location - R.Vector(R.to_blender(rs['car']['pos']))).length < 1e-3,
      f"z {rs['car']['pos'][2]:.1f} m down the road")
CUT = [(0.0, 'carPass'), (1.5, 'carTrack'), (3.0, 'crashLow')]
cams = race.make_cameras(CUT, (f0, f1), t0=0.0, state_fn=state_fn)
got = sorted((m.frame, m.camera.name.split('_')[1]) for m in scene.timeline_markers if m.name.startswith('race_'))
want = [(f0, 'carPass'), (f0 + math.ceil(1.5 * FPS - 1e-9), 'carTrack'), (f0 + math.ceil(3.0 * FPS - 1e-9), 'crashLow')]
check('race make_cameras: my cut as cameras, markers at the cuts', got == want, f'{got}')
bad = 0
for (fa, name), cam in cams.items():
    t = (fa - f0) / FPS
    scene.frame_set(fa)
    c = race.cam_at(name, t, state_fn(t)) or race.cams[name]
    if (cam.matrix_world.translation - race.camera_matrix(c).translation).length > 1e-3:
        bad += 1
check('race cameras keyed on their shots', bad == 0, f'{len(cams)} cameras')
try:
    race.make_cameras([(0.0, 'carSide')], (f0, f0 + 1), t0=3.5, state_fn=state_fn)
    check('race key_camera: a car camera with the car in its crash says so', False)
except ValueError as e:
    check('race key_camera: a car camera with the car in its crash says so', 'crash' in str(e))
# set_active: parked outside its section (every mesh hidden, every light at 0, keyed), then back
fa, fb = f1 + 1, f1 + 2
race.set_active(False, frame=fa)
race.update(4.0, state_fn(4.0), frame=fa)
race.set_active(True, frame=fb)
race.update(4.1, state_fn(4.1), frame=fb)
make_linear(key_log)                # what the harness's runner does after the build
L = race.lights
energies = lambda: [L[k].data.energy for k in ('key', 'glow_a', 'glow_b', 'rim', 'back_rim', 'neon_fill', 'beam')] + [L['sodium'].energy]
scene.frame_set(fa)
off = energies()
shown = [o.name for o in race.objects if o.type == 'MESH' and not o.hide_render]
scene.frame_set(fb)
on = energies()
hidden = [o.name for o in race.objects if o.type == 'MESH' and o.hide_render and o.name.startswith('race:road')]
check('race set_active(False / True) keyed: every light at 0 and every mesh hidden, then the set back',
      max(off) == 0.0 and not shown and min(on[:2]) > 0 and on[-1] > 0 and not hidden,
      f'off max {max(off):.2f} W, meshes shown {len(shown)}; on key {on[0]:.0f} W, sodium {on[-1]:.0f} W')
scene.frame_set(f0 + 3)
early = energies()
check('race set_active keys a step: the frames before the park still show the set and its lights',
      not race.parts['road'].hide_render and not race.parts['towers']['towers'].hide_render and early[0] > 0,
      f"frame {f0 + 3}: road shown, key {early[0]:.0f} W")
# parked for a long span (no update() inside it): the lights hold 0 across it, they do not fade back up
fc0, fc1 = fb + 1, fb + 40
race.set_active(False, frame=fc0)
race.set_active(True, frame=fc1)
race.update(5.0, state_fn(5.0), frame=fc1)
make_linear(key_log)
scene.frame_set((fc0 + fc1) // 2)
mid = energies()
check('race parked across a span: the lights stay at 0 inside it (CONSTANT steps, no fade)', max(mid) == 0.0,
      f'mid-span max {max(mid):.3f} W')
race.dispose()                     # its cameras (make_cameras' collection) go with it
for m in list(scene.timeline_markers):
    scene.timeline_markers.remove(m)
left = leftovers(before)
check('race dispose: no datablock of the set left (its cameras and the keys\' actions included)', not left, f'{left}')

# ---- the bin: 12 s on my clock; the mark climbs out from 1 to 10 s, a hush from 7 to 8 s; my shots with their moves
keys.clear()
before = names()
b = B.build(scene, sheets=400, balls=40, falling=50, atlas_scale=0.25, cache_dir=os.path.join(HERE, 'out', 'cache'))
check("bin dict-style access (s['parts']['mark'])", b['parts']['mark'] is b.mark)
bstate = lambda t: {'climb': B.ease_in(t, 1.0, 10.0), 'hush': 1.0 if 7.0 <= t < 8.0 else 0.0, 'wind': 0.4}
f0, f1 = 1, 12 * FPS + 1
b.animate((f0, f1), t0=0.0, state_fn=bstate)
scene.frame_set(f1)
z = B.lerp(b.Z_IN, b.Z_OUT, B.smooth(0, 1, 1.0))
check('bin animate: the mark keyed up the climb to the lip', abs(b.mark.location.z - (b._fill_y3(0, z) + 0.03)) < 1e-4)
SH = [(0.0, 'binWide', {'push': 2.0}), (4.0, 'paperClose'), (7.0, 'climb', {'orbit': 0.3}), (10.0, 'topDown')]
cams = b.make_cameras(SH, (f0, f1), t0=0.0)
got = sorted((m.frame, m.camera.name.split('_')[1]) for m in scene.timeline_markers if m.name.startswith('bin_'))
want = [(f0 + round(s[0] * FPS), s[1]) for s in SH]
check('bin make_cameras: my shots as cameras and markers at the cuts', got == want, f'{got}')
done = b.apply_render_settings(scene, bloom=True)
check("bin apply_render_settings: AgX, ray tracing, the bloom option and the set's fog",
      scene.view_settings.view_transform == 'AgX' and any('bloom' in str(d) for d in done) and 'fog' in done, f'{done}')
b.dispose()
for m in list(scene.timeline_markers):
    scene.timeline_markers.remove(m)
left = leftovers(before)
check("bin dispose: no datablock of the set left (the can's glTF import and the keys' actions included)", not left, f'{left}')
print('[test_sections]', 'ALL PASS' if not fails else f'{len(fails)} FAIL: {fails}', flush=True)
sys.exit(1 if fails else 0)
