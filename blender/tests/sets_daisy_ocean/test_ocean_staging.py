"""The set without a render: build every part, then check the port against the WebGPU set's own numbers
(ocean_dump.mjs): the coast, the moon and the layout's turn, every shot's camera and her mark through the verse, the
pages' flights and highlights, the echoes, the dune grass; then key the verse and read it back at frames.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_ocean_staging.py
"""
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402

from eidoblend.sets.daisy import ocean  # noqa: E402
from eidoblend.sets.daisy.ocean import echoes as EC, land as LD, util as UT  # noqa: E402

ck = C.Checks('staging')
js = C.js_dump()
B3 = UT.B3


def close(a, b, tol):
    return float(np.max(np.abs(np.asarray(a, float) - np.asarray(b, float)))) <= tol


# ---- the coast and the moon (no Blender objects needed)
coast = LD.make_coast()
S = np.array(js['coast']['samples'])
ck.check('coast: signed distance = land.js', close(coast.sdist_3(S[:, 0], S[:, 1]), S[:, 2], 1e-9))
ck.check('coast: height = land.js', close(coast.height_3(S[:, 0], S[:, 1]), S[:, 3], 1e-9),
         f'max {np.abs(coast.height_3(S[:, 0], S[:, 1]) - S[:, 3]).max():.2e}')
ck.check('coast: her mark and the house pad', abs(coast.markY - js['coast']['markY']) < 1e-12 and
         all(abs(coast.house[k] - js['coast']['house'][k]) < 1e-12 for k in ('x', 'z', 'yaw', 'grade')))
ck.check('sky moon = skyMoonDir', close(ocean.sky_moon_dir_three(), js['moon'], 1e-12))
lights = EC.plan_echoes(coast)
ck.check('echoes: same lights from rng(23) (to the JS attributes\' float32)', len(lights) == len(js['echoes']) and all(
    close(L['p'], J['c'], 1e-4) and close(L['col'], J['col'], 1e-6) and
    close((L['s'], L['phase'], L['freq'], L['far']), J['prm'], 1e-6) for L, J in zip(lights, js['echoes'])),
    f'{len(lights)} lights')
tuft, blades = LD.plan_dune_grass(coast)
M = np.array(js['grass']['matrices']).reshape(-1, 16)
ck.check('dune grass: 2600 tufts placed as land.js', len(blades) == js['grass']['count'] and
         close(np.array(blades)[:, [0, 1, 2]], M[:, 12:15], 1e-5))
ck.check('dune grass: the tuft geometry', close(tuft[0].reshape(-1), js['grass']['tuft']['position'], 1e-6))

# ---- build everything
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene
sc.render.fps = 24
t0 = time.time()
O = ocean.build({'scene': sc})
print(f'[staging] build {time.time() - t0:.1f}s; parts {sorted(O.parts)}', flush=True)
ck.check('layout turn PSI = ocean.js', abs(O.PSI - js['PSI']) < 1e-9, f'{O.PSI:.6f}')
for which in (2023, 2026):
    p = O.pages.p23 if which == 2023 else O.pages.p26
    jh = js['pages'][str(which)]
    ck.check(f'page {which}: highlight rects (Pillow vs canvas text metrics)', len(p.his) == len(jh['his']) and close(
        [[h['u0'], h['u1'], h['v0'], h['v1']] for h in p.his], [[h['u0'], h['u1'], h['v0'], h['v1']] for h in jh['his']], 0.02),
        f"centre {tuple(round(c, 4) for c in p.hi_center)} vs {tuple(round(c, 4) for c in jh['hiCenter'])}")

# ---- every shot through the verse
worst = {'cam': 0.0, 'tgt': 0.0, 'fov': 0.0, 'yaw': 0.0, 'p23': 0.0, 'p26': 0.0, 'q': 0.0, 'reveal': 0.0}
for fr in js['frames']:
    u = fr['u']
    c = O.camera(u)
    m = O.mark_at(u)
    worst['cam'] = max(worst['cam'], np.abs(np.array(c['pos']) - B3(fr['cam']['pos'])).max())
    worst['tgt'] = max(worst['tgt'], np.abs(np.array(c['target']) - B3(fr['cam']['target'])).max())
    worst['fov'] = max(worst['fov'], abs(c['fov'] - fr['cam']['fov']))
    dy = (m['yaw'] - fr['mark']['yaw'] + math.pi) % (2 * math.pi) - math.pi
    worst['yaw'] = max(worst['yaw'], abs(dy))
    st = O.state(100 + u, {'u': u, 'pulse': 0.5})
    worst['reveal'] = max(worst['reveal'], abs(st['sea.reveal'] - fr['reveal']), abs(st['sea.glow'] - fr['glow']),
                          abs(st['echoes.sink'] - fr['echoes']['sink']), abs(st['echoes.level'] - fr['echoes']['level']))
    for tag in ('p23', 'p26'):
        if fr[tag]['on'] != st[tag + '.on']:
            worst[tag] = 99
        elif fr[tag]['on']:
            worst[tag] = max(worst[tag], np.abs(np.array(st[tag + '.pos']) - B3(fr[tag]['pos'])).max())
            qj = fr[tag]['q']
            qb = Quaternion((qj[3], qj[0], -qj[2], qj[1]))
            worst['q'] = max(worst['q'], Quaternion(st[tag + '.q']).rotation_difference(qb).angle)
ck.check('cameras through the verse = ocean.js (0.05 s steps)', worst['cam'] < 0.01 and worst['tgt'] < 0.01 and worst['fov'] < 1e-9,
         f"pos {worst['cam'] * 1000:.2f} mm, target {worst['tgt'] * 1000:.2f} mm (the inserts ride the page highlight)")
ck.check('her mark and facing = ocean.js', worst['yaw'] < 1e-9, f"yaw {worst['yaw']:.2e} rad")
ck.check('pages fly as ocean.js', worst['p23'] < 1e-9 and worst['p26'] < 1e-9 and worst['q'] < 1e-6,
         f"pos {max(worst['p23'], worst['p26']):.2e} m, rot {worst['q']:.2e} rad")
ck.check('reveal / glow / echo sink and level = ocean.js update', worst['reveal'] < 1e-12)

# ---- key the verse, then read a few frames back (the saved .blend's view)
cam_d = bpy.data.cameras.new('ocean_cam')
cam = bpy.data.objects.new('ocean_cam', cam_d)
sc.collection.objects.link(cam)
t0 = time.time()
rep = O.key_verse(frame_start=1, fps=24, t0=100.0, camera_obj=cam, pulse=lambda u: 0.5)
print(f'[staging] key_verse {time.time() - t0:.1f}s: {rep}', flush=True)
nf = rep['frames'][1] - rep['frames'][0] + 1
ck.check('verse keyed: 18 bars at 24 fps', nf == int(33.75 * 24) + 1, f'{nf} frames, {len(rep["cuts"])} cuts')
errs = []
for f in (1, 100, 181, 260, 400, 500, 640, 760, 811):
    sc.frame_set(f)
    u = (f - 1) / 24
    c = O.camera(u)
    want = O.group.matrix_world @ Vector(c['pos'])
    errs.append((cam.matrix_world.translation - want).length)
ck.check('camera keys play back the shots', max(errs) < 1e-4, f'max {max(errs) * 1000:.3f} mm')
sc.frame_set(int(9 * 24) + 1)
ck.check('the 2023 page shows at u 9 (and the 2026 one does not)', not O.pages.p23.mesh.hide_render and O.pages.p26.mesh.hide_render)
sc.frame_set(int(30 * 24) + 1)
ck.check('porch light on at u 30 (window on)', O.house.group['porch'] > 0.9 and O.house.group['win'] > 0.99 and
         O.house.porch_light.data.energy > 50, f"porch {O.house.group['porch']:.3f}, {O.house.porch_light.data.energy:.1f} W")
C.save_blend(os.path.join(C.OUT, 'ocean_staging.blend'))

# ---- the per-frame path (the harness's ctx.key style): update(t, st, key=True, frame=f) frame by frame
sc.frame_set(1)
O.dispose()
ck.check('dispose() removes the set', 'set:ocean' not in bpy.data.objects and 'ocean_of_faces' not in bpy.data.objects)
O2 = ocean.build({'scene': sc, 'parts': ('sea', 'echoes', 'pages', 'house', 'apparitions', 'lights', 'land', 'grass')})
for f, u in ((10, 0.4), (200, 8.0), (700, 29.0)):
    O2.update(100 + u, {'u': u, 'pulse': 0.0}, key=True, frame=f)
sc.frame_set(200)
ok = abs(O2.sea.mesh['t'] - 108.0) < 1e-6 and not O2.pages.p23.mesh.hide_render
sc.frame_set(700)
ok = ok and O2.house.group['porch'] > 0.9 and abs(O2.sea.mesh['porch'] - O2.house.group['porch']) < 1e-9
sc.frame_set(10)
ok = ok and O2.echoes.control['level'] == 1.0 and O2.pages.p23.mesh.hide_render
ck.check('update(t, st, key=True, frame) keys every channel frame by frame', ok)
# the sea's glints follow the porch, the house and the sea agree on where it is
pw = Vector(O2.sea.mesh['porchW'])
ck.check('the sea knows where the porch lamp is', (pw - O2.house.porch_world()).length < 1e-4, f'{tuple(round(c, 2) for c in pw)}')
O2.apparitions.update(15.7, 115.7, key=True, frame=377)
sc.frame_set(377)
rb = O2.apparitions.robot['holder']
ck.check('apparitions.update keys the robot (risen, eyes on)', not O2.apparitions.robot['objects'][0].hide_render and
         rb['rEyes'] > 0.9 and rb['rTop'] - rb['rBase'] > 10.4, f"z {rb.location.z:.2f}, eyes {rb['rEyes']:.2f}")
from eidoblend.sets.daisy.ocean import land as LD2  # noqa: E402
L2 = LD2.build_land(LD2.make_coast(), mesh=False, grass=True, daisies=False, webgpu_sway=True)
from eidoblend.sets.daisy.ocean import _bl  # noqa: E402
slot, _p = _bl.modifier_input_path(L2.grass.modifiers['sway'], 'WebGPU')
ck.check('build_land(webgpu_sway=True): the film\'s sway arithmetic', slot.value == 1.0)
ck.summary()
with open(os.path.join(C.OUT, 'test_ocean_staging.json'), 'w') as f:
    json.dump(ck.rows, f, indent=1)
