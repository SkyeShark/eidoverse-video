"""Does each operator's CARRIED gradient match the slope of the height it outputs?

Ekigar's field is vec4(height, dh/dx, dh/dy, aux): every node passes its analytic gradient downstream, and Phacelle
erosion aims its gullies along the gradient it receives. Where an operator's carried gradient disagrees with the real
slope of its own output, an erosion after it cuts gullies in the wrong direction. This measures, per operator on
Ekigar's own example fixture at 256 texels: the median and 90th-percentile angle between the carried gradient and the
central-difference slope of the output height (where the slope is not negligible), and the median magnitude ratio.

    python gradcheck.py [op,op]      # prints a table, writes renders/gradcheck.json
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

ek = _ekigar_load.load()
N = 256


def check(op):
    g, t, fx = ek.operator_example(op)
    hf = ek.generate(g, target=t, resolution=N, world_size=1.0, workers=4)
    h, cx, cy = hf.field[0], hf.field[1], hf.field[2]
    # central differences per tile unit, periodic (the example tiles)
    fx_ = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * (N / 2.0)
    fy_ = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * (N / 2.0)
    fd = np.hypot(fx_, fy_)
    car = np.hypot(cx, cy)
    sel = fd > max(np.percentile(fd, 25), 1e-6)
    sel[:2], sel[-2:], sel[:, :2], sel[:, -2:] = False, False, False, False
    if sel.sum() < 100:
        return {'fixture': fx, 'note': 'flat output'}
    cos = (cx * fx_ + cy * fy_)[sel] / np.maximum(car[sel] * fd[sel], 1e-12)
    ang = np.degrees(np.arccos(np.clip(cos, -1, 1)))
    ratio = car[sel] / fd[sel]
    return {'fixture': fx, 'angle_p50': float(np.median(ang)), 'angle_p90': float(np.percentile(ang, 90)),
            'ratio_p50': float(np.median(ratio)), 'reversed_pct': float(np.mean(ang > 90) * 100)}


if __name__ == '__main__':
    ops = sys.argv[1].split(',') if len(sys.argv) > 1 else [o for o in ek.gallery_ids()
                                                             if ek.OPERATORS[o]['category'] != 'derive']
    res = {}
    print(f"{'operator':22s} {'fixture':14s} {'ang50':>6s} {'ang90':>6s} {'ratio':>6s} {'rev%':>5s}")
    for op in ops:
        try:
            r = check(op)
        except Exception as ex:
            r = {'error': f'{type(ex).__name__}: {ex}'}
        res[op] = r
        if 'angle_p50' in r:
            print(f"{op:22s} {r['fixture']:14s} {r['angle_p50']:6.1f} {r['angle_p90']:6.1f} {r['ratio_p50']:6.2f} "
                  f"{r['reversed_pct']:5.1f}", flush=True)
        else:
            print(f"{op:22s} {r}", flush=True)
    os.makedirs(scenes.RENDERS, exist_ok=True)
    with open(os.path.join(scenes.RENDERS, 'gradcheck.json'), 'w') as f:
        json.dump(res, f, indent=1)
