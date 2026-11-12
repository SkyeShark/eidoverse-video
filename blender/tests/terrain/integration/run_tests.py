#!/usr/bin/env python3
"""run_tests.py: every terrain package's tests in one run, PASS / FAIL per test (system Python, from anywhere):

    python blender/tests/terrain/integration/run_tests.py              # all of them
    python blender/tests/terrain/integration/run_tests.py --list       # the manifest, in the order it runs
    python blender/tests/terrain/integration/run_tests.py --kinds py   # plain Python only (numpy twins, no Blender)
    python blender/tests/terrain/integration/run_tests.py --only karst # the tests whose name contains a text
    python blender/tests/terrain/integration/run_tests.py --failed     # again, the ones the last run did not pass
    ... --slots heavy.sh              # the GPU slots it may use, in order (default heavy.sh, heavy2.sh, heavy3.sh)
    ... --out <folder>                # logs and summary.json elsewhere (default out/integration/tests/)
    ... --rejudge                     # the last run's logs read again (no test runs): summary.json rewritten
    ... --rerun test_mesh,test_karst  # these tests again, the last run's other results carried into summary.json

The runner is blender/tests/run_all.py's (the same logs, PASS / FAIL / SKIP rules, --resume and --failed), given
the terrain family's manifest below, which run_all.py itself leaves out. The kinds:

    py   plain Python with numpy (the kernels' twins, the judge, masks, the analytic profiles): no Blender, no GPU
    bl   Blender with no kernel and no render (the import smoke, the surfacing unit tests, the loft parity)
    gpu  Blender through a GPU slot (the main checkout's heavy.sh, heavy2.sh, heavy3.sh, or the --slots given,
         retried every 60 s while all are busy): every test that dispatches a kernel (the GPU-twin parities,
         make_terrain) or renders

Each package's CPU tests run first, then its GPU tests, one at a time. Logs (one per test) and summary.json go to
blender/tests/terrain/out/integration/tests/ (git-ignored). A PASS is a test's own verdict; the recipes are judged
against their places by recipe_sheets.py, beside this.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))                    # blender/tests/terrain
TESTS = os.path.normpath(os.path.join(TN, '..'))                   # blender/tests
sys.path.insert(0, TESTS)

import run_all as R  # noqa: E402  (the whole branch's runner: its machinery, this family's manifest)

NR = '--no-render'


def py(pkg, script, *args, **k):
    return R.T('py', f'terrain/{pkg}' if pkg else 'terrain', script, *args, **k)


def bl(pkg, script, *args, **k):
    return R.T('bl', f'terrain/{pkg}' if pkg else 'terrain', script, *args, **k)


def gpu(pkg, script, *args, **k):
    return R.T('gpu', f'terrain/{pkg}' if pkg else 'terrain', script, *args, **k)


M = []
# integration (13): the deletions of design section 3 and the moves, then the import smoke of every module
M += [py('integration', 'test_deletions.py'), bl('integration', 'test_imports.py')]
# core (1)
M += [py('core', s) for s in ('test_core.py', 'test_metrics.py', 'test_twins.py')]
M += [gpu('core', 'test_gpu.py')]
# judge (2)
M += [py('judge', 'test_judge.py')]
# fluvial backbone and hydrology (3)
M += [gpu('fluvial', 'test_kernels.py')]
# masks (4)
M += [py('masks', 'test_masks.py')]
# mesh and API (5): the ring mesh in numpy, then real_place Lauterbrunnen through the runner, every part of the
# acceptance (synthetic, place, api, cracks), and the seams' creases on real data
M += [py('mesh_api', 'test_mesh.py'), gpu('mesh_api', 'test_api.py'), gpu('mesh_api', 'test_api_blender.py'),
      gpu('mesh_api', 'test_seam_crease.py')]
# surfacing and dressing (6): the unit tests, then the shimmer probe and its metric (bar: OLD_AUTO). The metric is
# queued with the renders ('gpy'), so it reads this run's frames, not an earlier run's
M += [bl('surfacing', 'test_surfacing.py'), gpu('surfacing', 'test_shimmer.py', '--tag', 'integration'),
      R.T('gpy', 'terrain/surfacing', 'shimmer_metric.py', 'integration', vram=1,
          tag='the shimmer metric of the probe above')]
# glacial (7)
M += [py('glacial', 'test_twins.py'), gpu('glacial', 'test_gpu.py')]
# wind and sand (8)
M += [py('wind_sand', 'test_twins.py'), gpu('wind_sand', 'test_gpu.py')]
# volcanoes and craters (9)
M += [py('volcanoes_craters', s) for s in ('test_profiles.py', 'test_references.py', 'test_aging.py')]
# layered rock (10)
M += [py('layered_rock', 'test_strata.py'), gpu('layered_rock', 'test_kernels.py')]
# karst and coast (11)
M += [py('karst', 'test_karst.py'), py('coast', 'test_coast.py'), gpu('coast', 'test_coast_gpu.py')]
# detail (12)
M += [py('detail', 'test_detail_twins.py'), gpu('detail', 'test_detail_gpu.py')]
# the family's tools for built geometry (kept as they were) and their probes on make_terrain's ground
M += [bl('', 'test_loft.py', NR, tag='loft against the engine (no render)')]
M += [gpu('', s) for s in ('test_placement.py', 'test_kit.py', 'test_layer_surface.py', 'test_relief.py',
                           'test_loft.py')]


_JUDGE = R.judge
_PASS_LINE = re.compile(r'^(\s*\[PASS\].*)$', re.M)


def judge(rc, text):
    """run_all's verdict, where a line its test marks [PASS] stays a pass line even when it reports a FAIL it was
    looking for (the judge's tests: "[PASS] ekigar_volcano_fails: vs mount_fuji: FAIL on [...]")."""
    return _JUDGE(rc, _PASS_LINE.sub(lambda m: m.group(1).replace('FAIL', 'fail'), text))


def rejudge(out):
    """Read the last run's logs again with this judge (no test runs): summary.json rewritten."""
    path = os.path.join(out, 'summary.json')
    d = json.load(open(path, encoding='utf-8'))
    for r in d['results']:
        log = os.path.join(R.ROOT, r.get('log', '')) if r.get('log') else None
        if not log or not os.path.exists(log) or r['status'] == 'NOT RUN':
            continue
        text = open(log, encoding='utf-8', errors='replace').read().split('\n\n', 1)[-1]
        m = re.search(r'\[run_all\] TIMEOUT', text)
        rc = 'timeout' if m else (1 if r['status'] == 'FAIL' and 'exit ' in r.get('detail', '') else 0)
        if rc == 'timeout':
            continue
        r['status'], r['detail'] = judge(rc, text)
    d['counts'] = {s: sum(1 for r in d['results'] if r['status'] == s) for s in ('PASS', 'FAIL', 'SKIP', 'NOT RUN')}
    d['rejudged'] = time.strftime('%Y-%m-%d %H:%M')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(d, f, indent=1)
    for r in d['results']:
        print(f"{r['status']:7s} {r['test']}" + (f"  -- {r['detail']}" if r['status'] != 'PASS' else ''))
    print(d['counts'])
    return 1 if d['counts']['FAIL'] else 0


def _take(argv, flag, default):
    """Remove `flag VALUE` from argv (run_all's parser does not know it) and return VALUE or the default."""
    if flag in argv:
        i = argv.index(flag)
        value = argv[i + 1]
        del argv[i:i + 2]
        return value
    return default


def main():
    R.M = M
    R.AREA_ORDER = []
    for t in M:
        if t.area not in R.AREA_ORDER:
            R.AREA_ORDER.append(t.area)
    argv = sys.argv[1:]
    R.OUT = os.path.abspath(_take(argv, '--out', os.path.join(TN, 'out', 'integration', 'tests')))
    R.judge = judge
    if '--rejudge' in argv:
        return rejudge(R.OUT)
    rerun = _take(argv, '--rerun', '')
    if rerun:                                  # these tests again, the rest of the last run carried over
        path = os.path.join(R.OUT, 'summary.json')
        d = json.load(open(path, encoding='utf-8'))
        texts = [s for s in rerun.split(',') if s]
        for r in d['results']:
            if any(s in r['test'] for s in texts):
                r['status'], r['detail'] = 'NOT RUN', 'to be run again (--rerun)'
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(d, f, indent=1)
        partial = os.path.join(R.OUT, 'summary.partial.json')
        if os.path.exists(partial):
            os.remove(partial)
        argv.append('--resume')
    # the GPU slots to use, in order (default all three; --slots heavy.sh keeps to one when the shared ledger in
    # work/.gpu_jobs/ reserves one slot for this work)
    slots = [s for s in _take(argv, '--slots', 'heavy.sh,heavy2.sh,heavy3.sh').split(',') if s]
    if R.SLOTS:                                          # the main checkout's slot scripts are here
        unknown = [s for s in slots if s not in R.SLOTS]
        if unknown or not slots:
            sys.exit(f'run_tests: --slots {",".join(slots)}: the slots here are {", ".join(R.SLOTS)}')
        R.SLOTS = slots
    if not any(a == '--kinds' or a.startswith('--kinds=') for a in argv):
        argv += ['--kinds', 'py,bl,gpu,gpy']             # run_all's import smoke covers the other families
    sys.argv = [sys.argv[0]] + argv
    return R.main()


if __name__ == '__main__':
    sys.exit(main())
