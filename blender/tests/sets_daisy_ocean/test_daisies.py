"""The ocean's daisies (ocean/daisies.py, the port of sets/ocean/daisies.js on the flora family's daisy): every option
of daisies.js exercised, and its header example (a superbloom of 14000 on 60 m with a path cleared across it) built
and rendered: open by day, with a beat's pulse, shut at dusk. The swaying superbloom is one realized field of about
9.7 million vertices: its render wants a 32 GB memory cap (at 12 GB Blender's draw cache runs out of memory).

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_daisies.py --no-render
    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_daisies.py
    (the render: a GPU job; on a shared machine queue it with EIDO_GPU_WRAP: blender/tests/_where.py)
"""
import importlib.util
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

args = C.argv()
NO_RENDER = '--no-render' in args
spec = importlib.util.spec_from_file_location('flora_scene', os.path.join(C.BLENDER_DIR, 'tests', 'flora', '_scene.py'))
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

from eidoblend.flora import reset_flora_occupancy  # noqa: E402
from eidoblend.sets.daisy.ocean import daisies as D  # noqa: E402

OUT = os.path.join(C.OUT, 'daisies')
os.makedirs(OUT, exist_ok=True)
ck = C.Checks('daisies')


def evaluated_points(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.zeros(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    names = [a.name for a in me.attributes]
    ray = None
    if 'ocean_ray' in names:
        a = me.attributes['ocean_ray']
        ray = np.zeros(len(a.data), np.float32)
        a.data.foreach_get('value', ray)
    ev.to_mesh_clear()
    return co.reshape(-1, 3), ray, names


# ------------------------------------------------------------------------------------------------ the set's own field
S.new_scene(res=(960, 540), samples=16)
sc = bpy.context.scene
reset_flora_occupancy()
t0 = time.time()
from eidoblend.sets.daisy.ocean.land import make_coast  # noqa: E402
coast = make_coast()
f = D.build(count=420, width=5.2, depth=4.6, center=(0.25, 0.5), seed=5, height_fn=coast.height_3,
            face_dir=(0.1, 0.6, 1.0), clear=[{'a': (-0.25, 0.0), 'b': (0.25, 0.0), 'w': 1.25}], close=0.0,
            stem_height=(0.16, 0.28), head_scale=1.2, wind=0.0, name='set_field')
print(f'[daisies] the set\'s field {time.time() - t0:.1f}s, stats {f.field.stats}', flush=True)
heads = f.parts['heads'] or f.field.count * D.HEADS_PER_CLUMP
ck.check('count: about 420 heads on the set\'s 5.2 x 4.6 m (flora clumps x heads per clump)', 250 < heads < 650,
         f'{f.field.count} clumps, {heads} heads')
mods = [m.name for m in f.field.prototype.modifiers]
ck.check('pulse: its modifier runs before flora\'s close (the hinge records are still there)', mods[:2] == ['pulse', 'close'],
         f'{mods}')
co0, ray, names = evaluated_points(f.group)
ck.check('pulse: the rays are tagged on the realized field (ocean_ray)', ray is not None and 0.05 < ray.mean() < 0.9,
         f'{ray.mean():.3f} of the vertices are rays' if ray is not None else f'missing: {names}')
f.update(None, {'pulse': 1.0})
co1, _r, _n = evaluated_points(f.group)
d = np.linalg.norm(co1 - co0, axis=1)
is_ray = ray > 0.5
ck.check('pulse 1: the rays grow (move off their hinges), everything else stays put',
         d[is_ray].max() > 0.002 and d[~is_ray].max() < 1e-6,
         f'rays move up to {d[is_ray].max() * 1000:.1f} mm, the rest {d[~is_ray].max() * 1000:.4f} mm')
mats = [m for m in f.field.prototype.data.materials if m]
drv = [m for m in mats if m.node_tree.animation_data and any('ocean_pulse' in fc.data_path for fc in m.node_tree.animation_data.drivers)]
ck.check('pulse: the field has its own petal-glow materials (the flora material is left as it was)',
         len(drv) == len(mats) > 0 and all(m.name.endswith('_pulse') for m in mats), f'{[m.name for m in mats]}')
f.update(None, {'pulse': 0.0, 'close': 1.0})
co2, _r, _n = evaluated_points(f.group)
ck.check('close 1: the rays fold shut (pulse back at 0)', np.linalg.norm(co2 - co0, axis=1)[is_ray].max() > 0.01,
         f'rays move up to {np.linalg.norm(co2 - co0, axis=1)[is_ray].max() * 1000:.0f} mm')
f.update(2.5, {'wind': 0.35}, frame=1)
toff = None
for item in f.field.modifier.node_group.interface.items_tree:
    if getattr(item, 'in_out', None) == 'INPUT' and item.name == 'Time Offset':
        toff = getattr(f.field.modifier.properties.inputs, item.identifier).value
ck.check('t: the sway clock at frame 1 is film time 2.5 s (flora Time Offset)', toff is not None and abs(toff - (2.5 - 1 / 24)) < 1e-6,
         f'Time Offset {toff}')
f.remove()
# ---- palette: daisies.js's [[r, g, b, weight]] (sRGB) -> flora's mix
reset_flora_occupancy()
pal = [[0.85, 0.47, 0.34, 0.7], [0.98, 0.8, 0.32, 0.3]]
g = D.build(count=60, width=1.5, depth=1.5, seed=3, palette=pal, name='palette_field')
ck.check('palette: [[r, g, b, w]] becomes flora\'s colour mix', g.opts['color'] == {(0.85, 0.47, 0.34): 0.7, (0.98, 0.8, 0.32): 0.3}
         and g.field.plan.get('daisy_palette') and len(g.field.plan['daisy_palette']) == 2,
         f"{g.opts['color']}")
g.remove()
# ---- face_dir vs sun_dir, yaw_spread, stem height, head scale: what the brush receives
reset_flora_occupancy()
h = D.build(count=40, width=1.0, depth=1.0, seed=9, sun_dir=(0.0, 0.3, 1.0), yaw_spread=0.4, stem_height=(0.3, 0.5),
            head_scale=2.0, name='opts_field')
hd = h.opts['heading']
ck.check('sun_dir (no face_dir): heads turn toward the sun (three +z = Blender -y)', hd[1] < -0.9 and abs(hd[0]) < 1e-9,
         f'heading {tuple(round(v, 3) for v in hd)}')
o = h.field.plan.get('o') or {}
print('[daisies] plan options', {k: o[k] for k in sorted(o) if not callable(o[k])}, flush=True)
ck.check('yaw_spread / stem_height / head_scale reach the brush',
         abs(o.get('heading_jitter', 0.2) - 0.2) < 1e-9 and abs(o.get('height', 0.4) - 0.4) < 1e-9
         and abs(o.get('head_scale', 2.8) - 2.8) < 1e-9, f"jitter {o.get('heading_jitter')}, height {o.get('height')}, head {o.get('head_scale')}")
h.remove()

# ------------------------------------------------------------------------------------------------ the header example
reset_flora_occupancy()
t0 = time.time()
SUN3 = (-0.9, 0.35, 0.25)                         # the example's sunDir is the caller's: heads toward -x, the sun from there
bloom = D.build_example('superbloom', wind=0.6, sun_dir=SUN3)
SUN_AZ = math.degrees(math.atan2(-SUN3[2], SUN3[0]))           # Blender azimuth of (x, -z) (from +X toward +Y)
SUN_EL = math.degrees(math.asin(SUN3[1] / math.sqrt(sum(c * c for c in SUN3))))
tb = time.time() - t0
hb = bloom.parts['heads'] or bloom.field.count * D.HEADS_PER_CLUMP
print(f'[daisies] superbloom {tb:.1f}s: {bloom.field.count} clumps, {hb} heads, stats {bloom.field.stats}', flush=True)
ck.check('superbloom: about 14000 heads on 60 x 60 m', 9000 < hb < 20000, f'{bloom.field.count} clumps, {hb} heads, {tb:.0f} s')
pts = np.zeros(len(bloom.group.data.vertices) * 3, np.float32)
bloom.group.data.vertices.foreach_get('co', pts)
pts = pts.reshape(-1, 3)
x3, z3 = pts[:, 0], -pts[:, 1]
in_lane = (np.abs(z3) < 1.1 - 0.05) & (np.abs(x3) < 29.9)
ck.check('superbloom: the path stays clear (no plant within 1.1 m of the lane), all inside 60 x 60 m',
         not in_lane.any() and np.abs(x3).max() <= 30.0 and np.abs(z3).max() <= 30.0,
         f'{int(in_lane.sum())} in the lane, extent x {np.abs(x3).max():.1f} z {np.abs(z3).max():.1f}')
gz = D.meadow_height(x3, z3)
ck.check('superbloom: every plant stands on its heightFn', np.abs(pts[:, 2] - gz).max() < 0.02,
         f'max |z - h| {np.abs(pts[:, 2] - gz).max() * 1000:.1f} mm')

if NO_RENDER:
    ck.summary()
    sys.exit(0)

# the meadow under it: the flora fixture's ground plane, bent to the same swell
S.ground(size=80.0)
gd = bpy.data.objects['test_ground']
me = gd.data
import bmesh  # noqa: E402
bm = bmesh.new()
bm.from_mesh(me)
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=120, use_grid_fill=True)
bm.to_mesh(me)
bm.free()
co = np.zeros(len(me.vertices) * 3, np.float32)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
co[:, 2] = D.meadow_height(co[:, 0], -co[:, 1]) - 0.01
me.vertices.foreach_set('co', co.ravel())
me.update()
stills = []


def shot(name, loc, tgt, lens, sun_elev, sun_az, strength=4.0, sky_strength=1.0, color=(1.0, 1.0, 1.0)):
    for o in [o for o in bpy.data.objects if o.type == 'LIGHT' or o.type == 'CAMERA']:
        bpy.data.objects.remove(o)
    S.lights(sun_elev_deg=sun_elev, sun_az_deg=sun_az, strength=strength, physical=True, sky_strength=sky_strength,
             color=color)
    S.camera(loc, tgt, lens)
    p = os.path.join(OUT, f'{name}.png')
    t1 = time.time()
    S.render(p, 1)
    print(f'[daisies] {name} {time.time() - t1:.1f}s', flush=True)
    stills.append((name, p))
    return p


sc.frame_set(1)
bloom.update(0.0, {'close': 0.0, 'pulse': 0.0, 'wind': 0.6})        # set, not keyed: the stills below change them
CLOSE = ((0.4, -2.3, 0.45), (2.6, -2.75, 0.12), 45.0)
shot('superbloom_day_path', (-8.0, 0.4, 1.6), (14.0, -0.6, 0.0), 30.0, SUN_EL, SUN_AZ)
shot('superbloom_day_wide', (-34.0, 22.0, 10.0), (2.0, -6.0, 0.0), 32.0, SUN_EL, SUN_AZ)
p_day_close = shot('superbloom_day_close', *CLOSE, SUN_EL, SUN_AZ)
bloom.update(None, {'pulse': 1.0})
p_pulse_close = shot('superbloom_pulse_close', *CLOSE, SUN_EL, SUN_AZ)
bloom.update(None, {'pulse': 0.0, 'close': 1.0})
shot('superbloom_dusk_shut', *CLOSE, 4.0, SUN_AZ, strength=2.0, color=(1.0, 0.62, 0.4))

from PIL import Image  # noqa: E402
a = np.asarray(Image.open(p_day_close).convert('RGB'), np.float32)
b = np.asarray(Image.open(p_pulse_close).convert('RGB'), np.float32)
ck.check('pulse 1 brightens the petals (the beat\'s glow)', (b - a).mean() > 0.3, f'mean +{(b - a).mean():.2f} / 255')
for name, p in stills:
    im = np.asarray(Image.open(p).convert('RGB'), np.float32) / 255.0
    ck.check(f'{name}: rendered', im.mean() > 0.02, f'mean {im.mean():.3f}')
th = [Image.open(p).convert('RGB').resize((480, 270)) for _n, p in stills]
sheet = Image.new('RGB', (480 * 3, 270 * ((len(th) + 2) // 3)))
for i, t in enumerate(th):
    sheet.paste(t, ((i % 3) * 480, (i // 3) * 270))
sheet.save(os.path.join(OUT, 'superbloom_sheet.png'))
ck.summary()
with open(os.path.join(OUT, 'test_daisies.json'), 'w') as fh:
    json.dump(ck.rows, fh, indent=1)
