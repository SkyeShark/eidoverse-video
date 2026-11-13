"""dunes: dunes made by the wind regime and the sand supply (design sections 4.6 and 5): star dunes by default;
barchan, transverse or linear dunes with kind=.

    t = make_terrain('dunes')                                         # star dunes, 8 km, like the Namib's
    t = make_terrain('dunes', params={'kind': 'barchan'})             # crescents on a bare plain, 3 km
    t = make_terrain('dunes', params={'kind': 'transverse', 'wind_rotate_deg': 30})
    t = make_terrain('dunes', params={'kind': 'star', 'spacing_m': 600, 'sand_m': 40})

Which dune you get is the wind and the sand, not a shape (Rubin & Hunter 1987, Courrech du Pont et al. 2014, Zhang et
al. 2012): one wind and thin sand make barchans; one wind and thick sand transverse ridges; two winds more than 90
degrees apart linear ridges along their resultant; three winds of similar weight star dunes. The stage is
solvers/aeolian.py's dune_field (Werner's slab model on the GPU, design 4.6), run on every level: the field grows
once, periodic, on the coarsest level that resolves the spacing (the bed: a gently rolling gravel plain; the sand: the
kind's thickness, thinner and thicker over kilometres (sand_patchiness), seeded at the target spacing), until the
dunes stand at the target height; coarser levels average it, finer levels sharpen its crests and slip faces at their
own cell (star dunes: under the last season's wind alone, so the big dunes keep the forms the whole regime gave
them). Ripples belong in the material (the dunes palette).

Winds are compass degrees the wind blows FROM (225 is a south-westerly: the sand moves north-east, the slip faces
face north-east), with weights for how long each blows. The kinds' regimes:
    star        28, 148 and 268 degrees, weights 1, 0.75, 0.55   sand 45 m, spacing 1.4 km, 8 km  (Namib, GSD)
                (each a season blowing as gusts that wander 30 degrees about its direction, every wind turned
                by the regional relief in its own smooth pattern; a speed-up that grows toward the crest, so the
                dunes' flanks stretch into broad aprons; masses of sand with long bare pans between them)
    barchan     225 degrees                                     sand 2.5 m, spacing 250 m, 3 km
    transverse  225 degrees                                     sand 5 m, spacing 120 m, 3 km    (White Sands)
    linear      120 and 240 degrees, equal (resultant from 180) sand 45 m, spacing 2 km, 10 km  (Namib linear)
The star defaults are calibrated on the Namib at Sossusvlei (solvers/aeolian.py KINDS['star'] says what each choice
fixed: wandering gusts and the steered winds against three straight arms at a fixed 120 degrees, the patchy capped
supply drawn out east-west against an even sheet left as straight-edged plates, the speed-up growing toward the
crest against straight-sided pyramids at repose, the feathered smoothed sheet and the time-averaged read-out
against pitted sand, the last season on the finer levels for a sharp brink above a fresh slip face).
The design's starting point (0/120/240 equal, 120 m of sand at 900 m) piles every dune into a pyramid at repose. For
the Great Sand Dunes' reversing ridges in a near-unbroken sand sea: params={'winds': [[282, 1.0], [102, 0.7],
[192, 0.5]], 'sand_m': 40, 'spacing_m': 900, 'bed_relief_m': 30, 'sand_patchiness': 0.5} (12 of the judge's 14
bands; its dunes stand a little steeper than the Great Sand Dunes', slope p50 15 and p90 27.6 degrees).
"""
from __future__ import annotations

from ..core.recipe import Knob, Recipe, Stage

SIZES = {'star': 8000.0, 'barchan': 3000.0, 'transverse': 3000.0, 'linear': 10000.0}


def _prepare(values, plan):
    """The level stack, for the dune field's growth level (solvers/aeolian.py)."""
    from ..solvers import aeolian
    aeolian.prepare(values, plan)


def defaults_for(values):
    """The main tile's size follows the kind (the extent of the reference it is judged against)."""
    return {'size': SIZES.get(values.get('kind') or 'star', 8000.0)}


DUNES = Recipe(
    'dunes', 'Dunes from the wind regime and the sand supply: star, barchan, transverse or linear',
    references=['namib_star_dunes', 'great_sand_dunes', 'white_sands', 'namib_linear_dunes'],
    defaults={'size': 8000.0, 'context': 4, 'hero_cell': 0.5, 'palette': 'dunes'},
    knobs={
        'kind': Knob('star', 'choice', ('star', 'barchan', 'transverse', 'linear'),
                     'the wind regime and sand supply: star (three winds), barchan (one wind, thin sand), '
                     'transverse (one wind, thick sand), linear (two winds 120 degrees apart)'),
        'winds': Knob(None, 'list', None,
                      '[[from_deg, weight], ...] compass degrees the wind blows FROM and how long each blows; None: '
                      "the kind's regime"),
        'wind_rotate_deg': Knob(0.0, 'deg', (-360.0, 360.0), 'turn the whole wind regime clockwise'),
        'sand_m': Knob(0.0, 'm', (0.0, 500.0),
                       "mean sand thickness; 0: the kind's (star 45, linear 45, transverse 5, barchan 2.5)"),
        'spacing_m': Knob(0.0, 'm', (0.0, 20000.0),
                          "target dune spacing; 0: the kind's (star 1400, linear 2000, barchan 250, transverse 120)"),
        'bed_relief_m': Knob(0.0, 'm', (0.0, 200.0),
                             "the rolling gravel plain under the sand: standard deviation of its height; 0: the "
                             "kind's (star 20, linear 6, transverse and barchan 1.5)"),
        'sand_patchiness': Knob(0.0, '', (0.0, 1.5),
                                "how unevenly the sand lies over kilometres (the start's supply variation); 0: the "
                                "kind's (star 0.6: dune masses with long bare pans between them, as at Sossusvlei; "
                                "0.35, the others': an even sand sea)"),
    },
    stages=[
        Stage('dune_field', {'kind': '$kind', 'winds': '$winds', 'wind_rotate_deg': '$wind_rotate_deg',
                             'sand_m': '$sand_m', 'spacing_m': '$spacing_m', 'bed_m': '$bed_relief_m',
                             'patchiness': '$sand_patchiness'},
              levels='all'),
    ],
    doc='Werner\'s slab model on the GPU (solvers/aeolian.py): grown once, periodic, on the coarsest level that '
        'resolves the dune spacing; finer levels sharpen it and add the small dunes.')
DUNES.prepare = _prepare
DUNES.defaults_for = defaults_for

RECIPES = [DUNES]
