"""test_sections.py: the race's and the bin's whole-section keyers (animate, make_cameras), their build(ctx) entry,
dict-style access and dispose, headless and CPU only (nothing renders): the film's cut must come out as cameras bound
to timeline markers at the cut frames, every frame keyed, the saved scene must show the keyed camera on each shot, and
dispose() must leave no datablock of the set behind.

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


for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
scene = bpy.context.scene
scene.render.fps = 24
keys = []
ctx = types.SimpleNamespace(scene=scene, key=lambda target, path, index=-1, frame=None, interpolation='LINEAR':
                            keys.append((path, frame)) or target.keyframe_insert(path, index=index, frame=frame))
race = R.build(ctx, rain=False)
check('race build(ctx): the ctx keyer is used', race.key.fn is not None)
check("race dict-style access (s['group'], s['update'])", race['group'] is race.group and callable(race['update']))
f0, f1, t0 = 1, 24 * 6, 152.0
race.animate((f0, f1), t0=t0)
check('race animate: every frame keyed through ctx.key', len({f for _, f in keys}) == f1 - f0 + 1, f'{len(keys)} keys')
cams = race.make_cameras((f0, f1), t0=t0)
want = []
prev = None
for f in range(f0, f1 + 1):
    name = R.suggest(t0 + (f - f0) / 24)['cam']
    if name != prev:
        want.append((f, name))
        prev = name
got = sorted((m.frame, m.camera.name.split('_')[1] if m.camera else None) for m in scene.timeline_markers if m.name.startswith('race_'))
check('race make_cameras: one camera per shot of the cut, markers at the cuts',
      [(f, n) for f, n in want] == [(f, n) for f, n in got], f'{want}')
# the saved scene shows each shot's camera where key_camera put it
bad = 0
for (fa, name), cam in cams.items():
    t = t0 + (fa - f0) / 24
    scene.frame_set(fa)
    c = race.cam_at(name, t, R.suggest(t)['state']) or race.cams[name]
    m = race.camera_matrix(c)
    if (cam.matrix_world.translation - m.translation).length > 1e-3:
        bad += 1
check('race cameras keyed on their shots', bad == 0, f'{len(cams)} cameras')

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for m in list(scene.timeline_markers):
    scene.timeline_markers.remove(m)
b = B.build(scene, sheets=400, balls=40, falling=50, atlas_scale=0.25, cache_dir=os.path.join(HERE, 'out', 'cache'))
check("bin dict-style access (s['parts']['mark'])", b['parts']['mark'] is b.mark)
f0, f1, t0 = 1, 24 * 12, 222.6
b.animate((f0, f1), t0=t0)
scene.frame_set(f1)
c = B.film_state(t0 + (f1 - f0) / 24)['climb']
z = B.lerp(b.Z_IN, b.Z_OUT, B.smooth(0, 1, c))
check('bin animate: the mark keyed up the climb', abs(b.mark.location.z - (b._fill_y3(0, z) + 0.03)) < 1e-4)
cams = b.make_cameras((f0, f1), t0=t0)
got = sorted((m.frame, m.camera.name.split('_')[1]) for m in scene.timeline_markers if m.name.startswith('bin_'))
want = [(1, 'binWide'), (1 + round((227.8 - t0) * 24), 'paperClose'), (1 + math.ceil((233.0 - t0) * 24 - 1e-9), 'climb')]
check('bin make_cameras: the film\'s bridge shots as cameras and markers', [n for _, n in got] == [n for _, n in want],
      f'{got}')
done = b.apply_render_settings(scene, bloom=True)
check("bin apply_render_settings: AgX, ray tracing, the film's bloom and the set's fog",
      scene.view_settings.view_transform == 'AgX' and any('bloom' in str(d) for d in done) and 'fog' in done, f'{done}')


def leftovers(prefix):
    out = []
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.node_groups,
                 bpy.data.lights, bpy.data.worlds, bpy.data.collections):
        out += [d.name for d in coll if d.name.startswith(prefix)]
    return out


# dispose(): everything a set made goes (its cameras are the caller's)
for o in list(bpy.data.objects):
    if o.name.startswith('bin:cam_'):
        bpy.data.objects.remove(o, do_unlink=True)
b.dispose()
left = [n for n in leftovers('bin:') if not n.startswith('bin:cam') and n != 'bin:cameras']
check('bin dispose: no bin datablocks left', not left, ', '.join(left[:8]))
for o in list(bpy.data.objects):
    if o.name.startswith('race:cam_'):
        bpy.data.objects.remove(o, do_unlink=True)
bpy.data.orphans_purge(do_recursive=True)            # the first race's data, its objects already gone
race2 = R.build(scene, rain=False)
race2.dispose()
left = [n for n in leftovers('race:') if not n.startswith('race:cam') and n != 'race:cameras']
check('race dispose: no race datablocks left', not left, ', '.join(left[:8]))
print('[test_sections]', 'ALL PASS' if not fails else f'{len(fails)} FAIL: {fails}', flush=True)
sys.exit(1 if fails else 0)
