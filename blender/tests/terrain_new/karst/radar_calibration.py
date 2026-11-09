"""How much a 30 m radar reference (Copernicus GLO-30) softens steep walls, measured, for the judge's source chain.

The judge passes a generated field through the radar references' documented chain (box to 30 m, cubic up, Gaussian
0.6 native px: judge/match.py) before comparing slopes. This script checks that chain on the one radar reference
whose walls are known: the Cliffs of Moher are vertical, 120-214 m high. Through the documented chain a vertical
200 m cliff keeps a 76 degree maximum slope; Copernicus Moher's own data tops out at 70.9 degrees (p99.9 63.5): the
radar's effective resolution is coarser than its posting, and an extra Gaussian of about 20 m reproduces it. With
that extra smoothing the tower_karst field's numbers are recomputed beside the judge's, so the lead can see which
of guilin_karst's bands measure the landform and which measure the radar.

    python blender/tests/terrain_new/karst/radar_calibration.py       # writes out/karst/radar_calibration.json
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
for p in (os.path.normpath(os.path.join(TN, '..', '..')), TN, HERE, os.path.join(TN, 'reference')):
    sys.path.insert(0, p)

import karst_numbers as KN  # noqa: E402
import landform_refs as R  # noqa: E402
from eidoblend.terrain.core import metrics as M  # noqa: E402
from eidoblend.terrain.solvers import karst as K  # noqa: E402


def spectrum_slope(h, cell, extent):
    wl, P = M.radial_spectrum(h, cell)
    return float(M.spectrum_summary(wl, P, cell, extent)[0])


def main():
    out = {}
    hm, mm = R.load('cliffs_of_moher')
    sm = R.slope_deg(hm, mm['pixel_size_m'])
    out['copernicus_moher'] = dict(max_slope_deg=float(sm.max()), p999_slope_deg=float(np.percentile(sm, 99.9)),
                                   p99_slope_deg=float(np.percentile(sm, 99)), note='vertical cliffs 120-214 m')
    cliff = {}
    n, cell = 1000, 6.0
    x = (np.arange(n) + 0.5) * cell
    for H in (150.0, 200.0):
        tile = np.tile(np.where(x < 3000.0, H, 0.0), (n, 1))
        base = KN.as_copernicus(tile, cell, out_cell=cell)
        for extra in (0.0, 10.0, 20.0, 30.0):
            f = KN.gaussian_blur(base, extra / cell) if extra else base
            cliff[f'{H:.0f}m_extra{extra:.0f}m'] = float(KN.slope_deg(f, cell)[100:-100, 100:-100].max())
    out['vertical_cliff_max_slope_through_chain'] = cliff
    href, _ = R.load('guilin_karst')
    sr = KN.slope_deg(href, 8.0)
    out['guilin_reference'] = dict(slope_p50_p90_p99=[float(np.percentile(sr, q)) for q in (50, 90, 99)],
                                   spectrum_slope=spectrum_slope(href.astype(np.float64), 8.0, 8000.0))
    for seed in (7, 11):
        plan = K.plan_karst(seed, (-16000.0, -16000.0, 32000.0), {}, via=(0.0, 0.0), main=(-4000.0, -4000.0, 8000.0))
        h = K.evaluate(plan, -4000.0, -4000.0, 8.0, 1000)['h'].astype(np.float64)
        row = {}
        base = KN.as_copernicus(h, 8.0)
        for extra in (0.0, 20.0):
            f = KN.gaussian_blur(base, extra / 8.0) if extra else base
            s = KN.slope_deg(f, 8.0)
            row[f'chain_plus_{extra:.0f}m'] = dict(slope_p50_p90_p99=[float(np.percentile(s, q)) for q in (50, 90, 99)],
                                                   spectrum_slope=spectrum_slope(f, 8.0, 8000.0))
        out[f'tower_karst_seed{seed}'] = row
    path = os.path.join(TN, 'out', 'karst', 'radar_calibration.json')
    with open(path, 'w') as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
