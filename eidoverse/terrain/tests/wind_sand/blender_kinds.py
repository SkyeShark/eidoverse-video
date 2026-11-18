"""The Blender edition's dunes recipe for each kind and seed, its Terrain.save and the judge's verdict: the Blender half
of the wind-and-sand package's recipe parity (PORT_PLAN.md 5.3 "recipe, distribution class", 5.5: seeds 1-4 at draft
quality at the reference's extent). Runs in Blender (the slab model needs its GPU):

    bash run_blender.sh eidoverse/terrain/tests/wind_sand/blender_kinds.py -- [--variants star,gsd,transverse,linear,barchan]
        [--seeds 1,2,3,4] [--quality draft] [--out <dir>] [--skip-floor]
    (a GPU job: on a shared machine behind $EIDO_GPU_WRAP)

A variant is the recipe with its knobs and the reference it is judged against (VARIANTS): the star kind against the
Namib at Sossusvlei (the recipe's own default), the recipe doc's Great Sand Dunes knobs against the Great Sand Dunes,
the transverse kind against White Sands, the linear kind against the Namib's linear dunes, the barchan kind (no
reference of its own: its 3 km tile is White Sands') against White Sands for the judge's numbers. Each run: the
solvers' memos cleared (plan 5.4), api.generate(recipe, size, seed, params, quality, cache=False) as the floor's runs
call it (tests/parity/blender_chaos_floor.py), the judge's verdict (tests/parity/_blender.py judge_dict), the
Terrain.save. Writes <out>/<variant>_s<seed>/terrain.npz + .json, verdict.json, run.json (default out:
eidoverse/terrain/tests/out/wind_sand/blender_kinds/). With --skip-floor a star run the floor already holds (its base
run: the same call) is copied from there instead of made again.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', 'parity')))
import _blender as B  # noqa: E402

GSD = {'winds': [[282, 1.0], [102, 0.7], [192, 0.5]], 'sand_m': 40, 'spacing_m': 900, 'bed_relief_m': 30,
       'sand_patchiness': 0.5}
VARIANTS = {
    'star': dict(reference='namib_star_dunes', params=None),
    'gsd': dict(reference='great_sand_dunes', params=GSD),
    'transverse': dict(reference='white_sands', params={'kind': 'transverse'}),
    'linear': dict(reference='namib_linear_dunes', params={'kind': 'linear'}),
    'barchan': dict(reference='white_sands', params={'kind': 'barchan'}),
}


def args():
    a = B.script_args()
    opt = dict(variants=','.join(VARIANTS), seeds='1,2,3,4', quality='draft',
               out=os.path.join(B.TERRAIN, 'tests', 'out', 'wind_sand', 'blender_kinds'), skip_floor=False)
    i = 0
    while i < len(a):
        k = a[i].lstrip('-').replace('-', '_')
        if k == 'skip_floor':
            opt[k] = True
            i += 1
            continue
        opt[k] = a[i + 1]
        i += 2
    return opt


def main():
    opt = args()
    B.import_blender_terrain()
    from eidoblend.terrain import api as A
    from eidoblend.terrain.core import gpu as G
    from judge import refs
    sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', 'parity')))
    import _hooks as H
    gpu = G.init()
    os.makedirs(opt['out'], exist_ok=True)
    key = B.source_key()
    for variant in opt['variants'].split(','):
        v = VARIANTS[variant]
        ref = refs.load(v['reference'])
        for seed in [int(s) for s in opt['seeds'].split(',')]:
            d = os.path.join(opt['out'], f'{variant}_s{seed}')
            if os.path.exists(os.path.join(d, 'run.json')):
                print(f'[blender_kinds] {variant} seed {seed}: done already', flush=True)
                continue
            os.makedirs(d, exist_ok=True)
            floor = os.path.join(B.parity_root(), key['folder'], f'dunes_s{seed}_{opt["quality"]}', 'base')
            if opt['skip_floor'] and variant == 'star' and os.path.exists(os.path.join(floor, 'done.json')):
                for f in ('terrain.npz', 'terrain.json', 'verdict.json'):
                    shutil.copy2(os.path.join(floor, f), os.path.join(d, f))
                fr = B.read_json(os.path.join(floor, 'run.json'))
                B.write_json(os.path.join(d, 'run.json'), dict(variant=variant, seed=seed, reference=v['reference'],
                                                              size=ref.extent, params=v['params'], seconds=fr['seconds'],
                                                              from_floor=floor, versions=fr.get('versions'), key=key))
                print(f'[blender_kinds] {variant} seed {seed}: the floor\'s base run, copied', flush=True)
                continue
            try:
                n = H.clear_memos()
                logs = []
                t0 = time.perf_counter()
                t = A.generate('dunes', size=ref.extent, seed=seed, params=v['params'], quality=opt['quality'],
                               cache=False, log=lambda m: logs.append(m))
                secs = time.perf_counter() - t0
                verdict = B.judge_dict(t, v['reference'], label=f'dunes_{variant}_seed{seed}', source_chain=True)
                t.save(os.path.join(d, 'terrain'))
                B.write_json(os.path.join(d, 'verdict.json'), verdict)
                B.write_json(os.path.join(d, 'run.json'), dict(variant=variant, seed=seed, reference=v['reference'],
                                                              size=ref.extent, params=v['params'], quality=opt['quality'],
                                                              seconds=round(secs, 2), memos_cleared=n,
                                                              levels=[repr(lv) for lv in t.levels],
                                                              log=[m for m in logs if 'aeolian' in m][:40],
                                                              versions=B.versions(gpu), key=key))
                judged = [r for r in verdict['rows'] if r['passed'] is not None]
                print(f'[blender_kinds] {variant} seed {seed}: {secs:.1f} s, {v["reference"]} '
                      f'{sum(1 for r in judged if r["passed"])}/{len(judged)} bands', flush=True)
            except Exception:                                          # noqa: BLE001
                print(f'[blender_kinds] {variant} seed {seed} FAILED:\n{traceback.format_exc()}', flush=True)
                with open(os.path.join(d, 'failed.txt'), 'w', encoding='utf-8') as f:
                    f.write(traceback.format_exc())


main()
