"""eidoblend.sets.same_seed.lab.lows: the lab's close pieces as lows, their UVs and what the GPU bake reads (Blender).

    bash run_blender.sh blender/eidoblend/sets/same_seed/cli.py lab lows --dir <out>
        -> <out>/lab_lows.blend, <out>/bake/{bench,chair,radiators}_{low,high}.npz, .json, atlases.json

The pieces a lens comes within about two metres of: the bench and its pedestal (4096), the task chair (2048) and the two
radiators under the board (2048). Each part was built as one mass with one bevel, so its low is its OWN CONSTRUCTION
WITHOUT THE BEVEL (bake.make_low), hard where its faces turn more than the bevel's 30 degrees; a moulded part (the
chair's seat and back, their shells and piping) is its own smooth skin, drawn ring by ring on the form: the low is that
skin. Each low unwrapped by planes, each island at its true size times the square root of what the lenses see of it
(faces toward the window wall, which no lens sees, at a tenth to a third), packed with an 8-texel gutter at 4096. The AO
reaches the atlas's rigid neighbours (the floor, the floor box; the wall, the board and the skirting behind the radiators).
"""

import os

import bpy

from .. import bake as B
from .. import look as L

RAD = [f'radiator_{k}_{p}' for k in (0, 1) for p in ('front', 'back', 'ends', 'grille', 'valve', 'lockshield', 'pipe_0', 'pipe_1', 'floor_collars')]
# atlas -> (size, [part names], AO reach mm, AO neighbours by name prefix)
ATLASES = {
    'bench': (4096, ['bench_top', 'bench_legs', 'bench_rails', 'bench_stretchers', 'bench_feet', 'pedestal_body', 'pedestal_cap', 'pedestal_fronts',
                     'pedestal_handles', 'pedestal_lock', 'pedestal_castors'], 250.0, ['room_floor', 'floor_box_']),
    'chair': (2048, ['chair_base', 'chair_castors', 'chair_column', 'chair_mechanism', 'chair_lever', 'chair_seat_shell', 'chair_seat_cushion',
                     'chair_seat_piping', 'chair_back_upright', 'chair_back_cushion', 'chair_back_shell', 'chair_back_mount'], 150.0, ['room_floor']),
    'radiators': (2048, RAD, 200.0, ['room_floor', 'wall_back', 'window_board', 'skirting', 'radiator_0_fins_dark', 'radiator_1_fins_dark']),
}
MOULDED = {'chair_seat_shell', 'chair_seat_cushion', 'chair_seat_piping', 'chair_back_cushion', 'chair_back_shell'}
BAKE_RAYS = {'ao': 96, 'cav': 48}


def weight(name, c, n):
    """texels where the lenses look. c: the face's centre (m, the room's space), n: its normal. Every lens of the room
    looks along +y from y -2.0 .. -5.0 at 1.45-1.6 m: faces toward +y (the window wall) show to none of them"""
    away = n.y > 0.7
    if name.startswith('bench_top'):
        return 1.0 if n.z > 0.9 else (0.1 if n.z < -0.9 else (0.25 if away else 0.8))
    if name.startswith(('bench_legs', 'bench_rails', 'bench_stretchers')):
        if n.z > 0.9 and c.z > 0.8:
            return 0.05                                        # under the top
        return 0.3 if away else 0.7
    if name.startswith('bench_feet') or name.startswith('pedestal_castors'):
        return 0.5
    if name.startswith('pedestal'):
        if n.z < -0.9:
            return 0.05
        if away:
            return 0.12
        if n.z > 0.9:
            return 0.35                                        # (the cap: seen from 1.5 m over 0.3 m under the top)
        return 1.0 if n.y < -0.7 else 0.6
    if name.startswith('chair'):
        return 0.4 if n.z < -0.9 else 0.85
    if name.startswith('radiator'):
        if away:
            return 0.06
        if n.z < -0.9:
            return 0.15
        return 1.0 if n.y < -0.7 else 0.55
    return 1.0


def main(out_dir):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, 'lab_high.blend'))
    sc = bpy.context.scene
    room = bpy.data.collections['lab_room']
    OB = bpy.data.objects
    lows_c = bpy.data.collections.new('lab_lows')
    sc.collection.children.link(lows_c)
    bake_dir = os.path.join(out_dir, 'bake')
    record = []
    for atlas, (size, names, ao_mm, neigh) in ATLASES.items():
        highs = [OB[n] for n in names if n in OB]
        missing = [n for n in names if n not in OB]
        if missing:
            L.log('lab lows', f'{atlas}: not in the high: {missing}')
        lows = [B.make_low(h, lows_c, hard=h.name not in MOULDED) for h in highs]
        B.unwrap(lows)
        for o in lows:
            B.true_size_weighted(o, weight)
        B.pack(lows, size, rotate_method='ANY')
        dens = B.density(lows, size)
        L.log('lab lows', f'{atlas}: {len(lows)} lows packed; px/m (densest, median): ' + ', '.join(f'{k}={v}' for k, v in dens.items()))
        claims = {o.name: [o['bake_from']] for o in lows}
        cages = {o.name: (max(1.5, 0.6 * o['bevel_mm']), 3.0 + 1.6 * o['bevel_mm']) for o in lows}
        occ = [o for o in room.objects if o.type == 'MESH' and o.name.startswith(tuple(neigh)) and o.name not in names]
        B.export_atlas(atlas, lows, claims, bake_dir, size, occluders=occ, cages=cages, ao_mm=ao_mm)
        for o in lows:
            o['atlas'] = atlas
        record.append({'name': atlas, 'size': size, **BAKE_RAYS})
    B.write_atlases(os.path.join(bake_dir, 'atlases.json'), record)
    # the file: the lows stand in the room; the highs they were baked from leave (the bake's inputs hold them)
    for o in list(lows_c.objects):
        bpy.data.objects.remove(OB[o['bake_from']], do_unlink=True)
        lows_c.objects.unlink(o)
        room.objects.link(o)
    bpy.data.collections.remove(lows_c)
    for m in list(bpy.data.meshes):
        if m.users == 0:
            bpy.data.meshes.remove(m)
    return L.save(os.path.join(out_dir, 'lab_lows.blend'))
