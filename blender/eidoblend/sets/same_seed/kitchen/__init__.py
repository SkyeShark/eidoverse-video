"""eidoblend.sets.same_seed.kitchen: a family's kitchen at noon, 6.0 x 5.0 m with a 9 ft (2743 mm) ceiling.

    from eidoblend.sets.same_seed import kitchen
    room = kitchen.build(ctx, render=True)               # the made room appended (make.py makes it once)
    room.marks['table_top']                              # the table's top: z 0.74 over (0.9, -0.45), 1.5 x 0.9 m
    cam = room.make_camera('wide')

    python blender/eidoblend/sets/same_seed/make.py kitchen [--stills] [--quick] [--sun 14 --sun-el 30 --garden 4 ...]

An eat-in kitchen in a timber-framed house: plastered walls, a soffit over the wall cupboards, a twin double-hung
window over the sink with its roller shades, a two-panel door to the hall, colonial base boards, two ceiling fittings
(off at noon), a clock over the window; white painted cupboards (frame-and-panel doors, nickel knobs and hinges), a
beige laminate worktop, a steel sink and its tap, a dishwasher, an electric cooker (its oven window opaque smoked glass
with a clear coat) under its hood, a refrigerator with a child's drawing, a school letter and a shopping list held on
it by magnets; a farmhouse table in coated pine with four Windsor chairs (the child's pulled out from the table's end,
a gingham cushion on it), the homework on the table (a worksheet, a spelling sheet, a composition book, pencils, a
glass of milk), a school bag; the basil on the window's stool (eidoblend.props.houseplants.basil). Poly Haven gives a
wooden bowl of apples, pears and bananas and a cutting board. Noon: a winter sun through the window, the sky at the
glass, suburban_garden outside on a backdrop seen only through the glass, a volume probe baked over the room.

The room's space: x across (the cameras look along +y), y to the back wall (the window's), z up from the floor;
metres. Modules: kit (its numbers and build helpers), shell, cabinets, fridge, table, things (the build's groups, in
that order), high (the build step), lows (the table, the cupboards' fronts and the refrigerator as lows, baked in
Blender's Cycles: their own bake, which the look's wear thresholds are set on; about 13 minutes at 4096 on a desktop
GPU, --quick a preview), prints (its pictures, plain Python), look (materials, CC0 models, light, probes), cc0.json.
"""

from __future__ import annotations

import importlib

NAME = 'kitchen'
COLLECTION = 'kitchen_room'
WORLD = 'kitchen_noon_world'
STEPS = ('high', 'lows', 'prints', 'look')
ABOUT = 'the kitchen at noon: cupboards, a cooker, a refrigerator, a farmhouse table with the homework on it, the basil on the sill'
MODULES = ('kit', 'shell', 'cabinets', 'fridge', 'table', 'things', 'high', 'lows', 'prints', 'look')

# what a performance and the props stand on (metres, the room's space)
MARKS = {
    'table_top': {'pos': (0.9, -0.45, 0.74), 'size': (1.5, 0.9), 'about': "the table's top, where things are set down"},
    'homework': {'pos': (0.68, -0.2, 0.74), 'size': (0.216, 0.279), 'about': 'the worksheet being read, turned 184 degrees on the top'},
    'child_chair': {'pos': (1.98, -0.4, 0.0), 'yaw': 110.0, 'about': "the child's chair, pulled out from the table's end and turned; its seat about 0.45 up"},
    'stand': {'pos': (0.9, 0.3, 0.0), 'yaw': 0.0, 'about': 'standing between the table and the sink, facing -y; nothing stands between the cameras and it'},
    'basil': {'pos': (1.47, 3.003, 1.112), 'about': "the basil's saucer on the window's stool"},
}
# its cameras: (position, aim, lens mm on a 36 mm sensor); the first three are the film's
CAMS = {
    'wide': ((0.4, -4.6, 1.4), (0.9, 0.0, 1.1), 28.0),
    'table': ((0.0, -2.3, 1.5), (0.85, 0.1, 1.1), 40.0),
    'window': ((0.9, -2.6, 1.55), (0.9, 0.3, 1.5), 60.0),
    'table_homework': ((0.55, -1.25, 1.25), (0.85, -0.35, 0.74), 40.0),
    'cupboard_door_knob': ((-2.05, 1.55, 0.95), (-1.95, 2.37, 0.62), 50.0),
    'fridge_papers': ((2.2, 1.1, 1.35), (2.56, 2.21, 1.15), 40.0),
    'sink_tap_sun': ((0.55, 1.75, 1.45), (0.9, 2.75, 0.98), 40.0),
    'basil_on_the_sill': ((1.25, 2.35, 1.38), (1.47, 3.0, 1.2), 50.0),
    'chair_and_cushion': ((2.35, -1.45, 0.95), (1.98, -0.4, 0.45), 40.0),
    'cooker_and_kettle': ((-1.0, 1.55, 1.45), (-1.16, 2.7, 0.95), 40.0),
    'window_and_clock': ((0.9, 0.9, 1.6), (0.9, 3.0, 1.8), 35.0),
}
# its render settings (look.eevee), the film's own: 96 samples, AgX at exposure +0.3, screen-traced rays, Fast GI as
# global illumination to 1.5 m; what it does not name keeps Blender's own (base=False)
RENDER = {'base': False, 'samples': 96, 'exposure': 0.3, 'shadow_pool': None, 'use_raytracing': True, 'ray_tracing_method': 'SCREEN',
          'use_shadows': True, 'shadow_ray_count': 2, 'shadow_step_count': 8, 'use_fast_gi': True, 'fast_gi_method': 'GLOBAL_ILLUMINATION',
          'fast_gi_distance': 1.5, 'fast_gi_resolution': '2', 'use_shadow_jitter_viewport': True, 'volumetric_tile_size': '8',
          'rt': {'resolution_scale': '1', 'trace_max_roughness': 0.6, 'use_denoise': True}}
# its look's options and their defaults (make.py --sun 14 --sun-el 30 ...)
LOOK = {'sun': 14.0, 'sun_el': 30.0, 'sun_az': -22.0, 'sky': 22.0, 'fill': 25.0, 'garden': 4.0, 'garden_rot': -18.0, 'ambient': 0.3}


def build(ctx=None, **kw):
    """the made room appended into the scene (eidoblend.sets.same_seed.room.append) -> room.Room"""
    from ..room import append
    return append(NAME, ctx=ctx, **kw)


def __getattr__(name):
    if name in MODULES:
        return importlib.import_module(f'{__name__}.{name}')
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
