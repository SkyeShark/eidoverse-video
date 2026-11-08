"""Verse 3 rendered from the film's cameras: the whole set built, the claudesona (claude_suit at 0.87, a calm clip)
on her mark, the verse keyed by key_verse (cameras, marks, her gestures, springs), then one still per shot at the
moment each shot is about (A alone on the rise ... I she turns to the lens), from the saved keys. Each still is read
back and checked for what it must show (the faces' glow after the reveal, the pages, the robot, the porch light).

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sets_daisy_ocean/test_ocean_shots.py [--sky] [--res 960x540] [--samples 16] [--only B,H]
    --sky: the engine sky (the sky family's make_sky at SKY hours, clear) for camera rays, wrapped by the set's
           night environment (wrap_world); default: the set's own night world
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

from eidoblend.sets.daisy import ocean  # noqa: E402

args = C.argv()
use_sky = '--sky' in args
res = (960, 540)
samples = 16
only = None
for i, a in enumerate(args):
    if a == '--res':
        res = tuple(int(v) for v in args[i + 1].split('x'))
    if a == '--samples':
        samples = int(args[i + 1])
    if a == '--only':
        only = set(args[i + 1].split(','))
tag = 'sky' if use_sky else 'night'
OUT = os.path.join(C.OUT, 'shots_' + tag)
os.makedirs(OUT, exist_ok=True)
ck = C.Checks('shots')
CS = C.characters_stage()
sc = CS.clean_scene(fps=24)
for w in list(bpy.data.worlds):
    bpy.data.worlds.remove(w)
CS.probe_render(sc, res=res, samples=samples)
ocean.render_settings(sc)                          # the shadow pool for the moon over 3 km, no fast GI at night
FPS = 24
F0 = 1
U_END = ocean.VERSE_SECONDS
sc.frame_start, sc.frame_end = F0, F0 + int(U_END * FPS)

t0 = time.time()
cam = bpy.data.objects.new('ocean_cam', bpy.data.cameras.new('ocean_cam'))
sc.collection.objects.link(cam)
sc.camera = cam
sky = None
if use_sky:
    from eidoblend.sky import make_sky
    sky = make_sky(sc, camera=cam, hours=ocean.SKY['hours'], clouds='clear', cache_dir=os.path.join(OUT, 'sky_cache'),
                   quality='draft', shadows=False)
O = ocean.build({'scene': sc, 'sky': sky})
print(f'[shots] set built {time.time() - t0:.1f}s', flush=True)
if sky is not None:
    sky.update(0.0)
    from mathutils import Vector as _V  # noqa: E402
    a_moon = math.degrees(_V(sky.moon_dir).normalized().angle(_V(O.moon)))
    ck.check('the layout meets the sky family\'s moon at SKY hours', a_moon < 0.5, f'{a_moon:.3f} deg apart')

# ---- the claudesona
from eidoblend.characters import load_vrm, play_vrma_default  # noqa: E402
t1 = time.time()
me = load_vrm('claude_suit')
play_vrma_default(me, 'idle', t=0.0)
print(f'[shots] claude_suit + idle {time.time() - t1:.1f}s', flush=True)
t1 = time.time()
rep = O.key_verse(frame_start=F0, fps=FPS, t0=0.0, vrm=me, camera_obj=cam, pulse=lambda u: max(0.0, math.cos(u / 0.46875 * math.pi)) ** 4)
print(f"[shots] key_verse {time.time() - t1:.1f}s: perform {rep.get('perform')}, springs "
      f"{ {k: rep['springs'][k] for k in ('springs', 'joints', 'resets', 'stiffened_frames', 'nan')} if rep.get('springs') else None}", flush=True)
# ---- her gestures, measured on the keyed pose (as the saved file plays it)
from mathutils import Vector  # noqa: E402
from eidoblend.sets.daisy.ocean import _three as T3  # noqa: E402
from eidoblend.sets.daisy.ocean.perform import _Frame  # noqa: E402


def head_forward(f):
    """her face's forward in the world: the normalized head's model rotation (three) on +z, into the world"""
    sc.frame_set(f)
    q = _Frame(me).model_q('head')
    v = T3.apply_q((0.0, 0.0, 1.0), q)
    return (me.arm.matrix_world.to_3x3() @ Vector((v[0], -v[2], v[1]))).normalized()


def bone_world(name, f):
    sc.frame_set(f)
    pb = me.arm.pose.bones[me.humanoid[name]]
    return me.arm.matrix_world @ pb.head


def ang(a, b):
    return math.degrees(a.angle(b))


f = F0 + int(round(21.4 * FPS))
d = (bone_world('rightHand', f) - bone_world('head', f)).length
ck.check('F: her right hand has risen beside her face (wrist within 0.35 m of the head)', d < 0.35, f'{d:.3f} m')
f = F0 + int(round(16.0 * FPS))
d0 = (bone_world('rightHand', f) - bone_world('head', f)).length
ck.check('E: the hand is down before the gesture', d0 > 0.45, f'{d0:.3f} m')
f = F0 + int(round(32.6 * FPS))
sc.frame_set(f)
to_cam = (cam.matrix_world.translation - bone_world('head', f)).normalized()
a = ang(head_forward(f), to_cam)
ck.check('I: she looks into the lens (face forward within 25 deg of the camera)', a < 25, f'{a:.1f} deg')
f = F0 + int(round(13.0 * FPS))
pz = O.pose26(13.0)
page = Vector(O.to_world(pz[0]))
to_page = (page - bone_world('head', f)).normalized()
a = ang(head_forward(f), to_page)
ck.check('D: she reads the 2026 page (face forward within 30 deg of it)', a < 30, f'{a:.1f} deg')
SHOTS = [('A_alone', 1.6), ('B_reveal', 5.6), ('B_crane', 7.2), ('C1_page23', 8.6), ('C2_insert23', 10.2),
         ('D1_page26', 12.4), ('D2_insert26', 14.2), ('E_robot', 15.65), ('E_human', 17.25), ('F_flower', 21.4),
         ('G_house', 24.5), ('H_porch', 29.0), ('I_lens', 32.6)]
if only:
    SHOTS = [s for s in SHOTS if s[0].split('_')[0] in only or s[0] in only]
frames = [(name, F0 + int(round(u * FPS))) for name, u in SHOTS]
C.save_blend(os.path.join(OUT, f'ocean_verse3_{tag}.blend'))

if '--dry' in args:                                # everything but the renders (API check, no GPU)
    ck.summary()
    sys.exit(0)
stills = []
for name, f in frames:
    if sky is not None:                            # one sky frame per still (a bake rebuilds the world: wrap it again)
        t1 = time.time()
        sky.bake(frame_start=f, frame_end=f)
        O.wrap_world(sc.world)
        print(f'[shots] sky frame {f} baked {time.time() - t1:.1f}s', flush=True)
    sc.frame_set(f)
    path = os.path.join(OUT, f'{name}_f{f:04d}.png')
    sc.render.filepath = path
    t1 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f'[shots] {name} frame {f} rendered {time.time() - t1:.1f}s', flush=True)
    stills.append((name, f, path))

# ---- read the stills back
from PIL import Image  # noqa: E402


def img(path):
    return np.asarray(Image.open(path).convert('RGB'), np.float32) / 255.0


for name, f, path in stills:
    ok = os.path.exists(path)
    a = img(path) if ok else None
    ck.check(f'{name}: rendered', ok and a.mean() > 0.01, f'mean {a.mean():.3f}' if ok else 'missing')
    if not ok:
        continue
    warm = (a[..., 0] > 0.35) & (a[..., 0] > a[..., 2] * 1.4)
    if name.startswith('B_'):
        ck.check(f'{name}: the faces glow warm on the sea', warm[: res[1] * 3 // 4].mean() > 0.002, f'{warm.mean() * 100:.2f} % warm px')
    if name.startswith('H_'):
        ck.check(f'{name}: the porch light is on', warm.mean() > 0.0005, f'{warm.mean() * 100:.3f} % warm px')
    if name.startswith('E_robot'):
        red = (a[..., 0] > 0.5) & (a[..., 1] < 0.25)
        ck.check(f'{name}: the robot stands in the moon path (its eyes / gold edges)', (red | warm).mean() > 0.0002,
                 f'{(red | warm).mean() * 100:.3f} %')
# a contact sheet
th = [Image.open(p).convert('RGB').resize((res[0] // 2, res[1] // 2)) for _n, _f, p in stills]
cols = 3
rows = (len(th) + cols - 1) // cols
sheet = Image.new('RGB', (cols * res[0] // 2, rows * res[1] // 2), (0, 0, 0))
for i, t in enumerate(th):
    sheet.paste(t, ((i % cols) * res[0] // 2, (i // cols) * res[1] // 2))
sp = os.path.join(OUT, f'verse3_sheet_{tag}.png')
sheet.save(sp)
print('[shots] sheet', sp)
ck.summary()
with open(os.path.join(OUT, 'test_ocean_shots.json'), 'w') as f:
    json.dump({'checks': ck.rows, 'key_verse': {k: v for k, v in rep.items() if k != 'springs'}}, f, indent=1, default=str)
