"""Does the far billboard answer the sun like the tree it stands in for?

    bash run_blender.sh blender/tests/trees2/billboard_light_match.py [oak] [joshua] [glow] [--out <dir>]
    (glow: grow with the opt-in 'glow' backlight route instead of the default 'translucent')

Grows the plant with every level and its billboard, then renders LOD0 and the
billboard alone from the same far camera under three suns: behind the camera
(front-lit), from the right (side-lit) and behind the plant (back-lit). The ground
still casts and catches light but is hidden from the camera, and the film is
transparent, so the alpha is the plant's coverage. For each render it measures the
plant's mean luminance and its right-minus-left balance: the app's billboard is
lighter (it never shadows itself, impostor.js), but it must darken and turn with
the sun the way the tree does. Last, the forest ring with every slot a billboard,
side-lit and back-lit, rendered with the ground for looking (each instance lights
from its own dome origin).
LOD2 (the card level) is measured beside them. Writes <out>/bbl_<species>_<light>_<level>.png
(RGBA) and bbl_<species>_forest_*.png.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.trees import raw  # noqa: E402

CASES = {
    'oak': ('whiteOak', 1737, 'grass'),
    'joshua': ('joshuaTree', 7, 'desert'),
}
LIGHTS = (('front', 180.0), ('side', 90.0), ('back', 0.0))    # where the sun comes from, see below


def out_dir():
    a = sys.argv
    if '--out' in a:
        return a[a.index('--out') + 1]
    return os.path.join(S.OUT, 'verify')


def read_rgba(path):
    img = bpy.data.images.load(path)
    px = np.array(img.pixels[:], np.float32).reshape(img.size[1], img.size[0], 4)[::-1]
    bpy.data.images.remove(img)
    return px


def measure(path):
    px = read_rgba(path)
    a = px[..., 3]
    m = a > 0.5
    lum = (px[..., :3] @ np.array([0.2126, 0.7152, 0.0722], np.float32)) / np.maximum(a, 1e-6)
    xs = np.nonzero(m)[1]
    cx = np.median(xs) if len(xs) else px.shape[1] / 2
    col = np.arange(px.shape[1])[None, :]
    left, right = lum[m & (col < cx)], lum[m & (col >= cx)]
    return {'mean': float(lum[m].mean()) if m.any() else 0.0, 'cover': float(m.mean()),
            'rl': float(right.mean() - left.mean()) if len(left) and len(right) else 0.0}


def main():
    which = [w for w in S.args() if w in CASES] or list(CASES)
    route = 'glow' if 'glow' in S.args() else 'translucent'   # the plant's backlight route (set_backlight)
    od = out_dir()
    os.makedirs(od, exist_ok=True)
    api = raw()
    for case in which:
        species, seed, ground_kind = CASES[case]
        key = case if route == 'translucent' else '%s_glow' % case
        scene = S.reset()
        S.render_settings(scene, 640, 640, 16)
        api.set_wind(strength=0.0)
        api.set_backlight(route)
        tree = api.create_tree(species=species, seed=seed, level='ALL', billboard=True)
        gr = S.ground(scene, api.ASSETS_DIR, ground_kind, tile=3.0)
        h = tree['stats']['summary']['heightMeters']
        w = tree['stats']['summary'].get('widthMeters', h)
        dist = 75.0
        target = Vector((0.0, 0.0, h * 0.5))
        cam_loc = Vector((0.0, -dist, 1.7))
        fov = 2 * math.atan(max(h, w) * 0.62 / dist)
        lens = 18.0 / math.tan(fov / 2)                     # 36 mm sensor: the plant fills the frame
        rows = []
        for light, az in LIGHTS:
            S.clear_lights_cameras(scene)
            # S.sky_and_sun: az in degrees from +Y toward +X, where the light comes FROM. The
            # camera stands at -Y looking +Y (its right is +X): 180 = behind the camera,
            # 90 = from the right, 0 = behind the plant
            sun, _ = S.sky_and_sun(scene, sun_elev_deg=25.0, sun_az_deg=az, strength=0.12, sun_strength=4.0)
            api.set_sun(sun)
            S.camera(scene, cam_loc, target, lens=lens)
            scene.render.film_transparent = True
            gr.visible_camera = False
            stats = {}
            for level in ('LOD0', 'LOD2', 'BB'):
                for n, objs in tree['objects'].items():
                    for o in objs:
                        o.hide_render = n != level
                api.light_probe(tree)
                p = os.path.join(od, 'bbl_%s_%s_%s.png' % (key, light, level))
                scene.render.image_settings.color_mode = 'RGBA'
                S.render(scene, p)
                stats[level] = measure(p)
            rows.append((light, stats))
            print('[bbl] %s %-5s LOD0 mean %.3f cover %.3f r-l %+.3f | LOD2 mean %.3f r-l %+.3f | BB mean %.3f cover %.3f '
                  'r-l %+.3f | LOD2/LOD0 %.2f BB/LOD0 %.2f' % (
                      key, light, stats['LOD0']['mean'], stats['LOD0']['cover'], stats['LOD0']['rl'], stats['LOD2']['mean'],
                      stats['LOD2']['rl'], stats['BB']['mean'], stats['BB']['cover'], stats['BB']['rl'],
                      stats['LOD2']['mean'] / max(1e-6, stats['LOD0']['mean']),
                      stats['BB']['mean'] / max(1e-6, stats['LOD0']['mean'])))
        scene.render.film_transparent = False
        gr.visible_camera = True
        ratio = {light: st['BB']['mean'] / max(1e-6, st['LOD0']['mean']) for light, st in rows}
        bbm = [st['BB']['mean'] for _, st in rows]
        l0m = [st['LOD0']['mean'] for _, st in rows]
        # the billboard is lighter by design (it never shadows itself, so back-lit it keeps a
        # little more light than the self-shadowed tree), but a sun behind the plant must not
        # light it up (the whole-card glint and the backward-leaning detail did: back / front
        # 1.74 on the oak, 2.0 on the Joshua tree)
        S.check('%s: back-lit, the billboard does not light up (BB/LOD0 back <= 1.35 x front)' % key,
                ratio['back'] <= 1.35 * ratio['front'],
                'BB front / side / back %s, LOD0 %s' % (['%.3f' % v for v in bbm], ['%.3f' % v for v in l0m]))
        S.check('%s: the billboard stays within x0.6..x2 of LOD0\'s luminance under every sun' % key,
                all(0.6 <= v <= 2.0 for v in ratio.values()), str({k: round(v, 2) for k, v in ratio.items()}))
        side = dict(rows)['side']
        S.check('%s: side-lit, the billboard is brighter on the sun side, like LOD0' % key,
                side['BB']['rl'] > 0 and side['LOD0']['rl'] > 0,
                'right - left: LOD0 %+.3f, BB %+.3f (sun from the right)' % (side['LOD0']['rl'], side['BB']['rl']))
        cov = {light: st['BB']['cover'] / max(1e-6, st['LOD0']['cover']) for light, st in rows}
        S.check('%s: the billboard covers the plant\'s silhouette (coverage within 15 %%)' % key,
                all(0.85 < c < 1.15 for c in cov.values()), str({k: round(v, 2) for k, v in cov.items()}))
        # the grove: every slot a billboard, lit from the right and from behind (the hero at LOD0)
        for n, objs in tree['objects'].items():
            for o in objs:
                o.hide_render = n != 'LOD0'
        forest = None
        for light, az in (('side', 90.0), ('back', 0.0)):
            S.clear_lights_cameras(scene)
            sun, _ = S.sky_and_sun(scene, sun_elev_deg=25.0, sun_az_deg=az, strength=0.12, sun_strength=4.0)
            api.set_sun(sun)
            if forest is None:
                forest = api.make_forest_ring(tree, count=64, seed=seed, billboard_dist=0.0)
            S.camera(scene, (0.0, -150.0, 25.0), (0.0, 0.0, h * 0.5), lens=35.0)
            api.light_probe(tree)
            S.render(scene, os.path.join(od, 'bbl_%s_forest_%s.png' % (key, light)))
        if case == 'oak' and route == 'translucent':
            # the two framings: the bake worker's trunk axis (default) and the main thread's
            # bounding-box centre (impostor.js bakeImpostor)
            t2 = api.create_tree(species=species, seed=seed, level='LOD0', location=(40.0, 0.0, 0.0))
            api.bake_impostor(t2, size=512, centered='box')
            lv = next(l for l in t2['tree']['levels'] if l['name'] == 'LOD0')
            box = api.stats_of({'levels': [lv]}, t2['tree'].get('assets'))['boundingBox']
            cx, cz = [(a + b) / 2 for a, b in zip(box['min'], box['max'])][0::2]
            card = t2['billboard']['cards'][0]
            axis_card = tree['billboard']['cards'][0]
            S.check('%s: centered=\'box\' frames the bounding box, \'axis\' the trunk' % key,
                    abs(card.location.x - cx) < 1e-4 and abs(card.location.y + cz) < 1e-4
                    and abs(axis_card.location.x) < 1e-6 and abs(axis_card.location.y) < 1e-6 and abs(cx) + abs(cz) > 0.01,
                    'box card at (%.3f, %.3f) = box centre (%.3f, %.3f); axis card at (%.3f, %.3f)' % (
                        card.location.x, card.location.y, cx, -cz, axis_card.location.x, axis_card.location.y))
    api.set_backlight('translucent')     # the library default again for later scripts in a batch
    S.summary('billboard_light_match')


main()
