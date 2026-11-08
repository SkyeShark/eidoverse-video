"""Probe stills of the other SeedThree generators, each in light that tests it.

    bash run_blender.sh blender/tests/trees/species_probes.py [names...]

names: joshua (backlit rosettes and dead-leaf skirt), saguaro (backlit: spine
halo, ribs against the skin texture), saguaro_front (front-lit: the damage
scars at the default Bark damage), creosote (spray shrub on desert ground),
willow (curtains in a meadow), apple (orchard tree with its fruit), apple_fruit
(a fruit close-up, grown in a fresh file after 'apple': the fruit cache across
files), birch, oak_autumn / joshua_dry (material dials).
Writes blender/tests/trees/out/probe_<name>.png.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from eidoblend.trees import make_seed_tree  # noqa: E402

# name: species, seed, dials, ground, sun (elev, az), camera (loc, target, lens)
PROBES = {
    'joshua': ('joshuaTree', 7, {}, 'desert_ground', (18, 20), ((4.5, -8.5, 1.6), (0, 0, 2.8), 35)),
    'saguaro': ('saguaro', 3, {}, 'desert_ground', (14, 25), ((4.0, -12.5, 1.7), (0, 0, 3.6), 30)),
    'saguaro_ribs': ('saguaro', 3, {}, 'desert_ground', (30, 120), ((1.6, -2.4, 2.2), (0, 0, 2.6), 35)),
    'saguaro_front': ('saguaro', 3, {}, 'desert_ground', (35, 200), ((2.5, -10.5, 1.7), (0, 0, 3.4), 35)),
    'apple_fruit': ('apple', 5, {}, 'grass', (42, 200), 'fruit'),
    'creosote': ('creosote', 5, {}, 'desert_ground', (35, 210), ((3.2, -4.2, 1.4), (0, 0, 0.9), 35)),
    'willow': ('weepingWillow', 2, {}, 'grass', (38, 215), ((19, -25, 1.6), (0, 0, 6.0), 30)),
    'apple': ('apple', 5, {}, 'grass', (42, 200), ((3.8, -5.2, 1.6), (0, 0, 2.6), 30)),
    'birch': ('paperBirch', 9, {}, 'grass', (40, 215), ((14, -20, 1.6), (0, 0, 7.5), 32)),
    # the material folder (applied by the EEVEE materials; the JS API ignores it)
    'oak_autumn': ('whiteOak', 1737, {'leafColorize': 0xc8642a, 'leafTintAmount': 0.75, 'barkTint': 0xd8d0c8},
                   'grass', (40, 215), ((19, -22, 1.6), (0, 0, 6.0), 32)),
    'joshua_dry': ('joshuaTree', 7, {'frondDryness': 0.55}, 'desert_ground', (35, 210),
                   ((4.5, -8.5, 1.6), (0, 0, 2.8), 35)),
}


def fruit_camera(t):
    """A camera 0.9 m from the outermost fruit at 1.5-3.5 m on the -Y (camera) side, looking at it."""
    fr = next(o for o in t['objects']['LOD0'] if o.name.endswith('fruit'))
    bpy.context.view_layer.update()
    me = fr.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    M = np.array(fr.matrix_world)
    w = co.reshape(-1, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3]
    band = w[(w[:, 2] > 1.5) & (w[:, 2] < 3.5)]
    p = Vector(band[np.argmin(band[:, 1] - 0.3 * band[:, 0])])
    out = Vector((p.x, p.y, 0)).normalized() if (p.x or p.y) else Vector((0, -1, 0))
    return tuple(p + out * 0.9 + Vector((0, 0, 0.15))), tuple(p), 50


def main():
    names = S.args() or list(PROBES)
    for name in names:
        sp, seed, dials, ground, (el, az), camspec = PROBES[name]
        scene = S.reset()
        S.render_settings(scene)
        t0 = time.perf_counter()
        t = make_seed_tree(species=sp, seed=seed, dials=dials, location=(0, 0, 0))
        make_seed_tree.set_wind(strength=0.0)
        print('[trees] %s seed %d built in %.2f s:' % (sp, seed, time.perf_counter() - t0), t['stats']['summary'])
        S.ground(scene, t['api'].ASSETS_DIR, ground, tile=3.0)
        sun, _ = S.sky_and_sun(scene, el, az, strength=0.10, sun_strength=4.0)
        make_seed_tree.set_sun(sun)            # the backlight follows this lamp
        make_seed_tree.light_probe(t)          # occluded sky inside the plant (bake after lighting)
        cam, tgt, lens = fruit_camera(t) if camspec == 'fruit' else camspec
        S.camera(scene, cam, tgt, lens=lens)
        S.render(scene, os.path.join(S.OUT, 'probe_%s.png' % name))


main()
