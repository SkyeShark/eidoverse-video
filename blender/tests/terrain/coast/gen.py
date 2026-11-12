"""Generate sea_cliffs at a reference's extent and save its fields for the judge and for a look (Blender, a GPU slot):

    python blender/tests/terrain/coast/slot.py blender/tests/terrain/coast/gen.py -- \
        --rock chalk --seeds 1,2 --tag r2 [--quality film] [--params '{"retreat_m": 400}'] \
        [--variants '[{"name": "a", "rocks": {...}, "patch": {...}, "stages": [...], "context": 8}, ...]']

A variant (variants.py: rocks, patch, stages, defaults; plus context and params here) tries settings before they go
into recipes/sea_cliffs.py. Writes blender/tests/terrain/out/coast/gen/<tag>_<rock>[_<variant>]_s<seed>.npz (the
main level: h, cell, frame, sea_level, context_h, context_cell: what judge/run.py --field reads) and ..._fields.npz
(the main level's coast and process fields), plus <tag>_<rock>_record.json (levels, seconds).
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'core'))
import plain_import  # noqa: E402

plain_import.install()
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

from eidoblend.terrain import api as A  # noqa: E402
from variants import recipe_for  # noqa: E402

OUT = os.path.normpath(os.path.join(TN, 'out', 'coast', 'gen'))
REF = {'chalk': ('seven_sisters', 6000.0), 'layered': ('cliffs_of_moher', 6000.0)}


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(rock=opt('--rock', 'chalk'), seeds=[int(s) for s in opt('--seeds', '1').split(',')],
                tag=opt('--tag', 'r'), quality=opt('--quality', 'film'), params=json.loads(opt('--params', '{}')),
                variants=json.loads(opt('--variants', '[{"name": ""}]')))


def main():
    a = args()
    os.makedirs(OUT, exist_ok=True)
    rec = dict(args=a, runs={})
    for var in a['variants']:
        R = recipe_for(var)
        for seed in a['seeds']:
            t0 = time.time()
            params = dict(a['params'], **(var.get('params') or {}), rock=a['rock'])
            # (a ROCKS override changes the resolved stages but not the recipe dict the generate cache is keyed on)
            t = A.generate(R, size=REF[a['rock']][1], seed=seed, params=params, quality=a['quality'],
                           cache=not var.get('rocks'), context=var.get('context'))
            lv = t.main
            f = t.fields('main')
            ctx = [v for v in t.levels if v.role == 'context']
            c = max(ctx, key=lambda v: v.side) if ctx else None
            name = f"{a['tag']}_{a['rock']}" + (f"_{var['name']}" if var.get('name') else '') + f'_s{seed}'
            extra = {}
            if c is not None:
                extra = dict(context_h=np.asarray(t.fields(c.index)['h'], np.float32), context_cell=float(c.cell))
            np.savez(os.path.join(OUT, name + '.npz'), h=np.asarray(f['h'], np.float32), cell=float(lv.cell),
                     frame='south_up', sea_level=float(t.info.get('sea_level') or 0.0), **extra)
            keep = {k: np.asarray(f[k], np.float32) for k in ('coast_E', 'coast_d0', 'coast_cut', 'coast_s0', 'wear',
                                                              'talus', 'deposit', 'Sc', 'bed', 'A') if k in f}
            np.savez_compressed(os.path.join(OUT, name + '_fields.npz'), **keep)
            info = t.info
            rec['runs'][name] = dict(seconds=round(time.time() - t0, 1), levels=[str(v) for v in t.levels],
                                     info_seconds=info.get('seconds'), skipped=info.get('skipped_stages'),
                                     variant=var)
            print(f'[coast.gen] {name}: {rec["runs"][name]["seconds"]} s', flush=True)
    with open(os.path.join(OUT, f"{a['tag']}_{a['rock']}_record.json"), 'w', encoding='utf-8') as fh:
        json.dump(rec, fh, indent=1, default=str)
    os._exit(0)


main()
