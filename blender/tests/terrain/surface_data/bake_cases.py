"""Bake the surface data of the test terrains (snapshots, _cases.py) on the GPU, timed, cached in the test's own
folder, and optionally make and save the atlas images:

    bash run_blender.sh blender/tests/terrain/surface_data/bake_cases.py --case toroweap [--case canyon ...]
        [--all] [--images] [--palette] [--maps masks] [--again]
    (queue it with EIDO_GPU_WRAP on a shared machine: blender/tests/_where.py)

Per case: out/surface_data/cache/<case>/surface_<key>_L<i>.npz (the bake, read by the sheets and the seam test in
plain Python), out/surface_data/bake_<case>.json (per-level timings: cold, then a cache hit; image times; memory).
--images makes every family's image (timed) and saves them to out/surface_data/images/<case>/. --again bakes a
second time cold (the timing of a warm GPU and driver: kernels compiled, nothing cached).
"""
import json
import os
import shutil
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _cases as C  # noqa: E402


def bake_one(name, args, log=print):
    from eidoblend.terrain import surface as S
    from eidoblend.terrain.surface import atlas as AT
    from eidoblend.terrain.surface import maps as MP
    rec = dict(case=name)
    t0 = time.perf_counter()
    t = C.terrain(name)
    rec['load_seconds'] = round(time.perf_counter() - t0, 2)
    rec['levels'] = [str(lv) for lv in t.levels]
    folder = os.path.join(C.OUT, 'cache', name)
    opts = {}
    if '--maps' in args:
        opts['maps'] = args[args.index('--maps') + 1]
    pal = C.CASES[name].get('palette') if '--palette' in args else None
    runs = []
    for k in range(2 if '--again' in args else 1):
        if os.path.isdir(folder) and k == 0 and '--keep' not in args:
            shutil.rmtree(folder)
        if k == 1:
            shutil.rmtree(folder, ignore_errors=True)
        t1 = time.perf_counter()
        sd = S.bake_surface(t, palette=pal, options=opts, cache=folder, log=log)
        runs.append(dict(cold=True, seconds=round(time.perf_counter() - t1, 3), bake=sd.info.get('seconds'),
                         levels=sd.info.get('levels'), palette=sd.info.get('palette_bake'),
                         bake_hit=bool(sd.info.get('cache_hit'))))
    t2 = time.perf_counter()
    sd = S.bake_surface(t, palette=pal, options=opts, cache=folder, log=log)
    runs.append(dict(cold=False, seconds=round(time.perf_counter() - t2, 3)))
    rec['runs'] = runs
    rec['key'] = sd.key
    rec['names'] = sd.names()
    rec['info'] = {k: v for k, v in sd.info.items() if k not in ('levels',)}
    if '--images' in args:
        t3 = time.perf_counter()
        imgs = sd.images()
        rec['images_seconds'] = round(time.perf_counter() - t3, 3)
        rec['image_seconds'] = sd.info.get('image_seconds')
        rec['images'] = {f: [im.size[0], im.size[1]] for f, im in imgs.items()}
        rec['memory_mb'] = {f: round(AT.megabytes(sd.layouts[f], MP.FAMILIES['M' if f.startswith('M') else f]
                                                  ['format']), 1) for f in imgs}
        t4 = time.perf_counter()
        rec['saved'] = sd.save_images(os.path.join(C.OUT, 'images', name))
        rec['save_seconds'] = round(time.perf_counter() - t4, 3)
    rec['describe'] = sd.describe()
    with open(os.path.join(C.OUT, f'bake_{name}.json'), 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1, default=str)
    log(f"[bake_cases] {name}: cold {runs[0]['seconds']} s, hit {runs[-1]['seconds']} s"
        + (f", images {rec.get('images_seconds')} s" if '--images' in args else ''))
    log(sd.describe())
    return rec


def main():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    names = [a[i + 1] for i, v in enumerate(a) if v == '--case' and i + 1 < len(a)]
    if '--all' in a:
        names = list(C.CASES)
    if not names:
        print(f'bake_cases: --case one of {", ".join(C.CASES)} (or --all)')
        return 2
    rc = 0
    for name in names:
        try:
            bake_one(name, a)
        except Exception:                                    # noqa: BLE001 - reported; the other cases go on
            traceback.print_exc()
            rc = 1
        sys.stdout.flush()
    return rc


if __name__ == '__main__':
    code = main()
    sys.stdout.flush()
    os._exit(code)
