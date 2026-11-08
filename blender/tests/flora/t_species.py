"""t_species.py: the rest of the brush in EEVEE: a small Mojave stand (galleta, blackbrush, creosote, sagebrush,
yucca heroes; the guide's recipe at a smaller size) and planted corn and sunflower rows (a peeled-ear interleave,
heads turned to the sun). Writes out/species_<scene>_<shot>.png.
    bash run_blender.sh blender/tests/flora/t_species.py [--scenes desert,crops]
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402

import bpy  # noqa: E402
from eidoblend.flora import create_flora, reset_flora_occupancy  # noqa: E402


def sand_ground():
    g = S.ground()
    m = g.data.materials[0]
    pr = m.node_tree.nodes.get('Principled BSDF')
    for l in list(pr.inputs['Base Color'].links):
        m.node_tree.links.remove(l)
    pr.inputs['Base Color'].default_value = (0.42, 0.33, 0.24, 1)
    return g


for scene in S.arg('--scenes', 'desert,crops').split(','):
    S.new_scene()
    reset_flora_occupancy()
    if scene == 'desert':
        sun, to_sun = S.lights(sun_elev_deg=28, sun_az_deg=-30, strength=5.0, sky_strength=0.7, gradient=True)
        sand_ground()
        create_flora('galleta_dry', size=26, seed=3, density=1.3)
        create_flora('blackbrush', size=24, seed=5, density=0.85, center=(3, 2), footprint='organic')
        create_flora('creosote', size=24, seed=8, density=0.9, center=(-3, 4), footprint='organic')
        create_flora('sagebrush', size=20, seed=12, center=(1, -2), footprint='organic')
        create_flora('yucca', placements=[(1.6, 2.6, 1.7), (-2.2, 1.0, 2.1)], seed=21)
        shots = {'wide': ((9.0, -8.0, 2.2), (0.0, 1.5, 0.4), 32), 'close': ((3.6, -1.8, 1.1), (0.6, 1.8, 0.6), 30)}
    else:
        sun, to_sun = S.lights(sun_elev_deg=32, sun_az_deg=60, strength=5.0, sky_strength=0.7, gradient=True)
        S.ground()
        create_flora('corn', width=9, depth=6, center=(-2.5, 3.5), seed=4, rows={'spacing': 0.9, 'stride': 4})
        create_flora('corn', width=9, depth=6, center=(-2.5, 3.5), seed=9, rows={'spacing': 0.9, 'stride': 4, 'phase': 2},
                     corn={'peel': True})
        create_flora('corn', width=9, depth=6, center=(-2.5, 3.5), seed=13, rows={'spacing': 0.9, 'stride': 4, 'phase': 1})
        create_flora('corn', width=9, depth=6, center=(-2.5, 3.5), seed=17, rows={'spacing': 0.9, 'stride': 4, 'phase': 3})
        az = math.atan2(to_sun.y, to_sun.x)
        create_flora('sunflower', width=7, depth=5, center=(4.0, 2.5), seed=3, rows={'spacing': 0.85, 'plant': 0.5},
                     heading=az)
        create_flora('grass', size=30, seed=7, height=0.3, density=0.5, clip_fn=lambda x, y: -7.5 < x < 7.5 and -0.5 < y < 6.5)
        shots = {'wide': ((9.5, -7.5, 2.4), (0.0, 3.0, 1.0), 30), 'close': ((5.5, -1.6, 1.45), (4.0, 2.5, 1.5), 30)}
        # API check (no render): webgpu_heading=True reaches the plan and keeps the WebGPU facing, i.e. every yaw is
        # the default's plus the stroke's head yaw (two identical off-stage strokes, out of the occupancy registry)
        pl = [(30.0 + i, 30.0, 1.0) for i in range(4)]
        a = create_flora('sunflower', placements=pl, seed=3, heading=az, avoid=False, name='chk_heading')
        b = create_flora('sunflower', placements=pl, seed=3, heading=az, avoid=False, webgpu_heading=True,
                         name='chk_webgpu_heading')
        d = b.plan['posRot'][:, 3] - a.plan['posRot'][:, 3]
        assert abs(d - a.plan['stats']['headYaw']).max() < 1e-12, d
        print(f'[species] webgpu_heading=True: yaws = default + head yaw {a.plan["stats"]["headYaw"]:.4f} rad (ok)')
        a.remove()
        b.remove()
    for name, (loc, tgt, lens) in shots.items():
        S.camera(loc, tgt, lens, name='cam_' + name)
        S.render(os.path.join(S.OUT, f'species_{scene}_{name}.png'), 1)
print('[species] done')
