"""test_bin.py: builds THE BIN (eidoblend.sets.unknown_force.bin) headless as a reusable set, keys asset states at probe
frames (the mark's climb out of the can, the light inside it, the hush, the wind in the falling paper) with the set's
own four cameras and their moves, checks what it keyed after jumping to each frame, and renders stills of the set into
out/bin_<camera>_<what>.png, with two views of my own (the leaning lid close, the canyon from above).

Then the set's invariants: right after the build no orphan data is left from the can's glTF import; moved (its root
translated) the set renders the same pictures; a saved .blend renders a keyed frame on its own; dispose() leaves
nothing of the set (the import's meshes, materials and maps, and the keys' actions included); and an options build (no
sky, no lights, a quarter-size atlas, fewer sheets) renders.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sets_uf_race_bin/test_bin.py -- [--build-only] [--res 960x540] [--samples 16]
        [--atlas 1] [--shots tag,tag] [--no-invariants]

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
from eidoblend.sets.unknown_force import bin as B  # noqa: E402
from eidoblend.sets.unknown_force.race import from_blender  # noqa: E402

args = common.script_args()
OUT = os.path.join(HERE, 'out')
CACHE = os.path.join(OUT, 'cache')
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


KINDS = ('objects', 'meshes', 'materials', 'images', 'node_groups', 'lights', 'worlds', 'collections', 'actions',
         'cameras')


def names():
    return {k: {d.name for d in getattr(bpy.data, k)} for k in KINDS}


# (tag, camera, t, state, move {push, u, orbit}): asset states on the probe's clock (t drives the falling paper and the
# flicker of the light inside the can)
SHOTS = [
    ('canyon_mark_low_inside', 'binWide', 1.0, {'climb': 0.0}, {}),
    ('canyon_mark_on_the_lip_pushed_in', 'binWide', 2.0, {'climb': 1.0}, {'push': 2.0, 'u': 1.0}),
    ('readable_pages_below_the_lip', 'paperClose', 3.0, {'climb': 1.0}, {}),
    ('over_the_rim_mark_halfway', 'climb', 4.0, {'climb': 0.5}, {}),
    ('into_the_mouth', 'topDown', 5.0, {'climb': 0.3}, {}),
    ('hushed_rims_down_glow_low', 'climb', 6.0, {'climb': 0.9, 'hush': 1.0, 'glow': 0.3}, {}),
    ('paper_storm_wind_1.6', 'binWide', 7.0, {'climb': 1.0, 'wind': 1.6}, {'push': -3.0, 'u': 0.5}),
    ('lid_leaning_close', 'lid', 8.0, {'climb': 1.0}, {}),
    ('overview_canyon_from_above', 'overview', 9.0, {'climb': 1.0}, {}),
]
only = arg('--shots')
if only and only is not True:
    keep = set(only.split(','))
    SHOTS = [s for s in SHOTS if s[0] in keep or s[1] in keep]
scene = bpy.context.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
bpy.data.orphans_purge(do_recursive=True)
W, H = (int(v) for v in arg('--res', '960x540').split('x'))
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = W, H, 100
scene.render.fps = 24
cam = bpy.data.objects.new('probe_cam', bpy.data.cameras.new('probe_cam'))
scene.collection.objects.link(cam)
scene.camera = cam
before = names()
t0 = time.time()
b = B.build(scene, atlas_scale=float(arg('--atlas', 1.0)), cache_dir=CACHE)
print(f'[test_bin] build {time.time() - t0:.1f} s, objects {len(b.objects)}', flush=True)
check('the set, not the video: no song clock in the module (BRIDGE, film_state, FILM_SHOTS)',
      not any(hasattr(B, k) for k in ('BRIDGE', 'film_state', 'FILM_SHOTS')))
orphans = [m.name for m in bpy.data.meshes if m.users == 0] + [m.name for m in bpy.data.materials if m.users == 0]
check("the can's glTF import leaves no orphan meshes or materials behind", not orphans, ', '.join(orphans[:8]))
check('build: can radius 1.88 m', abs(b.R - 1.8768) < 0.002, f'{b.R:.4f}')
check('build: can rim at 6.2 m', abs(b.parts['can'].dimensions.z - B.H) < 0.01, f'{b.parts["can"].dimensions.z:.3f}')
pj = os.path.join(OUT, 'parity', 'bin.json')
if os.path.isfile(pj):      # the placed pieces against bin.js (bin_parity_dump.mjs): lid, toppled can, lamp, lights
    import json
    J = json.load(open(pj))
    t3 = lambda v: Vector(B.to_blender(v))
    err = max((b.parts['toppled'].location - t3(J['toppled']['pos'])).length,
              (b.parts['lamp'].location - t3(J['lampPos'])).length)
    qj = J['lid']['q']
    ql = b.parts['lid'].rotation_quaternion
    qe = min(sum(abs(a - c) for a, c in zip(ql, B.quat_to_blender(qj))), sum(abs(a + c) for a, c in zip(ql, B.quat_to_blender(qj))))
    check('toppled can and lamp where bin.js puts them; the lid at its angle', err < 1e-3 and qe < 1e-3,
          f'pos {err:.1e}, lid rotation {qe:.1e}')
    # bin.js reads the lid's radius from a bounding box its scale() already scaled, then scales it again: its lid sits
    # about 12 m up, out of every shot. The port leans it against the can's front left, as BIN.md describes.
    lid_z = b.parts['lid'].location.z
    check('the lid leans against the can (BIN.md), not 12 m up (bin.js)', 0.5 < lid_z < 3.0 and J['lid']['pos'][1] > 10,
          f'port z {lid_z:.2f} m; bin.js y {J["lid"]["pos"][1]:.2f} m')
    b.update(230, {'climb': 1})                     # the dump's last update
    le = 0.0
    for k, v in J['lights'].items():
        if k == 'hemi':
            continue
        o = b.lights[k]
        le = max(le, (o.location - t3(v['pos'])).length)
        Wt = B.cd(v['i']) if o.data.type != 'SUN' else v['i']
        le = max(le, abs(o.data.energy - Wt) / max(1.0, Wt))
    check('lights at bin.js positions and intensities (4 pi I W)', le < 1e-3, f'max err {le:.1e}')
n_tri = sum(len(o.data.polygons) for o in b.objects if o.type == 'MESH')
print(f'[test_bin] triangles {n_tri}', flush=True)

# my two views: the lid where it leans (from the canyon floor, clear of the heap) and the canyon from above
lid3 = np.array(from_blender(b.parts['lid'].location))
eye = lid3 + np.array([-0.9, 0.0, 4.4])
eye[1] = max(lid3[1] - 0.2, B.heap_height_three(eye[0], eye[2], b.R) + 0.9)
b.cams['lid'] = {'pos': B.to_blender(eye), 'target': B.to_blender(lid3 + np.array([0.3, 0.1, 0.0])), 'fov': 40}
b.cams['overview'] = {'pos': B.to_blender((16.0, 24.0, 30.0)), 'target': B.to_blender((0.0, 3.0, -2.0)), 'fov': 50}
print(f'[test_bin] lid at {tuple(round(c, 2) for c in lid3)} (three), its camera at {tuple(round(c, 2) for c in eye)}', flush=True)

frames = []
for i, (tag, name, t, st, mv) in enumerate(SHOTS):
    f = i + 1
    b.update(t, st, frame=f)
    b.key_camera(cam, name, frame=f, push=mv.get('push', 0.0), u=mv.get('u', 0.0), orbit=mv.get('orbit', 0.0))
    frames.append((f, t, tag, name, st, mv))
fx = len(SHOTS) + 1                                   # one more keyed frame 1/24 s after the paper storm (not rendered)
storm = [s for s in SHOTS if s[0].startswith('paper_storm')]
if storm:
    b.update(storm[0][2] + 1 / 24, storm[0][3], frame=fx)
b.finish()
scene.frame_start, scene.frame_end = 1, len(SHOTS)
print('[test_bin] render settings:', b.apply_render_settings(scene), flush=True)
scene.eevee.taa_render_samples = int(arg('--samples', 16))
worst = 0.0
for f, t, tag, name, st, mv in reversed(frames):
    scene.frame_set(f)
    c = st.get('climb', 0.0)
    zt = B.lerp(b.Z_IN, b.Z_OUT, B.smooth(0, 1, c))
    want = Vector(B.to_blender((0, b._fill_y3(0, zt) + 0.03, zt)))
    worst = max(worst, (Vector(b.mark.location) - want).length)
check('keyed mark on the climb at its frame', worst < 1e-4, f'max err {worst:.2e}')
hush = [fr for fr in frames if fr[4].get('hush')]
if hush:
    scene.frame_set(hush[0][0])
    r = [b.lights[k].data.energy / b.base[k] for k in ('magenta', 'cyan', 'sodium', 'rim')]
    g = b.lights['inside'].data.energy / b.base['inside']
    check('keyed hush: the rims, the rim spot and the lamp at 0.4; the inside light at its glow', all(abs(x - 0.4) < 1e-4 for x in r)
          and 0.3 * 0.7 <= g <= 0.3 * 1.0 + 1e-6, f'rims {[round(x, 3) for x in r]}, inside {g:.3f}')
if storm:
    def falling_z(f):
        scene.frame_set(f)
        ev = b.falling.evaluated_get(bpy.context.evaluated_depsgraph_get())
        return np.array([v.co[:] for v in ev.data.vertices])
    sf = [fr[0] for fr in frames if fr[2].startswith('paper_storm')][0]
    pa, pb = falling_z(sf), falling_z(fx)
    dz = np.linalg.norm(pb - pa, axis=1)
    check('falling paper GN: sheets between the floor and 23 m, falling a little in 1/24 s',
          pa[:, 2].min() > -1 and pa[:, 2].max() < 24.5 and 0.001 < np.median(dz) < 1.0,
          f'z {pa[:, 2].min():.1f}..{pa[:, 2].max():.1f}; median move {np.median(dz) * 100:.1f} cm per frame')


def img(path):
    from PIL import Image
    return np.asarray(Image.open(path).convert('RGB'), np.float32) / 255.0


def render(path):
    scene.render.filepath = path
    t2 = time.time()
    bpy.ops.render.render(write_still=True)
    return os.path.isfile(path), time.time() - t2


def same(a, c):
    d = np.abs(img(a) - img(c))
    return float(d.mean()), float((d.max(-1) > 0.08).mean())


done = {}
if not arg('--build-only'):
    scene.render.image_settings.file_format = 'PNG'
    for f, t, tag, name, st, mv in frames:
        scene.frame_set(f)
        path = os.path.join(OUT, f'bin_{name}_{tag}.png')
        ok, secs = render(path)
        check(f'render {name}: {tag}', ok, f'{secs:.1f} s')
        done[tag] = (f, path)

if not arg('--build-only') and not arg('--no-invariants'):
    by_tag = {fr[2]: fr for fr in frames}
    probe = [tg for tg in ('canyon_mark_low_inside', 'over_the_rim_mark_halfway') if tg in done]
    b.group.location = (-20.0, 9.0, 3.0)
    bpy.context.view_layer.update()
    for tg in probe:
        f, t, _tag, name, st, mv = by_tag[tg]
        b.key_camera(cam, name, frame=f, push=mv.get('push', 0.0), u=mv.get('u', 0.0), orbit=mv.get('orbit', 0.0))
        scene.frame_set(f)
        p = os.path.join(OUT, f'bin_{name}_{tg}_set_moved.png')
        ok, secs = render(p)
        mad, frac = same(done[tg][1], p) if ok else (1.0, 1.0)
        check(f'moved set renders the same still: {tg}', ok and mad < 0.004 and frac < 0.005,
              f'mean abs diff {mad:.4f}, pixels off by > 0.08: {frac * 100:.2f}%')
    fp = b.focal_point()
    check('focal_point() follows the moved root (world position)',
          (fp - (Vector((-20.0, 9.0, 3.0)) + b.focal.matrix_basis.translation)).length < 1e-6, f'{tuple(round(c, 3) for c in fp)}')
    b.group.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    for tg in probe:
        f, t, _tag, name, st, mv = by_tag[tg]
        b.key_camera(cam, name, frame=f, push=mv.get('push', 0.0), u=mv.get('u', 0.0), orbit=mv.get('orbit', 0.0))
    blend = os.path.join(OUT, 'bin_keyed_probe_frames.blend')
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
    b.dispose()
    now = names()
    extra = {k: sorted(now[k] - before[k]) for k in KINDS}
    # what apply_render_settings put on the scene (the fog's compositor group), the render's own images and the probe
    # camera's keys are the scene's, not the set's
    scene_level = {'node_groups': {'eido_sky_fog'}, 'images': {'Render Result', 'Viewer Node'}}
    left = {k: [n for n in v if n not in scene_level.get(k, set()) and not n.startswith('probe_cam')] for k, v in extra.items()}
    left = {k: v for k, v in left.items() if v}
    check("dispose(): nothing of the set left (the can's imported meshes, materials and maps, and the keys' actions included)",
          not left, f'{left}')
    ob = B.build(scene, sky=False, lights=False, atlas_scale=0.25, sheets=500, balls=40, falling=50, cache_dir=CACHE)
    check('options build: no lights, no world', not ob.parts.get('lights') and getattr(ob, 'world', None) is None)
    ob.update(1.0, {'climb': 1.0}, frame=1)
    ob.key_camera(cam, 'binWide', frame=1)
    ob.finish()
    # without its own lights and sky the set waits for the film's: a plain grey world stands in for them here
    pw = bpy.data.worlds.new('probe_world')
    pw.use_nodes = True
    pw.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.8
    scene.world = pw
    scene.frame_set(1)
    p = os.path.join(OUT, 'bin_binWide_options_nosky_nolights_atlas0.25_500sheets_grey_world.png')
    ok, secs = render(p)
    check('render the options build', ok, f'{secs:.1f} s')
    keep = [(tg, done[tg]) for tg in ('over_the_rim_mark_halfway', 'paper_storm_wind_1.6') if tg in done]
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
print('[test_bin]', 'ALL PASS' if not fails else f'{len(fails)} FAIL: {fails}', flush=True)
sys.exit(1 if fails else 0)
