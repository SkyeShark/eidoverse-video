"""The judge's generic and dune numbers for sweep_box.py's fields against namib_star_dunes (plain Python, numpy): each
box (row 0 south) goes through the judge's own match (judge/match.py: box-averaged to the reference's pixel and, the
reference being 30 m radar data, its source chain) over the reference's extent, cropped about the centre when the box
is smaller, then judge/generic.numbers, judge/family.dunes and the calibrated bands (judge/bands.py). A quick rank of
growth variants on the numbers before a full judge run in Blender. A dune_lab.py dump is judged on its level at the
reference's extent (the main level), after the refinement. A3 is the 3-fold harmonic of the slopes' aspects: three
straight arms at fixed angles push it up (the Namib's is 0.06).

    python judge_box.py <box or lab dir> [label ...]      -> a table on stdout and <dir>/judged.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'core'))
sys.path.insert(0, TN)
import plain_import  # noqa: E402
plain_import.install()

import numpy as np  # noqa: E402
from judge import bands as B  # noqa: E402
from judge import family as F  # noqa: E402
from judge import generic as GN  # noqa: E402
from judge import match as MT  # noqa: E402
from judge import refs  # noqa: E402

KEYS = ('relief_m', 'hypsometric_integral', 'slope_p50', 'slope_p90', 'slope_p99', 'frac_slope_lt5',
        'spectrum_slope', 'anisotropy_8')


def main():
    d = sys.argv[1]
    labels = sys.argv[2:] or sorted(os.path.splitext(f)[0] for f in os.listdir(d) if f.endswith('.npz'))
    ref = refs.load('namib_star_dunes')
    rnum = GN.numbers(np.asarray(ref.h, np.float64), ref.pixel)
    rfam = F.dunes(np.asarray(ref.h, np.float64), ref.pixel)
    cal = dict(B.load().get('calibration', {}), **B.load().get('references', {}).get(ref.name, {}).get('calibration',
                                                                                                      {}))
    out = {}
    from eidoblend.terrain.core import metrics as M

    def a3(h, cell):
        """The 3-fold aspect harmonic: how much the slopes face three directions (a regime of three winds builds
        it; the Namib's 0.06)."""
        return M.aspect_harmonics(h, cell, orders=(3,))[3]
    print(f'{"variant":28s} ' + ' '.join(f'{k[:10]:>10s}' for k in KEYS) + '   spacing  lee     A3  fails')
    print(f'{"namib (ref)":28s} ' + ' '.join(f'{rnum[k]:10.3g}' for k in KEYS)
          + f'   {rfam["dune_spacing_m"]:7.0f}  {rfam["lee_aspect_peaks"]:3d}  {a3(np.asarray(ref.h, np.float64), ref.pixel):5.3f}')
    for label in labels:
        z = np.load(os.path.join(d, label + '.npz'))
        if 'h' in z.files:                                         # a sweep_box.py field
            h, cell = np.asarray(z['h'], np.float64), float(z['cell'])
        else:                                                      # a dune_lab.py dump: its main level (8 km)
            i = min((k for k in range(16) if f'win_{k}' in z.files and abs(z[f'win_{k}'][2] * z[f'win_{k}'][3]
                                                                         - ref.extent) < 1.0), default=None)
            if i is None:
                print(f'{label}: no level at the reference extent')
                continue
            h, cell = np.asarray(z[f'h_{i}'], np.float64), float(z[f'win_{i}'][2])
        m = MT.match(h, cell, ref)
        g = GN.numbers(m.gen, m.pixel)
        gf = F.dunes(m.gen, m.pixel)
        rows = B.generic_rows(g, rnum, True, cal) + B.family_rows('dunes', gf, rfam, cal)
        fails = [r['metric'] for r in rows if r.get('passed') is False]
        A3 = a3(m.gen, m.pixel)
        out[label] = dict(numbers={k: g[k] for k in KEYS}, family=gf, fails=fails, A3=A3)
        print(f'{label:28s} ' + ' '.join(f'{g[k]:10.3g}' for k in KEYS)
              + f'   {gf["dune_spacing_m"]:7.0f}  {gf["lee_aspect_peaks"]:3d}  {A3:5.3f}  {",".join(fails)}')
    with open(os.path.join(d, 'judged.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, default=float)


if __name__ == '__main__':
    main()
