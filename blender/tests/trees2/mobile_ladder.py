"""The mobile LOD ladders, the willow's gravity-aligned card sheets, Joshua rosette
cards with the thatch bark, and the hangingSprays foliage mode, every level rendered.

    bash run_blender.sh blender/tests/trees2/mobile_ladder.py [joshua oak willow saguaro hanging]

For each plant: level='ALL' with lod={'mobileTarget': True} (desktop for 'willow'
and 'hanging'), cards baked; one frame per level from a camera that frames the plant,
in a strip: out/mobile_<plant>_<level>.png and out/mobile_<plant>_strip.png. Checks
the levels and their flags (hiddenInApp / appOnly), the thatch material on the
reduced Joshua rungs, the rosette cards on LOD3 / LOD4, and that each rung costs less
than the one before.
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.trees import raw  # noqa: E402

PLANTS = {
    'joshua': dict(species='joshuaTree', seed=7, lod={'mobileTarget': True}),
    'oak': dict(species='whiteOak', seed=1737, lod={'mobileTarget': True}),
    'saguaro': dict(species='saguaro', seed=3, lod={'mobileTarget': True}),
    'willow': dict(species='weepingWillow', seed=2, lod={}),
    # no preset uses hangingSprays: a red maple with its foliage switched to it (the parity case),
    # and the willow hanging the app's own spray card (weeping_willow_spray) from its feeders
    'hanging': dict(species='redMaple', seed=3, lod={}, controls=None,
                    hanging={'foliage': {'mode': 'hangingSprays', 'leavesPerBranch': 3, 'size': 0.9}}),
    'hangspray': dict(species='weepingWillow', seed=2, lod={}, controls=None,
                      hanging={'foliage': {'mode': 'hangingSprays', 'leavesPerBranch': 2, 'size': 0.55, 'widthRatio': 0.5},
                               'leaf': 'weeping_willow_spray_albedo.png'}),
}


def strip(paths, out):
    import numpy as np
    imgs = []
    for p in paths:
        im = bpy.data.images.load(p)
        w, h = im.size
        a = np.empty(w * h * 4, np.float32)
        im.pixels.foreach_get(a)
        imgs.append(a.reshape(h, w, 4))
        bpy.data.images.remove(im)
    row = np.concatenate(imgs, axis=1)
    h, w = row.shape[:2]
    o = bpy.data.images.new('strip', w, h, alpha=True)
    o.pixels.foreach_set(row.ravel())
    o.filepath_raw = out
    o.file_format = 'PNG'
    o.save()
    bpy.data.images.remove(o)


def main():
    picks = [a for a in S.args() if a in PLANTS] or list(PLANTS)
    api = raw()
    scene = S.reset()
    S.render_settings(scene, 640, 640, 16)
    S.ground(scene, api.ASSETS_DIR, 'grass', tile=3.0)
    sun, _ = S.sky_and_sun(scene, sun_elev_deg=35, sun_az_deg=210, strength=0.10, sun_strength=4.0)
    api.set_wind(strength=0.0)
    for key in picks:
        cfg = PLANTS[key]
        if cfg.get('hanging'):
            from seedthree.species import SPECIES
            sp = SPECIES[cfg['species']]
            saved = (dict(sp['foliage']), sp.get('leaf'))
            sp['foliage'].update(cfg['hanging']['foliage'])
            if cfg['hanging'].get('leaf'):
                sp['leaf'] = cfg['hanging']['leaf']
        try:
            tree = api.create_tree(species=cfg['species'], seed=cfg['seed'], controls=cfg.get('controls'),
                                   lod=cfg['lod'], level='ALL', sun_light=sun)
        finally:
            if cfg.get('hanging'):
                sp['foliage'].clear()
                sp['foliage'].update(saved[0])
                sp['leaf'] = saved[1]
        levels = json.loads(tree['object']['seedthree_levels'])
        per = {l['name']: l['triangles'] for l in tree['stats']['perLod']}
        print('[trees2] %s levels %s' % (key, json.dumps(per)))
        mobile = bool(cfg['lod'].get('mobileTarget'))
        if mobile:
            flags = {l['name']: (bool(l.get('hiddenInApp')), bool(l.get('appOnly'))) for l in levels}
            S.check('%s mobile flags' % key, flags.get('LOD0') == (True, False) and flags.get('LOD1') == (True, False)
                    and flags.get('LOD2') == (False, False) and flags.get('LOD3') == (False, True)
                    and flags.get('LOD4') == (False, True), json.dumps(flags))
            S.check('%s rungs get cheaper (LOD2 > LOD3 > LOD4)' % key, per['LOD2'] > per['LOD3'] > per['LOD4'],
                    '%d > %d > %d' % (per['LOD2'], per['LOD3'], per['LOD4']))
        if key == 'joshua':
            bark = {n: next(o for o in objs if o.name.endswith(' bark')).data.materials[0].name
                    for n, objs in tree['objects'].items()}
            S.check('joshua thatch bark on LOD2-4 only', all('thatch' in bark[n] for n in ('LOD2', 'LOD3', 'LOD4'))
                    and 'thatch' not in bark['LOD0'], json.dumps(bark))
            S.check('joshua rosette cards on LOD3/LOD4', all(any(o.name.endswith(' cards') for o in tree['objects'][n])
                                                             for n in ('LOD3', 'LOD4')))
        if key == 'willow':
            cards = next((o for o in tree['objects']['LOD2'] if o.name.endswith(' cards')), None)
            S.check('willow LOD2 gravity sheets (front + side views)', cards is not None and len(cards.data.materials) >= 2,
                    '%d slots' % (len(cards.data.materials) if cards else 0))
        h = tree['stats']['summary']['heightMeters']
        w = tree['stats']['summary']['widthMeters']
        d = max(h, w) * 1.25 + 2
        cam = S.camera(scene, (d * 0.55, -d, h * 0.45), (0, 0, h * 0.45), lens=40, name='cam ' + key)
        paths = []
        for lv in [l['name'] for l in levels]:
            S.show_only(tree, lv)
            api.light_probe(tree)
            p = os.path.join(S.OUT, 'mobile_%s_%s.png' % (key, lv))
            S.render(scene, p)
            paths.append(p)
        strip(paths, os.path.join(S.OUT, 'mobile_%s_strip.png' % key))
        for objs in tree['objects'].values():
            for o in objs:
                o.hide_render = True
        bpy.data.objects.remove(cam, do_unlink=True)
    S.summary('mobile_ladder')


main()
