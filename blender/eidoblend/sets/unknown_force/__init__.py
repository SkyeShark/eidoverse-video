"""eidoblend.sets.unknown_force: the sets of the UNKNOWN FORCE music video (2026-10), the Blender 5.2 EEVEE edition of
eidoverse/sets/unknown_force/. Every camp of the AI argument gets its own room, painted for the futurist post pass, and
the claudesona walks through them all.

A lazy registry: importing this package imports no set. A set's module (and its libraries) load on first use, so
building the city never pulls in the race, and a set still being ported never breaks the others.

    from eidoblend.sets import unknown_force as UF
    UF.names()                                # every set, in song order
    UF.available()                            # the ones whose module is on disk
    city = UF.build('city')                   # UF.module('city').build(...)
    C = UF.module('city')                     # the module itself (C.dive_cam, C.key_dive ...)
    UF.city                                   # the same, as an attribute
    UF.SETS['bin']['song']                    # (222.8, 243.2): the song seconds it was made for

The film's set contract stays, in Blender terms: build(...) returns a dict with group (the root Empty), parts,
update(t, state[, frame]) (frame keys what it sets), dispose() and cams (set-local pos / target / vertical fov,
Blender axes). The beats, cues and camera plans were written for that film at 92.90 BPM; every update key is free, so
drive the sets on your own clock.
"""
from __future__ import annotations

import importlib
import os

BPM = 92.90
_HERE = os.path.dirname(os.path.abspath(__file__))

# set -> its module, its doc (eidoverse/sets/unknown_force/), the song section and seconds it was made for, the form
# of its focal point (where the post's sun cones radiate from) and the shared libraries it stands on
SETS = {
    'city': {'module': 'city', 'doc': 'CITY_HOLE.md', 'section': 'intro', 'song': (0.0, 40.8),
             'focal': "city.dive_focal(t) during the dive (Blender axes, also parts['set_focal'])", 'libs': ('citykit',),
             'what': "a night megacity built round a sunken well; the intro's Crali dive"},
    'quiet_room': {'module': 'quiet_room', 'doc': 'INTERIORS.md', 'section': 'verse 1', 'song': (40.8, 60.0),
                   'focal': 'an object in the group (the altar board)', 'libs': ('quiet_room_art', 'interiors_lib'),
                   'what': 'pews, a whiteboard altar, a crate that ships'},
    'hole': {'module': 'hole', 'doc': 'CITY_HOLE.md#the-hole-holejs', 'section': 'choruses, outro', 'song': None,
             'focal': 'the singer herself (her chest)', 'libs': ('citykit',),
             'what': 'the hole in the middle: the chorus stage (built by city, or alone)'},
    'corridor': {'module': 'corridor', 'doc': 'CORRIDOR_NEWS.md', 'section': 'verse 2', 'song': (120.7, 140.2),
                 'focal': 'a set-local point (the door)', 'libs': ('cn_lib',),
                 'what': 'the gold corridor: SUPREME INTELLIGENCE, a poll board, a cap'},
    'race': {'module': 'race', 'doc': 'RACE.md', 'section': 'verses 3-4', 'song': (142.5, 162.8),
             'focal': 'focal(cam_name): a set-local point per shot', 'libs': (),
             'what': "an elevated highway, two billboards, Marinetti's car in the ditch"},
    'showroom': {'module': 'showroom', 'doc': 'INTERIORS.md#the-showroom-showroomjs', 'section': 'pre-chorus 2',
                 'song': (163.1, 173.7), 'focal': 'an object in the group (her face height on the turntable)',
                 'libs': ('showroom_art', 'interiors_lib'),
                 'what': 'a product launch, a turntable, a toaster with a warning'},
    'news': {'module': 'news', 'doc': 'CORRIDOR_NEWS.md#the-evening-news-newsjs-song-20132222-s', 'section': 'verse 5',
             'song': (201.3, 222.2), 'focal': 'a set-local point (the floodlight behind her)', 'libs': ('cn_lib',),
             'what': 'the evening news: a data centre, a fence, pickets, a tag'},
    'bin': {'module': 'bin', 'doc': 'BIN.md', 'section': 'bridge', 'song': (222.8, 243.2),
            'focal': 'focal_point(v): the world position of the lip where she rises', 'libs': ('bin_pages',),
            'what': 'a canyon of thrown-away paper and a giant trash can'},
}
LIBS = ('citykit', 'interiors_lib', 'quiet_room_art', 'showroom_art', 'cn_lib', 'bin_pages')
DOCS_DIR = os.path.normpath(os.path.join(_HERE, '..', '..', '..', '..', 'eidoverse', 'sets', 'unknown_force'))


def names():
    """Every UNKNOWN FORCE set, in song order (the hole first appears after the quiet room)."""
    return list(SETS)


def available():
    """The sets whose module is on disk (checked without importing them)."""
    return [n for n, s in SETS.items() if os.path.isfile(os.path.join(_HERE, s['module'] + '.py'))]


def module(name):
    """A set's module, imported on first use (or one of the shared libraries: citykit, interiors_lib, cn_lib ...)."""
    if name in SETS:
        mod = SETS[name]['module']
    elif name in LIBS:
        mod = name
    else:
        raise KeyError(f'unknown_force: no set {name!r} (sets: {", ".join(SETS)}; libraries: {", ".join(LIBS)})')
    if not os.path.isfile(os.path.join(_HERE, mod + '.py')):
        raise ModuleNotFoundError(f'unknown_force: the {name!r} set is not ported yet ({mod}.py is missing)')
    return importlib.import_module(f'{__name__}.{mod}')


def build(name, *args, **kwargs):
    """Build a set: module(name).build(*args, **kwargs)."""
    return module(name).build(*args, **kwargs)


def doc(name):
    """The path of a set's WebGPU doc (its options, beats and costs), with its section anchor if any."""
    d = SETS[name]['doc']
    path, _, anchor = d.partition('#')
    return os.path.join(DOCS_DIR, path) + (('#' + anchor) if anchor else '')


def __getattr__(attr):
    """UF.city, UF.hole, UF.citykit ...: the modules, lazily."""
    if attr in SETS or attr in LIBS:
        return module(attr)
    raise AttributeError(attr)


def __dir__():
    return sorted(list(globals()) + list(SETS) + list(LIBS))
