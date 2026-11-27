"""eidoblend.props.helicopter.high: the helicopter built part by part, as the aircraft is: one measured datum
(datum.py), a lofted skin whose sections are the aircraft's own, a hollow cockpit and cabin, openings cut through the
wall with their glass, retainers, seals and screws, and each assembly by itself.

    from eidoblend.props.helicopter import high
    col = high.build()       # in the open scene: the collection 'helicopter_high' (290 parts) and the Empties
                             # 'main_rotor' / 'tail_rotor' that turn the rotors (helicopter.spin keys them)

    hull    the skin, the hollow, the openings, the glazing and its frames      (leaves b.surf, the skin to ask)
    top     the spine over the controls and the gearbox, the two engines' cowlings, intakes, exhausts and their shields,
            the drive shaft's cover                                             (leaves b.spine)
    tail    the pylon, the stabilator, the tail rotor
    rotor   the mast, swashplate, hub, spindles, dampers, pitch links, bifilar, the four blades
    gear    the main gear (drag beams, oleos, wheels, brakes) and the tail wheel, hanging as in flight
    cabin   the floor, ceiling, the troop and gunners' seats, the pilots' seats, the panel and consoles
    doors   the cabin doors slid aft on their tracks, the cockpit doors' hinges and handles
    fit     what stands on the skin: pitots, cutters, wipers, aerials, steps, handholds, lights, the hook

SPACE: millimetres in every table (x AFT of the mast, y RIGHT, z UP from the cabin floor); the scene is in metres. The
parts carry clay materials named for their role ('clay', 'clay_glass', 'clay_rubber', 'clay_dark', 'clay_fabric',
'clay_steel', 'clay_liner', 'clay_floor'): look.py gives each its material by that role and the part's name.
"""

from __future__ import annotations

import types

from ..hardsurface import masses as hs
from . import cabin, doors, fit, gear, hull, rotor, tail, top

PARTS = ('hull', 'top', 'tail', 'rotor', 'gear', 'cabin', 'doors', 'fit')
_MODULES = {'hull': hull, 'top': top, 'tail': tail, 'rotor': rotor, 'gear': gear, 'cabin': cabin, 'doors': doors, 'fit': fit}


def build(parts=PARTS, name='helicopter_high'):
    """Build the helicopter's high in the open scene (best in an empty file: parts find each other by name). parts:
    the assemblies to build, in order (doors and fit need the hull; fit needs the top). Returns the collection."""
    hs.start(name, orient=False)
    b = types.SimpleNamespace(
        clay=hs.mat('clay', (0.5, 0.5, 0.5), 0.6, 0.0), glass=hs.mat('clay_glass', (0.012, 0.016, 0.016), 0.3, 0.0),
        rubber=hs.mat('clay_rubber', (0.04, 0.04, 0.04), 0.7, 0.0), dark=hs.mat('clay_dark', (0.02, 0.02, 0.02), 0.5, 0.0),
        fabric=hs.mat('clay_fabric', (0.33, 0.34, 0.30), 0.95, 0.0), steel=hs.mat('clay_steel', (0.62, 0.62, 0.62), 0.35, 1.0),
        liner=hs.mat('clay_liner', (0.30, 0.32, 0.30), 0.8, 0.0), floor=hs.mat('clay_floor', (0.22, 0.22, 0.23), 0.9, 0.0),
        surf=None, spine=None)
    for p in parts:
        _MODULES[p].build(b)
    hs.sweep_tmp()
    print(f'[helicopter] {len(hs.REPORT)} parts, open-edged: {[r[0] for r in hs.REPORT if r[1]]}; faces {sum(r[3] for r in hs.REPORT):,}')
    return hs.col
