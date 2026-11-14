"""Design probe (PORT_PLAN.md section 4.4): the chaos floor of the Blender edition itself. The port's kernels can only
agree with the GLSL kernels to float rounding (1e-7 .. 3e-5 of a field's range per dispatch), and a few thousand
erosion steps amplify any such difference. So the parity tolerance for whole runs is measured here, on the source of
truth alone: each recipe generated twice as it is (determinism: bit for bit), then once more with every erosion run's
start height moved by one float32 ulp on a random half of the cells (FluvialRun, the backbone every eroding stage
runs on: fluvial, volcano aging, layered-rock fluvial). The difference between the first and the perturbed run is
what a perfect port still shows.

    bash run_blender.sh eidoverse/terrain/tests/design_probes/blender_chaos_floor.py -- <out.json> [recipe ...]

The Blender edition is found at blender/ beside eidoverse/ in this checkout, else at $EIDO_BLENDER_EDITION.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def blender_edition():
    for root in (os.path.normpath(os.path.join(HERE, '..', '..', '..', '..')), os.environ.get('EIDO_BLENDER_EDITION', '')):
        if root and os.path.isdir(os.path.join(root, 'blender', 'eidoblend', 'terrain', 'core')):
            return root
    sys.exit('blender_chaos_floor: no Blender edition here or at $EIDO_BLENDER_EDITION')


sys.path.insert(0, os.path.join(blender_edition(), 'blender'))
import numpy as np  # noqa: E402

from eidoblend.terrain import api as A  # noqa: E402
from eidoblend.terrain.core import metrics as M  # noqa: E402
from eidoblend.terrain.solvers import fluvial as FL  # noqa: E402

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
OUT = args[0]
RECIPES = args[1:] or ['fluvial_range', 'stratovolcano', 'canyon']
KEYS = ('relief_m', 'hypsometric_integral', 'slope_p10', 'slope_p50', 'slope_p90', 'slope_p99', 'frac_slope_lt5',
        'depression_area_frac', 'spectrum_slope', 'spectrum_knee_m', 'anisotropy_4', 'anisotropy_8', 'cliff_pair_frac')

_orig_init = FL.FluvialRun.__init__
PERTURB = {'on': False, 'runs': 0}


def _perturbed_init(self, dev, cell, fields, *a, **k):
    if PERTURB['on']:
        h = np.asarray(fields['h'], np.float32)
        rng = np.random.default_rng(1000 + PERTURB['runs'])
        up = rng.random(h.shape) < 0.25
        dn = rng.random(h.shape) < 0.25
        hp = np.where(up, np.nextafter(h, np.float32(np.inf)), np.where(dn, np.nextafter(h, np.float32(-np.inf)), h))
        fields = dict(fields)
        fields['h'] = hp.astype(np.float32)
        PERTURB['runs'] += 1
    _orig_init(self, dev, cell, fields, *a, **k)


FL.FluvialRun.__init__ = _perturbed_init


def gen(recipe):
    t0 = time.perf_counter()
    t = A.generate(recipe, seed=1, quality='draft', cache=False, log=lambda m: None)
    return t, time.perf_counter() - t0


def channels(f, cell):
    a = np.asarray(f.get('A', np.zeros_like(f['h'])), np.float64)
    return a > max(1e6, 400 * cell * cell)


res = {'quality': 'draft', 'seed': 1, 'perturbation': 'every FluvialRun start: +1 ulp on 25 % of cells, -1 ulp on 25 %',
       'recipes': {}}
for rec in RECIPES:
    try:
        t1, s1 = gen(rec)
        t2, s2 = gen(rec)
        PERTURB['on'], PERTURB['runs'] = True, 0
        t3, s3 = gen(rec)
        PERTURB['on'] = False
    except Exception as e:  # noqa: BLE001
        res['recipes'][rec] = {'error': f'{type(e).__name__}: {e}'}
        print(rec, 'ERROR', e, flush=True)
        continue
    levels = []
    for i, lv in enumerate(t1.levels):
        h1 = np.asarray(t1.fields(i)['h'], np.float64)
        h2 = np.asarray(t2.fields(i)['h'], np.float64)
        h3 = np.asarray(t3.fields(i)['h'], np.float64)
        rel = float(np.ptp(h1))
        d = h3 - h1
        c1, c3 = channels(t1.fields(i), lv.cell), channels(t3.fields(i), lv.cell)
        inter, union = int((c1 & c3).sum()), int((c1 | c3).sum())
        levels.append({'level': str(lv), 'bit_identical_rerun': bool(np.array_equal(h1, h2)),
                       'rms_over_relief': float(np.sqrt(np.mean(d * d)) / max(rel, 1e-9)),
                       'p99_abs_over_relief': float(np.percentile(np.abs(d), 99) / max(rel, 1e-9)),
                       'max_abs_m': float(np.max(np.abs(d))), 'relief_m': rel,
                       'channel_jaccard': inter / union if union else 1.0})
    main = t1.main
    m1 = M.metrics(np.asarray(t1.fields('main')['h'], np.float64), main.cell)
    m3 = M.metrics(np.asarray(t3.fields('main')['h'], np.float64), main.cell)
    res['recipes'][rec] = {'seconds': [round(s1, 1), round(s2, 1), round(s3, 1)], 'perturbed_runs': PERTURB['runs'],
                           'levels': levels,
                           'main_metrics_delta': {k: [m1.get(k), m3.get(k)] for k in KEYS}}
    print(rec, json.dumps(res['recipes'][rec]), flush=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=1, default=float)
print('RESULT', json.dumps(res, default=float), flush=True)
