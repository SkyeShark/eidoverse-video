"""eidoblend.sets.same_seed.desk.lows: the desk room's close pieces as lows, their UVs and what the GPU bake reads
(Blender).

    bash run_blender.sh blender/eidoblend/sets/same_seed/cli.py desk lows --dir <out>
        -> <out>/desk_lows.blend, <out>/bake/{desk,computer,guitar,window,radiator,door}_{low,high}.npz, .json, atlases.json

The built pieces the room's lenses hold for longest keep their HIGH as the builder made it (one mass a part, a
three-segment bevel on its arrises) and get a LOW DRAWN ON IT: a part made as one mass of boxes, prisms, rings and
sweeps has for its low ITS OWN CONSTRUCTION WITHOUT THE BEVEL (bake.make_low), hard where its faces turn more than the
bevel's 30 degrees; a moulded part (the headphones' pads and band cushion, the mouse's shell) is its own smooth skin,
drawn ring by ring on the form by the builder: the low is that skin, smooth all over. The lows KEEP their material
slots (the guitar's body is spruce on top, rosewood round it: the look gives each slot its family's material).
THE ATLASES, all 2048 (the nearest of the room's wide lenses is 2.5-4 m from any of them):
  desk      the oak top, the welded frame, the grommet, the glides
  computer  the monitor (body, neck, hinge, base), the keyboard's case and caps, the mouse, the PC's case and front, the
            headphones (cups, yokes, band, sliders, cushion, pads)
  guitar    the body (top, back and sides in one mass), neck, fingerboard, bridge, pickguard, nut, saddle
  window    the frame, both sashes, both beads, the mullion, the handles and hinges, the board
  radiator  the front panel, side covers, grille, thermostat and grip, pipes and collars
  door      the leaf, its lining (two legs and head), the architraves, the handle, the hinges
Each low unwrapped by planes, each island at its true size times the square root of what the lenses see of it (faces
toward the window wall and the door's corridor side at 6 %, undersides at 10 %), packed with a 4-texel gutter. The AO
reaches the atlas's rigid neighbours (the floor, the walls, the board; nothing that moves or is set down).
"""

import os

import bpy

from .. import bake as B
from .. import look as L

HP = ['headphone_cup_l', 'headphone_cup_r', 'headphone_yoke_l', 'headphone_yoke_r', 'headphone_band', 'headphone_slider_l',
      'headphone_slider_r', 'headphone_cushion', 'headphone_pad_l', 'headphone_pad_r']
# atlas -> (size, [part names], AO reach mm, AO neighbours by name prefix)
ATLASES = {
    'desk': (2048, ['desk_top', 'desk_frame_parts', 'desk_grommet_ring', 'desk_grommet_cap', 'desk_glides'], 250.0, ['room_floor']),
    'computer': (2048, ['monitor_body', 'monitor_neck', 'monitor_hinge', 'monitor_base', 'kb_case', 'keyboard_keycaps', 'mouse_shell',
                        'mouse_base', 'pc_case', 'pc_front_panel'] + HP, 80.0, ['desk_top', 'desk_mat', 'room_floor', 'keyboard_switches']),
    'guitar': (2048, ['guitar_body', 'guitar_neck', 'guitar_fingerboard', 'guitar_bridge', 'guitar_pickguard', 'guitar_nut', 'guitar_saddle'],
               150.0, ['room_floor', 'wall_back', 'skirting_back_and_sides', 'guitar_frets', 'guitar_tuners', 'guitar_bridge_pins']),
    'window': (2048, ['window_frame', 'window_sash_0', 'window_sash_1', 'window_bead_0', 'window_bead_1', 'window_mullion',
                      'window_handles_and_hinges', 'window_board'], 150.0, ['wall_back', 'window_gasket_', 'window_sill_outside']),
    'radiator': (2048, ['radiator_front_panel', 'radiator_side_cover_l', 'radiator_side_cover_r', 'radiator_grille', 'radiator_thermostat',
                        'radiator_thermostat_grip', 'radiator_pipes_and_collars'], 200.0,
                 ['room_floor', 'wall_back', 'window_board', 'skirting_back_and_sides', 'radiator_fins', 'radiator_back_panel']),
    'door': (2048, ['door_leaf', 'door_lining_front', 'door_lining_back', 'door_lining_head', 'door_architrave', 'door_handle', 'door_hinges'],
             200.0, ['wall_right', 'room_floor', 'door_backing', 'skirting_right_front']),
}
MOULDED = {'headphone_cushion', 'headphone_pad_l', 'headphone_pad_r', 'mouse_shell'}
BAKE_RAYS = {'ao': 96, 'cav': 48}


def weight(name, c, n):
    """texels where the lenses look. c: the face's centre (m, the room's space), n: its normal. Every lens of the room
    looks along +y from y -2.1 .. -4.6 at 1.3-1.55 m: faces toward +y (the window wall) show to none of them; the door's
    corridor side (+x) to none; undersides to almost none; what lies below the lenses' eyes shows its top most"""
    if n.y > 0.7:
        return 0.06
    if name.startswith('door') and n.x > 0.7:
        return 0.06
    if n.z < -0.9:
        return 0.1
    if n.z > 0.9 and c.z < 1.2:
        return 1.0
    return 0.8 if abs(n.y) < 0.7 else 1.0


def main(out_dir):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, 'desk_high.blend'))
    sc = bpy.context.scene
    room = bpy.data.collections['desk_room']
    OB = bpy.data.objects
    lows_c = bpy.data.collections.new('desk_lows')
    sc.collection.children.link(lows_c)
    bake_dir = os.path.join(out_dir, 'bake')
    record = []
    for atlas, (size, names, ao_mm, neigh) in ATLASES.items():
        highs = [OB[n] for n in names if n in OB]
        missing = [n for n in names if n not in OB]
        if missing:
            L.log('desk lows', f'{atlas}: not in the high: {missing}')
        lows = [B.make_low(h, lows_c, hard=h.name not in MOULDED, keep_slots=True, smooth_soft=True) for h in highs]
        B.unwrap(lows)
        for o in lows:
            B.true_size_weighted(o, weight)
        B.pack(lows, size, rotate_method='ANY')
        dens = B.density(lows, size)
        L.log('desk lows', f'{atlas}: {len(lows)} lows packed; px/m (densest, median): ' + ', '.join(f'{k}={v}' for k, v in dens.items()))
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
    return L.save(os.path.join(out_dir, 'desk_lows.blend'))
