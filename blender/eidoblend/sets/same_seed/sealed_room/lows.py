"""eidoblend.sets.same_seed.sealed_room.lows: the sealed room's lows, their UVs and what the GPU bake reads (Blender).

    bash run_blender.sh blender/eidoblend/sets/same_seed/cli.py sealed_room lows --dir <out>
        -> <out>/sealed_room_lows.blend, <out>/bake/{bench,door,plates,fixtures}_{low,high}.npz, .json, atlases.json

FOUR ATLASES:
  bench    4096: the bench's lows as bench.py drew them (their UVs written at true size as they were built), each
                 claiming its HIGH parts by name (the high file's 'bake_claims'): a leg claims its foot weld and the
                 stretchers' end welds, so the beads bake into both pieces they join.
  door     2048: the door, its frame, kick plate, lock blank, lite rim and closer;
  plates   2048: the two window plates, their sills and bolts;
  fixtures 2048: the vent, the switch, the boxes, the straps, the connectors.
                 Each of these a part made as one mass with ONE bevel, so its low is its OWN CONSTRUCTION WITHOUT THE
                 BEVEL (bake.make_low), unwrapped by planes.
Each low's islands at true size times the square root of what the lenses see of them (weight()), packed with an 8-texel
gutter at 4096. The AO of each atlas reaches its rigid neighbours (the floor, the wall behind; nothing movable).
"""

import json
import os

import bpy

from .. import bake as B
from .. import look as L

DOOR = ['door_frame', 'door_leaf', 'door_lock_blank', 'door_kick_plate', 'door_screws', 'door_lite_rim', 'door_closer_body', 'door_closer_pinion',
        'door_closer_arm', 'door_closer_forearm', 'door_closer_elbow', 'door_closer_shoe', 'door_closer_shoe_pin']
PLATES = ['window_back_plate', 'window_left_plate', 'window_back_sill', 'window_left_sill', 'window_back_bolts', 'window_left_bolts']
FIX = ['vent_frame', 'vent_blades', 'vent_screws', 'switch_box', 'switch_cover', 'switch_boss', 'switch_toggle', 'ceiling_box',
       'ceiling_box_cover', 'box_cover_screws', 'conduit_straps']
# atlas -> (size, AO reach mm, AO neighbours by name prefix)
ATLASES = {
    'bench': (4096, 250.0, ['room_floor']),
    'door': (2048, 200.0, ['wall_back', 'room_floor', 'door_backing', 'cove_base_back']),
    'plates': (2048, 150.0, ['wall_back', 'wall_left']),
    'fixtures': (2048, 150.0, ['wall_back', 'wall_left', 'room_ceiling', 'conduit_']),
}
BAKE_RAYS = {'ao': 96, 'cav': 48}


def weight(name, c, n):
    """texels where the lenses look. c: a face's centre (m, the room's space), n: its normal. Every lens of the room
    looks from the front half (y < 0.3) toward +y, from 1.0-2.3 m up."""
    if name.startswith('bench_top'):
        if n.z > 0.9 and c.z > 0.87:
            return 1.0                                          # the face things lie on
        return 0.04 if n.z < -0.9 else 0.7                     # (the underside: nobody sees it)
    if name.startswith('bench_shelf'):
        return 0.6 if n.z > 0.9 else (0.04 if n.z < -0.9 else 0.4)
    if name.startswith('bench_leg') or name.startswith('bench_stretcher'):
        return 0.55 if n.y < 0.5 else 0.3
    if name.startswith('bench_foot'):
        return 0.35
    if name.startswith('door_'):
        return 1.0 if n.y < -0.7 else 0.2                      # (its room side faces -y)
    if name.startswith('window_back'):
        return 1.0 if n.y < -0.7 else 0.12
    if name.startswith('window_left'):
        return 1.0 if n.x > 0.7 else 0.12
    return 0.8 if (n.y < -0.7 or n.x > 0.7 or n.z < -0.7) else 0.3


def main(out_dir):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, 'sealed_room_high.blend'))
    sc = bpy.context.scene
    room = bpy.data.collections['sealed_room']
    OB = bpy.data.objects
    lows_c = bpy.data.collections.new('sealed_lows')
    sc.collection.children.link(lows_c)
    bench_claims = json.loads(sc['bake_claims'])
    bake_dir = os.path.join(out_dir, 'bake')
    names = {'bench': sorted(bench_claims), 'door': DOOR, 'plates': PLATES,
             'fixtures': FIX + sorted(o.name for o in room.objects if o.name.startswith('connector_'))}
    record = []
    for atlas, (size, ao_mm, neigh) in ATLASES.items():
        if atlas == 'bench':
            lows = [OB[n] for n in names[atlas]]
            for o in lows:                                      # (drawn and unwrapped by bench.py)
                room.objects.unlink(o)
                lows_c.objects.link(o)
                o.data.uv_layers.active = o.data.uv_layers['atlas']
            claims = {o.name: bench_claims[o.name] for o in lows}
            cages = {o.name: ((6.0, 3.0) if o.name.startswith(('bench_leg', 'bench_stretcher', 'bench_foot_plate', 'bench_foot_nut')) else (2.0, 3.0))
                     for o in lows}
            occ = [o for o in bpy.data.collections['bench_high'].objects if o.name.startswith('bench_rail_')]   # (AO only)
        else:
            highs = [OB[n] for n in names[atlas] if n in OB]
            missing = [n for n in names[atlas] if n not in OB]
            if missing:
                L.log('sealed lows', f'{atlas}: not in the high: {missing}')
            lows = [B.make_low(h, lows_c) for h in highs]
            B.unwrap(lows)
            claims = {o.name: [o['bake_from']] for o in lows}
            cages = {o.name: (max(1.5, 0.6 * o['bevel_mm']), 3.0 + 1.6 * o['bevel_mm']) for o in lows}
            occ = []
        for o in lows:
            B.true_size_weighted(o, weight)
        B.pack(lows, size)
        dens = B.density(lows, size)
        L.log('sealed lows', f'{atlas}: {len(lows)} lows packed; px/m (densest, median): '
                             + ', '.join(f'{k}={v}' for k, v in list(dens.items())[:8]) + (' ...' if len(dens) > 8 else ''))
        members = {h for c in claims.values() for h in c}
        occ += [o for o in room.objects if o.type == 'MESH' and o.name.startswith(tuple(neigh)) and o.name not in members]
        B.export_atlas(atlas, lows, claims, bake_dir, size, occluders=occ, cages=cages, ao_mm=ao_mm)
        for o in lows:
            o['atlas'] = atlas
        record.append({'name': atlas, 'size': size, **BAKE_RAYS})
    B.write_atlases(os.path.join(bake_dir, 'atlases.json'), record)
    # the file: the lows stand in the room; the highs they were baked from leave (the bake's inputs hold them)
    gone = {o['bake_from'] for o in lows_c.objects if o.get('bake_from')}
    for n in gone:
        bpy.data.objects.remove(OB[n], do_unlink=True)
    for o in list(lows_c.objects):
        lows_c.objects.unlink(o)
        room.objects.link(o)
    bpy.data.collections.remove(lows_c)
    hc = bpy.data.collections['bench_high']
    for o in list(hc.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(hc)
    del sc['bake_claims']
    for m in list(bpy.data.meshes):
        if m.users == 0:
            bpy.data.meshes.remove(m)
    return L.save(os.path.join(out_dir, 'sealed_room_lows.blend'))
