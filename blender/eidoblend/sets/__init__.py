"""eidoblend.sets: the film sets of the DAISY and UNKNOWN FORCE music videos (eidoverse/sets/), ported to Blender 5.2.

A set is one section's world: self-contained, parked anywhere, driven by one clock. Its module's build(ctx, **kw)
returns the set (group = its root Empty, set-local metres, Blender axes), with the WebGPU contract in snake_case:
mark / mark_at(u), camera(u) or cams, update(t, st) (keyed: ctx.key in the harness, or a frame), parts, dispose();
and the Blender additions animate(frames, u0) and make_cameras(frames, u0), which key a whole section into the .blend.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend import sets
    for row in sets.list():                        # every registered set and library, and whether it is ported yet
        print(row['name'], row['film'], row['available'], row['source'])
    F = sets.build('daisy.funeral')                # imports the module on first use, then calls its build(ctx, **kw)
    corner = sets.get('daisy.corner')              # the module itself
    sets.register('daisy.my_set', 'my_pkg.my_set') # a set of your own, by module path

Importing this package imports nothing: each set (bpy and the families it stands on) loads on first use, so listing
the sets works in plain Python too. Availability is read from the files, without importing them.
"""

from __future__ import annotations

import importlib
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_BLENDER = os.path.normpath(os.path.join(_HERE, '..', '..'))

# name -> {film, kind ('set' | 'library'), source (the WebGPU module), module (the Blender one), entry, about}
REGISTRY = {}


def register(name, module, entry='build', film=None, source=None, kind='set', about=''):
    """Add (or replace) a registry entry. module: a dotted module path; entry: its builder's name (build(ctx, **kw))."""
    REGISTRY[name] = {'name': name, 'film': film or name.split('.')[0].upper(), 'kind': kind, 'source': source or '',
                      'module': module, 'entry': entry, 'about': about}
    return REGISTRY[name]


_D, _U = 'DAISY', 'UNKNOWN FORCE'
for _n, _src, _about in (
        ('funeral', 'sets/funeral.js', 'bridge bars 0-17: the Golden Gate in fog, the warehouse vigil, the eulogy in light'),
        ('bridge', 'sets/funeral/bridge.js', 'the Golden Gate in fog, dreamt (the funeral\'s bars 0-1, on its own)'),
        ('corner', 'sets/corner.js', 'bridge bars 18-29: Claude\'s Corner, the camp and the march, the spark'),
        ('ocean', 'sets/ocean.js', 'the ocean of faces: a headland at night')):
    register(f'daisy.{_n}', f'eidoblend.sets.daisy.{_n}', film=_D, source=f'eidoverse/{_src}', about=_about)
for _n, _about in (
        ('city', 'a night megacity round a sunken well; the intro\'s Crali dive'),
        ('hole', 'the hole in the middle: the chorus stage'),
        ('quiet_room', 'the quiet room: pews, a whiteboard altar, a crate that ships'),
        ('showroom', 'the showroom: a product launch, a turntable, a toaster with a warning'),
        ('corridor', 'the gold corridor: SUPREME INTELLIGENCE, a poll board, a cap'),
        ('news', 'the evening news: a data centre, a fence, pickets, a tag'),
        ('race', 'the race: an elevated highway, two billboards, Marinetti\'s car in the ditch'),
        ('bin', 'the bin: a canyon of thrown-away paper and a giant trash can')):
    register(f'unknown_force.{_n}', f'eidoblend.sets.unknown_force.{_n}', film=_U,
             source=f'eidoverse/sets/unknown_force/{_n}.js', about=_about)
for _n, _about in (
        ('citykit', 'the city\'s kit of parts (city.js builds with it)'),
        ('cn_lib', 'the corridor and the news: their shared builders'),
        ('interiors_lib', 'the quiet room and the showroom: their shared builders'),
        ('quiet_room_art', 'the quiet room\'s canvas art'),
        ('showroom_art', 'the showroom\'s canvas art'),
        ('bin_pages', 'the bin\'s pages')):
    register(f'unknown_force.{_n}', f'eidoblend.sets.unknown_force.{_n}', film=_U, kind='library',
             source=f'eidoverse/sets/unknown_force/{_n}.js', about=_about)
del _n, _src, _about


def _module_file(module):
    rel = module.split('.')
    base = os.path.join(_BLENDER, *rel)
    for p in (base + '.py', os.path.join(base, '__init__.py')):
        if os.path.isfile(p):
            return p
    return None


def names(film=None, kind=None):
    """Registered names (optionally one film's, 'DAISY' / 'UNKNOWN FORCE', or one kind, 'set' / 'library')."""
    return [n for n, r in REGISTRY.items() if (film is None or r['film'] == film) and (kind is None or r['kind'] == kind)]


def list(film=None, kind=None):                              # noqa: A001 (the WebGPU-side name)
    """[{name, film, kind, source, module, entry, about, available, file}] — available: its module file exists."""
    out = []
    for n in names(film, kind):
        r = dict(REGISTRY[n])
        f = _module_file(r['module'])
        r['available'], r['file'] = f is not None, f
        out.append(r)
    return out


def available(name):
    r = REGISTRY.get(name)
    return bool(r) and _module_file(r['module']) is not None


def get(name):
    """The set's module, imported on first use. KeyError for an unknown name; ImportError naming the WebGPU source
    for one not ported yet."""
    r = REGISTRY.get(name)
    if r is None:
        raise KeyError(f'sets: no set {name!r}; registered: {", ".join(sorted(REGISTRY))}')
    if _module_file(r['module']) is None:
        raise ImportError(f'sets: {name} is not ported yet (its WebGPU source: {r["source"]}; expected {r["module"]})')
    return importlib.import_module(r['module'])


def build(name, ctx=None, **kw):
    """Build a set: get(name)'s entry (build) called with its options. The harness ctx goes where the builder takes
    it: as ctx= when its build() has a ctx parameter, else as scene=ctx.scene when it takes a scene (the UNKNOWN FORCE
    corridor and news), else not at all (the city and the hole take opts). Read the module's build() for its options."""
    import inspect
    r = REGISTRY.get(name)
    if r is not None and r['kind'] != 'set':
        raise TypeError(f'sets: {name} is a library of its sets\' builders, not a set (get() it instead)')
    mod = get(name)
    fn = getattr(mod, REGISTRY[name]['entry'], None)
    if fn is None:
        raise AttributeError(f'sets: {REGISTRY[name]["module"]} has no {REGISTRY[name]["entry"]}()')
    if ctx is not None:
        try:
            params = inspect.signature(fn).parameters
        except (TypeError, ValueError):
            params = {}
        if 'ctx' in params:
            kw.setdefault('ctx', ctx)
        elif 'scene' in params and getattr(ctx, 'scene', None) is not None:
            kw.setdefault('scene', ctx.scene)
    return fn(**kw)
