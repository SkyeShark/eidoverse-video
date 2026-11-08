"""Probe: the UNKNOWN FORCE city (with the hole inside it) built in Blender 5.2 and rendered from the film's cameras.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 \
        bash run_blender.sh <worktree>/blender/tests/sets_uf_city/test_city_render.py [--no-render] [--shots a,b]
        [--samples 16] [--res 960x540] [--bloom] [--save] [--power 1.0] [--her] [--vrm path] [--sweep]
        [--compare] [--refs dir] [--tag _suffix] [--clamp-indirect 10] [--set rain=0,wet=0.5] [--hash hoskins]
        [--lapse dive,hole]

Builds the city (seed 1909) and checks it numerically: the buildings, signs, lamps and cars against the engine's
counts (1908, 4446 + the hole's 24, 1967, 2161), the merged buffers, the Geometry Nodes systems after evaluation (rain
quads round the camera, cars on the roads, camera-facing cables), the uniforms and the pixel-angle driver, the keyed
dive (camera, clock, focal light, rain velocity), the light linking of the hole's lights. Then renders stills (EEVEE,
AgX) from the dive at the engine's mid-shot times, the city's two static views and the eight chorus cameras into
out/, driven as the film's probe stage drove them. --her imports the claudesona (claude_suit.vrm, or --vrm) on her
mark for the chorus shots. --compare writes out/compare_<shot>.png: the film's own WebGPU still of that shot (the
probe stage's, from --refs, default <cwd>/work/unknown_force/sets/probes) beside this render. --lapse dive,hole renders
the probe stage's divelapse and holelapse (the whole dive, the eight chorus shots start to end) at half size into
out/lapse_<which>/ and out/lapse_<which>.mp4. Prints PASS / FAIL.
"""
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from eidoblend.common import script_args  # noqa: E402
from eidoblend.sets.unknown_force import citykit as KIT  # noqa: E402
from eidoblend.sets.unknown_force import city as C  # noqa: E402
from eidoblend.sets.unknown_force import hole as H  # noqa: E402

OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
args = script_args()


def opt(name, default=None):
    return args[args.index(name) + 1] if name in args else default


RENDER = '--no-render' not in args
SAMPLES = int(opt('--samples', 16))
RES = [int(v) for v in opt('--res', '960x540').split('x')]
TAG = opt('--tag', '')                      # a suffix for the stills' names (a variant beside the probes)
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('[uf-city] %s %s %s' % ('PASS' if ok else 'FAIL', name, detail), flush=True)


def empty_scene():
    for c in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras,
              bpy.data.node_groups, bpy.data.images, bpy.data.worlds):
        for x in list(c):
            c.remove(x)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)


empty_scene()
scene = bpy.context.scene
scene.render.resolution_x, scene.render.resolution_y = RES
scene.render.resolution_percentage = 100
scene.render.fps = 24
KIT.eevee_settings(scene, samples=SAMPLES)
if opt('--clamp-indirect'):                 # EEVEE's clamp on indirect light (reflections included), 0 = off
    scene.eevee.clamp_surface_indirect = float(opt('--clamp-indirect'))
scene.render.film_transparent = False
t0 = time.perf_counter()
city = C.build(scene=scene, **({'hash': opt('--hash')} if opt('--hash') else {}))
build_s = time.perf_counter() - t0
P = city['parts']
K = P['kit']
hole = P['hole']
P['apply_atmosphere'](scene)
check('build time', build_s < 240, f'{build_s:.1f} s')
check('buildings (engine: 1908)', P['stats']['buildings'] == 1908, str(P['stats']['buildings']))
check('building signs (engine: 4446)', P['stats']['signs'] == 4446, str(P['stats']['signs']))
check('lamps (engine: 1967)', P['stats']['lamps'] == 1967, str(P['stats']['lamps']))
check('cars (engine: 2161)', P['stats']['cars'] == 2161, str(P['stats']['cars']))
nsign = len(P['signs'].data.polygons)
check('signs mesh: one quad per sign + the hole\'s 24 city signs', nsign == 4446 + 24, str(nsign))
M = P['meshes']
vc = {k: len(o.data.vertices) for k, o in M.items()}
check('merged buffers (vertices as the engine)', vc['uf_towers_concrete'] == 109464 and vc['uf_towers_metal'] == 45336
      and vc['uf_frames'] == 326980 and vc['uf_strips'] == 41016 and vc['uf_far'] == 10080, str(vc))
tris = sum(len(o.data.polygons) * 2 for o in M.values())
check('city triangles', 300_000 < tris < 1_200_000, f'{tris}')
# the uniforms and the pixel-angle driver
U = K.U
check('uniforms node group', all(('u_' + n) in U.tree.nodes for n, _ in KIT.U_FLOATS), ', '.join(U.names()))
cam_d = bpy.data.cameras.new('probe_cam')
cam_d.clip_start, cam_d.clip_end = 0.25, 6000.0
cam = bpy.data.objects.new('probe_cam', cam_d)
scene.collection.objects.link(cam)
scene.camera = cam
f0, f1 = C.key_dive(cam, K, frame_start=1, fps=24)
check('dive keyed (40.8 s at 24 fps)', (f0, f1) == (1, 980), f'{f0}..{f1}')
scene.frame_start, scene.frame_end = 1, 980
scene.frame_set(int(16 * 24) + 1)
dg = bpy.context.evaluated_depsgraph_get()
pix_eval = U.tree.evaluated_get(dg).nodes['u_pix'].outputs[0].default_value if hasattr(U.tree, 'evaluated_get') else None
pix_want = 2 * math.tan(cam.data.angle_y / 2) / RES[1]
check('pix driver follows the active camera', pix_eval is not None and abs(pix_eval - pix_want) < 1e-6,
      f'{pix_eval} vs {pix_want:.6g}')
tv = U.tree.evaluated_get(dg).nodes['u_time'].outputs[0].default_value
check('keyed clock at frame 385 = 16.0 s', abs(tv - 16.0) < 1e-4, f'{tv:.4f}')
want = C.dive_cam(16.0)
camp = cam.evaluated_get(dg).matrix_world.translation
check('keyed camera = dive_cam(16)', (camp - __import__('mathutils').Vector(want['pos'])).length < 1e-3,
      f'{tuple(round(v, 2) for v in camp)}')
fp = [U.tree.evaluated_get(dg).nodes['u_focal_pos_' + c].outputs[0].default_value for c in 'xyz']
check('keyed focal = dive_focal(16)', max(abs(a - b) for a, b in zip(fp, C.dive_focal(16.0))) < 1e-3, str(fp))
# Geometry Nodes systems, evaluated
rain = P['rain'].evaluated_get(dg).data
check('rain: 26000 streaks round the camera', len(rain.vertices) == 26000 * 4, str(len(rain.vertices)))
rv = np.empty(len(rain.vertices) * 3, np.float32)
rain.vertices.foreach_get('co', rv)
rv = rv.reshape(-1, 3)
off = np.abs(rv - np.asarray(camp, np.float32))
check('rain wraps the camera (70 x 70 x 56 m box)', off[:, 0].max() < 36 and off[:, 1].max() < 36 and off[:, 2].max() < 30,
      f'max offsets {off.max(0).round(1)}')
cars = P['traffic'].evaluated_get(dg).data
check('traffic: one 8-vertex car per path', len(cars.vertices) == 2161 * 8, str(len(cars.vertices)))
cz = np.empty(len(cars.vertices) * 3, np.float32)
cars.vertices.foreach_get('co', cz)
cz = cz.reshape(-1, 3)
check('cars ride the street (z in 12..13.4 m)', cz[:, 2].min() > 11.9 and cz[:, 2].max() < 13.5,
      f'{cz[:, 2].min():.2f}..{cz[:, 2].max():.2f}')
ncar_v = len(cars.vertices)
scene.frame_set(int(20 * 24) + 1)
dg = bpy.context.evaluated_depsgraph_get()
cz2 = np.empty(ncar_v * 3, np.float32)
P['traffic'].evaluated_get(dg).data.vertices.foreach_get('co', cz2)
moved = np.linalg.norm(cz2.reshape(-1, 3)[::8] - cz[::8], axis=1)
check('cars move with the keyed clock (4 s: 13-21 m/s)', 40 < float(np.median(moved)) < 90,
      f'median {np.median(moved):.1f} m')
cl = P['clouds'].evaluated_get(dg).matrix_world.translation
cpos = cam.evaluated_get(dg).matrix_world.translation
check('the cloud deck rides the camera in x and y (makeClouds\' update)', abs(cl.x - cpos.x) < 1e-3 and
      abs(cl.y - cpos.y) < 1e-3 and abs(cl.z) < 1e-6, f'deck ({cl.x:.1f}, {cl.y:.1f}), camera ({cpos.x:.1f}, {cpos.y:.1f})')
cab = hole['parts']['cables'].evaluated_get(dg).data
cv = np.empty(len(cab.vertices) * 3, np.float32)
cab.vertices.foreach_get('co', cv)
cv = cv.reshape(-1, 2, 3)
check('cables: 24 ribbons placed from their ends', len(cab.vertices) == 24 * 22 and np.isfinite(cv).all(),
      str(len(cab.vertices)))
# light linking
L = hole['parts']['lights']
rc = L['ring'].light_linking.receiver_collection
check('quiet ring lights the hole + her', rc is not None and {c.name for c in rc.children} ==
      {hole['collection'].name, hole['parts']['her'].name})
rc2 = L['screen0'].light_linking.receiver_collection
check('screen and kicker lights reach her only', rc2 is not None and [c.name for c in rc2.children] ==
      [hole['parts']['her'].name])
check('the hole: 12 billboards, 4 tickers, 48 arms', len(hole['parts']['billboards']) == 12 and
      len(hole['parts']['tickers']) == 4 and len(hole['parts']['arms']) == 48)
check('audit flags as the engine set them (rain, clouds, traffic, pillar, cables)',
      P['rain'].get('no_support_check') and P['traffic'].get('no_clipping_check') and
      hole['parts']['column'].get('no_camera_collide') and hole['parts']['cables'].get('no_clipping_check') and
      all(s.get('no_z_fight_check') for s in P['clouds'].children))

# ------------------------------------------------------------------ camera clearance (the engine's BVH promises)
from mathutils.bvhtree import BVHTree  # noqa: E402
from mathutils import Vector  # noqa: E402
solid = [o for o in list(P['meshes'].values()) + list(hole['parts']['meshes'].values()) +
         [b['mesh'] for b in hole['parts']['billboards']] + hole['parts']['arms'] + [P['lamps']]]
solid += [o for o in hole['collection'].objects if o.name.startswith('uf_billboard_housing')]
trees = [BVHTree.FromObject(o, dg) for o in solid]


def clearance(p):
    p = Vector(p)
    return min((t.find_nearest(p)[3] for t in trees if t.find_nearest(p)[0] is not None), default=1e9)


dmin = min((clearance(C.dive_cam(t)['pos']), t) for t in np.arange(0.0, 40.81, 0.1))
check('dive: the camera stays >= ~15 m from every surface (the engine\'s BVH check)', dmin[0] > 14.0,
      f'min {dmin[0]:.1f} m at t {dmin[1]:.1f}')
ends = [H.cable_ends(i, k) for i in range(12) for k in (0, 1)]


def seg_dist(p, a, b):
    p, a, b = Vector(p), Vector(a), Vector(b)
    ab = b - a
    u = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (p - (a + ab * u)).length


worst = {}
for nme in H.HOLE_CAMS:
    dur = H.HOLE_CAM_DUR[nme]
    cs, cc = 1e9, 1e9
    for t in np.linspace(0, dur, 61):
        pos = H.hole_cam(nme, t)['pos']
        cs = min(cs, clearance(pos))
        cc = min(cc, min(seg_dist(pos, e['a'], e['b']) for e in ends))
    worst[nme] = (cs, cc)
check('chorus cameras: clear of every solid surface (>= 0.3 m)', all(v[0] >= 0.3 for v in worst.values()),
      ', '.join(f'{k} {v[0]:.2f}' for k, v in worst.items()))
check('chorus cameras: >= 0.74 m from the cables (the engine\'s figure, to two decimals)',
      all(v[1] >= 0.735 for v in worst.values()),
      ', '.join(f'{k} {v[1]:.2f}' for k, v in worst.items()))

# ------------------------------------------------------------------ the singer (optional): the claudesona on her mark
her_objs = []
if '--her' in args:
    try:
        from eidoblend.characters import load_vrm, play_vrma_default
        vrm = Path(opt('--vrm')) if opt('--vrm') else Path(KIT.common.ASSETS_DIR) / 'vrm' / 'claude_suit.vrm'
        if not vrm.exists():
            hits = list(Path(KIT.common.ASSETS_DIR).rglob('claude_suit.vrm'))
            vrm = hits[0] if hits else vrm
        before = set(bpy.data.objects)
        her_h = load_vrm(str(vrm), name='uf_singer')
        play_vrma_default(her_h, 'idle', t=0.0)        # the film's probe stage played the default idle on her
        her_objs = [o for o in bpy.data.objects if o not in before]
        for o in her_objs:
            if o.type == 'MESH':
                hole['parts']['her'].objects.link(o)
        # a loaded VRM faces -Y (the characters family's convention), which is her mark's front (three's +Z)
        check('the claudesona on her mark, idling', bool(her_objs), str(vrm.name))
        meshes_her = [o for o in her_objs if o.type == 'MESH']
        done, left = KIT.fog_objects(K, meshes_her)
        P['apply_atmosphere'](scene, objects=meshes_her)              # (idempotent: wrapped once)
        check('her materials take the haze, as scene.fogNode gave it', done > 0,
              f'{done} wrapped, {left} see-through left as they are')
    except Exception as e:                              # noqa: BLE001
        check('the claudesona on her mark', False, repr(e))

# ------------------------------------------------------------------ renders
if '--power' in args:
    U['power'] = float(opt('--power'))
for kv in (opt('--set') or '').split(','):          # --set rain=0,wet=0.5: uniforms for a variant (with --tag)
    if '=' in kv:
        k, v = kv.split('=', 1)
        U[k.strip()] = float(v)
        print(f'[uf-city] uniform {k.strip()} = {float(v)}', flush=True)
if '--bloom' in args:
    tree = bpy.data.node_groups.new('probe_bloom', 'CompositorNodeTree')
    scene.compositing_node_group = tree
    rl = tree.nodes.new('CompositorNodeRLayers')
    gl = tree.nodes.new('CompositorNodeGlare')
    try:
        gl.glare_type = 'BLOOM'
    except TypeError:
        pass
    for nm, v in (('Threshold', 0.7), ('Strength', 0.55), ('Size', 0.5)):
        if nm in gl.inputs:
            try:
                gl.inputs[nm].default_value = v
            except TypeError:
                pass
    out = tree.nodes.new('NodeGroupOutput')
    tree.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    tree.links.new(rl.outputs['Image'], gl.inputs['Image'])
    tree.links.new(gl.outputs['Image'], out.inputs['Image'])

# The stills are driven as the film's probe stage drove them (work/unknown_force/sets/probes/sets_probe.js), so they
# compare like for like with its stills: the dive's focal light at gain 0.6 over 230 m; the hole's and the static
# views' at (0, 0, 3) (three's (0, 3, 0)), gain 0.35 over 70 m, song time 80 s + the shot's time. (The film's
# conductor itself left gain 1 over 230 m and put the focal point on her chest: the set's animate() keys that.)
FOCAL_DIVE = {'gain': 0.6, 'radius': 230.0}
FOCAL_HOLE = {'pos': (0.0, 0.0, 3.0), 'gain': 0.35, 'radius': 70.0}
shots = []
for t in (4.0, 16.0, 30.0, 40.8):
    shots.append(('dive_t%04.1f' % t, 'dive', t))
for nme in ('avenue', 'skyline'):
    shots.append((f'city_{nme}', 'static', nme))
for nme in H.HOLE_CAMS:
    shots.append((f'hole_{nme}', 'hole', nme))
want_shots = opt('--shots')
if want_shots:
    keep = want_shots.split(',')
    shots = [s for s in shots if any(k in s[0] for k in keep)]
cam2_d = bpy.data.cameras.new('probe_cam_still')
cam2_d.clip_start, cam2_d.clip_end = 0.25, 6000.0
cam2 = bpy.data.objects.new('probe_cam_still', cam2_d)
scene.collection.objects.link(cam2)
scene.render.image_settings.file_format = 'PNG'
times = []
if RENDER:
    for name, kind, what in shots:
        if kind == 'dive':
            scene.camera = cam
            U['focal_gain'], U['focal_r'] = FOCAL_DIVE['gain'], FOCAL_DIVE['radius']
            scene.frame_set(int(round(what * 24)) + 1)
        else:
            scene.camera = cam2
            if kind == 'static':
                pose = city['cams'][what]
                t_song = 80.0
            else:
                tt = H.HOLE_CAM_DUR[what] * 0.5
                pose = H.hole_cam(what, tt)
                t_song = 80.0 + tt
            KIT.apply_cam(cam2, pose)
            # a still: render at a frame where the song clock reads t_song; the dive keyed focal_pos and cam_vel, so
            # key this still's values at its own frame (after the dive's range: the dive's frames keep theirs)
            fr = int(round(t_song * 24)) + 1
            U.key('cam_vel', fr, (0.0, 0.0, 0.0))
            U.key('focal_pos', fr, FOCAL_HOLE['pos'])
            U['focal_gain'], U['focal_r'] = FOCAL_HOLE['gain'], FOCAL_HOLE['radius']
            scene.frame_set(fr)
        path = OUT / f'probe_{name}{TAG}.png'
        scene.render.filepath = str(path)
        ts = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        dt = time.perf_counter() - ts
        times.append(dt)
        ok = path.exists()
        if ok:
            img = bpy.data.images.load(str(path))
            px = np.empty(img.size[0] * img.size[1] * 4, np.float32)
            img.pixels.foreach_get(px)
            px = px.reshape(-1, 4)[:, :3]
            lum = float((px @ np.array([0.2126, 0.7152, 0.0722])).mean())
            bpy.data.images.remove(img)
            check(f'render {name}', np.isfinite(px).all() and lum > 0.01, f'{dt:.1f} s, mean display luma {lum:.3f}')
        else:
            check(f'render {name}', False, 'no file written')
# ------------------------------------------------------------------ the uniforms, swept on one view (small stills)
SWEEP = [('base', {}), ('power_0.35', {'power': 0.35}), ('flash_1', {'flash': 1.0}), ('wet_0', {'wet': 0.0}),
         ('floods_crowns_0', {'flood': 0.0, 'crown': 0.0}), ('fog_cloud_0', {'fog': 0.0, 'cloud': 0.0}),
         ('win_0_neon_0', {'win': 0.0, 'neon': 0.0}), ('street_0', {'street': 0.0}),
         ('focal_gain_4', {'focal_gain': 4.0}), ('screens_column_0', {'screens': 0.0, 'column': 0.0, 'cable': 0.0})]
if RENDER and '--sweep' in args:
    view = opt('--sweep-view', 'avenue')
    scene.camera = cam2
    pose = city['cams'][view] if view in city['cams'] else H.hole_cam(view, H.HOLE_CAM_DUR[view] * 0.5)
    KIT.apply_cam(cam2, pose)
    fr = int(61.0 * 24) + 1
    U.key('cam_vel', fr, (0.0, 0.0, 0.0))
    U.key('focal_pos', fr, C.dive_focal(40.8))
    scene.frame_set(fr)
    scene.render.resolution_x, scene.render.resolution_y = RES[0] // 2, RES[1] // 2
    base = {k: U[k] for k, _ in KIT.U_FLOATS}
    lums = {}
    for tag, change in SWEEP:
        for k, v in base.items():
            if k != 'time':
                U[k] = v
        for k, v in change.items():
            U[k] = v
        path = OUT / f'sweep_{view}_{tag}.png'
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(str(path))
        a = np.empty(im.size[0] * im.size[1] * 4, np.float32)
        im.pixels.foreach_get(a)
        bpy.data.images.remove(im)
        lums[tag] = float((a.reshape(-1, 4)[:, :3] @ np.array([0.2126, 0.7152, 0.0722])).mean())
        print(f'[uf-city] sweep {tag}: luma {lums[tag]:.4f}', flush=True)
    b = lums['base']
    check('sweep: the outro turn-down darkens the city', lums['power_0.35'] < b * 0.85, f"{lums['power_0.35']:.4f} < {b:.4f}")
    check('sweep: windows and neon off darken it', lums['win_0_neon_0'] < b, f"{lums['win_0_neon_0']:.4f}")
    check('sweep: lightning on the deck brightens it', lums['flash_1'] > b, f"{lums['flash_1']:.4f}")
    check('sweep: every control changes the picture', all(abs(v - b) > 1e-4 for k, v in lums.items() if k != 'base'),
          ', '.join(f'{k} {v - b:+.4f}' for k, v in lums.items() if k != 'base'))
    for k, v in base.items():
        U[k] = v
    scene.render.resolution_x, scene.render.resolution_y = RES
# ------------------------------------------------------------------ the outro (song 294.8 s on): the city turns itself
# down around the vanishing point, as the film drove power = 1 - 0.85 smooth((t - 300) / 24); riseUp high in the well
if RENDER and (not want_shots or 'outro' in want_shots):
    t_song = 318.5
    pw = 1 - 0.85 * KIT.smooth((t_song - 300) / 24)
    scene.camera = cam2
    KIT.apply_cam(cam2, H.hole_cam('riseUp', 9.0))
    fr = int(round(t_song * 24)) + 1
    U.key('cam_vel', fr, (0.0, 0.0, 0.0))
    U.key('focal_pos', fr, FOCAL_HOLE['pos'])
    U['focal_gain'], U['focal_r'] = FOCAL_HOLE['gain'], FOCAL_HOLE['radius']
    scene.frame_set(fr)
    U['power'] = pw
    path = OUT / 'probe_hole_riseUp_outro.png'
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    U['power'] = 1.0
    check('render the outro (power %.2f)' % pw, path.exists())
# ------------------------------------------------------------------ the probe stage's lapses (divelapse / holelapse)
# the whole dive (41 frames, one per 1.02 s of song) and the eight chorus shots (5 frames each, start to end), at a
# quarter of the probe size, driven as the stills above, assembled into out/lapse_<dive|hole>.mp4 (H.264, 10 fps)
LAPSE = [x for x in (opt('--lapse') or '').split(',') if x]
if RENDER and LAPSE:
    import shutil
    import subprocess
    scene.render.resolution_x, scene.render.resolution_y = RES[0] // 2, RES[1] // 2
    scene.eevee.taa_render_samples = 8
    for which in LAPSE:
        ldir = OUT / f'lapse_{which}'
        if ldir.exists():
            shutil.rmtree(ldir)
        ldir.mkdir()
        if which == 'dive':
            steps = [('dive', t) for t in np.linspace(0.0, C.DIVE_LEN, 41)]
        else:
            steps = [(n, u * H.HOLE_CAM_DUR[n]) for n in H.HOLE_CAMS for u in np.linspace(0, 1, 5)]
        ts = time.perf_counter()
        for k, (n, t) in enumerate(steps):
            if n == 'dive':
                scene.camera = cam
                U['focal_gain'], U['focal_r'] = FOCAL_DIVE['gain'], FOCAL_DIVE['radius']
                scene.frame_set(int(round(t * 24)) + 1)
            else:
                scene.camera = cam2
                KIT.apply_cam(cam2, H.hole_cam(n, t))
                fr = int(round((80.0 + t) * 24)) + 1 + k            # a frame of its own per lapse step
                U.key('cam_vel', fr, (0.0, 0.0, 0.0))
                U.key('focal_pos', fr, FOCAL_HOLE['pos'])
                U.key('time', fr, 80.0 + t)
                U['focal_gain'], U['focal_r'] = FOCAL_HOLE['gain'], FOCAL_HOLE['radius']
                scene.frame_set(fr)
            scene.render.filepath = str(ldir / f'{which}_{k:03d}.png')
            bpy.ops.render.render(write_still=True)
        n_png = len(list(ldir.glob('*.png')))
        mp4 = OUT / f'lapse_{which}.mp4'
        ff = shutil.which('ffmpeg')
        if ff:
            subprocess.run([ff, '-y', '-loglevel', 'error', '-framerate', '10', '-i', str(ldir / f'{which}_%03d.png'),
                            '-c:v', 'libx264', '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-crf', '18', str(mp4)],
                           check=False)
        check(f'lapse {which}: {len(steps)} frames' + (' and an MP4' if ff else ''), n_png == len(steps) and
              (mp4.exists() or not ff), f'{time.perf_counter() - ts:.1f} s')
    scene.render.resolution_x, scene.render.resolution_y = RES
    scene.eevee.taa_render_samples = SAMPLES
# ------------------------------------------------------------------ the film's own stills beside these renders
# (the probe stage's WebGPU stills, look off: fin_<shot>_off.png). Their probe ran 0.8 s clips; the still is a frame
# near the shot's mid time, the times used here.
REFS = {'dive_t16.0': 'fin_dive16_off.png', 'dive_t40.8': 'fin_dive40_off.png',
        'hole_closeSing': 'fin_hole_close_off.png', 'hole_low': 'fin_hole_low_off.png'}
if RENDER and '--compare' in args:
    from PIL import Image, ImageDraw
    ref_dir = Path(opt('--refs', str(Path.cwd() / 'work' / 'unknown_force' / 'sets' / 'probes')))
    made = 0
    for shot, ref in REFS.items():
        mine, theirs = OUT / f'probe_{shot}.png', ref_dir / ref
        if not (mine.exists() and theirs.exists()):
            continue
        a = Image.open(theirs).convert('RGB')
        b = Image.open(mine).convert('RGB').resize(a.size, Image.LANCZOS)
        sheet = Image.new('RGB', (a.width * 2 + 8, a.height + 28), (12, 12, 14))
        sheet.paste(a, (0, 28))
        sheet.paste(b, (a.width + 8, 28))
        d = ImageDraw.Draw(sheet)
        d.text((8, 7), f'WebGPU (the film\'s probe stage): {ref}', fill=(230, 230, 230))
        d.text((a.width + 16, 7), f'Blender 5.2 EEVEE: probe_{shot}.png', fill=(230, 230, 230))
        sheet.save(OUT / f'compare_{shot}.png')
        made += 1
    check('compare sheets beside the film\'s stills', made > 0, f'{made} written from {ref_dir}')
if '--save' in args:
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'city_probe.blend'), compress=True)
fails = [n for n, ok in results if not ok]
print(f'[uf-city] {len(results) - len(fails)}/{len(results)} passed' + (f'; FAILED: {fails}' if fails else '') +
      (f'; renders {np.mean(times):.1f} s each' if times else ''), flush=True)
