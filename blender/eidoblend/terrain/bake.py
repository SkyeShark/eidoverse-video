"""Bake a terrain from the command line (design section 8): fill the cache and write the preview PNGs, so an agent can
try a recipe without building a scene.

    bash run_blender.sh blender/eidoblend/terrain/bake.py --recipe dunes --size 6000 --seed 3 --out <dir>
    bash run_blender.sh blender/eidoblend/terrain/bake.py --recipe real_place --param dem=lauterbrunnen \\
        --focus 480,1640 --out <dir>
    bash run_blender.sh blender/eidoblend/terrain/bake.py --describe real_place

Options: --recipe NAME (or a recipe .json), --size M, --resolution N, --seed N, --quality draft|film|hero,
--focus X,Y[;X,Y...], --hero-cell M, --context K, --param KNOB=VALUE (repeatable; numbers parsed) or --params JSON,
--no-cache, --save (also write the terrain: <out>/<name>.npz + .json), --name NAME, --list, --describe NAME.
Writes <out>/<name>_main_hillshade.png, _hero_hillshade.png, _mask_<name>.png and <name>_bake.json (the plan, the
timings, the cache key, the main tile's metrics). The level runner's kernels need Blender, so bake through a GPU
slot (--list and --describe need neither).
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))

from eidoblend.terrain import api as A  # noqa: E402


def _value(s):
    try:
        return json.loads(s)
    except ValueError:
        return s


def parse(argv):
    ap = argparse.ArgumentParser(prog='bake.py', description='bake a terrain: cache + preview PNGs')
    ap.add_argument('--recipe')
    ap.add_argument('--size', type=float)
    ap.add_argument('--resolution', type=int)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--quality', default='film', choices=('draft', 'film', 'hero'))
    ap.add_argument('--focus', help='x,y or x,y;x,y;... in metres')
    ap.add_argument('--hero-cell', type=float)
    ap.add_argument('--context', type=float)
    ap.add_argument('--param', action='append', default=[], help='knob=value (repeatable)')
    ap.add_argument('--params', help='the knobs as a JSON object')
    ap.add_argument('--no-cache', action='store_true')
    ap.add_argument('--save', action='store_true')
    ap.add_argument('--name')
    ap.add_argument('--out', default='.')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--describe')
    return ap.parse_args(argv)


def main(argv=None):
    if argv is None:
        argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    a = parse(argv)
    if a.list:
        for k, v in A.recipes().items():
            print(f'{k:22s} {v}')
        return 0
    if a.describe:
        A.describe(a.describe)
        return 0
    if not a.recipe:
        print('bake.py: --recipe is required (--list shows them)', file=sys.stderr)
        return 2
    recipe = a.recipe
    if recipe.lower().endswith('.json') and os.path.isfile(recipe):
        with open(recipe, encoding='utf-8') as f:
            recipe = json.load(f)
    params = json.loads(a.params) if a.params else {}
    for kv in a.param:
        k, _, v = kv.partition('=')
        params[k.strip()] = _value(v.strip())
    focus = None
    if a.focus:
        pts = [tuple(float(c) for c in p.split(',')) for p in a.focus.split(';') if p.strip()]
        focus = pts[0] if len(pts) == 1 else pts
    t0 = time.perf_counter()
    t = A.generate(recipe, size=a.size, resolution=a.resolution, seed=a.seed, params=params, focus=focus,
                   hero_cell=a.hero_cell, context=a.context, quality=a.quality, cache=not a.no_cache)
    name = a.name or (t.recipe.name + (f"_{params['dem']}" if 'dem' in params else '') + f'_s{a.seed}')
    os.makedirs(a.out, exist_ok=True)
    files = t.preview(os.path.join(a.out, name))
    if a.save:
        files.append(t.save(os.path.join(a.out, name)))
    try:
        m = t.metrics()
    except Exception as e:                                # the judge's numbers are a courtesy here
        m = {'error': f'{type(e).__name__}: {e}'}
    rec = dict(recipe=t.recipe.name, knobs=t.knobs, seed=a.seed, quality=a.quality, cache_key=t.info['cache_key'],
               cache_hit=t.info['cache_hit'], seconds=dict(t.info['seconds'], bake=round(time.perf_counter() - t0, 2)),
               levels=[str(lv) for lv in t.levels], triangles=t.ring.triangle_count,
               skipped_stages=t.info['skipped_stages'], warnings=t.info['warnings'], metrics=m, files=files)
    with open(os.path.join(a.out, name + '_bake.json'), 'w', encoding='utf-8') as f:
        json.dump(A._plain(rec), f, indent=1)
    A._summary(t, print)
    print(f'[bake] {len(files)} files in {a.out}', flush=True)
    return 0


if __name__ == '__main__':
    code = main()
    if code:
        sys.exit(code)
