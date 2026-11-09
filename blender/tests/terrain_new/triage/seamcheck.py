"""Does each subject really tile? Ekigar declares every tile periodic (tile = (1, 1)) and its compiler snaps lattices so
it should: evaluate the graph on a strip of texels that crosses the tile's x = 1 edge (positions 0.98..1.02, so the
same texels as the field's last and first columns, continued) and on the strip shifted back by exactly one tile
(-0.02..0.02). A periodic field gives the same heights on both; the largest difference, in metres at the subject's
tile size, is the seam a tiled layout (build_mesh(wrap=True), a 3 x 3 film set) would show. Same along y.

    python seamcheck.py [name,name]     # prints a table, writes renders/seamcheck.json
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..', 'terrain_ekigar')))
sys.path.insert(0, HERE)
import _ekigar_load  # noqa: E402
import scenes  # noqa: E402
import generate  # noqa: E402

ek = _ekigar_load.load()
from ekigar.compile import compile_graph, Ctx  # noqa: E402
from ekigar._tsl import Vec, Tile  # noqa: E402
from ekigar import _deriv  # noqa: E402

N = 1024
K = 16          # texels each side of the edge


def strip(graph, target, x0, axis):
    """Heights on a K*2 x 256 strip of texel centres starting at x0 (in tile units) across `axis`."""
    a = (np.arange(-K, K) + 0.5) / N + x0
    b = (np.arange(0, N, 4) + 0.5) / N
    if axis == 'x':
        X, Y = np.meshgrid(a, b)
    else:
        Y, X = np.meshgrid(a, b)
        X, Y = X.T, Y.T
    old = _deriv.set_mode('coarse')
    try:
        with np.errstate(all='ignore'):
            r = compile_graph(graph, target, Ctx(Vec(X, Y), Tile(1, 1), resolution=N))
    finally:
        _deriv.set_mode(old)
    return np.broadcast_to(np.asarray(r['field'].x, dtype=np.float64), X.shape)


def check(s):
    g, t, terrain = generate.build(s)
    t = terrain or t
    out = {}
    for axis in ('x', 'y'):
        across = strip(g, t, 1.0, axis)          # crosses the tile edge at 1
        inside = strip(g, t, 0.0, axis)          # the same texels one tile back
        out[axis] = float(np.abs(across - inside).max() * scenes.VS * s['W'])
    return out


if __name__ == '__main__':
    names = sys.argv[1].split(',') if len(sys.argv) > 1 else \
        [s['name'] for s in scenes.SUBJECTS if s['build'][0] != 'dem']
    res = {}
    print(f"{'subject':34s} {'x seam m':>10s} {'y seam m':>10s}")
    for n in names:
        s = scenes.BY_NAME[n]
        try:
            r = check(s)
        except Exception as ex:
            r = {'error': f'{type(ex).__name__}: {ex}'}
        res[n] = r
        if 'error' in r:
            print(f"{n:34s} {r['error']}", flush=True)
        else:
            flag = '   <-- does not tile' if max(r['x'], r['y']) > 0.5 else ''
            print(f"{n:34s} {r['x']:10.2f} {r['y']:10.2f}{flag}", flush=True)
    with open(os.path.join(scenes.RENDERS, 'seamcheck.json'), 'w') as f:
        json.dump(res, f, indent=1)
