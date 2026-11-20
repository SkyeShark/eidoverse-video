"""The karst evaluate's own floor (PORT_PLAN.md 5.3, 5.4): how far karst.py's evaluate (numpy, Blender's Python)
moves at the same world cells when its window moves. The tower loop works in window-local float32 metres
(karst.py: "window-local metres: float32 keeps millimetres here"), so a window shifted by whole cells rounds every
subsample's offset from each tower differently; where the rock is steep in plan (a wall table rising up to 57 m per
metre at a foot's notch, the buried rock at tan 85 degrees, the talus gate's slope in azimuth) that last bit becomes
millimetres. For each karst.evaluate fixture window of tests/out/karst_coast/fixtures, numpy's evaluate is run again
from windows shifted by whole cells and compared with the fixture's own on the overlap: per field, the largest
|difference| over the samples, its share of the field's range, and the cells over 1e-5 and 1e-4 of the range.
tests/karst_coast/evaluate_test.mjs grades the port against max(1e-5 x range, 1.25 x this floor).

    <blender python> -I eidoverse/terrain/tests/karst_coast/karst_window_floor.py [--only "hero 2 m,film"]

Writes tests/out/karst_coast/fixtures/window_floor.json. Needs the Blender edition ($EIDO_BLENDER_EDITION)."""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'parity'))
import _blender  # noqa: E402

_blender.bare_terrain_package()
import numpy as np  # noqa: E402
from eidoblend.terrain.solvers import karst as K  # noqa: E402

FIX = os.path.join(HERE, '..', 'out', 'karst_coast', 'fixtures')
SHIFTS = ((16, 16), (-8, 24), (5, -11))        # whole cells: a tile, then shifts that are not
FIELDS = ('h', 'bed', 'deposit', 'talus', 'water', 'plain')


def array(spec):
    return np.fromfile(os.path.join(FIX, spec['file']), dtype={'f32': '<f4', 'f64': '<f8', 'i32': '<i4'}[spec['dtype']]
                       ).reshape(spec['shape'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default=None)
    a = ap.parse_args()
    only = a.only.split(',') if a.only else None
    m = json.load(open(os.path.join(FIX, 'manifest.json')))
    out_path = os.path.join(FIX, 'window_floor.json')
    record = json.load(open(out_path)) if os.path.exists(out_path) else {}
    record['_doc'] = __doc__.split('\n\n')[0]
    plans = {}
    for c in m['cases']:
        if c['function'] != 'karst.evaluate' or (only and not any(o in c['label'] for o in only)):
            continue
        g = c['args']
        if g['plan'] not in plans:
            plans[g['plan']] = K.plan_karst(g['seed'], g['domain'], g['params'], g['via'], g['main'])
        plan = plans[g['plan']]
        n, cell = g['n'], g['cell']
        want = {k: array(c['outputs'][k]).astype(np.float64) for k in FIELDS}
        row = {'shifts': [list(s) for s in SHIFTS], 'fields': {}}
        t0 = time.time()
        for si, sj in SHIFTS:
            o = K.evaluate(plan, g['x0'] + si * cell, g['y0'] + sj * cell, cell, n)
            # the overlap: fixture cells [max(0, s), min(n, n + s)) are the shifted window's [.. - s]
            ai, bi = max(0, si), min(n, n + si)
            aj, bj = max(0, sj), min(n, n + sj)
            for k in FIELDS:
                w = want[k]
                rng = float(w.max() - w.min()) or 1.0
                d = np.abs(w[aj:bj, ai:bi] - o[k].astype(np.float64)[aj - sj:bj - sj, ai - si:bi - si])
                f = row['fields'].setdefault(k, {'range': rng, 'max': 0.0, 'over': 0.0, 'n1e5': 0, 'n1e4': 0})
                if d.max() > f['max']:
                    jj, ii = np.unravel_index(int(np.argmax(d)), d.shape)
                    f.update(max=float(d.max()), over=float(d.max()) / rng, at=[int(ii + ai), int(jj + aj)])
                f['n1e5'] = max(f['n1e5'], int((d > 1e-5 * rng).sum()))
                f['n1e4'] = max(f['n1e4'], int((d > 1e-4 * rng).sum()))
        row['seconds'] = round(time.time() - t0, 2)
        record[c['label']] = row
        print(c['label'][:64], ' '.join(f"{k} {f['over']:.2e} ({f['n1e5']})" for k, f in row['fields'].items()), flush=True)
    with open(out_path, 'w') as fh:
        json.dump(record, fh, indent=1)
    print('->', out_path)


if __name__ == '__main__':
    main()
