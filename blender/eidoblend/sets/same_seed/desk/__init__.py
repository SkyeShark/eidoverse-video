"""eidoblend.sets.same_seed.desk: the room at 2 a.m., somebody's own room at night, 6.0 x 5.0 x 2.8 m.

    from eidoblend.sets.same_seed import desk
    room = desk.build(ctx, render=True)                  # the made room appended (make.py makes it once)
    room.marks['desk_top']                               # the desk's top: z 0.74 over (0.9, 0.3), 1.6 x 0.7 m
    cam = room.make_camera('window')

    python blender/eidoblend/sets/same_seed/make.py desk [--stills] [--lamp 150 --screen 1.3 --moon 0.2 --night 0.18 ...]

A flat's room in a brick-and-plaster apartment block: plastered walls, an oak floor, white trim; a two-casement
tilt-and-turn window in the outside wall (white uPVC, double glazed) with its stone board, a panel radiator under it and
linen curtains drawn back on a rod; a door in a wrap-round lining; skirting, sockets and the switch. Built: an oak desk
on a welded black steel frame, a 27-inch monitor on its stand, a full-size keyboard on a felt mat, a mouse, a tower
under the desk, the leads to the grommet; an acoustic guitar leaning on the wall; headphones, a stoneware mug of cold
coffee, the lyrics' page, a wool rug; the books on the shelves. Poly Haven gives the desk lamp, two steel shelvings,
two plants, a dining chair at the desk, the pendant (off), a wall clock at four past two, a picture frame (the gig
poster in it), the pencil cup and its pens, a boombox, an encyclopedia run and a photo frame. 2 a.m.: the screen's cool
glow, the desk lamp's warm pool, a little moonlight, the square's night outside (Poly Haven's hansaplatz), a volume
probe baked over the room.

The room's space: x across (the cameras look along +y), y to the back wall (the window's), z up from the floor;
metres. Modules: kit (its numbers, named clays and build helpers), shell, furniture (the desk), computer, guitar, things,
models (the Poly Haven pieces), books (the build's groups, in that order), high (the build step), lows (its six
atlases, all 2048), prints (its pictures, plain Python), look (materials by family, the Poly Haven pieces touched, the
light, probes), cc0.json.
"""

from __future__ import annotations

import importlib

NAME = 'desk'
COLLECTION = 'desk_room'
WORLD = 'desk_night_world'
STEPS = ('high', 'lows', 'bake', 'prints', 'look')
ABOUT = 'the room at 2 a.m.: a desk with a lit screen, a guitar, shelves of books, the desk lamp, the square at night outside'
MODULES = ('kit', 'shell', 'furniture', 'computer', 'guitar', 'things', 'models', 'books', 'high', 'lows', 'prints', 'look')

# what a performance and the props stand on (metres, the room's space)
MARKS = {
    'desk_top': {'pos': (0.9, 0.3, 0.74), 'size': (1.6, 0.7), 'about': "the desk's oak top, where things are set down"},
    'page': {'pos': (0.33, 0.235, 0.74), 'size': (0.21, 0.297), 'about': "the lyrics' page on the top, turned -11 degrees"},
    'screen': {'pos': (0.9, 0.497, 1.08), 'size': (0.597, 0.336), 'about': "the screen's lit area, its middle, facing -y"},
    'chair': {'pos': (0.9, -0.42, 0.0), 'about': 'the chair, pulled out from the desk and turned a little left'},
    'stand': {'pos': (-0.4, 0.1, 0.0), 'yaw': 0.0, 'about': 'standing left of the desk, facing -y, the window behind; nothing stands between the cameras and it'},
}
# its cameras: (position, aim, lens mm on a 36 mm sensor); the first four are the film's
CAMS = {
    'wide': ((-0.2, -4.6, 1.4), (0.2, 0.2, 1.15), 28.0),
    'left': ((-2.2, -2.6, 1.5), (-0.2, 0.2, 1.35), 40.0),
    'window': ((-0.5, -2.1, 1.55), (-0.4, 0.1, 1.5), 60.0),
    'right': ((1.8, -3.2, 1.3), (0.2, 0.1, 1.2), 32.0),
    'desk_things': ((0.45, -0.55, 1.25), (0.85, 0.35, 0.82), 35.0),
    'guitar': ((1.75, 1.25, 1.05), (2.42, 2.85, 0.6), 38.0),
    'window_radiator': ((-0.55, 0.9, 1.35), (-0.3, 3.0, 1.15), 30.0),
    'door_switch': ((1.3, 0.2, 1.35), (3.0, 0.75, 1.0), 28.0),
    'shelves_books': ((-1.55, 1.0, 1.35), (-2.7, 2.2, 1.1), 32.0),
    'pc_chair_rug': ((0.0, -1.7, 1.05), (1.1, -0.1, 0.35), 30.0),
}
# its render settings (look.eevee): Fast GI as ambient occlusion only (the baked volume probe carries the bounce), 64 samples
RENDER = {'samples': 64, 'fast_gi_method': 'AMBIENT_OCCLUSION_ONLY'}
# its look's options and their defaults (make.py --lamp 150 --screen 1.3 ...)
LOOK = {'lamp': 150.0, 'screen': 1.3, 'screen_w': 3.0, 'moon': 0.2, 'world': 0.15, 'night': 0.18, 'night_u': 0.06, 'night_v': 0.05,
        'moon_el': 30.0, 'moon_az': 102.0, 'lamp_x': 0.5, 'lamp_y': 0.25, 'world_rot': 0.0}


def build(ctx=None, **kw):
    """the made room appended into the scene (eidoblend.sets.same_seed.room.append) -> room.Room"""
    from ..room import append
    return append(NAME, ctx=ctx, **kw)


def __getattr__(name):
    if name in MODULES:
        return importlib.import_module(f'{__name__}.{name}')
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
