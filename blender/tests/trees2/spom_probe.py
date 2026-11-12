"""The app's Parallax terrain (SPOM) toggle at eye height: the demo terrain with SPOM off, with the
app's own height maps (heights='app') and with the default relief integrated from the layers'
normal maps (heights='normals'), temperate and desert.

    bash run_blender.sh blender/tests/trees2/spom_probe.py [temperate] [desert]

Views: 'rock', the rockiest spot 25-60 m out seen from 4.5 m away and 1.6 m up, toward the sun;
and for the desert 'floor', the flat gravel floor by the plant, eye height (1.7 m), 6 m ahead,
the sun from the side. Renders spom_<biome>_<view>_{off,app_heights,relief}.png and a strip
(off | app heights | relief), and checks that the relief moves the texture (parallax), that
its self-shadow darkens without blackening, that it draws no needles (a needle field turns
the ground's edges vertical: the share of horizontal gradients rises; the app's heights
still do, by design of heights='app'), that its depths are centimetres, and the render time.
"""

import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.trees import raw  # noqa: E402

VARIANTS = (('off', None), ('app_heights', 'app'), ('relief', 'normals'))


def lum(path):
    img = bpy.data.images.load(path)
    px = np.array(img.pixels[:], np.float32).reshape(img.size[1], img.size[0], 4)[::-1]
    bpy.data.images.remove(img)
    return px[..., :3]


def shot(biome, view, heights):
    from seedthree import api as STA
    from seedthree.scene import terrain as T, spom as SP
    from seedthree.bl.sun import set_sun
    scene = S.reset()
    S.render_settings(scene, 960, 540, 16)
    scene.view_settings.view_transform = 'AgX'
    desert = biome == 'desert'
    shaped, _ = STA.shaped_species('joshuaTree' if desert else 'whiteOak', None, 7 if desert else 1)
    env = T.build_environment(scene, biome, seed=7 if desert else 1, radius=280, segs=320, sun_az=40, sun_el=24,
                              spom=False, species=shaped)
    mat = None
    if heights:
        mat = SP.spom_terrain_material(biome, shaped, heights=heights)
        env['terrain'].data.materials.clear()
        env['terrain'].data.materials.append(mat)
    set_sun(env['sun'])
    smp = env['sampler']
    sd = env['sun'].rotation_euler.to_quaternion() @ Vector((0, 0, 1))      # matrix_world is stale here

    def hz(x, y):
        return float(smp.height_at(np.array([x]), np.array([-y]))[0])
    if view == 'rock':
        best = None
        for r in np.linspace(25, 60, 15):
            for ang in np.linspace(0, 2 * math.pi, 48, endpoint=False):
                x, z = r * math.cos(ang), r * math.sin(ang)
                k = float(smp.rockness_at(np.array([x]), np.array([z]))[0])
                if best is None or k > best[0]:
                    best = (k, x, z)
        k, x, z = best
        tgt = Vector((x, -z, hz(x, -z)))
        camp = tgt + Vector((-sd.x, -sd.y, 0)).normalized() * 4.5
        camp.z = hz(camp.x, camp.y) + 1.6
    else:
        side = Vector((-sd.y, sd.x, 0)).normalized()
        camp = -side * 3.0
        tgt = camp + side * 6.0
        tgt.z = hz(tgt.x, tgt.y)
        camp.z = hz(camp.x, camp.y) + 1.7
    S.camera(scene, tuple(camp), tuple(tgt), lens=35)
    path = os.path.join(S.OUT, 'spom_%s_%s_%s.png' % (biome, view, dict((h, n) for n, h in VARIANTS)[heights]))
    t0 = time.perf_counter()
    S.render(scene, path)
    return lum(path), time.perf_counter() - t0, mat


def edge_ratio(img, lower):
    g = img[lower].mean(2)
    return float(np.abs(np.diff(g, axis=1)).mean() / max(1e-6, np.abs(np.diff(g, axis=0)).mean()))


def main():
    a = S.args()
    biomes = [b for b in a if b in ('temperate', 'desert')] or ['temperate', 'desert']
    raw()
    for biome in biomes:
        for view in (('rock', 'floor') if biome == 'desert' else ('rock',)):
            res = {}
            for name, heights in VARIANTS:
                res[name] = shot(biome, view, heights)
                print('[spom] %s %s %s: render %.1f s%s' % (biome, view, name, res[name][1], (
                    '; depths (m) %s' % [round(d, 3) for d in res[name][2]['seedthree_spom_depths_m']]) if res[name][2] else ''))
            off, app, rel = res['off'][0], res['app_heights'][0], res['relief'][0]
            lower = slice(int(off.shape[0] * 0.45), off.shape[0])      # the ground half of the frame
            tag = '%s %s' % (biome, view)
            diff = float(np.abs(rel[lower] - off[lower]).mean())
            dark = float(rel[lower].mean() / max(1e-6, off[lower].mean()))
            e_off, e_app, e_rel = edge_ratio(off, lower), edge_ratio(app, lower), edge_ratio(rel, lower)
            S.check('%s: the relief moves the texture' % tag, diff > 0.01, 'mean |relief - off| %.3f' % diff)
            S.check('%s: its self-shadow darkens, not blackens' % tag, 0.6 < dark < 1.05, 'mean relief / off %.3f' % dark)
            if view == 'rock':
                S.check('%s: no needles (horizontal-gradient share within 10 %% of SPOM off)' % tag, e_rel < 1.1 * e_off,
                        'gx / gy: off %.3f, relief %.3f, app heights %.3f' % (e_off, e_rel, e_app))
                S.check('%s: heights=\'app\' still draws the app\'s needles' % tag, e_app > 1.3 * e_off,
                        'app heights / off %.2f' % (e_app / e_off))
            depths = list(res['relief'][2]['seedthree_spom_depths_m'])
            S.check('%s: relief depths are centimetres (0.5-10 cm)' % tag, all(0.005 < d < 0.1 for d in depths),
                    str([round(d, 3) for d in depths]))
            S.check('%s: renders in reasonable time' % tag, res['relief'][1] < 120, '%.1f s' % res['relief'][1])
            strip = np.concatenate([off, app, rel], axis=1)
            img = bpy.data.images.new('strip', strip.shape[1], strip.shape[0])
            img.pixels.foreach_set(np.concatenate([strip[::-1], np.ones(strip.shape[:2] + (1,), np.float32)], axis=2).ravel())
            img.filepath_raw = os.path.join(S.OUT, 'spom_%s_%s_strip_off_app_relief.png' % (biome, view))
            img.file_format = 'PNG'
            img.save()
    S.summary('spom_probe')


main()
