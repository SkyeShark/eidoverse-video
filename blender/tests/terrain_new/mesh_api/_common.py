"""What the mesh and API package's Lauterbrunnen scripts share.

    from _common import EYE, lauterbrunnen
    recipe, skipped = lauterbrunnen()     # real_place as a recipe dict, with MESH_API_SKIP_STAGES switched off
    t = make_terrain(recipe, params={'dem': 'lauterbrunnen'}, focus=EYE, ...)

MESH_API_SKIP_STAGES (comma-separated op names, e.g. 'breakup,hydraulic') sets those stages' `enabled` to False, which
the level runner honours: a way to run this package's checks while another package's stage is mid-change. The
results record which stages were off.
"""
import os

from eidoblend.terrain import recipes

EYE = (479.15, 1639.04)          # the Lauterbrunnen reference's eye spot (reference/renders/lauterbrunnen_views.json)


def lauterbrunnen():
    """(real_place's recipe dict with the MESH_API_SKIP_STAGES stages switched off, the ops switched off)."""
    d = recipes.get('real_place').to_dict()
    skip = sorted({s.strip() for s in os.environ.get('MESH_API_SKIP_STAGES', '').split(',') if s.strip()})
    for st in d['stages']:
        if st['op'] in skip:
            st['params'] = dict(st['params'], enabled=False)
    return d, skip
