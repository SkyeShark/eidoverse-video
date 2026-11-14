"""The chaos floor of the Blender edition by the revised protocol (PORT_PLAN.md C1, 5.4), and the runs every later
package is checked by: each recipe and seed at draft quality, at its reference's extent, once as it is (the base run)
and five times perturbed, every run in a process of its own (so the solvers' per-process memos start empty, and
are cleared besides), every run with its dispatch log, readbacks and step snapshots (5.7), the base run also with
its stage dumps (blender_stage_dump.py) and its Terrain.save. The hooks are design_probes/blender_floor_patterns.py's
(tests/parity/_hooks.py); nothing in the Blender branch changes.

    bash eidoverse/terrain/tests/parity/floor_runs.sh [--recipes a,b] [--seeds 1,2] [--patterns 0-5]
        [--dump-seeds 1,2] [--quality draft] [--retry-failed]
                     the runs, one Blender job after another through the Blender edition's run_blender.sh, after
                     $EIDO_GPU_WRAP when it is set; a run already done is skipped, so it resumes where it stopped.
                     The jobs are started by that shell, not by Python: a GPU queue may refuse a job whose
                     launching shell it cannot see
    <Blender's python> -I eidoverse/terrain/tests/parity/blender_chaos_floor.py --next [the same options]
                     the next run that is not done (floor_runs.sh asks; exit code 3 when none is left)
    <Blender's python> -I eidoverse/terrain/tests/parity/blender_chaos_floor.py --status [the same options]
                     which runs are done, failed and missing
    <Blender's python> -I eidoverse/terrain/tests/parity/blender_chaos_floor.py --summarise
                     floor.json from every run in: the tolerances (5.3), the classes (5.4 item 6)
    bash run_blender.sh eidoverse/terrain/tests/parity/blender_chaos_floor.py -- --run --recipe R --seed S
        --pattern P --dir <dir> --root <root> [--dump] [--quality draft]
                     one run (floor_runs.sh starts these)

The Blender edition is found as _blender.py finds it ($EIDO_BLENDER_EDITION, or blender/ in this checkout).
Outputs, under $EIDO_PARITY_OUT or eidoverse/terrain/tests/out/parity/, keyed by the Blender commit and code hash
(5.1): blender_<commit>_<code hash>/
    manifest.json                       the key (commit, dirty files, the Blender field and terrain hashes, a hash of
                                        every file that makes the fields), the versions (Python, numpy, zlib,
                                        Blender), the protocol
    <recipe>_s<seed>_<quality>/base/    run.json, done.json, dispatch_log.jsonl.gz, readbacks.jsonl.gz,
                                        kernels.json, snap/ (d<dispatch>.npz, index.json), terrain.npz + .json (the
                                        Terrain.save of every level), verdict.json (the judge's numbers and verdict
                                        on the main level, when the recipe has a reference), stages/ (with --dump),
                                        plans/ (every plan call: plans.json, calls.pkl, r<k>.npz; _hooks.py)
    <recipe>_s<seed>_<quality>/p<k>/    run.json, done.json, sample.json (against the base: every level's RMS and
                                        p99 |dh| over relief and channel overlap, the judge's numbers, the kernel
                                        sequence and uniforms, the step snapshots' differences), the run's own logs
    floor.json                          --summarise

What a run is (5.4, 5.5): api.generate(recipe, size=<the reference's extent>, seed, quality='draft', params,
cache=False), as the judge's blender_job.recipe_item generates it (real_place: dem = its reference, judged without
the source chain); meadow has no reference and runs at its own size, with Core's metrics in place of the judge.
A perturbed run (pattern k) moves every float32 field of the level by one ulp on half the cells at each op's
entry and each kernel's images after its first dispatch in each op call (_hooks.py).
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _blender as B  # noqa: E402

PROTOCOL = ('PORT_PLAN.md C1 / 5.4: draft quality at the reference extent; base run plus five patterns; every float32 '
            'field of the level +-1 ulp on half the cells at every op entry (default_rng([pattern, op call])) and '
            'every kernel\'s images +-1 ulp after its first dispatch in each op call (default_rng([pattern, op call, '
            'kernel, 1])); one process per run, memos cleared; cache off')
KEYS = ('relief_m', 'hypsometric_integral', 'slope_p10', 'slope_p50', 'slope_p90', 'slope_p99', 'frac_slope_lt5',
        'depression_area_frac', 'spectrum_slope', 'spectrum_knee_m', 'anisotropy_4', 'anisotropy_8', 'cliff_pair_frac')
BOUNDARY = 0.02                 # the provisional class boundary on the main level's RMS / relief (5.4 item 6)


def channels(f, cell):
    """The channel cells of a level (blender_floor_patterns.py): drainage area above max(1 km^2, 400 cells)."""
    if 'A' not in f:
        return None
    return np.asarray(f['A'], np.float64) > max(1e6, 400 * cell * cell)


# -------------------------------------------------------------------------------------------- one run (Blender) ---

def _log_lines(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        for line in f:
            yield json.loads(line)


def compare_logs(base_path, path):
    """The kernel sequence and uniforms of a run against the base's: equal sequences, the first dispatch that differs
    in kernel or uniforms, and how many dispatches carry other uniforms."""
    n = same_u = 0
    first_k = first_u = None
    other_u = 0
    a_iter, b_iter = _log_lines(base_path), _log_lines(path)
    while True:
        a, b = next(a_iter, None), next(b_iter, None)
        if a is None or b is None:
            longer = 'base' if a is not None else ('perturbed' if b is not None else None)
            rest = (1 + sum(1 for _ in a_iter)) if a is not None else ((1 + sum(1 for _ in b_iter)) if b is not None
                                                                       else 0)
            break
        if first_k is None and (a[1] != b[1] or a[0] != b[0]):
            first_k = dict(index=n, base=[a[0], a[1]], perturbed=[b[0], b[1]])
        if a[2] != b[2]:
            other_u += 1
            if first_u is None:
                first_u = dict(index=n, op=a[0], kernel=a[1],
                               uniforms=[[x, y] for x, y in zip(a[2], b[2]) if x != y][:6])
        else:
            same_u += 1
        n += 1
    return dict(compared=n, same_kernel_sequence=first_k is None and longer is None, first_kernel_difference=first_k,
                longer=longer, extra_dispatches=rest, dispatches_with_other_uniforms=other_u,
                first_uniform_difference=first_u)


def run_one(a):
    root = B.import_blender_terrain()
    import _hooks as H
    from blender_stage_dump import StageDumper
    h = H.install()
    from eidoblend.terrain import api as A
    from eidoblend.terrain.core import metrics as M
    gpu = h.G.init()
    manifest = B.read_json(os.path.join(a.root, 'manifest.json'))
    fh, th = B.blender_code_hashes()
    if manifest is None or (fh, th) != (manifest['key']['field_hash'], manifest['key']['terrain_hash']):
        sys.exit(f'[floor] the Blender code at {root} is not the code {a.root} is keyed by: start the driver again')
    ref_name, size, params, source_chain = B.reference_for(a.recipe)
    tag = 'base' if a.pattern == 0 else f'p{a.pattern}'
    pdir = os.path.join(a.dir, tag)
    os.makedirs(pdir, exist_ok=True)
    for f in ('done.json', 'failed.json'):
        if os.path.exists(os.path.join(pdir, f)):
            os.remove(os.path.join(pdir, f))
    base_dir = os.path.join(a.dir, 'base')
    snap = (H.SnapStore(os.path.join(pdir, 'snap')) if a.pattern == 0
            else H.SnapStore(None, base_dir=os.path.join(base_dir, 'snap')))
    dumper = StageDumper(os.path.join(pdir, 'stages')) if (a.dump and a.pattern == 0) else None
    print(f'[floor] {a.recipe} seed {a.seed} {tag}: reference {ref_name}, size {size}', flush=True)
    plans = H.PlanRecorder(os.path.join(pdir, 'plans')) if a.pattern == 0 else None
    h.start(pattern=None if a.pattern == 0 else a.pattern, log_dir=pdir, snap=snap, dumper=dumper, plans=plans)
    t0 = time.perf_counter()
    try:
        t = A.generate(a.recipe, size=size, seed=a.seed, params=params, quality=a.quality, cache=False,
                       log=lambda m: None)
    finally:
        snapdiffs = h.stop(log_dir=pdir)
    secs = time.perf_counter() - t0
    summ = h.summary()
    levels = []
    for i, lv in enumerate(t.levels):
        hh = np.asarray(t.fields(i)['h'], np.float64)
        levels.append(dict(index=i, role=lv.role, cell=lv.cell, n=lv.n, relief_m=float(np.ptp(hh)), level=repr(lv)))
    hm = np.asarray(t.fields('main')['h'], np.float64)
    metrics = M.metrics(hm, t.main.cell)
    verdict = None
    tj = time.perf_counter()
    if ref_name:
        verdict = B.judge_dict(t, ref_name, label=f'{a.recipe}_seed{a.seed}', source_chain=source_chain)
    judge_s = time.perf_counter() - tj
    run = dict(recipe=a.recipe, seed=a.seed, pattern=a.pattern, quality=a.quality, size=size, params=params,
               reference=ref_name, source_chain=source_chain, seconds=round(secs, 2), judge_seconds=round(judge_s, 2),
               levels=levels, main_index=t.main.index, metrics_main={k: metrics.get(k) for k in metrics},
               summary=summ, versions=B.versions(gpu), key=manifest['key'], protocol=PROTOCOL,
               stage_dump_bytes=dumper.bytes if dumper is not None else None,
               snapshot_bytes=snap.bytes if a.pattern == 0 else None)
    if a.pattern == 0:
        t.save(os.path.join(pdir, 'terrain'))
        if verdict is not None:
            B.write_json(os.path.join(pdir, 'verdict.json'), verdict)
    else:
        sample = dict(pattern=a.pattern, levels=[], snapshots=snapdiffs)
        with np.load(os.path.join(base_dir, 'terrain.npz')) as z:
            for i, lv in enumerate(t.levels):
                fb = {k.split('__', 2)[2]: z[k] for k in (f'L{i}__f__h', f'L{i}__f__A') if k in z.files}
                fp = t.fields(i)
                hb, hp = np.asarray(fb['h'], np.float64), np.asarray(fp['h'], np.float64)
                r = float(np.ptp(hb)) or 1.0
                d = hp - hb
                cb, cp = channels(fb, lv.cell), channels(fp, lv.cell)
                ov = None
                if cb is not None and cp is not None:
                    inter, union = int((cb & cp).sum()), int((cb | cp).sum())
                    ov = inter / union if union else 1.0
                sample['levels'].append(dict(index=i, role=lv.role, cell=lv.cell,
                                             rms_over_relief=float(np.sqrt(np.mean(d * d)) / r),
                                             p99_abs_over_relief=float(np.percentile(np.abs(d), 99) / r),
                                             max_abs_m=float(np.max(np.abs(d))), channel_overlap=ov,
                                             bit_identical=bool(np.array_equal(hb, hp))))
        base_run = B.read_json(os.path.join(base_dir, 'run.json'))
        bm = base_run['metrics_main']
        sample['metrics_main'] = {k: [bm.get(k), metrics.get(k)] for k in KEYS}
        if verdict is not None:
            bv = B.read_json(os.path.join(base_dir, 'verdict.json'))
            sample['judge'] = {kind: {k: [bv['numbers'][kind].get(k), v] for k, v in verdict['numbers'][kind].items()}
                               for kind in ('generated', 'generated_family') if verdict['numbers'].get(kind)}
            sample['judge_passed'] = [bv['passed'], verdict['passed']]
        sample['dispatch'] = compare_logs(os.path.join(base_dir, 'dispatch_log.jsonl.gz'),
                                          os.path.join(pdir, 'dispatch_log.jsonl.gz'))
        B.write_json(os.path.join(pdir, 'sample.json'), sample)
        main = next(x for x in sample['levels'] if x['role'] == 'main')
        print(f"[floor] {a.recipe} seed {a.seed} {tag}: main RMS {main['rms_over_relief']:.4g}, p99 "
              f"{main['p99_abs_over_relief']:.4g}, overlap {main['channel_overlap']}, same kernels "
              f"{sample['dispatch']['same_kernel_sequence']}", flush=True)
    B.write_json(os.path.join(pdir, 'run.json'), run)
    B.write_json(os.path.join(pdir, 'done.json'), dict(seconds=round(secs, 2), dispatches=summ['dispatches'],
                                                      date=time.strftime('%Y-%m-%d %H:%M:%S')))
    print(f"[floor] {a.recipe} seed {a.seed} {tag}: done in {secs:.1f} s ({summ['dispatches']} dispatches, "
          f"{summ['readbacks']} readbacks, {summ['op_calls']} op calls)", flush=True)


# ------------------------------------------------------------------------------------------------ the driver ---

# The order the recipes are run in: what the port's packages need first comes first (plan 8.3, 8.4: the hydrology
# and fluvial packages' recipes, then detail's, wind and sand, volcanoes and craters, layered rock, karst and coast,
# glacial). Every recipe of the registry is in it; a recipe added to the registry later runs last.
RECIPE_ORDER = ('rolling_hills', 'tower_karst', 'fluvial_range', 'meadow', 'real_place', 'dunes', 'caldera',
                'cinder_cones', 'impact_crater', 'stratovolcano', 'canyon', 'incised_meanders', 'mesas_buttes',
                'badlands', 'sea_cliffs', 'alpine_valley')


def _root_and_manifest():
    """The output root for the Blender code as it is now (keyed by its commit and code hash), its manifest made."""
    edition = B.bare_terrain_package()
    key = B.source_key(edition)
    root = os.path.join(B.parity_root(), key['folder'])
    os.makedirs(root, exist_ok=True)
    man_path = os.path.join(root, 'manifest.json')
    if B.read_json(man_path) is None:
        B.write_json(man_path, dict(key=key, versions=B.versions(), protocol=PROTOCOL,
                                    created=time.strftime('%Y-%m-%d %H:%M:%S')))
    return edition, key, root


def _wanted(a):
    from eidoblend.terrain import recipes as RG
    names = RG.names()
    recipes = [r for r in a.recipes.split(',') if r] if a.recipes else \
        [r for r in RECIPE_ORDER if r in names] + [r for r in names if r not in RECIPE_ORDER]
    seeds = [int(s) for s in a.seeds.split(',') if s]
    lo, _, hi = a.patterns.partition('-')
    patterns = list(range(int(lo), int(hi or lo) + 1))
    dump_seeds = {int(s) for s in a.dump_seeds.split(',') if s}
    return recipes, seeds, patterns, dump_seeds


def next_run(a):
    """--next: the next run that is not done, for floor_runs.sh: its folder on the first line, then the words that
    follow `run_blender.sh` (this script, then its arguments), one per line; exit code 3 when nothing is left. Seeds
    outermost (every recipe's seed 1 before any seed 2), then the recipes in RECIPE_ORDER, then the base run and its
    patterns. A run with failed.json is passed over (--clear-failed removes those marks, so the runs are taken
    again), and so are the perturbed runs of a base that is not done."""
    _edition, key, root = _root_and_manifest()
    recipes, seeds, patterns, dump_seeds = _wanted(a)
    for seed in seeds:
        for recipe in recipes:
            rdir = os.path.join(root, f'{recipe}_s{seed}_{a.quality}')
            base_done = os.path.exists(os.path.join(rdir, 'base', 'done.json'))
            for p in patterns:
                pdir = os.path.join(rdir, 'base' if p == 0 else f'p{p}')
                if os.path.exists(os.path.join(pdir, 'done.json')):
                    continue
                if os.path.exists(os.path.join(pdir, 'failed.json')):
                    continue
                if p > 0 and not base_done:
                    continue
                os.makedirs(pdir, exist_ok=True)
                words = [os.path.abspath(__file__), '--run', '--recipe', recipe, '--seed', seed, '--pattern', p,
                         '--dir', rdir, '--root', root, '--quality', a.quality]
                if p == 0 and seed in dump_seeds:
                    words.append('--dump')
                print('\n'.join(str(w).replace('\\', '/') for w in [pdir] + words), flush=True)
                return
    sys.exit(3)


def clear_failed(a):
    """--clear-failed: remove the failed.json of every wanted run, so --next takes them again (floor_runs.sh
    --retry-failed)."""
    _edition, key, root = _root_and_manifest()
    recipes, seeds, patterns, _dump = _wanted(a)
    n = 0
    for seed in seeds:
        for recipe in recipes:
            for p in patterns:
                f = os.path.join(root, f'{recipe}_s{seed}_{a.quality}', 'base' if p == 0 else f'p{p}', 'failed.json')
                if os.path.exists(f):
                    os.remove(f)
                    n += 1
    print(f'[floor] {n} failed run(s) will be taken again', flush=True)


def mark_failed(a):
    """--mark-failed <run folder> --rc N: failed.json with the exit code and the log's tail (floor_runs.sh, after a
    run that left no done.json), so --next passes it over."""
    tail = ''
    try:
        with open(os.path.join(a.mark_failed, 'blender.log'), encoding='utf-8', errors='replace') as f:
            tail = f.read()[-3000:]
    except OSError:
        pass
    B.write_json(os.path.join(a.mark_failed, 'failed.json'),
                 dict(rc=a.rc, log_tail=tail, date=time.strftime('%Y-%m-%d %H:%M:%S')))


def status(a):
    """--status: one line per recipe and seed (which runs are done, failed or missing) and the totals."""
    _edition, key, root = _root_and_manifest()
    recipes, seeds, patterns, _dump = _wanted(a)
    done = failed = missing = 0
    secs = 0.0
    for seed in seeds:
        for recipe in recipes:
            rdir = os.path.join(root, f'{recipe}_s{seed}_{a.quality}')
            marks = []
            for p in patterns:
                pdir = os.path.join(rdir, 'base' if p == 0 else f'p{p}')
                d = B.read_json(os.path.join(pdir, 'done.json'))
                if d is not None:
                    marks.append('ok')
                    done += 1
                    secs += float(d.get('seconds', 0.0))
                elif os.path.exists(os.path.join(pdir, 'failed.json')):
                    marks.append('FAILED')
                    failed += 1
                else:
                    marks.append('-')
                    missing += 1
            print(f'{recipe:18s} seed {seed}: ' + ' '.join(marks), flush=True)
    print(f"[floor] {root}: {done} done ({secs / 60:.1f} min of generation), {failed} failed, {missing} to run",
          flush=True)


# ----------------------------------------------------------------------------------------------- the summary ---

def _choose_boundary(vals):
    """The class boundary (5.4 item 6): 2 % unless a recipe's largest main-level sample sits within a factor of two
    of it; then the geometric middle of the widest gap (in ratio) between neighbouring values from 0.25 % to 25 %."""
    v = sorted(x for x in vals if x is not None and x > 0)
    near = [x for x in v if BOUNDARY / 2 <= x <= BOUNDARY * 2]
    if not near:
        return BOUNDARY, 'provisional (no recipe within a factor of two of 2 %)', None
    best = None
    for x, y in zip(v, v[1:]):
        if x < 0.0025 or y > 0.25:
            continue
        r = y / x
        if best is None or r > best[0]:
            best = (r, x, y)
    if best is None:
        return BOUNDARY, 'provisional (no gap between 0.25 % and 25 %)', None
    return float(np.sqrt(best[1] * best[2])), 'the widest gap', [best[1], best[2]]


def summarise(a):
    edition = B.bare_terrain_package()
    key = B.source_key(edition)
    root = os.path.join(B.parity_root(), a.key or key['folder'])
    out = dict(key=B.read_json(os.path.join(root, 'manifest.json'), {}).get('key'), protocol=PROTOCOL,
               date=time.strftime('%Y-%m-%d %H:%M:%S'), recipes={})
    for name in sorted(os.listdir(root)):
        rdir = os.path.join(root, name)
        if not os.path.isdir(rdir) or '_s' not in name:
            continue
        recipe, rest = name.rsplit('_s', 1)
        seed = rest.split('_', 1)[0]
        base = B.read_json(os.path.join(rdir, 'base', 'run.json'))
        if base is None:
            continue
        samples = []
        for p in range(1, 10):
            s = B.read_json(os.path.join(rdir, f'p{p}', 'sample.json'))
            if s is not None:
                samples.append(s)
        ent = dict(reference=base.get('reference'), base_seconds=base['seconds'], dispatches=base['summary']['dispatches'],
                   samples=len(samples), levels=[])
        for lv in base['levels']:
            ss = [next((x for x in s['levels'] if x['index'] == lv['index']), None) for s in samples]
            ss = [x for x in ss if x is not None]
            rms = [x['rms_over_relief'] for x in ss]
            p99 = [x['p99_abs_over_relief'] for x in ss]
            ov = [x['channel_overlap'] for x in ss if x['channel_overlap'] is not None]
            ent['levels'].append(dict(
                index=lv['index'], role=lv['role'], cell=lv['cell'], n=lv['n'], relief_m=lv['relief_m'],
                rms=rms, p99=p99, overlap=ov,
                tol_rms=max(1.25 * max(rms), 1e-4) if rms else None,
                tol_p99=max(1.25 * max(p99), 1e-4) if p99 else None,
                overlap_min=(min(ov) - (max(ov) - min(ov))) if ov else None))
        judge = {}
        for s in samples:
            for kind, nums in (s.get('judge') or {}).items():
                for k, (b, v) in nums.items():
                    if isinstance(b, (int, float)) and isinstance(v, (int, float)) and not isinstance(b, bool):
                        j = judge.setdefault(k, dict(base=b, values=[]))
                        j['values'].append(v)
        for k, j in judge.items():
            j['max_change'] = max(abs(v - j['base']) for v in j['values'])
        ent['judge'] = judge
        ent['dispatch'] = [dict(same_kernel_sequence=s['dispatch']['same_kernel_sequence'],
                                dispatches_with_other_uniforms=s['dispatch']['dispatches_with_other_uniforms'],
                                first_kernel_difference=s['dispatch']['first_kernel_difference'])
                           for s in samples]
        snap = {}
        for s in samples:
            for k, rec in (s.get('snapshots') or {}).items():
                if not isinstance(rec, dict):
                    continue
                for im, chans in rec.items():
                    if im in ('d', 'base_d', 'missing_in_base') or not isinstance(chans, list):
                        continue
                    cur = snap.setdefault(k, {}).setdefault(im, [None] * len(chans))
                    for c, v in enumerate(chans):
                        if v and v[0] is not None:
                            cur[c] = v[0] if cur[c] is None else max(cur[c], v[0])
        ent['snapshots_max_over_range'] = snap
        out['recipes'].setdefault(recipe, {})[seed] = ent
    vals = {}
    for recipe, seeds in out['recipes'].items():
        m = [max(lv['rms']) for e in seeds.values() for lv in e['levels'] if lv['role'] == 'main' and lv['rms']]
        vals[recipe] = max(m) if m else None
    boundary, why, gap = _choose_boundary(vals.values())
    out['boundary'] = dict(value=boundary, why=why, gap=gap, main_level_largest_rms=vals)
    for recipe, seeds in out['recipes'].items():
        complete = all(e['samples'] >= 5 for e in seeds.values()) and len(seeds) >= 2
        v = vals.get(recipe)
        seeds_cls = None if v is None else ('field' if v < boundary else 'distribution')
        out['recipes'][recipe] = dict(seeds=seeds, main_level_largest_rms=v, class_=seeds_cls,
                                      complete=complete)
    path = os.path.join(root, 'floor.json')
    B.write_json(path, out)
    print(f'[floor] {path}: boundary {boundary:.4g} ({why}); ' + ', '.join(
        f"{r} {e['class_']} ({e['main_level_largest_rms']:.3g})" for r, e in out['recipes'].items()
        if e['main_level_largest_rms'] is not None), flush=True)
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--summarise', action='store_true')
    ap.add_argument('--recipe')
    ap.add_argument('--recipes', default='')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--seeds', default='1,2')
    ap.add_argument('--pattern', type=int, default=0)
    ap.add_argument('--patterns', default='0-5')
    ap.add_argument('--dump', action='store_true')
    ap.add_argument('--dump-seeds', default='1,2')
    ap.add_argument('--dir')
    ap.add_argument('--root')
    ap.add_argument('--key', default='')
    ap.add_argument('--quality', default='draft')
    ap.add_argument('--next', action='store_true')
    ap.add_argument('--clear-failed', action='store_true')
    ap.add_argument('--mark-failed', default='')
    ap.add_argument('--rc', type=int, default=1)
    ap.add_argument('--status', action='store_true')
    a = ap.parse_args(B.script_args())
    if a.run:
        run_one(a)
    elif a.summarise:
        summarise(a)
    elif a.mark_failed:
        mark_failed(a)
    elif a.clear_failed:
        clear_failed(a)
    elif a.next:
        next_run(a)
    elif a.status:
        status(a)
    else:
        ap.error('give --next, --status, --summarise, --clear-failed, --mark-failed or --run (floor_runs.sh starts the '
                 'runs)')


if __name__ == '__main__':
    main()
