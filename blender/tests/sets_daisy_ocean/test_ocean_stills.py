"""The ocean set rendered as an asset: built once (no figure on the mark), then stills from views that show its parts
and its controls: the sea of faces out over the moon path, the reveal's bright front partway out, the lanterns before
the faces, the faces at the waterline, the headland from the air, the house with its window and porch light (and with
the porch off), her shut daisies and the dune grass on the rise, the robot stood and breaking up, the human of light
whole and coming apart, the two pages held up to the lens, three of the sea's look uniforms, and the same set under
the engine sky (the sky family's moon at the set's hour, the world wrapped by the set's night). Then the reveal keyed
by animate() as a short H.264 clip, the .blend saved, reopened in place and a frame re-rendered from its keys alone.
Each still is read back and checked for what it must show.

    cd <main checkout> && bash run_blender.sh \
        <worktree>/blender/tests/sets_daisy_ocean/test_ocean_stills.py [--res 960x540] [--samples 16] [--only a,b]
        [--no-sky] [--no-motion]
    (a GPU job; on a shared machine queue it with EIDO_GPU_WRAP: blender/tests/_where.py)
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
from PIL import Image  # noqa: E402

from eidoblend.sets.daisy import ocean  # noqa: E402
from eidoblend.sets.daisy.ocean.staging import D_MOON  # noqa: E402

args = C.argv()
res, samples, only = (960, 540), 16, None
for i, a in enumerate(args):
    if a == '--res':
        res = tuple(int(v) for v in args[i + 1].split('x'))
    if a == '--samples':
        samples = int(args[i + 1])
    if a == '--only':
        only = set(args[i + 1].split(','))
OUT = os.path.join(C.OUT, 'stills')
os.makedirs(OUT, exist_ok=True)
ck = C.Checks('stills')
CS = C.characters_stage()
sc = CS.clean_scene(fps=24)
for w in list(bpy.data.worlds):
    bpy.data.worlds.remove(w)
CS.probe_render(sc, res=res, samples=samples)
ocean.render_settings(sc)                          # the shadow pool for the moon over 3 km, no fast GI at night
t0 = time.time()
O = ocean.build({'scene': sc})
print(f'[stills] set built {time.time() - t0:.1f}s', flush=True)
MY = O.coast.markY
E = MY + 1.52
H = O.coast.house
sea = (math.sin(D_MOON), 0.0, math.cos(D_MOON))   # design: out to sea along the moon path
side = (math.cos(D_MOON), 0.0, -math.sin(D_MOON))

cam = bpy.data.objects.new('probe_cam', bpy.data.cameras.new('probe_cam'))
sc.collection.objects.link(cam)
cam.data.sensor_fit = 'VERTICAL'
cam.data.clip_start, cam.data.clip_end = 0.05, 3200.0
cam.rotation_mode = 'QUATERNION'
sc.camera = cam


def at(p3):
    return Vector(O.to_world(p3))


def aim(pos3, tgt3, fov):
    p, t = at(pos3), at(tgt3)
    cam.location = p
    cam.rotation_quaternion = (t - p).to_track_quat('-Z', 'Y')
    cam.data.angle_y = math.radians(fov)
    bpy.context.view_layer.update()


def off(base, *terms):
    x, y, z = base
    for v, k in terms:
        x, y, z = x + v[0] * k, y + v[1] * k, z + v[2] * k
    return (x, y, z)


EYE = (0.0, E, 0.0)
OVER = off(EYE, (sea, -3.4), (side, 0.7), ((0, 1, 0), 0.9))       # over the mark's shoulder, out to sea
OUT_TO = off(EYE, (sea, 26.0), ((0, 1, 0), -3.2))
BEHIND = off(EYE, (sea, -4.2), (side, 1.5), ((0, 1, 0), 0.1))
FIG = off(EYE, (sea, 22.0), ((0, 1, 0), 2.0))
HOUSE = (H['x'], H['grade'] + 1.8, H['z'])
to_h = (H['x'] / math.hypot(H['x'], H['z']), 0.0, H['z'] / math.hypot(H['x'], H['z']))
FROM_RISE = off(EYE, (to_h, -1.2), ((0, 1, 0), -0.1))
# the pages: held up 0.55 m in front of the lens, side by side, their text sides toward it
PCAM = off(EYE, (sea, -0.6), ((0, 1, 0), -0.05))
PL = off(PCAM, (sea, 0.55), (side, -0.125))
PR = off(PCAM, (sea, 0.55), (side, 0.125))
pages_st = {'page_2023': {'pos': tuple(at(PL)), 'face': tuple(at(PCAM))},
            'page_2026': {'pos': tuple(at(PR)), 'face': tuple(at(PCAM))}, 'page_flutter': 0.3}
T = 7.3                                            # the clock for every still (the swells' phase)
VIEWS = [
    # name, camera, target, vertical fov, controls
    ('sea_of_faces', OVER, OUT_TO, 40.0, {}),
    ('reveal_front', OVER, OUT_TO, 40.0, {'reveal': 0.42}),
    ('lanterns_before_faces', off(EYE, (sea, -0.6), ((0, 1, 0), 0.35)), off(EYE, (sea, 60.0), ((0, 1, 0), -0.4)), 45.0,
     {'reveal': 0.0}),
    ('waterline_faces', (2.6, MY - 0.3, -3.2), (5.0, -0.6, -22.0), 50.0, {}),
    ('headland_aerial', (7.0, 16.0, 20.0), (-4.0, 0.0, -14.0), 50.0, {}),
    ('house_across_cove', FROM_RISE, HOUSE, 22.0, {}),
    ('house_porch_off', FROM_RISE, HOUSE, 22.0, {'porch': 0.0}),
    ('rise_daisies', (1.5, MY + 0.5, 2.1), (-0.2, MY + 0.15, -0.6), 42.0, {}),
    ('dunes_grass', (-6.0, 1.75, 4.5), (-11.0, 1.2, -24.0), 38.0, {}),
    ('robot_stood', BEHIND, FIG, 40.0, {'robot_rise': 1.0}),
    ('robot_eyes_off', BEHIND, FIG, 40.0, {'robot_rise': 1.0, 'robot_eyes': 0.0}),
    ('robot_breaking_up', BEHIND, FIG, 40.0, {'robot_rise': 1.0, 'robot_dissolve': 0.45}),
    ('human_of_light', BEHIND, FIG, 40.0, {'human_rise': 1.0}),
    ('human_coming_apart', BEHIND, FIG, 40.0, {'human_rise': 1.0, 'human_dissolve': 0.55}),
    ('pages_held_up', PCAM, off(PCAM, (sea, 0.55)), 32.0, pages_st),
    ('look_fog_x4', (7.0, 16.0, 20.0), (-4.0, 0.0, -14.0), 50.0, {'fog': 0.0044}),
    ('look_moon_off', OVER, OUT_TO, 40.0, {'moonI': 0.0}),
    ('look_red_moon', OVER, OUT_TO, 40.0, {'moonCol': (1.0, 0.3, 0.2)}),
]
if only:
    VIEWS = [v for v in VIEWS if v[0] in only]


def render(name, path=None):
    path = path or os.path.join(OUT, f'{name}.png')
    bpy.context.scene.render.filepath = path                 # (the current scene: the file may have been reopened)
    t1 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f'[stills] {name} {time.time() - t1:.1f}s', flush=True)
    return path


def img(path):
    return np.asarray(Image.open(path).convert('RGB'), np.float32) / 255.0


def warm(a):
    return (a[..., 0] > 0.35) & (a[..., 0] > a[..., 2] * 1.4)


stills = {}
for name, p3, t3, fov, st in VIEWS:
    aim(p3, t3, fov)
    O.update(T, st)
    stills[name] = render(name)

for name, p in stills.items():
    a = img(p)
    ck.check(f'{name}: rendered', a.mean() > 0.01, f'mean {a.mean():.3f}')
A = {n: img(p) for n, p in stills.items()}
if 'sea_of_faces' in A:
    w = warm(A['sea_of_faces'])
    ck.check('sea_of_faces: the faces glow warm on the swells', w.mean() > 0.004, f'{w.mean() * 100:.2f} % warm px')
if 'reveal_front' in A and 'sea_of_faces' in A:
    band = slice(int(res[1] * 0.333), int(res[1] * 0.41))   # this view's far sea: from about 40 m out to the horizon
    nr, fr = warm(A['reveal_front'])[band].mean(), warm(A['sea_of_faces'])[band].mean()
    ck.check('reveal 0.42: the faces stop at the front about 40 m out, the far sea still dark (vs the full reveal)',
             fr > 0.002 and nr < fr * 0.2, f'warm px beyond the front {nr * 100:.2f} % vs {fr * 100:.2f} %')
if 'lanterns_before_faces' in A:
    a = A['lanterns_before_faces']
    lit = (a.max(-1) > 0.55).mean()
    ck.check('lanterns_before_faces: no faces yet, the lanterns lit over the dark sea', warm(a).mean() < 0.01 and lit > 0.0002,
             f'{lit * 100:.3f} % bright px, {warm(a).mean() * 100:.3f} % warm')
if 'house_across_cove' in A and 'house_porch_off' in A:
    on, of = warm(A['house_across_cove']).mean(), warm(A['house_porch_off']).mean()
    d = np.abs(A['house_across_cove'] - A['house_porch_off']).mean() * 255
    ck.check('the porch light: on it lights the porch and glints on the cove (vs off)', on > of and d > 0.3,
             f'warm {on * 100:.3f} % vs {of * 100:.3f} %, mean |diff| {d:.2f} / 255')
if 'robot_stood' in A and 'robot_eyes_off' in A:
    d = A['robot_stood'] - A['robot_eyes_off']                 # what its eyes add
    lit = d[..., 0] > 0.1
    rg = d[lit][:, 0].mean() / max(1e-6, d[lit][:, 1].mean()) if lit.any() else 0.0
    ck.check('robot_stood: its lenses glow red (eyes on vs off: a small, red-dominant change)', 20 < lit.sum() < 4000 and rg > 1.4,
             f'{int(lit.sum())} px brighter, red / green of the change {rg:.2f}')
if 'robot_breaking_up' in A:
    a = A['robot_breaking_up']
    gold = (a[..., 0] > 0.7) & (a[..., 1] > 0.45) & (a[..., 2] < a[..., 0] * 0.8)
    ck.check('robot_breaking_up: its fragments\' edges burn gold', gold.mean() > 0.0002, f'{gold.mean() * 100:.3f} % gold px')
if 'human_of_light' in A:
    a = A['human_of_light']
    cy = (a[..., 2] > 0.6) & (a[..., 2] >= a[..., 0])
    ck.check('human_of_light: a figure of cold points', cy.mean() > 0.0005, f'{cy.mean() * 100:.3f} % light px')
if 'pages_held_up' in A:
    a = A['pages_held_up']
    paper = (a.mean(-1) > 0.35).mean()
    mark = ((a[..., 0] > 0.45) & (a[..., 0] > a[..., 2] * 1.25)).mean()
    ck.check('pages_held_up: two sheets fill the frame, their highlights marked', paper > 0.3 and mark > 0.003,
             f'{paper * 100:.1f} % paper, {mark * 100:.2f} % marker')
for name, base in (('look_fog_x4', 'headland_aerial'), ('look_moon_off', 'sea_of_faces'), ('look_red_moon', 'sea_of_faces')):
    if name in A and base in A:
        d = np.abs(A[name] - A[base]).mean() * 255
        ck.check(f'{name}: the uniform changes the picture', d > 0.5, f'mean |diff| {d:.2f} / 255')

# ---- under the engine sky
sky_stills = {}
if '--no-sky' not in args and (only is None or 'sky' in only):
    from eidoblend.sky import make_sky
    from eidoblend.sets.daisy.ocean.staging import wrap_world
    t1 = time.time()
    sky = make_sky(sc, camera=cam, hours=O.SKY['hours'], clouds='clear', cache_dir=os.path.join(OUT, 'sky_cache'),
                   quality='draft', shadows=False)
    sky.update(0.0)
    a_moon = math.degrees(Vector(sky.moon_dir).normalized().angle(Vector(O.moon)))
    ck.check("under the engine sky: the layout meets the sky family's moon", a_moon < 0.5, f'{a_moon:.3f} deg apart')
    sky.bake(frame_start=sc.frame_current, frame_end=sc.frame_current)
    wrap_world(sc.world, O.moon, sky.sun)
    print(f'[stills] sky made and baked {time.time() - t1:.1f}s', flush=True)
    for name, p3, t3, fov, st in [v for v in VIEWS if v[0] in ('sea_of_faces', 'house_across_cove')]:
        aim(p3, t3, fov)
        O.update(T, st)
        sky_stills['sky_' + name] = render('sky_' + name)
    for name, p in sky_stills.items():
        a = img(p)
        ck.check(f'{name}: rendered under the engine sky', a.mean() > 0.01, f'mean {a.mean():.3f}')

# ---- contact sheet
allp = list(stills.items()) + list(sky_stills.items())
th = [Image.open(p).convert('RGB').resize((480, 270)) for _n, p in allp]
sheet = Image.new('RGB', (480 * 3, 270 * ((len(th) + 2) // 3)))
for i, t in enumerate(th):
    sheet.paste(t, ((i % 3) * 480, (i // 3) * 270))
sheet.save(os.path.join(OUT, 'ocean_stills_sheet.png'))

# ---- the reveal keyed on its own clock: a clip, then the saved .blend reopened renders a frame from its keys alone
if '--no-motion' not in args and only is None:
    aim(OVER, OUT_TO, 40.0)
    F0, F1, FPS = 1, 72, 24
    sc.frame_start, sc.frame_end = F0, F1
    O.animate({'reveal': lambda t: ocean.ease(t, 0.2, 2.6), 'echoes_sink': lambda t: ocean.ease(t, 0.0, 2.8),
               'echoes': lambda t: 1.0 - 0.6 * ocean.ease(t, 0.5, 2.8)}, frames=(F0, F1), t0=0.0, fps=FPS)
    seq = os.path.join(OUT, 'reveal_seq')
    os.makedirs(seq, exist_ok=True)
    r = sc.render
    keep = (r.resolution_x, r.resolution_y, r.filepath)
    r.resolution_x, r.resolution_y = 480, 270
    r.filepath = os.path.join(seq, 'f_')
    t1 = time.time()
    bpy.ops.render.render(animation=True)
    print(f'[stills] reveal clip {F1 - F0 + 1} frames {time.time() - t1:.1f}s', flush=True)
    r.resolution_x, r.resolution_y, r.filepath = keep
    mp4 = os.path.join(OUT, 'ocean_reveal_sweep_480p.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-start_number', str(F0),
                    '-i', os.path.join(seq, 'f_%04d.png'), '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
                    '-shortest', '-c:v', 'libx264', '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-crf', '18',
                    '-c:a', 'aac', '-b:a', '96k', mp4], check=False)
    ck.check('the reveal plays as an H.264 clip', os.path.exists(mp4) and os.path.getsize(mp4) > 10000,
             f'{os.path.getsize(mp4) // 1024} KB' if os.path.exists(mp4) else 'missing')
    w0, w1 = (warm(img(os.path.join(seq, f'f_{f:04d}.png'))).mean() for f in (F0, F1))
    ck.check('the keyed reveal sweeps: no faces on its first frame, the sea of faces on its last', w0 < 0.2 * w1 and w1 > 0.004,
             f'warm px {w0 * 100:.2f} % -> {w1 * 100:.2f} %')
    fk = 40
    sc.frame_set(fk)
    first = render('keys_before_save')
    blend = os.path.join(OUT, 'ocean_set_keyed.blend')
    C.save_blend(blend)
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc2 = bpy.context.scene
    sc2.frame_set(fk)
    sc2.render.filepath = os.path.join(OUT, 'keys_reopened.png')
    bpy.ops.render.render(write_still=True)
    a, b = img(first), img(sc2.render.filepath)
    d = np.abs(a - b) * 255
    ck.check('the reopened .blend renders the same frame from its keys alone (no handlers, no Python)', d.mean() < 1.0,
             f'mean |diff| {d.mean():.3f} / 255, p99 {np.percentile(d, 99):.1f}')

# ---- another hour: built for 21:30, the moon stands higher and the layout turns so it is still out over the sea
if only is None or 'late_moon' in only:
    sc3 = bpy.context.scene
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for cl in list(bpy.data.collections):
        bpy.data.collections.remove(cl)
    O3 = ocean.build({'scene': sc3, 'parts': ('world', 'lights', 'land', 'grass', 'sea', 'echoes', 'house'),
                      'hours': 21.5, 'name': 'set_ocean_late'})
    c3 = bpy.data.objects.new('late_cam', bpy.data.cameras.new('late_cam'))
    sc3.collection.objects.link(c3)
    c3.data.sensor_fit = 'VERTICAL'
    c3.data.clip_start, c3.data.clip_end = 0.05, 3200.0
    c3.rotation_mode = 'QUATERNION'
    sc3.camera = c3
    E3 = O3.coast.markY + 1.52
    s3, k3 = math.sin(D_MOON), math.cos(D_MOON)
    p, tg = Vector(O3.to_world((-s3 * 3.4 + k3 * 0.7, E3 + 0.9, -k3 * 3.4 - s3 * 0.7))), \
        Vector(O3.to_world((s3 * 26.0, E3 + 8.5, k3 * 26.0)))           # 14 deg up: the moon and the faces both in
    c3.location = p
    c3.rotation_quaternion = (tg - p).to_track_quat('-Z', 'Y')
    c3.data.angle_y = math.radians(60.0)
    O3.update(T)
    late = render('late_moon_sea_of_faces')
    a = img(late)
    el = math.degrees(math.asin(O3.moon[2]))
    ck.check('hours=21.5: the set renders under its higher moon (still out over the sea in front of the mark)',
             a.mean() > 0.01 and el > 30.0, f'moon {el:.1f} deg up, mean {a.mean():.3f}')
ck.summary()
with open(os.path.join(OUT, 'test_ocean_stills.json'), 'w') as fh:
    json.dump(ck.rows, fh, indent=1)
