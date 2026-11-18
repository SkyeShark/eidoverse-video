"""A dunes run of the Blender edition with its stage dumps, dispatch log, readbacks and step snapshots, for a kind
whose levels refine (PORT_PLAN.md 5.1, 5.2, 5.7), and the stage floors of every level's call. In Blender:

    bash run_blender.sh eidoverse/terrain/tests/wind_sand/blender_refine.py -- [--variant linear] [--seed 1]
        [--quality draft] [--patterns 5] [--samples 5] [--out <dir>]
    (a GPU job: on a shared machine behind $EIDO_GPU_WRAP)

With --samples N (after the base run is done) it also makes the perturbed runs p1..pN of the floor's protocol
(blender_chaos_floor.py run_one's: the same call with every op's entry and each kernel's first dispatch nudged by one
ulp, memos cleared), each kept only as its sample.json of the step snapshots' differences from the base run's: the
snapshot floors tests/parity/replay.mjs grades a replay's snapshots by.

Why: the floor's dunes runs (tests/parity/blender_chaos_floor.py) are the star kind at draft quality, whose main
level is its growth level, so their dumps hold the growth and the coarser levels' averages but no refinement. The
linear kind's 2 km spacing grows on the coarsest context level (78 m cells) and refines the two finer levels at their
own cells, the code path every film or hero terrain runs below its growth level (aeolian.refine). This is the floor's
base run as it is (tests/parity/_hooks.py and blender_stage_dump.py, no change to the Blender branch: run_one's
calls with the variant's knobs), then blender_stage_dump.stage_floors on every level with the recipe's prepare hook
done first: dune_field finds its level stack in aeolian._CURRENT, which the recipe's prepare sets and a replay of a
dump alone does not (the floor tool's replays of a refining call would otherwise grow a tile on that level instead).
Writes <out>/dunes_<variant>_s<seed>_<quality>/base/ in the floor's format (default out:
eidoverse/terrain/tests/out/wind_sand/parity/).
"""
from __future__ import annotations

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PARITY = os.path.normpath(os.path.join(HERE, '..', 'parity'))
sys.path.insert(0, PARITY)
import _blender as B  # noqa: E402

import numpy as np  # noqa: E402

VARIANTS = {'linear': ('namib_linear_dunes', {'kind': 'linear'}), 'transverse': ('white_sands', {'kind': 'transverse'}),
            'barchan': ('white_sands', {'kind': 'barchan'}), 'star': ('namib_star_dunes', None)}


def args():
    a = B.script_args()
    opt = dict(variant='linear', seed='1', quality='draft', patterns='5', samples='0',
               out=os.path.join(B.TERRAIN, 'tests', 'out', 'wind_sand', 'parity'))
    for i in range(0, len(a) - 1, 2):
        opt[a[i].lstrip('-')] = a[i + 1]
    return opt


def main():
    opt = args()
    B.import_blender_terrain()
    import _hooks as H
    from blender_stage_dump import StageDumper, stage_floors
    h = H.install()
    from eidoblend.terrain import api as A
    from eidoblend.terrain.core import levels as L
    from eidoblend.terrain.solvers import aeolian as AE
    from judge import refs
    gpu = h.G.init()
    ref_name, params = VARIANTS[opt['variant']]
    ref = refs.load(ref_name)
    seed = int(opt['seed'])
    run_dir = os.path.join(opt['out'], f"dunes_{opt['variant']}_s{seed}_{opt['quality']}")
    pdir = os.path.join(run_dir, 'base')
    os.makedirs(pdir, exist_ok=True)
    if os.path.exists(os.path.join(pdir, 'stage_floors.done')):
        for k in range(1, int(opt['samples']) + 1):
            kdir = os.path.join(run_dir, f'p{k}')
            if os.path.exists(os.path.join(kdir, 'sample.json')):
                continue
            os.makedirs(kdir, exist_ok=True)
            snap = H.SnapStore(None, base_dir=os.path.join(pdir, 'snap'))
            h.start(pattern=k, log_dir=kdir, snap=snap)
            t0 = time.perf_counter()
            try:
                A.generate('dunes', size=ref.extent, seed=seed, params=params, quality=opt['quality'], cache=False,
                           log=lambda m: None)
            finally:
                diffs = h.stop(log_dir=kdir)
            B.write_json(os.path.join(kdir, 'sample.json'), dict(pattern=k, snapshots=diffs,
                                                                seconds=round(time.perf_counter() - t0, 2)))
            B.write_json(os.path.join(kdir, 'done.json'), dict(pattern=k, date=time.strftime('%Y-%m-%d %H:%M:%S')))
            print(f'[blender_refine] perturbed run p{k}: {time.perf_counter() - t0:.1f} s', flush=True)
        print('[blender_refine] done', flush=True)
        return
    snap = H.SnapStore(os.path.join(pdir, 'snap'))
    dumper = StageDumper(os.path.join(pdir, 'stages'))
    plans = H.PlanRecorder(os.path.join(pdir, 'plans'))
    print(f"[blender_refine] dunes {opt['variant']} seed {seed}: reference {ref_name}, size {ref.extent}", flush=True)
    h.start(pattern=None, log_dir=pdir, snap=snap, dumper=dumper, plans=plans)
    t0 = time.perf_counter()
    try:
        t = A.generate('dunes', size=ref.extent, seed=seed, params=params, quality=opt['quality'], cache=False,
                       log=lambda m: None)
    finally:
        h.stop(log_dir=pdir)
    secs = time.perf_counter() - t0
    verdict = B.judge_dict(t, ref_name, label=f"dunes_{opt['variant']}_seed{seed}", source_chain=True)
    t.save(os.path.join(pdir, 'terrain'))
    B.write_json(os.path.join(pdir, 'verdict.json'), verdict)
    levels = [dict(index=i, role=lv.role, cell=lv.cell, n=lv.n, relief_m=float(np.ptp(np.asarray(t.fields(i)['h']))),
                   level=repr(lv)) for i, lv in enumerate(t.levels)]
    B.write_json(os.path.join(pdir, 'run.json'), dict(recipe='dunes', variant=opt['variant'], seed=seed, pattern=0,
                                                     quality=opt['quality'], size=ref.extent, params=params,
                                                     reference=ref_name, seconds=round(secs, 2), levels=levels,
                                                     main_index=t.main.index, summary=h.summary(),
                                                     versions=B.versions(gpu), key=B.source_key()))
    B.write_json(os.path.join(pdir, 'done.json'), dict(seconds=round(secs, 2), dispatches=h.dispatches,
                                                      date=time.strftime('%Y-%m-%d %H:%M:%S')))
    print(f'[blender_refine] the run: {secs:.1f} s, {h.dispatches} dispatches; now the stage floors', flush=True)
    header = B.read_json(os.path.join(pdir, 'stages', 'stages.json'))
    AE.prepare(header['values'], [L.Level.from_dict(d) for d in header['plan']])     # the recipe's prepare hook
    stage_floors(os.path.join(pdir, 'stages'), patterns=int(opt['patterns']), levels='all')
    print('[blender_refine] done', flush=True)


main()
