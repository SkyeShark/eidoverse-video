"""The four dune families on the port's fields, measured by the Blender package's own dune_measures.py and judged by
test_families' criteria (blender/tests/terrain/wind_sand/test_gpu.py), beside Blender's own measures of its runs.
numpy only (Blender's Python, -I); tests/wind_sand/sim_test.mjs makes the fields and runs this:

    <Blender's python> -I eidoverse/terrain/tests/wind_sand/families.py <dir>

<dir> holds <kind>.npz (h, sand: the field after the run and one cycle, its sand denoised; blocks: the surface at
the end of each block of that cycle) and <kind>.json (cell, winds, slab_cells, iters) for barchan, transverse,
linear and star. Writes <dir>/families.json: the port's measures, the four criteria and their verdicts, Blender's
measures (out/wind_sand/gpu_tests.json, when the Blender package's tests have run) side by side.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', 'parity')))
import _blender as B  # noqa: E402

import numpy as np  # noqa: E402


def main():
    d = B.script_args()[0]
    root = B.bare_terrain_package()
    sys.path.insert(0, os.path.join(root, 'blender', 'tests', 'terrain', 'wind_sand'))
    import dune_measures as DM
    from eidoblend.terrain.solvers import aeolian as A
    m = {}
    for kind in ('barchan', 'transverse', 'linear', 'star'):
        with np.load(os.path.join(d, f'{kind}.npz')) as z:
            h, s, blocks = (np.asarray(z[k], np.float64) for k in ('h', 'sand', 'blocks'))
        info = json.load(open(os.path.join(d, f'{kind}.json'), encoding='utf-8'))
        cell = float(info['cell'])
        winds = [tuple(w) for w in info['winds']]
        thick = 0.25 * float(info['slab_cells']) * cell
        meas = DM.summary(h, cell, s, winds, thick_m=thick)
        main = max(winds, key=lambda w: w[1])[0]
        horns, nb = DM.horns_downwind(s, cell, main, max(thick, 0.5))
        faces = []
        for hb in blocks:
            slope, aspect, _gx, _gy = DM.slope_aspect(hb, cell)
            faces.append(aspect[slope > 20.0])
        cyc_n, cyc_dirs = DM.lee_peaks_of(np.concatenate(faces))
        meas.update(iters=info['iters'], spacing_m=A.spacing_peak(h, cell), relief_m=float(np.ptp(h)),
                    horns_downwind_share=horns, horn_bodies=nb, cycle_lee_peaks=cyc_n, cycle_lee_dirs=cyc_dirs)
        m[kind] = {k: (float(v) if isinstance(v, (np.floating, float)) else (int(v) if isinstance(v, (np.integer,)) else v))
                   for k, v in meas.items()}
    b, tr, li, st = m['barchan'], m['transverse'], m['linear'], m['star']
    downwind = (A.KINDS['transverse']['winds'][0][0] + 180.0) % 360.0
    tr_axis = DM.axis_offset(tr['gradient_dir_deg'], downwind)
    lin_axis = DM.axis_offset(li['gradient_dir_deg'], 90.0)
    fam = {
        'barchan: separate crescents on bare ground, horns downwind (cover < 0.5, >= 10 bodies, the footprint '
        'ahead of the mass in >= 70 % of them)':
            bool(b['sand_cover'] < 0.5 and b['bodies'] >= 10 and b['horns_downwind_share'] >= 0.7),
        'transverse: a continuous sheet of ridges across the wind (cover >= 0.6, gradient within 30 deg of the '
        'wind, lee faces only)': bool(tr['sand_cover'] >= 0.6 and tr_axis <= 30.0 and tr['lee_lee_share'] >= 0.8),
        'linear: ridges along the resultant (coherence >= 0.5, crests within 20 deg of north-south, 2 lee '
        'directions)': bool(li['coherence'] >= 0.5 and lin_axis <= 20.0 and li['lee_peaks'] == 2),
        'star: no ridge direction (coherence < 0.3, against linear\'s >= 0.5) and slip faces in 3 or more '
        'directions over a wind cycle or at its end':
            bool(st['coherence'] < 0.3 and max(st['cycle_lee_peaks'], st['lee_peaks']) >= 3),
    }
    blender = None
    gt = os.path.join(root, 'blender', 'tests', 'terrain', 'out', 'wind_sand', 'gpu_tests.json')
    if os.path.exists(gt):
        blender = json.load(open(gt, encoding='utf-8')).get('four_regimes_four_families', {}).get('detail', {}).get('measures')
    keys = ('sand_cover', 'bodies', 'coherence', 'gradient_dir_deg', 'lee_peaks', 'lee_lee_share', 'lee_stoss_share',
            'horns_downwind_share', 'cycle_lee_peaks', 'slope_p99', 'relief_m', 'spacing_m')
    side = {k: {q: [round(m[k][q], 3) if isinstance(m[k][q], float) else m[k][q],
                    (blender or {}).get(k, {}).get(q)] for q in keys if q in m[k]} for k in m}
    out = dict(port=m, families=fam, all=all(fam.values()), blender=blender, side_by_side=side,
               note='each pair: [port, Blender]; Blender: its own GPU runs of test_families (gpu_tests.json)',
               versions=B.versions())
    B.write_json(os.path.join(d, 'families.json'), out)
    print(f"[families] {'all four families' if out['all'] else 'NOT all families'}: " +
          ', '.join(f"{k.split(':')[0]} {v}" for k, v in fam.items()), flush=True)


if __name__ == '__main__':
    main()
