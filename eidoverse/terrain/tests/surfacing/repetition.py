"""The repetition measure of the surfacing judge (blender/tests/terrain/surfacing_judge/measures.py repetition, the
Blender edition's own code, imported in place: one judge) on ground crops of renders: the port's beside Blender's
(PORT_PLAN.md 8.2 row P17: "the repetition peak <= 0.12"; SURFACING_DESIGN.md 5.4 package 2 check 3, with the crop's
high-pass energy beside, so blur cannot pass for de-tiling).

    python eidoverse/terrain/tests/surfacing/repetition.py <png> [<png> ...] [--box x0,y0,x1,y1] [--mode 2d|rows]
        [--out <json>]
    (numpy and Pillow; EIDO_BLENDER_EDITION: a checkout of the blender branch, for the judge's measures)

Prints per image the peak, its lag and the energy; --out writes them as JSON.
"""
import json
import os
import sys

import numpy as np
from PIL import Image


def judge():
    ed = os.environ.get('EIDO_BLENDER_EDITION')
    here = os.path.dirname(os.path.abspath(__file__))
    for root in ([ed] if ed else []) + [os.path.normpath(os.path.join(here, '..', '..', '..', '..'))]:
        p = os.path.join(root, 'blender', 'tests', 'terrain')
        if os.path.isdir(os.path.join(p, 'surfacing_judge')):
            sys.path.insert(0, p)
            from surfacing_judge import measures as M
            return M
    sys.exit('repetition.py: set EIDO_BLENDER_EDITION to a checkout of the blender branch (the judge\'s measures)')


def main(argv):
    M = judge()
    box, mode, out, files = None, '2d', None, []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--box':
            box = [int(v) for v in argv[i + 1].split(',')]
            i += 2
        elif a == '--mode':
            mode = argv[i + 1]
            i += 2
        elif a == '--out':
            out = argv[i + 1]
            i += 2
        else:
            files.append(a)
            i += 1
    res = {}
    for f in files:
        rgb = np.asarray(Image.open(f).convert('RGB'), np.float64) / 255.0
        r = M.repetition(M.luma(rgb), box=box, mode=mode)
        res[os.path.basename(f)] = r
        print(f"{os.path.basename(f)}: peak {r['peak'] if r['peak'] is None else round(r['peak'], 3)} lag {r['lag']} "
              f"energy {r['energy']:.4f}")
    if out:
        with open(out, 'w') as fh:
            json.dump(dict(box=box, mode=mode, images=res), fh, indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])
