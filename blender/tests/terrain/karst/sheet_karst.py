"""The karst package's compare sheet: the Guilin reference's row above the generated variants' rows (fenglin seeds 7
and 11, fengcong seed 5), each the reference rig's three views with the judge's numbers, and each variant's hero eye
(2 m cells, the fluting on) in a row under it. The judge's own sheet (judge/sheet.py compose), on make_views.py's
fields and render_karst.py's renders. System Python (Pillow).

    python blender/tests/terrain/karst/sheet_karst.py [--names fenglin_s7,fenglin_s11,fengcong_s5]

Writes out/karst/compare_guilin_karst_variants.png and out/karst/verdicts_variants.json.
"""
import argparse
import json
import os
import shutil
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
OUT = os.path.join(TN, 'out', 'karst')
sys.path.insert(0, TN)

from judge import judging, refs  # noqa: E402
from judge import sheet as S  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--names', default='fenglin_s7,fenglin_s11,fengcong_s5')
    a = ap.parse_args()
    ref = refs.load('guilin_karst') if hasattr(refs, 'load') else refs.Reference('guilin_karst')
    verdicts, out = [], {}
    for name in [n for n in a.names.split(',') if n]:
        f = np.load(os.path.join(OUT, f'{name}_fields.npz'))
        v = judging.judge(dict(h=f['h_main'].astype(np.float64), cell=8.0, frame='north_up'), 'guilin_karst')
        v.label = name
        verdicts.append(v)
        out[name] = v.to_dict()
        hero = os.path.join(OUT, f'{name}_hero_eye_1p7m.png')
        if os.path.exists(hero):
            shutil.copyfile(hero, os.path.join(OUT, f'{name}_hero_eye.png'))
    title = ('Guilin tower karst (fenglin) vs tower_karst: fenglin seeds 7 and 11, fengcong seed 5 (no DEM '
             'reference: its numbers are against Guilin for information)')
    S.compose(os.path.join(OUT, 'compare_guilin_karst_variants.png'), ref, verdicts, OUT, title=title)
    with open(os.path.join(OUT, 'verdicts_variants.json'), 'w') as fh:
        json.dump(out, fh, indent=1, default=float)
    for v in verdicts:
        print(v.label, f"{sum(1 for r in v.judged if r['passed'])}/{len(v.judged)}", v.failures)


if __name__ == '__main__':
    main()
