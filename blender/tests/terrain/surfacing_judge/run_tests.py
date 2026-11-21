#!/usr/bin/env python3
"""run_tests.py: the surfacing round's tests in one run (the surface data, the material, the looks, the plants and the
judge), PASS / FAIL per test, from anywhere with system Python:

    python blender/tests/terrain/surfacing_judge/run_tests.py              # all of them
    python blender/tests/terrain/surfacing_judge/run_tests.py --list       # the manifest, in the order it runs
    python blender/tests/terrain/surfacing_judge/run_tests.py --kinds py   # plain Python only
    python blender/tests/terrain/surfacing_judge/run_tests.py --only plants --failed --resume ...

The runner is blender/tests/run_all.py's (its kinds, logs, PASS / FAIL / SKIP rules, --resume and --failed), given
this manifest; blender/tests/terrain/integration/run_tests.py runs the landform packages' tests the same way. GPU
tests queue through EIDO_GPU_WRAP when it is set (blender/tests/_where.py). Logs and summary.json go to
blender/tests/terrain/out/surfacing_judge/tests/ (git-ignored). The package each test belongs to is in its area's
name: surface_data (1, the surface data), surfacing (2, the material), surface_look (3, the looks), plants (4),
surfacing_judge (5, the judge and the integration).
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))                    # blender/tests/terrain
TESTS = os.path.normpath(os.path.join(TN, '..'))                   # blender/tests
sys.path.insert(0, TESTS)

import run_all as R  # noqa: E402


def t(kind, pkg, script, *args, **k):
    return R.T(kind, f'terrain/{pkg}', script, *args, **k)


M = []
# 1. the surface data: the twins and the stored bakes in plain Python, then the GPU parities
M += [t('py', 'surface_data', s) for s in ('test_bake_small.py', 'test_relief.py', 'test_seams.py',
                                            'test_drainage.py')]
M += [t('gpu', 'surface_data', s) for s in ('test_expr.py', 'test_kernels.py', 'test_noise.py')]
# 2. the material: the unit tests (no render), then the per-texel material on baked data
M += [t('bl', 'surfacing', 'test_surfacing.py'), t('gpu', 'surfacing', 'test_material_data.py', timeout=5400)]
# 3. the looks: every palette, recipe and place resolves and checks, and every recipe's cache key equals HEAD's
M += [t('py', 'surface_look', s) for s in ('test_look.py', 'test_cache_keys.py')]
# 4. the plants: planning in numpy, then the instancing in Blender
M += [t('py', 'plants', 'test_plants.py', timeout=3600), t('gpu', 'plants', 'test_instances.py', timeout=3600)]
# 5. the judge's measures, then make_terrain with its surface and plants end to end, and the guide's examples
M += [t('py', 'surfacing_judge', 'test_measures.py'),
      t('gpu', 'surfacing_judge', 'test_integration.py', timeout=3600),
      t('gpu', 'surfacing_judge', 'test_guide.py', timeout=3600)]


def main():
    R.M = M
    R.AREA_ORDER = []
    for x in M:
        if x.area not in R.AREA_ORDER:
            R.AREA_ORDER.append(x.area)
    argv = sys.argv[1:]
    R.OUT = os.path.join(TN, 'out', 'surfacing_judge', 'tests')
    if '--out' in argv:
        i = argv.index('--out')
        R.OUT = os.path.abspath(argv[i + 1])
        del argv[i:i + 2]
    if not any(a == '--kinds' or a.startswith('--kinds=') for a in argv):
        argv += ['--kinds', 'py,bl,gpu']
    sys.argv = [sys.argv[0]] + argv
    return R.main()


if __name__ == '__main__':
    sys.exit(main())
