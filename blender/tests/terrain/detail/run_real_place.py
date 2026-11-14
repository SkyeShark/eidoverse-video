"""real_place Lauterbrunnen with its hero levels around the reference's eye spot (the mesh-and-API package's focus),
generated in variants, every level's fields saved for the sheets and numbers (sheets.py):

    bash run_blender.sh blender/tests/terrain/detail/run_real_place.py [--variants upsampled,detail,full] [--tag t]
        [--breakup '{"relief": 0.05}'] [--hydraulic '{"steps": 3000}'] [--recipe real_place|fluvial_range]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

variants (real_place):
    upsampled   the DEM stage only: the hero levels are the DEM upsampled (Catmull-Rom), clay at eye level
    detail      the DEM, then this package's rock breakup and hydraulic pass on the hero levels
    full        the registered recipe: fluvial refinement, talus, rock breakup, hydraulic (packages 3 and 12)
fluvial_range: --recipe fluvial_range runs the registered recipe ('full') and the same without the detail stages
('nodetail'), focus on a hillside (--focus x,y).

Writes out/detail/runs/<tag>_<variant>/L<i>.npz (h and every field of the level) and run.json (plan, timings, the
log of every stage).
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'core'))
sys.path.insert(0, HERE)
import plain_import  # noqa: E402

plain_import.install()
import numpy as np  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'detail', 'runs'))


def args():
    a = plain_import.script_args()
    get = (lambda k, d: a[a.index(k) + 1] if k in a else d)
    return dict(variants=get('--variants', 'upsampled,detail,full').split(','), tag=get('--tag', 'lb'),
                breakup=json.loads(get('--breakup', '{}')), hydraulic=json.loads(get('--hydraulic', '{}')),
                recipe=get('--recipe', 'real_place'), focus=get('--focus', ''), quality=get('--quality', 'film'),
                cache=get('--cache', '1') == '1')


def recipe_for(name, variant, bp, hp):
    from eidoblend.terrain import recipes as RG
    d = RG.get(name).to_dict()
    keep = {'upsampled': ('dem',), 'detail': ('dem', 'breakup', 'hydraulic'), 'nodetail': None,
            'full': None}[variant]
    stages = []
    for s in d['stages']:
        if keep is not None and s['op'] not in keep:
            continue
        if variant == 'nodetail' and s['op'] in ('breakup', 'hydraulic'):
            continue
        if s['op'] == 'breakup':
            s['params'].update(bp)
        if s['op'] == 'hydraulic':
            s['params'].update(hp)
        stages.append(s)
    d['stages'] = stages
    return d


def main():
    A = args()
    from eidoblend.terrain import api
    import lauterbrunnen_truth as LT
    if A['recipe'] == 'real_place':
        pts, _eye = LT.focus()
        params = {'dem': 'lauterbrunnen'}
    else:
        fx, fy = (float(v) for v in A['focus'].split(',')) if A['focus'] else (2600.0, -1500.0)
        pts, params = [(fx, fy)], {}
    for variant in A['variants']:
        lines = []

        def log(m):
            lines.append(str(m))
            print(m, flush=True)
        t0 = time.perf_counter()
        t = api.generate(recipe_for(A['recipe'], variant, A['breakup'], A['hydraulic']), seed=1, params=params,
                         focus=pts, quality=A['quality'], cache=A['cache'], log=log)
        sec = time.perf_counter() - t0
        d = os.path.join(OUT, f"{A['tag']}_{variant}")
        os.makedirs(d, exist_ok=True)
        for lv in t.levels:
            f = t.fields(lv.index)
            np.savez_compressed(os.path.join(d, f'L{lv.index}.npz'), **{k: np.asarray(v) for k, v in f.items()})
        rec = dict(recipe=A['recipe'], variant=variant, seconds=round(sec, 2), info_seconds=t.info['seconds'],
                   plan=[lv.to_dict() for lv in t.levels], skipped=t.info.get('skipped_stages'),
                   breakup=A['breakup'], hydraulic=A['hydraulic'], focus=[list(p) for p in pts], log=lines)
        with open(os.path.join(d, 'run.json'), 'w') as f:
            json.dump(rec, f, indent=1, default=str)
        print(f'[run_real_place] {variant}: {sec:.1f} s -> {d}', flush=True)


if __name__ == '__main__':
    main()
