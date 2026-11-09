"""How much the ground crawls when the camera moves (system Python: numpy + OpenCV). Moved from
tests/terrain/shimmer_metric.py with the film material's filtering (design section 3); the arithmetic is unchanged.

    python blender/tests/terrain_new/surfacing/shimmer_metric.py <tag> [<tag> ...] [--dir <folder>]

Reads meadow_<tag>_shimmer_0/1/2.png (test_shimmer.py: the meadow's 'edge' view with the camera turned by 0, 0.5 and
1 pixel), default folder out/surfacing/. Each frame is blurred (Gaussian sigma 1.5 px); the half-pixel frame is
compared with the average of its two neighbours, as a fraction of the real one-pixel change,
    mean |f1 - (f0 + f2) / 2|  /  mean |f2 - f0|
per band of rows: distant (rows 206-250, ~28 m to the horizon), middle (250-330, ~9-28 m) and near (400-540,
~3.5-6 m). Smooth motion scores near 0 (the midpoint frame is the average of its neighbours); texture aliasing that
reshuffles with every sub-pixel offset scores ~1 (it changes the image as much as the motion does). The old film
material, measured 11-07 at 960x540, 16 samples:
    Cubic everywhere   distant 1.00  middle 0.85  near 0.26
    Linear everywhere  distant 0.14  middle 0.11  near 0.08
    Auto (4, 9)        distant 0.14  middle 0.11  near 0.22
"""
import sys
from pathlib import Path

import cv2
import numpy as np

BANDS = {'distant': (206, 250), 'middle': (250, 330), 'near': (400, 540)}
OLD_AUTO = {'distant': 0.14, 'middle': 0.11, 'near': 0.22}


def _load(p):
    a = cv2.imread(str(p), cv2.IMREAD_COLOR)
    if a is None:
        raise FileNotFoundError(p)
    a = a.astype(np.float64) / 255.0
    return cv2.GaussianBlur(a[..., 2] * 0.2126 + a[..., 1] * 0.7152 + a[..., 0] * 0.0722, (0, 0), 1.5)


def metric(folder, tag):
    f = [_load(Path(folder) / ('meadow_%s_shimmer_%d.png' % (tag, k))) for k in range(3)]
    out = {}
    for name, (r0, r1) in BANDS.items():
        s = slice(r0, r1)
        e = np.abs(f[1][s] - 0.5 * (f[0][s] + f[2][s])).mean()
        m = np.abs(f[2][s] - f[0][s]).mean()
        out[name] = e / max(m, 1e-9)
    return out


if __name__ == '__main__':
    args = sys.argv[1:]
    folder = Path(__file__).resolve().parents[1] / 'out' / 'surfacing'
    if '--dir' in args:
        i = args.index('--dir')
        folder = Path(args[i + 1])
        del args[i:i + 2]
    for tag in args:
        r = metric(folder, tag)
        print('%-24s %s' % (tag, '  '.join('%s %.2f' % kv for kv in r.items())))
