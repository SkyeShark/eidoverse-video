"""eidoblend.sets.same_seed.lab: a lab full of light, 8.0 x 5.0 x 2.8 m, on an upper floor.

    from eidoblend.sets.same_seed import lab
    room = lab.build(ctx, render=True)                   # the made room appended (make.py makes it once)
    room.marks['bench_top']                              # the bench's face: z 0.9 over (1.6, 1.2), 2.6 x 0.8 m
    cam = room.make_camera('wide')

    python blender/eidoblend/sets/same_seed/make.py lab [--stills] [--sun 30 --sun-el 38 --world 4.5 ...]

A research office: the whole back wall above the sill one ribbon of glazing (five bays, one sash tilted open, roller
blinds over the head, two panel radiators under the board), white plaster, linoleum, a hung tile ceiling with eight LED
panels; a standing-height bench and its drawer pedestal with a screen, keyboard, mouse, computer and power strip, two
mugs, a clipboard and pen; a whiteboard with a clock over it; a task chair turned to the room's middle; and the
houseplants (eidoblend.props.houseplants): a rubber plant, a Monstera on its coir pole, a corn plant, a watering can on
the board. Daylight: a sun lamp through the windows and Poly Haven's pretoria_gardens outside, with a volume probe baked
over the room.

The room's space: x across (the cameras look along +y), y to the window wall, z up from the floor; metres. Modules: kit
(mouldings and the houseplants' kit), shell, furniture, high (the build step, the plants grown in place), lows (its three
atlases: bench 4096, chair and radiators 2048), prints (its pictures, plain Python), look (materials, CC0 models, light,
probes), cc0.json.
"""

from __future__ import annotations

import importlib

NAME = 'lab'
COLLECTION = 'lab_room'
WORLD = 'lab_world'
STEPS = ('high', 'lows', 'bake', 'prints', 'look')
ABOUT = 'a lab full of light: a ribbon of windows, a bench, a whiteboard, LED panels, a task chair and the houseplants'
MODULES = ('kit', 'shell', 'furniture', 'high', 'lows', 'prints', 'look')

MARKS = {
    'bench_top': {'pos': (1.6, 1.2, 0.9), 'size': (2.6, 0.8), 'about': "the bench's face, where things are set down"},
    'stand': {'pos': (0.0, 0.4, 0.0), 'yaw': 0.0, 'about': 'standing before the window wall, facing -y; nothing stands between the cameras and it'},
    'chair': {'pos': (1.2, -0.75, 0.0), 'about': "the task chair's column, turned toward the room's middle"},
    'rubber_plant': {'pos': (-2.8, 2.4, 0.0)}, 'monstera': {'pos': (-2.1, 2.4, 0.0)}, 'corn_plant': {'pos': (3.3, 2.4, 0.0)},
}
CAMS = {
    'wide': ((-0.8, -5.0, 1.5), (0.4, 0.4, 1.2), 26.0),
    'wide_left': ((-1.6, -4.2, 1.5), (0.4, 0.6, 1.2), 28.0),
    'window': ((-0.4, -2.2, 1.55), (0.0, 0.4, 1.5), 55.0),
    'bench': ((1.9, -2.6, 1.6), (0.2, 0.4, 1.4), 35.0),
    'plants_left': ((-1.75, 1.35, 0.95), (-2.45, 2.4, 0.3), 40.0),
    'monstera': ((-1.65, -0.04, 1.06), (-2.1, 2.36, 0.66), 50.0),
    'corn_plant': ((2.35, -0.4, 1.25), (3.3, 2.4, 0.95), 50.0),
    'whiteboard': ((1.6, 0.2, 1.6), (4.0, 1.2, 1.7), 35.0),
}
# its render settings (look.eevee): Fast GI as ambient occlusion only (the baked volume probe carries the bounce), 64 samples
RENDER = {'samples': 64, 'fast_gi_method': 'AMBIENT_OCCLUSION_ONLY'}
LOOK = {'world': 4.5, 'sun': 30.0, 'panel': 8.0, 'sun_el': 38.0, 'sun_az': 70.0, 'screen': 1.6, 'clamp': 4.0}


def build(ctx=None, **kw):
    """the made room appended into the scene (eidoblend.sets.same_seed.room.append) -> room.Room"""
    from ..room import append
    return append(NAME, ctx=ctx, **kw)


def __getattr__(name):
    if name in MODULES:
        return importlib.import_module(f'{__name__}.{name}')
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
