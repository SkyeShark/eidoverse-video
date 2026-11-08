"""test_race.py: builds THE RACE (eidoblend.sets.unknown_force.race) headless, keys the film's cut (suggest) at a set of
probe frames, checks what it keyed against the pure state (race_state) after jumping to each frame, and renders the
probes from the film's cameras into out/race_<n>_<shot>.png.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sets_uf_race_bin/test_race.py -- [--build-only] [--shots a,b] [--res 960x540]
        [--samples 16] [--blend] [--no-rain] [--cycles name] [--singer [--vrm path]] [--film]

--singer puts the claudesona on her mark at the film's scale (claude_suit by default, --vrm for the film's own suit)
and tags the probes _singer; --film keys the whole section on the film's cut and renders nothing.

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
from eidoblend.sets.unknown_force import race as R  # noqa: E402

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


# the probe shots: (song time, camera) -- the film's cut (suggest) at its moments, plus the craft and wide views
SHOTS = [
    (142.6, 'billA'), (145.2, 'billB'), (148.9, 'billboards'), (150.8, 'singer'), (153.3, 'carPass'),
    (155.25, 'carTrack'), (157.4, 'carChase'), (158.45, 'carChase'), (159.9, 'crashLow'), (160.8, 'crashLow'),
    (161.6, 'crashLow'), (161.5, 'shadows'), (162.3, 'heel'), (162.5, 'heel'), (162.45, 'heelTop'),
    (160.5, 'crash'), (161.5, 'shadowsWide'), (154.0, 'carSide'), (154.0, 'carFront'), (154.0, 'carRear'),
]
only = arg('--shots')
if only and only is not True:
    keep = set(only.split(','))
    SHOTS = [s for s in SHOTS if s[1] in keep or f'{s[0]}' in keep]
if arg('--film'):            # the whole section, every frame at 24 fps on the film's own cut (nothing renders)
    SHOTS = [(142.1 + i / 24.0, R.suggest(142.1 + i / 24.0)['cam']) for i in range(int(20.7 * 24) + 1)]

scene = bpy.context.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
res = arg('--res', '960x540')
W, H = (int(v) for v in res.split('x'))
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = W, H, 100
scene.render.fps = 24
t0 = time.time()
race = R.build(scene, rain=not arg('--no-rain'))
print(f'[test_race] build {time.time() - t0:.1f} s, objects {len(race.objects)}', flush=True)
check('build: car path length', abs(race.path.length() - R.CAR_LEN) < 0.01, f'{race.path.length():.3f}')
check('build: 38 sodium lamps', len(race.parts['lights']['sodium']) == 38)
check('build: 4 debris pieces', len(race.debris_obs) == 4)
n_tri = sum(len(o.data.polygons) for o in race.objects if o.type == 'MESH')
print(f'[test_race] triangles {n_tri}', flush=True)
nr = [race.parts['lamps']['cones'], race.parts.get('rain'), race.parts['splash'], race.car['shadow']]
check("noRefl: the light cones, rain, splash and contact pad stay out of the road's planar mirror",
      all(o is None or o.hide_probe_plane for o in nr))
check("race['uniforms'] is race.js's U (the keyed values every material reads)", race['uniforms'] is race.U)
check("the road stays out of its own planar mirror's capture (else every puddle reflects the road's underside)",
      'reflector' not in race.parts or race.parts['road'].hide_probe_plane)
check("the screens' glow lights light the set without specular (their reflections are the screens themselves)",
      all(race.lights[k].data.specular_factor == 0.0 for k in ('glow_a', 'glow_b')))

# geometry parity: every mesh's vertex count and position sum (three's axes) against race.js's own (the dump)
pj = os.path.join(OUT, 'parity', 'race.json')
if os.path.isfile(pj):
    import json
    import numpy as np
    js = {}
    for k, v in json.load(open(pj))['meshes'].items():
        js.setdefault(k.split('#')[0], []).append(v)
    mine = {}
    for o in race.objects:
        if o.type != 'MESH':
            continue
        co = np.empty(len(o.data.vertices) * 3, np.float32)
        o.data.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3).astype(np.float64)
        s = co.sum(0)
        t3 = co[:, [0, 2, 1]] * np.array([1.0, 1.0, -1.0])
        mine.setdefault(o.name.split('.')[0], []).append({'count': len(co), 'sum': [s[0], s[2], -s[1]],
                                                          'min': t3.min(0).tolist(), 'max': t3.max(0).tolist()})
    baked = {'race:screen_a', 'race:screen_b', 'race:carShadow', 'race:arrowBoard', 'race:drum_hit', 'race:barricade_legs',
             'race:barricade_boards'}                       # meshes whose object offset the port bakes into the geometry
    ren = {'race:drum_hit_mesh': 'race:drum_hit', 'race:barricade_legs_mesh': 'race:barricade_legs',
           'race:barricade_boards_mesh': 'race:barricade_boards'}
    bad, n_ok = [], 0
    for name, lst in mine.items():
        jn = ren.get(name, name)
        if jn not in js:
            continue
        a = sorted(lst, key=lambda d: (d['count'], d['sum'][0]))
        b = sorted(js[jn], key=lambda d: (d['count'], d['sum'][0]))
        if [d['count'] for d in a] != [d['count'] for d in b]:
            bad.append(f"{name}: {[d['count'] for d in a]} vs {[d['count'] for d in b]}")
            continue
        if jn not in baked:
            # extrusions' caps are triangulated differently (earcut there, Blender's tessellator here): same shape,
            # other vertex sums, so those compare by their bounds
            ext = jn in ('race:barriers', 'race:car_brass')
            if ext:
                err = max(max(abs(x - y) for x, y in zip(da[k], db[k])) for da, db in zip(a, b) for k in ('min', 'max'))
            else:
                err = max(max(abs(x - y) for x, y in zip(da['sum'], db['sum'])) / max(1, da['count']) for da, db in zip(a, b))
            if err > 2e-4:
                bad.append(f'{name}: {"bounds" if ext else "mean position"} off by {err:.2e}')
                continue
        n_ok += 1
    check('geometry parity with race.js (vertex counts, mean positions)', not bad, f'{n_ok} meshes match; ' + '; '.join(bad[:6]))

# the lamp field the materials' doses, the rain and the splash read (Race._fields, built as nodes) against race.js's
# lampField / workField computed here in plain Python at the same points: on the deck, under it (occluded), under the
# gap (lit), by the works, at the heel
def _smooth(e0, e1, x):
    k = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return k * k * (3 - 2 * k)


def _stp(e, x):
    return 1.0 if x >= e else 0.0


def lamp_field_js(P, N):
    Dd = R.D

    def one(L):
        d = np.subtract(L, P)
        d2 = max(d @ d, 0.25)
        l = d / math.sqrt(d2)
        ty = min(1.0, max(0.0, (-0.7 - P[1]) / max(L[1] - P[1], 1e-3)))
        xc, zc = P[0] + (L[0] - P[0]) * ty, P[2] + (L[2] - P[2]) * ty
        under = (_stp(P[1], -0.8) * _stp(Dd['x_r'], xc) * _stp(xc, Dd['x_l']) * _stp(Dd['z_far'], zc)
                 * (1 - _stp(Dd['gap0'], zc) * _stp(zc, Dd['gap1']) * _stp(xc, Dd['x_med'] - 0.6)))
        return (max(N @ l, 0.0) * 0.85 + 0.15) * _smooth(0.18, 0.72, l[1]) * (1 - under) / d2
    acc = 0.0
    kr = math.floor(P[2] / 34 + 0.5)
    for o in (-1, 0, 1):
        z = (kr + o) * 34
        acc += one((1.4, 10.15, z)) * _stp(z, Dd['gap0'] + 0.5) * _stp(Dd['z_far'] + 10, z)
    kl = math.floor((P[2] - 17) / 34 + 0.5)
    for o in (-1, 0, 1):
        z = (kl + o) * 34 + 17
        acc += one((16.6, 10.15, z)) * _stp(Dd['z_far'] + 10, z)
    return acc * 140.0


def work_field_js(P, N):
    acc = 0.0
    for p, a, ci, co, I, key in R.WORK:
        d = np.subtract(p, P)
        d2 = max(d @ d, 1.0)
        l = d / math.sqrt(d2)
        an = np.asarray(a) / np.linalg.norm(a)
        acc += (max(N @ l, 0.0) * 0.8 + 0.2) * _smooth(co, ci, -(l @ an)) * I / d2 * (0.0 if key else 1.0)
    return acc


import numpy as np  # noqa: E402
from eidoblend.sets.unknown_force.race import NB, V  # noqa: E402

FP = [((3.6, 0.6, 0.0), (0, 1, 0)), ((5.0, 1.0, 20.0), (1, 0, 0)), ((3.0, -5.0, 10.0), (0, 1, 0)),
      ((3.0, -5.0, 110.0), (0, 1, 0)), ((0.5, 0.3, 88.0), (0, 0.6, 0.8)), ((-0.55, 0.2, 9.6), (-0.7, 0.3, 0.6))]
me = bpy.data.meshes.new('field_probe')
me.vertices.add(len(FP))
me.vertices.foreach_set('co', [c for p, _ in FP for c in R.to_blender(p)])
na_ = me.attributes.new('nrm3', 'FLOAT_VECTOR', 'POINT')
na_.data.foreach_set('vector', [c for _, n in FP for c in n])
fob = bpy.data.objects.new('field_probe', me)
scene.collection.objects.link(fob)
tree = bpy.data.node_groups.new('field_probe_gn', 'GeometryNodeTree')
tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
nb = NB(tree)
gin, gout = nb.node('NodeGroupInput'), nb.node('NodeGroupOutput')
pos = V(nb, nb.node('GeometryNodeInputPosition').outputs[0], True)
nan = nb.node('GeometryNodeInputNamedAttribute', data_type='FLOAT_VECTOR')
nan.inputs['Name'].default_value = 'nrm3'
(lf,), (wf,) = race._fields(nb, nb.three(pos), [nb.normalize(V(nb, nan.outputs['Attribute'], True))],
                            lambda k: 0.0 if k == 'heel_key' else 1.0)
geo = race._store(nb, gin.outputs['Geometry'], 'lamp_f', lf, 'FLOAT')
geo = race._store(nb, geo, 'work_f', wf, 'FLOAT')
nb.links.new(geo, gout.inputs['Geometry'])
fob.modifiers.new('field_probe', 'NODES').node_group = tree
ev = fob.evaluated_get(bpy.context.evaluated_depsgraph_get())
err = 0.0
for i, (p, n) in enumerate(FP):
    nn = np.asarray(n, float) / np.linalg.norm(n)
    for att, fn in (('lamp_f', lamp_field_js), ('work_f', work_field_js)):
        want = fn(np.asarray(p, float), nn)
        got = ev.data.attributes[att].data[i].value
        err = max(err, abs(got - want) / max(1e-3, abs(want)))
check("the lamp and works fields in nodes (the doses, the rain, the splash) are race.js's", err < 1e-3,
      f'{len(FP)} points, max rel err {err:.1e}; deck {lamp_field_js(np.array(FP[0][0], float), np.array([0, 1.0, 0])):.2f}, '
      f'under the deck {lamp_field_js(np.array(FP[2][0], float), np.array([0, 1.0, 0])):.3f}')
bpy.data.objects.remove(fob, do_unlink=True)
bpy.data.meshes.remove(me)
bpy.data.node_groups.remove(tree)

if arg('--singer'):          # the claudesona on her mark, at the film's scale (the cameras are framed for her)
    try:
        from eidoblend.characters import load_vrm, play_vrma_default
        h = load_vrm(arg('--vrm', 'claude_suit'), scene=scene)      # --vrm <path>: the film's own suit
        h.arm.parent = race.group
        h.arm.matrix_parent_inverse.identity()
        h.arm.location, h.arm.scale = (0.0, 0.0, 0.0), (0.87, 0.87, 0.87)
        play_vrma_default(h, 'sing_low', t=0.0)
        print(f"[test_race] singer on the mark ({os.path.basename(str(arg('--vrm', 'claude_suit')))} x 0.87, sing_low)", flush=True)
    except Exception as e:                      # a probe aid: the set renders without her
        print('[test_race] singer not loaded:', e, flush=True)
cam = bpy.data.objects.new('probe_cam', bpy.data.cameras.new('probe_cam'))
scene.collection.objects.link(cam)
scene.camera = cam
t1 = time.time()
frames = []
REPLAY = 260.0              # break 2: the march replays under shadowsWide (the film's setState('race') for t > 258)
if not arg('--film') and (not isinstance(only, str) or 'replay' in only):
    SHOTS.append((REPLAY, 'shadowsWide'))
rp = R.film_state(REPLAY)
check('film_state: break 2 replays the march (the column phase of 161.6 s, car parked, no boot)',
      rp['march'] == 1 and abs(rp['march_t'] - (161.6 + REPLAY - 258.6)) < 1e-9 and rp['car_t'] == 0 and rp['heel'] == 0
      and R.film_cut(REPLAY) == 'shadowsWide' and R.film_cut(150.8) == 'singer' and R.film_state(150.8) == R.suggest(150.8)['state'])
for i, (t, name) in enumerate(SHOTS):
    f = i + 1
    st = R.film_state(t)                        # the film's state: suggest(t) in the verses, the replay in break 2
    if name in ('carSide', 'carFront', 'carRear'):
        st['heel'] = 0
    race.update(t, st, frame=f)
    race.key_camera(cam, name, t, st, frame=f)
    frames.append((f, t, name, st))
nk = race.finish()
print(f'[test_race] keyed {len(SHOTS)} frames in {time.time() - t1:.1f} s ({nk} keys made linear / constant)', flush=True)
scene.frame_start, scene.frame_end = 1, len(SHOTS)
print('[test_race] render settings:', race.apply_render_settings(scene), flush=True)
scene.eevee.taa_render_samples = int(arg('--samples', 16))

# jump to each frame: the keyed scene must show what race_state says (the .blend plays on its own)
worst = {'car': 0.0, 'heel': 0.0, 'wheel': 0.0, 'debris': 0.0, 'uniform': 0.0}
bad_vis = 0
for f, t, name, st in reversed(frames):
    scene.frame_set(f)
    rs = R.race_state(t, st, race.path, race.debris)
    g = race.car['group']
    worst['car'] = max(worst['car'], (Vector(g.location) - Vector(R.to_blender(rs['car']['pos']))).length)
    worst['heel'] = max(worst['heel'], abs(race.heel['root'].location.z - rs['heel']['y']))
    worst['wheel'] = max(worst['wheel'], abs(race.car['wheels'][0]['spin'].rotation_euler.x - rs['wheel_ang']))
    for (ob, _d), (p, _r) in zip(race.debris_obs, rs['debris']):
        worst['debris'] = max(worst['debris'], (Vector(ob.location) - Vector(R.to_blender(p))).length)
    worst['uniform'] = max(worst['uniform'], abs(race.U.nodes['time'][0].outputs[0].default_value - t),
                           abs(race.U.nodes['crash_age'][0].outputs[0].default_value - rs['U']['crash_age']))
    boot = race.heel['meshes']['leather']
    if boot.hide_render == rs['heel']['visible']:
        bad_vis += 1
for k, v in worst.items():
    check(f'keyed {k} at its frame', v < 1e-3, f'max err {v:.2e}')
check('keyed visibility (the boot only in its shot)', bad_vis == 0, f'{bad_vis} wrong')
dg = bpy.context.evaluated_depsgraph_get()
if 'rain' in race.parts:
    ev = race.parts['rain'].evaluated_get(dg)
    zs = [v.co.z for v in ev.data.vertices]
    check('rain GN: drops placed round the camera', len(zs) == 4 * 5200 and (max(zs) - min(zs)) > 5, f'z range {min(zs):.1f}..{max(zs):.1f}')
if arg('--blend'):
    p = os.path.join(OUT, 'race_probe.blend')
    bpy.ops.wm.save_as_mainfile(filepath=p, compress=True)
    print('[test_race] saved', p)

if not arg('--build-only'):
    scene.render.image_settings.file_format = 'PNG'
    cyc = arg('--cycles')
    tag = '_singer' if arg('--singer') else ''
    for f, t, name, st in frames:
        scene.frame_set(f)
        path = os.path.join(OUT, f'race_{f:02d}_{name}_{t:.2f}{tag}.png')
        scene.render.filepath = path
        t2 = time.time()
        bpy.ops.render.render(write_still=True)
        ok = os.path.isfile(path)
        check(f'render {name} @ {t}', ok, f'{time.time() - t2:.1f} s')
    if cyc and cyc is not True:              # the same frame path traced (round one's look.probe.render_reference)
        from eidoblend.look.probe import render_reference
        for f, t, name, st in frames:
            if name != cyc:
                continue
            path = os.path.join(OUT, f'race_{f:02d}_{name}_{t:.2f}_cycles.png')
            secs = render_reference(scene, path, frame=f, samples=128, bounces=6)
            check(f'cycles reference {name} @ {t}', os.path.isfile(path), f'{secs:.1f} s')
print('[test_race]', 'ALL PASS' if not fails else f'{len(fails)} FAIL: {fails}', flush=True)
sys.exit(1 if fails else 0)
