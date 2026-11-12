"""The fluvial package's acceptance in one record (design section 11, row 3), from what the other scripts wrote:

    python blender/tests/terrain/fluvial/acceptance.py --gen <out/fluvial/gen> \
        --range r6_fluvial_range_s1,r6_fluvial_range_s2 --hills r6_rh_d --meadow r6_meadow_s1 \
        --hero r5_fluvial_range_s1_hero --det r4_det_a,r4_det_b

  kernels      out/fluvial/kernel_tests.json (test_kernels.py): every kernel against its twin, creep and threshold
               conserving the sum of h within 1e-5, the fluvial stage deterministic, the step cost
  bands        the judge's verdict of each generated main level against its reference (judge_fields.py wrote
               <tag>_verdict.json); the meadow's own checks (slope p99 < 15 degrees, no closed depressions)
  seams        every child level against its parent (<tag>_seams.json): |dh| <= 0.05 m on the edge ring, slope jump
               <= 3 degrees on the outer two rings
  determinism  two runs of one recipe and seed, every level's fields compared bit for bit
Writes out/fluvial/acceptance.json and prints the table.
"""
import argparse
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'fluvial'))


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gen', default=os.path.join(OUT, 'gen'))
    ap.add_argument('--range', default='')
    ap.add_argument('--hills', default='')
    ap.add_argument('--meadow', default='')
    ap.add_argument('--hero', default='')
    ap.add_argument('--det', default='')
    a = ap.parse_args()
    rec = {'checks': []}

    def check(name, ok, detail):
        rec['checks'].append(dict(check=name, passed=bool(ok), detail=detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    kt = os.path.join(OUT, 'kernel_tests.json')
    if os.path.exists(kt):
        k = load(kt)
        fails = [f for f in k.get('failed', []) if 'fluvial step' not in f]
        par = {n: v for n, v in k.items() if n.startswith('parity') and isinstance(v, dict) and 'ok' in v}
        check('every kernel against its twin', all(v['ok'] for v in par.values()) and par,
              f"{sum(v['ok'] for v in par.values())}/{len(par)} parity checks; worst ratio "
              f"{max(k.get('parity_worst', {0: 0}).values()):.2g} (tolerance 1e-4)")
        con = k.get('conservation', {})
        check('creep and threshold conserve the sum of h within 1e-5', all(v['rel_sum_change'] <= 1e-5
                                                                          for v in con.values()) and con,
              ', '.join(f"{n} {v['rel_sum_change']:.1e}" for n, v in con.items()))
        det = [n for n in k if n.startswith('determinism')]
        check('the fluvial stage is deterministic', det and all(k[n]['ok'] for n in det), det[0] if det else None)
        rec['cost'] = k.get('cost')
        rec['kernel_failures'] = fails
    for group, tags in (('fluvial_range', a.range), ('rolling_hills', a.hills), ('meadow', a.meadow)):
        for tag in [t for t in tags.split(',') if t]:
            v = load(os.path.join(a.gen, tag + '_verdict.json'))
            if group == 'meadow':
                check(f'{group} {tag}: slope p99 < 15 deg, no pits', v['passed'],
                      f"p99 {v['numbers']['slope_p99']:.1f}, depressions {v['numbers']['depression_area_frac']:.4f}")
            else:
                rows = [r for r in v['rows'] if r.get('passed') is not None]
                bad = [f"{r['metric']} {r['gen']:.3g} (band {r['band']})" for r in rows if not r['passed']]
                check(f'{group} {tag} against {v["reference"]}', not bad,
                      f"{sum(r['passed'] for r in rows)}/{len(rows)} bands" + (f'; failing: {bad}' if bad else ''))
    for tag in [t for t in (a.range + ',' + a.hills + ',' + a.meadow + ',' + a.hero).split(',') if t]:
        p = os.path.join(a.gen, tag + '_seams.json')
        if os.path.exists(p):
            s = load(p)
            ok = all(r['edge_max_dh_m'] <= 0.05 and r['edge_slope_jump_deg'] <= 3.0 for r in s)
            check(f'seams {tag}', ok, ', '.join(f"{r['child_cell_m']:.3g} m: |dh| {r['edge_max_dh_m']:.3f}, jump "
                                                f"{r['edge_slope_jump_deg']:.2f}" for r in s))
    if a.det:
        x, y = a.det.split(',')
        A = np.load(os.path.join(a.gen, x + '_levels.npz'))
        B = np.load(os.path.join(a.gen, y + '_levels.npz'))
        same = all(np.array_equal(A[k], B[k]) for k in A.files)
        check('a whole recipe is deterministic on one machine', same, f'{len(A.files)} arrays over every level')
    with open(os.path.join(OUT, 'acceptance.json'), 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1, default=str)


main()
