"""test_race.py: builds THE RACE (eidoblend.sets.unknown_force.race) headless as a reusable set, keys asset states at
probe frames (the screens, the car on its run, through the works and over the edge, the march's shadows, the boot)
with the set's own cameras, checks what it keyed against the pure state (race_state) after jumping to each frame, and
renders stills of the set into out/race_<camera>_<what>.png.

Then the set's invariants: moved (its root translated) it renders the same pictures, since everything reads set-local
coordinates; a saved .blend renders a keyed frame on its own; and an options build (no mirror, no sky, no towers, no
rain, dim lamps) builds and renders after the full set's dispose().

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sets_uf_race_bin/test_race.py -- [--build-only] [--shots tag,tag] [--res 960x540]
        [--samples 16] [--no-rain] [--cycles <tag>] [--no-invariants]

Prints PASS / FAIL lines; exits 1 on a FAIL.
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend import common  # noqa: E402
from eidoblend.sets.unknown_force import race as R  # noqa: E402
from eidoblend.sets.unknown_force.race import NB, V  # noqa: E402

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


PATH = R.car_path()


def s_at(z):
    """The car's path distance where it stands at three's z (metres down the road)."""
    return R._path_at_z(PATH, z)


CRASHED = {'car_t': 1.0, 'crash': 1.0}           # the car settled in the drain (out of the deck shots)
# a high view of the works, the broken deck, the gap and the drain, the billboards far behind (not one of race.js's
# cameras: the layout and the scale at a glance)
OVERVIEW = {'pos': [46.0, 34.0, 150.0], 'target': [6.0, -6.0, 75.0], 'fov': 50}
# (tag, camera, t, state): the set's own cameras on asset states (seconds on the probe's clock; t drives the rain,
# the screens' flow, the engine's shake and the march's lockstep)
SHOTS = [
    ('gold_screen', 'billA', 1.0, dict(CRASHED)),
    ('red_screen_tearing', 'billB', 2.0, dict(CRASHED)),
    ('faces_glancing_across', 'billboards', 3.2, dict(CRASHED, gaze=R.glance(3.2, 2.0))),
    ('performer_mark_under_red_screen', 'singer', 4.0, dict(CRASHED)),
    ('car_out_between_billboards', 'carPass', 5.0, {'car_s': s_at(-34.0)}),
    ('car_beside_the_mark', 'carTrack', 6.0, {'car_t': 0.776}),
    ('car_into_the_drum_taper', 'carChase', 7.0, {'car_s': s_at(44.0)}),
    ('barricades_flying', 'carChase', 8.0, {'car_s': s_at(70.0)}),
    ('car_over_the_edge', 'crashLow', 9.0, {'car_t': 1.0, 'crash': 0.15}),
    ('nose_into_the_drain', 'crashLow', 10.0, {'car_t': 1.0, 'crash': 0.45}),
    ('over_on_its_back', 'crashLow', 11.0, {'car_t': 1.0, 'crash': 0.72}),
    ('settled_wheels_up_steam', 'crashLow', 12.0, dict(CRASHED)),
    ('whole_trajectory', 'crash', 13.0, {'car_t': 1.0, 'crash': 0.35}),
    ('march_on_the_wall', 'shadows', 14.0, dict(CRASHED, march=1.0, march_t=1.6)),
    ('march_wide_caption_room', 'shadowsWide', 15.0, dict(CRASHED, march=1.0, march_t=2.3)),
    ('boot_hovering', 'heel', 16.0, dict(CRASHED, heel=0.55)),
    ('boot_struck_toe_down', 'heel', 17.0, dict(CRASHED, heel=0.8)),
    ('heel_on_the_manifesto', 'heelTop', 18.0, dict(CRASHED, heel=0.7)),
    ('craft_side', 'carSide', 19.0, {'car_s': s_at(22.0)}),
    ('craft_front', 'carFront', 19.0, {'car_s': s_at(22.0)}),
    ('craft_rear', 'carRear', 19.0, {'car_s': s_at(22.0)}),
    ('overview_works_gap_drain', 'overview', 20.0, dict(CRASHED)),
]
only = arg('--shots')
if only and only is not True:
    keep = set(only.split(','))
    SHOTS = [s for s in SHOTS if s[0] in keep or s[1] in keep]

scene = bpy.context.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
W, H = (int(v) for v in arg('--res', '960x540').split('x'))
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = W, H, 100
scene.render.fps = 24
t0 = time.time()
race = R.build(scene, rain=not arg('--no-rain'))
race.cams['overview'] = R.cam_to_blender(OVERVIEW)
print(f'[test_race] build {time.time() - t0:.1f} s, objects {len(race.objects)}', flush=True)
check('build: car path length', abs(race.path.length() - R.CAR_LEN) < 0.01, f'{race.path.length():.3f}')
check('build: 38 sodium lamps', len(race.parts['lights']['sodium']) == 38)
check('build: 4 debris pieces', len(race.debris_obs) == 4)
check('the set, not the video: no song clock in the module (CUES, suggest, film_state, film_cut, FILM_SPANS)',
      not any(hasattr(R, k) for k in ('CUES', 'suggest', 'film_state', 'film_cut', 'FILM_SPANS')))
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
wn = [n for n in race.mats['towers'].node_tree.nodes if n.bl_idname == 'ShaderNodeTexWhiteNoise']
check("the windows' hash reads a rounded seed (TSL's toUint): solid windows, no speckle that shimmers as the camera moves",
      wn and all(n.inputs['W'].is_linked and n.inputs['W'].links[0].from_node.operation == 'FLOOR' for n in wn), f'{len(wn)} hashes')

# geometry parity: every mesh's vertex count and position sum (three's axes) against race.js's own (the dump)
pj = os.path.join(OUT, 'parity', 'race.json')
if os.path.isfile(pj):
    import json
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

cam = bpy.data.objects.new('probe_cam', bpy.data.cameras.new('probe_cam'))
scene.collection.objects.link(cam)
scene.camera = cam
t1 = time.time()
frames = []
for i, (tag, name, t, st) in enumerate(SHOTS):
    f = i + 1
    race.update(t, st, frame=f)
    race.key_camera(cam, name, t, st, frame=f)
    frames.append((f, t, tag, name, st))
nk = race.finish()
print(f'[test_race] keyed {len(SHOTS)} frames in {time.time() - t1:.1f} s ({nk} keys made linear / constant)', flush=True)
scene.frame_start, scene.frame_end = 1, max(1, len(SHOTS))
print('[test_race] render settings:', race.apply_render_settings(scene), flush=True)
scene.eevee.taa_render_samples = int(arg('--samples', 16))

# jump to each frame: the keyed scene must show what race_state says (the .blend plays on its own)
worst = {'car': 0.0, 'heel': 0.0, 'wheel': 0.0, 'debris': 0.0, 'uniform': 0.0}
bad_vis = 0
for f, t, tag, name, st in reversed(frames):
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
check('keyed visibility (the boot only where heel > 0)', bad_vis == 0, f'{bad_vis} wrong')
dg = bpy.context.evaluated_depsgraph_get()
if 'rain' in race.parts:
    ev = race.parts['rain'].evaluated_get(dg)
    zs = [v.co.z for v in ev.data.vertices]
    check('rain GN: drops placed round the camera', len(zs) == 4 * 5200 and (max(zs) - min(zs)) > 5, f'z range {min(zs):.1f}..{max(zs):.1f}')


def img(path):
    from PIL import Image
    return np.asarray(Image.open(path).convert('RGB'), np.float32) / 255.0


def render(path):
    scene.render.filepath = path
    t2 = time.time()
    bpy.ops.render.render(write_still=True)
    return os.path.isfile(path), time.time() - t2


def same(a, b):
    d = np.abs(img(a) - img(b))
    return float(d.mean()), float((d.max(-1) > 0.08).mean())


done = {}
if not arg('--build-only'):
    scene.render.image_settings.file_format = 'PNG'
    for f, t, tag, name, st in frames:
        scene.frame_set(f)
        path = os.path.join(OUT, f'race_{name}_{tag}.png')
        ok, secs = render(path)
        check(f'render {name}: {tag}', ok, f'{secs:.1f} s')
        done[tag] = (f, path)
    cyc = arg('--cycles')
    if cyc and cyc is not True and cyc in done:        # the same frame path traced (round one's look.probe)
        from eidoblend.look.probe import render_reference
        f, p = done[cyc]
        path = p.replace('.png', '_cycles.png')
        secs = render_reference(scene, path, frame=f, samples=128, bounces=6)
        check(f'cycles reference {cyc}', os.path.isfile(path), f'{secs:.1f} s')

if not arg('--build-only') and not arg('--no-invariants'):
    # 1. moved: the root translated, the cameras re-keyed through it; every material, light, effect and camera reads
    #    set-local coordinates, so each still must come out the same
    probe = [tg for tg in ('faces_glancing_across', 'car_beside_the_mark', 'heel_on_the_manifesto', 'march_on_the_wall')
             if tg in done]
    race.group.location = (37.0, -12.0, 4.0)
    bpy.context.view_layer.update()
    by_tag = {fr[2]: fr for fr in frames}
    for tg in probe:
        f, t, _tag, name, st = by_tag[tg]
        race.key_camera(cam, name, t, st, frame=f)
        scene.frame_set(f)
        p = os.path.join(OUT, f'race_{name}_{tg}_set_moved.png')
        ok, secs = render(p)
        mad, frac = same(done[tg][1], p) if ok else (1.0, 1.0)
        check(f'moved set renders the same still: {tg}', ok and mad < 0.004 and frac < 0.005,
              f'mean abs diff {mad:.4f}, pixels off by > 0.08: {frac * 100:.2f}%')
    race.group.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    for tg in probe:
        f, t, _tag, name, st = by_tag[tg]
        race.key_camera(cam, name, t, st, frame=f)
    # 2. the keyed .blend on its own (reopened below, after the options build)
    blend = os.path.join(OUT, 'race_keyed_probe_frames.blend')
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
    # 3. dispose(), then an options build in the same file: no mirror, no sky (world), no towers, no rain, dim lamps
    race.dispose()
    left = [d.name for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.images,
                                bpy.data.node_groups, bpy.data.lights, bpy.data.worlds, bpy.data.lightprobes,
                                bpy.data.collections, bpy.data.actions)
            for d in coll if d.name.startswith(('race:', 'set:race'))]
    check('dispose(): nothing of the set left (keys and actions included; the caller\'s camera stays)', not left,
          ', '.join(left[:8]))
    ro = R.build(scene, reflect=False, sky=False, towers=False, rain=False, lamp_i=40.0, amounts=('$7', 'NOT YET'))
    check('options build: no mirror, no world, no towers, no rain',
          all(k not in ro.parts for k in ('reflector', 'rain', 'towers')) and getattr(ro, 'world', None) is None,
          f"parts {sorted(ro.parts)}")
    check('options build: lamp_i drives the sodium heads', abs(ro.lights['sodium'].energy - R.cd(40.0)) < 1e-3,
          f'{ro.lights["sodium"].energy:.1f} W')
    check('options build: amounts writes the screens\' bands', [ro.parts['billboards'][k]['amount'] for k in 'ab'] == ['$7', 'NOT YET'])
    st = {'car_t': 0.776, 'gaze': 0.6}
    ro.update(6.0, st, frame=1)
    ro.key_camera(cam, 'billboards', 6.0, st, frame=1)
    ro.finish()
    scene.world = None
    scene.frame_set(1)
    p = os.path.join(OUT, 'race_billboards_options_amounts_nomirror_nosky_notowers_norain_lamps40.png')
    ok, secs = render(p)
    check('render the options build', ok, f'{secs:.1f} s')
    # 4. reopen the keyed .blend: its frames render what this session rendered
    keep = [(tg, done[tg]) for tg in ('car_beside_the_mark', 'nose_into_the_drain') if tg in done]
    bpy.ops.wm.open_mainfile(filepath=blend)
    scene = bpy.context.scene
    scene.render.image_settings.file_format = 'PNG'
    for tg, (f, p0) in keep:
        scene.frame_set(f)
        p = p0.replace('.png', '_reopened.png')
        ok, secs = render(p)
        mad, frac = same(p0, p) if ok else (1.0, 1.0)
        check(f'the saved .blend renders the keyed frame on its own: {tg}', ok and mad < 0.004 and frac < 0.005,
              f'mean abs diff {mad:.4f}, pixels off by > 0.08: {frac * 100:.2f}%')
    os.remove(blend)
print('[test_race]', 'ALL PASS' if not fails else f'{len(fails)} FAIL: {fails}', flush=True)
sys.exit(1 if fails else 0)
