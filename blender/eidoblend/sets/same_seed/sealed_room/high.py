"""eidoblend.sets.same_seed.sealed_room.high: the sealed room's build step (Blender): the shell and fixtures (room.py)
and the bench's HIGH (collection bench_high, unrendered: what the bake reads) and LOW (in the room: what renders), with
each low's claims on the high (the scene's 'bake_claims', a json string).

    bash run_blender.sh blender/eidoblend/sets/same_seed/cli.py sealed_room high --dir <out>   -> <out>/sealed_room_high.blend
"""

import json
import os

import bpy

from ....props.hardsurface import masses as hs
from .. import look as L
from . import bench, room


def build():
    """the room's parts into collection 'sealed_room' of a new file -> {low name: [high names]}"""
    hs.new_file()
    sc = hs.start('sealed_room', orient=False)
    clay = hs.mat('clay', (0.5, 0.5, 0.5), 0.6, 0.0)
    dark = hs.mat('clay_dark', (0.03, 0.03, 0.03), 0.4, 0.0)
    room.build(hs, clay, dark)
    hs.sweep_tmp()
    high = bpy.data.collections.new('bench_high')
    sc.collection.children.link(high)
    claims = bench.build(high, hs.col)
    for o in high.objects:
        bench.finish_high(o, clay)
    lows = [o for o in hs.col.objects if o.name.startswith('bench_') and o.name.endswith('_low')]
    for o in lows:
        bench.finish_low(o, clay)
    missing = sorted({h for hl in claims.values() for h in hl if h not in bpy.data.objects})
    if missing or sorted(claims) != sorted(o.name for o in lows):
        raise RuntimeError(f'the bench\'s claims do not match its parts: missing highs {missing}')
    sc['bake_claims'] = json.dumps(claims)
    high.hide_render = True
    bpy.data.collections.remove(hs.tmp)
    tri = lambda objs: sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)  # noqa: E731
    opened = [r[0] for r in hs.REPORT if r[1]]
    L.log('sealed high', f'{len(hs.col.objects)} parts; bench high {len(high.objects)} parts {tri(high.objects):,} tris, '
                         f'low {len(lows)} parts {tri(lows):,} tris; open-edged: {opened or "none"}')
    return claims


def main(out_dir):
    build()
    return L.save(os.path.join(out_dir, 'sealed_room_high.blend'))
