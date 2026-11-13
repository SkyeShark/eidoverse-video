"""Slope histograms of dune fields beside the Namib's and the Great Sand Dunes' (plain Python, numpy): each field goes
through the judge's match to namib_star_dunes first (box-averaged to its pixel through the 30 m radar chain), so the
classes compare like with like. Where a field's steepness sits tells what its dunes lack: the Namib's dunes put 44 %
of the ground at 5-20 degrees (broad concave aprons) and 6 % above 25.

    python slope_hist.py <npz> [<npz> ...]      (sweep_box.py or dune_lab.py dumps: h, cell or h_<i>, win_<i>)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'core'))
sys.path.insert(0, TN)
import plain_import  # noqa: E402
plain_import.install()

import numpy as np  # noqa: E402
from judge import match as MT  # noqa: E402
from judge import refs  # noqa: E402
from eidoblend.terrain.core import grid  # noqa: E402

BINS = [0, 2, 5, 10, 15, 20, 25, 28, 31, 35, 90]


def hist(h, cell):
    c, _ = np.histogram(grid.slope_deg(h, cell), BINS)
    return c / c.sum()


def field(path):
    z = np.load(path)
    if 'h' in z.files:
        return np.asarray(z['h'], np.float64), float(z['cell'])
    mains = [k for k in z.files if k.startswith('win_')]
    for k in sorted(mains):                                   # dune_lab: the main level is the 8 km window
        w = z[k]
        if abs(w[2] * w[3] - 8000.0) < 1.0:
            i = k.split('_')[1]
            return np.asarray(z[f'h_{i}'], np.float64), float(w[2])
    raise KeyError(f'{path}: no h and no 8 km level')


def main():
    ref = refs.load('namib_star_dunes')
    print(f'{"field":24s}' + ' '.join(f'{a}-{b}'.rjust(6) for a, b in zip(BINS[:-1], BINS[1:])))
    print(f'{"namib (real)":24s}' + ' '.join(f'{v:6.3f}' for v in hist(np.asarray(ref.h, np.float64), ref.pixel)))
    g = refs.load('great_sand_dunes')
    print(f'{"great sand dunes (real)":24s}' + ' '.join(f'{v:6.3f}' for v in hist(np.asarray(g.h, np.float64), g.pixel)))
    for p in sys.argv[1:]:
        h, cell = field(p)
        m = MT.match(h, cell, ref)
        print(f'{os.path.basename(p)[:24]:24s}' + ' '.join(f'{v:6.3f}' for v in hist(m.gen, m.pixel)))


if __name__ == '__main__':
    main()
