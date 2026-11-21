"""The Blender edition's own runs the glacial package compares the port with, where bake.py cannot make them:
alpine_valley's 'yosemite' preset (recipes/alpine_valley.py PRESETS: a 12 km tile, its base elevation 1100 m, the
upland horseshoe draining west), at draft quality, saved in the Terrain.save format both editions read. Run in
Blender (its GPU kernels), as bake.py runs:

    bash run_blender.sh eidoverse/terrain/tests/glacial/blender_runs.py -- <out folder> [--seeds 1,2,3,4] [--quality draft]
        [--dump]

Per seed, <out>/alpine_valley_yosemite_s<seed>.npz + .json (api.generate(...).save, bake.py's call with the preset's
size, knobs and base elevation) and <out>/alpine_valley_yosemite_s<seed>_bake.json (the run record, as bake.py writes
it). A GPU job: on a shared machine behind $EIDO_GPU_WRAP.

--dump  the run of one seed (give one: the solvers' per-process memos must start empty) made as a floor run's base
        is (tests/parity/blender_chaos_floor.py run_one, no perturbation): P3's hooks (tests/parity/_hooks.py) keep
        its dispatch log, step snapshots and stage dumps (blender_stage_dump.py's format) in
        <out>/dumps/alpine_valley_yosemite_s<seed>_draft/base/, with run.json, done.json and its Terrain.save as
        terrain.npz + .json, so tests/glacial/replay_test.mjs --run-dir replays the preset's own calls. The preset has
        no stage floors: its replay is graded at the kernel grade, a diagnosis, not an acceptance.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'parity'))
import _blender as B  # noqa: E402

B.import_blender_terrain()
from eidoblend.terrain import api as A  # noqa: E402
from eidoblend.terrain.recipes import alpine_valley as AV  # noqa: E402

args = B.script_args()
out = args[0]
seeds = [1, 2, 3, 4]
quality = 'draft'
if '--seeds' in args:
    seeds = [int(s) for s in args[args.index('--seeds') + 1].split(',')]
if '--quality' in args:
    quality = args[args.index('--quality') + 1]
dump = '--dump' in args
if dump and len(seeds) != 1:
    sys.exit('blender_runs.py --dump: one seed per process (the solvers keep memos within a process)')
os.makedirs(out, exist_ok=True)
for s in seeds:
    p = AV.preset('yosemite')
    name = f'alpine_valley_yosemite_s{s}'
    t0 = time.perf_counter()
    if dump:
        import _hooks as H  # noqa: E402
        from blender_stage_dump import StageDumper  # noqa: E402
        h = H.install()
        pdir = os.path.join(out, 'dumps', f'{name}_{quality}', 'base')
        os.makedirs(pdir, exist_ok=True)
        if os.path.exists(os.path.join(pdir, 'done.json')):
            os.remove(os.path.join(pdir, 'done.json'))
        h.start(pattern=None, log_dir=pdir, snap=H.SnapStore(os.path.join(pdir, 'snap')),
                dumper=StageDumper(os.path.join(pdir, 'stages')), plans=H.PlanRecorder(os.path.join(pdir, 'plans')))
        try:
            t = A.generate('alpine_valley', size=p['size'], seed=s, params=p['params'],
                           base_elevation_m=p['base_elevation_m'], quality=quality, cache=False, log=lambda m: None)
        finally:
            h.stop(log_dir=pdir)
        t.save(os.path.join(pdir, 'terrain'))
        B.write_json(os.path.join(pdir, 'run.json'), dict(recipe='alpine_valley', preset='yosemite', seed=s,
                     pattern=0, quality=quality, size=p['size'], params=p['params'],
                     base_elevation_m=p['base_elevation_m'], seconds=round(time.perf_counter() - t0, 2),
                     summary=h.summary(), versions=B.versions()))
        B.write_json(os.path.join(pdir, 'done.json'), dict(done=True))
        print(f'[glacial] {name}: dumps in {pdir}', flush=True)
        continue
    t = A.generate('alpine_valley', size=p['size'], seed=s, params=p['params'], base_elevation_m=p['base_elevation_m'],
                   quality=quality, cache=False)
    t.save(os.path.join(out, name))
    rec = dict(recipe='alpine_valley', preset='yosemite', seed=s, quality=quality, knobs=t.knobs,
               seconds=round(time.perf_counter() - t0, 2), levels=[str(lv) for lv in t.levels],
               skipped_stages=t.info['skipped_stages'], warnings=t.info['warnings'], versions=B.versions())
    with open(os.path.join(out, name + '_bake.json'), 'w', encoding='utf-8') as f:
        json.dump(A._plain(rec), f, indent=1)
    print(f'[glacial] {name}: {rec["seconds"]} s', flush=True)
