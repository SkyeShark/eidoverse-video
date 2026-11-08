"""A white oak DESIGNED for a sunny meadow shot, through SeedThree's dials.

A lone open-grown white oak reads as a short massive bole that divides low into a
few heavy, near-horizontal, gnarled scaffold limbs under a broad dome wider than
it is tall; leaves fill the outer shell, light reaches the limbs inside.

    bash run_blender.sh blender/tests/trees/meadow_oak.py [shots...] [--default]

shots: wide (37 m, three-quarter sun), near (8 m, trunk base and limbs),
       back (backlit, sun behind the crown), under (under the crown looking
       toward the sun: leaf translucency), sunset (a 7 degree sun straight
       behind the crown), far (LOD0 / LOD1 / LOD2 from 70 m, same camera).
       --default renders the untouched species defaults with the same seed and
       cameras, for comparison.
Every shot binds the backlight to its sun and re-bakes the light probe.
Writes blender/tests/trees/out/meadow_oak_<shot>.png, the design as an app
preset (meadow_oak_preset.seedthree.json), and prints the stats.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402

from eidoblend.trees import make_seed_tree  # noqa: E402
from meadow_oak_design import MEADOW_OAK, SEED  # noqa: E402


def main():
    a = S.args()
    default = '--default' in a
    shots = [x for x in a if not x.startswith('--')] or ['wide', 'near', 'back', 'under', 'sunset', 'far']
    scene = S.reset()
    S.render_settings(scene)
    t0 = time.perf_counter()
    oak = make_seed_tree(species='whiteOak', seed=SEED, dials=None if default else MEADOW_OAK,
                         location=(0, 0, 0), level='ALL' if 'far' in shots else 'LOD0')
    build_s = time.perf_counter() - t0
    st = oak['stats']['summary']
    print('[trees] meadow oak built in %.2f s:' % build_s, json.dumps(st))
    make_seed_tree.set_wind(strength=0.0)
    api = oak['api']
    S.ground(scene, api.ASSETS_DIR, 'grass', tile=3.0)
    h, w = st['heightMeters'], st['widthMeters']
    tag = 'default_' if default else ''
    for shot in shots:
        for o in [o for o in scene.objects if o.type in ('LIGHT', 'CAMERA')]:
            bpy_remove(o)
        show_level(oak, 'LOD0')
        if shot == 'far':   # the three levels from 70 m (the JS's LOD2 distance), same camera
            sun, _ = S.sky_and_sun(scene, sun_elev_deg=40, sun_az_deg=215, strength=0.10, sun_strength=4.0)
            make_seed_tree.set_sun(sun)
            S.camera(scene, (0.0, -70.0, 1.7), (0.0, 0.0, 7.0), lens=50)
            for level in ('LOD0', 'LOD1', 'LOD2'):
                show_level(oak, level)
                make_seed_tree.light_probe(oak)
                S.render(scene, os.path.join(S.OUT, 'meadow_oak_%sfar70_%s.png' % (tag, level)))
            show_level(oak, 'LOD0')
            continue
        if shot == 'wide':
            S.sky_and_sun(scene, sun_elev_deg=40, sun_az_deg=215, strength=0.10, sun_strength=4.0)
            S.camera(scene, (24, -28, 1.6), (0, 0, h * 0.4), lens=32)
        elif shot == 'near':
            S.sky_and_sun(scene, sun_elev_deg=40, sun_az_deg=215, strength=0.10, sun_strength=4.0)
            S.camera(scene, (5.5, -6.0, 1.5), (0, 0, 2.4), lens=24)
        elif shot == 'back':
            S.sky_and_sun(scene, sun_elev_deg=22, sun_az_deg=330, strength=0.10, sun_strength=4.0)
            S.camera(scene, (-14, -30, 1.4), (0, 0, h * 0.45), lens=30)
        elif shot == 'under':
            S.sky_and_sun(scene, sun_elev_deg=36, sun_az_deg=315, strength=0.10, sun_strength=4.0)
            S.camera(scene, (6, -6, 1.5), (0, 0, 7), lens=24)
        elif shot == 'sunset':   # a 7 degree sun straight behind the crown: the classic backlit shot
            S.sky_and_sun(scene, sun_elev_deg=7, sun_az_deg=0, strength=0.10, sun_strength=4.0)
            S.camera(scene, (0.0, -34.0, 1.6), (0.0, 0.0, 7.5), lens=35)
        make_seed_tree.set_sun(next(o for o in scene.objects if o.type == 'LIGHT'))   # the backlight's lamp
        make_seed_tree.light_probe(oak)   # re-baked per shot: the sun moved
        S.render(scene, os.path.join(S.OUT, 'meadow_oak_%s%s.png' % (tag, shot)))
    with open(os.path.join(S.OUT, 'meadow_oak_%spreset.seedthree.json' % tag), 'w') as fh:
        fh.write(api.preset_json(oak['preset']))


def show_level(tree, level):
    for name, objs in tree['objects'].items():
        for o in objs:
            o.hide_render = name != level


def bpy_remove(o):
    import bpy
    data = o.data
    bpy.data.objects.remove(o, do_unlink=True)
    if data is not None and data.users == 0:
        if isinstance(data, bpy.types.Light):
            bpy.data.lights.remove(data)
        elif isinstance(data, bpy.types.Camera):
            bpy.data.cameras.remove(data)


main()
