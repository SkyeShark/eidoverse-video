"""t_scale.py: P6, the guide's superbloom at scale: four interleaved daisy strokes (size 48, ~20k clumps, one cohort
turned to the sun) over a grass base. Measures plants, realized vertices, geometry-nodes evaluation time, render time
per frame (with and without the Vector pass, which makes EEVEE evaluate the neighbouring frames too) and peak memory.
Writes out/scale_superbloom[_split][_vec].png (--split: the big stand still, motion=False, with a moving meadow in front
of the camera; --vector: the Vector pass on).
    bash run_blender.sh blender/tests/flora/t_scale.py [--size 48] [--vector] [--split]
"""
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402

import bpy  # noqa: E402
from eidoblend.flora import create_flora, reset_flora_occupancy  # noqa: E402

size = float(S.arg('--size', '48'))
sc = S.new_scene(samples=16)
sun, to_sun = S.lights(sun_elev_deg=24, sun_az_deg=-60, strength=4.0, sky_strength=0.7, gradient=True)
S.ground(size=140)
reset_flora_occupancy()
t0 = time.time()
MIX = {'white': 5, 'orange': 3, 'yellow': 1, 'pink': 1}
split = '--split' in S.args()      # the big stand still (instanced, motion=False), a moving meadow in front of the camera
fields = [create_flora('grass', size=size + 10, center=(0, 18), seed=7, height=0.35, density=0.6, motion=not split)]
for seed, dens, heading in ((3, 0.31, None), (17, 0.31, None), (29, 0.27, None), (41, 0.26, (to_sun.x, to_sun.y, to_sun.z))):
    fields.append(create_flora('daisy', size=size, center=(0, 18), seed=seed, density=dens, color=MIX, heading=heading,
                               motion=not split))
if split:
    fields.append(create_flora('grass', size=10, center=(0, 1.5), seed=23, height=0.4, blades='fine'))
    fields.append(create_flora('daisy', size=8, center=(0, 2.5), seed=31, density=0.5, color=MIX))
t_build = time.time() - t0
plants = sum(f.count for f in fields if f.species == 'daisy')
t1 = time.time()
dg = bpy.context.evaluated_depsgraph_get()
verts = 0
for f in fields:
    ev = f.object.evaluated_get(dg)
    me = ev.to_mesh()
    verts += len(me.vertices)
    ev.to_mesh_clear()
t_eval = time.time() - t1
t2 = time.time()
sc.frame_set(2)
bpy.context.evaluated_depsgraph_get()
t_frame = time.time() - t2
print(f'[scale] {plants} daisy clumps + {sum(f.count for f in fields if f.species == "grass")} grass plants; '
      f'{verts / 1e6:.1f} M realized verts (moving strokes); '
      f'build {t_build:.1f} s, first evaluation {t_eval:.1f} s, frame change re-evaluation {t_frame:.1f} s', flush=True)
S.camera((0.0, -6.0, 1.7), (0.0, 12.0, 0.0), 35)
if '--vector' in S.args():
    for vl in sc.view_layers:
        vl.use_pass_vector = True
t3 = time.time()
S.render(os.path.join(S.OUT, 'scale_superbloom' + ('_split' if split else '') + ('_vec' if '--vector' in S.args() else '')
                      + '.png'), 2)
print(f'[scale] render {time.time() - t3:.1f} s (vector pass {"on" if "--vector" in S.args() else "off"})', flush=True)
try:
    import psutil
    print(f'[scale] process RSS {psutil.Process().memory_info().rss / 2**30:.1f} GB')
except ImportError:
    pass
print('[scale] done')
