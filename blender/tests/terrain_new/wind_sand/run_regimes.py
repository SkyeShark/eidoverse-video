"""The four wind regimes on one periodic box (design 4.6's table; package 8's test "the four wind regimes give four
different dune families", and "one wind gives slip faces on the lee side"). In Blender (GPU):

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/terrain_new/wind_sand/run_regimes.py [--n 256] [--cell 4] [--iters 6000] \\
        [--kinds star,barchan,transverse,linear] [--tag name] [--set key=value ...]

Each kind starts from the same kind of start (dune_field's start_fields: a flat bed, a sand sheet of the kind's
thickness with a supply variation, a seed at the target spacing) on an n x n periodic box of `cell` metres, and runs
its own wind regime. Snapshots (h, sand) go to out/wind_sand/regimes<tag>/<kind>.npz and every measure (dune_measures)
to <kind>.json; sheet_regimes.py lays them out.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'core'))
sys.path.insert(0, HERE)
import plain_import  # noqa: E402
plain_import.install()

import numpy as np  # noqa: E402
from eidoblend.terrain.core import levels as L  # noqa: E402
from eidoblend.terrain.solvers import aeolian as A  # noqa: E402
import dune_measures as DM  # noqa: E402

# the box each kind runs in: the sand and spacing scaled to a 1 km box (the slab model has no scale of its own
# beyond the cell: these are the kinds' proportions)
BOX = {
    'barchan': dict(sand_m=1.0, spacing_m=150.0, supply_var=0.5),
    'transverse': dict(sand_m=6.0, spacing_m=150.0),
    'linear': dict(sand_m=6.0, spacing_m=200.0),
    'star': dict(sand_m=8.0, spacing_m=200.0),
}


def parse():
    a = plain_import.script_args()
    opt = dict(n=256, cell=4.0, iters=6000, kinds='star,barchan,transverse,linear', tag='', snaps='500,1500,3000,6000')
    sets = {}
    i = 0
    while i < len(a):
        k = a[i].lstrip('-')
        if k == 'set':
            kk, vv = a[i + 1].split('=', 1)
            try:
                sets[kk] = json.loads(vv)
            except json.JSONDecodeError:
                sets[kk] = vv
            i += 2
            continue
        opt[k] = a[i + 1]
        i += 2
    return opt, sets


def main():
    opt, sets = parse()
    n, cell, iters = int(opt['n']), float(opt['cell']), int(opt['iters'])
    snaps = sorted({int(s) for s in str(opt['snaps']).split(',') if s} | {iters})
    out = os.path.join(plain_import.OUT, '..', 'wind_sand', 'regimes' + (('_' + opt['tag']) if opt['tag'] else ''))
    out = os.path.normpath(out)
    os.makedirs(out, exist_ok=True)
    lv = L.Level(0, 'main', 0.0, 0.0, n * cell, cell, n)
    for kind in [k for k in opt['kinds'].split(',') if k]:
        p = A.resolve_params(dict(BOX.get(kind, {}), kind=kind, **sets))
        bed, sand = A.start_fields(lv, p, seed=3, period_m=lv.side)
        bed[:] = 0.0                                                   # a flat bed: the box is about the sand
        sim = A.SandSim(bed, sand, cell, A.T.BOUND_PERIODIC, p, seed=11)
        total0 = float(np.sum(sand, dtype=np.float64))
        shots, meas = [], []
        t0 = time.perf_counter()
        done = 0
        for target in snaps:
            done += sim.run(p['winds'], target - done) if target > done else 0
            b, s = sim.read()
            s = A.denoise(s, float(p['smooth_cells']), periodic=True)    # what a level's run hands on
            h = b + s
            m = DM.summary(h, cell, s, p['winds'], thick_m=0.25 * p['slab_cells'] * cell)
            m.update(iters=done, seconds=round(time.perf_counter() - t0, 2),
                     spacing_m=A.spacing_peak(h, cell), mass_rel_change=float(np.sum(s, dtype=np.float64) / total0 - 1))
            meas.append(m)
            shots.append((done, h.astype(np.float32), s.astype(np.float32)))
            print(f'[regimes] {kind} {done} it {m["seconds"]} s: relief {m["relief_m"]:.2f} m, p99 {m["slope_p99"]:.1f}, '
                  f'max {m["slope_max"]:.1f}, lee peaks {m["lee_peaks"]} {m["lee_peak_dirs"]}, grad dir '
                  f'{m["gradient_dir_deg"]:.0f} coh {m["coherence"]:.2f}, cover {m["sand_cover"]:.2f}, bodies '
                  f'{m["bodies"]}, spacing {m["spacing_m"]:.0f} m, mass {m["mass_rel_change"]:.2e}', flush=True)
        np.savez_compressed(os.path.join(out, f'{kind}.npz'), iters=np.array([s[0] for s in shots]),
                            h=np.stack([s[1] for s in shots]), sand=np.stack([s[2] for s in shots]), cell=cell)
        with open(os.path.join(out, f'{kind}.json'), 'w') as f:
            json.dump(dict(kind=kind, params={k: v for k, v in p.items() if not callable(v)}, n=n, cell=cell,
                           measures=meas), f, indent=1, default=str)


main()
