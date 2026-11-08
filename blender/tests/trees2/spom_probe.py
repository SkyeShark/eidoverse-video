"""The app's Parallax terrain (SPOM) toggle: the demo terrain with and without the
parallax-occlusion march, temperate and desert, from the same low camera over rock.

    bash run_blender.sh blender/tests/trees2/spom_probe.py [temperate] [desert]

Renders spom_<biome>_off.png / spom_<biome>_on.png (and a difference strip) and checks
that the march moves the rock texture (parallax), that the relief self-shadow darkens it,
and that the material compiles and renders in reasonable time.
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


def lum(path):
    img = bpy.data.images.load(path)
    px = np.array(img.pixels[:], np.float32).reshape(img.size[1], img.size[0], 4)[::-1]
    bpy.data.images.remove(img)
    return px[..., :3]


def main():
    a = S.args()
    biomes = [b for b in a if b in ('temperate', 'desert')] or ['temperate', 'desert']
    raw()
    from seedthree.scene import terrain as T
    from seedthree.bl.sun import set_sun
    for biome in biomes:
        shots = {}
        for spom in (False, True):
            scene = S.reset()
            S.render_settings(scene, 960, 540, 16)
            scene.view_settings.view_transform = 'AgX'
            env = T.build_environment(scene, biome, seed=7 if biome == 'desert' else 1, radius=280, segs=320,
                                      sun_az=40, sun_el=24, spom=spom)
            set_sun(env['sun'])
            smp = env['sampler']
            # the rockiest spot 25-60 m out, and a low camera 5 m from it facing the sun side
            best = None
            for r in np.linspace(25, 60, 15):
                for ang in np.linspace(0, 2 * math.pi, 48, endpoint=False):
                    x, z = r * math.cos(ang), r * math.sin(ang)
                    k = float(smp.rockness_at(np.array([x]), np.array([z]))[0])
                    if best is None or k > best[0]:
                        best = (k, x, z)
            k, x, z = best
            tgt = Vector((x, -z, float(smp.height_at(np.array([x]), np.array([z]))[0])))
            sd = (env['sun'].rotation_euler.to_quaternion() @ Vector((0, 0, 1)))   # matrix_world is stale here
            off = Vector((-sd.x, -sd.y, 0)).normalized() * 4.5
            camp = tgt + off
            camp.z = float(smp.height_at(np.array([camp.x]), np.array([-camp.y]))[0]) + 1.6
            S.camera(scene, tuple(camp), tuple(tgt), lens=35)
            t0 = time.perf_counter()
            path = os.path.join(S.OUT, 'spom_%s_%s.png' % (biome, 'on' if spom else 'off'))
            S.render(scene, path)
            dt = time.perf_counter() - t0
            print('[spom] %s %s: rockness %.2f at (%.1f, %.1f), render %.1f s' % (biome, 'on' if spom else 'off', k, x, z, dt))
            shots[spom] = (lum(path), dt)
        off, on = shots[False][0], shots[True][0]
        lower = slice(int(off.shape[0] * 0.45), off.shape[0])      # the ground half of the frame
        diff = np.abs(on[lower] - off[lower]).mean()
        dark = float(on[lower].mean() / max(1e-6, off[lower].mean()))
        S.check('%s SPOM moves the relief' % biome, diff > 0.01, 'mean |on - off| %.3f' % diff)
        S.check('%s SPOM self-shadow darkens, not blackens' % biome, 0.5 < dark < 1.0, 'mean on / off %.3f' % dark)
        S.check('%s SPOM renders in reasonable time' % biome, shots[True][1] < 120, '%.1f s' % shots[True][1])
        strip = np.concatenate([off, on, np.clip(np.abs(on - off) * 4, 0, 1)], axis=1)
        img = bpy.data.images.new('strip', strip.shape[1], strip.shape[0])
        img.pixels.foreach_set(np.concatenate([strip[::-1], np.ones(strip.shape[:2] + (1,), np.float32)], axis=2).ravel())
        img.filepath_raw = os.path.join(S.OUT, 'spom_%s_strip.png' % biome)
        img.file_format = 'PNG'
        img.save()
    S.summary('spom_probe')


main()
