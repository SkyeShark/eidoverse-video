"""t_mix.py: our meadow mixed with scanned CC0 Poly Haven plants through the same brush (placement, wind, pushers):
a trodden path across fine-habit meadow grass with white / Claude-orange daisies. The scanned plants grow where a
path lets them be seen: grass_medium_02 tufts along its edges, short grass_medium_01, dandelions, weed_plant_02 and a
shrub_sorrel_01 carpet in it, celandine at the meadow's foot. Writes out/mix_<shot>.png and saves out/mix.blend.
    bash run_blender.sh blender/tests/flora/t_mix.py [--no-render]
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402

import bpy  # noqa: E402
from eidoblend.flora import create_flora, reset_flora_occupancy  # noqa: E402

S.new_scene()
S.lights(sun_elev_deg=34, sun_az_deg=-35, strength=4.5, sky_strength=0.7, gradient=True)
S.ground()
reset_flora_occupancy()


def across(x, y):
    """position across the path (a gentle S running along x, its middle at 0): |across| < 0.4 is in the path"""
    return y - 0.35 - 0.18 * math.sin(x * 0.9)


fields = [
    create_flora('grass', size=16, seed=3, height=0.42, blades='fine', clip_fn=lambda x, y: abs(across(x, y)) < 0.45),
    create_flora('daisy', size=9, seed=5, center=(0.3, 2.0), density=0.4, color='white',
                 clip_fn=lambda x, y: abs(across(x, y)) < 0.55),
    create_flora('daisy', size=7, seed=29, center=(-1.2, 2.6), density=0.3, color='orange',
                 clip_fn=lambda x, y: abs(across(x, y)) < 0.55),
    # the path's edges: scanned tufts between the trodden middle and the tall meadow
    create_flora('ph:grass_medium_02', size=9, seed=7, center=(0.0, 0.4), density=1.0,
                 clip_fn=lambda x, y: not (0.28 < abs(across(x, y)) < 0.52)),
    # in the path: short scanned grass, a sorrel carpet, dandelions and weeds
    create_flora('ph:grass_medium_01', size=9, seed=5, center=(0.0, 0.4), density=0.35, variants=['small', 'tiny', 'mid'],
                 clip_fn=lambda x, y: abs(across(x, y)) > 0.4),
    create_flora('ph:shrub_sorrel_01', size=9, seed=19, center=(0.0, 0.4), density=0.8,
                 clip_fn=lambda x, y: abs(across(x, y)) > 0.38),
    create_flora('ph:dandelion_01', size=9, seed=11, center=(0.0, 0.4), density=2.5,
                 clip_fn=lambda x, y: abs(across(x, y)) > 0.42),
    create_flora('ph:weed_plant_02', size=9, seed=23, center=(0.0, 0.4), density=2.0,
                 clip_fn=lambda x, y: abs(across(x, y)) > 0.4),
    # celandine at the meadow's foot on the far side
    create_flora('ph:celandine_01', size=9, seed=13, center=(0.0, 0.4), density=3.0,
                 clip_fn=lambda x, y: not (0.35 < across(x, y) < 0.75)),
]
dg = bpy.context.evaluated_depsgraph_get()
for f in fields:
    ev = f.object.evaluated_get(dg)
    me = ev.to_mesh()
    print(f'[mix] {f.object.name}: {f.count} plants -> {len(me.vertices)} verts, materials {[m.name for m in me.materials]}')
    assert f.count > 0 and len(me.vertices) > 0, f.object.name
    ev.to_mesh_clear()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'mix.blend'))
for name, (loc, tgt, lens) in {
        # low along the path, the meadow rising on both sides
        'low': ((2.2, 0.45, 0.42), (-0.8, 0.3, 0.1), 30),
        # standing in the path looking down at the feet
        'pov': ((0.0, 0.05, 1.62), (0.0, 1.0, 0.0), 24),
        # crouched at the path's edge, close on the scanned plants
        'close': ((0.75, 0.05, 0.3), (0.0, 0.45, 0.04), 35)}.items():
    S.camera(loc, tgt, lens, name='cam_' + name)
    S.render(os.path.join(S.OUT, f'mix_{name}.png'), 1)
print('[mix] done')
