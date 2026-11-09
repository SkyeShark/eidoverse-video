"""The ocean set without a render. First the port against the WebGPU set's own numbers: ocean_dump.mjs (the coast,
the moon at three hours, the layout's turn, the eye point and the mark, the pages' highlights, the echoes, the dune
grass) and envelopes_dump.mjs (house.js's window and porch light, apparitions.js's robot and human of light, run with
their clocks shifted onto the port's own start times). Then the set built: every control reaches its channel, events
switch things on at their own times, animate() keys them on its own clock (read back at frames), update() keys
through a harness-style ctx, build() takes the harness ctx (and through eidoblend.sets), stand() and heading() face the
sea and the house, hours= turns the layout to another moon, dispose() removes it all.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_ocean_set.py
"""
import json
import math
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.sets.daisy import ocean  # noqa: E402
from eidoblend.sets.daisy.ocean import echoes as EC, land as LD, util as UT  # noqa: E402
from eidoblend.sets.daisy.ocean.apparitions import robot_envelope, human_envelope, robot_pose, human_pose  # noqa: E402
from eidoblend.sets.daisy.ocean.house import window_level, porch_level  # noqa: E402

ck = C.Checks('set')
js = C.js_dump()
ENV = os.path.join(C.OUT, 'envelopes_js.json')
if not os.path.exists(ENV):
    subprocess.run(['deno', 'run', '--no-config', '--no-lock', '-A', os.path.join(C.HERE, 'envelopes_dump.mjs'),
                    C.THREE_BUILD, ENV], cwd=C.REPO, check=True)
with open(ENV) as fh:
    env = json.load(fh)
B3 = UT.B3


def close(a, b, tol):
    return float(np.max(np.abs(np.asarray(a, float) - np.asarray(b, float)))) <= tol


# ================================================================== the WebGPU numbers (no Blender objects)
coast = LD.make_coast()
S = np.array(js['coast']['samples'])
ck.check('coast: signed distance = land.js', close(coast.sdist_3(S[:, 0], S[:, 1]), S[:, 2], 1e-9))
ck.check('coast: height = land.js', close(coast.height_3(S[:, 0], S[:, 1]), S[:, 3], 1e-9),
         f'max {np.abs(coast.height_3(S[:, 0], S[:, 1]) - S[:, 3]).max():.2e}')
ck.check('coast: the mark and the house pad', abs(coast.markY - js['coast']['markY']) < 1e-12 and
         all(abs(coast.house[k] - js['coast']['house'][k]) < 1e-12 for k in ('x', 'z', 'yaw', 'grade')))
ok = close(ocean.sky_moon_dir_three(), js['moon'], 1e-12) and all(
    close(ocean.sky_moon_dir_three(m['hours'], m['azimuth']), m['dir'], 1e-12) for m in js['moons'])
ck.check('the moon = skyMoonDir, at the set\'s hour and two others', ok)
lights = EC.plan_echoes(coast)
ck.check('echoes: the same lights from rng(23) (to the JS attributes\' float32)', len(lights) == len(js['echoes']) and all(
    close(L['p'], J['c'], 1e-4) and close(L['col'], J['col'], 1e-6) and
    close((L['s'], L['phase'], L['freq'], L['far']), J['prm'], 1e-6) for L, J in zip(lights, js['echoes'])),
    f'{len(lights)} lights')
tuft, blades = LD.plan_dune_grass(coast)
M = np.array(js['grass']['matrices']).reshape(-1, 16)
ck.check('dune grass: 2600 tufts placed as land.js', len(blades) == js['grass']['count'] and
         close(np.array(blades)[:, [0, 1, 2]], M[:, 12:15], 1e-5))
ck.check('dune grass: the tuft geometry', close(tuft[0].reshape(-1), js['grass']['tuft']['position'], 1e-6))

# ---- the moving parts on their own clocks = house.js / apparitions.js shifted (JS: u since its own cue, t its clock)
H = np.array(env['house'])                                   # u, t, win, porch, porch W (cd), window (cd)
win = np.array([window_level(t, t - u + 22.52) for u, t in H[:, :2]])
porch = np.array([porch_level(t, t - u + 28.13) for u, t in H[:, :2]])
ck.check('house: window_level / porch_level = house.js (the swell, the catch, the breath)',
         close(win, H[:, 2], 1e-9) and close(porch, H[:, 3], 1e-9),
         f'window {np.abs(win - H[:, 2]).max():.1e}, porch {np.abs(porch - H[:, 3]).max():.1e}')
ck.check('house: its lights are the levels x 7.5 / 1.6 cd as house.js', close(H[:, 4], H[:, 3] * 7.5, 1e-9) and
         close(H[:, 5], H[:, 2] * 1.6, 1e-9))
R = np.array(env['robot'])                                   # u, visible, y, rDiss, rEyes, rBase, rTop
rows = [(robot_envelope(u, 15.0), u) for u in R[:, 0]]
ry = np.array([robot_pose(e['rise'], e['dissolve'], e['eyes'])['y'] for e, _u in rows])
rd = np.array([e['dissolve'] for e, _u in rows])
re_ = np.array([e['eyes'] for e, _u in rows])
rv = np.array([1.0 if e['visible'] else 0.0 for e, _u in rows])
neg = int((R[:, 4] < 0).sum())
ck.check('robot: robot_envelope + robot_pose = apparitions.js (height, dissolve, visibility)',
         close(ry, R[:, 2], 1e-9) and close(rd, R[:, 3], 1e-12) and close(rv, R[:, 1], 0),
         f'height {np.abs(ry - R[:, 2]).max():.1e} m')
ck.check('robot: its eyes = apparitions.js, held at 0 where the JS went negative', close(re_, np.maximum(R[:, 4], 0.0), 1e-12)
         and re_.min() >= 0.0, f'the JS dips below 0 on {neg} of {len(R)} samples (u 15.0 - 15.2: black lenses)')
ck.check('robot: the dissolve spans its height (rTop - rBase = 10.5 m)', close(R[:, 6] - R[:, 5], 10.5, 1e-9))
Hm = np.array(env['human'])                                  # u, visible, y, hDiss
rows = [human_envelope(u, 16.45) for u in Hm[:, 0]]
hy = np.array([human_pose(e['rise'], e['dissolve'])['y'] for e in rows])
hd = np.array([e['dissolve'] for e in rows])
hv = np.array([1.0 if e['visible'] else 0.0 for e in rows])
ck.check('human of light: human_envelope + human_pose = apparitions.js', close(hy, Hm[:, 2], 1e-9) and
         close(hd, Hm[:, 3], 1e-12) and close(hv, Hm[:, 1], 0))

# ================================================================== the set built
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene
sc.render.fps = 24
t0 = time.time()
O = ocean.build({'scene': sc})
print(f'[set] build {time.time() - t0:.1f}s; parts {sorted(O.parts)}', flush=True)
ck.check('layout turn PSI = ocean.js', abs(O.PSI - js['PSI']) < 1e-9, f'{O.PSI:.6f}')
ck.check('the eye point and the mark = ocean.js', close(O.E_design, js['E'], 1e-12) and close(O.mark, B3(js['mark']), 1e-12),
         f"E {tuple(round(c, 4) for c in O.E)}")
for which in (2023, 2026):
    p = O.pages.p23 if which == 2023 else O.pages.p26
    jh = js['pages'][str(which)]
    ck.check(f'page {which}: highlight rects (Pillow vs canvas text metrics)', len(p.his) == len(jh['his']) and close(
        [[h['u0'], h['u1'], h['v0'], h['v1']] for h in p.his], [[h['u0'], h['u1'], h['v0'], h['v1']] for h in jh['his']], 0.02),
        f"centre {tuple(round(c, 4) for c in p.hi_center)} vs {tuple(round(c, 4) for c in jh['hiCenter'])}")


def settle():
    sc.frame_set(sc.frame_current)                           # drivers evaluate (and write back to the lights)


# ---- the resting look (CONTROLS)
settle()
g, hs = O.sea.mesh, O.house.group
ok = g['reveal'] == 1.0 and g['glow'] == 1.0 and O.echoes.control['level'] == 1.0 and hs['porch'] == 1.0 and \
    hs['win'] == 1.0 and O.pages.p23.mesh.hide_render and O.pages.p26.mesh.hide_render and \
    all(o.hide_render for o in O.apparitions.robot['objects'] + O.apparitions.human['objects'])
ck.check('built in its resting look: faces out, lanterns lit, window and porch on, pages and figures put away', ok)
ck.check('the house lights follow their levels (7.5 cd and 1.6 cd as watts)',
         abs(O.house.porch_light.data.energy - 4 * math.pi * 7.5) < 1e-3 and
         abs(O.house.win_light.data.energy - 4 * math.pi * 1.6) < 1e-3,
         f'porch {O.house.porch_light.data.energy:.1f} W, window {O.house.win_light.data.energy:.1f} W')
pw = Vector(g['porchW'])
ck.check('the sea knows where the porch lamp is (its glint on the cove)', (pw - O.house.porch_world()).length < 1e-4)

# ---- every control reaches its channel
st = {'reveal': 0.3, 'glow': 1.4, 'echoes': 0.5, 'echoes_sink': 0.6, 'window': 0.25, 'porch': 0.0, 'fog': 0.002,
      'moonCol': (1.0, 0.5, 0.4), 'grass_wind': 0.4, 'moon': 2.0, 'fill': 1.0, 'page_flutter': 0.5, 'page_glow': 0.2,
      'daisies_close': 0.4, 'daisies_pulse': 1.0, 'daisies_wind': 0.8}
O.update(12.5, st)
settle()
pp = O.land.daisies.field.prototype.modifiers['close']
cl = None
for it in pp.node_group.interface.items_tree:
    if getattr(it, 'in_out', None) == 'INPUT' and it.name == 'Close':
        cl = getattr(pp.properties.inputs, it.identifier).value
ok = (abs(g['reveal'] - 0.3) < 1e-9 and abs(g['glow'] - 1.4) < 1e-9 and abs(g['fog'] - 0.002) < 1e-9 and
      close(tuple(g['moonCol']), (1.0, 0.5, 0.4), 1e-9) and abs(g['t'] - 12.5) < 1e-9 and
      abs(O.echoes.control['level'] - 0.5) < 1e-9 and abs(O.echoes.control['sink'] - 0.6) < 1e-9 and
      abs(hs['win'] - 0.25) < 1e-9 and hs['porch'] == 0.0 and g['porch'] == 0.0 and abs(g['win'] - 0.25) < 1e-9 and
      abs(O.land.grass['wind'] - 0.4) < 1e-9 and abs(O.land.grass['t'] - 12.5) < 1e-9 and
      abs(O.lights['moon'].data.energy - 2.0) < 1e-9 and abs(O.lights['fill'].data.energy - 4 * math.pi) < 1e-6 and
      abs(O.lights['sea_glow'].data.energy - 4 * math.pi * 3.5 * 0.3) < 1e-6 and
      abs(O.pages.p26.mesh['flutter'] - 0.5) < 1e-9 and abs(O.pages.p26.mesh['glow'] - 0.2) < 1e-9 and
      cl is not None and abs(cl - 0.4) < 1e-6 and abs(O.land.daisies.group['pulse'] - 1.0) < 1e-9)
ck.check('every control reaches its channel (sea, echoes, house, glints, grass, lights, pages, daisies)', ok,
         f'daisies close {cl}')
ck.check('the house lights follow (porch off, window at 0.25)', O.house.porch_light.data.energy < 1e-6 and
         abs(O.house.win_light.data.energy - 4 * math.pi * 1.6 * 0.25) < 1e-3)
try:
    O.update(0.0, {'no_such_control': 1})
    ck.check('an unknown control is refused', False)
except KeyError as e:
    ck.check('an unknown control is refused', True, str(e))

# ---- a page placed in the world, its text side turned to a point
P = Vector(O.to_world((0.6, coast.markY + 1.45, 0.5)))
F = Vector(O.to_world((0.0, coast.markY + 1.52, 0.0)))
O.update(1.0, {'page_2026': {'pos': tuple(P), 'face': tuple(F)}})
bpy.context.view_layer.update()
hw = O.pages.p26.holder.matrix_world
txt = (hw.to_3x3() @ Vector((0.0, -1.0, 0.0))).normalized()
ang = math.degrees(txt.angle((F - P).normalized()))
ck.check('page_2026 placed: at its world position, the text side toward the point, the other page put away',
         (hw.translation - P).length < 1e-5 and ang < 1e-3 and not O.pages.p26.mesh.hide_render and
         O.pages.p23.mesh.hide_render, f'{(hw.translation - P).length * 1000:.4f} mm, {ang:.5f} deg')

# ---- the figures: levels, and their envelopes from a start time
O.update(3.0, {'robot_rise': 0.5})
rb = O.apparitions.robot['holder']
want = robot_pose(0.5, 0.0, base_y=0.0)['y']
ck.check('robot_rise 0.5: the robot shows, half risen', not O.apparitions.robot['objects'][0].hide_render and
         abs(rb.location.z - want) < 1e-5 and abs(rb['rEyes'] - 0.5) < 1e-9 and O.apparitions.human['objects'][0].hide_render,
         f'z {rb.location.z:.2f}')
O.update(2.7, {'robot_at': 2.0, 'human_at': 1.0})
e = robot_envelope(2.7, 2.0)
ck.check('robot_at: 0.7 s in, stood with its eyes on (rBase / rTop span it in the world)',
         abs(rb['rEyes'] - e['eyes']) < 1e-9 and e['eyes'] > 0.99 and abs(rb['rTop'] - rb['rBase'] - 10.5) < 1e-9 and
         not O.apparitions.robot['objects'][0].hide_render, f"eyes {rb['rEyes']:.3f}, base {rb['rBase']:.2f} m")
hh = O.apparitions.human['holder']
ck.check('human_at: 1.7 s in, coming apart', abs(hh['hDiss'] - human_envelope(2.7, 1.0)['dissolve']) < 1e-9 and
         hh['hDiss'] > 0.5 and not O.apparitions.human['objects'][0].hide_render, f"hDiss {hh['hDiss']:.3f}")
O.update(3.9, {'robot_at': 2.0})
ck.check('robot_at: gone 1.8 s in', all(o.hide_render for o in O.apparitions.robot['objects']))
O.update(5.0, {'porch_on': 4.9, 'window_on': 4.8})
ck.check('porch_on / window_on: the swell 0.1 s in, the window 0.2 s in',
         abs(hs['porch'] - porch_level(5.0, 4.9)) < 1e-12 and abs(hs['win'] - window_level(5.0, 4.8)) < 1e-12 and
         0.3 < hs['porch'] < 0.9, f"porch {hs['porch']:.3f}, window {hs['win']:.3f}")

# ---- animate: the controls on its own clock, keyed, read back at frames (the saved .blend's view)
cam = bpy.data.objects.new('test_cam', bpy.data.cameras.new('test_cam'))
sc.collection.objects.link(cam)
cam.location = O.to_world((-1.0, coast.markY + 1.4, 2.4))
sc.camera = cam
t1 = time.time()
rep = O.animate({'reveal': lambda t: ocean.ease(t, 0.5, 2.5), 'echoes_sink': lambda t: ocean.ease(t, 0.0, 3.0),
                 'porch_on': 2.0, 'robot_at': 1.0, 'daisies_close': lambda t: 1.0 - ocean.ease(t, 0.0, 3.0),
                 'page_2023': lambda t: {'pos': tuple(P + Vector((0.0, 0.0, 0.1 * t))), 'face': tuple(F)}},
                frames=(1, 97), t0=0.0, fps=24)
print(f'[set] animate {time.time() - t1:.1f}s: {rep}', flush=True)
errs = []
for f in (1, 25, 37, 49, 61, 97):
    sc.frame_set(f)
    t = (f - 1) / 24
    errs.append(max(abs(g['reveal'] - ocean.ease(t, 0.5, 2.5)), abs(O.echoes.control['sink'] - ocean.ease(t, 0.0, 3.0)),
                    abs(hs['porch'] - porch_level(t, 2.0))))
ck.check('animate keys the controls (read back at frames)', max(errs) < 1e-5 and rep['channels'] > 30,
         f"max {max(errs):.1e}, {rep['channels']} channels")
sc.frame_set(37)                                             # t 1.5: the robot stood (0.5 s in)
vis_up = not O.apparitions.robot['objects'][0].hide_render
sc.frame_set(97)                                             # t 4.0: gone
ck.check('animate keys the robot\'s visibility (CONSTANT): up 0.5 s in, gone after',
         vis_up and O.apparitions.robot['objects'][0].hide_render)
sc.frame_set(49)
bpy.context.view_layer.update()
dz = (O.pages.p23.holder.matrix_world.translation - (P + Vector((0.0, 0.0, 0.2)))).length
ck.check('animate keys the placed page along its path (t 2: 0.2 m up)', dz < 1e-4 and not O.pages.p23.mesh.hide_render,
         f'{dz * 1000:.3f} mm')
ad = pp.id_data.animation_data
from eidoblend.sets.daisy.ocean.staging import _action_fcurves  # noqa: E402
fcs = _action_fcurves(ad.action) if ad is not None and ad.action is not None else []
ck.check('animate keys her daisies\' close where it changes', any('modifiers["close"]' in fc.data_path for fc in fcs),
         f'{len(fcs)} curves on the plant')
fp = [O.lights['fill'].matrix_world.translation.copy()]
cam.location.x += 3.0
bpy.context.view_layer.update()
O.update(1.0)
bpy.context.view_layer.update()
fp.append(O.lights['fill'].matrix_world.translation.copy())
E_w = Vector(O.to_world(O.E_design))
d0 = Vector((fp[1].x - E_w.x, fp[1].y - E_w.y, 0.0)).normalized()
dc = Vector((cam.location.x - E_w.x, cam.location.y - E_w.y, 0.0)).normalized()
ck.check('the fill stands off her face toward the camera (and follows it)', (fp[1] - fp[0]).length > 0.05 and
         d0.angle(dc) < math.radians(12), f'{math.degrees(d0.angle(dc)):.1f} deg off the camera side')

# ---- update(..., ctx=) keys through the harness's ctx.key
class HarnessLikeCtx:
    """the shape of eidoblend.harness.context.Ctx: an object with .scene and .key(target, data_path, index, frame,
    interpolation), not a mapping"""
    def __init__(self, scene):
        self.scene, self.fps, self.frame_start, self.keyed = scene, 24, 1, 0

    def key(self, target, data_path, index=-1, frame=None, interpolation='LINEAR'):
        self.keyed += 1
        return target.keyframe_insert(data_path, index=index, frame=sc.frame_current if frame is None else frame)


hc = HarnessLikeCtx(sc)
O.update(4.0, {'reveal': 0.8}, frame=120, ctx=hc)
ck.check('update(t, st, frame, ctx) keys through ctx.key', hc.keyed > 20, f'{hc.keyed} keys')

# ---- a figure on the mark: toward the sea (the moon path) and toward the house
fig = bpy.data.objects.new('test_figure', None)
sc.collection.objects.link(fig)
O.stand(fig, facing='sea')
bpy.context.view_layer.update()
fwd = fig.matrix_world.to_3x3() @ Vector((0.0, -1.0, 0.0))
mh = Vector((O.moon[0], O.moon[1], 0.0)).normalized()
a_sea = math.degrees(Vector((fwd.x, fwd.y, 0.0)).normalized().angle(mh))
mk = O.group.matrix_world @ Vector(O.mark)
O.stand(fig, facing='house')
bpy.context.view_layer.update()
fwd = fig.matrix_world.to_3x3() @ Vector((0.0, -1.0, 0.0))
hw_ = O.house.group.matrix_world.translation - mk
a_house = math.degrees(Vector((fwd.x, fwd.y, 0.0)).normalized().angle(Vector((hw_.x, hw_.y, 0.0)).normalized()))
ck.check("stand(): on the mark, facing 'sea' is the moon path, 'house' the house",
         (fig.matrix_world.translation - mk).length < 1e-6 and a_sea < 1e-4 and a_house < 1e-4,
         f'sea {a_sea:.5f} deg, house {a_house:.5f} deg')

# ---- dispose, then the harness ctx object as build's ctx, through eidoblend.sets, and another hour's moon
O.dispose()
ck.check('dispose() removes the set', 'set:ocean' not in bpy.data.objects and 'ocean_of_faces' not in bpy.data.objects)
err = None
try:
    Oh = ocean.build(hc, parts=('lights', 'sea'), name='set_ocean_harness')
    Oh.dispose()
    from eidoblend import sets
    Os = sets.build('daisy.ocean', hc, parts=('lights',))       # (sets.build's own first argument is the set's name)
    Os.dispose()
except Exception as ex:  # noqa: BLE001
    err = f'{type(ex).__name__}: {ex}'
ck.check("build(<harness ctx object>) and sets.build('daisy.ocean', ctx) build", err is None, err or '')
O2 = ocean.build({'scene': sc, 'parts': ('lights', 'world'), 'hours': 21.5, 'name': 'set_ocean_late'})
md = O2.to_design(tuple(O2.group.matrix_world.translation + Vector(O2.moon)))
az = math.atan2(md[0], md[2])
want = js['moons'][0]['dir']
ck.check('hours=21.5: the moon is the sky\'s at that hour, and the layout turns to meet it (design azimuth D_MOON)',
         close(Vector(O2.moon), B3(want), 1e-6) and abs(az - ocean.staging.D_MOON) < 1e-6,
         f'moon {tuple(round(c, 3) for c in O2.moon)}, design azimuth {az:.6f}')
O2.dispose()
L2 = LD.build_land(LD.make_coast(), mesh=False, grass=True, daisies=False, webgpu_sway=True)
from eidoblend.sets.daisy.ocean import _bl  # noqa: E402
slot, _p = _bl.modifier_input_path(L2.grass.modifiers['sway'], 'WebGPU')
ck.check("build_land(webgpu_sway=True): the WebGPU edition's sway arithmetic", slot.value == 1.0)
ck.summary()
with open(os.path.join(C.OUT, 'test_ocean_set.json'), 'w') as f:
    json.dump(ck.rows, f, indent=1)
