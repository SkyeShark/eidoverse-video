"""The helicopter seen: three stills in daylight (a GPU job, EEVEE, 960 x 540, 16 samples).

    bash run_blender.sh blender/tests/props_helicopter/test_stills.py          (after test_build.py)

eidoblend.props.helicopter.cli stills on out/helicopter.blend into out/stills/: left_front_above (the open left door
from above and behind it: the nose's windows, the cockpit door's, the gunners'), left_front_below (the side and the
nose from below: the chin window, the windshield's frames, the rivet rows down the cabin), nose_left (the nose from
the left front). Checks (PASS / FAIL): each still written, the aircraft neither black nor blown. A PASS is not a look:
open the stills, close (the nose's frames, the rivet rows as dots, the exhaust shields in the airframe's paint).
"""
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.props.helicopter import cli  # noqa: E402

OUT = os.path.join(HERE, 'out')
VIEWS = ('left_front_above', 'left_front_below', 'nose_left')
FAILS = []


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg, flush=True)
    if not ok:
        FAILS.append(msg)


def main():
    look = os.path.join(OUT, 'helicopter.blend')
    if not os.path.isfile(look):
        print('SKIP out/helicopter.blend is missing (run test_build.py)')
        return
    cli.cmd_stills(['stills', '--blend', look, '--out', os.path.join(OUT, 'stills'), '--views', ','.join(VIEWS), '--res', '960x540', '--samples', '16'])
    for nm in VIEWS:
        path = os.path.join(OUT, 'stills', f'{nm}.png')
        if not os.path.isfile(path):
            check(False, f'{nm}: not written')
            continue
        im = bpy.data.images.load(path)
        a = np.empty(len(im.pixels), np.float32)
        im.pixels.foreach_get(a)
        a = a.reshape(im.size[1], im.size[0], 4)[..., :3]
        hot = float((a.max(axis=2) >= 250 / 255).mean())
        check(0.1 < float(a.mean()) < 0.8 and hot < 0.02, f'{nm}: written; mean {a.mean():.3f}, highlights {hot * 100:.2f} %')
        bpy.data.images.remove(im)
    print(f'[helicopter stills] {len(FAILS)} FAIL' if FAILS else '[helicopter stills] all checks passed')


if __name__ == '__main__':
    try:
        main()
    except Exception:                                           # noqa: BLE001
        import traceback
        traceback.print_exc()
        FAILS.append('exception')
    sys.stdout.flush()
    os._exit(1 if FAILS else 0)
