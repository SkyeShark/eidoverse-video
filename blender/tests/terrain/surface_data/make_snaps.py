"""Make the surface-data tests' terrain snapshots (Blender, a GPU job per terrain: the level runner's kernels):

    bash run_blender.sh blender/tests/terrain/surface_data/make_snaps.py --case toroweap [--case canyon ...] [--force]
    bash run_blender.sh blender/tests/terrain/surface_data/make_snaps.py --all
    (on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py; set EIDO_TERRAIN_CACHE_GB above the
    terrain cache's size so a cache miss here does not prune other tests' terrains)

Each case (_cases.CASES) is generated at the judge's settings (seed 1, film quality, hero levels on its focus) and
saved to blender/tests/terrain/out/surface_data/snap/<case>.npz + .json (about 0.5 GB each). A case whose snapshot
exists is skipped unless --force. Writes snap/<case>_make.json (the plan, the timings, the cache key).
"""
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _cases as C  # noqa: E402


def main():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    names = [a[i + 1] for i, v in enumerate(a) if v == '--case' and i + 1 < len(a)]
    if '--all' in a:
        names = list(C.CASES)
    bad = [n for n in names if n not in C.CASES]
    if bad or not names:
        print(f'make_snaps: --case one of {", ".join(C.CASES)} (or --all); unknown: {bad}')
        return 2
    rc = 0
    for name in names:
        p = C.snap_path(name)
        if os.path.exists(p) and '--force' not in a:
            print(f'[make_snaps] {name}: snapshot exists ({p}); --force remakes it', flush=True)
            continue
        t0 = time.time()
        try:
            t = C.generate(name)
        except Exception:                                    # noqa: BLE001 - reported, the other cases go on
            traceback.print_exc()
            rc = 1
            continue
        rec = dict(case=name, seconds=round(time.time() - t0, 1), levels=[str(lv) for lv in t.levels],
                   cache_key=t.info.get('cache_key'), cache_hit=t.info.get('cache_hit'),
                   timings=t.info.get('seconds'), skipped=t.info.get('skipped_stages'),
                   fields=sorted(t.fields('main').keys()), masks=t.masks.names())
        with open(os.path.join(C.SNAP, name + '_make.json'), 'w', encoding='utf-8') as f:
            json.dump(rec, f, indent=1, default=str)
        print(f"[make_snaps] {name}: {len(t.levels)} levels in {rec['seconds']} s -> {p}", flush=True)
    return rc


if __name__ == '__main__':
    code = main()
    sys.stdout.flush()
    os._exit(code)
