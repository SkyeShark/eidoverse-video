"""eidoblend.sets.same_seed.sealed_room: a sealed room in an old government building, 5.0 x 4.6 x 2.6 m.

    from eidoblend.sets.same_seed import sealed_room
    room = sealed_room.build(ctx)                        # the made room appended (make.py makes it once)
    room.marks['bench_top']                              # the bench's face: z 0.88 over (0, -0.75), 1.4 x 0.6 m
    cam = room.make_camera('bench_right')

    python blender/eidoblend/sets/same_seed/make.py sealed_room [--stills]

Painted concrete block on three walls, a vinyl tile floor, a painted concrete ceiling, a rubber cove base; two window
openings closed with 6 mm steel plates bolted over them above their old sills; a flush steel door with no handle on
this side; EMT conduit from the switch to the ceiling box, the light and the camera; a return grille. A welded steel
bench (a formed 2.5 mm top on square tube, a shelf, levelling feet) is its one piece of furniture; Poly Haven gives it
a workshop stool (metal_stool_02), a wall camera in the corner (security_camera_02) and one fluorescent batten
(mounted_fluorescent_lights). Its own light only: the world is black.

The room's space: x across (the cameras look along +y), y to the back wall (the door is in it), z up from the floor;
metres, the floor at z 0, the room's centre over the origin. Modules: room (the shell and fixtures), bench (the bench,
high and low), high (the build step), lows (its four atlases: bench 4096, door, plates, fixtures 2048), look (its
materials, CC0 models and light), cc0.json (its CC0 IDs).
"""

from __future__ import annotations

import importlib

NAME = COLLECTION = 'sealed_room'
WORLD = 'sealed_room_world'
STEPS = ('high', 'lows', 'bake', 'look')
ABOUT = 'a sealed room: painted block, plated windows, a door with no handle, a welded steel bench, its own light'
MODULES = ('room', 'bench', 'high', 'lows', 'look')

# what a performance and the props stand on (metres, the room's space)
MARKS = {
    'bench_top': {'pos': (0.0, -0.75, 0.88), 'size': (1.4, 0.6), 'about': "the bench's face, where a prop is set down"},
    'stool_seat': {'pos': (-1.2, 0.8, 0.445), 'about': "the stool's seat top"},
    'stand': {'pos': (0.0, -0.2, 0.0), 'yaw': 0.0, 'about': 'standing behind the bench, facing -y'},
}
# its cameras: (position, aim, lens mm on a 36 mm sensor)
CAMS = {
    'wide': ((0.0, -4.4, 1.5), (0.0, 0.0, 1.1), 28.0),
    'bench_right': ((0.9, -1.9, 1.35), (0.0, -0.45, 1.1), 45.0),
    'bench_left': ((-0.8, -2.3, 1.45), (0.0, -0.3, 1.15), 40.0),
    'corner': ((-0.1, -3.4, 1.3), (-0.8, 0.6, 0.95), 28.0),
    'stool': ((1.3, 0.3, 1.0), (-1.2, 0.6, 0.95), 40.0),
    'bench_close': ((0.62, -1.42, 1.08), (0.30, -0.95, 0.80), 40.0),
    'door': ((0.85, 0.85, 1.25), (1.208, 2.75, 1.08), 35.0),
    'window_plate': ((-1.25, 0.95, 1.45), (-1.3, 2.75, 1.5), 32.0),
}
# its render settings (look.eevee): the rooms' own (look.FILM_RENDER)
RENDER = {'samples': 16}
# its look's options and their defaults (make.py --tube 14 ...)
LOOK = {'tube': 14.0, 'watts': 150.0, 'wallfill': 0.05}


def build(ctx=None, **kw):
    """the made room appended into the scene (eidoblend.sets.same_seed.room.append) -> room.Room"""
    from ..room import append
    return append(NAME, ctx=ctx, **kw)


def __getattr__(name):
    if name in MODULES:
        return importlib.import_module(f'{__name__}.{name}')
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
