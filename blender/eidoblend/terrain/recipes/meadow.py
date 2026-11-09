"""meadow: small-scale gentle ground with hummocks and rills (design section 5), for the meadow films that used the old
noise make_terrain. No elevation reference exists at this scale: it is judged by slope p99 < 15 degrees, no pits,
and the look with grass from the old meadow probe's framing.

    t = make_terrain('meadow', seed=7, flatten=[{'at': (0, 0), 'radius': 8, 'falloff': 8}])   # the probe's clearing

rolling_hills' process at 80-400 m: a plateau a few metres high carved by the fluvial backbone at a valley spacing of
tens of metres (swales and low rises), then the detail package's hydraulic rills on the finest level, then soil
hummocks (frost mounds, tussock bases: 1-3 m across, a hand or two high). A level clearing is the API's flatten.
"""
from __future__ import annotations

import numpy as np

from ..core.recipe import Knob, Recipe, Stage


def _start(p):
    p.stage('uplift')['start_m'] = 1.3 * float(p['relief_m'])


def _detail(p):
    for s in p.stages('hydraulic'):
        s['enabled'] = bool(p['detail'])


def op_hummocks(fields, level, params, seed=0):
    """Stage 'hummocks': soil microrelief added to h (loose soil: bed unchanged): low mounds and hollows about
    amplitude_m high and deep, spacing_m apart (world-space noise, so every level that runs it agrees), fading out
    on ground steeper than 18 degrees. (Clipped positive bumps at 2.2 m read as gravel from above and reached 42
    degrees: soil hummocks are gentle swells.)"""
    from ..solvers import fluvial as FL
    amp = float(params.get('amplitude_m', 0.08))
    sp = float(params.get('spacing_m', 4.0))
    if sp < 6.0 * level.cell or amp <= 0:
        return fields
    n = FL._field({'kind': 'fbm', 'wavelength_m': sp, 'octaves': 2, 'amp': 3.0}, level, int(seed) + 9001,
                  FL.device())                                            # about N(0, 1) (GPU in Blender)
    gy, gx = np.gradient(np.asarray(fields['h'], np.float64), level.cell)
    steep = np.clip((np.degrees(np.arctan(np.hypot(gx, gy))) - 12.0) / 6.0, 0.0, 1.0)
    fields['h'] = (np.asarray(fields['h'], np.float64) + 0.5 * amp * n * (1.0 - steep)).astype(np.float32)
    return fields


FLUVIAL = dict(K=1e-3, valley_spacing_m='$valley_spacing_m', threshold_deg=33.0, threshold_noise=0.1,
               threshold_scale_m=40.0, roughness='$roughness', roughness_scales_m=[60.0, 15.0, 4.0],
               deposition=0.3, age_myr='$age_myr', relief_m='$relief_m', gullies=False, breakup=0.0, outcrops=0.0)

MEADOW = Recipe(
    'meadow', 'Small-scale gentle ground: swales, low rises, rills and hummocks (a meadow, 80-400 m)',
    references=[],
    defaults={'size': 160.0, 'context': 4, 'hero_cell': 0.5, 'palette': 'meadow', 'base_elevation_m': 300.0},
    knobs={
        'relief_m': Knob(5.0, 'm', (0.5, 40.0), "the main tile's relief", apply=_start),
        'valley_spacing_m': Knob(40.0, 'm', (8.0, 400.0), "the swales' spacing (the old meadow's rises were 32 m "
                                                         "apart)"),
        'age_myr': Knob(0.03, 'Myr', (0.002, 1.0), 'erosion time on the coarsest level (K t about 30: settled)'),
        'roughness': Knob(0.5, '', (0.0, 1.5), 'erodibility noise at 60, 15 and 4 m: irregular swales'),
        'hummocks_m': Knob(0.08, 'm', (0.0, 0.6), 'soil hummocks\' height (about 4 m apart)'),
        'detail': Knob(True, 'bool', None, "the detail package's hydraulic rills on the finest level",
                       apply=_detail),
    },
    stages=[
        Stage('uplift', {'shape': {'kind': 'plateau', 'centre': [0.0, 0.0], 'radius_m': 280.0, 'edge_m': 100.0,
                                   'texture': 0.25},
                         'U_m_per_yr': 2e-4, 'start_m': 5.0, 'start_roughness': 0.4}, levels='all'),
        Stage('fluvial', FLUVIAL, levels='all'),
        Stage('hydraulic', {}, levels='last'),
        Stage('hummocks', {'amplitude_m': '$hummocks_m', 'spacing_m': 4.0}, levels='last'),
    ],
    doc='rolling_hills at meadow scale (a plateau a few metres high carved into swales and low rises), hydraulic '
        'rills, soil hummocks; pass flatten=[...] for a level clearing.')

RECIPES = [MEADOW]
OPS = {'hummocks': op_hummocks}
