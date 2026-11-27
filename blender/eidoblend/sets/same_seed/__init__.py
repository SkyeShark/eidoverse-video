"""eidoblend.sets.same_seed: the four rooms of the SAME SEED music video, each a free, reusable set. They were built
in Blender for that film (no WebGPU original): every part a lens comes close to is a proper asset, a high and a low
drawn on one construction with the high baked onto the low on the GPU, under one layer stack per material from CC0
photographic sets, with CC0 Poly Haven models where one fits.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend import sets
    room = sets.build('same_seed.sealed_room', ctx)      # appends the made room (make it once, below)
    room.group.location = (180.0, 0.0, 0.0)             # its root Empty; room.parts, .lights, .probes, .marks, .cams
    cam = room.make_camera('bench_right')
    from eidoblend.sets import same_seed
    same_seed.ROOMS                                     # ('sealed_room', 'kitchen', 'lab', 'desk')

    python blender/eidoblend/sets/same_seed/make.py sealed_room [--stills]    # make a room (plain Python, its steps)

    sealed_room   a sealed room in an old government building: painted block, plated windows, a door with no handle on
                  this side, a welded steel bench, a stool, a camera in the corner, one fluorescent batten
    kitchen       a kitchen at noon: a twin window on a garden, cupboards, a fridge with a child's drawing, the table
                  set with homework, a pot of basil on the sill
    lab           a lab full of light: a laminate bench, a whiteboard, LED panels, radiators, a task chair, and the
                  houseplants (eidoblend.props.houseplants)
    desk          the room at 2 a.m.: a desk lamp's pool, a screen's glow, the moon; a guitar, books, a bed's corner

Each room's package holds its builder (high.py and the modules it builds with), lows.py (its lows, UVs and the bake's
inputs), look.py (its materials, CC0 pieces and light), prints.py where it draws pictures (Pillow), cc0.json (its CC0
IDs, fetched on first use) and in __init__.py its marks (where a body stands, the surfaces things are set on), its
cameras and its render settings. Shared: look (the material layer, the CC0 library, the render settings), bake (the
atlases written for blender/tools/gpu_bake.py), room (a made room appended into a scene), cli (the Blender steps), make
(the chain). Guide: tools-guides/props-and-sets.md, "The SAME SEED rooms".
"""

from __future__ import annotations

import importlib

ROOMS = ('sealed_room', 'kitchen', 'lab', 'desk')
FILM = 'SAME SEED'


def info(name):
    """{'steps', 'about', 'collection'} of a room, read without Blender"""
    m = importlib.import_module(f'{__name__}.{name}')
    return {'steps': m.STEPS, 'about': m.ABOUT, 'collection': m.COLLECTION}


def build(name, ctx=None, **kw):
    """Append a made room into the scene (eidoblend.sets.same_seed.room.append): blend=, scene=, world=True,
    render=False, location=, rotation_z=. -> room.Room"""
    from .room import append
    return append(name, ctx=ctx, **kw)


def __getattr__(name):
    """same_seed.sealed_room, .kitchen, .lab, .desk and the shared modules, imported on first access"""
    if name in ROOMS or name in ('look', 'bake', 'room', 'cli', 'make'):
        return importlib.import_module(f'{__name__}.{name}')
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
