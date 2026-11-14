"""The terrains the surface-data tests bake: the five real places and three recipes of the acceptance sheets, each
with a focus so its hero levels exist, made once and kept as a snapshot (Terrain.save) so every later test loads it.

    import _cases as C
    C.CASES['toroweap']                     # dict(recipe, params, size, focus (metres from the recipe's centre), ...)
    t = C.terrain('toroweap')               # Terrain.load(build=False) of its snapshot; raises with the command that
                                            # makes it when the snapshot is missing
    C.snap_path('toroweap')                 # blender/tests/terrain/out/surface_data/snap/toroweap.npz

Snapshots are made by make_snaps.py (a GPU job each, minutes). A snapshot keeps the terrain as it was generated, so
a test is not at the mercy of the shared terrain cache's pruning, nor of another package's solver edit.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))                      # blender/tests/terrain
BLENDER_DIR = os.path.normpath(os.path.join(TN, '..', '..'))         # blender/
OUT = os.path.join(TN, 'out', 'surface_data')
SNAP = os.path.join(OUT, 'snap')
if BLENDER_DIR not in sys.path:
    sys.path.insert(0, BLENDER_DIR)

# focus: metres east and north of the recipe's centre (the review's matched cameras, out/review/views_plan.json, or
# the reference site's eye-level view point, reference/sites.py)
CASES = {
    'toroweap': dict(recipe='real_place', params={'dem': 'grand_canyon_toroweap'}, size=None, focus=(387.1, 356.2),
                     title='Grand Canyon at Toroweap (real DEM)', palette='auto'),
    'lauterbrunnen': dict(recipe='real_place', params={'dem': 'lauterbrunnen'}, size=None, focus=(583.7, 1908.9),
                          title='Lauterbrunnen (real DEM)', palette='auto'),
    'meteor_crater': dict(recipe='real_place', params={'dem': 'meteor_crater'}, size=None, focus=(18.2, 556.6),
                          title='Meteor Crater (real DEM)', palette='auto'),
    'great_sand_dunes': dict(recipe='real_place', params={'dem': 'great_sand_dunes'}, size=None,
                             focus=(1904.0, -1503.9), title='Great Sand Dunes (real DEM)', palette='auto'),
    'badlands_sd': dict(recipe='real_place', params={'dem': 'badlands_sd'}, size=None, focus=(692.2, -1419.3),
                        title='Badlands, South Dakota (real DEM)', palette='auto'),
    'canyon': dict(recipe='canyon', params=None, size=8000.0, focus=(441.4, 972.7), title='canyon recipe',
                   palette='auto'),
    'alpine_valley': dict(recipe='alpine_valley', params=None, size=8000.0, focus=(1337.1, 2540.5),
                          title='alpine_valley recipe', palette='auto'),
    # the review's canyon_road camera: where the fluvial package measured the trunk's catchment falling from
    # 37 km2 on the main level to 1.5 km2 on the finest hero level
    'fluvial_range': dict(recipe='fluvial_range', params=None, size=12000.0, focus=(-2413.9, 2329.1),
                          title='fluvial_range recipe, canyon_road focus', palette='auto'),
}
SHEET_CASES = ('toroweap', 'lauterbrunnen', 'meteor_crater', 'great_sand_dunes', 'badlands_sd', 'canyon',
               'alpine_valley')


def snap_path(name):
    return os.path.join(SNAP, name + '.npz')


def recipe_centre(recipe, params):
    """The recipe's default centre (world metres): a focus is given from it."""
    from eidoblend.terrain import api as A
    R = A._registry.resolve(recipe)
    values, _ = R.resolve(params or None)
    dfl = dict(R.defaults)
    if getattr(R, 'defaults_for', None) is not None:
        dfl.update(R.defaults_for(values))
    c = dfl.get('centre', (0.0, 0.0))
    return float(c[0]), float(c[1])


def generate(name, log=print):
    """Generate a case's terrain (the levels, fields, masks and ring mesh; no Blender object) and save its snapshot.
    Needs Blender's GPU module (the level runner's kernels)."""
    from eidoblend.terrain import api as A
    c = CASES[name]
    c0 = recipe_centre(c['recipe'], c['params'])
    focus = [(c0[0] + c['focus'][0], c0[1] + c['focus'][1])]
    t = A.generate(c['recipe'], size=c['size'], seed=1, params=c['params'], focus=focus, quality='film',
                   cache=True, palette=c['palette'], log=log)
    os.makedirs(SNAP, exist_ok=True)
    t.save(snap_path(name))
    return t


def terrain(name):
    """The case's terrain from its snapshot (no Blender object, no GPU)."""
    from eidoblend.terrain import api as A
    p = snap_path(name)
    if not os.path.exists(p):
        raise FileNotFoundError(f'no snapshot of {name!r} at {p}: make it with\n    bash run_blender.sh '
                                f'blender/tests/terrain/surface_data/make_snaps.py --case {name}')
    return A.Terrain.load(p, build=False)
