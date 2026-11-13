"""Dune-field growth variants on one periodic box, for looking side by side (the slab model is scale-free in cells,
so a box at the growth level's cell and cells-per-spacing grows what the recipe's growth level grows, a quarter of the
area). In Blender (GPU):

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/terrain/wind_sand/sweep_box.py --variants <file.json> --tag name

<file.json>: [[label, {"n": 512, "cell": 15.625, "iters": 27000, "snaps": [9000, 18000], "seed": 1,
                       "set": {...dune_field / slab model params...}}], ...]
Each variant: dune_field's resolve_params (kind star unless set), start_fields over the box (periodic), the growth
run (grow_tile's loop: grow_phases or grow_iters, whole wind cycles), the same denoise. Writes
out/wind_sand/box_<tag>/<label>.npz (h, sand, bed and the snapshots' h) and <label>.json (params, timing, the
measures at each snapshot). look_box.py draws them.
"""
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TERRAIN_TESTS = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TERRAIN_TESTS, 'core'))
sys.path.insert(0, HERE)
import plain_import  # noqa: E402
plain_import.install()

import numpy as np  # noqa: E402
from eidoblend.terrain.core import levels as L  # noqa: E402
from eidoblend.terrain.solvers import aeolian as A  # noqa: E402
import dune_measures as DM  # noqa: E402

OUT = os.path.join(TERRAIN_TESTS, 'out', 'wind_sand')


def args():
    a = plain_import.script_args()
    opt = dict(tag='box', variants='')
    i = 0
    while i < len(a):
        opt[a[i].lstrip('-')] = a[i + 1]
        i += 2
    return opt


def run_variant(label, v, out):
    """The production growth (aeolian.grow_tile: pre-passes, the growth run with its checks, the denoise) on an
    n x n periodic box of `cell` metres; v['iters'] sets grow_iters (and grow_min_iters) unless the set gives them."""
    n = int(v.get('n', 512))
    cell = float(v.get('cell', 15.625))
    seed = int(v.get('seed', 1))
    st = dict({'kind': 'star'}, **(v.get('set') or {}))
    if v.get('iters'):
        st.setdefault('grow_iters', int(v['iters']))
        st.setdefault('grow_min_iters', int(v['iters']))
    p = A.resolve_params(st)
    lv = L.Level(0, 'main', 0.0, 0.0, n * cell, cell, n)
    t0 = time.perf_counter()
    tile = A.grow_tile(lv, p, seed, log=lambda m: print(m, flush=True))
    b, s = tile['bed'], tile['sand']
    h = b + s
    m = DM.summary(h, cell, s, p['winds'], thick_m=0.5)
    slope = DM.slope_aspect(h, cell)[0]
    m.update(iters=tile['iters'] + tile.get('prepass_iters', 0), spacing_m=A.spacing_peak(h, cell),
             dune_height_m=A.dune_height(s), seconds=round(time.perf_counter() - t0, 2),
             frac_lt5=float(np.mean(slope < 5.0)))
    meas = [dict(hh, kind='history') for hh in tile['history']] + [m]
    np.savez_compressed(os.path.join(out, f'{label}.npz'), h=h.astype(np.float32), sand=s.astype(np.float32),
                        bed=b.astype(np.float32), snaps=np.zeros((0, n, n), np.float32), cell=cell)
    with open(os.path.join(out, f'{label}.json'), 'w', encoding='utf-8') as fo:
        json.dump(dict(label=label, variant=v, params={k: val for k, val in p.items() if not callable(val)},
                       measures=meas), fo, indent=1, default=str)
    print(f'[sweep] {label}: {m["iters"]} it in {m["seconds"]} s; dunes {m["dune_height_m"]:.0f} m (target '
          f'{p["target_height_m"]:.0f}), spacing {m["spacing_m"]:.0f} m (target {p["spacing_m"]:.0f}), cover '
          f'{m["sand_cover"]:.2f}, p99 {m["slope_p99"]:.1f}, lee peaks {m["lee_peaks"]}', flush=True)


def main():
    opt = args()
    variants = json.load(open(opt['variants'], encoding='utf-8'))
    out = os.path.join(OUT, 'box_' + opt['tag'])
    os.makedirs(out, exist_ok=True)
    for label, v in variants:
        try:
            run_variant(label, v, out)
        except Exception:                                          # noqa: BLE001
            print(f'[sweep] {label} failed:\n{traceback.format_exc()}', flush=True)
    os._exit(0)


main()
