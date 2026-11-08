"""Verse 3 under the engine sky: the keyed verse (test_ocean_shots.py's ocean_verse3_night.blend) reopened, the sky
family's sky put up at the set's hour (make_sky, clear, SKY['hours']), the layout checked against its moon, then per
shot one sky frame baked and the world wrapped by the set's night environment (wrap_world: camera rays keep the engine
sky, every other ray sees the set's night) and the still rendered from the film's camera.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sets_daisy_ocean/test_ocean_sky.py [--only A,B]
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
from mathutils import Vector  # noqa: E402

args = C.argv()
only = set(args[args.index('--only') + 1].split(',')) if '--only' in args else None
SRC = os.path.join(C.OUT, 'shots_night', 'ocean_verse3_night.blend')
OUT = os.path.join(C.OUT, 'shots_sky')
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=SRC)
sys.path.insert(0, C.BLENDER_DIR)
from eidoblend.sets.daisy import ocean  # noqa: E402
from eidoblend.sets.daisy.ocean.staging import wrap_world  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402

ck = C.Checks('sky')
sc = bpy.context.scene
cam = sc.camera
group = bpy.data.objects['set:ocean']
moon_world = tuple((group.matrix_world.to_3x3() @ Vector(ocean.sky_moon_dir())).normalized())
t0 = time.time()
sky = make_sky(sc, camera=cam, hours=ocean.SKY['hours'], clouds='clear', cache_dir=os.path.join(OUT, 'sky_cache'),
               quality='draft', shadows=False)
sky.update(0.0)
print(f'[sky] make_sky {time.time() - t0:.1f}s', flush=True)
a_moon = math.degrees(Vector(sky.moon_dir).normalized().angle(Vector(moon_world)))
ck.check("the layout meets the sky family's moon at SKY hours", a_moon < 0.5, f'{a_moon:.3f} deg apart')
sun_el = math.degrees(math.asin(max(-1.0, min(1.0, Vector(sky.sun_dir).normalized().z))))
print(f'[sky] the sky\'s sun stands {sun_el:.1f} deg above the horizon (its lamp is hidden: the set keeps the sun off)',
      flush=True)
if '--dry' in args:                                # the sky put up and checked, nothing baked or rendered (no GPU)
    ck.summary()
    sys.exit(0)

FPS = sc.render.fps
SHOTS = [('A_alone', 1.6), ('B_reveal', 5.6), ('B_crane', 7.2), ('C1_page23', 8.6), ('E_robot', 15.65),
         ('E_human', 17.25), ('F_flower', 21.4), ('G_house', 24.5), ('H_porch', 29.0), ('I_lens', 32.6)]
if only:
    SHOTS = [s for s in SHOTS if s[0].split('_')[0] in only or s[0] in only]
stills = []
for name, u in SHOTS:
    f = sc.frame_start + int(round(u * FPS))
    t1 = time.time()
    sky.bake(frame_start=f, frame_end=f)
    wrap_world(sc.world, moon_world, sky.sun)
    tb = time.time() - t1
    sc.frame_set(f)
    path = os.path.join(OUT, f'{name}_sky_f{f:04d}.png')
    sc.render.filepath = path
    t1 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f'[sky] {name} frame {f}: sky baked {tb:.1f}s, rendered {time.time() - t1:.1f}s', flush=True)
    stills.append((name, f, path))

from PIL import Image  # noqa: E402
night = os.path.join(C.OUT, 'shots_night')
for name, f, path in stills:
    ok = os.path.exists(path)
    a = np.asarray(Image.open(path).convert('RGB'), np.float32) / 255.0 if ok else None
    ck.check(f'{name}: rendered under the engine sky', ok and a.mean() > 0.01, f'mean {a.mean():.3f}' if ok else 'missing')
    ref = os.path.join(night, f'{name}_f{f:04d}.png')
    if ok and os.path.exists(ref):
        b = np.asarray(Image.open(ref).convert('RGB'), np.float32) / 255.0
        h = a.shape[0]
        top_a, top_b = a[: h // 3].mean(), b[: h // 3].mean()
        print(f'[sky] {name}: sky third {top_a:.3f} (engine sky) vs {top_b:.3f} (the set\'s own night)', flush=True)
th = [Image.open(p).convert('RGB').resize((480, 270)) for _n, _f, p in stills]
sheet = Image.new('RGB', (480 * 3, 270 * ((len(th) + 2) // 3)))
for i, t in enumerate(th):
    sheet.paste(t, ((i % 3) * 480, (i // 3) * 270))
sheet.save(os.path.join(OUT, 'verse3_sheet_sky.png'))
ck.summary()
with open(os.path.join(OUT, 'test_ocean_sky.json'), 'w') as fh:
    json.dump(ck.rows, fh, indent=1)
