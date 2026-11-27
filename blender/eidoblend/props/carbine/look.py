"""eidoblend.props.carbine.look: the carbine's ONE layered material on its bakes, and its condition.

    from eidoblend.props.carbine import look
    mat = look.apply(parts, 'work/carbine/bake', condition={'wear': 1.0, 'dust': 1.0, 'grime': 1.0, 'polish': 1.0})

materials.layered.baked_material with the carbine's own tables (a working carbine carried in a dry, dusty country:
worn at its edges and where it is handled, dusty in its recesses, oiled, not rusted):
    substrates   per baked ID: hard-anodised aluminium (the upper, the lower and the fore-end each a batch's own tone),
                 phosphated steel, black oxide, moulded polymer (stock, grip), the magazine's grey dry film, stainless,
                 rubber; the anodise takes the satin grain of a CC0 photograph (ambientCG Metal027), the phosphate a
                 finer crystal (Metal063), the polymer a smudged roughness (Plastic013A)
    hands        the grip, the fore-end, the magazine's lower half, the charging handle, the selector and trigger, the
                 stock's cheek: polish and fingerprints
    knocks       the muzzle device and the front sight, the butt, the magazine's foot, the optic: chipped more
    stains       carbon at the muzzle's slots and on the deflector behind the ejection port
condition scales the wear, the polish, the dust and the grime together (1.0: as built; 0.3: nearly new; 1.6: hard
used). The lenses take a coated-glass material of their own.
"""

from __future__ import annotations

import bpy

from ...materials import layered as LY

IDS = {1: 'upper_anodised', 2: 'lower_anodised', 3: 'rail_anodised', 4: 'anodised', 5: 'phosphate', 6: 'muzzle', 7: 'oxide',
       8: 'stock_polymer', 9: 'grip_polymer', 10: 'magazine', 11: 'stainless', 12: 'glass', 13: 'rubber'}


def substrate(n: str) -> int:
    """The substrate ID of a part by its name (the ID map's value and the tables' row)."""
    if 'lens' in n:
        return 12
    if n == 'optic_front_sleeve':
        return 13
    if n in ('magazine', 'magazine_floor_plate'):
        return 10
    if n == 'pistol_grip':
        return 9
    if n in ('stock', 'stock_latch'):
        return 8
    if n == 'upper_receiver':
        return 1
    if n == 'lower_receiver':
        return 2
    if n == 'rail_fore_end':
        return 3
    if n in ('receiver_extension', 'charging_handle', 'trigger_guard', 'delta_ring', 'optic', 'optic_mount', 'rear_sight',
             'brightness_knob') or n.startswith(('turret', 'battery')):
        return 4
    if n == 'flash_hider':
        return 6
    if n == 'gas_tube':
        return 11
    if n.startswith(('grip_screw', 'mount_', 'rs_')):
        return 7
    return 5


def _row(base, worn, c2, c3, c4, c5):
    """(base, worn, (base rough, base metal, worn metal), (worn rough, wear, polish), (dust, grime, grain),
    (mottle, rub, scratches)) as a Substrate"""
    return LY.Substrate(base, worn, c2[0], c2[1], c2[2], c3[0], c3[1], c3[2], c4[0], c4[1], c4[2], c5[0], c5[1], c5[2])


ALU, STEEL, POLY = (0.70, 0.71, 0.73), (0.50, 0.50, 0.52), (0.030, 0.030, 0.031)
# (the anodise a little cool beside the phosphate's warm grey; the magazine a mid grey, the lightest thing on it)
SUBSTRATES = {
    1: _row((0.026, 0.031, 0.033), ALU, (0.46, 0.0, 1.0), (0.30, 1.0, 0.6), (0.6, 0.7, 0), (0.05, 1.3, 0.6)),       # upper
    2: _row((0.024, 0.028, 0.030), ALU, (0.48, 0.0, 1.0), (0.30, 1.0, 0.6), (0.6, 0.7, 0), (0.05, 1.3, 0.6)),       # lower
    3: _row((0.024, 0.028, 0.030), ALU, (0.47, 0.0, 1.0), (0.30, 1.2, 0.9), (0.6, 0.7, 0), (0.05, 1.3, 0.6)),       # fore-end
    4: _row((0.025, 0.028, 0.030), ALU, (0.46, 0.0, 1.0), (0.30, 0.9, 0.5), (0.6, 0.7, 0), (0.05, 1.2, 0.5)),       # anodise
    5: _row((0.048, 0.046, 0.041), STEEL, (0.66, 0.0, 1.0), (0.36, 0.9, 0.5), (0.6, 0.8, 1), (0.09, 0.8, 0.2)),     # phosphate
    6: _row((0.048, 0.046, 0.041), STEEL, (0.68, 0.0, 1.0), (0.36, 0.4, 0.3), (0.6, 0.9, 1), (0.09, 0.8, 0.2)),     # muzzle
    7: _row((0.021, 0.021, 0.023), STEEL, (0.42, 0.0, 1.0), (0.34, 0.7, 0.3), (0.5, 0.6, 1), (0.03, 1.0, 0.2)),     # oxide
    8: _row((0.0145, 0.0145, 0.0155), POLY, (0.56, 0.0, 0.0), (0.32, 0.6, 0.8), (0.6, 0.5, 2), (0.03, 0.6, 0.1)),   # stock
    9: _row((0.0150, 0.0150, 0.0160), POLY, (0.52, 0.0, 0.0), (0.30, 0.6, 1.0), (0.5, 0.5, 2), (0.03, 0.6, 0.1)),   # grip
    10: _row((0.150, 0.156, 0.160), ALU, (0.50, 0.0, 1.0), (0.40, 0.25, 0.7), (0.5, 0.5, 0), (0.08, 0.1, 0.7)),     # magazine
    11: _row((0.50, 0.48, 0.45), (0.50, 0.48, 0.45), (0.40, 1.0, 1.0), (0.40, 0.0, 0.0), (0.4, 0.3, 4), (0.10, 0.0, 0.0)),  # stainless
    12: _row((0.02, 0.02, 0.02), POLY, (0.05, 0.0, 0.0), (0.05, 0.0, 0.0), (0.0, 0.0, 4), (0.0, 0.0, 0.0)),         # (glass)
    13: _row((0.017, 0.017, 0.017), POLY, (0.74, 0.0, 0.0), (0.60, 0.2, 0.5), (0.7, 0.6, 2), (0.03, 0.3, 0.0)),     # rubber
}
# where hands go (soft boxes in the carbine's mm): the grip, the fore-end, the magazine's lower half, the charging handle,
# the selector and trigger, the stock's cheek
HANDS = [((-15, -40, -160), (75, 40, -45), 6.0), ((225, -40, -40), (378, 40, 40), 8.0), ((125, -40, -200), (215, 40, -105), 8.0),
         ((5, -25, 18), (42, 25, 34), 4.0), ((45, -20, -45), (75, 20, -20), 4.0), ((-175, -30, -2), (-95, 30, 22), 10.0)]
# the extremities, where knocks go: the muzzle device and sight, the butt, the magazine's foot, the optic
KNOCKS = [('x', 400.0, 440.0), ('x', -120.0, -150.0), ('z', -150.0, -170.0), ('z', 70.0, 80.0)]
# carbon at the muzzle's slots; on the deflector behind the ejection port (the right side)
STAINS = [([('x', 548.0, 568.0)], 0.8), ([('x', 84.0, 92.0), ('x', 116.0, 108.0), ('z', -4.0, 4.0), ('y', -8.0, -12.0)], 0.65)]


def lens_material(name='carbine.lens_coated'):
    """The optic's coated glass: a warm metallic coating, nearly a mirror."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value, b.inputs['Roughness'].default_value, b.inputs['Metallic'].default_value = (0.35, 0.08, 0.03, 1), 0.04, 1.0
    return m


def apply(parts, bake_dir, name='carbine', condition=None, photo_set=None):
    """The layered material on the low's parts (lenses: the coated glass). Returns the material."""
    maps = LY.load_bake(bake_dir, name)
    mat = LY.baked_material(f'{name}.layered', maps, SUBSTRATES, photo_set=photo_set, hands=HANDS, knocks=KNOCKS,
                            stains=STAINS, condition=condition)
    lens = lens_material(f'{name}.lens_coated')
    for o in parts:
        o.data.materials.clear()
        o.data.materials.append(lens if 'lens' in o.name else mat)
    return mat
