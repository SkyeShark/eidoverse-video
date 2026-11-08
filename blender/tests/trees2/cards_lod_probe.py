"""Baked branch cards and the billboard impostor on a white oak, every level from
the same cameras.

    bash run_blender.sh blender/tests/trees2/cards_lod_probe.py [species] [seed]

Grows the plant with level='ALL', the desktop card LOD2 (bake: 3 variants x 512)
and the billboard (1024), then renders LOD0 / LOD1 / LOD2 / BB from 70 m (the JS
LOD2 switch distance) and LOD0 / LOD2 from 24 m, plus the baked card and billboard
textures. Checks the card set, the billboard group and the triangle budget.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
import bpy  # noqa: E402

from eidoblend.trees import raw  # noqa: E402


def main():
    a = S.args()
    species = a[0] if a else 'whiteOak'
    seed = int(a[1]) if len(a) > 1 else 1737
    api = raw()
    scene = S.reset()
    S.render_settings(scene, 960, 540, 16)
    t0 = time.perf_counter()
    tree = api.create_tree(species=species, seed=seed, level='ALL', billboard=True)
    print('[trees2] %s grown with cards + billboard in %.1f s' % (species, time.perf_counter() - t0))
    per = {l['name']: l['triangles'] for l in tree['stats']['perLod']}
    print('[trees2] per-LOD triangles', json.dumps(per))
    S.check('card LOD2 built', any('cards' in o.name for o in tree['objects'].get('LOD2', [])))
    cards_ob = next((o for o in tree['objects'].get('LOD2', []) if 'cards' in o.name), None)
    if cards_ob:
        S.check('card materials are baked card materials', all(m.get('st_card') for m in cards_ob.data.materials),
                '%d slots' % len(cards_ob.data.materials))
        S.check('card triangles = stats', len(cards_ob.data.polygons) > 0)
    S.check('LOD2 under 20% of LOD0', per['LOD2'] < 0.2 * per['LOD0'], '%d vs %d' % (per['LOD2'], per['LOD0']))
    bb = tree.get('billboard')
    S.check('billboard level', bb is not None and len(bb['cards']) == 2)
    lod_names = tree['object'].children
    api.set_wind(strength=0.0)
    S.ground(scene, api.ASSETS_DIR, 'grass', tile=3.0)
    h = tree['stats']['summary']['heightMeters']
    for shot, cam, levels in (('far70', ((0.0, -70.0, 1.7), (0.0, 0.0, h * 0.45), 50), ('LOD0', 'LOD1', 'LOD2', 'BB')),
                              ('near24', ((14.0, -19.0, 1.6), (0.0, 0.0, h * 0.5), 35), ('LOD0', 'LOD2', 'BB'))):
        S.clear_lights_cameras(scene)
        sun, _ = S.sky_and_sun(scene, sun_elev_deg=40, sun_az_deg=215, strength=0.10, sun_strength=4.0)
        api.set_sun(sun)
        S.camera(scene, cam[0], cam[1], lens=cam[2])
        for level in levels:
            S.show_only(tree, level)
            api.light_probe(tree)
            S.render(scene, os.path.join(S.OUT, 'cards_%s_%s_%s.png' % (species, shot, level)))
        if shot == 'far70':
            # the billboard casts the canopy's shadow on the ground (and receives none), like LOD0
            import numpy as np

            def lum(level):
                img = bpy.data.images.load(os.path.join(S.OUT, 'cards_%s_%s_%s.png' % (species, shot, level)))
                px = np.array(img.pixels[:], np.float32).reshape(img.size[1], img.size[0], 4)[::-1]
                bpy.data.images.remove(img)
                return px[..., :3] @ np.array([0.2126, 0.7152, 0.0722])
            l0, lb = lum('LOD0'), lum('BB')
            rows = slice(int(l0.shape[0] * 0.70), int(l0.shape[0] * 0.78))
            band0, bandb = l0[rows], lb[rows]
            shade = band0 < 0.8 * np.median(band0)
            if shade.any():
                r0 = float(band0[shade].mean() / band0[~shade].mean())
                rb = float(bandb[shade].mean() / bandb[~shade].mean())
                S.check('the billboard casts the canopy shadow (ground darkening vs LOD0)', rb < 0.9,
                        'shadowed / lit ground: LOD0 %.2f, BB %.2f' % (r0, rb))
            bb_cards = tree['objects']['BB']
            S.check('billboard cards cast only', all(c.visible_shadow and c.get('seedthree_cast_only') == sun.name
                                                       for c in bb_cards), str([c.get('seedthree_cast_only') for c in bb_cards]))
    # the baked textures, for looking at
    seen = set()
    for m in bpy.data.materials:
        if not (m.get('st_card') or m.get('st_billboard')):
            continue
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image and n.image.name not in seen:
                seen.add(n.image.name)
                S.save_image(n.image, os.path.join(S.OUT, 'bakes', n.image.name.replace(' ', '_') + '.png'))
    print('[trees2] wrote %d baked textures' % len(seen))
    S.summary('cards_lod_probe')


main()
