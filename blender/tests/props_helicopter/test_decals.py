"""The helicopter's drawn pictures (plain Python with Pillow; no Blender).

    python blender/tests/props_helicopter/test_decals.py

decals.draw into out/decals/. Checks (PASS / FAIL): the three pictures at 2.5 mm a pixel over the aircraft's side
(5680 x 1560); rivet rows, seams and fasteners in skin_side's three channels; the stencils on both sides, at the same
places, the right side's laid differently (each word turned so it reads true there); decals.json's rectangle.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.props.helicopter import decals  # noqa: E402

OUT = os.path.join(HERE, 'out', 'decals')
FAILS = []


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg, flush=True)
    if not ok:
        FAILS.append(msg)


def main():
    import numpy as np
    from PIL import Image
    spec = decals.draw(OUT)
    skin = np.asarray(Image.open(os.path.join(OUT, 'skin_side.png')))
    left = np.asarray(Image.open(os.path.join(OUT, 'marks_left.png')))
    right = np.asarray(Image.open(os.path.join(OUT, 'marks_right.png')))
    check(skin.shape == (1560, 5680, 3) and left.shape == right.shape == (1560, 5680), f'the pictures at 2.5 mm a pixel: {skin.shape}')
    ink = [(skin[..., c] > 0).mean() for c in range(3)]
    check(ink[0] > 0.002 and ink[1] > 0.001 and ink[2] > 0.0005, f'rivets, seams and fasteners drawn ({[round(i * 100, 3) for i in ink]} %)')
    lk, rk = left > 128, right > 128
    check(abs(lk.mean() - rk.mean()) < 0.2 * lk.mean(), f'the stencils on both sides ({lk.mean() * 100:.3f} %, {rk.mean() * 100:.3f} %)')
    check((lk != rk).mean() > 0.3 * lk.mean(), 'the right side\'s words are laid differently (each turned to read true there)')
    cols_l, cols_r = np.nonzero(lk.any(axis=0))[0], np.nonzero(rk.any(axis=0))[0]
    check(abs(cols_l.min() - cols_r.min()) < 200 and abs(cols_l.max() - cols_r.max()) < 200, 'the stencils stand at the same places on both sides')
    js = json.load(open(os.path.join(OUT, 'decals.json'), encoding='utf-8'))
    check(js == spec and js['rect']['x'] == [-4700.0, 9500.0], 'decals.json records the rectangle')
    print(f'[decals] {len(FAILS)} FAIL' if FAILS else '[decals] all checks passed')
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
