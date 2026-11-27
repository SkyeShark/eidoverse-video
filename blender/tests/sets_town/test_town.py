"""The town (eidoblend.sets.town): a small intact town built and checked, two stills under the sky family; a struck
house and a sign checked on their own. Blender (a GPU job: EEVEE, 960 x 540, 16 samples):

    bash run_blender.sh blender/tests/sets_town/test_town.py [--no-render] [--extent 260x160] [--trees built]

Its CC0 sets and models come from the shared library (EIDO_ASSET_CACHE, else this checkout's cache; fetched on first
use unless EIDO_NO_FETCH=1). Checks (PASS / FAIL):
  1. the build: buildings, streets, ground and air made; every face has an area and every point is finite; no struck
     house, no crater, no wreck and every tn_dust 0 (an intact town unless asked); the masks on the meshes
  2. the roads' sanded ends: where the asphalt ends (PAVED) and how far in the sand lies follow the extent
  3. a struck house (dmg 1, front blown off) has torn slab edges, hanging pieces, rubble; plan_strikes places strikes
  4. a sign of words is laid as letters on its board, in the board's ink
  5. the stills (out/town_*.png): written, neither black nor blown
A PASS is not a look: open the stills.
"""
import math
import os
import random
import sys
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend import common  # noqa: E402
from eidoblend.sets import town as TOWN  # noqa: E402
from eidoblend.sets.town import materials as MT, signs as SG, views as V  # noqa: E402
from eidoblend.sets.town.house import House  # noqa: E402

OUT = os.path.join(HERE, 'out')
FAILS = []


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg, flush=True)
    if not ok:
        FAILS.append(msg)


def faces_ok(meshes):
    """the town's own meshes (not the CC0 scans): every point finite, and at most one face in ten thousand without an
    area (a turned profile's point where two rings meet) -> {mesh: (faces without area, faces)} of those that fail"""
    bad, n0, nf = {}, 0, 0
    for me in meshes:
        if me.name.startswith('cc0_'):
            continue
        ar, co = np.zeros(len(me.polygons), np.float32), np.zeros(len(me.vertices) * 3, np.float32)
        me.polygons.foreach_get('area', ar)
        me.vertices.foreach_get('co', co)
        z = int((ar < 1e-7).sum())
        n0, nf = n0 + z, nf + len(ar)
        if z > max(1, len(ar) // 10000) or not np.isfinite(co).all():
            bad[me.name] = (z, len(ar))
    print(f'[test] faces without an area: {n0} of {nf}', flush=True)
    return bad


def main():
    a = common.script_args()
    ex, ey = (float(v) for v in (a[a.index('--extent') + 1] if '--extent' in a else '260x160').split('x'))
    trees = a[a.index('--trees') + 1] if '--trees' in a else 'built'
    print(f'[test] extent {ex:g} x {ey:g}, yard trees {trees!r}', flush=True)
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    t0 = time.time()
    T = TOWN.build(extent=(ex, ey), seed=7, edge=60.0, yard_trees=trees)
    st = T.stats
    print(f'[test] built in {time.time() - t0:.1f} s: {st}', flush=True)
    # 1. the build
    check(st['buildings'] >= 40, f"buildings placed: {st['buildings']}")
    check(T.parts['ground'] is not None and T.parts['streets'] is not None and T.parts['air'] is not None, 'ground, streets and air made')
    meshes = {o.data for o in T.collection.all_objects if o.type == 'MESH' and o.name != 'town_air'}
    bad = faces_ok(meshes)
    check(not bad, f'every face has an area and every point is finite in {len(meshes)} meshes' + (f': {bad}' if bad else ''))
    names = {m.name for m in meshes}
    struck = [n for n in names if n.startswith(('town_H', 'town_S', 't_wall')) or 'burnt' in n]
    dust = max(float(o.get('tn_dust', 0.0)) for o in T.collection.objects)
    check(not struck and not T.strikes and dust == 0.0, f'intact: no struck house, wreck or blast wall ({struck[:4]}), strikes {T.strikes}, tn_dust max {dust}')
    crater = [m for m in bpy.data.materials if m.name in ('town.crater', 'town.plaster_dmg', 'town.roof_dmg')]
    check(not crater, f'no crater or struck material made ({[m.name for m in crater]})')
    bld = next(o for o in T.parts['buildings'] if o.data.name.startswith('town_A_'))
    attrs = {at.name for at in bld.data.attributes}
    lanes = {at.name for at in T.parts['streets'].data.attributes} | {at.name for at in T.parts['ground'].data.attributes}
    check({'tl_edge', 'tl_box', 'tl_corner'} <= attrs and 'tl_lane' in lanes, f'the masks: {sorted(attrs & {"tl_edge", "tl_box", "tl_corner", "tl_soot"})}, streets {sorted(lanes)}')
    check(st['things'].get('chair', 0) > 0, f"CC0 things placed: {st['things']}")
    # 2. the sanded ends follow the extent
    check(abs(T.paved[0] - (ex / 2 + 30.0)) < 1e-6 and abs(T.paved[1] - (ey / 2 + 10.0)) < 1e-6 and MT.SAND_REACH == [34.0, 12.0],
          f'the asphalt ends at x +-{T.paved[0]:g}, y +-{T.paved[1]:g}; the sand reaches {MT.SAND_REACH} m in')
    road = bpy.data.materials.get('town.road')
    gr = [n for n in road.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image and 'rock_ground_02' in n.image.filepath] if road else []
    check(road is not None and len(gr) >= 1, f'the road reads the track\'s and the plain\'s own sets at its ends ({len(gr)} rock_ground_02 lookups)')
    # 3. damage, on its own
    h = House(random.Random(75), 15.0, 11.0, 4, True, 1)
    me = h.mesh('test_front_blown', MT.M)
    mats = {m.name for m in me.materials}
    check({'town.concrete_broken', 'town.rubble', 'town.rebar'} <= mats, f'a front blown off: torn edges, rubble, steel ({len(me.polygons)} faces)')
    ss = TOWN.plan_strikes(random.Random(3), 840.0, 300.0)
    check(len(ss) == 8 and all(28.0 <= s[2] <= 45.0 for s in ss), f'plan_strikes on 840 x 300: {len(ss)} strikes')
    # 4. a sign of words
    S = SG.prepare(['BAKERY'])
    House.signs = S                                                  # (the layout sets the town's signs on the class)
    hs = House(random.Random(71), 14.5, 10.5, 2, True, 0)
    me2 = hs.mesh('test_sign', MT.M)
    House.signs = []
    smats = {m.name for m in me2.materials}
    check(S and S[0]['polys'] and 'town.sign_text_0' in smats and 'town.sign_board_0' in smats,
          f"a sign of words: {len(S[0]['polys'])} letter faces, aspect {S[0]['aspect']:.2f}; materials {sorted(m for m in smats if 'sign' in m)}")
    for o in list(bpy.data.meshes):
        if o.name.startswith('test_'):
            bpy.data.meshes.remove(o)
    if '--no-render' in a:
        print('[test] --no-render: no stills')
    else:
        # 5. two stills under the sky family
        sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 960, 540, 100
        cd = bpy.data.cameras.new('test_lens')
        cd.clip_start, cd.clip_end = 0.3, 4500.0
        cam = bpy.data.objects.new('test_lens', cd)
        sc.collection.objects.link(cam)
        sc.camera = cam
        vs = {v[0]: v for v in T.views()}
        V.aim(cam, *vs['over_the_main_road_24mm'][1:])
        sky = TOWN.light(sc, cam, sky='sky', cache_dir=os.path.join(OUT, 'sky_cache'))
        TOWN.eevee(sc, 16)
        sc.render.image_settings.file_format = 'PNG'
        for nm in ('over_the_main_road_24mm', 'street_level_main_road_28mm'):
            V.aim(cam, *vs[nm][1:])
            sky.bake(sc.frame_current, sc.frame_current, log=lambda *m: None)
            p = os.path.join(OUT, f'town_{nm}.png')
            sc.render.filepath = p
            t1 = time.time()
            bpy.ops.render.render(write_still=True)
            img = bpy.data.images.load(p, check_existing=False)
            px = np.empty(img.size[0] * img.size[1] * 4, np.float32)
            img.pixels.foreach_get(px)
            px = px.reshape(-1, 4)[:, :3]
            m, hi = float(px.mean()), float((px > 0.98).mean())
            bpy.data.images.remove(img)
            check(0.08 < m < 0.85 and hi < 0.05, f'still {nm}: mean {m:.3f}, {hi * 100:.2f} % blown, {time.time() - t1:.1f} s')
    print(f'[test] {"ALL PASS" if not FAILS else f"{len(FAILS)} FAIL"} in {time.time() - t0:.1f} s', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        FAILS.append('exception')
    sys.stdout.flush()
    os._exit(1 if FAILS else 0)          # (no Python teardown after the GPU module's sky bake)
