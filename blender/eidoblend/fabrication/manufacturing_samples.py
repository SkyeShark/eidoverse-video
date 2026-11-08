"""eidoblend.fabrication.manufacturing_samples: ordinary source meshes shared by the examples (manufacturing_samples.js,
MIT / CC0), built with three's exact tessellation (three_geometry) as Blender objects.

    ob = manufacturing_sample('handle')    # 'Offset handle mesh': an empty with a tapered shaft and an offset lug
    ob = manufacturing_sample('bracket')   # 'Fork bracket with bore': a 12 mm extruded fork with a 4 mm bore
    ob = manufacturing_sample('ring')      # a torus knot ring (128 x 16, p 2, q 3)

Each lands at the origin in the given collection (the scene's by default), placed as the original places it.
"""

from __future__ import annotations

import math

from . import three_geometry as tg

SAMPLES = ('handle', 'bracket', 'ring')


def manufacturing_sample(name='handle', collection=None, as_parts=False):
    """as_parts=True returns the planners' exact form instead of objects: three_geometry.Parts for the handle (its
    placements in double precision, as three composes them) and the bare Geom for the bracket and ring."""
    if as_parts:
        if name == 'handle':
            parts = tg.Parts()
            parts.add(tg.cylinder(.012, .010, .080, 40, 6), 'Offset handle shaft', rotation=(0, 0, math.pi / 2))
            parts.add(tg.capsule(.005, .030, 6, 20), 'Offset handle lug', position=(.004, .012, .004),
                      rotation=(0, 0, math.pi / 2))
            return parts
        if name == 'bracket':
            outline = [(-.030, -.015), (.030, -.015), (.030, .015), (.012, .015), (.012, -.001), (-.012, -.001),
                       (-.012, .015), (-.030, .015)]
            hole = tg.circle_hole(-.021, .006, .004, 0, math.pi * 2, True, curve_segments=24)
            g = tg.extrude(tg.shape(outline, [hole]), depth=.012, curve_segments=24).rotate_x(-math.pi / 2)
            g.name = 'Fork bracket with bore'
            return g
        if name == 'ring':
            return tg.torus_knot(.018, .0045, 128, 16, 2, 3)
        raise ValueError('Unknown source mesh sample')
    import bpy
    col = collection or bpy.context.scene.collection
    if name == 'handle':
        group = tg.make_object('Offset handle mesh', None, collection=col)
        tg.make_object('Offset handle shaft', tg.cylinder(.012, .010, .080, 40, 6), rotation=(0, 0, math.pi / 2),
                       parent=group, collection=col)
        tg.make_object('Offset handle lug', tg.capsule(.005, .030, 6, 20), position=(.004, .012, .004),
                       rotation=(0, 0, math.pi / 2), parent=group, collection=col)
        return group
    if name == 'bracket':
        outline = [(-.030, -.015), (.030, -.015), (.030, .015), (.012, .015), (.012, -.001), (-.012, -.001), (-.012, .015),
                   (-.030, .015)]
        hole = tg.circle_hole(-.021, .006, .004, 0, math.pi * 2, True, curve_segments=24)
        g = tg.extrude(tg.shape(outline, [hole]), depth=.012, curve_segments=24).rotate_x(-math.pi / 2)
        return tg.make_object('Fork bracket with bore', g, collection=col)
    if name == 'ring':
        return tg.make_object('Torus knot ring', tg.torus_knot(.018, .0045, 128, 16, 2, 3), collection=col)
    raise ValueError('Unknown source mesh sample')
