"""A far tree line the way films should build one: LOD0 everywhere, a few grown
individuals placed many times as linked duplicates, one light probe over the grove.

    bash run_blender.sh blender/tests/trees/treeline.py

Grows three white-oak individuals (meadow dials, seeds 1737 / 42 / 7), places
twelve trees 55-130 m from an eye-height camera (rotations and spacing varied),
bakes one Light Probe Volume over them, and renders
blender/tests/trees/out/treeline.png. Prints build, duplicate, bake and render times.
"""

import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402

import bpy  # noqa: E402
from eidoblend.trees import make_seed_tree  # noqa: E402
from meadow_oak_design import MEADOW_OAK  # noqa: E402


def main():
    scene = S.reset()
    S.render_settings(scene)
    rnd = random.Random(5)
    t0 = time.perf_counter()
    grown = [make_seed_tree(species='whiteOak', seed=s, dials=MEADOW_OAK, location=(0, 0, -500)) for s in (1737, 42, 7)]
    t_build = time.perf_counter() - t0
    t0 = time.perf_counter()
    trees = []
    x = -95.0
    for i in range(12):
        src = grown[i % 3]
        y = 55.0 + rnd.uniform(0, 75)
        loc = (x, y, 0.0)
        trees.append(make_seed_tree.duplicate(src, location=loc, rotation=rnd.uniform(0, 2 * math.pi)))
        x += rnd.uniform(13, 22)
    for g in grown:   # the grown originals stay as the shared mesh data, out of the render
        g['object'].hide_render = True
        for objs in g['objects'].values():
            for o in objs:
                o.hide_render = True
    t_dup = time.perf_counter() - t0
    make_seed_tree.set_wind(strength=0.0)
    S.ground(scene, grown[0]['api'].ASSETS_DIR, 'grass', size=600.0, tile=3.0)
    sun, _ = S.sky_and_sun(scene, sun_elev_deg=30, sun_az_deg=230, strength=0.10, sun_strength=4.0)
    make_seed_tree.set_sun(sun)
    t0 = time.perf_counter()
    make_seed_tree.light_probe(trees, spacing=3.0)
    t_bake = time.perf_counter() - t0
    S.camera(scene, (0.0, -10.0, 1.7), (0.0, 80.0, 7.0), lens=35)
    t0 = time.perf_counter()
    S.render(scene, os.path.join(S.OUT, 'treeline.png'))
    t_render = time.perf_counter() - t0
    tris = sum(len(o.data.polygons) for t in trees for objs in t['objects'].values() for o in objs if not o.hide_render)
    print('[trees] tree line: %d trees, %.1f M triangles drawn; grow 3 individuals %.1f s, duplicate %.2f s, '
          'probe bake %.1f s, render %.1f s' % (len(trees), tris / 1e6, t_build, t_dup, t_bake, t_render))


main()
